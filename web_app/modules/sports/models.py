"""Нормализованные структуры данных BahonIQ Sports."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CachedEnvelope:
    """Обёртка ответа с метаданными свежести и кеша."""
    data: Any
    updated_at_utc: str
    source: str
    stale: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SportMatch:
    """Нормализованный футбольный матч."""
    id: str
    club_id: str
    league: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    date_utc: str
    date_local: str
    status: str  # scheduled | live | finished | postponed | canceled
    status_label: str
    venue: str = "Нет данных"
    home_logo: str = ""
    away_logo: str = ""
    source: str = ""


@dataclass
class SportNewsItem:
    """Нормализованная новость из RSS/API."""
    id: str
    title: str
    summary: str
    url: str
    published_utc: str
    published_local: str
    category: str  # football | f1 | ufc
    source: str
    is_rumor: bool = False
    image_url: str = ""


@dataclass
class F1RaceEvent:
    """Этап чемпионата Formula 1."""
    round_num: int
    race_name: str
    circuit_name: str
    country: str
    locality: str
    date_utc: str
    date_local: str
    sessions: list[dict[str, str]] = field(default_factory=list)
    status: str = "scheduled"
    source: str = "Jolpica F1"


@dataclass
class UfcFight:
    """Бой в карде турнира UFC."""
    id: str
    fighter_a: str
    fighter_b: str
    record_a: str
    record_b: str
    weight_class: str
    card_section: str  # main_card | prelims | early_prelims
    is_main_event: bool = False
    is_co_main: bool = False
    status: str = "scheduled"  # scheduled | live | finished | canceled | postponed
    winner: str | None = None
    method: str = ""
    round_num: int | None = None
    time_str: str = ""
