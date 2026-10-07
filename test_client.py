import asyncio
import inspect
import json
import sys
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WS_URL = "ws://127.0.0.1:8000/ws/xiaozhi"


async def simulate_esp32_full_loop():
    print(f"[TEST CLIENT] Đang kết nối tới {WS_URL}...")
    headers = {
        "Device-Id": "24:DC:C3:AA:BB:CC",
        "Client-Id": "esp32-test-client-uuid",
        "Protocol-Version": "1",
    }

    connect_kwargs = {}
    sig = inspect.signature(websockets.connect)
    if "additional_headers" in sig.parameters:
        connect_kwargs["additional_headers"] = headers
    else:
        connect_kwargs["extra_headers"] = headers

    try:
        async with websockets.connect(WS_URL, **connect_kwargs) as ws:
            print("[TEST CLIENT] Kết nối thành công!")

            # 1. Bắt tay Hello
            hello_msg = {
                "type": "hello",
                "version": 1,
                "transport": "websocket",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": 16000,
                    "channels": 1,
                    "frame_duration": 60,
                },
            }
            await ws.send(json.dumps(hello_msg))
            resp = await ws.recv()
            print(f"[TEST CLIENT] Nhận phản hồi Hello ACK: {resp}\n")

            # ----------------------------------------------------
            # KỊCH BẢN 1: Hỏi đáp hoàn chỉnh (Full Loop)
            # ----------------------------------------------------
            question = "Hôm nay thời tiết đẹp quá, bạn có khỏe không?"
            print(f"=== KỊCH BẢN 1: Hỏi câu '{question}' ===")

            # Báo robot bắt đầu nói
            await ws.send(json.dumps({"type": "listen", "state": "start"}))
            # Báo robot nói xong kèm nội dung câu hỏi
            await ws.send(json.dumps({"type": "listen", "state": "stop", "text": question}))

            audio_chunks_received = 0
            audio_bytes_total = 0

            # Lắng nghe toàn bộ phản hồi từ Server
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    if msg_type == "stt":
                        print(f"  [MÀN HÌNH] Nhận diện câu nói: '{data.get('text')}'")
                    elif msg_type == "llm":
                        print(f"  [BIỂU CẢM] {data.get('emotion')} -> {data.get('text')}")
                    elif msg_type == "tts":
                        state = data.get("state")
                        if state == "start":
                            print("  [LOA] Server bắt đầu phát âm thanh...")
                        elif state == "sentence_start":
                            print(f"  [PHỤ ĐỀ] Robot nói: \"{data.get('text')}\"")
                        elif state == "stop":
                            print("  [LOA] Server kết thúc phát âm thanh.")
                            break
                elif isinstance(msg, bytes):
                    audio_chunks_received += 1
                    audio_bytes_total += len(msg)

            print(f"  -> Nhận tổng cộng: {audio_chunks_received} gói audio ({audio_bytes_total/1024:.2f} KB)\n")

            # ----------------------------------------------------
            # KỊCH BẢN 2: Kiểm tra cơ chế ngắt lời (Barge-in / Abort)
            # ----------------------------------------------------
            print("=== KỊCH BẢN 2: Thử nghiệm ngắt lời khi robot đang nói ===")
            question2 = "Kể cho tôi nghe một câu chuyện dài nhé!"
            await ws.send(json.dumps({"type": "listen", "state": "start"}))
            await ws.send(json.dumps({"type": "listen", "state": "stop", "text": question2}))

            interrupted = False
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    if msg_type == "llm":
                        print(f"  [BIỂU CẢM] {data.get('emotion')} -> {data.get('text')}")
                    elif msg_type == "tts" and data.get("state") == "sentence_start":
                        print(f"  [PHỤ ĐỀ] Robot bắt đầu nói: \"{data.get('text')[:30]}...\"")
                    elif msg_type == "tts" and data.get("state") == "stop":
                        if interrupted:
                            print("  [NGẮT LỜI THÀNH CÔNG] Server đã dừng phát audio ngay khi nhận abort!")
                            break
                elif isinstance(msg, bytes) and not interrupted:
                    # Ngay khi nhận được gói audio đầu tiên, gửi lệnh abort ngắt lời lập tức
                    print("  -> Đang nhận audio... Gửi ngay lệnh ABORT (ngắt lời)!")
                    await ws.send(json.dumps({"type": "abort", "reason": "user_interrupted"}))
                    interrupted = True

            print("\n[TEST CLIENT] Đã hoàn thành toàn bộ kịch bản kiểm thử thành công!")

    except (ConnectionRefusedError, OSError):
        print("[LỖI] Không thể kết nối. Hãy chắc chắn 'python server.py' đang chạy!")
    except Exception as e:
        print(f"[LỖI] {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(simulate_esp32_full_loop())
