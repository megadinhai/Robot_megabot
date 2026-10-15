#!/bin/bash
set -e

apt-get update -y
apt-get install -y python3-venv python3-pip curl psmisc debian-keyring debian-archive-keyring apt-transport-https

# Trỏ chính xác vào thư mục MyServer_WebSocket
WORK_DIR="/root/megabot-server/MyServer_WebSocket"
SERVER_FILE="$WORK_DIR/server.py"

echo "Target server: $SERVER_FILE"

cd "$WORK_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip

# Cài đặt thư viện từ requirements.txt nếu có
if [ -f "$WORK_DIR/requirements.txt" ]; then
    ./venv/bin/pip install -r "$WORK_DIR/requirements.txt"
elif [ -f "/root/megabot-server/requirements.txt" ]; then
    ./venv/bin/pip install -r "/root/megabot-server/requirements.txt"
fi

# Cài các gói cơ bản hay dùng cho WebSocket server
./venv/bin/pip install websockets uvicorn fastapi requests python-dotenv

# Tắt service cũ nếu đang chạy lỗi
systemctl stop megabot 2>/dev/null || true

# Tạo systemd service trỏ đúng file server.py
cat << EOF > /etc/systemd/system/megabot.service
[Unit]
Description=Megabot WebSocket Server
After=network.target

[Service]
User=root
WorkingDirectory=$WORK_DIR
Environment="PYTHONPATH=$WORK_DIR"
ExecStart=$WORK_DIR/venv/bin/python $SERVER_FILE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Tắt cf-tunnel cũ nếu có
systemctl stop cf-tunnel 2>/dev/null || true
systemctl disable cf-tunnel 2>/dev/null || true

# Cài đặt Caddy Server nếu chưa có
if ! command -v caddy &> /dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y
    apt-get install -y caddy
fi

# Cấu hình Caddy reverse proxy về cổng 8000
cat << EOF > /etc/caddy/Caddyfile
megabotai.duckdns.org {
    reverse_proxy localhost:8000
}
EOF

systemctl daemon-reload
systemctl enable megabot caddy
systemctl restart megabot caddy

echo "=========================================="
echo "HOAN TAT! KIEM TRA TRANG THAI:"
systemctl status megabot --no-pager
echo "=========================================="
