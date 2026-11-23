import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from ..comprehensive_audit import (
    REQUIRED_SHEETS,
    is_comprehensive_audit_request,
    run_comprehensive_audit,
    verify_comprehensive_audit_result,
)


def _make_book(path: Path, headers: list[str], rows: list[list]):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)


class ComprehensiveAuditTests(unittest.TestCase):
    def test_audit_end_to_end_conflicts_dups_errors(self):
        instruction = (
            "Проведи комплексную сверку всех загруженных файлов. "
            "Определи основную карточку каждого студента по ИИН, а при его отсутствии — по электронной почте и нормализованному ФИО. "
            "Объедини недостающие сведения, но не выбирай значение автоматически при конфликте. "
            "Удали полные дубликаты, сохрани вероятные дубликаты для проверки, найди некорректные ИИН и почтовые адреса, "
            "выяви расхождения по факультету, специальности, курсу и задолженности. "
            "Создай новый Excel с листами «Итоговая база», «Не найдены», «Неоднозначные совпадения», «Конфликты», «Дубликаты», «Ошибки данных» и «Сводка». "
            "Исходные файлы не изменяй и укажи причину каждого принятого решения."
        )
        self.assertTrue(is_comprehensive_audit_request(instruction))
        self.assertFalse(is_comprehensive_audit_request("Найди студентов из первого файла во втором и добавь недостающие столбцы"))

        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            f1 = tdir / "list1.xlsx"
            f2 = tdir / "list2.xlsx"
            out = tdir / "audit_out.xlsx"

            _make_book(
                f1,
                ["ФИО", "ИИН", "Почта", "Факультет", "Специальность", "Курс", "Сумма долга"],
                [
                    ["Иванов Иван Иванович", "010101500012", "ivanov@mail.ru", "Медицина", "Общая медицина", 2, 100000],
                    ["Иванов Иван Иванович", "010101500012", "ivanov@mail.ru", "Медицина", "Общая медицина", 2, 100000],  # exact dup
                    ["Петров Пётр", "", "bad email@", "Стоматология", "Стоматология", 1, 50000],  # invalid email + unmatched
                ],
            )
            _make_book(
                f2,
                ["ФИО обучающегося", "ИИН обучающегося", "Почта", "Факультет", "ГОП (Специальность)", "Курс", "Баланс за основное обучение"],
                [
                    ["Иванов Иван Иванович", "010101500012", "ivanov@mail.ru", "Фармация", "Фармация", 3, 250000],  # conflict in fac/spec/course/debt
                    ["Сидоров Сидор", "12345", "sidorov@gmail.com", "Медицина", "Медицина", 1, 0],  # invalid IIN
                ],
            )

            res = run_comprehensive_audit([f1, f2], instruction, out)
            self.assertTrue(res["verification"]["passed"], res["verification"]["errors"])
            self.assertEqual(res["counts"]["exact_duplicates"], 1)
            self.assertGreaterEqual(res["counts"]["conflicts"], 4)
            self.assertGreaterEqual(res["counts"]["invalid_iin"], 1)
            self.assertGreaterEqual(res["counts"]["invalid_email"], 1)
            self.assertEqual(res["counts"]["unmatched"], 1)

            wb = load_workbook(out, read_only=True)
            self.assertEqual(wb.sheetnames, REQUIRED_SHEETS)
            wb.close()

    def test_post_verification_rejects_missing_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            src = tdir / "src.xlsx"
            out = tdir / "broken.xlsx"
            _make_book(src, ["ФИО"], [["Тест"]])
            _make_book(out, ["Итоговая база"], [["Тест"]])
            v = verify_comprehensive_audit_result(
                output_path=out,
                requirements={"required_sheets": REQUIRED_SHEETS},
                source_hashes_before={str(src): ""},
                sources=[src],
                expected_counts={"conflicts": 0},
            )
            self.assertFalse(v["passed"])
            self.assertFalse(v["checks"]["exact_7_sheets"])


if __name__ == "__main__":
    unittest.main()
