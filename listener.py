"""
Listener service - runs as systemd service.
Handles: outbox polling (send SMS) + realtime SMS receive via +CMT.
Does NOT serve HTTP. Only reads/writes SQLite DB.
"""
import signal
import sys
import time

import requests

from config import DELETE_IMPORTED_SMS, MODEM_POLL_INTERVAL, SERIAL_BAUD, SERIAL_PORT, WEBHOOK_URL
from ml307 import ML307, ML307Error
from sms_db import get_queued_sms, init_db, mark_outbox, save_sms, sms_ref_exists


def normalize_number(number: str) -> str:
    cleaned = (number or "").strip().replace(" ", "")
    cleaned = "".join(ch for ch in cleaned if ch in "+0123456789")
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


def send_outbox_messages(modem: ML307):
    for outbox_id, number, text in get_queued_sms():
        normalized = normalize_number(number)
        body = (text or "").strip()

        if not normalized:
            mark_outbox(outbox_id, "FAILED", "Số điện thoại không hợp lệ")
            continue
        if not body:
            mark_outbox(outbox_id, "FAILED", "Nội dung tin nhắn trống")
            continue

        try:
            print(f"📤 Gửi SMS đến {normalized}")
            mark_outbox(outbox_id, "PROCESSING")
            resp = modem.send_sms(normalized, body)
            mark_outbox(outbox_id, "SENT", resp[:200])
            print(f"✅ Gửi thành công")
        except ML307Error as exc:
            error_msg = str(exc).replace("\n", " ")[:200]
            mark_outbox(outbox_id, "FAILED", error_msg)
            print(f"❌ Gửi thất bại: {error_msg}")


def import_unread(modem: ML307):
    for msg in modem.list_sms("REC UNREAD"):
        index = msg["index"]
        if sms_ref_exists("IN", index):
            continue
        number = msg.get("number", "Unknown")
        text = msg.get("text", "")
        print(f"📩 SMS #{index} từ {number}")
        save_sms("IN", number, text, "RECEIVED", ref=index)
        _fire_webhook(number, text, index)
        if DELETE_IMPORTED_SMS:
            modem.delete_sms(index)


def _fire_webhook(number, text, index=None):
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json={"from": number, "text": text, "index": index}, timeout=2)
    except Exception as exc:
        print(f"⚠️ Webhook error: {exc}")


def listen_realtime(modem: ML307):
    """Block-read loop for +CMT push notifications."""
    print("📡 Realtime listener running...")
    last_poll = 0

    while True:
        # Non-blocking poll every MODEM_POLL_INTERVAL seconds
        now = time.time()
        if now - last_poll >= MODEM_POLL_INTERVAL:
            try:
                send_outbox_messages(modem)
                import_unread(modem)
            except Exception as exc:
                print(f"⚠️ Poll error: {exc}")
            last_poll = time.time()

        # Read one line (timeout=1s set on serial port)
        try:
            line = modem.readline()
            if not line:
                continue
            if line.startswith("+CMT:"):
                parts = line.split(",")
                number = parts[0].split(":")[1].replace('"', '').strip()
                text = modem.readline()
                print(f"📩 [realtime] SMS từ {number}: {text}")
                save_sms("IN", number, text, "RECEIVED")
                _fire_webhook(number, text)
        except Exception as exc:
            print(f"⚠️ Read error: {exc}")
            time.sleep(1)


def main():
    def _stop(sig, frame):
        print("\n🛑 Listener stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    init_db()

    print(f"🔌 Connecting to modem on {SERIAL_PORT}...")
    for attempt in range(10):
        try:
            modem = ML307(port=SERIAL_PORT, baud=SERIAL_BAUD)
            modem.init()
            break
        except ML307Error as exc:
            print(f"⏳ Attempt {attempt + 1}/10: {exc}")
            time.sleep(3)
    else:
        print("❌ Cannot connect to modem after 10 attempts. Exiting.")
        sys.exit(1)

    listen_realtime(modem)


if __name__ == "__main__":
    main()
