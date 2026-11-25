# -*- coding: utf-8 -*-
"""База данных BahonIQ Academy (SQLite) — 4 этапа, 60 уроков, микрошаги ИИ-тренера и прогресс."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .syllabus_data import LESSONS_DATA, STAGES_DATA

LOGGER = logging.getLogger("bahoniq.academy.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB_APP_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WEB_APP_DIR / "data"
DB_PATH = DATA_DIR / "academy.db"
DEFAULT_PROFILE_ID = "default"
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_db_lock = threading.Lock()


def validate_profile_id(profile_id: str | None) -> str:
    """Проверяет profile_id: допускает только 'default' (внутр.) или строгий UUID."""
    if profile_id is None:
        return DEFAULT_PROFILE_ID
    raw = str(profile_id).strip()
    if not raw or raw == DEFAULT_PROFILE_ID:
        return DEFAULT_PROFILE_ID
    if not _UUID_RE.fullmatch(raw):
        raise ValueError("Некорректный идентификатор профиля (ожидается UUID).")
    return raw.lower()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Безопасно добавляет недостающие колонки в таблицу без потери данных."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for col_name, col_def in columns.items():
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            except Exception as exc:
                LOGGER.debug("Column %s exists or cannot add: %s", col_name, exc)


def init_academy_db() -> None:
    """Инициализирует БД SQLite, создаёт таблицы и загружает полный каталог 60 уроков."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")

            # 1. Таблица этапов
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS academy_stages (
                    id INTEGER PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT NOT NULL,
                    order_index INTEGER NOT NULL
                );
                """
            )

            # 2. Таблица уроков
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS academy_lessons (
                    id INTEGER PRIMARY KEY,
                    stage_id INTEGER NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    order_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    ai_theory TEXT NOT NULL,
                    task_prompt TEXT NOT NULL,
                    starter_code TEXT NOT NULL,
                    expected_hint TEXT DEFAULT '',
                    file_path TEXT DEFAULT '',
                    FOREIGN KEY(stage_id) REFERENCES academy_stages(id)
                );
                """
            )

            # Расширяем колонками для микрошагов и интерактивного теста
            _ensure_columns(
                conn,
                "academy_lessons",
                {
                    "step1_concept": "TEXT DEFAULT ''",
                    "step1_trap_code": "TEXT DEFAULT ''",
                    "step1_trap_question": "TEXT DEFAULT ''",
                    "step1_trap_expected": "TEXT DEFAULT ''",
                    "step1_rule": "TEXT DEFAULT ''",
                    "step2_concept": "TEXT DEFAULT ''",
                    "step2_task_prompt": "TEXT DEFAULT ''",
                    "step2_starter_code": "TEXT DEFAULT ''",
                    "step2_rule": "TEXT DEFAULT ''",
                    "step2_expected_criteria": "TEXT DEFAULT ''",
                    "is_ai_generated": "INTEGER DEFAULT 0",
                    "quiz_data_json": "TEXT DEFAULT '[]'",
                    "stable_id": "TEXT DEFAULT ''",
                },
            )

            # 3. Таблица прогресса пользователя
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS academy_progress (
                    lesson_id INTEGER PRIMARY KEY,
                    completed INTEGER DEFAULT 0,
                    user_code TEXT DEFAULT '',
                    mentor_feedback TEXT DEFAULT '',
                    completed_at TEXT DEFAULT '',
                    FOREIGN KEY(lesson_id) REFERENCES academy_lessons(id)
                );
                """
            )

            _ensure_columns(
                conn,
                "academy_progress",
                {
                    "current_step": "INTEGER DEFAULT 1",
                    "step1_answer": "TEXT DEFAULT ''",
                    "step1_passed": "INTEGER DEFAULT 0",
                    "step2_code": "TEXT DEFAULT ''",
                    "step2_passed": "INTEGER DEFAULT 0",
                    "quiz_score": "INTEGER DEFAULT 0",
                },
            )

            # Заполняем этапы
            for st in STAGES_DATA:
                conn.execute(
                    """
                    INSERT INTO academy_stages (id, slug, title, subtitle, order_index)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        slug = excluded.slug,
                        title = excluded.title,
                        subtitle = excluded.subtitle,
                        order_index = excluded.order_index;
                    """,
                    (st["id"], st["slug"], st["title"], st["subtitle"], st["order_index"]),
                )

            # Заполняем все 60 уроков
            for les in LESSONS_DATA:
                quiz_json = json.dumps(les.get("quiz_data", []), ensure_ascii=False)
                stable_id = les.get("stable_id") or ""
                conn.execute(
                    """
                    INSERT INTO academy_lessons (
                        id, stage_id, slug, order_index, title, language, summary,
                        ai_theory, task_prompt, starter_code, expected_hint, file_path,
                        step1_concept, step1_trap_code, step1_trap_question,
                        step1_trap_expected, step1_rule,
                        step2_concept, step2_task_prompt, step2_starter_code, step2_rule,
                        quiz_data_json, stable_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        stage_id = excluded.stage_id,
                        slug = excluded.slug,
                        order_index = excluded.order_index,
                        title = excluded.title,
                        language = excluded.language,
                        summary = excluded.summary,
                        ai_theory = excluded.ai_theory,
                        task_prompt = excluded.task_prompt,
                        starter_code = excluded.starter_code,
                        expected_hint = excluded.expected_hint,
                        file_path = excluded.file_path,
                        step1_concept = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step1_concept ELSE excluded.step1_concept END,
                        step1_trap_code = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step1_trap_code ELSE excluded.step1_trap_code END,
                        step1_trap_question = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step1_trap_question ELSE excluded.step1_trap_question END,
                        step1_trap_expected = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step1_trap_expected ELSE excluded.step1_trap_expected END,
                        step1_rule = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step1_rule ELSE excluded.step1_rule END,
                        step2_concept = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step2_concept ELSE excluded.step2_concept END,
                        step2_task_prompt = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step2_task_prompt ELSE excluded.step2_task_prompt END,
                        step2_starter_code = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step2_starter_code ELSE excluded.step2_starter_code END,
                        step2_rule = CASE WHEN academy_lessons.is_ai_generated = 1 THEN academy_lessons.step2_rule ELSE excluded.step2_rule END,
                        quiz_data_json = excluded.quiz_data_json,
                        stable_id = CASE WHEN excluded.stable_id != '' THEN excluded.stable_id ELSE academy_lessons.stable_id END;
                    """,
                    (
                        les["id"],
                        les["stage_id"],
                        les["slug"],
                        les["order_index"],
                        les["title"],
                        les["language"],
                        les["summary"],
                        les["ai_theory"],
                        les.get("step2_task_prompt") or les.get("task_prompt", ""),
                        les.get("step2_starter_code") or les.get("starter_code", ""),
                        les.get("expected_hint", ""),
                        les.get("file_path", ""),
                        les.get("step1_concept", ""),
                        les.get("step1_trap_code", ""),
                        les.get("step1_trap_question", ""),
                        les.get("step1_trap_expected", ""),
                        les.get("step1_rule", ""),
                        les.get("step2_concept", ""),
                        les.get("step2_task_prompt", ""),
                        les.get("step2_starter_code", ""),
                        les.get("step2_rule", ""),
                        quiz_json,
                        stable_id,
                    ),
                )

            # Восстанавливаем дефолтный прогресс: Урок 1 и Урок 2 всегда пройдены (2/18)
            conn.execute(
                """
                INSERT OR IGNORE INTO academy_progress (
                    lesson_id, completed, current_step, quiz_score, completed_at, step1_passed, step2_passed
                ) VALUES 
                (1, 1, 3, 5, '2026-11-16 13:00:00', 1, 1),
                (2, 1, 3, 5, '2026-11-17 14:00:00', 1, 1);
                """
            )
            conn.execute(
                """
                UPDATE academy_progress 
                SET completed = 1, current_step = 3, quiz_score = 5, step1_passed = 1, step2_passed = 1 
                WHERE lesson_id IN (1, 2) AND completed = 0;
                """
            )

            # 3.1. Мультипрофильная таблица прогресса (profile_id + lesson_id)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS academy_profile_progress (
                    profile_id TEXT NOT NULL,
                    lesson_id INTEGER NOT NULL,
                    completed INTEGER DEFAULT 0,
                    current_step INTEGER DEFAULT 1,
                    step1_answer TEXT DEFAULT '',
                    step1_feedback TEXT DEFAULT '',
                    step1_passed INTEGER DEFAULT 0,
                    step2_code TEXT DEFAULT '',
                    step2_passed INTEGER DEFAULT 0,
                    user_code TEXT DEFAULT '',
                    mentor_feedback TEXT DEFAULT '',
                    quiz_score INTEGER DEFAULT 0,
                    completed_at TEXT DEFAULT '',
                    PRIMARY KEY (profile_id, lesson_id),
                    FOREIGN KEY(lesson_id) REFERENCES academy_lessons(id)
                );
                """
            )

            # Миграция старого прогресса в профиль 'default' без удаления старой таблицы
            has_default = conn.execute(
                "SELECT 1 FROM academy_profile_progress WHERE profile_id = ? LIMIT 1",
                (DEFAULT_PROFILE_ID,),
            ).fetchone()
            if not has_default:
                legacy_cols = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(academy_progress)").fetchall()
                }
                if "lesson_id" in legacy_cols:
                    def _col_expr(col: str, default_sql: str) -> str:
                        return f"COALESCE({col}, {default_sql})" if col in legacy_cols else default_sql

                    conn.execute(
                        f"""
                        INSERT OR IGNORE INTO academy_profile_progress (
                            profile_id, lesson_id, completed, current_step, step1_answer,
                            step1_feedback, step1_passed, step2_code, step2_passed,
                            user_code, mentor_feedback, quiz_score, completed_at
                        )
                        SELECT ?, lesson_id,
                               {_col_expr('completed', '0')},
                               {_col_expr('current_step', '1')},
                               {_col_expr('step1_answer', "''")},
                               {_col_expr('step1_feedback', "''")},
                               {_col_expr('step1_passed', '0')},
                               {_col_expr('step2_code', "''")},
                               {_col_expr('step2_passed', '0')},
                               {_col_expr('user_code', "''")},
                               {_col_expr('mentor_feedback', "''")},
                               {_col_expr('quiz_score', '0')},
                               {_col_expr('completed_at', "''")}
                        FROM academy_progress;
                        """,
                        (DEFAULT_PROFILE_ID,),
                    )

            conn.commit()
            LOGGER.info("База данных Academy успешно синхронизирована (60 уроков, 4 этапа).")
        finally:
            conn.close()


