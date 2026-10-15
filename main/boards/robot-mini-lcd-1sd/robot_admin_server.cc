#include "robot_admin_server.h"
#include "system_info.h"
#include <esp_log.h>
#include <esp_system.h>
#include <cJSON.h>
#include <cstring>
#include <cstdlib>

#define TAG "RobotAdminServer"

static RobotAdminServer* s_admin_server = nullptr;

static const char kAdminHtml[] = R"rawliteral(<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DB-ROBOT CONTROL PANEL</title>
<style>
:root {
  --bg: #090d16;
  --panel: #111827;
  --border: #1f293d;
  --cyan: #00e5ff;
  --blue: #38bdf8;
  --magenta: #ec4899;
  --green: #10b981;
  --amber: #f59e0b;
  --red: #ef4444;
  --text: #f1f5f9;
  --text-dim: #94a3b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Courier New', monospace;
  padding: 16px;
  line-height: 1.5;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--border);
  padding-bottom: 12px;
  margin-bottom: 16px;
}
.title-group { display: flex; align-items: center; gap: 12px; }
.logo {
  width: 42px; height: 42px;
  background: linear-gradient(135deg, var(--cyan), var(--blue));
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px;
}
h1 { font-size: 20px; font-weight: 700; color: var(--cyan); letter-spacing: 1px; }
.subtitle { font-size: 11px; color: var(--text-dim); }
.status-pill {
  padding: 4px 10px; border-radius: 999px;
  background: rgba(16, 185, 129, 0.15); border: 1px solid var(--green);
  color: var(--green); font-size: 12px; font-weight: 600;
}
.alert-box {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  color: #fde68a;
  margin-bottom: 16px;
  line-height: 1.6;
}
.quick-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
  color: #fff;
}
.btn-wiggle { background: linear-gradient(135deg, #a855f7, var(--magenta)); }
.btn-dance { background: linear-gradient(135deg, #0284c7, var(--cyan)); }
.btn-wander { background: linear-gradient(135deg, #059669, var(--green)); }
.btn-stop { background: linear-gradient(135deg, #b91c1c, var(--red)); }
.btn:hover { transform: translateY(-2px); opacity: 0.9; }
.btn:active { transform: translateY(0); }
.key-hints {
  background: #0f172a;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-dim);
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-bottom: 20px;
}
.key-hints kbd {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 2px 6px;
  color: var(--cyan);
  font-weight: 600;
}
.tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}
.tab {
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.tab.active {
  color: var(--cyan);
  border-bottom-color: var(--cyan);
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
}
.card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--cyan);
  text-transform: uppercase;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 12px;
}
.form-row label { color: var(--text-dim); }
select, input[type="number"], input[type="text"] {
  background: #0b1120;
  border: 1px solid #293548;
  border-radius: 6px;
  color: #fff;
  padding: 5px 8px;
  font-size: 12px;
  min-width: 140px;
  outline: none;
}
select:focus, input:focus { border-color: var(--cyan); }
.slider-group {
  margin-bottom: 14px;
}
.slider-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}
.slider-header span:last-child {
  color: var(--cyan);
  font-weight: 700;
}
input[type="range"] {
  width: 100%;
  accent-color: var(--cyan);
}
.actions-footer {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.btn-save-reboot {
  background: linear-gradient(135deg, #059669, #10b981);
}
.btn-save {
  background: linear-gradient(135deg, #0284c7, var(--cyan));
}
.btn-reset {
  background: #334155;
  color: #f1f5f9;
}
.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  background: #1e293b;
  border: 1px solid var(--cyan);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.5);
  display: none;
  z-index: 999;
}
@media (max-width: 600px) {
  .quick-bar { grid-template-columns: repeat(2, 1fr); }
  .grid-cards { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="header">
  <div class="title-group">
    <div class="logo">🤖</div>
    <div>
      <h1>DB-ROBOT CONTROL PANEL</h1>
      <div class="subtitle">CONTROL PANEL V2 - HIỆU CHỈNH CHÂN GPIO & CẤU HÌNH ROBOT</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:8px;">
    <div id="pinBadge" style="padding:4px 12px;border-radius:999px;background:rgba(0,229,255,0.15);border:1px solid var(--cyan);color:var(--cyan);font-size:12px;font-weight:700;font-family:monospace;">MÃ PIN: ...</div>
    <div class="status-pill">ONLINE</div>
  </div>
</div>

<div class="alert-box">
  🔢 <b>Mã kết nối Robot:</b> Dùng mã PIN 6 số hiển thị ở góc trên để ghép nối Robot vào Web Quản Trị.<br>
  ⚡ <b>Mẹo an toàn:</b> Giữ nút <b>BOOT 3 giây</b> (trong 15s đầu khi bật nguồn) để xoá bản đồ chân, tự khởi động lại bằng cấu hình mặc định.<br>
  💡 <b>Sai chân màn hình cũng không mất web:</b> Cổng 8080 luôn mở độc lập. Chưa có Wi-Fi thì kết nối vào sóng <b>megadinh-xxxx</b> rồi mở <b>http://192.168.4.1:8080</b>.
</div>

<div class="quick-bar">
  <button class="btn btn-wiggle" onclick="sendControl('wiggle')">💃 LẮC LƯ</button>
  <button class="btn btn-dance" onclick="sendControl('dance')">🕺 NHẢY MÚA</button>
  <button class="btn btn-wander" onclick="sendControl('wander')">🧭 TỰ ĐI</button>
  <button class="btn btn-stop" onclick="sendControl('stop')">🛑 STOP</button>
</div>

<div class="key-hints">
  <span><kbd>W</kbd> Tiến</span>
  <span><kbd>S</kbd> Lùi</span>
  <span><kbd>A</kbd> Quay trái</span>
  <span><kbd>D</kbd> Quay phải</span>
  <span><kbd>Q</kbd> Xoay ↺</span>
  <span><kbd>E</kbd> Xoay ↻</span>
  <span><kbd>Space</kbd> DỪNG</span>
  <span><kbd>↑ / ↓</kbd> Tốc độ</span>
</div>

<div class="tabs">
  <button class="tab active" onclick="switchTab(0)">🗺️ BẢN ĐỒ CHÂN GPIO</button>
  <button class="tab" onclick="switchTab(1)">⚙️ HIỆU CHỈNH ĐỘNG CƠ</button>
  <button class="tab" onclick="switchTab(2)">🛡️ CẢM BIẾN AN TOÀN & PIN</button>
</div>

<!-- TAB 1: GPIO PIN MAPPING -->
<div class="tab-content active" id="tab-0">
  <div class="grid-cards">
    <!-- ĐỘNG CƠ MX1616 -->
    <div class="card">
      <div class="card-title">🚗 ĐỘNG CƠ BÁNH XE (MX1616)</div>
      <div class="form-row"><label>IN1 - BÁNH TRÁI TIẾN</label><select id="p_m_in1"></select></div>
      <div class="form-row"><label>IN2 - BÁNH TRÁI LÙI</label><select id="p_m_in2"></select></div>
      <div class="form-row"><label>IN3 - BÁNH PHẢI TIẾN</label><select id="p_m_in3"></select></div>
      <div class="form-row"><label>IN4 - BÁNH PHẢI LÙI</label><select id="p_m_in4"></select></div>
    </div>

    <!-- MÀN HÌNH OLED -->
    <div class="card">
      <div class="card-title">🖥️ MÀN HÌNH OLED I2C</div>
      <div class="form-row"><label>SDA DATA</label><select id="p_o_sda"></select></div>
      <div class="form-row"><label>SCL CLOCK</label><select id="p_o_scl"></select></div>
      <div class="form-row">
        <label>LOẠI CHIP</label>
        <select id="p_o_chip">
          <option value="0">SSD1306</option>
          <option value="1">SH1106</option>
        </select>
      </div>
      <div class="form-row">
        <label>KÍCH THƯỚC</label>
        <select id="p_o_h">
          <option value="64">128 x 64</option>
          <option value="32">128 x 32</option>
        </select>
      </div>
    </div>

    <!-- MICRO INMP441 -->
    <div class="card">
      <div class="card-title">🎤 MICRO INMP441 (I2S)</div>
      <div class="form-row"><label>WS (LRCK)</label><select id="p_mic_ws"></select></div>
      <div class="form-row"><label>SCK (BCLK)</label><select id="p_mic_sck"></select></div>
      <div class="form-row"><label>SD - DOUT</label><select id="p_mic_sd"></select></div>
    </div>

    <!-- LOA MAX98357A -->
    <div class="card">
      <div class="card-title">🔊 LOA MAX98357A (I2S)</div>
      <div class="form-row"><label>DIN (DATA IN)</label><select id="p_spk_din"></select></div>
      <div class="form-row"><label>BCLK (CLOCK)</label><select id="p_spk_bclk"></select></div>
      <div class="form-row"><label>LRC (WS)</label><select id="p_spk_lrc"></select></div>
    </div>

    <!-- ĐÈN & CẢM BIẾN CHẠM -->
    <div class="card">
      <div class="card-title">💡 ĐÈN LED & CẢM BIẾN CHẠM</div>
      <div class="form-row"><label>WS2812 DIN (RGB)</label><select id="p_rgb_din"></select></div>
      <div class="form-row"><label>SỐ BÓNG WS2812</label><input type="number" id="p_rgb_cnt" min="1" max="64" value="8"></div>
      <div class="form-row"><label>ĐÈN HIỆU COB / LAMP</label><select id="p_lamp_io"></select></div>
      <div class="form-row"><label>CHÂN CẢM BIẾN CHẠM TTP223</label><select id="p_tch_io"></select></div>
      <div class="form-row">
        <label>CHẠM LÀ MỨC</label>
        <select id="p_tch_lvl">
          <option value="0">THẤP (Active LOW)</option>
          <option value="1">CAO (Active HIGH)</option>
        </select>
      </div>
    </div>

    <!-- THẺ NHỚ & CẢM BIẾN KHOẢNG CÁCH -->
    <div class="card">
      <div class="card-title">📡 CẢM BIẾN MỞ RỘNG & THẺ NHỚ</div>
      <div class="form-row"><label>VL53L0X SDA</label><select id="p_vl_sda"></select></div>
      <div class="form-row"><label>VL53L0X SCL</label><select id="p_vl_scl"></select></div>
      <div class="form-row"><label>HC-SR04 TRIG</label><select id="p_hc_trig"></select></div>
      <div class="form-row"><label>HC-SR04 ECHO</label><select id="p_hc_echo"></select></div>
      <div class="form-row"><label>THẺ SD - CS</label><select id="p_sd_cs"></select></div>
      <div class="form-row"><label>THẺ SD - CLK</label><select id="p_sd_clk"></select></div>
      <div class="form-row"><label>THẺ SD - MOSI</label><select id="p_sd_mosi"></select></div>
      <div class="form-row"><label>THẺ SD - MISO</label><select id="p_sd_miso"></select></div>
      <div class="form-row"><label>CHÂN ĐO ÁP PIN (ADC)</label><select id="p_bat_adc"></select></div>
    </div>
  </div>

  <div class="actions-footer">
    <button class="btn btn-reset" onclick="resetDefaults()">♻️ VỀ MẶC ĐỊNH</button>
    <button class="btn btn-save" onclick="savePins(false)">💾 LƯU VÀO CHIP</button>
    <button class="btn btn-save-reboot" onclick="savePins(true)">💾 LƯU & KHỞI ĐỘNG LẠI</button>
  </div>
</div>

<!-- TAB 2: MOTOR CALIBRATION -->
<div class="tab-content" id="tab-1">
  <div class="grid-cards">
    <div class="card">
      <div class="card-title">⚙️ HIỆU CHỈNH ĐỘNG CƠ BÁNH XE</div>
      <div class="form-row">
        <label>LOẠI DRIVER ĐANG DÙNG</label>
        <select id="c_drv_t">
          <option value="0">MX1616 / DRV8833</option>
          <option value="1">L298N MINI</option>
        </select>
      </div>
      <div class="slider-group">
        <div class="slider-header">
          <span>CÂN BẰNG BÁNH TRÁI (LEFT TRIM)</span>
          <span id="txt_l_trim">0%</span>
        </div>
        <input type="range" id="c_l_trim" min="-50" max="50" value="0" oninput="updateSliderVal('l_trim', '%')">
      </div>
      <div class="slider-group">
        <div class="slider-header">
          <span>CÂN BẰNG BÁNH PHẢI (RIGHT TRIM)</span>
          <span id="txt_r_trim">0%</span>
        </div>
        <input type="range" id="c_r_trim" min="-50" max="50" value="0" oninput="updateSliderVal('r_trim', '%')">
      </div>
      <div class="slider-group">
        <div class="slider-header">
          <span>DUTY TỐI THIỂU (MIN PWM / BÙ NGƯỠNG CHẾT)</span>
          <span id="txt_min_pwm">20</span>
        </div>
        <input type="range" id="c_min_pwm" min="0" max="150" value="20" oninput="updateSliderVal('min_pwm', '')">
      </div>
      <div style="margin-top:16px;">
        <button class="btn btn-save" onclick="saveMotorCalib()">💾 LƯU VÀO CHIP</button>
      </div>
    </div>
  </div>
</div>

<!-- TAB 3: SAFETY & BATTERY -->
<div class="tab-content" id="tab-2">
  <div class="grid-cards">
    <div class="card">
      <div class="card-title">🛡️ HIỆU CHỈNH CẢM BIẾN AN TOÀN</div>
      <div class="form-row">
        <label>CHẾ ĐỘ LÀM VIỆC</label>
        <select id="c_safe_m">
          <option value="0">🛡️ CHỐNG RƠI MÉP BÀN</option>
          <option value="1">🚧 TRÁNH VẬT CẢN</option>
        </select>
      </div>
      <div class="slider-group">
        <div class="slider-header">
          <span>NGƯỠNG VẬT CẢN (DƯỚI MỨC NÀY THÌ DỪNG)</span>
          <span id="txt_obs_cm">28 cm</span>
        </div>
        <input type="range" id="c_obs_cm" min="5" max="80" value="28" oninput="updateSliderVal('obs_cm', ' cm')">
      </div>
      <div class="slider-group">
        <div class="slider-header">
          <span>NGƯỠNG MÉP BÀN CHỐNG RƠI</span>
          <span id="txt_clf_mm">50 mm</span>
        </div>
        <input type="range" id="c_clf_mm" min="20" max="150" value="50" oninput="updateSliderVal('clf_mm', ' mm')">
      </div>
      <div class="form-row">
        <label>BẬT CẢM BIẾN LASER</label>
        <input type="checkbox" id="c_las_en" checked style="width:20px;height:20px;">
      </div>
      <div style="margin-top:16px;">
        <button class="btn btn-save" onclick="saveSafetyCalib()">💾 LƯU VÀO CHIP</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast">Đã lưu thành công!</div>

<script>
const gpios = [-1];
for (let i = 0; i <= 48; i++) gpios.push(i);

function populateSelect(id, selectedVal) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = '';
  gpios.forEach(pin => {
    const opt = document.createElement('option');
    opt.value = pin;
    opt.textContent = pin === -1 ? '- không lắp -' : 'GPIO ' + pin;
    if (pin === selectedVal) opt.selected = true;
    el.appendChild(opt);
  });
}

function switchTab(index) {
  document.querySelectorAll('.tab').forEach((t, i) => t.classList.toggle('active', i === index));
  document.querySelectorAll('.tab-content').forEach((c, i) => c.classList.toggle('active', i === index));
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function updateSliderVal(id, unit) {
  const slider = document.getElementById('c_' + id);
  const txt = document.getElementById('txt_' + id);
  if (slider && txt) txt.textContent = slider.value + unit;
}

let curSpeed = 80;

function sendControl(action, dir) {
  const payload = { action: action };
  if (dir) payload.direction = dir;
  payload.speed = curSpeed;
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(data => {
    showToast('Đã gửi lệnh: ' + (dir || action));
  }).catch(e => console.error(e));
}

window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const k = e.key.toLowerCase();
  if (k === 'w') sendControl('move', 'forward');
  else if (k === 's') sendControl('move', 'backward');
  else if (k === 'a') sendControl('move', 'left');
  else if (k === 'd') sendControl('move', 'right');
  else if (k === 'q') sendControl('move', 'spin_left');
  else if (k === 'e') sendControl('move', 'spin_right');
  else if (k === ' ') { e.preventDefault(); sendControl('stop'); }
  else if (e.key === 'ArrowUp') { curSpeed = Math.min(100, curSpeed + 5); showToast('Tốc độ: ' + curSpeed + '%'); }
  else if (e.key === 'ArrowDown') { curSpeed = Math.max(20, curSpeed - 5); showToast('Tốc độ: ' + curSpeed + '%'); }
});

function loadConfig() {
  fetch('/api/config')
    .then(r => r.json())
    .then(data => {
      const p = data.pins || {};
      const c = data.calib || {};
      const pinMap = {
        p_m_in1: p.motor_in1, p_m_in2: p.motor_in2, p_m_in3: p.motor_in3, p_m_in4: p.motor_in4,
        p_o_sda: p.oled_sda, p_o_scl: p.oled_scl,
        p_mic_ws: p.mic_ws, p_mic_sck: p.mic_sck, p_mic_sd: p.mic_sd,
        p_spk_din: p.spk_din, p_spk_bclk: p.spk_bclk, p_spk_lrc: p.spk_lrc,
        p_rgb_din: p.led_rgb_din, p_lamp_io: p.lamp_gpio,
        p_tch_io: p.touch_gpio,
        p_vl_sda: p.vl53_sda, p_vl_scl: p.vl53_scl,
        p_hc_trig: p.hcsr04_trig, p_hc_echo: p.hcsr04_echo,
        p_sd_cs: p.sd_cs, p_sd_clk: p.sd_clk, p_sd_mosi: p.sd_mosi, p_sd_miso: p.sd_miso,
        p_bat_adc: p.bat_adc
      };
      for (const [id, val] of Object.entries(pinMap)) {
        populateSelect(id, val !== undefined ? val : -1);
      }
      if (data.pin_code && document.getElementById('pinBadge')) {
        document.getElementById('pinBadge').innerText = `MÃ PIN: ${data.pin_code}`;
      }
      if (document.getElementById('p_o_chip')) document.getElementById('p_o_chip').value = p.oled_chip || 0;
      if (document.getElementById('p_o_h')) document.getElementById('p_o_h').value = p.oled_height || 64;
      if (document.getElementById('p_rgb_cnt')) document.getElementById('p_rgb_cnt').value = p.led_rgb_count || 8;
      if (document.getElementById('p_tch_lvl')) document.getElementById('p_tch_lvl').value = p.touch_level || 0;

      if (document.getElementById('c_drv_t')) document.getElementById('c_drv_t').value = c.driver_type || 0;
      if (document.getElementById('c_l_trim')) document.getElementById('c_l_trim').value = c.left_trim || 0;
      if (document.getElementById('c_r_trim')) document.getElementById('c_r_trim').value = c.right_trim || 0;
      if (document.getElementById('c_min_pwm')) document.getElementById('c_min_pwm').value = c.min_pwm || 20;
      updateSliderVal('l_trim', '%');
      updateSliderVal('r_trim', '%');
      updateSliderVal('min_pwm', '');

      if (document.getElementById('c_safe_m')) document.getElementById('c_safe_m').value = c.safety_mode || 0;
      if (document.getElementById('c_obs_cm')) document.getElementById('c_obs_cm').value = c.obstacle_cm || 28;
      if (document.getElementById('c_clf_mm')) document.getElementById('c_clf_mm').value = c.cliff_mm || 50;
      if (document.getElementById('c_las_en')) document.getElementById('c_las_en').checked = !!c.laser_enabled;
      updateSliderVal('obs_cm', ' cm');
      updateSliderVal('clf_mm', ' mm');
    })
    .catch(e => console.error(e));
}

function savePins(reboot) {
  const payload = {
    reboot: reboot,
    motor_in1: parseInt(document.getElementById('p_m_in1').value),
    motor_in2: parseInt(document.getElementById('p_m_in2').value),
    motor_in3: parseInt(document.getElementById('p_m_in3').value),
    motor_in4: parseInt(document.getElementById('p_m_in4').value),
    oled_sda: parseInt(document.getElementById('p_o_sda').value),
    oled_scl: parseInt(document.getElementById('p_o_scl').value),
    oled_chip: parseInt(document.getElementById('p_o_chip').value),
    oled_height: parseInt(document.getElementById('p_o_h').value),
    mic_ws: parseInt(document.getElementById('p_mic_ws').value),
    mic_sck: parseInt(document.getElementById('p_mic_sck').value),
    mic_sd: parseInt(document.getElementById('p_mic_sd').value),
    spk_din: parseInt(document.getElementById('p_spk_din').value),
    spk_bclk: parseInt(document.getElementById('p_spk_bclk').value),
    spk_lrc: parseInt(document.getElementById('p_spk_lrc').value),
    led_rgb_din: parseInt(document.getElementById('p_rgb_din').value),
    led_rgb_count: parseInt(document.getElementById('p_rgb_cnt').value),
    lamp_gpio: parseInt(document.getElementById('p_lamp_io').value),
    touch_gpio: parseInt(document.getElementById('p_tch_io').value),
    touch_level: parseInt(document.getElementById('p_tch_lvl').value),
    vl53_sda: parseInt(document.getElementById('p_vl_sda').value),
    vl53_scl: parseInt(document.getElementById('p_vl_scl').value),
    hcsr04_trig: parseInt(document.getElementById('p_hc_trig').value),
    hcsr04_echo: parseInt(document.getElementById('p_hc_echo').value),
    sd_cs: parseInt(document.getElementById('p_sd_cs').value),
    sd_clk: parseInt(document.getElementById('p_sd_clk').value),
    sd_mosi: parseInt(document.getElementById('p_sd_mosi').value),
    sd_miso: parseInt(document.getElementById('p_sd_miso').value),
    bat_adc: parseInt(document.getElementById('p_bat_adc').value)
  };
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(data => {
    showToast(reboot ? 'Đã lưu! Robot đang khởi động lại...' : 'Đã lưu thành công vào chip!');
  }).catch(e => showToast('Lỗi lưu cấu hình!'));
}

function saveMotorCalib() {
  const payload = {
    driver_type: parseInt(document.getElementById('c_drv_t').value),
    left_trim: parseInt(document.getElementById('c_l_trim').value),
    right_trim: parseInt(document.getElementById('c_r_trim').value),
    min_pwm: parseInt(document.getElementById('c_min_pwm').value)
  };
  fetch('/api/motor_calib', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(data => {
    showToast('Đã áp dụng hiệu chỉnh động cơ!');
  }).catch(e => showToast('Lỗi hiệu chỉnh động cơ!'));
}

function resetDefaults() {
  if (!confirm('Bạn có chắc chắn muốn xoá toàn bộ cấu hình và về mặc định?')) return;
  fetch('/api/reset', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      showToast('Đang khôi phục mặc định & khởi động lại...');
      setTimeout(() => location.reload(), 3000);
    });
}

window.onload = loadConfig;
</script>
</body>
</html>
)rawliteral";

RobotAdminServer::RobotAdminServer(RobotPinConfig& pin_cfg, RobotCalibration& calib, RobotController* controller)
    : pin_cfg_(pin_cfg), calib_(calib), controller_(controller) {
    s_admin_server = this;
}

RobotAdminServer::~RobotAdminServer() {
    Stop();
    if (s_admin_server == this) {
        s_admin_server = nullptr;
    }
}

bool RobotAdminServer::Start(int port) {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = port;
    config.max_open_sockets = 7;
    config.ctrl_port = 32770;
    config.stack_size = 8192;
    config.max_uri_handlers = 16;
    config.lru_purge_enable = true;

    ESP_LOGI(TAG, "Starting Robot Admin Web Server on port %d...", port);
    if (httpd_start(&server_, &config) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server on port %d", port);
        return false;
    }

    httpd_uri_t root_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = RootGetHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &root_uri);

    httpd_uri_t config_get_uri = {
        .uri = "/api/config",
        .method = HTTP_GET,
        .handler = ConfigGetHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &config_get_uri);

    httpd_uri_t config_post_uri = {
        .uri = "/api/config",
        .method = HTTP_POST,
        .handler = ConfigPostHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &config_post_uri);

    httpd_uri_t motor_calib_uri = {
        .uri = "/api/motor_calib",
        .method = HTTP_POST,
        .handler = MotorCalibPostHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &motor_calib_uri);

    httpd_uri_t control_uri = {
        .uri = "/api/control",
        .method = HTTP_POST,
        .handler = ControlPostHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &control_uri);

    httpd_uri_t reset_uri = {
        .uri = "/api/reset",
        .method = HTTP_POST,
        .handler = ResetPostHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &reset_uri);

    httpd_uri_t reboot_uri = {
        .uri = "/api/reboot",
        .method = HTTP_POST,
        .handler = RebootPostHandler,
        .user_ctx = nullptr
    };
    httpd_register_uri_handler(server_, &reboot_uri);

    ESP_LOGI(TAG, "Robot Admin Web Server started successfully on port %d", port);
    return true;
}

void RobotAdminServer::Stop() {
    if (server_ != nullptr) {
        httpd_stop(server_);
        server_ = nullptr;
    }
}

esp_err_t RobotAdminServer::RootGetHandler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, kAdminHtml, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

esp_err_t RobotAdminServer::ConfigGetHandler(httpd_req_t *req) {
    if (!s_admin_server) return ESP_FAIL;

    cJSON* root = cJSON_CreateObject();
    cJSON* pins = cJSON_CreateObject();
    cJSON* calib = cJSON_CreateObject();

    auto& p = s_admin_server->pin_cfg_;
    cJSON_AddNumberToObject(pins, "motor_in1", p.motor_in1);
    cJSON_AddNumberToObject(pins, "motor_in2", p.motor_in2);
    cJSON_AddNumberToObject(pins, "motor_in3", p.motor_in3);
    cJSON_AddNumberToObject(pins, "motor_in4", p.motor_in4);
    cJSON_AddNumberToObject(pins, "oled_sda", p.oled_sda);
    cJSON_AddNumberToObject(pins, "oled_scl", p.oled_scl);
    cJSON_AddNumberToObject(pins, "oled_chip", p.oled_chip);
    cJSON_AddNumberToObject(pins, "oled_height", p.oled_height);
    cJSON_AddNumberToObject(pins, "mic_ws", p.mic_ws);
    cJSON_AddNumberToObject(pins, "mic_sck", p.mic_sck);
    cJSON_AddNumberToObject(pins, "mic_sd", p.mic_sd);
    cJSON_AddNumberToObject(pins, "spk_din", p.spk_din);
    cJSON_AddNumberToObject(pins, "spk_bclk", p.spk_bclk);
    cJSON_AddNumberToObject(pins, "spk_lrc", p.spk_lrc);
    cJSON_AddNumberToObject(pins, "led_rgb_din", p.led_rgb_din);
    cJSON_AddNumberToObject(pins, "led_rgb_count", p.led_rgb_count);
    cJSON_AddNumberToObject(pins, "lamp_gpio", p.lamp_gpio);
    cJSON_AddNumberToObject(pins, "touch_gpio", p.touch_gpio);
    cJSON_AddNumberToObject(pins, "touch_level", p.touch_level);
    cJSON_AddNumberToObject(pins, "vl53_sda", p.vl53_sda);
    cJSON_AddNumberToObject(pins, "vl53_scl", p.vl53_scl);
    cJSON_AddNumberToObject(pins, "hcsr04_trig", p.hcsr04_trig);
    cJSON_AddNumberToObject(pins, "hcsr04_echo", p.hcsr04_echo);
    cJSON_AddNumberToObject(pins, "sd_cs", p.sd_cs);
    cJSON_AddNumberToObject(pins, "sd_clk", p.sd_clk);
    cJSON_AddNumberToObject(pins, "sd_mosi", p.sd_mosi);
    cJSON_AddNumberToObject(pins, "sd_miso", p.sd_miso);
    cJSON_AddNumberToObject(pins, "bat_adc", p.bat_adc);

    auto& c = s_admin_server->calib_;
    cJSON_AddNumberToObject(calib, "driver_type", c.driver_type);
    cJSON_AddNumberToObject(calib, "left_trim", c.left_trim);
    cJSON_AddNumberToObject(calib, "right_trim", c.right_trim);
    cJSON_AddNumberToObject(calib, "min_pwm", c.min_pwm);
    cJSON_AddNumberToObject(calib, "safety_mode", c.safety_mode);
    cJSON_AddNumberToObject(calib, "obstacle_cm", c.obstacle_cm);
    cJSON_AddNumberToObject(calib, "cliff_mm", c.cliff_mm);
    cJSON_AddBoolToObject(calib, "laser_enabled", c.laser_enabled);

    cJSON_AddItemToObject(root, "pins", pins);
    cJSON_AddItemToObject(root, "calib", calib);
    cJSON_AddStringToObject(root, "pin_code", SystemInfo::GetDevicePinCode().c_str());
    cJSON_AddStringToObject(root, "mac", SystemInfo::GetMacAddress().c_str());

    char* rendered = cJSON_PrintUnformatted(root);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, rendered, HTTPD_RESP_USE_STRLEN);
    cJSON_free(rendered);
    cJSON_Delete(root);
    return ESP_OK;
}

esp_err_t RobotAdminServer::ConfigPostHandler(httpd_req_t *req) {
    if (!s_admin_server) return ESP_FAIL;

    char buf[1024];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) return ESP_FAIL;
    buf[ret] = '\0';

    cJSON* root = cJSON_Parse(buf);
    if (!root) return ESP_FAIL;

    auto& p = s_admin_server->pin_cfg_;
    cJSON* item;
    if ((item = cJSON_GetObjectItem(root, "motor_in1"))) p.motor_in1 = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "motor_in2"))) p.motor_in2 = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "motor_in3"))) p.motor_in3 = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "motor_in4"))) p.motor_in4 = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "oled_sda"))) p.oled_sda = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "oled_scl"))) p.oled_scl = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "oled_chip"))) p.oled_chip = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "oled_height"))) p.oled_height = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "mic_ws"))) p.mic_ws = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "mic_sck"))) p.mic_sck = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "mic_sd"))) p.mic_sd = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "spk_din"))) p.spk_din = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "spk_bclk"))) p.spk_bclk = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "spk_lrc"))) p.spk_lrc = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "led_rgb_din"))) p.led_rgb_din = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "led_rgb_count"))) p.led_rgb_count = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "lamp_gpio"))) p.lamp_gpio = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "touch_gpio"))) p.touch_gpio = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "touch_level"))) p.touch_level = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "vl53_sda"))) p.vl53_sda = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "vl53_scl"))) p.vl53_scl = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "hcsr04_trig"))) p.hcsr04_trig = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "hcsr04_echo"))) p.hcsr04_echo = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "sd_cs"))) p.sd_cs = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "sd_clk"))) p.sd_clk = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "sd_mosi"))) p.sd_mosi = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "sd_miso"))) p.sd_miso = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "bat_adc"))) p.bat_adc = item->valueint;

    p.SaveToNvs();
    ESP_LOGI(TAG, "Pin configuration saved to NVS");

    bool do_reboot = false;
    if ((item = cJSON_GetObjectItem(root, "reboot"))) {
        do_reboot = cJSON_IsTrue(item);
    }
    cJSON_Delete(root);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);

    if (do_reboot) {
        esp_restart();
    }
    return ESP_OK;
}

