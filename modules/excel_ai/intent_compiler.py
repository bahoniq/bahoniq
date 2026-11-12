
"""Compile conversational Excel requests into a stable semantic intent.

This module never executes a workbook operation. It identifies actions and
matches phrases to real sheet/header names so deterministic routes and Ollama
receive the same, unambiguous interpretation.
"""

from __future__ import annotations

import re
from typing import Any


# ============================================================
# NORMALIZATION
# ============================================================

def _norm(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _stem(word: str) -> str:
    special = {
        "имени": "имя",
        "имя": "имя",
    }

    if word in special:
        return special[word]

    endings = (
        "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими",
        "иях", "ах", "ях", "ов", "ев", "ей", "ом", "ем", "ам",
        "ям", "ую", "юю", "ая", "яя", "ое", "ее", "ые", "ие",
        "ой", "ый", "ий", "ия", "ии", "а", "я", "ы", "и", "у",
        "ю", "е", "о",
    )

    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)]

    return word


def _tokens(value: Any) -> list[str]:
    return re.findall(r"\w+", _norm(value), flags=re.UNICODE)


def _stems(value: Any) -> list[str]:
    return [_stem(word) for word in _tokens(value)]


# ============================================================
# WORKBOOK SCHEMA
# ============================================================

def _sheets(analysis: Any) -> list[dict]:
    if not isinstance(analysis, dict):
        return []

    value = analysis.get("sheets", [])

    if isinstance(value, list):
        return [
            item for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, dict):
        return [
            {
                "name": name,
                **(details if isinstance(details, dict) else {}),
            }
            for name, details in value.items()
        ]

    return []


def _sheet_name(sheet: dict) -> str:
    return str(
        sheet.get("name")
        or sheet.get("sheet_name")
        or ""
    ).strip()


def _headers(sheet: dict) -> list[str]:
    value = sheet.get("headers", [])

    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        if isinstance(item, dict):
            item = item.get("name") or item.get("header")

        if item is not None and str(item).strip():
            result.append(str(item).strip())

    return result


# ============================================================
# HEADER MATCHING
# ============================================================

def _header_mentions(text: str, headers: list[str]) -> list[dict]:
    """
    Finds workbook headers whose meaningful words occur in the request.

    This preserves the existing stem-based matching behavior.
    """

    stems = _stems(text)
    mentions = []

    for header in headers:
        header_stems = _stems(header)

        if not header_stems:
            continue

        positions = []

        for stem in header_stems:
            try:
                positions.append(stems.index(stem))
            except ValueError:
                positions = []
                break

        if positions:
            mentions.append({
                "header": header,
                "position": min(positions),
                "specificity": len(header_stems),
            })

    mentions.sort(
        key=lambda item: (
            item["position"],
            -item["specificity"],
        )
    )

    return mentions


def _explicit_header_candidates(
    text: str,
    headers: list[str],
) -> list[str]:
    """
    Finds explicitly mentioned real headers.

    A multi-word header is accepted only when all its meaningful words
    are present. Results are deduplicated without inventing column names.
    """

    mentions = _header_mentions(text, headers)

    return list(dict.fromkeys(
        item["header"]
        for item in mentions
    ))


# ============================================================
# MISSING-DATA SCOPE DETECTION
# ============================================================

