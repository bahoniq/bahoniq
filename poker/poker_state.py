"""Сервис Poker Club: столы, бай-ин, сессия за столом, шаги ботов и публичное состояние для интерфейса."""
from __future__ import annotations

import logging
import random
import threading

from . import poker_ai
from .hand_evaluator import describe_hole_board, detect_draws
from .poker_engine import HUMAN_SEAT, IllegalAction, NUM_SEATS, STREETS, PokerGame, Seat, money
from .poker_storage import START_BALANCE, PokerStorage

log = logging.getLogger("poker")

TABLES = [
    dict(id="rookie", name="ROOKIE TABLE", sb=10, bb=20, min_buyin=1_000, max_buyin=4_000, level=1,
         level_name="Начинающие", tagline="Тихий зал для первых раздач"),
    dict(id="city", name="CITY CLUB", sb=50, bb=100, min_buyin=5_000, max_buyin=15_000, level=2,
         level_name="Средний уровень", tagline="Городской клуб, играют уверенно"),
    dict(id="grand", name="GRAND HALL", sb=200, bb=400, min_buyin=20_000, max_buyin=50_000, level=3,
         level_name="Продвинутые", tagline="Большой зал, считают шансы банка"),
    dict(id="high", name="HIGH ROLLER", sb=500, bb=1_000, min_buyin=75_000, max_buyin=200_000, level=4,
         level_name="Сильные", tagline="Давление и адаптация к вашему стилю"),
    dict(id="private", name="PRIVATE ROOM", sb=2_000, bb=4_000, min_buyin=250_000, max_buyin=1_000_000,
         level=5, level_name="Экспертные", tagline="Закрытая комната. Ошибки не прощают"),
]
TABLE_BY_ID = {t["id"]: t for t in TABLES}

BOTS = [
    dict(name="Баке", persona="rock", label="СКАЛА", trait="Осторожный"),
    dict(name="Жаке", persona="shark", label="АКУЛА", trait="Агрессивный"),
    dict(name="Моля", persona="analyst", label="АНАЛИТИК", trait="Математичный"),
    dict(name="Тима", persona="wildcard", label="ДЖОКЕР", trait="Рисковый"),
    dict(name="Алтуна", persona="analyst", label="АНАЛИТИК", trait="Расчётливая"),
    dict(name="Айдон", persona="shark", label="АКУЛА", trait="Напористый"),
    dict(name="Абеке", persona="bluffer", label="БЛЕФЕР", trait="Блефует чаще всех"),
    dict(name="Венди", persona="rock", label="СКАЛА", trait="Осторожная"),
]
BOT_BY_NAME = {b["name"]: b for b in BOTS}


