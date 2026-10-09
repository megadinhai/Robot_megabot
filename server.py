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
from devices_manager import device_manager, generate_device_code, DEFAULT_DEVICES
from youtube_music import search_youtube, get_audio_stream_info, stream_youtube_audio_chunks, clean_query

# Quản lý phát nhạc YouTube online trên từng Robot
active_music_tasks: Dict[str, asyncio.Task] = {}
active_music_info: Dict[str, Dict[str, Any]] = {}

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
        response = FileResponse(html_path)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
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



@app.get("/test")
async def test_page():
    """Giao diện debug chat websocket."""
    html_path = os.path.join(os.path.dirname(__file__), "test_client.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "test_client.html not found"})


def get_active_socket(device_id: Optional[str] = None) -> Optional[WebSocket]:
    """Tìm WebSocket đang kết nối linh hoạt theo ID, MAC, PIN. Không mượn nhầm socket của robot khác."""
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
                if k and isinstance(k, str) and k.lower() in active_websockets:
                    return active_websockets[k.lower()]
        return None
    # Fallback: Chỉ khi không chỉ định robot cụ thể và có robot kết nối, lấy robot đầu tiên
    return next(iter(active_websockets.values()), None)


# ==========================================
# AUTHENTICATION & QUẢN TRỊ TÀI KHOẢN ROBOT RIÊNG (GMBOT MODEL)
# ==========================================

@app.post("/api/auth/login")
async def auth_login(req: Request):
    """
    Đăng nhập vào tài khoản quản trị của từng Robot riêng biệt (tương tự GMBot).
    Tên đăng nhập: Mã PIN 6 số (927184), ID thiết bị (ong-robot), hoặc địa chỉ MAC.
    Mật khẩu: Mật khẩu robot đã đặt (mặc định: 123456).
    """
    try:
        data = await req.json()
    except Exception:
        data = {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username:
        return JSONResponse({"success": False, "error": "Vui lòng nhập Mã PIN 6 số hoặc Tên Robot!"}, status_code=400)

    auth_res = device_manager.authenticate_device(username, password)
    if not auth_res:
        return JSONResponse({"success": False, "error": "Mã PIN/Tên Robot hoặc Mật khẩu không chính xác!"}, status_code=401)

    dev = auth_res["device"]
    # Kiểm tra trạng thái online thời gian thực
    dev_id = dev.get("id")
    dev_mac = str(dev.get("device_mac", "")).strip()
    dev_code = str(dev.get("device_code", "")).strip()
    has_socket = bool(
        (dev_id and dev_id in active_websockets)
        or (dev_mac and (dev_mac in active_websockets or dev_mac.lower() in active_websockets))
        or (dev_code and dev_code in active_websockets)
    )
    dev["is_online"] = has_socket

    return JSONResponse({
        "success": True,
        "token": auth_res["token"],
        "device": dev,
        "message": f"Đăng nhập thành công vào quản trị {dev.get('name')}!"
    })


@app.post("/api/auth/register")
async def auth_register(req: Request):
    """
    Kích hoạt / Đăng ký tài khoản quản trị cho một Robot mới.
    """
    try:
        data = await req.json()
    except Exception:
        data = {}

    name = str(data.get("name", "")).strip()
    code = str(data.get("device_code", "")).strip()
    password = str(data.get("password", "123456")).strip() or "123456"

    if not code and not data.get("device_mac"):
        return JSONResponse({"success": False, "error": "Vui lòng nhập Mã PIN 6 số hoặc Địa chỉ MAC của Robot!"}, status_code=400)

    auth_res = device_manager.register_device_account(data)
    dev = auth_res["device"]

    dev_id = dev.get("id")
    dev_mac = str(dev.get("device_mac", "")).strip()
    dev_code = str(dev.get("device_code", "")).strip()
    has_socket = bool(
        (dev_id and dev_id in active_websockets)
        or (dev_mac and (dev_mac in active_websockets or dev_mac.lower() in active_websockets))
        or (dev_code and dev_code in active_websockets)
    )
    dev["is_online"] = has_socket

    return JSONResponse({
        "success": True,
        "token": auth_res["token"],
        "device": dev,
        "message": f"Đã kích hoạt tài khoản Robot '{dev.get('name')}' thành công!"
    })


@app.get("/api/auth/accounts")
async def auth_list_accounts():
    """Lấy danh sách các tài khoản robot đang có trên server (hỗ trợ chuyển đổi nhanh)."""
    accounts = device_manager.get_accounts_summary()
    for acc in accounts:
        acc_id = acc.get("id")
        acc_code = acc.get("device_code")
        acc_mac = acc.get("device_mac")
        acc["is_online"] = bool(
            (acc_id and acc_id in active_websockets)
            or (acc_code and acc_code in active_websockets)
            or (acc_mac and (acc_mac in active_websockets or acc_mac.lower() in active_websockets))
        )
    return JSONResponse(accounts)


@app.get("/api/auth/me")
async def auth_me(req: Request):
    """Lấy thông tin tài khoản robot hiện tại qua Token hoặc Query ID."""
    token = req.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        token = req.query_params.get("token", "").strip()
    device_id = req.query_params.get("device_id", "").strip()

    dev = None
    if token:
        dev = device_manager.get_device_by_token(token)
    if not dev and device_id:
        dev = device_manager.get_device(device_id)

    if not dev:
        # Mặc định lấy robot đầu tiên nếu có
        dev = device_manager.get_default_device()

    if not dev:
        return JSONResponse({"success": False, "error": "Chưa đăng nhập tài khoản robot nào!"}, status_code=401)

    dev_id = dev.get("id")
    dev_mac = str(dev.get("device_mac", "")).strip()
    dev_code = str(dev.get("device_code", "")).strip()
    dev["is_online"] = bool(
        (dev_id and dev_id in active_websockets)
        or (dev_code and dev_code in active_websockets)
        or (dev_mac and (dev_mac in active_websockets or dev_mac.lower() in active_websockets))
    )
    return JSONResponse({"success": True, "device": dev})


@app.post("/api/auth/logout")
async def auth_logout():
    """Đăng xuất tài khoản robot."""
    return JSONResponse({"success": True, "message": "Đã đăng xuất thành công!"})


@app.post("/api/auth/change-password")
async def auth_change_password(req: Request):
    """Đổi mật khẩu quản trị cho robot."""
    try:
        data = await req.json()
    except Exception:
        data = {}
    device_id = str(data.get("device_id", "")).strip()
    new_pwd = str(data.get("password", "")).strip()
    if not device_id or not new_pwd:
        return JSONResponse({"success": False, "error": "Thiếu thông tin thiết bị hoặc mật khẩu mới!"}, status_code=400)
    ok = device_manager.change_device_password(device_id, new_pwd)
    if ok:
        return JSONResponse({"success": True, "message": "Đổi mật khẩu thành công!"})
    return JSONResponse({"success": False, "error": "Không tìm thấy thiết bị!"}, status_code=404)


# ==========================================
# REST APIS QUẢN LÝ THIẾT BỊ & CẤU HÌNH
# ==========================================

@app.get("/api/devices")
async def list_devices():
    """Danh sách thiết bị robot."""
    devices = device_manager.get_all_devices()
    now = time.time()
    for dev in devices:
        dev_id = dev.get("id")
        dev_mac = str(dev.get("device_mac", "")).strip()
        dev_code = str(dev.get("device_code", "")).strip()
        last_seen = float(dev.get("last_seen_ts") or 0)
        recently_active = (now - last_seen) < 120 if last_seen > 0 else False
        has_socket = bool(
            (dev_id and dev_id in active_websockets)
            or (dev_mac and (dev_mac in active_websockets or dev_mac.lower() in active_websockets))
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
    dev_mac = str(new_dev.get("device_mac", "")).strip()
    dev_code = str(new_dev.get("device_code", "")).strip()

    # Kiểm tra xem chính robot này có đang mở WebSocket không
    ws = None
    if dev_code and dev_code in active_websockets:
        ws = active_websockets[dev_code]
    elif dev_mac:
        ws = active_websockets.get(dev_mac.lower()) or active_websockets.get(dev_mac)

    if ws:
        if dev_id:
            active_websockets[dev_id] = ws
        if dev_code:
            active_websockets[dev_code] = ws
        if dev_mac:
            active_websockets[dev_mac] = ws
            active_websockets[dev_mac.lower()] = ws
        new_dev["is_online"] = True
        new_dev["last_seen_ts"] = time.time()
        device_manager.save_data()
    else:
        new_dev["is_online"] = False

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
    dev = device_manager.get_device(device_id)
    if dev:
        active_websockets.pop(dev.get("id"), None)
        active_websockets.pop(str(dev.get("device_code", "")).strip(), None)
        mac = str(dev.get("device_mac", "")).strip()
        if mac:
            active_websockets.pop(mac, None)
            active_websockets.pop(mac.lower(), None)
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

ENGLISH_TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "Web_templates", "all_english_templates.json")

def load_english_templates_file() -> Dict[str, Any]:
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "Web_templates", "all_english_templates.json"),
        os.path.join(os.path.dirname(__file__), "all_english_templates.json"),
        os.path.join(os.path.dirname(__file__), "Web_templates_Backup", "all_english_templates.json"),
        os.path.join(os.path.dirname(__file__), "Web_templates", "_archive", "all_english_templates.json"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Lỗi đọc {p}: {e}")
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
    template_id = data.get("templateId") or data.get("template_id") or data.get("id")
    template_obj = data.get("template") or {}

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    all_t = load_english_templates_file()
    all_items = all_t.get("lessons", []) + all_t.get("roleplay", [])
    item = next((t for t in all_items if t.get("id") == template_id or (data.get("title") and t.get("title") == data.get("title"))), None)

    # Nếu không tìm thấy bằng id trong file, sử dụng template_obj hoặc tiêu đề gửi lên
    if not item and template_obj:
        item = template_obj
    elif not item and data.get("title"):
        item = {
            "id": template_id or str(uuid.uuid4()),
            "title": data.get("title"),
            "level": data.get("level", "starter"),
            "topic": data.get("topic", "General"),
            "mode": data.get("mode", "lesson"),
            "target_words": data.get("target_words", []),
            "target_phrases": data.get("target_phrases", []),
            "tutor_note": data.get("tutor_note", ""),
        }

    # Nếu vẫn không tìm thấy, lấy bài học đầu tiên trong danh sách có sẵn
    if not item and all_items:
        item = all_items[0]

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
    return JSONResponse({
        "status": "ok",
        "success": True,
        "activeId": item.get("id"),
        "message": f"Đã áp dụng bài học: {item.get('title')}",
        "template": item
    })

@app.post("/api/english-tutor/activate")
async def activate_custom_english_tutor(req: Request):
    """Kích hoạt bài học tự tạo từ giao diện App tiếng Anh."""
    data = await req.json()
    device_id = data.get("deviceId") or data.get("device_id")
    title = data.get("title") or "Bài học tiếng Anh tùy chỉnh"
    level = data.get("level") or "starter"
    topic = data.get("topic") or "General"
    mode = data.get("mode") or "lesson"
    target_words = data.get("targetWords") or data.get("target_words") or ""
    target_phrases = data.get("targetPhrases") or data.get("target_phrases") or ""
    note = data.get("note") or data.get("tutor_note") or ""

    words_list = [w.strip() for w in target_words.split(",") if w.strip()] if isinstance(target_words, str) else (target_words or [])
    phrases_list = [p.strip() for p in target_phrases.split("\n") if p.strip()] if isinstance(target_phrases, str) else (target_phrases or [])

    template_item = {
        "id": f"custom-{uuid.uuid4().hex[:8]}",
        "title": title,
        "level": level,
        "topic": topic,
        "mode": mode,
        "target_words": words_list,
        "target_phrases": phrases_list,
        "tutor_note": note,
        "created_at": datetime.datetime.now().isoformat()
    }

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    words_str = ", ".join(words_list)
    phrases_str = "\n".join([f"- {p}" for p in phrases_list])
    dev["prompt"] = (
        f"# CHẾ ĐỘ GIA SƯ TIẾNG ANH SOPHIA ({'NHẬP VAI LUYỆN NÓI' if mode == 'roleplay' else 'BÀI HỌC'})\n"
        f"Bài học: {title}\n"
        f"Level: {level}\n"
        f"Chủ đề: {topic}\n\n"
        f"Từ vựng mục tiêu: {words_str}\n"
        f"Mẫu câu luyện tập:\n{phrases_str}\n\n"
        f"Ghi chú gia sư:\n{note}\n\n"
        f"Quy tắc giao tiếp: Nói tiếng Anh chậm rãi, thân thiện, kiên nhẫn. Sau mỗi lượt nói, đặt 1 câu hỏi hoặc gợi ý bé nhắc lại."
    )
    dev["active_english_template"] = template_item
    device_manager.save_data()
    device_manager.add_memory(target_id, f"[ENGLISH_TUTOR] {title}")

    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "llm", "emotion": "happy", "text": "🔤"}))
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": f"English Lesson: {title}"}))
        except Exception:
            pass

    return JSONResponse({
        "success": True,
        "status": "ok",
        "activeId": template_item["id"],
        "template": template_item
    })

