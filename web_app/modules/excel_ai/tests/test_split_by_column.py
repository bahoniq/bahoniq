
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from modules.excel_ai.operations import (
    plan_operations,
    execute_operations,
)


class SplitByColumnSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.source = self.root / "source.xlsx"
        self.output = self.root / "result.xlsx"
        self.split_dir = self.root / "groups"

        wb = Workbook()
        ws = wb.active
        ws.title = "Students"

        ws.append(["ID", "Name", "Course"])
        ws.append([1, "Aruzhan", "A"])
        ws.append([2, "Dias", "B"])
        ws.append([3, "Mira", "A"])

        wb.save(self.source)
        wb.close()

    def tearDown(self):
        self.temp.cleanup()

    def make_plan(self):
        return plan_operations(
            self.source,
            self.output,
            [{
                "type": "split_by_column",
                "sheet": "Students",
                "column": "Course",
                "output_dir": str(self.split_dir),
            }],
        )

    def test_creates_all_group_files(self):
        result = execute_operations(
            self.make_plan(),
            confirmed=True,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.split_dir.is_dir())

        self.assertEqual(
            {p.name for p in self.split_dir.glob("*.xlsx")},
            {"A.xlsx", "B.xlsx"},
        )

        wb = load_workbook(self.split_dir / "A.xlsx", read_only=True)
        try:
            ws = wb["Students"]
            self.assertEqual(ws["A1"].value, "ID")
            self.assertEqual(ws["B2"].value, "Aruzhan")
            self.assertEqual(ws["B3"].value, "Mira")
        finally:
            wb.close()

    def test_rejects_nonempty_output_directory_without_changes(self):
        self.split_dir.mkdir()
        existing = self.split_dir / "keep.txt"
        existing.write_text("Не удалять", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            execute_operations(
                self.make_plan(),
                confirmed=True,
            )

        self.assertEqual(
            existing.read_text(encoding="utf-8"),
            "Не удалять",
        )
        self.assertEqual(list(self.split_dir.iterdir()), [existing])

    def test_rolls_back_created_files_if_commit_fails(self):
        # Создаём пустую папку заранее: она должна сохраниться.
        self.split_dir.mkdir()

        real_link = __import__("os").link
        calls = {"count": 0}

        def failing_link(src, dst, *args, **kwargs):
            calls["count"] += 1

            if calls["count"] == 2:
                raise OSError("Имитируем ошибку публикации")

            return real_link(src, dst, *args, **kwargs)

        with patch(
            "modules.excel_ai.operations.os.link",
            side_effect=failing_link,
        ):
            with self.assertRaisesRegex(
                OSError,
                "Имитируем ошибку публикации",
            ):
                execute_operations(
                    self.make_plan(),
                    confirmed=True,
                )

        self.assertTrue(self.split_dir.is_dir())
        self.assertEqual(list(self.split_dir.iterdir()), [])

        # Основной результат также не должен быть опубликован.
        self.assertFalse(self.output.exists())

    def test_does_not_overwrite_existing_group_file(self):
        # Имитируем появление файла после проверки папки,
        # но до публикации подготовленных результатов.
        self.split_dir.mkdir()
        existing = self.split_dir / "B.xlsx"
        existing.write_bytes(b"DO NOT OVERWRITE")

        real_link = __import__("os").link

        def create_conflict_then_link(src, dst, *args, **kwargs):
            dst = Path(dst)

            if dst.name == "A.xlsx":
                return real_link(src, dst, *args, **kwargs)

            if dst.name == "B.xlsx":
                # Файл уже существует, публикация должна завершиться
                # ошибкой, не затронув его содержимое.
                return real_link(src, dst, *args, **kwargs)

            return real_link(src, dst, *args, **kwargs)

        # Папка с существующим файлом должна быть отклонена заранее.
        with self.assertRaises(FileExistsError):
            execute_operations(
                self.make_plan(),
                confirmed=True,
            )

        self.assertEqual(existing.read_bytes(), b"DO NOT OVERWRITE")
        self.assertFalse((self.split_dir / "A.xlsx").exists())


if __name__ == "__main__":
    unittest.main()
