import unittest

from modules.excel_ai.autonomous_planner import plan_autonomously


STUDENT = {
    "sheets": [{
        "name": "Sheet0",
        "headers": ["Фамилия", "Имя", "Отчество", "Образовательная программа", "Форма оплаты"],
        "semantic_profile": {"columns": [
            {"name": "Фамилия", "inferred_type": "text", "examples": ["Иванов"]},
            {"name": "Имя", "inferred_type": "text", "examples": ["Иван"]},
            {"name": "Отчество", "inferred_type": "text", "examples": ["Иванович"]},
            {"name": "Образовательная программа", "inferred_type": "text", "examples": ["Медицина"]},
            {"name": "Форма оплаты", "inferred_type": "text", "examples": ["Платная", "Бесплатная"]},
        ]},
        "duplicate_columns": [{
            "header": "Форма оплаты",
            "examples": [{"value": "Платная"}, {"value": "Бесплатная"}],
        }],
    }]
}

COUNTRIES = {
    "sheets": [{
        "name": "Статистика стран мира",
        "headers": ["Страна", "Континент / Регион", "Население", "ВВП на душу"],
        "semantic_profile": {"columns": [
            {"name": "Страна", "inferred_type": "text", "examples": ["Казахстан"]},
            {"name": "Континент / Регион", "inferred_type": "text", "examples": ["Азия", "Европа"]},
            {"name": "Население", "inferred_type": "number", "examples": [20000000]},
            {"name": "ВВП на душу", "inferred_type": "number", "examples": [14000]},
        ]},
    }]
}


class AutonomousModernizationTests(unittest.TestCase):
    def test_01_to_10_copy_named_columns(self):
        variants = [
            "Перенеси столбцы Фамилия Имя Отчество на новый лист",
            "Скопируй Фамилия, Имя и Отчество в новую таблицу",
            "Выведи на отдельный лист Фамилия Имя Отчество",
            "Возьми Фамилия, Имя, Отчество и создай новый лист",
            "Перенеси данные Фамилия и Имя на новый лист",
            "Скопируй столбцы Имя и Фамилия на отдельный лист",
            "Выведи Фамилия и Отчество в новую таблицу",
            "Возьми Имя и Отчество на новый лист",
            "Перенеси Фамилия, Имя на отдельный лист",
            "Скопируй Имя, Отчество в новую таблицу",
        ]
        for task in variants:
            with self.subTest(task=task):
                result = plan_autonomously(task, STUDENT)
                self.assertIsNotNone(result)
                self.assertEqual(result["operations"][0]["type"], "copy_columns_to_sheet")
                self.assertGreaterEqual(len(result["operations"][0]["columns"]), 2)

    def test_11_to_20_count_and_compare(self):
        variants = [
            "Посчитай студентов по образовательным программам и сравни платное и бесплатное обучение",
            "Сравни платных и бесплатных студентов и посчитай их по образовательным программам",
            "Количество студентов по образовательным программам, сравни платную и бесплатную форму оплаты",
            "Посчитай записи по образовательной программе и сравни платное с бесплатным",
            "Сравни бесплатное и платное обучение, затем посчитай по образовательным программам",
            "Посчитай по образовательным программам и сравни категории Платная и Бесплатная",
            "Нужно сравнить платную и бесплатную оплату и посчитать студентов по образовательной программе",
            "Посчитай количество по образовательной программе, сравни Платная и Бесплатная",
            "Сравни формы Платная и Бесплатная, посчитай количество по образовательным программам",
            "Посчитай студентов по программам и сравни платное и бесплатное",
        ]
        for task in variants:
            with self.subTest(task=task):
                result = plan_autonomously(task, STUDENT)
                self.assertIsNotNone(result)
                types = [op["type"] for op in result["operations"]]
                self.assertEqual(types, ["group_by_aggregate", "pivot_count"])

    def test_21_to_30_split_count_average(self):
        variants = [
            "Раздели страны по континентам, посчитай количество и сравни средний ВВП на душу",
            "Посчитай страны по регионам, раздели их и покажи средний ВВП на душу",
            "Раздели по Континент / Регион и посчитай страны, средний ВВП на душу",
            "Количество стран по континентам, раздели по регионам и вычисли средний ВВП на душу",
            "Раздели список по регионам, посчитай количество и найди средний ВВП на душу",
            "Посчитай по Континент / Регион, раздели на листы и сравни средний ВВП на душу",
            "Раздели страны по континентам и посчитай их, покажи средний ВВП на душу",
            "Найди средний ВВП на душу по регионам, посчитай страны и раздели по континентам",
            "Посчитай количество стран по регионам, раздели список и рассчитай средний ВВП на душу",
            "Раздели по континентам, количество стран и средний ВВП на душу",
        ]
        for task in variants:
            with self.subTest(task=task):
                result = plan_autonomously(task, COUNTRIES)
                self.assertIsNotNone(result)
                types = [op["type"] for op in result["operations"]]
                self.assertEqual(types, ["split_to_sheets", "group_by_aggregate", "group_by_aggregate"])
                self.assertEqual(result["operations"][0]["column"], "Континент / Регион")
                self.assertEqual(result["operations"][2]["target_column"], "ВВП на душу")


if __name__ == "__main__":
    unittest.main()