@app.get("/api/english-tutor/active")
async def get_active_english_tutor(deviceId: Optional[str] = None):
    """Lấy thông tin bài tiếng Anh đang học (tương thích cả Dashboard và English Tutor App)."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    active = dev.get("active_english_template")
    if not active:
        return JSONResponse({"activeId": None, "active": None, "title": None, "content": ""})

    words = active.get("target_words", [])
    phrases = active.get("target_phrases", [])
    content = (
        f"[ENGLISH_TUTOR] Tiêu đề: {active.get('title')}\n"
        f"Trình độ: {active.get('level', 'starter')}\n"
        f"Chủ đề: {active.get('topic', 'General')}\n\n"
        f"Từ mục tiêu:\n" + "\n".join([f"- {w}" for w in words]) + "\n\n"
        f"Câu mục tiêu:\n" + "\n".join([f"- {p}" for p in phrases]) + (f"\n\nGhi chú cho gia sư:\n{active.get('tutor_note')}" if active.get("tutor_note") else "")
    )
    return JSONResponse({
        "success": True,
        "activeId": active.get("id"),
        "title": active.get("title"),
        "content": content,
        "createdAt": active.get("created_at") or datetime.datetime.now().isoformat(),
        "active": active
    })

@app.post("/api/english-tutor/deactivate")
@app.delete("/api/english-tutor/active")
async def deactivate_english_tutor(req: Request, deviceId: Optional[str] = None):
    """Tắt chế độ gia sư tiếng Anh trên robot."""
    dev_id = deviceId or req.query_params.get("deviceId") or req.query_params.get("device_id")
    if not dev_id:
        try:
            body = await req.json()
            dev_id = body.get("deviceId") or body.get("device_id")
        except Exception:
            pass
    dev = device_manager.get_device(dev_id) or device_manager.get_default_device()
    target_id = dev.get("id")
    dev["active_english_template"] = None
    default_prompt = DEFAULT_DEVICES[0].get("prompt", "Bạn là trợ lý robot thông minh Megabot.")
    dev["prompt"] = default_prompt
    device_manager.save_data()

    # Cập nhật thông báo lên màn hình OLED của robot nếu đang online
    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({
                "type": "tts",
                "state": "sentence_start",
                "text": "Đã tắt chế độ tiếng Anh."
            }))
        except Exception:
            pass

    logger.info(f"[ENGLISH TUTOR DEACTIVATED] Robot {dev.get('name')} đã tắt chế độ gia sư tiếng Anh")
    return JSONResponse({"success": True, "status": "ok", "message": "Đã tắt chế độ gia sư tiếng Anh"})

@app.post("/api/english-tutor/quick-review")
async def quick_review_english_tutor(req: Request):
    """Kích hoạt bài ôn tập nhanh 5 phút."""
    body = await req.json()
    device_id = body.get("deviceId")
    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    target_id = dev.get("id")

    review_item = {
        "id": f"review-{int(time.time())}",
        "title": "⚡ Ôn nhanh 5 phút",
        "level": "starter",
        "topic": "Quick Review",
        "mode": "lesson",
        "target_words": ["hello", "how are you", "good job", "thank you"],
        "target_phrases": ["How are you today?", "I am doing great!", "What is your favorite color?"],
        "tutor_note": "Ôn tập phản xạ nhanh trong 5 phút. Khen ngợi và khuyến khích bé nói to rõ ràng.",
        "created_at": datetime.datetime.now().isoformat()
    }

    dev["prompt"] = (
        "# CHẾ ĐỘ GIA SƯ TIẾNG ANH: ÔN NHANH 5 PHÚT\n"
        "Nhiệm vụ: Hỏi các câu hỏi tiếng Anh vui tươi, ngắn gọn để bé trả lời phản xạ nhanh.\n"
        "Khuyến khích bé nói cả câu. Nếu bé nói đúng, khen 'Excellent!' hoặc 'Good job!'."
    )
    dev["active_english_template"] = review_item
    device_manager.save_data()

    ws = get_active_socket(target_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": "Let's do a quick 5 minute English review!"}))
        except Exception:
            pass

    content = "[ENGLISH_TUTOR] Tiêu đề: Ôn nhanh 5 phút\nThời lượng: 5 phút\n\nTừ mục tiêu:\n- hello\n- how are you\n\nCâu mục tiêu:\n- How are you today?"
    active_obj = {
        "activeId": review_item["id"],
        "title": review_item["title"],
        "content": content,
        "createdAt": review_item["created_at"]
    }
    return JSONResponse({"success": True, "activeLesson": active_obj, "active": review_item})

@app.get("/api/english-tutor/recommendation")
async def get_english_tutor_recommendation(deviceId: Optional[str] = None):
    """Gợi ý bài học tiếng Anh phù hợp tiếp theo."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    active = dev.get("active_english_template")
    if active:
        return JSONResponse({
            "success": True,
            "type": "active",
            "title": active.get("title"),
            "reason": "Robot đang có bài học đang diễn ra. Hãy tiếp tục luyện tập cùng bé!",
            "estimatedMinutes": 10,
            "level": active.get("level", "starter"),
            "topic": active.get("topic", "General"),
            "mode": active.get("mode", "lesson"),
            "activeId": active.get("id"),
            "createdAt": active.get("created_at") or datetime.datetime.now().isoformat()
        })
    else:
        all_t = load_english_templates_file()
        lessons = all_t.get("lessons", [])
        rec_lesson = lessons[0] if lessons else {"title": "Daily Routine - Bài 1: My day", "level": "starter", "topic": "Daily Routine"}
        return JSONResponse({
            "success": True,
            "type": "recommended",
            "title": rec_lesson.get("title"),
            "reason": "Bài học nhập môn phù hợp nhất cho bé bắt đầu làm quen tiếng Anh hôm nay.",
            "estimatedMinutes": 10,
            "level": rec_lesson.get("level", "starter"),
            "topic": rec_lesson.get("topic", "Daily Routine"),
            "mode": "lesson"
        })

