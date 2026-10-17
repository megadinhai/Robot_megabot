#pragma once

// Cyberpunk Dark Web Admin UI for Otto Robot / Megabot
const char WEB_ADMIN_HTML[] = R"rawliteral(<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DB-ROBOT OTTO CONTROL PANEL v2.0</title>
<style>
:root {
  --bg: #090d16;
  --card-bg: #111827;
  --card-border: #1e293b;
  --neon-cyan: #00f0ff;
  --neon-pink: #ec4899;
  --neon-purple: #8b5cf6;
  --neon-green: #10b981;
  --neon-red: #ef4444;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace, sans-serif; }
body { background: var(--bg); color: var(--text-main); padding: 16px; min-height: 100vh; }
.container { max-width: 680px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }

/* Header */
.header {
  background: var(--card-bg);
  border: 1px solid var(--neon-cyan);
  box-shadow: 0 0 15px rgba(0,240,255,0.25);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}
.header h1 { font-size: 1.25rem; font-weight: 800; letter-spacing: 2px; color: var(--neon-cyan); text-shadow: 0 0 8px rgba(0,240,255,0.6); margin-bottom: 6px; }
.badges { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: 0.8rem; }
.badge { background: #1e293b; padding: 4px 10px; border-radius: 999px; border: 1px solid #334155; }
.badge.cyan { border-color: var(--neon-cyan); color: var(--neon-cyan); }
.badge.green { border-color: var(--neon-green); color: var(--neon-green); }
.badge.pink { border-color: var(--neon-pink); color: var(--neon-pink); }

/* Cards */
.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
}
.card-title {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: var(--neon-cyan);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 8px;
}

/* Quick Action Bar */
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.btn-quick {
  border: none;
  border-radius: 8px;
  padding: 14px 6px;
  font-weight: 700;
  font-size: 0.82rem;
  letter-spacing: 1px;
  color: #fff;
  cursor: pointer;
  text-align: center;
  transition: transform 0.1s, filter 0.2s;
  box-shadow: 0 4px 10px rgba(0,0,0,0.3);
}
.btn-quick:active { transform: scale(0.95); }
.btn-swing { background: linear-gradient(135deg, #ec4899, #8b5cf6); }
.btn-dance { background: linear-gradient(135deg, #06b6d4, #3b82f6); }
.btn-walk { background: linear-gradient(135deg, #10b981, #059669); }
.btn-stop { background: linear-gradient(135deg, #ef4444, #b91c1c); box-shadow: 0 0 12px rgba(239,68,68,0.5); }

/* Direction Pad */
.dpad-container { display: flex; flex-direction: column; align-items: center; gap: 8px; margin: 12px 0; }
.dpad-row { display: flex; gap: 8px; }
.btn-dir {
  width: 72px; height: 52px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  color: var(--text-main);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
}
.btn-dir span.sub { font-size: 0.65rem; color: var(--text-muted); }
.btn-dir:hover, .btn-dir.active { background: #334155; border-color: var(--neon-cyan); color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0,240,255,0.4); }
.btn-dir:active { transform: scale(0.94); }

/* Extra Moves */
.extra-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
.btn-extra {
  background: #1e293b;
  border: 1px solid #334155;
  color: var(--text-main);
  padding: 10px 4px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.btn-extra:hover { border-color: var(--neon-purple); color: var(--neon-purple); }
.btn-extra:active { transform: scale(0.95); }

/* Keyboard Help */
.keys-guide { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.72rem; color: var(--text-muted); background: #0c121e; padding: 10px; border-radius: 6px; margin-top: 10px; }
.keys-guide kbd { background: #1e293b; color: var(--neon-cyan); padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #334155; }

/* Forms & Radios */
.form-group { margin-bottom: 12px; }
.form-label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
.radio-group { display: flex; flex-direction: column; gap: 8px; }
.radio-card {
  display: flex; align-items: center; gap: 10px;
  background: #0c121e; padding: 10px 12px; border-radius: 8px;
  border: 1px solid #1e293b; cursor: pointer; transition: border-color 0.2s;
}
.radio-card:hover { border-color: var(--neon-cyan); }
.radio-card input { accent-color: var(--neon-cyan); }
.radio-text { flex: 1; font-size: 0.82rem; }
.radio-text small { display: block; color: var(--text-muted); font-size: 0.72rem; }
.input-text {
  width: 100%; background: #0c121e; border: 1px solid #334155;
  border-radius: 6px; color: #fff; padding: 8px 12px; font-size: 0.85rem; margin-top: 6px;
}
.input-text:focus { outline: none; border-color: var(--neon-cyan); box-shadow: 0 0 6px rgba(0,240,255,0.4); }

/* Sliders */
.slider-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 0.8rem; gap: 10px; }
.slider-label { width: 120px; font-weight: 600; }
.slider-input { flex: 1; accent-color: var(--neon-cyan); cursor: pointer; }
.slider-val { width: 44px; text-align: right; color: var(--neon-cyan); font-weight: bold; }

/* Action Buttons Bottom */
.btn-save {
  width: 100%; background: linear-gradient(135deg, #0ea5e9, #2563eb);
  color: #fff; font-weight: 700; border: none; border-radius: 8px;
  padding: 12px; font-size: 0.85rem; cursor: pointer; letter-spacing: 1px;
  box-shadow: 0 0 12px rgba(14,165,233,0.3); transition: filter 0.2s;
}
.btn-save:hover { filter: brightness(1.15); }
.btn-save:active { transform: scale(0.98); }
.btn-secondary {
  background: #1e293b; color: var(--text-main); font-weight: 600;
  border: 1px solid #334155; border-radius: 6px; padding: 8px 14px;
  cursor: pointer; font-size: 0.8rem; transition: all 0.2s;
}
.btn-secondary:hover { border-color: var(--neon-red); color: var(--neon-red); }

.toast {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: rgba(15,23,42,0.95); border: 1px solid var(--neon-cyan);
  box-shadow: 0 0 15px rgba(0,240,255,0.5); padding: 10px 20px; border-radius: 8px;
  font-size: 0.85rem; font-weight: bold; color: var(--neon-cyan);
  opacity: 0; pointer-events: none; transition: opacity 0.3s; z-index: 999;
}
.toast.show { opacity: 1; }
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>🤖 DB-ROBOT OTTO CONTROL PANEL</h1>
    <div style="font-size:0.75rem; color:var(--text-muted); letter-spacing:1px;">FIRMWARE TIẾNG VIỆT • GIAO DIỆN QUẢN TRỊ PORT :8080</div>
    <div class="badges">
      <div class="badge cyan" id="b-ip">IP: Đang kết nối...</div>
      <div class="badge green" id="b-bat">🔋 --%</div>
      <div class="badge pink" id="b-srv">⚡ Megabot</div>
    </div>
  </div>

  <!-- Quick Action Buttons -->
  <div class="card">
    <div class="card-title">⚡ HÀNH ĐỘNG NHANH (QUICK ACTIONS)</div>
    <div class="quick-grid">
      <button class="btn-quick btn-swing" onclick="sendAction('swing', {steps:4, speed:1000})">🌸 LẮC LƯ</button>
      <button class="btn-quick btn-dance" onclick="sendAction('dance', {steps:4, speed:1000})">💃 NHẢY MÚA</button>
      <button class="btn-quick btn-walk" onclick="sendAction('walk', {steps:4, dir:1, speed:1000})">🚀 TỰ ĐI</button>
      <button class="btn-quick btn-stop" onclick="sendAction('stop')">🛑 STOP</button>
    </div>

    <!-- Direction Pad -->
    <div class="dpad-container">
      <div class="dpad-row">
        <button class="btn-dir" id="k-q" onclick="sendAction('turn', {steps:2, dir:1, speed:1200})">↺<span class="sub">Q Quay T</span></button>
        <button class="btn-dir" id="k-w" onclick="sendAction('walk', {steps:2, dir:1, speed:1000})">▲<span class="sub">W Tiến</span></button>
        <button class="btn-dir" id="k-e" onclick="sendAction('turn', {steps:2, dir:-1, speed:1200})">↻<span class="sub">E Quay P</span></button>
      </div>
      <div class="dpad-row">
        <button class="btn-dir" id="k-a" onclick="sendAction('turn', {steps:2, dir:1, speed:1200})">◄<span class="sub">A Trái</span></button>
        <button class="btn-dir" id="k-s" onclick="sendAction('walk', {steps:2, dir:-1, speed:1000})">▼<span class="sub">S Lùi</span></button>
        <button class="btn-dir" id="k-d" onclick="sendAction('turn', {steps:2, dir:-1, speed:1200})">►<span class="sub">D Phải</span></button>
      </div>
    </div>

    <!-- Extra Moves -->
    <div class="extra-grid">
      <button class="btn-extra" onclick="sendAction('jump', {steps:2, speed:600})">🤸 Nhảy cao</button>
      <button class="btn-extra" onclick="sendAction('moonwalk', {steps:2, dir:-1, speed:900})">🕺 Moonwalk</button>
      <button class="btn-extra" onclick="sendAction('hand_wave', {dir:1})">👋 Vẫy tay</button>
      <button class="btn-extra" onclick="sendAction('sit')">🪑 Ngồi xuống</button>
      <button class="btn-extra" onclick="sendAction('fitness', {steps:3, speed:1000})">🏋️ Thể dục</button>
      <button class="btn-extra" onclick="sendAction('takeoff', {steps:3, speed:400})">🚁 Cất cánh</button>
      <button class="btn-extra" onclick="sendAction('tiptoe_swing', {steps:3, speed:900})">✨ Kiễng chân</button>
      <button class="btn-extra" onclick="sendAction('home')">🏠 Vị trí gốc</button>
    </div>

    <!-- Keys Guide -->
    <div class="keys-guide">
      <div><kbd>W</kbd> Tiến | <kbd>S</kbd> Lùi | <kbd>A</kbd> Trái | <kbd>D</kbd> Phải</div>
      <div><kbd>Q</kbd> Quay trái | <kbd>E</kbd> Quay phải | <kbd>Space</kbd> Dừng</div>
    </div>
  </div>

  <!-- Server Selection -->
  <div class="card">
    <div class="card-title">🌐 CHỌN MÁY CHỦ WEBSOCKET (SERVER CONNECT)</div>
    <div class="radio-group">
      <label class="radio-card">
        <input type="radio" name="srv_opt" value="megabot" id="opt-megabot" onchange="onServerChange()">
        <div class="radio-text">
          <strong>⚡ Server Megabot Render (Của bạn)</strong>
          <small>wss://robot-megabot.onrender.com/ws/megabot</small>
        </div>
      </label>
      <label class="radio-card">
        <input type="radio" name="srv_opt" value="xiaozhi" id="opt-xiaozhi" onchange="onServerChange()">
        <div class="radio-text">
          <strong>🌐 Server Xiaozhi Cloud (Gốc / Tenclass)</strong>
          <small>wss://api.tenclass.net/xiaozhi/v1/</small>
        </div>
      </label>
      <label class="radio-card">
        <input type="radio" name="srv_opt" value="custom" id="opt-custom" onchange="onServerChange()">
        <div class="radio-text">
          <strong>🛠️ Server tùy chỉnh (Custom WebSocket)</strong>
          <small>Nhập địa chỉ WebSocket máy chủ riêng</small>
        </div>
      </label>
    </div>
    <div id="custom-url-box" style="display:none; margin-top:10px;">
      <input type="text" id="custom-ws-url" class="input-text" placeholder="wss://your-domain.com/ws">
    </div>
    <button class="btn-save" style="margin-top:14px;" onclick="saveServer()">💾 LƯU & KẾT NỐI SERVER</button>
  </div>

  <!-- Screen Orientation -->
  <div class="card">
    <div class="card-title">🖥️ CẤU HÌNH HƯỚNG HIỂN THỊ MÀN HÌNH</div>
    <div class="radio-group">
      <label class="radio-card">
        <input type="radio" name="scr_ori" value="landscape" id="scr-land">
        <div class="radio-text">
          <strong>🖥️ Chiều ngang (Landscape - Mặc định khuyên dùng)</strong>
          <small>Hoán đổi toạ độ X-Y (Swap XY = true)</small>
        </div>
      </label>
      <label class="radio-card">
        <input type="radio" name="scr_ori" value="portrait" id="scr-port">
        <div class="radio-text">
          <strong>📱 Chiều dọc (Portrait - Cài đặt gốc)</strong>
          <small>Toạ độ chuẩn ban đầu (Swap XY = false)</small>
        </div>
      </label>
    </div>
    <div style="display:flex; gap:16px; margin-top:10px; font-size:0.8rem;">
      <label><input type="checkbox" id="mir-x"> Đảo gương trục X</label>
      <label><input type="checkbox" id="mir-y"> Đảo gương trục Y</label>
    </div>
    <button class="btn-save" style="margin-top:14px;" onclick="saveDisplay()">💾 LƯU CHIỀU MÀN HÌNH (CẦN KHỞI ĐỘNG LẠI)</button>
  </div>

  <!-- Servo Calibration (Trims) -->
  <div class="card">
    <div class="card-title">⚙️ HIỆU CHỈNH GÓC LỆCH 6 ĐỘNG CƠ (TRIMS)</div>
    <div id="sliders">
      <div class="slider-row"><span class="slider-label">🦵 Chân trái:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-ll" oninput="updTrim(this)"><span class="slider-val" id="v-tr-ll">0°</span></div>
      <div class="slider-row"><span class="slider-label">🦵 Chân phải:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-rl" oninput="updTrim(this)"><span class="slider-val" id="v-tr-rl">0°</span></div>
      <div class="slider-row"><span class="slider-label">🦶 Bàn chân trái:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-lf" oninput="updTrim(this)"><span class="slider-val" id="v-tr-lf">0°</span></div>
      <div class="slider-row"><span class="slider-label">🦶 Bàn chân phải:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-rf" oninput="updTrim(this)"><span class="slider-val" id="v-tr-rf">0°</span></div>
      <div class="slider-row"><span class="slider-label">✋ Tay trái:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-lh" oninput="updTrim(this)"><span class="slider-val" id="v-tr-lh">0°</span></div>
      <div class="slider-row"><span class="slider-label">✋ Tay phải:</span><input type="range" min="-30" max="30" value="0" class="slider-input" id="tr-rh" oninput="updTrim(this)"><span class="slider-val" id="v-tr-rh">0°</span></div>
    </div>
    <div style="display:flex; gap:8px; margin-top:10px;">
      <button class="btn-save" style="flex:2;" onclick="saveTrims()">💾 LƯU GÓC LỆCH VÀO CHIP</button>
      <button class="btn-secondary" style="flex:1;" onclick="resetTrims()">🔄 VỀ 0</button>
    </div>
  </div>

  <!-- System info & Reboot -->
  <div class="card">
    <div class="card-title">ℹ️ THÔNG TIN HỆ THỐNG & KHỞI ĐỘNG LẠI</div>
    <div style="font-size:0.8rem; color:var(--text-muted); line-height:1.6; margin-bottom:12px;">
      <div>Free Heap RAM: <strong id="s-heap" style="color:var(--neon-green)">--</strong> KB</div>
      <div>Micro: INMP441 (16kHz) | Loa: MAX98357A (16kHz Simplex)</div>
      <div>Màn hình: ST7789 SPI 240x240 | Pin: ADC GPIO 14 (Chg: GPIO 21)</div>
    </div>
    <button class="btn-secondary" style="width:100%; padding:10px; border-color:var(--neon-red); color:var(--neon-red);" onclick="rebootRobot()">🔄 KHỞI ĐỘNG LẠI ROBOT (REBOOT)</button>
  </div>

</div>

<div class="toast" id="toast">Thông báo</div>

<script>
function showToast(msg) {
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function updTrim(el) {
  document.getElementById('v-' + el.id).innerText = el.value + '°';
}

function onServerChange() {
  const isCustom = document.getElementById('opt-custom').checked;
  document.getElementById('custom-url-box').style.display = isCustom ? 'block' : 'none';
}

function sendAction(act, extra = {}) {
  fetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: act, ...extra })
  }).then(r => r.json()).then(d => {
    showToast('Lệnh: ' + act);
  }).catch(e => {
    console.error(e);
  });
}

function saveServer() {
  let srv = 'megabot';
  if (document.getElementById('opt-xiaozhi').checked) srv = 'xiaozhi';
  else if (document.getElementById('opt-custom').checked) srv = 'custom';
  const url = document.getElementById('custom-ws-url').value.trim();

  fetch('/api/server', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ server_type: srv, url: url })
  }).then(r => r.json()).then(d => {
    showToast('Đã lưu máy chủ! Đang khởi động lại...');
    setTimeout(rebootRobot, 1000);
  });
}

function saveDisplay() {
  const isLand = document.getElementById('scr-land').checked;
  const mx = document.getElementById('mir-x').checked;
  const my = document.getElementById('mir-y').checked;

  fetch('/api/display', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ swap_xy: isLand, mirror_x: mx, mirror_y: my })
  }).then(r => r.json()).then(d => {
    showToast('Đã lưu chiều màn hình! Đang khởi động lại...');
    setTimeout(rebootRobot, 1000);
  });
}

function saveTrims() {
  const trims = {
    left_leg: parseInt(document.getElementById('tr-ll').value),
    right_leg: parseInt(document.getElementById('tr-rl').value),
    left_foot: parseInt(document.getElementById('tr-lf').value),
    right_foot: parseInt(document.getElementById('tr-rf').value),
    left_hand: parseInt(document.getElementById('tr-lh').value),
    right_hand: parseInt(document.getElementById('tr-rh').value)
  };
  fetch('/api/trims', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trims)
  }).then(r => r.json()).then(d => {
    showToast('Đã lưu góc lệch 6 servo vào chip!');
  });
}

function resetTrims() {
  ['tr-ll', 'tr-rl', 'tr-lf', 'tr-rf', 'tr-lh', 'tr-rh'].forEach(id => {
    const el = document.getElementById(id);
    el.value = 0;
    updTrim(el);
  });
  saveTrims();
}

function rebootRobot() {
  if (confirm('Khởi động lại robot ngay bây giờ?')) {
    fetch('/api/reboot', { method: 'POST' }).then(() => {
      showToast('Robot đang khởi động lại...');
    });
  }
}

// Fetch status on load
function loadStatus() {
  fetch('/api/status').then(r => r.json()).then(d => {
    if (d.ip) document.getElementById('b-ip').innerText = 'IP: ' + d.ip + ':8080';
    if (d.battery !== undefined) document.getElementById('b-bat').innerText = '🔋 ' + d.battery + '%' + (d.charging ? ' (Sạc)' : '');
    if (d.server_type) {
      if (d.server_type === 'megabot') {
        document.getElementById('opt-megabot').checked = true;
        document.getElementById('b-srv').innerText = '⚡ Megabot';
      } else if (d.server_type === 'xiaozhi') {
        document.getElementById('opt-xiaozhi').checked = true;
        document.getElementById('b-srv').innerText = '🌐 Xiaozhi';
      } else {
        document.getElementById('opt-custom').checked = true;
        document.getElementById('b-srv').innerText = '🛠️ Tùy chỉnh';
      }
      onServerChange();
    }
    if (d.custom_ws_url) document.getElementById('custom-ws-url').value = d.custom_ws_url;

    if (d.swap_xy) document.getElementById('scr-land').checked = true;
    else document.getElementById('scr-port').checked = true;
    if (d.mirror_x) document.getElementById('mir-x').checked = true;
    if (d.mirror_y) document.getElementById('mir-y').checked = true;

    if (d.trims) {
      if (d.trims.left_leg !== undefined) { document.getElementById('tr-ll').value = d.trims.left_leg; updTrim(document.getElementById('tr-ll')); }
      if (d.trims.right_leg !== undefined) { document.getElementById('tr-rl').value = d.trims.right_leg; updTrim(document.getElementById('tr-rl')); }
      if (d.trims.left_foot !== undefined) { document.getElementById('tr-lf').value = d.trims.left_foot; updTrim(document.getElementById('tr-lf')); }
      if (d.trims.right_foot !== undefined) { document.getElementById('tr-rf').value = d.trims.right_foot; updTrim(document.getElementById('tr-rf')); }
      if (d.trims.left_hand !== undefined) { document.getElementById('tr-lh').value = d.trims.left_hand; updTrim(document.getElementById('tr-lh')); }
      if (d.trims.right_hand !== undefined) { document.getElementById('tr-rh').value = d.trims.right_hand; updTrim(document.getElementById('tr-rh')); }
    }
    if (d.free_heap) document.getElementById('s-heap').innerText = Math.round(d.free_heap / 1024);
  }).catch(e => console.log('Status fetch error:', e));
}

// Keyboard controls
const keyMap = {
  'KeyW': () => { sendAction('walk', {steps:2, dir:1, speed:1000}); flashKey('k-w'); },
  'KeyS': () => { sendAction('walk', {steps:2, dir:-1, speed:1000}); flashKey('k-s'); },
  'KeyA': () => { sendAction('turn', {steps:2, dir:1, speed:1200}); flashKey('k-a'); },
  'KeyD': () => { sendAction('turn', {steps:2, dir:-1, speed:1200}); flashKey('k-d'); },
  'KeyQ': () => { sendAction('turn', {steps:2, dir:1, speed:1200}); flashKey('k-q'); },
  'KeyE': () => { sendAction('turn', {steps:2, dir:-1, speed:1200}); flashKey('k-e'); },
  'Space': () => { sendAction('stop'); }
};
function flashKey(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('active'); setTimeout(() => el.classList.remove('active'), 200); }
}
window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (keyMap[e.code]) { e.preventDefault(); keyMap[e.code](); }
});

loadStatus();
setInterval(loadStatus, 5000);
</script>
</body>
</html>
)rawliteral";

