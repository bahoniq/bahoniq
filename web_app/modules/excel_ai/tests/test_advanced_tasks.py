import unittest

from modules.excel_ai.advanced_tasks import plan_advanced_request


ANALYSIS = {"sheets": [{
    "name": "Незаполненные журналы", "header_row": 3,
    "headers": ["№", "Факультет преподавателя", "Кафедра преподавателя", "Преподаватель", "Дисциплина/ Модуль", "Академический период", "Название главного потока", "Группа", "ОП", "Курс", "Количество обучающихся с не выставленной оценкой итогового контроля"],
}]}


class AdvancedTasksTests(unittest.TestCase):
    def test_colloquial_exact_filter_keeps_all_conditions(self):
        result = plan_advanced_request("вытащи тех у каво препод не назначен за акопериод осинь 2026 с 01.09.2026 по 31.12.2026 и итог скока их", ANALYSIS)
        action = result["operations"][0]["actions"][0]
        self.assertEqual(action["kind"], "filter")
        self.assertEqual(len(action["conditions"]), 2)
        self.assertIn("summary_output_sheet", action)

    def test_four_condition_filter_and_sort(self):
        result = plan_advanced_request("Отбери, где преподаватель не назначен, период осень 2026, курс равен 1, количество больше 3, затем сортируй по количеству", ANALYSIS)
        action = result["operations"][0]["actions"][0]
        self.assertEqual(len(action["conditions"]), 4)
        self.assertTrue(action["descending"])

    def test_vague_problem_request_requires_definition(self):
        result = plan_advanced_request("Покажи проблемные записи и сделай хороший отчёт", ANALYSIS)
        self.assertTrue(result["questions"])
        self.assertEqual(result["operations"], [])

    def test_destructive_vague_request_is_blocked(self):
        result = plan_advanced_request("Удали все неправильные строки и оставь полезные данные", ANALYSIS)
        self.assertTrue(result["questions"])
        self.assertEqual(result["operations"], [])

    def test_clean_copy_does_not_add_unrequested_filter(self):
        result = plan_advanced_request("Создай очищенную копию, убери пробелы и унифицируй преподаватель не назначен. На листе Изменения покажи старое и новое значение", ANALYSIS)
        actions = result["operations"][0]["actions"]
        self.assertEqual([item["kind"] for item in actions], ["clean_copy"])


if __name__ == "__main__":
    unittest.main()
