from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill


# ============================================================
# BAHONIQ — EXCEL AI OPERATIONS
# ============================================================

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}

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
    "split_by_column",
    "split_to_sheets",
    "merge_sheets",
    "summary_count",
    "validate_values",
    "compare_columns",
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
    "reorder": "reorder_columns",
    "merge": "merge_sheets",
    "count": "summary_count",
    "validate": "validate_values",
    "compare": "compare_columns",
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
    name = (name or "Лист")[:31]
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


def _validate_paths(source, output):
    src = Path(source).expanduser().resolve()
    dst = Path(output).expanduser().resolve()

    if not src.is_file():
        raise FileNotFoundError(
            f"Исходный файл не найден: {src}"
        )

    if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Поддерживаются .xlsx и .xlsm. "
            "Файл .xls сначала сохраните как .xlsx."
        )

    if dst.suffix.lower() not in SUPPORTED_EXTENSIONS:
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


def _resolve_column(
    ws,
    value,
    header_rows=1,
    operation_name="операция",
):
    """Принимает номер столбца или название заголовка."""

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
                f"Операция {index}: ожидался объект."
            )

        op = _canonicalize_operation(raw)
        kind = op.get("type")

        if kind not in SUPPORTED_TYPES:
            raise ValueError(
                f"Операция {index}: тип не поддерживается: {kind!r}"
            )

        sheet = op.get("sheet")

        if kind != "merge_sheets":
            if not isinstance(sheet, str) or sheet not in wb.sheetnames:
                raise ValueError(
                    f"Операция {index}: лист {sheet!r} не найден. "
                    f"Доступные листы: {', '.join(wb.sheetnames)}"
                )

        op.setdefault("header_rows", 1)
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
                "find_blank_cells",
                "sort_rows",
                "split_by_column",
                "split_to_sheets",
                "summary_count",
                "validate_values",
                "compare_columns",
            }

            if kind in column_types:
                op["column"] = _resolve_column(
                    ws,
                    op.get("column"),
                    hr,
                    f"Операция {index} ({kind})",
                )

            if kind == "compare_columns":
                op["other_column"] = _resolve_column(
                    ws,
                    op.get("other_column"),
                    hr,
                    f"Операция {index} (compare_columns)",
                )

            if kind in {"select_columns", "reorder_columns"}:
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

                if op.get("column") is not None:
                    op["column"] = _resolve_column(
                        ws,
                        op["column"],
                        hr,
                        f"Операция {index} (fill_empty)",
                    )

            if kind == "replace_values":
                if not isinstance(op.get("old"), str) or not isinstance(
                    op.get("new"), str
                ):
                    raise ValueError(
                        "replace_values требует строковые поля old и new."
                    )

                if op.get("column") is not None:
                    op["column"] = _resolve_column(
                        ws,
                        op["column"],
                        hr,
                        f"Операция {index} (replace_values)",
                    )

            if kind == "split_by_column":
                if (
                    not isinstance(op.get("output_dir"), str)
                    or not op["output_dir"].strip()
                ):
                    raise ValueError(
                        "split_by_column требует папку output_dir."
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

    return result


# ============================================================
# CREATE PLAN
# ============================================================

def plan_operations(source, output, operations):
    src, dst = _validate_paths(source, output)

    wb = load_workbook(
        src,
        keep_vba=src.suffix.lower() == ".xlsm",
        data_only=False,
    )

    try:
        normalized = _validate_ops(operations, wb)

        plan = {
            "source": str(src),
            "output": str(dst),
            "source_sha256": _sha(src),
            "operations": normalized,
            "steps": [
                f"{op['type']} — {op.get('sheet', '')}"
                for op in normalized
            ],
            "requires_confirmation": True,
            "source_will_be_modified": False,
        }

        plan["plan_sha256"] = _fingerprint(plan)
        return plan

    finally:
        wb.close()


# ============================================================
# EXECUTE OPERATIONS
# ============================================================

def _do(wb, op, changes, reports, created_side_effect_files=None):
    """
    Выполняет одну операцию.

    created_side_effect_files отслеживает файлы, созданные
    split_by_column, чтобы удалить их, если общий процесс упадёт.
    """
    if created_side_effect_files is None:
        created_side_effect_files = []

    # В исходном присланном коде эти три переменные отсутствовали.
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

    if kind == "remove_empty_rows":
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
            "removed_rows": removed,
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
        col = op.get("column")
        columns = [col] if col else range(1, ws.max_column + 1)
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

        for row in ws.iter_rows(min_row=hr + 1):
            for cell in row:
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
        col = op.get("column")
        columns = [col] if col else range(1, ws.max_column + 1)

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

            # Не считаем пустые строки дубликатами.
            if all(_empty(value) for value in values):
                continue

            # Сохраняем типы значений, чтобы число 1 и текст "1"
            # не считались одинаковыми автоматически.
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
        col = op["column"]
        blanks = []

        for row_num in range(hr + 1, ws.max_row + 1):
            cell = ws.cell(row_num, col)

            if _empty(cell.value):
                blanks.append({
                    "cell": cell.coordinate,
                    "row": row_num,
                    "column": col,
                })

        reports.setdefault("blank_cells", []).append({
            "sheet": sheet,
            "cells": blanks,
        })

        changes.append({
            "type": kind,
            "sheet": sheet,
            "blank_cells": len(blanks),
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
        col = op["column"]
        groups = {}

        for row_num in range(hr + 1, ws.max_row + 1):
            value = ws.cell(row_num, col).value

            group_name = (
                str(value).strip()
                if not _empty(value)
                else "Пусто"
            )

            groups.setdefault(group_name, []).append([
                ws.cell(row_num, c).value
                for c in range(1, ws.max_column + 1)
            ])

        if not groups:
            raise ValueError(
                f"На листе {sheet!r} нет строк для разделения."
            )

        if kind == "split_to_sheets":
            created = []

            for group_name, rows in groups.items():
                name = _safe_sheet_name(
                    group_name,
                    wb.sheetnames,
                )
                target = wb.create_sheet(name)

                for row_num in range(1, hr + 1):
                    target.append([
                        ws.cell(row_num, c).value
                        for c in range(1, ws.max_column + 1)
                    ])

                for row in rows:
                    target.append(row)

                created.append({
                    "sheet": name,
                    "group": group_name,
                    "rows": len(rows),
                })

            changes.append({
                "type": kind,
                "source_sheet": sheet,
                "column": col,
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

                # Сначала создаём и проверяем все файлы во временной папке.
                for group_name, rows in groups.items():
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

                # Повторная проверка перед публикацией.
                for item in staged_files:
                    if item["final_path"].exists():
                        raise FileExistsError(
                            "Файл появился во время подготовки: "
                            f"{item['final_path']}"
                        )

                # Публикуем через hard link: существующий файл
                # не перезаписывается даже при гонке процессов.
                for item in staged_files:
                    os.link(
                        item["staged_path"],
                        item["final_path"],
                    )

                    created_files.append(item["final_path"])

                    # Внешний список нужен для отката всего процесса,
                    # если позднее упадёт сохранение основного Excel.
                    created_side_effect_files.append(
                        item["final_path"]
                    )

                files = [
                    str(item["final_path"])
                    for item in staged_files
                ]

            except Exception:
                # Удаляем только файлы, созданные этой операцией.
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

    # Не перезаписываем существующий отчёт.
    if report_path.exists():
        raise FileExistsError(
            f"Файл отчёта уже существует: {report_path}"
        )

    backup_dir = dst.parent / "BahonIQ_Backups" / "ExcelAI"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup = backup_dir / (
        f"{src.stem}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        f"{src.suffix}"
    )

    shutil.copy2(src, backup)

    if _sha(src) != _sha(backup):
        backup.unlink(missing_ok=True)
        raise RuntimeError(
            "Резервная копия не прошла проверку."
        )

    fd, temp_name = tempfile.mkstemp(
        suffix=dst.suffix,
        dir=dst.parent,
    )
    os.close(fd)
    temp = Path(temp_name)

    # Отчёт также создаётся во временном файле.
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
        wb = load_workbook(
            backup,
            keep_vba=src.suffix.lower() == ".xlsm",
            data_only=False,
        )

        normalized = _validate_ops(
            plan["operations"],
            wb,
        )

        if normalized != plan["operations"]:
            raise ValueError(
                "Операции изменились после утверждения плана."
            )

        for op in normalized:
            _do(
                wb,
                op,
                changes,
                reports,
                created_side_effect_files=created_side_effect_files,
            )

        wb.save(temp)
        wb.close()
        wb = None

        # Проверяем, что итоговая книга читается.
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

        # Сначала записываем полный JSON во временный файл.
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

        # Атомарно публикуем итоговую книгу без перезаписи.
        # os.link не заменит файл, появившийся после проверки.
        os.link(temp, dst)
        output_published = True

        # Отчёт публикуется только после успешной записи.
        # Если путь занят, существующий файл не будет перезаписан.
        os.link(report_temp, report_path)
        report_published = True

        return report

    except Exception:
        # Откатываем только файлы групп, созданные текущим запуском.
        for created_path in reversed(created_side_effect_files):
            try:
                Path(created_path).unlink(missing_ok=True)
            except OSError:
                pass

        # Удаляем итоговую книгу только если именно этот запуск
        # создал её и публикация отчёта не завершилась.
        if output_published and not report_published:
            try:
                dst.unlink(missing_ok=True)
            except OSError:
                pass

        # Удаляем отчёт только если именно этот запуск его создал,
        # а последующая операция завершилась ошибкой.
        if report_published:
            try:
                report_path.unlink(missing_ok=True)
            except OSError:
                pass

        raise

    finally:
        if wb is not None:
            wb.close()

        temp.unlink(missing_ok=True)
        report_temp.unlink(missing_ok=True)