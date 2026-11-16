# -*- coding: utf-8 -*-
"""Роутер BahonIQ Academy (FastAPI + Gemini Flash 24/7 + SQLite + PDF-книга От А до Я)."""

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
    """Запускает Python-код или SQL-запрос в изолированной учебной среде и возвращает вывод/ошибки."""
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


def _generate_live_theory_sync(lesson: dict[str, Any]) -> str:
    """Генерирует живое, понятное объяснение темы через Gemini Flash на жизненных аналогиях."""
    system_inst = (
        "Ты — живой, дружелюбный ИИ-наставник BahonIQ Academy. "
        "Объясняй тему простым человеческим языком без скучной академической воды: "
        "используй понятные аналогии из жизни и работы университетского IT-центра BahonIQ / АИС Platonus, "
        "покажи короткий и наглядный пример кода и объясни каждую строчку."
    )
    repo_ctx = ""
    if lesson.get("repo_source_preview"):
        repo_ctx = f"\n\nФрагмент реального файла проекта ({lesson.get('file_path')}):\n{lesson['repo_source_preview'][:2200]}"

    prompt = (
        f"Этап: {lesson['stage_title']}\n"
        f"Тема урока: {lesson['title']}\n"
        f"Краткая суть: {lesson['summary']}\n"
        f"Практическая задача урока: {lesson['task_prompt']}"
        f"{repo_ctx}\n\n"
        "Сгенерируй живое, увлекательное объяснение этой темы (3-4 коротких абзаца + короткий пример кода в блоке ```), "
        "чтобы ученик с первого раза понял суть и легко решил практическую задачу."
    )
    text = generate_text(
        prompt=prompt,
        system_instruction=system_inst,
        temperature=0.35,
        timeout=35,
    )
    return str(text).strip()


