import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from modules.excel_ai.analyzer import analyze_workbook


class WorkbookAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "sample.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Students"
        sheet.append(["ID", "Name", "Score"])
        sheet.append([1, "Aruzhan", 90])
        sheet.append([2, "Dias", 85])
        sheet.append([2, "Dias", 85])
        sheet.append([3, "Aruzhan", "=SUM(C2:C4)"])
        sheet.append([4, None, 70])
        sheet.append([None, None, None])

        hidden = workbook.create_sheet("Hidden")
        hidden.sheet_state = "hidden"
        hidden.append(["Note"])
        hidden.append(["Internal"])

        workbook.save(self.path)
        workbook.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reports_sheet_names_and_hidden_sheets(self):
        report = analyze_workbook(self.path)
        self.assertEqual(report["sheet_count"], 2)
        self.assertEqual(report["sheets"][0]["name"], "Students")
        self.assertTrue(report["sheets"][1]["hidden"])

    def test_detects_duplicate_rows_and_column_values(self):
        report = analyze_workbook(self.path)
        students = report["sheets"][0]
        self.assertEqual(students["duplicate_rows"], 1)

        name_column = next(
            col for col in students["duplicate_columns"]
            if col["header"] == "Name"
        )
        self.assertEqual(name_column["duplicate_value_count"], 2)
        self.assertEqual(name_column["examples"][0]["value"], "Aruzhan")

    def test_detects_formula_and_blank_cells(self):
        report = analyze_workbook(self.path)
        students = report["sheets"][0]
        self.assertEqual(students["formula_count"], 1)
        self.assertGreater(students["blank_cells"], 0)

    def test_report_can_be_serialised_as_json(self):
        report = analyze_workbook(self.path)
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertIn("Students", encoded)

    def test_rejects_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            analyze_workbook(self.path.parent / "missing.xlsx")


if __name__ == "__main__":
    unittest.main()
