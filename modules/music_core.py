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
DATA_DIR = Path(os.getenv("MUSIC_DATA_DIR", str(ROOT_DIR / "data"))).expanduser().resolve()
DB_PATH = DATA_DIR / "music_catalog.db"
MUSIC_CACHE_DIR = DATA_DIR / "music_stream_cache"
SESSION_FILE = Path(
    os.getenv("TELEGRAM_SESSION_FILE", str(DATA_DIR.parent / "telegram_session.txt"))
).expanduser().resolve()
LOGGER = logging.getLogger(__name__)

# Автоматическая подгрузка переменных окружения из .env
_ENV_FILE = ROOT_DIR / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE)
    except ImportError:
        pass

# Синглтон-клиент Telethon
_client = None
_client_lock = asyncio.Lock()
_cached_channel_entity = None
_cached_channel_client = None
_sync_lock = asyncio.Lock()
# Ограничиваем количество одновременных MTProto-загрузок. Нельзя использовать
# один per-track lock и для стрима, и для фонового download: длительный Range-
# запрос тогда блокирует офлайн-сохранение этого же трека.
_cache_locks: Dict[int, asyncio.Lock] = {}
_active_downloads: Dict[int, "_ProgressiveDownload"] = {}
_runtime_session_override = ""


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


def _session_candidates() -> List[Tuple[str, str]]:
    """Уникальные кандидаты сессии: свежая локальная раньше старой Render env."""
    candidates: List[Tuple[str, str]] = []

    def add(source: str, value: str) -> None:
        clean = (value or "").strip()
        if clean and all(existing != clean for _, existing in candidates):
            candidates.append((source, clean))

    add("runtime", _runtime_session_override)
    try:
        if SESSION_FILE.exists():
            add("file", SESSION_FILE.read_text(encoding="utf-8"))
    except OSError as exc:
        LOGGER.warning("Cannot read Telegram session file %s: %s", SESSION_FILE, exc)

    try:
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT value FROM sync_meta WHERE key='runtime_telegram_session'"
            ).fetchone()
            add("database", row[0] if row else "")
        finally:
            conn.close()
    except Exception as exc:
        LOGGER.warning("Cannot read Telegram session from database: %s", exc)

    add("environment", os.getenv("TELEGRAM_SESSION", ""))
    return candidates


def get_saved_telegram_session_str() -> str:
    """Возвращает наиболее свежую сохранённую строку сессии."""
    candidates = _session_candidates()
    return candidates[0][1] if candidates else ""


async def save_telegram_session_str(session_str: str) -> None:
    """Сохраняет новую строку сессии в sync_meta и локальный файл, и сбрасывает клиент для переподключения."""
    global _client, _cached_channel_entity, _cached_channel_client, _runtime_session_override
    clean = (session_str or "").strip()
    if len(clean) < 50:
        raise ValueError("Telegram StringSession is empty or malformed")
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('runtime_telegram_session', ?)",
                (clean,),
            )
    finally:
        conn.close()
    _runtime_session_override = clean
    os.environ["TELEGRAM_SESSION"] = clean
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SESSION_FILE.with_suffix(SESSION_FILE.suffix + ".tmp")
        tmp_path.write_text(clean, encoding="utf-8")
        os.replace(tmp_path, SESSION_FILE)
    except OSError as exc:
        LOGGER.warning("Cannot persist Telegram session to %s: %s", SESSION_FILE, exc)
    async with _client_lock:
        if _client is not None:
            try:
                await _client.disconnect()
            except Exception:
                pass
        _client = None
        _cached_channel_entity = None
        _cached_channel_client = None


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
    global _client, _cached_channel_entity, _cached_channel_client
    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        api_id_str = os.getenv("TELEGRAM_API_ID", "").strip()
        api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
        candidates = _session_candidates()

        if not api_id_str or not api_hash or not candidates:
            return None

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except ImportError:
            return None

        api_id = int(api_id_str)
        for source, session_str in candidates:
            client = None
            try:
                client = TelegramClient(StringSession(session_str), api_id, api_hash)
                await asyncio.wait_for(client.connect(), timeout=20)
                if not await asyncio.wait_for(client.is_user_authorized(), timeout=15):
                    await client.disconnect()
                    LOGGER.warning("Telegram session from %s is not authorized", source)
                    continue
                _client = client
                _cached_channel_entity = None
                _cached_channel_client = None
                os.environ["TELEGRAM_SESSION"] = session_str
                LOGGER.info("Telegram session restored from %s", source)
                return _client
            except Exception as exc:
                LOGGER.warning("Telegram session from %s failed: %s", source, exc)
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
        return None


