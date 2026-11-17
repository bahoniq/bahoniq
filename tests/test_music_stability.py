import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from modules import music_core
from web_app.routers.music import _parse_single_range


class FakeTelegramClient:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.download_calls = 0

    async def iter_download(self, document, chunk_size=256 * 1024):
        self.download_calls += 1
        for pos in range(0, len(self.payload), 17):
            yield self.payload[pos:pos + 17]


class MusicCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_flight_cache_and_exact_range(self):
        payload = (b"ID3" + bytes(range(64))) * 1000
        client = FakeTelegramClient(payload)
        track = {"id": 7, "telegram_msg_id": 99, "file_size": len(payload)}
        document = SimpleNamespace(size=len(payload))

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(music_core, "MUSIC_CACHE_DIR", Path(tmp)), \
             patch.object(music_core, "get_track_by_id", return_value=track), \
             patch.object(music_core, "get_telegram_document_for_track", AsyncMock(return_value=(track, document))), \
             patch.object(music_core, "get_telegram_client", AsyncMock(return_value=client)):
            music_core._cache_locks.clear()
            first = await music_core.ensure_track_cached(7)
            second = await music_core.ensure_track_cached(7)
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), payload)
            self.assertEqual(client.download_calls, 1)

            chunks = []
            async for chunk in music_core.read_cached_track_chunks(first, 10, 123, 31):
                chunks.append(chunk)
            self.assertEqual(b"".join(chunks), payload[10:133])

    def test_range_parser(self):
        self.assertEqual(_parse_single_range("bytes=10-20", 100), (10, 20))
        self.assertEqual(_parse_single_range("bytes=90-", 100), (90, 99))
        self.assertEqual(_parse_single_range("bytes=-10", 100), (90, 99))
        with self.assertRaises(ValueError):
            _parse_single_range("bytes=100-", 100)
        with self.assertRaises(ValueError):
            _parse_single_range("bytes=0-1,5-6", 100)


if __name__ == "__main__":
    unittest.main()
