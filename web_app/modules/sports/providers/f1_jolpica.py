"""Адаптер Jolpica F1 API (преемник Ergast API, бесплатный без ключа)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..time_utils import format_qyzylorda, parse_utc
from .base import fetch_json

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"

CONSTRUCTOR_WIKI_MAP: dict[str, dict[str, str]] = {
    "mercedes": {
        "wiki": "https://en.wikipedia.org/wiki/Mercedes-Benz_in_Formula_One",
        "accent": "#00d2be",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/mercedes-logo.png",
        "short": "MER",
    },
    "ferrari": {
        "wiki": "https://en.wikipedia.org/wiki/Scuderia_Ferrari",
        "accent": "#dc0000",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/ferrari-logo.png",
        "short": "FER",
    },
    "red_bull": {
        "wiki": "https://en.wikipedia.org/wiki/Red_Bull_Racing",
        "accent": "#1e41ff",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/red-bull-racing-logo.png",
        "short": "RBR",
    },
    "mclaren": {
        "wiki": "https://en.wikipedia.org/wiki/McLaren",
        "accent": "#ff8700",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/mclaren-logo.png",
        "short": "MCL",
    },
    "aston_martin": {
        "wiki": "https://en.wikipedia.org/wiki/Aston_Martin_in_Formula_One",
        "accent": "#006f62",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/aston-martin-logo.png",
        "short": "AMR",
    },
    "alpine": {
        "wiki": "https://en.wikipedia.org/wiki/Alpine_F1_Team",
        "accent": "#ff87bc",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/alpine-logo.png",
        "short": "ALP",
    },
    "williams": {
        "wiki": "https://en.wikipedia.org/wiki/Williams_Racing",
        "accent": "#005aff",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/williams-logo.png",
        "short": "WIL",
    },
    "rb": {
        "wiki": "https://en.wikipedia.org/wiki/Racing_Bulls",
        "accent": "#6692ff",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/racing-bulls-logo.png",
        "short": "RB",
    },
    "haas": {
        "wiki": "https://en.wikipedia.org/wiki/Haas_F1_Team",
        "accent": "#b6babd",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/haas-logo.png",
        "short": "HAA",
    },
    "sauber": {
        "wiki": "https://en.wikipedia.org/wiki/Sauber_Motorsport",
        "accent": "#52e252",
        "logo": "https://media.formula1.com/content/dam/fom-website/teams/2025/kick-sauber-logo.png",
        "short": "SAU",
    },
    "audi": {
        "wiki": "https://en.wikipedia.org/wiki/Audi_in_Formula_One",
        "accent": "#e10600",
        "logo": "",
        "short": "AUD",
    },
    "cadillac": {
        "wiki": "https://en.wikipedia.org/wiki/Cadillac_in_Formula_One",
        "accent": "#d4af37",
        "logo": "",
        "short": "CAD",
    },
}


def get_constructor_meta(constructor_id: str) -> dict[str, str]:
    cid = str(constructor_id or "").casefold()
    return CONSTRUCTOR_WIKI_MAP.get(cid, {"wiki": "", "accent": "#e10600", "logo": "", "short": cid[:3].upper() or "F1"})


def _combine_utc(date_str: str | None, time_str: str | None) -> str:
    if not date_str:
        return ""
    t = (time_str or "00:00:00Z").strip()
    if not t.endswith("Z"):
        t += "Z"
    return f"{date_str.strip()}T{t}"


def _extract_sessions(race: dict[str, Any]) -> list[dict[str, str]]:
    mapping = [
        ("FirstPractice", "Практика 1"),
        ("SecondPractice", "Практика 2"),
        ("ThirdPractice", "Практика 3"),
        ("SprintQualifying", "Спринт-квалификация"),
        ("Sprint", "Спринт"),
        ("Qualifying", "Квалификация"),
    ]
    sessions: list[dict[str, str]] = []
    for key, label in mapping:
        block = race.get(key)
        if isinstance(block, dict) and block.get("date"):
            dt_utc = _combine_utc(block.get("date"), block.get("time"))
            sessions.append({
                "name": label,
                "date_utc": dt_utc,
                "date_local": format_qyzylorda(dt_utc),
            })
    main_utc = _combine_utc(race.get("date"), race.get("time"))
    sessions.append({
        "name": "Гонка",
        "date_utc": main_utc,
        "date_local": format_qyzylorda(main_utc),
    })
    return sessions


def fetch_f1_calendar() -> dict[str, Any]:
    """Загружает календарь текущего сезона F1 и определяет ближайший этап."""
    payload = fetch_json(f"{JOLPICA_BASE}/current.json")
    mr = (payload.get("MRData") or {}) if isinstance(payload, dict) else {}
    races_raw = ((mr.get("RaceTable") or {}).get("Races")) or []
    season = str(mr.get("RaceTable", {}).get("season") or "")

    now = datetime.now(timezone.utc)
    races: list[dict[str, Any]] = []
    next_race: dict[str, Any] | None = None

    for r in races_raw:
        dt_utc = _combine_utc(r.get("date"), r.get("time"))
        dt_obj = parse_utc(dt_utc)
        is_past = bool(dt_obj and dt_obj < now)
        circuit = r.get("Circuit") or {}
        loc = circuit.get("Location") or {}
        item = {
            "round": int(r.get("round") or 0),
            "race_name": r.get("raceName") or "Нет данных",
            "circuit_name": circuit.get("circuitName") or "Нет данных",
            "country": loc.get("country") or "Нет данных",
            "locality": loc.get("locality") or "Нет данных",
            "date_utc": dt_utc,
            "date_local": format_qyzylorda(dt_utc),
            "sessions": _extract_sessions(r),
            "status": "finished" if is_past else "scheduled",
            "source": "Jolpica F1",
        }
        races.append(item)
        if not is_past and next_race is None:
            next_race = item

    return {
        "season": season,
        "next_race": next_race,
        "races": races,
    }


def fetch_f1_standings() -> dict[str, Any]:
    """Загружает личный зачёт гонщиков и Кубок конструкторов."""
    drivers_payload = fetch_json(f"{JOLPICA_BASE}/current/driverStandings.json")
    constructors_payload = fetch_json(f"{JOLPICA_BASE}/current/constructorStandings.json")

    def _first_list(payload: Any, key: str) -> list[dict[str, Any]]:
        mr = (payload.get("MRData") or {}) if isinstance(payload, dict) else {}
        lists = ((mr.get("StandingsTable") or {}).get("StandingsLists")) or []
        return lists[0].get(key, []) if lists else []

    drivers = []
    for d in _first_list(drivers_payload, "DriverStandings"):
        drv = d.get("Driver") or {}
        con = (d.get("Constructors") or [{}])[0]
        cid = con.get("constructorId") or ""
        cmeta = get_constructor_meta(cid)
        drivers.append({
            "pos": int(d.get("position") or 0),
            "driver_id": drv.get("driverId") or "",
            "name": f"{drv.get('givenName', '')} {drv.get('familyName', '')}".strip() or "Нет данных",
            "number": drv.get("permanentNumber") or "—",
            "nationality": drv.get("nationality") or "Нет данных",
            "team": con.get("name") or "Нет данных",
            "constructor_id": cid,
            "team_logo": cmeta.get("logo", ""),
            "team_accent": cmeta.get("accent", "#e10600"),
            "wiki_url": drv.get("url") or "",
            "points": d.get("points") or "0",
            "wins": d.get("wins") or "0",
        })

    constructors = []
    for c in _first_list(constructors_payload, "ConstructorStandings"):
        con = c.get("Constructor") or {}
        cid = con.get("constructorId") or ""
        cmeta = get_constructor_meta(cid)
        constructors.append({
            "pos": int(c.get("position") or 0),
            "constructor_id": cid,
            "name": con.get("name") or "Нет данных",
            "nationality": con.get("nationality") or "Нет данных",
            "logo": cmeta.get("logo", ""),
            "accent": cmeta.get("accent", "#e10600"),
            "short": cmeta.get("short", ""),
            "wiki_url": con.get("url") or cmeta.get("wiki", ""),
            "points": c.get("points") or "0",
            "wins": c.get("wins") or "0",
        })

    return {
        "drivers": drivers,
        "constructors": constructors,
    }


def fetch_f1_last_results() -> dict[str, Any]:
    """Загружает результаты последнего завершённого Гран-при."""
    payload = fetch_json(f"{JOLPICA_BASE}/current/last/results.json")
    mr = (payload.get("MRData") or {}) if isinstance(payload, dict) else {}
    races = ((mr.get("RaceTable") or {}).get("Races")) or []
    if not races:
        return {"race_name": "Нет данных", "results": []}
    race = races[0]
    rows = []
    for res in race.get("Results") or []:
        drv = res.get("Driver") or {}
        con = res.get("Constructor") or {}
        rows.append({
            "pos": res.get("position") or "—",
            "driver": f"{drv.get('givenName', '')} {drv.get('familyName', '')}".strip(),
            "team": con.get("name") or "Нет данных",
            "time": ((res.get("Time") or {}).get("time")) or res.get("status") or "—",
            "points": res.get("points") or "0",
        })
    return {
        "race_name": race.get("raceName") or "Нет данных",
        "date_utc": _combine_utc(race.get("date"), race.get("time")),
        "date_local": format_qyzylorda(_combine_utc(race.get("date"), race.get("time"))),
        "results": rows,
    }


def fetch_f1_round_details(round_num: int) -> dict[str, Any]:
    """Загружает результаты гонки, квалификации и спринта для выбранного этапа."""
    race_payload = fetch_json(f"{JOLPICA_BASE}/current/{round_num}/results.json")
    qual_payload = fetch_json(f"{JOLPICA_BASE}/current/{round_num}/qualifying.json")
    try:
        sprint_payload = fetch_json(f"{JOLPICA_BASE}/current/{round_num}/sprint.json")
    except Exception:
        sprint_payload = {}

    def _first_race(p: Any) -> dict[str, Any]:
        races = (((p.get("MRData") or {}).get("RaceTable") or {}).get("Races")) or []
        return races[0] if races else {}

    race = _first_race(race_payload)
    qual = _first_race(qual_payload)
    sprint = _first_race(sprint_payload)

    race_rows = [
        {
            "pos": r.get("position") or "—",
            "driver": f"{(r.get('Driver') or {}).get('givenName', '')} {(r.get('Driver') or {}).get('familyName', '')}".strip(),
            "driver_id": (r.get("Driver") or {}).get("driverId") or "",
            "team": (r.get("Constructor") or {}).get("name") or "Нет данных",
            "time": ((r.get("Time") or {}).get("time")) or r.get("status") or "—",
            "points": r.get("points") or "0",
        }
        for r in (race.get("Results") or [])
    ]
    qual_rows = [
        {
            "pos": q.get("position") or "—",
            "driver": f"{(q.get('Driver') or {}).get('givenName', '')} {(q.get('Driver') or {}).get('familyName', '')}".strip(),
            "team": (q.get("Constructor") or {}).get("name") or "Нет данных",
            "q1": q.get("Q1") or "—",
            "q2": q.get("Q2") or "—",
            "q3": q.get("Q3") or "—",
        }
        for q in (qual.get("QualifyingResults") or [])
    ]
    sprint_rows = [
        {
            "pos": s.get("position") or "—",
            "driver": f"{(s.get('Driver') or {}).get('givenName', '')} {(s.get('Driver') or {}).get('familyName', '')}".strip(),
            "team": (s.get("Constructor") or {}).get("name") or "Нет данных",
            "time": ((s.get("Time") or {}).get("time")) or s.get("status") or "—",
            "points": s.get("points") or "0",
        }
        for s in (sprint.get("SprintResults") or [])
    ]

    return {
        "round": round_num,
        "race_name": race.get("raceName") or qual.get("raceName") or f"Этап {round_num}",
        "race_results": race_rows,
        "qualifying_results": qual_rows,
        "sprint_results": sprint_rows,
    }


def fetch_f1_driver_profile(driver_id: str) -> dict[str, Any]:
    """Загружает профиль гонщика F1: отдельно текущий сезон и карьерная статистика."""
    drv_payload = fetch_json(f"{JOLPICA_BASE}/drivers/{driver_id}.json")
    drivers = (((drv_payload.get("MRData") or {}).get("DriverTable") or {}).get("Drivers")) or []
    drv = drivers[0] if drivers else {}
    full_name = f"{drv.get('givenName', '')} {drv.get('familyName', '')}".strip() or driver_id

    # Текущий сезон (без смешивания с карьерой)
    season_races_payload = fetch_json(f"{JOLPICA_BASE}/current/drivers/{driver_id}/results.json")
    season_races = (((season_races_payload.get("MRData") or {}).get("RaceTable") or {}).get("Races")) or []
    season_results = []
    current_team = "Нет данных"
    for r in season_races:
        res = (r.get("Results") or [{}])[0]
        if res.get("Constructor"):
            current_team = res["Constructor"].get("name") or current_team
        season_results.append({
            "round": r.get("round"),
            "race_name": r.get("raceName"),
            "position": res.get("position") or "—",
            "points": res.get("points") or "0",
            "status": res.get("status") or "—",
        })

    # Карьера (до 500 последних гонок в Ergast/Jolpica)
    career_payload = fetch_json(f"{JOLPICA_BASE}/drivers/{driver_id}/results.json", params={"limit": 500})
    career_races = (((career_payload.get("MRData") or {}).get("RaceTable") or {}).get("Races")) or []
    starts = len(career_races)
    wins, podiums, poles, fastest_laps = 0, 0, 0, 0
    for r in career_races:
        res = (r.get("Results") or [{}])[0]
        pos = str(res.get("position") or "")
        if pos == "1":
            wins += 1
        if pos in {"1", "2", "3"}:
            podiums += 1
        if str(res.get("grid") or "") == "1":
            poles += 1
        if str(((res.get("FastestLap") or {}).get("rank")) or "") == "1":
            fastest_laps += 1

    return {
        "driver_id": driver_id,
        "name": full_name,
        "number": drv.get("permanentNumber") or "—",
        "nationality": drv.get("nationality") or "Нет данных",
        "date_of_birth": drv.get("dateOfBirth") or "Нет данных",
        "wiki_url": drv.get("url") or "",
        "current_team": current_team,
        "season_results": list(reversed(season_results)),
        "career_stats": {
            "starts": starts,
            "wins": wins,
            "podiums": podiums,
            "poles": poles,
            "fastest_laps": fastest_laps,
        },
        "source": "Jolpica F1",
    }


def fetch_f1_constructor_profile(constructor_id: str) -> dict[str, Any]:
    """Загружает профиль команды (конструктора) Formula 1."""
    con_payload = fetch_json(f"{JOLPICA_BASE}/constructors/{constructor_id}.json")
    cons = (((con_payload.get("MRData") or {}).get("ConstructorTable") or {}).get("Constructors")) or []
    con = cons[0] if cons else {}

    drv_payload = fetch_json(f"{JOLPICA_BASE}/current/constructors/{constructor_id}/drivers.json")
    drvs = (((drv_payload.get("MRData") or {}).get("DriverTable") or {}).get("Drivers")) or []
    drivers_list = [
        {
            "driver_id": d.get("driverId") or "",
            "name": f"{d.get('givenName', '')} {d.get('familyName', '')}".strip(),
            "number": d.get("permanentNumber") or "—",
        }
        for d in drvs
    ]

    cmeta = get_constructor_meta(constructor_id)
    return {
        "constructor_id": constructor_id,
        "name": con.get("name") or constructor_id,
        "nationality": con.get("nationality") or "Нет данных",
        "drivers": drivers_list,
        "logo": cmeta.get("logo", ""),
        "accent": cmeta.get("accent", "#e10600"),
        "short": cmeta.get("short", ""),
        "wiki_url": con.get("url") or cmeta.get("wiki", ""),
        "base": "Нет данных",
        "team_chief": "Нет данных",
        "power_unit": "Нет данных",
        "source": "Jolpica F1",
    }
