import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poker.hand_evaluator import (FLUSH, FULL_HOUSE, HIGH_CARD, PAIR, QUADS, STRAIGHT, STRAIGHT_FLUSH, TRIPS,
                                  TWO_PAIR, describe, describe_hole_board, detect_draws, evaluate)


def ev(s):
    return evaluate(s.split())


class EvaluatorTests(unittest.TestCase):
    def test_each_category(self):
        cases = {
            HIGH_CARD: "As Kd 9h 7c 4s 3d 2h",
            PAIR: "As Ad 9h 7c 4s 3d 2h",
            TWO_PAIR: "As Ad 9h 9c 4s 3d 2h",
            TRIPS: "As Ad Ah 7c 4s 3d 2h",
            STRAIGHT: "5s 6d 7h 8c 9s Kd 2h",
            FLUSH: "As 9s 7s 4s 2s Kd Qh",
            FULL_HOUSE: "As Ad Ah 7c 7s 3d 2h",
            QUADS: "As Ad Ah Ac 7s 3d 2h",
            STRAIGHT_FLUSH: "5h 6h 7h 8h 9h Kd 2c",
        }
        for cat, hand in cases.items():
            self.assertEqual(ev(hand)[0], cat, hand)

    def test_royal_flush(self):
        sc = ev("As Ks Qs Js Ts 2d 3c")
        self.assertEqual(sc, (STRAIGHT_FLUSH, 14))
        self.assertEqual(describe(sc), "Роял-флеш")

    def test_wheel_straight_and_straight_flush(self):
        self.assertEqual(ev("As 2d 3h 4c 5s Kd 9h"), (STRAIGHT, 5))
        self.assertEqual(ev("Ah 2h 3h 4h 5h Kd 9c"), (STRAIGHT_FLUSH, 5))
        self.assertGreater(ev("2d 3h 4c 5s 6s Kd 9h"), ev("As 2d 3h 4c 5s Kd 9h"))

    def test_category_order(self):
        order = ["As Kd 9h 7c 4s 3d 2h", "As Ad 9h 7c 4s 3d 2h", "As Ad 9h 9c 4s 3d 2h",
                 "As Ad Ah 7c 4s 3d 2h", "5s 6d 7h 8c 9s Kd 2h", "As 9s 7s 4s 2s Kd Qh",
                 "As Ad Ah 7c 7s 3d 2h", "As Ad Ah Ac 7s 3d 2h", "5h 6h 7h 8h 9h Kd 2c"]
        scores = [ev(h) for h in order]
        self.assertEqual(scores, sorted(scores))

    def test_kickers(self):
        self.assertGreater(ev("As Ad Kh 7c 4s 3d 2h"), ev("As Ad Qh 7c 4s 3d 2h"))
        self.assertGreater(ev("As Ad 9h 9c Kc 3d 2h"), ev("As Ad 9h 9c Qc 3d 2h"))
        self.assertGreater(ev("Ah Ad Ac Ks 7d 3d 2h"), ev("Ah Ad Ac Qs 7d 3d 2h"))
        self.assertGreater(ev("Ks Kd 9h 7c 5s 3d 2h"), ev("Qs Qd Ah 7c 5s 3d 2h"))

    def test_equal_hands_tie(self):
        a = ev("As Kd Qh Jc 9s 3d 2h")
        b = ev("Ac Kh Qs Jd 9d 4d 2c")
        self.assertEqual(a, b)

    def test_board_plays(self):
        board = "As Ks Qs Js Ts"
        self.assertEqual(ev(board + " 2d 3c"), ev(board + " 4h 5h"))

    def test_best_five_of_seven(self):
        # три пары: берём две старшие, кикер — лучшая из оставшихся
        self.assertEqual(ev("Ks Kd 9h 9c 5s 5d 2h"), (TWO_PAIR, 13, 9, 5))
        # две тройки = фулл-хаус
        self.assertEqual(ev("As Ad Ah 7c 7s 7d 2h"), (FULL_HOUSE, 14, 7))
        # флеш из шести карт — берём пять старших
        self.assertEqual(ev("As Ks 9s 7s 4s 2s 3d"), (FLUSH, 14, 13, 9, 7, 4))
        # стрит из семи карт — старший
        self.assertEqual(ev("5s 6d 7h 8c 9s Td Jh"), (STRAIGHT, 11))

    def test_flush_beats_straight_in_same_hand(self):
        self.assertEqual(ev("5s 6s 7s 8s 2s 9d Td")[0], FLUSH)

    def test_descriptions(self):
        self.assertEqual(describe(ev("Js Jd 9h 7c 4s 3d 2h")), "Пара валетов")
        self.assertEqual(describe(ev("As Ad Kh Kc 4s 3d 2h")), "Две пары: тузов и королей")
        self.assertEqual(describe_hole_board(["Jh", "Jd"], []), "Карманная пара валетов")

    def test_draws(self):
        self.assertIn("Флеш-дро", detect_draws(["As", "Ks"], ["2s", "7s", "9d"]))
        self.assertTrue(any("Стрит-дро" in d for d in detect_draws(["8h", "9d"], ["6c", "7s", "Kd"])))
        self.assertEqual(detect_draws(["As", "Kd"], ["2s", "7c", "9d"]), [])


if __name__ == "__main__":
    unittest.main()
