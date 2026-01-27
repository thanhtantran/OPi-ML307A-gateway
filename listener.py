import serial
import time
import requests
from config import PORT, BAUD, WEBHOOK_URL
from sms_db import (
    init_db, save_sms,
    get_queued_sms, mark_outbox
)

def send_at(ser, cmd, wait=0.5):
    ser.write((cmd + "\r").encode())
    time.sleep(wait)
    return ser.read_all().decode(errors="ignore")

def send_sms(ser, number, text):
    send_at(ser, "AT+CMGF=1")
    ser.write(f'AT+CMGS="{number}"\r'.encode())
    time.sleep(0.3)
    ser.write(text.encode() + b"\x1A")
    time.sleep(3)
    return ser.read_all().decode(errors="ignore")

def init_modem(ser):
    send_at(ser, "AT")
    send_at(ser, "AT+CMGF=1")
    send_at(ser, 'AT+CSCS="GSM"')
    send_at(ser, "AT+CNMI=2,1,0,2,1")
    #            │ │ │ │ └ delivery report
    #            │ │ │ └ realtime SMS
    print("✅ Modem initialized")

def handle_delivery(line):
    # +CDS: <length><CR><LF>PDU...
    save_sms("OUT", "", "", "DELIVERED")
    print("📬 Delivery report")

def main():
    init_db()
    ser = serial.Serial(PORT, BAUD, timeout=1)
    init_modem(ser)

    print("📡 Listener running")

    while True:
        # ===== OUTBOX =====
        for id, number, text in get_queued_sms():
            print(f"📤 Sending SMS to {number}")
            resp = send_sms(ser, number, text)

            if "OK" in resp:
                mark_outbox(id, "SENT")
                save_sms("OUT", number, text, "SENT")
            else:
                mark_outbox(id, "FAILED")
                save_sms("OUT", number, text, "FAILED")

        # ===== INCOMING =====
        line = ser.readline().decode(errors="ignore").strip()

        if line.startswith("+CMT:"):
            header = line
            text = ser.readline().decode(errors="ignore").strip()
            number = header.split(",")[1].replace('"', '')

            print(f"📩 SMS from {number}: {text}")
            save_sms("IN", number, text)

            try:
                requests.post(
                    WEBHOOK_URL,
                    json={"from": number, "text": text},
                    timeout=2
                )
            except:
                pass

        elif line.startswith("+CDS"):
            handle_delivery(line)

        time.sleep(0.2)

if __name__ == "__main__":
    main()
