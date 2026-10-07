import asyncio
import io
import logging
import os
import sys
from typing import AsyncGenerator, Optional
import edge_tts
from dotenv import load_dotenv

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


# 2. Chuyển đổi văn bản thành luồng âm thanh (TTS Stream)
async def text_to_speech_stream(
    text: str,
    voice: str = DEFAULT_VOICE,
    chunk_size: int = 1024,
) -> AsyncGenerator[bytes, None]:
    """
    Chuyển văn bản thành audio MP3 bằng Edge-TTS và cắt thành các chunk nhị phân
    sẵn sàng stream qua WebSocket ngược về ESP32.

    Args:
        text: Nội dung văn bản cần đọc.
        voice: Mã giọng đọc (mặc định vi-VN-HoaiMyNeural).
        chunk_size: Kích thước mỗi gói dữ liệu gửi đi (bytes).

    Yields:
        Các chunk dữ liệu âm thanh dạng bytes.
    """
    if not text or not text.strip():
        return

    logger.info(f"[TTS] Bắt đầu tổng hợp giọng nói: '{text[:50]}...' (Voice: {voice})")
    communicate = edge_tts.Communicate(text=text, voice=voice)

    buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.extend(chunk["data"])
            # Chia nhỏ buffer thành các chunk theo kích thước chunk_size
            while len(buffer) >= chunk_size:
                yield bytes(buffer[:chunk_size])
                del buffer[:chunk_size]

    # Gửi phần dữ liệu còn lại trong buffer nếu có
    if len(buffer) > 0:
        yield bytes(buffer)

    logger.info(f"[TTS] Đã hoàn thành stream audio cho text: '{text[:30]}...'")


async def text_to_speech_bytes(
    text: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """
    Chuyển toàn bộ văn bản thành 1 khối bytes audio MP3 hoàn chỉnh.
    """
    communicate = edge_tts.Communicate(text=text, voice=voice)
    audio_stream = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])
    return audio_stream.getvalue()


# 3. Gợi ý & Xử lý Speech-to-Text (STT): Chuyển âm thanh từ micro ESP32 thành văn bản
#
# Cách 1 (Khuyên dùng - Đơn giản nhất): Sử dụng Gemini Multimodal Audio API
#   Ưu điểm: Không cần tải model hàng GB, chạy trực tiếp trên cloud cực nhanh,
#            sử dụng chung API Key Gemini đã cấu hình sẵn.
async def transcribe_audio_gemini(
    audio_bytes: bytes,
    mime_type: str = "audio/wav",  # hoặc "audio/mp3", "audio/ogg"
) -> str:
    """
    Nhận diện giọng nói từ dữ liệu audio thô thông qua Gemini Audio API.
    """
    try:
        from google.genai import types
        from llm_handler import get_genai_client

        client = get_genai_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = "Hãy lắng nghe đoạn âm thanh này và gõ lại nội dung lời nói bằng tiếng Việt chính xác. Chỉ trả về văn bản được nói, không thêm lời dẫn giải."

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=[audio_part, prompt],
        )

        result_text = response.text.strip() if response.text else ""
        logger.info(f"[STT Gemini] Kết quả nhận dạng: '{result_text}'")
        return result_text

    except Exception as e:
        logger.error(f"[STT ERROR] Lỗi nhận diện âm thanh qua Gemini: {e}", exc_info=True)
        return ""


# Cách 2: Sử dụng Faster-Whisper (Offline tại local)
#   Yêu cầu cài đặt thêm: pip install faster-whisper
#   Thích hợp khi: Muốn xử lý hoàn toàn offline không phụ thuộc internet.
def transcribe_audio_faster_whisper(audio_file_path: str, model_size: str = "base") -> str:
    """
    Ví dụ sử dụng Faster-Whisper để chuyển đổi audio file thành văn bản offline.
    """
    try:
        from faster_whisper import WhisperModel

        # Chạy trên CPU với định dạng int8 để nhẹ RAM
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_file_path, language="vi")
        text = " ".join([segment.text for segment in segments]).strip()
        return text
    except ImportError:
        logger.warning("Chưa cài đặt 'faster-whisper'. Cài đặt bằng: pip install faster-whisper")
        return ""
    except Exception as e:
        logger.error(f"[Whisper ERROR] {e}")
        return ""


# Kiểm tra chạy thử độc lập file audio_handler.py
if __name__ == "__main__":
    async def main():
        test_text = "Chào bạn! Tôi là Tiểu Trí, hệ thống âm thanh đã sẵn sàng."
        print(f"Đang tạo audio thử nghiệm cho câu: '{test_text}'...")

        chunk_count = 0
        total_size = 0
        async for chunk in text_to_speech_stream(test_text, chunk_size=1024):
            chunk_count += 1
            total_size += len(chunk)

        print(f"Tổng hợp thành công! Tổng số chunks: {chunk_count}, Tổng dung lượng: {total_size} bytes ({total_size/1024:.2f} KB)")

        # Lưu thử ra file mp3 để nghe kiểm tra nếu muốn
        output_file = "test_output.mp3"
        full_audio = await text_to_speech_bytes(test_text)
        with open(output_file, "wb") as f:
            f.write(full_audio)
        print(f"Đã lưu file âm thanh mẫu: {output_file}")

    asyncio.run(main())
