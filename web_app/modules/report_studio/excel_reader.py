# -*- coding: utf-8 -*-
"""Чтение Excel и базовая проверка качества данных."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import SUPPORTED_EXTENSIONS


class ExcelReadError(Exception):
    """Ошибка чтения Excel-файла."""


def _is_empty(value: Any) -> bool:
    """Проверяет, является ли значение пустым."""
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _cell_text(value: Any) -> str:
    """Преобразует значение ячейки в строку с форматированием."""
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")

    return str(value).strip()


def _trim_matrix(matrix: list[list[Any]]) -> list[list[Any]]:
    """Удаляет пустые строки и столбцы по краям данных."""
    if not matrix:
        return []

    # Удаляем пустые строки снизу
    while matrix and all(_is_empty(v) for v in matrix[-1]):
        matrix.pop()

    if not matrix:
        return []

    # Находим самый правый заполненный столбец
    last_column = -1
    for row in matrix:
        for index, value in enumerate(row):
            if not _is_empty(value):
                last_column = max(last_column, index)

    if last_column < 0:
        return []

    # Обрезаем столбцы справа
    matrix = [row[:last_column + 1] for row in matrix]

    # Удаляем пустые строки сверху
    while matrix and all(_is_empty(v) for v in matrix[0]):
        matrix.pop(0)

    return matrix


def _find_header_row(matrix: list[list[Any]]) -> int:
    """
    Автоматически находит строку заголовков таблицы.
    Пропускает декоративные названия отчётов и объединения ячеек вверху.
    """
    if not matrix:
        return 0

    best_row_index = 0
    max_filled_columns = 0

    # Проверяем первые 15 строк
    for index, row in enumerate(matrix[:15]):
        filled_count = sum(1 for cell in row if not _is_empty(cell))

        # Если в этой строке заполнено больше столбцов, чем в предыдущих кандидатах
        if filled_count > max_filled_columns:
            max_filled_columns = filled_count
            best_row_index = index

    return best_row_index


def _read_xlsx(path: Path) -> dict:
    """Читает современные файлы .xlsx / .xlsm через openpyxl."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ExcelReadError(
            "Не установлен openpyxl. Выполните: "
            "python -m pip install openpyxl"
        ) from exc

    warnings = []
    sheets = []

    workbook = None
    formula_workbook = None

    try:
        # Книга с вычисленными значениями
        workbook = load_workbook(
            filename=str(path),
            read_only=True,
            data_only=True,
            keep_links=False,
        )

        # Книга с сырыми формулами для проверки невычисленных ячеек
        formula_workbook = load_workbook(
            filename=str(path),
            read_only=True,
            data_only=False,
            keep_links=False,
        )

        for ws in workbook.worksheets:
            formula_ws = formula_workbook[ws.title]

            if hasattr(ws, "reset_dimensions"):
                ws.reset_dimensions()
            if hasattr(formula_ws, "reset_dimensions"):
                formula_ws.reset_dimensions()

            matrix = [list(row) for row in ws.iter_rows(values_only=True)]
            formula_matrix = [list(row) for row in formula_ws.iter_rows(values_only=True)]

            missing_formula_values = 0

            for row_index, formula_row in enumerate(formula_matrix):
                if row_index >= len(matrix):
                    break

                value_row = matrix[row_index]

                for col_index, formula in enumerate(formula_row):
                    if (
                        isinstance(formula, str)
                        and formula.startswith("=")
                        and col_index < len(value_row)
                        and value_row[col_index] is None
                    ):
                        missing_formula_values += 1

            if missing_formula_values:
                warnings.append(
                    f"Лист «{ws.title}»: у {missing_formula_values} формул отсутствуют "
                    "сохранённые результаты. Значения не заменены нулями."
                )

            sheets.append({
                "name": ws.title,
                "matrix": _trim_matrix(matrix),
            })

    finally:
        if workbook is not None:
            workbook.close()
        if formula_workbook is not None:
            formula_workbook.close()

    return {
        "path": str(path.resolve()),
        "format": path.suffix.lower(),
        "sheets": sheets,
        "warnings": warnings,
    }


