# Robot Mini ESP32-S3 (XiaoZhi AI Voice Assistant)

Firmware tích hợp trợ lý giọng nói AI XiaoZhi dành cho Robot Mini chạy ESP32-S3 theo đúng sơ đồ mạch `Robot_Mini_LCD_1SD.jpg`.

## 1. Sơ đồ kết nối phần cứng (Pinout)

### Bộ xử lý chính
- **ESP32-S3-WROOM-1** (DevKitC-1)

### Âm thanh (Audio I2S Simplex)
- **Microphone MEMS INMP441**:
  - `VDD`: 3.3V
  - `GND` & `L/R`: GND (Kênh Left)
  - `SD` (Data Out): **GPIO 6** (DIN của ESP32)
  - `SCK` (Clock): **GPIO 5**
  - `WS` (Word Select / LRCK): **GPIO 4**
- **Mạch khuếch đại MAX98357A & Loa**:
  - `VIN`: 3.3V / 5V
  - `GND`: GND
  - `SD`: Nối lên 3.3V
  - `DIN` (Data In): **GPIO 7** (DOUT của ESP32)
  - `BCLK`: **GPIO 15**
  - `LRC`: **GPIO 16**

### Màn hình hiển thị
- **OLED 0.96 inch I2C (SSD1306 hoặc SH1106 128x64 / 128x32)**:
  - `VCC`: 3.3V
  - `GND`: GND
  - `SDA`: **GPIO 9**
  - `SCL`: **GPIO 46**

### Động cơ bánh xe (MX1616 Dual DC Motor Driver)
- **Bánh Trái (Motor A)**:
  - `IN1`: **GPIO 1**
  - `IN2`: **GPIO 2**
- **Bánh Phải (Motor B)**:
  - `IN3`: **GPIO 42**
  - `IN4`: **GPIO 41**
- `VCC`: Nguồn 5V từ mạch Boost qua công tắc
- `GND`: Chung GND

### Nút nhấn & Cảm biến chạm
- **Nút BOOT**: **GPIO 0**
- **Cảm biến chạm TTP223** (Hàn nối chân A - Active Low): **GPIO 0** (nối song song với nút BOOT)
  - Chạm 1 lần: Bật/Tắt đối thoại AI.
  - Chạm giữ lâu khi vừa khởi động: Vào chế độ cài đặt Wi-Fi.

### Đèn LED
- **Dải 8 LED RGB WS2812**: **GPIO 48** (DIN) - Hiển thị trạng thái AI (lắng nghe, suy nghĩ, đang nói, nhấp nháy,...).
- **Đèn sợi đốt dẻo / Đèn trang trí (Lamp)**: **GPIO 21** - Điều khiển bật/tắt bằng giọng nói qua công cụ MCP (`self.lamp.turn_on`, `self.lamp.turn_off`).

### Cảm biến mở rộng (Tùy chọn)
- **Biến trở chiết áp 10k/100k**: **GPIO 14** (ADC2_CH3)
- **Cảm biến siêu âm HC-SR04**: `Trig` -> **GPIO 13**, `Echo` -> **GPIO 12**
- **Cảm biến khoảng cách Laser VL53L0X**: `SDA` -> **GPIO 10**, `SCL` -> **GPIO 11**
- **Thẻ nhớ Mini SD**: `CS` -> **GPIO 47**, `MOSI` -> **GPIO 38**, `CLK` -> **GPIO 39**, `MISO` -> **GPIO 40**

---

## 2. Các công cụ MCP Robot hỗ trợ giọng nói AI

Robot tích hợp sẵn bộ công cụ MCP Server:
- `self.robot.forward` (duration_ms, speed): Đi thẳng về phía trước
- `self.robot.backward` (duration_ms, speed): Lùi về sau
- `self.robot.turn_left` (duration_ms, speed): Rẽ trái
- `self.robot.turn_right` (duration_ms, speed): Rẽ phải
- `self.robot.move` (direction, speed, duration_ms): Điều khiển linh hoạt
- `self.robot.stop`: Dừng khẩn cấp
- `self.lamp.turn_on` / `self.lamp.turn_off`: Bật / tắt đèn sợi đốt LED

---

## 3. Lệnh biên dịch Firmware

```bash
# Nạp môi trường ESP-IDF (nếu dùng PowerShell trên Windows):
. C:\esp\v6.1\esp-idf\export.ps1

# Biên dịch bản 16MB Flash (mặc định với SSD1306 128x64):
python scripts/build.py robot-mini-s3 --name robot-mini-s3

# Hoặc bản 8MB Flash (nếu module ESP32-S3 là 8MB Flash):
python scripts/build.py robot-mini-s3 --name robot-mini-s3-8m

# Hoặc màn hình OLED SH1106:
python scripts/build.py robot-mini-s3 --name robot-mini-s3-sh1106
```
