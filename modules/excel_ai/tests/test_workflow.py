import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.excel_ai.engine import TaskEngine
from modules.excel_ai.models import TaskStatus
from modules.excel_ai.workflow import ExcelWorkflow


class ExcelWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "students.xlsx"
        self.output_dir = self.root / "results"

        wb = Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(["ID", "Name", "Status"])
        ws.append([1, "Aruzhan", None])
        ws.append([2, "Dias", "OK"])
        ws.append([2, "Dias", "OK"])
        wb.save(self.source)
        wb.close()

        self.engine = TaskEngine(self.root / "tasks.sqlite3")
        self.workflow = ExcelWorkflow(self.engine)
        self.operations = [
            {
                "type": "fill_empty",
                "sheet": "Students",
                "columns": [3],
                "value": "Pending",
            },
            {
                "type": "remove_duplicates",
                "sheet": "Students",
                "columns": [1, 2],
            },
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prepare_creates_plan_without_modifying_source(self):
        before = self.source.read_bytes()
        task = self.workflow.create_task(
            "Заполнить пропуски и удалить дубликаты",
            self.source,
            self.output_dir,
        )

        prepared = self.workflow.prepare(task.id, self.operations)

        self.assertEqual(prepared["task"].status, TaskStatus.PLANNED)
        self.assertTrue(prepared["requires_confirmation"])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(Path(prepared["plan"]["output"]).exists())

    def test_execution_requires_confirmation(self):
        task = self.workflow.create_task(
            "Очистить таблицу", self.source, self.output_dir
        )
        self.workflow.prepare(task.id, self.operations)

        with self.assertRaises(PermissionError):
            self.workflow.confirm_and_execute(task.id)

        self.assertEqual(
            self.engine.get_task(task.id).status, TaskStatus.PLANNED
        )

    def test_confirmed_execution_completes_and_records_history(self):
        task = self.workflow.create_task(
            "Обработать таблицу", self.source, self.output_dir
        )
        self.workflow.prepare(task.id, self.operations)
        response = self.workflow.confirm_and_execute(
            task.id, confirmed=True
        )

        self.assertEqual(response["task"].status, TaskStatus.COMPLETED)
        self.assertTrue(Path(response["result"]["output"]).is_file())
        self.assertTrue(Path(response["result"]["backup"]).is_file())
        self.assertFalse(response["result"]["source_modified"])

        history = self.workflow.get_history(task.id)
        event_types = [event["event_type"] for event in history["events"]]
        self.assertIn("plan_ready", event_types)
        self.assertIn("user_confirmed", event_types)
        self.assertIn("verification_passed", event_types)

        wb = load_workbook(response["result"]["output"])
        try:
            ws = wb["Students"]
            self.assertEqual(ws["C2"].value, "Pending")
            self.assertEqual(ws.max_row, 3)
        finally:
            wb.close()

        def test_invalid_task_source_fails_cleanly(self):
            missing_source = self.root / "missing.xlsx"

            with self.assertRaises(FileNotFoundError):
                self.workflow.create_task(
                "Анализ",
                missing_source,
                self.output_dir,
            )


if __name__ == "__main__":
    unittest.main()