async def reset_telegram_client() -> None:
    """Сбрасывает оборванное MTProto-соединение для автопереподключения."""
    global _client, _cached_channel_entity, _cached_channel_client
    async with _client_lock:
        old_client = _client
        _client = None
        _cached_channel_entity = None
        _cached_channel_client = None
        if old_client is not None:
            try:
                await old_client.disconnect()
            except Exception:
                pass


async def _entity_has_audio(client, entity) -> bool:
    """Проверяет наличие хотя бы одного аудиофайла в указанном канале или чате."""
    if not entity:
        return False
    try:
        async for m in client.iter_messages(entity, limit=15):
            if extract_metadata(m) is not None:
                return True
    except Exception:
        pass
    return False


async def get_channel_entity(client):
    """
    Определяет Telegram Entity канала по ID, автопоиском в диалогах или по username.
    Гарантированно выбирает чат/канал, в котором реально загружены аудиофайлы («Музыка ДИТ»).
    """
    global _cached_channel_entity, _cached_channel_client
    if _cached_channel_entity is not None and _cached_channel_client is client:
        return _cached_channel_entity

    fallback_entity = None

    channel_id_env = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if channel_id_env:
        try:
            cid = int(channel_id_env)
            ent = await client.get_entity(cid)
            if ent:
                if await _entity_has_audio(client, ent):
                    _cached_channel_entity = ent
                    _cached_channel_client = client
                    return ent
                fallback_entity = fallback_entity or ent
        except Exception:
            pass

    # 1. Поиск среди диалогов пользователя группы/канала «Музыка ДИТ» с реальными аудиофайлами
    try:
        candidates = []
        async for d in client.iter_dialogs(limit=50):
            if d.name and "музыка дит" in d.name.lower():
                candidates.append(d.entity)

        for cand in candidates:
            if await _entity_has_audio(client, cand):
                _cached_channel_entity = cand
                _cached_channel_client = client
                return cand

        if candidates and fallback_entity is None:
            fallback_entity = candidates[0]
    except Exception:
        pass

    # 2. Прямой ID чата с музыкой (-5288727334 — «Музыка ДИТ»)
    try:
        ent = await client.get_entity(-5288727334)
        if ent:
            if await _entity_has_audio(client, ent):
                _cached_channel_entity = ent
                _cached_channel_client = client
                return ent
            fallback_entity = fallback_entity or ent
    except Exception:
        pass

    # 3. По username канала (только если там реально есть аудио, либо как резерв)
    channel_user_env = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip().replace("@", "")
    if channel_user_env:
        try:
            ent = await client.get_entity(channel_user_env)
            if ent:
                if await _entity_has_audio(client, ent):
                    _cached_channel_entity = ent
                    _cached_channel_client = client
                    return ent
                fallback_entity = fallback_entity or ent
        except Exception:
            pass

    # 4. Попытка через invite link если задан.
    invite_env = os.getenv("TELEGRAM_CHANNEL_INVITE", "").strip()
    if invite_env:
        try:
            ent = await client.get_entity(invite_env)
            if ent:
                _cached_channel_entity = ent
                _cached_channel_client = client
                return ent
        except Exception:
            pass

    if fallback_entity is not None:
        _cached_channel_entity = fallback_entity
        _cached_channel_client = client
        return fallback_entity

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

    # Собираем все связанные сущности группы «Музыка ДИТ»:
    # когда обычной группе (Chat 5288727334) назначается публичная ссылка t.me/bahoniqmusic,
    # Telegram мигрирует её в супергруппу (Channel 4330974221), оставляя старые 100 песен в старом Chat ID,
    # а новые публикации складывая в новый Channel ID. Сканируем обе истории!
    entities_to_scan = [channel]
    seen_entity_ids = {getattr(channel, "id", None)}

    channel_user_env = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip().replace("@", "")
    if channel_user_env:
        try:
            pub_ent = await client.get_entity(channel_user_env)
            if pub_ent and getattr(pub_ent, "id", None) not in seen_entity_ids:
                entities_to_scan.insert(0, pub_ent)
                seen_entity_ids.add(getattr(pub_ent, "id", None))
        except Exception:
            pass

    try:
        old_chat = await client.get_entity(-5288727334)
        if old_chat and getattr(old_chat, "id", None) not in seen_entity_ids:
            entities_to_scan.append(old_chat)
            seen_entity_ids.add(getattr(old_chat, "id", None))
    except Exception:
        pass

    conn = get_db_connection()
    new_tracks_count = 0
    updated_tracks_count = 0
    total_found = 0
    scanned_messages = 0
    media_messages = 0
    skipped_media = 0
    skipped_examples: List[Dict[str, Any]] = []

    try:
        # Сканируем сообщения как новой супергруппы (t.me/bahoniqmusic), так и домиграционной истории чата
        for target_entity in entities_to_scan:
            async for message in client.iter_messages(target_entity, limit=None):
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
        has_session = bool(get_saved_telegram_session_str())
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