def get_roadmap_data(profile_id: str | None = None) -> dict[str, Any]:
    """Возвращает общую структуру роадмапа: 4 этапа, 60 уроков и прогресс профиля."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    conn = _get_conn()
    try:
        stages_rows = conn.execute(
            "SELECT * FROM academy_stages ORDER BY order_index ASC"
        ).fetchall()
        lessons_rows = conn.execute(
            """
            SELECT l.id, l.stage_id, l.order_index, l.title, l.slug, l.stable_id, l.language, l.summary,
                   l.file_path,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.current_step, 1) AS current_step,
                   COALESCE(p.step1_passed, 0) AS step1_passed,
                   COALESCE(p.step2_passed, 0) AS step2_passed,
                   COALESCE(p.quiz_score, 0) AS quiz_score
            FROM academy_lessons l
            LEFT JOIN academy_profile_progress p ON p.lesson_id = l.id AND p.profile_id = ?
            ORDER BY l.stage_id ASC, l.order_index ASC
            """,
            (pid,),
        ).fetchall()
    finally:
        conn.close()

    by_stage: dict[int, list[dict[str, Any]]] = {}
    total_lessons = 0
    completed_lessons = 0

    for row in lessons_rows:
        item = dict(row)
        item["completed"] = bool(item["completed"])
        item["step1_passed"] = bool(item["step1_passed"])
        item["step2_passed"] = bool(item["step2_passed"])
        if not item.get("stable_id"):
            item["stable_id"] = f"python_{item['id']:02d}_{item['slug'].replace('-', '_')}"
        total_lessons += 1
        if item["completed"]:
            completed_lessons += 1
        by_stage.setdefault(item["stage_id"], []).append(item)

    stages_out = []
    for st in stages_rows:
        st_dict = dict(st)
        st_lessons = by_stage.get(st["id"], [])
        st_done = sum(1 for x in st_lessons if x["completed"])
        st_total = len(st_lessons)
        st_dict["lessons"] = st_lessons
        st_dict["total_lessons"] = st_total
        st_dict["completed_lessons"] = st_done
        st_dict["percent"] = round((st_done / st_total) * 100) if st_total else 0
        stages_out.append(st_dict)

    overall_percent = round((completed_lessons / total_lessons) * 100) if total_lessons else 0
    return {
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "overall_percent": overall_percent,
        "stages": stages_out,
    }


def get_lesson_by_id(lesson_id: int, profile_id: str | None = None) -> dict[str, Any] | None:
    """Возвращает урок со всеми микрошагами, вопросами теста и прогрессом профиля."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.current_step, 1) AS current_step,
                   COALESCE(p.step1_answer, '') AS step1_answer,
                   COALESCE(p.step1_passed, 0) AS step1_passed,
                   COALESCE(p.step2_code, '') AS step2_code,
                   COALESCE(p.step2_passed, 0) AS step2_passed,
                   COALESCE(p.quiz_score, 0) AS quiz_score,
                   COALESCE(p.user_code, '') AS user_code,
                   COALESCE(p.mentor_feedback, '') AS mentor_feedback
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_profile_progress p ON p.lesson_id = l.id AND p.profile_id = ?
            WHERE l.id = ?
            """,
            (pid, lesson_id),
        ).fetchone()
        if not row:
            return None

        next_row = conn.execute(
            """
            SELECT id, title, stage_id FROM academy_lessons
            WHERE id > ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (lesson_id,),
        ).fetchone()
    finally:
        conn.close()

    data = dict(row)
    data["completed"] = bool(data["completed"])
    data["step1_passed"] = bool(data["step1_passed"])
    data["step2_passed"] = bool(data["step2_passed"])
    data["next_lesson_id"] = int(next_row["id"]) if next_row else None
    data["next_lesson_title"] = next_row["title"] if next_row else ""

    # Парсим JSON теста
    raw_quiz = data.get("quiz_data_json") or "[]"
    try:
        data["quiz_data"] = json.loads(raw_quiz)
    except Exception:
        data["quiz_data"] = []

    data["repo_source_preview"] = ""
    data["file_path"] = ""
    return data



