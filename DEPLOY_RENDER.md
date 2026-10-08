# Hướng Dẫn Cấu Hình Render.com Cho Robot Megabot ESP32

Mã nguồn dự án đã được đẩy lên GitHub thành công tại:
👉 **https://github.com/megadinhai/Robot_megabot**

Dưới đây là các bước chi tiết để bạn thiết lập chạy server trên [Render.com](https://render.com/):

---

## Bước 3: Đăng ký & Tạo Web Service trên Render

1. Truy cập [render.com](https://render.com/) $\rightarrow$ Chọn **Sign in** $\rightarrow$ Đăng nhập bằng tài khoản **GitHub**.
2. Tại trang Dashboard của Render, nhấn nút **New +** (góc trên bên phải) $\rightarrow$ Chọn **Web Service**.
3. Chọn tùy chọn **Build and deploy from a Git repository** $\rightarrow$ Bấm **Next**.
4. Tìm repository **`Robot_megabot`** (hoặc paste link `https://github.com/megadinhai/Robot_megabot.git`) $\rightarrow$ Bấm nút **Connect**.
   *(Lưu ý: Nếu service trước đó đã tạo với tên cũ, bạn chỉ cần vào **Settings** của Service trên Render $\rightarrow$ đổi tên Name thành `robot-megabot`)*.

---

## Bước 4: Thiết lập cấu hình triển khai (Settings)

Điền chính xác các thông số cấu hình sau:

| Mục thiết lập | Giá trị điền | Ghi chú |
| :--- | :--- | :--- |
| **Name** | `robot-megabot` *(hoặc tên tùy thích)* | Tên này quyết định đường link miền của bạn |
| **Region** | **Singapore (Southeast Asia)** | Giúp giảm ping/độ trễ giọng nói về Việt Nam thấp nhất |
| **Branch** | `main` | Nhánh chứa mã nguồn chính |
| **Root Directory** | *(Để trống)* | Render sẽ tìm trực tiếp `requirements.txt` và `server.py` |
| **Runtime** | **Python 3** | Môi trường chạy Python |
| **Build Command** | `pip install -r requirements.txt` | Lệnh cài đặt thư viện cần thiết |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` | **Bắt buộc dùng `$PORT`** để Render tự gán cổng mạng |
| **Instance Type** | **Free** (512 MB RAM, 0.1 CPU) | Miễn phí 100% |

---

## Bước 5: Cấu hình API Key (Environment Variables)

Cuộn xuống mục **Environment Variables** $\rightarrow$ Bấm **Add Environment Variable**:
- **Key**: `GEMINI_API_KEY` $\rightarrow$ **Value**: Dán API Key Gemini của bạn (lấy tại Google AI Studio).

*(Tùy chọn - nếu bạn muốn dùng thêm ChatGPT hoặc DeepSeek):*
- **Key**: `OPENAI_API_KEY` $\rightarrow$ **Value**: Dán mã OpenAI API Key (bắt đầu bằng `sk-...`).
- **Key**: `DEEPSEEK_API_KEY` $\rightarrow$ **Value**: Dán mã DeepSeek API Key (bắt đầu bằng `sk-...`).
- **Key**: `TTS_VOICE` $\rightarrow$ **Value**: `vi-VN-HoaiMyNeural`

Cuối cùng, nhấn nút **Create Web Service** ở cuối trang.

---

## Bước 6: Lấy link WebSocket nạp vào Robot ESP32

1. Render sẽ tự động kéo code từ GitHub về, build và cài đặt thư viện (mất khoảng 1 - 2 phút).
2. Khi nhìn thấy log hiển thị:
   ```
   Application startup complete.
   Uvicorn running on http://0.0.0.0:xxxx
   ```
   Và trạng thái chuyển sang **Live** màu xanh lục, server đã online thành công!
3. Ở góc trên bên trái (ngay dưới tên Service), URL do Render cấp sẽ là:
   ```
   https://robot-megabot.onrender.com
   ```
4. Đổi sang định dạng **WebSocket WSS an toàn**:
   ```
   wss://robot-megabot.onrender.com/ws/megabot
   ```
   *(Server hỗ trợ cả 2 endpoint `/ws/megabot` và `/ws/xiaozhi` tương thích ngược 100%)*
5. Nạp link này vào mục cấu hình Server của ESP32 (qua giao diện cấu hình WiFi Captive Portal của robot hoặc mã nguồn). Robot sẽ tự động kết nối và hội thoại AI ngay lập tức!

