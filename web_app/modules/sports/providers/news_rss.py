"""Полноценный русскоязычный новостной агрегатор BahonIQ Sports (RSS + Atom)."""
from __future__ import annotations

import hashlib
import html as htmllib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..time_utils import format_qyzylorda, parse_utc, utc_now_iso
from .base import fetch_text
from .translator import translate_en_to_ru

ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Стабильные источники новостей (только Formula 1 и UFC, чтобы хаб оставался лёгким)
NEWS_CENTER_FEEDS: list[dict[str, Any]] = [
    # Formula 1
    {"source": "Autosport F1", "url": "https://www.autosport.com/rss/f1/news/", "default_topic": "f1", "category": "f1", "limit": 12},
    {"source": "Motorsport F1", "url": "https://www.motorsport.com/rss/f1/news/", "default_topic": "f1", "category": "f1", "limit": 10},
    # UFC / MMA
    {"source": "BBC Sport MMA", "url": "https://feeds.bbci.co.uk/sport/mixed-martial-arts/rss.xml", "default_topic": "ufc", "category": "ufc", "limit": 12},
    {"source": "Google News · UFC", "url": "https://news.google.com/rss/search?q=UFC+when:7d&hl=en-US&gl=US&ceid=US:en", "default_topic": "ufc", "category": "ufc", "limit": 10},
]

RSS_FEEDS = {
    "football": [
        (f["source"], f["url"]) for f in NEWS_CENTER_FEEDS if f["category"] == "football"
    ],
    "f1": [
        (f["source"], f["url"]) for f in NEWS_CENTER_FEEDS if f["category"] == "f1"
    ],
    "ufc": [
        (f["source"], f["url"]) for f in NEWS_CENTER_FEEDS if f["category"] == "ufc"
    ],
}

CATEGORY_RU = {
    "football": "Футбол",
    "f1": "Formula 1",
    "ufc": "UFC",
}

TOPIC_LABELS = {
    "real_madrid": "Real Madrid",
    "juventus": "Juventus",
    "man_utd": "Manchester United",
    "f1": "Formula 1",
    "ufc": "UFC",
    "transfers": "Трансферы",
}

ENTITY_DICTS: dict[str, dict[str, Any]] = {
    "real_madrid": {
        "keywords": (
            "real madrid", "los blancos", "bernabeu", "bernabeú", "la liga",
            "mbappe", "mbappé", "vinicius", "vinícius", "bellingham", "valverde",
            "courtois", "camavinga", "tchouameni", "rodrygo", "guler", "güler",
            "ancelotti", "xabi alonso", "arbeloa", "carvajal", "rudiger", "rüdiger",
        ),
    },
    "juventus": {
        "keywords": (
            "juventus", "juve", "bianconeri", "turin", "allianz stadium", "serie a",
            "vlahovic", "vlahović", "yildiz", "yıldız", "bremer", "locatelli",
            "koopmeiners", "cambiaso", "di gregorio", "thuram", "tudor", "spalletti",
        ),
    },
    "man_utd": {
        "keywords": (
            "manchester united", "man utd", "man united", "red devils", "old trafford",
            "bruno fernandes", "fernandes", "mainoo", "garnacho", "amass", "martinez",
            "de ligt", "mazraoui", "onana", "rasmus hojlund", "hojlund", "amorim",
            "cunha", "sesko", "mbeumo", "rashford", "casemiro", "dalot",
        ),
    },
    "f1": {
        "keywords": (
            "formula 1", "formula one", "f1", "grand prix", "qualifying", "pole position",
            "verstappen", "hamilton", "leclerc", "norris", "piastri", "russell",
            "antonelli", "alonso", "sainz", "ferrari", "mercedes", "red bull",
            "mclaren", "aston martin", "williams", "alpine", "haas", "audi", "cadillac",
            "las vegas gp", "qatar gp", "abu dhabi gp", "fia", "constructor",
        ),
    },
    "ufc": {
        "keywords": (
            "ufc", "mma", "octagon", "dana white", "makhachev", "prochazka", "procházka",
            "volkanovski", "topuria", "gaethje", "petr yan", "yan", "gane", "aspinall",
            "strickland", "ulberg", "pereira", "chimaev", "kayla harrison", "dern",
            "natalia silva", "joshua van", "fight night", "title fight", "heavyweight",
            "welterweight", "lightweight", "bantamweight", "featherweight", "middleweight",
        ),
    },
}