def update_lesson_ai_content(lesson_id: int, ai_data: dict[str, Any]) -> None:
    """Сохраняет сгенерированный ИИ уникальный интерактивный микроурок в базу данных."""
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                """
                UPDATE academy_lessons
                SET step1_concept = ?,
                    step1_trap_code = ?,
                    step1_trap_question = ?,
                    step1_trap_expected = ?,
                    step1_rule = ?,
                    step2_concept = ?,
                    step2_task_prompt = ?,
                    step2_starter_code = ?,
                    step2_expected_criteria = ?,
                    step2_rule = ?,
                    is_ai_generated = 1
                WHERE id = ?
                """,
                (
                    str(ai_data.get("step1_concept") or "").strip(),
                    str(ai_data.get("step1_trap_code") or "").strip(),
                    str(ai_data.get("step1_trap_question") or "").strip(),
                    str(ai_data.get("step1_trap_expected") or "").strip(),
                    str(ai_data.get("step1_rule") or "").strip(),
                    str(ai_data.get("step2_concept") or "").strip(),
                    str(ai_data.get("step2_task_prompt") or "").strip(),
                    str(ai_data.get("step2_starter_code") or "").strip(),
                    str(ai_data.get("step2_expected_criteria") or "").strip(),
                    str(ai_data.get("step2_rule") or "").strip(),
                    lesson_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def save_step1_result(lesson_id: int, answer: str, feedback: str, passed: bool, profile_id: str | None = None) -> None:
    """Сохраняет ответ на Шаг 1 (чтение кода / ловушка) и переводит на Шаг 2 при успехе."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO academy_profile_progress (profile_id, lesson_id, current_step, step1_answer, step1_passed, mentor_feedback)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, lesson_id) DO UPDATE SET
                    step1_answer = excluded.step1_answer,
                    step1_passed = CASE WHEN ? = 1 THEN 1 ELSE academy_profile_progress.step1_passed END,
                    current_step = CASE WHEN ? = 1 THEN MAX(2, academy_profile_progress.current_step) ELSE academy_profile_progress.current_step END,
                    mentor_feedback = excluded.mentor_feedback;
                """,
                (pid, lesson_id, 2 if passed else 1, answer, 1 if passed else 0, feedback, 1 if passed else 0, 1 if passed else 0),
            )
            conn.commit()
        finally:
            conn.close()


