"""Кешируемый переводчик спортивных текстов (новости, биографии) на русский язык."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests

CACHE_PATH = Path(__file__).resolve().parents[3] / "data" / "sports_cache" / "translations_ru.json"
_LOCK = threading.Lock()
_MEM: dict[str, str] | None = None
_GTX_URL = "https://translate.googleapis.com/translate_a/single"


def _load_store() -> dict[str, str]:
    global _MEM
    if _MEM is not None:
        return _MEM
    try:
        if CACHE_PATH.exists():
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                _MEM = {str(k): str(v) for k, v in raw.items()}
                return _MEM
    except Exception:
        pass
    _MEM = {}
    return _MEM


def _save_store(store: dict[str, str]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except Exception:
        pass


def _is_mostly_russian(text: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        return True
    cyr = sum(1 for ch in letters if "А" <= ch <= "я" or ch in ("Ё", "ё"))
    return (cyr / len(letters)) >= 0.55


def _chunk_text(text: str, max_len: int = 1200) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    cur = ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if len(cur) + len(sent) + 1 <= max_len:
            cur = f"{cur} {sent}".strip()
        else:
            if cur:
                parts.append(cur)
            cur = sent[:max_len]
    if cur:
        parts.append(cur)
    return parts or [text[:max_len]]


def translate_en_to_ru(text: str | None) -> tuple[str, bool]:
    """Переводит текст с английского на русский с постоянным кешем.

    Возвращает кортеж (текст, applied_auto_translation).
    """
    clean = " ".join(str(text or "").strip().split())
    if not clean or clean == "Нет данных" or _is_mostly_russian(clean):
        return clean or "Нет данных", False

    key = hashlib.sha1(clean.encode("utf-8")).hexdigest()
    with _LOCK:
        store = _load_store()
        if key in store and store[key]:
            return store[key], True

    translated_parts: list[str] = []
    try:
        for chunk in _chunk_text(clean):
            resp = None
            for attempt in range(2):
                resp = requests.get(
                    _GTX_URL,
                    params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": chunk},
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    break
                time.sleep(0.5 * (attempt + 1))
            if resp is None or resp.status_code != 200:
                return clean, False
            data: Any = resp.json()
            if not isinstance(data, list) or not data or not isinstance(data[0], list):
                return clean, False
            piece = "".join(str(seg[0]) for seg in data[0] if isinstance(seg, list) and seg and seg[0])
            if not piece:
                return clean, False
            translated_parts.append(piece.strip())
    except Exception:
        return clean, False

    final_ru = " ".join(translated_parts).strip()
    if not final_ru:
        return clean, False

    with _LOCK:
        store = _load_store()
        if len(store) > 3000:
            # Оставляем последние ~2000 переводов, чтобы файл не разрастался бесконечно
            keys = list(store.keys())[-2000:]
            store = {k: store[k] for k in keys}
        store[key] = final_ru
        _MEM = store
        _save_store(store)
    return final_ru, True
