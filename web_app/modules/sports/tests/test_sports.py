"""Базовые тесты для BahonIQ Sports (Этап 2)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from web_app.modules.sports.cache import SportsCache
from web_app.modules.sports.providers import f1_jolpica, football_espn, news_rss, ufc_espn
from web_app.modules.sports.service import SportsService
from web_app.modules.sports.time_utils import format_qyzylorda
from web_app.server import app


class SportsTimeAndCacheTests(unittest.TestCase):
    def test_utc_to_qyzylorda_conversion(self):
        self.assertEqual(format_qyzylorda("2026-11-20T15:00:00Z"), "20.11.2026 20:00")
        self.assertEqual(format_qyzylorda(""), "Нет данных")

    def test_cache_handles_corrupted_json_and_preserves_good_cache_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = SportsCache(Path(tmp))
            bad = Path(tmp) / "broken.json"
            bad.write_text("{bad json", encoding="utf-8")
            self.assertIsNone(cache.get("broken", ttl=60))
            self.assertIsNone(cache.get_stale("broken"))

            service = SportsService(cache=cache)
            # 1. Успешное сохранение в кеш
            with patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_calendar", return_value={"season": "2026", "next_race": None, "races": []}), \
                 patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_standings", return_value={"drivers": [], "constructors": []}), \
                 patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_last_results", return_value={"race_name": "Test GP", "results": []}), \
                 patch("web_app.modules.sports.providers.news_rss.fetch_rss_news", return_value=[]):
                ok = service.get_f1_overview(force=True)
                self.assertFalse(ok["meta"]["stale"])
                self.assertEqual(ok["last_results"]["race_name"], "Test GP")

            # 2. Сбой сети -> возврат исправного кеша с пометкой stale=True
            with patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_calendar", side_effect=RuntimeError("timeout")), \
                 patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_standings", side_effect=RuntimeError("timeout")), \
                 patch("web_app.modules.sports.providers.f1_jolpica.fetch_f1_last_results", side_effect=RuntimeError("timeout")), \
                 patch("web_app.modules.sports.providers.news_rss.fetch_rss_news", side_effect=RuntimeError("timeout")):
                fallback = service.get_f1_overview(force=True)
                self.assertTrue(fallback["meta"]["stale"])
                self.assertEqual(fallback["last_results"]["race_name"], "Test GP")


class SportsProvidersNormalizationTests(unittest.TestCase):
    def test_football_postponed_and_deduplication(self):
        fake_schedule = {
            "events": [
                {
                    "id": "101",
                    "date": "2026-11-22T20:00Z",
                    "competitions": [{
                        "status": {"type": {"name": "STATUS_POSTPONED", "state": "pre", "completed": False}},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Real Madrid"}},
                            {"homeAway": "away", "team": {"displayName": "Barcelona"}},
                        ],
                    }],
                },
                {
                    "id": "101",
                    "date": "2026-11-22T20:00Z",
                    "competitions": [{
                        "status": {"type": {"name": "STATUS_POSTPONED", "state": "pre", "completed": False}},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Real Madrid"}},
                            {"homeAway": "away", "team": {"displayName": "Barcelona"}},
                        ],
                    }],
                },
            ]
        }
        with patch("web_app.modules.sports.providers.football_espn.fetch_json", return_value=fake_schedule):
            res = football_espn.fetch_club_schedule("real_madrid")
            self.assertEqual(len(res["matches"]), 1)
            self.assertEqual(res["matches"][0]["status"], "postponed")
            self.assertEqual(res["matches"][0]["status_label"], "Перенесён")

    def test_ufc_canceled_fight_status(self):
        fake_ufc = {
            "events": [{
                "id": "999",
                "name": "UFC 320",
                "date": "2026-12-01T03:00Z",
                "competitions": [{
                    "id": "f1",
                    "status": {"type": {"name": "STATUS_CANCELED", "state": "post", "completed": False}},
                    "competitors": [
                        {"athlete": {"displayName": "Fighter A"}, "records": [{"summary": "20-1"}]},
                        {"athlete": {"displayName": "Fighter B"}, "records": [{"summary": "18-2"}]},
                    ],
                }],
            }]
        }
        with patch("web_app.modules.sports.providers.ufc_espn.fetch_json", return_value=fake_ufc):
            res = ufc_espn.fetch_ufc_scoreboard()
            self.assertEqual(res["fights"][0]["status"], "canceled")
            self.assertEqual(res["fights"][0]["status_label"], "Отменён")

    def test_rss_rumor_marking_and_deduplication(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel>
          <item><title>Real Madrid transfer rumour: player linked with move</title><link>https://example.com/1</link></item>
          <item><title>Real Madrid transfer rumour: player linked with move</title><link>https://example.com/1</link></item>
          <item><title>Real Madrid official match report</title><link>https://example.com/2</link></item>
        </channel></rss>"""
        with patch("web_app.modules.sports.providers.news_rss.fetch_text", return_value=xml):
            items = news_rss.fetch_rss_news("football")
            self.assertEqual(len(items), 2)
            self.assertTrue(items[0]["is_rumor"])
            self.assertFalse(items[1]["is_rumor"])


