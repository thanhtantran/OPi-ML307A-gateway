import signal
import sys
import time

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
    cleaned = (number or "").strip().replace(" ", "")
    allowed = "+0123456789"
    cleaned = "".join(ch for ch in cleaned if ch in allowed)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


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
    print("\n🛑 Shutting down...")
    sys.exit(0)


def main():
    """Main listener loop."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_db()

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

    try:
        while True:
            try:
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
            except Exception as exc:
                print(f"⚠️ Error processing outbox: {exc}")

            try:
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
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as exc:
        print(f"❌ Fatal error: {exc}")
    finally:
        ser.close()
        print("👋 Listener stopped")


if __name__ == "__main__":
    main()
