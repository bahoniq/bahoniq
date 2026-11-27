"""Симуляция большого числа раздач: поиск зависаний, дублей карт и потери/создания денег."""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poker import poker_ai
from poker.poker_engine import STREETS, PokerGame, Seat
from poker.poker_state import BOTS, TABLES


def check_invariants(g: PokerGame) -> None:
    assert g.total_chips() == g.expected_chips(), (
        f"деньги изменились: {g.total_chips()} != {g.expected_chips()}")
    cards = [c for s in g.seats for c in s.hole] + g.board + g.deck
    dup = [c for c, n in Counter(cards).items() if n > 1]
    assert not dup, f"дубли карт: {dup}"
    for s in g.seats:
        assert s.stack >= 0 and s.bet >= 0 and s.total >= s.bet, f"некорректный стек/ставка у {s.name}"


def random_legal(g: PokerGame, i: int, rng) -> tuple:
    legal = g.legal_actions(i)
    key = rng.choice(list(legal))
    if key in ("bet", "raise"):
        lo, hi = legal[key]
        amt = lo if rng.random() < 0.5 else rng.randint(lo, hi)
        return key, amt
    return key, None


def run_simulation(hands=200, table_id="city", seed=1, verbose=False) -> dict:
    rng, ai_rng = random.Random(seed), random.Random(seed + 7)
    table = next(t for t in TABLES if t["id"] == table_id)
    stats = Counter()
    game = None
    for _ in range(hands):
        if game is None or game.seats[0].stack <= 0:
            stats["sessions"] += 1
            seats = [Seat(0, "Вы", True, table["max_buyin"])]
            helper = PokerGame(table, [Seat(0, "x", True, 1)], rng=rng)
            seats += [Seat(i, b["name"], False, helper._bot_stack(), persona=b["persona"])
                      for i, b in enumerate(BOTS, start=1)]
            game = PokerGame(table, seats, rng=rng)
        game.start_hand()
        steps = 0
        while game.phase in STREETS:
            steps += 1
            assert steps < 400, "раздача зависла"
            if game.to_act is None:
                if game.auto_runout:
                    game.step_auto()
                else:
                    game.recover()
                    stats["recover_calls"] += 1
            else:
                i = game.to_act
                seat = game.seats[i]
                if i == 0 and rng.random() < 0.5:
                    action, amount = random_legal(game, i, rng)
                else:
                    persona = seat.persona or rng.choice(list(poker_ai.PERSONAS))
                    action, amount = poker_ai.decide(game.bot_view(i), table["level"], persona, ai_rng)
                game.act(i, action, amount)
                stats["actions"] += 1
            check_invariants(game)
        assert game.paid and game.pot == 0 and game.result, "банк не выплачен"
        assert sum(game.result["net"]) == 0 or game.rebuys_total >= 0
        check_invariants(game)
        stats["hands"] += 1
        stats["showdowns"] += int(game.result["showdown"])
        stats["side_pots"] += int(len(game.result["pots"]) > 1)
        stats["allin_hands"] += int(any(s.all_in for s in game.seats))
    return dict(stats)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    poker_ai.ITERS_SCALE = 0.1
    total = Counter()
    for t in TABLES:
        res = run_simulation(n, t["id"], seed=42)
        print(t["id"].ljust(8), res)
        total.update(res)
    print("ИТОГО:", dict(total))
