"""
Автоматические тесты для модуля «Музыка в авто» (modules/music_core.py и web_app/routers/music.py).
Используются моки — реальные сетевые запросы к Telegram не выполняются.
"""
import io
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from modules.music_core import (
    clear_catalog_cache,
    extract_metadata,
    get_catalog_status,
    get_db_connection,
    get_track_by_id,
    query_tracks,
)


class DummyAudioAttr:
    def __init__(self, title, performer, duration=180):
        self.title = title
        self.performer = performer
        self.duration = duration


class DummyFilenameAttr:
    def __init__(self, file_name):
        self.file_name = file_name


class DummyDocument:
    def __init__(self, doc_id, size, mime_type, attributes, thumbs=None):
        self.id = doc_id
        self.size = size
        self.mime_type = mime_type
        self.attributes = attributes
        self.thumbs = thumbs or []
        self.access_hash = 123456789
        self.file_reference = b"dummy_ref"


class DummyMessage:
    def __init__(self, msg_id, document=None, message=""):
        self.id = msg_id
        self.media = SimpleNamespace(document=document) if document else None
        self.message = message
        self.date = SimpleNamespace(isoformat=lambda: "2026-11-17T12:00:00Z")


class TestMusicPlayer(unittest.TestCase):
    def setUp(self):
        # Используем временную SQLite-базу для каждого теста
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.patcher = patch("modules.music_core.DB_PATH", self.temp_db.name)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except OSError:
                pass

    def test_extract_metadata_with_audio_attributes(self):
        doc = DummyDocument(
            doc_id=101,
            size=5000000,
            mime_type="audio/mpeg",
            attributes=[DummyAudioAttr("Bohemian Rhapsody", "Queen", 354)]
        )
        msg = DummyMessage(msg_id=42, document=doc)
        meta = extract_metadata(msg)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "Bohemian Rhapsody")
        self.assertEqual(meta["artist"], "Queen")
        self.assertEqual(meta["duration"], 354)
        self.assertEqual(meta["file_size"], 5000000)
        self.assertEqual(meta["telegram_msg_id"], 42)

    def test_extract_metadata_fallback_to_filename(self):
        doc = DummyDocument(
            doc_id=102,
            size=4000000,
            mime_type="audio/mpeg",
            attributes=[DummyFilenameAttr("Daft Punk - One More Time.mp3")]
        )
        msg = DummyMessage(msg_id=43, document=doc)
        meta = extract_metadata(msg)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["artist"], "Daft Punk")
        self.assertEqual(meta["title"], "One More Time")

    def test_extract_metadata_ignores_non_audio(self):
        doc = DummyDocument(
            doc_id=103,
            size=200000,
            mime_type="application/pdf",
            attributes=[DummyFilenameAttr("document.pdf")]
        )
        msg = DummyMessage(msg_id=44, document=doc)
        meta = extract_metadata(msg)
        self.assertIsNone(meta)

    def test_deduplication_and_query(self):
        conn = get_db_connection()
        doc = DummyDocument(
            doc_id=201,
            size=6000000,
            mime_type="audio/mpeg",
            attributes=[DummyAudioAttr("Track 1", "Artist A", 200)]
        )
        msg = DummyMessage(msg_id=50, document=doc)
        meta = extract_metadata(msg)

        # Первая вставка
        with conn:
            conn.execute("""
                INSERT INTO tracks (telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (meta["telegram_msg_id"], meta["document_id"], meta["access_hash"], meta["title"], meta["artist"], meta["duration"], meta["file_size"], meta["mime_type"], meta["date"]))

        # Попытка вставки дубликата должна вызывать IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            with conn:
                conn.execute("""
                    INSERT INTO tracks (telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (meta["telegram_msg_id"], meta["document_id"], meta["access_hash"], meta["title"], meta["artist"], meta["duration"], meta["file_size"], meta["mime_type"], meta["date"]))

        tracks, total = query_tracks(query="Artist A")
        self.assertEqual(total, 1)
        self.assertEqual(tracks[0]["artist"], "Artist A")
        self.assertEqual(tracks[0]["title"], "Track 1")

    def test_no_secrets_in_public_tracks_query(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (telegram_msg_id, document_id, access_hash, file_reference, title, artist, duration, file_size, mime_type, date)
                VALUES (77, 999, 123456, X'01020304', 'Secretless Track', 'Artist', 150, 3000000, 'audio/mpeg', '2026-11-17')
            """)

        tracks, _ = query_tracks()
        self.assertEqual(len(tracks), 1)
        track = tracks[0]
        # Проверяем, что секретные внутренние поля не отдаются
        self.assertNotIn("access_hash", track)
        self.assertNotIn("file_reference", track)
        self.assertNotIn("session", track)

    def test_status_without_configured_telegram(self):
        with patch.dict(os.environ, {"TELEGRAM_SESSION": "", "TELEGRAM_API_ID": ""}):
            status = get_catalog_status()
            self.assertEqual(status["status"], "ok")
            self.assertFalse(status["telegram_configured"])
            self.assertEqual(status["total_tracks"], 0)

    def test_clear_cache(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date)
                VALUES (88, 1000, 123, 'Test Track', 'Artist', 100, 1000, 'audio/mpeg', '2026-11-17')
            """)
        tracks, total = query_tracks()
        self.assertEqual(total, 1)

        clear_catalog_cache()
        tracks, total = query_tracks()
        self.assertEqual(total, 0)


if __name__ == "__main__":
    unittest.main()
