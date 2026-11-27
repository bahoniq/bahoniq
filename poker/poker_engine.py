"""Движок No-Limit Texas Hold'em на 6 мест: один человек (место 0) и пять ботов.

Движок — единственный источник истины по игре: ставки, очередность, улицы, банки, выплаты.
Колода создаётся и перемешивается один раз за раздачу и дальше используется последовательно.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import asdict, dataclass, field

from .hand_evaluator import FULL_DECK, describe, evaluate

STREETS = ("preflop", "flop", "turn", "river")
POSITIONS_5 = ("BTN", "SB", "BB", "UTG", "CO")
POSITIONS_6 = ("BTN", "SB", "BB", "UTG", "HJ", "CO")
POSITIONS_9 = ("BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO")
NUM_SEATS = 9
HUMAN_SEAT = 0


class IllegalAction(Exception):
    """Недопустимое действие участника."""


def money(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


@dataclass
class Seat:
    index: int
    name: str
    is_human: bool
    stack: int
    persona: str = ""
    hole: list = field(default_factory=list)
    bet: int = 0            # ставка на текущей улице
    total: int = 0          # вложено за раздачу
    folded: bool = False
    all_in: bool = False
    acted: bool = False
    raise_closed: bool = False
    revealed: bool = False
    last_action: str = ""


def _new_obs() -> dict:
    return {"hands": 0, "vpip": 0, "pfr": 0, "bets": 0, "calls": 0, "faced": 0, "folds_to_bet": 0}


def coerce_amount(amount) -> int:
    """Защита от NaN, отрицательных, дробных и нечисловых сумм."""
    if amount is None or isinstance(amount, bool):
        raise IllegalAction("Не указана сумма")
    if isinstance(amount, str):
        try:
            amount = float(amount.replace(" ", ""))
        except ValueError:
            raise IllegalAction("Некорректная сумма")
    if not isinstance(amount, (int, float)):
        raise IllegalAction("Некорректная сумма")
    if not math.isfinite(amount) or int(amount) != amount:
        raise IllegalAction("Сумма должна быть целым числом")
    amount = int(amount)
    if amount <= 0:
        raise IllegalAction("Сумма должна быть положительной")
    return amount


_STATE_FIELDS = (
    "table", "sb", "bb", "dealer", "hand_no", "phase", "board", "deck", "current_bet", "min_raise", "to_act",
    "auto_runout", "paid", "stats_applied", "result", "log", "hand_actions", "seq", "rebuys_total",
    "initial_total", "leave_requested", "obs", "moods", "start_stacks", "vpip_seen",
    "mode", "tournament_buyin", "eliminated_order", "prize_paid",
)


class PokerGame:
    def __init__(self, table: dict, seats: list, rng=None, dealer: int | None = None,
                 mode: str = "cash", tournament_buyin: int = 0):
        self.table = dict(table)
        self.sb = int(table["sb"])
        self.bb = int(table["bb"])
        self.seats = seats
        self.n_seats = len(seats)
        self.rng = rng or random.SystemRandom()
        self.dealer = dealer if dealer is not None else self.rng.randrange(self.n_seats)
        self.hand_no = 0
        self.phase = "idle"          # idle | preflop | flop | turn | river | complete
        self.board: list = []
        self.deck: list = []
        self.current_bet = 0
        self.min_raise = self.bb
        self.to_act: int | None = None
        self.auto_runout = False
        self.paid = False
        self.stats_applied = False
        self.result: dict | None = None
        self.log: list = []
        self.hand_actions: list = []
        self.seq = 0
        self.rebuys_total = 0
        self.initial_total = sum(s.stack for s in seats)
        self.leave_requested = False
        self.obs = [_new_obs() for _ in seats]
        self.moods = [1.0] * len(seats)
        self.start_stacks = [s.stack for s in seats]
        self.vpip_seen: list = []
        self.mode = mode if mode in ("cash", "tournament") else "cash"
        self.tournament_buyin = int(tournament_buyin)
        self.eliminated_order: list = []
        self.prize_paid = False

    # ------------------------------------------------------------------ сериализация
    def to_dict(self) -> dict:
        d = {k: copy.deepcopy(getattr(self, k)) for k in _STATE_FIELDS}
        d["seats"] = [asdict(s) for s in self.seats]
        return d

    @classmethod
    def from_dict(cls, d: dict, rng=None) -> "PokerGame":
        seats = [Seat(**s) for s in d["seats"]]
        g = cls(d["table"], seats, rng=rng, dealer=d["dealer"])
        for k in _STATE_FIELDS:
            if k in d:
                setattr(g, k, copy.deepcopy(d[k]))
        return g

    # ------------------------------------------------------------------ вспомогательное
    @property
    def pot(self) -> int:
        return 0 if self.paid else sum(s.total for s in self.seats)

    def total_chips(self) -> int:
        """Сумма всех стеков и банка. Должна равняться initial_total + rebuys_total."""
        return sum(s.stack for s in self.seats) + self.pot

    def expected_chips(self) -> int:
        return self.initial_total + self.rebuys_total

    def _alive(self) -> list:
        return [s for s in self.seats if not s.folded]

    def _next_with_chips(self, start: int) -> int:
        for k in range(1, self.n_seats + 1):
            idx = (start + k) % self.n_seats
            if self.seats[idx].stack > 0:
                return idx
        return start

    def position_of(self, i: int) -> str:
        pos_list = POSITIONS_5 if self.n_seats == 5 else POSITIONS_6 if self.n_seats == 6 else POSITIONS_9
        return pos_list[(i - self.dealer) % self.n_seats]

    def _log(self, text: str, seat: int | None = None) -> None:
        self.log.append({"text": text, "seat": seat})
        if len(self.log) > 80:
            del self.log[:-80]

    def _bot_stack(self) -> int:
        lo, hi = self.table["min_buyin"], self.table["max_buyin"]
        raw = self.rng.uniform(0.55, 1.0) * hi
        v = int(round(raw / self.bb)) * self.bb
        return max(lo, min(hi, v))

    def _put(self, seat: Seat, amount: int) -> int:
        add = max(0, min(int(amount), seat.stack))
        seat.stack -= add
        seat.bet += add
        seat.total += add
        if seat.stack == 0:
            seat.all_in = True
        return add

    # ------------------------------------------------------------------ старт раздачи
    def start_hand(self, deck: list | None = None) -> None:
        if self.phase in STREETS:
            raise IllegalAction("Раздача уже идёт")
        if self.seats[HUMAN_SEAT].stack <= 0:
            raise IllegalAction("У вас закончились фишки")

        if self.mode == "tournament":
            if sum(1 for s in self.seats if s.stack > 0) < 2:
                raise IllegalAction("Турнир уже завершён")
            mults = (1, 2, 3, 5, 8, 12, 20, 30)
            lvl = min(len(mults) - 1, self.hand_no // 6)
            new_sb = int(self.table["sb"]) * mults[lvl]
            new_bb = int(self.table["bb"]) * mults[lvl]
            if new_bb > self.bb:
                self.sb, self.bb = new_sb, new_bb
                self._log(f"Блайнды выросли: {money(self.sb)} / {money(self.bb)}")
        else:
            for s in self.seats:
                if not s.is_human and s.stack < self.bb:
                    new_stack = self._bot_stack()
                    self.rebuys_total += new_stack - s.stack
                    s.stack = new_stack
                    self._log(f"{s.name} докупает фишки", s.index)

        self.hand_no += 1
        if self.hand_no > 1:
            self.dealer = self._next_with_chips(self.dealer) if self.mode == "tournament" else (self.dealer + 1) % self.n_seats
        self.board = []
        self.result = None
        self.paid = False
        self.stats_applied = False
        self.auto_runout = False
        self.current_bet = 0
        self.min_raise = self.bb
        self.to_act = None
        self.hand_actions = []
        self.vpip_seen = []
        for s in self.seats:
            s.hole = []
            s.bet = s.total = 0
            out = self.mode == "tournament" and s.stack <= 0
            s.folded = out
            s.all_in = False
            s.acted = out
            s.raise_closed = out
            s.revealed = False
            s.last_action = "Выбыл" if out else ""
        self.start_stacks = [s.stack for s in self.seats]
        for i, s in enumerate(self.seats):
            if self.mode == "tournament" and s.stack <= 0:
                continue
            self.obs[i]["hands"] += 1
            vol = {"wildcard": 0.6, "bluffer": 0.15}.get(s.persona, 0.0)
            self.moods[i] = 1.0 + self.rng.uniform(-vol, vol) if vol else 1.0

        if deck is None:
            d = list(FULL_DECK)
            self.rng.shuffle(d)
            self.deck = d
        else:
            if len(deck) != 52 or len(set(deck)) != 52:
                raise IllegalAction("Некорректная колода")
            self.deck = list(reversed(deck))

        first = (self.dealer + 1) % self.n_seats
        for _ in range(2):
            for k in range(self.n_seats):
                seat = self.seats[(first + k) % self.n_seats]
                if self.mode == "tournament" and seat.stack <= 0:
                    continue
                seat.hole.append(self.deck.pop())

        self.phase = "preflop"
        if self.mode == "tournament":
            active_cnt = sum(1 for s in self.seats if s.stack > 0)
            sb_i = self.dealer if active_cnt == 2 else self._next_with_chips(self.dealer)
            bb_i = self._next_with_chips(sb_i)
        else:
            sb_i, bb_i = (self.dealer + 1) % self.n_seats, (self.dealer + 2) % self.n_seats
        self._log(f"Раздача №{self.hand_no}. Дилер — {self.seats[self.dealer].name}")
        for idx, amt, label in ((sb_i, self.sb, "Малый блайнд"), (bb_i, self.bb, "Большой блайнд")):
            s = self.seats[idx]
            add = self._put(s, amt)
            s.last_action = f"{label} {money(add)}"
            self.current_bet = max(self.current_bet, s.bet)
        self.seq += 1
        if self._round_complete():
            self._finish_round()
        else:
            self.to_act = self._next_to_act(bb_i)

    # ------------------------------------------------------------------ допустимые действия
    def legal_actions(self, i: int) -> dict:
        """fold/check: True; call/allin: сумма фишек; bet/raise: (мин, макс) ставка «до»."""
        if self.phase not in STREETS or self.to_act != i:
            return {}
        p = self.seats[i]
        if p.folded or p.all_in or p.stack <= 0:
            return {}
        to_call = max(0, self.current_bet - p.bet)
        legal: dict = {"fold": True}
        if to_call > 0:
            legal["call"] = min(to_call, p.stack)
        else:
            legal["check"] = True
        max_to = p.bet + p.stack
        if self.current_bet == 0:
            legal["bet"] = (min(self.bb, p.stack), p.stack)
        elif not p.raise_closed and p.stack > to_call:
            min_to = self.current_bet + self.min_raise
            if max_to >= min_to:
                legal["raise"] = (min_to, max_to)
        if to_call >= p.stack or self.current_bet == 0 or not p.raise_closed:
            legal["allin"] = p.stack
        return legal

    # ------------------------------------------------------------------ действие
    def act(self, i: int, action: str, amount=None) -> None:
        if self.phase not in STREETS:
            raise IllegalAction("Сейчас нет активной раздачи")
        if self.to_act != i:
            raise IllegalAction("Сейчас не ваш ход")
        p = self.seats[i]
        legal = self.legal_actions(i)
        if action not in legal:
            raise IllegalAction("Это действие сейчас недоступно")

        prev_level = self.current_bet
        street = self.phase
        facing = prev_level - p.bet > 0
        aggressive = False

        if action == "fold":
            p.folded = True
            p.last_action = "Сброс"
            text = "сбрасывает"
        elif action == "check":
            p.last_action = "Чек"
            text = "чек"
        elif action == "call":
            add = self._put(p, legal["call"])
            p.last_action = f"Уравнял {money(add)}" + (" (ва-банк)" if p.all_in else "")
            text = f"уравнивает {money(add)}"
        elif action in ("bet", "raise"):
            target = coerce_amount(amount)
            lo, hi = legal[action]
            if not lo <= target <= hi:
                raise IllegalAction(f"Допустимая сумма: от {money(lo)} до {money(hi)}")
            self._put(p, target - p.bet)
            aggressive = self._raise_to(p, target, prev_level)
            verb = "Ставка" if action == "bet" else "Рейз до"
            p.last_action = f"{verb} {money(target)}" + (" (ва-банк)" if p.all_in else "")
            text = (f"ставка {money(target)}" if action == "bet" else f"повышает до {money(target)}")
        else:  # allin
            target = p.bet + p.stack
            self._put(p, p.stack)
            if target > prev_level:
                aggressive = self._raise_to(p, target, prev_level)
                p.last_action = f"Ва-банк {money(target)}"
                text = f"ва-банк {money(target)}"
            else:
                p.last_action = f"Уравнял {money(p.bet)} (ва-банк)"
                text = f"уравнивает ва-банк {money(p.bet)}"
        p.acted = True
        self._record(i, action, street, facing, aggressive)
        self._log(f"{p.name}: {text}", i)
        self.seq += 1
        self._post_action(i)

    def _raise_to(self, p: Seat, new_to: int, prev_level: int) -> bool:
        """Применяет повышение. Возвращает True, если действие агрессивное (повышение)."""
        if new_to <= self.current_bet:
            return False
        inc = new_to - prev_level
        self.current_bet = new_to
        if inc >= self.min_raise:
            self.min_raise = inc
            for q in self.seats:
                if q is not p and not q.folded and not q.all_in:
                    q.acted = False
                    q.raise_closed = False
        else:  # неполный all-in: не открывает торги для уже походивших
            for q in self.seats:
                if q is not p and not q.folded and not q.all_in and q.acted:
                    q.raise_closed = True
        return True

    def _record(self, i: int, action: str, street: str, facing: bool, aggressive: bool) -> None:
        self.hand_actions.append({"seat": i, "action": action, "street": street, "aggr": aggressive})
        o = self.obs[i]
        if street == "preflop":
            if action in ("call", "bet", "raise", "allin") and i not in self.vpip_seen:
                self.vpip_seen.append(i)
                o["vpip"] += 1
            if aggressive:
                o["pfr"] += 1
        else:
            if aggressive:
                o["bets"] += 1
            elif action == "call":
                o["calls"] += 1
        if facing:
            o["faced"] += 1
            if action == "fold":
                o["folds_to_bet"] += 1

    # ------------------------------------------------------------------ ход раздачи
    def _needs_action(self, p: Seat) -> bool:
        return not p.folded and not p.all_in and (not p.acted or p.bet < self.current_bet)

    def _round_complete(self) -> bool:
        actors = [p for p in self._alive() if not p.all_in]
        if len(actors) <= 1 and all(p.bet >= self.current_bet for p in actors):
            return True
        return not any(self._needs_action(p) for p in actors)

    def _next_to_act(self, start: int) -> int | None:
        for k in range(1, self.n_seats + 1):
            idx = (start + k) % self.n_seats
            if self._needs_action(self.seats[idx]):
                return idx
        return None

    def _post_action(self, last: int) -> None:
        alive = self._alive()
        if len(alive) == 1:
            self._award_uncontested(alive[0])
            return
        if self._round_complete():
            self._finish_round()
            return
        nxt = self._next_to_act(last)
        if nxt is None:
            self._finish_round()
        else:
            self.to_act = nxt

    def _reset_street(self) -> None:
        for p in self.seats:
            p.bet = 0
            p.acted = False
            p.raise_closed = False
            if not p.folded and not p.all_in:
                p.last_action = ""
        self.current_bet = 0
        self.min_raise = self.bb

    def _finish_round(self) -> None:
        alive = self._alive()
        if self.phase == "river":
            self._showdown()
            return
        can_bet = [p for p in alive if not p.all_in]
        if len(can_bet) <= 1:
            self.auto_runout = True
            self.to_act = None
            self._reset_street()
            for p in alive:
                p.revealed = True
            self._log("Ва-банк: карты открыты")
            return
        self._deal_next_street()

    def _deal_next_street(self) -> None:
        idx = STREETS.index(self.phase) + 1
        self.phase = STREETS[idx]
        self.deck.pop()  # burn
        n = 3 if self.phase == "flop" else 1
        new = [self.deck.pop() for _ in range(n)]
        self.board.extend(new)
        self._reset_street()
        names = {"flop": "Флоп", "turn": "Тёрн", "river": "Ривер"}
        self._log(f"{names[self.phase]}: {' '.join(new)}")
        self.seq += 1
        if self.auto_runout:
            self.to_act = None
        else:
            self.to_act = self._next_to_act(self.dealer)
            if self.to_act is None:
                self._finish_round()

    def step_auto(self) -> None:
        """Один шаг автоматического доигрывания (когда торговаться уже некому)."""
        if self.phase not in STREETS or not self.auto_runout:
            raise IllegalAction("Автоматическое доигрывание недоступно")
        if self.phase == "river":
            self._showdown()
        else:
            self._deal_next_street()
        self.seq += 1

    def recover(self) -> None:
        """Защита от зависания: если ход никому не передан — двигаем раздачу дальше."""
        if self.phase not in STREETS:
            return
        if self.to_act is None and not self.auto_runout:
            nxt = self._next_to_act(self.dealer)
            if nxt is None or self._round_complete():
                self._finish_round()
            else:
                self.to_act = nxt
            self.seq += 1

    # ------------------------------------------------------------------ банки и выплаты
    def _build_pots(self) -> list:
        levels = sorted({p.total for p in self.seats if not p.folded and p.total > 0})
        pots, prev = [], 0
        for lv in levels:
            amount = sum(min(p.total, lv) - min(p.total, prev) for p in self.seats)
            eligible = [p.index for p in self.seats if not p.folded and p.total >= lv]
            if amount > 0:
                pots.append({"amount": amount, "eligible": eligible})
            prev = lv
        rest = sum(max(0, p.total - prev) for p in self.seats)
        if rest and pots:
            pots[-1]["amount"] += rest
        return pots

    def _order_from_dealer(self, indexes: list) -> list:
        return sorted(indexes, key=lambda i: (i - self.dealer - 1) % self.n_seats)

    def _showdown(self) -> None:
        alive = self._alive()
        for p in alive:
            p.revealed = True
        scores = {p.index: evaluate(p.hole + self.board) for p in alive}
        winnings = [0] * self.n_seats
        pot_info = []
        for pot in self._build_pots():
            best = max(scores[i] for i in pot["eligible"])
            winners = [i for i in pot["eligible"] if scores[i] == best]
            share, rem = divmod(pot["amount"], len(winners))
            for k, w in enumerate(self._order_from_dealer(winners)):
                winnings[w] += share + (1 if k < rem else 0)
            pot_info.append({"amount": pot["amount"], "winners": winners, "eligible": pot["eligible"]})
        hands = {i: describe(sc) for i, sc in scores.items()}
        self._finalize(winnings, True, pot_info, hands)

    def _award_uncontested(self, winner: Seat) -> None:
        amount = self.pot
        winnings = [0] * self.n_seats
        winnings[winner.index] = amount
        info = [{"amount": amount, "winners": [winner.index], "eligible": [winner.index]}]
        self._finalize(winnings, False, info, {})

    def _finalize(self, winnings: list, showdown: bool, pots: list, hands: dict) -> None:
        if self.paid:
            raise IllegalAction("Банк уже выплачен")
        for i, amt in enumerate(winnings):
            self.seats[i].stack += amt
        self.paid = True
        net = [self.seats[i].stack - self.start_stacks[i] for i in range(self.n_seats)]
        winners = [{"seat": i, "name": self.seats[i].name, "amount": winnings[i], "hand": hands.get(i, "")}
                   for i in range(self.n_seats) if winnings[i] > 0]
        self.result = {
            "showdown": showdown, "winners": winners, "pots": pots,
            "net": net, "won": list(winnings), "total_pot": sum(winnings),
        }
        self.phase = "complete"
        self.to_act = None
        for w in winners:
            suffix = f" ({w['hand']})" if w["hand"] else ""
            self._log(f"{w['name']} забирает {money(w['amount'])}{suffix}", w["seat"])
        if self.mode == "tournament":
            for s in self.seats:
                if s.stack <= 0 and s.index not in self.eliminated_order:
                    self.eliminated_order.append(s.index)
                    self._log(f"{s.name} выбывает из турнира", s.index)
        self.seq += 1

    # ------------------------------------------------------------------ вид для ботов
    def bot_view(self, i: int) -> dict:
        """Только публичная информация и собственные карты. Чужих закрытых карт здесь нет."""
        me = self.seats[i]
        acts = self.hand_actions
        street = self.phase
        order = lambda k: (k - self.dealer - 1) % self.n_seats
        others_alive = [s for s in self._alive() if s.index != i]
        in_position = all(order(i) > order(s.index) for s in others_alive) if others_alive else True
        preflop_aggr = [a for a in acts if a["street"] == "preflop" and a["aggr"]]
        limpers = sum(1 for a in acts if a["street"] == "preflop" and a["action"] == "call") \
            if not preflop_aggr else 0
        return {
            "seat": i, "hole": list(me.hole), "board": list(self.board), "street": street,
            "pot": self.pot, "to_call": max(0, self.current_bet - me.bet), "stack": me.stack,
            "bet": me.bet, "current_bet": self.current_bet, "min_raise": self.min_raise,
            "bb": self.bb, "sb": self.sb, "position": self.position_of(i),
            "n_active": len(self._alive()), "in_position": in_position,
            "legal": self.legal_actions(i), "level": self.table["level"],
            "preflop_raises": len(preflop_aggr), "limpers": limpers,
            "raises_this_street": sum(1 for a in acts if a["street"] == street and a["aggr"]
                                      and a["seat"] != i),
            "was_preflop_aggressor": bool(preflop_aggr) and preflop_aggr[-1]["seat"] == i,
            "mood": self.moods[i],
            "players": [{"seat": s.index, "stack": s.stack, "bet": s.bet, "folded": s.folded,
                         "all_in": s.all_in, "last_action": s.last_action,
                         "position": self.position_of(s.index)} for s in self.seats if s.index != i],
            "obs": copy.deepcopy(self.obs),
            "hand_actions": copy.deepcopy(acts),
        }
