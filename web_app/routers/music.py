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
    clear_catalog_cache,
    download_full_track,
    get_catalog_status,
    get_track_by_id,
    query_tracks,
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
    if total == 0 and os.getenv("TELEGRAM_SESSION"):
        if _auto_sync_task is None or _auto_sync_task.done():
            _auto_sync_task = asyncio.create_task(sync_catalog(force=False))

    return {
        "status": "ok",
        "tracks": tracks,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/tracks/{track_id}")
def get_track(track_id: int):
    """Метаданные конкретного трека."""
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
        raise HTTPException(status_code=404, detail="Трек не найден")

    file_size = track["file_size"]
    mime_type = track["mime_type"] or "audio/mpeg"

    if file_size <= 0:
        raise HTTPException(status_code=400, detail="Некорректный размер файла")

    # Обработка Range-запроса (например: bytes=1048576- или bytes=0-1048575)
    if range_header and range_header.startswith("bytes="):
        range_val = range_header[6:].strip()
        parts = range_val.split("-")
        try:
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        except ValueError:
            start = 0
            end = file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        length = end - start + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": mime_type,
            "Cache-Control": "no-cache",
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
        "Cache-Control": "no-cache",
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
    Возвращает 200 OK с точным Content-Length.
    """
    track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    file_size = track["file_size"]
    mime_type = track["mime_type"] or "audio/mpeg"
    raw_name = track["file_name"] or f"{track['artist']} - {track['title']}.mp3"
    safe_filename = quote(raw_name)

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}',
        "Content-Length": str(file_size),
        "Content-Type": mime_type,
        "Cache-Control": "private, max-age=86400",
    }
    return StreamingResponse(
        download_full_track(track_id),
        status_code=200,
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
