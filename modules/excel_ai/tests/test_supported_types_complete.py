import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from modules.excel_ai.operations import SUPPORTED_TYPES, _do, _validate_ops


class SupportedTypesCompleteTests(unittest.TestCase):
    """Every advertised operation must validate and reach a real executor."""

    def _book(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["ID", "Group", "Value", "Text", "Other"])
        ws.append(["001", "A", 10, " x ", 10])
        ws.append(["002", "A", 20, "a,b", 21])
        ws.append(["002", "B", None, "", 20])
        ws.append([None, None, None, None, None])
        extra = wb.create_sheet("Extra")
        extra.append(["ID", "Group", "Value", "Text", "Other"])
        extra.append(["003", "C", 30, "z", 30])
        return wb

    def _operation(self, kind, temp_dir):
        common = {"type": kind, "sheet": "Data"}
        params = {
            "apply_formula": {"column": "Other", "formula": "=C{row}*2"},
            "compare_columns": {"column": "Value", "other_column": "Other"},
            "copy_columns_to_sheet": {"columns": ["ID", "Group"], "output_sheet": "Selected"},
            "copy_sheet": {"output_sheet": "Data copy"},
            "distinct_count": {"id_column": "ID", "columns": ["Group"]},
            "extract_split_values_to_sheet": {"column": "Text"},
            "fill_empty": {"column": "Value", "value": 0},
            "find_blank_cells": {"all_columns": True, "columns": []},
            "find_repeated_values": {"column": "ID"},
            "filter_rows": {"column": "Value", "operator": "gt", "value": 10, "output_sheet": "Filtered"},
            "group_by_aggregate": {"columns": ["Group"], "column": "Group", "function": "count"},
            "merge_sheets": {"sheets": ["Data", "Extra"]},
            "remove_duplicates": {"columns": ["ID"]},
            "pivot_count": {"row_column": "Group", "column_column": "Text"},
            "reorder_columns": {"columns": ["Other", "Text", "Value", "Group", "ID"]},
            "replace_values": {"column": "Text", "old": "x", "new": "y"},
            "select_columns": {"columns": ["ID", "Group"]},
            "smart_summary": {"columns": ["Group"], "include_charts": False},
            "sort_rows": {"column": "Value"},
            "split_by_column": {"column": "Group", "output_dir": str(Path(temp_dir) / "groups")},
            "split_cell_values_to_rows": {"column": "Text"},
            "split_to_sheets": {"column": "Group"},
            "student_data_audit": {},
            "summary_count": {"column": "Group"},
            "validate_values": {"column": "Value", "rule": "numeric"},
        }
        common.update(params.get(kind, {}))
        return common

    def test_all_supported_types_have_working_handlers(self):
        exercised = set()
        with tempfile.TemporaryDirectory() as temp_dir:
            for kind in sorted(SUPPORTED_TYPES):
                with self.subTest(operation=kind):
                    wb = self._book()
                    operation = self._operation(kind, temp_dir)
                    normalized = _validate_ops([operation], wb)[0]
                    changes, reports, side_effects = [], {}, []
                    _do(wb, normalized, changes, reports, side_effects)
                    self.assertTrue(changes, f"{kind} did not report a result")
                    self.assertEqual(changes[-1]["type"], kind)
                    exercised.add(kind)
                    wb.close()
        self.assertEqual(exercised, SUPPORTED_TYPES)

    def test_find_blank_cells_all_columns_preserves_zero_and_false(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["A", "B", "C"])
        ws.append([0, False, None])
        ws.append([None, None, None])
        ws.append(["x", "   ", 1])
        op = _validate_ops([{
            "type": "find_blank_cells",
            "sheet": "Data",
            "all_columns": True,
        }], wb)[0]
        changes, reports = [], {}
        _do(wb, op, changes, reports)
        cells = reports["blank_cells"][0]["cells"]
        self.assertEqual({item["cell"] for item in cells}, {"C2", "B4"})
        self.assertEqual(changes[0]["matching_rows"], 2)
        wb.close()


if __name__ == "__main__":
    unittest.main()