@app.get("/api/english-tutor/report")
async def get_english_tutor_report(deviceId: Optional[str] = None):
    """Báo cáo học tập tiếng Anh toàn diện cho phụ huynh."""
    dev = device_manager.get_device(deviceId) or device_manager.get_default_device()
    memories = dev.get("memories", [])
    english_mems = [m for m in memories if "[ENGLISH_TUTOR]" in m.get("content", "")]

    completed_count = len(english_mems)
    active = dev.get("active_english_template") or {}
    known = list(dict.fromkeys(active.get("target_words", []) + ["hello", "goodbye", "thank you", "cat", "dog", "apple"]))
    weak = ["weather", "umbrella"] if completed_count < 3 else []
    weak_p = ["It is raining outside."] if completed_count < 3 else []

    sessions = []
    for i, m in enumerate(english_mems[:10]):
        title = m.get("content").replace("[ENGLISH_TUTOR]", "").strip()
        sessions.append({
            "id": f"ses-{i+1}",
            "title": title or "Bài học tiếng Anh",
            "date": m.get("created_at", datetime.datetime.now().isoformat()),
            "duration_minutes": 10,
            "score": 9.0,
            "status": "completed"
        })

    return JSONResponse({
        "success": True,
        "total_lessons_completed": completed_count,
        "recent_lessons": [m.get("content").replace("[ENGLISH_TUTOR]", "").strip() for m in english_mems[:5]],
        "fluency_score": "8.5/10",
        "vocabulary_mastered": len(known),
        "advice": "Bé phát âm rất tự nhiên và phản xạ nhanh với các từ vựng chủ đề Động vật và Sinh hoạt hàng ngày!",
        "profile": {
            "known_words": known,
            "weak_words": weak,
            "weak_phrases": weak_p,
            "streak_days": max(1, completed_count)
        },
        "stats": {
            "completed_sessions": completed_count,
            "started_sessions": completed_count + (1 if active else 0),
            "abandoned_sessions": 0,
            "total_seconds": completed_count * 600,
            "avg_score": 8.8
        },
        "sessions": sessions
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


@app.post("/api/ocr")
async def ocr_image_endpoint(req: Request):
    """Trích xuất chữ từ ảnh (Sách giáo khoa, bài tập) qua AI Gemini Vision."""
    try:
        data = await req.json()
        image_data = data.get("image", "")  # Base64 data url hoặc raw base64
        prompt_type = data.get("type", "lesson")  # 'lesson' hoặc 'homework'
        custom_title = data.get("title", "").strip()

        if not image_data:
            return JSONResponse({"error": "Vui lòng cung cấp hình ảnh để scan."}, status_code=400)

        # Xử lý base64 data URI
        import base64
        import re
        mime_type = "image/jpeg"
        if image_data.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.*)", image_data)
            if match:
                mime_type = match.group(1)
                base64_str = match.group(2)
            else:
                base64_str = image_data
        else:
            base64_str = image_data

        try:
            image_bytes = base64.b64decode(base64_str)
        except Exception as e:
            return JSONResponse({"error": f"Lỗi giải mã ảnh base64: {e}"}, status_code=400)

        from google.genai import types
        from llm_handler import get_genai_client

        client = get_genai_client()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        if prompt_type == "homework":
            prompt = (
                "Bạn là chuyên gia OCR và trợ lý giáo dục. Hãy nhận diện và trích xuất toàn bộ câu hỏi, "
                "bài tập, công thức toán học hoặc yêu cầu đề bài trong bức ảnh này. "
                "Chỉ trả về văn bản đề bài rõ ràng, giữ nguyên cấu trúc các câu hỏi/bài tập, không thêm lời chào."
            )
        else:
            prompt = (
                "Bạn là chuyên gia OCR và trợ lý giáo dục. Hãy nhận diện và trích xuất toàn bộ văn bản, nội dung bài học, "
                "đoạn văn, kiến thức trong trang sách giáo khoa này. "
                "Chỉ trả về nội dung bài học chính xác và mạch lạc, không thêm lời chào."
            )

        extracted_text = ""
        candidate_models = ["gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite", "gemini-flash-latest"]
        last_err = None

        for m in candidate_models:
            try:
                resp = await client.aio.models.generate_content(
                    model=m,
                    contents=[image_part, prompt],
                )
                if resp.text:
                    extracted_text = resp.text.strip()
                    break
            except Exception as e:
                last_err = e
                logger.warning(f"[OCR] Lỗi model {m}: {e}")
                continue

        if not extracted_text:
            return JSONResponse({
                "error": f"Không thể nhận dạng văn bản từ ảnh: {last_err or 'Không có chữ trong ảnh'}"
            }, status_code=500)

        # Tự động tạo tiêu đề nếu người dùng chưa nhập
        detected_title = custom_title
        if not detected_title:
            first_line = extracted_text.split("\n")[0][:60].strip()
            first_line = re.sub(r'[*#_]', '', first_line).strip()
            if prompt_type == "homework":
                detected_title = f"Bài tập: {first_line or 'Bài tập từ ảnh'}"
            else:
                detected_title = f"Bài học: {first_line or 'Nội dung trang sách'}"

        return JSONResponse({
            "status": "ok",
            "title": detected_title,
            "text": extracted_text,
        })
    except Exception as e:
        logger.error(f"[OCR ERROR] {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/generate-lesson-plan")
async def generate_lesson_plan_endpoint(req: Request):
    """Dùng AI soạn bài giảng tương tác chi tiết cho robot từ văn bản đã scan."""
    try:
        data = await req.json()
        text = data.get("text", "").strip()
        title = data.get("title", "").strip() or "Bài học từ trang sách"

        if not text:
            return JSONResponse({"error": "Chưa có nội dung văn bản để soạn bài."}, status_code=400)

        prompt = (
            f"Bạn là chuyên gia sư phạm. Hãy dựa vào nội dung sách giáo khoa sau để soạn một kịch bản bài dạy tương tác "
            f"cho robot thông minh dạy một em học sinh.\n\n"
            f"NỘI DUNG SÁCH:\n{text}\n\n"
            f"YÊU CẦU BÀI DẠY:\n"
            f"1. Xác định mục tiêu bài học ngắn gọn.\n"
            f"2. Chia làm 2-3 phần giải thích thật dễ hiểu, dùng ngôn ngữ gần gũi, sinh động.\n"
            f"3. Sau mỗi phần, đưa ra 1 câu hỏi kiểm tra kèm lời khen ngợi khích lệ.\n"
            f"4. Trình bày rõ ràng, mạch lạc."
        )

        plan = await chat_with_gemini(prompt)
        return JSONResponse({
            "status": "ok",
            "title": title,
            "content": plan
        })
    except Exception as e:
        logger.error(f"[GENERATE LESSON ERROR] {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)



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
    api_keys = {
        "openai_api_key": dev.get("openai_api_key"),
        "deepseek_api_key": dev.get("deepseek_api_key"),
        "gemini_api_key": dev.get("gemini_api_key"),
    }

    reply = await chat_with_gemini(user_text, system_instruction=prompt, model_override=model_override, api_keys=api_keys)

    # Nếu có robot đang kết nối, hiển thị câu trả lời lên màn hình OLED của robot
    ws = get_active_socket(device_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": reply}))
        except Exception:
            pass

    return JSONResponse({"reply": reply})


# ==========================================
# QUẢN LÝ PHÁT NHẠC YOUTUBE ONLINE TRÊN ROBOT
# ==========================================

async def stop_youtube_music_on_robot(device_id: str) -> bool:
    """Dừng stream nhạc YouTube đang phát trên Robot."""
    task = active_music_tasks.get(device_id)
    stopped = False
    if task and not task.done():
        logger.info(f"[MUSIC STOP] Dừng phát nhạc cho robot {device_id}")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        stopped = True

    if device_id in active_music_tasks:
        del active_music_tasks[device_id]

    if device_id in active_music_info:
        active_music_info[device_id]["status"] = "stopped"

    ws = get_active_socket(device_id)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "stop"}))
            await ws.send_text(json.dumps({"type": "llm", "emotion": "neutral", "text": "😊"}))
        except Exception:
            pass

    return stopped


