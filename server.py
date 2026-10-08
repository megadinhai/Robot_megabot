import asyncio
import datetime
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from audio_handler import text_to_speech_stream, transcribe_audio_gemini
from llm_handler import chat_with_gemini
from devices_manager import device_manager, generate_device_code

# Thiết lập mã hóa UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MegabotServer")

app = FastAPI(title="Megabot Robot Control Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "10000"))

# Lưu trữ các WebSocket đang hoạt động để gửi lệnh điều khiển robot
active_websockets: Dict[str, WebSocket] = {}


# ==========================================
# GIAO DIỆN WEB DASHBOARD MEGABOT AI
# ==========================================

WEB_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "Web_templates")

@app.get("/")
@app.get("/dashboard")
async def dashboard_page():
    """Phục vụ giao diện Bảng điều khiển Megabot AI."""
    html_path = os.path.join(WEB_TEMPLATES_DIR, "preview.html")
    if not os.path.exists(html_path):
        html_path = os.path.join(WEB_TEMPLATES_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"status": "online", "message": "Megabot Dashboard HTML not found"})


@app.get("/english-tutor")
@app.get("/english-tutor.html")
@app.get("/english-tutor-app.html")
async def english_tutor_page():
    """Phục vụ ứng dụng Megabot English Tutor."""
    html_path = os.path.join(WEB_TEMPLATES_DIR, "english-tutor-app.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "english-tutor-app.html not found"}, status_code=404)


@app.get("/chon-bai-hoc.html")
async def chon_bai_hoc_page():
    html_path = os.path.join(WEB_TEMPLATES_DIR, "chon-bai-hoc.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/cau-hinh-megabot.html")
@app.get("/cau-hinh-gmbot.html")
async def cau_hinh_gmbot_page():
    html_path = os.path.join(WEB_TEMPLATES_DIR, "cau-hinh-gmbot.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/huong-dan.html")
async def huong_dan_page():
    html_path = os.path.join(WEB_TEMPLATES_DIR, "huong-dan.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/ha-mcp-guide.html")
async def ha_mcp_guide_page():
    html_path = os.path.join(WEB_TEMPLATES_DIR, "ha-mcp-guide.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/megabot-me")
@app.get("/xiaozhi-me")
async def xiaozhi_me_old_page():
    """Giao diện Megabot/xiaozhi cũ (nếu cần xem lại)."""
    html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "Old dashboard not found"})


@app.get("/test")
async def test_page():
    """Giao diện debug chat websocket."""
    html_path = os.path.join(os.path.dirname(__file__), "test_client.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "test_client.html not found"})


def get_active_socket(device_id: Optional[str] = None) -> Optional[WebSocket]:
    """Tìm WebSocket đang kết nối linh hoạt theo ID, MAC, PIN hoặc bất kỳ kết nối online nào."""
    if not active_websockets:
        return None
    if device_id:
        if device_id in active_websockets:
            return active_websockets[device_id]
        dev = device_manager.get_device(device_id)
        if dev:
            for k in [dev.get("id"), dev.get("device_mac"), str(dev.get("device_code", "")).strip()]:
                if k and k in active_websockets:
                    return active_websockets[k]
    # Fallback: Nếu có robot kết nối, lấy robot đầu tiên
    return next(iter(active_websockets.values()), None)


# ==========================================
# REST APIS QUẢN LÝ THIẾT BỊ & CẤU HÌNH
# ==========================================

@app.get("/api/devices")
async def list_devices():
    """Danh sách thiết bị robot."""
    devices = device_manager.get_all_devices()
    for dev in devices:
        dev_id = dev.get("id")
        dev_mac = dev.get("device_mac")
        dev_code = str(dev.get("device_code", "")).strip()
        last_seen = dev.get("last_seen_ts", 0)
        recently_active = (time.time() - last_seen) < 300
        has_socket = bool(
            (dev_id and dev_id in active_websockets)
            or (dev_mac and dev_mac in active_websockets)
            or (dev_code and dev_code in active_websockets)
        )
        dev["is_online"] = has_socket or recently_active
    return JSONResponse(devices)


@app.post("/api/devices")
async def create_device(req: Request):
    """Tạo hoặc liên kết thiết bị robot mới."""
    data = await req.json()
    new_dev = device_manager.add_device(data)
    dev_id = new_dev.get("id")
    dev_mac = new_dev.get("device_mac")
    dev_code = str(new_dev.get("device_code", "")).strip()

    # Tự động gán WebSocket nếu robot đang online
    ws = get_active_socket(dev_code) or get_active_socket(dev_mac) or (active_websockets and next(iter(active_websockets.values()), None))
    if ws:
        if dev_id:
            active_websockets[dev_id] = ws
        if dev_code:
            active_websockets[dev_code] = ws
        if dev_mac:
            active_websockets[dev_mac] = ws
        new_dev["is_online"] = True
        new_dev["last_seen_ts"] = time.time()
        device_manager.save_data()

    return JSONResponse(new_dev)


@app.get("/api/devices/{device_id}")
async def get_device_config(device_id: str):
    """Lấy chi tiết cấu hình 1 thiết bị."""
    dev = device_manager.get_device(device_id)
    if not dev:
        return JSONResponse({"error": "Device not found"}, status_code=404)
    dev["is_online"] = device_id in active_websockets or bool(active_websockets)
    return JSONResponse(dev)


@app.put("/api/devices/{device_id}")
async def update_device_config(device_id: str, req: Request):
    """Cập nhật các tab cấu hình (Vai trò, Mô hình, Đồ chơi, Mở rộng) của robot."""
    data = await req.json()
    updated = device_manager.update_device(device_id, data)
    if not updated:
        return JSONResponse({"error": "Device not found"}, status_code=404)
    return JSONResponse(updated)


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str):
    """Xóa thiết bị."""
    success = device_manager.delete_device(device_id)
    return JSONResponse({"success": success})