F1_CONSTRUCTOR_NAMES = {
    "mercedes": ("Mercedes", ("mercedes",)),
    "ferrari": ("Ferrari", ("ferrari", "scuderia")),
    "red_bull": ("Red Bull", ("red bull",)),
    "mclaren": ("McLaren", ("mclaren",)),
    "aston_martin": ("Aston Martin", ("aston martin",)),
    "alpine": ("Alpine", ("alpine",)),
    "williams": ("Williams", ("williams",)),
    "rb": ("RB F1 Team", ("racing bulls", "rb f1")),
    "haas": ("Haas", ("haas",)),
    "audi": ("Audi", ("audi",)),
    "cadillac": ("Cadillac", ("cadillac",)),
}

F1_DRIVER_SLUGS = {
    "max_verstappen": ("Max Verstappen", ("verstappen",)),
    "hamilton": ("Lewis Hamilton", ("hamilton",)),
    "leclerc": ("Charles Leclerc", ("leclerc",)),
    "norris": ("Lando Norris", ("norris",)),
    "piastri": ("Oscar Piastri", ("piastri",)),
    "russell": ("George Russell", ("russell",)),
    "antonelli": ("Kimi Antonelli", ("antonelli",)),
    "alonso": ("Fernando Alonso", ("alonso",)),
    "sainz": ("Carlos Sainz", ("sainz",)),
}

UFC_FIGHTER_NAMES = (
    "Islam Makhachev", "Jiří Procházka", "Petr Yan", "Justin Gaethje",
    "Alexander Volkanovski", "Sean Strickland", "Carlos Ulberg", "Ciryl Gane",
    "Joshua Van", "Kayla Harrison", "Mackenzie Dern", "Natalia Silva",
    "Ilia Topuria", "Alex Pereira", "Tom Aspinall", "Khamzat Chimaev",
)

RUMOR_MARKERS = (
    "rumour", "rumor", "gossip", "linked with", "could sign", "talks",
    "interest in", "want to sign", "eyeing", "transfer news", "monitored",
    "интерес", "слух", "может перейти", "переговор", "radar", "target",
)
TRANSFER_MARKERS = (
    "transfer", "sign", "signs", "signed", "signing", "loan", "deal", "bid",
    "contract", "extension", "free agent", "clause", "move to", "leaves", "joins",
    "трансфер", "переход", "подписал", "аренд", "контракт",
)
CONFIRMED_IN_MARKERS = ("signs for", "completes move", "officially joins", "announces signing", "подписал", "перешёл в")
CONFIRMED_OUT_MARKERS = ("leaves", "departs", "sold to", "loaned to", "покинул", "ушёл в")


def _canonical_url(raw: str) -> str:
    if not raw:
        return ""
    try:
        u = urlparse(raw.strip())
        kept = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k.lower() not in {"oc", "ref", "src"}]
        return urlunparse((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), "", urlencode(kept), ""))
    except Exception:
        return raw.strip()


def _pub_to_utc(raw: str | None) -> str:
    if not raw:
        return ""
    s = raw.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    dt2 = parse_utc(s)
    if dt2:
        return dt2.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return ""


def _strip_html(raw: str | None) -> str:
    txt = htmllib.unescape(str(raw or ""))
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _extract_image(node: ET.Element) -> str:
    for child in node:
        tag = child.tag.lower()
        if tag.endswith("thumbnail") or tag.endswith("content") or tag == "enclosure":
            url = child.attrib.get("url") or ""
            mtype = (child.attrib.get("type") or "").lower()
            if url and (not mtype or mtype.startswith("image/")):
                return url.strip()
    return ""


def _kw_match(kw: str, text_low: str) -> bool:
    return bool(re.search(rf"(?<![a-zа-яё0-9]){re.escape(kw)}(?![a-zа-яё0-9])", text_low))


