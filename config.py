# Serial port for ML307A AT commands
AT_PORT = "/dev/ml307-at"  # AT command port (ttyUSB1)
BAUD = 115200

DB = "sms.db"

WEBHOOK_URL = "http://127.0.0.1:1880/sms"  # Node-RED / HA / API

# SMS sending behavior
SMS_PROMPT_TIMEOUT = 5   # seconds to wait for '>' after AT+CMGS
SMS_SEND_TIMEOUT = 20    # seconds to wait for final OK/ERROR after Ctrl+Z
SERIAL_POLL_INTERVAL = 0.2
