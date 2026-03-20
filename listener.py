import threading
import time

import requests

from config import DELETE_IMPORTED_SMS, MODEM_POLL_INTERVAL, WEBHOOK_URL
from ml307 import ML307, ML307Error
from sms_db import get_queued_sms, mark_outbox, save_sms, sms_ref_exists


def normalize_number(number: str) -> str:
    cleaned = (number or "").strip().replace(" ", "")
    allowed = "+0123456789"
    cleaned = "".join(ch for ch in cleaned if ch in allowed)
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
            print(f"✅ Gửi thành công: {resp}")
        except ML307Error as exc:
            error_msg = str(exc).replace("\n", " ")[:200]
            mark_outbox(outbox_id, "FAILED", error_msg)
            print(f"❌ Gửi thất bại: {error_msg}")


def import_inbox(modem: ML307):
    for msg in modem.list_sms("REC UNREAD"):
        index = msg["index"]
        if sms_ref_exists("IN", index):
            continue

        number = msg.get("number", "Unknown")
        text = msg.get("text", "")
        print(f"📩 SMS #{index} từ {number}: {text}")
        save_sms("IN", number, text, "RECEIVED", ref=index)

        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"from": number, "text": text, "index": index}, timeout=2)
            except Exception as exc:
                print(f"⚠️ Webhook error: {exc}")

        if DELETE_IMPORTED_SMS:
            modem.delete_sms(index)
            print(f"🗑️ Đã xóa SMS #{index} khỏi modem")


def _sms_callback(number: str, text: str, index: int = None):
    """Called when +CMT pushes a new SMS in realtime."""
    if index is not None and sms_ref_exists("IN", index):
        return
    print(f"📩 [realtime] SMS từ {number}: {text}")
    save_sms("IN", number, text, "RECEIVED", ref=index)

    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"from": number, "text": text}, timeout=2)
        except Exception as exc:
            print(f"⚠️ Webhook error: {exc}")


def _listen_loop(modem: ML307):
    """Realtime +CMT listener running in its own thread."""
    print("📡 Realtime SMS listener started")
    while True:
        try:
            line = modem.readline()
            if line.startswith("+CMT:"):
                # +CMT: "<number>","","<timestamp>"
                parts = line.split(",")
                number = parts[0].split(":")[1].replace('"', '').strip()
                text_line = modem.readline()
                _sms_callback(number, text_line)
        except Exception as exc:
            print(f"❌ Listener error: {exc}")
            time.sleep(1)


def _poll_loop(modem: ML307):
    """Periodic outbox sender + inbox sync."""
    while True:
        try:
            send_outbox_messages(modem)
        except Exception as exc:
            print(f"⚠️ Outbox error: {exc}")

        try:
            import_inbox(modem)
        except Exception as exc:
            print(f"⚠️ Inbox sync error: {exc}")

        time.sleep(MODEM_POLL_INTERVAL)


def start_listener(modem: ML307):
    """Start listener and poll threads. Call once from app.py."""
    t_listen = threading.Thread(target=_listen_loop, args=(modem,), daemon=True, name="sms-listener")
    t_poll = threading.Thread(target=_poll_loop, args=(modem,), daemon=True, name="sms-poll")
    t_listen.start()
    t_poll.start()
    print("🚀 Listener threads started")
