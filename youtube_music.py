"""
Module xử lý tìm kiếm và stream nhạc YouTube online cho Robot Xiaozhi ESP32.
Sử dụng yt-dlp để trích xuất link âm thanh và httpx / ffmpeg để stream từng gói dữ liệu qua WebSocket.
"""

import asyncio
import logging
import os
import re
import shutil
from typing import AsyncGenerator, Dict, List, Optional, Any
import httpx
import yt_dlp

logger = logging.getLogger("YouTubeMusic")

# Cache tìm kiếm và audio stream URL để tăng tốc độ phản hồi
SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}
AUDIO_INFO_CACHE: Dict[str, Dict[str, Any]] = {}

FFMPEG_PATH = shutil.which("ffmpeg")
if FFMPEG_PATH:
    logger.info(f"[YOUTUBE MUSIC] Đã tìm thấy ffmpeg tại: {FFMPEG_PATH}")
else:
    logger.info("[YOUTUBE MUSIC] Không có ffmpeg trong PATH, sẽ stream trực tiếp từ URL của YouTube.")


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
    q = query.strip()
    
    # Danh sách tiền tố cần loại bỏ
    prefixes = [
        r"^hát cho tôi nghe bài\s*", r"^hát cho em nghe bài\s*", r"^hát cho bé nghe bài\s*",
        r"^cho tôi nghe bài\s*", r"^cho em nghe bài\s*",
        r"^mở bài hát\s*", r"^phát bài hát\s*", r"^bật bài hát\s*", r"^hát bài hát\s*",
        r"^nghe bài hát\s*", r"^tìm bài hát\s*", r"^chơi bài hát\s*",
        r"^mở bài\s*", r"^phát bài\s*", r"^bật bài\s*", r"^hát bài\s*", r"^nghe bài\s*",
        r"^tìm bài\s*", r"^chơi bài\s*",
        r"^mở nhạc\s*", r"^phát nhạc\s*", r"^bật nhạc\s*", r"^nghe nhạc\s*",
        r"^hát bài\s*", r"^hát\s*",
    ]
    
    # Danh sách hậu tố cần loại bỏ
    suffixes = [
        r"\s*ở trên youtube$", r"\s*trên youtube$", r"\s*ở youtube$", r"\s*qua youtube$", r"\s*từ youtube$",
        r"\s*trên mạng$", r"\s*cho tôi nghe$", r"\s*cho em nghe$", r"\s*cho bé nghe$",
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

    return q if q else query.strip()


async def search_youtube(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Tìm kiếm video trên YouTube bằng yt-dlp (chế độ flat extraction siêu nhanh ~1-2s).
    """
    cleaned_q = clean_query(query)
    cache_key = f"{cleaned_q}_{max_results}".lower()
    if cache_key in SEARCH_CACHE:
        return SEARCH_CACHE[cache_key]

    def _sync_search() -> List[Dict[str, Any]]:
        # Nếu query là link YouTube trực tiếp
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
        SEARCH_CACHE[cache_key] = results
    return results


async def get_audio_stream_info(video_id_or_url: str) -> Optional[Dict[str, Any]]:
    """
    Trích xuất đường link audio stream trực tiếp và thông tin chi tiết của bài hát.
    """
    target = video_id_or_url
    if not (target.startswith("http://") or target.startswith("https://")):
        target = f"https://www.youtube.com/watch?v={video_id_or_url}"

    if target in AUDIO_INFO_CACHE:
        return AUDIO_INFO_CACHE[target]

    def _sync_extract() -> Optional[Dict[str, Any]]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                }
            },
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=False)
                if not info:
                    return None

                # Lấy audio url trực tiếp
                audio_url = info.get("url")
                if not audio_url and "formats" in info:
                    # Tìm format audio tốt nhất
                    for f in info["formats"]:
                        if f.get("acodec") != "none" and f.get("url"):
                            audio_url = f.get("url")
                            break

                if not audio_url:
                    logger.warning(f"[YOUTUBE EXTRACT] Không tìm thấy direct audio URL cho {target}")
                    return None

                vid = info.get("id")
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
            logger.error(f"[YOUTUBE EXTRACT ERROR] {e}")
            return None

    info = await asyncio.to_thread(_sync_extract)
    if info:
        AUDIO_INFO_CACHE[target] = info
    return info


async def stream_youtube_audio_chunks(
    audio_url: str,
    chunk_size: int = 1024,
    pace_delay: float = 0.045,
    max_duration_sec: int = 600,
) -> AsyncGenerator[bytes, None]:
    """
    Generator stream dữ liệu âm thanh dạng bytes để đẩy qua WebSocket tới robot.
    Có pacing (asyncio.sleep) để tránh tràn bộ nhớ RAM của chip ESP32.
    """
    logger.info(f"[AUDIO STREAM] Bắt đầu stream YouTube audio (chunk_size={chunk_size}, pace={pace_delay}s)...")

    # Cách 1: Nếu có ffmpeg, transcode sang MP3 mono 24kHz (khớp 100% định dạng Edge-TTS)
    if FFMPEG_PATH:
        try:
            logger.info("[AUDIO STREAM] Sử dụng ffmpeg để chuẩn hóa audio sang MP3...")
            proc = await asyncio.create_subprocess_exec(
                FFMPEG_PATH,
                "-re",  # Đọc theo tốc độ phát thực tế
                "-i", audio_url,
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "24000",
                "-ac", "1",
                "-b:a", "48k",
                "-f", "mp3",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            chunk_idx = 0
            while True:
                chunk = await proc.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                chunk_idx += 1
                if chunk_idx > 10:
                    await asyncio.sleep(pace_delay)
                else:
                    await asyncio.sleep(0.005)

            try:
                proc.terminate()
                await proc.wait()
            except Exception:
                pass
            logger.info(f"[AUDIO STREAM] Hoàn thành stream qua ffmpeg ({chunk_idx} chunks).")
            return
        except Exception as ffmpeg_err:
            logger.warning(f"[AUDIO STREAM FFMPEG WARNING] {ffmpeg_err}. Chuyển sang HTTP direct stream.")

    # Cách 2: Stream trực tiếp từ CDN URL của YouTube qua HTTP stream
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None), follow_redirects=True) as client:
        async with client.stream("GET", audio_url, headers=headers) as resp:
            if resp.status_code not in (200, 206):
                logger.error(f"[AUDIO STREAM ERROR] HTTP {resp.status_code} khi tải audio stream")
                return

            chunk_idx = 0
            buffer = bytearray()
            async for data in resp.aiter_bytes():
                buffer.extend(data)
                while len(buffer) >= chunk_size:
                    out_chunk = bytes(buffer[:chunk_size])
                    del buffer[:chunk_size]
                    yield out_chunk
                    chunk_idx += 1
                    # Gửi 10 gói đầu nhanh để làm đầy buffer bộ đệm trên ESP32, sau đó nhịp đều
                    if chunk_idx > 10:
                        await asyncio.sleep(pace_delay)
                    else:
                        await asyncio.sleep(0.005)

            if buffer:
                yield bytes(buffer)
                chunk_idx += 1

            logger.info(f"[AUDIO STREAM] Hoàn thành stream HTTP direct ({chunk_idx} chunks).")
