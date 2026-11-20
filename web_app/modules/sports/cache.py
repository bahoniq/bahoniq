"""Локальный файловый кеш BahonIQ Sports с TTL и устойчивостью к сбоям."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "sports_cache"

TTL_LIVE = 120          # 2 минуты для текущих/live событий
TTL_SCHEDULE = 3 * 3600 # 3 часа для ближайших матчей, гонок, кардов
TTL_NEWS = 1800         # 30 минут для новостей
TTL_PROFILES = 24 * 3600  # 24 часа для статичных профилей и команд


class SportsCache:
    """Потокобезопасный JSON-кеш, сохраняющий последнюю успешную копию при сбоях."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key).strip("_") or "item"
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str, ttl: int) -> dict[str, Any] | None:
        """Возвращает свежую запись кеша или None, если она отсутствует/истекла/повреждена."""
        entry = self.get_stale(key)
        if entry is None:
            return None
        age = time.time() - float(entry.get("saved_ts", 0))
        if age > ttl:
            return None
        return entry

    def get_stale(self, key: str) -> dict[str, Any] | None:
        """Возвращает последнюю сохранённую запись независимо от TTL; при битом JSON — None."""
        path = self._path(key)
        if not path.exists():
            return None
        with self._lock:
            try:
                raw = path.read_text(encoding="utf-8")
                payload = json.loads(raw)
                if not isinstance(payload, dict) or "data" not in payload:
                    return None
                return payload
            except Exception:
                return None

    def set(self, key: str, data: Any, updated_at_utc: str, source: str) -> None:
        """Атомарно сохраняет успешный результат в кеш."""
        path = self._path(key)
        tmp_path = path.with_suffix(".tmp")
        payload = {
            "saved_ts": time.time(),
            "updated_at_utc": updated_at_utc,
            "source": source,
            "data": data,
        }
        with self._lock:
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(path)