async def ensure_catalog_ready() -> None:
    """Если база треков пуста (например, после редеплоя Render), синхронизирует каталог один раз."""
    conn = get_db_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    finally:
        conn.close()
    if total > 0:
        return

    has_session = bool(get_saved_telegram_session_str())
    has_creds = bool(os.getenv("TELEGRAM_API_ID") and os.getenv("TELEGRAM_API_HASH"))
    if not (has_session and has_creds):
        return

    async with _sync_lock:
        conn = get_db_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        finally:
            conn.close()
        if total == 0:
            await sync_catalog(force=False)


async def get_telegram_document_for_track(track_id: int):
    """Находит сообщение и Telethon document для трека (включая как супергруппу t.me/bahoniqmusic, так и домиграционную историю чата «Музыка ДИТ»)."""
    track = get_track_by_id(track_id)
    if not track:
        return None, None

    client = await get_telegram_client()
    if not client:
        return track, None

    document = None
    msg_id = track["telegram_msg_id"]
    expected_doc_id = int(track.get("document_id") or 0)

    def _matches(doc) -> bool:
        if not doc:
            return False
        if expected_doc_id and getattr(doc, "id", 0) and int(getattr(doc, "id", 0)) != expected_doc_id:
            return False
        return True

    # 1. Попытка получить из основного активного канала/группы
    try:
        channel = await get_channel_entity(client)
        if channel:
            message = await client.get_messages(channel, ids=msg_id)
            if message and getattr(message, "media", None):
                cand_doc = getattr(message.media, "document", None)
                if _matches(cand_doc):
                    document = cand_doc
    except Exception:
        pass

    # 2. Попытка из публичной супергруппы t.me/bahoniqmusic (для новых треков после миграции)
    if not document:
        channel_user_env = os.getenv("TELEGRAM_CHANNEL_USERNAME", "bahoniqmusic").strip().replace("@", "")
        if channel_user_env:
            try:
                pub_ent = await client.get_entity(channel_user_env)
                if pub_ent:
                    message = await client.get_messages(pub_ent, ids=msg_id)
                    if message and getattr(message, "media", None):
                        cand_doc = getattr(message.media, "document", None)
                        if _matches(cand_doc):
                            document = cand_doc
            except Exception:
                pass

    # 3. Резервная попытка из домиграционного чата «Музыка ДИТ» (-5288727334)
    if not document:
        try:
            ent = await client.get_entity(-5288727334)
            if ent:
                message = await client.get_messages(ent, ids=msg_id)
                if message and getattr(message, "media", None):
                    cand_doc = getattr(message.media, "document", None)
                    if _matches(cand_doc):
                        document = cand_doc
        except Exception:
            pass

    # 4. Резервная попытка глобального поиска сообщения по ID
    if not document:
        try:
            message = await client.get_messages(None, ids=msg_id)
            if message and getattr(message, "media", None):
                cand_doc = getattr(message.media, "document", None)
                if _matches(cand_doc):
                    document = cand_doc
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


class _ProgressiveDownload:
    """Единый потоковый буфер загрузки трека из Telegram (как в нативном Telegram-плеере).

    Одновременно раздаёт первые чанки в онлайн-стрим (/stream) без ожидания конца файла
    и позволяет фоновому сохранению (/download) читать тот же самый поток без второго
    соединения к Telegram MTProto.
    """
    def __init__(self, track_id: int, final_path: Path, part_path: Path, expected_size: int):
        self.track_id = track_id
        self.final_path = final_path
        self.part_path = part_path
        self.expected_size = expected_size
        self.written = 0
        self.done = False
        self.error: Optional[BaseException] = None
        self.cond = asyncio.Condition()
        self.readers = 0
        self.task: Optional[asyncio.Task] = None


