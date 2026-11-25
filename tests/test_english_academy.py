# -*- coding: utf-8 -*-
"""Автоматические тесты критической логики English Academy Studio (A0–B2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from web_app.modules.english_academy.curriculum import (
    DIALOGUES,
    LEVEL_ORDER,
    LEVELS,
    get_all_lessons_flat,
    get_base_vocabulary,
    get_lesson_by_id,
)
from web_app.modules.english_academy.engine import (
    SCHEMA_VERSION,
    build_progress_report,
    check_exercise_answer,
    complete_lesson_attempt,
    compute_unlock_map,
    create_default_state,
    export_progress_bundle,
    get_vocabulary_items,
    import_progress_bundle,
    load_state,
    migrate_state,
    record_exercise_attempt,
    review_vocab_word,
    save_state,
    toggle_hard_word,
)
from web_app.modules.english_academy.tutor import ask_english_tutor
from web_app.server import app


class EnglishAcademyTests(unittest.TestCase):
    def test_curriculum_completeness_a0_to_b2(self):
        codes = [lvl["code"] for lvl in LEVELS]
        self.assertEqual(codes, LEVEL_ORDER)
        for lvl in LEVELS:
            lessons = [les for sec in lvl["sections"] for les in sec["lessons"]]
            self.assertGreaterEqual(len(lessons), 3, f"Level {lvl['code']} must have real lessons and exam")
            exams = [les for les in lessons if les.get("kind") == "exam"]
            self.assertEqual(len(exams), 1, f"Level {lvl['code']} must have an exam")
            for les in lessons:
                self.assertGreaterEqual(len(les.get("exercises", [])), 3)

        vocab = get_base_vocabulary()
        self.assertGreaterEqual(len(vocab), 40)
        self.assertGreaterEqual(len(DIALOGUES), 5)

    def test_answer_checking_and_first_attempt_hint(self):
        lesson = get_lesson_by_id("a0-l4")
        self.assertIsNotNone(lesson)
        ex_order = next(x for x in lesson["exercises"] if x["type"] == "word_order")

        # 1-я ошибка: даёт подсказку, но НЕ раскрывает эталон сразу
        r1 = check_exercise_answer(ex_order, ["am", "I", "ready"], attempt=1)
        self.assertFalse(r1["correct"])
        self.assertFalse(r1["revealed"])
        self.assertIsNone(r1["expected"])

        # 2-я ошибка: раскрывает эталон и объяснение
        r2 = check_exercise_answer(ex_order, ["am", "I", "ready"], attempt=2)
        self.assertFalse(r2["correct"])
        self.assertTrue(r2["revealed"])
        self.assertEqual(r2["expected"], "I am ready")

        # Верный ответ (в том числе со стяжением I'm)
        r_ok = check_exercise_answer(ex_order, ["I", "am", "ready"], attempt=1)
        self.assertTrue(r_ok["correct"])

        # Проверка match
        l1 = get_lesson_by_id("a0-l1")
        ex_match = next(x for x in l1["exercises"] if x["type"] == "match")
        good_map = {p["left"]: p["right"] for p in ex_match["pairs"]}
        self.assertTrue(check_exercise_answer(ex_match, good_map)["correct"])
        bad_map = dict(good_map)
        bad_map["cat"] = "автобус"
        self.assertFalse(check_exercise_answer(ex_match, bad_map)["correct"])

        # Проверка письменного ответа B2
        b2_l2 = get_lesson_by_id("b2-l2")
        ex_free = next(x for x in b2_l2["exercises"] if x["type"] == "free_writing")
        self.assertFalse(check_exercise_answer(ex_free, "Привет мир")["correct"])
        self.assertTrue(
            check_exercise_answer(
                ex_free,
                "Automation reduces manual work across departments; however, clear staff training remains very important for quality.",
            )["correct"]
        )

    def test_unlock_progression_and_exam_gate(self):
        state = create_default_state()
        unlocks = compute_unlock_map(state)
        self.assertTrue(unlocks["a0-l1"])
        self.assertFalse(unlocks["a0-l2"])
        self.assertFalse(unlocks["a1-l1"])

        # Нельзя сдать закрытый урок в обход очереди
        with self.assertRaises(PermissionError):
            complete_lesson_attempt(state, "a0-l2", {})

        # Низкий балл (< 75%) не открывает следующий урок
        l1 = get_lesson_by_id("a0-l1")
        complete_lesson_attempt(state, "a0-l1", {l1["exercises"][0]["id"]: True})
        self.assertFalse(compute_unlock_map(state)["a0-l2"])

        # Полное прохождение A0 открывает A1 только после сдачи экзамена A0 >= 80%
        all_a0 = [x for x in get_all_lessons_flat() if x["level"] == "A0"]
        for item in all_a0[:-1]:
            all_true = {ex["id"]: True for ex in item["exercises"]}
            out = complete_lesson_attempt(state, item["id"], all_true)
            self.assertTrue(out["passed"])

        # До сдачи a0-exam уровень A1 закрыт
        self.assertTrue(compute_unlock_map(state)["a0-exam"])
        self.assertFalse(compute_unlock_map(state)["a1-l1"])

        exam = all_a0[-1]
        # 60% на экзамене недостаточно (порог 80%)
        sixty_pct = {ex["id"]: (idx < 3) for idx, ex in enumerate(exam["exercises"])}
        out_fail = complete_lesson_attempt(state, exam["id"], sixty_pct)
        self.assertFalse(out_fail["passed"])
        self.assertFalse(compute_unlock_map(state)["a1-l1"])

        # 100% на экзамене A0 открывает A1!
        all_exam_ok = {ex["id"]: True for ex in exam["exercises"]}
        out_pass = complete_lesson_attempt(state, exam["id"], all_exam_ok)
        self.assertTrue(out_pass["passed"])
        self.assertTrue(compute_unlock_map(state)["a1-l1"])
        self.assertEqual(state["current_level"], "A1")

    def test_spaced_repetition_and_mistakes_journal(self):
        state = create_default_state()
        words = get_base_vocabulary()
        wid = words[0]["id"]

        # Ошибки помечают слово трудным со 2-го промаха
        review_vocab_word(state, wid, False)
        w2 = review_vocab_word(state, wid, False)
        self.assertTrue(w2["is_hard"])
        self.assertEqual(w2["status"], "learning")

        # Успешные повторения продвигают по коробкам SRS до mastered
        for _ in range(4):
            w_ok = review_vocab_word(state, wid, True)
        self.assertEqual(w_ok["status"], "mastered")

        # Ручное переключение трудного слова
        toggled = toggle_hard_word(state, wid)
        self.assertFalse(toggled["is_hard"])
        self.assertEqual(len(get_vocabulary_items(state, mode="mastered")), 1)

        # Журнал ошибок и закрытие после двух чистых ответов
        les = get_lesson_by_id("a0-l1")
        ex = les["exercises"][0]
        record_exercise_attempt(state, les["id"], ex, "неверно", attempt=1)
        self.assertEqual(build_progress_report(state)["unresolved_mistakes_count"], 1)
        record_exercise_attempt(state, les["id"], ex, ex["answer"], attempt=1)
        self.assertEqual(build_progress_report(state)["unresolved_mistakes_count"], 1)
        record_exercise_attempt(state, les["id"], ex, ex["answer"], attempt=1)
        self.assertEqual(build_progress_report(state)["unresolved_mistakes_count"], 0)

    def test_persistence_migration_and_corrupted_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ea_state.json"

            # 1. Миграция старой схемы v1
            legacy_v1 = {
                "schema_version": 1,
                "completed_lessons": ["a0-l1", "a0-l2"],
                "study_seconds": 600,
            }
            migrated = migrate_state(legacy_v1)
            self.assertEqual(migrated["schema_version"], SCHEMA_VERSION)
            self.assertTrue(migrated["lessons"]["a0-l1"]["passed"])
            self.assertTrue(migrated["lessons"]["a0-l2"]["passed"])
            save_state(migrated, p)

            reloaded = load_state(p)
            self.assertEqual(reloaded["study_seconds"], 600)
            self.assertTrue(reloaded["lessons"]["a0-l1"]["passed"])

            # 2. Экспорт и импорт
            bundle = export_progress_bundle(reloaded)
            imported = import_progress_bundle(bundle)
            self.assertEqual(imported["lessons"]["a0-l2"]["score"], 85)

            # 3. Защита от повреждённого JSON
            p.write_text("{corrupted_json: [1, 2,", encoding="utf-8")
            recovered = load_state(p)
            self.assertEqual(recovered["schema_version"], SCHEMA_VERSION)
            self.assertEqual(recovered["current_level"], "A0")
            self.assertTrue(p.with_suffix(".corrupted.bak").exists())

    def test_offline_tutor_and_api_endpoints(self):
        state = create_default_state()
        reply = ask_english_tutor(state, mode="explain", message="", lesson_id="a0-l1", force_offline=True)
        self.assertFalse(reply["online"])
        self.assertIn("Алфавит", reply["answer"])

        hint_reply = ask_english_tutor(state, mode="hint", message="Help", lesson_id="a0-l4", force_offline=True)
        self.assertIn("Подсказка", hint_reply["answer"])

        # HTTP интеграция через FastAPI TestClient
        client = TestClient(app)
        r_boot = client.get("/api/english-academy/bootstrap")
        self.assertEqual(r_boot.status_code, 200)
        payload = r_boot.json()
        self.assertIn("curriculum", payload)
        self.assertIn("progress", payload)
        self.assertEqual(len(payload["curriculum"]["levels"]), 5)


if __name__ == "__main__":
    unittest.main()
