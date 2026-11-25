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
import shutil
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
DEFAULT_PROFILE_ID = "default"
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_STATE_LOCK = threading.RLock()
_PROFILE_LOCKS: dict[str, threading.RLock] = {}


def validate_profile_id(profile_id: str | None) -> str:
    """Строгая проверка profile_id: только 'default' или UUID (защита от path traversal)."""
    if profile_id is None:
        return DEFAULT_PROFILE_ID
    raw = str(profile_id).strip()
    if not raw or raw == DEFAULT_PROFILE_ID:
        return DEFAULT_PROFILE_ID
    if not _UUID_RE.fullmatch(raw):
        raise ValueError("Некорректный формат profile_id (ожидается UUID).")
    return raw.lower()


def _get_profile_lock(profile_id: str) -> threading.RLock:
    with _STATE_LOCK:
        lock = _PROFILE_LOCKS.get(profile_id)
        if lock is None:
            lock = threading.RLock()
            _PROFILE_LOCKS[profile_id] = lock
        return lock


def default_storage_path() -> Path:
    """Локальное файловое хранилище в соответствии с архитектурой Work Center."""
    local_bahoniq = Path.home() / "AppData" / "Local" / "BahonIQ"
    if os.name == "nt" and local_bahoniq.is_dir():
        return local_bahoniq / "english_academy_state.json"
    web_data = Path(__file__).resolve().parents[2] / "data"
    web_data.mkdir(parents=True, exist_ok=True)
    return web_data / "english_academy_state.json"


def get_profile_storage_path(profile_id: str | None = None, base_dir: Path | None = None) -> Path:
    """Возвращает изолированный путь JSON-состояния профиля с защитой от path traversal."""
    pid = validate_profile_id(profile_id)
    legacy_path = default_storage_path() if base_dir is None else (base_dir / "english_academy_state.json")
    profiles_dir = (legacy_path.parent / "english_academy_profiles").resolve()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    target = (profiles_dir / f"{pid}.json").resolve()
    if target.parent != profiles_dir:
        raise ValueError("Недопустимый путь профиля.")
    # Миграция старого одиночного файла в профиль default без удаления оригинала
    if pid == DEFAULT_PROFILE_ID and not target.exists() and legacy_path.exists():
        try:
            shutil.copy2(legacy_path, target)
        except Exception:
            pass
    return target


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
        "placement_result": None,
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


def load_state(path: Path | None = None, profile_id: str | None = None) -> dict[str, Any]:
    pid = validate_profile_id(profile_id)
    target = path or get_profile_storage_path(pid)
    lock = _get_profile_lock(str(target))
    with lock:
        if not target.exists():
            state = create_default_state()
            save_state(state, target, profile_id=pid)
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
            save_state(state, target, profile_id=pid)
            return state


def save_state(state: dict[str, Any], path: Path | None = None, profile_id: str | None = None) -> dict[str, Any]:
    pid = validate_profile_id(profile_id)
    target = path or get_profile_storage_path(pid)
    lock = _get_profile_lock(str(target))
    with lock:
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

    out = {
        "correct": is_correct,
        "attempt": attempt,
        "revealed": can_reveal,
        "feedback": feedback,
        "hint": hint,
        "expected": expected_display if can_reveal else None,
        "explanation": explanation if can_reveal else None,
    }
    if ex_type in ("guided_writing", "free_writing"):
        out["rubric"] = evaluate_writing_rubric(exercise, str(user_answer or ""))
    return out


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
        "placement_result": state.get("placement_result"),
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


# ============================================================================
# БЛОК 5. ВХОДНОЙ PLACEMENT TEST (ДЕТЕРМИНИРОВАННЫЙ, ОФЛАЙН)
# ============================================================================