def _classify_item(text_low: str, default_topic: str, default_cat: str) -> tuple[list[str], str, list[dict[str, str]]]:
    topics: list[str] = []
    entities: list[dict[str, str]] = []

    for topic_key, cfg in ENTITY_DICTS.items():
        if any(_kw_match(k, text_low) for k in cfg["keywords"]):
            topics.append(topic_key)

    if default_topic in TOPIC_LABELS and default_topic not in topics:
        # Для специализированных лент (Managing Madrid, JuveFC) сохраняем базовый клуб
        if default_topic in {"real_madrid", "juventus", "man_utd", "f1", "ufc"}:
            topics.append(default_topic)

    # Определяем основную категорию
    cat = default_cat
    if any(t in topics for t in ("real_madrid", "juventus", "man_utd")):
        cat = "football"
    elif "f1" in topics:
        cat = "f1"
    elif "ufc" in topics:
        cat = "ufc"

    is_transfer = any(_kw_match(m, text_low) for m in TRANSFER_MARKERS)
    if is_transfer and "transfers" not in topics:
        topics.append("transfers")

    # Связанные сущности для переходов внутри Sports Hub
    for cid in ("real_madrid", "juventus", "man_utd"):
        if cid in topics:
            entities.append({"type": "club", "id": cid, "label": TOPIC_LABELS[cid]})

    if "f1" in topics:
        for cid, (cname, kws) in F1_CONSTRUCTOR_NAMES.items():
            if any(_kw_match(k, text_low) for k in kws):
                entities.append({"type": "f1_constructor", "id": cid, "label": cname})
        for did, (dname, kws) in F1_DRIVER_SLUGS.items():
            if any(_kw_match(k, text_low) for k in kws):
                entities.append({"type": "f1_driver", "id": did, "label": dname})

    if "ufc" in topics:
        for fname in UFC_FIGHTER_NAMES:
            parts = [p for p in fname.casefold().split() if len(p) >= 4]
            if any(_kw_match(p, text_low) for p in parts):
                entities.append({"type": "ufc_fighter", "id": "", "name": fname, "label": fname})

    return topics, cat, entities[:8]


def _build_neutral_digest(category_ru: str, topics: list[str], source: str, title_ru: str, summary_ru: str) -> str:
    topic_names = [TOPIC_LABELS[t] for t in topics if t in TOPIC_LABELS]
    scope = ", ".join(topic_names) if topic_names else category_ru
    lead = summary_ru if summary_ru and summary_ru != "Нет описания" else title_ru
    return f"Краткое изложение ({source} · {scope}): {lead}"


