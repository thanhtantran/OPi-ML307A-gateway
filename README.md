# OPi-ML307A-gateway

Gateway SMS sử dụng chip ML307A trên Orange Pi

## Tính năng

- ✅ Gửi SMS qua ModemManager (`mmcli`)
- ✅ Đồng bộ SMS nhận được từ ModemManager vào SQLite
- ✅ Giao diện Streamlit để đưa tin nhắn vào hàng đợi
- ✅ Theo dõi trạng thái gửi: chờ gửi / đang gửi / thành công / lỗi
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

## Cài đặt phần mềm

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Bảo đảm ModemManager đang chạy:
```bash
sudo systemctl enable ModemManager
sudo systemctl restart ModemManager
mmcli -L
```

3. Chỉnh sửa `config.py` nếu cần thay đổi:
- `MODEM_ID` - modem index trong `mmcli -L`
- `MODEM_POLL_INTERVAL` - chu kỳ đồng bộ gửi/nhận SMS
- `DELETE_IMPORTED_SMS` - có xóa SMS received khỏi modem sau khi import hay không
- `WEBHOOK_URL` - nơi nhận webhook cho SMS đến

4. Khởi động listener service:
```bash

sudo cp ml307a-listener.service /etc/systemd/system/
sudo systemctl enable ml307a-listener.service
sudo systemctl restart ml307a-listener.service
sudo systemctl status ml307a-listener.service

ls -l /dev/ml307*
# Kết quả:
# lrwxrwxrwx 1 root root 7 Jan 27 11:30 /dev/ml307-at -> ttyUSB1

```

5. Chạy Streamlit web interface:
```bash
streamlit run app.py
```

## Cấu trúc mã nguồn
=======
2. Cấu hình (tùy chọn):
Chỉnh sửa `config.py` nếu cần thay đổi:
- Port AT (mặc định: `/dev/ml307-at`)
- Baud rate (mặc định: 115200)
- Webhook URL
- Timeout gửi SMS

- `config.py` - Cấu hình database và ModemManager/mmcli
- `listener.py` - Đồng bộ outbox/inbox qua `mmcli`
- `sms_db.py` - Database operations cho SMS và hàng đợi gửi
- `app.py` - Streamlit web interface
- `ml307a-listener.service` - Systemd service file

## Luồng SMS dùng trong mã nguồn

### Gửi SMS
Mã nguồn listener dùng đúng luồng ModemManager được khuyến nghị:

```bash
sudo mmcli -m 0 --messaging-create-sms="text='Xin chào từ ML307A',number='+849xxxxxxxx'"
sudo mmcli -s <sms_id> --send
```

Trong source:
- `queue_sms()` ghi yêu cầu gửi vào SQLite
- `listener.py` gọi `mmcli -m <MODEM_ID> --messaging-create-sms=...`
- lấy `SMS/<id>` vừa tạo
- gọi tiếp `mmcli -s <id> --send`
- cập nhật trạng thái `SENT` hoặc `FAILED` cùng phản hồi mmcli

### Nhận & đọc SMS
Listener đồng bộ inbox bằng:

```bash
sudo mmcli -m 0 --messaging-list-sms
sudo mmcli -s <sms_id>
```

Chỉ các SMS ở trạng thái `received` mới được import vào SQLite để tránh nhập lại các SMS do chính hệ thống vừa tạo để gửi.

### Xóa SMS
Nếu muốn tự động xóa SMS đã import khỏi modem, đặt:

```python
DELETE_IMPORTED_SMS = True
```

Khi đó listener sẽ gọi:

```bash
sudo mmcli -s <sms_id> --delete
```

## Database

SQLite database (`sms.db`) chứa 2 bảng chính:
- `sms` - lịch sử SMS gửi/nhận
- `outbox` - hàng đợi gửi, phản hồi lỗi và `modem_sms_id`

## Troubleshooting

- **Không gửi được SMS**:
  - chạy thử tay: `mmcli -m 0 --messaging-create-sms=...` rồi `mmcli -s <id> --send`
  - kiểm tra modem có xuất hiện trong `mmcli -L` hay không
  - kiểm tra service `ModemManager` đang chạy
  - xem cột lỗi trong giao diện web hoặc journal của `ml307a-listener.service`
- **Không thấy SMS đến**:
  - kiểm tra `mmcli -m 0 --messaging-list-sms`
  - bảo đảm `MODEM_ID` đúng modem đang dùng
  - nếu muốn dọn sạch hộp thư sau khi import, bật `DELETE_IMPORTED_SMS = True`
