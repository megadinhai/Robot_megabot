import asyncio
import datetime
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Thiết lập UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

logger = logging.getLogger("LLMHandler")

# 1. Đọc API Keys và cấu hình từ môi trường / .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# 2. System Prompt định hình tính cách cho robot Megabot
SYSTEM_INSTRUCTION = """Bạn là trợ lý robot thông minh Megabot trên phần cứng ESP32.
Nhiệm vụ của bạn là trò chuyện với người dùng bằng giọng nói qua micro và loa.

Quy tắc phản hồi bắt buộc:
1. Luôn trả lời bằng tiếng Việt tự nhiên, thân thiện, lễ phép và thông minh.
2. Vì câu trả lời sẽ được chuyển thành giọng nói (TTS) để phát qua loa robot, bạn PHẢI trả lời ngắn gọn, súc tích (tối đa 2 đến 3 câu).
3. Tuyệt đối KHÔNG dùng các ký tự định dạng markdown như **, *, #, gạch đầu dòng, bảng biểu hay emoji vì loa robot không đọc được các ký tự này.
4. Xưng hô tự nhiên, thân thiện: xưng là 'em' hoặc 'Megabot', gọi người dùng là 'bạn' hoặc 'anh/chị'.
"""


def clean_for_speech(text: str) -> str:
    """Loại bỏ ký tự markdown, emoji, code block để phát loa TTS rõ ràng nhất."""
    if not text:
        return ""
    # Xóa code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Xóa inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Xóa ký tự markdown *, _, ~, #
    text = re.sub(r'[*_~#]', '', text)
    # Xóa bullet points đầu dòng
    text = re.sub(r'^\s*[-+*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Xóa các emoji phổ biến gây gián đoạn TTS
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Thu gọn khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_quick_smart_reply(prompt: str) -> str:
    """Tạo câu trả lời thông minh nhanh nếu kết nối các AI gặp sự cố."""
    p = prompt.lower().strip()
    if any(w in p for w in ["chào", "hello", "hi"]):
        return "Chào bạn! Em là robot Megabot rất vui được trò chuyện cùng bạn. Hôm nay bạn thế nào?"
    if any(w in p for w in ["bạn là ai", "tên gì", "giới thiệu"]):
        return "Em là trợ lý robot AI Megabot chạy trên vi điều khiển ESP32, sẵn sàng lắng nghe và trả lời bạn!"
    if any(w in p for w in ["khỏe không", "thế nào", "ổn không"]):
        return "Em khỏe lắm, luôn đầy năng lượng và sẵn sàng giúp đỡ bạn bất cứ lúc nào!"
    if any(w in p for w in ["thời tiết", "mưa", "nắng"]):
        return "Hôm nay thời tiết rất đẹp, rất thích hợp để chúng ta cùng trò chuyện và học tập!"
    if any(w in p for w in ["tiếng anh", "english"]):
        return "Hello there! I am your AI robot companion. It is a pleasure to talk to you!"
    if any(w in p for w in ["cười", "hài", "kể chuyện"]):
        return "Một người hỏi máy tính: Bạn có biết tất cả mọi thứ không? Máy tính đáp: Có chứ, trừ mật khẩu của bạn thôi!"
    if any(w in p for w in ["mấy giờ", "ngày mấy"]):
        now = datetime.datetime.now()
        return f"Bây giờ là khoảng {now.strftime('%H giờ %M phút')}. Chúc bạn một ngày thật vui vẻ!"
    return f"Em đã nghe rõ câu nói: '{prompt}'. Em luôn sẵn sàng đồng hành và trò chuyện cùng bạn!"


# ==========================================
# 1. GOOGLE GEMINI HANDLER
# ==========================================
_gemini_client = None

def get_genai_client(api_key: Optional[str] = None):
    """Khởi tạo hoặc lấy Google GenAI client."""
    global _gemini_client
    from google import genai
    key = api_key or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if api_key:
        return genai.Client(api_key=api_key)
    if _gemini_client is None:
        if not key or key == "your_gemini_api_key_here":
            logger.warning("GEMINI_API_KEY chưa được thiết lập hợp lệ.")
        _gemini_client = genai.Client(api_key=key or "dummy_key")
    return _gemini_client


async def chat_with_gemini_internal(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Gửi câu hỏi tới Google Gemini API."""
    from google.genai import types

    client = get_genai_client(api_key)
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

    active_sys = system_instruction.strip() if system_instruction and system_instruction.strip() else SYSTEM_INSTRUCTION
    config = types.GenerateContentConfig(
        system_instruction=active_sys,
        temperature=0.7,
        max_output_tokens=300,
    )

    candidate_list = ["gemini-3.8-flash", "gemini-3.1-flash-lite-preview"]
    target_model = model_name if model_name in candidate_list else DEFAULT_GEMINI_MODEL
    models_to_try = [target_model] + [c for c in candidate_list if c != target_model]

    last_error = None
    for m in models_to_try:
        try:
            logger.info(f"[LLM-Gemini] Gửi prompt tới {m}: '{user_text}'")
            chat = client.aio.chats.create(
                model=m,
                history=history_contents if history_contents else None,
                config=config,
            )
            response = await asyncio.wait_for(chat.send_message(user_text.strip()), timeout=7.0)
            reply = response.text.strip() if response.text else ""
            if reply:
                logger.info(f"[LLM-Gemini] Phản hồi ({m}): '{reply}'")
                return clean_for_speech(reply)
        except Exception as e:
            last_error = e
            logger.warning(f"[LLM-Gemini WARNING] Lỗi model {m}: {e}")
            continue

    raise Exception(f"Tất cả model Gemini đều lỗi: {last_error}")


# ==========================================
# 2. OPENAI (CHATGPT) HANDLER
# ==========================================
async def chat_with_openai_internal(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Gửi câu hỏi tới OpenAI API (ChatGPT)."""
    from openai import AsyncOpenAI

    key = (api_key or os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY or "").strip()
    if not key or key == "your_openai_api_key_here":
        raise ValueError("OPENAI_API_KEY chưa được thiết lập trong .env hoặc cấu hình")

    model = model_name or "gpt-4o-mini"
    if model in ["chatgpt", "openai"]:
        model = "gpt-4o-mini"

    client = AsyncOpenAI(api_key=key)

    active_sys = system_instruction.strip() if system_instruction and system_instruction.strip() else SYSTEM_INSTRUCTION
    messages: List[Dict[str, str]] = [{"role": "system", "content": active_sys}]

    if chat_history:
        for item in chat_history:
            if isinstance(item, dict):
                role = item.get("role", "user")
                if role == "model":
                    role = "assistant"
                elif role not in ["user", "assistant", "system"]:
                    role = "user"
                content = item.get("text") or item.get("content", "")
                if content:
                    messages.append({"role": role, "content": str(content)})

    messages.append({"role": "user", "content": user_text.strip()})

    logger.info(f"[LLM-OpenAI] Gửi prompt tới {model}: '{user_text}'")
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        ),
        timeout=8.0,
    )

    reply = response.choices[0].message.content or ""
    logger.info(f"[LLM-OpenAI] Phản hồi ({model}): '{reply}'")
    return clean_for_speech(reply.strip())


