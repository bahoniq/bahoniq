"""Professional execution and assessment core for Python and SQL lessons.

The UI deliberately depends on this module instead of implementing validation
rules itself.  That keeps lessons, exams and projects on the same contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence
import ast
import contextlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import time


@dataclass(frozen=True)
class TestCase:
    name: str
    stdin: str = ""
    expected_stdout: str | None = None
    expected_returncode: int = 0
    hidden: bool = False


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    duration_ms: int = 0
    hidden: bool = False


@dataclass(frozen=True)
class PythonReport:
    passed: bool
    syntax_ok: bool
    cases: tuple[CaseResult, ...]
    message: str


class PythonPolicyError(ValueError):
    """Raised when learner code requests capabilities outside the lab."""


class _PolicyVisitor(ast.NodeVisitor):
    blocked_imports = {
        "ctypes", "multiprocessing", "resource", "signal", "socket",
        "subprocess", "sys", "winreg",
    }
    blocked_calls = {"breakpoint", "compile", "eval", "exec", "__import__"}

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            if item.name.split(".", 1)[0] in self.blocked_imports:
                raise PythonPolicyError(f"Импорт {item.name!r} недоступен в учебной песочнице")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".", 1)[0]
        if node.level or root in self.blocked_imports:
            raise PythonPolicyError("Относительный или системный импорт недоступен в учебной песочнице")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in self.blocked_calls:
            raise PythonPolicyError(f"Вызов {node.func.id}() недоступен в учебной песочнице")
        self.generic_visit(node)


def validate_python_policy(code: str) -> ast.Module:
    if len(code.encode("utf-8")) > 100_000:
        raise PythonPolicyError("Код превышает учебный лимит 100 КБ")
    tree = ast.parse(code, filename="main.py")
    _PolicyVisitor().visit(tree)
    return tree


def _normalise_output(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").strip().split("\n"))


class PythonRunner:
    """Runs each case in a fresh isolated process and temporary directory."""

    def __init__(self, timeout_seconds: float = 3.0, max_output: int = 50_000):
        self.timeout_seconds = timeout_seconds
        self.max_output = max_output

    def run_case(self, code: str, case: TestCase) -> CaseResult:
        from .python_runtime import execute_python
        result = execute_python(code, stdin=case.stdin, timeout=self.timeout_seconds, max_output=self.max_output)
        stderr = result.stderr + ('\n' + result.reason if result.reason else '')
        matches = case.expected_stdout is None or _normalise_output(result.stdout) == _normalise_output(case.expected_stdout)
        passed = not result.reason and result.returncode == case.expected_returncode and matches
        return CaseResult(case.name, passed, result.stdout, stderr, result.returncode,
                          result.duration_ms, case.hidden)

    def assess(self, code: str, cases: Sequence[TestCase]) -> PythonReport:
        try:
            validate_python_policy(code)
        except SyntaxError as exc:
            return PythonReport(False, False, (), f"Ошибка синтаксиса, строка {exc.lineno}: {exc.msg}")
        except PythonPolicyError as exc:
            return PythonReport(False, True, (), str(exc))
        actual = tuple(self.run_case(code, case) for case in cases)
        passed = bool(actual) and all(case.passed for case in actual)
        total = len(actual)
        correct = sum(case.passed for case in actual)
        return PythonReport(passed, True, actual, f"Пройдено тестов: {correct}/{total}")


@dataclass(frozen=True)
class SQLResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    duration_ms: int
    plan: tuple[str, ...] = ()


@dataclass(frozen=True)
class SQLExpectation:
    columns: tuple[str, ...] | None = None
    rows: tuple[tuple[Any, ...], ...] | None = None
    ordered: bool = True


@dataclass(frozen=True)
class SQLReport:
    passed: bool
    result: SQLResult | None
    message: str


def task_manager_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL);
        CREATE TABLE tasks(
            id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('open','done')),
            priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
            user_id INTEGER NOT NULL REFERENCES users(id)
        );
        INSERT INTO users VALUES
            (1,'Алия','Разработка'),(2,'Бек','Аналитика'),(3,'Дана','Поддержка'),(4,'Марат','Аналитика');
        INSERT INTO tasks VALUES
            (1,'Python','open',5,1),(2,'SQL','done',4,1),(3,'Git','open',3,2),
            (4,'API','open',5,2),(5,'Tkinter','done',2,1),(6,'Отчёт','open',4,3);
    """)
    return db


class SQLRunner:
    """Executes one statement against a fresh dataset and returns typed data."""

    allowed_actions = {
        sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }

    def __init__(self, database_factory=task_manager_db, max_rows: int = 500):
        self.database_factory = database_factory
        self.max_rows = max_rows

    def execute(self, query: str, *, read_only: bool = True, explain: bool = False) -> SQLResult:
        if len(query.encode("utf-8")) > 100_000:
            raise ValueError("SQL превышает учебный лимит 100 КБ")
        db = self.database_factory()
        started = time.monotonic()
        try:
            db.set_progress_handler(lambda: 1 if time.monotonic() - started > 3 else 0, 1000)
            if read_only:
                db.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in self.allowed_actions else sqlite3.SQLITE_DENY)
            cur = db.execute(query)
            columns = tuple(item[0] for item in (cur.description or ()))
            rows = tuple(cur.fetchmany(self.max_rows + 1))
            if len(rows) > self.max_rows:
                raise ValueError(f"Результат превышает лимит {self.max_rows} строк")
            plan: tuple[str, ...] = ()
            if explain and read_only:
                plan = tuple(str(row[-1]) for row in db.execute("EXPLAIN QUERY PLAN " + query))
            return SQLResult(columns, rows, int((time.monotonic() - started) * 1000), plan)
        finally:
            db.close()

    def assess(self, query: str, expectation: SQLExpectation) -> SQLReport:
        try:
            result = self.execute(query, read_only=True, explain=True)
        except (sqlite3.Error, ValueError) as exc:
            return SQLReport(False, None, f"SQL не выполнен: {exc}")
        if expectation.columns is not None and result.columns != expectation.columns:
            return SQLReport(False, result, f"Ожидались столбцы {expectation.columns}, получены {result.columns}")
        if expectation.rows is not None:
            actual = result.rows if expectation.ordered else tuple(sorted(result.rows, key=repr))
            wanted = expectation.rows if expectation.ordered else tuple(sorted(expectation.rows, key=repr))
            if actual != wanted:
                return SQLReport(False, result, f"Результат содержит другие данные: ожидалось {len(wanted)} строк, получено {len(actual)}")
        return SQLReport(True, result, f"Результат подтверждён: {len(result.rows)} строк")