def _read_xls(path: Path) -> dict:
    """Читает старый формат .xls через xlrd."""
    try:
        import xlrd
    except ImportError as exc:
        raise ExcelReadError(
            "Для чтения старого формата .xls установите xlrd:\n"
            "python -m pip install xlrd"
        ) from exc

    try:
        workbook = xlrd.open_workbook(
            str(path),
            on_demand=True,
        )

        sheets = []

        try:
            for sheet in workbook.sheets():
                matrix = [
                    [
                        _convert_xls_cell(
                            sheet.cell_value(row_index, col_index),
                            sheet.cell_type(row_index, col_index),
                            xlrd,
                        )
                        for col_index in range(sheet.ncols)
                    ]
                    for row_index in range(sheet.nrows)
                ]

                sheets.append({
                    "name": sheet.name,
                    "matrix": _trim_matrix(matrix),
                })
        finally:
            workbook.release_resources()

        return {
            "path": str(path.resolve()),
            "format": ".xls",
            "sheets": sheets,
            "warnings": [
                "В формате .xls формулы могут быть представлены "
                "только сохранёнными результатами. Их актуальность "
                "не гарантируется."
            ],
        }

    except Exception as exc:
        raise ExcelReadError(
            f"Не удалось прочитать XLS-файл «{path.name}»: {exc}"
        ) from exc


def _convert_xls_cell(value: Any, cell_type: int, xlrd):
    """Преобразует ячейки xlrd в стандартные типы Python."""
    if cell_type in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None

    if cell_type == xlrd.XL_CELL_DATE:
        try:
            return datetime(*xlrd.xldate_as_tuple(value, 0))
        except Exception:
            return value

    if cell_type == xlrd.XL_CELL_BOOLEAN:
        return bool(value)

    if cell_type == xlrd.XL_CELL_ERROR:
        return f"Ошибка Excel: {xlrd.error_text_from_code.get(value, value)}"

    if cell_type == xlrd.XL_CELL_TEXT:
        return value

    return value


def read_excel(path: str | Path) -> dict:
    """Читает Excel и возвращает данные листов и предупреждения."""
    path = Path(path).expanduser()

    if not path.is_file():
        raise ExcelReadError(f"Файл не найден: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ExcelReadError(
            f"Формат {extension or '(без расширения)'} не поддерживается."
        )

    try:
        if extension == ".xls":
            return _read_xls(path)

        return _read_xlsx(path)

    except ExcelReadError:
        raise
    except Exception as exc:
        raise ExcelReadError(
            f"Не удалось прочитать «{path.name}»: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def analyze_sheet_matrix(matrix: list[list[Any]]) -> dict:
    """Разделяет заголовки и записи, рассчитывает пропуски."""
    matrix = _trim_matrix([list(row) for row in matrix])

    if not matrix:
        return {
            "headers": [],
            "rows": [],
            "row_count": 0,
            "column_count": 0,
            "empty_cells": 0,
            "warnings": ["Лист не содержит данных."],
        }

    # Находим реальную строку с заголовками таблицы
    header_row_index = _find_header_row(matrix)

    # Срезаем всё, что находилось над таблицей (декоративные названия отчётов)
    matrix = matrix[header_row_index:]

    headers = [
        _cell_text(value) or f"Столбец {index + 1}"
        for index, value in enumerate(matrix[0])
    ]

    rows = []
    empty_cells = 0

    for raw_row in matrix[1:]:
        row = list(raw_row[:len(headers)])
        row.extend([None] * (len(headers) - len(row)))

        if all(_is_empty(value) for value in row):
            continue

        empty_cells += sum(_is_empty(value) for value in row)
        rows.append(row)

    warnings = []

    if header_row_index > 0:
        warnings.append(
            f"Пропущено {header_row_index} строк над таблицей для поиска истинной шапки."
        )

    if not rows:
        warnings.append("После строки заголовков записи не обнаружены.")

    if empty_cells:
        warnings.append(
            f"Обнаружено пустых ячеек в строках данных: {empty_cells}."
        )

    return {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(headers),
        "empty_cells": empty_cells,
        "warnings": warnings,
    }