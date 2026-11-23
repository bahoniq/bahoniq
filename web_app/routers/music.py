"""
Роутер API для модуля «Музыка в авто» BahonIQ Work Center.
"""
from __future__ import annotations
import os
import re
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pathlib import Path
import asyncio

from modules.music_core import (
    _start_or_join_progressive_download,
    clear_catalog_cache,
    download_full_track,
    ensure_catalog_ready,
    ensure_track_cached,
    get_cached_track_path,
    get_catalog_status,
    get_saved_telegram_session_str,
    get_telegram_client,
    get_telegram_document_for_track,
    get_track_by_id,
    query_tracks,
    reset_telegram_client,
    resolve_track_cover,
    save_telegram_session_str,
    stream_track_chunks,
    sync_catalog,
)
from modules.music_covers import extract_embedded_cover_from_bytes
try:
    from ..modules.radio_service import RADIO_BY_ID as _RADIO_BY_ID
    from ..modules.radio_service import RADIO_STATIONS, get_station_metadata, public_station
except ImportError:
    from modules.radio_service import RADIO_BY_ID as _RADIO_BY_ID
    from modules.radio_service import RADIO_STATIONS, get_station_metadata, public_station

router = APIRouter(prefix="/api/music", tags=["music"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
LOGO_PATH = STATIC_DIR / "logo.png"

_auto_sync_task = None

DEFAULT_VINYL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect width="512" height="512" fill="#07111f" rx="32"/>
  <circle cx="256" cy="256" r="210" fill="#0d1829" stroke="#00e5ff" stroke-width="4" stroke-opacity="0.5"/>
  <circle cx="256" cy="256" r="170" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-opacity="0.12"/>
  <circle cx="256" cy="256" r="130" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-opacity="0.12"/>
  <circle cx="256" cy="256" r="90" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-opacity="0.12"/>
  <circle cx="256" cy="256" r="60" fill="#00e5ff" fill-opacity="0.2" stroke="#00e5ff" stroke-width="3"/>
  <circle cx="256" cy="256" r="20" fill="#07111f"/>
  <path d="M246 170v140a32 32 0 1 1-20-30v-80l60-20v50" fill="none" stroke="#facc15" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def _parse_single_range(range_header: str, file_size: int) -> tuple[int, int]:
    """Разбирает один RFC 7233 byte-range или поднимает ValueError.

    Поддерживает bytes=START-END, bytes=START- и bytes=-SUFFIX.
    Несколько диапазонов намеренно не поддерживаются.
    """
    if file_size <= 0 or not range_header or not range_header.lower().startswith("bytes="):
        raise ValueError("invalid range")
    value = range_header.split("=", 1)[1].strip()
    if not value or "," in value or value.count("-") != 1:
        raise ValueError("multiple or malformed ranges are unsupported")
    first, last = (part.strip() for part in value.split("-", 1))
    if not first:
        # suffix-byte-range-spec: последние N байт
        if not last.isdigit():
            raise ValueError("invalid suffix")
        suffix = int(last)
        if suffix <= 0:
            raise ValueError("invalid suffix")
        suffix = min(suffix, file_size)
        return file_size - suffix, file_size - 1
    if not first.isdigit() or (last and not last.isdigit()):
        raise ValueError("invalid byte position")
    start = int(first)
    if start >= file_size:
        raise ValueError("range starts after end of file")
    end = int(last) if last else file_size - 1
    if end < start:
        raise ValueError("range end precedes start")
    return start, min(end, file_size - 1)


def _check_admin_auth(request: Request, x_music_admin_token: Optional[str] = None) -> bool:
    """Проверка прав администратора для синхронизации."""
    expected_token = os.getenv("MUSIC_ADMIN_TOKEN", "").strip()
    bahoniq_password = os.getenv("BAHONIQ_PASSWORD", "").strip()

    # Проверка через заголовок X-Music-Admin-Token
    if expected_token and x_music_admin_token == expected_token:
        return True

    # Проверка через основную куку авторизации Work Center
    from web_app.server import AUTH_COOKIE_NAME, AUTH_TOKEN
    cookie_val = request.cookies.get(AUTH_COOKIE_NAME)
    if AUTH_TOKEN and cookie_val == AUTH_TOKEN:
        return True

    # Если пароли не настроены вообще — доступ открыт
    if not expected_token and not bahoniq_password:
        return True

    return False


@router.get("/status")
def music_status():
    """Статус подключения и кэша (безопасный, без секретов)."""
    return get_catalog_status()


@router.get("/tracks")
async def list_tracks(
    q: Optional[str] = Query(None, description="Поисковый запрос"),
    artist: Optional[str] = Query(None, description="Фильтр по исполнителю"),
    album: Optional[str] = Query(None, description="Фильтр по альбому"),
    sort_by: str = Query("date", description="Поле сортировки: date, title, artist, duration"),
    order: str = Query("desc", description="Порядок: asc, desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Каталог треков с поиском, фильтрами и пагинацией. При пустой базе авто-синхронизирует."""
    global _auto_sync_task
    tracks, total = query_tracks(
        query=q,
        artist=artist,
        album=album,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset
    )

    # Авто-синхронизация при первом запросе, если в базе ещё нет треков
    has_session = bool(get_saved_telegram_session_str())
    if total == 0 and has_session:
        await ensure_catalog_ready()
        tracks, total = query_tracks(
            query=q,
            artist=artist,
            album=album,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset
        )

    for t in tracks:
        ver = t.get("cover_hash") or t.get("cover_version") or 0
        t["cover_url"] = f"/api/music/cover/{t['id']}?v={ver}"

    return {
        "status": "ok",
        "tracks": tracks,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/tracks/{track_id}")
async def get_track(track_id: int):
    """Метаданные конкретного трека."""
    track = get_track_by_id(track_id)
    if not track:
        await ensure_catalog_ready()
        track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")
    ver = track.get("cover_hash") or track.get("cover_version") or 0
    return {
        "id": track["id"],
        "file_unique_id": track.get("file_unique_id", f"track_{track['id']}"),
        "title": track["title"],
        "artist": track["artist"],
        "album": track["album"],
        "duration": track["duration"],
        "file_size": track["file_size"],
        "mime_type": track["mime_type"],
        "file_name": track["file_name"],
        "date": track["date"],
        "has_cover": bool(track["has_cover"]),
        "cover_hash": track.get("cover_hash", ""),
        "cover_source": track.get("cover_source", ""),
        "cover_version": ver,
        "cover_url": f"/api/music/cover/{track['id']}?v={ver}",
    }


@router.get("/tracks/{track_id}/stream")
async def stream_track(
    track_id: int,
    range_header: Optional[str] = Header(None, alias="Range")
):
    """
    Потоковое онлайн-воспроизведение аудиофайла с поддержкой HTTP Range (206 Partial Content).
    Позволяет мгновенно начать воспроизведение и свободно перематывать трек.
    """
    track = get_track_by_id(track_id)
    if not track:
        await ensure_catalog_ready()
        track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    file_size = int(track["file_size"] or 0)
    mime_type = track["mime_type"] or "audio/mpeg"

    try:
        cached_path = get_cached_track_path(track_id)
        if cached_path is not None:
            file_size = cached_path.stat().st_size
        else:
            state = await _start_or_join_progressive_download(track_id)
            if state.expected_size > 0:
                file_size = state.expected_size
            elif file_size <= 0:
                cached_path = await ensure_track_cached(track_id)
                file_size = cached_path.stat().st_size
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось получить аудиофайл: {exc}") from exc
    if file_size <= 0:
        raise HTTPException(status_code=502, detail="Telegram вернул пустой аудиофайл")

    # Обработка Range-запроса (например: bytes=1048576- или bytes=0-1048575)
    if range_header:
        try:
            start, end = _parse_single_range(range_header, file_size)
        except ValueError:
            return Response(
                status_code=416,
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-store",
                },
            )
        length = end - start + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": mime_type,
            "Cache-Control": "private, no-store",
        }
        return StreamingResponse(
            stream_track_chunks(track_id, start=start, length=length),
            status_code=206,
            headers=headers
        )

    # Запрос без Range — отдаём от начала
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": mime_type,
        "Cache-Control": "private, no-store",
    }
    return StreamingResponse(
        stream_track_chunks(track_id, start=0, length=file_size),
        status_code=200,
        headers=headers
    )


@router.get("/tracks/{track_id}/download")
async def download_track(track_id: int):
    """
    Прогрессивная выдача полного файла для OPFS/IndexedDB.
    Не ждёт, пока Render сначала скачает весь трек: каждый чанк Telegram сразу
    передаётся браузеру и одновременно записывается в серверный кеш.
    """
    track = get_track_by_id(track_id)
    if not track:
        await ensure_catalog_ready()
        track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    try:
        cached_path = get_cached_track_path(track_id)
        if cached_path is not None:
            file_size = cached_path.stat().st_size
        else:
            state = await _start_or_join_progressive_download(track_id)
            file_size = int(state.expected_size or track["file_size"] or 0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось скачать аудиофайл: {exc}") from exc
    if file_size <= 0:
        raise HTTPException(status_code=502, detail="Пустой аудиофайл")

    mime_type = track["mime_type"] or "audio/mpeg"
    raw_name = track["file_name"] or f"{track['artist']} - {track['title']}.mp3"
    safe_filename = quote(raw_name)

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}',
        "Content-Length": str(file_size),
        "Cache-Control": "private, max-age=86400",
    }
    return StreamingResponse(
        download_full_track(track_id),
        status_code=200,
        media_type=mime_type,
        headers=headers,
    )


def _extract_embedded_cover_bytes(audio_path: Path) -> Optional[tuple[bytes, str]]:
    """Извлекает встроенную обложку (MP3 ID3v2.2 PIC, ID3v2.3/2.4 APIC, MP4/M4A covr, FLAC, OGG) с валидацией изображения."""
    try:
        with audio_path.open("rb") as f:
            head = f.read(524288)
    except OSError:
        return None
    return extract_embedded_cover_from_bytes(head)


@router.get("/cover/{track_id}")
@router.get("/tracks/{track_id}/cover")
async def track_cover(
    track_id: int,
    request: Request,
    fallback: Optional[str] = Query(None),
    v: Optional[str] = Query(None),
):
    """
    Возвращает обложку трека со строгим приоритетом:
    1. Встроенная обложка из метаданных аудиофайла (embedded).
    2. Миниатюра Telegram-документа (thumb), если встроенной обложки нет.
    3. Ранее сохранённая реальная обложка трека.
    4. HTTP 404 (при fallback=404) либо фирменная заглушка BahonIQ (с Cache-Control: no-store, чтобы заглушка никогда не кешировалась как финальная обложка).
    """
    resolved = await resolve_track_cover(track_id, allow_network=True)
    if resolved and resolved.get("bytes"):
        img_bytes: bytes = resolved["bytes"]
        mime: str = resolved.get("mime") or "image/jpeg"
        cover_hash: str = resolved.get("cover_hash") or ""
        source: str = resolved.get("source") or "embedded"
        etag = f'"{cover_hash}"' if cover_hash else ""
        cache_ctrl = (
            "public, max-age=31536000, immutable"
            if (v and cover_hash and str(v) == str(cover_hash))
            else "public, max-age=86400"
        )
        headers = {
            "Cache-Control": cache_ctrl,
            "X-Cover-Source": source,
            "X-Cover-Placeholder": "false",
        }
        if etag:
            headers["ETag"] = etag
            inm = (request.headers.get("if-none-match") or "").strip()
            if inm and (inm == etag or inm.strip('"') == cover_hash):
                return Response(status_code=304, headers=headers)

        return Response(
            content=img_bytes,
            media_type=mime,
            headers=headers,
        )

    if fallback == "404":
        raise HTTPException(status_code=404, detail="No embedded cover")

    placeholder_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "X-Cover-Source": "placeholder",
        "X-Cover-Placeholder": "true",
    }
    if LOGO_PATH.exists():
        return FileResponse(LOGO_PATH, media_type="image/png", headers=placeholder_headers)
    return Response(
        content=DEFAULT_VINYL_SVG,
        media_type="image/svg+xml",
        headers=placeholder_headers,
    )


