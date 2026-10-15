import asyncio
import datetime
import gc
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Set
import av
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Chủ động cấu hình Garbage Collector dọn dẹp bộ nhớ trên môi trường hạn chế RAM (Render Free 512MB)
gc.set_threshold(400, 10, 10)

try:
    import ctypes
    _libc = ctypes.CDLL("libc.so.6")
    def malloc_trim():
        try:
            _libc.malloc_trim(0)
        except Exception:
            pass
except Exception:
    def malloc_trim():
        pass

def release_memory():
    """Thu hồi bộ nhớ Python và trả RAM C/FFmpeg trực tiếp về hệ điều hành Linux trên Render."""
    try:
        gc.collect()
        malloc_trim()
    except Exception:
        pass

from audio_handler import (
    text_to_speech_stream,
    text_to_speech_opus_stream,
    stream_speech_to_socket,
    decode_opus_packets_to_wav,
    decode_opus_packet_peak,
    transcribe_audio_gemini,
    format_tts_speed,
    format_tts_pitch,
)
from llm_handler import chat_with_gemini
from devices_manager import device_manager, generate_device_code, DEFAULT_DEVICES
from youtube_music import (
    search_youtube,
    get_audio_stream_info,
    stream_youtube_audio_chunks,
    stream_youtube_audio_opus_packets,
    clean_query,
    extract_music_intent,
)

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

