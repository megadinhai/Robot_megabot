# HƯỚNG DẪN NẠP FIRMWARE & SỬ DỤNG WEB ADMIN ROBOT MINI LCD 1SD (MEGABOT)

Thư mục này chứa đầy đủ các file firmware `.bin` mới nhất dành riêng cho dòng **Robot Mini LCD 1SD**, chuẩn theo sơ đồ mạch tại `SoDoMach/Robot_Mini_LCD_1SD`:

---

## 📌 1. Cấu hình phần cứng theo sơ đồ mạch

| Ngoại vi / Chức năng | Chân ESP32-S3 mặc định | Ghi chú |
| :--- | :--- | :--- |
| **Màn hình OLED SSD1306** | **SCL = GPIO 8**, **SDA = GPIO 3** | I2C Bus tốc độ 400kHz |
| **Loa MAX98357A (I2S DAC)** | **DIN = GPIO 7**, **BCLK = GPIO 5**, **LRC = GPIO 6** | Chuẩn âm thanh I2S Stereo/Mono |
| **Micro INMP441 (I2S Mic)** | **SD = GPIO 4**, **WS = GPIO 15**, **SCK = GPIO 16** | Tự động cân bằng pha & lọc DC |
| **Động cơ MX1616 (Trái)** | **IN1 = GPIO 1**, **IN2 = GPIO 2** | Điều xung PWM LEDC 1kHz |
| **Động cơ MX1616 (Phải)** | **IN3 = GPIO 42**, **IN4 = GPIO 41** | Điều xung PWM LEDC 1kHz |
| **Thẻ nhớ Micro SD (SPI)** | **CS = 47**, **CLK = 45**, **MOSI = 48**, **MISO = 40** | Khe cắm MicroSD Card |
| **Cảm biến khoảng cách ToF** | **SDA = GPIO 46**, **SCL = GPIO 9** | VL53L0X (I2C2) |
| **Cảm biến siêu âm HC-SR04** | **TRIG = GPIO 13**, **ECHO = GPIO 14** | Đo khoảng cách vật cản |
| **Cảm biến chạm TTP223** | **TOUCH = GPIO 21** | Chạm kích hoạt / đổi trạng thái |
| **Đèn LED RGB WS2812** | **DIN = GPIO 20** | Chuỗi 8 LED RGB thông minh |
| **Đo điện áp Pin (ADC)** | **ADC = GPIO 12** | Cầu phân áp đọc dung lượng pin |
| **Nút BOOT (Safe Reset)** | **GPIO 0** | Giữ nút BOOT 3 giây khi khởi động để khôi phục mặc định chân cắm |

---

## 🌐 2. Giao diện Web Admin Quản trị & Cài đặt chân GPIO

Firmware đã tích hợp sẵn một **Web Admin Control Panel** chạy độc lập trên cổng **`8080`**:

### Cách truy cập:
1. **Khi kết nối vào WiFi AP của Robot:**
   - Dùng điện thoại/máy tính kết nối vào mạng WiFi do robot phát ra (ví dụ: `Xiaozhi-XXXX` hoặc `Megabot-XXXX`).
   - Mở trình duyệt web truy cập: **`http://192.168.4.1:8080`**
2. **Khi Robot đã kết nối WiFi nhà:**
   - Xem địa chỉ IP của Robot (hiển thị trên màn hình OLED hoặc trang quản trị router).
   - Mở trình duyệt web truy cập: **`http://<IP-CỦA-ROBOT>:8080`** (Ví dụ: `http://192.168.1.50:8080`)

### Các chức năng nổi bật trên Web Admin:
- **Pin Configuration (Cài đặt lại chân GPIO):**
  Cho phép sửa lại bất kỳ chân cắm nào của Động cơ, OLED, Micro, Loa, Thẻ nhớ SD, Cảm biến chạm, Cảm biến siêu âm, VL53L0X, LED RGB và ADC Pin mà không cần phải biên dịch lại code!
- **Motor Live Control & Test:**
  Các nút bấm điều khiển di chuyển trực tiếp: **TIẾN (Forward)**, **LÙI (Backward)**, **RẼ TRÁI (Left)**, **RẼ PHẢI (Right)**, **DỪNG (Stop)** và thanh kéo tốc độ Speed (PWM 0 - 255).