def save_step2_result(lesson_id: int, code: str, feedback: str, passed: bool, profile_id: str | None = None) -> None:
    """Сохраняет код на Шаг 2 (практика) и открывает Финальный тест при успехе."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO academy_profile_progress (profile_id, lesson_id, current_step, step2_code, step2_passed, user_code, mentor_feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, lesson_id) DO UPDATE SET
                    step2_code = excluded.step2_code,
                    user_code = excluded.user_code,
                    step2_passed = CASE WHEN ? = 1 THEN 1 ELSE academy_profile_progress.step2_passed END,
                    current_step = CASE WHEN ? = 1 THEN MAX(3, academy_profile_progress.current_step) ELSE academy_profile_progress.current_step END,
                    mentor_feedback = excluded.mentor_feedback;
                """,
                (pid, lesson_id, 3 if passed else 2, code, 1 if passed else 0, code, feedback, 1 if passed else 0, 1 if passed else 0),
            )
            conn.commit()
        finally:
            conn.close()


def save_quiz_result(lesson_id: int, score: int, passed: bool, profile_id: str | None = None) -> None:
    """Сохраняет результат теста и отмечает весь урок пройденным."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO academy_profile_progress (profile_id, lesson_id, completed, current_step, quiz_score, completed_at)
                VALUES (?, ?, ?, 3, ?, ?)
                ON CONFLICT(profile_id, lesson_id) DO UPDATE SET
                    quiz_score = MAX(excluded.quiz_score, academy_profile_progress.quiz_score),
                    completed = CASE WHEN ? = 1 THEN 1 ELSE academy_profile_progress.completed END,
                    completed_at = CASE WHEN ? = 1 THEN excluded.completed_at ELSE academy_profile_progress.completed_at END;
                """,
                (pid, lesson_id, 1 if passed else 0, score, now_iso if passed else "", 1 if passed else 0, 1 if passed else 0),
            )
            conn.commit()
        finally:
            conn.close()


