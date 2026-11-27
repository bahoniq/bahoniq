"""Боты Poker Club.

Бот принимает решение ТОЛЬКО по «виду бота» (view): собственные карты, общие карты, публичные
действия и стеки. Чужих закрытых карт и порядка колоды здесь нет и быть не может — модуль
намеренно не импортирует движок. Сложность растёт только за счёт качества решений.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from .hand_evaluator import FULL_DECK, RANK_VALUE, detect_draws, evaluate

ITERS_SCALE = 1.0  # тесты уменьшают, чтобы симуляции шли быстро

LEVELS = {
    1: dict(level=1, iters=30, noise=0.10, mistake=0.12, bluff=0.35, position=False, texture=False,
            semi=False, adapt=0, sizes=(0.5, 1.0)),
    2: dict(level=2, iters=70, noise=0.065, mistake=0.06, bluff=0.8, position=True, texture=False,
            semi=False, adapt=0, sizes=(0.4, 0.6, 0.9)),
    3: dict(level=3, iters=130, noise=0.04, mistake=0.03, bluff=1.0, position=True, texture=True,
            semi=True, adapt=0, sizes=(0.33, 0.5, 0.75, 1.0)),
    4: dict(level=4, iters=220, noise=0.025, mistake=0.012, bluff=1.1, position=True, texture=True,
            semi=True, adapt=1, sizes=(0.25, 0.4, 0.6, 0.85, 1.2)),
    5: dict(level=5, iters=340, noise=0.015, mistake=0.005, bluff=1.15, position=True, texture=True,
            semi=True, adapt=2, sizes=(0.25, 0.33, 0.5, 0.67, 0.9, 1.25)),
}

PERSONAS = {
    "rock":     dict(tight=0.80, aggr=0.35, bluff=0.30),
    "shark":    dict(tight=0.28, aggr=1.05, bluff=1.15),
    "analyst":  dict(tight=0.52, aggr=0.60, bluff=0.65),
    "bluffer":  dict(tight=0.25, aggr=0.95, bluff=2.20),
    "wildcard": dict(tight=0.22, aggr=1.10, bluff=1.60),
}

BASE_OPEN = {"UTG": 8.5, "HJ": 7.5, "CO": 6.5, "BTN": 5.0, "SB": 6.5, "BB": 99.0}


# ---------------------------------------------------------------- оценка руки
def chen_score(hole) -> int:
    r1, r2 = sorted((RANK_VALUE[hole[0][0]], RANK_VALUE[hole[1][0]]), reverse=True)

    def pts(r):
        return {14: 10, 13: 8, 12: 7, 11: 6}.get(r, r / 2)

    score = pts(r1)
    if r1 == r2:
        score = max(5, score * 2)
    else:
        if hole[0][1] == hole[1][1]:
            score += 2
        gap = r1 - r2 - 1
        score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
        if gap <= 1 and r1 < 12:
            score += 1
    return math.ceil(score)


def estimate_equity(hole, board, n_opp: int, iters: int, rng) -> float:
    """Monte-Carlo против n_opp случайных рук. Использует только известные боту карты."""
    if n_opp <= 0:
        return 1.0
    known = set(hole) | set(board)
    deck = [c for c in FULL_DECK if c not in known]
    need = 5 - len(board)
    total = 0.0
    for _ in range(iters):
        draw = rng.sample(deck, need + 2 * n_opp)
        full = board + draw[:need]
        mine = evaluate(hole + full)
        best = max(evaluate(draw[need + 2 * k: need + 2 * k + 2] + full) for k in range(n_opp))
        if mine > best:
            total += 1
        elif mine == best:
            total += 0.5
    return total / iters


def board_wetness(board) -> float:
    if len(board) < 3:
        return 0.0
    suits = Counter(c[1] for c in board)
    ranks = sorted({RANK_VALUE[c[0]] for c in board})
    best = max(sum(1 for r in ranks if lo <= r <= lo + 4) for lo in range(2, 11))
    w = 0.4 * (max(suits.values()) >= 3) + 0.15 * (max(suits.values()) == 2)
    w += 0.25 * (best >= 3) + 0.2 * (best >= 4)
    return min(1.0, w)


# ---------------------------------------------------------------- профиль человека (публичные наблюдения)
def _human_profile(view) -> dict:
    """Публичные наблюдения за соперниками, которые ещё в раздаче (приоритет — живой игрок, место 0)."""
    obs = view.get("obs") or []
    active = [p["seat"] for p in view["players"] if not p["folded"]]
    picks = [0] if (view["seat"] != 0 and 0 in active) else active
    folds, aggs, vpips, faced_total = [], [], [], 0
    for s in picks:
        if s >= len(obs):
            continue
        o = obs[s]
        hands = max(1, o["hands"])
        post = o["bets"] + o["calls"]
        folds.append(o["folds_to_bet"] / o["faced"] if o["faced"] >= 6 else 0.4)
        aggs.append(o["bets"] / post if post >= 8 else 0.4)
        vpips.append(o["vpip"] / hands if hands >= 8 else 0.3)
        faced_total += o["faced"]
    if not folds:
        return {"n": 0, "fold": 0.4, "agg": 0.4, "vpip": 0.3}
    k = len(folds)
    return {"n": faced_total, "fold": sum(folds) / k, "agg": sum(aggs) / k, "vpip": sum(vpips) / k}


# ---------------------------------------------------------------- вспомогательные решения
def _round_to(view, x: float) -> int:
    unit = max(1, view["sb"])
    return int(round(x / unit) * unit)


def _bet_or_raise(view, target: float):
    legal = view["legal"]
    key = "raise" if "raise" in legal else "bet" if "bet" in legal else None
    if key is None:
        return ("allin", None) if "allin" in legal else None
    lo, hi = legal[key]
    amt = max(lo, min(hi, _round_to(view, target)))
    if amt >= hi * 0.6 and "allin" in legal:
        return ("allin", None)
    return (key, amt)


def _size_fraction(lv, rng, strength: str) -> float:
    sizes = lv["sizes"]
    if strength == "big":
        pool = [s for s in sizes if s >= 0.6] or list(sizes)
    elif strength == "small":
        pool = [s for s in sizes if s <= 0.6] or list(sizes)
    else:
        pool = list(sizes)
    return rng.choice(pool)


def _sloppy(view, rng):
    legal = view["legal"]
    if "check" in legal:
        return ("check", None)
    if "call" in legal and rng.random() < 0.7:
        return ("call", None)
    return ("fold", None) if "fold" in legal else None


# ---------------------------------------------------------------- префлоп
def _preflop(view, lv, ps, rng):
    legal = view["legal"]
    bb, pos, stack = view["bb"], view["position"], view["stack"]
    eff_bb = (stack + view["bet"]) / bb
    mood = view["mood"]
    c = chen_score(view["hole"]) + rng.gauss(0, lv["noise"] * 18) + (mood - 1.0) * 3.0
    tight_adj = (ps["tight"] - 0.5) * 4.0
    raises, to_call = view["preflop_raises"], view["to_call"]

    if lv["adapt"] >= 1:
        prof = _human_profile(view)
        if prof["agg"] > 0.6:
            c += 0.8   # игрок давит — защищаемся шире
        if prof["vpip"] < 0.18 and raises:
            c -= 1.2   # узкий игрок, уважаем его рейзы

    if rng.random() < lv["mistake"]:
        return _sloppy(view, rng)

    if eff_bb <= 12 and "allin" in legal:
        thr = 8.5 - (12 - eff_bb) * 0.5 + tight_adj * 0.5
        if c >= thr:
            return ("allin", None)
        if "check" in legal:
            return ("check", None)
        return ("fold", None)

    if raises == 0:
        open_th = (BASE_OPEN[pos] if lv["position"] else 7.5) + tight_adj
        if to_call == 0:  # опция большого блайнда
            if c >= 10.5 - (ps["aggr"] - 0.5) * 2 and "raise" in legal:
                return _bet_or_raise(view, bb * 3.5)
            return ("check", None)
        steal = (lv["position"] and pos in ("BTN", "CO", "SB")
                 and rng.random() < 0.10 * ps["bluff"] * lv["bluff"])
        if c >= open_th or steal:
            size = bb * rng.choice((2.5, 3.0, 3.0, 3.5)) + view["limpers"] * bb
            res = _bet_or_raise(view, size)
            if res:
                return res
        if lv["level"] == 1 and c >= open_th - 2.5 and "call" in legal and to_call <= bb:
            return ("call", None)
        return ("fold", None)

    if raises == 1:
        ratio = view["current_bet"] / bb
        req = 8.0 + 0.9 * max(0.0, ratio - 2.5) + tight_adj
        if pos == "BB" and lv["position"]:
            req -= 1.0
        three_bet = 11.5 + tight_adj * 0.5 - (ps["aggr"] - 0.5) * 2.5
        bluff3 = (lv["position"] and pos in ("BTN", "SB", "BB", "CO") and 4.5 <= c < req
                  and rng.random() < 0.06 * ps["bluff"] * lv["bluff"])
        if (c >= three_bet or bluff3) and "raise" in legal:
            mult = 3.0 if pos in ("BTN", "CO") else 3.6
            res = _bet_or_raise(view, view["current_bet"] * mult)
            if res:
                return res
        if c >= req and "call" in legal and (to_call <= stack * 0.18 or c >= req + 2.5):
            return ("call", None)
        return ("fold", None)

    # 3-бет и выше
    if c >= 15.5:
        res = _bet_or_raise(view, view["current_bet"] * 2.4)
        if res:
            return res
    if c >= 13 and "call" in legal:
        return ("call", None)
    if eff_bb <= 25 and c >= 11 and "allin" in legal:
        return ("allin", None)
    return ("fold", None)


# ---------------------------------------------------------------- постфлоп
def _postflop(view, lv, ps, rng):
    legal = view["legal"]
    pot, to_call, street = view["pot"], view["to_call"], view["street"]
    n_opp = max(1, view["n_active"] - 1)
    iters = max(10, int(lv["iters"] * ITERS_SCALE))
    e = estimate_equity(view["hole"], view["board"], n_opp, iters, rng)
    e += rng.gauss(0, lv["noise"])
    mood = view["mood"]
    aggr = ps["aggr"] * mood
    wet = board_wetness(view["board"]) if lv["texture"] else 0.3

    e_adj = e
    if to_call > 0:  # диапазон ставящего сильнее случайной руки
        size = min(2.0, to_call / max(1, pot - to_call))
        disc = (0.03 + 0.025 * view["raises_this_street"]) * (0.5 if lv["level"] == 1 else 1.0) * (0.5 + size)
        e_adj = e - disc

    prof = _human_profile(view) if lv["adapt"] >= 1 else None
    draw = lv["semi"] and street in ("flop", "turn") and 0.25 < e < 0.58 and bool(
        detect_draws(view["hole"], view["board"]))

    # частота блефа и смелой игры
    bp = 0.16 * ps["bluff"] * lv["bluff"]
    if street == "river":
        bp *= 0.8
    if n_opp >= 3:
        bp *= 0.3
    if lv["position"] and view["in_position"]:
        bp *= 1.25
    if street == "flop" and to_call == 0 and view["was_preflop_aggressor"] and n_opp <= 2:
        bp = max(bp, 0.40 * lv["bluff"] * (0.6 + 0.5 * ps["aggr"]))
    if prof:
        if prof["fold"] > 0.5:
            bp *= 1 + (prof["fold"] - 0.5) * 3
        elif prof["fold"] < 0.28:
            bp *= 0.4

    if rng.random() < lv["mistake"]:
        return _sloppy(view, rng)

    value_th = 0.60 + (ps["tight"] - 0.5) * 0.12 - (aggr - 0.6) * 0.08
    value_th += 0.03 * wet if e_adj < 0.75 else 0

    # ---- никто не ставил
    if to_call == 0:
        if "bet" not in legal:
            return ("check", None)
        if (lv["adapt"] >= 2 and e_adj > 0.92 and street in ("flop", "turn") and wet < 0.4
                and rng.random() < 0.30):
            return ("check", None)  # слоуплей
        if e_adj >= value_th:
            strength = "big" if e_adj >= 0.80 or wet > 0.6 else "small" if e_adj < 0.68 else "mid"
            res = _bet_or_raise(view, _size_fraction(lv, rng, strength) * pot)
            if res:
                return res
        if draw and rng.random() < 0.45 * aggr:
            res = _bet_or_raise(view, _size_fraction(lv, rng, "small") * pot)
            if res:
                return res
        if e_adj >= 0.50 and lv["adapt"] >= 2 and prof and prof["agg"] < 0.35 and rng.random() < 0.35:
            res = _bet_or_raise(view, 0.33 * pot)  # тонкий вэлью против пассивного
            if res:
                return res
        if rng.random() < bp:
            res = _bet_or_raise(view, _size_fraction(lv, rng, "mid") * pot)
            if res:
                return res
        return ("check", None)

    # ---- нужно отвечать на ставку
    pot_odds = to_call / (pot + to_call)
    margin = 0.02 + (ps["tight"] - 0.5) * 0.09 + (0.02 if street == "river" else 0) - max(0.0, aggr - 0.8) * 0.05
    if lv["level"] == 1:
        pot_odds *= rng.uniform(0.7, 1.3)  # плохо считает размер банка
    req = pot_odds + margin
    callish = False
    if prof:
        if prof["agg"] > 0.6:
            req -= 0.04
            callish = True
        elif prof["agg"] < 0.3 and view["raises_this_street"]:
            req += 0.05

    if "raise" in legal or "allin" in legal:
        if e_adj >= 0.78 and rng.random() < 0.35 + 0.5 * aggr:
            res = _bet_or_raise(view, view["current_bet"] + max(
                view["min_raise"], _size_fraction(lv, rng, "big") * (pot + to_call)))
            if res and res[0] != "allin" or (res and e_adj > 0.9):
                return res
        if draw and to_call < 0.5 * pot and rng.random() < 0.18 * aggr and "raise" in legal:
            return _bet_or_raise(view, view["current_bet"] + max(
                view["min_raise"], 0.7 * (pot + to_call)))
        if (lv["adapt"] >= 2 and street != "river" and "raise" in legal
                and rng.random() < bp * 0.25):
            return _bet_or_raise(view, view["current_bet"] + max(
                view["min_raise"], 0.75 * (pot + to_call)))

    if e_adj >= req and "call" in legal:
        return ("call", None)
    if callish and e_adj >= req - 0.06 and "call" in legal:
        return ("call", None)
    return ("fold", None) if "fold" in legal else ("check", None)


# ---------------------------------------------------------------- публичный интерфейс
def _sanitize(choice, view):
    legal = view["legal"]
    if choice:
        action, amt = choice
        if action == "fold" and "fold" in legal:
            return ("fold", None)
        if action == "check" and "check" in legal:
            return ("check", None)
        if action == "call" and "call" in legal:
            return ("call", None)
        if action in ("bet", "raise") and action in legal:
            lo, hi = legal[action]
            return (action, int(max(lo, min(hi, amt if amt else lo))))
        if action == "allin" and "allin" in legal:
            return ("allin", None)
    if "check" in legal:
        return ("check", None)
    if "fold" in legal:
        return ("fold", None)
    if "call" in legal:
        return ("call", None)
    return ("allin", None) if "allin" in legal else ("check", None)


def decide(view: dict, level: int, persona: str, rng=None) -> tuple:
    """Возвращает (действие, сумма). Сумма — «ставка до» для bet/raise, иначе None."""
    rng = rng or random.Random()
    lv = LEVELS[max(1, min(5, int(level)))]
    ps = PERSONAS.get(persona, PERSONAS["analyst"])
    try:
        if view["street"] == "preflop":
            choice = _preflop(view, lv, ps, rng)
        else:
            choice = _postflop(view, lv, ps, rng)
    except Exception:
        choice = None
    return _sanitize(choice, view)