async def play_youtube_music_on_robot(
    device_id: str,
    query_or_url: str,
    session_id: Optional[str] = None,
    announce: bool = True
) -> Dict[str, Any]:
    """Tìm bài hát trên YouTube và stream dữ liệu audio qua WebSocket xuống robot."""
    ws = get_active_socket(device_id)
    if not ws:
        logger.warning(f"[MUSIC PLAY] Robot {device_id} chưa kết nối WebSocket")
        return {"success": False, "error": "Robot chưa kết nối WebSocket"}

    # Dừng bài nhạc trước nếu đang phát
    await stop_youtube_music_on_robot(device_id)

    target = query_or_url.strip()
    is_url = target.startswith("http://") or target.startswith("https://")

    stream_info = None
    if is_url:
        stream_info = await get_audio_stream_info(target)
    else:
        results = await search_youtube(target, max_results=1)
        if results:
            stream_info = await get_audio_stream_info(results[0]["id"])

    if not stream_info or not stream_info.get("audio_url"):
        error_msg = f"Không tìm thấy bài hát '{target}' trên YouTube"
        logger.warning(f"[MUSIC PLAY ERROR] {error_msg}")
        try:
            await ws.send_text(json.dumps({"type": "tts", "state": "sentence_start", "text": error_msg[:30]}))
            await ws.send_text(json.dumps({"type": "llm", "emotion": "sad", "text": "😢"}))
        except Exception:
            pass
        return {"success": False, "error": error_msg}

    title = stream_info.get("title", "YouTube Music")
    uploader = stream_info.get("uploader", "YouTube")
    thumbnail = stream_info.get("thumbnail", "")
    duration_str = stream_info.get("duration_str", "00:00")
    audio_url = stream_info.get("audio_url")

    active_music_info[device_id] = {
        "title": title,
        "uploader": uploader,
        "thumbnail": thumbnail,
        "duration_str": duration_str,
        "url": stream_info.get("url", ""),
        "started_at": time.time(),
        "status": "playing",
    }

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    voice = dev.get("voice", "vi-VN-HoaiMyNeural")
    sess_id = session_id or uuid.uuid4().hex

    async def _stream_worker():
        try:
            # 1. Câu thông báo mở đầu
            if announce:
                try:
                    await ws.send_text(json.dumps({
                        "session_id": sess_id,
                        "type": "tts",
                        "state": "start"
                    }))
                    await ws.send_text(json.dumps({
                        "session_id": sess_id,
                        "type": "tts",
                        "state": "sentence_start",
                        "text": f"🎵 {title[:25]}"
                    }))
                    await ws.send_text(json.dumps({
                        "session_id": sess_id,
                        "type": "llm",
                        "emotion": "happy",
                        "text": "🎵"
                    }))

                    intro_speech = f"Em đang phát bài {clean_query(target)} trên YouTube ạ!"
                    async for chunk in text_to_speech_stream(intro_speech, voice=voice, chunk_size=1024):
                        await ws.send_bytes(chunk)
                        await asyncio.sleep(0.001)
                    await asyncio.sleep(0.4)
                except Exception as tts_err:
                    logger.warning(f"[MUSIC INTRO WARNING] {tts_err}")

            # 2. Bắt đầu phiên TTS stream nhạc
            await ws.send_text(json.dumps({
                "session_id": sess_id,
                "type": "tts",
                "state": "start"
            }))
            await ws.send_text(json.dumps({
                "session_id": sess_id,
                "type": "tts",
                "state": "sentence_start",
                "text": f"🎵 {title[:28]}"
            }))
            await ws.send_text(json.dumps({
                "session_id": sess_id,
                "type": "llm",
                "emotion": "happy",
                "text": "🎶"
            }))

            # 3. Stream các gói audio
            logger.info(f"[MUSIC STREAM] Bắt đầu stream '{title}' tới robot {device_id}...")
            chunk_count = 0
            async for chunk in stream_youtube_audio_chunks(audio_url, chunk_size=1024, pace_delay=0.045):
                await ws.send_bytes(chunk)
                chunk_count += 1

            logger.info(f"[MUSIC STREAM] Hoàn thành stream {chunk_count} gói cho '{title}'.")

            # 4. Kết thúc phiên stream
            await ws.send_text(json.dumps({
                "session_id": sess_id,
                "type": "tts",
                "state": "stop"
            }))
            await ws.send_text(json.dumps({
                "session_id": sess_id,
                "type": "llm",
                "emotion": "neutral",
                "text": "😊"
            }))
        except asyncio.CancelledError:
            logger.info(f"[MUSIC STREAM] Tác vụ phát bài '{title}' đã bị hủy.")
            try:
                await ws.send_text(json.dumps({
                    "session_id": sess_id,
                    "type": "tts",
                    "state": "stop"
                }))
                await ws.send_text(json.dumps({
                    "session_id": sess_id,
                    "type": "llm",
                    "emotion": "neutral",
                    "text": "😊"
                }))
            except Exception:
                pass
            raise
        except Exception as err:
            logger.error(f"[MUSIC STREAM ERROR] {err}", exc_info=True)
            try:
                await ws.send_text(json.dumps({"session_id": sess_id, "type": "tts", "state": "stop"}))
            except Exception:
                pass
        finally:
            if device_id in active_music_info:
                active_music_info[device_id]["status"] = "stopped"
            if device_id in active_music_tasks:
                del active_music_tasks[device_id]

    task = asyncio.create_task(_stream_worker())
    active_music_tasks[device_id] = task
    return {
        "success": True,
        "title": title,
        "uploader": uploader,
        "thumbnail": thumbnail,
        "duration_str": duration_str,
        "status": "playing",
    }


