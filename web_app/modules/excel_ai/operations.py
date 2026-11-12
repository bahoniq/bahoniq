from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from copy import copy
from collections import Counter
from pathlib import Path
from datetime import datetime

from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
try:
    from .sheet_names import resolve_sheet_name
except ImportError:  # direct module loading used by legacy regression tests
    def resolve_sheet_name(value, names):
        names = list(names)
        if value in names:
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Не указан исходный лист.")
        key = lambda item: re.sub(r"\s+", " ", item.strip()).casefold()
        matches = [name for name in names if key(name) == key(value)]
        if not matches:
            matches = [
                name for name in names if len(name) == 31 and value.startswith(name)
                and re.fullmatch(r"[)\]}\s]+", value[len(name):])
            ]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(f"Лист {value!r} не найден.")


# ============================================================
# BAHONIQ — EXCEL AI OPERATIONS
# ============================================================

SUPPORTED_SOURCE_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
SUPPORTED_OUTPUT_EXTENSIONS = {".xlsx", ".xlsm"}

SUPPORTED_TYPES = {
    "remove_empty_rows",
    "remove_duplicates",
    "fill_empty",
    "trim_text",
    "replace_values",
    "highlight_empty",
    "find_duplicate_rows",
    "find_repeated_values",
    "find_blank_cells",
    "sort_rows",
    "reorder_columns",
    "select_columns",
    "copy_columns_to_sheet",
    "copy_sheet",
    "filter_rows",
    "split_by_column",
    "split_to_sheets",
    "merge_sheets",
    "summary_count",
    "validate_values",
    "compare_columns",
    "student_data_audit",
    "group_by_aggregate",
    "pivot_count",
    "apply_formula",
    "smart_summary",
    "distinct_count",
    "split_cell_values_to_rows",
    "extract_split_values_to_sheet",
}

TYPE_ALIASES = {
    "trim": "trim_text",
    "strip": "trim_text",
    "replace": "replace_values",
    "sort": "sort_rows",
    "split": "split_by_column",
    "split_column": "split_by_column",
    "split_into_files": "split_by_column",
    "split_by_course": "split_to_sheets",
    "split_into_sheets": "split_to_sheets",
    "split_by_column_to_sheets": "split_to_sheets",
    "deduplicate": "remove_duplicates",
    "drop_duplicates": "remove_duplicates",
    "delete_duplicates": "remove_duplicates",
    "delete_empty_rows": "remove_empty_rows",
    "remove_blank_rows": "remove_empty_rows",
    "choose_columns": "select_columns",
    "keep_columns": "select_columns",
    "copy_columns": "copy_columns_to_sheet",
    "copy_selected_columns": "copy_columns_to_sheet",
    "move_columns_to_sheet": "copy_columns_to_sheet",
    "duplicate_sheet": "copy_sheet",
    "copy_worksheet": "copy_sheet",
    "filter": "filter_rows",
    "reorder": "reorder_columns",
    "merge": "merge_sheets",
    "count": "summary_count",
    "validate": "validate_values",
    "compare": "compare_columns",
    "summary": "smart_summary",
    "dashboard": "smart_summary",
    "split_cell_to_rows": "split_cell_values_to_rows",
    "split_cells_to_rows": "split_cell_values_to_rows",
    "explode_cell": "split_cell_values_to_rows",
}


# ============================================================
# HELPERS
# ============================================================

def _sha(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def _fingerprint(obj):
    return hashlib.sha256(
        json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _empty(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _norm(value):
    text = str(value or "").strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text.replace("ё", "е")


def _safe_sheet_name(value, existing_names):
    name = re.sub(r'[\\/*?:\[\]]', "_", str(value)).strip()
    name = (name or "Результат")[:31]
    existing = {str(n).casefold() for n in existing_names}

    if name.casefold() not in existing:
        return name

    base = name
    counter = 2

    while True:
        suffix = f"_{counter}"
        candidate = base[:31 - len(suffix)] + suffix

        if candidate.casefold() not in existing:
            return candidate
        counter += 1


def _header_map(ws, header_row=1):
    return {
        str(ws.cell(header_row, column).value or f"Столбец {column}").strip(): column
        for column in range(1, ws.max_column + 1)
    }


def _auto_dimensions(ws, header_row=1, limit=8):
    blocked = (
        "фио", "фамил", "имя", "отчеств", "телефон", "email", "адрес",
        "паспорт", "иин", "идентификатор", "номер записи", " id", "id ",
    )
    row_count = max(0, ws.max_row - header_row)
    candidates = []
    for header, column in _header_map(ws, header_row).items():
        normalized = f" {header.casefold()} "
        if any(marker in normalized for marker in blocked):
            continue
        values = [
            ws.cell(row, column).value
            for row in range(header_row + 1, ws.max_row + 1)
            if not _empty(ws.cell(row, column).value)
        ]
        unique = len({(type(value).__name__, str(value).strip()) for value in values})
        if unique < 1 or not values:
            continue
        if row_count >= 20 and unique / max(1, len(values)) > .55:
            continue
        if unique > 100:
            continue
        candidates.append((unique, header, column))
    candidates.sort(key=lambda item: (item[0] > 30, item[0], item[1].casefold()))
    return [column for _, _, column in candidates[:limit]]


def _style_summary_sheet(ws):
    navy = "183153"; pale = "EEF4FF"; border = Side(style="thin", color="D9E0E8")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows():
        for cell in row:
            cell.border = Border(left=border, right=border, top=border, bottom=border)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for column_cells in ws.columns:
        width = min(45, max(12, max(len(str(cell.value or "")) for cell in column_cells) + 2))
        ws.column_dimensions[column_cells[0].column_letter].width = width
    for row in range(2, ws.max_row + 1):
        if row % 2 == 0:
            for cell in ws[row]:
                cell.fill = PatternFill("solid", fgColor=pale)


def _add_bar_chart(ws, data_rows, title):
    if data_rows < 1:
        return
    last_row = min(ws.max_row - 1, data_rows + 1)
    if last_row < 2:
        return

    chart = BarChart()
    chart.type = "bar"
    chart.grouping = "clustered"
    chart.overlap = 0
    chart.varyColors = False
    chart.style = 10
    chart.title = title
    chart.y_axis.title = "Категория"
    chart.x_axis.title = "Количество"
    chart.height = max(7, min(12, data_rows * 0.55 + 3))
    chart.width = 16

    # Ровно одна серия: столбец «Количество». Названия факультетов и
    # других групп являются категориями, а не отдельными рядами данных.
    data = Reference(ws, min_col=2, min_row=1, max_row=last_row)
    cats = Reference(ws, min_col=1, min_row=2, max_row=last_row)
    chart.add_data(data, titles_from_data=True, from_rows=False)
    chart.set_categories(cats)
    chart.legend = None
    chart.dLbls = DataLabelList()
    chart.dLbls.showVal = True
    ws.add_chart(chart, "F2")


def _validate_paths(source, output):
    src = Path(source).expanduser().resolve()
    dst = Path(output).expanduser().resolve()

    if not src.is_file():
        raise FileNotFoundError(
            f"Исходный файл не найден: {src}"
        )

    if src.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
        raise ValueError(
            "Поддерживаются .xls, .xlsx и .xlsm."
        )

    if dst.suffix.lower() not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ValueError(
            "Результат должен иметь расширение .xlsx или .xlsm."
        )

    if src == dst:
        raise ValueError(
            "Нельзя перезаписывать исходный файл."
        )

    if dst.exists():
        raise FileExistsError(
            f"Файл результата уже существует: {dst}"
        )

    if src.suffix.lower() == ".xlsm" and dst.suffix.lower() != ".xlsm":
        raise ValueError(
            "Для книги с макросами используйте выходной файл .xlsm."
        )

    return src, dst


def _xls_values_workbook(path):
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "Для работы с .xls установи xlrd: py -m pip install xlrd"
        ) from exc

    source = xlrd.open_workbook(str(path), formatting_info=False)
    target = Workbook()
    target.remove(target.active)

    try:
        for sheet_index in range(source.nsheets):
            old_sheet = source.sheet_by_index(sheet_index)
            title = _safe_sheet_name(old_sheet.name, target.sheetnames)
            new_sheet = target.create_sheet(title)

            for row_index in range(old_sheet.nrows):
                for column_index in range(old_sheet.ncols):
                    cell = old_sheet.cell(row_index, column_index)
                    value = cell.value

                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        value = None
                    elif cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate_as_datetime(value, source.datemode)
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        value = bool(value)
                    elif cell.ctype == xlrd.XL_CELL_ERROR:
                        value = xlrd.error_text_from_code.get(value, "#ERROR!")
                    elif cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                        value = int(value)

                    new_sheet.cell(row_index + 1, column_index + 1, value)

            for row_start, row_end, col_start, col_end in getattr(old_sheet, "merged_cells", []):
                if row_end > row_start and col_end > col_start:
                    new_sheet.merge_cells(
                        start_row=row_start + 1,
                        end_row=row_end,
                        start_column=col_start + 1,
                        end_column=col_end,
                    )
    finally:
        source.release_resources()

    if not target.sheetnames:
        target.create_sheet("Sheet1")

    return target


def _load_source_workbook(path):
    path = Path(path)

    if path.suffix.lower() != ".xls":
        return load_workbook(
            path,
            keep_vba=path.suffix.lower() == ".xlsm",
            data_only=False,
        )

    converted_path = None
    excel = None
    document = None
    try:
        if os.name != "nt":
            raise RuntimeError("Microsoft Excel COM доступен только в Windows.")

        import win32com.client

        fd, temp_name = tempfile.mkstemp(prefix="bahoniq_xls_", suffix=".xlsx")
        os.close(fd)
        converted_path = Path(temp_name)
        converted_path.unlink(missing_ok=True)

        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        document = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True)
        document.SaveAs(str(converted_path), FileFormat=51)
        document.Close(False)
        document = None
        excel.Quit()
        excel = None

        workbook = load_workbook(converted_path, data_only=False)
        return workbook
    except Exception:
        return _xls_values_workbook(path)
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        if converted_path is not None:
            converted_path.unlink(missing_ok=True)


# ============================================================
# AUTOMATIC COLUMN DETECTION
# ============================================================

def _headers(ws, header_rows=1):
    if header_rows < 1:
        return {}

    return {
        c: ws.cell(header_rows, c).value
        for c in range(1, ws.max_column + 1)
        if not _empty(ws.cell(header_rows, c).value)
    }


def _detect_header_row(ws, scan_limit=30):
    """Detect a table header in sheets that start with titles or notes."""
    best_row, best_score = 1, float("-inf")
    last = min(ws.max_row, scan_limit)
    for row in range(1, last + 1):
        values = [ws.cell(row, c).value for c in range(1, ws.max_column + 1)]
        populated = [v for v in values if not _empty(v)]
        if not populated:
            continue
        text = [v for v in populated if isinstance(v, str) and not v.startswith("=")]
        unique = len({str(v).strip().casefold() for v in populated})
        score = len(populated) * 2.0 + len(text) * 1.5 + unique * 0.5
        if len(populated) == 1:
            score -= 8.0
        elif len(populated) == 2:
            score -= 3.0
        compatible = 0
        for next_row in range(row + 1, min(last, row + 4) + 1):
            count = sum(
                not _empty(ws.cell(next_row, c).value)
                for c in range(1, ws.max_column + 1)
            )
            if count >= max(1, min(len(populated), 3)):
                compatible += 1
        score += compatible * 2.0
        if score > best_score:
            best_row, best_score = row, score
    return best_row


def _resolve_column(
    ws,
    value,
    header_rows=1,
    operation_name="операция",
):
    if isinstance(value, int) and not isinstance(value, bool):
        if 1 <= value <= ws.max_column:
            return value

        raise ValueError(
            f"{operation_name}: столбец №{value} отсутствует "
            f"на листе {ws.title!r}."
        )

    if value is None or not str(value).strip():
        raise ValueError(
            f"{operation_name}: ИИ не указал столбец."
        )

    wanted = _norm(value)
    headers = _headers(ws, header_rows)

    exact = [
        col for col, label in headers.items()
        if _norm(label) == wanted
    ]

    if len(exact) == 1:
        return exact[0]

    if len(exact) > 1:
        raise ValueError(
            f"Заголовок {value!r} повторяется на листе "
            f"{ws.title!r}. Нельзя безопасно выбрать столбец."
        )

    partial = [
        col for col, label in headers.items()
        if wanted in _norm(label) or _norm(label) in wanted
    ]

    if len(partial) == 1:
        return partial[0]

    available = ", ".join(
        f"{col}: {label}" for col, label in headers.items()
    ) or "заголовки не найдены"

    if len(partial) > 1:
        raise ValueError(
            f"Название {value!r} подходит к нескольким столбцам. "
            f"Доступные заголовки: {available}"
        )

    raise ValueError(
        f"Столбец {value!r} не найден на листе {ws.title!r}. "
        f"Доступные заголовки: {available}"
    )


def _resolve_columns(
    ws,
    values,
    header_rows=1,
    operation_name="операция",
):
    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list) or not values:
        raise ValueError(
            f"{operation_name}: требуется непустой список столбцов."
        )

    result = [
        _resolve_column(ws, value, header_rows, operation_name)
        for value in values
    ]

    if len(set(result)) != len(result):
        raise ValueError(
            f"{operation_name}: один столбец указан несколько раз."
        )

    return result