def _mentor_evaluate_code_sync(
    lesson: dict[str, Any],
    user_code: str,
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    """Умная проверка кода и разбор ошибок через Gemini Flash."""
    stdout_str = (exec_result.get("stdout") or "").strip()
    stderr_str = (exec_result.get("stderr") or "").strip()
    has_runtime_error = bool(stderr_str) or exec_result.get("returncode", 0) != 0

    system_inst = (
        "Ты — опытный и поддерживающий ИИ-ментор курса программирования BahonIQ Academy. "
        "Твоя задача — проверить код ученика по условию урока.\n"
        "ПРАВИЛА ПРОВЕРКИ:\n"
        "1. Если в коде есть синтаксическая или логическая ошибка (или условие задачи не выполнено): "
        "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдавать готовый правильный код целиком! "
        "По-человечески объясни, в какой строке и почему произошел сбой, разжуй логику и дай наводящую подсказку, "
        "чтобы ученик исправил ошибку сам.\n"
        "2. Если решение верное и выводит ожидаемый результат: искренне похвали ученика, коротко покажи, "
        "почему его решение работает хорошо (или как можно сделать код ещё чище), и поздравь с прохождением темы.\n"
        "Ответь СТРОГО в формате JSON без обёрток ```json:\n"
        '{"passed": true/false, "feedback": "Подробный живой ответ ментора на русском языке"}'
    )

    prompt = (
        f"Урок: {lesson['title']} ({lesson['stage_title']})\n"
        f"Язык: {lesson['language']}\n"
        f"Условие задачи:\n{lesson['task_prompt']}\n\n"
        f"Код пользователя:\n{user_code}\n\n"
        f"Вывод программы (stdout):\n{stdout_str or '(пусто)'}\n\n"
        f"Ошибки выполнения (stderr):\n{stderr_str or '(ошибок нет)'}\n\n"
        "Оцени решение и верни JSON {\"passed\": ..., \"feedback\": \"...\"}:"
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
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(cleaned[start : end + 1])
            passed = bool(parsed.get("passed", False))
            feedback = str(parsed.get("feedback", "")).strip()
        else:
            feedback = cleaned
            passed = (not has_runtime_error) and bool(stdout_str)
    except Exception as exc:
        LOGGER.warning("Fallback проверки ментора: %s", exc)
        if has_runtime_error:
            passed = False
            feedback = (
                f"При выполнении кода возникла ошибка:\n`{stderr_str}`\n\n"
                f"**Подсказка ментора:** {lesson.get('expected_hint') or 'Проверьте синтаксис и названия переменных.'}"
            )
        elif not stdout_str:
            passed = False
            feedback = (
                "Код выполнился без ошибок, но ничего не вывел на экран.\n\n"
                f"**Подсказка ментора:** {lesson.get('expected_hint') or 'Используйте print() или SELECT для вывода результата.'}"
            )
        else:
            passed = True
            feedback = (
                f"Отличная работа! Код выполнился корректно и вывел результат:\n`{stdout_str}`\n\n"
                "Урок засчитан — можешь переходить к следующей теме!"
            )

    # Дополнительная страховка: если была явная ошибка интерпретатора Python/SQL, урок не может быть засчитан
    if has_runtime_error:
        passed = False

    return {"passed": passed, "feedback": feedback}


@router.get("/roadmap")
async def academy_roadmap_get():
    """Возвращает структуру всех 4 этапов, список уроков и прогресс пользователя."""
    return await run_in_threadpool(get_roadmap_data)


@router.get("/lesson/{lesson_id}")
async def academy_lesson_get(lesson_id: int, regenerate: bool = False):
    """Возвращает данные конкретного урока и его живую теорию."""
    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден.")
    if regenerate:
        try:
            fresh_theory = await run_in_threadpool(_generate_live_theory_sync, lesson)
            if fresh_theory:
                await run_in_threadpool(save_lesson_theory, lesson_id, fresh_theory)
                lesson["ai_theory"] = fresh_theory
        except Exception as exc:
            LOGGER.warning("Не удалось перегенерировать теорию урока %d: %s", lesson_id, exc)
    return lesson


@router.post("/lesson")
async def academy_lesson_post(request: Request):
    """Получение или генерация живого объяснения урока через Gemini Flash."""
    body = await _parse_body(request)
    lesson_id = int(body.get("lesson_id") or 1)
    regenerate = bool(body.get("regenerate", False))
    return await academy_lesson_get(lesson_id, regenerate=regenerate)


@router.post("/check")
async def academy_check_post(request: Request):
    """Умная проверка кода с ИИ-ментором (запуск кода + разбор ошибок или зачёт урока в SQLite)."""
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
        _mentor_evaluate_code_sync,
        lesson,
        user_code,
        exec_res,
    )

    passed = eval_res["passed"]
    feedback = eval_res["feedback"]

    await run_in_threadpool(save_user_attempt, lesson_id, user_code, feedback, passed)
    roadmap = await run_in_threadpool(get_roadmap_data)

    return {
        "lesson_id": lesson_id,
        "passed": passed,
        "feedback": feedback,
        "stdout": exec_res["stdout"],
        "stderr": exec_res["stderr"],
        "returncode": exec_res["returncode"],
        "next_lesson_id": lesson.get("next_lesson_id"),
        "next_lesson_title": lesson.get("next_lesson_title"),
        "roadmap": roadmap,
    }


@router.post("/mentor-ask")
async def academy_mentor_ask_post(request: Request):
    """Встроенный контекстный чат «Задать вопрос по уроку» (видит текущую тему, задачу и код на экране)."""
    body = await _parse_body(request)
    lesson_id = int(body.get("lesson_id") or 1)
    question = str(body.get("question") or "").strip()
    current_code = str(body.get("code") or "").strip()
    current_output = str(body.get("output") or "").strip()

    if not question:
        raise HTTPException(400, "Введите вопрос для ИИ-ментора.")

    lesson = await run_in_threadpool(get_lesson_by_id, lesson_id)
    lesson_ctx = ""
    if lesson:
        lesson_ctx = (
            f"Текущий этап: {lesson['stage_title']}\n"
            f"Текущий урок: {lesson['title']}\n"
            f"Задание урока: {lesson['task_prompt']}\n"
        )

    system_inst = (
        "Ты — персональный ИИ-ментор BahonIQ Academy. Ученик задаёт вопрос прямо во время выполнения урока. "
        "Отвечай дружелюбно, понятно, на живых примерах, строго в контексте текущего урока и кода ученика. "
        "Не решай всю задачу за ученика, но ясно объясни нужную концепцию или синтаксис."
    )
    prompt = (
        f"{lesson_ctx}\n"
        f"Код ученика сейчас на экране:\n{current_code or '(пусто)'}\n\n"
        f"Вывод консоли:\n{current_output or '(нет вывода)'}\n\n"
        f"Вопрос ученика: {question}"
    )

    try:
        answer = await run_in_threadpool(
            generate_text,
            prompt=prompt,
            system_instruction=system_inst,
            temperature=0.3,
            timeout=35,
        )
        return {"answer": str(answer).strip()}
    except Exception as exc:
        raise HTTPException(400, f"Не удалось получить ответ ментора: {exc}") from exc


@router.get("/export-pdf")
@router.post("/export-pdf")
async def academy_export_pdf():
    """Генерирует и отдаёт персональную PDF-книгу «От А до Я: Python, SQL и Архитектура BahonIQ»."""
    try:
        pdf_bytes = await run_in_threadpool(build_academy_pdf_book)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="BahonIQ_Academy_Book_A_to_Z.pdf"',
                "Cache-Control": "no-store",
            },
        )
    except Exception as exc:
        LOGGER.error("Ошибка генерации PDF-книги Academy: %s", exc)
        raise HTTPException(400, f"Ошибка генерации PDF-книги: {exc}") from exc
