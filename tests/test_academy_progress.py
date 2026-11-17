# -*- coding: utf-8 -*-
import unittest
import os
import sys

# Добавляем пути в sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP_DIR = os.path.join(BASE_DIR, "web_app")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if WEB_APP_DIR not in sys.path:
    sys.path.insert(0, WEB_APP_DIR)

from web_app.modules.code_academy.syllabus_data import STAGE_1_CANONICAL_IDS, resolve_stable_id
from web_app.modules.code_academy.db import (
    init_academy_db,
    get_roadmap_data,
    get_lesson_by_id,
    save_quiz_result,
    save_lesson_theory,
    mark_lesson_completed,
    sync_completed_lessons,
)


class TestAcademyProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_academy_db()

    def test_stable_ids_mapping(self):
        """Проверка наличия стабильных ID для всех уроков Этапа 1."""
        self.assertEqual(STAGE_1_CANONICAL_IDS[1], "python_01_environment")
        self.assertEqual(STAGE_1_CANONICAL_IDS[2], "python_02_variables")
        self.assertEqual(STAGE_1_CANONICAL_IDS[3], "python_03_numbers")

        self.assertEqual(resolve_stable_id(1, "environment-setup"), "python_01_environment")
        self.assertEqual(resolve_stable_id(2, "variables-types"), "python_02_variables")
        self.assertEqual(resolve_stable_id(3, "numbers-math"), "python_03_numbers")

    def test_lesson_2_retains_completed_after_init(self):
        """Урок 2 «Переменные» сохранен как завершенный, общий прогресс этапа 1 — 2/18."""
        roadmap = get_roadmap_data()
        stage1 = roadmap["stages"][0]
        self.assertEqual(stage1["id"], 1)

        lesson1 = next(l for l in stage1["lessons"] if l["id"] == 1)
        lesson2 = next(l for l in stage1["lessons"] if l["id"] == 2)

        self.assertTrue(lesson1["completed"], "Урок 1 должен быть завершен")
        self.assertTrue(lesson2["completed"], "Урок 2 должен быть завершен")
        self.assertEqual(lesson1["stable_id"], "python_01_environment")
        self.assertEqual(lesson2["stable_id"], "python_02_variables")

        # Проверяем, что завершено минимум 2 из 18
        self.assertGreaterEqual(stage1["completed_lessons"], 2)
        self.assertEqual(stage1["total_lessons"], 18)

    def test_next_recommended_lesson_is_3(self):
        """Следующий рекомендуемый к прохождению урок — №3."""
        roadmap = get_roadmap_data()
        stage1 = roadmap["stages"][0]
        first_incomplete = next((l for l in stage1["lessons"] if not l["completed"]), None)
        self.assertIsNotNone(first_incomplete)
        self.assertEqual(first_incomplete["id"], 3)
        self.assertEqual(first_incomplete["stable_id"], "python_03_numbers")

    def test_ai_theory_update_does_not_reset_progress(self):
        """Генерация нового примера от ИИ (обновление теории) не сбрасывает прогресс урока."""
        save_lesson_theory(2, "Обновленная теория от ИИ без сброса прогресса")
        l2 = get_lesson_by_id(2)
        self.assertTrue(l2["completed"], "Урок 2 должен оставаться завершенным после генерации ИИ")

    def test_sync_completed_lessons_idempotent(self):
        """Синхронизация стабильных ID идемпотентна и не создает дубликатов."""
        res1 = sync_completed_lessons(["python_01_environment", "python_02_variables"])
        self.assertTrue(res1["success"])

        # Повторная синхронизация тех же уроков
        res2 = sync_completed_lessons(["python_01_environment", "python_02_variables", 2])
        self.assertTrue(res2["success"])

        roadmap = get_roadmap_data()
        stage1 = roadmap["stages"][0]
        self.assertGreaterEqual(stage1["completed_lessons"], 2)

    def test_mark_lesson_completed_by_stable_id(self):
        """Административная отметка завершения урока по stable_id."""
        res = mark_lesson_completed("python_02_variables", score=5)
        self.assertTrue(res["success"])
        self.assertEqual(res["lesson_id"], 2)

        l2 = get_lesson_by_id(2)
        self.assertTrue(l2["completed"])


if __name__ == "__main__":
    unittest.main()
