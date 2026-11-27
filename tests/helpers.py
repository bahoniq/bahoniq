import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random

from poker.hand_evaluator import FULL_DECK
from poker.poker_engine import PokerGame, Seat

TABLE = dict(id="t", name="TEST", sb=10, bb=20, min_buyin=100, max_buyin=100000, level=2, level_name="x")
SMALL = dict(id="s", name="SMALL", sb=5, bb=10, min_buyin=100, max_buyin=100000, level=2, level_name="x")


def make_game(stacks, dealer=8, table=TABLE, seed=1):
    if len(stacks) == 6:
        stacks = list(stacks) + [0, 0, 0]
    seats = [Seat(i, "Вы" if i == 0 else f"Bot{i}", i == 0, st, persona="" if i == 0 else "analyst")
             for i, st in enumerate(stacks)]
    # Для 6-местных тестов даём стеки всем 9 местам, если передано ровно 6
    if len(seats) == 9 and all(s.stack == 0 for s in seats[6:]):
        for s in seats[6:]:
            s.stack = stacks[0]
    return PokerGame(table, seats, rng=random.Random(seed), dealer=dealer)


def deck_from(holes, board, first=0):
    """Колода под сценарий. holes: {место: (карта, карта)}, board: 5 карт. first — место, которому сдают первым."""
    deck = [None] * 18
    for seat, (a, b) in holes.items():
        k = (seat - first) % 9
        deck[k], deck[9 + k] = a, b
    used = {c for pair in holes.values() for c in pair} | set(board)
    filler = [c for c in FULL_DECK if c not in used]
    for i in range(18):
        if deck[i] is None:
            deck[i] = filler.pop()
    full = deck + [filler.pop()] + board[0:3] + [filler.pop()] + [board[3]] + [filler.pop()] + [board[4]] + filler
    assert len(full) == 52 and len(set(full)) == 52
    return full


def run_out(g):
    guard = 0
    while g.phase != "complete":
        guard += 1
        assert guard < 10
        g.step_auto()