def _has_all_columns_scope(text: str) -> bool:
    """
    Detects an explicit request to inspect the entire worksheet/table.

    This prevents the compiler from requiring one particular column
    when the user clearly requested a full-table check.
    """

    patterns = (
        r"\bвсю\s+таблиц\w*\b",
        r"\bво\s+всей\s+таблиц\w*\b",
        r"\bпо\s+всей\s+таблиц\w*\b",
        r"\bвсе\s+столбц\w*\b",
        r"\bкажд\w*\s+столбц\w*\b",
        r"\bвсех\s+столбц\w*\b",
        r"\bкажд\w*\s+ячейк\w*\b",
        r"\bвсе\s+ячейк\w*\b",
        r"\bкажд\w*\s+пол\w*\b",
        r"\bпо\s+всем\s+столбц\w*\b",
        r"\bпо\s+всем\s+ячейк\w*\b",
        r"\bво\s+всех\s+столбц\w*\b",
        r"\bво\s+всех\s+ячейк\w*\b",
        r"\bвсю\s+рабоч\w*\s+таблиц\w*\b",
        r"\bвесь\s+лист\b",
        r"\bполностью\s+весь\s+лист\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def _has_required_fields_intent(text: str) -> bool:
    """
    Detects requests concerning mandatory/required fields.

    Such requests must not silently become a check of every cell:
    the user may mean only a subset of business-required columns.
    """

    patterns = (
        r"\bобязательн\w*\s+пол\w*\b",
        r"\bобязательн\w*\s+столбц\w*\b",
        r"\bобязательн\w*\s+данн\w*\b",
        r"\bобязательн\w*\s+значени\w*\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ============================================================
# ID HEADER ALIASES — LEGACY COMPATIBILITY ONLY
# ============================================================

_ID_ALIASES = {
    "id",
    "айди",
    "ид",
    "идентификатор",
    "идентификаторы",
}

_ID_CONTEXT_ALIASES = {
    "выпускник",
    "выпускники",
    "выпускников",
    "выпускника",
    "студент",
    "студенты",
    "студентов",
    "номер",
}


def _is_id_header(header: str) -> bool:
    """
    Checks whether a real column header represents an ID field.

    Used only by the legacy split_cell_values_to_rows operation.
    The new universal extraction operation does not select ID columns
    automatically.

    ИИН is deliberately NOT treated as an ID alias.
    """

    words = set(_tokens(header))

    if not words:
        return False

    if words.intersection(_ID_ALIASES):
        return True

    normalized = _norm(header)

    patterns = (
        r"\bid\b",
        r"\bайди\b",
        r"\bид\b",
        r"\bидентификатор\w*\b",
    )

    return any(
        re.search(pattern, normalized)
        for pattern in patterns
    )


def _id_header_candidates(headers: list[str]) -> list[str]:
    result = []

    for header in headers:
        if _is_id_header(header):
            result.append(header)

    return list(dict.fromkeys(result))


# ============================================================
# NEW OPERATION: EXTRACT VALUES TO A NEW SHEET
# ============================================================

def _has_extract_split_values_intent(text: str) -> bool:
    """
    Detects requests to extract multiple values from a column/cell
    and write each value into a separate row on a NEW worksheet.

    This is deliberately stricter than ordinary split-to-sheets intent.
    """

    has_new_sheet = bool(re.search(
        r"\b(?:нов\w*\s+лист\w*|"
        r"отдельн\w*\s+лист\w*|"
        r"друг\w*\s+лист\w*|"
        r"создай\s+лист\w*|"
        r"на\s+отдельн\w*\s+лист\w*)\b",
        text,
    ))

    has_value_context = bool(re.search(
        r"\b(?:значени\w*|элемент\w*|номер\w*|"
        r"содержим\w*|данн\w*|ячейк\w*|"
        r"столбц\w*|колонк\w*)\b",
        text,
    ))

    has_row_context = bool(re.search(
        r"\b(?:отдельн\w*\s+строк\w*|"
        r"кажд\w*\s+строк\w*|"
        r"по\s+одному\s+на\s+строк\w*|"
        r"кажд\w*\s+(?:значени\w*|элемент\w*|номер\w*))\b",
        text,
    ))

    has_cell_split_context = bool(re.search(
        r"\b(?:в\s+одной\s+ячейке|"
        r"из\s+одной\s+ячейки|"
        r"из\s+ячеек|"
        r"в\s+ячейках|"
        r"нескольк\w*\s+значени\w*|"
        r"нескольк\w*\s+элемент\w*|"
        r"значени\w*\s+через\s+запят\w*|"
        r"разделител\w*)\b",
        text,
    ))

    has_extract_verb = bool(re.search(
        r"\b(?:извлек\w*|вытащ\w*|выгруз\w*|"
        r"вынес\w*|выдел\w*|собер\w*|"
        r"раздели\w*|разбей\w*|разверни\w*|"
        r"распредели\w*|перенес\w*)\b",
        text,
    ))

    return (
        has_new_sheet
        and has_value_context
        and has_row_context
        and (has_extract_verb or has_cell_split_context)
    )


def _resolve_extract_target(
    text: str,
    schema: list[dict],
) -> tuple[dict, dict]:
    """
    Resolves the target column and worksheet for universal extraction.

    No automatic ID-column fallback.
    No automatic first-column fallback.
    """

    candidates = []

    for sheet in schema:
        sheet_name = sheet["sheet"]

        for header in sheet["headers"]:
            header_stems = _stems(header)

            if not header_stems:
                continue

            request_stems = _stems(text)

            if all(stem in request_stems for stem in header_stems):
                candidates.append({
                    "sheet": sheet_name,
                    "column": header,
                    "specificity": len(header_stems),
                })

    unique_candidates = []
    seen = set()

    for item in candidates:
        key = (item["sheet"], item["column"])

        if key not in seen:
            seen.add(key)
            unique_candidates.append(item)

    if len(unique_candidates) == 1:
        item = unique_candidates[0]

        return {
            "column": item["column"],
            "sheet": item["sheet"],
            "output_sheet": "Результат",
            "split_delimiters": [",", ";", "\n", "\r"],
        }, {}

    if len(unique_candidates) > 1:
        return {}, {
            "type": "multiple_extract_targets",
            "extract_candidates": unique_candidates,
        }

    available_headers = []

    for sheet in schema:
        for header in sheet["headers"]:
            available_headers.append({
                "sheet": sheet["sheet"],
                "column": header,
            })

    return {}, {
        "type": "extract_target_not_found",
        "extract_candidates": [],
        "available_headers": available_headers,
    }


# ============================================================
# LEGACY CELL-TO-ROWS INTENT DETECTION
# ============================================================

def _has_split_cell_intent(text: str) -> bool:
    """
    Detects the legacy operation that expands cell values into rows
    while preserving the rest of the source records.

    New-sheet extraction is detected separately and takes precedence.
    """

    patterns = (
        r"\b(?:несколько|нескольких)\s+"
        r"(?:id|айди|ид|идентификатор\w*)\b",

        r"\b(?:кажд\w*\s+)?"
        r"(?:id|айди|ид|идентификатор\w*)"
        r".{0,50}\bотдельн\w*\s+строк\w*",

        r"\b(?:разверни|развернуть|разворачивай|"
        r"раздели|разделить|разбей|разбить|"
        r"распредели|распределить)\b"
        r".{0,70}\b(?:id|айди|ид|идентификатор\w*)\b",

        r"\bкажд\w*\s+"
        r"(?:значени\w*|номер\w*|элемент\w*|запис\w*)"
        r".{0,60}\bотдельн\w*\s+строк\w*",

        r"\b(?:все\s+)?"
        r"(?:значени\w*|номер\w*|элемент\w*)"
        r".{0,60}\b(?:на|в)\s+отдельн\w*\s+строк\w*",

        r"\b(?:раздели|разделить|разбей|разбить|"
        r"разверни|развернуть|распредели|распределить)\b"
        r".{0,80}\b(?:значени\w*|содержим\w*|данн\w*)"
        r".{0,60}\b(?:ячейк\w*|строк\w*)",

        r"\bиз\s+одн\w*\s+ячейк\w*"
        r".{0,80}\b(?:отдельн\w*\s+строк\w*|"
        r"нескольк\w*\s+строк\w*)",

        r"\b(?:значени\w*|id|айди|ид)"
        r".{0,50}\b(?:в\s+одной\s+ячейке|"
        r"из\s+одной\s+ячейки)\b",

        r"\bраздели\s+(?:их|значения|id|айди|ид)\b",

        r"\bв\s+отдельную\s+строку\b",

        r"\bна\s+отдельную\s+строку\b",

        r"\bкаждый\s+id\s+в\s+отдельн\w*\s+строк\w*",

        r"\bкаждый\s+айди\s+в\s+отдельн\w*\s+строк\w*",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ============================================================
# MAIN COMPILER
# ============================================================

def compile_intent(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict:

    raw = str(task or "").strip()
    normalized = _norm(raw)

    sheets = _sheets(analysis)

    # --------------------------------------------------------
    # Respect explicitly selected worksheet.
    # --------------------------------------------------------

    if selected_sheet:
        selected = str(selected_sheet).strip()

        sheets = [
            sheet for sheet in sheets
            if _sheet_name(sheet) == selected
        ]

    # --------------------------------------------------------
    # Build workbook schema.
    # --------------------------------------------------------

    schema = []
    all_headers = []

    for sheet in sheets:
        name = _sheet_name(sheet)
        headers = _headers(sheet)

        schema.append({
            "sheet": name,
            "headers": headers,
        })

        all_headers.extend(headers)

    all_headers = list(dict.fromkeys(all_headers))

    # --------------------------------------------------------
    # Detect operations.
    # --------------------------------------------------------

    extract_values = _has_extract_split_values_intent(normalized)

    legacy_split_cell = (
        _has_split_cell_intent(normalized)
        and not extract_values
    )

    split = bool(re.search(
        r"\b(?:раздел\w*|разбей\w*|раскид\w*|распредел\w*)\b"
        r"|\b(?:отдельн\w*|разн\w*)\s+"
        r"лист(?:ы|ах|ам|ами|ов)\b",
        normalized,
    )) and not extract_values and not legacy_split_cell

    sort = bool(re.search(
        r"\b(?:сортир\w*|отсортир\w*|располож\w*|упорядоч\w*)\b",
        normalized,
    ))

    shorthand_sort = split and bool(
        re.search(r"\b(?:там|внутри)\b.*\bпо\b", normalized)
    )

    count = bool(re.search(
        r"\b(?:посчитай|подсчитай|количеств\w*|сколько)\b",
        normalized,
    ))

    smart_summary = bool(re.search(
        r"\b(?:общ\w*\s+(?:сводк\w*|сводн\w*\s+таблиц\w*)|"
        r"сводк\w*|сводн\w*\s+таблиц\w*|отчет\w*|отчёт\w*|"
        r"дашборд\w*|dashboard|"
        r"проанализир\w*\s+(?:файл\w*|данн\w*|таблиц\w*)|"
        r"анализ\w*\s+(?:файл\w*|данн\w*|таблиц\w*))\b",
        normalized,
    ))

    trim = bool(re.search(
        r"\b(?:убер\w*|удал\w*|очист\w*)\b.*\bпробел\w*",
        normalized,
    ))

    missing = bool(re.search(
        r"\b(?:без|пуст\w*|отсутств\w*|не\s+заполн\w*|"
        r"незаполн\w*|пропущенн\w*)\b",
        normalized,
    )) and not extract_values and not legacy_split_cell

    all_columns_scope = (
        missing and _has_all_columns_scope(normalized)
    )

    required_fields_scope = (
        missing and _has_required_fields_intent(normalized)
    )

    # --------------------------------------------------------
    # Register actions.
    # --------------------------------------------------------

    actions = []

    for name, enabled in (
        ("extract_split_values_to_sheet", extract_values),
        ("split_cell_values_to_rows", legacy_split_cell),
        ("trim_text", trim),
        ("find_missing", missing),
        ("split_to_sheets", split),
        ("smart_summary", smart_summary),
        ("group_count", count),
        ("sort_rows", sort or shorthand_sort),
    ):
        if enabled:
            actions.append(name)

    # --------------------------------------------------------
    # Find explicitly mentioned headers.
    # --------------------------------------------------------

    mentions = _header_mentions(
        normalized,
        all_headers,
    )

    mentioned_headers = [
        item["header"]
        for item in mentions
    ]

    # --------------------------------------------------------
    # Resolve operation.
    # --------------------------------------------------------

    resolved = {}
    ambiguity = {}
    canonical = raw

    # --------------------------------------------------------
    # New-sheet extraction.
    # --------------------------------------------------------

    if extract_values:

        resolved, ambiguity = _resolve_extract_target(
            normalized,
            schema,
        )

        if resolved:
            canonical = (
                f"Извлечь значения из столбца "
                f"«{resolved['column']}» на листе "
                f"«{resolved['sheet']}». "
                "Разделить значения по запятым, точкам с запятой "
                "и переносам строк. Разместить каждое значение "
                "на отдельной строке нового листа "
                "«Результат». Исходный лист не изменять."
            )

        elif ambiguity.get("type") == "multiple_extract_targets":

            canonical = (
                "Найдено несколько подходящих столбцов. "
                "Необходимо уточнить лист и столбец "
                "для извлечения значений."
            )

        else:
            canonical = (
                "Не удалось определить исходный столбец. "
                "Необходимо уточнить точное название столбца. "
                "Автоматически выбирать первый столбец или ID "
                "запрещено."
            )

    # --------------------------------------------------------
    # Legacy split-cell operation.
    # --------------------------------------------------------

    elif legacy_split_cell:

        explicit_candidates = list(dict.fromkeys(
            mentioned_headers
        ))

        if len(explicit_candidates) == 1:

            target_header = explicit_candidates[0]

            resolved = {
                "split_cell_column": target_header,
            }

            canonical = (
                f"Развернуть значения из столбца "
                f"«{target_header}» в отдельные строки, "
                "сохранив остальные данные исходных строк."
            )

        elif len(explicit_candidates) > 1:

            ambiguity = {
                "type": "multiple_explicit_headers",
                "split_cell_candidates": explicit_candidates,
            }

            canonical = (
                "Найдено несколько упомянутых столбцов. "
                "Необходимо уточнить, из какого столбца "
                "разворачивать значения."
            )

        else:

            id_candidates = _id_header_candidates(all_headers)

            if len(id_candidates) == 1:

                target_header = id_candidates[0]

                resolved = {
                    "split_cell_column": target_header,
                }

                canonical = (
                    f"Развернуть значения из столбца "
                    f"«{target_header}» в отдельные строки, "
                    "сохранив остальные данные исходных строк."
                )

            elif len(id_candidates) > 1:

                ambiguity = {
                    "type": "multiple_id_headers",
                    "split_cell_candidates": id_candidates,
                }

                canonical = (
                    "Найдено несколько столбцов с идентификаторами. "
                    "Необходимо уточнить целевой столбец."
                )

            else:

                ambiguity = {
                    "type": "header_not_found",
                    "split_cell_candidates": [],
                    "available_headers": all_headers,
                }

                canonical = (
                    "Нужно уточнить, из какого столбца разворачивать "
                    "значения. Автоматически выбирать первый столбец "
                    "запрещено."
                )

        if resolved and len(schema) == 1:
            resolved["split_cell_sheet"] = schema[0]["sheet"]

    # --------------------------------------------------------
    # Missing values: entire worksheet / all columns.
    # --------------------------------------------------------

    elif missing and all_columns_scope:

        resolved = {
            "scope": "all_columns",
            "all_columns": True,
            "columns": [],
            "column": None,
            "sheet": (
                schema[0]["sheet"]
                if len(schema) == 1
                else None
            ),
            "check_blank_cells": True,
            "check_whitespace_only": True,
            "output_sheet": "Отчёт проверки",
        }

        canonical = (
            "Проверить все столбцы текущего листа на отсутствие данных. "
            "Проверить физически пустые ячейки, ячейки, содержащие "
            "только пробелы, и формулы, возвращающие пустую строку. "
            "Для каждой найденной проблемы указать номер исходной "
            "строки, название столбца, исходное значение и тип проблемы. "
            "Создать лист «Отчёт проверки». Исходный лист не изменять. "
            "Не ограничивать проверку одним столбцом."
        )

    # --------------------------------------------------------
    # Missing values: explicitly required fields.
    # --------------------------------------------------------

    elif missing and required_fields_scope and not mentioned_headers:

        ambiguity = {
            "type": "required_fields_not_specified",
            "available_headers": all_headers,
        }

        canonical = (
            "Необходимо уточнить, какие именно столбцы являются "
            "обязательными. Не считать все столбцы обязательными "
            "автоматически."
        )

    # --------------------------------------------------------
    # Missing values: one or more explicitly named columns.
    # --------------------------------------------------------

    elif missing and mentioned_headers:

        unique_missing_headers = list(dict.fromkeys(
            mentioned_headers
        ))

        if len(unique_missing_headers) == 1:

            resolved = {
                "scope": "selected_columns",
                "all_columns": False,
                "columns": unique_missing_headers,
                "column": unique_missing_headers[0],
                "sheet": (
                    schema[0]["sheet"]
                    if len(schema) == 1
                    else None
                ),
                "check_blank_cells": True,
                "check_whitespace_only": True,
                "output_sheet": "Отчёт проверки",
            }

            canonical = (
                f"Проверить столбец «{unique_missing_headers[0]}» "
                "на отсутствие данных, ячейки с пробелами и формулы, "
                "возвращающие пустую строку. Создать лист "
                "«Отчёт проверки» с номерами исходных строк "
                "и типами проблем. Исходный лист не изменять."
            )

        else:

            resolved = {
                "scope": "selected_columns",
                "all_columns": False,
                "columns": unique_missing_headers,
                "column": None,
                "sheet": (
                    schema[0]["sheet"]
                    if len(schema) == 1
                    else None
                ),
                "check_blank_cells": True,
                "check_whitespace_only": True,
                "output_sheet": "Отчёт проверки",
            }

            canonical = (
                "Проверить следующие столбцы на отсутствие данных: "
                + ", ".join(
                    f"«{header}»"
                    for header in unique_missing_headers
                )
                + ". Найти пустые ячейки, ячейки с пробелами "
                "и формулы, возвращающие пустую строку. "
                "Создать лист «Отчёт проверки». "
                "Исходный лист не изменять."
            )

    # --------------------------------------------------------
    # Missing values: no scope or target identified.
    # --------------------------------------------------------

    elif missing:

        ambiguity = {
            "type": "missing_scope_not_specified",
            "available_headers": all_headers,
        }

        canonical = (
            "Необходимо уточнить, проверять ли всю таблицу "
            "или конкретные столбцы. Если пользователь имеет "
            "в виду всю таблицу, использовать режим all_columns."
        )

    # --------------------------------------------------------
    # Split then sort.
    # --------------------------------------------------------

    elif split and (sort or shorthand_sort) and len(mentioned_headers) >= 2:

        split_column = mentioned_headers[0]
        sort_column = mentioned_headers[-1]

        resolved = {
            "split_by": split_column,
            "sort_each_sheet_by": sort_column,
            "sort_direction": (
                "descending" if bool(re.search(
                    r"\b(?:по убыванию|от я до а|от z до a)\b",
                    normalized,
                )) else "ascending"
            ),
        }

        canonical = (
            f"Разделить данные по столбцу «{split_column}» "
            "на отдельные листы. "
            f"Внутри каждого листа отсортировать строки по столбцу "
            f"«{sort_column}» "
            + (
                "по убыванию."
                if resolved["sort_direction"] == "descending"
                else "по возрастанию."
            )
        )

    # --------------------------------------------------------
    # Ordinary split-to-sheets.
    # --------------------------------------------------------

    elif split and mentioned_headers:

        resolved = {
            "split_by": mentioned_headers[0],
        }

        canonical = (
            f"Разделить данные по столбцу "
            f"«{mentioned_headers[0]}» на отдельные листы."
        )

    # --------------------------------------------------------
    # Smart summary.
    # --------------------------------------------------------

    elif smart_summary:

        resolved = {
            "summary_columns": mentioned_headers,
            "include_charts": True,
            "include_cross_tables": True,
        }

        if mentioned_headers:

            canonical = (
                "Создать общую сводку по столбцам "
                + ", ".join(
                    f"«{header}»"
                    for header in mentioned_headers
                )
                + ". Рассчитать количество, долю и рейтинг категорий. "
                "Добавить диаграммы и перекрёстные таблицы."
            )

        else:

            canonical = (
                "Автоматически выбрать информативные категориальные "
                "столбцы. Создать общую сводку с количеством, долей "
                "и рейтингом категорий, диаграммами "
                "и перекрёстными таблицами."
            )

    # --------------------------------------------------------
    # Group count.
    # --------------------------------------------------------

    elif count and mentioned_headers:

        resolved = {
            "group_by": mentioned_headers[-1],
            "aggregate": "count",
        }

        canonical = (
            f"Подсчитать количество записей по столбцу "
            f"«{mentioned_headers[-1]}» "
            "и создать отдельный лист со сводкой."
        )

    # --------------------------------------------------------
    # Sorting direction.
    # --------------------------------------------------------

    descending = bool(re.search(
        r"\b(?:по убыванию|от я до а|от z до a)\b",
        normalized,
    ))

    # Conversational ID extraction: "выведи каждый айди ... на новые строки".
    # Treat generic student ID as an ID-like header, but never silently use ИИН.
    if not actions and re.search(
        r"\b(?:вывед|вывест|извлек|перенес|разверн|раздел)\w*.*(?:айди|\bid\b).*"
        r"(?:нов\w*\s+строк|по\s+строк|вертикальн)",
        normalized,
    ):
        candidates = []
        for item in schema:
            for header in item.get("headers", []):
                key = _norm(header)
                if key != "иин" and re.search(r"(?:\bid\b|айди|идентификатор)", key):
                    candidates.append((item.get("sheet"), header))
        if len(candidates) == 1:
            actions.append("extract_split_values_to_sheet")
            resolved = {
                "sheet": candidates[0][0],
                "column": candidates[0][1],
                "output_sheet": candidates[0][1],
            }
            canonical = (
                f"Извлечь значения из столбца «{candidates[0][1]}» "
                "в отдельные строки одного нового листа."
            )

    # --------------------------------------------------------
    # Final semantic intent.
    # --------------------------------------------------------

    return {
        "raw_instruction": raw,

        "canonical_instruction": canonical,

        "actions": actions,

        "resolved": resolved,

        "mentioned_headers": mentioned_headers,

        "ambiguity": ambiguity,

        "workbook_schema": schema,

        "constraints": {
            "preserve_source": True,
            "delete_rows": bool(re.search(
                r"\bудал\w*\s+строк\w*",
                normalized,
            )),
            "sort_direction": (
                "descending" if descending else "ascending"
            ),
        },

        "needs_ai": not bool(actions),
    }
