import serial
import time
import threading
from config import GPS_PORT, BAUD, GPS_UPDATE_INTERVAL

class GPSReader:
    def __init__(self):
        self.ser = None
        self.latitude = None
        self.longitude = None
        self.altitude = None
        self.speed = None
        self.course = None
        self.satellites = None
        self.fix_quality = None
        self.timestamp = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
    def parse_nmea(self, line):
        """Parse NMEA sentence (GPGGA, GPRMC, etc.)"""
        if not line.startswith('$'):
            return None
            
        try:
            parts = line.strip().split(',')
            sentence_type = parts[0]
            
            # GPGGA - Global Positioning System Fix Data
            if sentence_type == '$GPGGA' or sentence_type == '$GNGGA':
                if len(parts) >= 15:
                    time_str = parts[1] if parts[1] else None
                    lat_raw = parts[2] if parts[2] else None
                    lat_dir = parts[3] if parts[3] else None
                    lon_raw = parts[4] if parts[4] else None
                    lon_dir = parts[5] if parts[5] else None
                    fix_quality = parts[6] if parts[6] else '0'
                    satellites = parts[7] if parts[7] else '0'
                    altitude = parts[9] if parts[9] else None
                    
                    if lat_raw and lon_raw and fix_quality != '0':
                        # Convert DDMM.MMMM to decimal degrees
                        lat_deg = float(lat_raw[:2])
                        lat_min = float(lat_raw[2:])
                        latitude = lat_deg + (lat_min / 60.0)
                        if lat_dir == 'S':
                            latitude = -latitude
                            
                        lon_deg = float(lon_raw[:3])
                        lon_min = float(lon_raw[3:])
                        longitude = lon_deg + (lon_min / 60.0)
                        if lon_dir == 'W':
                            longitude = -longitude
                            
                        with self.lock:
                            self.latitude = latitude
                            self.longitude = longitude
                            self.altitude = float(altitude) if altitude else None
                            self.satellites = int(satellites) if satellites else 0
                            self.fix_quality = int(fix_quality)
                            self.timestamp = time.time()
                            
                        return {
                            'latitude': latitude,
                            'longitude': longitude,
                            'altitude': float(altitude) if altitude else None,
                            'satellites': int(satellites) if satellites else 0,
                            'fix_quality': int(fix_quality)
                        }
            
            # GPRMC - Recommended Minimum Specific GPS/Transit Data
            elif sentence_type == '$GPRMC' or sentence_type == '$GNRMC':
                if len(parts) >= 12:
                    status = parts[2] if parts[2] else 'V'
                    if status == 'A':  # Active (valid fix)
                        speed_knots = parts[7] if parts[7] else '0'
                        course = parts[8] if parts[8] else '0'
                        
                        with self.lock:
                            self.speed = float(speed_knots) * 1.852  # Convert knots to km/h
                            self.course = float(course) if course else None
                            
        except (ValueError, IndexError) as e:
            print(f"⚠️ GPS parse error: {e}")
            return None
            
        return None
    
    def read_gps(self):
        """Read GPS data in background thread"""
        try:
            self.ser = serial.Serial(GPS_PORT, BAUD, timeout=1)
            print(f"✅ GPS port opened: {GPS_PORT}")
            
            while self.running:
                try:
                    line = self.ser.readline().decode(errors='ignore').strip()
                    if line:
                        self.parse_nmea(line)
                except serial.SerialException as e:
                    print(f"⚠️ GPS serial error: {e}")
                    time.sleep(1)
                except Exception as e:
                    print(f"⚠️ GPS read error: {e}")
                    time.sleep(0.5)
                    
        except serial.SerialException as e:
            print(f"❌ Failed to open GPS port {GPS_PORT}: {e}")
        except Exception as e:
            print(f"❌ GPS reader error: {e}")
        finally:
            if self.ser:
                self.ser.close()
                self.ser = None
    
    def start(self):
        """Start GPS reading thread"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self.read_gps, daemon=True)
        self.thread.start()
        print("🛰️ GPS reader started")
    
    def stop(self):
        """Stop GPS reading thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.ser:
            self.ser.close()
            self.ser = None
        print("🛰️ GPS reader stopped")
    
    def get_position(self):
        """Get current GPS position (thread-safe)"""
        with self.lock:
            return {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'altitude': self.altitude,
                'speed': self.speed,
                'course': self.course,
                'satellites': self.satellites,
                'fix_quality': self.fix_quality,
                'timestamp': self.timestamp,
                'has_fix': self.latitude is not None and self.longitude is not None
            }
    
    def has_fix(self):
        """Check if GPS has valid fix"""
        with self.lock:
            return self.latitude is not None and self.longitude is not None

# Global GPS reader instance
gps_reader = GPSReader()