# ============================================================
# NORMALIZE OPERATION
# ============================================================

def _canonicalize_operation(raw):
    op = dict(raw)

    kind = (
        op.get("type")
        or op.get("operation")
        or op.get("action")
    )

    if isinstance(kind, str):
        kind = kind.strip().lower().replace("-", "_").replace(" ", "_")

    op["type"] = TYPE_ALIASES.get(kind, kind)

    for nested_key in ("parameters", "params", "arguments", "args"):
        nested = op.get(nested_key)

        if isinstance(nested, dict):
            for key, value in nested.items():
                op.setdefault(key, value)

    if not op.get("sheet"):
        for key in (
            "sheet_name", "worksheet", "лист", "имя_листа"
        ):
            if op.get(key):
                op["sheet"] = op[key]
                break

    if op.get("column") is None:
        for key in (
            "column_name",
            "field",
            "column_to_use",
            "столбец",
            "колонка",
            "поле",
        ):
            if op.get(key) is not None:
                op["column"] = op[key]
                break

    if op.get("columns") is None:
        for key in (
            "column_names", "fields", "столбцы", "колонки"
        ):
            if op.get(key) is not None:
                op["columns"] = op[key]
                break

    if isinstance(op.get("columns"), str):
        op["columns"] = [op["columns"]]

    if op.get("other_column") is None:
        for key in (
            "second_column",
            "compare_column",
            "column2",
            "столбец2",
        ):
            if op.get(key) is not None:
                op["other_column"] = op[key]
                break

    return op


# ============================================================
# VALIDATE OPERATIONS
# ============================================================

