import re
import time
import serial


class ML307Error(RuntimeError):
    pass


class ML307:
    def __init__(self, port="/dev/ml307-at", baud=115200, timeout=1):
        try:
            self.ser = serial.Serial(port, baud, timeout=timeout)
        except serial.SerialException as e:
            raise ML307Error(f"Không mở được cổng {port}: {e}") from e

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_at(self, cmd: str, wait=0.5) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode())
        time.sleep(wait)
        return self.ser.read_all().decode(errors="ignore")

    # ===== INIT =====
    def init(self):
        resp = self.send_at("AT")
        if "OK" not in resp:
            raise ML307Error("Modem không phản hồi AT")
        self.send_at("AT+CMGF=1")          # text mode
        self.send_at('AT+CSCS="GSM"')      # GSM charset
        self.send_at("AT+CNMI=2,2,0,0,0")  # push SMS realtime via +CMT
        print("✅ Modem initialized")

    # ===== SEND SMS =====
    def send_sms(self, number: str, text: str) -> str:
        self.ser.reset_input_buffer()
        self.ser.write(b"AT+CMGF=1\r")
        time.sleep(0.3)
        self.ser.write(f'AT+CMGS="{number}"\r'.encode())
        time.sleep(0.3)
        self.ser.write(text.encode() + b"\x1A")  # Ctrl+Z to send
        time.sleep(3)
        resp = self.ser.read_all().decode(errors="ignore")
        if "ERROR" in resp:
            raise ML307Error(f"Gửi SMS thất bại: {resp.strip()}")
        return resp.strip()

    # ===== LIST SMS =====
    def list_sms(self, box="ALL"):
        resp = self.send_at(f'AT+CMGL="{box}"', wait=1)
        messages = []
        lines = resp.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith("+CMGL:"):
                header = lines[i]
                text = lines[i + 1] if i + 1 < len(lines) else ""
                parts = header.split(",")
                try:
                    index = int(parts[0].split(":")[1].strip())
                    status = parts[1].replace('"', '').strip()
                    number = parts[2].replace('"', '').strip()
                    messages.append({"index": index, "status": status, "number": number, "text": text.strip()})
                except (IndexError, ValueError):
                    pass
                i += 2
            else:
                i += 1
        return messages

    # ===== DELETE SMS =====
    def delete_sms(self, index: int) -> bool:
        resp = self.send_at(f"AT+CMGD={index}")
        return "OK" in resp

    def delete_all_sms(self) -> str:
        return self.send_at("AT+CMGD=1,4")

    # ===== READ LINE (for listener thread) =====
    def readline(self) -> str:
        return self.ser.readline().decode(errors="ignore").strip()
