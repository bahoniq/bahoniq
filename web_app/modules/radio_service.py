"""Каталог и ICY-метаданные онлайн-радио BahonIQ."""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any


def _station(
    station_id: str,
    name: str,
    freq: str,
    genre: str,
    subgroup: str,
    description: str,
    url: str | None = None,
    aliases: tuple[str, ...] = (),
    source: str = "",
    country: str = "KZ",
) -> dict[str, Any]:
    return {
        "id": station_id,
        "name": name,
        "aliases": list(aliases),
        "freq": freq,
        "genre": genre,
        "subgroup": subgroup,
        "description": description,
        "country": country,
        "url": url,
        "source": source,
        "available": bool(url),
        "unavailableReason": None if url else "Прямой поток пока не подтверждён",
    }


# Порядок закреплён пользовательским каталогом. Неподтверждённый поток намеренно
# оставляется пустым: чужой эфир лучше неработающей кнопки.
RADIO_STATIONS: list[dict[str, Any]] = [
    _station("russkoe_radio_asia", "Русское Радио Азия", "104.7 FM", "Поп · Хиты", "pop", "Русскоязычная поп-музыка, хиты и утренние шоу."),
    _station("zhuldyz_fm", "Жұлдыз FM", "101.4 FM", "Қазақ музыкасы · Поп", "pop", "Современная казахстанская эстрада и развлекательные программы.", "http://91.201.214.229:8000/zhulduz", aliases=("Жулдыз FM",), source="официальный эфир / публичный каталог потока"),
    _station("radio_ns", "Радио NS", "106.0 FM", "Поп · Хиты", "pop", "Зарубежные и отечественные хиты разных десятилетий.", "https://icecast.ns.kz/radions", aliases=("Национальная Сеть", "NS"), source="ns.kz / публичный каталог потока"),
    _station("europa_plus_kz", "Европа Плюс Казахстан", "107.0 FM", "Поп · Top 40", "pop", "Современные мировые поп- и танцевальные хиты."),
    _station("avtoradio_kz", "Авторадио Казахстан", "105.4 FM", "Поп · Новости дорог", "pop", "Музыка для автомобилистов, дорожные сводки и викторины.", "http://178.88.167.62:8080/AVTORADIO_192", source="avtoradio.kz / публичный каталог потока"),
    _station("toi_duman", "Той Думан", "101.8 FM", "Қазақ музыкасы · Той", "pop", "Казахские хиты, той-музыка и народные мотивы.", "http://stream.gakku.kz:8000/live.mp3", source="toiduman.kz / публичный каталог потока"),
    _station("love_radio_kz", "Love Radio Казахстан", "103.5 FM", "Поп · Love songs", "pop", "Романтические поп-хиты и современная танцевальная музыка.", "http://stream.gakku.tv:8000/love128.mp3", source="публичный каталог потока"),
    _station("energy_fm_kz", "Energy FM Казахстан", "102.2 FM", "Dance · Pop", "pop", "Клубная, танцевальная и современная поп-музыка.", "http://89.219.34.117:8008/NEWENERGY", source="публичный каталог потока"),
    _station("beu_fm", "Beu FM", "97.7 FM", "Қазақ музыкасы · Инди", "pop", "Современная казахстанская поп-, молодёжная и инди-музыка.", "https://stream.beufm.kz/beufm", aliases=("BEU FM",), source="beufm.kz"),
    _station("lux_fm", "Lux FM", "87.7 FM", "Поп · Город", "pop", "Лёгкая современная музыка и городские новости.", "https://service.luxfm.kz/bc/live", source="luxfm.kz / публичный каталог потока"),
    _station("retro_fm_kz", "Ретро FM Казахстан", "107.5 FM", "Ретро", "niche", "Золотые хиты 1970-х, 1980-х и 1990-х годов.", aliases=("Ретро FM Qazaqstan",)),
    _station("radio_dacha_kz", "Радио Дача Казахстан", "91.3 FM", "Ретро · Эстрада", "niche", "Душевные песни, ретро-хиты и семейные программы."),
    _station("narodnoe_radio", "Народное радио", "100.2 FM", "Эстрада · Разговорное", "niche", "Известные хиты, душевная музыка и разговорные эфиры.", "http://178.88.167.62:8080/DALA_192", source="публичный каталог потока"),
    _station("tengri_fm", "Tengri FM", "Online", "Rock", "niche", "Классический и современный зарубежный и казахстанский рок.", "http://91.201.214.229:8000/tengrifm", source="публичный каталог потока"),
    _station("radio_classic", "Radio Classic", "102.8 FM", "Классика · Джаз", "niche", "Классическая, джазовая и академическая музыка.", "https://radio-streams.kaztrk.kz/classic/classic/icecast.audio", aliases=("Радио Classic",), source="Qazaqstan RTRK"),
    _station("dala_fm", "Dala FM", "Online", "Қазақ музыкасы · Folk", "niche", "Современные казахстанские хиты и фольклорные мотивы."),
    _station("qazaq_radiosy", "Қазақ радиосы", "101.0 FM", "Новости · Қазақ музыкасы", "talk", "Новости, аналитика, культура и музыкальные передачи.", "https://radio-streams.kaztrk.kz/qazradio/qazradio/icecast.audio", aliases=("Казахское радио", "Qazaq Radiosy"), source="Qazaqstan RTRK"),
    _station("shalqar", "Радио Шалқар", "106.5 FM", "Культура · Дәстүр", "talk", "Казахский язык, национальная культура, литература и традиционная музыка.", "https://radio-streams.kaztrk.kz/shalqar/shalqar/icecast.audio", aliases=("Радио Шалкар", "Шалқар радиосы"), source="Qazaqstan RTRK"),
    _station("business_fm_kz", "Business FM Казахстан", "89.6 FM", "Бизнес · Новости", "talk", "Экономика, финансы, рынки, деловые новости и интервью.", "https://bfmreg.hostingradio.ru/kz.bfm128.mp3", source="businessfm.kz"),
    _station("orda_fm", "Orda FM", "99.3 FM", "Новости · Поп", "talk", "Новости, аналитика и качественная музыка."),
    _station("europa_plus", "Европа Плюс", "106.2 FM", "Top 40 · Pop", "pop", "Мировые поп- и танцевальные хиты.", "http://ep128server.streamr.ru:8030/ep128", country="RU"),
    _station("rusradio", "Русское Радио", "105.7 FM", "Русские хиты", "pop", "Популярная русскоязычная музыка.", "https://rusradio.hostingradio.ru/rusradio96.aacp", country="RU"),
    _station("dfm_dance", "DFM Dance", "101.2 FM", "Club · Dance", "pop", "Клубная и танцевальная музыка.", "https://dfm-dfmrusdance.hostingradio.ru/dfmrusdance96.aacp", country="RU"),
    _station("dorognoe", "Дорожное радио", "96.0 FM", "В дорогу · Ретро", "niche", "Музыка для дороги и знакомые хиты.", "http://dorognoe.hostingradio.ru:8000/dorognoe", country="RU"),
    _station("marusya", "Маруся ФМ", "91.4 FM", "Поп · Танцевальное", "pop", "Современная поп- и танцевальная музыка.", "https://listen.vdfm.ru:8000/marusya", country="RU"),
    _station("mixadance", "Mixadance FM", "Online", "Deep House · Chill", "niche", "Электронная музыка, deep house и chill.", "https://stream.mixadance.fm/mixadance", country="RU"),
]

