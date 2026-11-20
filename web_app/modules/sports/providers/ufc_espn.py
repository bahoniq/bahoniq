"""Адаптер UFC: актуальные чемпионы (UFC.com + проверка свежести) и кард (ESPN UFC Scoreboard)."""
from __future__ import annotations

import html as htmllib
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from ..time_utils import format_qyzylorda
from .base import fetch_json, fetch_text, fetch_text_with_headers

UFC_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
UFC_OFFICIAL_RANKINGS_URL = "https://www.ufc.com/rankings"
UFC_WIKI_CHAMPIONS_URL = "https://en.wikipedia.org/api/rest_v1/page/html/List_of_UFC_champions"
UFC_ATHLETE_URL = "https://site.api.espn.com/apis/common/v3/sports/mma/ufc/athletes/{fighter_id}"

MAX_SOURCE_AGE_DAYS = 30

_DIVISION_MAP: dict[str, tuple[str, str]] = {
    "heavyweight": ("Тяжёлый вес", "men"),
    "light heavyweight": ("Полутяжёлый вес", "men"),
    "middleweight": ("Средний вес", "men"),
    "welterweight": ("Полусредний вес", "men"),
    "lightweight": ("Лёгкий вес", "men"),
    "featherweight": ("Полулёгкий вес", "men"),
    "bantamweight": ("Легчайший вес", "men"),
    "flyweight": ("Наилегчайший вес", "men"),
    "women's bantamweight": ("Женский легчайший вес", "women"),
    "women's flyweight": ("Женский наилегчайший вес", "women"),
    "women's strawweight": ("Женский минимальный вес", "women"),
    "women's featherweight": ("Женский полулёгкий вес", "women"),
}


def translate_weight_class(raw: str | None) -> str:
    clean = " ".join(htmllib.unescape(str(raw or "")).strip().split())
    low = clean.casefold()
    if low in _DIVISION_MAP:
        return _DIVISION_MAP[low][0]
    for k, (ru, _) in _DIVISION_MAP.items():
        if k in low:
            return ru
    if "pound-for-pound" in low:
        return "Женский P4P" if "women" in low else "Мужской P4P"
    return clean or "Весовая категория не указана"


def _map_fight_status(status_obj: dict[str, Any]) -> tuple[str, str]:
    type_obj = status_obj.get("type") or {}
    name = str(type_obj.get("name") or "").upper()
    state = str(type_obj.get("state") or "").lower()
    desc = str(type_obj.get("shortDetail") or type_obj.get("description") or "").strip()

    if "CANCEL" in name:
        return "canceled", "Отменён"
    if "POSTPONE" in name:
        return "postponed", "Перенесён"
    if state == "in":
        return "live", desc or "LIVE"
    if state == "post" or type_obj.get("completed") is True:
        return "finished", "Завершён"
    return "scheduled", "Запланирован"


