# -*- coding: utf-8 -*-
"""Роутер BahonIQ Academy (FastAPI + Gemini Flash 24/7 + 60 уроков + микрошаги + тесты + PDF-книга)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ai_service import generate_text
from ..modules.code_academy.db import (
    get_lesson_by_id,
    get_roadmap_data,
    save_lesson_theory,
    save_quiz_result,
    save_step1_result,
    save_step2_result,
    save_user_attempt,
)
from ..modules.code_academy.pathway import run_sql
from ..modules.code_academy.pdf_book_generator import build_academy_pdf_book
from ..modules.code_academy.python_runtime import execute_python

LOGGER = logging.getLogger("bahoniq.routers.academy")

router = APIRouter(prefix="/api/academy", tags=["BahonIQ Academy"])


async def _parse_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    return dict(form)


def _execute_lesson_code(language: str, code: str, stdin: str = "") -> dict[str, Any]:
    """Запускает Python-код или SQL-запрос в изолированной учебной среде."""
    clean_code = (code or "").strip()
    if not clean_code:
        return {"stdout": "", "stderr": "Код пуст. Напишите решение в редакторе.", "returncode": 1}

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
        return {
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
            "returncode": res.returncode if res.returncode is not None else 0,
        }
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "returncode": 1}


# ============================================================================
# ОЦЕНКА МИКРОШАГА 1: ЧТЕНИЕ КОДА («ПОЙМАЙ ЛОВУШКУ»)
# ============================================================================

def _evaluate_step1_sync(lesson: dict[str, Any], user_answer: str) -> dict[str, Any]:
    """Оценивает понимание учеником чтения кода и ловушки через Gemini Flash."""
    clean_answer = (user_answer or "").strip()
    if not clean_answer:
        return {
            "passed": False,
            "feedback": "Напишите своими словами, что выведет этот код на экран и почему.",
            "rule": lesson.get("step1_rule") or "",
        }

    system_inst = (
        "Ты — проницательный, дружелюбный и внимательный ИИ-тренер BahonIQ Academy. "
        "Ученик выполняет микрошаг Типа А («Чтение кода / Поймай ловушку»). "
        "Он должен был понять, что выведет код на экран и в чём подвох/механика.\n\n"
        "ПРАВИЛА ОЦЕНКИ ПОД МИКРОСКОПОМ:\n"
        "1. Если ученик понял суть и ответил в целом правильно: "
        "похвали его живой короткой фразой (1-2 предложения) и подтверди правильность вывода.\n"
        "2. Если ученик ошибся или не заметил подвох (например, перепутал строку и число, забыл про регистр, не понял кавычки): "
        "НЕ РУГАЙ и НЕ ВЫДАВАЙ готовый правильный ответ целиком! "
        "Мягко укажи, на какую именно деталь обратить внимание (например: «Посмотри внимательно на кавычки во второй строке — это текст или переменная?»), "
        "и попроси подумать ещё разок.\n"
        "Ответь СТРОГО в формате JSON:\n"
        '{"passed": true/false, "feedback": "Твой живой дружелюбный разбор ответа ученика"}'
    )

    prompt = (
        f"Тема урока: {lesson['title']}\n"
        f"Код ловушки:\n{lesson.get('step1_trap_code')}\n\n"
        f"Вопрос тренера:\n{lesson.get('step1_trap_question')}\n\n"
        f"Эталонный смысл правильного ответа:\n{lesson.get('step1_trap_expected')}\n\n"
        f"Ответ ученика:\n{clean_answer}\n\n"
        "Оцени ответ ученика и верни JSON {\"passed\": bool, \"feedback\": string}:"
    )

    passed = False
    feedback = ""
    try:
        raw_ai = generate_text(
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.25,
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
            feedback = cleaned
            passed = len(clean_answer) >= 15
    except Exception as exc:
        LOGGER.warning("Ошибка оценки шага 1 через Gemini: %s", exc)
        passed = len(clean_answer) >= 15
        feedback = (
            "Отличный ответ! Ты уловил суть механики."
            if passed
            else "Попробуй описать чуть подробнее: что появится на экране при выполнении этих строк?"
        )

    return {
        "passed": passed,
        "feedback": feedback,
        "rule": lesson.get("step1_rule") or "",
    }


# ============================================================================
# ОЦЕНКА МИКРОШАГА 2: НАПИСАНИЕ КОДА (ПРАКТИКА)
# ============================================================================

def _evaluate_step2_sync(
    lesson: dict[str, Any],
    user_code: str,
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    """Оценка написанного кода ученика через запуск + разбор Gemini Flash под микроскопом."""
    stdout_str = (exec_result.get("stdout") or "").strip()
    stderr_str = (exec_result.get("stderr") or "").strip()
    has_runtime_error = bool(stderr_str) or exec_result.get("returncode", 0) != 0

    system_inst = (
        "Ты — опытный, чуткий и поддерживающий ИИ-ментор курса программирования BahonIQ Academy. "
        "Твоя задача — оценить практический код ученика на микрошаге 2.\n\n"
        "ПРАВИЛА ОЦЕНКИ ПОД МИКРОСКОПОМ:\n"
        "1. Если в коде есть синтаксическая или логическая ошибка: "
        "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдавать готовый правильный код целиком! "
        "По-человечески разбери ошибку под микроскопом (несовпадение регистра, опечатка в имени, кавычки вместо числа, двоеточие, отступ), "
        "объясни на пальцах и дай точную наводящую подсказку для исправления.\n"
        "2. Если решение верное: искренне похвали ученика, отметь чистоту решения и подчеркни ключевое правило темы.\n"
        "Ответь СТРОГО в формате JSON:\n"
        '{"passed": true/false, "feedback": "Твой живой разбор кода ученика"}'
    )

    prompt = (
        f"Урок: {lesson['title']} ({lesson.get('stage_title', '')})\n"
        f"Язык: {lesson['language']}\n"
        f"Задание шага 2:\n{lesson.get('step2_task_prompt') or lesson.get('task_prompt')}\n\n"
        f"Код ученика:\n{user_code}\n\n"
        f"Вывод программы (stdout):\n{stdout_str or '(нет вывода)'}\n\n"
        f"Ошибки выполнения (stderr):\n{stderr_str or '(ошибок нет)'}\n\n"
        "Оцени решение и верни JSON {\"passed\": bool, \"feedback\": string}:"
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
            feedback = cleaned
            passed = (not has_runtime_error) and bool(stdout_str)
    except Exception as exc:
        LOGGER.warning("Fallback оценки шага 2: %s", exc)
        if has_runtime_error:
            passed = False
            feedback = f"Код вызвал ошибку выполнения:\n{stderr_str}\n\nПроверьте названия переменных и синтаксис."
        elif not stdout_str:
            passed = False
            feedback = "Код выполнился, но ничего не вывел. Добавьте вызов print() или SELECT для отображения результата."
        else:
            passed = True
            feedback = f"Отличная работа! Код успешно вывел результат:\n{stdout_str}"

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
async def academy_roadmap_get():
    """Возвращает дорожную карту всех 4 этапов, 60 уроков и общий прогресс."""
    return await run_in_threadpool(get_roadmap_data)


@router.get("/lesson/{lesson_id}")
async def academy_lesson_get(lesson_id: int):
    """Возвращает урок с микрошагами 1 и 2, вопросами теста и кодом проекта."""
    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")
    return lesson


@router.post("/step1/evaluate")
async def academy_step1_eval_post(request: Request):
    """Проверка микрошага 1: чтение кода («Поймай ловушку») с живым разбором Gemini Flash."""
    body = await _parse_body(request)
    lesson_id = int(body.get("lesson_id") or 1)
    answer = str(body.get("answer") or "").strip()

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    eval_res = await run_in_threadpool(_evaluate_step1_sync, lesson, answer)
    await run_in_threadpool(
        save_step1_result,
        lesson_id,
        answer,
        eval_res["feedback"],
        eval_res["passed"],
    )

    roadmap = await run_in_threadpool(get_roadmap_data)
    updated_lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)

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
    body = await _parse_body(request)
    lesson_id = int(body.get("lesson_id") or 1)
    user_code = str(body.get("code") or "")
    stdin_str = str(body.get("stdin") or "")

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
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
    )

    roadmap = await run_in_threadpool(get_roadmap_data)
    updated_lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)

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
    lesson_id = int(body.get("lesson_id") or 1)
    answers = body.get("answers") or {}  # формат {"0": 1, "1": 0, ...}

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")

    quiz_items = lesson.get("quiz_data") or []
    if not quiz_items:
        raise HTTPException(400, "Для данного урока тест не настроен.")

    score = 0
    detailed: list[dict[str, Any]] = []
    for idx, q in enumerate(quiz_items):
        user_choice = answers.get(str(idx))
        if user_choice is None:
            user_choice = answers.get(idx)
        user_choice_int = int(user_choice) if user_choice is not None else -1
        correct_idx = int(q.get("correct_index", 0))
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
    await run_in_threadpool(save_quiz_result, lesson_id, score, passed)
    roadmap = await run_in_threadpool(get_roadmap_data)

    return {
        "lesson_id": lesson_id,
        "score": score,
        "total": len(quiz_items),
        "passed": passed,
        "detailed": detailed,
        "next_lesson_id": lesson.get("next_lesson_id"),
        "next_lesson_title": lesson.get("next_lesson_title"),
        "roadmap": roadmap,
    }


@router.post("/mentor-ask")
async def academy_mentor_ask_post(request: Request):
    """Живой диалог с ИИ-ментором по уроку (контекстный ответ без раскрытия спойлеров)."""
    body = await _parse_body(request)
    lesson_id = int(body.get("lesson_id") or 1)
    question = str(body.get("question") or "").strip()
    current_code = str(body.get("code") or "").strip()

    if not question:
        raise HTTPException(400, "Введите вопрос для наставника.")

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    lesson_ctx = ""
    if lesson:
        lesson_ctx = (
            f"Тема: {lesson['title']} ({lesson.get('stage_title', '')})\n"
            f"Суть: {lesson['summary']}\n"
            f"Шаг 1: {lesson.get('step1_concept', '')}\n"
            f"Шаг 2: {lesson.get('step2_concept', '')}\n"
        )

    system_inst = (
        "Ты — персональный ИИ-ментор BahonIQ Academy (Gemini Flash 24/7). "
        "Ученик задаёт вопрос во время изучения урока. "
        "Отвечай дружелюбно, на простых примерах из жизни или проекта BahonIQ. "
        "НЕ РЕШАЙ ВСЮ ЗАДАЧУ ЗА НЕГО, но понятно объясни механику."
    )
    prompt = (
        f"{lesson_ctx}\n"
        f"Код на экране ученика:\n{current_code or '(пусто)'}\n\n"
        f"Вопрос ученика: {question}"
    )

    try:
        answer = await run_in_threadpool(
            generate_text,
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.3,
            timeout=30,
        )
        return {"answer": str(answer).strip()}
    except Exception as exc:
        raise HTTPException(400, f"Ошибка ментора: {exc}") from exc


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
