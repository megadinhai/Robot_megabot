"""
Module xử lý tìm kiếm và stream nhạc YouTube online cho Robot Megabot (Xiaozhi ESP32).
Sử dụng yt-dlp để trích xuất link âm thanh và PyAV để transcode trực tiếp sang các gói Opus chuẩn 60ms
phù hợp hoàn hảo với bộ giải mã esp_opus_dec trên vi điều khiển ESP32.
"""

import asyncio
import io
import logging
import os
import re
import shutil
import threading
from typing import AsyncGenerator, Dict, List, Optional, Any, Tuple
import yt_dlp
import av

logger = logging.getLogger("YouTubeMusic")

# Cache tìm kiếm và audio stream URL để tăng tốc độ phản hồi
SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}
AUDIO_INFO_CACHE: Dict[str, Dict[str, Any]] = {}


def format_duration(seconds: Optional[int]) -> str:
    """Định dạng số giây thành chuỗi mm:ss hoặc hh:mm:ss."""
    if not seconds or seconds < 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_query(query: str) -> str:
    """Làm sạch câu lệnh tìm kiếm bài hát từ giọng nói hoặc nhập liệu."""
    if not query:
        return ""
    q = query.strip()
    
    # Loại bỏ tiền xưng hô hoặc mệnh lệnh ở đầu câu
    lead_in = [
        r"^(?:xin\s+chào\s+)?(?:megabot|robot|em|bạn)\s*[,:]?\s*",
        r"^(?:bạn|em|robot)\s+(?:hãy|ơi|giúp\s+mình|giúp\s+tôi|giúp\s+em|có\s+thể)\s*",
        r"^(?:hãy|vui\s+lòng|xin\s+hãy|làm\s+ơn)\s*",
    ]
    for pattern in lead_in:
        q = re.sub(pattern, "", q, flags=re.IGNORECASE).strip()

    # Danh sách tiền tố bài hát cần loại bỏ
    prefixes = [
        r"^hát cho tôi nghe bài\s*", r"^hát cho em nghe bài\s*", r"^hát cho bé nghe bài\s*",
        r"^cho tôi nghe bài\s*", r"^cho em nghe bài\s*", r"^cho mình nghe bài\s*",
        r"^tìm và phát bài hát\s*", r"^tìm và phát bài\s*", r"^tìm bài hát\s*", r"^tìm bài\s*",
        r"^mở bài hát\s*", r"^phát bài hát\s*", r"^bật bài hát\s*", r"^hát bài hát\s*",
        r"^nghe bài hát\s*", r"^chơi bài hát\s*",
        r"^mở ca khúc\s*", r"^phát ca khúc\s*", r"^bật ca khúc\s*",
        r"^mở bài\s*", r"^phát bài\s*", r"^bật bài\s*", r"^hát bài\s*", r"^nghe bài\s*",
        r"^tìm bài\s*", r"^chơi bài\s*",
        r"^mở nhạc\s*", r"^phát nhạc\s*", r"^bật nhạc\s*", r"^nghe nhạc\s*", r"^chơi nhạc\s*",
        r"^hát cho tôi nghe\s*", r"^hát cho em nghe\s*", r"^hát cho bé nghe\s*",
        r"^hát\s*",
    ]
    
    # Danh sách hậu tố cần loại bỏ
    suffixes = [
        r"\s*ở trên youtube$", r"\s*trên youtube$", r"\s*ở youtube$", r"\s*qua youtube$", r"\s*từ youtube$", r"\s*youtube$",
        r"\s*trên mạng$", r"\s*cho tôi nghe$", r"\s*cho em nghe$", r"\s*cho bé nghe$", r"\s*cho mình nghe$",
        r"\s*đi robot$", r"\s*đi bạn$", r"\s*đi em$", r"\s*đi nha$", r"\s*đi nhé$", r"\s*đi$",
        r"\s*nhé$", r"\s*nha$", r"\s*với$", r"\s*giùm$", r"\s*hộ$",
    ]

    changed = True
    while changed:
        old_q = q
        for p in prefixes:
            q = re.sub(p, "", q, flags=re.IGNORECASE).strip()
        for s in suffixes:
            q = re.sub(s, "", q, flags=re.IGNORECASE).strip()
        changed = (old_q != q)

    # Loại bỏ dấu ngoặc kép hoặc ký tự bao quanh
    q = q.strip('\"\'“” :,')
    return q if q else query.strip()


