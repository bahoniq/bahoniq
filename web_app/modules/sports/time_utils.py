"""Утилиты времени для BahonIQ Sports: хранение в UTC и отображение в Asia/Qyzylorda."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TARGET_TZ_NAME = "Asia/Qyzylorda"
try:
    TARGET_TZ = ZoneInfo(TARGET_TZ_NAME)
except Exception:  # pragma: no cover - fallback на случай отсутствия tzdata
    TARGET_TZ = timezone(timedelta(hours=5))


def utc_now_iso() -> str:
    """Возвращает текущее время в UTC ISO-8601 (с суффиксом Z)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    """Разбирает строку даты/времени в timezone-aware datetime (UTC)."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_qyzylorda(value: str | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Конвертирует UTC-дату в строку часового пояса Asia/Qyzylorda."""
    dt = parse_utc(value)
    if dt is None:
        return "Нет данных"
    local_dt = dt.astimezone(TARGET_TZ)
    return local_dt.strftime(fmt)


def seconds_until(value: str | None, now: datetime | None = None) -> int | None:
    """Возвращает количество секунд до события (или 0 если уже началось/прошло)."""
    dt = parse_utc(value)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    return max(0, int((dt - ref).total_seconds()))
