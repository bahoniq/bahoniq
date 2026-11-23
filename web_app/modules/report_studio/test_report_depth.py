from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from . import launcher


class ReportDepthRegressionTests(TestCase):
    def test_web_route_positional_contract_accepts_report_depth(self):
        """The web route passes report_depth as the thirteenth argument."""
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.xlsx"
            source.write_bytes(b"test")
            matrix = [["Категория", "Значение"], ["A", 1], ["B", 2]]
            workbook = {
                "sheets": [{"name": "Лист1", "matrix": matrix, "warnings": []}],
                "warnings": [],
            }
            ai = {
                "available": True,
                "source": "cloud_ai",
                "summary": "Результат анализа",
                "findings": ["Вывод"],
                "stories": [{"topic": "A"}, {"topic": "B"}],
            }

            def fake_pdf(**kwargs):
                self.assertEqual(kwargs["report_depth"], "Краткий (C-Level, 3-4 стр)")
                target = Path(kwargs["output_dir"]) / "report.pdf"
                target.write_bytes(b"%PDF-test")
                return target

            with (
                patch.object(launcher, "read_excel", return_value=workbook),
                patch.object(launcher, "analyze_matrix", return_value={"row_count": 2, "column_count": 2}),
                patch.object(launcher, "generate_ai_analysis", return_value=ai),
                patch.object(launcher, "build_analytics_pdf", side_effect=fake_pdf),
                patch.object(launcher, "add_record"),
            ):
                result = launcher.generate_report(
                    source, "Лист1", "Тест", temp, "", False, "auto",
                    ("pdf",), None, "Автоматически", "Руководство", None,
                    "Краткий (C-Level, 3-4 стр)",
                )

            self.assertTrue(result["success"])
            self.assertTrue(Path(result["output_file"]).is_file())


if __name__ == "__main__":
    import unittest
    unittest.main()