def extract_music_intent(text: str) -> Optional[Dict[str, Any]]:
    """
    Phát hiện ý định phát nhạc hoặc dừng nhạc từ chuỗi văn bản người dùng (giọng nói hoặc web chat).
    Trả về {'action': 'stop'} hoặc {'action': 'play', 'song': 'tên bài hát'} hoặc None.
    """
    if not text:
        return None
    raw = text.strip()
    lower = raw.lower()
    
    # 1. Kiểm tra lệnh dừng nhạc
    stop_words = [
        "dừng nhạc", "tắt nhạc", "ngừng nhạc", "ngừng phát nhạc",
        "dừng bài hát", "tắt bài hát", "dừng phát", "ngừng phát",
        "dừng bài", "tắt bài", "dừng hát", "tắt loa", "dừng lại đi",
        "stop music", "dừng phát nhạc", "thôi đừng hát", "im lặng đi"
    ]
    for w in stop_words:
        if w in lower:
            return {"action": "stop"}

    # 2. Kiểm tra lệnh phát nhạc
    play_kw = [
        "hát cho tôi nghe bài", "hát cho em nghe bài", "hát cho bé nghe bài",
        "cho tôi nghe bài", "cho em nghe bài", "cho mình nghe bài",
        "tìm và phát bài hát", "tìm và phát bài", "tìm bài hát", "tìm bài",
        "phát bài hát", "mở bài hát", "bật bài hát", "nghe bài hát", "hát bài hát", "chơi bài hát",
        "phát ca khúc", "mở ca khúc", "bật ca khúc",
        "phát bài", "mở bài", "bật bài", "nghe bài", "hát bài", "chơi bài",
        "phát nhạc", "mở nhạc", "bật nhạc", "nghe nhạc", "chơi nhạc",
        "hát cho tôi nghe", "hát cho em nghe", "hát cho bé nghe"
    ]

    found_kw = None
    for kw in sorted(play_kw, key=len, reverse=True):
        idx = lower.find(kw)
        if idx != -1:
            found_kw = (kw, idx)
            break

    if found_kw:
        kw, idx = found_kw
        song = raw[idx + len(kw):].strip()
        # Loại bỏ các từ đệm hậu tố
        suffixes = [
            "ở trên youtube", "trên youtube", "ở youtube", "qua youtube", "từ youtube", "youtube",
            "cho tôi nghe", "cho em nghe", "cho bé nghe", "cho mình nghe",
            "đi robot", "đi bạn", "đi em", "đi nha", "đi nhé", "đi",
            "nhé", "nha", "với", "giùm", "hộ"
        ]
        changed = True
        while changed:
            changed = False
            for s in suffixes:
                if song.lower().endswith(s):
                    song = song[:-len(s)].strip()
                    changed = True
                    break
        song = song.strip('\"\'“” :,')
        if len(song) >= 2:
            return {"action": "play", "song": song}

    return None