@router.post("/sync")
async def trigger_sync(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token")
):
    """Синхронизация каталога с Telegram-каналом (только для администратора)."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: требуется авторизация администратора")

    result = await sync_catalog(force=True)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Ошибка синхронизации"))
    return result


@router.post("/clear-cache")
def trigger_clear_cache(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token")
):
    """Очистка серверного SQLite-кэша метаданных."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: требуется авторизация администратора")

    clear_catalog_cache()
    return {"status": "ok", "message": "Серверный кэш метаданных успешно очищен"}


_web_auth_state: dict = {
    "client": None,
    "phone": "",
    "phone_code_hash": "",
    "qr_login": None,
}
_web_auth_lock = asyncio.Lock()


@router.get("/auth/session-status")
async def music_session_status():
    """Проверяет живую авторизацию текущей Telegram-сессии."""
    client = await get_telegram_client()
    if client is not None:
        try:
            me = await client.get_me()
            return {
                "authorized": True,
                "user": f"{getattr(me, 'first_name', '') or ''} (@{getattr(me, 'username', '') or getattr(me, 'id', '')})".strip(),
            }
        except Exception:
            await reset_telegram_client()
    return {"authorized": False, "user": None}


@router.post("/auth/qr-start")
async def music_auth_qr_start(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token"),
):
    """Генерирует QR-ссылку (tg://login?token=...) для мгновенного входа сканированием с телефона БЕЗ кода."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: войдите в Work Center")

    api_id_str = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    if not api_id_str or not api_hash:
        raise HTTPException(status_code=500, detail="TELEGRAM_API_ID и TELEGRAM_API_HASH не заданы в .env")

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    async with _web_auth_lock:
        old_client = _web_auth_state.get("client")
        if old_client is not None:
            try:
                await old_client.disconnect()
            except Exception:
                pass
        client = TelegramClient(StringSession(), int(api_id_str), api_hash)
        await client.connect()
        try:
            qr_login = await client.qr_login()
        except Exception as exc:
            await client.disconnect()
            raise HTTPException(status_code=400, detail=f"Ошибка генерации QR Telegram: {exc}") from exc

        _web_auth_state["client"] = client
        _web_auth_state["qr_login"] = qr_login
        return {"status": "qr_ready", "url": qr_login.url}


@router.post("/auth/qr-poll")
async def music_auth_qr_poll(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token"),
):
    """Проверяет, отсканирован ли QR-код в приложении Telegram на телефоне, и автоматически обновляет токен до истечения 30 сек."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: войдите в Work Center")

    from telethon.errors import SessionPasswordNeededError

    async with _web_auth_lock:
        client = _web_auth_state.get("client")
        qr_login = _web_auth_state.get("qr_login")
        if not client or not qr_login:
            return {"status": "expired"}

        try:
            await qr_login.wait(timeout=1.5)
        except asyncio.TimeoutError:
            # Если до истечения 30-секундного токена осталось мало времени — заранее перевыпускаем свежий QR
            return {"status": "waiting"}
        except SessionPasswordNeededError:
            return {"status": "2fa_required", "message": "Введите облачный пароль 2FA"}
        except Exception:
            try:
                await qr_login.recreate()
                return {"status": "waiting", "url": qr_login.url}
            except Exception:
                return {"status": "expired"}

        me = await client.get_me()
        session_string = client.session.save()
        await client.disconnect()
        _web_auth_state["client"] = None
        _web_auth_state["qr_login"] = None

    await save_telegram_session_str(session_string)
    sync_res = await sync_catalog(force=True)
    return {
        "status": "ok",
        "user": f"{getattr(me, 'first_name', '') or ''} (@{getattr(me, 'username', '') or getattr(me, 'id', '')})".strip(),
        "session_string": session_string,
        "sync": sync_res,
    }