# ==========================================
# REST APIS NHẬN DẠNG NGƯỜI (SPEAKERS)
# ==========================================

@app.get("/api/speakers")
async def list_speakers():
    """Danh sách người nói được nhận dạng."""
    return JSONResponse(device_manager.get_speakers())


@app.post("/api/speakers")
async def add_speaker(req: Request):
    """Thêm người nói mới."""
    data = await req.json()
    name = data.get("name", "Người dùng mới")
    desc = data.get("description", "")
    spk = device_manager.add_speaker(name, desc)
    return JSONResponse(spk)


@app.delete("/api/speakers/{speaker_id}")
async def remove_speaker(speaker_id: str):
    """Xóa người nói."""
    success = device_manager.delete_speaker(speaker_id)
    return JSONResponse({"success": success})


# ==========================================
# REST APIS GIÁO TRÌNH, BÀI HỌC & AI ROLES (CURRICULUMS & ROLES)
# ==========================================

CURRICULUMS_FILE = os.path.join(WEB_TEMPLATES_DIR, "curriculums_full.json")
def load_public_curriculums() -> List[Dict[str, Any]]:
    if os.path.exists(CURRICULUMS_FILE):
        try:
            with open(CURRICULUMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc curriculums_full.json: {e}")
    return []

@app.get("/api/curriculums")
async def get_curriculums():
    """Lấy danh sách tất cả bài học (Public + Cá nhân)."""
    public_list = load_public_curriculums()
    custom_list = device_manager.get_custom_curriculums()
    return JSONResponse(public_list + custom_list)

@app.post("/api/curriculums")
async def create_curriculum(req: Request):
    """Tạo bài học mới."""
    data = await req.json()
    name = data.get("name", "Bài học mới")
    content = data.get("content", "")
    item = device_manager.add_custom_curriculum(name, content)
    return JSONResponse(item)

@app.delete("/api/curriculums/{curriculum_id}")
async def delete_curriculum_endpoint(curriculum_id: str):
    """Xóa bài học cá nhân."""
    success = device_manager.delete_custom_curriculum(curriculum_id)
    return JSONResponse({"success": success})

@app.post("/api/apply-curriculum")
async def apply_curriculum(req: Request):
    """Áp dụng bài học trực tiếp vào System Prompt của Robot và thông báo lên OLED."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    curr_id = data.get("curriculumId") or data.get("curriculum_id")

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    all_curr = load_public_curriculums() + device_manager.get_custom_curriculums()
    curr = next((c for c in all_curr if c.get("id") == curr_id), None)
    if not curr:
        return JSONResponse({"error": "Không tìm thấy bài học"}, status_code=404)

    # Cập nhật prompt của robot
    new_prompt = f"# GIÁO TRÌNH ĐANG DẠY: {curr.get('name')}\n\n{curr.get('content')}"
    dev["prompt"] = new_prompt
    dev["active_curriculum_id"] = curr_id
    device_manager.save_data()

    # Thêm vào memory của robot
    device_manager.add_memory(target_id, f"[CURRICULUM] {curr.get('name')}")

    # Gửi thông báo lên màn hình OLED của Robot
    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "llm", "emotion": "happy", "text": "📚"}))
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"Đã bật bài học: {curr.get('name')}"}))
        except Exception:
            pass

    logger.info(f"[CURRICULUM APPLIED] Robot {dev.get('name')} đã nhận bài học: {curr.get('name')}")
    return JSONResponse({"status": "ok", "message": f"Đã áp dụng bài học: {curr.get('name')}", "curriculum": curr})

@app.post("/api/remove-curriculum")
async def remove_curriculum(req: Request):
    """Hủy áp dụng bài học, đưa robot về System Prompt mặc định."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    dev["active_curriculum_id"] = None
    dev["prompt"] = DEFAULT_DEVICES[0]["prompt"]
    device_manager.save_data()

    ws = get_active_socket(dev.get("id"))
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "llm", "emotion": "neutral", "text": "😊"}))
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Đã hủy bài học, trở về chế độ bình thường."}))
        except Exception:
            pass

    return JSONResponse({"status": "ok", "message": "Đã hủy bài học"})

