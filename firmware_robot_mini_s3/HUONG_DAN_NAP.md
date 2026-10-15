# HƯỚNG DẪN NẠP FIRMWARE CHO ROBOT MINI S3 (MEGABOT)

Thư mục này chứa đầy đủ các file firmware `.bin` mới nhất đã được build hoàn chỉnh, tích hợp:
- **Phần cứng:** ESP32-S3 (Flash 16MB N16R8), Màn hình OLED SSD1306 I2C (0x3C), Micro INMP441, Loa MAX98357A, Mạch điều khiển động cơ MX1616.
- **Từ khóa đánh thức (Custom Wake Word):** *"Xin chào Megabot"*
- **Kết nối Server:** WebSocket bảo mật `wss://megabotai.duckdns.org/ws/xiaozhi`
- **Dashboard quản trị:** `https://megabotai.duckdns.org`

---

## 📁 Cấu trúc các file Firmware

```text
firmware_robot_mini_s3/
├── robot-mini-s3-merged-all-in-one-0x0.bin  <-- [KHUYÊN DÙNG] File gộp toàn bộ nạp tại địa chỉ 0x0
├── flash_robot.bat                          <-- Tool nạp tự động 1-click trên Windows
├── HUONG_DAN_NAP.md                         <-- Tài liệu này
└── individual_bins/                         <-- Bộ 5 file nạp riêng lẻ theo phân vùng
    ├── 0x0000_bootloader.bin                (Địa chỉ: 0x0)
    ├── 0x8000_partition-table.bin          (Địa chỉ: 0x8000)
    ├── 0xd000_ota_data_initial.bin          (Địa chỉ: 0xd000)
    ├── 0x10000_srmodels.bin                 (Địa chỉ: 0x10000 - Model nhận diện giọng nói)
    └── 0x400000_xiaozhi_app.bin             (Địa chỉ: 0x400000 - Ứng dụng chính)
```

---

## 🚀 CÁCH 1: Nạp nhanh 1-Click bằng file `flash_robot.bat` (Đơn giản nhất)

1. Cắm cáp USB nối mạch Robot ESP32-S3 vào máy tính.
2. Kiểm tra cổng COM trong **Device Manager** (ví dụ: `COM8`, `COM3`, `COM5`).
3. Nhấp đúp chuột vào file `flash_robot.bat`.
4. Nhập tên cổng COM của robot rồi nhấn **Enter**.
5. Đợi thanh tiến trình chạy 100% là robot sẽ tự khởi động lại.

---

## 🖥️ CÁCH 2: Nạp bằng phần mềm "ESP Flash Download Tool" (Giao diện đồ họa)

Tải phần mềm chính thức của Espressif: [Flash Download Tool](https://www.espressif.com/en/support/download/other-tools)

1. Mở phần mềm, chọn:
   - **Chip Type:** `ESP32-S3`
   - **WorkMode:** `develop`
   - **LoadMode:** `UART`
2. **Cách nạp 1 file duy nhất (Khuyên dùng):**
   - Tích chọn ô đầu tiên, chọn file: `robot-mini-s3-merged-all-in-one-0x0.bin`
   - Điền địa chỉ bên cạnh: `0x0`
3. Cấu hình bên dưới:
   - **SPI SPEED:** `80MHz`
   - **SPI MODE:** `DIO`
   - **Flash Size:** `128Mbit` (hoặc `16MB`)
4. Chọn đúng cổng **COM**, tốc độ **BAUD:** `460800` (hoặc `921600`).
5. Nhấn **START** và chờ đến khi hiện chữ **FINISH**.

*(Nếu muốn nạp theo 5 file riêng lẻ, chọn 5 file trong thư mục `individual_bins/` tương ứng với các địa chỉ `0x0`, `0x8000`, `0xd000`, `0x10000`, `0x400000`).*

---

## 🌐 CÁCH 3: Nạp trực tiếp trên trình duyệt Web (Không cần cài đặt gì)

1. Sử dụng Google Chrome hoặc Microsoft Edge truy cập: [https://espressif.github.io/esptool-js/](https://espressif.github.io/esptool-js/)
2. Chọn Baudrate: `460800` $\rightarrow$ Nhấn **Connect** $\rightarrow$ Chọn cổng COM của mạch robot.
3. Tại ô **Flash Address 1**, điền `0x0`, nhấn **Browse** chọn file:
   `robot-mini-s3-merged-all-in-one-0x0.bin`
4. Nhấn **Program** và đợi nạp xong.

---

## 📡 CÁCH CẤU HÌNH WIFI CHO ROBOT MỚI SAU KHI NẠP

Sau khi nạp xong cho một robot mới:
1. Màn hình OLED sẽ sáng lên và hiển thị tên mạng WiFi cấu hình (thường có dạng: `Xiaozhi-XXXX` hoặc `Megabot-XXXX`).
2. Dùng điện thoại hoặc máy tính kết nối vào mạng WiFi đó (mật khẩu mặc định nếu có: `12345678`).
3. Trình duyệt sẽ tự động mở trang cấu hình WiFi (hoặc truy cập `192.168.4.1`).
4. Chọn WiFi gia đình/văn phòng và nhập mật khẩu để robot kết nối Internet.
5. Sau khi kết nối WiFi thành công, robot sẽ tự động liên kết tới Server `https://megabotai.duckdns.org` và xuất hiện trạng thái **ONLINE** trên trang web điều khiển!

