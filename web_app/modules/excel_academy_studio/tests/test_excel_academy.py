import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from web_app.modules.excel_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.excel_academy_studio.validation import validate_workbook


class TestExcelAcademyStudio(unittest.TestCase):

    def test_complete_curriculum(self):
        """Проверка структуры 6 этапов и 72 уроков."""
        course = get_curriculum()
        self.assertEqual(len(course["stages"]), 6, "Должно быть ровно 6 этапов")
        self.assertEqual(len(course["lessons"]), 72, "Должно быть ровно 72 урока")

        stage_counts = [sum(x["stage_id"] == s["id"] for x in course["lessons"]) for s in course["stages"]]
        self.assertEqual(stage_counts, [12, 14, 12, 12, 10, 12], "Распределение уроков по этапам должно быть 12, 14, 12, 12, 10, 12")

    def test_all_lessons_have_individual_professional_fields(self):
        """Каждый из 72 уроков должен содержать все обязательные поля без пропусков."""
        course = get_curriculum()
        required_fields = [
            "goal", "work_situation", "theory", "example",
            "task", "steps", "common_errors", "result",
            "professional_tip", "checks"
        ]
        lesson_ids = set()
        for lesson in course["lessons"]:
            lid = lesson["id"]
            self.assertNotIn(lid, lesson_ids, f"ID урока {lid} повторяется")
            lesson_ids.add(lid)

            for field in required_fields:
                self.assertIn(field, lesson, f"В уроке {lid} отсутствует поле {field}")
                val = lesson[field]
                if isinstance(val, (str, list)):
                    self.assertTrue(len(val) > 0, f"Поле {field} в уроке {lid} пустое")

            self.assertIsInstance(lesson["steps"], list, f"steps в {lid} должен быть списком")
            self.assertGreaterEqual(len(lesson["steps"]), 2, f"В {lid} должно быть минимум 2 шага")
            self.assertIsInstance(lesson["common_errors"], list, f"common_errors в {lid} должен быть списком")
            self.assertGreaterEqual(len(lesson["common_errors"]), 2, f"В {lid} должно быть минимум 2 типичные ошибки")

    def test_cell_and_formula_validation(self):
        """Проверка валидации ячеек и базовых формул."""
        book = {
            "activeSheet": 0,
            "sheets": [{"name": "Сотрудники", "cells": {"E6": {"value": "Уволен"}}}],
            "operations": [],
            "charts": [],
            "pivots": []
        }
        res1 = validate_workbook(book, get_lesson("1-1")["checks"])
        self.assertTrue(res1["passed"])

        book["sheets"][0]["cells"]["D2"] = {"formula": "=VLOOKUP(A2,Общежитие!A2:C7,3,FALSE)"}
        res2 = validate_workbook(book, get_lesson("2-2")["checks"])
        self.assertTrue(res2["passed"])

    def test_advanced_entities(self):
        """Проверка расширенных сущностей: сводные таблицы и диаграммы."""
        book = {
            "activeSheet": 0,
            "sheets": [{"name": "Картотека", "cells": {"B2": {"formula": "=TRIM(A2)"}}}],
            "operations": [],
            "charts": [{"type": "line", "data": [1, 2, 3]}],
            "pivots": [{"fields": ["A", "B"]}]
        }
        self.assertTrue(validate_workbook(book, get_lesson("3-2")["checks"])["passed"])
        self.assertTrue(validate_workbook(book, get_lesson("5-1")["checks"])["passed"])

    def test_reconciliation_requires_actual_statuses_and_journal(self):
        """Проверка сверки статусов и журнала."""
        book = {
            "activeSheet": 0,
            "sheets": [
                {"name": "Сверка", "cells": {"A1": {"value": "Совпало"}, "A2": {"value": "Только в A"}, "A3": {"value": "Только в B"}}},
                {"name": "Журнал", "cells": {"A1": {"value": "Ключ"}, "A2": {"value": "1"}, "A3": {"value": "2"}}}
            ],
            "operations": [],
            "charts": [],
            "pivots": []
        }
        self.assertTrue(validate_workbook(book, [{"kind": "required_texts", "expected": ["Совпало", "Только в A", "Только в B"]}])["passed"])
        self.assertTrue(validate_workbook(book, [{"kind": "used_rows_on_sheet", "sheet": "Журнал", "min": 3}])["passed"])

    def test_all_new_validation_rules(self):
        """Проверка всех расширенных типов проверок."""
        # 1. formula_at & calculated_value
        book1 = {
            "activeSheet": 0,
            "sheets": [{"name": "Sheet1", "cells": {"C1": {"formula": "=ROUNDUP(A1*1.15, 2)", "value": 115.5}}}],
            "operations": ["sort:A:asc", "filter:B"],
            "charts": [{"type": "bar", "data": [10, 20, 30]}],
            "pivots": [{"fields": ["A", "B"], "sheet": "Сводная_1"}],
            "filters": {"B": {"condition": "contains", "value": "IT"}}
        }
        self.assertTrue(validate_workbook(book1, [{"kind": "formula_at", "cell": "C1", "contains": "ROUNDUP"}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "calculated_value", "cell": "C1", "min": 100, "max": 120}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "sorted_column", "column": "A", "direction": "asc"}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "filtered_rows", "column": "B"}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "chart_source", "type": "bar", "min_data": 3}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "pivot_config", "fields": ["A", "B"]}])["passed"])
        self.assertTrue(validate_workbook(book1, [{"kind": "error_free_formulas"}])["passed"])

        # 2. formula_contains_refs
        book2 = {
            "activeSheet": 0,
            "sheets": [{"name": "Расчёт", "cells": {"E2": {"formula": "=IFERROR(VLOOKUP(A2; $B$2:$D$10; 3; FALSE); 0)"}}}],
            "operations": [],
            "charts": [],
            "pivots": []
        }
        self.assertTrue(validate_workbook(book2, [{"kind": "formula_contains_refs", "cell": "E2", "refs": ["A2", "B2:D10"]}])["passed"])


if __name__ == "__main__":
    unittest.main()
