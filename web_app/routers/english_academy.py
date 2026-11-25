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
    FREE_DIALOGUE_SCENARIOS,
    apply_placement_level,
    build_progress_report,
    compare_pronunciation,
    complete_lesson_attempt,
    create_default_state,
    evaluate_free_dialogue_turn,
    evaluate_placement_test,
    export_progress_bundle,
    get_placement_test,
    get_vocabulary_items,
    import_progress_bundle,
    load_state,
    record_exercise_attempt,
    review_vocab_word,
    save_state,
    toggle_hard_word,
    touch_study_activity,
    validate_profile_id,
)
from ..modules.english_academy.tutor import ask_english_tutor

router = APIRouter(prefix="/api/english-academy", tags=["English Academy Studio"])


def _extract_profile_id(request: Request, body: dict[str, Any] | None = None) -> str:
    raw = request.headers.get("X-Profile-Id") or request.query_params.get("profile_id")
    if not raw and isinstance(body, dict):
        raw = body.get("profile_id")
    try:
        return validate_profile_id(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/bootstrap")
def bootstrap(request: Request) -> dict[str, Any]:
    """Единая точка начальной загрузки курса, прогресса и настроек."""
    pid = _extract_profile_id(request)
    state = load_state(profile_id=pid)
    report = build_progress_report(state)
    return {
        "profile_id": pid,
        "curriculum": get_curriculum_payload(),
        "state": state,
        "progress": report,
        "vocabulary": get_vocabulary_items(state, mode="all"),
    }


@router.get("/lesson/{lesson_id}")
def get_lesson_endpoint(lesson_id: str, request: Request) -> dict[str, Any]:
    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(404, "Урок не найден")
    pid = _extract_profile_id(request)
    state = load_state(profile_id=pid)
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
    pid = _extract_profile_id(request, body)
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

    state = load_state(profile_id=pid)
    result = record_exercise_attempt(
        state=state,
        lesson_id=lesson_id,
        exercise=exercise,
        user_answer=user_answer,
        attempt=attempt,
        reveal=reveal,
    )
    saved = save_state(state, profile_id=pid)
    return {
        "result": result,
        "progress": build_progress_report(saved),
        "mistakes": saved["mistakes"],
    }


@router.post("/lesson/complete")
async def complete_lesson_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    lesson_id = str(body.get("lesson_id") or "")
    exercise_results = body.get("exercise_results")
    spent_seconds = int(body.get("spent_seconds", 120) or 120)
    if not isinstance(exercise_results, dict):
        exercise_results = {}

    state = load_state(profile_id=pid)
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

    saved = save_state(state, profile_id=pid)
    return {
        "outcome": outcome,
        "state": saved,
        "progress": build_progress_report(saved),
        "vocabulary": get_vocabulary_items(saved, mode="all"),
    }


@router.get("/vocabulary")
def list_vocabulary(request: Request, mode: str = "all", level: str = "", topic: str = "", q: str = "") -> dict[str, Any]:
    pid = _extract_profile_id(request)
    state = load_state(profile_id=pid)
    items = get_vocabulary_items(state, mode=mode, level=level, topic=topic, query=q)
    return {
        "items": items,
        "summary": build_progress_report(state)["vocab_summary"],
    }


@router.post("/vocabulary/review")
async def review_vocabulary_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    word_id = str(body.get("word_id") or "")
    knew_it = bool(body.get("knew_it", False))
    state = load_state(profile_id=pid)
    try:
        item = review_vocab_word(state, word_id, knew_it)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    saved = save_state(state, profile_id=pid)
    return {
        "word": item,
        "progress": build_progress_report(saved),
    }


@router.post("/vocabulary/hard")
async def toggle_hard_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    word_id = str(body.get("word_id") or "")
    state = load_state(profile_id=pid)
    try:
        item = toggle_hard_word(state, word_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    saved = save_state(state, profile_id=pid)
    return {
        "word": item,
        "progress": build_progress_report(saved),
    }


@router.post("/dialogue/complete")
async def complete_dialogue_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    dlg_id = str(body.get("dialogue_id") or "")
    if not any(d["id"] == dlg_id for d in DIALOGUES):
        raise HTTPException(404, "Диалог не найден")
    state = load_state(profile_id=pid)
    if dlg_id not in state["dialogues_done"]:
        state["dialogues_done"].append(dlg_id)
    state["skill_stats"]["speaking"]["total"] += 1
    state["skill_stats"]["speaking"]["correct"] += 1
    touch_study_activity(state, add_seconds=60)
    saved = save_state(state, profile_id=pid)
    return {
        "dialogues_done": saved["dialogues_done"],
        "progress": build_progress_report(saved),
    }


@router.post("/mistakes/resolve")
async def resolve_mistake_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    mistake_id = str(body.get("mistake_id") or "")
    answer = body.get("answer")
    state = load_state(profile_id=pid)
    m = next((x for x in state["mistakes"] if x["id"] == mistake_id), None)
    if not m:
        raise HTTPException(404, "Запись об ошибке не найдена")

    lesson = get_lesson_by_id(m["lesson_id"])
    exercise = next((ex for ex in (lesson or {}).get("exercises", []) if ex["id"] == m["exercise_id"]), None)
    if not exercise:
        m["resolved"] = True
        saved = save_state(state, profile_id=pid)
        return {"correct": True, "resolved": True, "mistakes": saved["mistakes"], "progress": build_progress_report(saved)}

    res = record_exercise_attempt(state, m["lesson_id"], exercise, answer, attempt=2, reveal=True)
    if res["correct"]:
        m["resolved"] = True
        m["clean_streak"] = max(2, int(m.get("clean_streak", 0)))
    saved = save_state(state, profile_id=pid)
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
    pid = _extract_profile_id(request, body)
    mode = str(body.get("mode") or "chat")
    message = str(body.get("message") or "")[:2000]
    lesson_id = str(body.get("lesson_id") or "")
    force_offline = bool(body.get("force_offline", False))

    state = load_state(profile_id=pid)
    reply = await run_in_threadpool(
        ask_english_tutor,
        state,
        mode,
        message,
        lesson_id,
        force_offline,
    )
    touch_study_activity(state, add_seconds=15)
    save_state(state, profile_id=pid)
    return reply


@router.post("/settings")
async def update_settings_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    state = load_state(profile_id=pid)
    if isinstance(body, dict):
        clean_settings = {k: v for k, v in body.items() if k != "profile_id"}
        state["settings"] = {**state.get("settings", {}), **clean_settings}
    saved = save_state(state, profile_id=pid)
    return {"settings": saved["settings"], "progress": build_progress_report(saved)}


@router.get("/export")
def export_endpoint(request: Request) -> dict[str, Any]:
    pid = _extract_profile_id(request)
    state = load_state(profile_id=pid)
    return export_progress_bundle(state)


@router.post("/import")
async def import_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    try:
        clean_state = import_progress_bundle(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    saved = save_state(clean_state, profile_id=pid)
    return {
        "state": saved,
        "progress": build_progress_report(saved),
        "vocabulary": get_vocabulary_items(saved, mode="all"),
    }


@router.post("/reset")
def reset_endpoint(request: Request) -> dict[str, Any]:
    pid = _extract_profile_id(request)
    fresh = save_state(create_default_state(), profile_id=pid)
    return {
        "state": fresh,
        "progress": build_progress_report(fresh),
        "vocabulary": get_vocabulary_items(fresh, mode="all"),
    }


@router.get("/placement")
def placement_questions_endpoint() -> dict[str, Any]:
    return {"questions": get_placement_test()}


@router.post("/placement/submit")
async def placement_submit_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        answers = {}
    state = load_state(profile_id=pid)
    result = evaluate_placement_test(answers, state=state)
    saved = save_state(state, profile_id=pid)
    return {"result": result, "state": saved, "progress": build_progress_report(saved)}


@router.post("/placement/apply")
async def placement_apply_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    chosen_level = str(body.get("level") or "A0").upper()
    state = load_state(profile_id=pid)
    apply_placement_level(state, chosen_level)
    saved = save_state(state, profile_id=pid)
    return {"state": saved, "progress": build_progress_report(saved)}


@router.post("/pronunciation/compare")
async def pronunciation_compare_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    reference = str(body.get("reference") or "")
    recognized = str(body.get("recognized") or "")
    return compare_pronunciation(reference, recognized)


@router.get("/free-dialogue/scenarios")
def free_dialogue_scenarios_endpoint() -> dict[str, Any]:
    return {"scenarios": FREE_DIALOGUE_SCENARIOS}


@router.post("/free-dialogue/turn")
async def free_dialogue_turn_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    pid = _extract_profile_id(request, body)
    topic_id = str(body.get("topic_id") or "intro")
    user_text = str(body.get("user_text") or "")[:1000]
    state = load_state(profile_id=pid)
    result = evaluate_free_dialogue_turn(topic_id, user_text, state=state)
    saved = save_state(state, profile_id=pid)
    return {
        "result": result,
        "progress": build_progress_report(saved),
        "mistakes": saved["mistakes"],
    }
