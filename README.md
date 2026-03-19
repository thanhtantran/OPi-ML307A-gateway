# OPi-ML307A-gateway

Gateway SMS sử dụng chip ML307A trên Orange Pi

## Tính năng

- ✅ Gửi/nhận SMS qua ML307A
- ✅ Giao diện Streamlit để đưa tin nhắn vào hàng đợi
- ✅ Theo dõi trạng thái gửi: chờ gửi / đang gửi / thành công / lỗi
- ✅ Lưu lịch sử SMS gửi/nhận vào SQLite
- ✅ Webhook notification cho SMS đến

## Cài đặt phần cứng

Cài đặt modem

```bash
sudo apt update
sudo apt install usbutils modemmanager wvdial
sudo apt remove brltty
```

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
```

## Cài đặt phần mềm

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Cấu hình (tùy chọn):
Chỉnh sửa `config.py` nếu cần thay đổi:
- Port AT (mặc định: `/dev/ml307-at`)
- Baud rate (mặc định: 115200)
- Webhook URL
- Timeout gửi SMS

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

- `config.py` - Cấu hình serial port, timeout, database
- `listener.py` - Service chính xử lý SMS
- `sms_db.py` - Database operations cho SMS và hàng đợi gửi
- `app.py` - Streamlit web interface
- `ml307a-listener.service` - Systemd service file

## Sử dụng

### Gửi SMS
- Mở web interface Streamlit
- Nhập số điện thoại và nội dung tin nhắn
- Click "Gửi SMS"
- Kiểm tra tab hàng đợi để xem trạng thái modem trả về

### Webhook
Khi có SMS đến, hệ thống sẽ POST đến `WEBHOOK_URL` với format:
```json
{
  "from": "+84901234567",
  "text": "Nội dung tin nhắn"
}
```

## Database

SQLite database (`sms.db`) chứa 2 bảng chính được dùng bởi ứng dụng:
- `sms` - Lịch sử SMS đã gửi/nhận
- `outbox` - Hàng đợi SMS cần gửi và lỗi modem gần nhất

## Troubleshooting

- **Lỗi serial port**: Kiểm tra quyền truy cập (`sudo usermod -aG dialout $USER` và logout/login lại)
- **SMS không gửi được**:
  - Kiểm tra SIM card, tín hiệu mạng và trạng thái đăng ký mạng (`AT+CREG?`, `AT+CSQ`)
  - Mở giao diện web để xem lỗi modem được lưu trong hàng đợi
  - Nếu nội dung có dấu tiếng Việt, thử gửi không dấu trước để xác nhận modem đang hoạt động ở chế độ text mode
