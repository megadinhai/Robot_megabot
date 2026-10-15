import array
import asyncio
import io
import logging
import os
import sys
import wave
from typing import Any, AsyncGenerator, List, Optional, Union
import edge_tts
from dotenv import load_dotenv
import av

# Thiết lập UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

logger = logging.getLogger("AudioHandler")

# 1. Cấu hình giọng đọc tiếng Việt của Edge-TTS
# Lựa chọn phổ biến:
# - 'vi-VN-HoaiMyNeural': Giọng nữ miền Bắc, truyền cảm, tự nhiên
# - 'vi-VN-NamMinhNeural': Giọng nam miền Bắc, trầm ấm
DEFAULT_VOICE = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")

def format_tts_speed(speed: Any) -> str:
    if speed == "slow":
        return "-15%"
    elif speed == "fast":
        return "+30%"
    return "+15%"

def format_tts_pitch(pitch: Any) -> str:
    try:
        p = int(pitch)
        hz = p * 15
        return f"{hz:+d}Hz"
    except Exception:
        return "+0Hz"


# 2. Chuyển đổi văn bản thành luồng gói âm thanh chuẩn Opus (16kHz mono 60ms) cho XiaoZhi ESP32
async def text_to_speech_opus_stream(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+15%",
    pitch: str = "+0Hz",
    sample_rate: int = 16000,
    frame_duration_ms: int = 60,
) -> AsyncGenerator[bytes, None]:
    """
    Chuyển văn bản thành audio bằng Edge-TTS, sau đó mã hóa sang từng frame Opus
    (16kHz, Mono, 60ms = 960 mẫu/frame) khớp chuẩn 100% với AudioService::PushPacketToDecodeQueue
    của firmware XiaoZhi trên ESP32-S3.
    """
    if not text or not text.strip():
        return

    logger.info(f"[TTS OPUS] Bắt đầu tổng hợp giọng nói: '{text[:50]}...' (Voice: {voice}, Rate: {rate}, Pitch: {pitch})")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    mp3_stream = io.BytesIO()

    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_stream.write(chunk["data"])
    except Exception as e:
        logger.error(f"[TTS ERROR] Lỗi khi tải luồng Edge-TTS: {e}")
        return

    mp3_bytes = mp3_stream.getvalue()
    if not mp3_bytes:
        logger.warning("[TTS OPUS] Không có dữ liệu audio MP3 từ Edge-TTS")
        return

    # Frame size tính theo mẫu PCM: 16000 Hz * 0.060s = 960 mẫu
    samples_per_frame = int(sample_rate * (frame_duration_ms / 1000.0))

    input_container = None
    out_container = None
    try:
        input_container = av.open(io.BytesIO(mp3_bytes), format="mp3")
        in_stream = input_container.streams.audio[0]

        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)

        out_container = av.open(io.BytesIO(), mode="w", format="opus")
        out_stream = out_container.add_stream("opus", rate=sample_rate, layout="mono")
        out_stream.bit_rate = 32000

        fifo = av.AudioFifo()

        for frame in input_container.decode(in_stream):
            for rf in resampler.resample(frame):
                fifo.write(rf)
                while fifo.samples >= samples_per_frame:
                    chunk_frame = fifo.read(samples_per_frame)
                    for packet in out_stream.encode(chunk_frame):
                        yield bytes(packet)

        # Xử lý phần mẫu còn lại trong buffer
        if fifo.samples > 0:
            chunk_frame = fifo.read(fifo.samples)
            for packet in out_stream.encode(chunk_frame):
                yield bytes(packet)

        # Xả toàn bộ encoder
        for packet in out_stream.encode(None):
            yield bytes(packet)

    except Exception as e:
        logger.error(f"[TTS OPUS ENCODE ERROR] Lỗi transcode MP3 sang Opus: {e}", exc_info=True)
    finally:
        if out_container:
            try:
                out_container.close()
            except Exception:
                pass
        if input_container:
            try:
                input_container.close()
            except Exception:
                pass
        import gc
        gc.collect()


