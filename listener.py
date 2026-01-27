import serial
import time
import requests
import signal
import sys
from config import AT_PORT, BAUD, WEBHOOK_URL, GPS_UPDATE_INTERVAL
from sms_db import (
    init_db, save_sms,
    get_queued_sms, mark_outbox, save_gps_position
)
from gps_module import gps_reader

def send_at(ser, cmd, wait=0.5):
    """Send AT command and return response"""
    try:
        ser.write((cmd + "\r").encode())
        time.sleep(wait)
        response = ser.read_all().decode(errors="ignore")
        return response
    except serial.SerialException as e:
        print(f"⚠️ Serial error sending AT command: {e}")
        return ""

def send_sms(ser, number, text):
    """Send SMS message"""
    try:
        # Set text mode
        send_at(ser, "AT+CMGF=1", wait=0.5)
        
        # Send SMS command
        ser.write(f'AT+CMGS="{number}"\r'.encode())
        time.sleep(0.3)
        
        # Send message content and Ctrl+Z (0x1A)
        ser.write(text.encode() + b"\x1A")
        time.sleep(3)
        
        response = ser.read_all().decode(errors="ignore")
        return response
    except serial.SerialException as e:
        print(f"⚠️ Serial error sending SMS: {e}")
        return "ERROR"

def init_modem(ser):
    """Initialize modem with AT commands"""
    try:
        # Test connection
        resp = send_at(ser, "AT", wait=1)
        if "OK" not in resp:
            raise Exception("Modem not responding")
        
        # Set SMS text mode
        send_at(ser, "AT+CMGF=1", wait=0.5)
        
        # Set character set
        send_at(ser, 'AT+CSCS="GSM"', wait=0.5)
        
        # Configure SMS notification
        # AT+CNMI=2,1,0,2,1
        #            │ │ │ │ └ delivery report
        #            │ │ │ └ realtime SMS
        send_at(ser, "AT+CNMI=2,1,0,2,1", wait=0.5)
        
        # Enable GPS (if supported via AT commands)
        send_at(ser, "AT+CGNSPWR=1", wait=0.5)  # Power on GPS
        send_at(ser, "AT+CGNSTST=1", wait=0.5)  # Start GPS session
        
        print("✅ Modem initialized")
        return True
    except Exception as e:
        print(f"❌ Modem initialization failed: {e}")
        return False

def handle_delivery(line):
    """Handle SMS delivery report"""
    # +CDS: <length><CR><LF>PDU...
    save_sms("OUT", "", "", "DELIVERED")
    print("📬 Delivery report")

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\n🛑 Shutting down...")
    gps_reader.stop()
    sys.exit(0)

def main():
    """Main listener loop"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database
    init_db()
    
    # Start GPS reader
    gps_reader.start()
    
    # Open serial port for AT commands
    ser = None
    try:
        ser = serial.Serial(AT_PORT, BAUD, timeout=1)
        print(f"✅ AT port opened: {AT_PORT}")
    except serial.SerialException as e:
        print(f"❌ Failed to open AT port {AT_PORT}: {e}")
        print("   Make sure the device is connected and permissions are correct")
        gps_reader.stop()
        sys.exit(1)
    
    # Initialize modem
    if not init_modem(ser):
        print("❌ Failed to initialize modem")
        ser.close()
        gps_reader.stop()
        sys.exit(1)

    print("📡 Listener running")
    
    last_gps_save = 0
    
    try:
        while True:
            # ===== OUTBOX =====
            try:
                for id, number, text in get_queued_sms():
                    print(f"📤 Sending SMS to {number}")
                    resp = send_sms(ser, number, text)

                    if "OK" in resp:
                        mark_outbox(id, "SENT")
                        save_sms("OUT", number, text, "SENT")
                        print(f"✅ SMS sent successfully")
                    else:
                        mark_outbox(id, "FAILED")
                        save_sms("OUT", number, text, "FAILED")
                        print(f"❌ SMS send failed: {resp[:100]}")
            except Exception as e:
                print(f"⚠️ Error processing outbox: {e}")

            # ===== INCOMING SMS =====
            try:
                line = ser.readline().decode(errors="ignore").strip()

                if line.startswith("+CMT:"):
                    header = line
                    text = ser.readline().decode(errors="ignore").strip()
                    number = header.split(",")[1].replace('"', '')

                    print(f"📩 SMS from {number}: {text}")
                    save_sms("IN", number, text)

                    # Send webhook notification
                    try:
                        requests.post(
                            WEBHOOK_URL,
                            json={"from": number, "text": text},
                            timeout=2
                        )
                    except Exception as e:
                        print(f"⚠️ Webhook error: {e}")

                elif line.startswith("+CDS"):
                    handle_delivery(line)
            except serial.SerialException as e:
                print(f"⚠️ Serial read error: {e}")
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Error processing incoming SMS: {e}")

            # ===== GPS POSITION SAVE =====
            # Save GPS position periodically
            current_time = time.time()
            if current_time - last_gps_save >= GPS_UPDATE_INTERVAL:
                if gps_reader.has_fix():
                    pos = gps_reader.get_position()
                    save_gps_position(pos['latitude'], pos['longitude'], 
                                     pos['altitude'], pos['speed'], 
                                     pos['satellites'])
                    last_gps_save = current_time

            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        if ser:
            ser.close()
        gps_reader.stop()
        print("👋 Listener stopped")

if __name__ == "__main__":
    main()