def _validate_ops(ops, wb):
    if not isinstance(ops, list) or not ops:
        raise ValueError("Список операций пуст.")

    result = []

    for index, raw in enumerate(ops, start=1):
        if not isinstance(raw, dict):
            raise ValueError(
                f"Операция {index} должна быть объектом."
            )

        op = _canonicalize_operation(raw)
        kind = op.get("type")

        if kind not in SUPPORTED_TYPES:
            raise ValueError(
                f"Операция {index}: тип не поддерживается: {kind!r}"
            )

        sheet = op.get("sheet")

        if kind not in {"merge_sheets", "student_data_audit"}:
            try:
                sheet = resolve_sheet_name(sheet, wb.sheetnames)
                op["sheet"] = sheet
            except ValueError:
                raise ValueError(
                    f"Операция {index}: лист {sheet!r} не найден. "
                    f"Доступные листы: {', '.join(wb.sheetnames)}"
                )

        if "header_rows" not in op:
            target_sheet = sheet
            if kind == "merge_sheets":
                candidates = op.get("sheets") or []
                target_sheet = candidates[0] if candidates else None
            op["header_rows"] = (
                _detect_header_row(wb[target_sheet])
                if target_sheet in wb.sheetnames else 1
            )
        hr = op["header_rows"]

        if not isinstance(hr, int) or isinstance(hr, bool) or hr < 0:
            raise ValueError(
                "header_rows должен быть целым числом >= 0."
            )

        if kind == "merge_sheets":
            sheets = op.get("sheets")

            if (
                not isinstance(sheets, list)
                or not sheets
                or any(s not in wb.sheetnames for s in sheets)
            ):
                raise ValueError(
                    "merge_sheets требует список существующих листов."
                )

        else:
            ws = wb[sheet]

            column_types = {
                "find_repeated_values",
                "sort_rows",
                "split_by_column",
                "split_to_sheets",
                "summary_count",
                "validate_values",
                "compare_columns",
                "group_by_aggregate",
                "apply_formula",
                "split_cell_values_to_rows",
                "extract_split_values_to_sheet",
                "filter_rows",
            }

            if kind == "pivot_count":
                op["row_column"] = _resolve_column(
                    ws, op.get("row_column"), hr,
                    f"Операция {index} (pivot_count, строки)",
                )
                op["column_column"] = _resolve_column(
                    ws, op.get("column_column"), hr,
                    f"Операция {index} (pivot_count, столбцы)",
                )
                if op["row_column"] == op["column_column"]:
                    raise ValueError("Для перекрёстной таблицы нужны два разных столбца.")

            if kind in {"split_to_sheets", "group_by_aggregate"} and op.get("columns"):
                op["columns"] = _resolve_columns(
                    ws,
                    op["columns"],
                    hr,
                    f"Операция {index} ({kind})",
                )
                op["column"] = op["columns"][0]

            elif kind in column_types:
                op["column"] = _resolve_column(
                    ws,
                    op.get("column"),
                    hr,
                    f"Операция {index} ({kind})",
                )

            if kind == "find_blank_cells":
                if op.get("all_columns") is True:
                    op["columns"] = list(range(1, ws.max_column + 1))
                    op["column"] = None
                elif op.get("columns"):
                    op["columns"] = _resolve_columns(
                        ws,
                        op["columns"],
                        hr,
                        f"Операция {index} ({kind})",
                    )
                    op["column"] = (
                        op["columns"][0]
                        if len(op["columns"]) == 1
                        else None
                    )
                else:
                    op["column"] = _resolve_column(
                        ws,
                        op.get("column"),
                        hr,
                        f"Операция {index} ({kind})",
                    )
                    op["columns"] = [op["column"]]

            if kind == "extract_split_values_to_sheet":
                output_sheet = op.get("output_sheet", "Результат")

                if not isinstance(output_sheet, str) or not output_sheet.strip():
                    raise ValueError(
                        f"Операция {index}: output_sheet должен быть непустой строкой."
                    )

                op["output_sheet"] = output_sheet.strip()

            if kind in {"copy_sheet", "filter_rows"}:
                output_sheet = op.get(
                    "output_sheet",
                    "Копия" if kind == "copy_sheet" else "Отбор",
                )
                if not isinstance(output_sheet, str) or not output_sheet.strip():
                    raise ValueError(
                        f"Операция {index}: output_sheet должен быть непустой строкой."
                    )
                op["output_sheet"] = output_sheet.strip()

            if kind == "filter_rows":
                operator = str(op.get("operator", "")).strip().lower()
                if operator not in {
                    "eq", "ne", "gt", "ge", "lt", "le",
                    "contains", "blank", "not_blank",
                }:
                    raise ValueError(
                        f"Операция {index}: неизвестное условие фильтра {operator!r}."
                    )
                if operator not in {"blank", "not_blank"} and "value" not in op:
                    raise ValueError(
                        f"Операция {index}: для фильтра {operator!r} нужно значение."
                    )
                op["operator"] = operator

            if kind == "compare_columns":
                op["other_column"] = _resolve_column(
                    ws,
                    op.get("other_column"),
                    hr,
                    f"Операция {index} (compare_columns)",
                )

            if kind == "group_by_aggregate":
                function = str(op.get("function", "sum")).strip().lower()
                if function not in {"sum", "avg", "count", "min", "max"}:
                    raise ValueError(
                        f"Операция {index}: функция агрегации должна быть "
                        "sum, avg, count, min или max."
                    )
                op["function"] = function
                if function != "count" and op.get("target_column") is None:
                    raise ValueError(
                        f"Операция {index}: для функции {function!r} "
                        "необходимо указать target_column."
                    )
                if op.get("target_column") is not None:
                    op["target_column"] = _resolve_column(
                        ws,
                        op["target_column"],
                        hr,
                        f"Операция {index} (group_by_aggregate, target_column)",
                    )
                if not isinstance(op.get("output_sheet", "Агрегация"), str):
                    raise ValueError(
                        f"Операция {index}: output_sheet должен быть строкой."
                    )

            if kind == "distinct_count":
                op["id_column"] = _resolve_column(ws, op.get("id_column"), hr, "distinct_count ID")
                raw_groups = op.get("columns") or []
                op["columns"] = _resolve_columns(ws, raw_groups, hr, "distinct_count groups") if raw_groups else []
                if op["id_column"] in op["columns"]:
                    raise ValueError("ID не может одновременно быть полем группировки.")

            if kind == "smart_summary":
                if op.get("columns"):
                    op["columns"] = _resolve_columns(
                        ws, op["columns"], hr,
                        f"Операция {index} (smart_summary)",
                    )
                else:
                    op["columns"] = _auto_dimensions(ws, hr, limit=8)
                if op.get("include_other_dimensions"):
                    additional = _auto_dimensions(ws, hr, limit=12)
                    op["columns"] = (op["columns"] + [c for c in additional if c not in op["columns"]])[:8]
                if not op["columns"]:
                    raise ValueError(
                        "Не найдены пригодные категориальные столбцы для сводки. "
                        "Укажите названия столбцов явно."
                    )
                op["include_cross_tables"] = bool(op.get("include_cross_tables", True))
                op["include_charts"] = bool(op.get("include_charts", True))

            if kind == "apply_formula":
                formula = op.get("formula")
                if not isinstance(formula, str) or not formula.strip().startswith("="):
                    raise ValueError(
                        f"Операция {index}: formula должна быть строкой Excel-формулы, "
                        "начинающейся с '='."
                    )
                if "{row}" not in formula:
                    raise ValueError(
                        f"Операция {index}: формула должна содержать плейсхолдер {{row}}."
                    )
                try:
                    formula.format(row=2)
                except (KeyError, IndexError, ValueError) as exc:
                    raise ValueError(
                        f"Операция {index}: некорректный шаблон формулы: {exc}"
                    ) from exc
                op["formula"] = formula.strip()

            if kind in {"select_columns", "reorder_columns", "copy_columns_to_sheet"}:
                op["columns"] = _resolve_columns(
                    ws,
                    op.get("columns"),
                    hr,
                    f"Операция {index} ({kind})",
                )

                if any(c > ws.max_column for c in op["columns"]):
                    raise ValueError(
                        f"Операция {index}: столбец выходит за границы листа."
                    )

                if (
                    kind == "reorder_columns"
                    and sorted(op["columns"]) != list(
                        range(1, ws.max_column + 1)
                    )
                ):
                    raise ValueError(
                        "reorder_columns требует каждый столбец ровно один раз."
                    )

                if kind == "copy_columns_to_sheet":
                    output_sheet = op.get("output_sheet")
                    if not isinstance(output_sheet, str) or not output_sheet.strip():
                        raise ValueError(
                            f"Операция {index}: укажите непустой output_sheet."
                        )
                    if output_sheet.strip().casefold() == sheet.casefold():
                        raise ValueError(
                            f"Операция {index}: исходный и целевой листы должны различаться."
                        )
                    op["output_sheet"] = output_sheet.strip()

            if (
                kind == "remove_duplicates"
                and op.get("columns") is not None
            ):
                op["columns"] = _resolve_columns(
                    ws,
                    op["columns"],
                    hr,
                    f"Операция {index} (remove_duplicates)",
                )

            if kind == "fill_empty":
                if "value" not in op:
                    raise ValueError(
                        "fill_empty требует поле value."
                    )

                raw_columns = op.get("columns") or (
                    [op["column"]] if op.get("column") is not None else []
                )
                if raw_columns:
                    op["columns"] = _resolve_columns(
                        ws, raw_columns, hr, f"Операция {index} (fill_empty)"
                    )
                    op["column"] = op["columns"][0] if len(op["columns"]) == 1 else None

            if kind == "replace_values":
                if not isinstance(op.get("old"), str) or not isinstance(
                    op.get("new"), str
                ):
                    raise ValueError(
                        "replace_values требует строковые поля old и new."
                    )

                raw_columns = op.get("columns") or (
                    [op["column"]] if op.get("column") is not None else []
                )
                if raw_columns:
                    op["columns"] = _resolve_columns(
                        ws, raw_columns, hr, f"Операция {index} (replace_values)"
                    )
                    op["column"] = op["columns"][0] if len(op["columns"]) == 1 else None

            if kind == "trim_text" and op.get("columns"):
                op["columns"] = _resolve_columns(
                    ws, op["columns"], hr, f"Операция {index} (trim_text)"
                )

            if kind == "split_by_column":
                if (
                    not isinstance(op.get("output_dir"), str)
                    or not op["output_dir"].strip()
                ):
                    raise ValueError(
                        "split_by_column требует папку output_dir."
                    )

            if kind == "split_to_sheets" and op.get("sort_column") is not None:
                op["sort_column"] = _resolve_column(
                    ws,
                    op["sort_column"],
                    hr,
                    f"Операция {index} (split_to_sheets, sort_column)",
                )
                op["sort_descending"] = bool(
                    op.get("sort_descending", False)
                )

            if kind == "validate_values":
                rule = op.get("rule", "not_empty")

                if rule not in {
                    "not_empty",
                    "numeric",
                    "positive",
                    "allowed_values",
                }:
                    raise ValueError(
                        f"Неизвестное правило validate_values: {rule!r}"
                    )

                if rule == "allowed_values" and not isinstance(
                    op.get("allowed_values"), list
                ):
                    raise ValueError(
                        "allowed_values должен быть списком."
                    )

        result.append(op)

        # Validate dependent steps against sheets created by earlier steps.
        # This is a planning-only workbook, so lightweight placeholder sheets
        # are safe and prevent false "лист не найден" errors.
        output_name = op.get("output_sheet")
        if output_name and kind in {
            "copy_sheet", "filter_rows", "copy_columns_to_sheet",
            "extract_split_values_to_sheet", "group_by_aggregate",
        }:
            if output_name in wb.sheetnames:
                preview_ws = wb[output_name]
            else:
                preview_ws = wb.create_sheet(output_name)
            if preview_ws.max_row == 1 and preview_ws.max_column == 1 and preview_ws["A1"].value is None:
                if kind == "copy_columns_to_sheet":
                    preview_headers = [ws.cell(hr, col).value for col in op["columns"]]
                elif kind == "extract_split_values_to_sheet":
                    preview_headers = [
                        op.get("output_header") or ws.cell(hr, op["column"]).value
                    ]
                elif kind == "group_by_aggregate":
                    preview_headers = [
                        ws.cell(hr, col).value for col in op.get("columns", [])
                    ] + [
                        "Количество" if op.get("function") == "count" else {
                            "sum": "Сумма", "avg": "Среднее",
                            "min": "Минимум", "max": "Максимум",
                        }.get(op.get("function"), "Значение")
                    ]
                else:
                    preview_headers = [
                        ws.cell(hr, col).value for col in range(1, ws.max_column + 1)
                    ]
                for preview_col, preview_value in enumerate(preview_headers, 1):
                    preview_ws.cell(hr, preview_col).value = preview_value

        if kind == "select_columns":
            selected_headers = [ws.cell(hr, col).value for col in op["columns"]]
            for col, value in enumerate(selected_headers, 1):
                ws.cell(hr, col).value = value
            for col in range(len(selected_headers) + 1, ws.max_column + 1):
                ws.cell(hr, col).value = None

    return result


# ============================================================
# CREATE PLAN
# ============================================================

def plan_operations(source, output, operations):
    src, dst = _validate_paths(source, output)

    wb = _load_source_workbook(src)

    try:
        normalized = _validate_ops(operations, wb)

        previews = []
        for op in normalized:
            preview = {
                "type": op["type"],
                "sheet": op.get("sheet"),
                "output_sheet": op.get("output_sheet"),
            }
            if op["type"] == "extract_split_values_to_sheet" and op.get("sheet") in wb.sheetnames:
                source_ws = wb[op["sheet"]]
                delimiter = op.get("delimiter")
                split_pattern = re.escape(str(delimiter)) if delimiter else r"[,;\n\r]+"
                output_rows = 0
                non_formula_sources = 0
                for row_num in range(op.get("header_rows", 1) + 1, source_ws.max_row + 1):
                    value = source_ws.cell(row_num, op["column"]).value
                    if _empty(value):
                        continue
                    raw = str(value).strip().strip("{}[]")
                    parts = [p for p in re.split(split_pattern, raw) if p.strip()]
                    output_rows += len(parts)
                    if not str(value).strip().startswith("="):
                        non_formula_sources += 1
                if output_rows == 0 or non_formula_sources == 0:
                    raise ValueError(
                        "В выбранном столбце нет обычных значений для извлечения."
                    )
                preview["output_rows"] = output_rows
            previews.append(preview)

        plan = {
            "source": str(src),
            "output": str(dst),
            "source_sha256": _sha(src),
            "operations": normalized,
            "display_operations": normalized,
            "previews": previews,
            "steps": [
                f"{op['type']} — {op.get('sheet', '')}"
                for op in normalized
            ],
            "requires_confirmation": True,
            "source_will_be_modified": False,
            "source_format": src.suffix.lower(),
            "converted_from_xls": src.suffix.lower() == ".xls",
        }

        plan["plan_sha256"] = _fingerprint(plan)
        return plan

    finally:
        wb.close()


# ============================================================
# EXECUTE OPERATIONS
# ============================================================

