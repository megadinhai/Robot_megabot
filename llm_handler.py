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
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = "gemini-2.5-flash-lite"

# 2. System Prompt định hình tính cách cho robot Xiaozhi
SYSTEM_INSTRUCTION = """Bạn là trợ lý robot thông minh Xiaozhi (Tiểu Trí) trên phần cứng ESP32.
Nhiệm vụ của bạn là trò chuyện với người dùng bằng giọng nói qua micro và loa.

Quy tắc phản hồi bắt buộc:
1. Luôn trả lời bằng tiếng Việt tự nhiên, thân thiện, lễ phép và thông minh.
2. Vì câu trả lời sẽ được chuyển thành giọng nói (TTS) để phát qua loa robot, bạn PHẢI trả lời ngắn gọn, súc tích (tối đa 2 đến 3 câu).
3. Tuyệt đối KHÔNG dùng các ký tự định dạng markdown như **, *, #, gạch đầu dòng, bảng biểu hay emoji vì loa robot không đọc được các ký tự này.
4. Xưng hô tự nhiên, thân thiện: xưng là 'em' hoặc 'Xiaozhi', gọi người dùng là 'bạn' hoặc 'anh/chị'.
"""

def get_quick_smart_reply(prompt: str) -> str:
    """Tạo câu trả lời thông minh nhanh nếu kết nối Gemini AI gặp sự cố."""
    p = prompt.lower().strip()
    if any(w in p for w in ["chào", "hello", "hi"]):
        return "Chào bạn! Em là robot Xiaozhi rất vui được trò chuyện cùng bạn. Hôm nay bạn thế nào?"
    if any(w in p for w in ["bạn là ai", "tên gì", "giới thiệu"]):
        return "Em là trợ lý robot AI Xiaozhi chạy trên vi điều khiển ESP32, sẵn sàng lắng nghe và trả lời bạn!"
    if any(w in p for w in ["khỏe không", "thế nào", "ổn không"]):
        return "Em khỏe lắm, luôn đầy năng lượng và sẵn sàng giúp đỡ bạn bất cứ lúc nào!"
    if any(w in p for w in ["thời tiết", "mưa", "nắng"]):
        return "Hôm nay thời tiết rất đẹp, rất thích hợp để chúng ta cùng trò chuyện và học tập!"
    if any(w in p for w in ["tiếng anh", "english"]):
        return "Hello there! I am your AI robot companion. It is a pleasure to talk to you!"
    if any(w in p for w in ["cười", "hài", "kể chuyện"]):
        return "Một người hỏi máy tính: Bạn có biết tất cả mọi thứ không? Máy tính đáp: Có chứ, trừ mật khẩu của bạn thôi!"
    if any(w in p for w in ["mấy giờ", "ngày mấy"]):
        import datetime
        now = datetime.datetime.now()
        return f"Bây giờ là khoảng {now.strftime('%H giờ %M phút')}. Chúc bạn một ngày thật vui vẻ!"
    return f"Em đã nghe rõ câu nói: '{prompt}'. Em luôn sẵn sàng đồng hành và trò chuyện cùng bạn!"


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
        Câu trả lời ngắn gọn (2-3 câu) từ Gemini hoặc Smart Local Fallback.
    """
    import asyncio

    if not user_text or not user_text.strip():
        return ""

    client = get_genai_client()

    # Chuẩn bị danh sách nội dung lịch sử hội thoại
    history_contents: List[types.Content] = []

    if chat_history:
        for item in chat_history:
            if isinstance(item, types.Content):
                history_contents.append(item)
            elif isinstance(item, dict):
                role = item.get("role", "user")
                if role == "assistant":
                    role = "model"
                text = item.get("text") or item.get("content", "")
                if text:
                    history_contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=str(text))],
                        )
                    )

    # Sử dụng system instruction tùy chỉnh hoặc mặc định
    active_system_instruction = system_instruction.strip() if system_instruction and system_instruction.strip() else SYSTEM_INSTRUCTION

    config = types.GenerateContentConfig(
        system_instruction=active_system_instruction,
        temperature=0.7,
        max_output_tokens=300,
    )

    # Danh sách model thực tế được Google GenAI hỗ trợ
    candidate_list = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    primary_model = model_override if model_override in candidate_list else MODEL_NAME
    models_to_try = [primary_model]
    for candidate in candidate_list:
        if candidate not in models_to_try:
            models_to_try.append(candidate)

    last_error = None
    for model in models_to_try:
        try:
            logger.info(f"[LLM] Đang gửi prompt tới model {model}: '{user_text}'")
            chat = client.aio.chats.create(
                model=model,
                history=history_contents if history_contents else None,
                config=config,
            )

            # Đặt timeout 7 giây để không bị treo server
            response = await asyncio.wait_for(
                chat.send_message(user_text.strip()),
                timeout=7.0,
            )

            reply_text = response.text.strip() if response.text else ""
            if reply_text:
                logger.info(f"[LLM] Phản hồi từ Gemini ({model}): '{reply_text}'")
                return reply_text

        except Exception as e:
            last_error = e
            logger.warning(f"[LLM WARNING] Lỗi khi gọi model {model}: {e}")
            continue

    logger.warning(f"[LLM FALLBACK] Dùng câu trả lời thông minh thay thế (Lỗi Gemini: {last_error})")
    return get_quick_smart_reply(user_text)


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
