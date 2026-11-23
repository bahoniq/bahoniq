from __future__ import annotations

from unittest import TestCase

from .ai_interpreter import _normalize_model_result


class AnalyticsQualityGuardTests(TestCase):
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
