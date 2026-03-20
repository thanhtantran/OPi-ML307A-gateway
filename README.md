# OPi-ML307A-gateway

Gateway SMS sử dụng chip ML307A trên Orange Pi qua AT command trực tiếp.

## Tính năng

- ✅ Gửi SMS qua AT command (`AT+CMGS`)
- ✅ Nhận SMS realtime qua `+CMT` push notification
- ✅ Đồng bộ SMS chưa đọc từ modem vào SQLite
- ✅ Giao diện Streamlit để quản lý tin nhắn
- ✅ Theo dõi trạng thái gửi: chờ / đang gửi / thành công / lỗi
- ✅ Webhook notification cho SMS đến

## Cài đặt phần cứng

```bash
sudo apt update
sudo apt install usbutils
sudo apt remove brltty
```

Cài đặt udev rules cho ML307A:

`sudo nano /etc/udev/rules.d/99-ml307a.rules`

```udev
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="2ecc", ATTR{idProduct}=="3012", \
  RUN+="/sbin/modprobe option", \
  RUN+="/bin/sh -c 'echo 2ecc 3012 > /sys/bus/usb-serial/drivers/option1/new_id'"

SUBSYSTEM=="tty", KERNEL=="ttyUSB*", \
ENV{DEVPATH}=="*/3-1:1.1/*", \
SYMLINK+="ml307-at", MODE="0660", GROUP="dialout"
```

Thêm user vào group dialout:

```bash
sudo usermod -aG dialout $USER
```

## Cài đặt phần mềm

```bash
pip install -r requirements.txt
```

Chỉnh sửa `config.py` nếu cần:
- `SERIAL_PORT` - cổng serial của modem (mặc định `/dev/ml307-at`)
- `SERIAL_BAUD` - baud rate (mặc định `115200`)
- `MODEM_POLL_INTERVAL` - chu kỳ poll outbox/inbox (giây)
- `DELETE_IMPORTED_SMS` - xóa SMS khỏi modem sau khi import
- `WEBHOOK_URL` - endpoint nhận webhook khi có SMS đến (để trống nếu không dùng)

## Chạy ứng dụng

```bash
streamlit run app.py
```

Listener thread sẽ tự khởi động cùng với app.

## Cấu trúc mã nguồn

- `config.py` - Cấu hình
- `ml307.py` - Class giao tiếp AT command với modem ML307A
- `listener.py` - Background threads: gửi outbox + lắng nghe SMS đến
- `sms_db.py` - Database operations (SQLite)
- `app.py` - Streamlit web interface, khởi động listener khi start

## Luồng SMS

### Gửi SMS
1. App ghi vào bảng `outbox` với status `QUEUE`
2. Poll thread (`MODEM_POLL_INTERVAL` giây) pick up và gửi qua `AT+CMGS`
3. Cập nhật status `SENT` hoặc `FAILED`

### Nhận SMS
- Realtime: modem push `+CMT` → listener thread đọc và lưu vào DB ngay lập tức
- Fallback: poll thread đồng bộ `REC UNREAD` mỗi chu kỳ

## Database

SQLite (`sms.db`):
- `sms` - lịch sử SMS gửi/nhận
- `outbox` - hàng đợi gửi

## Troubleshooting

- **Không mở được cổng serial**: kiểm tra `ls /dev/ml307-at`, đảm bảo user trong group `dialout`
- **Không gửi được SMS**: thử tay `minicom -D /dev/ml307-at -b 115200` rồi gõ `AT`
- **Không nhận được SMS**: kiểm tra `AT+CNMI?` trả về `2,2,0,0,0`