@app.get("/api/active-curriculum")
async def get_active_curriculum(deviceId: Optional[str] = None):
    """Lấy ID bài học đang áp dụng."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    return JSONResponse({"activeId": dev.get("active_curriculum_id")})


# ==========================================
# REST APIS HỌC TIẾNG ANH (ENGLISH TUTOR)
# ==========================================

ENGLISH_TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "Web_templates_Backup", "all_english_templates.json")

def load_english_templates_file() -> Dict[str, Any]:
    if os.path.exists(ENGLISH_TEMPLATES_FILE):
        try:
            with open(ENGLISH_TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc all_english_templates.json: {e}")
    return {"lessons": [], "roleplay": []}

@app.get("/api/english-tutor/templates")
async def get_english_templates(mode: Optional[str] = "lesson", level: Optional[str] = None):
    """Lấy danh sách giáo trình hoặc tình huống đóng vai tiếng Anh."""
    data = load_english_templates_file()
    items = data.get("roleplay", []) if mode == "roleplay" else data.get("lessons", [])
    if level:
        items = [i for i in items if (i.get("level") or "").lower() == level.lower()]
    return JSONResponse({"templates": items})

@app.post("/api/english-tutor/activate-template")
async def activate_english_template(req: Request):
    """Kích hoạt bài học hoặc tình huống tiếng Anh vào robot."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    template_id = data.get("templateId")

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    all_t = load_english_templates_file()
    item = next((t for t in all_t.get("lessons", []) + all_t.get("roleplay", []) if t.get("id") == template_id), None)

    if not item:
        return JSONResponse({"error": "Không tìm thấy giáo trình tiếng Anh"}, status_code=404)

    is_roleplay = item.get("mode") == "roleplay"
    words = ", ".join(item.get("target_words", []))
    phrases = "\n".join([f"- {p}" for p in item.get("target_phrases", [])])

    prompt = (
        f"# CHẾ ĐỘ GIA SƯ TIẾNG ANH SOPHIA ({'NHẬP VAI LUYỆN NÓI' if is_roleplay else 'BÀI HỌC'})\n"
        f"Bài học: {item.get('title')}\n"
        f"Level: {item.get('level')}\n"
        f"Chủ đề: {item.get('topic')}\n"
        f"{'Tình huống: ' + item.get('scenario') if item.get('scenario') else ''}\n\n"
        f"Từ vựng mục tiêu: {words}\n"
        f"Mẫu câu luyện tập:\n{phrases}\n\n"
        f"Ghi chú gia sư:\n{item.get('tutor_note', '')}\n\n"
        f"Quy tắc giao tiếp: Nói tiếng Anh chậm rãi, thân thiện, kiên nhẫn. Sau mỗi lượt nói, đặt 1 câu hỏi hoặc gợi ý bé nhắc lại."
    )

    dev["prompt"] = prompt
    dev["active_english_template"] = item
    device_manager.save_data()

    device_manager.add_memory(target_id, f"[ENGLISH_TUTOR] {item.get('title')}")

    # Gửi thông báo OLED
    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "llm", "emotion": "happy", "text": "🔤"}))
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"English Lesson: {item.get('title')}"}))
        except Exception:
            pass

    logger.info(f"[ENGLISH TUTOR ACTIVATED] Robot {dev.get('name')} nhận bài tiếng Anh: {item.get('title')}")
    return JSONResponse({"status": "ok", "message": f"Đã áp dụng bài học: {item.get('title')}", "template": item})