async def stream_speech_to_socket(
    ws,
    text: str,
    voice: str = DEFAULT_VOICE,
    session_id: str = "",
    emotion: str = "happy",
    rate: str = "+15%",
    pitch: str = "+0Hz",
) -> int:
    """
    Gửi trọn vẹn một phiên hội thoại/giọng nói xuống Robot ESP32 qua WebSocket:
    1. Gửi lệnh TTS start (đưa robot vào kDeviceStateSpeaking)
    2. Gửi sentence_start (hiển thị phụ đề lên OLED)
    3. Gửi emotion speaking
    4. Gửi các gói Opus với nhịp độ nhịp nhàng (pacing 55ms) tránh tràn buffer 20 gói
    5. Đợi 0.5s cho loa phát hết và gửi TTS stop
    """
    import json
    if not ws:
        return 0

    base_payload = {"session_id": session_id} if session_id else {}

    try:
        # 1. Bật trạng thái Speaking trên ESP32
        start_msg = {**base_payload, "type": "tts", "state": "start"}
        await ws.send_text(json.dumps(start_msg))

        # 2. Phụ đề trên OLED
        sub_msg = {**base_payload, "type": "tts", "state": "sentence_start", "text": text}
        await ws.send_text(json.dumps(sub_msg))

        # 3. Biểu cảm nói
        emo_msg = {**base_payload, "type": "llm", "emotion": "speaking", "text": "🗣️"}
        await ws.send_text(json.dumps(emo_msg))

        # 4. Stream từng gói Opus với pacing chuẩn 55ms
        pkt_count = 0
        async for pkt in text_to_speech_opus_stream(text, voice=voice, rate=rate, pitch=pitch):
            await ws.send_bytes(pkt)
            pkt_count += 1
            if pkt_count <= 8:
                # 8 gói đầu nạp nhanh vào buffer (khoảng 480ms âm thanh) tránh gián đoạn loa
                await asyncio.sleep(0.005)
            else:
                # Các gói tiếp theo gửi đều đặn nhịp 58ms (mỗi gói Opus chuẩn là 60ms)
                await asyncio.sleep(0.058)

        logger.info(f"[STREAM SPEECH] Đã gửi {pkt_count} gói Opus cho câu nói '{text[:30]}...'")

        # 5. Đợi hàng đợi phát âm thanh trên ESP32 xả hết
        await asyncio.sleep(0.5)

        # 6. Kết thúc phiên nói và đưa robot về chế độ chờ (Idle/Standby)
        stop_msg = {**base_payload, "type": "tts", "state": "stop", "next": "idle"}
        await ws.send_text(json.dumps(stop_msg))

        neutral_msg = {**base_payload, "type": "llm", "emotion": emotion or "neutral", "text": "😊"}
        await ws.send_text(json.dumps(neutral_msg))

        idle_msg = {"type": "system", "command": "idle"}
        await ws.send_text(json.dumps(idle_msg))

        return pkt_count
    except Exception as e:
        logger.error(f"[STREAM SPEECH ERROR] {e}", exc_info=True)
        return 0


# 3. Giải mã các gói Opus từ Micro Robot ESP32 thành chuẩn WAV
def decode_opus_packets_to_wav(packets: List[bytes], sample_rate: int = 16000) -> bytes:
    """
    Nhận danh sách các gói nhị phân Opus gửi từ micro ESP32,
    giải mã bằng PyAV và xuất ra tệp RIFF WAV 16kHz Mono 16-bit PCM.
    """
    if not packets:
        return b""

    dec_ctx = None
    try:
        dec_ctx = av.CodecContext.create("opus", "r")
        dec_ctx.sample_rate = sample_rate
        dec_ctx.layout = "mono"
        dec_ctx.open()

        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)
        wav_io = io.BytesIO()

        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            for pkt_bytes in packets:
                if not pkt_bytes or len(pkt_bytes) < 3:
                    continue
                try:
                    pkt = av.Packet(pkt_bytes)
                    for frame in dec_ctx.decode(pkt):
                        for rf in resampler.resample(frame):
                            wf.writeframes(bytes(rf.planes[0]))
                except Exception as frame_err:
                    logger.debug(f"[OPUS DECODE FRAME] Bỏ qua gói lỗi: {frame_err}")

        wav_bytes = wav_io.getvalue()
        logger.info(f"[OPUS TO WAV] Đã chuyển {len(packets)} gói Opus thành {len(wav_bytes)} bytes WAV")
        return wav_bytes
    except Exception as e:
        logger.error(f"[OPUS TO WAV ERROR] Lỗi giải mã: {e}", exc_info=True)
        return b""
    finally:
        if dec_ctx:
            try:
                dec_ctx.close()
            except Exception:
                pass


def decode_opus_packet_peak(pkt_bytes: bytes, dec_ctx=None) -> int:
    """
    Giải mã nhanh 1 gói Opus thô và lấy biên độ đỉnh (peak 0 - 32767).
    """
    if not pkt_bytes or len(pkt_bytes) < 4:
        return 0
    created_ctx = False
    try:
        if dec_ctx is None:
            dec_ctx = av.CodecContext.create("opus", "r")
            dec_ctx.sample_rate = 16000
            dec_ctx.layout = "mono"
            dec_ctx.open()
            created_ctx = True
        pkt = av.Packet(pkt_bytes)
        peak = 0
        for frame in dec_ctx.decode(pkt):
            pcm = array.array('h', bytes(frame.planes[0]))
            if pcm:
                fpeak = max(abs(s) for s in pcm)
                if fpeak > peak:
                    peak = fpeak
        return peak
    except Exception:
        return 0
    finally:
        if created_ctx and dec_ctx:
            try:
                dec_ctx.close()
            except Exception:
                pass


