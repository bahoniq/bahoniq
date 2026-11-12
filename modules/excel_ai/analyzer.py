
from collections import Counter
from pathlib import Path
from datetime import date, datetime
from itertools import chain
import math

from .intelligence import enrich_analysis

SUPPORTED_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}


def _normalise(value):
    """Преобразует значения ячеек в представление для отчёта."""
    if value is None or value == "":
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, float):
        if math.isnan(value):
            return None
        if not math.isfinite(value):
            return str(value)

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _key(value):
    value = _normalise(value)
    return type(value).__name__, repr(value)


def _is_nonempty(row):
    return any(value is not None for value in row)


def _column_letter(number):
    result = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _header_score(rows, index):
    """Score a row as a likely table header without using domain keywords."""
    values = [_normalise(value) for value in rows[index][0]]
    populated = [value for value in values if value is not None]
    if not populated:
        return float("-inf")

    text_values = [value for value in populated if isinstance(value, str)]
    formulas = [value for value in text_values if value.startswith("=")]
    unique = len({_key(value) for value in populated})
    score = len(populated) * 2.0 + len(text_values) * 1.5 + unique * 0.5

    # A document title or note commonly occupies only one or two cells.
    if len(populated) == 1:
        score -= 8.0
    elif len(populated) == 2:
        score -= 3.0
    if formulas:
        score -= len(formulas) * 4.0

    # Real headers are normally followed by rows using several of the same
    # columns. This also prevents a long title above the table from winning.
    following = rows[index + 1:index + 5]
    compatible = 0
    for raw, _ in following:
        next_values = [_normalise(value) for value in raw]
        next_count = sum(value is not None for value in next_values)
        if next_count >= max(1, min(len(populated), 3)):
            compatible += 1
    score += compatible * 2.0
    return score


def _detect_header(rows):
    """Return the zero-based index of the most plausible header row."""
    candidates = [i for i, (raw, _) in enumerate(rows) if _is_nonempty(raw)]
    if not candidates:
        return None
    return max(candidates, key=lambda i: (_header_score(rows, i), -i))


def _xls_cell_value(book, sheet, row_index, col_index):
    import xlrd

    cell = sheet.cell(row_index, col_index)
    value = cell.value

    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None

    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(value, book.datemode)
        except (ValueError, OverflowError):
            return value

    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(value)

    if cell.ctype == xlrd.XL_CELL_ERROR:
        return f"#XLS_ERROR_{int(value)}"

    if cell.ctype == xlrd.XL_CELL_NUMBER:
        if math.isfinite(value) and value.is_integer():
            return int(value)

    return value