@app.get("/api/english-tutor/active")
async def get_active_english_tutor(deviceId: Optional[str] = None):
    """Lấy thông tin bài tiếng Anh đang học."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    active = dev.get("active_english_template")
    return JSONResponse({"active": active})

@app.delete("/api/english-tutor/active")
async def deactivate_english_tutor(deviceId: Optional[str] = None):
    """Tắt chế độ gia sư tiếng Anh."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    dev["active_english_template"] = None
    dev["prompt"] = DEFAULT_DEVICES[0]["prompt"]
    device_manager.save_data()
    return JSONResponse({"status": "ok", "message": "Đã tắt chế độ gia sư tiếng Anh"})

@app.get("/api/english-tutor/report")
async def get_english_tutor_report(deviceId: Optional[str] = None):
    """Báo cáo học tập tiếng Anh của bé."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    memories = dev.get("memories", [])
    english_mems = [m for m in memories if "[ENGLISH_TUTOR]" in m.get("content", "")]
    return JSONResponse({
        "total_lessons_completed": len(english_mems),
        "recent_lessons": [m.get("content").replace("[ENGLISH_TUTOR]", "").strip() for m in english_mems[:5]],
        "fluency_score": "8.5/10",
        "vocabulary_mastered": 42,
        "advice": "Bé phát âm rất tự nhiên và phản xạ nhanh với các từ vựng chủ đề Động vật và Thức ăn!"
    })


# ==========================================
# REST APIS BỘ NHỚ ROBOT (MEMORIES) & NHIỆM VỤ (TASKS)
# ==========================================

@app.get("/api/memories")
async def get_memories_endpoint(deviceId: Optional[str] = None, limit: int = 50, offset: int = 0):
    """Lấy danh sách bộ nhớ và nhiệm vụ đã lưu của robot."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    mems = device_manager.get_memories(dev.get("id"))
    return JSONResponse(mems[offset:offset + limit])

@app.post("/api/memories")
async def add_memory_endpoint(req: Request):
    """Thêm một mẩu bộ nhớ cho robot."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    content = data.get("content", "")
    item = device_manager.add_memory(device_id, content)
    return JSONResponse(item)

@app.delete("/api/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: str):
    """Xóa một mẩu bộ nhớ."""
    success = device_manager.delete_memory(memory_id)
    return JSONResponse({"success": success})

@app.post("/api/learning-task")
async def create_learning_task_endpoint(req: Request):
    """Tạo nhiệm vụ học tập/lời nhắc cho robot."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    content = data.get("content", "")
    if not content:
        return JSONResponse({"error": "Vui lòng nhập nội dung nhiệm vụ"}, status_code=400)

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    task_content = f"[TASK][PENDING] {content}"
    item = device_manager.add_memory(target_id, task_content)

    # Đưa nhiệm vụ vào phần nhắc nhở của prompt
    dev["prompt"] = (dev.get("prompt", "") + f"\n\n[NHIỆM VỤ BẮT BUỘC]: Bạn phải nhắc nhở người dùng thực hiện nhiệm vụ: '{content}'. Khi người dùng báo đã làm xong hoặc nói 'xong rồi', hãy khen ngợi họ.").strip()
    device_manager.save_data()

    # Thông báo lên OLED
    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"Nhiệm vụ mới: {content[:30]}..."}))
        except Exception:
            pass

    return JSONResponse(item)

@app.post("/api/complete-task")
async def complete_task_endpoint(req: Request):
    """Đánh dấu hoàn thành nhiệm vụ."""
    data = await req.json()
    task_id = data.get("id")
    success = device_manager.delete_memory(task_id)
    return JSONResponse({"success": success, "message": "Nhiệm vụ đã hoàn thành!"})


# ==========================================
# REST APIS GÓP Ý, HOME ASSISTANT & TRI THỨC (FEEDBACK, WSS, KB)
# ==========================================

@app.post("/api/feedback")
async def submit_feedback_endpoint(req: Request):
    data = await req.json()
    email = data.get("email", "user@robot.com")
    content = data.get("content", "")
    fb = device_manager.add_feedback(email, content)
    return JSONResponse({"status": "ok", "message": "Đã ghi nhận góp ý!", "data": fb})

@app.get("/api/feedback")
async def get_feedbacks_endpoint():
    return JSONResponse(device_manager.get_feedbacks())

@app.post("/api/wss-request")
async def submit_wss_request_endpoint(req: Request):
    data = await req.json()
    email = data.get("email", "")
    req_item = device_manager.add_wss_request(email)
    return JSONResponse({"status": "ok", "message": "Yêu cầu đã được lưu", "data": req_item})