esp_err_t RobotAdminServer::MotorCalibPostHandler(httpd_req_t *req) {
    if (!s_admin_server) return ESP_FAIL;

    char buf[512];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) return ESP_FAIL;
    buf[ret] = '\0';

    cJSON* root = cJSON_Parse(buf);
    if (!root) return ESP_FAIL;

    auto& c = s_admin_server->calib_;
    cJSON* item;
    if ((item = cJSON_GetObjectItem(root, "driver_type"))) c.driver_type = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "left_trim"))) c.left_trim = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "right_trim"))) c.right_trim = item->valueint;
    if ((item = cJSON_GetObjectItem(root, "min_pwm"))) c.min_pwm = item->valueint;

    c.SaveToNvs();

    if (s_admin_server->controller_) {
        s_admin_server->controller_->SetCalibration(c.left_trim, c.right_trim, c.min_pwm, c.driver_type);
    }
    cJSON_Delete(root);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

esp_err_t RobotAdminServer::ControlPostHandler(httpd_req_t *req) {
    if (!s_admin_server || !s_admin_server->controller_) return ESP_FAIL;

    char buf[256];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) return ESP_FAIL;
    buf[ret] = '\0';

    cJSON* root = cJSON_Parse(buf);
    if (!root) return ESP_FAIL;

    cJSON* act = cJSON_GetObjectItem(root, "action");
    int speed = 80;
    cJSON* spd = cJSON_GetObjectItem(root, "speed");
    if (spd) speed = spd->valueint;

    if (act && act->valuestring) {
        std::string action = act->valuestring;
        if (action == "stop") {
            s_admin_server->controller_->Stop();
        } else if (action == "wiggle") {
            s_admin_server->controller_->Wiggle();
        } else if (action == "dance") {
            s_admin_server->controller_->Dance();
        } else if (action == "wander") {
            s_admin_server->controller_->Wander();
        } else if (action == "move") {
            cJSON* dir = cJSON_GetObjectItem(root, "direction");
            if (dir && dir->valuestring) {
                s_admin_server->controller_->Move(dir->valuestring, speed, 800);
            }
        }
    }

    cJSON_Delete(root);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"status\":\"ok\"}", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

esp_err_t RobotAdminServer::ResetPostHandler(httpd_req_t *req) {
    RobotPinConfig::ResetToDefaults();
    RobotCalibration::ResetToDefaults();
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"status\":\"reset_ok\"}", HTTPD_RESP_USE_STRLEN);
    esp_restart();
    return ESP_OK;
}

esp_err_t RobotAdminServer::RebootPostHandler(httpd_req_t *req) {
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, "{\"status\":\"rebooting\"}", HTTPD_RESP_USE_STRLEN);
    esp_restart();
    return ESP_OK;
}

