from __future__ import annotations

from unittest import TestCase

from .ai_interpreter import _normalize_model_result
from .pdf_builder import _v52_fact


class AnalyticsQualityGuardTests(TestCase):
    def test_category_share_uses_filled_values_as_denominator(self):
        column = {
            "count": 80,
            "missing_count": 20,
            "statistics": {
                "top_values": [
                    {"value": "Алматы", "count": 40},
                    {"value": "Астана", "count": 24},
                ],
            },
        }

        fact, share, _ = _v52_fact(column, 100)

        self.assertEqual(share, 50.0)
        self.assertIn("50.0% от 80 заполненных", fact)

    def test_complete_category_keeps_total_denominator_wording_compact(self):
        column = {
            "count": 100,
            "missing_count": 0,
            "statistics": {
                "top_values": [
                    {"value": "Алматы", "count": 40},
                    {"value": "Астана", "count": 24},
                ],
            },
        }

        fact, share, _ = _v52_fact(column, 100)

        self.assertEqual(share, 40.0)
        self.assertIn("(40.0%)", fact)
        self.assertNotIn("заполненных значений", fact)

    def test_unsupported_claims_are_removed_and_wording_is_corrected(self):
        result = _normalize_model_result({
            "summary": "Резидентура полностью зависит от гранта на 57.3%.",
            "findings": [
                "Сегмент содержит 100 студентов (57.3%).",
                "Высокая доля формирует стабильный валютный источник доходов.",
            ],
            "risks": ["Платежеспособность создаёт риск отчисления."],
            "recommendations": ["Сопоставить долю 57.3% с планом."],
            "stories": [
                {
                    "topic": "Форма оплаты",
                    "headline": "Суперконцентрация оплаты",
                    "evidence": "Платная форма — 100 студентов (57.3%).",
                    "interpretation": "Это гарантирует рост доходов и нагрузку на кафедры.",
                    "limitation": "",
                    "action": "Снизить риск отчисления по платежеспособности.",
                },
                {
                    "topic": "Язык обучения",
                    "headline": "Структура языков",
                    "evidence": "Казахский язык — 80 студентов (46.0%).",
                    "interpretation": "Текущий срез описывает распределение.",
                    "limitation": "Причины не установлены.",
                    "action": "",
                },
            ],
        }, "test")

        self.assertIn("в значительной степени", result["summary"])
        self.assertEqual(result["risks"], [])
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["stories"][0]["headline"], "Высокая концентрация оплаты")
        self.assertEqual(result["stories"][0]["interpretation"], "")
        self.assertEqual(result["stories"][0]["action"], "")


if __name__ == "__main__":
    import unittest
    unittest.main()
