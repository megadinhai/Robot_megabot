import logging
import os
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Thiết lập UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

logger = logging.getLogger("LLMHandler")

# 1. Đọc API Key và cấu hình model từ .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = "gemini-3.5-flash-lite"

# 2. System Prompt định hình tính cách cho robot Xiaozhi
SYSTEM_INSTRUCTION = """Bạn là trợ lý robot thông minh Xiaozhi (Tiểu Trí) trên phần cứng ESP32.
Nhiệm vụ của bạn là trò chuyện với người dùng bằng giọng nói qua micro và loa.

Quy tắc phản hồi bắt buộc:
1. Luôn trả lời bằng tiếng Việt tự nhiên, thân thiện, lễ phép và thông minh.
2. Vì câu trả lời sẽ được chuyển thành giọng nói (TTS) để phát qua loa robot, bạn PHẢI trả lời ngắn gọn, súc tích (tối đa 2 đến 3 câu).
3. Tuyệt đối KHÔNG dùng các ký tự định dạng markdown như **, *, #, gạch đầu dòng, bảng biểu hay emoji vì loa robot không đọc được các ký tự này.
4. Xưng hô tự nhiên, thân thiện: xưng là 'em' hoặc 'Xiaozhi', gọi người dùng là 'bạn' hoặc 'anh/chị'.
"""

# Khởi tạo GenAI Client
_client: Optional[genai.Client] = None


def get_genai_client() -> genai.Client:
    """Khởi tạo hoặc lấy client Google GenAI."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            logger.warning(
                "GEMINI_API_KEY chưa được thiết lập hợp lệ trong file .env. "
                "Vui lòng cập nhật API key để sử dụng tính năng AI."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY or "dummy_key")
    return _client


async def chat_with_gemini(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    """
    Gửi tin nhắn của người dùng và lịch sử hội thoại tới Gemini Flash.

    Args:
        user_text: Câu nói/văn bản người dùng vừa nói.
        chat_history: Danh sách các tin nhắn trước đó.
        system_instruction: Lời nhắc hệ thống tùy chỉnh từ cấu hình thiết bị.
        model_override: Mã mô hình AI cụ thể (nếu có).

    Returns:
        Câu trả lời ngắn gọn (2-3 câu) từ Gemini.
    """
    if not user_text or not user_text.strip():
        return ""

    client = get_genai_client()

    # Chuẩn bị danh sách nội dung hội thoại theo chuẩn SDK mới
    contents: List[types.Content] = []

    if chat_history:
        for item in chat_history:
            if isinstance(item, types.Content):
                contents.append(item)
            elif isinstance(item, dict):
                role = item.get("role", "user")
                if role == "assistant":
                    role = "model"
                text = item.get("text") or item.get("content", "")
                if text:
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=str(text))],
                        )
                    )

    # Thêm câu nói hiện tại của người dùng
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_text.strip())],
        )
    )

    # Sử dụng system instruction tùy chỉnh hoặc mặc định
    active_system_instruction = system_instruction.strip() if system_instruction and system_instruction.strip() else SYSTEM_INSTRUCTION

    # Cấu hình gọi model với System Instruction, tắt suy nghĩ thừa để tối ưu tốc độ và tránh bị cắt câu
    config = types.GenerateContentConfig(
        system_instruction=active_system_instruction,
        temperature=0.7,
        max_output_tokens=300,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Thử model chính, nếu 503 (quá tải) tự động fallback sang flash-lite
    primary_model = model_override or MODEL_NAME
    models_to_try = [primary_model]
    if FALLBACK_MODEL not in models_to_try:
        models_to_try.append(FALLBACK_MODEL)

    last_error = None
    for model in models_to_try:
        try:
            logger.info(f"[LLM] Đang gửi prompt tới model {model}: '{user_text}'")
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            reply_text = response.text.strip() if response.text else ""
            logger.info(f"[LLM] Phản hồi từ Gemini ({model}): '{reply_text}'")
            return reply_text

        except Exception as e:
            last_error = e
            logger.warning(f"[LLM WARNING] Lỗi khi gọi model {model}: {e}")
            continue

    logger.error(f"[LLM ERROR] Tất cả các model đều thất bại: {last_error}", exc_info=True)
    return "Xin lỗi bạn, em đang gặp sự cố kết nối với máy chủ AI. Bạn hãy thử lại sau nhé!"


# Test nhanh trực tiếp file nếu chạy: python llm_handler.py
if __name__ == "__main__":
    import asyncio

    async def main():
        print("Đang kiểm tra kết nối với Gemini...")
        test_history = [
            {"role": "user", "text": "Chào bạn, bạn là ai?"},
            {"role": "model", "text": "Chào bạn, em là robot Xiaozhi rất vui được trò chuyện cùng bạn!"},
        ]
        test_prompt = "Hôm nay thời tiết đẹp quá, chúng ta nên làm gì nhỉ?"
        reply = await chat_with_gemini(test_prompt, test_history)
        print(f"User: {test_prompt}")
        print(f"Xiaozhi: {reply}")

    asyncio.run(main())
