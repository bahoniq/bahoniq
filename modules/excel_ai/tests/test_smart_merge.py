import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from ..smart_merge import (
    analyze_multi_file_sources,
    execute_multi_file_plan,
    plan_multi_file_task,
    validate_multi_file_plan,
)


def _book(path, headers, rows, sheet="Data"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()


class MultiFileAITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_append_arbitrary_sales_files(self):
        jan = self.root / "jan.xlsx"
        feb = self.root / "feb.xlsx"
        _book(jan, ["Товар", "Регион", "Сумма"], [["A", "Север", 10]])
        _book(feb, ["Товар", "Регион", "Сумма"], [["B", "Юг", 20]])
        result = plan_multi_file_task("Объедини строки файлов друг под другом", [jan, feb])
        self.assertFalse(result["questions"])
        self.assertEqual(result["plan"]["mode"], "append")
        output = self.root / "sales.xlsx"
        executed = execute_multi_file_plan(result["plan"], result["schemas"], output)
        self.assertEqual(executed["records"], 2)
        wb = load_workbook(output, read_only=True, data_only=True)
        self.assertEqual([cell.value for cell in wb["Результат"][3]], ["B", "Юг", 20])
        wb.close()

    def test_join_arbitrary_employee_files(self):
        people = self.root / "people.xlsx"
        salary = self.root / "salary.xlsx"
        _book(people, ["ID", "ФИО", "Отдел"], [[1, "Алия", "ИТ"], [2, "Бек", "HR"]])
        _book(salary, ["Код", "Зарплата"], [[1, 500], [2, 400]])
        schemas = analyze_multi_file_sources([people, salary])
        raw_plan = {
            "mode": "join", "join_type": "inner", "deduplicate_by": [], "sort_by": [],
            "sources": [
                {"file_index": 0, "sheet": "Data", "key_columns": ["ID"], "columns": [
                    {"source": "ФИО", "output": "Сотрудник"}, {"source": "Отдел", "output": "Отдел"}
                ]},
                {"file_index": 1, "sheet": "Data", "key_columns": ["Код"], "columns": [
                    {"source": "Зарплата", "output": "Зарплата"}
                ]},
            ],
        }
        plan = validate_multi_file_plan(raw_plan, schemas)
        output = self.root / "employees.xlsx"
        executed = execute_multi_file_plan(plan, schemas, output)
        self.assertEqual(executed["records"], 2)
        wb = load_workbook(output, read_only=True, data_only=True)
        self.assertEqual([cell.value for cell in wb["Результат"][2]], ["Алия", "ИТ", 500])
        wb.close()

    def test_multilingual_directory_is_a_plan_not_hardcoded_executor(self):
        ru = self.root / "ru.xlsx"
        kk = self.root / "kk.xlsx"
        en = self.root / "en.xlsx"
        _book(ru, ["№", "Название организации", "Страна"], [[1, "Организация", "Казахстан"]])
        _book(kk, ["№", "Ұйым атауы", "Ел"], [[1, "Ұйым", "Қазақстан"]])
        _book(en, ["No.", "Organization name", "Country"], [[1, "Organization", "Kazakhstan"]])
        result = plan_multi_file_task(
            "Объедини по номеру, нужны названия на русском, казахском и английском и страна",
            [ru, kk, en],
        )
        self.assertFalse(result["questions"])
        self.assertEqual(result["plan"]["mode"], "join")
        self.assertEqual(len(result["plan"]["sources"]), 3)

    def test_rejects_invented_column(self):
        one = self.root / "one.xlsx"
        two = self.root / "two.xlsx"
        _book(one, ["ID", "Имя"], [[1, "A"]])
        _book(two, ["ID", "Сумма"], [[1, 10]])
        schemas = analyze_multi_file_sources([one, two])
        with self.assertRaisesRegex(ValueError, "Недопустимое сопоставление"):
            validate_multi_file_plan({
                "mode": "join", "join_type": "inner", "sources": [
                    {"file_index": 0, "sheet": "Data", "key_columns": ["ID"], "columns": [{"source": "Выдумано", "output": "X"}]},
                    {"file_index": 1, "sheet": "Data", "key_columns": ["ID"], "columns": [{"source": "Сумма", "output": "Сумма"}]},
                ]
            }, schemas)


if __name__ == "__main__":
    unittest.main()
