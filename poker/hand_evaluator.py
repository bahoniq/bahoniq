"""Оценка покерных комбинаций Texas Hold'em: лучшая пятёрка из 5–7 карт.

Карта — строка из двух символов: ранг (23456789TJQKA) и масть (s, h, d, c), например "Ah", "Td".
Оценка — кортеж, который можно сравнивать напрямую: (категория, *кикеры).
"""
from __future__ import annotations

from collections import Counter

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
FULL_DECK = [r + s for r in RANKS for s in SUITS]

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)

_NOM = {2: "двойка", 3: "тройка", 4: "четвёрка", 5: "пятёрка", 6: "шестёрка", 7: "семёрка",
        8: "восьмёрка", 9: "девятка", 10: "десятка", 11: "валет", 12: "дама", 13: "король", 14: "туз"}
_GEN = {2: "двойки", 3: "тройки", 4: "четвёрки", 5: "пятёрки", 6: "шестёрки", 7: "семёрки",
        8: "восьмёрки", 9: "девятки", 10: "десятки", 11: "валета", 12: "дамы", 13: "короля", 14: "туза"}
_PLU = {2: "двоек", 3: "троек", 4: "четвёрок", 5: "пятёрок", 6: "шестёрок", 7: "семёрок",
        8: "восьмёрок", 9: "девяток", 10: "десяток", 11: "валетов", 12: "дам", 13: "королей", 14: "тузов"}


def _straight_high(rank_set) -> int:
    """Старшая карта стрита (5 для «колеса» A-2-3-4-5) или 0, если стрита нет."""
    rs = set(rank_set)
    if 14 in rs:
        rs.add(1)
    for high in range(14, 4, -1):
        if all((high - k) in rs for k in range(5)):
            return high
    return 0


def evaluate(cards) -> tuple:
    """Лучшая пятикарточная комбинация из 5–7 карт."""
    ranks = [RANK_VALUE[c[0]] for c in cards]
    suit_count = Counter(c[1] for c in cards)

    flush_ranks = None
    for suit, n in suit_count.items():
        if n >= 5:
            flush_ranks = sorted((RANK_VALUE[c[0]] for c in cards if c[1] == suit), reverse=True)
            sf = _straight_high(flush_ranks)
            if sf:
                return (STRAIGHT_FLUSH, sf)

    rc = Counter(ranks)
    quads = sorted((r for r, n in rc.items() if n == 4), reverse=True)
    trips = sorted((r for r, n in rc.items() if n == 3), reverse=True)
    pairs = sorted((r for r, n in rc.items() if n == 2), reverse=True)

    if quads:
        q = quads[0]
        return (QUADS, q, max(r for r in ranks if r != q))
    if trips and (len(trips) > 1 or pairs):
        return (FULL_HOUSE, trips[0], max(trips[1:] + pairs))
    if flush_ranks:
        return (FLUSH, *flush_ranks[:5])
    st = _straight_high(ranks)
    if st:
        return (STRAIGHT, st)
    if trips:
        t = trips[0]
        kick = sorted((r for r in ranks if r != t), reverse=True)[:2]
        return (TRIPS, t, *kick)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return (TWO_PAIR, p1, p2, max(r for r in ranks if r != p1 and r != p2))
    if pairs:
        p = pairs[0]
        kick = sorted((r for r in ranks if r != p), reverse=True)[:3]
        return (PAIR, p, *kick)
    return (HIGH_CARD, *sorted(ranks, reverse=True)[:5])


def describe(score: tuple) -> str:
    """Название комбинации по-русски."""
    cat = score[0]
    if cat == HIGH_CARD:
        return f"Старшая карта: {_NOM[score[1]]}"
    if cat == PAIR:
        return f"Пара {_PLU[score[1]]}"
    if cat == TWO_PAIR:
        return f"Две пары: {_PLU[score[1]]} и {_PLU[score[2]]}"
    if cat == TRIPS:
        return f"Тройка {_PLU[score[1]]}"
    if cat == STRAIGHT:
        return f"Стрит до {_GEN[score[1]]}"
    if cat == FLUSH:
        return f"Флеш до {_GEN[score[1]]}"
    if cat == FULL_HOUSE:
        return f"Фулл-хаус: {_PLU[score[1]]} и {_PLU[score[2]]}"
    if cat == QUADS:
        return f"Каре {_PLU[score[1]]}"
    if score[1] == 14:
        return "Роял-флеш"
    return f"Стрит-флеш до {_GEN[score[1]]}"


def describe_hole_board(hole, board) -> str:
    """Подпись текущей комбинации игрока (для информационной панели)."""
    if len(hole) < 2:
        return ""
    if len(board) < 3:
        a, b = (RANK_VALUE[hole[0][0]], RANK_VALUE[hole[1][0]])
        if a == b:
            return f"Карманная пара {_PLU[a]}"
        return f"Старшая карта: {_NOM[max(a, b)]}"
    return describe(evaluate(list(hole) + list(board)))


def detect_draws(hole, board) -> list[str]:
    """Дро на флопе/тёрне. Используется как необязательная подсказка и ботами высокого уровня."""
    if len(board) not in (3, 4) or len(hole) < 2:
        return []
    cards = list(hole) + list(board)
    out = []
    suits = Counter(c[1] for c in cards)
    for s, n in suits.items():
        if n == 4 and any(h[1] == s for h in hole):
            out.append("Флеш-дро")
            break
    ranks = {RANK_VALUE[c[0]] for c in cards}
    if not _straight_high(ranks):
        outs = {r for r in range(2, 15) if r not in ranks and _straight_high(ranks | {r})}
        if len(outs) >= 2:
            out.append("Стрит-дро (с двух сторон)")
        elif len(outs) == 1:
            out.append("Стрит-дро (гатшот)")
    return out