# 4. Nhận diện giọng nói Speech-to-Text (STT) thông qua Gemini API
async def transcribe_audio_gemini(
    audio_input: Union[bytes, List[bytes]],
    mime_type: str = "audio/wav",
    api_key: Optional[str] = None,
) -> str:
    """
    Nhận diện giọng nói tiếng Việt từ dữ liệu audio (gói Opus hoặc WAV/MP3 bytes)
    thông qua Gemini Multimodal Audio API.
    """
    try:
        from google.genai import types
        from llm_handler import get_genai_client

        if isinstance(audio_input, list):
            # Nếu là danh sách các gói Opus thô từ WebSocket ESP32
            if len(audio_input) < 6:
                # Quá ngắn (< 360ms), thường là tiếng ồn hoặc vô tình bấm nút
                logger.info(f"[STT] Dữ liệu audio quá ngắn ({len(audio_input)} gói), bỏ qua STT.")
                return ""

            # Kiểm tra âm lượng đỉnh (peak) với 1 context duy nhất để tránh leak RAM
            max_peak = 0
            temp_dec = None
            try:
                temp_dec = av.CodecContext.create("opus", "r")
                temp_dec.sample_rate = 16000
                temp_dec.layout = "mono"
                temp_dec.open()
                for pkt in audio_input:
                    p = decode_opus_packet_peak(pkt, temp_dec)
                    if p > max_peak:
                        max_peak = p
            except Exception:
                pass
            finally:
                if temp_dec:
                    try:
                        temp_dec.close()
                    except Exception:
                        pass

            if max_peak < 1000:
                logger.info(f"[STT] Âm thanh dưới ngưỡng phát hiện (peak={max_peak} < 1000) -> Không có người nói, bỏ qua STT.")
                return ""

            audio_bytes = decode_opus_packets_to_wav(audio_input)
            mime_type = "audio/wav"
        else:
            audio_bytes = audio_input
            if audio_bytes.startswith(b"RIFF"):
                mime_type = "audio/wav"
            elif audio_bytes.startswith(b"ID3") or audio_bytes.startswith(b"\xff\xfb"):
                mime_type = "audio/mp3"
            elif audio_bytes.startswith(b"OggS"):
                mime_type = "audio/ogg"

        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        effective_key = api_key or os.getenv("GEMINI_API_KEY")
        client = get_genai_client(api_key=effective_key)
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = (
            "Hãy lắng nghe đoạn âm thanh này và chép lại nội dung lời nói bằng tiếng Việt. "
            "QUAN TRỌNG: Nếu đoạn âm thanh chỉ có tiếng ồn, tiếng thở, tiếng xì xào nền, không có người nói rõ ràng hoặc im lặng, hãy trả về đúng từ: [EMPTY]. "
            "Chỉ trả về văn bản được nói, không thêm lời dẫn giải hay ký hiệu khác."
        )

        candidate_stt_models = [
            os.getenv("GEMINI_STT_MODEL", "gemini-3.1-flash-lite-preview"),
            "gemini-3.1-flash-lite-preview",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
        ]

        result_text = ""
        seen_models = set()
        for m in candidate_stt_models:
            if not m or m in seen_models:
                continue
            seen_models.add(m)
            try:
                logger.info(f"[STT Gemini] Thử nhận dạng bằng model '{m}'...")
                response = await client.aio.models.generate_content(
                    model=m,
                    contents=[audio_part, prompt],
                )
                if response and response.text:
                    result_text = response.text.strip()
                    break
            except Exception as model_err:
                logger.warning(f"[STT Gemini] Model '{m}' gặp lỗi: {model_err}")

        if result_text.upper() in ["[EMPTY]", "EMPTY", "...", ".", "KHÔNG CÓ", "NONE", "IM LẶNG"]:
            logger.info("[STT Gemini] Âm thanh không chứa lời nói ([EMPTY]).")
            return ""

        logger.info(f"[STT Gemini] Kết quả nhận dạng: '{result_text}'")
        return result_text

    except Exception as e:
        logger.error(f"[STT ERROR] Lỗi nhận diện âm thanh qua Gemini: {e}", exc_info=True)
        return ""
    finally:
        import gc
        gc.collect()


# Giữ lại các hàm cũ cho tương thích ngược
async def text_to_speech_stream(
    text: str,
    voice: str = DEFAULT_VOICE,
    chunk_size: int = 1024,
) -> AsyncGenerator[bytes, None]:
    """Hàm phát sinh MP3 chunks (tương thích ngược)."""
    if not text or not text.strip():
        return
    communicate = edge_tts.Communicate(text=text, voice=voice)
    buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.extend(chunk["data"])
            while len(buffer) >= chunk_size:
                yield bytes(buffer[:chunk_size])
                del buffer[:chunk_size]
    if len(buffer) > 0:
        yield bytes(buffer)


async def text_to_speech_bytes(
    text: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Chuyển văn bản thành 1 khối bytes MP3."""
    communicate = edge_tts.Communicate(text=text, voice=voice)
    audio_stream = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])
    return audio_stream.getvalue()