@router.post("/auth/send-code")
async def music_auth_send_code(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token"),
):
    """Отправляет код авторизации Telegram на указанный номер телефона."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: войдите в Work Center")
    payload = await request.json()
    phone = str(payload.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Укажите номер телефона в формате +7...")

    api_id_str = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    if not api_id_str or not api_hash:
        raise HTTPException(status_code=500, detail="TELEGRAM_API_ID и TELEGRAM_API_HASH не заданы в .env / Render")

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    async with _web_auth_lock:
        old_client = _web_auth_state.get("client")
        if old_client is not None:
            try:
                await old_client.disconnect()
            except Exception:
                pass
        client = TelegramClient(StringSession(), int(api_id_str), api_hash)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
        except Exception as exc:
            await client.disconnect()
            raise HTTPException(status_code=400, detail=f"Ошибка отправки кода Telegram: {exc}") from exc

        _web_auth_state["client"] = client
        _web_auth_state["phone"] = phone
        _web_auth_state["phone_code_hash"] = sent.phone_code_hash
        return {"status": "code_sent", "phone": phone}


@router.post("/auth/verify-code")
async def music_auth_verify_code(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token"),
):
    """Подтверждает код из Telegram (и облачный пароль 2FA при наличии), сохраняет StringSession и синхронизирует каталог."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: войдите в Work Center")
    payload = await request.json()
    code = str(payload.get("code") or "").strip()
    password = str(payload.get("password") or "").strip()

    from telethon.errors import SessionPasswordNeededError

    async with _web_auth_lock:
        client = _web_auth_state.get("client")
        phone = _web_auth_state.get("phone")
        phone_code_hash = _web_auth_state.get("phone_code_hash")
        if not client:
            raise HTTPException(status_code=400, detail="Сначала запустите QR-вход или запросите код")

        try:
            if code:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            elif password:
                await client.sign_in(password=password)
            else:
                raise HTTPException(status_code=400, detail="Введите код из Telegram или облачный пароль 2FA")
        except SessionPasswordNeededError:
            if password:
                try:
                    await client.sign_in(password=password)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Неверный облачный пароль 2FA: {exc}") from exc
            else:
                return {"status": "2fa_required", "message": "Требуется облачный пароль двухэтапной аутентификации (2FA)"}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Ошибка входа: {exc}") from exc

        me = await client.get_me()
        session_string = client.session.save()
        await client.disconnect()
        _web_auth_state["client"] = None

    await save_telegram_session_str(session_string)
    sync_res = await sync_catalog(force=True)
    return {
        "status": "ok",
        "user": f"{getattr(me, 'first_name', '') or ''} (@{getattr(me, 'username', '') or getattr(me, 'id', '')})".strip(),
        "session_string": session_string,
        "sync": sync_res,
    }