# ==========================================
# 3. DEEPSEEK HANDLER
# ==========================================
async def chat_with_deepseek_internal(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Gửi câu hỏi tới DeepSeek API (deepseek-chat / deepseek-reasoner)."""
    from openai import AsyncOpenAI

    key = (api_key or os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_API_KEY or "").strip()
    if not key or key == "your_deepseek_api_key_here":
        raise ValueError("DEEPSEEK_API_KEY chưa được thiết lập trong .env hoặc cấu hình")

    model = model_name or "deepseek-chat"
    if model in ["deepseek", "deepseek-v3"]:
        model = "deepseek-chat"
    elif model in ["deepseek-r1"]:
        model = "deepseek-reasoner"

    client = AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com")

    active_sys = system_instruction.strip() if system_instruction and system_instruction.strip() else SYSTEM_INSTRUCTION
    messages: List[Dict[str, str]] = [{"role": "system", "content": active_sys}]

    if chat_history:
        for item in chat_history:
            if isinstance(item, dict):
                role = item.get("role", "user")
                if role == "model":
                    role = "assistant"
                elif role not in ["user", "assistant", "system"]:
                    role = "user"
                content = item.get("text") or item.get("content", "")
                if content:
                    messages.append({"role": role, "content": str(content)})

    messages.append({"role": "user", "content": user_text.strip()})

    logger.info(f"[LLM-DeepSeek] Gửi prompt tới {model}: '{user_text}'")
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        ),
        timeout=10.0,
    )

    reply = response.choices[0].message.content or ""
    logger.info(f"[LLM-DeepSeek] Phản hồi ({model}): '{reply}'")
    return clean_for_speech(reply.strip())


# ==========================================
# 4. BỘ ĐIỀU PHỐI ĐA MÔ HÌNH (UNIFIED ROUTER)
# ==========================================
def detect_provider(model: Optional[str]) -> str:
    """Xác định nhà cung cấp mô hình AI (gemini, openai, deepseek)."""
    m = (model or "").lower().strip()
    if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or "openai" in m or "chatgpt" in m:
        return "openai"
    if "deepseek" in m:
        return "deepseek"
    return "gemini"


async def chat_with_llm(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_override: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None,
) -> str:
    """
    Điều phối gửi prompt tới mô hình AI tương ứng (ChatGPT, DeepSeek, hoặc Gemini)
    với cơ chế Fallback thông minh đảm bảo Robot luôn trả lời.
    """
    if not user_text or not user_text.strip():
        return ""

    provider = detect_provider(model_override)
    keys = api_keys or {}

    # 1. Thử gọi nhà cung cấp được cấu hình
    try:
        if provider == "openai":
            key = keys.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            return await chat_with_openai_internal(
                user_text=user_text,
                chat_history=chat_history,
                system_instruction=system_instruction,
                model_name=model_override,
                api_key=key,
            )
        elif provider == "deepseek":
            key = keys.get("deepseek_api_key") or os.getenv("DEEPSEEK_API_KEY")
            return await chat_with_deepseek_internal(
                user_text=user_text,
                chat_history=chat_history,
                system_instruction=system_instruction,
                model_name=model_override,
                api_key=key,
            )
        else:
            key = keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
            return await chat_with_gemini_internal(
                user_text=user_text,
                chat_history=chat_history,
                system_instruction=system_instruction,
                model_name=model_override,
                api_key=key,
            )
    except Exception as primary_err:
        logger.warning(f"[LLM WARNING] Gọi {provider} ({model_override}) thất bại: {primary_err}")

    # 2. Fallback sang Gemini nếu provider chính gặp lỗi và có Gemini API key
    if provider != "gemini":
        gemini_key = keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                logger.info("[LLM FALLBACK] Tự động chuyển hướng xử lý sang Google Gemini...")
                return await chat_with_gemini_internal(
                    user_text=user_text,
                    chat_history=chat_history,
                    system_instruction=system_instruction,
                    model_name=DEFAULT_GEMINI_MODEL,
                    api_key=gemini_key,
                )
            except Exception as fb_err:
                logger.warning(f"[LLM FALLBACK FAILED] Fallback Gemini cũng lỗi: {fb_err}")

    # 3. Fallback cuối cùng: Trả lời thông minh offline không cần mạng
    logger.info("[LLM FALLBACK] Sử dụng câu trả lời thông minh offline cục bộ.")
    return get_quick_smart_reply(user_text)


# Tương thích ngược 100% với các mã nguồn gọi hàm chat_with_gemini cũ
async def chat_with_gemini(
    user_text: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    system_instruction: Optional[str] = None,
    model_override: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None,
) -> str:
    """Bí danh của chat_with_llm để đảm bảo tương thích với các module cũ."""
    return await chat_with_llm(
        user_text=user_text,
        chat_history=chat_history,
        system_instruction=system_instruction,
        model_override=model_override,
        api_keys=api_keys,
    )


# Test nhanh trực tiếp file
if __name__ == "__main__":
    async def main():
        print("=== KIỂM TRA HỆ THỐNG ĐA MÔ HÌNH (GEMINI, OPENAI, DEEPSEEK) ===")
        test_msg = "Xin chào Megabot! Bạn có khỏe không?"
        print(f"User: {test_msg}")
        reply = await chat_with_llm(test_msg, model_override="gemini-2.5-flash")
        print(f"Megabot (Gemini): {reply}")

    asyncio.run(main())