def get_cached_track_path(track_id: int) -> Optional[Path]:
    """Возвращает путь к уже полностью скачанному на сервер файлу трека, если он валиден."""
    track = get_track_by_id(track_id)
    if not track:
        return None
    final_path = MUSIC_CACHE_DIR / f"track_{track_id}_{track['telegram_msg_id']}.bin"
    expected_db_size = int(track.get("file_size") or 0)
    if final_path.exists() and final_path.stat().st_size >= 20000:
        actual_size = final_path.stat().st_size
        if not expected_db_size or actual_size == expected_db_size:
            final_path.touch()
            return final_path
        # Если локальный кэш валиден (например, WAV/MP3 заголовок), используем его как резерв
        try:
            with final_path.open("rb") as f:
                head = f.read(4)
            if head in (b"RIFF", b"ID3\x03", b"ID3\x04", b"\xff\xfb", b"\xff\xf3", b"OggS", b"fLaC"):
                final_path.touch()
                return final_path
        except OSError:
            pass
    return None


async def _start_or_join_progressive_download(track_id: int) -> _ProgressiveDownload:
    """Запускает единую фоновую загрузку трека в .part -> .bin или подключается к текущей."""
    track = get_track_by_id(track_id)
    if not track:
        raise FileNotFoundError(f"Track {track_id} not found")

    MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    final_path = MUSIC_CACHE_DIR / f"track_{track_id}_{track['telegram_msg_id']}.bin"
    expected_db_size = int(track.get("file_size") or 0)

    # Отменяем старые фоновые загрузки других треков, которые больше никто не слушает,
    # чтобы 100% канала Telegram MTProto отдавалось текущему треку.
    for other_id, other_state in list(_active_downloads.items()):
        if other_id != track_id and other_state.readers <= 0 and not other_state.done:
            if other_state.task and not other_state.task.done():
                other_state.task.cancel()
            _active_downloads.pop(other_id, None)

    async with _get_cache_lock(track_id):
        if final_path.exists() and final_path.stat().st_size > 0:
            if not expected_db_size or final_path.stat().st_size == expected_db_size:
                final_path.touch()
                done_state = _ProgressiveDownload(track_id, final_path, final_path.with_suffix(".part"), final_path.stat().st_size)
                done_state.written = done_state.expected_size
                done_state.done = True
                return done_state
            final_path.unlink(missing_ok=True)

        existing = _active_downloads.get(track_id)
        if existing is not None and not existing.done and existing.error is None:
            if existing.task and not existing.task.done():
                return existing

        live_track, document = await get_telegram_document_for_track(track_id)
        if not document:
            raise FileNotFoundError(f"Telegram document for track {track_id} is unavailable")
        expected_size = int(getattr(document, "size", 0) or expected_db_size)
        client = await get_telegram_client()
        if not client:
            raise RuntimeError("Telegram client is not authorized")

        part_path = final_path.with_suffix(".part")
        part_path.unlink(missing_ok=True)
        state = _ProgressiveDownload(track_id, final_path, part_path, expected_size)
        _active_downloads[track_id] = state

        async def _runner() -> Path:
            try:
                current_client = client
                current_document = document
                for attempt in range(2):
                    try:
                        state.error = None
                        state.written = 0
                        part_path.unlink(missing_ok=True)
                        with part_path.open("wb") as output:
                            async for chunk in current_client.iter_download(
                                current_document, chunk_size=256 * 1024
                            ):
                                if not chunk:
                                    continue
                                output.write(chunk)
                                output.flush()
                                state.written += len(chunk)
                                async with state.cond:
                                    state.cond.notify_all()
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as download_exc:
                        if attempt >= 1:
                            raise
                        LOGGER.warning(
                            "Telegram stream for track %s broke; reconnecting once: %s",
                            track_id,
                            download_exc,
                        )
                        await reset_telegram_client()
                        _, current_document = await get_telegram_document_for_track(track_id)
                        current_client = await get_telegram_client()
                        if current_client is None or current_document is None:
                            raise RuntimeError("Telegram reconnect failed") from download_exc

                if state.written <= 0 or (expected_size > 0 and state.written != expected_size):
                    raise IOError(f"Incomplete Telegram file: expected={expected_size}, received={state.written}")

                async with state.cond:
                    os.replace(part_path, final_path)
                    state.done = True
                    state.cond.notify_all()

                if expected_db_size != state.written:
                    try:
                        conn = get_db_connection()
                        try:
                            with conn:
                                conn.execute("UPDATE tracks SET file_size=? WHERE id=?", (state.written, track_id))
                        finally:
                            conn.close()
                    except Exception:
                        pass
                _prune_music_cache(protected=final_path)
                return final_path
            except BaseException as exc:
                state.error = exc
                part_path.unlink(missing_ok=True)
                async with state.cond:
                    state.cond.notify_all()
                raise
            finally:
                if _active_downloads.get(track_id) is state:
                    _active_downloads.pop(track_id, None)

        state.task = asyncio.create_task(_runner())
        return state