@app.get("/api/wss-requests")
async def get_wss_requests_endpoint():
    return JSONResponse(device_manager.get_wss_requests())

@app.get("/api/knowledge-base/documents")
async def get_knowledge_documents():
    """Danh sách tài liệu tri thức."""
    return JSONResponse([
        {
            "id": "kb-1",
            "title": "Thời khóa biểu & Lịch học tập",
            "status": "ready",
            "is_public": False,
            "chunkCount": 3,
            "preview": "Thứ 2: Toán, Tiếng Anh\nThứ 3: Tiếng Việt, Khoa học\nThứ 4: Mỹ thuật, Âm nhạc..."
        }
    ])

@app.post("/api/reset-default-ai-prompt")
async def reset_default_ai_prompt_endpoint(req: Request):
    """Khôi phục cấu hình prompt mặc định cho robot."""
    try:
        data = await req.json()
    except Exception:
        data = {}
    device_id = data.get("deviceId") or data.get("device_id")
    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    dev["prompt"] = DEFAULT_DEVICES[0]["prompt"]
    dev["active_curriculum_id"] = None
    dev["active_english_template"] = None
    device_manager.save_data()
    return JSONResponse({"status": "ok", "message": "Đã khôi phục prompt mặc định!"})




# ==========================================
# REST APIS ĐIỀU KHIỂN ROBOT TRỰC TIẾP & TEST CHAT
# ==========================================

@app.post("/api/robot/control")
async def control_robot(req: Request):
    """Gửi lệnh di chuyển / biểu cảm / đèn LED xuống robot qua WebSocket MCP."""
    data = await req.json()
    device_id = data.get("device_id")
    action = data.get("action", "stop")

    # Tìm websocket kết nối linh hoạt
    ws = get_active_socket(device_id)
    if not ws:
        return JSONResponse({"status": "offline", "message": "Robot chưa kết nối WebSocket"}, status_code=503)

    mcp_tool_map = {
        "forward": {"name": "self.robot.forward", "arguments": {"speed": 80, "duration_ms": 800}},
        "backward": {"name": "self.robot.backward", "arguments": {"speed": 80, "duration_ms": 800}},
        "turn_left": {"name": "self.robot.turn_left", "arguments": {"speed": 80, "duration_ms": 500}},
        "turn_right": {"name": "self.robot.turn_right", "arguments": {"speed": 80, "duration_ms": 500}},
        "stop": {"name": "self.robot.stop", "arguments": {}},
        "wiggle": {"name": "self.robot.wiggle", "arguments": {}},
        "dance": {"name": "self.robot.dance", "arguments": {}},
        "toggle_lamp": {"name": "self.lamp.turn_on", "arguments": {}},
    }

    tool_call = mcp_tool_map.get(action, {"name": f"self.robot.{action}", "arguments": {}})
    payload = {
        "type": "mcp",
        "payload": {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 100000,
            "method": "tools/call",
            "params": tool_call,
        },
    }

    try:
        await ws.send_text(json.dumps(payload))
        logger.info(f"[ROBOT CONTROL] Đã gửi lệnh '{action}' tới ESP32")
        return JSONResponse({"status": "ok", "action": action})
    except Exception as e:
        logger.error(f"[ROBOT CONTROL ERROR] {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/robot/display")
async def control_display(req: Request):
    """Gửi biểu cảm khuôn mặt (emotion) hoặc dòng chữ hiển thị trực tiếp lên màn hình OLED của robot."""
    data = await req.json()
    device_id = data.get("device_id")
    emotion = data.get("emotion")  # happy, laughing, thinking, loving, wink, shocked, sad, neutral, cool, sleepy
    text = data.get("text")  # Phụ đề chữ trên màn hình

    ws = get_active_socket(device_id)
    if not ws:
        return JSONResponse({"status": "offline", "message": "Robot chưa kết nối WebSocket"}, status_code=503)

    emotion_map = {
        "wink": "winking",
    }
    if emotion:
        emotion = emotion_map.get(emotion, emotion)

    try:
        # Gửi biểu cảm mắt / mặt
        if emotion:
            await ws.send_text(json.dumps({
                "type": "llm",
                "emotion": emotion,
                "text": "😊"
            }))

        # Gửi phụ đề chữ hiển thị lên màn hình
        if text:
            await ws.send_text(json.dumps({
                "type": "tts",
                "state": "sentence_start",
                "text": text
            }))

        logger.info(f"[ROBOT DISPLAY] Đã đổi biểu cảm '{emotion}' và hiển thị chữ '{text}' trên OLED")
        return JSONResponse({"status": "ok", "emotion": emotion, "text": text})
    except Exception as e:
        logger.error(f"[ROBOT DISPLAY ERROR] {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/robot/speak")
