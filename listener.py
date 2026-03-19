<<<<<<< codex/remove-gps-features-from-code
import re
=======
>>>>>>> main
import signal
import subprocess
import sys
import time
<<<<<<< codex/remove-gps-features-from-code
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
        cmd = [MMCLI_BIN, *args]
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
=======

import requests
import serial

from config import (
    AT_PORT,
    BAUD,
    SERIAL_POLL_INTERVAL,
    SMS_PROMPT_TIMEOUT,
    SMS_SEND_TIMEOUT,
    WEBHOOK_URL,
)
from sms_db import get_queued_sms, init_db, mark_outbox, save_sms


FINAL_RESPONSE_TOKENS = ("\r\nOK\r\n", "\r\nERROR\r\n", "+CMS ERROR:", "+CME ERROR:")


def normalize_number(number):
    """Keep only valid phone-number characters for AT+CMGS."""
>>>>>>> main
    cleaned = (number or "").strip().replace(" ", "")
    allowed = "+0123456789"
    cleaned = "".join(ch for ch in cleaned if ch in allowed)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


<<<<<<< codex/remove-gps-features-from-code
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
=======
def read_until(ser, expected=None, timeout=5, initial_wait=0.2):
    """Read serial data until one of the expected tokens is found or timeout expires."""
    buffer = ""
    expected = tuple(expected or ())
    deadline = time.time() + timeout

    if initial_wait > 0:
        time.sleep(initial_wait)

    while time.time() < deadline:
        waiting = getattr(ser, "in_waiting", 0)
        chunk = ser.read(waiting or 1).decode(errors="ignore")
        if chunk:
            buffer += chunk
            if expected and any(token in buffer for token in expected):
                break
        else:
            time.sleep(0.1)

    return buffer


def send_at(ser, cmd, timeout=5, expected=None):
    """Send AT command and return response."""
    expected_tokens = expected or FINAL_RESPONSE_TOKENS
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    ser.flush()
    return read_until(ser, expected=expected_tokens, timeout=timeout)


def send_sms(ser, number, text):
    """Send SMS message and return success flag + modem response."""
    normalized_number = normalize_number(number)
    body = (text or "").strip()

    if not normalized_number:
        return False, "Invalid phone number"
    if not body:
        return False, "Message body is empty"

    send_at(ser, "AT+CMGF=1", timeout=3)
    send_at(ser, 'AT+CSCS="IRA"', timeout=3)

    ser.reset_input_buffer()
    ser.write(f'AT+CMGS="{normalized_number}"\r'.encode())
    ser.flush()

    prompt_response = read_until(ser, expected=(">", "ERROR", "+CMS ERROR:", "+CME ERROR:"), timeout=SMS_PROMPT_TIMEOUT)
    if ">" not in prompt_response:
        return False, prompt_response or "No prompt received for AT+CMGS"

    ser.write(body.encode("utf-8") + b"\x1A")
    ser.flush()

    response = read_until(ser, expected=FINAL_RESPONSE_TOKENS, timeout=SMS_SEND_TIMEOUT)
    success = "+CMGS:" in response and "OK" in response and "ERROR" not in response
    return success, response


def init_modem(ser):
    """Initialize modem with AT commands required for SMS."""
    checks = [
        ("AT", 3),
        ("ATE0", 3),
        ("AT+CMGF=1", 3),
        ('AT+CSCS="IRA"', 3),
        ("AT+CPMS=\"ME\",\"ME\",\"ME\"", 5),
        ("AT+CNMI=2,1,0,2,1", 5),
    ]

    for cmd, timeout in checks:
        response = send_at(ser, cmd, timeout=timeout)
        if "OK" not in response:
            raise RuntimeError(f"Command failed: {cmd} -> {response.strip()}")

    print("✅ Modem initialized for SMS")
    return True


def handle_delivery(_line):
    """Handle SMS delivery report."""
    print("📬 Delivery report received")


def handle_incoming_sms(ser, header_line):
    text = ser.readline().decode(errors="ignore").strip()
    parts = [part.strip().strip('"') for part in header_line.split(",")]
    number = parts[1] if len(parts) > 1 else "Unknown"

    print(f"📩 SMS from {number}: {text}")
    save_sms("IN", number, text)

    try:
        requests.post(WEBHOOK_URL, json={"from": number, "text": text}, timeout=2)
    except Exception as exc:
        print(f"⚠️ Webhook error: {exc}")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
>>>>>>> main
    print("\n🛑 Shutting down...")
    sys.exit(0)


<<<<<<< codex/remove-gps-features-from-code
def init_modem(client: ModemManagerClient):
    info = client.modem_info()
    if "state:" not in info.lower():
        raise MmcliError("ModemManager không trả về trạng thái modem hợp lệ")
    print(f"✅ ModemManager ready for modem {MODEM_ID}")


def main():
=======
def main():
    """Main listener loop."""
>>>>>>> main
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_db()
<<<<<<< codex/remove-gps-features-from-code
    client = ModemManagerClient()

    try:
        init_modem(client)
    except MmcliError as exc:
        print(f"❌ Failed to initialize ModemManager: {exc}")
        sys.exit(1)

    print("📡 Listener running via ModemManager")
=======

    try:
        ser = serial.Serial(AT_PORT, BAUD, timeout=1)
        print(f"✅ AT port opened: {AT_PORT}")
    except serial.SerialException as exc:
        print(f"❌ Failed to open AT port {AT_PORT}: {exc}")
        print("   Make sure the device is connected and permissions are correct")
        sys.exit(1)

    try:
        init_modem(ser)
    except Exception as exc:
        print(f"❌ Failed to initialize modem: {exc}")
        ser.close()
        sys.exit(1)

    print("📡 Listener running")
>>>>>>> main

    try:
        while True:
            try:
<<<<<<< codex/remove-gps-features-from-code
                send_outbox_messages(client)
=======
                for outbox_id, number, text in get_queued_sms():
                    print(f"📤 Sending SMS to {number}")
                    mark_outbox(outbox_id, "PROCESSING")
                    success, response = send_sms(ser, number, text)

                    if success:
                        mark_outbox(outbox_id, "SENT")
                        print("✅ SMS sent successfully")
                    else:
                        error_message = (response or "Unknown modem error").strip().replace("\n", " ")[:200]
                        mark_outbox(outbox_id, "FAILED", error_message)
                        print(f"❌ SMS send failed: {error_message}")
>>>>>>> main
            except Exception as exc:
                print(f"⚠️ Error processing outbox: {exc}")

            try:
<<<<<<< codex/remove-gps-features-from-code
                import_inbox(client)
            except Exception as exc:
                print(f"⚠️ Error importing inbox: {exc}")

            time.sleep(MODEM_POLL_INTERVAL)
=======
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    time.sleep(SERIAL_POLL_INTERVAL)
                    continue

                if line.startswith("+CMT:"):
                    handle_incoming_sms(ser, line)
                elif line.startswith("+CDS"):
                    handle_delivery(line)
            except serial.SerialException as exc:
                print(f"⚠️ Serial read error: {exc}")
                time.sleep(1)
            except Exception as exc:
                print(f"⚠️ Error processing incoming SMS: {exc}")

            time.sleep(SERIAL_POLL_INTERVAL)
>>>>>>> main
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as exc:
        print(f"❌ Fatal error: {exc}")
    finally:
<<<<<<< codex/remove-gps-features-from-code
=======
        ser.close()
>>>>>>> main
        print("👋 Listener stopped")


if __name__ == "__main__":
    main()