# ==========================================
# CÁC API ENDPOINTS PHÁT NHẠC YOUTUBE ONLINE
# ==========================================

@app.get("/api/music/search")
async def api_music_search(q: str = ""):
    """Tìm kiếm bài hát trên YouTube."""
    if not q or not q.strip():
        return JSONResponse({"success": False, "results": [], "error": "Vui lòng nhập tên bài hát cần tìm"})
    try:
        results = await search_youtube(q.strip(), max_results=6)
        return JSONResponse({"success": True, "results": results})
    except Exception as e:
        logger.error(f"[API MUSIC SEARCH ERROR] {e}")
        return JSONResponse({"success": False, "results": [], "error": str(e)}, status_code=500)


@app.post("/api/music/play")
async def api_music_play(req: Request):
    """Phát một bài hát YouTube trên Robot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    device_id = data.get("device_id")
    query_or_url = data.get("url") or data.get("video_id") or data.get("query") or ""
    if not query_or_url:
        return JSONResponse({"success": False, "error": "Vui lòng chọn bài hát hoặc nhập từ khóa tìm kiếm"}, status_code=400)

    if not device_id:
        dev = device_manager.get_default_device()
        device_id = dev.get("id") if dev else None

    if not device_id:
        return JSONResponse({"success": False, "error": "Không tìm thấy Robot đang đăng nhập"}, status_code=400)

    res = await play_youtube_music_on_robot(device_id, query_or_url)
    return JSONResponse(res)


@app.post("/api/music/stop")
async def api_music_stop(req: Request):
    """Dừng phát nhạc YouTube trên Robot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    device_id = data.get("device_id")
    if not device_id:
        dev = device_manager.get_default_device()
        device_id = dev.get("id") if dev else None

    if not device_id:
        return JSONResponse({"success": False, "error": "Không tìm thấy Robot"}, status_code=400)

    await stop_youtube_music_on_robot(device_id)
    return JSONResponse({"success": True, "status": "stopped"})