def _do(wb, op, changes, reports, created_side_effect_files=None):
    if created_side_effect_files is None:
        created_side_effect_files = []

    kind = op["type"]
    sheet = op.get("sheet")
    hr = op.get("header_rows", 1)

    if kind == "merge_sheets":
        name = _safe_sheet_name(
            op.get("output_sheet", "Объединено"),
            wb.sheetnames,
        )
        target = wb.create_sheet(name)

        for index, sheet_name in enumerate(op["sheets"]):
            source_ws = wb[sheet_name]
            start = 1 if index == 0 else hr + 1

            for row in source_ws.iter_rows(
                min_row=start,
                values_only=True,
            ):
                target.append(list(row))

        changes.append({
            "type": kind,
            "sheets": op["sheets"],
            "output_sheet": name,
        })
        return

    ws = wb[sheet]

    if kind == "extract_split_values_to_sheet":
        col = op["column"]

        source_header = (
            ws.cell(hr, col).value
            if hr >= 1 and not _empty(ws.cell(hr, col).value)
            else "Значение"
        )

        output_name = _safe_sheet_name(
            op.get("output_sheet", "Результат"),
            wb.sheetnames,
        )

        extracted_values = []
        source_cells = 0
        multi_value_cells = 0

        # Обрабатываем только выбранный столбец.
        # Исходный лист не изменяем.
        for row_num in range(hr + 1, ws.max_row + 1):
            value = ws.cell(row_num, col).value

            if _empty(value):
                continue

            source_cells += 1
            raw_value = str(value).strip().strip("{}[]")

            delimiter = op.get("delimiter")
            split_pattern = re.escape(str(delimiter)) if delimiter else r"[,;\n\r]+"
            parts = [
                part.strip()
                for part in re.split(split_pattern, raw_value)
                if part.strip()
            ]

            if len(parts) > 1:
                multi_value_cells += 1

            extracted_values.extend(parts)

        if not extracted_values:
            raise ValueError(
                f"В столбце {source_header!r} на листе {sheet!r} "
                "не найдено значений для извлечения."
            )

        expected_values = Counter(extracted_values)

        target = wb.create_sheet(output_name)
        start_row = max(2, int(op.get("start_row", 2)))
        target.cell(start_row - 1, 1).value = source_header
        target.column_dimensions["A"].width = 25
        target.freeze_panes = f"A{start_row}"

        for row_num, value in enumerate(extracted_values, start=start_row):
            cell = target.cell(row_num, 1)
            cell.number_format = "@"
            cell.value = value
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                cell.data_type = "s"

        target.auto_filter.ref = f"A{start_row - 1}:A{start_row + len(extracted_values) - 1}"

        actual_values = [
            target.cell(row_num, 1).value
            for row_num in range(start_row, target.max_row + 1)
        ]

        if actual_values != extracted_values:
            raise RuntimeError(
                "Проверка результата не пройдена: порядок или значения изменены."
            )

        if Counter(actual_values) != expected_values:
            raise RuntimeError(
                "Проверка результата не пройдена: обнаружена потеря или дублирование значений."
            )

        changes.append({
            "type": kind,
            "source_sheet": sheet,
            "source_column": col,
            "source_header": source_header,
            "output_sheet": output_name,
            "source_cells": source_cells,
            "multi_value_cells": multi_value_cells,
            "extracted_values": len(extracted_values),
            "source_modified": False,
            "validation_passed": True,
        })

        reports["extract_split_values_to_sheet"] = {
            "source_sheet": sheet,
            "source_column": col,
            "source_header": source_header,
            "output_sheet": output_name,
            "extracted_values": len(extracted_values),
            "validation_passed": True,
        }

    elif kind == "split_cell_values_to_rows":
        col = op["column"]
        max_col = ws.max_column
        new_rows = []
        expanded_cells = 0

        for row_num in range(1, hr + 1):
            new_rows.append([
                ws.cell(row_num, c).value
                for c in range(1, max_col + 1)
            ])

        for row_num in range(hr + 1, ws.max_row + 1):
            row_values = [
                ws.cell(row_num, c).value
                for c in range(1, max_col + 1)
            ]

            target_cell_value = row_values[col - 1]

            if _empty(target_cell_value):
                new_rows.append(row_values)
                continue

            raw_str = str(target_cell_value).strip().strip("{}[]")
            parts = [
                p.strip()
                for p in re.split(r"[,;\n\r]+", raw_str)
                if p.strip()
            ]

            if len(parts) <= 1:
                new_rows.append(row_values)
            else:
                expanded_cells += 1

                for part in parts:
                    if part.isdigit() and not (
                        len(part) > 1 and part.startswith("0")
                    ):
                        part_val = int(part)
                    else:
                        part_val = part

                    cloned_row = list(row_values)
                    cloned_row[col - 1] = part_val
                    new_rows.append(cloned_row)

        ws.delete_rows(1, ws.max_row)

        for row_idx, row_vals in enumerate(new_rows, 1):
            for col_idx, val in enumerate(row_vals, 1):
                ws.cell(row_idx, col_idx, val)

        changes.append({
            "type": kind,
            "sheet": sheet,
            "column": col,
            "expanded_cells": expanded_cells,
            "total_rows_after": len(new_rows),
        })

    elif kind == "student_data_audit":
        if hr < 1:
            raise ValueError("student_data_audit требует строку заголовков (header_rows >= 1).")
        if ws.max_column < 1:
            raise ValueError("На исходном листе нет столбцов для аудита.")

        max_col = ws.max_column
        raw_headers = {col: ws.cell(hr, col).value for col in range(1, max_col + 1)}
        headers = {
            col: (str(label).strip() if not _empty(label) and str(label).strip()
                  else f"Столбец {col} (заголовок пуст)")
            for col, label in raw_headers.items()
        }
        desired_names = ["Сводка", "Повторяющиеся ID", "Пустые данные", "Полные дубли",
                         "Проверка факультетов", "Нормализация"]
        existing_folded = {n.casefold() for n in wb.sheetnames}
        collisions = [n for n in desired_names if n.casefold() in existing_folded]
        if collisions:
            raise ValueError("Для аудита нужны свободные имена листов: " + ", ".join(collisions))

        def norm_text(value):
            if value is None:
                return ""
            return re.sub(r"\s+", " ", str(value).strip().casefold()).replace("ё", "е")

        def is_blank(value):
            return _empty(value) or (isinstance(value, str) and not value.strip())

        def typed_key(values):
            return json.dumps([[type(v).__name__, v.isoformat() if hasattr(v, "isoformat") else v]
                               for v in values], ensure_ascii=False, default=str,
                              separators=(",", ":"))

        rows, source_row_numbers = [], []
        for row_num in range(hr + 1, ws.max_row + 1):
            values = [ws.cell(row_num, col).value for col in range(1, max_col + 1)]
            if all(is_blank(v) for v in values):
                continue
            rows.append(values)
            source_row_numbers.append(row_num)

        id_candidates = {norm_text(x) for x in (
            "id обучающегося", "ид обучающегося", "student id", "student_id",
            "id студента", "идентификатор обучающегося", "код обучающегося", "id"
        )}
        faculty_candidates = {norm_text(x) for x in (
            "факультет", "наименование факультета", "faculty", "faculty name"
        )}
        id_columns = [c for c, label in raw_headers.items() if norm_text(label) in id_candidates]
        faculty_columns = [c for c, label in raw_headers.items() if norm_text(label) in faculty_candidates]
        if len(id_columns) > 1:
            raise ValueError("Найдено несколько возможных столбцов ID обучающегося; аудит остановлен для безопасности.")
        if len(faculty_columns) > 1:
            raise ValueError("Найдено несколько столбцов факультета; укажите однозначный заголовок.")

        blank_records = []
        for row_num, values in zip(source_row_numbers, rows):
            for col, value in enumerate(values, start=1):
                if is_blank(value):
                    blank_records.append((row_num, headers[col], None if value is None else value))

        duplicate_groups_by_key = {}
        for row_num, values in zip(source_row_numbers, rows):
            duplicate_groups_by_key.setdefault(typed_key(values), {"rows": [], "values": values})["rows"].append(row_num)
        duplicate_groups = [g for g in duplicate_groups_by_key.values() if len(g["rows"]) > 1]

        repeated_ids = {}
        if len(id_columns) == 1:
            id_col = id_columns[0]
            for row_num in source_row_numbers:
                value = ws.cell(row_num, id_col).value
                if not is_blank(value):
                    key = str(value).strip()
                    repeated_ids.setdefault(key, []).append(row_num)
            repeated_ids = {v: rr for v, rr in repeated_ids.items() if len(rr) > 1}

        faculty_variants, faculty_values_count = {}, {}
        if len(faculty_columns) == 1:
            faculty_col = faculty_columns[0]
            for row_num in source_row_numbers:
                value = ws.cell(row_num, faculty_col).value
                if is_blank(value):
                    continue
                raw = str(value).strip()
                key = norm_text(raw)
                faculty_variants.setdefault(key, {}).setdefault(raw, []).append(row_num)
                faculty_values_count[raw] = faculty_values_count.get(raw, 0) + 1
        norm_groups = [(key, variants) for key, variants in faculty_variants.items() if len(variants) > 1]

        summary = wb.create_sheet("Сводка")
        summary.append(["Показатель", "Результат"])
        summary_rows = [
            ("Исходный лист", sheet), ("Строк данных (непустых)", len(rows)),
            ("Столбцов", max_col), ("Пустых ячеек в непустых строках", len(blank_records)),
            ("Групп полных дублей", len(duplicate_groups)),
            ("Повторяющихся ID", len(repeated_ids)),
            ("Столбец ID обучающегося", headers[id_columns[0]] if id_columns else "Не найден однозначно"),
            ("Столбец факультета", headers[faculty_columns[0]] if faculty_columns else "Не найден однозначно"),
            ("Групп вариантов написания факультета", len(norm_groups)),
            ("Пустые заголовки", sum(1 for v in raw_headers.values() if is_blank(v))),
            ("Примечание", "ИИН автоматически не считается ID обучающегося."),
        ]
        for item in summary_rows:
            summary.append(list(item))

        ids_ws = wb.create_sheet("Повторяющиеся ID")
        ids_ws.append(["ID обучающегося", "Количество", "Номера строк"])
        for value, rr in sorted(repeated_ids.items(), key=lambda item: item[0].casefold()):
            ids_ws.append([value, len(rr), ", ".join(map(str, rr))])
        if not id_columns:
            ids_ws.append(["Столбец ID не найден по заголовку; повторения не проверялись", None, None])

        blanks_ws = wb.create_sheet("Пустые данные")
        blanks_ws.append(["Номер строки", "Поле", "Значение"])
        for record in blank_records:
            blanks_ws.append(list(record))

        dup_ws = wb.create_sheet("Полные дубли")
        dup_ws.append(["Номера строк", *[headers[c] for c in headers]])
        for group in duplicate_groups:
            dup_ws.append([", ".join(map(str, group["rows"])), *group["values"]])
        if not duplicate_groups:
            dup_ws.append(["Полных дублей не обнаружено", *([None] * max_col)])

        faculty_ws = wb.create_sheet("Проверка факультетов")
        faculty_ws.append(["Факультет", "Количество", "Номера строк"])
        if len(faculty_columns) == 1:
            for value, count in sorted(faculty_values_count.items(), key=lambda item: item[0].casefold()):
                rr = [r for r in source_row_numbers if str(ws.cell(r, faculty_columns[0]).value).strip() == value]
                faculty_ws.append([value, count, ", ".join(map(str, rr))])
        else:
            faculty_ws.append(["Столбец факультета не определён однозначно", None, None])

        norm_ws = wb.create_sheet("Нормализация")
        norm_ws.append(["Нормализованная форма", "Вариант написания", "Количество", "Номера строк"])
        for key, variants in norm_groups:
            for value, rr in sorted(variants.items(), key=lambda item: item[0].casefold()):
                norm_ws.append([key, value, len(rr), ", ".join(map(str, rr))])
        if not norm_groups:
            norm_ws.append(["Вариантов, отличающихся только регистром/пробелами/ё-е, не обнаружено", None, None, None])

        changes.append({"type": kind, "sheet": sheet, "rows_checked": len(rows),
                        "blank_cells": len(blank_records), "duplicate_groups": len(duplicate_groups),
                        "repeated_ids": len(repeated_ids), "faculty_variant_groups": len(norm_groups),
                        "id_column": id_columns[0] if id_columns else None,
                        "faculty_column": faculty_columns[0] if faculty_columns else None,
                        "output_sheets": desired_names})
        reports["student_data_audit"] = {
            "source_sheet": sheet,
            "rows_checked": len(rows),
            "blank_cells_count": len(blank_records),
            "duplicate_groups_count": len(duplicate_groups),
            "repeated_ids_count": len(repeated_ids),
            "faculty_variant_groups_count": len(norm_groups),
            "id_column": id_columns[0] if id_columns else None,
            "faculty_column": faculty_columns[0] if faculty_columns else None,
            "output_sheets": desired_names
        }
        return

    elif kind == "remove_empty_rows":
        output_sheet = op.get("output_sheet")
        if output_sheet:
            output_name = _safe_sheet_name(output_sheet, wb.sheetnames)
            ws = wb.copy_worksheet(ws)
            ws.title = output_name

        removed = 0

        for row_num in range(ws.max_row, hr, -1):
            if all(
                _empty(ws.cell(row_num, col).value)
                for col in range(1, ws.max_column + 1)
            ):
                ws.delete_rows(row_num)
                removed += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": ws.title,
            "removed_rows": removed,
        })

    elif kind == "pivot_count":
        row_col = op["row_column"]
        column_col = op["column_column"]
        include_empty = bool(op.get("include_empty", False))
        row_header = ws.cell(hr, row_col).value or f"Столбец {row_col}"
        column_header = ws.cell(hr, column_col).value or f"Столбец {column_col}"

        counts = {}
        row_values = []
        column_values = []
        for row_num in range(hr + 1, ws.max_row + 1):
            row_value = ws.cell(row_num, row_col).value
            column_value = ws.cell(row_num, column_col).value
            if not include_empty and (_empty(row_value) or _empty(column_value)):
                continue
            row_value = "(пусто)" if _empty(row_value) else row_value
            column_value = "(пусто)" if _empty(column_value) else column_value
            row_key = (type(row_value).__name__, str(row_value))
            column_key = (type(column_value).__name__, str(column_value))
            if row_key not in [item[0] for item in row_values]:
                row_values.append((row_key, row_value))
            if column_key not in [item[0] for item in column_values]:
                column_values.append((column_key, column_value))
            counts[(row_key, column_key)] = counts.get((row_key, column_key), 0) + 1

        output_name = _safe_sheet_name(
            op.get("output_sheet", "Перекрёстная таблица"), wb.sheetnames
        )
        target = wb.create_sheet(output_name)
        target.append([f"{row_header} / {column_header}",
                       *[value for _, value in column_values], "Всего"])
        column_totals = [0] * len(column_values)
        grand_total = 0
        for row_key, row_value in row_values:
            values = []
            for index, (column_key, _) in enumerate(column_values):
                value = counts.get((row_key, column_key), 0)
                values.append(value)
                column_totals[index] += value
            row_total = sum(values)
            grand_total += row_total
            target.append([row_value, *values, row_total])
        target.append(["Всего", *column_totals, grand_total])
        _auto_dimensions(target)
        target.freeze_panes = "B2"
        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": output_name,
            "row_column": row_header,
            "column_column": column_header,
            "data_rows": grand_total,
        })

    elif kind == "remove_duplicates":
        cols = op.get("columns") or list(
            range(1, ws.max_column + 1)
        )
        seen = set()
        rows_to_remove = []

        for row_num in range(hr + 1, ws.max_row + 1):
            values = tuple(
                ws.cell(row_num, col).value
                for col in cols
            )

            if all(_empty(value) for value in values):
                continue

            key = json.dumps(
                values,
                ensure_ascii=False,
                default=str,
            )

            if key in seen:
                rows_to_remove.append(row_num)
            else:
                seen.add(key)

        for row_num in reversed(rows_to_remove):
            ws.delete_rows(row_num)

        changes.append({
            "type": kind,
            "sheet": sheet,
            "removed_rows": len(rows_to_remove),
            "columns": cols,
        })

    elif kind == "fill_empty":
        columns = op.get("columns") or (
            [op["column"]] if op.get("column") else range(1, ws.max_column + 1)
        )
        count = 0

        for row_num in range(hr + 1, ws.max_row + 1):
            for column in columns:
                if (
                    1 <= column <= ws.max_column
                    and _empty(ws.cell(row_num, column).value)
                ):
                    ws.cell(row_num, column).value = op["value"]
                    count += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "filled_cells": count,
        })

    elif kind == "trim_text":
        count = 0
        columns = op.get("columns") or range(1, ws.max_column + 1)
        for row_num in range(hr + 1, ws.max_row + 1):
            for column in columns:
                cell = ws.cell(row_num, column)
                if (
                    isinstance(cell.value, str)
                    and cell.value != cell.value.strip()
                ):
                    cell.value = cell.value.strip()
                    count += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "changed_cells": count,
        })

    elif kind == "replace_values":
        count = 0
        columns = op.get("columns") or (
            [op["column"]] if op.get("column") else range(1, ws.max_column + 1)
        )

        for row_num in range(hr + 1, ws.max_row + 1):
            for column in columns:
                cell = ws.cell(row_num, column)

                if (
                    isinstance(cell.value, str)
                    and op["old"] in cell.value
                ):
                    cell.value = cell.value.replace(
                        op["old"],
                        op["new"],
                    )
                    count += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "changed_cells": count,
        })

    elif kind == "highlight_empty":
        fill = PatternFill(
            fill_type="solid",
            fgColor=op.get("color", "FFFF00"),
        )
        count = 0

        for row in ws.iter_rows(min_row=hr + 1):
            for cell in row:
                if _empty(cell.value):
                    cell.fill = fill
                    count += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "highlighted_cells": count,
        })

    elif kind == "find_duplicate_rows":
        row_groups = {}

        for row_num in range(hr + 1, ws.max_row + 1):
            values = tuple(
                ws.cell(row_num, col).value
                for col in range(1, ws.max_column + 1)
            )

            if all(_empty(value) for value in values):
                continue

            key = json.dumps(
                [
                    [type(value).__name__, value]
                    for value in values
                ],
                ensure_ascii=False,
                default=str,
            )

            row_groups.setdefault(key, {
                "rows": [],
                "values": list(values),
            })["rows"].append(row_num)

        duplicate_groups = [
            {
                "rows": group["rows"],
                "values": group["values"],
            }
            for group in row_groups.values()
            if len(group["rows"]) > 1
        ]

        repeated_rows = sum(
            len(group["rows"]) - 1
            for group in duplicate_groups
        )

        reports.setdefault("duplicate_rows", []).append({
            "sheet": sheet,
            "header_rows": hr,
            "duplicate_groups": duplicate_groups,
            "duplicate_groups_count": len(duplicate_groups),
            "repeated_rows_count": repeated_rows,
            "rows_in_duplicate_groups": sum(
                len(group["rows"])
                for group in duplicate_groups
            ),
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "duplicate_groups": len(duplicate_groups),
            "repeated_rows": repeated_rows,
            "modified": False,
        })

    elif kind == "find_repeated_values":
        col = op["column"]
        values = {}

        for row_num in range(hr + 1, ws.max_row + 1):
            value = ws.cell(row_num, col).value

            if not _empty(value):
                values.setdefault(
                    str(value).strip(), []
                ).append(row_num)

        repeated = {
            value: rows
            for value, rows in values.items()
            if len(rows) > 1
        }

        reports.setdefault("repeated_values", []).append({
            "sheet": sheet,
            "column": col,
            "values": repeated,
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "repeated_values": len(repeated),
        })

    elif kind == "find_blank_cells":
        columns = op.get("columns") or [op["column"]]
        blanks = []
        matching_rows = set()
        for row_num in range(hr + 1, ws.max_row + 1):
            row_values = [ws.cell(row_num, c).value for c in range(1, ws.max_column + 1)]
            if all(_empty(value) for value in row_values):
                continue
            for col in columns:
                if _empty(row_values[col - 1]):
                    blanks.append({
                        "row": row_num,
                        "column": col,
                        "header": ws.cell(hr, col).value if hr >= 1 else None,
                        "cell": ws.cell(row_num, col).coordinate,
                    })
                    matching_rows.add(row_num)

        matching_rows = sorted(matching_rows)

        output_sheet = _safe_sheet_name(
            op.get("output_sheet", "Найденные записи"),
            wb.sheetnames,
        )
        target = wb.create_sheet(output_sheet)

        column_names = [
            str(ws.cell(hr, col).value or f"Столбец {col}")
            for col in columns
        ]
        target.append(["ОТЧЕТ ПО ПУСТЫМ ЗНАЧЕНИЯМ"])
        target.append([f"Исходный лист:", sheet])
        target.append(["Проверяемые столбцы:", ", ".join(column_names)])
        target.append([f"Всего пропущенных записей:", len(blanks)])
        target.append([])

        header_row = [ws.cell(hr, c).value for c in range(1, ws.max_column + 1)]
        target.append(["№ строки Excel"] + header_row)

        for row_num in matching_rows:
            row_values = [ws.cell(row_num, c).value for c in range(1, ws.max_column + 1)]
            target.append([row_num] + row_values)

        reports.setdefault("blank_cells", []).append({
            "sheet": sheet,
            "column": columns[0] if len(columns) == 1 else None,
            "columns": columns,
            "cells": blanks,
            "blank_cells_count": len(blanks),
            "matching_rows": matching_rows,
            "matching_rows_count": len(matching_rows),
            "output_sheet": output_sheet,
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "column": columns[0] if len(columns) == 1 else None,
            "columns": columns,
            "blank_cells": len(blanks),
            "matching_rows": len(matching_rows),
            "output_sheet": output_sheet,
        })

    elif kind == "sort_rows":
        col = op["column"]

        rows = [
            list(row)
            for row in ws.iter_rows(
                min_row=hr + 1,
                values_only=True,
            )
        ]

        def sort_key(row):
            value = row[col - 1]

            if value is None:
                return (1, 0, "")

            if isinstance(value, (int, float)) and not isinstance(
                value, bool
            ):
                return (0, 0, value)

            return (0, 1, str(value).casefold())

        rows.sort(
            key=sort_key,
            reverse=bool(op.get("descending", False)),
        )

        for row_num, row in enumerate(rows, hr + 1):
            for column, value in enumerate(row, 1):
                ws.cell(row_num, column).value = value

        changes.append({
            "type": kind,
            "sheet": sheet,
            "rows_sorted": len(rows),
            "column": col,
        })

    elif kind == "copy_sheet":
        target = wb.copy_worksheet(ws)
        target.title = _safe_sheet_name(op.get("output_sheet", f"Копия {sheet}"), wb.sheetnames)
        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": target.title,
            "rows_copied": ws.max_row,
        })

    elif kind == "filter_rows":
        column = op["column"]
        operator = op["operator"]
        expected = op.get("value")
        target = wb.create_sheet(
            _safe_sheet_name(op.get("output_sheet", "Отбор"), wb.sheetnames)
        )

        def matches_filter(actual):
            if operator == "blank":
                return _empty(actual)
            if operator == "not_blank":
                return not _empty(actual)
            if operator == "contains":
                return str(expected).casefold() in str(actual or "").casefold()
            if operator == "eq":
                return actual == expected
            if operator == "ne":
                return actual != expected
            try:
                return {
                    "gt": actual > expected,
                    "ge": actual >= expected,
                    "lt": actual < expected,
                    "le": actual <= expected,
                }[operator]
            except (TypeError, KeyError):
                return False

        selected_rows = list(range(1, hr + 1))
        selected_rows.extend(
            row_num for row_num in range(hr + 1, ws.max_row + 1)
            if matches_filter(ws.cell(row_num, column).value)
        )
        for target_row, source_row in enumerate(selected_rows, start=1):
            for col_num in range(1, ws.max_column + 1):
                source_cell = ws.cell(source_row, col_num)
                target_cell = target.cell(target_row, col_num)
                target_cell.value = source_cell.value
                if source_cell.has_style:
                    target_cell._style = copy(source_cell._style)
                target_cell.number_format = source_cell.number_format
                target_cell.alignment = copy(source_cell.alignment)
                target_cell.protection = copy(source_cell.protection)
        for col_num in range(1, ws.max_column + 1):
            source_letter = ws.cell(1, col_num).column_letter
            target_letter = target.cell(1, col_num).column_letter
            target.column_dimensions[target_letter].width = ws.column_dimensions[source_letter].width
        target.freeze_panes = ws.freeze_panes
        if target.max_row and target.max_column:
            target.auto_filter.ref = target.dimensions
        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": target.title,
            "rows_selected": max(0, len(selected_rows) - hr),
        })

    elif kind == "copy_columns_to_sheet":
        cols = op["columns"]
        requested_name = op["output_sheet"]
        if requested_name in wb.sheetnames:
            existing = wb[requested_name]
            is_blank = (
                existing.max_row == 1
                and existing.max_column == 1
                and existing["A1"].value is None
            )
            target = existing if is_blank else wb.create_sheet(
                _safe_sheet_name(requested_name, wb.sheetnames)
            )
        else:
            target = wb.create_sheet(_safe_sheet_name(requested_name, wb.sheetnames))

        for target_col, source_col in enumerate(cols, start=1):
            source_letter = ws.cell(1, source_col).column_letter
            target_letter = target.cell(1, target_col).column_letter
            target.column_dimensions[target_letter].width = ws.column_dimensions[source_letter].width
            for row_num in range(1, ws.max_row + 1):
                source_cell = ws.cell(row_num, source_col)
                target_cell = target.cell(row_num, target_col)
                target_cell.value = source_cell.value
                if source_cell.has_style:
                    target_cell._style = copy(source_cell._style)
                target_cell.number_format = source_cell.number_format
                target_cell.alignment = copy(source_cell.alignment)
                target_cell.protection = copy(source_cell.protection)
        target.freeze_panes = ws.freeze_panes
        if target.max_row >= hr and target.max_column:
            target.auto_filter.ref = target.dimensions
        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": target.title,
            "columns": cols,
            "rows_copied": ws.max_row,
            "source_unchanged": True,
        })

    elif kind in {"select_columns", "reorder_columns"}:
        cols = op["columns"]
        old_max = ws.max_column

        data = [
            [ws.cell(row_num, col).value for col in cols]
            for row_num in range(1, ws.max_row + 1)
        ]

        for row_num, row in enumerate(data, 1):
            for column, value in enumerate(row, 1):
                ws.cell(row_num, column).value = value

            for column in range(len(cols) + 1, old_max + 1):
                ws.cell(row_num, column).value = None

        changes.append({
            "type": kind,
            "sheet": sheet,
            "columns": cols,
        })

    elif kind in {"split_by_column", "split_to_sheets"}:
        grouping_columns = op.get("columns") or [op["column"]]
        groups = {}

        source_data_rows = 0
        for values in ws.iter_rows(
            min_row=hr + 1,
            max_row=ws.max_row,
            min_col=1,
            max_col=ws.max_column,
            values_only=True,
        ):
            if all(_empty(value) for value in values):
                continue

            labels = tuple(
                str(values[col - 1]).strip()
                if not _empty(values[col - 1])
                else "Не указано"
                for col in grouping_columns
            )
            groups.setdefault(labels, []).append(values)
            source_data_rows += 1

        if not groups:
            raise ValueError(
                f"На листе {sheet!r} нет строк для разделения."
            )

        if kind == "split_to_sheets":
            created = []
            sort_column = op.get("sort_column")
            sort_descending = bool(op.get("sort_descending", False))

            def group_sort_key(row):
                value = row[sort_column - 1]
                if _empty(value):
                    return (1, 0, "")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return (0, 0, value)
                return (0, 1, str(value).strip().casefold())

            header_rows = [
                tuple(cell.value for cell in row)
                for row in ws.iter_rows(
                    min_row=1,
                    max_row=hr,
                    min_col=1,
                    max_col=ws.max_column,
                )
            ]

            for group_values, rows in groups.items():
                group_name = " — ".join(str(value) for value in group_values)
                if sort_column is not None:
                    rows.sort(
                        key=group_sort_key,
                        reverse=sort_descending,
                    )
                name = _safe_sheet_name(
                    group_name,
                    wb.sheetnames,
                )
                target = wb.create_sheet(name)

                for header in header_rows:
                    target.append(header)

                for row in rows:
                    target.append(row)

                created.append({
                    "sheet": name,
                    "group": group_name,
                    "group_values": list(group_values),
                    "rows": len(rows),
                })

            changes.append({
                "type": kind,
                "source_sheet": sheet,
                "column": grouping_columns[0] if len(grouping_columns) == 1 else None,
                "columns": grouping_columns,
                "source_data_rows": source_data_rows,
                "distributed_rows": sum(
                    item["rows"] for item in created
                ),
                "sort_column": sort_column,
                "sort_descending": sort_descending,
                "created_sheets": created,
            })

        else:
            outdir = Path(
                op["output_dir"]
            ).expanduser().resolve()

            if outdir.exists():
                if not outdir.is_dir():
                    raise NotADirectoryError(
                        f"Путь результатов не является папкой: {outdir}"
                    )

                if any(outdir.iterdir()):
                    raise FileExistsError(
                        f"Папка не пуста: {outdir}"
                    )

            output_dir_created = False
            created_files = []
            stage_dir = None

            try:
                if not outdir.exists():
                    outdir.mkdir(parents=True, exist_ok=False)
                    output_dir_created = True

                stage_dir = Path(
                    tempfile.mkdtemp(
                        prefix=".bahoniq_excelai_",
                        dir=str(outdir.parent),
                    )
                )

                staged_files = []

                for group_values, rows in groups.items():
                    group_name = " — ".join(str(value) for value in group_values)
                    safe = re.sub(
                        r'[\\/*?:"<>|]',
                        "_",
                        group_name,
                    ).strip()[:60] or "Пусто"

                    filename = f"{safe}.xlsx"
                    staged_path = stage_dir / filename
                    final_path = outdir / filename

                    if any(
                        item["filename"].casefold()
                        == filename.casefold()
                        for item in staged_files
                    ):
                        raise FileExistsError(
                            "Несколько групп получили одинаковое "
                            f"имя файла: {filename}"
                        )

                    if final_path.exists():
                        raise FileExistsError(
                            f"Файл уже существует: {final_path}"
                        )

                    book = Workbook()

                    try:
                        target = book.active
                        target.title = sheet[:31] or "Лист1"

                        for row_num in range(1, hr + 1):
                            target.append([
                                ws.cell(row_num, c).value
                                for c in range(1, ws.max_column + 1)
                            ])

                        for row in rows:
                            target.append(row)

                        book.save(staged_path)

                    finally:
                        book.close()

                    check_book = load_workbook(
                        staged_path,
                        read_only=True,
                        data_only=False,
                    )

                    try:
                        if not check_book.sheetnames:
                            raise RuntimeError(
                                "Созданный файл не содержит листов: "
                                f"{filename}"
                            )
                    finally:
                        check_book.close()

                    staged_files.append({
                        "filename": filename,
                        "staged_path": staged_path,
                        "final_path": final_path,
                        "group": group_name,
                        "rows": len(rows),
                    })

                for item in staged_files:
                    if item["final_path"].exists():
                        raise FileExistsError(
                            "Файл появился во время подготовки: "
                            f"{item['final_path']}"
                        )

                for item in staged_files:
                    os.link(
                        item["staged_path"],
                        item["final_path"],
                    )

                    created_files.append(item["final_path"])

                    created_side_effect_files.append(
                        item["final_path"]
                    )

                files = [
                    str(item["final_path"])
                    for item in staged_files
                ]

            except Exception:
                for created_path in reversed(created_files):
                    try:
                        created_path.unlink(missing_ok=True)
                    except OSError:
                        pass

                    try:
                        created_side_effect_files.remove(
                            created_path
                        )
                    except ValueError:
                        pass

                if output_dir_created:
                    try:
                        outdir.rmdir()
                    except OSError:
                        pass

                raise

            finally:
                if stage_dir is not None:
                    shutil.rmtree(stage_dir, ignore_errors=True)

            changes.append({
                "type": kind,
                "sheet": sheet,
                "groups": len(groups),
                "files": files,
            })

    elif kind == "smart_summary":
        dimensions = op["columns"]
        headers = {
            column: str(ws.cell(hr, column).value or f"Столбец {column}")
            for column in dimensions
        }
        rows = [
            tuple(values)
            for values in ws.iter_rows(
                min_row=hr + 1, max_row=ws.max_row,
                min_col=1, max_col=ws.max_column, values_only=True,
            )
            if not all(_empty(value) for value in values)
        ]
        total = len(rows)
        if not total:
            raise ValueError(f"На листе {sheet!r} нет строк данных для сводки.")

        created_sheets = []
        overview_name = _safe_sheet_name(
            op.get("output_sheet", "Общая сводка"), wb.sheetnames
        )
        overview = wb.create_sheet(overview_name, 0)
        overview.append(["Показатель", "Значение"])
        overview.append(["Исходный лист", sheet])
        overview.append(["Строк данных", total])
        id_columns = [col for col in range(1, ws.max_column + 1)
                      if _norm(ws.cell(hr, col).value) in {
                          "id обучающегося", "ид обучающегося", "id студента",
                          "student id", "student_id", "employee id", "id сотрудника",
                          "customer id", "id клиента", "id записи"}]
        unique_id_count = None
        if len(id_columns) == 1:
            id_col = id_columns[0]
            identifiers = {str(row[id_col - 1]).strip() for row in rows
                           if not _empty(row[id_col - 1])}
            unique_id_count = len(identifiers)
            overview.append(["Уникальных ID (непустых)", unique_id_count])
            overview.append(["Строк с пустым ID", sum(_empty(row[id_col - 1]) for row in rows)])
        overview.append(["Проанализировано разрезов", len(dimensions)])
        overview.append(["Разрезы", ", ".join(headers[c] for c in dimensions)])

        summary_blocks = []
        for column in dimensions:
            counts = Counter(
                str(row[column - 1]).strip() if not _empty(row[column - 1]) else "Не указано"
                for row in rows
            )
            ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
            leader, leader_count = ordered[0]
            overview.append([f"Лидер: {headers[column]}", f"{leader} — {leader_count} ({leader_count * 100 / total:.1f}%)"])
            summary_blocks.append((column, ordered))
        _style_summary_sheet(overview)
        created_sheets.append(overview_name)

        for column, ordered in summary_blocks:
            summary_name = _safe_sheet_name(f"Сводка {headers[column]}", wb.sheetnames)
            summary_ws = wb.create_sheet(summary_name)
            summary_ws.append([headers[column], "Количество", "Доля, %", "Ранг"])
            for rank, (label, count) in enumerate(ordered, 1):
                summary_ws.append([label, count, round(count * 100 / total, 2), rank])
            summary_ws.append(["ИТОГО", total, 100.0, ""])
            _style_summary_sheet(summary_ws)
            summary_ws.column_dimensions["F"].width = 2
            if op.get("include_charts"):
                _add_bar_chart(summary_ws, min(12, len(ordered)), headers[column])
            created_sheets.append(summary_name)

        cross_sheets = []
        if op.get("include_cross_tables") and len(dimensions) >= 2:
            cross_dimensions = dimensions[:8]
            cross_pairs = [(cross_dimensions[0], right) for right in cross_dimensions[1:]]
            cross_pairs.extend((cross_dimensions[i], cross_dimensions[j])
                               for i in range(1, min(4, len(cross_dimensions)))
                               for j in range(i + 1, min(4, len(cross_dimensions))))
            for left, right in cross_pairs:
                pair_counts = Counter()
                left_values = Counter(); right_values = Counter()
                for row in rows:
                    lv = str(row[left - 1]).strip() if not _empty(row[left - 1]) else "Не указано"
                    rv = str(row[right - 1]).strip() if not _empty(row[right - 1]) else "Не указано"
                    pair_counts[(lv, rv)] += 1; left_values[lv] += 1; right_values[rv] += 1
                other_label = "Прочие (сгруппировано)"
                while other_label in left_values or other_label in right_values:
                    other_label += "*"
                left_top = [x for x, _ in left_values.most_common(20)]
                right_top = [x for x, _ in right_values.most_common(20)]
                left_other = len(left_values) > 20
                right_other = len(right_values) > 20
                left_labels = left_top + ([other_label] if left_other else [])
                right_labels = right_top + ([other_label] if right_other else [])
                left_set, right_set = set(left_top), set(right_top)
                matrix = Counter()
                for (lv, rv), count in pair_counts.items():
                    display_left = lv if lv in left_set else other_label
                    display_right = rv if rv in right_set else other_label
                    matrix[(display_left, display_right)] += count
                cross_name = _safe_sheet_name(
                    f"{headers[left]} × {headers[right]}", wb.sheetnames
                )
                cross_ws = wb.create_sheet(cross_name)
                cross_ws.append([headers[left]] + right_labels + ["ИТОГО"])
                for lv in left_labels:
                    values = [matrix[(lv, rv)] for rv in right_labels]
                    cross_ws.append([lv] + values + [sum(values)])
                column_totals = [sum(matrix[(lv, rv)] for lv in left_labels)
                                 for rv in right_labels]
                cross_ws.append(["ИТОГО"] + column_totals + [sum(column_totals)])
                if sum(column_totals) != total:
                    raise RuntimeError("Перекрёстная таблица не прошла проверку итогов.")
                _style_summary_sheet(cross_ws)
                created_sheets.append(cross_name); cross_sheets.append(cross_name)

        changes.append({
            "type": kind, "sheet": sheet, "rows": total,
            "dimensions": [headers[c] for c in dimensions],
            "created_sheets": created_sheets, "cross_sheets": cross_sheets,
        })
        reports["smart_summary"] = {
            "source_sheet": sheet, "rows": total,
            "dimensions": [headers[c] for c in dimensions],
            "unique_id_count": unique_id_count,
            "output_sheets": created_sheets,
        }

    elif kind == "distinct_count":
        id_col = op["id_column"]
        grouping = op.get("columns", [])
        group_ids = {}
        all_ids = set()
        blank_ids = 0
        rows_total = 0
        conflicting = {}
        for values in ws.iter_rows(min_row=hr + 1, max_row=ws.max_row, values_only=True):
            if all(_empty(value) for value in values):
                continue
            rows_total += 1
            identifier = values[id_col - 1]
            if _empty(identifier):
                blank_ids += 1
                continue
            identifier = str(identifier).strip()
            key = tuple(str(values[c-1]).strip() if not _empty(values[c-1]) else "Не указано" for c in grouping)
            group_ids.setdefault(key, set()).add(identifier)
            conflicting.setdefault(identifier, set()).add(key)
            all_ids.add(identifier)
        ambiguous = sum(len(keys) > 1 for keys in conflicting.values())
        out_name = _safe_sheet_name(op.get("output_sheet", "Уникальные ID"), wb.sheetnames)
        out = wb.create_sheet(out_name)
        out.append(["Показатель", "Значение"])
        out.append(["Строк данных", rows_total])
        out.append(["Уникальных непустых ID", len(all_ids)])
        out.append(["Разница строк и уникальных ID", rows_total - len(all_ids)])
        out.append(["Строк с пустым ID", blank_ids])
        out.append(["ID в нескольких группах", ambiguous])
        if grouping:
            out.append([])
            out.append([*[str(ws.cell(hr,c).value) for c in grouping], "Уникальных ID"])
            for key, ids in sorted(group_ids.items()):
                out.append([*key, len(ids)])
        _style_summary_sheet(out)
        changes.append({"type": kind, "sheet": sheet, "id_column": id_col,
                        "group_columns": grouping, "unique_ids": len(all_ids),
                        "rows": rows_total, "blank_ids": blank_ids,
                        "cross_group_ids": ambiguous, "output_sheet": out_name})
        reports["distinct_count"] = {"unique_ids": len(all_ids), "rows": rows_total,
                                      "cross_group_ids": ambiguous}

    elif kind == "group_by_aggregate":
        grouping_columns = op.get("columns") or [op["column"]]
        target_col = op.get("target_column")
        function = op.get("function", "sum")
        include_empty = bool(op.get("include_empty", False))
        groups = {}

        for values in ws.iter_rows(
            min_row=hr + 1,
            max_row=ws.max_row,
            min_col=1,
            max_col=ws.max_column,
            values_only=True,
        ):
            if all(_empty(value) for value in values):
                continue

            raw_group_values = tuple(values[col - 1] for col in grouping_columns)
            if not include_empty and any(_empty(value) for value in raw_group_values):
                continue

            labels = tuple(
                value if not _empty(value) else "Не указано"
                for value in raw_group_values
            )
            key = tuple(
                (type(value).__name__, str(value))
                for value in labels
            )
            if key not in groups:
                groups[key] = {
                    "labels": labels,
                    "values": [],
                    "rows": 0,
                }
            groups[key]["rows"] += 1

            if function == "count":
                groups[key]["values"].append(1)
                continue

            target_value = values[target_col - 1] if target_col else None
            if not _empty(target_value):
                try:
                    num_val = float(str(target_value).replace(",", "."))
                    groups[key]["values"].append(num_val)
                except (ValueError, TypeError):
                    pass

        output_sheet = _safe_sheet_name(
            op.get("output_sheet", "Агрегация"),
            wb.sheetnames,
        )
        target_ws = wb.create_sheet(output_sheet)

        group_headers = [
            str(ws.cell(hr, col).value or f"Столбец {col}")
            for col in grouping_columns
        ]
        result_header = "Количество" if function == "count" else {
            "sum": "Сумма", "avg": "Среднее", "min": "Минимум", "max": "Максимум"
        }.get(function, "Значение")
        target_ws.append(group_headers + [result_header])

        total_rows = 0
        ordered_groups = sorted(
            groups.values(),
            key=lambda item: tuple(str(v).casefold() for v in item["labels"]),
        )

        for group in ordered_groups:
            if function == "count":
                value_count = group["rows"]
            else:
                numbers = group["values"]
                if function == "avg":
                    value_count = (sum(numbers) / len(numbers)) if numbers else 0
                elif function == "min":
                    value_count = min(numbers) if numbers else 0
                elif function == "max":
                    value_count = max(numbers) if numbers else 0
                else:
                    value_count = sum(numbers)

            if function == "count":
                total_rows += value_count
            target_ws.append(list(group["labels"]) + [value_count])

        if function == "count":
            target_ws.append(["ИТОГО"] + [""] * (len(grouping_columns) - 1) + [total_rows])

        changes.append({
            "type": kind,
            "sheet": sheet,
            "group_columns": grouping_columns,
            "function": function,
            "output_sheet": output_sheet,
            "groups": len(groups),
            "total_rows": total_rows if function == "count" else None,
        })

    elif kind == "apply_formula":
        col = op["column"]
        formula_template = op["formula"]
        count = 0

        for row_num in range(hr + 1, ws.max_row + 1):
            try:
                cell_formula = formula_template.format(row=row_num)
            except (KeyError, IndexError, ValueError) as exc:
                raise ValueError(f"Некорректный шаблон формулы: {exc}") from exc
            ws.cell(row_num, col).value = cell_formula
            count += 1

        changes.append({
            "type": kind,
            "sheet": sheet,
            "column": col,
            "inserted_formulas": count,
        })

    elif kind == "summary_count":
        col = op["column"]
        counts = {}

        for row_num in range(hr + 1, ws.max_row + 1):
            value = ws.cell(row_num, col).value
            key = str(value) if value is not None else "(пусто)"
            counts[key] = counts.get(key, 0) + 1

        name = _safe_sheet_name(
            op.get("output_sheet", "Сводка"),
            wb.sheetnames,
        )

        target = wb.create_sheet(name)
        target.append(["Значение", "Количество"])

        for key, count in sorted(
            counts.items(),
            key=lambda item: item[0].casefold(),
        ):
            target.append([key, count])

        changes.append({
            "type": kind,
            "sheet": sheet,
            "output_sheet": name,
            "categories": len(counts),
        })

    elif kind == "validate_values":
        col = op["column"]
        rule = op.get("rule", "not_empty")
        allowed = op.get("allowed_values", [])
        errors = []

        for row_num in range(hr + 1, ws.max_row + 1):
            value = ws.cell(row_num, col).value

            bad = (
                (rule == "not_empty" and _empty(value))
                or (
                    rule == "numeric"
                    and value is not None
                    and (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                    )
                )
                or (
                    rule == "positive"
                    and (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or value <= 0
                    )
                )
                or (
                    rule == "allowed_values"
                    and value not in allowed
                )
            )

            if bad:
                errors.append({
                    "row": row_num,
                    "cell": ws.cell(row_num, col).coordinate,
                    "value": value,
                    "rule": rule,
                })

        reports.setdefault("validation_errors", []).append({
            "sheet": sheet,
            "column": col,
            "errors": errors,
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "errors": len(errors),
        })

    elif kind == "compare_columns":
        a = op["column"]
        b = op["other_column"]
        mismatches = []

        for row_num in range(hr + 1, ws.max_row + 1):
            left = ws.cell(row_num, a).value
            right = ws.cell(row_num, b).value

            if left != right:
                mismatches.append({
                    "row": row_num,
                    "left": left,
                    "right": right,
                })

        reports.setdefault("column_comparisons", []).append({
            "sheet": sheet,
            "column": a,
            "other_column": b,
            "mismatches": mismatches,
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "mismatches": len(mismatches),
        })

    else:
        raise NotImplementedError(
            f"Обработчик операции {kind!r} не реализован."
        )


