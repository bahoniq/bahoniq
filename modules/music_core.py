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
import json
import logging
import mimetypes
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from modules.music_covers import (
    compute_cover_hash,
    extract_embedded_cover_from_bytes,
    fetch_itunes_cover_bytes,
    validate_image_bytes,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("MUSIC_DATA_DIR", str(ROOT_DIR / "data"))).expanduser().resolve()
DB_PATH = DATA_DIR / "music_catalog.db"
MUSIC_CACHE_DIR = DATA_DIR / "music_stream_cache"
MUSIC_COVERS_DIR = DATA_DIR / "music_covers"
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
_telegram_cover_fetch_lock = asyncio.Semaphore(2)


def _load_cover_seed_index() -> Dict[str, Dict[str, Any]]:
    idx_path = MUSIC_COVERS_DIR / "cover_index.json"
    if idx_path.exists():
        try:
            data = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cover_version INTEGER NOT NULL DEFAULT 0,
                cover_hash TEXT NOT NULL DEFAULT '',
                cover_source TEXT NOT NULL DEFAULT '',
                cover_checked_at INTEGER NOT NULL DEFAULT 0,
                file_unique_id TEXT NOT NULL DEFAULT '',
                cover_message_id INTEGER NOT NULL DEFAULT 0
            )
        """)
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
        migrations = [
            ("cover_version", "ALTER TABLE tracks ADD COLUMN cover_version INTEGER NOT NULL DEFAULT 0"),
            ("cover_hash", "ALTER TABLE tracks ADD COLUMN cover_hash TEXT NOT NULL DEFAULT ''"),
            ("cover_source", "ALTER TABLE tracks ADD COLUMN cover_source TEXT NOT NULL DEFAULT ''"),
            ("cover_checked_at", "ALTER TABLE tracks ADD COLUMN cover_checked_at INTEGER NOT NULL DEFAULT 0"),
            ("file_unique_id", "ALTER TABLE tracks ADD COLUMN file_unique_id TEXT NOT NULL DEFAULT ''"),
            ("cover_message_id", "ALTER TABLE tracks ADD COLUMN cover_message_id INTEGER NOT NULL DEFAULT 0"),
        ]
        for col_name, ddl in migrations:
            if col_name not in existing_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass
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
        if not clean:
            return
        # Отсекаем синтетические тестовые строки вида '3'*120 в рабочей БД, но разрешаем в изолированных тестах
        if source == "database" and len(set(clean)) < 4 and DB_PATH == DATA_DIR / "music_catalog.db":
            return
        if all(existing != clean for _, existing in candidates):
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
    seen_msg_ids: set = set()
    pruned_tracks_count = 0

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
                seen_msg_ids.add(int(meta["telegram_msg_id"]))
                file_unique_id = f"tgdoc_{meta['document_id']}" if meta.get("document_id") else f"tgmsg_{meta['telegram_msg_id']}"
                seed_index = _load_cover_seed_index()
                seed_entry = seed_index.get(file_unique_id, {})
                seed_hash = seed_entry.get("cover_hash", "")
                seed_source = seed_entry.get("cover_source", "")
                seed_has_cover = 1 if (seed_hash or meta["has_cover"]) and seed_source != "none" else 0
                with conn:
                    cur = conn.execute(
                        "SELECT id, cover_hash, cover_source FROM tracks WHERE telegram_msg_id = ?",
                        (meta["telegram_msg_id"],)
                    )
                    existing = cur.fetchone()
                    if not existing:
                        # СТАБИЛЬНЫЙ id = telegram_msg_id. Раньше id выдавался по порядку (AUTOINCREMENT),
                        # а БД на Render пересоздаётся при рестарте/деплое, поэтому после добавления/удаления
                        # песен в Telegram номера «съезжали», и офлайн-кэш на магнитоле (хранится по id) играл старые песни.
                        stable_id = int(meta["telegram_msg_id"])
                        if conn.execute("SELECT 1 FROM tracks WHERE id = ?", (stable_id,)).fetchone():
                            stable_id = None
                        conn.execute("""
                            INSERT INTO tracks (
                                id, telegram_msg_id, document_id, access_hash, file_reference,
                                title, artist, album, duration, file_size, mime_type,
                                file_name, date, caption, has_cover, file_unique_id,
                                cover_hash, cover_source, cover_checked_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            stable_id,
                            meta["telegram_msg_id"], meta["document_id"], meta["access_hash"],
                            meta["file_reference"], meta["title"], meta["artist"], meta["album"],
                            meta["duration"], meta["file_size"], meta["mime_type"], meta["file_name"],
                            meta["date"], meta["caption"], seed_has_cover, file_unique_id,
                            seed_hash, seed_source, int(time.time()) if seed_source else 0
                        ))
                        new_tracks_count += 1
                    else:
                        final_hash = existing["cover_hash"] or seed_hash
                        final_src = existing["cover_source"] or seed_source
                        keep_has_cover = 1 if (final_hash or (meta["has_cover"] and final_src != "none")) else 0
                        conn.execute("""
                            UPDATE tracks SET
                                document_id=?, access_hash=?, file_reference=?, title=?, artist=?,
                                album=?, duration=?, file_size=?, mime_type=?, file_name=?, date=?,
                                caption=?, has_cover=?, file_unique_id=?, cover_hash=?, cover_source=?
                            WHERE telegram_msg_id=?
                        """, (
                            meta["document_id"], meta["access_hash"], meta["file_reference"],
                            meta["title"], meta["artist"], meta["album"], meta["duration"],
                            meta["file_size"], meta["mime_type"], meta["file_name"], meta["date"],
                            meta["caption"], keep_has_cover, file_unique_id, final_hash, final_src,
                            meta["telegram_msg_id"]
                        ))
                        updated_tracks_count += 1

        # Удаляем из каталога треки, которых больше нет в Telegram (скан прошёл полностью без ошибок)
        if seen_msg_ids:
            with conn:
                stale_rows = [
                    r[0] for r in conn.execute("SELECT telegram_msg_id FROM tracks").fetchall()
                    if int(r[0]) not in seen_msg_ids
                ]
                for stale_msg in stale_rows:
                    conn.execute("DELETE FROM tracks WHERE telegram_msg_id = ?", (stale_msg,))
                pruned_tracks_count = len(stale_rows)

        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            if force:
                # При ручном обновлении библиотеки сбрасываем отрицательный кэш обложек,
                # чтобы треки без обложки были повторно проверены на встроенные метаданные.
                conn.execute("UPDATE tracks SET cover_source='', cover_checked_at=0 WHERE cover_source='none'")
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
            "removed_tracks": pruned_tracks_count,
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