@app.get("/api/music/status")
async def api_music_status(device_id: Optional[str] = None):
    """Lấy trạng thái bài hát đang phát trên Robot."""
    if not device_id:
        dev = device_manager.get_default_device()
        device_id = dev.get("id") if dev else None

    info = active_music_info.get(device_id, {})
    is_playing = (device_id in active_music_tasks) and not active_music_tasks[device_id].done()
    return JSONResponse({
        "success": True,
        "is_playing": is_playing,
        "track": info if is_playing else None,
    })


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
    if device_mac and isinstance(device_mac, str):
        active_websockets[device_mac.lower()] = websocket
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
        if target_device_id in active_music_tasks:
            await stop_youtube_music_on_robot(target_device_id)

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

            # --- KIỂM TRA LỆNH DỪNG NHẠC BẰNG GIỌNG NÓI ---
            prompt_clean = user_prompt.strip().lower()
            stop_triggers = [
                "dừng nhạc", "tắt nhạc", "ngừng nhạc", "ngừng phát nhạc",
                "dừng bài hát", "tắt bài hát", "dừng phát", "ngừng phát",
                "tắt loa", "dừng lại đi", "stop music", "dừng hát", "tắt bài"
            ]
            if any(t in prompt_clean for t in stop_triggers):
                logger.info(f"[VOICE COMMAND] Nhận lệnh dừng nhạc cho robot {target_device_id}")
                await stop_youtube_music_on_robot(target_device_id)
                reply_text = "Đã dừng phát nhạc rồi bạn nhé!"
                await websocket.send_text(json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "start"
                }))
                await websocket.send_text(json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "sentence_start",
                    "text": reply_text
                }))
                await websocket.send_text(json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "happy",
                    "text": "😊"
                }))
                async for chunk in text_to_speech_stream(reply_text, voice=voice_code, chunk_size=1024):
                    await websocket.send_bytes(chunk)
                    await asyncio.sleep(0.001)
                await websocket.send_text(json.dumps({
                    "session_id": session_id,
                    "type": "tts",
                    "state": "stop"
                }))
                await websocket.send_text(json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "neutral",
                    "text": "😊"
                }))
                return

            # --- KIỂM TRA LỆNH PHÁT NHẠC YOUTUBE BẰNG GIỌNG NÓI ---
            play_triggers = [
                "mở bài", "phát bài", "bật bài", "nghe bài", "hát bài", "chơi bài",
                "mở nhạc", "phát nhạc", "bật nhạc", "nghe nhạc", "hát cho tôi",
                "hát cho em", "hát cho bé", "tìm bài", "trên youtube", "ở youtube"
            ]
            if any(t in prompt_clean for t in play_triggers):
                song_search = clean_query(user_prompt)
                if song_search and len(song_search) >= 2:
                    logger.info(f"[VOICE COMMAND] Nhận lệnh phát nhạc YouTube: '{song_search}' cho robot {target_device_id}")
                    await play_youtube_music_on_robot(
                        device_id=target_device_id,
                        query_or_url=song_search,
                        session_id=session_id,
                        announce=True
                    )
                    return

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
            api_keys = {
                "openai_api_key": cur_cfg.get("openai_api_key"),
                "deepseek_api_key": cur_cfg.get("deepseek_api_key"),
                "gemini_api_key": cur_cfg.get("gemini_api_key"),
            }
            reply_text = await chat_with_gemini(
                user_prompt,
                chat_history=active_history,
                system_instruction=custom_prompt,
                model_override=model_id,
                api_keys=api_keys,
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
        if device_mac and isinstance(device_mac, str):
            active_websockets.pop(device_mac.lower(), None)
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