# ============================================================
# EXECUTE SAFELY
# ============================================================

def execute_operations(plan, confirmed=False):
    if confirmed is not True:
        raise PermissionError(
            "Нужно явное подтверждение пользователя."
        )

    if (
        not isinstance(plan, dict)
        or plan.get("requires_confirmation") is not True
    ):
        raise ValueError("Некорректный план.")

    fingerprint = plan.get("plan_sha256")
    base = dict(plan)
    base.pop("plan_sha256", None)

    if not fingerprint or _fingerprint(base) != fingerprint:
        raise ValueError(
            "План изменён после согласования. Подготовьте его заново."
        )

    src, dst = _validate_paths(
        plan["source"],
        plan["output"],
    )

    if _sha(src) != plan.get("source_sha256"):
        raise RuntimeError(
            "Исходный файл изменился после подготовки плана."
        )

    dst.parent.mkdir(parents=True, exist_ok=True)

    report_path = dst.with_suffix(
        dst.suffix + ".report.json"
    )

    if report_path.exists():
        raise FileExistsError(
            f"Файл отчёта уже существует: {report_path}"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = dst.parent / f"{src.stem}.backup_{stamp}{src.suffix}"
    counter = 2
    while backup.exists():
        backup = dst.parent / f"{src.stem}.backup_{stamp}_{counter}{src.suffix}"
        counter += 1
    shutil.copy2(src, backup)
    if _sha(backup) != plan["source_sha256"]:
        backup.unlink(missing_ok=True)
        raise RuntimeError("Резервная копия не прошла проверку контрольной суммы.")

    fd, temp_name = tempfile.mkstemp(
        suffix=dst.suffix,
        dir=dst.parent,
    )
    os.close(fd)
    temp = Path(temp_name)

    report_fd, report_temp_name = tempfile.mkstemp(
        prefix=".bahoniq_report_",
        suffix=".tmp",
        dir=dst.parent,
    )
    os.close(report_fd)
    report_temp = Path(report_temp_name)

    wb = None
    changes = []
    reports = {}

    created_side_effect_files = []
    output_published = False
    report_published = False

    try:
        validation_wb = _load_source_workbook(src)
        try:
            normalized = _validate_ops(
                plan["operations"],
                validation_wb,
            )
        finally:
            validation_wb.close()

        if normalized != plan["operations"]:
            raise ValueError(
                "Операции изменились после утверждения плана."
            )

        # Validation may create lightweight placeholder sheets for dependent
        # steps. Execute against a fresh workbook so placeholders never reach
        # the user's result.
        wb = _load_source_workbook(src)

        for op in normalized:
            _do(
                wb,
                op,
                changes,
                reports,
                created_side_effect_files=created_side_effect_files,
            )

        for change in changes:
            if change.get("type") == "split_to_sheets":
                if change.get("source_data_rows") != change.get("distributed_rows"):
                    raise RuntimeError(
                        "Разделение на листы потеряло или продублировало строки."
                    )

        wb.save(temp)
        wb.close()
        wb = None

        check = load_workbook(
            temp,
            read_only=True,
            keep_vba=dst.suffix.lower() == ".xlsm",
            data_only=False,
        )

        try:
            sheets = list(check.sheetnames)

            if not sheets:
                raise RuntimeError(
                    "Итоговая книга не содержит листов."
                )
        finally:
            check.close()

        if _sha(src) != plan["source_sha256"]:
            raise RuntimeError(
                "Исходный файл изменился во время обработки."
            )

        if dst.exists():
            raise FileExistsError(
                f"Файл результата уже существует: {dst}"
            )

        if report_path.exists():
            raise FileExistsError(
                f"Файл отчёта уже существует: {report_path}"
            )

        audit_ops = [op for op in plan.get("operations", []) if op.get("type") == "student_data_audit"]
        if audit_ops:
            required_audit_sheets = {
                "Сводка", "Повторяющиеся ID", "Пустые данные",
                "Полные дубли", "Проверка факультетов", "Нормализация",
            }
            missing_audit_sheets = sorted(required_audit_sheets.difference(sheets))
            audit_report = reports.get("student_data_audit")
            if missing_audit_sheets or not isinstance(audit_report, dict):
                raise RuntimeError(
                    "Комплексный аудит не прошёл проверку полноты. "
                    f"Отсутствуют листы: {missing_audit_sheets}; "
                    f"отчёт операции создан: {isinstance(audit_report, dict)}"
                )
            declared = set(audit_report.get("output_sheets", []))
            if not required_audit_sheets.issubset(declared):
                raise RuntimeError("Отчёт аудита не подтверждает создание всех шести листов.")

        report = {
            "status": "completed",
            "source": str(src),
            "output": str(dst),
            "backup": str(backup),
            "source_sha256": plan["source_sha256"],
            "output_sha256": _sha(temp),
            "source_modified": False,
            "source_was_modified": False,
            "sheets": sheets,
            "changes": changes,
            "reports": reports,
        }

        report_temp.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        os.link(temp, dst)
        output_published = True

        os.link(report_temp, report_path)
        report_published = True

        return report

    except Exception:
        for created_path in reversed(created_side_effect_files):
            try:
                Path(created_path).unlink(missing_ok=True)
            except OSError:
                pass

        if output_published and not report_published:
            try:
                dst.unlink(missing_ok=True)
            except OSError:
                pass

        if report_published:
            try:
                report_path.unlink(missing_ok=True)
            except OSError:
                pass

        try:
            backup.unlink(missing_ok=True)
        except OSError:
            pass

        raise

    finally:
        if wb is not None:
            wb.close()

        temp.unlink(missing_ok=True)
        report_temp.unlink(missing_ok=True)