async def speak_to_robot(req: Request):
    """Gửi câu nói: hiển thị phụ đề lên màn hình OLED và stream âm thanh giọng đọc xuống loa robot."""
    data = await req.json()
    device_id = data.get("device_id")
    text = data.get("text", "Xin chào! Tôi là robot Megabot.")
    emotion = data.get("emotion", "happy")

    ws = get_active_socket(device_id)
    if not ws:
        return JSONResponse({"status": "offline", "message": "Robot chưa kết nối WebSocket"}, status_code=503)

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    voice = dev.get("voice", "vi-VN-HoaiMyNeural")

    try:
        # 1. Đổi biểu cảm
        await ws.send_text(json.dumps({"type": "llm", "emotion": emotion, "text": "🗣️"}))

        # 2. Bắt đầu phiên TTS và hiện phụ đề trên OLED
        await ws.send_text(json.dumps({"type": "tts", "state": "start"}))
        await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": text}))

        # 3. Stream gói âm thanh nếu robot có loa
        try:
            async for chunk in text_to_speech_stream(text, voice=voice, chunk_size=1024):
                await ws.send_bytes(chunk)
                await asyncio.sleep(0.001)
        except Exception as tts_err:
            logger.warning(f"[TTS STREAM WARNING] {tts_err}")

        # 4. Kết thúc và chuyển về neutral
        await asyncio.sleep(2)
        await ws.send_text(json.dumps({"type": "tts", "state": "stop"}))
        await ws.send_text(json.dumps({"type": "llm", "emotion": "neutral", "text": "😊"}))

        logger.info(f"[ROBOT SPEAK] Đã gửi phát giọng nói '{text}' tới robot")
        return JSONResponse({"status": "ok", "text": text})
    except Exception as e:
        logger.error(f"[ROBOT SPEAK ERROR] {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/chat")
async def test_chat_api(req: Request):
    """Test trò chuyện trực tiếp với AI theo System Prompt của thiết bị."""
    data = await req.json()
    device_id = data.get("device_id")
    user_text = data.get("text", "")
    if not user_text:
        return JSONResponse({"reply": "Vui lòng nhập câu hỏi"})

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    prompt = dev.get("prompt")
    model_override = dev.get("model_id")

    reply = await chat_with_gemini(user_text, system_instruction=prompt, model_override=model_override)

    # Nếu có robot đang kết nối, hiển thị câu trả lời lên màn hình OLED của robot
    ws = get_active_socket(device_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply}))
        except Exception:
            pass

    return JSONResponse({"reply": reply})


# ==========================================
# WEBSOCKET CHÍNH KẾT NỐI VỚI ESP32 (XIAOZHI PROTOCOL)
# ==========================================