def _analyse_sheet(
    name,
    state,
    max_row,
    max_col,
    row_reader,
    merged_ranges,
    sample_rows,
    max_examples,
):
    """Анализирует лист, сохраняя прежнюю структуру отчёта."""
    cell_count = max_row * max_col if max_row and max_col else 0

    headers = []

    # Inspect a small prefix once. The rest of a large sheet remains streamed.
    prefix = []
    iterator = iter(row_reader)
    for _ in range(min(max_row, 30)):
        try:
            prefix.append(next(iterator))
        except StopIteration:
            break
    header_index = _detect_header(prefix)
    header_row = header_index + 1 if header_index is not None else None
    if header_index is not None:
        header_values = [_normalise(value) for value in prefix[header_index][0]]
        headers = [
            str(value).strip() if value is not None and str(value).strip()
            else f"Column {col_index}"
            for col_index, value in enumerate(header_values, start=1)
        ]

    nonempty_rows = 0
    blank_rows = 0
    nonempty_cells = 0
    formula_count = 0

    formula_examples = []
    preview = []

    duplicate_row_counts = Counter()
    column_counts = [Counter() for _ in range(max_col)]
    column_original_values = [{} for _ in range(max_col)]

    # row_reader теперь читает строки из одного последовательного
    # итератора, а не создаёт итератор заново для каждой строки.
    for row_index, (raw_values, formulas) in enumerate(chain(prefix, iterator)):
        values = [_normalise(value) for value in raw_values]
        row_has_data = _is_nonempty(values)

        if row_has_data:
            nonempty_rows += 1
            nonempty_cells += sum(value is not None for value in values)
        else:
            blank_rows += 1

        for col_index, formula in enumerate(formulas):
            if formula is None:
                continue

            formula_count += 1

            if len(formula_examples) < max_examples:
                formula_examples.append({
                    "cell": f"{_column_letter(col_index + 1)}{row_index + 1}",
                    "formula": formula,
                })

        # Titles, notes and blank spacer rows above the detected header are
        # workbook context, not table records.
        if header_index is not None and row_index <= header_index:
            continue

        if not row_has_data:
            continue

        if len(preview) < sample_rows:
            preview.append(values)

        duplicate_row_counts[
            tuple(_key(value) for value in values)
        ] += 1

        for col_index, value in enumerate(values):
            if value is None:
                continue

            key = _key(value)
            column_counts[col_index][key] += 1

            if key not in column_original_values[col_index]:
                column_original_values[col_index][key] = value

    duplicate_row_count = sum(
        count - 1
        for count in duplicate_row_counts.values()
        if count > 1
    )

    duplicate_columns = []

    for col_index, counts in enumerate(column_counts):
        duplicates = [
            {
                "value": column_original_values[col_index][key],
                "occurrences": count,
            }
            for key, count in counts.items()
            if count > 1
        ]

        duplicates.sort(
            key=lambda item: (
                -item["occurrences"],
                str(item["value"]),
            )
        )

        if duplicates:
            duplicate_columns.append({
                "column": col_index + 1,
                "header": (
                    headers[col_index]
                    if col_index < len(headers)
                    else f"Column {col_index + 1}"
                ),
                "duplicate_value_count": len(duplicates),
                "extra_occurrences": sum(
                    item["occurrences"] - 1
                    for item in duplicates
                ),
                "examples": duplicates[:max_examples],
            })

    blank_cells = max(0, cell_count - nonempty_cells)

    report = {
        "name": name,
        "state": state,
        "hidden": state != "visible",
        "rows": max_row,
        "columns": max_col,
        "nonempty_rows": nonempty_rows,
        "blank_rows": blank_rows,
        "nonempty_cells": nonempty_cells,
        "blank_cells": blank_cells,
        "headers": headers,
        "header_row": header_row,
        "data_start_row": header_row + 1 if header_row else None,
        "duplicate_rows": duplicate_row_count,
        "duplicate_columns": duplicate_columns,
        "formula_count": formula_count,
        "formula_examples": formula_examples,
        "merged_ranges": merged_ranges,
        "preview": preview,
    }
    return report


def _analyse_xls(file_path, sample_rows, max_examples):
    """Анализирует старый формат XLS через xlrd."""
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "Для чтения файлов .xls нужна библиотека xlrd. "
            "Установи её командой: py -m pip install xlrd"
        ) from exc

    try:
        book = xlrd.open_workbook(str(file_path), on_demand=True)
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось открыть XLS-файл: {file_path}. "
            "Проверь, что файл не повреждён или не защищён."
        ) from exc

    sheets = []

    try:
        for sheet_index in range(book.nsheets):
            ws = book.sheet_by_index(sheet_index)

            visibility = getattr(ws, "visibility", 0)
            state = (
                "visible" if visibility == 0
                else "hidden" if visibility == 1
                else "veryHidden"
            )

            def row_reader(current_sheet=ws):
                for row_index in range(current_sheet.nrows):
                    values = [
                        _xls_cell_value(
                            book, current_sheet, row_index, col_index
                        )
                        for col_index in range(current_sheet.ncols)
                    ]
                    yield values, [None] * current_sheet.ncols

            merged_ranges = []

            for rlo, rhi, clo, chi in ws.merged_cells:
                start = f"{_column_letter(clo + 1)}{rlo + 1}"
                end = f"{_column_letter(chi)}{rhi}"
                merged_ranges.append(f"{start}:{end}")

            sheets.append(_analyse_sheet(
                name=ws.name,
                state=state,
                max_row=ws.nrows,
                max_col=ws.ncols,
                row_reader=row_reader(),
                merged_ranges=merged_ranges,
                sample_rows=sample_rows,
                max_examples=max_examples,
            ))
    finally:
        book.release_resources()

    return sheets


