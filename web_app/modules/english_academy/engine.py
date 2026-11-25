# -*- coding: utf-8 -*-
"""Ядро образовательной логики English Academy Studio:
проверка упражнений, контроль освоения и блокировок, интервальное повторение (SRS),
персональный журнал ошибок, расчёт честного прогресса, хранение и миграции схемы.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from .curriculum import (
    DIALOGUES,
    LEVEL_ORDER,
    LEVELS,
    get_all_lessons_flat,
    get_base_vocabulary,
    get_lesson_by_id,
)

SCHEMA_VERSION = 2
SKILLS = ("reading", "writing", "listening", "vocabulary", "grammar", "speaking")
SRS_INTERVAL_DAYS = [0, 1, 3, 7, 14, 30]

_STATE_LOCK = threading.RLock()


def default_storage_path() -> Path:
    """Локальное файловое хранилище в соответствии с архитектурой Work Center."""
    local_bahoniq = Path.home() / "AppData" / "Local" / "BahonIQ"
    if os.name == "nt" and local_bahoniq.is_dir():
        return local_bahoniq / "english_academy_state.json"
    web_data = Path(__file__).resolve().parents[2] / "data"
    web_data.mkdir(parents=True, exist_ok=True)
    return web_data / "english_academy_state.json"


def _utc_today_str() -> str:
    return dt.date.today().isoformat()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def create_default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "current_level": "A0",
        "current_lesson_id": "a0-l1",
        "streak_days": 0,
        "last_study_date": "",
        "study_seconds": 0,
        "lessons": {},          # lesson_id -> {score, passed, attempts, completed_at, exercise_scores}
        "skill_stats": {s: {"correct": 0, "total": 0} for s in SKILLS},
        "vocab": {},            # word_id -> {status, box, correct_count, wrong_count, next_review, is_hard, last_seen}
        "mistakes": [],         # [{id, lesson_id, exercise_id, skill, prompt, user_answer, expected, explanation, count, clean_streak, resolved, updated_at}]
        "dialogues_done": [],   # [dialogue_id]
        "history": [],          # [{date, action, title, score, seconds}]
        "settings": {
            "speech_rate": 0.85,
            "auto_speak": False,
            "show_ru_hint": True,
            "daily_goal_minutes": 15,
        },
    }


def migrate_state(raw: Any) -> dict[str, Any]:
    """Безопасная миграция и санитизация состояния (поддержка v1 -> v2 и защита от повреждений)."""
    base = create_default_state()
    if not isinstance(raw, dict):
        return base

    version = raw.get("schema_version", 1)
    try:
        version = int(version)
    except (TypeError, ValueError):
        version = 1

    # Миграция схемы v1 (где completed_lessons мог быть списком, а vocab хранился по слову)
    if version < 2:
        completed_list = raw.get("completed_lessons")
        if isinstance(completed_list, list):
            lessons_map: dict[str, Any] = {}
            for lid in completed_list:
                if isinstance(lid, str) and get_lesson_by_id(lid):
                    lessons_map[lid] = {
                        "score": 85,
                        "passed": True,
                        "attempts": 1,
                        "completed_at": _now_iso(),
                        "exercise_scores": {},
                    }
            raw = dict(raw)
            raw["lessons"] = {**lessons_map, **(raw.get("lessons") if isinstance(raw.get("lessons"), dict) else {})}

    if isinstance(raw.get("current_level"), str) and raw["current_level"] in LEVEL_ORDER:
        base["current_level"] = raw["current_level"]

    if isinstance(raw.get("current_lesson_id"), str) and get_lesson_by_id(raw["current_lesson_id"]):
        base["current_lesson_id"] = raw["current_lesson_id"]

    for int_key in ("streak_days", "study_seconds"):
        val = raw.get(int_key)
        if isinstance(val, (int, float)) and val >= 0:
            base[int_key] = int(val)

    if isinstance(raw.get("last_study_date"), str):
        base["last_study_date"] = raw["last_study_date"][:10]

    if isinstance(raw.get("lessons"), dict):
        for lid, ldata in raw["lessons"].items():
            if isinstance(lid, str) and isinstance(ldata, dict) and get_lesson_by_id(lid):
                score = max(0, min(100, int(ldata.get("score", 0) or 0)))
                base["lessons"][lid] = {
                    "score": score,
                    "passed": bool(ldata.get("passed", score >= 75)),
                    "attempts": max(1, int(ldata.get("attempts", 1) or 1)),
                    "completed_at": str(ldata.get("completed_at") or _now_iso()),
                    "exercise_scores": ldata.get("exercise_scores") if isinstance(ldata.get("exercise_scores"), dict) else {},
                }

    if isinstance(raw.get("skill_stats"), dict):
        for s in SKILLS:
            st = raw["skill_stats"].get(s)
            if isinstance(st, dict):
                c = max(0, int(st.get("correct", 0) or 0))
                t = max(c, int(st.get("total", 0) or 0))
                base["skill_stats"][s] = {"correct": c, "total": t}

    valid_word_ids = {w["id"] for w in get_base_vocabulary()}
    if isinstance(raw.get("vocab"), dict):
        for wid, vdata in raw["vocab"].items():
            if wid in valid_word_ids and isinstance(vdata, dict):
                box = max(0, min(len(SRS_INTERVAL_DAYS) - 1, int(vdata.get("box", 0) or 0)))
                status = str(vdata.get("status", "learning"))
                if status not in ("new", "learning", "review", "mastered"):
                    status = "learning"
                base["vocab"][wid] = {
                    "status": status,
                    "box": box,
                    "correct_count": max(0, int(vdata.get("correct_count", 0) or 0)),
                    "wrong_count": max(0, int(vdata.get("wrong_count", 0) or 0)),
                    "next_review": str(vdata.get("next_review") or _utc_today_str())[:10],
                    "is_hard": bool(vdata.get("is_hard", False)),
                    "last_seen": str(vdata.get("last_seen") or _now_iso()),
                }

    if isinstance(raw.get("mistakes"), list):
        for m in raw["mistakes"][:200]:
            if isinstance(m, dict) and m.get("exercise_id"):
                base["mistakes"].append(
                    {
                        "id": str(m.get("id") or m["exercise_id"]),
                        "lesson_id": str(m.get("lesson_id") or ""),
                        "exercise_id": str(m["exercise_id"]),
                        "skill": str(m.get("skill") or "grammar"),
                        "prompt": str(m.get("prompt") or ""),
                        "user_answer": str(m.get("user_answer") or ""),
                        "expected": str(m.get("expected") or ""),
                        "explanation": str(m.get("explanation") or ""),
                        "count": max(1, int(m.get("count", 1) or 1)),
                        "clean_streak": max(0, int(m.get("clean_streak", 0) or 0)),
                        "resolved": bool(m.get("resolved", False)),
                        "updated_at": str(m.get("updated_at") or _now_iso()),
                    }
                )

    if isinstance(raw.get("dialogues_done"), list):
        valid_dlgs = {d["id"] for d in DIALOGUES}
        base["dialogues_done"] = [d for d in raw["dialogues_done"] if isinstance(d, str) and d in valid_dlgs]

    if isinstance(raw.get("history"), list):
        for h in raw["history"][-100:]:
            if isinstance(h, dict):
                base["history"].append(
                    {
                        "date": str(h.get("date") or _now_iso()),
                        "action": str(h.get("action") or "lesson"),
                        "title": str(h.get("title") or ""),
                        "score": int(h.get("score", 0) or 0),
                        "seconds": max(0, int(h.get("seconds", 0) or 0)),
                    }
                )

    if isinstance(raw.get("settings"), dict):
        s_in = raw["settings"]
        rate = s_in.get("speech_rate", 0.85)
        if isinstance(rate, (int, float)):
            base["settings"]["speech_rate"] = max(0.5, min(1.3, float(rate)))
        if isinstance(s_in.get("auto_speak"), bool):
            base["settings"]["auto_speak"] = s_in["auto_speak"]
        if isinstance(s_in.get("show_ru_hint"), bool):
            base["settings"]["show_ru_hint"] = s_in["show_ru_hint"]
        goal = s_in.get("daily_goal_minutes", 15)
        if isinstance(goal, (int, float)):
            base["settings"]["daily_goal_minutes"] = max(5, min(120, int(goal)))

    base["schema_version"] = SCHEMA_VERSION
    base["updated_at"] = _now_iso()
    _sync_current_level_from_progress(base)
    return base


def load_state(path: Path | None = None) -> dict[str, Any]:
    target = path or default_storage_path()
    with _STATE_LOCK:
        if not target.exists():
            state = create_default_state()
            save_state(state, target)
            return state
        try:
            raw_text = target.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            return migrate_state(data)
        except Exception:
            # Защита от повреждённых данных: сохраняем резерв повреждённого файла и создаём валидный стейт
            try:
                bak = target.with_suffix(".corrupted.bak")
                bak.write_bytes(target.read_bytes())
            except Exception:
                pass
            state = create_default_state()
            save_state(state, target)
            return state


def save_state(state: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or default_storage_path()
    with _STATE_LOCK:
        clean = migrate_state(state)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
        return clean


def touch_study_activity(state: dict[str, Any], add_seconds: int = 0) -> None:
    """Обновляет серию дней (streak) и время обучения."""
    today = dt.date.today()
    today_s = today.isoformat()
    last_s = state.get("last_study_date") or ""
    if last_s != today_s:
        if last_s:
            try:
                prev = dt.date.fromisoformat(last_s)
                if (today - prev).days == 1:
                    state["streak_days"] = int(state.get("streak_days", 0)) + 1
                elif (today - prev).days > 1:
                    state["streak_days"] = 1
            except ValueError:
                state["streak_days"] = 1
        else:
            state["streak_days"] = 1
        state["last_study_date"] = today_s
    if add_seconds > 0:
        state["study_seconds"] = int(state.get("study_seconds", 0)) + min(3600, int(add_seconds))


def compute_unlock_map(state: dict[str, Any]) -> dict[str, bool]:
    """Строгий последовательный контроль освоения:
    каждый следующий урок открывается после зачёта предыдущего (75%+, для экзамена уровня — 80%+).
    """
    lessons = get_all_lessons_flat()
    passed_map = state.get("lessons", {})
    unlocked: dict[str, bool] = {}
    prev_passed = True
    for item in lessons:
        lid = item["id"]
        unlocked[lid] = prev_passed
        rec = passed_map.get(lid, {})
        threshold = 80 if item.get("kind") == "exam" else 75
        is_passed = bool(rec.get("passed")) and int(rec.get("score", 0)) >= threshold
        prev_passed = prev_passed and is_passed
    return unlocked


def _sync_current_level_from_progress(state: dict[str, Any]) -> None:
    unlock_map = compute_unlock_map(state)
    lessons = get_all_lessons_flat()
    passed_map = state.get("lessons", {})
    next_lesson = lessons[0]
    for item in lessons:
        if unlock_map.get(item["id"]) and not passed_map.get(item["id"], {}).get("passed"):
            next_lesson = item
            break
    else:
        next_lesson = lessons[-1]
    state["current_level"] = next_lesson["level"]
    if not unlock_map.get(state.get("current_lesson_id", ""), False):
        state["current_lesson_id"] = next_lesson["id"]


def _norm_text(val: str) -> str:
    s = str(val or "").strip().lower()
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    s = re.sub(r"[.!?,;:]+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _expand_contractions(s: str) -> str:
    replacements = {
        "i'm": "i am",
        "you're": "you are",
        "he's": "he is",
        "she's": "she is",
        "it's": "it is",
        "we're": "we are",
        "they're": "they are",
        "isn't": "is not",
        "aren't": "are not",
        "don't": "do not",
        "doesn't": "does not",
        "didn't": "did not",
        "can't": "cannot",
        "won't": "will not",
        "haven't": "have not",
        "hasn't": "has not",
        "wouldn't": "would not",
        "shouldn't": "should not",
        "i've": "i have",
    }
    tokens = s.split(" ")
    return " ".join(replacements.get(t, t) for t in tokens)


def check_exercise_answer(exercise: dict[str, Any], user_answer: Any, attempt: int = 1, reveal: bool = False) -> dict[str, Any]:
    """Проверяет ответ на любое упражнение курса без ложных срабатываний."""
    ex_type = exercise.get("type", "choice")
    explanation = exercise.get("explanation", "")
    hint = exercise.get("hint") or "Обратите внимание на порядок слов и форму глагола в правиле урока."
    expected_display = str(exercise.get("answer", ""))

    is_correct = False

    if ex_type == "match":
        expected_pairs = {p["left"]: p["right"] for p in exercise.get("pairs", [])}
        expected_display = "; ".join(f"{k} — {v}" for k, v in expected_pairs.items())
        if isinstance(user_answer, dict):
            is_correct = len(user_answer) == len(expected_pairs) and all(
                str(user_answer.get(k, "")).strip() == v for k, v in expected_pairs.items()
            )
    elif ex_type in ("guided_writing", "free_writing"):
        text_raw = str(user_answer or "").strip()
        norm = _norm_text(text_raw)
        words = [w for w in re.split(r"\s+", norm) if w]
        min_words = int(exercise.get("min_words", 4))
        req = [t.lower() for t in exercise.get("required_tokens", [])]
        alt = [t.lower() for t in exercise.get("alternative_tokens", [])]
        req_any = [t.lower() for t in exercise.get("required_any", [])]

        has_Cyrillic = bool(re.search(r"[а-яё]", norm))
        tokens_ok = True
        if req:
            primary_ok = all(t in norm for t in req)
            alt_ok = bool(alt) and all(t in norm for t in alt)
            tokens_ok = primary_ok or alt_ok
        if req_any:
            tokens_ok = tokens_ok and any(t in norm for t in req_any)

        is_correct = (not has_Cyrillic) and len(words) >= min_words and tokens_ok
        if not is_correct:
            if has_Cyrillic:
                hint = "Пожалуйста, напишите ответ английскими буквами."
            elif len(words) < min_words:
                hint = f"Ответ слишком короткий — напишите хотя бы {min_words} слов(а) по образцу."
            else:
                hint = f"Используйте ключевую конструкцию урока (образец: {exercise.get('sample', expected_display)})."
    else:
        if isinstance(user_answer, list):
            candidate_raw = " ".join(str(x) for x in user_answer)
        else:
            candidate_raw = str(user_answer or "")

        cand = _norm_text(candidate_raw)
        cand_exp = _expand_contractions(cand)

        accepted_raw = list(exercise.get("accepted") or [])
        if exercise.get("answer"):
            accepted_raw.append(exercise["answer"])

        accepted_norm = {_norm_text(a) for a in accepted_raw if a}
        accepted_exp = {_expand_contractions(a) for a in accepted_norm}

        is_correct = bool(cand) and (cand in accepted_norm or cand_exp in accepted_exp)

    can_reveal = is_correct or reveal or attempt >= 2
    if is_correct:
        feedback = f"Верно! {explanation}".strip()
    elif not can_reveal:
        feedback = f"Пока не совсем так. Подсказка: {hint}"
    else:
        feedback = f"Правильный ответ: «{expected_display}». {explanation}".strip()

    return {
        "correct": is_correct,
        "attempt": attempt,
        "revealed": can_reveal,
        "feedback": feedback,
        "hint": hint,
        "expected": expected_display if can_reveal else None,
        "explanation": explanation if can_reveal else None,
    }


def record_exercise_attempt(
    state: dict[str, Any],
    lesson_id: str,
    exercise: dict[str, Any],
    user_answer: Any,
    attempt: int = 1,
    reveal: bool = False,
) -> dict[str, Any]:
    """Проверяет упражнение, обновляет статистику навыков, журнал ошибок и словарь."""
    result = check_exercise_answer(exercise, user_answer, attempt=attempt, reveal=reveal)
    skill = exercise.get("skill", "grammar")
    if skill not in SKILLS:
        skill = "grammar"

    state["skill_stats"].setdefault(skill, {"correct": 0, "total": 0})
    state["skill_stats"][skill]["total"] += 1
    if result["correct"]:
        state["skill_stats"][skill]["correct"] += 1

    ex_id = exercise["id"]
    existing = next((m for m in state["mistakes"] if m["exercise_id"] == ex_id), None)

    if not result["correct"]:
        user_str = (
            "; ".join(f"{k}: {v}" for k, v in user_answer.items())
            if isinstance(user_answer, dict)
            else (" ".join(str(x) for x in user_answer) if isinstance(user_answer, list) else str(user_answer or ""))
        )
        expected_str = str(exercise.get("answer") or "")
        if not expected_str and exercise.get("pairs"):
            expected_str = "; ".join(f"{p['left']} — {p['right']}" for p in exercise["pairs"])

        if existing:
            existing["count"] = int(existing.get("count", 1)) + 1
            existing["clean_streak"] = 0
            existing["resolved"] = False
            existing["user_answer"] = user_str[:300]
            existing["updated_at"] = _now_iso()
        else:
            state["mistakes"].append(
                {
                    "id": ex_id,
                    "lesson_id": lesson_id,
                    "exercise_id": ex_id,
                    "skill": skill,
                    "prompt": exercise.get("prompt", ""),
                    "user_answer": user_str[:300],
                    "expected": expected_str,
                    "explanation": exercise.get("explanation", ""),
                    "count": 1,
                    "clean_streak": 0,
                    "resolved": False,
                    "updated_at": _now_iso(),
                }
            )
    elif existing and not existing.get("resolved"):
        existing["clean_streak"] = int(existing.get("clean_streak", 0)) + 1
        existing["updated_at"] = _now_iso()
        if existing["clean_streak"] >= 2:
            existing["resolved"] = True

    touch_study_activity(state, add_seconds=20)
    return result


def complete_lesson_attempt(
    state: dict[str, Any],
    lesson_id: str,
    exercise_results: dict[str, bool],
    spent_seconds: int = 120,
) -> dict[str, Any]:
    """Фиксирует итог прохождения урока / проверки / экзамена и активирует слова урока в SRS."""
    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        raise ValueError(f"Unknown lesson_id: {lesson_id}")

    unlock_map = compute_unlock_map(state)
    if not unlock_map.get(lesson_id, False):
        raise PermissionError("Этот урок пока закрыт. Сначала освойте предыдущий шаг курса.")

    exercises = lesson.get("exercises", [])
    total = max(1, len(exercises))
    correct_count = sum(1 for ex in exercises if exercise_results.get(ex["id"]) is True)
    score = round((correct_count / total) * 100)
    threshold = 80 if lesson.get("kind") == "exam" else 75
    passed = score >= threshold

    prev_rec = state["lessons"].get(lesson_id, {})
    best_score = max(score, int(prev_rec.get("score", 0)))
    ever_passed = bool(prev_rec.get("passed")) or passed

    state["lessons"][lesson_id] = {
        "score": best_score,
        "passed": ever_passed,
        "attempts": int(prev_rec.get("attempts", 0)) + 1,
        "completed_at": _now_iso(),
        "exercise_scores": {ex["id"]: bool(exercise_results.get(ex["id"])) for ex in exercises},
    }

    # Добавляем слова урока в персональный словарь для интервального повторения
    today_s = _utc_today_str()
    for v in lesson.get("vocab", []):
        wid = f"w-{v['word'].strip().lower().replace(' ', '-')}"
        if wid not in state["vocab"]:
            state["vocab"][wid] = {
                "status": "learning",
                "box": 1,
                "correct_count": 1 if passed else 0,
                "wrong_count": 0,
                "next_review": (dt.date.today() + dt.timedelta(days=1)).isoformat() if passed else today_s,
                "is_hard": False,
                "last_seen": _now_iso(),
            }

    touch_study_activity(state, add_seconds=max(30, int(spent_seconds)))
    state["history"].append(
        {
            "date": _now_iso(),
            "action": lesson.get("kind", "lesson"),
            "title": lesson["title"],
            "score": score,
            "seconds": max(30, int(spent_seconds)),
        }
    )
    state["history"] = state["history"][-100:]
    _sync_current_level_from_progress(state)

    new_unlocks = compute_unlock_map(state)
    all_flat = get_all_lessons_flat()
    idx = next((i for i, x in enumerate(all_flat) if x["id"] == lesson_id), 0)
    next_lesson_id = all_flat[idx + 1]["id"] if (passed and idx + 1 < len(all_flat) and new_unlocks.get(all_flat[idx + 1]["id"])) else lesson_id
    state["current_lesson_id"] = next_lesson_id

    return {
        "lesson_id": lesson_id,
        "score": score,
        "best_score": best_score,
        "threshold": threshold,
        "passed": passed,
        "next_lesson_id": next_lesson_id,
        "current_level": state["current_level"],
    }


def review_vocab_word(state: dict[str, Any], word_id: str, knew_it: bool) -> dict[str, Any]:
    """Интервальное повторение слова (SRS): сдвигает интервал вперёд или возвращает в изучение."""
    base_words = {w["id"]: w for w in get_base_vocabulary()}
    if word_id not in base_words:
        raise ValueError("Слово не найдено в словаре курса.")

    rec = state["vocab"].get(
        word_id,
        {
            "status": "new",
            "box": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "next_review": _utc_today_str(),
            "is_hard": False,
            "last_seen": _now_iso(),
        },
    )

    state["skill_stats"]["vocabulary"]["total"] += 1
    if knew_it:
        state["skill_stats"]["vocabulary"]["correct"] += 1
        new_box = min(len(SRS_INTERVAL_DAYS) - 1, int(rec.get("box", 0)) + 1)
        days = SRS_INTERVAL_DAYS[new_box]
        next_date = (dt.date.today() + dt.timedelta(days=days)).isoformat()
        status = "mastered" if new_box >= 4 else "review"
        rec.update(
            {
                "box": new_box,
                "status": status,
                "correct_count": int(rec.get("correct_count", 0)) + 1,
                "next_review": next_date,
                "last_seen": _now_iso(),
            }
        )
    else:
        wrongs = int(rec.get("wrong_count", 0)) + 1
        rec.update(
            {
                "box": 0,
                "status": "learning",
                "wrong_count": wrongs,
                "next_review": _utc_today_str(),
                "is_hard": True if wrongs >= 2 else bool(rec.get("is_hard", False)),
                "last_seen": _now_iso(),
            }
        )

    state["vocab"][word_id] = rec
    touch_study_activity(state, add_seconds=10)
    return {**base_words[word_id], **rec}


def toggle_hard_word(state: dict[str, Any], word_id: str) -> dict[str, Any]:
    base_words = {w["id"]: w for w in get_base_vocabulary()}
    if word_id not in base_words:
        raise ValueError("Слово не найдено в словаре курса.")
    rec = state["vocab"].setdefault(
        word_id,
        {
            "status": "learning",
            "box": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "next_review": _utc_today_str(),
            "is_hard": False,
            "last_seen": _now_iso(),
        },
    )
    rec["is_hard"] = not bool(rec.get("is_hard", False))
    return {**base_words[word_id], **rec}


def get_vocabulary_items(
    state: dict[str, Any],
    mode: str = "all",
    level: str = "",
    topic: str = "",
    query: str = "",
) -> list[dict[str, Any]]:
    today_s = _utc_today_str()
    q = query.strip().lower()
    items: list[dict[str, Any]] = []

    for w in get_base_vocabulary():
        rec = state.get("vocab", {}).get(w["id"])
        merged = {
            **w,
            "status": rec["status"] if rec else "new",
            "box": rec["box"] if rec else 0,
            "correct_count": rec["correct_count"] if rec else 0,
            "wrong_count": rec["wrong_count"] if rec else 0,
            "next_review": rec["next_review"] if rec else today_s,
            "is_hard": rec["is_hard"] if rec else False,
        }
        if level and merged["level"] != level:
            continue
        if topic and merged["topic"] != topic:
            continue
        if q and q not in merged["word"].lower() and q not in merged["ru"].lower():
            continue

        if mode == "new" and merged["status"] != "new":
            continue
        if mode == "due" and not (merged["status"] in ("learning", "review") and merged["next_review"] <= today_s):
            continue
        if mode == "hard" and not merged["is_hard"]:
            continue
        if mode == "mastered" and merged["status"] != "mastered":
            continue

        items.append(merged)
    return items


def build_progress_report(state: dict[str, Any]) -> dict[str, Any]:
    """Честный расчёт прогресса по фактическим данным (без декоративных цифр)."""
    all_lessons = get_all_lessons_flat()
    unlock_map = compute_unlock_map(state)
    passed_map = state.get("lessons", {})

    total_count = len(all_lessons)
    passed_count = sum(1 for item in all_lessons if passed_map.get(item["id"], {}).get("passed"))
    overall_percent = round((passed_count / max(1, total_count)) * 100)

    levels_progress: list[dict[str, Any]] = []
    for lvl in LEVELS:
        lvl_lessons = [x for x in all_lessons if x["level"] == lvl["code"]]
        lvl_done = sum(1 for x in lvl_lessons if passed_map.get(x["id"], {}).get("passed"))
        lvl_pct = round((lvl_done / max(1, len(lvl_lessons))) * 100)
        lvl_unlocked = any(unlock_map.get(x["id"], False) for x in lvl_lessons)
        levels_progress.append(
            {
                "code": lvl["code"],
                "title": lvl["title"],
                "subtitle": lvl["subtitle"],
                "completed": lvl_done,
                "total": len(lvl_lessons),
                "percent": lvl_pct,
                "unlocked": lvl_unlocked,
            }
        )

    # Навыки: учитываем и точность ответов, и объём практики (чтобы 1 случайный ответ не давал 100% владения всем курсом)
    skills_report: dict[str, Any] = {}
    target_attempts_per_skill = 20
    for s in SKILLS:
        st = state.get("skill_stats", {}).get(s, {"correct": 0, "total": 0})
        total_s = int(st.get("total", 0))
        corr_s = int(st.get("correct", 0))
        accuracy = round((corr_s / total_s) * 100) if total_s > 0 else 0
        volume_factor = min(1.0, total_s / target_attempts_per_skill)
        mastery_pct = round(accuracy * volume_factor)
        skills_report[s] = {
            "correct": corr_s,
            "total": total_s,
            "accuracy": accuracy,
            "percent": mastery_pct,
        }

    # Незакрытые ошибки и слабые темы
    unresolved_mistakes = [m for m in state.get("mistakes", []) if not m.get("resolved")]
    weak_by_lesson: dict[str, int] = {}
    for m in unresolved_mistakes:
        lid = m.get("lesson_id") or ""
        if lid:
            weak_by_lesson[lid] = weak_by_lesson.get(lid, 0) + int(m.get("count", 1))

    weak_topics: list[dict[str, Any]] = []
    for lid, cnt in sorted(weak_by_lesson.items(), key=lambda x: x[1], reverse=True)[:5]:
        les = get_lesson_by_id(lid)
        if les:
            weak_topics.append({"lesson_id": lid, "title": les["title"], "level": les["level"], "mistakes_count": cnt})

    # Словарь
    today_s = _utc_today_str()
    vocab_entries = state.get("vocab", {})
    learned_words = sum(1 for v in vocab_entries.values() if v.get("status") in ("review", "mastered"))
    mastered_words = sum(1 for v in vocab_entries.values() if v.get("status") == "mastered")
    due_words = sum(
        1
        for v in vocab_entries.values()
        if v.get("status") in ("learning", "review") and str(v.get("next_review", today_s)) <= today_s
    )
    hard_words = sum(1 for v in vocab_entries.values() if v.get("is_hard"))

    # Определение главного следующего шага для кнопки «Продолжить обучение»
    next_lesson = all_lessons[0]
    for item in all_lessons:
        if unlock_map.get(item["id"]) and not passed_map.get(item["id"], {}).get("passed"):
            next_lesson = item
            break
    else:
        next_lesson = all_lessons[-1]

    cur_lvl_report = next((x for x in levels_progress if x["code"] == state.get("current_level", "A0")), levels_progress[0])

    # Рекомендация наставника на основе реальных данных
    if len(unresolved_mistakes) >= 3:
        recommendation = f"У вас накопилось {len(unresolved_mistakes)} незакрытых ошибок. Рекомендую заглянуть в раздел «Ошибки» на 3 минуты перед новым уроком."
    elif due_words >= 4:
        recommendation = f"Сегодня пора освежить в памяти {due_words} слов(а) по интервальному повторению, а затем переходить к уроку «{next_lesson['title']}»."
    else:
        recommendation = f"Следующий шаг маршрута {next_lesson['level']}: «{next_lesson['title']}» (~{next_lesson.get('estimated_minutes', 15)} мин). Идём спокойно шаг за шагом."

    return {
        "overall_percent": overall_percent,
        "completed_lessons": passed_count,
        "total_lessons": total_count,
        "current_level": state.get("current_level", "A0"),
        "current_level_progress": cur_lvl_report,
        "levels": levels_progress,
        "unlock_map": unlock_map,
        "skills": skills_report,
        "weak_topics": weak_topics,
        "unresolved_mistakes_count": len(unresolved_mistakes),
        "vocab_summary": {
            "total_in_course": len(get_base_vocabulary()),
            "started": len(vocab_entries),
            "learned": learned_words,
            "mastered": mastered_words,
            "due_today": due_words,
            "hard": hard_words,
        },
        "streak_days": int(state.get("streak_days", 0)),
        "study_minutes": round(int(state.get("study_seconds", 0)) / 60),
        "daily_goal_minutes": int(state.get("settings", {}).get("daily_goal_minutes", 15)),
        "next_step": {
            "lesson_id": next_lesson["id"],
            "level": next_lesson["level"],
            "kind": next_lesson.get("kind", "lesson"),
            "title": next_lesson["title"],
            "section_title": next_lesson["section_title"],
            "estimated_minutes": next_lesson.get("estimated_minutes", 15),
        },
        "recommendation": recommendation,
        "history": list(reversed(state.get("history", [])[-20:])),
    }


def export_progress_bundle(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "app": "BahonIQ English Academy Studio",
        "exported_at": _now_iso(),
        "schema_version": SCHEMA_VERSION,
        "state": copy.deepcopy(migrate_state(state)),
    }


def import_progress_bundle(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Некорректный формат файла прогресса.")
    inner = payload.get("state") if isinstance(payload.get("state"), dict) else payload
    return migrate_state(inner)
