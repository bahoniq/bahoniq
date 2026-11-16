"""
BahonIQ Voice v2 — Server-side Neural Text-to-Speech Router
Provides high-quality neural voice synthesis via edge-tts (ru-RU-DmitryNeural, ru-RU-SvetlanaNeural).
Includes in-memory LRU caching, concurrency limiting, IP rate limiting, and text sanitization.
"""

import asyncio
import hashlib
import logging
import re
import time
from collections import OrderedDict
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("bahoniq.voice")

router = APIRouter(prefix="/api/voice", tags=["Voice"])

# --- Allowed Voices & Pydantic Schema ---
ALLOWED_VOICES = Literal["ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"]

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: ALLOWED_VOICES = "ru-RU-DmitryNeural"
    rate: str = Field("+0%", max_length=10)
    pitch: str = Field("+0Hz", max_length=10)

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, v: str) -> str:
        v = (v or "+0%").strip()
        if not re.match(r"^[+-]?\d{1,3}%$", v):
            return "+0%"
        return v

    @field_validator("pitch")
    @classmethod
    def validate_pitch(cls, v: str) -> str:
        v = (v or "+0Hz").strip()
        if not re.match(r"^[+-]?\d{1,3}Hz$", v):
            return "+0Hz"
        return v


# --- Text Sanitization ---
def sanitize_tts_text(raw_text: str) -> str:
    """Removes HTML, Markdown, URLs, and dangerous control characters."""
    if not raw_text:
        return ""
    s = str(raw_text)
    # Remove HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Replace markdown code blocks with spoken note
    s = re.sub(r"```[\s\S]*?```", " Пример кода показан на экране. ", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Replace markdown links [anchor](url) -> anchor
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    # Remove remaining bare URLs
    s = re.sub(r"https?://\S+", "", s)
    # Remove markdown header tokens, formatting chars
    s = re.sub(r"[*_~#>]+", " ", s)
    # Remove dangerous/non-printable control chars
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", s)
    # Normalize whitespaces
    s = re.sub(r"\s+", " ", s).strip()
    return s[:4000]


# --- In-Memory LRU Cache ---
# Key: SHA-256 hash (never stores raw text in keys)
# Value: (audio_bytes, timestamp)
MAX_CACHE_ITEMS = 50
CACHE_TTL_SECONDS = 3600.0
_audio_cache: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
_cache_lock = asyncio.Lock()

async def get_cached_audio(cache_key: str) -> bytes | None:
    async with _cache_lock:
        if cache_key in _audio_cache:
            data, created_at = _audio_cache[cache_key]
            if time.time() - created_at < CACHE_TTL_SECONDS:
                _audio_cache.move_to_end(cache_key)
                return data
            else:
                del _audio_cache[cache_key]
    return None

async def set_cached_audio(cache_key: str, data: bytes) -> None:
    async with _cache_lock:
        if cache_key in _audio_cache:
            _audio_cache.move_to_end(cache_key)
        _audio_cache[cache_key] = (data, time.time())
        if len(_audio_cache) > MAX_CACHE_ITEMS:
            _audio_cache.popitem(last=False)


# --- Concurrency & Rate Limiting ---
TTS_SEMAPHORE = asyncio.Semaphore(3)  # Max 3 concurrent synthesis workers
IP_RATE_WINDOW = 60.0  # seconds
IP_RATE_MAX_REQUESTS = 30
_client_history: dict[str, list[float]] = {}
_history_lock = asyncio.Lock()

async def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    async with _history_lock:
        history = _client_history.setdefault(client_ip, [])
        # Prune old timestamps
        history[:] = [t for t in history if now - t < IP_RATE_WINDOW]
        if len(history) >= IP_RATE_MAX_REQUESTS:
            return False
        history.append(now)
        # Periodic cleanup of idle IPs
        if len(_client_history) > 200:
            for ip in list(_client_history.keys()):
                _client_history[ip] = [t for t in _client_history[ip] if now - t < IP_RATE_WINDOW]
                if not _client_history[ip]:
                    del _client_history[ip]
    return True


# --- Synthesis Engine (edge-tts) ---
async def synthesize_speech(text: str, voice: str, rate: str, pitch: str) -> bytes:
    """Synthesizes speech using edge-tts directly into memory with retry & parameter fallback."""
    import edge_tts

    # Try synthesis with requested rate/pitch first; if prosody rejected, fallback to default rate/pitch
    attempts = [
        {"rate": rate, "pitch": pitch},
        {"rate": "+0%", "pitch": "+0Hz"}
    ]
    for param in attempts:
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=param["rate"],
                pitch=param["pitch"],
                connect_timeout=8,
                receive_timeout=15
            )
            chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            audio = b"".join(chunks)
            if audio:
                return audio
        except Exception as e:
            logger.warning("Synthesis attempt with rate=%s failed (%s), retrying...", param["rate"], type(e).__name__)
            await asyncio.sleep(0.2)
    raise RuntimeError("No audio data received from edge-tts")


# --- Endpoint ---
@router.post("/tts")
async def tts_endpoint(req: TTSRequest, request: Request):
    """
    POST /api/voice/tts
    Synthesizes neural audio for given Russian text via edge-tts.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Rate Limiting Check
    if not await check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов на озвучивание. Подождите немного."
        )

    # 2. Text Sanitization
    clean_text = sanitize_tts_text(req.text)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текст для озвучивания пуст или содержит только недопустимые символы."
        )

    # 3. Cache Key Hash (SHA-256)
    key_src = f"{req.voice}|{req.rate}|{req.pitch}|{clean_text}".encode("utf-8")
    cache_key = hashlib.sha256(key_src).hexdigest()

    # 4. Check Cache
    cached_audio = await get_cached_audio(cache_key)
    if cached_audio:
        return Response(
            content=cached_audio,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Audio-Cache": "HIT"
            }
        )

    # 5. Acquire Concurrency Slot & Synthesize with Timeout
    try:
        async with TTS_SEMAPHORE:
            # 15s synthesis timeout
            audio_data = await asyncio.wait_for(
                synthesize_speech(clean_text, req.voice, req.rate, req.pitch),
                timeout=15.0
            )
    except asyncio.TimeoutError:
        logger.warning("TTS timeout for voice=%s len=%d hash=%s", req.voice, len(clean_text), cache_key[:8])
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Превышено время ожидания синтеза речи. Повторите попытку позже."
        )
    except Exception as exc:
        logger.warning("TTS failure for voice=%s len=%d hash=%s: %s", req.voice, len(clean_text), cache_key[:8], exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Служба нейроозвучки временно недоступна. Попробуйте системный голос."
        )

    # 6. Store in Cache
    await set_cached_audio(cache_key, audio_data)

    logger.info("TTS OK: voice=%s bytes=%d len=%d hash=%s", req.voice, len(audio_data), len(clean_text), cache_key[:8])

    return Response(
        content=audio_data,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Audio-Cache": "MISS"
        }
    )
