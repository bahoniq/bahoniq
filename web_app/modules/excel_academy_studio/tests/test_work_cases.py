import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from openpyxl import load_workbook

try:
    from web_app.modules.excel_academy_studio.work_cases import CASES, source_path, validate_submission
except ImportError:
    from modules.excel_academy_studio.work_cases import CASES, source_path, validate_submission


class WorkCaseTests(unittest.TestCase):
    def test_all_eight_sources_are_valid_workbooks(self):
        self.assertEqual(len(CASES), 8)
        for case in CASES:
            path = source_path(case["id"])
            self.assertTrue(path.exists(), path)
            self.assertTrue(load_workbook(path).worksheets)

    def test_unchanged_source_without_answers_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "attempt.xlsx"
            shutil.copy2(source_path("registry-cleanup"), target)
            result = validate_submission("registry-cleanup", target)
            self.assertFalse(result["passed"])
            self.assertLess(result["score"], 80)

    def test_reconciliation_accepts_correct_real_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "result.xlsx"
            shutil.copy2(source_path("student-reconciliation"), target)
            wb = load_workbook(target)
            ws = wb.create_sheet("Сверка")
            ws.append(["ID", "Статус"])
            for item_id in range(2001, 2091):
                if item_id <= 2065:
                    status = "Совпало"
                elif item_id <= 2080:
                    status = "Только в деканате"
                else:
                    status = "Только в общежитии"
                ws.append([item_id, status])
            wb.save(target)
            result = validate_submission("student-reconciliation", target)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["score"], 100)

    def test_source_edit_is_critical_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tampered.xlsx"
            shutil.copy2(source_path("student-reconciliation"), target)
            wb = load_workbook(target)
            wb["Деканат"]["A2"] = 999999
            ws = wb.create_sheet("Сверка")
            ws.append(["ID", "Статус"])
            for item_id in range(2001, 2091):
                status = "Совпало" if item_id <= 2065 else ("Только в деканате" if item_id <= 2080 else "Только в общежитии")
                ws.append([item_id, status])
            wb.save(target)
            result = validate_submission("student-reconciliation", target)
            self.assertFalse(result["passed"])
            self.assertTrue(any(not x["passed"] and x["critical"] for x in result["results"]))


if __name__ == "__main__":
    unittest.main()
