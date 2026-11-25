# -*- coding: utf-8 -*-
"""Роутер Code Academy (FastAPI + ИИ-тренер + 60 уроков + микрошаги + тесты + PDF-книга)."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ai_service import generate_text
from ..modules.code_academy.db import (
    get_lesson_by_id,
    get_roadmap_data,
    mark_lesson_completed,
    save_lesson_theory,
    save_quiz_result,
    save_step1_result,
    save_step2_result,
    save_user_attempt,
    sync_completed_lessons,
    update_lesson_ai_content,
    validate_profile_id,
)
from ..modules.code_academy.pathway import run_sql
from ..modules.code_academy.pdf_book_generator import build_academy_pdf_book
from ..modules.code_academy.python_runtime import execute_python

LOGGER = logging.getLogger("bahoniq.routers.academy")

router = APIRouter(prefix="/api/academy", tags=["Code Academy"])


async def _parse_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    return dict(form)


def _extract_profile_id(request: Request, body: dict[str, Any] | None = None) -> str:
    raw = request.headers.get("X-Profile-Id") or request.query_params.get("profile_id")
    if not raw and isinstance(body, dict):
        raw = body.get("profile_id")
    try:
        return validate_profile_id(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _ensure_code_exec_allowed() -> None:
    is_public_render = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"))
    has_password = bool(os.getenv("BAHONIQ_PASSWORD", "").strip())
    if is_public_render and not has_password:
        raise HTTPException(
            403,
            "Выполнение кода отключено на публичном сервере, пока не задан BAHONIQ_PASSWORD.",
        )


def _execute_lesson_code(language: str, code: str, stdin: str = "") -> dict[str, Any]:
    """Запускает Python-код или SQL-запрос в изолированной учебной среде."""
    clean_code = (code or "").strip()
    if not clean_code:
        return {"stdout": "", "stderr": "Код пуст. Напишите решение в редакторе.", "returncode": 1}
    if len(clean_code.encode("utf-8")) > 100_000:
        return {"stdout": "", "stderr": "Код превышает учебный лимит 100 КБ.", "returncode": 1}
    if len((stdin or "").encode("utf-8")) > 20_000:
        return {"stdout": "", "stderr": "Входные данные (stdin) превышают лимит 20 КБ.", "returncode": 1}

    try:
        if language == "sql":
            out = run_sql(clean_code)
            is_err = out.strip().lower().startswith("ошибка")
            return {
                "stdout": "" if is_err else out,
                "stderr": out if is_err else "",
                "returncode": 1 if is_err else 0,
            }
        res = execute_python(clean_code, stdin=stdin, timeout=4, max_output=50_000)
        stderr_out = (res.stderr or "").strip()
        if getattr(res, "reason", ""):
            stderr_out = (stderr_out + "\n" + res.reason).strip() if stderr_out else res.reason
        return {
            "stdout": res.stdout or "",
            "stderr": stderr_out,
            "returncode": res.returncode if res.returncode is not None else 0,
        }
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "returncode": 1}


def _generate_live_theory_sync(lesson: dict[str, Any]) -> str:
    """Генерирует живое объяснение темы через Gemini Flash (обратная совместимость с десктопом)."""
    prompt = (
        f"Этап: {lesson.get('stage_title', '')}\n"
        f"Тема урока: {lesson.get('title', '')}\n"
        f"Краткая суть: {lesson.get('summary', '')}\n\n"
        "Сгенерируй живое, понятное объяснение темы (2-3 коротких абзаца + пример кода)."
    )
    try:
        return str(generate_text(
            prompt=prompt,
            system_instruction="Ты — живой дружелюбный ИИ-наставник Code Academy.",
            temperature=0.35,
            timeout=30,
        )).strip()
    except Exception:
        return lesson.get("ai_theory", "")


def _mentor_evaluate_code_sync(lesson: dict[str, Any], user_code: str, exec_result: dict[str, Any]) -> dict[str, Any]:
    """Умная проверка кода через Gemini Flash (обратная совместимость с десктопом)."""
    return _evaluate_step2_sync(lesson, user_code, exec_result)


def _generate_unique_lesson_content(
    stage_id: int,
    stage_title: str,
    lesson_id: int,
    lesson_title: str,
    lesson_summary: str,
    language: str,
) -> dict[str, Any] | None:
    """Генерирует уникальный микроурок (ловушку, код, практическую задачу и критерии) через Gemini Flash API."""
    prompt = (
        f"Этап: {stage_title} (ID {stage_id})\n"
        f"Урок {lesson_id}: {lesson_title}\n"
        f"Суть темы: {lesson_summary}\n"
        f"Язык программирования: {language} (python / sql)\n\n"
        "СОЗДАЙ СТРОГО ПО ЭТОЙ КОНКРЕТНОЙ ТЕМЕ МИКРОШАГИ ДЛЯ ОБУЧЕНИЯ (БЕЗ ШАБЛОНОВ-ЗАГЛУШЕК):\n"
        "1. step1_concept: Короткое живое объяснение именно этой механики простыми словами (2-3 предложения, объясняя каждый знак, команду и назначение).\n"
        "2. step1_trap_code: Короткий код (3-5 строк) СТРОГО по теме урока с наглядной ловушкой или деталью чтения. НЕ используй команды и синтаксис из более поздних уроков (например, на первом уроке SQL по таблицам нельзя давать CREATE TABLE, PRIMARY KEY и INSERT).\n"
        "3. step1_trap_question: Вопрос ученику («Что выведет этот код?», «В чём ошибка?», «Что вернёт запрос?»).\n"
        "4. step1_trap_expected: Эталонный ответ для строгой проверки ИИ (что должен подметить ученик).\n"
        "5. step1_rule: Главное правило тренера (1 ёмкое практическое предложение с советом).\n"
        "6. step2_concept: Вводная фраза перед практикой в редакторе кода (1-2 предложения).\n"
        "7. step2_task_prompt: Чёткая практическая задача в редакторе СТРОГО по этой теме (на 2-5 строк кода). Укажи точные имена таблиц/колонок/переменных и что требуется сделать.\n"
        "8. step2_starter_code: Начальный шаблон кода или комментарий-подсказка для редактора.\n"
        "9. step2_expected_criteria: 2-3 строгих критерия правильного решения (что обязательно должно присутствовать в коде ученика).\n"
        "10. step2_rule: Практическое правило/совет для шага 2.\n\n"
        "Ответь СТРОГО в формате JSON без markdown-разметки:\n"
        "{\n"
        '  "step1_concept": "...",\n'
        '  "step1_trap_code": "...",\n'
        '  "step1_trap_question": "...",\n'
        '  "step1_trap_expected": "...",\n'
        '  "step1_rule": "...",\n'
        '  "step2_concept": "...",\n'
        '  "step2_task_prompt": "...",\n'
        '  "step2_starter_code": "...",\n'
        '  "step2_expected_criteria": "...",\n'
        '  "step2_rule": "..."\n'
        "}"
    )

    try:
        raw = generate_text(
            prompt=prompt,
            system_instruction="Ты — методист и AI-тренер Code Academy. Верни чистый JSON строго по теме конкретного урока.",
            temperature=0.3,
            timeout=35,
        )
        cleaned = str(raw).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if isinstance(data.get("step2_expected_criteria"), list):
                data["step2_expected_criteria"] = "; ".join(str(c) for c in data["step2_expected_criteria"])
            return data
    except Exception as exc:
        LOGGER.error("Failed to generate unique lesson via Gemini Flash: %s", exc)
    return None


# ============================================================================
# ОЦЕНКА МИКРОШАГА 1: ЧТЕНИЕ КОДА («ПОЙМАЙ ЛОВУШКУ»)
# ============================================================================

def _evaluate_step1_sync(lesson: dict[str, Any], user_answer: str) -> dict[str, Any]:
    """Строгая оценка ответа ученика по шагу чтения кода через Gemini Flash."""
    clean_answer = (user_answer or "").strip()
    if not clean_answer:
        return {
            "passed": False,
            "feedback": "Напишите своими словами, что выведет этот код на экран и почему.",
            "rule": lesson.get("step1_rule") or "",
        }

    system_inst = (
        "Ты — строгий, проницательный, справедливый и доброжелательный ИИ-тренер Code Academy.\n"
        "Ученик выполняет микрошаг Типа А («Чтение кода / Поймай ловушку»).\n\n"
        "СТРОЖАЙШИЕ ПРАВИЛА ПРОВЕРКИ ПОД МИКРОСКОПОМ:\n"
        "1. Сравни ответ ученика СТРОГО с эталонным смыслом и кодом ловушки.\n"
        "2. Если ученик ответил не по теме, угадал наугад, пропустил ключевой подвох (перепутал тип данных, кавычки, имя переменной или условие) — passed ОБЯЗАН быть false!\n"
        "   НЕ ругай и НЕ выдавай готовый ответ целиком! Доброжелательно укажи на конкретную строчку/знак, объясни в чём сомнение и попроси сформулировать точнее.\n"
        "3. ТОЛЬКО если ученик действительно понял логику кода и верно ответил на вопрос тренера — ставь passed: true и похвали его за внимательность.\n\n"
        "Ответь СТРОГО в формате JSON:\n"
        '{"passed": false/true, "feedback": "Твой живой разбор ответа ученика"}'
    )

    prompt = (
        f"Тема урока: {lesson['title']} ({lesson.get('stage_title', '')})\n"
        f"Код ловушки:\n{lesson.get('step1_trap_code')}\n\n"
        f"Вопрос тренера:\n{lesson.get('step1_trap_question')}\n\n"
        f"Эталонный смысл правильного ответа:\n{lesson.get('step1_trap_expected')}\n\n"
        f"Ответ ученика:\n{clean_answer}\n\n"
        "Оцени ответ ученика строго и верни JSON {\"passed\": bool, \"feedback\": string}:"
    )

    passed = False
    feedback = ""
    try:
        raw_ai = generate_text(
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.2,
            timeout=30,
        )
        cleaned = str(raw_ai).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            passed = bool(data.get("passed", False))
            feedback = str(data.get("feedback", "")).strip()
        else:
            passed = False
            feedback = "Ответ требует уточнения: внимательнее прочитайте вопрос тренера и объясните логику кода."
    except Exception as exc:
        LOGGER.warning("Fallback оценки шага 1: %s", exc)
        passed = False
        feedback = "ИИ-тренер временно обрабатывает запросы. Проверьте ваш ответ и попробуйте отправить ещё раз."

    return {
        "passed": passed,
        "feedback": feedback,
        "rule": lesson.get("step1_rule") or "",
    }


# ============================================================================
# ОЦЕНКА МИКРОШАГА 2: НАПИСАНИЕ КОДА (ПРАКТИКА СТРОГО ПО ЗАДАНИЮ)
# ============================================================================

def _evaluate_step2_sync(
    lesson: dict[str, Any],
    user_code: str,
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    """Строгая оценка практического кода ученика: сравнение СТРОГО с условием задачи + разбор по пунктам."""
    clean_code = (user_code or "").strip()
    if not clean_code:
        return {
            "passed": False,
            "feedback": "Код пуст. Напишите решение в редакторе перед отправкой на проверку.",
            "rule": lesson.get("step2_rule") or "",
        }

    stdout_str = (exec_result.get("stdout") or "").strip()
    stderr_str = (exec_result.get("stderr") or "").strip()
    has_runtime_error = bool(stderr_str) or exec_result.get("returncode", 0) != 0

    task_prompt = lesson.get("step2_task_prompt") or lesson.get("task_prompt") or ""
    criteria = lesson.get("step2_expected_criteria") or ""

    system_inst = (
        "Ты — строгий, бескомпромиссный, справедливый и доброжелательный ИИ-тренер по программированию Code Academy.\n"
        "Твоя обязанность — проверить практический код ученика под микроскопом СТРОГО по условию задачи.\n\n"
        "СТРОЖАЙШИЕ ПРАВИЛА ПРОВЕРКИ:\n"
        "1. ТОЧНОЕ СООТВЕТСТВИЕ УСЛОВИЮ ЗАДАЧИ:\n"
        "   - Сравнивай код СТРОГО с поставленной задачей и обязательными критериями.\n"
        "   - Если задача требовала выбрать ВСЕ колонки (SELECT * FROM ...), а ученик написал конкретную колонку (например SELECT facults или SELECT name) — это ГРУБАЯ ОШИБКА! passed ОБЯЗАН быть false!\n"
        "   - Если задача требовала создать таблицу (CREATE TABLE), а ученик выполнил SELECT или забыл поля — passed ОБЯЗАН быть false!\n"
        "   - Если задача требовала определённые типы или значения DEFAULT/NOT NULL, а ученик их пропустил — passed ОБЯЗАН быть false!\n"
        "   - Если код решает совершенно другую задачу или написан наугад — passed ОБЯЗАН быть false!\n"
        "2. РАЗБОР ПО ПУНКТАМ:\n"
        "   Если решение неверно, разбери ошибки доброжелательно и чётко по пунктам:\n"
        "   1. Что требовалось в задании.\n"
        "   2. Что написано у тебя и в чём нестыковка (синтаксис, регистр, кавычки, имена полей/переменных, логика).\n"
        "   3. Наводящая подсказка, как исправить (КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдавать готовый код целиком!).\n"
        "3. ЗАСЧИТЫВАНИЕ (passed = true):\n"
        "   Ставь passed: true ТОЛЬКО если код не содержит ошибок и ДЕЙСТВИТЕЛЬНО решает поставленную задачу целиком. Похвали за точность решения!\n\n"
        "Ответь СТРОГО в формате JSON:\n"
        '{"passed": false/true, "feedback": "Твой детальный разбор по пунктам"}'
    )

    prompt = (
        f"Урок: {lesson['title']} ({lesson.get('stage_title', '')})\n"
        f"Язык: {lesson['language']}\n"
        f"УСЛОВИЕ ЗАДАЧИ:\n{task_prompt}\n\n"
        f"ОБЯЗАТЕЛЬНЫЕ КРИТЕРИИ ПРОВЕРКИ:\n{criteria or 'Код должен точно решать поставленную задачу без ошибок.'}\n\n"
        f"КОД УЧЕНИКА:\n{clean_code}\n\n"
        f"Вывод программы (stdout):\n{stdout_str or '(нет вывода)'}\n\n"
        f"Ошибки выполнения (stderr):\n{stderr_str or '(ошибок нет)'}\n\n"
        "Оцени решение ученика строго по условию и верни JSON {\"passed\": bool, \"feedback\": string}:"
    )

    passed = False
    feedback = ""
    try:
        raw_ai = generate_text(
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.2,
            timeout=35,
        )
        cleaned = str(raw_ai).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            passed = bool(data.get("passed", False))
            feedback = str(data.get("feedback", "")).strip()
        else:
            passed = False
            feedback = "Решение требует доработки: проверьте соответствие кода условию практической задачи."
    except Exception as exc:
        LOGGER.warning("Fallback оценки шага 2: %s", exc)
        passed = False
        if has_runtime_error:
            feedback = f"Код вызвал ошибку выполнения:\n{stderr_str}\n\nИсправьте синтаксис и запустите снова."
        else:
            feedback = "Не удалось автоматически проверить код через ИИ. Убедитесь, что код полностью выполняет условие задачи."

    if has_runtime_error:
        passed = False

    return {
        "passed": passed,
        "feedback": feedback,
        "rule": lesson.get("step2_rule") or "",
    }

# ============================================================================
# РОУТЫ BAHONIQ ACADEMY API
# ============================================================================

@router.get("/roadmap")
async def academy_roadmap_get(request: Request):
    """Возвращает дорожную карту всех 4 этапов, 60 уроков и общий прогресс профиля."""
    pid = _extract_profile_id(request)
    return await run_in_threadpool(get_roadmap_data, pid)


@router.get("/lesson/{lesson_id}")
async def academy_lesson_get(lesson_id: int, request: Request):
    """Возвращает урок с микрошагами 1 и 2, вопросами теста и кодом проекта."""
    pid = _extract_profile_id(request)
    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")
    return lesson


@router.post("/start-lesson")
async def academy_start_lesson_post(request: Request):
    """Старт урока: генерация уникального объяснения и задачи от Gemini Flash в реальном времени с кэшированием в SQLite."""
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = int(body.get("lesson_id") or 1)
    force_refresh = bool(body.get("force_refresh", False))
    stage_id = int(body.get("stage_id") or 1)
    stage_title = str(body.get("stage_title") or f"Этап {stage_id}").strip()
    lesson_title = str(body.get("lesson_title") or "").strip()
    lesson_summary = str(body.get("lesson_summary") or "").strip()

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    if not lesson_title:
        lesson_title = lesson["title"]
    if not lesson_summary:
        lesson_summary = lesson["summary"]
    if not stage_title:
        stage_title = lesson.get("stage_title", f"Этап {lesson['stage_id']}")

    # Проверяем наличие закэшированного сгенерированного ИИ урока
    is_cached = bool(lesson.get("is_ai_generated", 0)) and bool(lesson.get("step1_trap_code"))
    if is_cached and not force_refresh:
        return lesson

    # Генерируем уникальный урок в реальном времени через Gemini Flash
    ai_content = await run_in_threadpool(
        _generate_unique_lesson_content,
        stage_id=stage_id,
        stage_title=stage_title,
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        lesson_summary=lesson_summary,
        language=lesson["language"],
    )

    if ai_content:
        await run_in_threadpool(update_lesson_ai_content, lesson_id, ai_content)
        refreshed = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
        if refreshed:
            lesson = refreshed

    return lesson



@router.post("/step1/evaluate")
async def academy_step1_eval_post(request: Request):
    """Проверка микрошага 1: чтение кода («Поймай ловушку») с живым разбором Gemini Flash."""
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = int(body.get("lesson_id") or 1)
    answer = str(body.get("answer") or "").strip()

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    eval_res = await run_in_threadpool(_evaluate_step1_sync, lesson, answer)
    await run_in_threadpool(
        save_step1_result,
        lesson_id,
        answer,
        eval_res["feedback"],
        eval_res["passed"],
        pid,
    )

    roadmap = await run_in_threadpool(get_roadmap_data, pid)
    updated_lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)

    return {
        "lesson_id": lesson_id,
        "step": 1,
        "passed": eval_res["passed"],
        "feedback": eval_res["feedback"],
        "rule": eval_res.get("rule") or lesson.get("step1_rule", ""),
        "current_step": updated_lesson.get("current_step", 1),
        "roadmap": roadmap,
    }


@router.post("/step2/evaluate")
@router.post("/check")
async def academy_step2_eval_post(request: Request):
    """Проверка микрошага 2: написание кода (запуск + разбор ошибок под микроскопом)."""
    _ensure_code_exec_allowed()
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = int(body.get("lesson_id") or 1)
    user_code = str(body.get("code") or "")
    stdin_str = str(body.get("stdin") or "")

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    exec_res = await run_in_threadpool(
        _execute_lesson_code,
        lesson["language"],
        user_code,
        stdin_str,
    )
    eval_res = await run_in_threadpool(
        _evaluate_step2_sync,
        lesson,
        user_code,
        exec_res,
    )

    await run_in_threadpool(
        save_step2_result,
        lesson_id,
        user_code,
        eval_res["feedback"],
        eval_res["passed"],
        pid,
    )

    roadmap = await run_in_threadpool(get_roadmap_data, pid)
    updated_lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)

    return {
        "lesson_id": lesson_id,
        "step": 2,
        "passed": eval_res["passed"],
        "feedback": eval_res["feedback"],
        "rule": eval_res.get("rule") or lesson.get("step2_rule", ""),
        "stdout": exec_res["stdout"],
        "stderr": exec_res["stderr"],
        "returncode": exec_res["returncode"],
        "current_step": updated_lesson.get("current_step", 2),
        "roadmap": roadmap,
    }


@router.post("/quiz/submit")
async def academy_quiz_submit_post(request: Request):
    """Проверка ответов интерактивного теста из 5 вопросов и зачёт урока."""
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = int(body.get("lesson_id") or 1)
    answers = body.get("answers") or {}  # формат {"0": 1, "1": 0, ...}

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    quiz_items = lesson.get("quiz_data") or []
    if not quiz_items:
        raise HTTPException(400, "Для данного урока тест не настроен.")

    try:
        score = 0
        detailed: list[dict[str, Any]] = []
        for idx, q in enumerate(quiz_items):
            user_choice = answers.get(str(idx))
            if user_choice is None:
                user_choice = answers.get(idx)
            try:
                user_choice_int = int(user_choice) if user_choice is not None else -1
            except (ValueError, TypeError):
                user_choice_int = -1
            try:
                correct_idx = int(q.get("correct_index", 0))
            except (ValueError, TypeError):
                correct_idx = 0
            is_correct = (user_choice_int == correct_idx)
            if is_correct:
                score += 1
            detailed.append({
                "question_index": idx,
                "user_choice": user_choice_int,
                "correct_index": correct_idx,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
            })

        # Тест засчитывается при результате 4 из 5 или 5 из 5 (>= 80%)
        passed = score >= 4
        await run_in_threadpool(save_quiz_result, lesson_id, score, passed, pid)
        roadmap = await run_in_threadpool(get_roadmap_data, pid)
        stable_id = lesson.get("stable_id") or f"python_{lesson_id:02d}_{lesson.get('slug', '').replace('-', '_')}"

        return {
            "lesson_id": lesson_id,
            "stable_id": stable_id,
            "score": score,
            "total": len(quiz_items),
            "passed": passed,
            "detailed": detailed,
            "next_lesson_id": lesson.get("next_lesson_id"),
            "next_lesson_title": lesson.get("next_lesson_title"),
            "roadmap": roadmap,
        }
    except Exception as exc:
        LOGGER.exception("Failed to check academy quiz for lesson %s: %s", lesson_id, exc)
        raise HTTPException(500, f"Ошибка при проверке теста на сервере: {exc}")


@router.post("/progress/sync")
async def academy_progress_sync_post(request: Request):
    """
    Двусторонняя синхронизация прогресса с клиентом:
    Принимает completed_ids (стабильные ID или числовые ID) из localStorage браузера
    и фиксирует их в SQLite БД, возвращая актуальный роадмап.
    """
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    completed_ids = body.get("completed_ids") or []
    if isinstance(completed_ids, str):
        try:
            completed_ids = json.loads(completed_ids)
        except Exception:
            completed_ids = [completed_ids]
    res = await run_in_threadpool(sync_completed_lessons, completed_ids, pid)
    return res


@router.post("/progress/mark")
async def academy_progress_mark_post(request: Request):
    """
    Административная / пользовательская отметка урока как завершённого
    (ручное восстановление прогресса по ID или stable_id).
    """
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = body.get("lesson_id") or body.get("id") or body.get("stable_id")
    if not lesson_id:
        raise HTTPException(400, "Параметр lesson_id обязателен.")
    res = await run_in_threadpool(mark_lesson_completed, lesson_id, 5, pid)
    return res


@router.post("/mentor-ask")
async def academy_mentor_ask_post(request: Request):
    """Живой диалог со свободным ИИ-тренером Code Academy (любые вопросы по программированию и текущему уроку)."""
    body = await _parse_body(request)
    pid = _extract_profile_id(request, body)
    lesson_id = int(body.get("lesson_id") or 1)
    question = str(body.get("question") or "").strip()
    current_code = str(body.get("code") or "").strip()
    current_output = str(body.get("output") or "").strip()
    theory_override = str(body.get("theory") or "").strip()
    trap_override = str(body.get("trap_code") or "").strip()
    task_override = str(body.get("task_prompt") or "").strip()
    history = body.get("history") or []

    if not question:
        raise HTTPException(400, "Введите вопрос для ИИ-тренера.")

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id, pid)
    lesson_ctx = ""
    if lesson:
        stage_title = lesson.get("stage_title") or f"Этап {lesson.get('stage_id', 1)}"
        lesson_title = lesson.get("title", "")
        lesson_summary = lesson.get("summary", "")
        step1_concept = theory_override or lesson.get("step1_concept", "") or lesson.get("ai_theory", "")
        step1_trap = trap_override or lesson.get("step1_trap_code", "")
        task_prompt = task_override or lesson.get("step2_task_prompt", "") or lesson.get("task_prompt", "")

        lesson_ctx = (
            f"Текущий этап: {stage_title}\n"
            f"Тема урока: {lesson_title}\n"
            f"Суть темы: {lesson_summary}\n"
        )
        if step1_concept:
            lesson_ctx += f"Теория шага 1: {step1_concept[:600]}\n"
        if step1_trap:
            lesson_ctx += f"Код ловушки/примера в уроке:\n{step1_trap}\n"
        if task_prompt:
            lesson_ctx += f"Практическое задание урока: {task_prompt}\n"

    history_ctx = ""
    if isinstance(history, list) and history:
        items = []
        for h in history[-6:]:
            if isinstance(h, dict):
                role = "Ученик" if h.get("role") == "user" else "ИИ-тренер"
                txt = (h.get("text") or "").strip()
                if txt:
                    items.append(f"{role}: {txt}")
        if items:
            history_ctx = "Предыдущие реплики диалога в этом уроке:\n" + "\n".join(items) + "\n\n"

    system_inst = (
        "Ты — персональный ИИ-тренер по программированию в Code Academy.\n"
        "Ученик может задать тебе АБСОЛЮТНО ЛЮБОЙ ВОПРОС: по Python, SQL, архитектуре ПО, синтаксису, библиотекам, "
        "алгоритмам, структурам данных или деталям текущего урока.\n\n"
        "ПРАВИЛА И СТИЛЬ ОТВЕТА:\n"
        "1. Отвечай доходчиво, доброжелательно, живым человеческим языком без сухой академической воды.\n"
        "2. Всегда приводи короткие, наглядные и рабочие примеры кода с комментариями к каждой строке.\n"
        "3. Если вопрос касается темы или кода текущего урока — учитывай его контекст и код ученика на экране.\n"
        "4. Если ученик спрашивает общую тему или концепт программирования (например: разница import и from ... import, "
        "ООП, декораторы, SQL JOIN, архитектурные паттерны) — дай исчерпывающее, доступное объяснение с простыми аналогиями и примером кода.\n"
        "5. Если ученик просит решить за него практическое задание урока целиком — не давай готовое решение в лоб, "
        "а дай наводящую подсказку и покажи принцип на похожем абстрактном примере.\n"
        "6. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО называть любые технические имена моделей или компаний (никаких Gemini, Flash, Ollama, OpenAI и т.п.). "
        "Ты — персональный ИИ-тренер Code Academy."
    )

    prompt = (
        f"КОНТЕКСТ ТЕКУЩЕГО УРОКА УЧЕНИКА:\n"
        f"{lesson_ctx or '(информация об уроке отсутствует)'}\n"
        f"Код в редакторе ученика сейчас:\n{current_code or '(редактор пуст)'}\n\n"
        f"Вывод консоли:\n{current_output or '(нет вывода)'}\n\n"
        f"{history_ctx}"
        f"ВОПРОС УЧЕНИКА:\n{question}"
    )

    try:
        answer = await run_in_threadpool(
            generate_text,
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.35,
            timeout=35,
        )
        return {"answer": str(answer).strip()}
    except Exception as exc:
        raise HTTPException(400, f"Ошибка ИИ-тренера: {exc}") from exc


@router.get("/export-pdf")
@router.post("/export-pdf")
async def academy_export_pdf():
    """Генерирует и отдаёт персональную PDF-книгу «От А до Я: Архитектура BahonIQ Work Center»."""
    try:
        pdf_bytes = await run_in_threadpool(build_academy_pdf_book)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="BahonIQ_Architecture_Book_A_to_Z.pdf"',
                "Cache-Control": "no-store",
            },
        )
    except Exception as exc:
        LOGGER.error("Ошибка генерации PDF-книги Academy: %s", exc)
        raise HTTPException(400, f"Ошибка генерации PDF-книги: {exc}") from exc
