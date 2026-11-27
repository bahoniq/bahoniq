"""HTTP-слой Poker Club. Не зависит от веб-фреймворка: dispatch() возвращает (статус, JSON).

В Work Center (FastAPI) эта функция оборачивается в один роутер с /api/poker/*.
"""
from __future__ import annotations

import logging

from .poker_state import PokerError, PokerService

log = logging.getLogger("poker")

PREFIX = "/api/poker"


def _ok(service: PokerService, state: dict) -> tuple:
    return 200, {"ok": True, "state": state}


def dispatch(service: PokerService, method: str, path: str, body: dict | None) -> tuple:
    body = body if isinstance(body, dict) else {}
    route = path.split("?", 1)[0].rstrip("/")
    if not route.startswith(PREFIX):
        return 404, {"ok": False, "error": "Не найдено"}
    name = route[len(PREFIX):].strip("/")
    try:
        if method == "GET" and name == "state":
            return _ok(service, service.state())
        if method != "POST":
            return 404, {"ok": False, "error": "Не найдено"}
        if name == "join":
            return _ok(service, service.join(body.get("table_id"), body.get("buyin"), body.get("seats", 5)))
        if name == "action":
            return _ok(service, service.action(body.get("seq"), str(body.get("action", "")), body.get("amount")))
        if name == "advance":
            return _ok(service, service.advance(body.get("seq")))
        if name == "next_hand":
            return _ok(service, service.next_hand(body.get("seq")))
        if name == "leave":
            return _ok(service, service.leave())
        if name == "cancel_leave":
            return _ok(service, service.cancel_leave())
        if name == "reset":
            return _ok(service, service.reset(body.get("confirm")))
        if name == "settings":
            return _ok(service, service.set_sound(body.get("sound")))
        return 404, {"ok": False, "error": "Не найдено"}
    except PokerError as e:
        return e.status, {"ok": False, "error": e.message, "state": service.state()}
    except Exception:
        log.exception("Критическая ошибка Poker Club")
        return 500, {"ok": False, "error": "Внутренняя ошибка. Попробуйте ещё раз.", "state": service.state()}