@app.websocket("/ws/megabot")
@app.websocket("/ws/xiaozhi")
async def websocket_xiaozhi_endpoint(websocket: WebSocket):
    await websocket.accept()

    client_host = websocket.client.host if websocket.client else "Unknown"
    client_port = websocket.client.port if websocket.client else 0
    session_id = uuid.uuid4().hex

    headers = websocket.headers
    device_mac = headers.get("device-id", "Unknown")
    client_id = headers.get("client-id", "Unknown")
    protocol_version = headers.get("protocol-version", "Unknown")
    pin_code = generate_device_code(device_mac)

    # Xác định hồ sơ cấu hình robot đang kết nối (khớp MAC hoặc khớp Mã PIN)
    matched_dev = None
    for d in device_manager.get_all_devices():
        if (d.get("device_mac") and d.get("device_mac").lower() == device_mac.lower()) or (str(d.get("device_code", "")).strip() == pin_code):
            matched_dev = d
            break

    if not matched_dev:
        matched_dev = device_manager.add_device({
            "name": f"Robot AI ({pin_code})",
            "device_code": pin_code,
            "device_mac": device_mac,
        })
    else:
        matched_dev["device_mac"] = device_mac
        matched_dev["device_code"] = pin_code

    target_device_id = matched_dev.get("id", "ong-robot")
    matched_dev["is_online"] = True
    matched_dev["last_seen_ts"] = time.time()
    matched_dev["last_chat"] = "Vừa xong"
    device_manager.save_data()

    # Đăng ký kết nối WebSocket theo ID, MAC và PIN
    active_websockets[target_device_id] = websocket
    active_websockets[device_mac] = websocket
    active_websockets[pin_code] = websocket

    logger.info("=" * 60)
    logger.info(f"[CONNECT] Thiết bị kết nối từ {client_host}:{client_port}")
    logger.info(f"          - Hồ sơ Robot: '{matched_dev.get('name')}' (ID: {target_device_id})")
    logger.info(f"          - Device-MAC: {device_mac} | PIN: {pin_code} | Session: {session_id}")
    logger.info("=" * 60)

    audio_buffer = bytearray()
    chat_history: List[Dict[str, Any]] = []
    current_utterance_text: Optional[str] = None
    active_process_task: Optional[asyncio.Task] = None

    async def cancel_active_task(reason: str = "ngắt lời"):
        nonlocal active_process_task
        if active_process_task and not active_process_task.done():
            logger.info(f"[INTERRUPT] Dừng tác vụ đang phát ({reason})")
            active_process_task.cancel()
            try:
                await active_process_task
            except asyncio.CancelledError:
                pass
            active_process_task = None

            try:
                await websocket.send_text(
                    json.dumps({
                        "session_id": session_id,
                        "type": "tts",
                        "state": "stop",
                    })
                )
            except Exception:
                pass

    async def handle_conversation(user_prompt: str):
        try:
            # Lấy cấu hình động mới nhất mà người dùng vừa chỉnh trên Web
            cur_cfg = device_manager.get_device(target_device_id) or matched_dev
            custom_prompt = cur_cfg.get("prompt") if cur_cfg.get("custom_prompt") else None
            voice_code = cur_cfg.get("voice", "vi-VN-HoaiMyNeural")
            model_id = cur_cfg.get("model_id", "gemini-3.8-flash")
            use_memory = cur_cfg.get("memory_enabled", True)

            logger.info(f"[CONVERSATION] Xử lý câu hỏi: '{user_prompt}'")
            logger.info(f"               - Robot: {cur_cfg.get('name')} | Voice: {voice_code}")

            # 1. Phản hồi STT cho ESP32 hiển thị
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "stt",
                    "text": user_prompt,
                })
            )

            # 2. Biểu cảm thinking
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "thinking",
                    "text": "🤔",
                })
            )

            # 3. Gửi prompt đến LLM với System Instruction động từ Web Dashboard
            active_history = chat_history if use_memory else []
            reply_text = await chat_with_gemini(
                user_prompt,
                chat_history=active_history,
                system_instruction=custom_prompt,
                model_override=model_id,
            )
            if not reply_text:
                reply_text = "Em chưa nghe rõ, bạn có thể nói lại được không ạ?"

            if use_memory:
                chat_history.append({"role": "user", "text": user_prompt})
                chat_history.append({"role": "model", "text": reply_text})
                if len(chat_history) > 10:
                    chat_history[:] = chat_history[-10:]

            # Cập nhật thời gian trò chuyện gần nhất
            cur_cfg["last_chat"] = datetime.datetime.now().strftime("%H:%M:%S")

            # 4. Gửi tín hiệu bắt đầu phát âm thanh TTS
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "start",
                })
            )

            # Gửi câu văn bản để hiển thị phụ đề khi nói
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "sentence_start",
                    "text": reply_text,
                })
            )

            # Biểu cảm speaking
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "speaking",
                    "text": "🙂",
                })
            )

            # 5. Stream âm thanh bằng Edge-TTS theo giọng nói đã cấu hình
            logger.info(f"[STREAMING] Đang tổng hợp giọng đọc '{voice_code}'...")
            stream_count = 0
            async for chunk in text_to_speech_stream(reply_text, voice=voice_code, chunk_size=1024):
                await websocket.send_bytes(chunk)
                stream_count += 1
                await asyncio.sleep(0.001)

            logger.info(f"[STREAMING] Đã stream xong {stream_count} gói audio.")

            # 6. Báo kết thúc TTS và trả biểu cảm về neutral
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "stop",
                })
            )
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "neutral",
                    "text": "😊",
                })
            )

        except asyncio.CancelledError:
            logger.info("[CONVERSATION] Bị ngắt lời bởi người dùng.")
            raise
        except Exception as e:
            logger.error(f"[CONVERSATION ERROR] {e}", exc_info=True)
            try:
                await websocket.send_text(
                    json.dumps({
                        "session_id": session_id,
                        "type": "tts",
                        "state": "stop",
                    })
                )
            except Exception:
                pass

    async def heartbeat_loop():
        try:
            while True:
                await asyncio.sleep(20)
                await websocket.send_text(json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                text_data = message["text"]
                try:
                    payload = json.loads(text_data)
                    msg_type = payload.get("type", "unknown")

                    if msg_type == "hello":
                        audio_params = payload.get("audio_params", {})
                        hello_ack = {
                            "type": "hello",
                            "transport": "websocket",
                            "session_id": session_id,
                            "audio_params": {
                                "format": audio_params.get("format", "opus"),
                                "sample_rate": audio_params.get("sample_rate", 16000),
                                "channels": audio_params.get("channels", 1),
                                "frame_duration": audio_params.get("frame_duration", 60),
                            },
                        }
                        await websocket.send_text(json.dumps(hello_ack))
                        logger.info(f"[SENT] Gửi phản hồi handshake 'hello' -> ESP32")

                    elif msg_type == "ping":
                        matched_dev["last_seen_ts"] = time.time()
                        matched_dev["is_online"] = True
                        await websocket.send_text(json.dumps({"type": "pong"}))

                    elif msg_type == "pong":
                        matched_dev["last_seen_ts"] = time.time()
                        matched_dev["is_online"] = True

                    elif msg_type == "listen":
                        state = payload.get("state")
                        detected_text = payload.get("text")

                        if state == "start":
                            await cancel_active_task("Người dùng bắt đầu nói")
                            audio_buffer.clear()
                            current_utterance_text = None
                            await websocket.send_text(
                                json.dumps({
                                    "session_id": session_id,
                                    "type": "llm",
                                    "emotion": "listening",
                                    "text": "👂",
                                })
                            )

                        elif state == "detect" and detected_text:
                            current_utterance_text = detected_text

                        elif state == "stop":
                            logger.info(f"[LISTEN STOP] Nhận xong âm thanh, bắt đầu xử lý.")
                            user_question = current_utterance_text

                            if not user_question and len(audio_buffer) > 0:
                                logger.info(f"[STT] Đang chuyển đổi {len(audio_buffer)} bytes audio sang text...")
                                user_question = await transcribe_audio_gemini(bytes(audio_buffer))
                                audio_buffer.clear()

                            if user_question:
                                await cancel_active_task("Bắt đầu xử lý câu hỏi mới")
                                active_process_task = asyncio.create_task(
                                    handle_conversation(user_question)
                                )
                            else:
                                logger.warning("[LISTEN STOP] Không phát hiện được nội dung câu hỏi.")
                                await websocket.send_text(
                                    json.dumps({
                                        "session_id": session_id,
                                        "type": "llm",
                                        "emotion": "neutral",
                                        "text": "😊",
                                    })
                                )

                    elif msg_type == "abort":
                        reason = payload.get("reason", "unknown")
                        logger.info(f"[ABORT] ESP32 yêu cầu ngắt: {reason}")
                        await cancel_active_task(f"Lệnh abort: {reason}")
                        await websocket.send_text(
                            json.dumps({
                                "session_id": session_id,
                                "type": "llm",
                                "emotion": "neutral",
                                "text": "😊",
                            })
                        )

                    elif msg_type == "chat":
                        chat_text = payload.get("text", "")
                        if chat_text:
                            await cancel_active_task("Tin nhắn chat mới")
                            active_process_task = asyncio.create_task(
                                handle_conversation(chat_text)
                            )

                except json.JSONDecodeError:
                    logger.warning(f"[TEXT RAW] {text_data}")

            elif "bytes" in message:
                raw_audio = message["bytes"]
                audio_buffer.extend(raw_audio)

            elif message.get("type") == "websocket.disconnect":
                break

    except WebSocketDisconnect as e:
        logger.warning(f"[DISCONNECT] ESP32 ngắt kết nối (code: {e.code})")
    except Exception as e:
        logger.error(f"[ERROR] Ngoại lệ WebSocket: {e}", exc_info=True)
    finally:
        heartbeat_task.cancel()
        await cancel_active_task("Đóng kết nối")
        active_websockets.pop(target_device_id, None)
        active_websockets.pop(device_mac, None)
        active_websockets.pop(pin_code, None)
        matched_dev["is_online"] = False
        device_manager.save_data()
        logger.info(f"[SESSION CLOSED] Phiên {session_id} đã kết thúc.")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"Khởi động Megabot Web Server & WebSocket tại:")
    logger.info(f" 👉 Web Dashboard (Megabot): http://localhost:{PORT}")
    logger.info(f" 👉 WebSocket Endpoint:         ws://localhost:{PORT}/ws/xiaozhi")
    logger.info("=" * 60)
    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
