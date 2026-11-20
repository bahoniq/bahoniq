"""Адаптер Wikipedia / Wikimedia REST & Action API с проверкой неоднозначности и русским переводом."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote

from .base import fetch_json
from .translator import translate_en_to_ru


def _extract_title_from_url(wiki_url: str) -> str:
    if not wiki_url:
        return ""
    m = re.search(r"/wiki/([^#?]+)", wiki_url)
    return unquote(m.group(1)).replace("_", " ") if m else ""


def _is_disambiguation(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return True
    if str(payload.get("type") or "").casefold() == "disambiguation":
        return True
    extract = str(payload.get("extract") or "").casefold()
    desc = str(payload.get("description") or "").casefold()
    return "may refer to" in extract or "topics referred to by the same term" in desc


def _matches_keywords(payload: dict[str, Any], required_keywords: tuple[str, ...]) -> bool:
    if not required_keywords:
        return True
    blob = f"{payload.get('title', '')} {payload.get('description', '')} {payload.get('extract', '')}".casefold()
    return any(k.casefold() in blob for k in required_keywords)


def _fetch_summary_raw(title_or_slug: str, lang: str = "en") -> dict[str, Any] | None:
    clean = " ".join(str(title_or_slug or "").strip().split())
    if not clean:
        return None
    slug = quote(clean.replace(" ", "_"), safe="()_-'")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        payload = fetch_json(url)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _search_wiki_titles(query: str, lang: str = "en", limit: int = 5) -> list[str]:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        payload = fetch_json(
            url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            },
        )
        hits = ((payload.get("query") or {}).get("search")) or [] if isinstance(payload, dict) else []
        return [str(h.get("title")) for h in hits if isinstance(h, dict) and h.get("title")]
    except Exception:
        return []


def fetch_wiki_summary(
    entity_name: str,
    lang: str = "en",
    wiki_url: str = "",
    search_hint: str = "",
    required_keywords: tuple[str, ...] = (),
    translate_ru: bool = True,
) -> dict[str, Any]:
    """Получает проверенную статью Wikipedia (без страниц неоднозначности) с русским переводом."""
    candidates: list[str] = []
    from_url = _extract_title_from_url(wiki_url)
    if from_url:
        candidates.append(from_url)
    clean_name = " ".join(str(entity_name or "").strip().split())
    if clean_name and clean_name not in candidates:
        candidates.append(clean_name)

    chosen: dict[str, Any] | None = None
    for cand in candidates:
        raw = _fetch_summary_raw(cand, lang=lang)
        if raw and not _is_disambiguation(raw) and _matches_keywords(raw, required_keywords):
            chosen = raw
            break

    # Если прямое имя не подошло или дало неоднозначность — ищем через MediaWiki Search API
    if chosen is None and clean_name:
        q = f"{clean_name} {search_hint}".strip() if search_hint else clean_name
        for title in _search_wiki_titles(q, lang=lang, limit=5):
            raw = _fetch_summary_raw(title, lang=lang)
            if raw and not _is_disambiguation(raw) and _matches_keywords(raw, required_keywords):
                chosen = raw
                break

    if not chosen:
        return {
            "title": clean_name or "Нет данных",
            "summary": "Нет данных",
            "summary_original": "",
            "is_auto_translated": False,
            "is_disambiguation": False,
            "photo": "",
            "source_url": wiki_url or "",
            "license_note": "",
        }

    orig_extract = str(chosen.get("extract") or "").strip()
    if translate_ru and orig_extract:
        ru_extract, auto_tr = translate_en_to_ru(orig_extract)
    else:
        ru_extract, auto_tr = (orig_extract or "Нет данных"), False

    thumb = ((chosen.get("thumbnail") or {}).get("source")) or ""
    page_url = (((chosen.get("content_urls") or {}).get("desktop") or {}).get("page")) or wiki_url or ""
    return {
        "title": chosen.get("title") or clean_name,
        "summary": ru_extract or "Нет данных",
        "summary_original": orig_extract,
        "is_auto_translated": auto_tr,
        "is_disambiguation": False,
        "photo": thumb,
        "source_url": page_url,
        "license_note": "Wikimedia / Wikipedia REST API" if thumb else "",
    }


def _clean_wikitext_val(raw: str) -> str:
    txt = re.sub(r"<ref[^>]*>.*?</ref>", "", raw, flags=re.S | re.I)
    txt = re.sub(r"<ref[^>]*/?>", "", txt, flags=re.I)
    txt = re.sub(r"<br\s*/?>", ", ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", txt)
    txt = re.sub(r"\{\{[^{}]*\}\}", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip(" ,;|")
    return txt


def fetch_f1_team_infobox(wiki_title_or_url: str) -> dict[str, str]:
    """Извлекает базу, руководителя и силовую установку команды F1 из инфобокса Wikipedia."""
    title = _extract_title_from_url(wiki_title_or_url) or wiki_title_or_url
    if not title:
        return {}
    try:
        payload = fetch_json(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
            },
        )
        pages = list(((payload.get("query") or {}).get("pages") or {}).values()) if isinstance(payload, dict) else []
        if not pages:
            return {}
        wikitext = ((((pages[0].get("revisions") or [{}])[0].get("slots") or {}).get("main") or {}).get("*")) or ""
        if not wikitext:
            return {}

        def _find_field(*names: str) -> str:
            for nm in names:
                m = re.search(rf"^\s*\|\s*{re.escape(nm)}\s*=\s*(.+)$", wikitext, re.M | re.I)
                if m:
                    val = _clean_wikitext_val(m.group(1))
                    if val:
                        return val
            return ""

        base = _find_field("base", "headquarters", "location")
        chief = _find_field("principal", "team_principal", "director", "founder")
        engine = _find_field("engine", "power_unit", "chassis_engine")
        out: dict[str, str] = {}
        if base:
            out["base"] = translate_en_to_ru(base)[0] if base else ""
        if chief:
            out["team_chief"] = chief
        if engine:
            out["power_unit"] = engine
        return out
    except Exception:
        return {}


def fetch_football_club_wiki_meta(club_wiki_title: str, stadium_wiki_title: str) -> dict[str, str]:
    """Получает актуального тренера клуба (manager) и фото стадиона из Wikipedia."""
    out: dict[str, str] = {"manager": "", "stadium_photo": ""}
    try:
        payload = fetch_json(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": club_wiki_title,
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
            },
        )
        pages = list(((payload.get("query") or {}).get("pages") or {}).values()) if isinstance(payload, dict) else []
        if pages:
            wikitext = ((((pages[0].get("revisions") or [{}])[0].get("slots") or {}).get("main") or {}).get("*")) or ""
            m = re.search(r"^\s*\|\s*(?:manager|head\s*coach)\s*=\s*(.+)$", wikitext, re.M | re.I)
            if m:
                out["manager"] = _clean_wikitext_val(m.group(1))
    except Exception:
        pass

    try:
        st_sum = _fetch_summary_raw(stadium_wiki_title, lang="en")
        if st_sum and isinstance(st_sum.get("thumbnail"), dict):
            out["stadium_photo"] = str(st_sum["thumbnail"].get("source") or "")
    except Exception:
        pass
    return out


def fetch_stadium_gallery(query: str, primary_photo: str = "", limit: int = 5) -> list[dict[str, str]]:
    """Загружает несколько реальных ракурсов стадиона из Wikimedia Commons."""
    gallery: list[dict[str, str]] = []
    seen: set[str] = set()
    if primary_photo:
        gallery.append({"url": primary_photo, "caption": "Общий вид стадиона"})
        seen.add(primary_photo)
    try:
        payload = fetch_json(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrnamespace": "6",
                "gsrsearch": query,
                "gsrlimit": str(limit + 3),
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": "960",
                "format": "json",
            },
        )
        pages = ((payload.get("query") or {}).get("pages") or {}) if isinstance(payload, dict) else {}
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            mime = str(ii.get("mime") or "")
            url = str(ii.get("thumburl") or ii.get("url") or "")
            if not url or not mime.startswith("image/") or "svg" in mime:
                continue
            if url in seen:
                continue
            seen.add(url)
            title = str(p.get("title") or "").replace("File:", "").rsplit(".", 1)[0]
            gallery.append({"url": url, "caption": title[:60] or "Вид стадиона"})
            if len(gallery) >= limit:
                break
    except Exception:
        pass
    return gallery


def fetch_wikipedia_photos_batch(names: list[str]) -> dict[str, str]:
    """Получает фото сразу для списка футболистов за минимальное число запросов Wikipedia API."""
    result: dict[str, str] = {}
    clean_names = [" ".join(str(n or "").strip().split()) for n in names if n and n != "Нет данных"]
    if not clean_names:
        return result

    # Чанками по 25 имён за 1 HTTP-запрос
    for i in range(0, len(clean_names), 25):
        batch = clean_names[i:i + 25]
        try:
            payload = fetch_json(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": "|".join(batch),
                    "redirects": "1",
                    "prop": "pageimages",
                    "pithumbsize": "330",
                    "format": "json",
                },
            )
            q = payload.get("query") or {} if isinstance(payload, dict) else {}
            norm_map = {n["from"]: n["to"] for n in (q.get("normalized") or []) if isinstance(n, dict)}
            redir_map = {r["from"]: r["to"] for r in (q.get("redirects") or []) if isinstance(r, dict)}
            pages = q.get("pages") or {}
            title_to_thumb: dict[str, str] = {}
            for p in pages.values():
                t = str(p.get("title") or "")
                src = str(((p.get("thumbnail") or {}).get("source")) or "")
                if t and src:
                    title_to_thumb[t] = src

            for orig in batch:
                t1 = norm_map.get(orig, orig)
                t2 = redir_map.get(t1, t1)
                if t2 in title_to_thumb:
                    result[orig] = title_to_thumb[t2]
        except Exception:
            continue
    return result
