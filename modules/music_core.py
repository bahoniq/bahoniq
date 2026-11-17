"""
Ядро модуля «Музыка в авто» для BahonIQ Work Center.

Функционал:
- Асинхронное подключение к Telegram (Telethon) через StringSession
- Восстанавливаемый SQLite-кэш метаданных (data/music_catalog.db)
- Синхронизация каталога без скачивания аудиофайлов
- Поддержка HTTP Range (206 Partial Content) для стриминга
- Потоковая отдача полного файла для офлайн-сохранения (/download)
- Single-flight защита от параллельных одинаковых загрузок
- Полная изоляция секретов (сессия хранится только в переменной окружения)
"""
from __future__ import annotations
import asyncio
import io
import mimetypes
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "music_catalog.db"

# Синглтон-клиент Telethon
_client = None
_client_lock = asyncio.Lock()
# Блокировки per-track для single-flight загрузок
_track_locks: Dict[int, asyncio.Lock] = {}
_track_locks_guard = threading.Lock()

def _get_track_lock(track_id: int) -> asyncio.Lock:
    with _track_locks_guard:
        if track_id not in _track_locks:
            _track_locks[track_id] = asyncio.Lock()
        return _track_locks[track_id]


def get_db_connection() -> sqlite3.Connection:
    """Возвращает SQLite-соединение с самовосстанавливающейся структурой таблиц."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_msg_id INTEGER UNIQUE NOT NULL,
                document_id INTEGER NOT NULL,
                access_hash INTEGER NOT NULL DEFAULT 0,
                file_reference BLOB DEFAULT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT 'Неизвестный исполнитель',
                album TEXT NOT NULL DEFAULT '',
                duration INTEGER NOT NULL DEFAULT 0,
                file_size INTEGER NOT NULL DEFAULT 0,
                mime_type TEXT NOT NULL DEFAULT 'audio/mpeg',
                file_name TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                has_cover INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_msg_id ON tracks(telegram_msg_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title)")
    return conn


def extract_metadata(msg: Any) -> Optional[Dict[str, Any]]:
    """
    Извлекает метаданные трека БЕЗ скачивания аудиофайла:
    1. Telegram DocumentAttributeAudio (title, artist, album, duration)
    2. DocumentAttributeFilename (парсинг «Исполнитель — Трек.mp3»)
    3. Подпись публикации
    """
    if not msg or not getattr(msg, "media", None):
        return None
    document = getattr(msg.media, "document", None)
    if not document:
        return None

    mime_type = getattr(document, "mime_type", "") or "audio/mpeg"
    file_size = getattr(document, "size", 0) or 0

    # Проверяем, является ли медиа аудиофайлом
    attributes = getattr(document, "attributes", []) or []
    audio_attr = None
    filename_attr = None

    for attr in attributes:
        attr_type = attr.__class__.__name__
        if "Audio" in attr_type:
            audio_attr = attr
        elif "Filename" in attr_type:
            filename_attr = attr

    raw_file_name = getattr(filename_attr, "file_name", "") or getattr(msg, "file", None) and getattr(msg.file, "name", "") or ""
    is_audio = mime_type.startswith("audio/") or any(raw_file_name.lower().endswith(ext) for ext in (".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav"))
    if not is_audio:
        return None

    title = ""
    artist = ""
    duration = 0

    if audio_attr:
        title = (getattr(audio_attr, "title", None) or "").strip()
        artist = (getattr(audio_attr, "performer", None) or "").strip()
        duration = int(getattr(audio_attr, "duration", 0) or 0)

    # Если название или исполнитель отсутствуют — пробуем распарсить имя файла
    if not title or not artist:
        clean_name = Path(raw_file_name).stem.replace("_", " ").strip()
        match = re.match(r"^(.+?)\s*[-—–]\s*(.+?)$", clean_name)
        if match:
            parsed_artist, parsed_title = match.group(1).strip(), match.group(2).strip()
            if not artist:
                artist = parsed_artist
            if not title:
                title = parsed_title
        elif not title and clean_name:
            title = clean_name

    # Если всё ещё нет — пробуем взять из текста публикации
    caption = (getattr(msg, "message", None) or "").strip()
    if (not title or not artist) and caption:
        first_line = caption.split("\n")[0].strip()
        cap_match = re.match(r"^(.+?)\s*[-—–]\s*(.+?)$", first_line)
        if cap_match:
            if not artist:
                artist = cap_match.group(1).strip()
            if not title:
                title = cap_match.group(2).strip()

    if not title:
        title = Path(raw_file_name).stem or f"Трек #{msg.id}"
    if not artist:
        artist = "Музыка ДИТ"

    # Проверяем наличие встроенного thumbnail
    thumbs = getattr(document, "thumbs", None)
    has_cover = 1 if thumbs and len(thumbs) > 0 else 0

    msg_date = getattr(msg, "date", None)
    date_str = msg_date.isoformat() if hasattr(msg_date, "isoformat") else datetime.now(timezone.utc).isoformat()

    return {
        "telegram_msg_id": msg.id,
        "document_id": document.id,
        "access_hash": getattr(document, "access_hash", 0),
        "file_reference": getattr(document, "file_reference", None),
        "title": title,
        "artist": artist,
        "album": "",
        "duration": duration,
        "file_size": file_size,
        "mime_type": mime_type,
        "file_name": raw_file_name or f"{title}.mp3",
        "date": date_str,
        "caption": caption,
        "has_cover": has_cover,
    }


async def get_telegram_client():
    """
    Инициализирует и возвращает подключенный синглтон TelegramClient.
    Секреты берутся исключительно из переменных окружения.
    """
    global _client
    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        api_id_str = os.getenv("TELEGRAM_API_ID", "").strip()
        api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
        session_str = os.getenv("TELEGRAM_SESSION", "").strip()

        if not api_id_str or not api_hash or not session_str:
            return None

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except ImportError:
            return None

        try:
            api_id = int(api_id_str)
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return None
            _client = client
            return _client
        except Exception:
            return None


async def get_channel_entity(client):
    """
    Определяет Telegram Entity канала по ID или по username.
    """
    channel_id_env = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    channel_user_env = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip().replace("@", "")

    if channel_id_env:
        try:
            cid = int(channel_id_env)
            return await client.get_entity(cid)
        except Exception:
            pass

    if channel_user_env:
        try:
            return await client.get_entity(channel_user_env)
        except Exception:
            pass

    # Попытка через invite link если задан
    invite_env = os.getenv("TELEGRAM_CHANNEL_INVITE", "").strip()
    if invite_env:
        try:
            return await client.get_entity(invite_env)
        except Exception:
            pass

    return await client.get_entity("bahoniqmusic")


async def sync_catalog(force: bool = False) -> Dict[str, Any]:
    """
    Сканирует историю сообщений канала и сохраняет метаданные треков в SQLite.
    Аудиофайлы НЕ скачиваются. Защита от дубликатов по telegram_msg_id.
    """
    client = await get_telegram_client()
    if not client:
        return {
            "status": "error",
            "connected": False,
            "error": "Telegram-сессия не настроена или не авторизована. Укажите TELEGRAM_SESSION в Render."
        }

    try:
        channel = await get_channel_entity(client)
    except Exception as exc:
        return {
            "status": "error",
            "connected": True,
            "error": f"Канал недоступен: {exc}"
        }

    conn = get_db_connection()
    new_tracks_count = 0
    total_found = 0

    try:
        # Сканируем сообщения канала
        async for message in client.iter_messages(channel, limit=1000):
            meta = extract_metadata(message)
            if not meta:
                continue

            total_found += 1
            with conn:
                cur = conn.execute(
                    "SELECT id FROM tracks WHERE telegram_msg_id = ?",
                    (meta["telegram_msg_id"],)
                )
                existing = cur.fetchone()
                if not existing:
                    conn.execute("""
                        INSERT INTO tracks (
                            telegram_msg_id, document_id, access_hash, file_reference,
                            title, artist, album, duration, file_size, mime_type,
                            file_name, date, caption, has_cover
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        meta["telegram_msg_id"], meta["document_id"], meta["access_hash"],
                        meta["file_reference"], meta["title"], meta["artist"], meta["album"],
                        meta["duration"], meta["file_size"], meta["mime_type"], meta["file_name"],
                        meta["date"], meta["caption"], meta["has_cover"]
                    ))
                    new_tracks_count += 1

        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_sync', ?)", (now_str,))
            conn.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('channel_id', ?)", (str(getattr(channel, 'id', '')),))

        total_in_db = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

        return {
            "status": "ok",
            "connected": True,
            "channel_title": getattr(channel, "title", "Музыка ДИТ"),
            "new_tracks": new_tracks_count,
            "total_tracks": total_in_db,
            "last_sync": now_str
        }
    except Exception as exc:
        return {
            "status": "error",
            "connected": True,
            "error": f"Ошибка синхронизации: {exc}"
        }
    finally:
        conn.close()