def fetch_ufc_scoreboard() -> dict[str, Any]:
    """Загружает ближайший/текущий турнир UFC, полный кард и статусы боёв (время Asia/Qyzylorda)."""
    payload = fetch_json(UFC_SCOREBOARD_URL)
    events = payload.get("events") if isinstance(payload, dict) else []
    if not events:
        return {"event": None, "fights": [], "main_event": None, "co_main": None}

    ev = events[0]
    date_utc = str(ev.get("date") or "")
    venue_obj = (ev.get("venues") or [{}])[0] if isinstance(ev.get("venues"), list) else {}
    addr = venue_obj.get("address") or {}
    location = ", ".join(p for p in (venue_obj.get("fullName"), addr.get("city"), addr.get("country")) if p) or "Нет данных"

    fights: list[dict[str, Any]] = []
    comps = ev.get("competitions") or []

    for idx, comp in enumerate(comps):
        competitors = comp.get("competitors") or []
        fa = competitors[0] if len(competitors) > 0 else {}
        fb = competitors[1] if len(competitors) > 1 else {}
        ath_a = fa.get("athlete") or {}
        ath_b = fb.get("athlete") or {}
        rec_a = (fa.get("records") or [{}])[0].get("summary", "Нет данных")
        rec_b = (fb.get("records") or [{}])[0].get("summary", "Нет данных")

        status, status_label = _map_fight_status(comp.get("status") or {})
        winner = None
        if fa.get("winner"):
            winner = ath_a.get("displayName")
        elif fb.get("winner"):
            winner = ath_b.get("displayName")

        # Не выдумываем Main Card / Prelims по позиции в массиве, если источник не передал cardSegment
        raw_segment = comp.get("cardSegment")
        if isinstance(raw_segment, dict):
            seg_label = str(raw_segment.get("description") or raw_segment.get("name") or "")
            seg_src = "ESPN API cardSegment"
        elif isinstance(raw_segment, str) and raw_segment.strip():
            seg_label = raw_segment.strip()
            seg_src = "ESPN API cardSegment"
        else:
            seg_label = "Порядок карда (секция не указана в API ESPN)"
            seg_src = "Не указано в API ESPN"

        fight_dt_utc = str(comp.get("date") or comp.get("startDate") or date_utc)
        wc_raw = ((comp.get("type") or {}).get("text")) or ""
        fights.append({
            "id": str(comp.get("id") or idx),
            "fighter_a": ath_a.get("displayName") or "Нет данных",
            "fighter_b": ath_b.get("displayName") or "Нет данных",
            "fighter_a_id": str(fa.get("id") or ath_a.get("id") or ""),
            "fighter_b_id": str(fb.get("id") or ath_b.get("id") or ""),
            "record_a": rec_a,
            "record_b": rec_b,
            "weight_class": translate_weight_class(wc_raw),
            "card_section": seg_label,
            "card_section_source": seg_src,
            "date_utc": fight_dt_utc,
            "date_local": format_qyzylorda(fight_dt_utc) if fight_dt_utc else "Нет данных",
            "status": status,
            "status_label": status_label,
            "winner": winner,
        })

    # В карде ESPN бои идут от ранних к главному — переворачиваем порядок отображения
    fights_ordered = list(reversed(fights))
    main_event = fights_ordered[0] if fights_ordered else None
    co_main = fights_ordered[1] if len(fights_ordered) > 1 else None
    ev_name = ev.get("name") or ev.get("shortName") or "UFC Event"

    return {
        "event": {
            "id": str(ev.get("id") or ""),
            "name": ev_name,
            "is_numbered": bool(re.search(r"\bUFC\s+\d+\b", ev_name, re.I)),
            "date_utc": date_utc,
            "date_local": format_qyzylorda(date_utc) if date_utc else "Нет данных",
            "location": location,
            "source": "ESPN UFC Scoreboard",
        },
        "main_event": main_event,
        "co_main": co_main,
        "fights": fights_ordered,
    }