RADIO_BY_ID = {station["id"]: station for station in RADIO_STATIONS}

_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_metadata_locks: dict[str, asyncio.Lock] = {}


def public_station(station: dict[str, Any]) -> dict[str, Any]:
    """Представление станции для клиента: HTTPS-потоки отдаются напрямую в телефон (0 МБ трафика Render)
    с резервным fallback на серверный прокси."""
    result = {key: value for key, value in station.items() if key not in {"url", "source"}}
    raw_url = str(station.get("url") or "").strip()
    if not raw_url:
        result["stream_url"] = None
        result["fallback_stream_url"] = None
    elif raw_url.lower().startswith("https://"):
        result["stream_url"] = raw_url
        result["fallback_stream_url"] = f"/api/music/radio/stream/{station['id']}"
    else:
        result["stream_url"] = f"/api/music/radio/stream/{station['id']}"
        result["fallback_stream_url"] = None
    return result


def split_stream_title(raw_title: str) -> tuple[str | None, str | None]:
    clean = re.sub(r"\s+", " ", (raw_title or "").strip()).strip(" -–—")
    if not clean:
        return None, None
    parts = re.split(r"\s+[-–—]\s+", clean, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip() or None, parts[1].strip() or None
    return None, clean


async def _read_icy_metadata(url: str) -> str | None:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=12, connect=6, sock_read=7)
    headers = {"Icy-MetaData": "1", "User-Agent": "BahonIQ-Music/1.0", "Accept": "*/*"}
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers, allow_redirects=True) as response:
            if response.status >= 400:
                return None
            interval_raw = response.headers.get("icy-metaint")
            if not interval_raw or not interval_raw.isdigit():
                return None
            interval = int(interval_raw)
            if interval <= 0 or interval > 2_000_000:
                return None
            await response.content.readexactly(interval)
            length_byte = await response.content.readexactly(1)
            metadata_length = length_byte[0] * 16
            if metadata_length <= 0 or metadata_length > 16_384:
                return None
            block = await response.content.readexactly(metadata_length)
            text = block.rstrip(b"\0").decode("utf-8", errors="replace")
            match = re.search(r"StreamTitle=['\"](.*?)['\"]\s*;", text, re.I)
            return match.group(1).strip() if match else None


async def get_station_metadata(station_id: str) -> dict[str, Any]:
    station = RADIO_BY_ID.get(station_id)
    if not station:
        raise KeyError(station_id)
    now = time.monotonic()
    cached = _metadata_cache.get(station_id)
    if cached and now - cached[0] < 15:
        return cached[1]
    lock = _metadata_locks.setdefault(station_id, asyncio.Lock())
    async with lock:
        cached = _metadata_cache.get(station_id)
        if cached and time.monotonic() - cached[0] < 15:
            return cached[1]
        raw = None
        error = None
        if station.get("url") and ".m3u8" not in station["url"]:
            try:
                raw = await _read_icy_metadata(station["url"])
            except Exception as exc:  # метаданные не должны ломать эфир
                error = type(exc).__name__
        artist, title = split_stream_title(raw or "")
        result = {
            "stationId": station_id,
            "artist": artist,
            "title": title,
            "program": None,
            "rawTitle": raw,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "available": bool(raw),
            "status": "ok" if raw else "no_metadata",
            "error": error,
        }
        _metadata_cache[station_id] = (time.monotonic(), result)
        return result