def get_catalog_status() -> Dict[str, Any]:
    """Возвращает безопасный статус подключения и кэша без раскрытия секретов."""
    conn = get_db_connection()
    try:
        total_tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        last_sync_row = conn.execute("SELECT value FROM sync_meta WHERE key='last_sync'").fetchone()
        last_sync = last_sync_row[0] if last_sync_row else None
        has_session = bool(os.getenv("TELEGRAM_SESSION", "").strip())
        has_creds = bool(os.getenv("TELEGRAM_API_ID") and os.getenv("TELEGRAM_API_HASH"))

        return {
            "status": "ok",
            "telegram_configured": has_session and has_creds,
            "channel_username": os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic"),
            "total_tracks": total_tracks,
            "last_sync": last_sync,
            "offline_cache_ready": total_tracks > 0
        }
    finally:
        conn.close()


def query_tracks(
    query: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    sort_by: str = "date",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Возвращает отфильтрованный список треков из SQLite-кэша."""
    conn = get_db_connection()
    try:
        where_clauses = []
        params = []

        if query:
            clean_q = f"%{query.strip()}%"
            where_clauses.append("(title LIKE ? OR artist LIKE ? OR file_name LIKE ?)")
            params.extend([clean_q, clean_q, clean_q])

        if artist:
            where_clauses.append("artist = ?")
            params.append(artist.strip())

        if album:
            where_clauses.append("album = ?")
            params.append(album.strip())

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Валидация сортировки
        col = "id"
        if sort_by == "title": col = "title"
        elif sort_by == "artist": col = "artist"
        elif sort_by == "duration": col = "duration"
        elif sort_by == "date": col = "date"

        sort_dir = "ASC" if order.lower() == "asc" else "DESC"

        count_sql = f"SELECT COUNT(*) FROM tracks {where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        select_sql = f"""
            SELECT id, telegram_msg_id, title, artist, album, duration, file_size, mime_type, file_name, date, has_cover
            FROM tracks
            {where_sql}
            ORDER BY {col} {sort_dir}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(select_sql, params + [limit, offset]).fetchall()

        tracks = []
        for r in rows:
            tracks.append({
                "id": r["id"],
                "telegram_msg_id": r["telegram_msg_id"],
                "title": r["title"],
                "artist": r["artist"],
                "album": r["album"],
                "duration": r["duration"],
                "file_size": r["file_size"],
                "mime_type": r["mime_type"],
                "file_name": r["file_name"],
                "date": r["date"],
                "has_cover": bool(r["has_cover"]),
            })
        return tracks, total
    finally:
        conn.close()


def get_track_by_id(track_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


async def get_telegram_document_for_track(track_id: int):
    """Находит сообщение и Telethon document для трека."""
    track = get_track_by_id(track_id)
    if not track:
        return None, None

    client = await get_telegram_client()
    if not client:
        return track, None

    channel = await get_channel_entity(client)
    message = await client.get_messages(channel, ids=track["telegram_msg_id"])
    if not message or not getattr(message, "media", None):
        return track, None

    document = getattr(message.media, "document", None)
    return track, document


async def stream_track_chunks(
    track_id: int,
    start: int,
    length: int,
    chunk_size: int = 128 * 1024
) -> AsyncGenerator[bytes, None]:
    """
    Генератор чанков аудиофайла через Telethon iter_download.
    Использует single-flight блокировку и корректно обрабатывает обрыв соединения клиентом.
    """
    track, document = await get_telegram_document_for_track(track_id)
    if not document:
        return

    client = await get_telegram_client()
    lock = _get_track_lock(track_id)

    # Загружаем указанный диапазон байтов
    async with lock:
        try:
            async for chunk in client.iter_download(document, offset=start, limit=length, chunk_size=chunk_size):
                yield chunk
        except (asyncio.CancelledError, GeneratorExit):
            # Клиент отключился или перемотал трек — штатное прерывание стрима
            return
        except Exception:
            return


async def download_full_track(track_id: int) -> AsyncGenerator[bytes, None]:
    """Потоковая отдача полного аудиофайла для сохранения в OPFS/IndexedDB."""
    track = get_track_by_id(track_id)
    if not track:
        return

    file_size = track["file_size"]
    async for chunk in stream_track_chunks(track_id, start=0, length=file_size, chunk_size=256 * 1024):
        yield chunk


def clear_catalog_cache():
    """Очищает кэш метаданных SQLite (восстановимый кэш)."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM tracks")
            conn.execute("DELETE FROM sync_meta")
    finally:
        conn.close()