def save_lesson_theory(lesson_id: int, ai_theory: str) -> None:
    """Кэширует перегенерированное живое объяснение урока."""
    init_academy_db()
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE academy_lessons SET ai_theory = ? WHERE id = ?",
                (ai_theory.strip(), lesson_id),
            )
            conn.commit()
        finally:
            conn.close()


def save_user_attempt(lesson_id: int, user_code: str, mentor_feedback: str, passed: bool, profile_id: str | None = None) -> None:
    """Сохраняет классическую попытку кода (обратная совместимость)."""
    save_step2_result(lesson_id, user_code, mentor_feedback, passed, profile_id=profile_id)


def get_conn_lessons_all(profile_id: str | None = None) -> list[dict[str, Any]]:
    """Возвращает полный список всех 60 уроков со всеми полями для PDF-книги."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.user_code, '') AS user_code,
                   COALESCE(p.quiz_score, 0) AS quiz_score
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_profile_progress p ON p.lesson_id = l.id AND p.profile_id = ?
            ORDER BY l.id ASC
            """,
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_lesson_completed(lesson_id_or_stable: int | str, score: int = 5, profile_id: str | None = None) -> dict[str, Any]:
    """Отмечает урок пройденным по ID, stable_id или slug с сохранением в SQLite."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    conn = _get_conn()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if isinstance(lesson_id_or_stable, int) or (isinstance(lesson_id_or_stable, str) and lesson_id_or_stable.isdigit()):
            lid = int(lesson_id_or_stable)
        else:
            row = conn.execute(
                "SELECT id FROM academy_lessons WHERE stable_id = ? OR slug = ? LIMIT 1",
                (str(lesson_id_or_stable), str(lesson_id_or_stable)),
            ).fetchone()
            if not row:
                return {"success": False, "error": f"Урок {lesson_id_or_stable} не найден"}
            lid = int(row["id"])

        with _db_lock:
            conn.execute(
                """
                INSERT INTO academy_profile_progress (
                    profile_id, lesson_id, completed, current_step, quiz_score, completed_at, step1_passed, step2_passed
                ) VALUES (?, ?, 1, 3, ?, ?, 1, 1)
                ON CONFLICT(profile_id, lesson_id) DO UPDATE SET
                    completed = 1,
                    current_step = 3,
                    quiz_score = MAX(excluded.quiz_score, academy_profile_progress.quiz_score),
                    step1_passed = 1,
                    step2_passed = 1,
                    completed_at = CASE WHEN academy_profile_progress.completed_at != '' THEN academy_profile_progress.completed_at ELSE excluded.completed_at END;
                """,
                (pid, lid, score, now_iso),
            )
            conn.commit()
    finally:
        conn.close()

    return {"success": True, "lesson_id": lid, "roadmap": get_roadmap_data(profile_id=pid)}


def sync_completed_lessons(completed_ids: list[int | str], profile_id: str | None = None) -> dict[str, Any]:
    """Синхронизирует набор пройденных уроков из localStorage клиента в SQLite."""
    pid = validate_profile_id(profile_id)
    init_academy_db()
    if not completed_ids:
        return {"success": True, "synced_count": 0, "roadmap": get_roadmap_data(profile_id=pid)}

    conn = _get_conn()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    synced = 0
    try:
        with _db_lock:
            for item in completed_ids:
                if isinstance(item, int) or (isinstance(item, str) and str(item).isdigit()):
                    lid = int(item)
                else:
                    row = conn.execute(
                        "SELECT id FROM academy_lessons WHERE stable_id = ? OR slug = ? LIMIT 1",
                        (str(item), str(item)),
                    ).fetchone()
                    if not row:
                        continue
                    lid = int(row["id"])

                conn.execute(
                    """
                    INSERT INTO academy_profile_progress (
                        profile_id, lesson_id, completed, current_step, quiz_score, completed_at, step1_passed, step2_passed
                    ) VALUES (?, ?, 1, 3, 5, ?, 1, 1)
                    ON CONFLICT(profile_id, lesson_id) DO UPDATE SET
                        completed = 1,
                        current_step = 3,
                        step1_passed = 1,
                        step2_passed = 1,
                        completed_at = CASE WHEN academy_profile_progress.completed_at != '' THEN academy_profile_progress.completed_at ELSE excluded.completed_at END;
                    """,
                    (pid, lid, now_iso),
                )
                synced += 1
            conn.commit()
    finally:
        conn.close()

    return {"success": True, "synced_count": synced, "roadmap": get_roadmap_data(profile_id=pid)}
