# OPi-ML307A-gateway

Cài cứng ML307A vào thiết bị

`sudo nano /etc/udev/rules.d/99-ml307a.rules`

thêm phần này vào

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

Reload và apply

```bash
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=tty
```

Hoặc reboot
```bash
sudo reboot
```

Kiểm tra
```bash
firefly@firefly:~$ ls -l /dev/ml307*
lrwxrwxrwx 1 root root 7 Jan 27 11:30 /dev/ml307-at -> ttyUSB1
lrwxrwxrwx 1 root root 7 Jan 27 11:30 /dev/ml307-gps -> ttyUSB4
