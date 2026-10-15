#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=============================================="
echo " [1/5] Cài đặt phụ thuộc hệ thống Ubuntu"
echo "=============================================="
apt-get update -y
apt-get install -y python3-venv python3-pip ffmpeg curl

echo "=============================================="
echo " [2/5] Khởi tạo môi trường ảo Python venv"
echo "=============================================="
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip

if [ -f "$APP_DIR/requirements.txt" ]; then
    pip install -r "$APP_DIR/requirements.txt"
elif [ -f "$APP_DIR/MyServer_WebSocket/requirements.txt" ]; then
    pip install -r "$APP_DIR/MyServer_WebSocket/requirements.txt"
fi

echo "=============================================="
echo " [3/5] Cấu hình và chạy megabot.service"
echo "=============================================="
if [ -f "$APP_DIR/MyServer_WebSocket/server.py" ]; then
    SERVER_WORKING_DIR="$APP_DIR/MyServer_WebSocket"
    SERVER_EXEC="$APP_DIR/venv/bin/python3 $APP_DIR/MyServer_WebSocket/server.py"
elif [ -f "$APP_DIR/server.py" ]; then
    SERVER_WORKING_DIR="$APP_DIR"
    SERVER_EXEC="$APP_DIR/venv/bin/python3 $APP_DIR/server.py"
else
    SERVER_WORKING_DIR="$APP_DIR"
    SERVER_EXEC="$APP_DIR/venv/bin/python3 server.py"
fi

cat <<EOF > /etc/systemd/system/megabot.service
[Unit]
Description=Megabot WebSocket & Web Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SERVER_WORKING_DIR
Environment="HOST=0.0.0.0"
Environment="PORT=8000"
Environment="PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$SERVER_EXEC
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable megabot.service
systemctl restart megabot.service

echo "=============================================="
echo " [4/5] Cấu hình Cloudflare Tunnel"
echo "=============================================="
if [ ! -f "/usr/local/bin/cloudflared" ]; then
    echo "Đang tải cloudflared-linux-amd64..."
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
fi

cat <<EOF > /etc/systemd/system/cf-tunnel.service
[Unit]
Description=Cloudflare Tunnel for Megabot Server
After=network.target megabot.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:8000 --no-autoupdate
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cf-tunnel.service
systemctl restart cf-tunnel.service

echo "=============================================="
echo " [5/5] Đang khởi tạo Tunnel..."
echo "=============================================="
sleep 8

echo "================================================================="
echo "🎉 CLOUDFLARE PUBLIC TUNNEL URL:"
journalctl -u cf-tunnel -n 50 --no-pager | grep -o "https://[-a-zA-Z0-9.]*\.trycloudflare\.com" | tail -n 1
echo "================================================================="
