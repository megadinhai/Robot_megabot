# Hướng Dẫn Nạp Firmware Otto Robot (Tiếng Việt & Web Admin :8080)

## 1. Thông tin bản Firmware
- **Tên board:** `otto-robot` (Chuẩn sơ đồ `SoDoMach/otto/otto_map.jpg`)
- **Ngôn ngữ mặc định:** Tiếng Việt (`vi-VN`) - Lời chào, thông báo, câu nhắc bằng tiếng Việt.
- **Màn hình OLED:** Cấu hình xoay **Ngang** (Landscape, `DISPLAY_SWAP_XY = true`), tự do xoay 0° / 90° / 180° / 270° trực tiếp từ Web Admin.
- **Âm thanh:** Tần số phát loa tối ưu 16.000 Hz, bộ đệm thông minh chống giật lag mạng.
- **Web Admin :8080:** Tích hợp giao diện quản trị Cyberpunk tại cổng `http://<IP_ROBOT>:8080` (hoặc `http://192.168.4.1:8080` khi ở chế độ AP).
  - Điều khiển bước chân Otto W / A / S / D.
  - Chuyển đổi linh hoạt giữa Server cá nhân `robot-megabot.onrender.com` và Server `xiaozhi.me` hoặc Server tùy chỉnh.
  - Tinh chỉnh góc Servo 4 chân (Trims Calibrate) lưu trực tiếp vào NVS.

---

## 2. Cách nạp cực nhanh (1-Click)
1. Cắm cáp USB mạch Otto ESP32 vào máy tính (Cổng COM, ví dụ: COM3).
2. Nhấp đúp vào file **`flash_otto.bat`**.
3. Nhập cổng COM (mặc định ấn Enter để chọn `COM3`).
4. Chờ 30 giây công cụ `esptool` tự động nạp file `otto_megabot_all_in_one_0x0.bin` vào flash tại địa chỉ `0x0`.

---

## 3. Lệnh nạp thủ công bằng Terminal (nếu muốn)
```bash
python -m esptool --chip esp32s3 -p COM3 -b 460800 --before default-reset --after hard-reset write_flash --flash_mode dio --flash_size 16MB --flash_freq 80m 0x0 otto_megabot_all_in_one_0x0.bin
```

---

## 4. Địa chỉ nạp từng phân vùng (Partition Offset)
Nếu nạp riêng lẻ:
- **Bootloader (`0x0`):** `bootloader_0x0.bin`
- **Partition Table (`0x8000`):** `partition_table_0x8000.bin`
- **OTA Data (`0xd000`):** `ota_data_0xd000.bin`
- **Application (`0x20000`):** `xiaozhi_app_0x20000.bin`
- **Assets (`0x800000`):** `generated_assets_0x800000.bin`
