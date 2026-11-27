import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import SMALL, deck_from, make_game, run_out

from poker.poker_engine import IllegalAction, NUM_SEATS, PokerGame


def conserved(g):
    return g.total_chips() == g.expected_chips()


class EngineTests(unittest.TestCase):
    def test_blinds_and_turn_order(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        self.assertEqual((g.seats[0].bet, g.seats[1].bet), (10, 20))   # SB — место 0, BB — место 1
        self.assertEqual(g.to_act, 2)
        order = []
        for _ in range(NUM_SEATS - 2):
            order.append(g.to_act)
            g.act(g.to_act, "fold")
        self.assertEqual(order, [2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(g.to_act, 0)
        self.assertTrue(conserved(g))

    def test_everybody_folds_pot_paid_once(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        for i in (2, 3, 4, 5, 6, 7, 8, 0):
            g.act(i, "fold")
        self.assertEqual(g.phase, "complete")
        self.assertEqual(g.result["winners"][0]["seat"], 1)
        self.assertEqual(g.seats[1].stack, 1010)
        self.assertEqual(g.seats[0].stack, 990)
        self.assertTrue(conserved(g))
        with self.assertRaises(IllegalAction):
            g._finalize([0] * NUM_SEATS, False, [], {})        # повторная выплата невозможна

    def test_check_through_streets_and_postflop_order(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        for i in (2, 3, 4, 5, 6, 7, 8):
            g.act(i, "call")
        g.act(0, "call")
        self.assertEqual(g.to_act, 1)                  # у BB есть опция
        g.act(1, "check")
        self.assertEqual((g.phase, len(g.board)), ("flop", 3))
        self.assertEqual(g.to_act, 0)                  # первым слева от дилера
        for expected, street, n in (("turn", "turn", 4), ("river", "river", 5)):
            for i in range(NUM_SEATS):
                self.assertEqual(g.to_act, i)
                g.act(i, "check")
            self.assertEqual((g.phase, len(g.board)), (street, n))
        for i in range(NUM_SEATS):
            g.act(i, "check")
        self.assertEqual(g.phase, "complete")
        self.assertTrue(g.result["showdown"])
        self.assertTrue(conserved(g))

    def test_min_raise_and_bad_amounts(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        lo, hi = g.legal_actions(2)["raise"]
        self.assertEqual((lo, hi), (40, 1000))
        for bad in (30, 39, 1001, -5, 0, float("nan"), float("inf"), "abc", None, True, 50.5):
            with self.assertRaises(IllegalAction, msg=str(bad)):
                g.act(2, "raise", bad)
        g.act(2, "raise", 100)
        self.assertEqual(g.legal_actions(3)["raise"][0], 180)    # рейз на 80 → минимум 100 + 80

    def test_no_double_action_and_wrong_turn(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        g.act(2, "call")
        with self.assertRaises(IllegalAction):
            g.act(2, "call")
        with self.assertRaises(IllegalAction):
            g.act(5, "call")
        with self.assertRaises(IllegalAction):
            g.act(3, "check")                          # нельзя чекнуть, когда есть ставка
        with self.assertRaises(IllegalAction):
            make_game([1000] * NUM_SEATS).act(0, "fold")       # раздача не начата

    def test_incomplete_allin_does_not_reopen(self):
        g = make_game([1000, 1000, 1000, 70, 1000, 1000, 1000, 1000, 1000])
        g.start_hand()
        g.act(2, "raise", 60)
        g.act(3, "allin")                              # 70 — неполный рейз (+10)
        for i in (4, 5, 6, 7, 8, 0, 1):
            g.act(i, "fold")
        self.assertEqual(g.to_act, 2)
        legal = g.legal_actions(2)
        self.assertIn("call", legal)
        self.assertNotIn("raise", legal)
        self.assertNotIn("allin", legal)
        g.act(2, "call")
        self.assertTrue(conserved(g))

    def test_full_raise_reopens_for_all(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        g.act(2, "call")
        g.act(3, "raise", 80)
        for i in (4, 5, 6, 7, 8, 0, 1):
            g.act(i, "call") if i != 0 else g.act(i, "fold")
        self.assertEqual(g.to_act, 2)
        self.assertIn("raise", g.legal_actions(2))

    def test_side_pots_three_way_allin(self):
        g = make_game([100, 300, 1000, 1000, 1000, 1000, 1000, 1000, 1000])
        holes = {0: ("As", "Ad"), 1: ("Ks", "Kd"), 2: ("7c", "2d")}
        board = ["9h", "8d", "3c", "4s", "Jh"]
        g.start_hand(deck=deck_from(holes, board))
        g.act(2, "allin")
        for i in (3, 4, 5, 6, 7, 8):
            g.act(i, "fold")
        g.act(0, "call")
        g.act(1, "call")
        self.assertTrue(g.auto_runout)
        run_out(g)
        self.assertEqual([p["amount"] for p in g.result["pots"]], [300, 400, 700])
        self.assertEqual((g.seats[0].stack, g.seats[1].stack, g.seats[2].stack), (300, 400, 700))
        self.assertTrue(conserved(g))
        self.assertEqual(g.result["net"][0], 200)

    def test_split_pot_with_odd_chip(self):
        g = make_game([1000] * NUM_SEATS, table=SMALL)
        board = ["As", "Ks", "Qs", "Js", "Ts"]                    # на столе роял-флеш — ничья
        g.start_hand(deck=deck_from({1: ("2c", "3d"), 2: ("4c", "5d")}, board))
        g.act(2, "call")
        for i in (3, 4, 5, 6, 7, 8, 0):
            g.act(i, "fold")
        g.act(1, "check")
        for _ in range(3):
            for i in (1, 2):
                g.act(i, "check")
        self.assertEqual(g.phase, "complete")
        self.assertEqual(len(g.result["winners"]), 2)
        self.assertEqual(g.seats[1].stack, 1003)                  # лишняя фишка — ближайшему слева от дилера
        self.assertEqual(g.seats[2].stack, 1002)
        self.assertEqual(g.seats[0].stack, 995)
        self.assertTrue(conserved(g))

    def test_multiple_winners_split_equally(self):
        g = make_game([1000] * NUM_SEATS)
        board = ["As", "Ks", "Qs", "Js", "Ts"]
        g.start_hand(deck=deck_from({}, board))
        for i in (2, 3, 4, 5, 6, 7, 8, 0):
            g.act(i, "call")
        g.act(1, "check")
        for _ in range(3):
            for i in range(NUM_SEATS):
                g.act(i, "check")
        self.assertEqual([w["amount"] for w in g.result["winners"]], [20] * NUM_SEATS)
        self.assertTrue(conserved(g))

    def test_dealer_rotation_and_rebuy_accounting(self):
        g = make_game([1000] * NUM_SEATS, dealer=2)
        d0 = g.dealer
        g.start_hand()
        self.assertEqual(g.dealer, d0)
        for _ in range(NUM_SEATS - 1):
            g.act(g.to_act, "fold")
        self.assertEqual(g.phase, "complete")
        g.start_hand()
        self.assertEqual(g.dealer, (d0 + 1) % NUM_SEATS)
        for _ in range(NUM_SEATS - 1):
            g.act(g.to_act, "fold")
        removed = g.seats[3].stack - 5
        g.seats[3].stack = 5                                     # бот почти без фишек
        g.initial_total -= removed                               # учёт внешнего изменения теста
        g.start_hand()
        self.assertGreaterEqual(g.seats[3].stack, g.table["min_buyin"])
        self.assertTrue(conserved(g))

    def test_serialization_roundtrip_mid_hand(self):
        g = make_game([1000] * NUM_SEATS)
        g.start_hand()
        g.act(2, "raise", 100)
        g2 = PokerGame.from_dict(g.to_dict())
        self.assertEqual(g.to_dict(), g2.to_dict())
        g.act(3, "call")
        g2.act(3, "call")
        self.assertEqual(g.to_dict(), g2.to_dict())

    def test_allin_blinds_short_stacks(self):
        g = make_game([5, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000])  # у игрока (SB) не хватает на блайнд
        g.start_hand()
        self.assertTrue(g.seats[0].all_in)
        self.assertEqual(g.seats[0].bet, 5)
        self.assertEqual(g.current_bet, 20)
        for i in (2, 3, 4, 5, 6, 7, 8):
            g.act(i, "fold")
        self.assertTrue(g.auto_runout)                             # BB торговаться не с кем — доигрываем борд
        run_out(g)
        self.assertEqual(g.result["pots"][-1]["eligible"], [1])    # лишняя часть ставки BB возвращается ему
        self.assertTrue(conserved(g))


if __name__ == "__main__":
    unittest.main()
