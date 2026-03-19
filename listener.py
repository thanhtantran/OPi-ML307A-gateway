import re
import signal
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional

import requests

from config import DELETE_IMPORTED_SMS, MMCLI_BIN, MODEM_ID, MODEM_POLL_INTERVAL, WEBHOOK_URL
from sms_db import get_queued_sms, init_db, mark_outbox, save_sms, sms_ref_exists


SMS_PATH_RE = re.compile(r"/org/freedesktop/ModemManager1/SMS/(\d+)")
FIELD_RE = re.compile(r"^\s*(?P<key>[A-Za-z ]+?)\s*\|\s*(?P<value>.*)$")
CONTINUATION_RE = re.compile(r"^\s*\|\s*(?P<value>.*)$")


class MmcliError(RuntimeError):
    pass


class ModemManagerClient:
    def __init__(self, runner: Optional[Callable[..., subprocess.CompletedProcess]] = None):
        self.runner = runner or subprocess.run

    def _run(self, *args: str) -> str:
        cmd = ["sudo", MMCLI_BIN, *args]
        try:
            result = self.runner(cmd, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise MmcliError(f"Không tìm thấy lệnh {MMCLI_BIN}: {exc}") from exc
        if result.returncode != 0:
            raise MmcliError((result.stderr or result.stdout or "mmcli failed").strip())
        return result.stdout.strip()

    @staticmethod
    def _escape_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    @staticmethod
    def _extract_sms_id(text: str) -> int:
        match = SMS_PATH_RE.search(text)
        if not match:
            raise MmcliError(f"Không tìm thấy SMS ID trong phản hồi: {text}")
        return int(match.group(1))

    @staticmethod
    def parse_sms_list(output: str) -> List[Dict[str, str]]:
        sms_entries: List[Dict[str, str]] = []
        for line in output.splitlines():
            match = re.search(r"/SMS/(\d+) \(([^)]+)\)", line)
            if match:
                sms_entries.append({"id": int(match.group(1)), "state": match.group(2).strip()})
        return sms_entries

    @staticmethod
    def parse_sms_details(output: str) -> Dict[str, str]:
        details: Dict[str, str] = {}
        current_section = None
        multiline_key = None

        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            field_match = FIELD_RE.match(line)
            if field_match:
                current_section = field_match.group("key").strip().lower().replace(" ", "_")
                value = field_match.group("value").strip()
            else:
                continuation_match = CONTINUATION_RE.match(line)
                if not continuation_match or current_section is None:
                    continue
                value = continuation_match.group("value").strip()

            if not value:
                continue

            if ":" in value:
                subkey, subvalue = value.split(":", 1)
                multiline_key = subkey.strip().lower().replace(" ", "_")
                details[multiline_key] = subvalue.strip()
            elif multiline_key:
                details[multiline_key] = f"{details[multiline_key]}\n{value}".strip()

            if current_section and current_section not in details:
                details[current_section] = value

        return details

    def modem_info(self) -> str:
        return self._run("-m", MODEM_ID)

    def create_sms(self, number: str, text: str) -> int:
        payload = f'--messaging-create-sms=text="{self._escape_value(text)}",number="{self._escape_value(number)}"'
        output = self._run("-m", MODEM_ID, payload)
        return self._extract_sms_id(output)

    def send_sms(self, sms_id: int) -> str:
        return self._run("-s", str(sms_id), "--send")

    def list_sms(self) -> List[Dict[str, str]]:
        return self.parse_sms_list(self._run("-m", MODEM_ID, "--messaging-list-sms"))

    def get_sms(self, sms_id: int) -> Dict[str, str]:
        details = self.parse_sms_details(self._run("-s", str(sms_id)))
        details["id"] = sms_id
        return details

    def delete_sms(self, sms_id: int) -> str:
        return self._run("-s", str(sms_id), "--delete")


def normalize_number(number: str) -> str:
    cleaned = (number or "").strip().replace(" ", "")
    allowed = "+0123456789"
    cleaned = "".join(ch for ch in cleaned if ch in allowed)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


def send_outbox_messages(client: ModemManagerClient):
    for outbox_id, number, text in get_queued_sms():
        normalized_number = normalize_number(number)
        body = (text or "").strip()

        if not normalized_number:
            mark_outbox(outbox_id, "FAILED", "Invalid phone number")
            continue
        if not body:
            mark_outbox(outbox_id, "FAILED", "Message body is empty")
            continue

        try:
            print(f"📤 Tạo SMS cho {normalized_number}")
            mark_outbox(outbox_id, "PROCESSING")
            modem_sms_id = client.create_sms(normalized_number, body)
            print(f"📨 ModemManager SMS ID: {modem_sms_id}")
            response = client.send_sms(modem_sms_id)
            mark_outbox(outbox_id, "SENT", response[:200], modem_sms_id=modem_sms_id)
            print(f"✅ SMS sent successfully: {response}")
        except MmcliError as exc:
            error_message = str(exc).replace("\n", " ")[:200]
            mark_outbox(outbox_id, "FAILED", error_message)
            print(f"❌ SMS send failed: {error_message}")


def import_inbox(client: ModemManagerClient):
    for entry in client.list_sms():
        sms_id = entry["id"]
        state = entry["state"].lower()
        if state != "received":
            continue
        if sms_ref_exists("IN", sms_id):
            continue

        try:
            details = client.get_sms(sms_id)
        except MmcliError as exc:
            print(f"⚠️ Không đọc được SMS {sms_id}: {exc}")
            continue

        number = details.get("number", "Unknown")
        text = details.get("text", "")
        print(f"📩 Imported SMS #{sms_id} from {number}")
        save_sms("IN", number, text, "RECEIVED", ref=sms_id)

        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"from": number, "text": text, "sms_id": sms_id}, timeout=2)
            except Exception as exc:
                print(f"⚠️ Webhook error: {exc}")

        if DELETE_IMPORTED_SMS:
            try:
                client.delete_sms(sms_id)
                print(f"🗑️ Deleted SMS #{sms_id} from modem storage")
            except MmcliError as exc:
                print(f"⚠️ Không xóa được SMS {sms_id}: {exc}")


def signal_handler(sig, frame):
    print("\n🛑 Shutting down...")
    sys.exit(0)


def init_modem(client: ModemManagerClient):
    info = client.modem_info()
    if "state:" not in info.lower():
        raise MmcliError("ModemManager không trả về trạng thái modem hợp lệ")
    print(f"✅ ModemManager ready for modem {MODEM_ID}")


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_db()
    client = ModemManagerClient()

    try:
        init_modem(client)
    except MmcliError as exc:
        print(f"❌ Failed to initialize ModemManager: {exc}")
        sys.exit(1)

    print("📡 Listener running via ModemManager")

    try:
        while True:
            try:
                send_outbox_messages(client)
            except Exception as exc:
                print(f"⚠️ Error processing outbox: {exc}")

            try:
                import_inbox(client)
            except Exception as exc:
                print(f"⚠️ Error importing inbox: {exc}")

            time.sleep(MODEM_POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as exc:
        print(f"❌ Fatal error: {exc}")
    finally:
        print("👋 Listener stopped")


if __name__ == "__main__":
    main()
