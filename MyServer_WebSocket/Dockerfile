FROM python:3.10-slim

# Cài đặt thư viện hệ thống cần thiết (ffmpeg cho audio conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tạo user không có quyền root theo tiêu chuẩn bảo mật của Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Cài đặt Python dependencies
COPY --chown=user ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY --chown=user . /app

# Hugging Face Spaces bắt buộc chạy ở cổng 7860
EXPOSE 7860

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]