- **Motor Calibration (Cân chỉnh động cơ):**
  - **Left Trim / Right Trim:** Tinh chỉnh bù trừ động cơ khi robot chạy bị lệch hướng.
  - **Min PWM:** Điều chỉnh ngưỡng PWM tối thiểu để động cơ thắng lực ma sát khởi động.
- **Factory Pin Reset (Khôi phục mặc định):**
  Đưa toàn bộ chân GPIO về đúng chuẩn theo sơ đồ `Robot_Mini_LCD_1SD`.
- **Safe Reset bằng nút cứng:**
  Nếu vô tình cài nhầm chân làm màn hình hoặc WiFi không lên, chỉ cần **nhấn giữ nút BOOT (GPIO 0) trong 3 giây khi cắm nguồn**, robot sẽ tự động xóa NVS cấu hình chân và quay về sơ đồ ban đầu!

---

## 📁 3. Cấu trúc các file Firmware

```text
firmware_robot_mini_lcd_1sd/
├── robot-mini-lcd-1sd-merged-all-in-one-0x0.bin  <-- [KHUYÊN DÙNG] File gộp toàn bộ nạp tại địa chỉ 0x0
├── flash_robot.bat                              <-- Tool nạp tự động 1-click trên Windows
├── HUONG_DAN_NAP.md                             <-- Tài liệu hướng dẫn này
└── individual_bins/                             <-- Bộ 5 file nạp riêng lẻ theo phân vùng
    ├── 0x0000_bootloader.bin                    (Địa chỉ: 0x0)
    ├── 0x8000_partition-table.bin              (Địa chỉ: 0x8000)
    ├── 0xd000_ota_data_initial.bin              (Địa chỉ: 0xd000)
    ├── 0x10000_srmodels.bin                     (Địa chỉ: 0x10000 - Model nhận diện giọng nói)
    └── 0x400000_xiaozhi_app.bin                 (Địa chỉ: 0x400000 - Ứng dụng chính)
```

---

## 🚀 4. Hướng dẫn nạp Firmware

### CÁCH 1: Nạp nhanh 1-Click bằng file `flash_robot.bat` (Khuyên dùng)
1. Cắm cáp USB nối mạch Robot ESP32-S3 vào máy tính.
2. Kiểm tra cổng COM trong **Device Manager** (ví dụ: `COM8`, `COM3`, `COM5`).
3. Nhấp đúp chuột vào file `flash_robot.bat`.
4. Nhập tên cổng COM rồi nhấn **Enter**.
5. Đợi chương trình nạp xong 100%, robot sẽ tự khởi động lại.

### CÁCH 2: Nạp bằng phần mềm "ESP Flash Download Tool"
1. Mở phần mềm [ESP Flash Download Tool](https://www.espressif.com/en/support/download/other-tools).
2. Chọn: **Chip Type: ESP32-S3**, **WorkMode: develop**, **LoadMode: UART**.
3. Tích ô đầu tiên, chọn file `robot-mini-lcd-1sd-merged-all-in-one-0x0.bin`, điền địa chỉ **`0x0`**.
4. Cài đặt: **SPI SPEED: 80MHz**, **SPI MODE: DIO**, **Flash Size: 128Mbit (16MB)**.
5. Chọn đúng cổng **COM**, **BAUD: 460800** $\rightarrow$ Nhấn **START**.

### CÁCH 3: Nạp trực tiếp qua trình duyệt Web (Không cần cài đặt)
1. Mở Chrome/Edge truy cập: [https://espressif.github.io/esptool-js/](https://espressif.github.io/esptool-js/)
2. Baudrate: `460800` $\rightarrow$ Nhấn **Connect** $\rightarrow$ Chọn cổng COM.
3. Tại ô **Flash Address 1**, điền **`0x0`**, chọn file `robot-mini-lcd-1sd-merged-all-in-one-0x0.bin`.
4. Nhấn **Program** và đợi nạp xong.

---

## 🎤 5. Tương tác giọng nói & Server AI
- **Từ khóa đánh thức:** *"Xin chào Megabot"*
- **Server WebSocket:** `wss://megabotai.duckdns.org/ws/xiaozhi`
- **Dashboard quản trị AI:** `https://megabotai.duckdns.org`
