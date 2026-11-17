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
import logging
import mimetypes
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "music_catalog.db"
MUSIC_CACHE_DIR = DATA_DIR / "music_stream_cache"
LOGGER = logging.getLogger(__name__)

# Синглтон-клиент Telethon
_client = None
_client_lock = asyncio.Lock()
# Ограничиваем количество одновременных MTProto-загрузок. Нельзя использовать
# один per-track lock и для стрима, и для фонового download: длительный Range-
# запрос тогда блокирует офлайн-сохранение этого же трека.
_cache_locks: Dict[int, asyncio.Lock] = {}


def _get_cache_lock(track_id: int) -> asyncio.Lock:
    lock = _cache_locks.get(track_id)
    if lock is None:
        lock = asyncio.Lock()
        _cache_locks[track_id] = lock
    return lock


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
        if not session_str:
            session_file = DATA_DIR.parent / "telegram_session.txt"
            if session_file.exists():
                session_str = session_file.read_text(encoding="utf-8").strip()

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
    Определяет Telegram Entity канала по ID, автопоиском в диалогах или по username.
    Автоматически находит канал «Музыка ДИТ» с аудиофайлами.
    """
    channel_id_env = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if channel_id_env:
        try:
            cid = int(channel_id_env)
            return await client.get_entity(cid)
        except Exception:
            pass

    # Явно настроенный username важнее эвристического поиска и старых каналов.
    channel_user_env = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip().replace("@", "")
    if channel_user_env:
        try:
            return await client.get_entity(channel_user_env)
        except Exception:
            pass

    # Поиск среди диалогов пользователя — только резервный вариант.
    try:
        candidates = []
        async for d in client.iter_dialogs(limit=50):
            if d.name and "музыка дит" in d.name.lower():
                candidates.append(d)

        # Выбираем тот канал, где есть реальные аудиофайлы
        for cand in candidates:
            async for m in client.iter_messages(cand.entity, limit=10):
                if m.media and getattr(m.media, "document", None) and (getattr(m.media.document, "mime_type", "") or "").startswith("audio/"):
                    return cand.entity

        if candidates:
            return candidates[0].entity
    except Exception:
        pass

    # Попытка через invite link если задан.
    invite_env = os.getenv("TELEGRAM_CHANNEL_INVITE", "").strip()
    if invite_env:
        try:
            return await client.get_entity(invite_env)
        except Exception:
            pass

    raise RuntimeError("Не удалось определить Telegram-канал. Проверьте TELEGRAM_CHANNEL_ID или TELEGRAM_CHANNEL_USERNAME.")


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
    updated_tracks_count = 0
    total_found = 0
    scanned_messages = 0
    media_messages = 0
    skipped_media = 0
    skipped_examples: List[Dict[str, Any]] = []

    try:
        # Сканируем сообщения канала
        async for message in client.iter_messages(channel, limit=None):
            scanned_messages += 1
            if getattr(message, "media", None):
                media_messages += 1
            meta = extract_metadata(message)
            if not meta:
                if getattr(message, "media", None):
                    skipped_media += 1
                    if len(skipped_examples) < 20:
                        document = getattr(message.media, "document", None)
                        attrs = getattr(document, "attributes", []) if document else []
                        file_obj = getattr(message, "file", None)
                        skipped_examples.append({
                            "message_id": getattr(message, "id", None),
                            "media_type": message.media.__class__.__name__,
                            "mime_type": getattr(document, "mime_type", "") if document else "",
                            "file_name": getattr(file_obj, "name", "") if file_obj else "",
                            "attributes": [a.__class__.__name__ for a in attrs],
                            "reason": "Файл не распознан как поддерживаемое аудио",
                        })
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
                else:
                    conn.execute("""
                        UPDATE tracks SET
                            document_id=?, access_hash=?, file_reference=?, title=?, artist=?,
                            album=?, duration=?, file_size=?, mime_type=?, file_name=?, date=?,
                            caption=?, has_cover=?
                        WHERE telegram_msg_id=?
                    """, (
                        meta["document_id"], meta["access_hash"], meta["file_reference"],
                        meta["title"], meta["artist"], meta["album"], meta["duration"],
                        meta["file_size"], meta["mime_type"], meta["file_name"], meta["date"],
                        meta["caption"], meta["has_cover"], meta["telegram_msg_id"]
                    ))
                    updated_tracks_count += 1

        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_sync', ?)", (now_str,))
            conn.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('channel_id', ?)", (str(getattr(channel, 'id', '')),))

        total_in_db = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

        return {
            "status": "ok",
            "connected": True,
            "channel_title": getattr(channel, "title", "Музыка ДИТ"),
            "channel_id": getattr(channel, "id", None),
            "new_tracks": new_tracks_count,
            "updated_tracks": updated_tracks_count,
            "total_tracks": total_in_db,
            "scanned_messages": scanned_messages,
            "media_messages": media_messages,
            "audio_found": total_found,
            "skipped_media": skipped_media,
            "skipped_examples": skipped_examples,
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
        has_session = bool(os.getenv("TELEGRAM_SESSION", "").strip() or (DATA_DIR.parent / "telegram_session.txt").exists())
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

    document = None
    # 1. Попытка получить из основного канала
    try:
        channel = await get_channel_entity(client)
        if channel:
            message = await client.get_messages(channel, ids=track["telegram_msg_id"])
            if message and getattr(message, "media", None):
                document = getattr(message.media, "document", None)
    except Exception:
        pass

    return track, document


def _cache_limit_bytes() -> int:
    try:
        mb = max(64, int(os.getenv("MUSIC_SERVER_CACHE_MB", "256")))
    except ValueError:
        mb = 256
    return mb * 1024 * 1024


def _prune_music_cache(protected: Optional[Path] = None) -> None:
    """Удаляет самые старые серверные аудиофайлы при превышении лимита."""
    MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in MUSIC_CACHE_DIR.glob("track_*.bin") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    limit = _cache_limit_bytes()
    for path in sorted(files, key=lambda p: p.stat().st_mtime):
        if total <= limit:
            break
        if protected and path == protected:
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            total -= size
        except OSError:
            continue


async def ensure_track_cached(track_id: int) -> Path:
    """Надёжно загружает Telegram-документ один раз и возвращает локальный файл.

    Стрим и офлайн-скачивание используют один и тот же проверенный файл, поэтому
    браузер всегда получает ровно заявленный Content-Length.
    """
    track = get_track_by_id(track_id)
    if not track:
        raise FileNotFoundError(f"Track {track_id} not found")

    MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    final_path = MUSIC_CACHE_DIR / f"track_{track_id}_{track['telegram_msg_id']}.bin"
    expected_db_size = int(track.get("file_size") or 0)
    if final_path.exists() and final_path.stat().st_size > 0:
        if not expected_db_size or final_path.stat().st_size == expected_db_size:
            final_path.touch()
            return final_path
        final_path.unlink(missing_ok=True)

    async with _get_cache_lock(track_id):
        if final_path.exists() and final_path.stat().st_size > 0:
            if not expected_db_size or final_path.stat().st_size == expected_db_size:
                final_path.touch()
                return final_path
            final_path.unlink(missing_ok=True)

        live_track, document = await get_telegram_document_for_track(track_id)
        if not document:
            raise FileNotFoundError(f"Telegram document for track {track_id} is unavailable")
        expected_size = int(getattr(document, "size", 0) or expected_db_size)
        client = await get_telegram_client()
        if not client:
            raise RuntimeError("Telegram client is not authorized")

        part_path = final_path.with_suffix(".part")
        part_path.unlink(missing_ok=True)
        written = 0
        try:
            with part_path.open("wb") as output:
                async for chunk in client.iter_download(document, chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    output.write(chunk)
                    written += len(chunk)
            if written <= 0 or (expected_size > 0 and written != expected_size):
                raise IOError(f"Incomplete Telegram file: expected={expected_size}, received={written}")
            os.replace(part_path, final_path)
            if expected_db_size != written:
                conn = get_db_connection()
                try:
                    with conn:
                        conn.execute("UPDATE tracks SET file_size=? WHERE id=?", (written, track_id))
                finally:
                    conn.close()
            _prune_music_cache(protected=final_path)
            return final_path
        except BaseException:
            part_path.unlink(missing_ok=True)
            raise


async def read_cached_track_chunks(
    path: Path, start: int, length: int, chunk_size: int = 256 * 1024
) -> AsyncGenerator[bytes, None]:
    """Отдаёт точный диапазон байтов из проверенного локального файла."""
    remaining = max(0, int(length))
    with path.open("rb") as source:
        source.seek(max(0, int(start)))
        while remaining > 0:
            chunk = source.read(min(chunk_size, remaining))
            if not chunk:
                raise IOError("Cached music file ended before requested range")
            remaining -= len(chunk)
            yield chunk


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
    path = await ensure_track_cached(track_id)
    async for chunk in read_cached_track_chunks(path, start, length, chunk_size):
        yield chunk


async def download_full_track(track_id: int) -> AsyncGenerator[bytes, None]:
    """Потоковая отдача полного аудиофайла для сохранения в OPFS/IndexedDB."""
    path = await ensure_track_cached(track_id)
    file_size = path.stat().st_size
    async for chunk in read_cached_track_chunks(path, start=0, length=file_size):
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
