import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.excel_ai.ai_interpreter import interpret_task
from modules.excel_ai.analyzer import analyze_workbook
from modules.excel_ai.operations import execute_operations, plan_operations


def _source(tmp_path):
    path = tmp_path / "source.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet0"
    ws.append(["Факультет", "Пол", "Форма оплаты"])
    ws.append(["Школа медицины", "Ж", "Грант"])
    ws.append(["Школа медицины", "М", "Платно"])
    ws.append(["Школа стоматологии", "Ж", "Грант"])
    wb.save(path)
    return path


class ComparativeSummaryFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = _source(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_comparative_request_uses_only_explicit_dimension(self):
        result = interpret_task(
            "Сделай сравнительный анализ по факультетам и нарисуй диаграммы",
            analyze_workbook(self.source),
        )
        self.assertEqual(result["questions"], [])
        self.assertEqual(len(result["operations"]), 1)
        operation = result["operations"][0]
        self.assertEqual(operation["type"], "smart_summary")
        self.assertEqual(operation["columns"], ["Факультет"])
        self.assertFalse(operation["include_other_dimensions"])
        self.assertFalse(operation["include_cross_tables"])

    def test_vague_cross_table_does_not_invent_columns(self):
        result = interpret_task(
            "Сделай сравнительный анализ по факультетам, диаграммы и перекрёстие",
            analyze_workbook(self.source),
        )
        self.assertEqual(result["operations"], [])
        self.assertIn("вторым столбцом", result["questions"][0])

    def test_summary_chart_has_one_series_and_no_legend(self):
        output = self.root / "result.xlsx"
        plan = plan_operations(self.source, output, [{
            "type": "smart_summary",
            "sheet": "Sheet0",
            "columns": ["Факультет"],
            "include_charts": True,
            "include_cross_tables": False,
        }])
        execute_operations(plan, confirmed=True)

        wb = load_workbook(output)
        chart = wb["Сводка Факультет"]._charts[0]
        self.assertEqual(len(chart.series), 1)
        self.assertIsNone(chart.legend)
        self.assertTrue(chart.dLbls.showVal)
        wb.close()

        with zipfile.ZipFile(output) as archive:
            chart_xml = archive.read("xl/charts/chart1.xml").decode("utf-8")
        self.assertEqual(chart_xml.count("<ser>"), 1)


if __name__ == "__main__":
    unittest.main()
