# Hướng Dẫn Triển Khai Megabot Server Lên Hugging Face Spaces & Kết Nối ESP32

Chào bạn! Dưới đây là tài liệu quy trình chuẩn Full Stack sẵn sàng 100% để triển khai server WebSocket quản trị robot Megabot ESP32 từ thư mục code `E:\MyData\LearnAI\Xiaozhi\xiaozhi-esp32-test\MyServer_WebSocket` lên nền tảng **Hugging Face Spaces (Docker)** chạy trực tuyến 24/7 hoàn toàn miễn phí.

---

## 📌 Tổng quan kiến trúc hệ thống

```
+--------------------------+          WSS (Internet)          +-------------------------------+
|       Robot ESP32        | <=============================> |  Hugging Face Space (Docker)  |
|  - Thu âm micro (Opus)   |      wss://<space>.hf.space      |  - FastAPI WebSocket (/ws)    |
|  - Phát loa TTS          |           /ws/megabot            |  - Google Gemini AI (LLM+STT) |
|  - Hiển thị LCD/OLED     |                                  |  - Edge-TTS (Giọng Việt)      |
+--------------------------+                                  |  - Web Dashboard Quản trị     |
                                                              +-------------------------------+
```

---

## 🛠️ Bước 1: Bộ 3 file cốt lõi đã sẵn sàng trong thư mục

Thư mục `E:\MyData\LearnAI\Xiaozhi\xiaozhi-esp32-test\MyServer_WebSocket` đã được cấu hình tối ưu:

1. **`requirements.txt`**:
   - `fastapi`, `uvicorn[standard]`, `websockets`, `google-genai`, `edge-tts`, `python-dotenv`, `pydantic`.
2. **`Dockerfile`**:
   - Base image `python:3.10-slim`.
   - Cài đặt `ffmpeg` xử lý âm thanh.
   - Thiết lập Non-root user (UID 1000) bảo mật theo chuẩn Hugging Face.
   - Cổng chạy bắt buộc: `7860`.
3. **`server.py` & hệ sinh thái**:
   - Hỗ trợ endpoint WebSocket: `/ws/megabot` (đồng thời giữ cả `/ws/xiaozhi` cho firmware cũ).
   - Tích hợp sẵn giao diện Web Dashboard quản lý cấu hình robot trực tiếp trên trình duyệt.

---

## 🚀 Bước 2: Tạo Space trên Hugging Face

1. Truy cập [huggingface.co](https://huggingface.co/) và đăng nhập tài khoản của bạn.
2. Bấm vào ảnh đại diện (góc trên bên phải) $\rightarrow$ chọn **New Space**.
3. Điền các trường thông tin:
   - **Space name**: Đặt tên (ví dụ: `megabot-server` hoặc `robot-megabot`).
   - **License**: Chọn `mit` hoặc `apache-2.0`.
   - **Select the Space SDK**: Chọn **Docker** $\rightarrow$ chọn **Blank** (để sử dụng `Dockerfile` tùy chỉnh).
   - **Space hardware**: Chọn **Free** (2 vCPU · 16 GB RAM).
   - **Privacy**: Để **Public** (để chip ESP32 kết nối trực tiếp không bị vướng token xác thực HTTP).
4. Nhấn **Create Space**.

---

## 🔑 Bước 3: Cấu hình Secret (Gemini API Key)

1. Tại giao diện Space vừa tạo, chuyển sang tab **Settings**.
2. Cuộn xuống phần **Variables and secrets** $\rightarrow$ nhấn **New secret**.
3. Điền thông tin:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: Dán mã khóa Gemini API của bạn (lấy tại Google AI Studio).
4. Bấm **Save**.

*(Tùy chọn: Thêm Variable `GEMINI_MODEL` = `gemini-2.5-flash` và `TTS_VOICE` = `vi-VN-HoaiMyNeural` nếu muốn tùy biến).*

---

## 📤 Bước 4: Đẩy mã nguồn lên Hugging Face Space

Mở Terminal (PowerShell hoặc VS Code Terminal) tại thư mục `E:\MyData\LearnAI\Xiaozhi\xiaozhi-esp32-test\MyServer_WebSocket`:

```powershell
cd E:\MyData\LearnAI\Xiaozhi\xiaozhi-esp32-test\MyServer_WebSocket

# 1. Khởi tạo Git nếu chưa có
git init

# 2. Thêm remote tới Space của bạn (thay <USERNAME> và <SPACE_NAME> tương ứng)
git remote add space https://huggingface.co/spaces/<YOUR_USERNAME>/<SPACE_NAME>

# 3. Add toàn bộ file mã nguồn
git add .

# 4. Commit
git commit -m "Deploy full xiaozhi websocket server"

# 5. Push lên Space (Nhập Username và Hugging Face Access Token khi được hỏi)
git push space main -f
```

> **Cách thay thế (không dùng Git):** Trên web Hugging Face, vào tab **Files**, bấm **Add file** $\rightarrow$ **Upload files**, kéo thả toàn bộ các file trong thư mục `MyServer_WebSocket` vào rồi bấm **Commit changes to main**.

Sau khi đẩy code, tab Space sẽ tự động chuyển sang trạng thái **Building**. Chờ khoảng 1-2 phút cho đến khi hiện màu xanh lục **Running**.

---

## 🌐 Bước 5: Lấy URL WebSocket (WSS) nạp vào ESP32

1. Tại góc trên bên phải của giao diện Space (cạnh nút *Running*), nhấn vào biểu tượng **ba chấm (...)** $\rightarrow$ chọn **Embed this Space**.
2. Tìm dòng **Direct URL**:
   ```
   https://<username>-<space-name>.hf.space
   ```
3. Đổi sang giao thức WebSocket an toàn (`wss://`):
   ```
   wss://<username>-<space-name>.hf.space/ws/xiaozhi
   ```
4. **Nạp vào firmware ESP32**:
   - Nếu bạn dùng cấu hình qua Web Cấu hình WiFi captive portal của ESP32: Điền URL trên vào ô `WebSocket Server URL`.
   - Nếu bạn cấu hình tĩnh trong file mã nguồn ESP32 (ví dụ `main/settings.cc` hoặc `menuconfig`): Gán `server_url` = `wss://<username>-<space-name>.hf.space/ws/xiaozhi`.