PLACEMENT_QUESTIONS: list[dict[str, Any]] = [
    {"id": "pl-1", "level": "A0", "skill": "vocabulary", "prompt": "Как переводится слово «book»?", "options": ["книга", "стол", "телефон", "улица"], "answer": "книга"},
    {"id": "pl-2", "level": "A0", "skill": "grammar", "prompt": "Выберите верную связку: «She ___ a student.»", "options": ["is", "am", "are", "be"], "answer": "is"},
    {"id": "pl-3", "level": "A0", "skill": "listening", "audio_text": "Hello! My name is Timur.", "prompt": "Прослушайте фразу. Как зовут говорящего?", "options": ["Тимур", "Айдар", "Дана", "Аскар"], "answer": "Тимур"},

    {"id": "pl-4", "level": "A1", "skill": "grammar", "prompt": "Выберите верное отрицание: «He ___ drink coffee.»", "options": ["doesn't", "don't", "isn't", "not"], "answer": "doesn't"},
    {"id": "pl-5", "level": "A1", "skill": "reading", "passage": "Every Monday Aidar has a meeting at 10 o'clock.", "prompt": "Во сколько у Айдара встреча по понедельникам?", "options": ["В 10 часов", "В 1 час дня", "В 9 часов", "Вечером"], "answer": "В 10 часов"},
    {"id": "pl-6", "level": "A1", "skill": "vocabulary", "prompt": "Как спросить цену в магазине?", "options": ["How much is this?", "Where is money?", "What time is it?", "Who is this?"], "answer": "How much is this?"},

    {"id": "pl-7", "level": "A2", "skill": "grammar", "prompt": "Исправьте вопрос в прошлом: «Did you ___ to the office yesterday?»", "options": ["go", "went", "going", "gone"], "answer": "go"},
    {"id": "pl-8", "level": "A2", "skill": "grammar", "prompt": "Выберите правильный вежливый вопрос:", "options": ["Could you tell me where the bank is?", "Could you tell me where is the bank?", "Where bank is?", "Tell me where does bank?"], "answer": "Could you tell me where the bank is?"},
    {"id": "pl-9", "level": "A2", "skill": "listening", "audio_text": "Tomorrow I am going to visit the clinic at nine AM.", "prompt": "Куда говорящий планирует пойти завтра в 9 утра?", "options": ["В клинику", "В аэропорт", "В магазин", "В банк"], "answer": "В клинику"},

    {"id": "pl-10", "level": "B1", "skill": "grammar", "prompt": "Выберите 1-й тип условного предложения: «If it ___ tomorrow, we will stay inside.»", "options": ["rains", "will rain", "rained", "raining"], "answer": "rains"},
    {"id": "pl-11", "level": "B2", "skill": "grammar", "prompt": "Выберите правильную инверсию: «Never ___ such a clear report.»", "options": ["have I read", "I have read", "did I readed", "had read I"], "answer": "have I read"},
    {"id": "pl-12", "level": "B2", "skill": "reading", "passage": "Despite initial costs, automated checks account for a 40% drop in manual errors.", "prompt": "Какой эффект дали автоматические проверки?", "options": ["Снижение ручных ошибок на 40%", "Рост затрат на 40%", "Остановку проверок", "Замедление отчёта"], "answer": "Снижение ручных ошибок на 40%"},
]


def get_placement_test() -> list[dict[str, Any]]:
    return [copy.deepcopy(q) for q in PLACEMENT_QUESTIONS]


