import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from simulate import run_simulation

from poker import poker_ai
from poker.poker_state import TABLES


class SimulationTests(unittest.TestCase):
    def test_simulation_all_tables(self):
        old = poker_ai.ITERS_SCALE
        poker_ai.ITERS_SCALE = 0.06
        try:
            for t in TABLES:
                res = run_simulation(hands=120, table_id=t["id"], seed=100 + t["level"])
                self.assertEqual(res["hands"], 120)
                self.assertEqual(res.get("recover_calls", 0), 0, "ход терялся и восстанавливался")
        finally:
            poker_ai.ITERS_SCALE = old


if __name__ == "__main__":
    unittest.main()
