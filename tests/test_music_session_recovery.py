import asyncio
import os
import tempfile
from pathlib import Path

import modules.music_core as music_core


def test_new_local_session_precedes_stale_environment():
    with tempfile.TemporaryDirectory() as tmp:
        old_file = music_core.SESSION_FILE
        old_override = music_core._runtime_session_override
        old_env = os.environ.get("TELEGRAM_SESSION")
        try:
            fresh = "1" * 120
            stale = "2" * 120
            music_core.SESSION_FILE = Path(tmp) / "telegram_session.txt"
            music_core.SESSION_FILE.write_text(fresh, encoding="utf-8")
            music_core._runtime_session_override = ""
            os.environ["TELEGRAM_SESSION"] = stale
            candidates = music_core._session_candidates()
            assert candidates[0] == ("file", fresh)
            assert ("environment", stale) in candidates
        finally:
            music_core.SESSION_FILE = old_file
            music_core._runtime_session_override = old_override
            if old_env is None:
                os.environ.pop("TELEGRAM_SESSION", None)
            else:
                os.environ["TELEGRAM_SESSION"] = old_env


def test_save_session_is_atomic_and_becomes_runtime_priority():
    with tempfile.TemporaryDirectory() as tmp:
        old_file = music_core.SESSION_FILE
        old_override = music_core._runtime_session_override
        old_env = os.environ.get("TELEGRAM_SESSION")
        try:
            fresh = "3" * 120
            music_core.SESSION_FILE = Path(tmp) / "telegram_session.txt"
            asyncio.run(music_core.save_telegram_session_str(fresh))
            assert music_core.SESSION_FILE.read_text(encoding="utf-8") == fresh
            assert music_core.get_saved_telegram_session_str() == fresh
            assert not music_core.SESSION_FILE.with_suffix(".txt.tmp").exists()
        finally:
            music_core.SESSION_FILE = old_file
            music_core._runtime_session_override = old_override
            if old_env is None:
                os.environ.pop("TELEGRAM_SESSION", None)
            else:
                os.environ["TELEGRAM_SESSION"] = old_env


def test_malformed_session_is_rejected():
    try:
        asyncio.run(music_core.save_telegram_session_str("short"))
    except ValueError:
        return
    raise AssertionError("Malformed session must be rejected")