def _strip_tags(raw: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _parse_wiki_title_dates() -> dict[str, dict[str, str]]:
    """Дополняет даты завоевания и защиты титулов из актуальной таблицы Wikipedia List of UFC champions."""
    out: dict[str, dict[str, str]] = {}
    try:
        html = fetch_text(UFC_WIKI_CHAMPIONS_URL)
        m = re.search(r'id="Current_champions".*?<table.*?</table>', html, re.S)
        if not m:
            return out
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S):
            cells = [_strip_tags(td) for td in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            if len(cells) >= 4 and "Division" not in cells[0]:
                # Формат таблицы: Division | Champion | Since | Defenses
                div_low = cells[0].casefold()
                champ_name = re.sub(r"\[[^\]]+\]", "", cells[1]).strip()
                since = re.sub(r"\[[^\]]+\]", "", cells[2]).strip()
                defenses = re.sub(r"\[[^\]]+\]", "", cells[3]).strip()
                out[div_low] = {"champion": champ_name, "since": since, "defenses": defenses}
    except Exception:
        pass
    return out


def _parse_http_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_ufc_rankings() -> dict[str, Any]:
    """Загружает актуальных чемпионов, претендентов и P4P с официального UFC.com с проверкой свежести."""
    html_text, headers = fetch_text_with_headers(UFC_OFFICIAL_RANKINGS_URL)

    last_mod_dt = _parse_http_dt(headers.get("last-modified"))
    now_utc = datetime.now(timezone.utc)
    is_fresh = bool(last_mod_dt and (now_utc - last_mod_dt) <= timedelta(days=MAX_SOURCE_AGE_DAYS))
    updated_utc = last_mod_dt.isoformat().replace("+00:00", "Z") if last_mod_dt else ""
    updated_local = format_qyzylorda(updated_utc) if updated_utc else "Дата обновления не подтверждена"

    wiki_dates = _parse_wiki_title_dates()

    # Парсим каждый блок view-grouping
    group_chunks = re.split(r'<div[^>]+class="[^"]*view-grouping(?=["\s])[^"]*"[^>]*>', html_text)[1:]
    divisions: list[dict[str, Any]] = []
    p4p_lists: list[dict[str, Any]] = []
    seen_divs: set[str] = set()

    for chunk in group_chunks:
        hdr_m = re.search(r'<div[^>]+class="[^"]*view-grouping-header[^"]*"[^>]*>(.*?)</div>', chunk, re.S)
        raw_div = _strip_tags(hdr_m.group(1)) if hdr_m else ""
        if not raw_div:
            continue
        div_key = raw_div.casefold()
        if div_key in seen_divs:
            continue
        seen_divs.add(div_key)

        # Лидер / Чемпион блока
        champ_m = re.search(r'rankings--athlete--champion(.*?)</table>', chunk, re.S)
        leader_name = ""
        leader_photo = ""
        if champ_m:
            block = champ_m.group(1)
            a_m = re.search(r'<h5[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.S)
            if not a_m:
                h5_m = re.search(r'<h5[^>]*>(.*?)</h5>', block, re.S)
                leader_name = _strip_tags(h5_m.group(1)) if h5_m else ""
            else:
                leader_name = _strip_tags(a_m.group(1))
            img_m = re.search(r'<img[^>]+src="([^"]+)"', block)
            if img_m:
                leader_photo = img_m.group(1)

        # Претенденты (1..15) из таблицы блока
        contenders: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
            rank_m = re.search(r'views-field-weight-class-rank[^>]*>(.*?)</td>', tr, re.S)
            name_m = re.search(r'views-field-title[^>]*>(.*?)</td>', tr, re.S)
            if rank_m and name_m:
                r_num = _strip_tags(rank_m.group(1))
                c_name = _strip_tags(name_m.group(1))
                if c_name:
                    contenders.append({"rank": r_num, "name": c_name, "id": "", "record": "", "country": ""})

        # Отделяем P4P от весовых категорий
        if "pound-for-pound" in div_key:
            p4p_lists.append({
                "name": translate_weight_class(raw_div),
                "leader": leader_name if is_fresh else "Данные не подтверждены",
                "contenders": contenders[:15],
                "source_url": UFC_OFFICIAL_RANKINGS_URL,
                "updated_local": updated_local,
            })
            continue

        if div_key not in _DIVISION_MAP:
            continue

        ru_name, gender = _DIVISION_MAP[div_key]
        w_info = wiki_dates.get(div_key, {})
        title_since = ""
        title_defenses = ""
        if is_fresh and leader_name and w_info.get("champion", "").casefold() == leader_name.casefold():
            title_since = w_info.get("since", "")
            title_defenses = w_info.get("defenses", "")

        champion_obj = {
            "name": leader_name if (is_fresh and leader_name) else "Актуальный чемпион не подтверждён",
            "verified": bool(is_fresh and leader_name),
            "photo": leader_photo if is_fresh else "",
            "title_since": title_since,
            "title_defenses": title_defenses,
            "updated_utc": updated_utc,
            "updated_local": updated_local,
            "source": "UFC.com Official Rankings",
            "source_url": UFC_OFFICIAL_RANKINGS_URL,
        }
        divisions.append({
            "name": ru_name,
            "name_en": raw_div,
            "gender": gender,
            "champion": champion_obj,
            "contenders": contenders[:10],
        })

    return {
        "divisions": divisions,
        "p4p": p4p_lists,
        "freshness_verified": is_fresh,
        "updated_utc": updated_utc,
        "updated_local": updated_local,
        "source": "UFC.com Official Rankings",
        "source_url": UFC_OFFICIAL_RANKINGS_URL,
    }


_STANCE_MAP = {
    "orthodox": "Правша",
    "southpaw": "Левша",
    "switch": "Смешанная",
}


def _resolve_ufc_fighter_id(fighter_name: str) -> str:
    clean = " ".join(str(fighter_name or "").strip().split())
    if not clean:
        return ""
    try:
        payload = fetch_json(
            "https://site.web.api.espn.com/apis/common/v3/search",
            params={"query": clean, "limit": 5},
        )
        items = payload.get("items") if isinstance(payload, dict) else []
        for it in items or []:
            if str(it.get("league") or "").casefold() == "ufc" and it.get("id"):
                return str(it["id"])
    except Exception:
        pass
    return ""


def _slugify_athlete(name: str) -> str:
    import unicodedata
    norm = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")


def _inches_to_str(raw: str | None) -> str:
    if not raw:
        return "Нет данных"
    try:
        inches = float(raw)
        cm = round(inches * 2.54)
        return f'{inches:.1f}" ({cm} см)'
    except Exception:
        return raw


def _fetch_ufc_com_athlete(fighter_name: str) -> dict[str, Any]:
    """Загружает официальные характеристики бойца со страницы ufc.com/athlete/<slug>."""
    slug = _slugify_athlete(fighter_name)
    if not slug:
        return {}
    try:
        html_text = fetch_text(f"https://www.ufc.com/athlete/{slug}")
    except Exception:
        return {}

    def _bio_field(label: str) -> str:
        m = re.search(rf'c-bio__label[^>]*>\s*{re.escape(label)}\s*</div>\s*<div[^>]*c-bio__text[^>]*>(.*?)</div>', html_text, re.S | re.I)
        return _strip_tags(m.group(1)) if m else ""

    def _hero_field(cls: str) -> str:
        m = re.search(rf'{re.escape(cls)}[^>]*>(.*?)<', html_text, re.S)
        return _strip_tags(m.group(1)) if m else ""

    img_m = re.search(r'class="hero-profile__image"[^>]+src="([^"]+)"', html_text)
    if not img_m:
        img_m = re.search(r'<img[^>]+src="([^"]+)"[^>]+class="hero-profile__image"', html_text)

    rec_raw = _hero_field("hero-profile__division-body")
    rec_m = re.search(r"(\d+-\d+-\d+)", rec_raw)
    div_raw = _hero_field("hero-profile__division-title").replace("Division", "").strip()
    style_raw = _bio_field("Fighting style")
    hometown = _bio_field("Hometown")

    return {
        "id": "",
        "name": fighter_name,
        "nickname": _hero_field("hero-profile__nickname").strip('" ') or "Нет данных",
        "country": hometown or "Нет данных",
        "age": _bio_field("Age") or "Нет данных",
        "height": _inches_to_str(_bio_field("Height")),
        "weight": _bio_field("Weight") or "Нет данных",
        "reach": _inches_to_str(_bio_field("Reach")),
        "stance": _STANCE_MAP.get(style_raw.casefold(), style_raw) or "Нет данных",
        "weight_class": translate_weight_class(div_raw) if div_raw else "Нет данных",
        "record": rec_m.group(1) if rec_m else (rec_raw or "Нет данных"),
        "photo": img_m.group(1) if img_m else "",
        "recent_fights": [],
        "source": "UFC.com Athlete Profile",
    }


def fetch_ufc_fighter_profile(fighter_id: str, fighter_name: str = "") -> dict[str, Any]:
    """Загружает детальный профиль бойца UFC из ESPN Athlete API или UFC.com Athlete."""
    resolved_id = str(fighter_id or "").strip()
    if not resolved_id and fighter_name:
        resolved_id = _resolve_ufc_fighter_id(fighter_name)
    if not resolved_id:
        ufc_prof = _fetch_ufc_com_athlete(fighter_name) if fighter_name else {}
        if ufc_prof and (ufc_prof.get("record") != "Нет данных" or ufc_prof.get("age") != "Нет данных"):
            return ufc_prof
        return {
            "id": "",
            "name": fighter_name or "Нет данных",
            "nickname": "Нет данных",
            "country": "Нет данных",
            "age": "Нет данных",
            "height": "Нет данных",
            "weight": "Нет данных",
            "reach": "Нет данных",
            "stance": "Нет данных",
            "weight_class": "Нет данных",
            "record": "Нет данных",
            "photo": "",
            "recent_fights": [],
            "source": "ESPN UFC",
        }
    payload = fetch_json(UFC_ATHLETE_URL.format(fighter_id=resolved_id))
    ath = payload.get("athlete") if isinstance(payload, dict) else {}
    if not isinstance(ath, dict):
        ath = {}

    flag = ath.get("flag")
    country = (flag.get("alt") if isinstance(flag, dict) else None) or ath.get("citizenship") or "Нет данных"
    stance = ath.get("stance")
    stance_raw = str((stance.get("text") if isinstance(stance, dict) else stance) or "").strip()
    stance_text = _STANCE_MAP.get(stance_raw.casefold(), stance_raw) or "Нет данных"
    wc = ath.get("weightClass")
    wc_text = translate_weight_class((wc.get("text") if isinstance(wc, dict) else wc) or "")

    stats_summary = (ath.get("statsSummary") or {}).get("statistics") or []
    rec = next((s.get("displayValue") for s in stats_summary if "record" in str(s.get("name", "")).casefold()), None)
    if not rec and ath.get("records"):
        rec = (ath.get("records") or [{}])[0].get("summary")

    return {
        "id": str(resolved_id),
        "name": ath.get("displayName") or fighter_name or "Нет данных",
        "nickname": ath.get("nickname") or "Нет данных",
        "country": country,
        "age": ath.get("age") if ath.get("age") is not None else "Нет данных",
        "height": ath.get("displayHeight") or "Нет данных",
        "weight": ath.get("displayWeight") or "Нет данных",
        "reach": ath.get("displayReach") or "Нет данных",
        "stance": stance_text,
        "weight_class": wc_text,
        "record": rec or "Нет данных",
        "photo": ((ath.get("headshot") or {}).get("href")) or "",
        "recent_fights": [],
        "source": "ESPN UFC",
    }