# ============================================================
# ОНЛАЙН-РАДИО (ЖИВЫЕ СТАНЦИИ И ПРОКСИ ПОТОКА)
# ============================================================

@router.get("/radio/stations")
def list_radio_stations():
    """Возвращает список подтверждённых и готовых к воспроизведению радиостанций."""
    return {"stations": [public_station(item) for item in RADIO_STATIONS if item.get("url")]}


@router.get("/radio/metadata/{station_id}")
async def radio_metadata(station_id: str):
    """Возвращает ICY StreamTitle текущей станции, если вещатель его передаёт."""
    try:
        return await get_station_metadata(station_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Радиостанция не найдена")


def _is_safe_public_radio_url(url: str) -> bool:
    """Базовая защита от SSRF для пользовательских URL радиопотоков."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return False
    try:
        for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except Exception:
        return False
    return True


async def _proxy_audio_stream(target_url: str, request: Request):
    """Асинхронная ретрансляция живого аудиопотока с корректным закрытием при обрыве."""
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=30)
    headers = {
        "User-Agent": "BahonIQ-Music/1.0",
        "Accept": "*/*",
    }
    session = aiohttp.ClientSession(timeout=timeout)
    try:
        resp = await session.get(target_url, headers=headers, allow_redirects=True)
        if resp.status >= 400:
            await resp.release()
            await session.close()
            raise HTTPException(status_code=502, detail=f"Радиостанция недоступна (HTTP {resp.status})")
        content_type = resp.headers.get("Content-Type") or "audio/mpeg"
    except HTTPException:
        raise
    except Exception as exc:
        await session.close()
        raise HTTPException(status_code=502, detail=f"Ошибка подключения к радио: {exc}") from exc

    async def stream_gen():
        try:
            async for chunk in resp.content.iter_chunked(16384):
                if await request.is_disconnected():
                    break
                if chunk:
                    yield chunk
        finally:
            resp.close()
            await session.close()

    return StreamingResponse(
        stream_gen(),
        media_type=content_type.split(";")[0].strip(),
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/radio/stream/{station_id}")
async def stream_radio_station(station_id: str, request: Request):
    """Стримит предустановленную радиостанцию через бэкенд (решает HTTPS/Mixed-Content и CORS)."""
    station = _RADIO_BY_ID.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Радиостанция не найдена")
    if not station.get("url"):
        raise HTTPException(status_code=503, detail=station.get("unavailableReason") or "Поток временно недоступен")
    return await _proxy_audio_stream(station["url"], request)


@router.get("/radio/proxy")
async def proxy_custom_radio(request: Request, url: str = Query(..., min_length=8)):
    """Проксирует пользовательский URL интернет-радио."""
    if not _is_safe_public_radio_url(url):
        raise HTTPException(status_code=400, detail="Недопустимый или небезопасный URL радиопотока")
    return await _proxy_audio_stream(url, request)


@router.post("/auth/set-session")
async def music_auth_set_session(
    request: Request,
    x_music_admin_token: Optional[str] = Header(None, alias="X-Music-Admin-Token"),
):
    """Позволяет вставить готовую строку TELEGRAM_SESSION напрямую и сразу запустить синхронизацию."""
    if not _check_admin_auth(request, x_music_admin_token):
        raise HTTPException(status_code=403, detail="Доступ запрещён: войдите в Work Center")
    payload = await request.json()
    session_string = str(payload.get("session_string") or "").strip()
    if len(session_string) < 50:
        raise HTTPException(status_code=400, detail="Некорректная строка TELEGRAM_SESSION")

    await save_telegram_session_str(session_string)
    client = await get_telegram_client()
    if not client:
        raise HTTPException(status_code=400, detail="Эта строка сессии недействительна или деавторизована в Telegram")
    me = await client.get_me()
    sync_res = await sync_catalog(force=True)
    return {
        "status": "ok",
        "user": f"{getattr(me, 'first_name', '') or ''} (@{getattr(me, 'username', '') or getattr(me, 'id', '')})".strip(),
        "sync": sync_res,
    }