@app.on_event("startup")
async def periodic_memory_cleaner():
    async def _clean_loop():
        while True:
            await asyncio.sleep(30)
            release_memory()
    asyncio.create_task(_clean_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Lưu trữ các WebSocket đang hoạt động để gửi lệnh điều khiển robot
active_websockets: Dict[str, WebSocket] = {}

recent_logs: List[str] = []

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            recent_logs.append(msg)
            if len(recent_logs) > 40:
                recent_logs.pop(0)
        except Exception:
            pass

_mem_handler = MemoryLogHandler()
_mem_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logger.addHandler(_mem_handler)
logging.getLogger().addHandler(_mem_handler)

@app.get("/api/debug/logs")
async def debug_logs():
    return JSONResponse({
        "active_sockets": list(active_websockets.keys()),
        "devices": [{ "id": d.get("id"), "online": d.get("is_online"), "mac": d.get("device_mac"), "code": d.get("device_code") } for d in device_manager.get_all_devices()],
        "logs": recent_logs[-30:]
    })


# ==========================================
# THEO DÕI LOG GHI ÂM MIC TRỰC TIẾP (LIVE MIC MONITOR)
# ==========================================
web_mic_monitors: Set[WebSocket] = set()
mic_telemetry_history: List[Dict[str, Any]] = []

current_mic_telemetry: Dict[str, Any] = {
    "state": "idle",
    "device_name": "Megabot",
    "peak": 0,
    "level": 0.0,
    "packet_count": 0,
    "duration_ms": 0,
    "bytes_received": 0,
    "last_text": "",
    "last_reply": "",
    "updated_at": ""
}

async def broadcast_mic_telemetry(payload: Dict[str, Any]):
    """Phát luồng dữ liệu sóng âm, trạng thái và log mic thời gian thực tới tất cả Web clients."""
    # Nếu không có Web dashboard nào đang mở theo dõi mic, không tạo chuỗi json và không phát
    if not web_mic_monitors and payload.get("type") == "audio_packet":
        return

    now_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    payload["timestamp"] = now_str
    
    mic_telemetry_history.append(payload)
    if len(mic_telemetry_history) > 30:
        mic_telemetry_history.pop(0)

    dead_sockets = set()
    for ws in list(web_mic_monitors):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead_sockets.add(ws)
    web_mic_monitors.difference_update(dead_sockets)


def get_devices_with_status() -> List[Dict[str, Any]]:
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
    return devices

async def broadcast_device_event(action: str, data: Dict[str, Any]):
    """Phát sự kiện cập nhật thiết bị real-time tới tất cả Web clients đang mở WebSocket."""
    payload = {
        "type": "device_event",
        "action": action,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        **data,
    }
    dead = set()
    for ws in list(web_mic_monitors):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    web_mic_monitors.difference_update(dead)

async def handle_device_ws_message(websocket: WebSocket, payload: Dict[str, Any]) -> bool:
    """Xử lý các gói tin quản lý, xem, sửa, xóa tài khoản thiết bị qua WebSocket."""
    msg_type = payload.get("type", "")

    if msg_type in ["device_list", "get_devices", "devices.list"]:
        devs = get_devices_with_status()
        await websocket.send_text(json.dumps({
            "type": "device_list",
            "success": True,
            "devices": devs,
            "count": len(devs),
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }))
        return True

    elif msg_type in ["device_get", "get_device", "devices.get"]:
        dev_id = payload.get("id") or payload.get("device_id") or payload.get("device_code")
        dev = device_manager.get_device(dev_id)
        if dev:
            now = time.time()
            last_seen = float(dev.get("last_seen_ts") or 0)
            has_socket = (
                dev.get("id") in active_websockets
                or dev.get("device_code") in active_websockets
                or dev.get("device_mac") in active_websockets
            )
            dev["is_online"] = has_socket or ((now - last_seen) < 120 if last_seen > 0 else False)
            await websocket.send_text(json.dumps({
                "type": "device_info",
                "success": True,
                "device": dev
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "device_info",
                "success": False,
                "error": f"Không tìm thấy thiết bị: {dev_id}"
            }))
        return True

    elif msg_type in ["device_create", "add_device", "devices.create"]:
        data = payload.get("data") or payload.get("device") or payload
        dev_input = {k: v for k, v in data.items() if k != "type"} if isinstance(data, dict) else {}
        new_dev = device_manager.add_device(dev_input)
        devs = get_devices_with_status()
        await websocket.send_text(json.dumps({
            "type": "device_created",
            "success": True,
            "device": new_dev,
            "message": f"Đã tạo tài khoản thiết bị {new_dev.get('name')} thành công"
        }))
        await broadcast_device_event("created", {"device": new_dev, "devices": devs})
        return True

    elif msg_type in ["device_update", "edit_device", "devices.update"]:
        dev_id = payload.get("id") or payload.get("device_id")
        update_data = payload.get("data") or payload.get("update") or payload
        clean_update = {k: v for k, v in update_data.items() if k not in ["type", "id", "device_id"]} if isinstance(update_data, dict) else {}
        updated = device_manager.update_device(dev_id, clean_update)
        if updated:
            devs = get_devices_with_status()
            await websocket.send_text(json.dumps({
                "type": "device_updated",
                "success": True,
                "device": updated,
                "message": f"Đã cập nhật thông tin thiết bị {updated.get('name')} thành công"
            }))
            await broadcast_device_event("updated", {"device": updated, "devices": devs})
        else:
            await websocket.send_text(json.dumps({
                "type": "device_updated",
                "success": False,
                "error": f"Không tìm thấy thiết bị để cập nhật: {dev_id}"
            }))
        return True

    elif msg_type in ["device_delete", "delete_device", "devices.delete"]:
        dev_id = payload.get("id") or payload.get("device_id")
        dev = device_manager.get_device(dev_id)
        if dev:
            active_websockets.pop(dev.get("id"), None)
            active_websockets.pop(str(dev.get("device_code", "")).strip(), None)
            mac = str(dev.get("device_mac", "")).strip()
            if mac:
                active_websockets.pop(mac, None)
                active_websockets.pop(mac.lower(), None)
        success = device_manager.delete_device(dev_id)
        devs = get_devices_with_status()
        await websocket.send_text(json.dumps({
            "type": "device_deleted",
            "success": success,
            "id": dev_id,
            "message": f"Đã xóa thiết bị {dev_id} thành công" if success else "Không tìm thấy thiết bị để xóa"
        }))
        if success:
            await broadcast_device_event("deleted", {"id": dev_id, "devices": devs})
        return True

    elif msg_type in ["admin_login", "auth.admin_login"]:
        u = payload.get("username", "admin")
        p = payload.get("password", "")
        admin_res = device_manager.authenticate_admin(u, p)
        await websocket.send_text(json.dumps({
            "type": "admin_login_res",
            "success": bool(admin_res),
            "is_admin": bool(admin_res),
            "token": admin_res["token"] if admin_res else None,
            "message": "Đăng nhập Admin thành công!" if admin_res else "Mật khẩu Admin không chính xác!"
        }))
        return True

    elif msg_type in ["admin_change_password"]:
        new_p = payload.get("password") or payload.get("new_password")
        ok = device_manager.change_admin_password(new_p)
        await websocket.send_text(json.dumps({
            "type": "admin_change_password_res",
            "success": ok,
            "message": "Đã đổi mật khẩu Admin thành công qua WebSocket!" if ok else "Lỗi đổi mật khẩu Admin"
        }))
        return True

    return False


@app.websocket("/ws/mic-monitor")
async def ws_mic_monitor_endpoint(websocket: WebSocket):
    """WebSocket stream dành riêng cho giao diện web dashboard theo dõi mic và quản lý thiết bị trực tiếp."""
    await websocket.accept()
    web_mic_monitors.add(websocket)
    try:
        # Gửi ngay trạng thái hiện tại, danh sách thiết bị và 30 log gần nhất cho dashboard khi kết nối
        await websocket.send_text(json.dumps({
            "type": "init",
            "current": current_mic_telemetry,
            "history": mic_telemetry_history[-40:],
            "active_devices": list(active_websockets.keys()),
            "devices": get_devices_with_status(),
        }))
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            try:
                payload = json.loads(msg)
                if isinstance(payload, dict):
                    await handle_device_ws_message(websocket, payload)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        web_mic_monitors.discard(websocket)


@app.websocket("/ws/devices")
async def ws_devices_endpoint(websocket: WebSocket):
    """WebSocket chuyên dụng quản lý, xem thông tin, chỉnh sửa, xóa các tài khoản thiết bị theo thời gian thực."""
    await websocket.accept()
    web_mic_monitors.add(websocket)
    try:
        # Gửi ngay danh sách thiết bị khi vừa kết nối
        devs = get_devices_with_status()
        await websocket.send_text(json.dumps({
            "type": "device_list",
            "success": True,
            "devices": devs,
            "count": len(devs),
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        }))
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            try:
                payload = json.loads(msg)
                if isinstance(payload, dict):
                    await handle_device_ws_message(websocket, payload)
            except Exception as e:
                logger.error(f"[WS DEVICES ERROR] {e}")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        web_mic_monitors.discard(websocket)


@app.get("/api/mic/status")
async def get_mic_status_api():
    """API lấy trạng thái và log micro hiện tại (hỗ trợ polling khi cần)."""
    return JSONResponse({
        "current": current_mic_telemetry,
        "history": mic_telemetry_history[-40:],
        "active_devices": list(active_websockets.keys()),
        "devices": get_devices_with_status(),
    })



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
    """Tìm WebSocket đang kết nối linh hoạt theo ID, MAC, PIN. Tự động chuyển tới robot đang kết nối nếu có."""
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
    # Fallback: Nếu không tìm thấy chính xác hoặc chỉ có robot duy nhất đang kết nối, tự động lấy robot đầu tiên
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

    # 1. Kiểm tra nếu đăng nhập tài khoản Super Admin
    if username.lower() in ["admin", "superadmin", "administrator"]:
        admin_res = device_manager.authenticate_admin(username, password)
        if admin_res:
            return JSONResponse({
                "success": True,
                "role": "admin",
                "is_admin": True,
                "token": admin_res["token"],
                "user": admin_res["user"],
                "message": "Đăng nhập thành công với quyền Quản Trị Viên (Super Admin)!"
            })
        else:
            return JSONResponse({"success": False, "error": "Tài khoản hoặc Mật khẩu Admin không chính xác!"}, status_code=401)

    auth_res = device_manager.authenticate_device(username, password)
    if not auth_res:
        return JSONResponse({"success": False, "error": "Mã PIN/Tên Robot hoặc Mật khẩu không chính xác!"}, status_code=401)

    if auth_res.get("role") == "admin":
        return JSONResponse({
            "success": True,
            "role": "admin",
            "is_admin": True,
            "token": auth_res["token"],
            "user": auth_res.get("user", {}),
            "message": "Đăng nhập thành công với quyền Quản Trị Viên (Super Admin)!"
        })

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
        "role": "device",
        "is_admin": False,
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
    """Lấy thông tin tài khoản hiện tại (Admin hoặc Robot) qua Token hoặc Query ID."""
    token = req.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        token = req.query_params.get("token", "").strip()
    device_id = req.query_params.get("device_id", "").strip()

    # 1. Kiểm tra nếu là Token của Super Admin
    if token and device_manager.is_admin_token(token):
        default_dev = device_manager.get_device("ong-robot") or device_manager.get_default_device()
        return JSONResponse({
            "success": True,
            "role": "admin",
            "is_admin": True,
            "user": {
                "username": device_manager.admin.get("username", "admin"),
                "name": device_manager.admin.get("name", "Quản Trị Viên (Super Admin)"),
                "role": "admin",
            },
            "device": default_dev
        })

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
    return JSONResponse({"success": True, "role": "device", "is_admin": False, "device": dev})


@app.post("/api/auth/logout")
async def auth_logout():
    """Đăng xuất tài khoản robot / admin."""
    return JSONResponse({"success": True, "message": "Đã đăng xuất thành công!"})


@app.post("/api/admin/change-password")
async def admin_change_password(req: Request):
    """Đổi mật khẩu tài khoản Quản Trị Viên (Admin)."""
    try:
        data = await req.json()
    except Exception:
        data = {}
    new_pwd = str(data.get("password") or data.get("new_password") or "").strip()
    if not new_pwd:
        return JSONResponse({"success": False, "error": "Vui lòng nhập mật khẩu Admin mới!"}, status_code=400)
    ok = device_manager.change_admin_password(new_pwd)
    if ok:
        return JSONResponse({"success": True, "message": "✓ Đã cập nhật mật khẩu Admin thành công!"})
    return JSONResponse({"success": False, "error": "Không thể đổi mật khẩu Admin!"}, status_code=500)


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
    return JSONResponse(get_devices_with_status())


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

    await broadcast_device_event("created", {"device": new_dev, "devices": get_devices_with_status()})
    return JSONResponse(new_dev)


@app.get("/api/devices/{device_id}")
async def get_device_config(device_id: str):
    """Lấy chi tiết cấu hình 1 thiết bị."""
    dev = device_manager.get_device(device_id)
    if not dev:
        return JSONResponse({"error": "Device not found"}, status_code=404)
    now = time.time()
    last_seen = float(dev.get("last_seen_ts") or 0)
    has_socket = bool(
        dev.get("id") in active_websockets
        or dev.get("device_code") in active_websockets
        or dev.get("device_mac") in active_websockets
    )
    dev["is_online"] = has_socket or ((now - last_seen) < 120 if last_seen > 0 else False)
    return JSONResponse(dev)


@app.put("/api/devices/{device_id}")
async def update_device_config(device_id: str, req: Request):
    """Cập nhật các tab cấu hình (Vai trò, Mô hình, Đồ chơi, Mở rộng) của robot."""
    data = await req.json()
    updated = device_manager.update_device(device_id, data)
    if not updated:
        return JSONResponse({"error": "Device not found"}, status_code=404)
    await broadcast_device_event("updated", {"device": updated, "devices": get_devices_with_status()})
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
    if success:
        await broadcast_device_event("deleted", {"id": device_id, "devices": get_devices_with_status()})
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
    """Gửi câu nói: hiển thị phụ đề lên màn hình OLED và stream âm thanh Opus xuống loa robot."""
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
        await stream_speech_to_socket(ws, text, voice=voice, emotion=emotion)
        logger.info(f"[ROBOT SPEAK] Đã phát giọng nói Opus '{text}' tới robot")
        return JSONResponse({"status": "ok", "text": text})
    except Exception as e:
        logger.error(f"[ROBOT SPEAK ERROR] {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/chat")
async def test_chat_api(req: Request):
    """Test trò chuyện trực tiếp với AI theo System Prompt: vừa trả về web vừa phát loa robot."""
    data = await req.json()
    device_id = data.get("device_id")
    user_text = data.get("text", "")
    if not user_text:
        return JSONResponse({"reply": "Vui lòng nhập câu hỏi"})

    if not device_id:
        dev = device_manager.get_default_device()
        device_id = dev.get("id") if dev else None

    # 1. Kiểm tra trực tiếp lệnh nhạc từ ý định câu nói (Fast Intent Check)
    music_intent = extract_music_intent(user_text)
    if music_intent:
        if music_intent["action"] == "stop":
            if device_id:
                asyncio.create_task(stop_youtube_music_on_robot(device_id))
            reply = "Dạ, em đã dừng phát nhạc rồi bạn nhé! 😊"
            ws = get_active_socket(device_id)
            if ws:
                dev = device_manager.get_device(device_id) or device_manager.get_default_device()
                voice = dev.get("voice", "vi-VN-HoaiMyNeural")
                asyncio.create_task(stream_speech_to_socket(ws, reply, voice=voice))
            return JSONResponse({"reply": reply})
        elif music_intent["action"] == "play":
            song = music_intent.get("song") or clean_query(user_text)
            reply = f"Dạ, em mở bài {song} trên YouTube cho bạn nghe ngay nhé! 🎵"
            if device_id:
                asyncio.create_task(play_youtube_music_on_robot(device_id, song, announce=True))
            return JSONResponse({"reply": reply})

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    prompt = dev.get("prompt")
    model_override = dev.get("model_id")
    voice = dev.get("voice", "vi-VN-HoaiMyNeural")
    api_keys = {
        "openai_api_key": dev.get("openai_api_key"),
        "deepseek_api_key": dev.get("deepseek_api_key"),
        "gemini_api_key": dev.get("gemini_api_key"),
    }

    reply = await chat_with_gemini(user_text, system_instruction=prompt, model_override=model_override, api_keys=api_keys)

    # 2. Kiểm tra nếu LLM phản hồi kèm thẻ điều khiển phát nhạc
    if "[[PLAY_MUSIC:" in reply:
        m = re.search(r'\[\[PLAY_MUSIC:\s*(.+?)\]\]', reply, flags=re.IGNORECASE)
        if m and device_id:
            song_name = m.group(1).strip()
            asyncio.create_task(play_youtube_music_on_robot(device_id, song_name, announce=False))
        reply = re.sub(r'\[\[PLAY_MUSIC:.*?\]\]', '', reply, flags=re.IGNORECASE).strip()
    elif "[[STOP_MUSIC]]" in reply:
        if device_id:
            asyncio.create_task(stop_youtube_music_on_robot(device_id))
        reply = re.sub(r'\[\[STOP_MUSIC\]\]', '', reply, flags=re.IGNORECASE).strip()

    # Nếu có robot đang kết nối, vừa hiển thị phụ đề vừa phát âm thanh Opus qua loa
    ws = get_active_socket(device_id)
    if ws:
        try:
            asyncio.create_task(stream_speech_to_socket(ws, reply, voice=voice))
        except Exception as e:
            logger.warning(f"[CHAT SPEAK WARNING] {e}")

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
        results = await search_youtube(target, max_results=4)
        for r in results:
            vid_id = r.get("id")
            if vid_id:
                stream_info = await get_audio_stream_info(vid_id)
                if stream_info and stream_info.get("audio_url"):
                    break

    dev = device_manager.get_device(device_id) or device_manager.get_default_device()
    voice = dev.get("voice", "vi-VN-HoaiMyNeural")

    if not stream_info or not stream_info.get("audio_url"):
        error_msg = f"Không tìm thấy bài hát '{target}' trên YouTube"
        logger.warning(f"[MUSIC PLAY ERROR] {error_msg}")
        try:
            await ws.send_text(json.dumps({"type": "llm", "emotion": "sad", "text": "😢"}))
            await stream_speech_to_socket(ws, f"Em chưa tìm thấy bài hát {clean_query(target)} trên YouTube bạn nhé!", voice=voice)
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
                    await stream_speech_to_socket(ws, intro_speech, voice=voice, session_id=sess_id)
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

            # 3. Stream các gói audio Opus chuẩn 60ms cho ESP32
            logger.info(f"[MUSIC STREAM] Bắt đầu stream Opus '{title}' tới robot {device_id}...")
            chunk_count = 0
            current_mic_telemetry.update({
                "state": "music_playing",
                "last_reply": f"🎵 {title}",
                "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
            })
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "state_change",
                "state": "music_playing",
                "message": f"🎶 [ĐANG PHÁT NHẠC] '{title}' ({duration_str}) trên loa Robot Megabot"
            }))

            async for chunk in stream_youtube_audio_opus_packets(audio_url, sample_rate=16000):
                await ws.send_bytes(chunk)
                chunk_count += 1
                if chunk_count <= 8:
                    await asyncio.sleep(0.010)
                else:
                    await asyncio.sleep(0.052)

            logger.info(f"[MUSIC STREAM] Hoàn thành stream {chunk_count} gói Opus cho '{title}'.")

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

    try:
        opus_monitor_ctx = av.CodecContext.create("opus", "r")
        opus_monitor_ctx.sample_rate = 16000
        opus_monitor_ctx.layout = "mono"
        opus_monitor_ctx.open()
    except Exception:
        opus_monitor_ctx = None

    current_mic_telemetry.update({
        "state": "idle",
        "device_name": matched_dev.get("name") or "Megabot",
        "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
    })
    asyncio.create_task(broadcast_mic_telemetry({
        "type": "state_change",
        "level_type": "success",
        "state": "connected",
        "message": f"🔗 Robot '{matched_dev.get('name')}' ({device_mac}) đã kết nối WebSocket!"
    }))

    audio_packets: List[bytes] = []
    audio_buffer = bytearray()
    chat_history: List[Dict[str, Any]] = []
    current_utterance_text: Optional[str] = None
    active_process_task: Optional[asyncio.Task] = None

    async def cancel_active_task(reason: str = "ngắt lời"):
        nonlocal active_process_task, silence_timer_task
        if silence_timer_task and not silence_timer_task.done():
            silence_timer_task.cancel()
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
            tts_speed_val = format_tts_speed(cur_cfg.get("voice_speed", "normal"))
            tts_pitch_val = format_tts_pitch(cur_cfg.get("voice_pitch", 0))

            logger.info(f"[CONVERSATION] Xử lý câu hỏi: '{user_prompt}'")
            logger.info(f"               - Robot: {cur_cfg.get('name')} | Voice: {voice_code} | Speed: {tts_speed_val} | Pitch: {tts_pitch_val}")

            # 1. Phản hồi STT cho ESP32 hiển thị
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "stt",
                    "text": user_prompt,
                })
            )

            # --- KIỂM TRA LỆNH ĐIỀU KHIỂN NHẠC BẰNG GIỌNG NÓI ---
            music_intent = extract_music_intent(user_prompt)
            if music_intent:
                if music_intent["action"] == "stop":
                    logger.info(f"[VOICE COMMAND] Nhận lệnh dừng nhạc cho robot {target_device_id}")
                    await stop_youtube_music_on_robot(target_device_id)
                    reply_text = "Đã dừng phát nhạc rồi bạn nhé!"
                    await stream_speech_to_socket(websocket, reply_text, voice=voice_code, session_id=session_id, rate=tts_speed_val, pitch=tts_pitch_val)
                    return
                elif music_intent["action"] == "play":
                    song_search = music_intent.get("song") or clean_query(user_prompt)
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

            play_song_from_llm = None
            stop_music_from_llm = False
            if "[[PLAY_MUSIC:" in reply_text:
                m = re.search(r'\[\[PLAY_MUSIC:\s*(.+?)\]\]', reply_text, flags=re.IGNORECASE)
                if m:
                    play_song_from_llm = m.group(1).strip()
                reply_text = re.sub(r'\[\[PLAY_MUSIC:.*?\]\]', '', reply_text, flags=re.IGNORECASE).strip()
            elif "[[STOP_MUSIC]]" in reply_text:
                stop_music_from_llm = True
                reply_text = re.sub(r'\[\[STOP_MUSIC\]\]', '', reply_text, flags=re.IGNORECASE).strip()

            if use_memory:
                chat_history.append({"role": "user", "text": user_prompt})
                chat_history.append({"role": "model", "text": reply_text})
                if len(chat_history) > 10:
                    chat_history[:] = chat_history[-10:]

            cur_cfg["last_chat"] = datetime.datetime.now().strftime("%H:%M:%S")

            current_mic_telemetry["last_reply"] = reply_text
            current_mic_telemetry["state"] = "speaking"
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "llm_reply",
                "state": "speaking",
                "reply": reply_text,
                "message": f"🤖 [AI PHẢN HỒI] '{reply_text}' (Đang phát ra loa robot)"
            }))

            # 4. Stream trọn vẹn giọng đọc Opus và phụ đề hiển thị xuống robot
            logger.info(f"[STREAMING] Đang phát giọng đọc Opus '{voice_code}' (Speed: {tts_speed_val}, Pitch: {tts_pitch_val})...")
            await stream_speech_to_socket(
                websocket,
                reply_text,
                voice=voice_code,
                session_id=session_id,
                emotion="neutral",
                rate=tts_speed_val,
                pitch=tts_pitch_val,
            )

            # Nếu có yêu cầu phát nhạc từ LLM, kích hoạt sau khi đã nói xong câu xác nhận
            if play_song_from_llm:
                logger.info(f"[LLM MUSIC TRIGGER] Bắt đầu phát bài '{play_song_from_llm}' theo phản hồi của AI")
                await play_youtube_music_on_robot(
                    device_id=target_device_id,
                    query_or_url=play_song_from_llm,
                    session_id=session_id,
                    announce=False
                )
                return
            elif stop_music_from_llm:
                await stop_youtube_music_on_robot(target_device_id)

            current_mic_telemetry["state"] = "idle"
            current_mic_telemetry["peak"] = 0
            current_mic_telemetry["level"] = 0.0
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "state_change",
                "state": "idle",
                "message": "🟢 [HOÀN TẤT] Robot đã hoàn thành câu nói và trở về trạng thái chờ."
            }))


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

    silence_timer_task: Optional[asyncio.Task] = None

    async def trigger_voice_processing(reason: str = "im lặng"):
        nonlocal current_utterance_text, active_process_task
        if silence_timer_task and not silence_timer_task.done():
            silence_timer_task.cancel()
        if len(audio_packets) < 5 and len(audio_buffer) < 500:
            return
        logger.info(f"[PROCESS AUDIO] Bắt đầu xử lý {len(audio_packets)} gói audio (lý do: {reason})...")
        pkts = list(audio_packets)
        total_bytes = len(audio_buffer)
        audio_packets.clear()
        audio_buffer.clear()

        current_mic_telemetry.update({
            "state": "processing",
            "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
        })
        asyncio.create_task(broadcast_mic_telemetry({
            "type": "state_change",
            "level_type": "warning",
            "state": "processing",
            "message": f"⏳ [DỪNG THU ÂM] Đã nhận {len(pkts)} gói ({len(pkts)*60}ms, {total_bytes} bytes, lý do: {reason}) -> Đang gọi STT Gemini..."
        }))

        # Kiểm tra âm lượng peak của các gói âm thanh để loại bỏ tiếng ồn nền
        max_peak = max([decode_opus_packet_peak(pkt, opus_monitor_ctx) for pkt in pkts] or [0])
        if max_peak < 5500 and not current_utterance_text:
            logger.info(f"[PROCESS AUDIO] Âm thanh dưới ngưỡng giọng nói (peak={max_peak} < 5500) -> Chuyển robot về chế độ chờ.")
            current_mic_telemetry.update({
                "state": "idle",
                "peak": 0,
                "level": 0.0,
                "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
            })
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "state_change",
                "level_type": "info",
                "state": "idle",
                "message": f"💤 [CHẾ ĐỘ CHỜ] Không phát hiện tiếng người (peak={max_peak} < 5500) -> Robot vào chế độ chờ."
            }))
            await websocket.send_text(json.dumps({"type": "system", "command": "idle"}))
            await websocket.send_text(json.dumps({"type": "llm", "emotion": "neutral", "text": "😊"}))
            return

        user_question = current_utterance_text
        current_utterance_text = None
        if not user_question:
            user_question = await transcribe_audio_gemini(pkts)

        if user_question:
            current_mic_telemetry.update({
                "state": "stt_done",
                "last_text": user_question,
                "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
            })
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "stt_result",
                "state": "stt_done",
                "text": user_question,
                "message": f"🗣️ [NHẬN DIỆN GIỌNG NÓI] '{user_question}'"
            }))

            await cancel_active_task(f"Xử lý câu hỏi: {user_question[:30]}")
            active_process_task = asyncio.create_task(handle_conversation(user_question))
        else:
            current_mic_telemetry.update({
                "state": "idle",
                "peak": 0,
                "level": 0.0,
                "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
            })
            logger.info("[PROCESS AUDIO] Không có lời nói nhận diện được -> Đưa robot về chế độ chờ.")
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "state_change",
                "level_type": "info",
                "state": "idle",
                "message": "💤 [CHẾ ĐỘ CHỜ] Không có tín hiệu giao tiếp -> Robot vào chế độ chờ."
            }))
            await websocket.send_text(json.dumps({"type": "system", "command": "idle"}))
            await websocket.send_text(
                json.dumps({
                    "session_id": session_id,
                    "type": "llm",
                    "emotion": "neutral",
                    "text": "😊",
                })
            )
        release_memory()

    async def on_silence_timeout():
        try:
            await asyncio.sleep(1.0)  # Đợi 1.0s im lặng sau gói âm thanh cuối
            await trigger_voice_processing("1.0s im lặng")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[AUTO VAD ERROR] {e}", exc_info=True)

    async def heartbeat_loop():
        try:
            while True:
                await asyncio.sleep(15)
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
                    if isinstance(payload, dict) and await handle_device_ws_message(websocket, payload):
                        continue
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
                            audio_packets.clear()
                            audio_buffer.clear()
                            current_utterance_text = None

                            current_mic_telemetry.update({
                                "state": "recording",
                                "device_name": matched_dev.get("name") or "Megabot",
                                "peak": 0,
                                "level": 0.0,
                                "packet_count": 0,
                                "duration_ms": 0,
                                "bytes_received": 0,
                                "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
                            })
                            asyncio.create_task(broadcast_mic_telemetry({
                                "type": "state_change",
                                "level_type": "info",
                                "state": "recording",
                                "message": f"🎙️ [BẮT ĐẦU THU ÂM] Robot '{matched_dev.get('name') or 'Megabot'}' đang thu âm từ Micro..."
                            }))

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
                            asyncio.create_task(trigger_voice_processing("lệnh stop từ ESP32"))

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
                audio_packets.append(raw_audio)
                audio_buffer.extend(raw_audio)

                pkt_idx = len(audio_packets)
                dur_ms = pkt_idx * 60

                # Tiết kiệm RAM/CPU: Chỉ tính toán và cập nhật VU-meter 4 lần/giây (mỗi 4 gói ~240ms)
                # và chỉ khi có người đang mở web theo dõi
                if web_mic_monitors and (pkt_idx % 4 == 1):
                    peak = decode_opus_packet_peak(raw_audio, opus_monitor_ctx)
                    level_pct = round(min(1.0, peak / 32767.0), 3)

                    current_mic_telemetry.update({
                        "state": "recording",
                        "device_name": matched_dev.get("name") or "Megabot",
                        "peak": peak,
                        "level": level_pct,
                        "packet_count": pkt_idx,
                        "duration_ms": dur_ms,
                        "bytes_received": len(audio_buffer),
                        "updated_at": datetime.datetime.now().strftime("%H:%M:%S")
                    })

                    asyncio.create_task(broadcast_mic_telemetry({
                        "type": "audio_packet",
                        "state": "recording",
                        "packet_index": pkt_idx,
                        "packet_size": len(raw_audio),
                        "peak": peak,
                        "level": level_pct,
                        "duration_ms": dur_ms,
                        "total_bytes": len(audio_buffer),
                        "message": f"📊 Gói #{pkt_idx:02d} ({len(raw_audio)}B) | Peak: {peak:5d} ({int(level_pct*100)}%) | {dur_ms}ms"
                    }))

                if len(audio_packets) >= 80:
                    asyncio.create_task(trigger_voice_processing("đạt giới hạn thời gian 5s"))
                else:
                    if silence_timer_task and not silence_timer_task.done():
                        silence_timer_task.cancel()
                    silence_timer_task = asyncio.create_task(on_silence_timeout())

            elif message.get("type") == "websocket.disconnect":
                break

    except WebSocketDisconnect as e:
        logger.warning(f"[DISCONNECT] ESP32 ngắt kết nối (code: {e.code})")
    except Exception as e:
        logger.error(f"[ERROR] Ngoại lệ WebSocket: {e}", exc_info=True)
    finally:
        if silence_timer_task and not silence_timer_task.done():
            silence_timer_task.cancel()
        heartbeat_task.cancel()
        await cancel_active_task("Đóng kết nối")
        if active_websockets.get(target_device_id) == websocket:
            active_websockets.pop(target_device_id, None)
        if active_websockets.get(device_mac) == websocket:
            active_websockets.pop(device_mac, None)
        if device_mac and isinstance(device_mac, str) and active_websockets.get(device_mac.lower()) == websocket:
            active_websockets.pop(device_mac.lower(), None)
        if active_websockets.get(pin_code) == websocket:
            active_websockets.pop(pin_code, None)
        # Chỉ đánh dấu offline nếu robot không còn bất kỳ socket nào hoạt động
        if not any(ws != websocket for ws in active_websockets.values()):
            matched_dev["is_online"] = False
            device_manager.save_data()
            current_mic_telemetry.update({
                "state": "disconnected",
                "peak": 0,
                "level": 0.0,
            })
            asyncio.create_task(broadcast_mic_telemetry({
                "type": "state_change",
                "level_type": "error",
                "state": "disconnected",
                "message": f"🔌 [NGẮT KẾT NỐI] Robot '{matched_dev.get('name')}' đã ngắt kết nối WebSocket."
            }))
        if opus_monitor_ctx:
            try:
                opus_monitor_ctx.close()
            except Exception:
                pass
            opus_monitor_ctx = None
        release_memory()
        logger.info(f"[SESSION CLOSED] Phiên {session_id} đã kết thúc.")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"Khởi động Megabot Web Server & WebSocket tại:")
    logger.info(f" 👉 Web Dashboard (Megabot): http://localhost:{PORT}")
    logger.info(f" 👉 WebSocket Endpoint:         ws://localhost:{PORT}/ws/xiaozhi")
    logger.info("=" * 60)
    is_reload = os.getenv("RELOAD", "false").lower() in ("true", "1")
    uvicorn.run("server:app", host=HOST, port=PORT, reload=is_reload)
