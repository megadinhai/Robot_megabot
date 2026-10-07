import asyncio
import datetime
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from audio_handler import text_to_speech_stream, transcribe_audio_gemini
from llm_handler import chat_with_gemini
from devices_manager import device_manager

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
logger = logging.getLogger("XiaozhiServer")

app = FastAPI(title="Xiaozhi Robot Control Server (xiaozhi.me clone)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))

# Lưu trữ các WebSocket đang hoạt động để gửi lệnh điều khiển robot
active_websockets: Dict[str, WebSocket] = {}


# ==========================================
# GIAO DIỆN WEB DASHBOARD (XIAOZHI.ME CLONE)
# ==========================================

@app.get("/")
@app.get("/dashboard")
async def dashboard_page():
    """Phục vụ giao diện Bảng điều khiển Xiaozhi chuẩn theo ảnh chụp xiaozhi.me."""
    html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"status": "online", "message": "Dashboard HTML not found"})


@app.get("/test")
async def test_page():
    """Giao diện debug chat websocket cũ."""
    html_path = os.path.join(os.path.dirname(__file__), "test_client.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"error": "test_client.html not found"})


# ==========================================
# REST APIS QUẢN LÝ THIẾT BỊ & CẤU HÌNH
# ==========================================

@app.get("/api/devices")
async def list_devices():
    """Danh sách thiết bị robot."""
    devices = device_manager.get_all_devices()
    for dev in devices:
        dev_id = dev.get("id")
        last_seen = dev.get("last_seen_ts", 0)
        recently_active = (time.time() - last_seen) < 300
        dev["is_online"] = dev_id in active_websockets or recently_active
    return JSONResponse(devices)


@app.post("/api/devices")
async def create_device(req: Request):
    """Tạo thiết bị robot mới."""
    data = await req.json()
    new_dev = device_manager.add_device(data)
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
# REST APIS ĐIỀU KHIỂN ROBOT TRỰC TIẾP & TEST CHAT
# ==========================================

@app.post("/api/robot/control")
async def control_robot(req: Request):
    """Gửi lệnh di chuyển / biểu cảm / đèn LED xuống robot qua WebSocket MCP."""
    data = await req.json()
    device_id = data.get("device_id")
    action = data.get("action", "stop")

    # Tìm websocket kết nối
    ws = active_websockets.get(device_id) or next(iter(active_websockets.values()), None)
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
        "method": "tools/call",
        "params": tool_call,
    }

    try:
        await ws.send_text(json.dumps(payload))
        logger.info(f"[ROBOT CONTROL] Đã gửi lệnh '{action}' tới ESP32")
        return JSONResponse({"status": "ok", "action": action})
    except Exception as e:
        logger.error(f"[ROBOT CONTROL ERROR] {e}")
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
    return JSONResponse({"reply": reply})


# ==========================================
# WEBSOCKET CHÍNH KẾT NỐI VỚI ESP32 (XIAOZHI PROTOCOL)
# ==========================================

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

    # Xác định hồ sơ cấu hình robot đang kết nối
    matched_dev = device_manager.get_device(device_mac) or device_manager.get_default_device()
    target_device_id = matched_dev.get("id", "ong-robot")
    active_websockets[target_device_id] = websocket
    matched_dev["is_online"] = True
    matched_dev["device_mac"] = device_mac
    matched_dev["last_seen_ts"] = time.time()
    matched_dev["last_chat"] = "Vừa xong"

    logger.info("=" * 60)
    logger.info(f"[CONNECT] Thiết bị kết nối từ {client_host}:{client_port}")
    logger.info(f"          - Hồ sơ Robot: '{matched_dev.get('name')}' (ID: {target_device_id})")
    logger.info(f"          - Device-MAC: {device_mac} | Session: {session_id}")
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
            model_id = cur_cfg.get("model_id", "gemini-2.5-flash")
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
        await cancel_active_task("Đóng kết nối")
        active_websockets.pop(target_device_id, None)
        matched_dev["is_online"] = False
        logger.info(f"[SESSION CLOSED] Phiên {session_id} đã kết thúc.")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"Khởi động Xiaozhi Web Server & WebSocket tại:")
    logger.info(f" 👉 Web Dashboard (xiaozhi.me): http://localhost:{PORT}")
    logger.info(f" 👉 WebSocket Endpoint:         ws://localhost:{PORT}/ws/xiaozhi")
    logger.info("=" * 60)
    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
