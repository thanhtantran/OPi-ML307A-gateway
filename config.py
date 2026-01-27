# Serial ports for ML307A
AT_PORT = "/dev/ml307-at"  # AT command port (ttyUSB1)
GPS_PORT = "/dev/ml307-gps"  # GPS NMEA port (ttyUSB4)
BAUD = 115200

DB = "sms.db"

WEBHOOK_URL = "http://127.0.0.1:1880/sms"  # Node-RED / HA / API

# GPS settings
GPS_UPDATE_INTERVAL = 5  # seconds between GPS updates
