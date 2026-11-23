"""
Автоматические тесты для модуля «Музыка в авто» (modules/music_core.py, modules/music_covers.py и web_app/routers/music.py).
Используются моки — реальные сетевые запросы к Telegram не выполняются.
"""
import asyncio
import base64
import io
import os
import shutil
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from modules.music_core import (
    clear_catalog_cache,
    extract_metadata,
    get_catalog_status,
    get_db_connection,
    get_track_by_id,
    get_track_unique_key,
    load_saved_real_cover,
    query_tracks,
    resolve_track_cover,
    save_real_cover,
    select_linked_photo_candidate,
)
from modules.music_covers import (
    clean_music_query,
    compute_cover_hash,
    extract_embedded_cover_from_bytes,
    fetch_itunes_cover_bytes,
    validate_image_bytes,
)
from web_app.routers.music import _parse_single_range, get_track, list_tracks, track_cover


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
        # Используем временную SQLite-базу и изолированные папки кэша для каждого теста
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bahoniq_music_test_"))
        self.temp_db_path = self.temp_dir / "test_music_catalog.db"
        self.temp_cache_dir = self.temp_dir / "music_stream_cache"
        self.temp_covers_dir = self.temp_dir / "music_covers"
        self.temp_cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_covers_dir.mkdir(parents=True, exist_ok=True)

        self.db_patcher = patch("modules.music_core.DB_PATH", self.temp_db_path)
        self.cache_patcher = patch("modules.music_core.MUSIC_CACHE_DIR", self.temp_cache_dir)
        self.covers_patcher = patch("modules.music_core.MUSIC_COVERS_DIR", self.temp_covers_dir)
        self.db_patcher.start()
        self.cache_patcher.start()
        self.covers_patcher.start()

    def tearDown(self):
        self.covers_patcher.stop()
        self.cache_patcher.stop()
        self.db_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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

    def test_http_range_parser(self):
        self.assertEqual(_parse_single_range("bytes=0-99", 1000), (0, 99))
        self.assertEqual(_parse_single_range("bytes=900-", 1000), (900, 999))
        self.assertEqual(_parse_single_range("bytes=-100", 1000), (900, 999))

    def test_http_range_parser_rejects_invalid_ranges(self):
        for value in ("items=0-10", "bytes=1000-", "bytes=50-10", "bytes=0-1,5-6", "bytes=-0"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _parse_single_range(value, 1000)

    # --- Тесты извлечения, валидации, приоритета и кэширования обложек ---

    @staticmethod
    def _make_test_image(fmt: str = "JPEG", color=(40, 180, 220), size=(64, 64)) -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    @staticmethod
    def _encode_synchsafe(val: int) -> bytes:
        return bytes([
            (val >> 21) & 0x7F,
            (val >> 14) & 0x7F,
            (val >> 7) & 0x7F,
            val & 0x7F,
        ])

    def _build_id3v23_apic_mp3(self, img_bytes: bytes, mime: str = "image/jpeg", pic_type: int = 3) -> bytes:
        apic_body = b"\x00" + mime.encode("ascii") + b"\x00" + bytes([pic_type]) + b"Cover\x00" + img_bytes
        frame = b"APIC" + struct.pack(">I", len(apic_body)) + b"\x00\x00" + apic_body
        tag_header = b"ID3\x03\x00\x00" + self._encode_synchsafe(len(frame))
        return tag_header + frame + b"\xff\xfb\x90\x64" * 32

    def _build_id3v24_apic_mp3(self, img_bytes: bytes, mime: str = "image/png", pic_type: int = 3) -> bytes:
        apic_body = b"\x03" + mime.encode("ascii") + b"\x00" + bytes([pic_type]) + b"\x00" + img_bytes
        frame = b"APIC" + self._encode_synchsafe(len(apic_body)) + b"\x00\x00" + apic_body
        tag_header = b"ID3\x04\x00\x00" + self._encode_synchsafe(len(frame))
        return tag_header + frame + b"\xff\xfb\x90\x64" * 32

    def _build_id3v22_pic_mp3(self, img_bytes: bytes, fmt3: bytes = b"JPG", pic_type: int = 3) -> bytes:
        pic_body = b"\x00" + fmt3 + bytes([pic_type]) + b"\x00" + img_bytes
        frame_size_24 = len(pic_body).to_bytes(3, "big")
        frame = b"PIC" + frame_size_24 + pic_body
        tag_header = b"ID3\x02\x00\x00" + self._encode_synchsafe(len(frame))
        return tag_header + frame + b"\xff\xfb\x90\x64" * 32

    @staticmethod
    def _build_m4a_covr(img_bytes: bytes, flags: int = 13) -> bytes:
        def atom(name: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", 8 + len(payload)) + name + payload

        ftyp = atom(b"ftyp", b"M4A \x00\x00\x02\x00isomiso2")
        data_atom = atom(b"data", struct.pack(">I", flags) + b"\x00\x00\x00\x00" + img_bytes)
        covr = atom(b"covr", data_atom)
        ilst = atom(b"ilst", covr)
        meta = atom(b"meta", b"\x00\x00\x00\x00" + ilst)
        udta = atom(b"udta", meta)
        moov = atom(b"moov", udta)
        return ftyp + moov

    @staticmethod
    def _build_flac_picture_block(img_bytes: bytes, mime: str = "image/jpeg", pic_type: int = 3) -> bytes:
        mime_b = mime.encode("ascii")
        desc_b = b"Front"
        block = (
            struct.pack(">I", pic_type)
            + struct.pack(">I", len(mime_b))
            + mime_b
            + struct.pack(">I", len(desc_b))
            + desc_b
            + struct.pack(">IIII", 64, 64, 24, 0)
            + struct.pack(">I", len(img_bytes))
            + img_bytes
        )
        return block

    def test_extract_id3v23_apic_jpeg(self):
        jpg = self._make_test_image("JPEG", color=(200, 30, 60))
        mp3 = self._build_id3v23_apic_mp3(jpg, mime="image/jpeg")
        res = extract_embedded_cover_from_bytes(mp3)
        self.assertIsNotNone(res)
        extracted_bytes, mime = res
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(extracted_bytes, jpg)

    def test_extract_id3v24_apic_png_and_front_cover_priority(self):
        back_jpg = self._make_test_image("JPEG", color=(10, 10, 10))
        front_png = self._make_test_image("PNG", color=(20, 220, 100))
        b1 = b"\x00image/jpeg\x00\x04Back\x00" + back_jpg
        f1 = b"APIC" + self._encode_synchsafe(len(b1)) + b"\x00\x00" + b1
        b2 = b"\x00image/png\x00\x03Front\x00" + front_png
        f2 = b"APIC" + self._encode_synchsafe(len(b2)) + b"\x00\x00" + b2
        frames = f1 + f2
        mp3 = b"ID3\x04\x00\x00" + self._encode_synchsafe(len(frames)) + frames
        res = extract_embedded_cover_from_bytes(mp3)
        self.assertIsNotNone(res)
        extracted_bytes, mime = res
        self.assertEqual(mime, "image/png")
        self.assertEqual(extracted_bytes, front_png)

    def test_extract_id3v22_pic(self):
        jpg = self._make_test_image("JPEG", color=(120, 80, 240))
        mp3 = self._build_id3v22_pic_mp3(jpg, fmt3=b"JPG")
        res = extract_embedded_cover_from_bytes(mp3)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], jpg)
        self.assertEqual(res[1], "image/jpeg")

    def test_extract_m4a_covr(self):
        jpg = self._make_test_image("JPEG", color=(250, 180, 0))
        m4a = self._build_m4a_covr(jpg)
        res = extract_embedded_cover_from_bytes(m4a)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], jpg)
        self.assertEqual(res[1], "image/jpeg")

    def test_extract_flac_picture(self):
        png = self._make_test_image("PNG", color=(0, 150, 255))
        pic_block = self._build_flac_picture_block(png, mime="image/png")
        header = bytes([0x80 | 6]) + len(pic_block).to_bytes(3, "big")
        flac_data = b"fLaC" + header + pic_block
        res = extract_embedded_cover_from_bytes(flac_data)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], png)
        self.assertEqual(res[1], "image/png")

    def test_extract_ogg_metadata_block_picture(self):
        jpg = self._make_test_image("JPEG", color=(90, 200, 90))
        pic_block = self._build_flac_picture_block(jpg, mime="image/jpeg")
        b64_val = base64.b64encode(pic_block)
        ogg_data = b"OggS\x00\x02" + b"\x00" * 24 + b"METADATA_BLOCK_PICTURE=" + b64_val + b"\x00"
        res = extract_embedded_cover_from_bytes(ogg_data)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], jpg)
        self.assertEqual(res[1], "image/jpeg")

    def test_validate_png_jpeg_webp_and_reject_corrupted_bytes(self):
        for fmt, expected_mime in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
            raw = self._make_test_image(fmt)
            validated = validate_image_bytes(raw)
            self.assertIsNotNone(validated, f"{fmt} should be valid")
            self.assertEqual(validated[1], expected_mime)

        # Повреждённая псевдо-картинка (случайные байты MP3-фрейма между \xff\xd8\xff и \xff\xd9)
        fake_jpeg = b"\xff\xd8\xff\xe0" + os.urandom(2048) + b"\xff\xd9"
        self.assertIsNone(validate_image_bytes(fake_jpeg))

        # MP3 без APIC, но с ложными маркерами JPEG в аудиопотоке
        tag_only_tenc = b"TENC\x00\x00\x00\x0b\x00\x00\x03Lavf60.3.1"
        mp3_no_apic = b"ID3\x04\x00\x00" + self._encode_synchsafe(len(tag_only_tenc)) + tag_only_tenc + fake_jpeg
        self.assertIsNone(extract_embedded_cover_from_bytes(mp3_no_apic))

    def test_cover_hash_stability_and_change(self):
        img1 = self._make_test_image("JPEG", color=(10, 20, 30))
        img2 = self._make_test_image("JPEG", color=(200, 100, 50))
        h1_a = compute_cover_hash(img1)
        h1_b = compute_cover_hash(img1)
        h2 = compute_cover_hash(img2)
        self.assertEqual(h1_a, h1_b)
        self.assertEqual(len(h1_a), 12)
        self.assertNotEqual(h1_a, h2)

    def test_priority_embedded_over_telegram_thumb_and_fallback_to_thumb(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (id, telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date, has_cover, file_unique_id)
                VALUES (1, 1001, 5001, 111, 'Embedded Track', 'Artist 1', 180, 4000000, 'audio/mp4', '2026-11-20', 1, 'tgdoc_5001'),
                       (2, 1002, 5002, 222, 'Thumb Only Track', 'Artist 2', 200, 4000000, 'audio/mpeg', '2026-11-20', 1, 'tgdoc_5002'),
                       (3, 1003, 5003, 333, 'No Cover Track', 'Artist 3', 190, 4000000, 'audio/mpeg', '2026-11-20', 0, 'tgdoc_5003')
            """)
        conn.close()

        embedded_jpg = self._make_test_image("JPEG", color=(255, 0, 0))
        thumb_jpg = self._make_test_image("JPEG", color=(0, 0, 255))
        m4a_with_covr = self._build_m4a_covr(embedded_jpg)
        mp3_without_cover = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x64" * 64

        class FakeClient:
            def __init__(self, file_map, thumb_bytes):
                self.file_map = file_map
                self.thumb_bytes = thumb_bytes

            async def iter_download(self, doc, offset=0, chunk_size=262144, request_size=262144):
                yield self.file_map[doc.id]

            async def download_media(self, doc, file=bytes, thumb=-1):
                return self.thumb_bytes if doc.thumbs else None

        doc1 = DummyDocument(5001, len(m4a_with_covr), "audio/mp4", [], thumbs=["thumb1"])
        doc2 = DummyDocument(5002, len(mp3_without_cover), "audio/mpeg", [], thumbs=["thumb2"])
        doc3 = DummyDocument(5003, len(mp3_without_cover), "audio/mpeg", [], thumbs=[])
        docs = {1: doc1, 2: doc2, 3: doc3}
        fake_client = FakeClient({5001: m4a_with_covr, 5002: mp3_without_cover, 5003: mp3_without_cover}, thumb_jpg)

        async def fake_get_doc(tid):
            return get_track_by_id(tid), docs[tid]

        async def run_test():
            with patch("modules.music_core.get_telegram_document_for_track", side_effect=fake_get_doc), \
                 patch("modules.music_core.get_telegram_client", AsyncMock(return_value=fake_client)):
                # Трек 1 имеет и встроенную обложку, и thumb в Telegram -> должна выбраться встроенная (embedded)
                r1 = await resolve_track_cover(1)
                self.assertIsNotNone(r1)
                self.assertEqual(r1["source"], "embedded")
                self.assertEqual(r1["bytes"], embedded_jpg)

                # Трек 2 не имеет встроенной обложки, но имеет thumb в Telegram -> выбирается thumb
                r2 = await resolve_track_cover(2)
                self.assertIsNotNone(r2)
                self.assertEqual(r2["source"], "thumb")
                self.assertEqual(r2["bytes"], thumb_jpg)

                # Трек 3 не имеет ни встроенной обложки, ни thumb -> None и cover_source='none'
                r3 = await resolve_track_cover(3)
                self.assertIsNone(r3)
                t3 = get_track_by_id(3)
                self.assertEqual(t3["cover_source"], "none")

        asyncio.run(run_test())

    def test_placeholder_never_overwrites_real_cover_and_real_cover_replaces_placeholder(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (id, telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date, has_cover, file_unique_id)
                VALUES (10, 2010, 6010, 123, 'Dynamic Cover Track', 'Artist', 210, 5000000, 'audio/mpeg', '2026-11-20', 0, 'tgdoc_6010')
            """)
        conn.close()

        dummy_req = SimpleNamespace(headers={})

        async def run_test():
            # 1. До появления реальной обложки возвращается заглушка с Cache-Control: no-store и X-Cover-Placeholder: true
            with patch("web_app.routers.music.resolve_track_cover", AsyncMock(return_value=None)):
                resp_ph = await track_cover(10, request=dummy_req, fallback=None, v="0")
                self.assertEqual(resp_ph.headers.get("X-Cover-Placeholder"), "true")
                self.assertIn("no-store", resp_ph.headers.get("Cache-Control", ""))

            # 2. Сохраняем реальную обложку — она должна заменить заглушку и обновить cover_hash
            real_png = self._make_test_image("PNG", color=(100, 50, 200))
            saved = save_real_cover(10, real_png, "image/png", source="embedded")
            self.assertIsNotNone(saved)
            c_hash = saved["cover_hash"]

            resp_real = await track_cover(10, request=dummy_req, fallback="404", v=c_hash)
            self.assertEqual(resp_real.status_code, 200)
            self.assertEqual(resp_real.headers.get("X-Cover-Placeholder"), "false")
            self.assertEqual(resp_real.headers.get("X-Cover-Source"), "embedded")
            self.assertEqual(resp_real.headers.get("ETag"), f'"{c_hash}"')
            self.assertIn("immutable", resp_real.headers.get("Cache-Control", ""))

            # 3. HTTP 304 Not Modified при совпадении If-None-Match
            req_304 = SimpleNamespace(headers={"if-none-match": f'"{c_hash}"'})
            resp_304 = await track_cover(10, request=req_304, fallback="404", v=c_hash)
            self.assertEqual(resp_304.status_code, 304)

            # 4. При временном сбое Telegram ранее сохранённая реальная обложка НЕ затирается заглушкой
            with patch("modules.music_core.get_telegram_document_for_track", AsyncMock(return_value=(get_track_by_id(10), None))):
                still_real = await resolve_track_cover(10, allow_network=True)
                self.assertIsNotNone(still_real)
                self.assertEqual(still_real["cover_hash"], c_hash)

            # 5. При обновлении обложки на новую меняется cover_hash
            new_jpg = self._make_test_image("JPEG", color=(10, 240, 80))
            saved2 = save_real_cover(10, new_jpg, "image/jpeg", source="embedded")
            self.assertNotEqual(saved2["cover_hash"], c_hash)
            loaded2 = load_saved_real_cover(get_track_by_id(10))
            self.assertEqual(loaded2["cover_hash"], saved2["cover_hash"])

        asyncio.run(run_test())

    def test_stable_file_unique_id_and_no_telegram_secrets_in_cover_api(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (id, telegram_msg_id, document_id, access_hash, file_reference, title, artist, duration, file_size, mime_type, date, has_cover)
                VALUES (42, 3042, 9876543210, 7777777, X'DEADBEEF', 'Safe Track', 'Safe Artist', 195, 4500000, 'audio/mpeg', '2026-11-20', 1)
            """)
        conn.close()

        jpg = self._make_test_image("JPEG", color=(40, 90, 140))
        save_real_cover(42, jpg, "image/jpeg", source="embedded")

        async def run_test():
            listing = await list_tracks(q=None, artist=None, album=None, sort_by="date", order="desc", limit=50, offset=0)
            self.assertEqual(len(listing["tracks"]), 1)
            t = listing["tracks"][0]
            self.assertEqual(t["file_unique_id"], "tgdoc_9876543210")
            self.assertEqual(get_track_unique_key(t), "tgdoc_9876543210")
            self.assertTrue(t["cover_url"].startswith(f"/api/music/cover/42?v={t['cover_hash']}"))
            for forbidden in ("access_hash", "file_reference", "session", "token", "api_hash"):
                self.assertNotIn(forbidden, t)
                self.assertNotIn(forbidden, t["cover_url"].lower())

            single = await get_track(42)
            self.assertEqual(single["file_unique_id"], "tgdoc_9876543210")
            self.assertEqual(single["cover_hash"], t["cover_hash"])
            for forbidden in ("access_hash", "file_reference", "session", "token"):
                self.assertNotIn(forbidden, single)

        asyncio.run(run_test())

    def test_frontend_onerror_loop_protection_and_sw_placeholder_filter(self):
        root_dir = Path(__file__).resolve().parent.parent
        music_js = (root_dir / "web_app" / "static" / "music" / "music.js").read_text(encoding="utf-8")
        sw_js = (root_dir / "web_app" / "static" / "music" / "sw.js").read_text(encoding="utf-8")

        # Проверяем защиту от бесконечного цикла onerror в music.js
        self.assertIn("dataset.fallbackApplied === 'true'", music_js)
        self.assertIn("getTrackCoverUrl", music_js)

        # Проверяем, что Service Worker не кэширует заглушки (X-Cover-Placeholder: true)
        self.assertIn("X-Cover-Placeholder", sw_js)
        self.assertIn("COVERS_CACHE_NAME", sw_js)

    def test_deduplication_by_normalized_artist_title_prefers_real_cover(self):
        conn = get_db_connection()
        with conn:
            conn.execute("""
                INSERT INTO tracks (id, telegram_msg_id, document_id, access_hash, title, artist, duration, file_size, mime_type, date, has_cover, cover_source, cover_hash, file_unique_id)
                VALUES
                    (10, 10010, 70010, 111, 'Rozalina [muzik.kz]', 'DAKELOT', 200, 4000000, 'audio/mpeg', '2026-05-01T10:00:00+00:00', 0, 'none', '', 'tgdoc_70010'),
                    (11, 20011, 70011, 222, 'Rozalina', 'Dakelot', 200, 4200000, 'audio/mpeg', '2026-11-23T14:00:00+00:00', 1, 'embedded', 'abc123def456', 'tgdoc_70011'),
                    (12, 10012, 70012, 333, 'Dosym', 'Baxa', 180, 3500000, 'audio/mpeg', '2026-05-01T10:00:00+00:00', 0, 'none', '', 'tgdoc_70012')
            """)
        conn.close()

        tracks, total = query_tracks()
        self.assertEqual(total, 2)
        roz = [t for t in tracks if "rozalina" in t["title"].lower()]
        self.assertEqual(len(roz), 1)
        self.assertEqual(roz[0]["id"], 11)
        self.assertEqual(roz[0]["cover_source"], "embedded")
        self.assertEqual(roz[0]["cover_hash"], "abc123def456")

    def test_select_linked_photo_candidate_ignores_service_avatar_and_matches_album_reply_caption(self):
        track = {"title": "Osek sozler", "artist": "Ajiniyaz"}
        # Служебное сообщение о смене аватарки чата (как msg_id=3 в @bahoniqmusic) должно игнорироваться
        service_avatar = SimpleNamespace(id=3, photo=True, action=object(), grouped_id=None, message="")
        unrelated_photo = SimpleNamespace(id=2, photo=True, action=None, grouped_id=None, message="Другая песня")
        audio_plain = SimpleNamespace(id=4, photo=None, action=None, grouped_id=None, reply_to=None)
        self.assertIsNone(select_linked_photo_candidate(audio_plain, [service_avatar, unrelated_photo], track))

        # Совпадение по grouped_id (медиаальбом)
        album_photo = SimpleNamespace(id=10, photo=True, action=None, grouped_id=99999, message="")
        audio_album = SimpleNamespace(id=11, photo=None, action=None, grouped_id=99999, reply_to=None)
        self.assertIs(select_linked_photo_candidate(audio_album, [service_avatar, album_photo], track), album_photo)

        # Совпадение по reply_to
        replied_photo = SimpleNamespace(id=20, photo=True, action=None, grouped_id=None, message="")
        audio_reply = SimpleNamespace(
            id=21, photo=None, action=None, grouped_id=None, reply_to=SimpleNamespace(reply_to_msg_id=20)
        )
        self.assertIs(select_linked_photo_candidate(audio_reply, [unrelated_photo, replied_photo], track), replied_photo)

        # Совпадение по caption/title
        caption_photo = SimpleNamespace(id=30, photo=True, action=None, grouped_id=None, message="Ajiniyaz - Osek sozler")
        self.assertIs(select_linked_photo_candidate(audio_plain, [unrelated_photo, caption_photo], track), caption_photo)

    def test_clean_music_query_and_itunes_fallback_mocked(self):
        a, t = clean_music_query("HammAli &amp; Navai", "А если это любовь? [kzmp3.kz] (2024)")
        self.assertEqual(a, "HammAli")
        self.assertEqual(t, "А если это любовь?")

        a2, t2 = clean_music_query("Неизвестный исполнитель", "Sadraddin - Taxi [muzik.kz]")
        self.assertEqual(a2, "Sadraddin")
        self.assertEqual(t2, "Taxi")

        jpg = self._make_test_image("JPEG", color=(30, 120, 210))

        class FakeResp:
            def __init__(self, data: bytes, status: int = 200):
                self._data = data
                self.status = status

            def read(self, n: int = -1):
                return self._data if n < 0 else self._data[:n]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        search_json = (
            '{"results":[{"artistName":"Sadraddin","trackName":"Taxi",'
            '"artworkUrl100":"https://is1-ssl.mzstatic.com/image/thumb/Music/100x100bb.jpg"}]}'
        ).encode("utf-8")

        def fake_urlopen(req, timeout=4.0):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "itunes.apple.com/search" in url:
                return FakeResp(search_json)
            self.assertIn("300x300bb.jpg", url)
            return FakeResp(jpg)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            res = fetch_itunes_cover_bytes("Sadraddin", "Taxi")
        self.assertIsNotNone(res)
        self.assertEqual(res[0], jpg)
        self.assertEqual(res[1], "image/jpeg")


if __name__ == "__main__":
    unittest.main()
