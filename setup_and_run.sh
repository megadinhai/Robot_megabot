#!/bin/bash
set -e

apt-get update -y
apt-get install -y python3-venv python3-pip curl psmisc

# Tìm thư mục chứa server.py
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

# Tìm port trong server.py (mặc định 8000 nếu không thấy)
PORT=$(grep -oP 'port\s*=\s*\K[0-9]+' "$SERVER_FILE" | head -n 1)
if [ -z "$PORT" ]; then PORT=8000; fi
echo "Detected Port: $PORT"

# Tạo service chạy ngầm WebSocket Server
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

# Cài đặt cloudflared Linux
if [ ! -f /usr/local/bin/cloudflared ]; then
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
fi

# Tạo service chạy ngầm Cloudflare Tunnel
cat << EOF > /etc/systemd/system/cf-tunnel.service
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:$PORT --no-autoupdate
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable megabot cf-tunnel
systemctl restart megabot cf-tunnel

echo "Waiting 8 seconds for Cloudflare domain..."
sleep 8
echo "=========================================="
echo "LINK TEN MIEN WEBSOCKET CUA BAN LA:"
journalctl -u cf-tunnel -n 50 --no-pager | grep -o "https://[-a-zA-Z0-9.]*\.trycloudflare\.com" | tail -n 1 | sed 's/https:/wss:/g'
echo "=========================================="
