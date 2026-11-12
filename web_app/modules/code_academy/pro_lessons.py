"""Executable acceptance criteria for the first professional Python/SQL route."""
from __future__ import annotations

from dataclasses import dataclass
from .pro_engine import SQLExpectation, TestCase


@dataclass(frozen=True)
class Acceptance:
    slug: str
    python_cases: tuple[TestCase, ...] = ()
    sql: SQLExpectation | None = None


ACCEPTANCE = {
    "p01": Acceptance("p01", python_cases=(
        TestCase("Программа выводит изменённые данные"),
    )),
    "p02": Acceptance("p02", python_cases=(
        TestCase("Обычная задача"),
    )),
    "s01": Acceptance("s01", sql=SQLExpectation(
        columns=("title", "status"),
        rows=(("API", "open"), ("Git", "open"), ("Python", "open"), ("SQL", "done"), ("Tkinter", "done"), ("Отчёт", "open")),
    )),
    "s02": Acceptance("s02", sql=SQLExpectation(
        columns=("id", "title", "status"),
        rows=((2, "SQL", "done"), (5, "Tkinter", "done")),
    )),
    "s03": Acceptance("s03", sql=SQLExpectation(
        columns=("user_id", "total"),
        rows=((1, 3), (2, 2), (3, 1)),
    )),
}


def acceptance_for(slug: str) -> Acceptance | None:
    return ACCEPTANCE.get(slug)