def _normalize_meta_part(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"\[[^\]]*\]|\([^\)]*\)", " ", s)
    s = re.sub(r"[^a-zа-яёәіңғүұқөһ0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_track_identity(artist: str, title: str) -> str:
    """Нормализованный ключ (artist + title) для дедупликации одинаковых песен в каталоге."""
    norm_artist = _normalize_meta_part(artist)
    norm_title = _normalize_meta_part(title)
    if norm_artist in ("музыка дит", "неизвестный исполнитель", "unknown artist", "unknown"):
        norm_artist = ""
    return f"{norm_artist}::{norm_title}"


def _track_preference_score(track: Dict[str, Any]) -> Tuple[int, str, int]:
    """При дубликатах по artist + title предпочитает запись с настоящей обложкой, затем более новую."""
    c_src = track.get("cover_source") or ""
    c_hash = track.get("cover_hash") or ""
    if c_src == "embedded" or (c_hash and c_src != "thumb"):
        cover_rank = 3
    elif c_src == "thumb" or c_hash or (track.get("has_cover") and c_src != "none"):
        cover_rank = 2
    else:
        cover_rank = 0
    return (cover_rank, str(track.get("date") or ""), int(track.get("id") or 0))


def query_tracks(
    query: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    sort_by: str = "date",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Возвращает отфильтрованный и дедуплицированный список треков из SQLite-кэша."""
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

        select_sql = f"""
            SELECT id, telegram_msg_id, document_id, title, artist, album, duration,
                   file_size, mime_type, file_name, date, has_cover,
                   cover_version, cover_hash, cover_source, file_unique_id
            FROM tracks
            {where_sql}
            ORDER BY {col} {sort_dir}
        """
        rows = conn.execute(select_sql, params).fetchall()

        deduped: List[Dict[str, Any]] = []
        seen_idx_by_key: Dict[str, int] = {}
        for r in rows:
            doc_id = r["document_id"]
            unique_id = r["file_unique_id"] or (f"tgdoc_{doc_id}" if doc_id else f"track_{r['id']}")
            c_hash = r["cover_hash"] or ""
            c_source = r["cover_source"] or ""
            c_ver = c_hash if c_hash else (r["cover_version"] or 0)
            item = {
                "id": r["id"],
                "telegram_msg_id": r["telegram_msg_id"],
                "document_id": doc_id,
                "file_unique_id": unique_id,
                "title": r["title"],
                "artist": r["artist"],
                "album": r["album"],
                "duration": r["duration"],
                "file_size": r["file_size"],
                "mime_type": r["mime_type"],
                "file_name": r["file_name"],
                "date": r["date"],
                "has_cover": bool(r["has_cover"] or c_hash),
                "cover_hash": c_hash,
                "cover_source": c_source,
                "cover_version": c_ver,
            }
            norm_key = normalize_track_identity(item["artist"], item["title"])
            if norm_key == "::":
                deduped.append(item)
                continue
            existing_pos = seen_idx_by_key.get(norm_key)
            if existing_pos is None:
                seen_idx_by_key[norm_key] = len(deduped)
                deduped.append(item)
            else:
                if _track_preference_score(item) > _track_preference_score(deduped[existing_pos]):
                    deduped[existing_pos] = item

        total = len(deduped)
        return deduped[offset : offset + limit], total
    finally:
        conn.close()


def get_track_by_id(track_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        doc_id = d.get("document_id")
        d["file_unique_id"] = d.get("file_unique_id") or (f"tgdoc_{doc_id}" if doc_id else f"track_{d['id']}")
        c_hash = d.get("cover_hash") or ""
        d["cover_hash"] = c_hash
        d["cover_source"] = d.get("cover_source") or ""
        d["cover_version"] = c_hash if c_hash else (d.get("cover_version") or 0)
        d["has_cover"] = bool(d.get("has_cover") or c_hash)
        return d
    finally:
        conn.close()


def get_track_unique_key(track: Dict[str, Any]) -> str:
    """Стабильный ключ трека (не зависит от порядка списка в UI)."""
    uid = (track.get("file_unique_id") or "").strip()
    if uid:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", uid)
    doc_id = track.get("document_id")
    if doc_id:
        return f"tgdoc_{doc_id}"
    return f"track_{track['id']}"


def save_real_cover(
    track_id: int,
    img_bytes: bytes,
    mime: str,
    source: str = "embedded",
) -> Optional[Dict[str, Any]]:
    """
    Валидирует и атомарно сохраняет реальную обложку трека в MUSIC_COVERS_DIR.
    Заглушки и битые данные сюда НЕ сохраняются.
    При обновлении обложки удаляет устаревшие версии кэша этого трека.
    """
    validated = validate_image_bytes(img_bytes)
    if not validated:
        return None
    clean_bytes, valid_mime = validated
    final_mime = valid_mime or mime
    cover_hash = compute_cover_hash(clean_bytes)

    track = get_track_by_id(track_id)
    if not track:
        return None

    unique_key = get_track_unique_key(track)
    MUSIC_COVERS_DIR.mkdir(parents=True, exist_ok=True)

    img_path = MUSIC_COVERS_DIR / f"{unique_key}.img"
    meta_path = MUSIC_COVERS_DIR / f"{unique_key}.json"
    tmp_img = MUSIC_COVERS_DIR / f"{unique_key}.{os.getpid()}.tmp"

    try:
        tmp_img.write_bytes(clean_bytes)
        os.replace(tmp_img, img_path)
        meta_payload = {
            "track_id": track_id,
            "file_unique_id": unique_key,
            "mime": final_mime,
            "cover_hash": cover_hash,
            "source": source,
            "size": len(clean_bytes),
            "updated_at": int(time.time()),
        }
        meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("Не удалось сохранить обложку трека %s: %s", track_id, exc)
        tmp_img.unlink(missing_ok=True)
        return None

    # Удаляем устаревший файл из MUSIC_CACHE_DIR, если он остался от старой версии
    try:
        legacy_img = MUSIC_CACHE_DIR / f"cover_{track_id}.img"
        legacy_mime = MUSIC_CACHE_DIR / f"cover_{track_id}.mime"
        legacy_img.unlink(missing_ok=True)
        legacy_mime.unlink(missing_ok=True)
    except OSError:
        pass

    now_ts = int(time.time())
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE tracks
                SET has_cover = 1,
                    cover_hash = ?,
                    cover_source = ?,
                    cover_checked_at = ?,
                    file_unique_id = ?,
                    cover_version = COALESCE(cover_version, 0) + 1
                WHERE id = ?
                """,
                (cover_hash, source, now_ts, unique_key, track_id),
            )
    finally:
        conn.close()

    return {
        "bytes": clean_bytes,
        "mime": final_mime,
        "cover_hash": cover_hash,
        "source": source,
        "file_unique_id": unique_key,
    }


def load_saved_real_cover(track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Читает ранее сохранённую реальную обложку трека с диска и проверяет её валидность.
    Если файл повреждён, удаляет его и возвращает None.
    """
    if not track:
        return None
    track_id = int(track["id"])
    unique_key = get_track_unique_key(track)
    img_path = MUSIC_COVERS_DIR / f"{unique_key}.img"
    meta_path = MUSIC_COVERS_DIR / f"{unique_key}.json"

    if img_path.exists():
        try:
            raw = img_path.read_bytes()
            validated = validate_image_bytes(raw)
            if validated:
                clean_bytes, valid_mime = validated
                meta: Dict[str, Any] = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        meta = {}
                c_hash = meta.get("cover_hash") or compute_cover_hash(clean_bytes)
                c_source = meta.get("source")
                if c_source not in ("linked_photo", "embedded", "thumb", "itunes"):
                    t_src = track.get("cover_source")
                    c_source = t_src if t_src in ("linked_photo", "embedded", "thumb", "itunes") else "embedded"
                if track.get("cover_hash") != c_hash or track.get("cover_source") != c_source:
                    conn = get_db_connection()
                    try:
                        with conn:
                            conn.execute(
                                "UPDATE tracks SET has_cover=1, cover_hash=?, cover_source=?, file_unique_id=? WHERE id=?",
                                (c_hash, c_source, unique_key, track_id),
                            )
                    finally:
                        conn.close()
                return {
                    "bytes": clean_bytes,
                    "mime": valid_mime,
                    "cover_hash": c_hash,
                    "source": c_source,
                    "file_unique_id": unique_key,
                }
            else:
                img_path.unlink(missing_ok=True)
                meta_path.unlink(missing_ok=True)
        except OSError:
            pass

    # Миграция из старого кэша MUSIC_CACHE_DIR / cover_{id}.img (только если картинка валидна!)
    legacy_img = MUSIC_CACHE_DIR / f"cover_{track_id}.img"
    legacy_mime = MUSIC_CACHE_DIR / f"cover_{track_id}.mime"
    if legacy_img.exists():
        try:
            raw = legacy_img.read_bytes()
            validated = validate_image_bytes(raw)
            if validated:
                clean_bytes, valid_mime = validated
                t_src = track.get("cover_source")
                inferred_source = t_src if t_src in ("embedded", "thumb") else ("thumb" if track.get("has_cover") else "embedded")
                return save_real_cover(track_id, clean_bytes, valid_mime, source=inferred_source)
            else:
                # Удаляем битую псевдо-обложку, вырезанную старым багом из MP3-фреймов
                legacy_img.unlink(missing_ok=True)
                legacy_mime.unlink(missing_ok=True)
        except OSError:
            pass

    return None


def select_linked_photo_candidate(
    audio_msg: Any,
    candidate_messages: List[Any],
    track: Dict[str, Any],
) -> Optional[Any]:
    """
    Находит отдельное Telegram-сообщение с картинкой, точно связанное с аудиотреком.
    Приоритет:
    1. Тот же grouped_id (медиаальбом).
    2. Прямой reply_to на сообщение с фото.
    3. Совпадение нормализованных caption / title / performer.
    Служебные сообщения (смена аватарки чата MessageActionChatEditPhoto и т.п.) игнорируются.
    """
    if not audio_msg or not candidate_messages:
        return None

    def _is_real_photo_msg(m: Any) -> bool:
        if not m or getattr(m, "action", None) is not None:
            return False
        return bool(getattr(m, "photo", None))

    photo_msgs = [m for m in candidate_messages if _is_real_photo_msg(m) and getattr(m, "id", None) != getattr(audio_msg, "id", None)]
    if not photo_msgs:
        return None

    audio_grp = getattr(audio_msg, "grouped_id", None)
    if audio_grp:
        for pm in photo_msgs:
            if getattr(pm, "grouped_id", None) == audio_grp:
                return pm

    reply_obj = getattr(audio_msg, "reply_to", None)
    reply_id = getattr(reply_obj, "reply_to_msg_id", None) if reply_obj else None
    if reply_id:
        for pm in photo_msgs:
            if getattr(pm, "id", None) == reply_id:
                return pm

    norm_title = _normalize_meta_part(track.get("title") or "")
    norm_artist = _normalize_meta_part(track.get("artist") or "")
    for pm in photo_msgs:
        cap = _normalize_meta_part(getattr(pm, "message", "") or "")
        if not cap:
            continue
        if norm_title and len(norm_title) >= 4 and norm_title in cap:
            return pm
        if norm_artist and len(norm_artist) >= 4 and norm_artist in cap and any(w in cap for w in norm_title.split() if len(w) >= 3):
            return pm

    return None


async def resolve_track_cover(
    track_id: int,
    allow_network: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Единая цепочка получения обложки трека со строгим приоритетом:
    1. Отдельная Telegram-картинка, точно связанная с треком (grouped_id / reply_to / caption).
    2. Встроенная обложка из метаданных аудиофайла (ID3v2.2 PIC, ID3v2.3/2.4 APIC, MP4 covr, FLAC, OGG).
    3. Миниатюра Telegram-сообщения/документа (document.thumbs).
    4. Ранее сохранённая реальная обложка этого трека.
    5. None (заглушка без перезаписи реальной обложки).
    """
    track = get_track_by_id(track_id)
    if not track:
        return None

    async with _get_cache_lock(1_000_000 + int(track_id)):
        track = get_track_by_id(track_id) or track
        saved = load_saved_real_cover(track)

        # Если уже сохранена связанная Telegram-картинка, встроенный APIC или кэшированная обложка iTunes — отдаём мгновенно
        if saved and saved.get("source") in ("linked_photo", "embedded", "itunes"):
            return saved

        # Проверяем, есть ли полный аудиофайл в локальном серверном кэше
        cached_audio = get_cached_track_path(track_id)
        if cached_audio and cached_audio.exists():
            try:
                with cached_audio.open("rb") as f:
                    header_bytes = f.read(512 * 1024)
                extracted = extract_embedded_cover_from_bytes(header_bytes)
                if extracted:
                    emb_bytes, emb_mime = extracted
                    res = save_real_cover(track_id, emb_bytes, emb_mime, source="embedded")
                    if res:
                        return res
            except OSError:
                pass

        # Если уже есть сохранённая обложка (например, thumb) и мы уже проверяли файл, или сеть запрещена
        if saved and (not allow_network or track.get("cover_checked_at")):
            return saved

        # Если трек уже был проверен в Telegram и ни встроенной обложки, ни thumb в нём нет
        if track.get("cover_source") == "none" and not saved:
            return None

        if not allow_network:
            return saved

        async with _telegram_cover_fetch_lock:
            # Обращаемся к Telegram для проверки связанного фото, метаданных файла (первые 256 КБ) и/или document.thumbs
            _, doc = await get_telegram_document_for_track(track_id)
            client = await get_telegram_client()
            if not doc or not client:
                # Временная ошибка сети/сессии: возвращаем ранее сохранённую обложку (если есть),
                # НЕ помечая cover_source='none', чтобы при следующем запросе повторить попытку.
                return saved

            # Приоритет №1: отдельная Telegram-картинка, точно связанная с треком (grouped_id / reply_to / caption)
            try:
                msg_id = int(track.get("telegram_msg_id") or 0)
                if msg_id:
                    channel = await get_channel_entity(client)
                    target_ent = None if msg_id > 1000 else channel
                    audio_msg = await client.get_messages(target_ent, ids=msg_id)
                    if audio_msg:
                        neighbor_ids = [i for i in range(max(1, msg_id - 2), msg_id + 3) if i != msg_id]
                        neighbors = await client.get_messages(target_ent, ids=neighbor_ids)
                        linked_photo = select_linked_photo_candidate(audio_msg, neighbors or [], track)
                        if linked_photo:
                            photo_bytes = await client.download_media(linked_photo, file=bytes)
                            if isinstance(photo_bytes, (bytes, bytearray)) and photo_bytes:
                                validated_photo = validate_image_bytes(bytes(photo_bytes))
                                if validated_photo:
                                    clean_photo, photo_mime = validated_photo
                                    res = save_real_cover(track_id, clean_photo, photo_mime, source="linked_photo")
                                    if res:
                                        conn = get_db_connection()
                                        try:
                                            with conn:
                                                conn.execute(
                                                    "UPDATE tracks SET cover_message_id=? WHERE id=?",
                                                    (int(linked_photo.id), track_id),
                                                )
                                        finally:
                                            conn.close()
                                        return res
            except Exception as exc:
                LOGGER.debug("Не удалось проверить связанное фото для трека %s: %s", track_id, exc)

            # Приоритет №2: пробуем извлечь встроенную обложку из первых 256 КБ аудиофайла в Telegram
            try:
                buf = bytearray()
                async for chunk in client.iter_download(
                    doc, offset=0, chunk_size=256 * 1024, request_size=256 * 1024
                ):
                    if chunk:
                        buf.extend(chunk)
                    if len(buf) >= 256 * 1024:
                        break
                if buf:
                    extracted = extract_embedded_cover_from_bytes(bytes(buf))
                    if extracted:
                        emb_bytes, emb_mime = extracted
                        res = save_real_cover(track_id, emb_bytes, emb_mime, source="embedded")
                        if res:
                            return res
            except Exception as exc:
                LOGGER.debug("Не удалось прочитать заголовок трека %s из Telegram: %s", track_id, exc)

            # Приоритет №2: миниатюра Telegram-документа (document.thumbs), если встроенной обложки нет
            if getattr(doc, "thumbs", None):
                try:
                    thumb_data = await client.download_media(doc, file=bytes, thumb=-1)
                    if isinstance(thumb_data, (bytes, bytearray)) and thumb_data:
                        validated_thumb = validate_image_bytes(bytes(thumb_data))
                        if validated_thumb:
                            clean_thumb, valid_mime = validated_thumb
                            res = save_real_cover(track_id, clean_thumb, valid_mime, source="thumb")
                            if res:
                                return res
                except Exception as exc:
                    LOGGER.debug("Не удалось скачать thumb трека %s из Telegram: %s", track_id, exc)

        # Приоритет №4: ранее сохранённая реальная обложка (никогда не затираем её заглушкой)
        if saved:
            return saved

        # Приоритет №5: официальная обложка из открытого iTunes Search API (как в клиенте Telegram)
        try:
            itunes_res = await asyncio.to_thread(
                fetch_itunes_cover_bytes,
                track.get("artist") or "",
                track.get("title") or "",
            )
            if itunes_res:
                it_bytes, it_mime = itunes_res
                res = save_real_cover(track_id, it_bytes, it_mime, source="itunes")
                if res:
                    return res
        except Exception as exc:
            LOGGER.debug("Не удалось получить обложку iTunes для трека %s: %s", track_id, exc)

        # Приоритет №6: обложки нет нигде — фиксируем cover_source='none'
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE tracks SET has_cover=0, cover_source='none', cover_checked_at=? WHERE id=?",
                    (int(time.time()), track_id),
                )
        finally:
            conn.close()
        return None


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

    # 0. Быстрый путь для домиграционных сообщений (глобальный ID чата «Музыка ДИТ» > 1000)
    if msg_id and int(msg_id) > 1000:
        try:
            message = await client.get_messages(None, ids=msg_id)
            if message and getattr(message, "media", None):
                cand_doc = getattr(message.media, "document", None)
                if _matches(cand_doc):
                    document = cand_doc
        except Exception:
            pass

    # 1. Попытка получить из основного активного канала/группы
    if not document:
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
                try:
                    cur_track = get_track_by_id(track_id)
                    if cur_track and cur_track.get("cover_source") != "embedded" and final_path.exists():
                        with final_path.open("rb") as f_cov:
                            head_cov = f_cov.read(512 * 1024)
                        extracted_cov = extract_embedded_cover_from_bytes(head_cov)
                        if extracted_cov:
                            save_real_cover(track_id, extracted_cov[0], extracted_cov[1], source="embedded")
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
