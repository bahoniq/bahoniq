import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.excel_ai.operations import plan_operations, execute_operations


class SafeOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.xlsx"
        self.output = self.root / "result.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["ID", "Name", "Status"])
        ws.append([1, "Aruzhan", None])
        ws.append([2, "Dias", "OK"])
        ws.append([2, "Dias", "OK"])
        ws.append([None, None, None])
        wb.save(self.source)
        wb.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_does_not_change_source(self):
        before = self.source.read_bytes()
        plan = plan_operations(
            self.source,
            self.output,
            [{"type": "fill_empty", "sheet": "Data",
              "columns": [3], "value": "Pending"}],
        )
        self.assertTrue(plan["requires_confirmation"])
        self.assertFalse(plan["source_will_be_modified"])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(self.output.exists())

    def test_execution_requires_confirmation(self):
        plan = plan_operations(
            self.source,
            self.output,
            [{"type": "remove_duplicates", "sheet": "Data", "columns": [1, 2]}],
        )
        with self.assertRaises(PermissionError):
            execute_operations(plan)
        self.assertFalse(self.output.exists())

    def test_execution_creates_output_and_backup(self):
        plan = plan_operations(
            self.source,
            self.output,
            [
                {"type": "fill_empty", "sheet": "Data",
                 "columns": [3], "value": "Pending"},
                {"type": "remove_duplicates", "sheet": "Data", "columns": [1, 2]},
                {"type": "remove_empty_rows", "sheet": "Data"},
            ],
        )

        report = execute_operations(plan, confirmed=True)
        self.assertEqual(report["status"], "completed")
        self.assertTrue(self.output.is_file())
        self.assertTrue(Path(report["backup"]).is_file())
        self.assertFalse(report["source_modified"])

        wb = load_workbook(self.output, data_only=False)
        try:
            ws = wb["Data"]
            self.assertEqual(ws["C2"].value, "Pending")
            self.assertEqual(ws.max_row, 3)
        finally:
            wb.close()

        original = load_workbook(self.source, data_only=False)
        try:
            self.assertEqual(original["Data"].max_row, 4)
            self.assertIsNone(original["Data"]["C2"].value)
        finally:
            original.close()

    def test_find_duplicate_rows_reports_without_changing_source(self):
        before = self.source.read_bytes()

        plan = plan_operations(
            self.source,
            self.output,
            [{
                "type": "find_duplicate_rows",
                "sheet": "Data",
                "header_rows": 1,
            }],
        )

        report = execute_operations(plan, confirmed=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(self.output.is_file())
        self.assertFalse(report["source_modified"])

        duplicate_report = report["reports"]["duplicate_rows"][0]
        self.assertEqual(duplicate_report["duplicate_groups_count"], 1)
        self.assertEqual(duplicate_report["repeated_rows_count"], 1)
        self.assertEqual(
            duplicate_report["duplicate_groups"][0]["rows"], [3, 4]
        )

    def test_rejects_source_as_output(self):
        with self.assertRaises(ValueError):
            plan_operations(
                self.source,
                self.source,
                [{"type": "remove_empty_rows", "sheet": "Data"}],
            )

    def test_rejects_unknown_operation(self):
        with self.assertRaises(ValueError):
            plan_operations(
                self.source,
                self.output,
                [{"type": "delete_everything", "sheet": "Data"}],
            )


if __name__ == "__main__":
    unittest.main()
