import os

html_section = """
    <!-- TEST MÀN HÌNH OLED & BIỂU CẢM KHÔNG CẦN ĐỘNG CƠ -->
    <div style="margin-top: 24px; padding: 20px; border-radius: 14px; background: #07152b; border: 1px solid rgba(59, 130, 246, 0.3);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
            <div>
                <h4 style="margin: 0; font-size: 16px; color: #60a5fa; display: flex; align-items: center; gap: 8px;">
                    <span>📺</span>
                    <span>Test Màn hình OLED & Biểu cảm (Dành cho mạch chưa gắn động cơ)</span>
                </h4>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 3px;">
                    Đổi biểu cảm mắt/khuôn mặt hoặc gửi dòng chữ hiển thị trực tiếp lên màn hình OLED 128x64 của robot
                </div>
            </div>
            <span style="font-size: 11px; background: rgba(34, 197, 94, 0.15); color: #4ade80; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(34, 197, 94, 0.3); font-weight: bold;">
                ● OLED Sẵn sàng
            </span>
        </div>

        <!-- Các nút biểu cảm nhanh -->
        <div style="margin-bottom: 16px;">
            <div style="font-size: 12px; color: #cbd5e1; font-weight: 600; margin-bottom: 8px;">1. Bấm để đổi Biểu cảm mắt / mặt tức thì trên OLED:</div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                <button onclick="sendOledDisplay('happy')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😊</span> <span>Vui vẻ (happy)</span>
                </button>
                <button onclick="sendOledDisplay('laughing')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😆</span> <span>Cười lớn (laughing)</span>
                </button>
                <button onclick="sendOledDisplay('thinking')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>🤔</span> <span>Suy nghĩ (thinking)</span>
                </button>
                <button onclick="sendOledDisplay('loving')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>💖</span> <span>Yêu thương (loving)</span>
                </button>
                <button onclick="sendOledDisplay('wink')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😉</span> <span>Nháy mắt (wink)</span>
                </button>
                <button onclick="sendOledDisplay('shocked')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😲</span> <span>Ngạc nhiên (shocked)</span>
                </button>
                <button onclick="sendOledDisplay('cool')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😎</span> <span>Ngầu (cool)</span>
                </button>
                <button onclick="sendOledDisplay('neutral')" style="padding: 8px 14px; border-radius: 8px; background: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>😐</span> <span>Bình thường (neutral)</span>
                </button>
            </div>
        </div>

        <!-- Gửi chữ hiển thị phụ đề lên màn hình -->
        <div>
            <div style="font-size: 12px; color: #cbd5e1; font-weight: 600; margin-bottom: 8px;">2. Gửi dòng chữ bất kỳ hiển thị lên màn hình OLED:</div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <input type="text" id="oledCustomTextInput" value="Xin chao! Robot Xiaozhi online." placeholder="Nhập câu chữ muốn hiển thị trên OLED..." style="flex: 1; min-width: 240px; padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.14); background: #0f172a; color: white; font-size: 13px;">
                <button onclick="sendCustomTextToOled()" style="padding: 10px 18px; border-radius: 8px; background: #0284c7; color: white; border: none; font-weight: bold; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>📝</span> <span>Gửi chữ lên OLED</span>
                </button>
                <button onclick="sendSpeakAndDisplay()" style="padding: 10px 18px; border-radius: 8px; background: #059669; color: white; border: none; font-weight: bold; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 6px;">
                    <span>📢</span> <span>Vừa nói vừa hiện chữ</span>
                </button>
            </div>
        </div>
    </div>
"""

js_code = """
    // 2.2 GỬI BIỂU CẢM & CHỮ HIỂN THỊ LÊN MÀN HÌNH OLED
    async function sendOledDisplay(emotion, text) {
      const feedback = document.getElementById("controlStatusText");
      if (feedback) feedback.innerText = `Đang gửi biểu cảm '${emotion}' tới màn hình OLED robot...`;

      try {
        const res = await fetch("/api/robot/display", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_id: activeDeviceId, emotion: emotion, text: text })
        });
        const data = await res.json();
        if (res.ok && data.status === "ok") {
          if (feedback) feedback.innerText = `✓ Đã cập nhật màn hình OLED: Biểu cảm '${emotion}'` + (text ? ` | Chữ: "${text}"` : '');
          showToast(`✓ Đã đổi màn hình OLED sang '${emotion}'!`);
        } else {
          if (feedback) feedback.innerText = `⚠ ${data.message || 'Lỗi gửi lệnh tới màn hình'}`;
          showToast(data.message || "Lỗi gửi lệnh", false);
        }
      } catch (err) {
        if (feedback) feedback.innerText = `✗ Lỗi mạng: ${err.message}`;
        showToast("Lỗi kết nối tới Server: " + err.message, false);
      }
    }

    async function sendCustomTextToOled() {
      const input = document.getElementById("oledCustomTextInput");
      const text = input ? input.value.trim() : "";
      if (!text) {
        showToast("Vui lòng nhập câu chữ muốn hiển thị", false);
        return;
      }
      sendOledDisplay("happy", text);
    }

    async function sendSpeakAndDisplay() {
      const input = document.getElementById("oledCustomTextInput");
      const text = input ? input.value.trim() : "Xin chao chu nhan!";
      const feedback = document.getElementById("controlStatusText");
      if (feedback) feedback.innerText = `Đang gửi câu nói & phát loa: "${text}"...`;

      try {
        const res = await fetch("/api/robot/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_id: activeDeviceId, text: text, emotion: "happy" })
        });
        const data = await res.json();
        if (res.ok && data.status === "ok") {
          if (feedback) feedback.innerText = `✓ Đã phát âm thanh và hiển thị lên màn hình OLED: "${text}"`;
          showToast(`✓ Robot đang phát âm thanh & hiển thị!`);
        } else {
          if (feedback) feedback.innerText = `⚠ ${data.message || 'Lỗi phát âm thanh'}`;
          showToast(data.message || "Lỗi phát âm thanh", false);
        }
      } catch (err) {
        if (feedback) feedback.innerText = `✗ Lỗi mạng: ${err.message}`;
        showToast("Lỗi kết nối tới Server: " + err.message, false);
      }
    }
"""

def update_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Thêm html_section trước controlFeedbackBox
    target_html = '<!-- Phản hồi trạng thái -->\n    <div id="controlFeedbackBox"'
    if target_html in content and "TEST MÀN HÌNH OLED" not in content:
        content = content.replace(target_html, html_section + "\n    " + target_html)
        print(f"[OK] Added HTML section to {path}")
    elif "TEST MÀN HÌNH OLED" in content:
        print(f"[SKIP] HTML section already exists in {path}")

    # Thêm js_code trước // 3. CHAT TRỰC TIẾP VỚI GEMINI AI
    target_js = '// 3. CHAT TRỰC TIẾP VỚI GEMINI AI'
    target_js_alt = '// 3. CHAT TR?'
    if target_js in content and "sendOledDisplay" not in content:
        content = content.replace(target_js, js_code + "\n    " + target_js)
        print(f"[OK] Added JS code to {path}")
    elif target_js_alt in content and "sendOledDisplay" not in content:
        content = content.replace(target_js_alt, js_code + "\n    " + target_js_alt)
        print(f"[OK] Added JS code to {path} (matched alt)")
    elif "sendOledDisplay" in content:
        print(f"[SKIP] JS code already exists in {path}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

update_file("preview.html")
update_file("index.html")
print("[DONE] Successfully updated templates!")

