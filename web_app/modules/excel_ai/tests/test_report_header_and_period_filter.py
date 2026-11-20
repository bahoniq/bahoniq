from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from web_app.modules.excel_ai.ai_interpreter import interpret_task
from web_app.modules.excel_ai.analyzer import analyze_workbook
from web_app.modules.excel_ai.operations import execute_operations, plan_operations
from web_app.modules.report_studio.fast_inspector import fast_inspect_excel


def _make_report(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Незаполненные журналы"
    ws.merge_cells("A1:C1")
    ws["A1"] = "Отчет по незаполненным журналам"
    ws.merge_cells("A2:C2")
    ws["A2"] = "Учебный год: 2026-2027"
    ws.append(["№", "Преподаватель", "Академический период"])
    ws.append([1, "(преподаватель не назначен)", "ак.период осень 2026 (01.09.2026 - 31.12.2026)"])
    ws.append([2, "Иванов И.И.", "ак.период осень 2026 (01.09.2026 - 31.12.2026)"])
    ws.append([3, "(преподаватель не назначен)", "ак.период осень 2026 (01.09.2026 - 23.01.2027)"])
    wb.save(path)


def test_preview_and_execution_use_real_header(tmp_path):
    source = tmp_path / "report.xlsx"
    output = tmp_path / "result.xlsx"
    _make_report(source)

    preview = fast_inspect_excel(source)["sheets"][0]
    assert preview["header_row"] == 3
    assert preview["headers"] == ["№", "Преподаватель", "Академический период"]
    assert preview["rows_count"] == 3

    analysis = analyze_workbook(source, 5, 5)
    instruction = (
        'сделай общую сводку, на новом листе отдельно список '
        '"преподаватель не назначен" именно тех, у кого акопериод осень 2026 '
        '(01.09.2026-31.12.2026)'
    )
    interpretation = interpret_task(instruction, analysis)
    operation = interpretation["operations"][0]
    assert operation["header_rows"] == 3
    assert len(operation["conditions"]) == 2

    plan = plan_operations(source, output, interpretation["operations"])
    result = execute_operations(plan, True)
    assert result["changes"][0]["rows_selected"] == 1

    wb = load_workbook(output, data_only=True)
    assert "Преподаватель не назначен" in wb.sheetnames
    assert "Общая сводка" in wb.sheetnames
    detail = wb["Преподаватель не назначен"]
    assert detail.max_row == 4
    assert detail["B4"].value == "(преподаватель не назначен)"
    assert wb["Общая сводка"]["B3"].value == 1


def test_complex_request_uses_reasoning_planner_first(tmp_path):
    source = tmp_path / "report.xlsx"
    _make_report(source)
    analysis = analyze_workbook(source, 5, 5)
    model_reply = {
        "questions": [],
        "operations": [{
            "type": "filter_rows",
            "sheet": "Незаполненные журналы",
            "conditions": [
                {"column": "Преподаватель", "operator": "contains", "value": "не назначен"},
                {"column": "Академический период", "operator": "contains", "value": "осень 2026"},
            ],
            "output_sheet": "Отбор",
            "summary_output_sheet": "Общая сводка",
        }],
        "explanation": "Отбор и сводка.",
        "confidence": 0.96,
    }
    task = (
        "Отбери список тех, у кого преподаватель не назначен, "
        "и сделай общую сводку за осень 2026"
    )
    with patch(
        "web_app.modules.excel_ai.ai_interpreter._post_to_ollama",
        return_value=model_reply,
    ) as model:
        result = interpret_task(task, analysis)
    model.assert_called_once()
    assert result["model_reasoning"] is True
    assert result["operations"][0]["column"] == "Преподаватель"
    assert len(result["operations"][0]["conditions"]) == 2