class SportsApiRoutesTests(unittest.TestCase):
    def test_fastapi_routes_and_unknown_club(self):
        client = TestClient(app)
        resp_404 = client.get("/api/sports/football/unknown_club")
        self.assertEqual(resp_404.status_code, 404)
        self.assertEqual(client.get("/api/sports/ufc/fighter").status_code, 400)

        with patch("web_app.routers.sports._service.get_overview", return_value={"clubs": {}, "meta": {"updated_at_local": "20.11.2026 12:30"}}), \
             patch("web_app.routers.sports._service.get_f1_overview", return_value={"season": "2026", "meta": {}}), \
             patch("web_app.routers.sports._service.get_ufc_overview", return_value={"event": None, "fights": [], "meta": {}}), \
             patch("web_app.routers.sports._service.get_profile", return_value={"profile": {"title": "Jude Bellingham"}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_match_detail", return_value={"match": {"id": "1"}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_football_player_profile", return_value={"player": {"id": "2"}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_f1_round", return_value={"round": {"round": 1}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_f1_driver", return_value={"driver": {"driver_id": "max_verstappen"}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_f1_constructor", return_value={"constructor": {"constructor_id": "red_bull"}, "meta": {}}), \
             patch("web_app.routers.sports._service.get_ufc_fighter", return_value={"fighter": {"name": "Islam Makhachev"}, "meta": {}}):
            self.assertEqual(client.get("/api/sports/overview").status_code, 200)
            self.assertEqual(client.get("/api/sports/f1").status_code, 200)
            self.assertEqual(client.get("/api/sports/ufc").status_code, 200)
            self.assertEqual(client.get("/api/sports/profile?name=Jude%20Bellingham").status_code, 200)
            self.assertEqual(client.get("/api/sports/football/real_madrid/match/1").status_code, 200)
            self.assertEqual(client.get("/api/sports/football/real_madrid/player/2").status_code, 200)
            self.assertEqual(client.get("/api/sports/f1/round/1").status_code, 200)
            self.assertEqual(client.get("/api/sports/f1/driver/max_verstappen").status_code, 200)
            self.assertEqual(client.get("/api/sports/f1/constructor/red_bull").status_code, 200)
            self.assertEqual(client.get("/api/sports/ufc/fighter?name=Islam%20Makhachev").status_code, 200)


class SportsStage3DetailsTests(unittest.TestCase):
    def test_match_detail_normalization(self):
        fake_summary = {
            "header": {
                "league": {"name": "La Liga"},
                "season": {"name": "2026-27"},
                "competitions": [{
                    "date": "2026-11-20T20:00Z",
                    "status": {"type": {"state": "post", "completed": True, "shortDetail": "FT"}},
                    "competitors": [
                        {"homeAway": "home", "score": "2", "team": {"displayName": "Real Madrid"}},
                        {"homeAway": "away", "score": "1", "team": {"displayName": "Getafe"}},
                    ],
                }],
            },
            "gameInfo": {"venue": {"fullName": "Santiago Bernabéu"}},
            "rosters": [{
                "homeAway": "home",
                "formation": "4-3-3",
                "team": {"displayName": "Real Madrid"},
                "roster": [{"starter": True, "jersey": "5", "athlete": {"id": "10", "displayName": "Jude Bellingham"}}],
            }],
            "keyEvents": [
                {"type": {"text": "Goal"}, "clock": {"displayValue": "45'"}, "text": "Goal!", "team": {"displayName": "Real Madrid"}},
            ],
            "boxscore": {"teams": [{"team": {"displayName": "Real Madrid"}, "statistics": [{"label": "Possession", "displayValue": "62%"}]}]},
        }
        with patch("web_app.modules.sports.providers.football_espn.fetch_json", return_value=fake_summary):
            m = football_espn.fetch_match_detail("real_madrid", "777")
            self.assertEqual(m["venue"], "Santiago Bernabéu")
            self.assertEqual(m["rosters"][0]["formation"], "4-3-3")
            self.assertEqual(len(m["goals"]), 1)
            self.assertEqual(m["team_stats"][0]["stats"][0]["value"], "62%")

    def test_f1_driver_separates_season_and_career(self):
        drv_info = {"MRData": {"DriverTable": {"Drivers": [{"driverId": "leclerc", "givenName": "Charles", "familyName": "Leclerc", "permanentNumber": "16", "nationality": "Monegasque", "dateOfBirth": "1997-10-16"}]}}}
        season_res = {"MRData": {"RaceTable": {"Races": [{"round": "1", "raceName": "Bahrain GP", "Results": [{"position": "2", "points": "18", "Constructor": {"name": "Ferrari"}}]}]}}}
        career_res = {"MRData": {"RaceTable": {"Races": [
            {"Results": [{"position": "1", "grid": "1", "FastestLap": {"rank": "1"}}]},
            {"Results": [{"position": "3", "grid": "2"}]},
        ]}}}
        with patch("web_app.modules.sports.providers.f1_jolpica.fetch_json", side_effect=[drv_info, season_res, career_res]):
            prof = f1_jolpica.fetch_f1_driver_profile("leclerc")
            self.assertEqual(len(prof["season_results"]), 1)
            self.assertEqual(prof["career_stats"]["starts"], 2)
            self.assertEqual(prof["career_stats"]["wins"], 1)
            self.assertEqual(prof["career_stats"]["podiums"], 2)
            self.assertEqual(prof["career_stats"]["poles"], 1)
            self.assertEqual(prof["career_stats"]["fastest_laps"], 1)

    def test_ufc_numbered_event_and_fighter_profile(self):
        fake_ath = {"athlete": {"displayName": "Islam Makhachev", "nickname": "None", "age": 34, "displayHeight": "5' 10\"", "displayWeight": "155 lbs", "displayReach": "70\"", "stance": {"text": "Southpaw"}, "headshot": {"href": "https://example.com/p.png"}}}
        with patch("web_app.modules.sports.providers.ufc_espn.fetch_json", return_value=fake_ath):
            prof = ufc_espn.fetch_ufc_fighter_profile("123")
            self.assertEqual(prof["name"], "Islam Makhachev")
            self.assertEqual(prof["stance"], "Левша")
            self.assertEqual(prof["reach"], "70\"")


class SportsSemanticQualityTests(unittest.TestCase):
    def test_wikipedia_skips_disambiguation_and_uses_f1_url(self):
        from web_app.modules.sports.providers import media_wiki

        disambig = {"type": "disambiguation", "title": "Mercedes", "extract": "Mercedes may refer to:"}
        f1_page = {
            "type": "standard",
            "title": "Mercedes-Benz in Formula One",
            "extract": "Mercedes-Benz is a Formula One constructor.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Mercedes-Benz_in_Formula_One"}},
            "thumbnail": {"source": "https://upload.wikimedia.org/merc.png"},
        }

        def fake_fetch(url, **kwargs):
            if "Mercedes-Benz_in_Formula_One" in url:
                return f1_page
            return disambig

        with patch("web_app.modules.sports.providers.media_wiki.fetch_json", side_effect=fake_fetch):
            res = media_wiki.fetch_wiki_summary(
                "Mercedes",
                wiki_url="https://en.wikipedia.org/wiki/Mercedes-Benz_in_Formula_One",
                required_keywords=("formula one", "constructor"),
                translate_ru=False,
            )
            self.assertEqual(res["title"], "Mercedes-Benz in Formula One")
            self.assertFalse(res["is_disambiguation"])
            self.assertIn("Formula One", res["summary"])

    def test_ufc_freshness_rejects_stale_or_missing_date(self):
        from web_app.modules.sports.providers import ufc_espn

        fake_html = """
        <div class="view-grouping">
          <div class="view-grouping-header">Lightweight</div>
          <div class="rankings--athlete--champion"><h5><a href="#">Justin Gaethje</a></h5></table></div>
        </div>
        <div class="view-grouping">
          <div class="view-grouping-header">Men's Pound-for-Pound Top Rank</div>
          <div class="rankings--athlete--champion"><h5><a href="#">Islam Makhachev</a></h5></table></div>
        </div>
        """
        with (
            patch("web_app.modules.sports.providers.ufc_espn.fetch_text_with_headers", return_value=(fake_html, {})),
            patch("web_app.modules.sports.providers.ufc_espn._parse_wiki_title_dates", return_value={}),
        ):
            res = ufc_espn.fetch_ufc_rankings()
            self.assertFalse(res["freshness_verified"])
            self.assertEqual(len(res["divisions"]), 1)
            self.assertEqual(len(res["p4p"]), 1)
            self.assertEqual(res["divisions"][0]["name"], "Лёгкий вес")
            self.assertEqual(res["divisions"][0]["champion"]["name"], "Актуальный чемпион не подтверждён")

    def test_club_news_and_rumors_strictly_filtered_by_club(self):
        from web_app.modules.sports.cache import SportsCache
        from web_app.modules.sports.service import SportsService

        with tempfile.TemporaryDirectory() as tmp:
            svc = SportsService(cache=SportsCache(cache_dir=Path(tmp)))
            svc.cache.set("football_schedule_real_madrid", {"last_match": None, "next_match": None, "form": [], "recent_results": [], "season_results": [], "upcoming_matches": [], "matches": []}, "2026-11-20T10:00:00Z", "ESPN")
            svc.cache.set("football_roster_real_madrid", {"players": [], "roster_grouped": {}, "coaches": [], "injuries": []}, "2026-11-20T10:00:00Z", "ESPN")
            svc.cache.set("football_standings_esp.1", {"season": "2026-27", "updated_at_local": "20.11.2026", "rows": []}, "2026-11-20T10:00:00Z", "ESPN")
            svc.cache.set("news_center_v1", {"items": [
                {"id": "1", "title": "Слух о Манчестер Юнайтед", "title_original": "Man Utd transfer rumour", "summary": "Man Utd target", "summary_original": "Man Utd", "topics": ["man_utd", "transfers"], "is_rumor": True, "transfer_type": "rumor"},
                {"id": "2", "title": "Новости Реал Мадрид", "title_original": "Real Madrid match preview", "summary": "Bernabeu", "summary_original": "Bernabeu", "topics": ["real_madrid"], "is_rumor": False, "transfer_type": "none"},
            ]}, "2026-11-20T10:00:00Z", "BBC")

            res = svc.get_football_club("real_madrid", force=False)
            self.assertEqual(len(res["news"]), 1)
            self.assertEqual(res["news"][0]["id"], "2")
            self.assertEqual(len(res["transfer_rumors"]), 0)


if __name__ == "__main__":
    unittest.main()