def _parse_feed_entries(xml_text: str, source_name: str, default_topic: str, default_cat: str, max_items: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    rows: list[dict[str, Any]] = []
    nodes = root.findall(".//item")
    is_atom = False
    if not nodes:
        nodes = root.findall(f".//{ATOM_NS}entry")
        is_atom = True

    for node in nodes:
        if is_atom:
            title_orig = _strip_html(node.findtext(f"{ATOM_NS}title"))
            link_el = node.find(f"{ATOM_NS}link[@rel='alternate']")
            if link_el is None:
                link_el = node.find(f"{ATOM_NS}link")
            link = (link_el.attrib.get("href") if link_el is not None else "") or ""
            guid = (node.findtext(f"{ATOM_NS}id") or link).strip()
            raw_desc = node.findtext(f"{ATOM_NS}summary") or node.findtext(f"{ATOM_NS}content") or ""
            pub_raw = node.findtext(f"{ATOM_NS}published") or node.findtext(f"{ATOM_NS}updated") or ""
        else:
            title_orig = _strip_html(node.findtext("title"))
            link = (node.findtext("link") or "").strip()
            guid = (node.findtext("guid") or link).strip()
            raw_desc = node.findtext("description") or ""
            pub_raw = node.findtext("pubDate") or ""

        if not title_orig or not link:
            continue

        # В Google News RSS title часто содержит " - SourceName", убираем дубль источника и чистим описание
        if source_name.startswith("Google News"):
            title_orig = re.sub(r"\s+-\s+[^-]+$", "", title_orig).strip()
        summary_orig = _strip_html(raw_desc)[:420]
        if summary_orig and summary_orig.casefold().startswith(title_orig.casefold()):
            summary_orig = ""

        rows.append({
            "title_orig": title_orig,
            "summary_orig": summary_orig,
            "link": link,
            "canon_url": _canonical_url(link),
            "guid": guid,
            "image": _extract_image(node),
            "pub_utc": _pub_to_utc(pub_raw),
            "source": source_name,
            "default_topic": default_topic,
            "default_cat": default_cat,
        })
        if len(rows) >= max_items:
            break
    return rows


def fetch_all_news_center() -> dict[str, Any]:
    """Загружает, дедуплицирует, классифицирует и переводит на русский все ленты новостного центра."""
    now_utc = datetime.now(timezone.utc)
    fetched_iso = utc_now_iso()
    fetched_local = format_qyzylorda(fetched_iso)

    seen_urls: set[str] = set()
    seen_guids: set[str] = set()
    seen_titles: set[str] = set()
    items: list[dict[str, Any]] = []
    sources_used: list[str] = []

    for fcfg in NEWS_CENTER_FEEDS:
        try:
            xml_text = fetch_text(fcfg["url"])
            parsed = _parse_feed_entries(
                xml_text,
                fcfg["source"],
                fcfg["default_topic"],
                fcfg["category"],
                int(fcfg.get("limit", 10)),
            )
            if parsed:
                sources_used.append(fcfg["source"])
        except Exception:
            continue

        for raw in parsed:
            norm_title = re.sub(r"[^a-zа-яё0-9]+", " ", raw["title_orig"].casefold()).strip()
            if not norm_title:
                continue
            if raw["canon_url"] in seen_urls or raw["guid"] in seen_guids or norm_title in seen_titles:
                continue
            seen_urls.add(raw["canon_url"])
            seen_guids.add(raw["guid"])
            seen_titles.add(norm_title)

            low = f"{raw['title_orig']} {raw['summary_orig']}".casefold()
            topics, cat, related_entities = _classify_item(low, raw["default_topic"], raw["default_cat"])

            is_rumor = any(m in low for m in RUMOR_MARKERS)
            transfer_type = "none"
            if is_rumor:
                transfer_type = "rumor"
            elif any(m in low for m in CONFIRMED_IN_MARKERS):
                transfer_type = "confirmed_in"
            elif any(m in low for m in CONFIRMED_OUT_MARKERS):
                transfer_type = "confirmed_out"

            pub_utc = raw["pub_utc"]
            pub_dt = parse_utc(pub_utc)
            is_older_7d = bool(pub_dt and (now_utc - pub_dt) > timedelta(days=7))
            is_featured = (not is_older_7d) and (
                len(related_entities) >= 2
                or any(t in topics for t in ("real_madrid", "juventus", "man_utd", "f1", "ufc"))
            )

            title_ru, tr_t = translate_en_to_ru(raw["title_orig"])
            summary_ru, tr_s = translate_en_to_ru(raw["summary_orig"]) if raw["summary_orig"] else ("Нет описания", False)
            cat_ru = CATEGORY_RU.get(cat, cat)

            item_id = hashlib.sha1(f"{raw['canon_url']}|{norm_title}".encode("utf-8")).hexdigest()[:16]
            rel_label = ", ".join(TOPIC_LABELS[t] for t in topics if t in TOPIC_LABELS) or cat_ru

            items.append({
                "id": item_id,
                "title": title_ru,
                "title_original": raw["title_orig"],
                "summary": summary_ru or "Краткое описание в RSS отсутствует.",
                "summary_original": raw["summary_orig"],
                "neutral_digest": _build_neutral_digest(cat_ru, topics, raw["source"], title_ru, summary_ru),
                "is_auto_translated": bool(tr_t or tr_s),
                "url": raw["link"],
                "image": raw["image"],
                "published_utc": pub_utc,
                "published_local": format_qyzylorda(pub_utc) if pub_utc else "Дата не указана",
                "fetched_utc": fetched_iso,
                "fetched_local": fetched_local,
                "is_older_7d": is_older_7d,
                "is_featured": is_featured,
                "category": cat,
                "category_ru": cat_ru,
                "topics": topics,
                "related_entity": rel_label,
                "related_entities": related_entities,
                "source": raw["source"],
                "is_rumor": is_rumor,
                "transfer_type": transfer_type,
            })

    # Сортируем: новые первыми (без даты — в конец)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    items.sort(key=lambda x: parse_utc(x["published_utc"]) or epoch, reverse=True)

    counts = {
        "all": len(items),
        "real_madrid": sum(1 for i in items if "real_madrid" in i["topics"]),
        "juventus": sum(1 for i in items if "juventus" in i["topics"]),
        "man_utd": sum(1 for i in items if "man_utd" in i["topics"]),
        "f1": sum(1 for i in items if "f1" in i["topics"]),
        "ufc": sum(1 for i in items if "ufc" in i["topics"]),
        "transfers": sum(1 for i in items if "transfers" in i["topics"]),
        "featured": sum(1 for i in items if i["is_featured"]),
    }

    trending = [
        {"topic": k, "label": TOPIC_LABELS[k], "count": counts[k]}
        for k in ("real_madrid", "juventus", "man_utd", "f1", "ufc", "transfers")
        if counts[k] > 0
    ]

    return {
        "items": items,
        "featured": [i for i in items if i["is_featured"]][:6],
        "trending": trending,
        "counts": counts,
        "sources": sources_used,
        "updated_utc": fetched_iso,
        "updated_local": fetched_local,
    }


def fetch_rss_news(category: str, limit: int = 12) -> list[dict[str, Any]]:
    """Обратная совместимость: возвращает переведённые новости по категории."""
    nc = fetch_all_news_center()
    filtered = [i for i in nc["items"] if i["category"] == category or category in i["topics"]]
    return filtered[:limit]
