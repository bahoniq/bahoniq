"""Адаптер ESPN Soccer API для Real Madrid, Juventus и Manchester United."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..time_utils import format_qyzylorda, parse_utc, utc_now_iso
from .base import fetch_json
from .translator import translate_en_to_ru

CLUBS_CONFIG: dict[str, dict[str, Any]] = {
    "real_madrid": {
        "id": "real_madrid",
        "name": "Real Madrid",
        "espn_id": "86",
        "league": "esp.1",
        "league_name": "La Liga",
        "country": "Испания",
        "accent": "#fbbf24",
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
        "keywords": ["real madrid", "los blancos", "bernabeu", "мадрид", "реал мадрид"],
    },
    "juventus": {
        "id": "juventus",
        "name": "Juventus",
        "espn_id": "111",
        "league": "ita.1",
        "league_name": "Serie A",
        "country": "Италия",
        "accent": "#e2e8f0",
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
        "keywords": ["juventus", "juve", "bianconeri", "ювентус", "турин"],
    },
    "man_utd": {
        "id": "man_utd",
        "name": "Manchester United",
        "espn_id": "360",
        "league": "eng.1",
        "league_name": "Premier League",
        "country": "Англия",
        "accent": "#ef4444",
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
        "keywords": ["manchester united", "man utd", "man united", "red devils", "old trafford", "манчестер юнайтед"],
    },
}

_POSITION_MAP: dict[str, tuple[str, str]] = {
    "goalkeeper": ("Вратарь", "gk"),
    "keeper": ("Вратарь", "gk"),
    "defender": ("Защитник", "def"),
    "center back": ("Центральный защитник", "def"),
    "centre back": ("Центральный защитник", "def"),
    "left back": ("Левый защитник", "def"),
    "right back": ("Правый защитник", "def"),
    "wing back": ("Фланговый защитник", "def"),
    "midfielder": ("Полузащитник", "mid"),
    "defensive midfielder": ("Опорный полузащитник", "mid"),
    "central midfielder": ("Центральный полузащитник", "mid"),
    "attacking midfielder": ("Атакующий полузащитник", "mid"),
    "forward": ("Нападающий", "fwd"),
    "attacker": ("Нападающий", "fwd"),
    "striker": ("Центрфорвард", "fwd"),
    "winger": ("Вингер", "fwd"),
    "left winger": ("Левый вингер", "fwd"),
    "right winger": ("Правый вингер", "fwd"),
}

_COUNTRY_MAP: dict[str, str] = {
    "spain": "Испания", "esp": "Испания",
    "france": "Франция", "fra": "Франция",
    "brazil": "Бразилия", "bra": "Бразилия",
    "england": "Англия", "eng": "Англия",
    "united kingdom": "Великобритания", "gbr": "Великобритания",
    "scotland": "Шотландия", "sco": "Шотландия",
    "wales": "Уэльс", "wal": "Уэльс",
    "northern ireland": "Северная Ирландия", "nir": "Северная Ирландия",
    "ireland": "Ирландия", "irl": "Ирландия",
    "italy": "Италия", "ita": "Италия",
    "germany": "Германия", "ger": "Германия",
    "portugal": "Португалия", "por": "Португалия",
    "argentina": "Аргентина", "arg": "Аргентина",
    "uruguay": "Уругвай", "uru": "Уругвай",
    "croatia": "Хорватия", "cro": "Хорватия",
    "belgium": "Бельгия", "bel": "Бельгия",
    "netherlands": "Нидерланды", "ned": "Нидерланды",
    "morocco": "Марокко", "mar": "Марокко",
    "turkey": "Турция", "tur": "Турция", "türkiye": "Турция",
    "denmark": "Дания", "den": "Дания",
    "ukraine": "Украина", "ukr": "Украина",
    "austria": "Австрия", "aut": "Австрия",
    "norway": "Норвегия", "nor": "Норвегия",
    "sweden": "Швеция", "swe": "Швеция",
    "united states": "США", "usa": "США",
    "colombia": "Колумбия", "col": "Колумбия",
    "serbia": "Сербия", "srb": "Сербия",
    "poland": "Польша", "pol": "Польша",
    "slovenia": "Словения", "svn": "Словения",
    "switzerland": "Швейцария", "sui": "Швейцария",
    "cameroon": "Камерун", "cmr": "Камерун",
    "ivory coast": "Кот-д'Ивуар", "côte d'ivoire": "Кот-д'Ивуар", "civ": "Кот-д'Ивуар",
    "canada": "Канада", "can": "Канада",
    "montenegro": "Черногория", "mne": "Черногория",
    "kosovo": "Косово", "kos": "Косово",
    "paraguay": "Парагвай", "par": "Парагвай",
    "ecuador": "Эквадор", "ecu": "Эквадор",
    "senegal": "Сенегал", "sen": "Сенегал",
    "ghana": "Гана", "gha": "Гана",
    "nigeria": "Нигерия", "nga": "Нигерия",
    "egypt": "Египет", "egy": "Египет",
    "japan": "Япония", "jpn": "Япония",
    "south korea": "Южная Корея", "kor": "Южная Корея",
}


def translate_position(raw_pos: str | None) -> tuple[str, str]:
    clean = str(raw_pos or "").strip()
    low = clean.casefold()
    if low in _POSITION_MAP:
        return _POSITION_MAP[low]
    if "goal" in low or "keep" in low:
        return "Вратарь", "gk"
    if "def" in low or "back" in low:
        return "Защитник", "def"
    if "mid" in low:
        return "Полузащитник", "mid"
    if "forw" in low or "strik" in low or "wing" in low or "att" in low:
        return "Нападающий", "fwd"
    return clean or "Нет данных", "other"


def translate_country(raw_country: str | None) -> str:
    clean = str(raw_country or "").strip()
    if not clean or clean == "Нет данных":
        return "Нет данных"
    low = clean.casefold()
    if low in _COUNTRY_MAP:
        return _COUNTRY_MAP[low]
    ru, _ = translate_en_to_ru(clean)
    return ru or clean


def _map_status(status_obj: dict[str, Any]) -> tuple[str, str]:
    type_obj = status_obj.get("type") or {}
    state = str(type_obj.get("state") or "").lower()
    name = str(type_obj.get("name") or "").upper()
    desc = str(type_obj.get("shortDetail") or type_obj.get("description") or "").strip()

    if "POSTPONED" in name:
        return "postponed", "Перенесён"
    if "CANCELED" in name or "CANCELLED" in name:
        return "canceled", "Отменён"
    if state == "in":
        return "live", "Идёт матч" if desc.casefold() in {"", "in progress"} else desc
    if state == "post" or type_obj.get("completed") is True:
        return "finished", "Завершён"
    return "scheduled", "Запланирован"


def _extract_score(competitor: dict[str, Any]) -> int | None:
    raw = competitor.get("score")
    if isinstance(raw, dict):
        raw = raw.get("value") if raw.get("value") is not None else raw.get("displayValue")
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _normalize_event(ev: dict[str, Any], club_key: str, default_league: str) -> dict[str, Any] | None:
    comps = ev.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    home_team = (home.get("team") or {}).get("displayName") or "Нет данных"
    away_team = (away.get("team") or {}).get("displayName") or "Нет данных"
    home_score = _extract_score(home)
    away_score = _extract_score(away)

    date_utc = str(ev.get("date") or comp.get("date") or "")
    status, status_label = _map_status(comp.get("status") or {})
    venue = ((comp.get("venue") or {}).get("fullName")) or "Нет данных"
    league_name = ((ev.get("season") or {}).get("displayName")) or default_league

    return {
        "id": str(ev.get("id") or ""),
        "club_id": club_key,
        "league": str(league_name),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score if status in {"live", "finished"} else None,
        "away_score": away_score if status in {"live", "finished"} else None,
        "date_utc": date_utc,
        "date_local": format_qyzylorda(date_utc),
        "status": status,
        "status_label": status_label,
        "venue": venue,
        "home_logo": ((home.get("team") or {}).get("logos") or [{}])[0].get("href", ""),
        "away_logo": ((away.get("team") or {}).get("logos") or [{}])[0].get("href", ""),
        "source": "ESPN Soccer",
    }


def _compute_form(finished_chrono: list[dict[str, Any]], club_name: str) -> list[str]:
    form: list[str] = []
    target = club_name.casefold()
    for m in finished_chrono[-5:]:
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None:
            continue
        is_home = target in str(m.get("home_team", "")).casefold()
        gf, ga = (hs, as_) if is_home else (as_, hs)
        if gf > ga:
            form.append("W")
        elif gf < ga:
            form.append("L")
        else:
            form.append("D")
    return form


def fetch_club_schedule(club_key: str) -> dict[str, Any]:
    """Загружает и объединяет прошедшие (/schedule) и будущие (/schedule?fixture=true) матчи клуба."""
    cfg = CLUBS_CONFIG[club_key]
    base_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{cfg['league']}/teams/{cfg['espn_id']}/schedule"

    raw_events: list[dict[str, Any]] = []
    season_display = ""
    raw_count = 0

    for params in (None, {"fixture": "true"}):
        try:
            payload = fetch_json(base_url, params=params)
            if isinstance(payload, dict):
                if not season_display:
                    season_display = str((payload.get("season") or {}).get("displayName") or "")
                evs = payload.get("events") or []
                raw_count += len(evs)
                raw_events.extend(evs)
        except Exception:
            if params is None and not raw_events:
                raise

    seen_ids: set[str] = set()
    matches: list[dict[str, Any]] = []
    for ev in raw_events:
        norm = _normalize_event(ev, club_key, cfg["league_name"])
        if norm and norm["id"] and norm["id"] not in seen_ids:
            seen_ids.add(norm["id"])
            matches.append(norm)

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    matches.sort(key=lambda m: parse_utc(m["date_utc"]) or epoch)

    finished_chrono: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []

    for m in matches:
        dt = parse_utc(m["date_utc"])
        if m["status"] == "finished":
            if dt is None or dt <= now + timedelta(minutes=10):
                finished_chrono.append(m)
        elif m["status"] in {"scheduled", "live", "postponed"}:
            if dt is None or dt >= now - timedelta(hours=3):
                upcoming.append(m)

    finished_desc = list(reversed(finished_chrono))

    return {
        "club": cfg,
        "season": season_display or cfg["league_name"],
        "raw_count": raw_count,
        "last_match": finished_desc[0] if finished_desc else None,
        "next_match": upcoming[0] if upcoming else None,
        "form": _compute_form(finished_chrono, cfg["name"]),
        "matches": matches,
        "recent_results": finished_desc[:5],
        "season_results": finished_desc,
        "upcoming_matches": upcoming,
    }


def fetch_club_roster(club_key: str) -> dict[str, Any]:
    """Загружает состав (сгруппированный по позициям на русском), тренеров и травмы клуба."""
    cfg = CLUBS_CONFIG[club_key]
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{cfg['league']}/teams/{cfg['espn_id']}/roster"
    payload = fetch_json(url)
    athletes = payload.get("athletes") if isinstance(payload, dict) else []
    coaches_raw = payload.get("coach") if isinstance(payload, dict) else []

    players: list[dict[str, Any]] = []
    injuries: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {"gk": [], "def": [], "mid": [], "fwd": [], "other": []}

    for a in athletes or []:
        raw_pos = ((a.get("position") or {}).get("displayName")) or ""
        pos_ru, pos_group = translate_position(raw_pos)
        pid = str(a.get("id") or "")
        name = a.get("fullName") or a.get("displayName") or "Нет данных"
        raw_country = a.get("citizenship") or ((a.get("birthCountry") or {}).get("abbreviation")) or "Нет данных"
        country_ru = translate_country(raw_country)

        player_inj = a.get("injuries") or []
        if player_inj:
            for inj in player_inj:
                injuries.append({
                    "player": name,
                    "status": inj.get("status") or "Травма / под вопросом",
                    "detail": inj.get("shortComment") or inj.get("longComment") or "Нет данных",
                })
        entry = {
            "id": pid,
            "name": name,
            "jersey": str(a.get("jersey") or "—"),
            "position": pos_ru,
            "position_group": pos_group,
            "nationality": country_ru,
            "age": a.get("age") if a.get("age") is not None else "Нет данных",
            "date_of_birth": str(a.get("dateOfBirth") or "Нет данных")[:10],
            "height": a.get("displayHeight") or "Нет данных",
            "club": cfg["name"],
            "photo": ((a.get("headshot") or {}).get("href")) or "",
            "season_stats": _extract_player_stats(a),
        }
        players.append(entry)
        grouped.setdefault(pos_group, grouped["other"]).append(entry)

    coaches = [
        {
            "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip() or "Нет данных",
            "role": "Главный тренер",
        }
        for c in (coaches_raw or [])
        if isinstance(c, dict)
    ]

    return {
        "club": cfg,
        "players": players,
        "roster_grouped": grouped,
        "coaches": coaches,
        "injuries": injuries,
    }


def fetch_league_standings(league: str) -> dict[str, Any]:
    """Загружает полную турнирную таблицу лиги со всеми столбцами и сезоном."""
    url = f"https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings"
    payload = fetch_json(url)
    children = payload.get("children") if isinstance(payload, dict) else []
    if not children:
        return {"season": "", "updated_at_utc": utc_now_iso(), "updated_at_local": format_qyzylorda(utc_now_iso()), "rows": []}

    stand_obj = children[0].get("standings") or {}
    season_name = str(
        stand_obj.get("seasonDisplayName")
        or ((payload.get("season") or {}).get("displayName"))
        or ""
    )
    entries = stand_obj.get("entries") or []
    rows: list[dict[str, Any]] = []
    for idx, entry in enumerate(entries, start=1):
        team = entry.get("team") or {}
        stats = {s.get("name"): (s.get("displayValue") if s.get("displayValue") is not None else s.get("value")) for s in (entry.get("stats") or [])}
        gf = str(stats.get("pointsFor", "0"))
        ga = str(stats.get("pointsAgainst", "0"))
        rows.append({
            "pos": int(float(stats.get("rank") or idx)),
            "team_id": str(team.get("id") or ""),
            "team": team.get("displayName") or "Нет данных",
            "logo": ((team.get("logos") or [{}])[0].get("href")) or "",
            "played": stats.get("gamesPlayed", "0"),
            "wins": stats.get("wins", "0"),
            "draws": stats.get("ties", "0"),
            "losses": stats.get("losses", "0"),
            "gf": gf,
            "ga": ga,
            "goals": f"{gf}:{ga}",
            "gd": stats.get("pointDifferential", "0"),
            "points": stats.get("points", "0"),
        })
    now_iso = utc_now_iso()
    return {
        "season": season_name,
        "updated_at_utc": now_iso,
        "updated_at_local": format_qyzylorda(now_iso),
        "raw_count": len(entries),
        "rows": rows,
    }


def _extract_player_stats(athlete: dict[str, Any]) -> dict[str, Any]:
    """Извлекает статистику игрока за текущий сезон из ответа ESPN roster."""
    stats_out: dict[str, Any] = {
        "appearances": "Нет данных",
        "goals": "Нет данных",
        "assists": "Нет данных",
        "minutes": "Нет данных",
        "yellow_cards": "Нет данных",
        "red_cards": "Нет данных",
    }
    cats = ((athlete.get("statistics") or {}).get("splits") or {}).get("categories") or []
    flat: dict[str, str] = {}
    for cat in cats:
        for st in cat.get("stats") or []:
            name = st.get("name")
            if name:
                flat[name] = str(st.get("displayValue") or st.get("value") or "0")
    if flat:
        stats_out["appearances"] = flat.get("appearances", flat.get("gamesPlayed", "Нет данных"))
        stats_out["goals"] = flat.get("totalGoals", flat.get("goals", "Нет данных"))
        stats_out["assists"] = flat.get("goalAssists", flat.get("assists", "Нет данных"))
        stats_out["minutes"] = flat.get("minutes", "Нет данных")
        stats_out["yellow_cards"] = flat.get("yellowCards", "Нет данных")
        stats_out["red_cards"] = flat.get("redCards", "Нет данных")
    return stats_out


def fetch_match_detail(club_key: str, event_id: str) -> dict[str, Any]:
    """Загружает детальную информацию о матче (составы, схема, голы, карточки, замены, статистика)."""
    cfg = CLUBS_CONFIG[club_key]
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{cfg['league']}/summary"
    payload = fetch_json(url, params={"event": event_id})
    if not isinstance(payload, dict):
        raise ValueError("Пустой ответ деталей матча")

    header = payload.get("header") or {}
    comp = (header.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    date_utc = str(comp.get("date") or "")
    status, status_label = _map_status(comp.get("status") or {})
    game_info = payload.get("gameInfo") or {}
    venue = ((game_info.get("venue") or {}).get("fullName")) or ((comp.get("venue") or {}).get("fullName")) or "Нет данных"
    league_name = ((header.get("league") or {}).get("name")) or cfg["league_name"]
    stage = ((header.get("season") or {}).get("name")) or "Нет данных"

    home_team_obj = home.get("team") or {}
    away_team_obj = away.get("team") or {}
    home_name = home_team_obj.get("displayName") or "Нет данных"
    away_name = away_team_obj.get("displayName") or "Нет данных"
    home_logo = (home_team_obj.get("logos") or [{}])[0].get("href", "")
    away_logo = (away_team_obj.get("logos") or [{}])[0].get("href", "")

    rosters_out = []
    for r in payload.get("rosters") or []:
        t_obj = r.get("team") or {}
        team_name = t_obj.get("displayName") or "Команда"
        team_logo = (t_obj.get("logos") or [{}])[0].get("href", "")
        formation = r.get("formation") or "Нет данных"
        starters, subs = [], []
        for p in r.get("roster") or []:
            ath = p.get("athlete") or {}
            pos_ru, _ = translate_position(((p.get("position") or {}).get("displayName")) or "")
            plays = p.get("plays") or []
            goals_cnt = sum(1 for pl in plays if pl.get("didScore") or pl.get("scoringPlay"))
            assists_cnt = sum(1 for pl in plays if pl.get("didAssist"))
            yc_cnt = sum(1 for pl in plays if pl.get("yellowCard"))
            rc_cnt = sum(1 for pl in plays if pl.get("redCard"))
            sub_out = any(pl.get("substitution") for pl in plays)
            entry = {
                "id": str(ath.get("id") or ""),
                "name": ath.get("displayName") or "Нет данных",
                "short_name": ath.get("shortName") or ath.get("displayName") or "Нет данных",
                "jersey": str(p.get("jersey") or "—"),
                "position": pos_ru,
                "formation_place": int(p.get("formationPlace") or 0) if str(p.get("formationPlace") or "").isdigit() else 0,
                "goals": goals_cnt,
                "assists": assists_cnt,
                "yellow_cards": yc_cnt,
                "red_cards": rc_cnt,
                "subbed_out": sub_out,
                "photo": ((ath.get("headshot") or {}).get("href")) or "",
            }
            if p.get("starter"):
                starters.append(entry)
            else:
                subs.append(entry)
        starters.sort(key=lambda x: x["formation_place"] or 99)
        rosters_out.append({
            "team": team_name,
            "logo": team_logo,
            "home_away": r.get("homeAway", ""),
            "formation": formation,
            "starters": starters,
            "subs": subs,
        })

    goals, cards, subs_events, timeline = [], [], [], []
    for ev in payload.get("keyEvents") or []:
        ev_type = ((ev.get("type") or {}).get("text")) or ""
        clock = ((ev.get("clock") or {}).get("displayValue")) or ""
        text = ev.get("text") or ev.get("shortText") or ""
        team_name = (ev.get("team") or {}).get("displayName") or ""
        participants = [((p.get("athlete") or {}).get("displayName")) for p in (ev.get("participants") or []) if (p.get("athlete") or {}).get("displayName")]
        item = {
            "clock": clock,
            "type": ev_type,
            "team": team_name,
            "text": text,
            "players": participants,
            "scorer": participants[0] if participants else "",
            "assist": participants[1] if len(participants) > 1 else "",
            "sub_in": participants[0] if len(participants) > 0 else "",
            "sub_out": participants[1] if len(participants) > 1 else "",
            "is_red": "red" in ev_type.casefold(),
            "is_yellow": "yellow" in ev_type.casefold(),
        }
        timeline.append(item)
        low = ev_type.casefold()
        if "goal" in low:
            goals.append(item)
        elif "card" in low:
            cards.append(item)
        elif "sub" in low:
            subs_events.append(item)

    team_stats = []
    for t in ((payload.get("boxscore") or {}).get("teams") or []):
        t_name = (t.get("team") or {}).get("displayName") or "Команда"
        stats_list = [
            {"label": s.get("label") or s.get("name"), "value": s.get("displayValue") or "0"}
            for s in (t.get("statistics") or [])
            if s.get("label") or s.get("name")
        ]
        team_stats.append({"team": t_name, "stats": stats_list})

    return {
        "id": str(event_id),
        "club_id": club_key,
        "league": league_name,
        "stage": str(stage),
        "venue": venue,
        "date_utc": date_utc,
        "date_local": format_qyzylorda(date_utc),
        "status": status,
        "status_label": status_label,
        "home_team": home_name,
        "away_team": away_name,
        "home_logo": home_logo,
        "away_logo": away_logo,
        "home_score": _extract_score(home),
        "away_score": _extract_score(away),
        "rosters": rosters_out,
        "goals": goals,
        "cards": cards,
        "substitutions": subs_events,
        "timeline": timeline,
        "team_stats": team_stats,
        "source": "ESPN Soccer Summary",
    }


def fetch_league_leaders(league_code: str) -> dict[str, Any]:
    """Загружает лучших бомбардиров и ассистентов чемпионата через ESPN statistics API."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/statistics"
    payload = fetch_json(url)
    stats = payload.get("stats") if isinstance(payload, dict) else []
    scorers: list[dict[str, Any]] = []
    assists: list[dict[str, Any]] = []

    def _parse_leaders(raw_leaders: list[dict[str, Any]], stat_key: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, ld in enumerate((raw_leaders or [])[:10], start=1):
            ath = ld.get("athlete") or {}
            team_obj = ath.get("team") or ld.get("team") or {}
            disp = str(ld.get("displayValue") or "")
            matches = ""
            stat_val = ld.get("value")
            if "Matches:" in disp:
                for part in disp.split(","):
                    if "Matches:" in part:
                        matches = part.split(":", 1)[1].strip()
                    elif f"{stat_key}:" in part:
                        stat_val = part.split(":", 1)[1].strip()
            if stat_val is None:
                stat_val = disp or "0"
            else:
                try:
                    stat_val = int(float(stat_val)) if float(stat_val).is_integer() else stat_val
                except Exception:
                    pass
            out.append({
                "rank": idx,
                "id": str(ath.get("id") or ""),
                "name": str(ath.get("displayName") or ath.get("fullName") or "Нет данных"),
                "team": str(team_obj.get("displayName") or team_obj.get("shortDisplayName") or "—"),
                "matches": matches or "—",
                "value": str(stat_val),
                "photo": ((ath.get("headshot") or {}).get("href")) or "",
            })
        return out

    for st in stats or []:
        sname = str(st.get("name") or "")
        if sname == "goalsLeaders":
            scorers = _parse_leaders(st.get("leaders") or [], "Goals")
        elif sname == "assistsLeaders":
            assists = _parse_leaders(st.get("leaders") or [], "Assists")

    return {"scorers": scorers, "assists": assists}
