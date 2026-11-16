from pathlib import Path

from openpyxl import Workbook, load_workbook

from web_app.modules.excel_ai.ai_interpreter import _safe_local_plan
from web_app.modules.excel_ai.operations import execute_operations, plan_operations


def _source(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Лист1"
    ws.append(["Фамилия", "Имя", "Отчество", "ИИН"])
    ws.append(["Абаев", "Арман", "Серикович", "001234567890"])
    ws.append(["Ибраева", "Алия", None, "001234567891"])
    wb.save(path)


def test_combines_sources_into_new_target_without_resolving_target(tmp_path):
    source = tmp_path / "source.xlsx"
    output = tmp_path / "result.xlsx"
    _source(source)
    operations = [{
        "type": "combine_columns", "sheet": "Лист1",
        "source_columns": ["Фамилия", "Имя", "Отчество"],
        "target_column": "ФИО", "separator": " ",
        "skip_empty": True, "trim_result": True, "position": "first",
    }]
    plan = plan_operations(source, output, operations)
    execute_operations(plan, True)
    wb = load_workbook(output)
    ws = wb["Лист1"]
    assert ws["A1"].value == "ФИО"
    assert ws["A2"].value == "Абаев Арман Серикович"
    assert ws["A3"].value == "Ибраева Алия"
    wb.close()


def test_interpreter_routes_fio_request_to_new_column():
    analysis = {"sheets": [{
        "name": "Лист1",
        "headers": ["Фамилия", "Имя", "Отчество", "ИИН"],
    }]}
    result = _safe_local_plan(
        "Объедини отдельные столбцы «Фамилия», «Имя» и «Отчество» "
        "в единый столбец «ФИО» через пробел.", analysis,
    )
    assert result["operations"][0]["type"] == "combine_columns"
    assert result["operations"][0]["target_column"] == "ФИО"