class PokerError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class PokerService:
    def __init__(self, storage_path, rng=None, ai_rng=None):
        self.storage = PokerStorage(storage_path)
        self.lock = threading.RLock()
        self.rng = rng or random.SystemRandom()
        self.ai_rng = ai_rng or random.Random()
        self.game: PokerGame | None = None
        self._restore()

    # ------------------------------------------------------------------ данные
    @property
    def data(self) -> dict:
        return self.storage.data

    def _restore(self) -> None:
        sess = self.data.get("session")
        if not sess:
            return
        try:
            self.game = PokerGame.from_dict(sess, rng=self.rng)
        except Exception:
            log.exception("Не удалось восстановить стол — безопасно возвращаю стек игрока в баланс")
            try:
                self.data["balance"] += max(0, int(sess["seats"][HUMAN_SEAT]["stack"]))
            except Exception:
                pass
            self.data["session"] = None
            self.game = None
            self.storage.save()
            return
        self._after_mutation()

    def _persist(self) -> None:
        self.data["session"] = self.game.to_dict() if self.game else None
        self.storage.save()

    def _after_mutation(self) -> None:
        g = self.game
        if g and g.phase == "complete" and not g.stats_applied and g.result:
            net = g.result["net"][HUMAN_SEAT]
            won = g.result["won"][HUMAN_SEAT]
            st = self.data["stats"]
            st["hands"] += 1
            if net > 0:
                st["wins"] += 1
                st["total_won"] += net
                st["biggest_pot"] = max(st["biggest_pot"], won)
            elif net < 0:
                st["losses"] += 1
                st["total_lost"] += -net
            g.stats_applied = True
        self._persist()

    # ------------------------------------------------------------------ столы
    def _tables_public(self) -> list:
        bal = self.data["balance"]
        out = []
        for t in TABLES:
            ok = bal >= t["min_buyin"]
            out.append({**t, "available": ok,
                        "lock_reason": "" if ok else f"Для входа необходимо минимум {money(t['min_buyin'])}"})
        return out

    def join(self, table_id: str, buyin, max_seats: int = 5) -> dict:
        with self.lock:
            if self.game:
                raise PokerError("Вы уже сидите за столом")
            table = TABLE_BY_ID.get(table_id)
            if not table:
                raise PokerError("Такого стола нет")
            try:
                buyin = int(buyin)
            except (TypeError, ValueError):
                raise PokerError("Некорректный бай-ин")
            try:
                max_seats = int(max_seats)
            except (TypeError, ValueError):
                max_seats = 5
            if max_seats not in (5, 9):
                max_seats = 5
            bal = self.data["balance"]
            if bal < table["min_buyin"]:
                raise PokerError(f"Для входа необходимо минимум {money(table['min_buyin'])}")
            if not table["min_buyin"] <= buyin <= table["max_buyin"]:
                raise PokerError(f"Бай-ин: от {money(table['min_buyin'])} до {money(table['max_buyin'])}")
            if buyin > bal:
                raise PokerError("Недостаточно средств на балансе")

            seats = [Seat(0, "Вы", True, buyin)]
            placeholder = PokerGame(table, [Seat(0, "Вы", True, buyin)], rng=self.rng)
            for i, b in enumerate(BOTS[: max_seats - 1], start=1):
                seats.append(Seat(i, b["name"], False, placeholder._bot_stack(), persona=b["persona"]))
            game = PokerGame(table, seats, rng=self.rng)
            self.data["balance"] = bal - buyin       # деньги переходят из банка за стол одной операцией
            self.game = game
            game.start_hand()
            self._after_mutation()
            return self.state()

    def leave(self) -> dict:
        with self.lock:
            g = self.game
            if not g:
                return self.state()
            if g.phase in STREETS:
                g.leave_requested = True
                self._persist()
                return self.state()
            self.data["balance"] += max(0, g.seats[HUMAN_SEAT].stack)
            self.game = None
            self._persist()
            return self.state()

    def cancel_leave(self) -> dict:
        with self.lock:
            if self.game:
                self.game.leave_requested = False
                self._persist()
            return self.state()

    def reset(self, confirm) -> dict:
        with self.lock:
            if confirm is not True:
                raise PokerError("Требуется подтверждение")
            self.game = None
            self.storage.reset()
            return self.state()

    def set_sound(self, enabled) -> dict:
        with self.lock:
            self.data["settings"]["sound"] = bool(enabled)
            self._persist()
            return self.state()

    # ------------------------------------------------------------------ игра
    def _check_seq(self, seq) -> PokerGame:
        g = self.game
        if not g:
            raise PokerError("Вы не за столом", 409)
        if seq is not None and seq != g.seq:
            raise PokerError("Состояние стола обновилось, повторите действие", 409)
        return g

    def action(self, seq, action: str, amount=None) -> dict:
        with self.lock:
            g = self._check_seq(seq)
            if g.to_act != HUMAN_SEAT:
                raise PokerError("Сейчас не ваш ход", 409)
            try:
                g.act(HUMAN_SEAT, action, amount)
            except IllegalAction as e:
                raise PokerError(str(e))
            self._after_mutation()
            return self.state()

    def advance(self, seq) -> dict:
        """Один автоматический шаг: ход бота или доигрывание борда. Устаревшие запросы игнорируются."""
        with self.lock:
            g = self.game
            if not g or seq != g.seq or g.phase not in STREETS:
                return self.state()
            if g.to_act is None:
                if g.auto_runout:
                    g.step_auto()
                else:
                    g.recover()
            elif g.to_act != HUMAN_SEAT:
                self._bot_move(g.to_act)
            self._after_mutation()
            return self.state()

    def _bot_move(self, i: int) -> None:
        g = self.game
        seat = g.seats[i]
        view = g.bot_view(i)
        try:
            action, amount = poker_ai.decide(view, g.table["level"], seat.persona, self.ai_rng)
            g.act(i, action, amount)
        except Exception:
            log.exception("Ошибка бота %s — безопасное действие", seat.name)
            legal = g.legal_actions(i)
            safe = "check" if "check" in legal else "fold" if "fold" in legal else "call"
            g.act(i, safe)

    def next_hand(self, seq) -> dict:
        with self.lock:
            g = self._check_seq(seq)
            if g.phase in STREETS:
                raise PokerError("Раздача ещё не завершена", 409)
            if g.leave_requested:
                raise PokerError("Вы запросили выход из-за стола")
            try:
                g.start_hand()
            except IllegalAction as e:
                raise PokerError(str(e))
            self._after_mutation()
            return self.state()

    # ------------------------------------------------------------------ публичное состояние
    def state(self) -> dict:
        bal = self.data["balance"]
        cheapest = min(t["min_buyin"] for t in TABLES)
        return {
            "profile": {
                "balance": bal, "start_balance": START_BALANCE, "stats": dict(self.data["stats"]),
                "settings": dict(self.data["settings"]),
                "bankrupt": self.game is None and bal < cheapest,
            },
            "tables": self._tables_public(),
            "session": self._session_public(),
        }

    def _session_public(self):
        g = self.game
        if not g:
            return None
        seats = []
        for s in g.seats:
            if s.is_human:
                cards = list(s.hole)
            elif s.revealed and not s.folded:
                cards = list(s.hole)
            else:
                cards = ["??"] * len(s.hole)
            bot = BOT_BY_NAME.get(s.name, {})
            seats.append({
                "index": s.index, "name": s.name, "is_human": s.is_human, "stack": s.stack, "bet": s.bet,
                "folded": s.folded, "all_in": s.all_in, "cards": cards, "last_action": s.last_action,
                "position": g.position_of(s.index), "label": bot.get("label", ""), "trait": bot.get("trait", ""),
                "persona": s.persona,
            })
        human = g.seats[HUMAN_SEAT]
        hint, draws = "", []
        if human.hole and not human.folded:
            hint = describe_hole_board(human.hole, g.board)
            if g.table["level"] == 1:  # подсказки по дро — только на самом лёгком столе
                draws = detect_draws(human.hole, g.board)
        legal = g.legal_actions(HUMAN_SEAT) if g.to_act == HUMAN_SEAT else {}
        legal_json = {k: (list(v) if isinstance(v, tuple) else v) for k, v in legal.items()}
        result = g.result
        return {
            "table": {k: g.table[k] for k in ("id", "name", "sb", "bb", "level", "level_name")},
            "seq": g.seq, "hand_no": g.hand_no, "phase": g.phase, "dealer": g.dealer,
            "board": list(g.board), "pot": g.pot, "current_bet": g.current_bet, "min_raise": g.min_raise,
            "to_act": g.to_act, "auto_runout": g.auto_runout,
            "to_call": max(0, g.current_bet - human.bet), "legal": legal_json,
            "seats": seats, "result": result, "log": [e["text"] for e in g.log[-14:]],
            "hint": hint, "draws": draws, "leave_requested": g.leave_requested,
            "can_leave_now": g.phase not in STREETS, "busted": human.stack <= 0 and g.phase == "complete",
            "human_stack": human.stack,
        }
