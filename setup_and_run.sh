#!/bin/bash
set -e

apt-get update -y
apt-get install -y python3-venv python3-pip curl psmisc debian-keyring debian-archive-keyring apt-transport-https

# 1. Tìm thư mục chứa server.py
SERVER_FILE=$(find /root/megabot-server -name "server.py" | head -n 1)
WORK_DIR=$(dirname "$SERVER_FILE")
echo "Found server.py at: $SERVER_FILE"

cd "$WORK_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
if [ -f requirements.txt ]; then
    ./venv/bin/pip install -r requirements.txt
elif [ -f /root/megabot-server/requirements.txt ]; then
    ./venv/bin/pip install -r /root/megabot-server/requirements.txt
fi

# 2. Xác định Port của server.py (mặc định 8000)
PORT=$(grep -oP 'port\s*=\s*\K[0-9]+' "$SERVER_FILE" | head -n 1)
if [ -z "$PORT" ]; then PORT=8000; fi
echo "Detected Port: $PORT"

# 3. Tạo service chạy ngầm WebSocket Server
cat << EOF > /etc/systemd/system/megabot.service
[Unit]
Description=Megabot WebSocket Server
After=network.target

[Service]
User=root
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/venv/bin/python $SERVER_FILE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Tắt cf-tunnel cũ để không tốn RAM
systemctl stop cf-tunnel 2>/dev/null || true
systemctl disable cf-tunnel 2>/dev/null || true

# 4. Cài đặt Caddy Server để tự động cấp SSL và nối megabotai.duckdns.org -> localhost:$PORT
if ! command -v caddy &> /dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y
    apt-get install -y caddy
fi

cat << EOF > /etc/caddy/Caddyfile
megabotai.duckdns.org {
    reverse_proxy localhost:$PORT
}
EOF

# Mở tường lửa nội bộ Ubuntu (nếu có)
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
ufw allow $PORT/tcp 2>/dev/null || true

systemctl daemon-reload
systemctl enable megabot caddy
systemctl restart megabot caddy

echo "=========================================="
echo "CAI DAT HOAN TAT! LINK CO DINH CUA BAN LA:"
echo "Web/API  : https://megabotai.duckdns.org"
echo "WebSocket: wss://megabotai.duckdns.org"
echo "=========================================="
