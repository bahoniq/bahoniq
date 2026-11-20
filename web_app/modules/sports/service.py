"""Центральный сервис BahonIQ Sports: координация провайдеров, кеша и fallback."""
from __future__ import annotations

from typing import Any, Callable

from .cache import SportsCache, TTL_NEWS, TTL_PROFILES, TTL_SCHEDULE
from .providers import f1_jolpica, football_espn, media_wiki, news_rss, ufc_espn
from .time_utils import format_qyzylorda, utc_now_iso


class SportsService:
    """Нормализованный сервис спортивных данных с автономным кешем."""

    def __init__(self, cache: SportsCache | None = None) -> None:
        self.cache = cache or SportsCache()

    def _with_cache(
        self,
        key: str,
        ttl: int,
        fetcher: Callable[[], Any],
        source_name: str,
        force: bool = False,
    ) -> dict[str, Any]:
        if not force:
            fresh = self.cache.get(key, ttl=ttl)
            if fresh is not None:
                return {
                    "data": fresh["data"],
                    "updated_at_utc": fresh["updated_at_utc"],
                    "updated_at_local": format_qyzylorda(fresh["updated_at_utc"]),
                    "source": fresh.get("source", source_name),
                    "stale": False,
                    "error": None,
                }
        try:
            data = fetcher()
            now_utc = utc_now_iso()
            self.cache.set(key, data, now_utc, source_name)
            return {
                "data": data,
                "updated_at_utc": now_utc,
                "updated_at_local": format_qyzylorda(now_utc),
                "source": source_name,
                "stale": False,
                "error": None,
            }
        except Exception as exc:
            stale = self.cache.get_stale(key)
            if stale is not None:
                return {
                    "data": stale["data"],
                    "updated_at_utc": stale["updated_at_utc"],
                    "updated_at_local": format_qyzylorda(stale["updated_at_utc"]),
                    "source": stale.get("source", source_name),
                    "stale": True,
                    "error": str(exc),
                }
            return {
                "data": None,
                "updated_at_utc": "",
                "updated_at_local": "Нет данных",
                "source": source_name,
                "stale": True,
                "error": str(exc),
            }

    _CLUB_EXTRAS: dict[str, dict[str, Any]] = {
        "real_madrid": {
            "wiki_title": "Real Madrid CF",
            "formed": "1902",
            "fallback_manager": "José Mourinho",
            "fallback_kit": "https://r2.thesportsdb.com/images/media/team/equipment/gntr911750591256.png",
            "away_kit": "",
            "third_kit": "",
            "stadium_wiki": "Santiago Bernabéu Stadium",
            "stadium_name": "Сантьяго Бернабеу",
            "stadium_city": "Мадрид, Испания",
            "stadium_capacity": "83 186",
            "stadium_opened": "1947",
            "stadium_surface": "Гибридный газон (выдвижное поле)",
            "stadium_gallery": [
                {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/M-estadio-santiago-bernabeu-diciembre-2024-a.jpg/960px-M-estadio-santiago-bernabeu-diciembre-2024-a.jpg", "caption": "Обновлённый Сантьяго Бернабеу — современный фасад"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/31/Estadio_Santiago_Bernab%C3%A9u_02.jpg/960px-Estadio_Santiago_Bernab%C3%A9u_02.jpg", "caption": "Фасад стадиона"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/fd/Estadio_Santiago_Bernab%C3%A9u_07.jpg/960px-Estadio_Santiago_Bernab%C3%A9u_07.jpg", "caption": "Трибуны и панорама"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c5/Estadio_Santiago_Bernab%C3%A9u_09.jpg/960px-Estadio_Santiago_Bernab%C3%A9u_09.jpg", "caption": "Чаша стадиона сверху"},
            ],
            "anthem": "Hala Madrid y nada más",
            "anthem_query": "Hala Madrid y nada mas",
            "colors": "Белый / Золотой",
            "kits": [
                {"type": "home", "label": "Домашняя 2026/27", "primary": "#f8fafc", "secondary": "#ec4899", "text": "#0f172a", "pattern": "solid", "desc": "Белая форма, тёмно-зелёная отделка и розовые полосы adidas"},
                {"type": "away", "label": "Гостевая 2026/27", "primary": "#17443b", "secondary": "#f5f0df", "text": "#ffffff", "pattern": "solid", "desc": "Тёмно-зелёная с молочно-белой отделкой"},
                {"type": "third", "label": "Третья 2026/27", "primary": "#ec4899", "secondary": "#f5f0df", "text": "#ffffff", "pattern": "solid", "desc": "Ярко-розовая с молочно-белыми деталями"},
            ],
            "records": {
                "appearances": "Рауль Гонсалес — 741 матч",
                "goals": "Криштиану Роналду — 450 голов",
            },
            "trophies": [
                {"icon": "🏆", "img": "https://upload.wikimedia.org/wikipedia/commons/d/d1/UEFA_Champions_League_logo_no_text.svg", "title": "Лига чемпионов УЕФА", "count": 15, "last": "2024"},
                {"icon": "👑", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/54/LaLiga_EA_Sports_2023_Vertical_Logo.svg/330px-LaLiga_EA_Sports_2023_Vertical_Logo.svg.png", "title": "Ла Лига (Чемпионат Испании)", "count": 36, "last": "2024"},
                {"icon": "🏅", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7b/Copa_del_Rey_logo_%282021%29.svg/330px-Copa_del_Rey_logo_%282021%29.svg.png", "title": "Кубок Испании (Copa del Rey)", "count": 20, "last": "2023"},
                {"icon": "⚡", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/f/fa/Supercopa-de-Espa%C3%B1a-RFEF.svg/330px-Supercopa-de-Espa%C3%B1a-RFEF.svg.png", "title": "Суперкубок Испании", "count": 13, "last": "2024"},
                {"icon": "🌍", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/0/0b/UEFA_Super_Cup_logo.svg/330px-UEFA_Super_Cup_logo.svg.png", "title": "Суперкубок УЕФА", "count": 6, "last": "2024"},
                {"icon": "🌐", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4e/FIFA_Club_World_Cup_logo.svg/330px-FIFA_Club_World_Cup_logo.svg.png", "title": "Клубный ЧМ / Межконт. кубок", "count": 9, "last": "2024"},
            ],
        },
        "juventus": {
            "wiki_title": "Juventus FC",
            "formed": "1897",
            "fallback_manager": "Luciano Spalletti",
            "fallback_kit": "https://r2.thesportsdb.com/images/media/team/equipment/fph30e1749928492.png",
            "away_kit": "",
            "third_kit": "",
            "stadium_wiki": "Juventus Stadium",
            "stadium_name": "Альянц Стэдиум",
            "stadium_city": "Турин, Италия",
            "stadium_capacity": "41 507",
            "stadium_opened": "2011",
            "stadium_surface": "Натуральный / гибридный газон",
            "stadium_gallery": [
                {"url": "https://upload.wikimedia.org/wikipedia/commons/a/a8/Turin_Juventus_Stadium_2.jpg", "caption": "Альянц Стэдиум — панорама трибун и поля"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/04/Inside_Juventus_Stadium_%283%29.jpg/960px-Inside_Juventus_Stadium_%283%29.jpg", "caption": "Внутри чаши стадиона"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/07/Juventus_Stadium_%28Est%29.jpg/960px-Juventus_Stadium_%28Est%29.jpg", "caption": "Внешний вид стадиона"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f2/2021%E2%80%9322_UEFA_Women%27s_Champions_League_Final_in_Turin%2C_Italy_1.jpg/960px-2021%E2%80%9322_UEFA_Women%27s_Champions_League_Final_in_Turin%2C_Italy_1.jpg", "caption": "Трибуны во время матча"},
            ],
            "anthem": "Juve (storia di un grande amore)",
            "anthem_query": "Juve storia di un grande amore",
            "colors": "Чёрный / Белый (бьянконери)",
            "kits": [
                {"type": "home", "label": "Домашняя 2026/27", "primary": "#f8fafc", "secondary": "#0f172a", "text": "#0f172a", "pattern": "stripes", "desc": "Официальная чёрно-белая домашняя форма сезона 2026/27"},
                {"type": "away", "label": "Гостевая", "primary": "#bae6fd", "secondary": "#0f172a", "text": "#0f172a", "pattern": "solid", "desc": "Светло-голубой / небесный"},
                {"type": "third", "label": "Третья", "primary": "#0f172a", "secondary": "#a855f7", "text": "#f8fafc", "pattern": "solid", "desc": "Тёмный антрацит"},
            ],
            "records": {
                "appearances": "Алессандро Дель Пьеро — 705 матчей",
                "goals": "Алессандро Дель Пьеро — 290 голов",
            },
            "trophies": [
                {"icon": "🏆", "img": "https://upload.wikimedia.org/wikipedia/commons/d/d1/UEFA_Champions_League_logo_no_text.svg", "title": "Лига чемпионов УЕФА", "count": 2, "last": "1996"},
                {"icon": "👑", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/a/ab/Serie_A_ENILIVE_logo.svg/330px-Serie_A_ENILIVE_logo.svg.png", "title": "Серия А (Чемпионат Италии)", "count": 36, "last": "2020"},
                {"icon": "🏅", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d2/Logo_of_Coppa_Italia_Frecciarossa_%282024-2025%29.svg/330px-Logo_of_Coppa_Italia_Frecciarossa_%282024-2025%29.svg.png", "title": "Кубок Италии (Coppa Italia)", "count": 15, "last": "2024"},
                {"icon": "⚡", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/8/87/Supercoppa_Italiana_logo.svg/330px-Supercoppa_Italiana_logo.svg.png", "title": "Суперкубок Италии", "count": 9, "last": "2020"},
                {"icon": "🥈", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1b/UEFA_Europa_League_logo_%282024_version%29.svg/330px-UEFA_Europa_League_logo_%282024_version%29.svg.png", "title": "Кубок УЕФА / Лига Европы", "count": 3, "last": "1993"},
                {"icon": "🌍", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/0/0b/UEFA_Super_Cup_logo.svg/330px-UEFA_Super_Cup_logo.svg.png", "title": "Суперкубок УЕФА", "count": 2, "last": "1996"},
            ],
        },
        "man_utd": {
            "wiki_title": "Manchester United F.C.",
            "formed": "1878",
            "fallback_manager": "Mauricio Pochettino",
            "fallback_kit": "/assets/kits/man_utd_home.jpg",
            "home_kit_override": "/assets/kits/man_utd_home.jpg",
            "away_kit": "",
            "third_kit": "",
            "stadium_wiki": "Old Trafford",
            "stadium_name": "Олд Траффорд",
            "stadium_city": "Манчестер, Англия",
            "stadium_capacity": "74 197",
            "stadium_opened": "1910",
            "stadium_surface": "Гибридный газон (Desso GrassMaster)",
            "stadium_gallery": [
                {"url": "https://upload.wikimedia.org/wikipedia/commons/a/a8/View_of_Old_Trafford_from_East_Stand.jpg", "caption": "Олд Траффорд — панорама поля и трибун"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ea/Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725263.jpg/960px-Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725263.jpg", "caption": "Общий вид стадиона"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a3/Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725289.jpg/960px-Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725289.jpg", "caption": "Трибуны и поле сверху"},
                {"url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/de/Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725302.jpg/960px-Manchester_%2C_Trafford_-_Old_Trafford_Football_Stadium_-_geograph.org.uk_-_3725302.jpg", "caption": "Трибуны Stretford End"},
            ],
            "anthem": "Glory Glory Man United",
            "anthem_query": "Glory Glory Man United",
            "colors": "Красный / Белый / Чёрный",
            "kits": [
                {"type": "home", "label": "Домашняя 2026/27", "primary": "#dc2626", "secondary": "#f8fafc", "text": "#ffffff", "pattern": "solid", "desc": "Красная форма с бело-чёрной отделкой в стиле 1970-х"},
                {"type": "away", "label": "Гостевая", "primary": "#f8fafc", "secondary": "#7c3aed", "text": "#0f172a", "pattern": "solid", "desc": "Белый с контрастной отделкой"},
                {"type": "third", "label": "Третья", "primary": "#111827", "secondary": "#facc15", "text": "#f8fafc", "pattern": "solid", "desc": "Чёрный с золотыми акцентами"},
            ],
            "records": {
                "appearances": "Райан Гиггз — 963 матча",
                "goals": "Уэйн Руни — 253 гола",
            },
            "trophies": [
                {"icon": "🏆", "img": "https://upload.wikimedia.org/wikipedia/commons/d/d1/UEFA_Champions_League_logo_no_text.svg", "title": "Лига чемпионов УЕФА", "count": 3, "last": "2008"},
                {"icon": "👑", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/f/f2/Premier_League_Logo.svg/330px-Premier_League_Logo.svg.png", "title": "Чемпионат Англии", "count": 20, "last": "2013"},
                {"icon": "🏅", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/d/d5/FA_Cup_logo_%282020%29.svg/330px-FA_Cup_logo_%282020%29.svg.png", "title": "Кубок Англии (FA Cup)", "count": 13, "last": "2024"},
                {"icon": "⚡", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/0/0c/EFL_%28Carabao%29_Cup_Logo.svg/330px-EFL_%28Carabao%29_Cup_Logo.svg.png", "title": "Кубок английской лиги", "count": 6, "last": "2023"},
                {"icon": "🛡", "img": "https://thumb.wikimedia.org/wikipedia/en/thumb/d/d6/FA_Community_Shield_logo.svg/330px-FA_Community_Shield_logo.svg.png", "title": "Суперкубок Англии", "count": 21, "last": "2016"},
                {"icon": "🥈", "img": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1b/UEFA_Europa_League_logo_%282024_version%29.svg/330px-UEFA_Europa_League_logo_%282024_version%29.svg.png", "title": "Лига Европы / Кубок кубков", "count": 2, "last": "2017"},
            ],
        },
    }

    def _fetch_club_profile_data(self, club_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
        from .providers.base import fetch_json
        extras = self._CLUB_EXTRAS.get(club_id, {})
        wiki_meta = media_wiki.fetch_football_club_wiki_meta(
            extras.get("wiki_title", cfg["name"]),
            extras.get("stadium_wiki", ""),
        )
        kit_image = ""
        formed = ""
        website = ""
        stadium_name = extras.get("stadium_name", "")
        try:
            sdb = fetch_json(
                "https://www.thesportsdb.com/api/v1/json/123/searchteams.php",
                params={"t": cfg["name"]},
                timeout=6.0,
                retries=1,
            )
            team_obj = next((t for t in (sdb.get("teams") or []) if str(t.get("strSport") or "").casefold() == "soccer"), {})
            if team_obj:
                kit_image = str(team_obj.get("strEquipment") or "")
                formed = str(team_obj.get("intFormedYear") or "")
                website = str(team_obj.get("strWebsite") or "")
                if team_obj.get("strStadium") and not stadium_name:
                    stadium_name = str(team_obj.get("strStadium"))
        except Exception:
            pass

        anthem_audio_url = ""
        from pathlib import Path
        local_anthem = Path(__file__).resolve().parents[2] / "static" / "audio" / f"{club_id}.mp3"
        if local_anthem.is_file() and local_anthem.stat().st_size > 10000:
            anthem_audio_url = f"/assets/audio/{club_id}.mp3"
        elif extras.get("anthem_query"):
            try:
                it = fetch_json(
                    "https://itunes.apple.com/search",
                    params={"term": extras["anthem_query"], "media": "music", "limit": "1"},
                    timeout=6.0,
                    retries=0,
                )
                res_list = it.get("results") if isinstance(it, dict) else []
                if res_list:
                    anthem_audio_url = str(res_list[0].get("previewUrl") or "")
            except Exception:
                pass

        home_kit_url = extras.get("home_kit_override") or kit_image or extras.get("fallback_kit", "")
        kits_gallery = []
        kit_labels = {str(k.get("type")): str(k.get("label")) for k in extras.get("kits", []) if isinstance(k, dict)}
        if home_kit_url:
            kits_gallery.append({"type": "home", "label": kit_labels.get("home", "Домашняя 2026/27"), "url": home_kit_url})
        if extras.get("away_kit"):
            kits_gallery.append({"type": "away", "label": kit_labels.get("away", "Гостевая 2026/27"), "url": extras["away_kit"]})
        if extras.get("third_kit"):
            kits_gallery.append({"type": "third", "label": kit_labels.get("third", "Третья 2026/27"), "url": extras["third_kit"]})

        curated_gallery = extras.get("stadium_gallery") or []
        stadium_gallery = curated_gallery if curated_gallery else media_wiki.fetch_stadium_gallery(
            f"{extras.get('stadium_wiki', stadium_name)} stadium",
            primary_photo=wiki_meta.get("stadium_photo") or "",
            limit=5,
        )

        return {
            "manager": wiki_meta.get("manager") or extras.get("fallback_manager", ""),
            "stadium": stadium_name or "Нет данных",
            "stadium_city": extras.get("stadium_city", ""),
            "stadium_capacity": extras.get("stadium_capacity", "Нет данных"),
            "stadium_opened": extras.get("stadium_opened", "—"),
            "stadium_surface": extras.get("stadium_surface", "Газон"),
            "stadium_photo": (stadium_gallery[0]["url"] if stadium_gallery else "") or wiki_meta.get("stadium_photo") or "",
            "stadium_gallery": stadium_gallery,
            "kit_image": home_kit_url,
            "kits_gallery": kits_gallery,
            "kits": extras.get("kits", []),
            "formed": formed or extras.get("formed", "Нет данных"),
            "website": website,
            "colors": extras.get("colors", "Нет данных"),
            "anthem": extras.get("anthem", "Нет данных"),
            "anthem_audio_url": anthem_audio_url,
            "records": extras.get("records", {}),
            "trophies": extras.get("trophies", []),
        }

    def get_football_club(self, club_id: str, force: bool = False) -> dict[str, Any]:
        """Возвращает нормализованные данные по одному из 3 клубов."""
        if club_id not in football_espn.CLUBS_CONFIG:
            raise ValueError(f"Неизвестный клуб: {club_id}")
        cfg = football_espn.CLUBS_CONFIG[club_id]

        schedule_env = self._with_cache(
            f"football_schedule_{club_id}",
            TTL_SCHEDULE,
            lambda: football_espn.fetch_club_schedule(club_id),
            "ESPN Soccer",
            force=force,
        )
        roster_env = self._with_cache(
            f"football_roster_{club_id}",
            TTL_PROFILES,
            lambda: football_espn.fetch_club_roster(club_id),
            "ESPN Soccer",
            force=force,
        )
        standings_env = self._with_cache(
            f"football_standings_{cfg['league']}",
            TTL_SCHEDULE,
            lambda: football_espn.fetch_league_standings(cfg["league"]),
            "ESPN Soccer",
            force=force,
        )
        leaders_env = self._with_cache(
            f"football_leaders_{cfg['league']}",
            TTL_SCHEDULE,
            lambda: football_espn.fetch_league_leaders(cfg["league"]),
            "ESPN Soccer Statistics",
            force=force,
        )
        news_center = self.get_news_center(force=force)
        all_news = news_center.get("items") or []

        sched = schedule_env["data"] or {}
        roster = roster_env["data"] or {}
        players_list = roster.get("players") or []
        missing_roster_photos = [p for p in players_list if not p.get("photo") and p.get("name")]
        if missing_roster_photos:
            # 1. Быстрый батч Wikipedia API (1 запрос на 25 игроков, без rate-limit)
            batch_photos = media_wiki.fetch_wikipedia_photos_batch([p["name"] for p in missing_roster_photos])
            updated_any = False
            still_missing = []
            for pl in missing_roster_photos:
                ph = batch_photos.get(pl["name"])
                if ph:
                    pl["photo"] = ph
                    updated_any = True
                else:
                    still_missing.append(pl)
            # 2. Для оставшихся (включая Rodrygo и т.д.) точечно через поиск с контекстом клуба
            if still_missing:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=6) as pool:
                    resolved = list(pool.map(lambda pl: self._resolve_footballer_photo(pl["name"], cfg["name"]), still_missing))
                for pl, ph in zip(still_missing, resolved):
                    if ph:
                        pl["photo"] = ph
                        updated_any = True
            if updated_any:
                photo_by_id = {str(p.get("id") or ""): p["photo"] for p in players_list if p.get("photo") and p.get("id")}
                photo_by_name = {str(p.get("name") or "").casefold(): p["photo"] for p in players_list if p.get("photo") and p.get("name")}
                for grp_list in (roster.get("roster_grouped") or {}).values():
                    for gpl in grp_list or []:
                        if not gpl.get("photo"):
                            ph = photo_by_id.get(str(gpl.get("id") or "")) or photo_by_name.get(str(gpl.get("name") or "").casefold())
                            if ph:
                                gpl["photo"] = ph
            if updated_any and roster_env.get("updated_at_utc"):
                self.cache.set(f"football_roster_{club_id}", roster, roster_env["updated_at_utc"], "ESPN Soccer")

        stand_data = standings_env["data"]
        if isinstance(stand_data, list):
            standings_rows = stand_data
            standings_season = sched.get("season") or cfg["league_name"]
            standings_updated = standings_env["updated_at_local"]
        elif isinstance(stand_data, dict):
            standings_rows = stand_data.get("rows") or []
            standings_season = stand_data.get("season") or sched.get("season") or cfg["league_name"]
            standings_updated = stand_data.get("updated_at_local") or standings_env["updated_at_local"]
        else:
            standings_rows = []
            standings_season = cfg["league_name"]
            standings_updated = standings_env["updated_at_local"]

        keywords = [str(k).casefold() for k in cfg.get("keywords", [cfg["name"]])]
        club_news = []
        for n in all_news:
            if club_id in (n.get("topics") or []):
                club_news.append(n)
                continue
            blob = f"{n.get('title_original', '')} {n.get('summary_original', '')} {n.get('title', '')} {n.get('summary', '')}".casefold()
            if any(k in blob for k in keywords):
                club_news.append(n)

        transfer_rumors = [n for n in club_news if n.get("is_rumor") or n.get("transfer_type") == "rumor"]
        transfers_confirmed_in = [n for n in club_news if n.get("transfer_type") == "confirmed_in"]
        transfers_confirmed_out = [n for n in club_news if n.get("transfer_type") == "confirmed_out"]
        transfers_confirmed = transfers_confirmed_in + transfers_confirmed_out

        profile_env = self._with_cache(
            f"football_club_profile_{club_id}_v2",
            TTL_PROFILES,
            lambda: self._fetch_club_profile_data(club_id, cfg),
            "Wikipedia + TheSportsDB",
            force=force,
        )
        club_profile = profile_env.get("data") or {}
        raw_coaches = roster.get("coaches") or []
        actual_manager = club_profile.get("manager") or (raw_coaches[0].get("name") if raw_coaches else "Нет данных")
        clean_coaches = [{"name": actual_manager, "role": "Главный тренер"}] if actual_manager else []

        return {
            "club": cfg,
            "club_profile": {**club_profile, "manager": actual_manager},
            "season": sched.get("season") or standings_season,
            "last_match": sched.get("last_match"),
            "next_match": sched.get("next_match"),
            "form": sched.get("form") or [],
            "recent_results": sched.get("recent_results") or [],
            "season_results": sched.get("season_results") or sched.get("recent_results") or [],
            "upcoming_matches": sched.get("upcoming_matches") or [],
            "matches": sched.get("matches") or [],
            "players": roster.get("players") or [],
            "roster_grouped": roster.get("roster_grouped") or {},
            "coaches": clean_coaches,
            "injuries": roster.get("injuries") or [],
            "standings": standings_rows,
            "standings_season": standings_season,
            "standings_updated_local": standings_updated,
            "league_leaders": leaders_env.get("data") or {"scorers": [], "assists": []},
            "news": club_news,
            "transfers_confirmed_in": transfers_confirmed_in,
            "transfers_confirmed_out": transfers_confirmed_out,
            "transfers_confirmed": transfers_confirmed,
            "transfer_rumors": transfer_rumors,
            "meta": {
                "updated_at_utc": schedule_env["updated_at_utc"],
                "updated_at_local": schedule_env["updated_at_local"],
                "stale": any(e["stale"] for e in (schedule_env, roster_env, standings_env)),
                "source": "ESPN Soccer",
            },
        }

    def _fetch_thesportsdb_photo(self, clean_name: str) -> str:
        from .providers.base import fetch_json
        try:
            payload = fetch_json(
                "https://www.thesportsdb.com/api/v1/json/123/searchplayers.php",
                params={"p": clean_name},
                timeout=6.0,
                retries=0,
            )
            players = payload.get("player") if isinstance(payload, dict) else []
            for pl in players or []:
                if str(pl.get("strSport") or "").casefold() == "soccer":
                    cutout = str(pl.get("strCutout") or "").strip()
                    thumb = str(pl.get("strThumb") or "").strip()
                    if cutout:
                        return cutout
                    if thumb:
                        return thumb
        except Exception:
            pass
        return ""

    def _resolve_footballer_photo(self, name: str, club_hint: str = "") -> str:
        clean = " ".join(str(name or "").strip().split())
        if not clean or clean == "Нет данных":
            return ""
        # 1. Проверяем кеш (Wikipedia и TheSportsDB)
        wiki_key = f"wiki_fb_photo_{clean.casefold()}"
        wiki_cached = self.cache.get(wiki_key, ttl=TTL_PROFILES)
        if wiki_cached and (wiki_cached.get("data") or {}).get("photo"):
            return str(wiki_cached["data"]["photo"])
        full_cached = self.cache.get_stale(f"wiki_fb_{clean.casefold()}")
        if full_cached and isinstance(full_cached.get("data"), dict) and full_cached["data"].get("photo"):
            return str(full_cached["data"]["photo"])

        # 2. Поиск в Wikipedia (с подсказкой клуба для однословных имён типа Rodrygo)
        hint = f"{club_hint} footballer".strip() if club_hint else "footballer"
        wiki_res = media_wiki.fetch_wiki_summary(
            clean,
            search_hint=hint,
            required_keywords=("football", "soccer", "la liga", "serie a", "premier league", "midfielder", "defender", "goalkeeper", "forward"),
            translate_ru=False,
        )
        wiki_photo = str((wiki_res or {}).get("photo") or "")
        if wiki_photo:
            self.cache.set(wiki_key, wiki_res, utc_now_iso(), "Wikipedia REST")
            return wiki_photo

        # 3. Fallback: TheSportsDB (если не нашли в Wikipedia)
        sdb_key = f"sdb_fb_photo_{clean.casefold()}"
        sdb_cached = self.cache.get(sdb_key, ttl=TTL_PROFILES)
        if sdb_cached and (sdb_cached.get("data") or {}).get("photo"):
            return str(sdb_cached["data"]["photo"])
        sdb_photo = self._fetch_thesportsdb_photo(clean)
        if sdb_photo:
            self.cache.set(sdb_key, {"photo": sdb_photo}, utc_now_iso(), "TheSportsDB")
            return sdb_photo
        return ""

    def get_match_detail(self, club_id: str, event_id: str, force: bool = False) -> dict[str, Any]:
        """Возвращает детальный отчёт матча (составы с фото, голы, карточки, замены)."""
        if club_id not in football_espn.CLUBS_CONFIG:
            raise ValueError(f"Неизвестный клуб: {club_id}")
        env = self._with_cache(
            f"match_{club_id}_{event_id}",
            TTL_SCHEDULE,
            lambda: football_espn.fetch_match_detail(club_id, event_id),
            "ESPN Soccer Summary",
            force=force,
        )
        match_data = env["data"]
        if isinstance(match_data, dict) and match_data.get("rosters"):
            missing = [
                p for r in match_data["rosters"] for p in (r.get("starters") or [])
                if not p.get("photo") and p.get("name")
            ]
            if missing:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=8) as pool:
                    photos = list(pool.map(lambda pl: self._resolve_footballer_photo(pl["name"]), missing))
                for pl, ph in zip(missing, photos):
                    if ph:
                        pl["photo"] = ph
                # Обновляем кеш матча, чтобы фото не догружались повторно
                if env.get("updated_at_utc"):
                    self.cache.set(f"match_{club_id}_{event_id}", match_data, env["updated_at_utc"], "ESPN Soccer Summary")
        return {
            "match": match_data,
            "meta": {
                "updated_at_utc": env["updated_at_utc"],
                "updated_at_local": env["updated_at_local"],
                "stale": env["stale"],
                "error": env["error"],
            },
        }

    def get_football_player_profile(self, club_id: str, player_id: str, force: bool = False) -> dict[str, Any]:
        """Возвращает полный профиль футболиста (ESPN + Wikipedia фото/биография)."""
        club_data = self.get_football_club(club_id, force=False)
        player = next((p for p in club_data.get("players", []) if str(p.get("id")) == str(player_id)), None)
        if player is not None and "season_stats" not in player:
            club_data = self.get_football_club(club_id, force=True)
            player = next((p for p in club_data.get("players", []) if str(p.get("id")) == str(player_id)), None)
        if player is None:
            raise ValueError(f"Игрок {player_id} не найден в составе {club_id}")

        wiki_env = self._with_cache(
            f"wiki_fb_{player['name'].casefold()}",
            TTL_PROFILES,
            lambda: media_wiki.fetch_wiki_summary(
                player["name"],
                search_hint="footballer",
                required_keywords=("football", "soccer", "la liga", "serie a", "premier league", "midfielder", "defender", "goalkeeper", "forward", "striker", "real madrid", "juventus", "manchester united"),
                translate_ru=True,
            ),
            "Wikipedia REST",
            force=force,
        )
        wiki = wiki_env["data"] or {}
        photo = player.get("photo") or self._resolve_footballer_photo(player["name"]) or wiki.get("photo") or ""
        return {
            "player": {
                **player,
                "photo": photo,
                "bio": wiki.get("summary") or "Нет данных",
                "bio_original": wiki.get("summary_original") or "",
                "is_auto_translated": bool(wiki.get("is_auto_translated")),
                "wiki_url": wiki.get("source_url") or "",
                "license_note": wiki.get("license_note") or "",
            },
            "meta": {
                "updated_at_utc": wiki_env["updated_at_utc"],
                "updated_at_local": wiki_env["updated_at_local"],
                "stale": wiki_env["stale"],
            },
        }

    def get_news_center(self, force: bool = False) -> dict[str, Any]:
        """Возвращает полноценный русскоязычный новостной центр с классификацией и связями."""
        env = self._with_cache(
            "news_center_v1",
            TTL_NEWS,
            news_rss.fetch_all_news_center,
            "Multi-RSS News Center",
            force=force,
        )
        data = dict(env["data"] or {})
        items = [dict(it) for it in (data.get("items") or [])]

        # Динамически связываем новости с игроками из уже закешированных составов 3 клубов
        roster_index: list[tuple[str, str, str, list[str]]] = []
        for cid in football_espn.CLUBS_CONFIG:
            r_stale = self.cache.get_stale(f"football_roster_{cid}")
            players = ((r_stale or {}).get("data") or {}).get("players") or []
            for p in players:
                pname = str(p.get("name") or "").strip()
                pid = str(p.get("id") or "").strip()
                parts = [w.casefold() for w in pname.split() if len(w) >= 5]
                if pname and pid and parts:
                    roster_index.append((cid, pid, pname, parts))

        if roster_index:
            for it in items:
                blob = f"{it.get('title_original', '')} {it.get('summary_original', '')}".casefold()
                ents = list(it.get("related_entities") or [])
                existing_labels = {str(e.get("label", "")).casefold() for e in ents}
                for cid, pid, pname, parts in roster_index:
                    if any(pt in blob for pt in parts) and pname.casefold() not in existing_labels:
                        ents.append({"type": "player", "club_id": cid, "id": pid, "label": pname})
                        existing_labels.add(pname.casefold())
                        if len(ents) >= 10:
                            break
                it["related_entities"] = ents

        data["items"] = items
        data["featured"] = [i for i in items if i.get("is_featured")][:6]
        data["meta"] = {
            "updated_at_utc": env["updated_at_utc"],
            "updated_at_local": env["updated_at_local"],
            "stale": env["stale"],
            "error": env["error"],
            "source": "BahonIQ Sports News Center",
        }
        return data

    def get_f1_overview(self, force: bool = False) -> dict[str, Any]:
        """Возвращает календарь, зачёты, результаты и новости Formula 1."""
        cal_env = self._with_cache(
            "f1_calendar", TTL_SCHEDULE, f1_jolpica.fetch_f1_calendar, "Jolpica F1", force=force
        )
        stand_env = self._with_cache(
            "f1_standings", TTL_SCHEDULE, f1_jolpica.fetch_f1_standings, "Jolpica F1", force=force
        )
        last_env = self._with_cache(
            "f1_last_results", TTL_SCHEDULE, f1_jolpica.fetch_f1_last_results, "Jolpica F1", force=force
        )
        nc = self.get_news_center(force=force)
        f1_news = [i for i in (nc.get("items") or []) if i.get("category") == "f1" or "f1" in (i.get("topics") or [])][:12]
        cal = cal_env["data"] or {}
        stand = stand_env["data"] or {}
        return {
            "season": cal.get("season") or "",
            "next_race": cal.get("next_race"),
            "races": cal.get("races") or [],
            "last_results": last_env["data"] or {"race_name": "Нет данных", "results": []},
            "drivers": stand.get("drivers") or [],
            "constructors": stand.get("constructors") or [],
            "news": f1_news,
            "meta": {
                "updated_at_utc": cal_env["updated_at_utc"],
                "updated_at_local": cal_env["updated_at_local"],
                "stale": any(e["stale"] for e in (cal_env, stand_env, last_env)),
                "source": "Jolpica F1",
            },
        }

    def get_ufc_overview(self, force: bool = False) -> dict[str, Any]:
        """Возвращает ближайший турнир UFC, кард, актуальные чемпионы с проверкой свежести и новости."""
        board_env = self._with_cache(
            "ufc_scoreboard", TTL_SCHEDULE, ufc_espn.fetch_ufc_scoreboard, "ESPN UFC Scoreboard", force=force
        )
        rank_env = self._with_cache(
            "ufc_rankings_official_v2", TTL_PROFILES, ufc_espn.fetch_ufc_rankings, "UFC.com Official Rankings", force=force
        )
        nc = self.get_news_center(force=force)
        ufc_news = [i for i in (nc.get("items") or []) if i.get("category") == "ufc" or "ufc" in (i.get("topics") or [])][:12]
        board = board_env["data"] or {}
        rank_data = rank_env["data"]
        if isinstance(rank_data, dict):
            divisions = rank_data.get("divisions") or []
            p4p = rank_data.get("p4p") or []
            freshness_ok = bool(rank_data.get("freshness_verified"))
            rank_updated_local = rank_data.get("updated_local") or rank_env["updated_at_local"]
            rank_source_url = rank_data.get("source_url") or ufc_espn.UFC_OFFICIAL_RANKINGS_URL
        elif isinstance(rank_data, list):
            divisions = rank_data
            p4p = []
            freshness_ok = False
            rank_updated_local = rank_env["updated_at_local"]
            rank_source_url = ""
        else:
            divisions, p4p, freshness_ok, rank_updated_local, rank_source_url = [], [], False, "Нет данных", ""

        return {
            "event": board.get("event"),
            "main_event": board.get("main_event"),
            "co_main": board.get("co_main"),
            "fights": board.get("fights") or [],
            "rankings": divisions,
            "p4p": p4p,
            "rankings_freshness_verified": freshness_ok,
            "rankings_updated_local": rank_updated_local,
            "rankings_source_url": rank_source_url,
            "news": ufc_news,
            "meta": {
                "updated_at_utc": board_env["updated_at_utc"],
                "updated_at_local": board_env["updated_at_local"],
                "stale": board_env["stale"] or rank_env["stale"],
                "source": "ESPN UFC + UFC.com",
            },
        }

    def get_profile(self, name: str, force: bool = False) -> dict[str, Any]:
        """Возвращает профиль спортсмена/команды из Wikipedia REST API (с кешем 24ч)."""
        key = f"profile_{name.casefold()}"
        env = self._with_cache(
            key, TTL_PROFILES, lambda: media_wiki.fetch_wiki_summary(name), "Wikipedia REST", force=force
        )
        return {
            "profile": env["data"] or {"title": name, "summary": "Нет данных", "photo": ""},
            "meta": {
                "updated_at_utc": env["updated_at_utc"],
                "updated_at_local": env["updated_at_local"],
                "stale": env["stale"],
            },
        }

    def get_f1_round(self, round_num: int, force: bool = False) -> dict[str, Any]:
        """Возвращает результаты гонки, квалификации и спринта для этапа F1."""
        env = self._with_cache(
            f"f1_round_{round_num}",
            TTL_SCHEDULE,
            lambda: f1_jolpica.fetch_f1_round_details(round_num),
            "Jolpica F1",
            force=force,
        )
        return {
            "round": env["data"],
            "meta": {
                "updated_at_utc": env["updated_at_utc"],
                "updated_at_local": env["updated_at_local"],
                "stale": env["stale"],
            },
        }

    def get_f1_driver(self, driver_id: str, force: bool = False) -> dict[str, Any]:
        """Возвращает профиль гонщика F1 (сезон + карьера + Wikipedia)."""
        drv_env = self._with_cache(
            f"f1_driver_{driver_id}",
            TTL_PROFILES,
            lambda: f1_jolpica.fetch_f1_driver_profile(driver_id),
            "Jolpica F1",
            force=force,
        )
        drv = drv_env["data"] or {"name": driver_id, "career_stats": {}, "season_results": []}
        f1 = self.get_f1_overview(force=False)
        standing = next((d for d in f1.get("drivers", []) if d.get("driver_id") == driver_id), {})

        wiki_env = self._with_cache(
            f"wiki_f1_drv_{driver_id or drv['name'].casefold()}",
            TTL_PROFILES,
            lambda: media_wiki.fetch_wiki_summary(
                drv["name"],
                wiki_url=drv.get("wiki_url") or standing.get("wiki_url") or "",
                search_hint="Formula One racing driver",
                required_keywords=("formula one", "racing driver", "grand prix", "motorsport"),
                translate_ru=True,
            ),
            "Wikipedia REST",
            force=force,
        )
        wiki = wiki_env["data"] or {}
        return {
            "driver": {
                **drv,
                "season_pos": standing.get("pos", "Нет данных"),
                "season_points": standing.get("points", "0"),
                "season_wins": standing.get("wins", "0"),
                "team_logo": standing.get("team_logo", ""),
                "photo": wiki.get("photo") or "",
                "bio": wiki.get("summary") or "Нет данных",
                "is_auto_translated": bool(wiki.get("is_auto_translated")),
                "wiki_url": wiki.get("source_url") or drv.get("wiki_url") or "",
                "license_note": wiki.get("license_note") or "",
            },
            "meta": {
                "updated_at_utc": drv_env["updated_at_utc"],
                "updated_at_local": drv_env["updated_at_local"],
                "stale": drv_env["stale"],
            },
        }

    def get_f1_constructor(self, constructor_id: str, force: bool = False) -> dict[str, Any]:
        """Возвращает профиль команды Formula 1."""
        con_env = self._with_cache(
            f"f1_constructor_{constructor_id}",
            TTL_PROFILES,
            lambda: f1_jolpica.fetch_f1_constructor_profile(constructor_id),
            "Jolpica F1",
            force=force,
        )
        con = con_env["data"] or {"name": constructor_id, "drivers": []}
        f1 = self.get_f1_overview(force=False)
        standing = next((c for c in f1.get("constructors", []) if c.get("constructor_id") == constructor_id), {})

        target_wiki_url = con.get("wiki_url") or standing.get("wiki_url") or ""
        wiki_env = self._with_cache(
            f"wiki_f1_con_{constructor_id}",
            TTL_PROFILES,
            lambda: media_wiki.fetch_wiki_summary(
                con["name"],
                wiki_url=target_wiki_url,
                search_hint="Formula One team constructor",
                required_keywords=("formula one", "grand prix", "constructor", "racing"),
                translate_ru=True,
            ),
            "Wikipedia REST",
            force=force,
        )
        wiki = wiki_env["data"] or {}
        infobox_env = self._with_cache(
            f"wiki_f1_box_{constructor_id}",
            TTL_PROFILES,
            lambda: media_wiki.fetch_f1_team_infobox(wiki.get("source_url") or target_wiki_url),
            "Wikipedia Infobox",
            force=force,
        )
        infobox = infobox_env["data"] or {}
        return {
            "constructor": {
                **con,
                "base": infobox.get("base") or con.get("base") or "Нет данных",
                "team_chief": infobox.get("team_chief") or con.get("team_chief") or "Нет данных",
                "power_unit": infobox.get("power_unit") or con.get("power_unit") or "Нет данных",
                "season_pos": standing.get("pos", "Нет данных"),
                "season_points": standing.get("points", "0"),
                "season_wins": standing.get("wins", "0"),
                "logo": con.get("logo") or standing.get("logo") or wiki.get("photo") or "",
                "photo": wiki.get("photo") or con.get("logo") or standing.get("logo") or "",
                "bio": wiki.get("summary") or "Нет данных",
                "is_auto_translated": bool(wiki.get("is_auto_translated")),
                "wiki_url": wiki.get("source_url") or target_wiki_url,
                "license_note": wiki.get("license_note") or "",
            },
            "meta": {
                "updated_at_utc": con_env["updated_at_utc"],
                "updated_at_local": con_env["updated_at_local"],
                "stale": con_env["stale"],
            },
        }

    def get_ufc_fighter(self, fighter_id: str = "", name: str = "", force: bool = False) -> dict[str, Any]:
        """Возвращает профиль бойца UFC (ESPN + рейтинги + Wikipedia)."""
        cache_key = f"ufc_fighter_{fighter_id or name.casefold()}"
        f_env = self._with_cache(
            cache_key,
            TTL_PROFILES,
            lambda: ufc_espn.fetch_ufc_fighter_profile(fighter_id, name),
            "ESPN UFC",
            force=force,
        )
        fighter = f_env["data"] or {"name": name or "Нет данных"}
        ufc = self.get_ufc_overview(force=False)
        rank_info = "Вне рейтинга / Нет данных"
        champ_status = "Нет"
        target_name = str(fighter.get("name") or name).casefold()
        for div in ufc.get("rankings", []):
            ch = div.get("champion")
            if ch and str(ch.get("name", "")).casefold() == target_name:
                champ_status = f"Чемпион ({div.get('name')})"
                rank_info = "Чемпион"
                break
            for c in div.get("contenders", []):
                if str(c.get("name", "")).casefold() == target_name:
                    rank_info = f"#{c.get('rank')} ({div.get('name')})"
                    break

        wiki_name = str(fighter.get("name") or name)
        wiki_env = self._with_cache(
            f"wiki_ufc_{wiki_name.casefold()}",
            TTL_PROFILES,
            lambda: media_wiki.fetch_wiki_summary(
                wiki_name,
                search_hint="UFC mixed martial artist",
                required_keywords=("mixed martial", "ufc", "mma", "martial artist", "fighter"),
                translate_ru=True,
            ),
            "Wikipedia REST",
            force=force,
        )
        wiki = wiki_env["data"] or {}
        return {
            "fighter": {
                **fighter,
                "photo": fighter.get("photo") or wiki.get("photo") or "",
                "ranking_position": rank_info,
                "champion_status": champ_status,
                "bio": wiki.get("summary") or "Нет данных",
                "is_auto_translated": bool(wiki.get("is_auto_translated")),
                "wiki_url": wiki.get("source_url") or "",
            },
            "meta": {
                "updated_at_utc": f_env["updated_at_utc"],
                "updated_at_local": f_env["updated_at_local"],
                "stale": f_env["stale"],
            },
        }

    def get_overview(self, force: bool = False) -> dict[str, Any]:
        """Сводный главный экран BahonIQ Sports."""
        clubs = {}
        for cid in football_espn.CLUBS_CONFIG:
            sched_env = self._with_cache(
                f"football_schedule_{cid}",
                TTL_SCHEDULE,
                lambda c=cid: football_espn.fetch_club_schedule(c),
                "ESPN Soccer",
                force=force,
            )
            data = sched_env["data"] or {}
            clubs[cid] = {
                "club": football_espn.CLUBS_CONFIG[cid],
                "last_match": data.get("last_match"),
                "next_match": data.get("next_match"),
                "form": data.get("form") or [],
                "stale": sched_env["stale"],
                "updated_at_local": sched_env["updated_at_local"],
            }

        f1 = self.get_f1_overview(force=force)
        ufc = self.get_ufc_overview(force=force)
        nc = self.get_news_center(force=force)
        all_nc = nc.get("items") or []
        fb_news = [i for i in all_nc if i.get("category") == "football"][:4]
        combined_news = fb_news + (f1.get("news") or [])[:3] + (ufc.get("news") or [])[:3]

        return {
            "clubs": clubs,
            "f1_next": f1.get("next_race"),
            "f1_last": f1.get("last_results"),
            "ufc_event": ufc.get("event"),
            "ufc_main_event": ufc.get("main_event"),
            "news": combined_news,
            "meta": {
                "updated_at_utc": utc_now_iso(),
                "updated_at_local": format_qyzylorda(utc_now_iso()),
                "timezone": "Asia/Qyzylorda",
            },
        }
