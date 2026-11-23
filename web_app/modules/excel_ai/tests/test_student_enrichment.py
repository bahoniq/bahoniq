import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from ..smart_merge import enrich_student_list
from ..comparison import detect_student_columns


class StudentEnrichmentTests(unittest.TestCase):
    def test_reconcile_detects_descriptive_fio_and_email_headers(self):
        detected = detect_student_columns([
            "№", "Факультет", "ФИО обучающегося", "ФИО транслитом",
            "ИИН обучающегося", "Почта",
        ])
        self.assertEqual(detected["fio"], "ФИО обучающегося")
        self.assertEqual(detected["iin"], "ИИН обучающегося")
        self.assertEqual(detected["email"], "Почта")

    def _book(self, path, headers, rows):
        wb = Workbook()
        ws = wb.active
        ws.title = "Данные"
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(path)
        wb.close()

    def test_adds_missing_columns_by_email_and_iin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.xlsx"
            reference = root / "reference.xlsx"
            output = root / "result.xlsx"
            self._book(target, ["ФИО", "Почта"], [
                ["Иванов Иван", "IVANOV@EXAMPLE.COM "],
                ["Серикова Алия", "aliya@example.com"],
            ])
            self._book(reference, ["ФИО обучающегося", "Почта", "ИИН обучающегося", "Факультет", "Курс"], [
                ["Иванов Иван", "ivanov@example.com", "001234567890", "Медицина", 2],
                ["Серикова Алия", "aliya@example.com", "009876543210", "Фармация", 3],
            ])

            result = enrich_student_list(target, reference, output)

            self.assertEqual(result["matched"], 2)
            self.assertEqual(result["unmatched"], 0)
            self.assertEqual(result["methods"], {"email": 2})
            wb = load_workbook(output, data_only=True)
            try:
                ws = wb["Данные"]
                headers = [cell.value for cell in ws[1]]
                self.assertIn("Факультет", headers)
                self.assertIn("Курс", headers)
                faculty_col = headers.index("Факультет") + 1
                self.assertEqual(ws.cell(2, faculty_col).value, "Медицина")
                self.assertIn("Отчёт сопоставления", wb.sheetnames)
            finally:
                wb.close()

    def test_does_not_guess_duplicate_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.xlsx"
            reference = root / "reference.xlsx"
            output = root / "result.xlsx"
            self._book(target, ["ФИО", "Комментарий"], [["Иванов Иван", "проверить"]])
            self._book(reference, ["ФИО обучающегося", "ID"], [
                ["Иванов Иван", 10],
                ["Иванов Иван", 11],
            ])

            result = enrich_student_list(target, reference, output)

            self.assertEqual(result["matched"], 0)
            self.assertEqual(result["ambiguous"], 1)
            wb = load_workbook(output, data_only=True)
            try:
                audit = wb["Отчёт сопоставления"]
                self.assertEqual(audit.cell(12, 2).value, "Неоднозначное совпадение")
            finally:
                wb.close()


if __name__ == "__main__":
    unittest.main()
