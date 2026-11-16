"""API Design Academy Studio."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ai_service import generate_text
from ..modules.design_academy_studio.curriculum import get_curriculum, get_lesson
from ..modules.design_academy_studio.validation import validate_document

router = APIRouter(prefix="/api/design-academy", tags=["Design Academy Studio"])


@router.get("/curriculum")
def curriculum() -> dict:
    return get_curriculum()


@router.get("/lesson/{lesson_id}")
def lesson(lesson_id: str) -> dict:
    item = get_lesson(lesson_id)
    if not item:
        raise HTTPException(404, "Урок не найден")
    return item


@router.post("/validate/{lesson_id}")
async def validate(lesson_id: str, request: Request) -> dict:
    item = get_lesson(lesson_id)
    if not item:
        raise HTTPException(404, "Урок не найден")
    body = await request.json()
    return validate_document(body.get("document", {}), item.get("checks", []))


def _mentor_sync(item: dict[str, Any], mode: str, question: str, document: dict[str, Any], validation: dict[str, Any]) -> dict:
    compact_objects = [{k: obj.get(k) for k in ("name", "type", "x", "y", "width", "height", "fill", "stroke", "radius", "opacity", "fontSize")} for obj in document.get("objects", [])[:60]]
    prompt = f"""Урок: {item['title']}\nЦель: {item['task']}\nРежим помощи: {mode}\nВопрос ученика: {question or 'Разбери мою работу'}\nОбъекты: {json.dumps(compact_objects, ensure_ascii=False)}\nРезультат технической проверки: {json.dumps(validation, ensure_ascii=False)}\nДай короткий конкретный ответ. Опирайся только на переданные параметры. Не рисуй работу за ученика и не выдумывай отсутствующие свойства."""
    try:
        answer = generate_text(prompt=prompt, system_instruction="Ты — доброжелательный, но точный наставник Design Academy Studio по UI/UX и Figma. Сначала объясни проблему, затем дай один следующий шаг.", temperature=.25, timeout=35)
        return {"answer": str(answer).strip(), "provider": "AI-наставник"}
    except Exception:
        failed = [x["message"] for x in validation.get("results", []) if not x.get("passed")]
        fallback = "Начните с требования урока и проверьте свойства выделенного объекта."
        if failed:
            fallback = "Сейчас стоит исправить: " + failed[0] + ". После этого повторите проверку."
        return {"answer": fallback, "provider": "Локальная подсказка"}


@router.post("/mentor/{lesson_id}")
async def mentor(lesson_id: str, request: Request) -> dict:
    item = get_lesson(lesson_id)
    if not item:
        raise HTTPException(404, "Урок не найден")
    body = await request.json()
    document = body.get("document", {})
    validation = validate_document(document, item.get("checks", []))
    return await run_in_threadpool(_mentor_sync, item, str(body.get("mode", "hint")), re.sub(r"\s+", " ", str(body.get("question", "")))[:1200], document, validation)
