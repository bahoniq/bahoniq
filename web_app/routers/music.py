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
    get_track_by_id,
    query_tracks,
    save_telegram_session_str,
    stream_track_chunks,
    sync_catalog,
)

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
    return {
        "id": track["id"],
        "title": track["title"],
        "artist": track["artist"],
        "album": track["album"],
        "duration": track["duration"],
        "file_size": track["file_size"],
        "mime_type": track["mime_type"],
        "file_name": track["file_name"],
        "date": track["date"],
        "has_cover": bool(track["has_cover"]),
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
    Получение полного файла для сохранения в OPFS или IndexedDB.
    Дожидается полной готовности проверенного серверного файла (.bin), чтобы не конкурировать
    по трафику с онлайн-стримингом (/stream), и отдаёт готовый файл с точным Content-Length.
    """
    track = get_track_by_id(track_id)
    if not track:
        await ensure_catalog_ready()
        track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    try:
        cached_path = await ensure_track_cached(track_id)
        file_size = cached_path.stat().st_size
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
    return FileResponse(
        cached_path,
        media_type=mime_type,
        headers=headers
    )


@router.get("/tracks/{track_id}/cover")
def track_cover(track_id: int):
    """Возвращает официальный логотип приложения BahonIQ как обложку."""
    if LOGO_PATH.exists():
        return FileResponse(LOGO_PATH, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})
    return Response(
        content=DEFAULT_VINYL_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=604800"}
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
            pass
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
