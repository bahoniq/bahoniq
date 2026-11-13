from unittest import TestCase
from unittest.mock import patch

from . import ai_interpreter, report_engine
from .launcher import (
    ReportGenerationError,
    _apply_ai_to_report_model,
    _require_real_ai,
)
from .report_engine import resolve_plan
from .report_engine import _ask_plan


class AIOnlyModeTests(TestCase):
    def test_fallback_is_rejected(self):
        with self.assertRaises(ReportGenerationError):
            _require_real_ai({"available": False, "source": "fallback"})

    def test_incomplete_ollama_result_is_rejected(self):
        with self.assertRaises(ReportGenerationError):
            _require_real_ai({"available": True, "source": "ollama", "summary": "x"})

    def test_complete_ollama_result_is_accepted(self):
        _require_real_ai({
            "available": True, "source": "ollama", "summary": "Резюме",
            "findings": ["Факт 1"], "stories": [{"topic": "A"}, {"topic": "B"}],
        })

    @patch.object(report_engine, "_ask_plan")
    def test_generic_request_always_uses_qwen_plan(self, ask):
        ask.return_value = {
            "title": "", "goal": "Анализ", "metrics": [], "dimensions": ["Группа"],
            "date_column": None, "grain": "auto", "start": None, "end": None,
            "filters": [], "comparisons": [], "questions": [], "notes": [],
            "source": "ollama", "model": "qwen",
        }
        analysis = {
            "headers": ["Группа"], "rows": [["A"], ["B"]],
            "numeric_columns": [],
            "categorical_columns": [{"index": 0, "name": "Группа", "kind": "categorical", "role": "dimension", "unique_count": 2}],
            "date_columns": [],
        }
        plan = resolve_plan(analysis, "")
        self.assertEqual(plan["source"], "ollama")
        ask.assert_called_once()

    def test_qwen_narrative_replaces_template_text(self):
        model = {
            "title": "Шаблон", "goal": "Шаблонная цель", "tasks": [], "notes": [],
            "findings": [{"text": "Старый вывод", "source": "local"}],
            "pages": [
                {"title": "Структура: Форма оплаты", "lead": "Шаблон", "note": "База", "table": []},
                {"title": "Структура: Факультет", "lead": "Шаблон 2", "note": "База", "table": []},
            ],
        }
        ai = {
            "report_title": "Структура финансирования", "summary": "Резюме Qwen",
            "research_plan": ["Сравнить формы оплаты"], "findings": ["60% записей относятся к платной форме"],
            "limitations": ["Текущий срез не показывает динамику"],
            "stories": [{
                "topic": "Форма оплаты", "headline": "Платная форма преобладает",
                "evidence": "Платная форма составляет 60%.",
                "interpretation": "Структура зависит от собственных средств.",
                "limitation": "Причины из данных не следуют.", "action": "",
            }, {
                "topic": "Факультет", "headline": "Крупнейший факультет выделяется",
                "evidence": "Крупнейшая группа содержит 40% записей.",
                "interpretation": "Структура распределена неравномерно.",
                "limitation": "Причины не установлены.", "action": "",
            }],
        }
        result = _apply_ai_to_report_model(model, ai)
        self.assertEqual(result["title"], "Структура финансирования")
        self.assertEqual(result["goal"], "Резюме Qwen")
        self.assertEqual(result["pages"][0]["title"], "Платная форма преобладает")
        self.assertNotIn("Шаблон", result["pages"][0]["lead"])

    def test_qwen_stories_remove_unselected_technical_pages(self):
        model = {
            "title": "Отчёт", "goal": "", "tasks": [], "notes": [], "findings": [],
            "pages": [
                {"title": "Структура: Факультет", "lead": "", "note": "", "table": []},
                *[{"title": f"Динамика: число записей ({i})", "lead": "", "note": "", "table": []}
                  for i in range(1, 30)],
                {"title": "Структура: Язык обучения", "lead": "", "note": "", "table": []},
            ],
        }
        ai = {
            "summary": "Резюме", "findings": ["Факт"], "limitations": [],
            "stories": [
                {"topic": "Факультет", "headline": "Факультеты", "evidence": "Факт 1"},
                {"topic": "Язык обучения", "headline": "Языки", "evidence": "Факт 2"},
            ],
        }
        result = _apply_ai_to_report_model(model, ai)
        self.assertEqual([p["title"] for p in result["pages"]], ["Факультеты", "Языки"])

    @patch.object(ai_interpreter, "_call_ollama")
    @patch.object(ai_interpreter, "_discover_ollama_model", return_value="qwen")
    @patch.object(report_engine.urllib.request, "urlopen")
    def test_questions_trigger_autonomous_recovery(self, urlopen, discover, call):
        import json

        first = {
            "metrics": [], "dimensions": [], "date_column": None,
            "grain": "auto", "start": None, "end": None, "filters": [],
            "comparisons": [], "questions": ["Нужно ли объединение файлов?"],
            "notes": [],
        }
        recovered = {
            "metrics": [], "dimensions": ["Факультет", "Форма оплаты"],
            "date_column": None, "grain": "auto", "start": None, "end": None,
            "filters": [], "comparisons": [], "questions": [], "notes": [],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                payload = {"response": json.dumps(first, ensure_ascii=False), "done": True}
                yield (json.dumps(payload, ensure_ascii=False) + "\n").encode()

        urlopen.return_value = Response()
        call.return_value = json.dumps(recovered, ensure_ascii=False)
        schema = [
            {"name": "Факультет", "kind": "categorical", "allowed": True, "distinct": 5},
            {"name": "Форма оплаты", "kind": "categorical", "allowed": True, "distinct": 2},
        ]
        result = _ask_plan("Проведи полный анализ", schema, "Автоматически", "Руководство")
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["dimensions"], ["Факультет", "Форма оплаты"])
        call.assert_called_once()

    @patch.object(ai_interpreter, "_discover_ollama_model", return_value="qwen")
    @patch.object(report_engine.urllib.request, "urlopen")
    def test_large_qwen_plan_is_compacted_without_user_question(self, urlopen, discover):
        import json

        plan = {
            "metrics": [
                {"column": f"N{i}", "aggregation": "mean"} for i in range(12)
            ],
            "dimensions": [f"D{i}" for i in range(12)],
            "date_column": None, "grain": "auto", "start": None, "end": None,
            "filters": [], "comparisons": [
                {"current": "N0", "previous": "N1", "aggregation": "mean"}
                for _ in range(12)
            ],
            "questions": [], "notes": [],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                event = {"response": json.dumps(plan), "done": True}
                yield (json.dumps(event) + "\n").encode()

        urlopen.return_value = Response()
        schema = (
            [{"name": f"N{i}", "kind": "numeric", "allowed": True, "distinct": 20} for i in range(12)] +
            [{"name": f"D{i}", "kind": "categorical", "allowed": True, "distinct": 4} for i in range(12)]
        )
        result = _ask_plan("Проведи полный анализ", schema, "Автоматически", "Руководство")
        self.assertEqual(len(result["metrics"]), 8)
        self.assertEqual(len(result["dimensions"]), 8)
        self.assertEqual(len(result["comparisons"]), 6)
        self.assertEqual(result["questions"], [])

    @patch.object(ai_interpreter, "_discover_ollama_model", return_value="qwen")
    @patch.object(report_engine.urllib.request, "urlopen")
    def test_personal_fields_from_qwen_plan_are_sanitized(self, urlopen, discover):
        import json

        plan = {
            "title": "Анализ контингента",
            "goal": "Оценить распределение",
            "metrics": [{"column": "Фамилия", "aggregation": "count"}],
            "dimensions": ["Фамилия", "Имя", "Форма оплаты", "Язык обучения"],
            "date_column": None, "grain": "auto", "start": None, "end": None,
            "filters": [{"column": "Фамилия", "op": "neq", "value": ""}],
            "comparisons": [], "questions": [], "notes": [],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                event = {"response": json.dumps(plan, ensure_ascii=False), "done": True}
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode()

        urlopen.return_value = Response()
        analysis = {
            "headers": ["Фамилия", "Имя", "Форма оплаты", "Язык обучения"],
            "rows": [
                ["Иванов", "Иван", "Платная", "Русский"],
                ["Сериков", "Али", "Грант", "Казахский"],
            ],
            "numeric_columns": [],
            "categorical_columns": [
                {"index": 0, "name": "Фамилия", "kind": "categorical", "role": "sensitive", "unique_count": 2},
                {"index": 1, "name": "Имя", "kind": "categorical", "role": "sensitive", "unique_count": 2},
                {"index": 2, "name": "Форма оплаты", "kind": "categorical", "role": "dimension", "unique_count": 2},
                {"index": 3, "name": "Язык обучения", "kind": "categorical", "role": "dimension", "unique_count": 2},
            ],
            "date_columns": [],
        }
        resolved = resolve_plan(analysis, "Проведи полный анализ")
        self.assertEqual(resolved["metrics"], [])
        self.assertEqual(resolved["dimensions"], ["Форма оплаты", "Язык обучения"])
        self.assertEqual(resolved["filters"], [])


if __name__ == "__main__":
    import unittest
    unittest.main()