async def ensure_track_cached(track_id: int) -> Path:
    """Надёжно загружает Telegram-документ один раз и возвращает локальный файл."""
    cached = get_cached_track_path(track_id)
    if cached is not None:
        return cached

    state = await _start_or_join_progressive_download(track_id)
    if state.done and state.final_path.exists():
        return state.final_path
    state.readers += 1
    try:
        assert state.task is not None
        return await state.task
    finally:
        state.readers = max(0, state.readers - 1)


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
    Прогрессивный генератор чанков:
    - Если файл уже в серверном кэше (.bin) — отдаёт мгновенно с диска.
    - Если файл ещё качается из Telegram — отдаёт первые байты сразу по мере их прихода в .part,
      чтобы музыка начинала играть за ~1.5 секунды, одновременно дописывая файл в кэш.
    """
    cached = get_cached_track_path(track_id)
    if cached is not None:
        async for chunk in read_cached_track_chunks(cached, start, length, chunk_size):
            yield chunk
        return

    state = await _start_or_join_progressive_download(track_id)
    if state.done and state.final_path.exists():
        async for chunk in read_cached_track_chunks(state.final_path, start, length, chunk_size):
            yield chunk
        return

    state.readers += 1
    pos = max(0, int(start))
    end_pos = pos + max(0, int(length))
    try:
        while pos < end_pos:
            async with state.cond:
                while state.written <= pos and not state.done and state.error is None:
                    await state.cond.wait()
            if state.error is not None:
                raise state.error

            available = state.written
            if available <= pos:
                if state.done:
                    break
                await asyncio.sleep(0.02)
                continue

            to_read = min(chunk_size, end_pos - pos, available - pos)
            try:
                f_obj = state.final_path.open("rb") if state.final_path.exists() else state.part_path.open("rb")
            except FileNotFoundError:
                f_obj = state.final_path.open("rb") if state.final_path.exists() else state.part_path.open("rb")
            with f_obj as source:
                source.seek(pos)
                data = source.read(to_read)
            if not data:
                if state.done:
                    break
                await asyncio.sleep(0.02)
                continue
            pos += len(data)
            yield data
    finally:
        state.readers = max(0, state.readers - 1)


async def download_full_track(track_id: int) -> AsyncGenerator[bytes, None]:
    """Потоковая отдача полного аудиофайла для сохранения в OPFS/IndexedDB (без дублирования загрузки из Telegram)."""
    cached = get_cached_track_path(track_id)
    if cached is not None:
        file_size = cached.stat().st_size
        async for chunk in read_cached_track_chunks(cached, start=0, length=file_size):
            yield chunk
        return

    state = await _start_or_join_progressive_download(track_id)
    total_size = state.expected_size
    if total_size <= 0 and state.task is not None:
        final_path = await ensure_track_cached(track_id)
        total_size = final_path.stat().st_size
    async for chunk in stream_track_chunks(track_id, start=0, length=total_size, chunk_size=256 * 1024):
        yield chunk


def clear_catalog_cache():
    """Очищает кэш метаданных SQLite (восстановимый кэш, сохраняет runtime_telegram_session)."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM tracks")
            conn.execute("DELETE FROM sync_meta WHERE key != 'runtime_telegram_session'")
    finally:
        conn.close()