def evaluate_placement_test(answers: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Детерминированная адаптивная оценка уровня (A0–B2) без зависимости от ИИ."""
    by_level: dict[str, dict[str, int]] = {
        "A0": {"correct": 0, "total": 0},
        "A1": {"correct": 0, "total": 0},
        "A2": {"correct": 0, "total": 0},
        "B1": {"correct": 0, "total": 0},
        "B2": {"correct": 0, "total": 0},
    }
    total_correct = 0
    for q in PLACEMENT_QUESTIONS:
        lvl = q["level"]
        by_level[lvl]["total"] += 1
        ans = answers.get(q["id"])
        if ans is not None and str(ans).strip().lower() == str(q["answer"]).strip().lower():
            by_level[lvl]["correct"] += 1
            total_correct += 1

    recommended = "A0"
    if by_level["A0"]["correct"] >= 2:
        recommended = "A1"
        if by_level["A1"]["correct"] >= 2:
            recommended = "A2"
            if by_level["A2"]["correct"] >= 2:
                recommended = "B1"
                if by_level["B1"]["correct"] >= 1 and by_level["B2"]["correct"] >= 2:
                    recommended = "B2"

    reasons = {
        "A0": "Рекомендуем начать с самого старта A0: закрепим чтение, базовые звуки, местоимения и первые конструкции.",
        "A1": "У вас уже есть базовое понимание слов и глагола be (A0 освоен). Оптимально начать с уровня A1.",
        "A2": "Вы уверенно справляетесь с базой A0–A1. На уровне A2 перейдём к прошлым и будущим событиям, сравнениям и живому общению.",
        "B1": "Базовая грамматика A0–A2 даётся вам легко. На уровне B1 сфокусируемся на сложных временах, переписке, отчётах и аргументации.",
        "B2": "Отличный результат! У вас сильная база A0–B1. Можно переходить сразу к уровню B2: нюансы стиля, переговоры и аналитика.",
    }
    result = {
        "recommended_level": recommended,
        "score": total_correct,
        "total": len(PLACEMENT_QUESTIONS),
        "breakdown": by_level,
        "explanation": reasons[recommended],
        "completed_at": _now_iso(),
    }
    if state is not None:
        state["placement_result"] = result
    return result


def apply_placement_level(state: dict[str, Any], chosen_level: str) -> dict[str, Any]:
    """Открывает выбранный пользователем стартовый уровень (только после явного подтверждения)."""
    lvl = str(chosen_level or "A0").upper()
    if lvl not in LEVEL_ORDER:
        lvl = "A0"
    all_lessons = get_all_lessons_flat()
    if lvl == "A0":
        state["current_level"] = "A0"
        state["current_lesson_id"] = "a0-l1"
        return state

    target_idx = LEVEL_ORDER.index(lvl)
    first_target_id = next((l["id"] for l in all_lessons if l["level"] == lvl), "a0-l1")
    for item in all_lessons:
        if LEVEL_ORDER.index(item["level"]) < target_idx:
            rec = state["lessons"].get(item["id"])
            if not rec or not rec.get("passed"):
                state["lessons"][item["id"]] = {
                    "passed": True,
                    "score": 80,
                    "best_score": 80,
                    "attempts": 1,
                    "placement_skipped": True,
                    "completed_at": _now_iso(),
                }
    state["current_level"] = lvl
    state["current_lesson_id"] = first_target_id
    return state


# ============================================================================
# БЛОК 6. СРАВНЕНИЕ ПРОИЗНОШЕНИЯ (SPEECH RECOGNITION)
# ============================================================================

def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def compare_pronunciation(reference_text: str, recognized_text: str) -> dict[str, Any]:
    """Сравнивает распознанные слова с эталоном (не является фонетической экспертизой)."""
    ref_words = _norm_words(reference_text)
    rec_words = _norm_words(recognized_text)
    if not ref_words:
        return {
            "match_percent": 0,
            "matched_words": [],
            "missing_words": [],
            "extra_words": rec_words,
            "disclaimer": "Автоматическое сравнение распознанных слов (не является профессиональной фонетической оценкой).",
        }
    rec_pool = list(rec_words)
    matched: list[str] = []
    missing: list[str] = []
    for w in ref_words:
        if w in rec_pool:
            matched.append(w)
            rec_pool.remove(w)
        else:
            missing.append(w)
    pct = round((len(matched) / len(ref_words)) * 100)
    return {
        "match_percent": pct,
        "matched_words": matched,
        "missing_words": missing,
        "extra_words": rec_pool,
        "disclaimer": "Автоматическое сравнение распознанных слов (не является профессиональной фонетической оценкой).",
    }


# ============================================================================
# БЛОК 7. СВОБОДНЫЙ ДИАЛОГ И ДЕТАЛЬНАЯ ПРОВЕРКА ПИСЬМА B1–B2
# ============================================================================

FREE_DIALOGUE_SCENARIOS: dict[str, dict[str, Any]] = {
    "intro": {"title": "Знакомство и работа", "level": "A0", "prompt": "Hello! Nice to meet you. What is your name and what do you do?", "keywords": ["name", "i", "am", "work", "student", "manager", "engineer", "doctor"]},
    "shop": {"title": "В магазине", "level": "A1", "prompt": "Good afternoon! Can I help you find something?", "keywords": ["how", "much", "card", "cash", "buy", "like", "please", "price"]},
    "travel": {"title": "Поездка и отель", "level": "A1", "prompt": "Welcome to the hotel! Do you have a reservation?", "keywords": ["reservation", "yes", "name", "room", "night", "passport", "have"]},
    "office": {"title": "Офис и задачи", "level": "A2", "prompt": "Hi! Are we ready for the morning update? What are you working on today?", "keywords": ["working", "report", "email", "meeting", "today", "finish", "project"]},
    "call": {"title": "Рабочий звонок", "level": "A2", "prompt": "Hello, this is Dana from support speaking. How can I assist you?", "keywords": ["speaking", "call", "help", "problem", "issue", "please", "repeat", "when"]},
    "meeting": {"title": "Созвон / Встреча", "level": "B1", "prompt": "Let's start the meeting. What is your opinion on the new timeline?", "keywords": ["opinion", "think", "agree", "however", "deadline", "week", "schedule", "suggest"]},
    "negotiation": {"title": "Переговоры", "level": "B2", "prompt": "We would like a 15% discount on the annual plan. What can you offer?", "keywords": ["provided", "offer", "discount", "unless", "compromise", "contract", "annual", "terms"]},
}


def _record_dialogue_mistake(
    state: dict[str, Any],
    topic_id: str,
    title: str,
    user_answer: str,
    expected_hint: str,
    explanation: str,
) -> None:
    mistakes = state.setdefault("mistakes", [])
    mid = f"free-dlg-{topic_id}"
    existing = next((m for m in mistakes if m.get("id") == mid), None)
    if existing:
        existing["count"] = int(existing.get("count", 1)) + 1
        existing["user_answer"] = str(user_answer or "")[:300]
        existing["resolved"] = False
        existing["updated_at"] = _now_iso()
    else:
        mistakes.append(
            {
                "id": mid,
                "lesson_id": f"dlg-{topic_id}",
                "exercise_id": mid,
                "skill": "speaking",
                "prompt": f"Свободный диалог: {title}",
                "user_answer": str(user_answer or "")[:300],
                "expected": expected_hint,
                "explanation": explanation,
                "count": 1,
                "clean_streak": 0,
                "resolved": False,
                "updated_at": _now_iso(),
            }
        )


def evaluate_free_dialogue_turn(
    topic_id: str,
    user_text: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Детерминированная офлайн-проверка свободной реплики в диалоге."""
    scenario = FREE_DIALOGUE_SCENARIOS.get(topic_id, FREE_DIALOGUE_SCENARIOS["intro"])
    clean = (user_text or "").strip()
    words = _norm_words(clean)
    has_cyr = bool(re.search(r"[а-яёА-ЯЁ]", clean))

    if len(words) < 3 or has_cyr:
        feedback = "Напишите полноценную реплику на английском (минимум 3 слова, без кириллицы)."
        if state is not None:
            _record_dialogue_mistake(
                state,
                topic_id,
                scenario["title"],
                user_text,
                "Минимум 3 слова на английском по теме сценария",
                feedback,
            )
            st = state.setdefault("skill_stats", {}).setdefault("speaking", {"correct": 0, "total": 0})
            st["total"] += 1
        return {"passed": False, "feedback": feedback, "next_prompt": scenario["prompt"]}

    hits = [kw for kw in scenario["keywords"] if kw in words]
    passed = len(hits) >= 1 or len(words) >= 6
    if state is not None:
        st = state.setdefault("skill_stats", {}).setdefault("speaking", {"correct": 0, "total": 0})
        st["total"] += 1
        if passed:
            st["correct"] += 1
            touch_study_activity(state, add_seconds=30)
        else:
            _record_dialogue_mistake(
                state,
                topic_id,
                scenario["title"],
                user_text,
                f"Используйте лексику по теме ({', '.join(scenario['keywords'][:4])})",
                "Реплика понятна, но не хватает слов по теме ситуации.",
            )

    feedback = (
        f"Отлично! Естественная реплика по теме «{scenario['title']}» ({len(words)} сл.)."
        if passed
        else f"Попробуйте добавить ключевые слова по теме «{scenario['title']}» (например: {', '.join(scenario['keywords'][:4])})."
    )
    return {
        "passed": passed,
        "feedback": feedback,
        "matched_keywords": hits,
        "next_prompt": "Great! Can you add one more detail or question to continue the conversation?" if passed else scenario["prompt"],
    }


def evaluate_writing_rubric(exercise: dict[str, Any], user_text: str) -> dict[str, Any]:
    """Детерминированная оценка письма по 5 критериям (0–20 каждый, итого 0–100)."""
    clean = (user_text or "").strip()
    words = _norm_words(clean)
    has_cyr = bool(re.search(r"[а-яёА-ЯЁ]", clean))
    min_words = int(exercise.get("min_words", 6))

    if has_cyr or not words:
        return {
            "total_score": 0,
            "task_completion": 0,
            "grammar": 0,
            "vocabulary": 0,
            "structure": 0,
            "coherence": 0,
        }

    req = [t.lower() for t in exercise.get("required_tokens", [])]
    req_any = [t.lower() for t in exercise.get("required_any", [])]
    len_ratio = min(1.0, len(words) / max(1, min_words))
    token_ok = True
    if req and not all(t in clean.lower() for t in req):
        token_ok = False
    if req_any and not any(t in clean.lower() for t in req_any):
        token_ok = False
    task_score = round(20 * len_ratio * (1.0 if token_ok else 0.55))

    grammar_score = 12
    if clean[0].isupper():
        grammar_score += 4
    if clean[-1] in ".!?":
        grammar_score += 4

    uniq_ratio = len(set(words)) / max(1, len(words))
    vocab_score = min(20, round(10 + 10 * uniq_ratio))

    sentences = [s for s in re.split(r"[.!?]+", clean) if s.strip()]
    structure_score = 20 if len(sentences) >= 2 else 14

    connectors = {
        "because", "however", "therefore", "although", "despite", "first", "then",
        "finally", "moreover", "furthermore", "result", "example", "provided", "while", "since",
    }
    conn_hits = sum(1 for c in connectors if c in words)
    coherence_score = min(20, 12 + conn_hits * 4)

    total = task_score + grammar_score + vocab_score + structure_score + coherence_score
    return {
        "total_score": total,
        "task_completion": task_score,
        "grammar": grammar_score,
        "vocabulary": vocab_score,
        "structure": structure_score,
        "coherence": coherence_score,
    }
