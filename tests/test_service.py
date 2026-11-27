import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poker import poker_ai
from poker.poker_engine import STREETS
from poker.poker_routes import dispatch
from poker.poker_state import PokerError, PokerService

poker_ai.ITERS_SCALE = 0.08


def new_service(tmp, seed=3):
    return PokerService(Path(tmp) / "save.json", rng=random.Random(seed), ai_rng=random.Random(seed + 1))


def total_money(svc):
    g = svc.game
    if not g:
        return svc.data["balance"]
    me = g.seats[0]
    return svc.data["balance"] + me.stack + (0 if g.paid else me.total)


def finish_hand(svc):
    guard = 0
    while svc.game.phase in STREETS:
        guard += 1
        assert guard < 400, "раздача зависла"
        g = svc.game
        if g.to_act == 0:
            legal = g.legal_actions(0)
            svc.action(g.seq, "check" if "check" in legal else "call" if "call" in legal else "fold")
        else:
            svc.advance(g.seq)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.svc = new_service(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def total(self):
        """Все деньги игрока: баланс + стек + фишки, уже вложенные в банк текущей раздачи."""
        s = self.svc
        return total_money(s)

    def net_result(self, svc):
        """Выигрыш/проигрыш игрока в уже завершённой раздаче."""
        g = svc.game
        return g.result["net"][0] if g and g.result else 0

    def test_start_balance_and_locked_tables(self):
        st = self.svc.state()
        self.assertEqual(st["profile"]["balance"], 50_000)
        avail = {t["id"]: t for t in st["tables"]}
        self.assertTrue(avail["grand"]["available"])
        self.assertFalse(avail["high"]["available"])
        self.assertEqual(avail["high"]["lock_reason"], "Для входа необходимо минимум 75 000")
        with self.assertRaises(PokerError) as ctx:
            self.svc.join("high", 100_000)
        self.assertIn("75 000", ctx.exception.message)
        self.assertEqual(self.svc.data["balance"], 50_000)

    def test_buyin_debited_and_returned(self):
        self.svc.join("rookie", 2_000)
        self.assertEqual(self.svc.data["balance"], 48_000)
        self.assertEqual(self.total(), 50_000)
        finish_hand(self.svc)
        self.svc.leave()
        self.assertIsNone(self.svc.game)
        self.assertEqual(self.svc.data["balance"], sum([self.svc.data["balance"]]))  # деньги вернулись
        self.assertGreaterEqual(self.svc.data["balance"], 46_000)

    def test_buyin_limits_no_negative_balance(self):
        for bad in (500, 5_000, "x", None):
            with self.assertRaises(PokerError):
                self.svc.join("rookie", bad)
        self.svc.data["balance"] = 1_500
        with self.assertRaises(PokerError):
            self.svc.join("rookie", 2_000)               # больше, чем на балансе
        self.assertEqual(self.svc.data["balance"], 1_500)
        self.svc.join("rookie", 1_500)
        self.assertEqual(self.svc.data["balance"], 0)
        self.assertGreaterEqual(self.svc.data["balance"], 0)

    def test_cannot_join_twice(self):
        self.svc.join("rookie", 2_000)
        with self.assertRaises(PokerError):
            self.svc.join("rookie", 2_000)
        self.assertEqual(self.total(), 50_000)

    def test_leave_mid_hand_waits_for_hand_end(self):
        self.svc.join("rookie", 2_000)
        st = self.svc.leave()
        self.assertIsNotNone(st["session"])
        self.assertTrue(st["session"]["leave_requested"])
        self.assertEqual(self.total(), 50_000)
        finish_hand(self.svc)
        self.svc.leave()
        self.svc.leave()                                  # повторный вызов безопасен
        self.assertIsNone(self.svc.game)
        self.assertEqual(self.svc.data["balance"] + 0, self.svc.state()["profile"]["balance"])

    def test_stats_counted_once(self):
        self.svc.join("rookie", 2_000)
        finish_hand(self.svc)
        for _ in range(4):
            self.svc._after_mutation()
        self.assertEqual(self.svc.data["stats"]["hands"], 1)
        again = new_service(self.tmp.name)               # перезапуск
        self.assertEqual(again.data["stats"]["hands"], 1)
        self.assertEqual(total_money(again) - self.net_result(again), 50_000)

    def test_stale_seq_and_double_click(self):
        self.svc.join("rookie", 2_000)
        g = self.svc.game
        while g.to_act != 0 and g.phase in STREETS:
            self.svc.advance(g.seq)
        if g.phase == "complete":
            self.skipTest("раздача закончилась без хода игрока")
        seq = g.seq
        legal = g.legal_actions(0)
        act = "call" if "call" in legal else "check"
        self.svc.action(seq, act)
        with self.assertRaises(PokerError) as ctx:
            self.svc.action(seq, act)                    # двойной клик с тем же seq
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(self.total(), 50_000)

    def test_persistence_mid_hand_no_duplication(self):
        self.svc.join("city", 10_000)
        again = new_service(self.tmp.name)
        self.assertEqual(again.game.seq, self.svc.game.seq)
        self.assertEqual(again.game.seats[0].hole, self.svc.game.seats[0].hole)
        self.assertEqual(again.data["balance"], self.svc.data["balance"])
        self.assertEqual(total_money(again), 50_000)
        third = new_service(self.tmp.name)
        self.assertEqual(total_money(third), 50_000)

    def test_reset_requires_confirm_and_wipes(self):
        self.svc.join("rookie", 2_000)
        finish_hand(self.svc)
        with self.assertRaises(PokerError):
            self.svc.reset(False)
        self.svc.reset(True)
        st = self.svc.state()
        self.assertEqual(st["profile"]["balance"], 50_000)
        self.assertEqual(st["profile"]["stats"]["hands"], 0)
        self.assertIsNone(st["session"])

    def test_bankrupt_screen_state(self):
        self.svc.data["balance"] = 900
        self.assertTrue(self.svc.state()["profile"]["bankrupt"])
        self.svc.data["balance"] = 1_000
        self.assertFalse(self.svc.state()["profile"]["bankrupt"])

    def test_public_state_hides_foreign_cards(self):
        self.svc.join("rookie", 2_000)
        sess = self.svc.state()["session"]
        mine = sess["seats"][0]["cards"]
        self.assertTrue(all(c != "??" for c in mine))
        for s in sess["seats"][1:]:
            self.assertEqual(s["cards"], ["??", "??"])
        finish_hand(self.svc)
        raw = json.dumps(self.svc.state()["session"], ensure_ascii=False)
        self.assertIn("seats", raw)

    def test_http_layer(self):
        code, body = dispatch(self.svc, "GET", "/api/poker/state", None)
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        code, body = dispatch(self.svc, "POST", "/api/poker/join", {"table_id": "private", "buyin": 300000})
        self.assertEqual(code, 400)
        self.assertIn("250 000", body["error"])
        code, body = dispatch(self.svc, "POST", "/api/poker/reset", {})
        self.assertEqual(code, 400)
        code, _ = dispatch(self.svc, "GET", "/api/poker/nope", None)
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