def _analyse_openpyxl(file_path, sample_rows, max_examples):
    """Анализирует XLSX/XLSM последовательным чтением строк."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "Не установлена библиотека openpyxl. "
            "Установи её командой: py -m pip install openpyxl"
        ) from exc

    try:
        workbook = load_workbook(
            filename=file_path,
            read_only=True,
            data_only=False,
            keep_vba=file_path.suffix.lower() == ".xlsm",
        )
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось открыть Excel-файл: {file_path}. "
            "Проверь, что файл не повреждён."
        ) from exc

    sheets = []

    try:
        for ws in workbook.worksheets:
            max_row = ws.max_row or 0
            max_col = ws.max_column or 0

            # Some valid XLSX producers (including openpyxl write-only mode)
            # leave the worksheet dimension as A1:A1 even when the sheet has
            # many rows and columns.  Recalculate only for this suspicious
            # minimal dimension; doing it for every sheet would add a second
            # full scan to normal workbooks.
            if max_row <= 1 and max_col <= 1:
                ws.reset_dimensions()
                try:
                    ws.calculate_dimension(force=True)
                    max_row = ws.max_row or 0
                    max_col = ws.max_column or 0
                except UnboundLocalError:
                    # openpyxl raises this for a genuinely empty read-only
                    # worksheet. An empty target sheet is valid Excel data.
                    max_row = max_col = 0

            def row_reader(current_sheet=ws, columns=max_col):
                if not columns:
                    return

                for cells in current_sheet.iter_rows(
                    min_row=1,
                    max_row=max_row,
                    min_col=1,
                    max_col=columns,
                ):
                    values = []
                    formulas = []

                    for cell in cells:
                        value = cell.value
                        values.append(value)
                        formulas.append(
                            value
                            if isinstance(value, str)
                            and value.startswith("=")
                            else None
                        )

                    yield values, formulas

            # В read_only режиме объединённые диапазоны могут
            # быть недоступны.
            merged_ranges = []
            try:
                merged_ranges = [
                    str(item) for item in ws.merged_cells.ranges
                ]
            except (AttributeError, TypeError):
                pass

            sheets.append(_analyse_sheet(
                name=ws.title,
                state=ws.sheet_state,
                max_row=max_row,
                max_col=max_col,
                row_reader=row_reader(),
                merged_ranges=merged_ranges,
                sample_rows=sample_rows,
                max_examples=max_examples,
            ))
    finally:
        workbook.close()

    return sheets


def analyze_workbook(path, sample_rows=5, max_examples=10):
    """
    Анализирует XLS, XLSX и XLSM.
    Исходный файл не изменяется.
    Структура отчёта совместима с существующим UI.
    """
    if (
        not isinstance(sample_rows, int)
        or isinstance(sample_rows, bool)
        or sample_rows < 0
    ):
        raise ValueError("sample_rows должен быть целым числом >= 0.")

    if (
        not isinstance(max_examples, int)
        or isinstance(max_examples, bool)
        or max_examples < 0
    ):
        raise ValueError("max_examples должен быть целым числом >= 0.")

    file_path = Path(path).expanduser().resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"Excel-файл не найден: {file_path}")

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Поддерживаются файлы .xls, .xlsx и .xlsm.")

    if extension == ".xls":
        sheets = _analyse_xls(file_path, sample_rows, max_examples)
    else:
        sheets = _analyse_openpyxl(file_path, sample_rows, max_examples)

    report = {
        "file": str(file_path),
        "file_name": file_path.name,
        "format": extension,
        "sheet_count": len(sheets),
        "totals": {
            "rows_across_sheets": sum(s["rows"] for s in sheets),
            "cells_in_used_ranges": sum(
                s["rows"] * s["columns"] for s in sheets
            ),
            "blank_cells": sum(s["blank_cells"] for s in sheets),
            "blank_rows": sum(s["blank_rows"] for s in sheets),
            "formulas": sum(s["formula_count"] for s in sheets),
        },
        "sheets": sheets,
    }
    return enrich_analysis(report)
