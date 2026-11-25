# -*- coding: utf-8 -*-
"""FastAPI роутер модуля English Academy Studio (/api/english-academy/*)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..modules.english_academy.curriculum import (
    DIALOGUES,
    get_curriculum_payload,
    get_lesson_by_id,
)
from ..modules.english_academy.engine import (
    build_progress_report,
    complete_lesson_attempt,
    create_default_state,
    export_progress_bundle,
    get_vocabulary_items,
    import_progress_bundle,
    load_state,
    record_exercise_attempt,
    review_vocab_word,
    save_state,
    toggle_hard_word,
    touch_study_activity,
)
from ..modules.english_academy.tutor import ask_english_tutor

router = APIRouter(prefix="/api/english-academy", tags=["English Academy Studio"])


@router.get("/bootstrap")
def bootstrap() -> dict[str, Any]:
    """Единая точка начальной загрузки курса, прогресса и настроек."""
    state = load_state()
    report = build_progress_report(state)
    return {
        "curriculum": get_curriculum_payload(),
        "state": state,
        "progress": report,
        "vocabulary": get_vocabulary_items(state, mode="all"),
    }


@router.get("/lesson/{lesson_id}")
def get_lesson_endpoint(lesson_id: str) -> dict[str, Any]:
    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден")
    state = load_state()
    report = build_progress_report(state)
    unlocked = report["unlock_map"].get(lesson_id, False)
    return {
        "lesson": lesson,
        "unlocked": unlocked,
        "record": state.get("lessons", {}).get(lesson_id),
    }


@router.post("/exercise/check")
async def check_exercise_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    lesson_id = str(body.get("lesson_id") or "")
    exercise_id = str(body.get("exercise_id") or "")
    attempt = max(1, int(body.get("attempt", 1) or 1))
    reveal = bool(body.get("reveal", False))
    user_answer = body.get("answer")

    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден")

    exercise = next((ex for ex in lesson.get("exercises", []) if ex["id"] == exercise_id), None)
    if not exercise:
        raise HTTPException(404, "Упражнение не найдено")

    state = load_state()
    result = record_exercise_attempt(
        state=state,
        lesson_id=lesson_id,
        exercise=exercise,
        user_answer=user_answer,
        attempt=attempt,
        reveal=reveal,
    )
    saved = save_state(state)
    return {
        "result": result,
        "progress": build_progress_report(saved),
        "mistakes": saved["mistakes"],
    }


@router.post("/lesson/complete")
async def complete_lesson_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    lesson_id = str(body.get("lesson_id") or "")
    exercise_results = body.get("exercise_results")
    spent_seconds = int(body.get("spent_seconds", 120) or 120)
    if not isinstance(exercise_results, dict):
        exercise_results = {}

    state = load_state()
    try:
        outcome = complete_lesson_attempt(
            state=state,
            lesson_id=lesson_id,
            exercise_results=exercise_results,
            spent_seconds=spent_seconds,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except PermissionError as exc:
        raise HTTPException(403, str(exc))

    saved = save_state(state)
    return {
        "outcome": outcome,
        "state": saved,
        "progress": build_progress_report(saved),
        "vocabulary": get_vocabulary_items(saved, mode="all"),
    }


@router.get("/vocabulary")
def list_vocabulary(mode: str = "all", level: str = "", topic: str = "", q: str = "") -> dict[str, Any]:
    state = load_state()
    items = get_vocabulary_items(state, mode=mode, level=level, topic=topic, query=q)
    return {
        "items": items,
        "summary": build_progress_report(state)["vocab_summary"],
    }


@router.post("/vocabulary/review")
async def review_vocabulary_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    word_id = str(body.get("word_id") or "")
    knew_it = bool(body.get("knew_it", False))
    state = load_state()
    try:
        item = review_vocab_word(state, word_id, knew_it)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    saved = save_state(state)
    return {
        "word": item,
        "progress": build_progress_report(saved),
    }


@router.post("/vocabulary/hard")
async def toggle_hard_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    word_id = str(body.get("word_id") or "")
    state = load_state()
    try:
        item = toggle_hard_word(state, word_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    saved = save_state(state)
    return {
        "word": item,
        "progress": build_progress_report(saved),
    }


@router.post("/dialogue/complete")
async def complete_dialogue_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    dlg_id = str(body.get("dialogue_id") or "")
    if not any(d["id"] == dlg_id for d in DIALOGUES):
        raise HTTPException(404, "Диалог не найден")
    state = load_state()
    if dlg_id not in state["dialogues_done"]:
        state["dialogues_done"].append(dlg_id)
    state["skill_stats"]["speaking"]["total"] += 1
    state["skill_stats"]["speaking"]["correct"] += 1
    touch_study_activity(state, add_seconds=60)
    saved = save_state(state)
    return {
        "dialogues_done": saved["dialogues_done"],
        "progress": build_progress_report(saved),
    }


@router.post("/mistakes/resolve")
async def resolve_mistake_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    mistake_id = str(body.get("mistake_id") or "")
    answer = body.get("answer")
    state = load_state()
    m = next((x for x in state["mistakes"] if x["id"] == mistake_id), None)
    if not m:
        raise HTTPException(404, "Запись об ошибке не найдена")

    lesson = get_lesson_by_id(m["lesson_id"])
    exercise = next((ex for ex in (lesson or {}).get("exercises", []) if ex["id"] == m["exercise_id"]), None)
    if not exercise:
        m["resolved"] = True
        saved = save_state(state)
        return {"correct": True, "resolved": True, "mistakes": saved["mistakes"], "progress": build_progress_report(saved)}

    res = record_exercise_attempt(state, m["lesson_id"], exercise, answer, attempt=2, reveal=True)
    if res["correct"]:
        m["resolved"] = True
        m["clean_streak"] = max(2, int(m.get("clean_streak", 0)))
    saved = save_state(state)
    return {
        "correct": res["correct"],
        "feedback": res["feedback"],
        "resolved": bool(m.get("resolved")),
        "mistakes": saved["mistakes"],
        "progress": build_progress_report(saved),
    }


@router.post("/tutor")
async def tutor_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    mode = str(body.get("mode") or "chat")
    message = str(body.get("message") or "")[:2000]
    lesson_id = str(body.get("lesson_id") or "")
    force_offline = bool(body.get("force_offline", False))

    state = load_state()
    reply = await run_in_threadpool(
        ask_english_tutor,
        state,
        mode,
        message,
        lesson_id,
        force_offline,
    )
    touch_study_activity(state, add_seconds=15)
    save_state(state)
    return reply


@router.post("/settings")
async def update_settings_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    state = load_state()
    if isinstance(body, dict):
        state["settings"] = {**state.get("settings", {}), **body}
    saved = save_state(state)
    return {"settings": saved["settings"], "progress": build_progress_report(saved)}


@router.get("/export")
def export_endpoint() -> dict[str, Any]:
    state = load_state()
    return export_progress_bundle(state)


@router.post("/import")
async def import_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    try:
        clean_state = import_progress_bundle(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    saved = save_state(clean_state)
    return {
        "state": saved,
        "progress": build_progress_report(saved),
        "vocabulary": get_vocabulary_items(saved, mode="all"),
    }


@router.post("/reset")
def reset_endpoint() -> dict[str, Any]:
    fresh = save_state(create_default_state())
    return {
        "state": fresh,
        "progress": build_progress_report(fresh),
        "vocabulary": get_vocabulary_items(fresh, mode="all"),
    }
