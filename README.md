# OPi-ML307A-gateway

Gateway SMS và GPS sử dụng chip ML307A trên Orange Pi

## Tính năng

- ✅ Gửi/nhận SMS qua ML307A
- ✅ Định vị GPS theo thời gian thực
- ✅ Hiển thị GPS trên bản đồ Streamlit
- ✅ Lưu trữ lịch sử GPS và SMS
- ✅ Webhook notification cho SMS đến

## Cài đặt phần cứng

Cài đặt udev rules cho ML307A:

`sudo nano /etc/udev/rules.d/99-ml307a.rules`

Thêm nội dung sau:

```udev
# 1️⃣ Ensure option driver (giữ nguyên)
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="2ecc", ATTR{idProduct}=="3012", \
  RUN+="/sbin/modprobe option", \
  RUN+="/bin/sh -c 'echo 2ecc 3012 > /sys/bus/usb-serial/drivers/option1/new_id'"

# 2️⃣ Primary AT port (interface :1.1 → bInterfaceNumber 01)
SUBSYSTEM=="tty", KERNEL=="ttyUSB*", \
ENV{DEVPATH}=="*/3-1:1.1/*", \
SYMLINK+="ml307-at", MODE="0660", GROUP="dialout"

# 3️⃣ GPS NMEA port (interface :1.2 → bInterfaceNumber 02)
SUBSYSTEM=="tty", KERNEL=="ttyUSB*", \
ENV{DEVPATH}=="*/3-1:1.2/*", \
SYMLINK+="ml307-gps", MODE="0660", GROUP="dialout"
```

Reload và apply:

```bash
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=tty
```

Hoặc reboot:
```bash
sudo reboot
```

Kiểm tra:
```bash
ls -l /dev/ml307*
# Kết quả:
# lrwxrwxrwx 1 root root 7 Jan 27 11:30 /dev/ml307-at -> ttyUSB1
# lrwxrwxrwx 1 root root 7 Jan 27 11:30 /dev/ml307-gps -> ttyUSB4
```

## Cài đặt phần mềm

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Cấu hình (tùy chọn):
Chỉnh sửa `config.py` nếu cần thay đổi:
- Ports (mặc định: `/dev/ml307-at` và `/dev/ml307-gps`)
- Baud rate (mặc định: 115200)
- Webhook URL
- GPS update interval

3. Khởi động listener service:
```bash
# Copy service file
sudo cp ml307a-listener.service /etc/systemd/system/

# Chỉnh sửa đường dẫn trong service file nếu cần
sudo nano /etc/systemd/system/ml307a-listener.service

# Enable và start service
sudo systemctl enable ml307a-listener.service
sudo systemctl start ml307a-listener.service

# Kiểm tra status
sudo systemctl status ml307a-listener.service
```

4. Chạy Streamlit web interface:
```bash
streamlit run app.py
```

Truy cập web interface tại: `http://localhost:8501`

## Cấu trúc mã nguồn

- `config.py` - Cấu hình ports, baud rate, database
- `listener.py` - Service chính xử lý SMS và GPS
- `gps_module.py` - Module đọc dữ liệu GPS từ NMEA
- `sms_db.py` - Database operations cho SMS và GPS
- `app.py` - Streamlit web interface
- `ml307a-listener.service` - Systemd service file

## Sử dụng

### Gửi SMS
- Mở web interface Streamlit
- Nhập số điện thoại và nội dung tin nhắn
- Click "Gửi SMS"
- Tin nhắn sẽ được thêm vào hàng đợi và gửi tự động

### Xem GPS
- Web interface tự động hiển thị vị trí GPS hiện tại
- Bản đồ hiển thị vị trí real-time
- Lịch sử GPS được lưu và hiển thị trên bản đồ

### Webhook
Khi có SMS đến, hệ thống sẽ POST đến `WEBHOOK_URL` với format:
```json
{
  "from": "+84901234567",
  "text": "Nội dung tin nhắn"
}
```

## Database

SQLite database (`sms.db`) chứa 3 bảng:
- `sms` - Lịch sử SMS đã gửi/nhận
- `outbox` - Hàng đợi SMS cần gửi
- `gps_positions` - Lịch sử vị trí GPS

## Troubleshooting

- **Không thấy GPS fix**: Đảm bảo thiết bị ở nơi có tín hiệu vệ tinh tốt, chờ vài phút để GPS khởi động
- **Lỗi serial port**: Kiểm tra quyền truy cập (`sudo usermod -aG dialout $USER` và logout/login lại)
- **SMS không gửi được**: Kiểm tra SIM card và tín hiệu mạng