async def search_youtube(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Tìm kiếm video trên YouTube bằng yt-dlp (chế độ flat extraction siêu nhanh ~1-2s).
    """
    cleaned_q = clean_query(query)
    cache_key = f"{cleaned_q}_{max_results}".lower()
    if cache_key in SEARCH_CACHE:
        return SEARCH_CACHE[cache_key]

    def _sync_search() -> List[Dict[str, Any]]:
        if cleaned_q.startswith("http://") or cleaned_q.startswith("https://"):
            search_target = cleaned_q
        else:
            search_target = f"ytsearch{max_results}:{cleaned_q}"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "default_search": "ytsearch",
            "no_cache_dir": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_creator", "android"],
                }
            },
        }

        results: List[Dict[str, Any]] = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_target, download=False)
                entries = info.get("entries", []) if "entries" in info else [info]
                for item in entries:
                    if not item:
                        continue
                    vid = item.get("id")
                    title = item.get("title", "Không rõ tiêu đề")
                    dur_sec = item.get("duration") or 0
                    uploader = item.get("uploader") or item.get("channel", "YouTube")
                    thumbnail = (
                        item.get("thumbnail")
                        or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    )
                    url = item.get("url") or f"https://www.youtube.com/watch?v={vid}"

                    results.append({
                        "id": vid,
                        "title": title,
                        "url": url,
                        "uploader": uploader,
                        "duration_sec": dur_sec,
                        "duration_str": format_duration(dur_sec),
                        "thumbnail": thumbnail,
                    })
        except Exception as e:
            logger.error(f"[YOUTUBE SEARCH ERROR] {e}")

        return results

    results = await asyncio.to_thread(_sync_search)
    if results:
        if len(SEARCH_CACHE) > 15:
            SEARCH_CACHE.pop(next(iter(SEARCH_CACHE)))
        SEARCH_CACHE[cache_key] = results
    return results


async def get_audio_stream_info(video_id_or_url: str) -> Optional[Dict[str, Any]]:
    """
    Trích xuất đường link audio stream trực tiếp và thông tin chi tiết của bài hát.
    Sử dụng luân phiên các player_client (android_creator, android, mweb) để vượt qua chặn bot trên cloud IP.
    """
    target = video_id_or_url
    if not (target.startswith("http://") or target.startswith("https://")):
        target = f"https://www.youtube.com/watch?v={video_id_or_url}"

    if target in AUDIO_INFO_CACHE:
        return AUDIO_INFO_CACHE[target]

    def _sync_extract() -> Optional[Dict[str, Any]]:
        client_candidates = [
            ["android_creator", "android"],
            ["android"],
            ["android_creator"],
            ["mweb"],
            ["tv_embedded"],
        ]

        last_err = None
        for clients in client_candidates:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": "bestaudio/ba/b",
                "no_cache_dir": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": clients,
                        "player_skip": ["webpage", "configs"],
                    }
                },
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target, download=False)
                    if not info:
                        continue

                    # Lấy audio url trực tiếp
                    audio_url = info.get("url")
                    if not audio_url and "formats" in info:
                        for f in info["formats"]:
                            if f.get("acodec") != "none" and f.get("url"):
                                audio_url = f.get("url")
                                break

                    if not audio_url:
                        continue

                    vid = info.get("id") or target
                    title = info.get("title", "Không rõ tiêu đề")
                    dur_sec = info.get("duration") or 0
                    uploader = info.get("uploader") or info.get("channel", "YouTube")
                    thumbnail = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

                    return {
                        "id": vid,
                        "title": title,
                        "url": target,
                        "audio_url": audio_url,
                        "uploader": uploader,
                        "duration_sec": dur_sec,
                        "duration_str": format_duration(dur_sec),
                        "thumbnail": thumbnail,
                        "acodec": info.get("acodec", "unknown"),
                        "ext": info.get("ext", "mp3"),
                    }
            except Exception as e:
                last_err = e
                logger.warning(f"[YOUTUBE EXTRACT TRY {clients}] Không trích xuất được: {e}")
                continue

        logger.error(f"[YOUTUBE EXTRACT ERROR] Tất cả client đều không lấy được audio cho {target}: {last_err}")
        return None

    info = await asyncio.to_thread(_sync_extract)
    if info:
        if len(AUDIO_INFO_CACHE) > 15:
            AUDIO_INFO_CACHE.pop(next(iter(AUDIO_INFO_CACHE)))
        AUDIO_INFO_CACHE[target] = info
    return info


async def stream_youtube_audio_opus_packets(
    audio_url: str,
    sample_rate: int = 16000,
    frame_duration_ms: int = 60,
    bit_rate: int = 36000,
) -> AsyncGenerator[bytes, None]:
    """
    Generator giải mã âm thanh từ YouTube và mã hóa trực tiếp thành các gói Opus 60ms (16000Hz mono),
    khớp 100% với định dạng của bộ giải mã esp_opus_dec trên ESP32.
    Sử dụng luồng phụ (producer thread) và queue bất đồng bộ để tránh làm block vòng lặp sự kiện FastAPI.
    """
    logger.info(f"[AUDIO OPUS STREAM] Khởi tạo luồng giải mã & Opus encoder (rate={sample_rate}, frame={frame_duration_ms}ms)...")
    samples_per_frame = int(sample_rate * (frame_duration_ms / 1000.0))  # 960 mẫu cho 60ms ở 16kHz
    queue: asyncio.Queue = asyncio.Queue(maxsize=40)
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()

    def producer():
        container = None
        out_container = None
        try:
            container = av.open(audio_url)
            if not container.streams.audio:
                logger.error("[AUDIO OPUS ERROR] Không tìm thấy audio stream trong container")
                return

            in_stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)

            out_io = io.BytesIO()
            out_container = av.open(out_io, mode="w", format="opus")
            out_stream = out_container.add_stream("opus", rate=sample_rate, layout="mono")
            out_stream.bit_rate = bit_rate

            fifo = av.AudioFifo()

            for frame in container.decode(in_stream):
                if stop_event.is_set():
                    break
                for rf in resampler.resample(frame):
                    fifo.write(rf)
                    while fifo.samples >= samples_per_frame:
                        if stop_event.is_set():
                            break
                        chunk_frame = fifo.read(samples_per_frame)
                        for pkt in out_stream.encode(chunk_frame):
                            data = bytes(pkt)
                            fut = asyncio.run_coroutine_threadsafe(queue.put(data), loop)
                            fut.result()

            # Xử lý phần mẫu còn dư trong FIFO
            if not stop_event.is_set() and fifo.samples > 0:
                chunk_frame = fifo.read(fifo.samples)
                for pkt in out_stream.encode(chunk_frame):
                    data = bytes(pkt)
                    asyncio.run_coroutine_threadsafe(queue.put(data), loop).result()

            # Flush bộ mã hóa Opus
            if not stop_event.is_set():
                for pkt in out_stream.encode(None):
                    data = bytes(pkt)
                    asyncio.run_coroutine_threadsafe(queue.put(data), loop).result()

        except Exception as e:
            if not stop_event.is_set():
                logger.warning(f"[AUDIO OPUS STREAM PRODUCER] Kết thúc hoặc lỗi: {e}")
        finally:
            if out_container:
                try:
                    out_container.close()
                except Exception:
                    pass
            if container:
                try:
                    container.close()
                except Exception:
                    pass
            # Gửi None báo hiệu kết thúc bài hát
            try:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
            except Exception:
                pass
            import gc
            gc.collect()

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    try:
        while True:
            pkt = await queue.get()
            if pkt is None:
                break
            yield pkt
    finally:
        stop_event.set()
        import gc
        gc.collect()


# Tương thích ngược với các lời gọi hàm cũ
async def stream_youtube_audio_chunks(
    audio_url: str,
    chunk_size: int = 1024,
    pace_delay: float = 0.050,
    max_duration_sec: int = 600,
) -> AsyncGenerator[bytes, None]:
    """Hàm bao bọc tương thích ngược: trả về từng gói Opus 60ms để gửi qua WebSocket tới ESP32."""
    async for pkt in stream_youtube_audio_opus_packets(audio_url, sample_rate=16000):
        yield pkt
