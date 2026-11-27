"""Локальное хранилище Poker Club: один JSON-файл, атомарная запись, единый источник истины по балансу."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("poker")

START_BALANCE = 50_000


def default_data(sound: bool = True) -> dict:
    return {
        "version": 1,
        "balance": START_BALANCE,
        "stats": {"hands": 0, "wins": 0, "losses": 0, "biggest_pot": 0, "total_won": 0, "total_lost": 0},
        "settings": {"sound": sound},
        "session": None,
    }


def _clean_int(v, default=0) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return default


class PokerStorage:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        base = default_data()
        if not self.path.exists():
            return base
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("bad root")
            base["balance"] = _clean_int(raw.get("balance"), START_BALANCE)
            for k in base["stats"]:
                base["stats"][k] = _clean_int((raw.get("stats") or {}).get(k))
            base["settings"]["sound"] = bool((raw.get("settings") or {}).get("sound", True))
            base["session"] = raw.get("session") if isinstance(raw.get("session"), dict) else None
            return base
        except Exception:
            log.exception("Файл прогресса повреждён, сохраняю копию и начинаю заново")
            try:
                os.replace(self.path, self.path.with_suffix(".corrupt.json"))
            except OSError:
                pass
            return base

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)

    def reset(self) -> None:
        with self.lock:
            sound = self.data["settings"]["sound"]
            self.data = default_data(sound)
            self.save()
