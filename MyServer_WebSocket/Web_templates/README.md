# Hướng dẫn & Cấu trúc thư mục Web_templates

Thư mục đã được làm sạch và sắp xếp gọn gàng theo chuẩn dự án web frontend.

---

## 1. Các trang ứng dụng chính (Chạy trực tiếp)

- **`index.html` / `preview.html`**: Trung tâm điều khiển GMBOT AI (Dashboard quản lý thiết bị, cấu hình GMbot, bộ nhớ, bài học, và điều hướng).
- **`english-tutor-app.html` / `english-tutor.html`**: Ứng dụng chuyên sâu GMBOT English Tutor (Đầy đủ 5 phân hệ: *Hôm nay, Lộ trình 50 bài, Giáo trình & Nhập vai, Tự tạo bài giảng, Báo cáo học tập*). Hoạt động offline 100% không phụ thuộc server.
- **`chon-bai-hoc.html`**: Trang chọn và áp dụng 20 bài học chuẩn SP-01 đến SP-20.
- **`cau-hinh-gmbot.html`**: Trang cấu hình giọng nói và nhận diện người nói cho GMbot.
- **`huong-dan.html`**: Hướng dẫn sử dụng hệ thống GMBOT AI.
- **`ha-mcp-guide.html`**: Hướng dẫn tích hợp Home Assistant MCP.

---

## 2. Dữ liệu chuẩn & Cấu hình

- **`curriculums_full.json` & `curriculums_full.md`**: Toàn bộ nội dung prompt và giáo trình của 20 bài học chuẩn.
- **`tailwind.config.js`**: Bảng mã màu chuẩn Dark Navy của GMBOT AI (`#071426`, `#0b1f38`, `#1e3a8a`, `#2563eb`).
- **`package.json`**: Cấu hình dependencies nếu cần chạy qua Node / Vite.

---

## 3. Thành phần React (Dành cho mở rộng dự án)

- **`App.jsx`**: Component React cho giao diện Dashboard chính.
- **`EnglishTutorDashboard.jsx`**: Component React cho phân hệ English Tutor.

---

## 4. Thư mục con

- **`pages_extracted/`**: Chứa các phân đoạn HTML tách lẻ của 15 thẻ giao diện.
- **`_archive/`**: Chứa toàn bộ các script cào dữ liệu trung gian (`.js`), các file build nháp và ảnh chụp màn hình kiểm thử Playwright.

