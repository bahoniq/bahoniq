import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from helpers import make_game

from poker import poker_ai
from poker.poker_engine import STREETS
from poker.poker_state import TABLES

poker_ai.ITERS_SCALE = 0.08


def walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from walk_strings(v)


class BotTests(unittest.TestCase):
    def test_bot_view_contains_no_foreign_hole_cards(self):
        for seed in range(30):
            g = make_game([5000] * 6, seed=seed)
            g.start_hand()
            for _ in range(random.Random(seed).randint(0, 8)):
                if g.phase not in STREETS or g.to_act is None:
                    break
                legal = g.legal_actions(g.to_act)
                g.act(g.to_act, "call" if "call" in legal else "check")
            for i in range(9):
                view = g.bot_view(i)
                strings = set(walk_strings(view))
                for other in g.seats:
                    if other.index == i:
                        continue
                    for c in other.hole:
                        self.assertNotIn(c, strings, f"бот {i} видит карту {c} места {other.index}")
                for c in g.deck:
                    self.assertNotIn(c, strings)
                json.dumps(view)

    def test_ai_module_has_no_engine_access(self):
        src = (Path(__file__).resolve().parents[1] / "poker" / "poker_ai.py").read_text(encoding="utf-8")
        self.assertNotIn("poker_engine", src)
        self.assertNotIn("PokerGame", src)
        self.assertNotIn(".deck", src)

    def test_difficulty_scales_with_table(self):
        lv = poker_ai.LEVELS
        for a, b in zip(range(1, 5), range(2, 6)):
            self.assertLess(lv[a]["iters"], lv[b]["iters"])
            self.assertGreater(lv[a]["mistake"], lv[b]["mistake"])
            self.assertGreater(lv[a]["noise"], lv[b]["noise"])
        self.assertEqual(sorted(t["level"] for t in TABLES), [1, 2, 3, 4, 5])

    def test_decisions_always_legal_for_all_levels_and_personas(self):
        rng = random.Random(5)
        for level in range(1, 6):
            for persona in poker_ai.PERSONAS:
                for seed in range(6):
                    g = make_game([random.Random(seed).choice((300, 2000, 20000)) for _ in range(6)], seed=seed)
                    g.table["level"] = level
                    g.start_hand()
                    guard = 0
                    while g.phase in STREETS and guard < 80:
                        guard += 1
                        if g.to_act is None:
                            g.step_auto()
                            continue
                        i = g.to_act
                        action, amount = poker_ai.decide(g.bot_view(i), level, persona, rng)
                        g.act(i, action, amount)           # не должен бросать IllegalAction
                    self.assertTrue(g.total_chips() == g.expected_chips())

    def test_personas_differ_in_aggression(self):
        def raise_rate(persona):
            rng, raises, total = random.Random(11), 0, 0
            for seed in range(160):
                g = make_game([5000] * 6, seed=seed)
                g.start_hand()
                view = g.bot_view(g.to_act)
                a, _ = poker_ai.decide(view, 3, persona, rng)
                total += 1
                raises += a in ("raise", "bet", "allin")
            return raises / total

        self.assertGreater(raise_rate("shark"), raise_rate("rock"))


if __name__ == "__main__":
    unittest.main()
