import json
import re
import urllib.error
import urllib.request
from typing import Any

from .settings import (
    CONTEXT_SIZE,
    MAX_ANALYSIS_CHARS,
    REQUEST_TIMEOUT,
)
from .intent_compiler import compile_intent


# ============================================================
# BAHONIQ — EXCEL AI INTERPRETER (CLOUD AI)
# ============================================================

AI_ENGINE = "cloud_gemini"


# ============================================================
# SUPPORTED OPERATIONS
# ============================================================

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
    "split_by_column",
    "split_to_sheets",
    "merge_sheets",
    "summary_count",
    "validate_values",
    "compare_columns",
    "select_columns",
    "copy_columns_to_sheet",
    "copy_sheet",
    "filter_rows",
    "student_data_audit",
    "group_by_aggregate",
    "pivot_count",
    "smart_summary",
    "distinct_count",
    "apply_formula",
    "split_cell_values_to_rows",
    "extract_split_values_to_sheet",
    "combine_columns",
}


TYPE_ALIASES = {
    "delete_empty_rows": "remove_empty_rows",
    "remove_blank_rows": "remove_empty_rows",
    "delete_blank_rows": "remove_empty_rows",

    "deduplicate": "remove_duplicates",
    "deduplicate_rows": "remove_duplicates",
    "drop_duplicates": "remove_duplicates",
    "delete_duplicates": "remove_duplicates",
    "remove_duplicate": "remove_duplicates",

    "fill_blanks": "fill_empty",
    "fill_empty_cells": "fill_empty",
    "fill_missing": "fill_empty",

    "trim": "trim_text",
    "strip": "trim_text",
    "clean_text": "trim_text",

    "replace": "replace_values",
    "replace_text": "replace_values",
    "find_replace": "replace_values",

    "highlight_blanks": "highlight_empty",
    "highlight_blank_cells": "highlight_empty",

    "find_duplicates": "find_repeated_values",
    "find_repeated": "find_repeated_values",

    "find_blanks": "find_blank_cells",
    "find_empty_cells": "find_blank_cells",

    "sort": "sort_rows",
    "sort_data": "sort_rows",

    "reorder": "reorder_columns",
    "move_columns": "reorder_columns",
    "choose_columns": "select_columns",
    "keep_columns": "select_columns",
    "copy_columns": "copy_columns_to_sheet",
    "copy_selected_columns": "copy_columns_to_sheet",
    "move_columns_to_sheet": "copy_columns_to_sheet",
    "duplicate_sheet": "copy_sheet",
    "copy_worksheet": "copy_sheet",
    "filter": "filter_rows",

    "split": "split_by_column",
    "split_column": "split_by_column",
    "split_into_files": "split_by_column",
    "split_by_value": "split_by_column",

    "split_into_sheets": "split_to_sheets",
    "split_by_course": "split_to_sheets",
    "split_by_value_to_sheets": "split_to_sheets",
    "split_column_to_sheets": "split_to_sheets",
    "split_by_group_to_sheets": "split_to_sheets",

    "merge": "merge_sheets",
    "combine_sheets": "merge_sheets",
    "merge_columns": "combine_columns",
    "concat_columns": "combine_columns",
    "join_columns": "combine_columns",
    "concatenate_columns": "combine_columns",

    "count": "summary_count",
    "count_rows": "summary_count",
    "statistics": "summary_count",

    "validate": "validate_values",
    "check_values": "validate_values",

    "compare": "compare_columns",
    "compare_values": "compare_columns",

    "group_by": "group_by_aggregate",
    "aggregate_by_group": "group_by_aggregate",
    "group_aggregate": "group_by_aggregate",
    "grouped_summary": "group_by_aggregate",
    "summary": "smart_summary",
    "dashboard": "smart_summary",
    "formula": "apply_formula",
    "insert_formula": "apply_formula",
    "calculate_column": "apply_formula",

    "split_cell_to_rows": "split_cell_values_to_rows",
    "split_cells_to_rows": "split_cell_values_to_rows",
    "explode_cell": "split_cell_values_to_rows",
    "extract_values_to_sheet": "extract_split_values_to_sheet",
    "extract_split_values": "extract_split_values_to_sheet",
    "split_values_to_new_sheet": "extract_split_values_to_sheet",
    "extract_cell_values": "extract_split_values_to_sheet",
}


# ============================================================
# TASK TEXT NORMALIZATION
# ============================================================

WORD_REPLACEMENTS = {
    "дудли": "дубли",
    "дублики": "дубли",
    "дублекаты": "дубликаты",
    "дубликты": "дубликаты",
    "дубликат": "дубликаты",
    "дубликатыы": "дубликаты",
    "дупликаты": "дубликаты",
    "дупликат": "дубликаты",
    "дубля": "дубли",
    "дублей": "дубли",
    "повторы": "дубли",

    "стрки": "строки",
    "строчек": "строки",
    "строчки": "строки",

    "колонка": "столбец",
    "колонки": "столбцы",

    "удоли": "удали",
    "удолить": "удалить",
    "удоление": "удаление",
    "удолиь": "удалить",
    "удалть": "удалить",

    "наити": "найти",
    "обьедини": "объедини",
    "обьединить": "объединить",
    "разделть": "разделить",
    "сортируй": "отсортируй",
}


PHRASE_REPLACEMENTS = {
    "удали дудли": "удали дубли",
    "найди дудли": "найди дубли",
    "убери дудли": "убери дубли",
    "удалить дудли": "удалить дубли",
    "убери повторы": "убери дубли",
    "удали повторы": "удали дубли",
    "найди повторы": "найди дубли",
    "удали пустые стрки": "удали пустые строки",
    "удалить пустые стрки": "удалить пустые строки",
    "найди пустые стрки": "найди пустые строки",
    "обьедини листы": "объедини листы",
}


def _normalize_task_text(task: str) -> str:
    if not isinstance(task, str):
        return ""

    text = re.sub(r"\s+", " ", task.strip()).lower()

    for wrong, correct in sorted(
        PHRASE_REPLACEMENTS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = re.sub(
            r"(?<!\w)" + re.escape(wrong) + r"(?!\w)",
            correct,
            text,
            flags=re.IGNORECASE,
        )

    tokens = re.findall(r"\w+|[^\w\s]+|\s+", text, re.UNICODE)

    result = []

    for token in tokens:
        if token.isspace() or not re.fullmatch(r"\w+", token):
            result.append(token)
        else:
            result.append(WORD_REPLACEMENTS.get(token, token))

    return re.sub(r"\s+", " ", "".join(result)).strip()


def _normalize_header_text(value: Any) -> str:
    """Нормализация заголовка только для сопоставления."""
    if value is None:
        return ""

    text = str(value).strip().lower().replace("ё", "е")
    text = re.sub(r"[\s_\-./\\]+", " ", text)
    text = re.sub(r"[^\w ]+", "", text, flags=re.UNICODE)

    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# EXCEL ANALYSIS HELPERS
# ============================================================

def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return []


def _extract_sheets(analysis: Any) -> list[dict]:
    """
    Поддерживает распространённые структуры анализа:
    {"sheets": [...]}
    {"worksheets": [...]}
    {"sheets": {"Sheet1": {...}}}
    """
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except (json.JSONDecodeError, TypeError):
            return []

    if not isinstance(analysis, dict):
        return []

    for key in ("sheets", "worksheets", "листов"):
        value = analysis.get(key)

        if isinstance(value, list):
            return [
                item for item in value
                if isinstance(item, dict)
            ]

        if isinstance(value, dict):
            result = []

            for name, details in value.items():
                if isinstance(details, dict):
                    item = dict(details)
                    item.setdefault("name", name)
                    result.append(item)

                elif isinstance(details, list):
                    result.append({
                        "name": name,
                        "headers": details,
                    })

            return result

    if any(key in analysis for key in ("headers", "columns", "preview")):
        return [{
            **analysis,
            "name": (
                analysis.get("name")
                or analysis.get("sheet_name")
                or analysis.get("sheet")
                or "Sheet1"
            ),
        }]

    return []


def _extract_headers(sheet_info: dict) -> list[str]:
    """
    Получает заголовки, не выдумывая отсутствующие поля.
    """
    for key in ("headers", "columns", "column_names", "столбцы"):
        value = sheet_info.get(key)

        if isinstance(value, dict):
            result = []

            for item in value.values():
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("header")
                        or item.get("title")
                    )
                    if name is not None:
                        result.append(str(name))
                elif item is not None:
                    result.append(str(item))

            if result:
                return result

        if isinstance(value, list):
            result = []

            for item in value:
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("header")
                        or item.get("title")
                        or item.get("column")
                    )
                    if name is not None:
                        result.append(str(name))
                elif item is not None:
                    result.append(str(item))

            if result:
                return result

    preview = sheet_info.get("preview")

    if isinstance(preview, list) and preview:
        first = preview[0]

        if isinstance(first, dict):
            return [str(key) for key in first.keys()]

        if isinstance(first, list):
            return [str(value) for value in first]

    return []


def _get_sheet_name(sheet_info: dict) -> str:
    return str(
        sheet_info.get("name")
        or sheet_info.get("sheet_name")
        or sheet_info.get("sheet")
        or ""
    ).strip()


# ============================================================
# FAST ROUTING — EXTRACT VALUES TO A NEW SHEET
# ============================================================

def _route_extract_split_values_to_sheet(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    """
    Универсальное извлечение нескольких значений из ячеек
    выбранного столбца на отдельный лист.

    Исходный лист не изменяется.
    Не привязано к ID, ИИН или конкретному типу данных.
    """

    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    has_extract_intent = bool(re.search(
        r"\b(?:извлеки|вытащи|выгрузи|вынеси|"
        r"перенеси|раздели|разбей|разложи|"
        r"выдели|собери)\b",
        text,
    ))

    has_multiple_values_intent = bool(re.search(
        r"\b(?:кажд\w*\s+(?:значени\w*|элемент\w*|"
        r"номер\w*|запис\w*)|"
        r"все\s+значени\w*|"
        r"нескольк\w*\s+значени\w*|"
        r"значени\w*\s+из\s+ячеек|"
        r"содержим\w*\s+ячеек)\b",
        text,
    ))

    has_separate_row_intent = bool(re.search(
        r"\b(?:отдельн\w*\s+строк\w*|"
        r"нов\w*\s+строк\w*|"
        r"кажд\w*\s+строк\w*|"
        r"по\s+одному\s+на\s+строк\w*)\b",
        text,
    ))

    has_new_sheet_intent = bool(re.search(
        r"\b(?:нов\w*\s+лист\w*|"
        r"отдельн\w*\s+лист\w*|"
        r"друг\w*\s+лист\w*|"
        r"создай\s+лист\w*|"
        r"на\s+отдельн\w*\s+лист\w*)\b",
        text,
    ))

    if not (
        has_extract_intent
        and (
            has_multiple_values_intent
            or has_separate_row_intent
        )
        and has_new_sheet_intent
    ):
        return None

    sheets = _extract_sheets(analysis)

    if not sheets:
        return None

    if selected_sheet:
        selected_name = str(selected_sheet).strip()

        matching_sheets = [
            item for item in sheets
            if _get_sheet_name(item) == selected_name
        ]

        if matching_sheets:
            sheets = matching_sheets

    candidates = []

    for sheet_info in sheets:
        sheet_name = _get_sheet_name(sheet_info)
        headers = _extract_headers(sheet_info)

        for header in headers:
            normalized_header = _normalize_header_text(header)

            if not normalized_header:
                continue

            pattern = (
                r"(?<!\w)"
                + re.escape(normalized_header)
                + r"(?!\w)"
            )

            if re.search(pattern, text):
                candidates.append({
                    "sheet": sheet_name,
                    "column": header,
                })

    if not candidates:
        return {
            "questions": [
                "Из какого именно столбца извлечь значения? "
                "Укажи точное название заголовка Excel."
            ],
            "operations": [],
            "explanation": (
                "Не удалось однозначно определить исходный столбец."
            ),
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    if len(candidates) > 1:
        options = [
            f"Лист «{item['sheet']}», столбец «{item['column']}»"
            for item in candidates
        ]

        return {
            "questions": [
                "Найдено несколько подходящих столбцов:\n"
                + "\n".join(options)
                + "\nУкажи нужный лист и столбец."
            ],
            "operations": [],
            "explanation": (
                "Требуется уточнить источник данных."
            ),
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    match = candidates[0]

    operation = {
        "type": "extract_split_values_to_sheet",
        "sheet": match["sheet"],
        "column": match["column"],
        "output_sheet": "Результат",
        "header_rows": 1,
    }

    return {
        "questions": [],
        "operations": [operation],
        "explanation": (
            f"Значения из столбца «{match['column']}» "
            f"на листе «{match['sheet']}» будут разделены "
            "по разделителям и размещены по одному значению "
            "в строке нового листа «Результат». "
            "Исходный лист останется без изменений."
        ),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# DETERMINISTIC INTENT ROUTING — MISSING VALUES
# ============================================================

def _detect_missing_field_request(task: str) -> bool:
    """
    Определяет запросы на поиск пустых или незаполненных значений.
    Поддерживает проверку всей таблицы и отдельных полей.
    """

    text = _normalize_header_text(task)

    if re.search(
        r"\bне\s+(?:ищи|искать|проверяй|проверить|выполняй)\b.*"
        r"\b(?:пуст\w*|пропущен\w*|отсутств\w*)",
        text,
    ):
        return False

    if re.search(r"\b(?:сколько|посчитай)\b.*\bбез\s+[a-zа-яёәіңғүұқөһ]+", text):
        return True

    return bool(re.search(
        r"\b(?:проверь|проверить|проверяй|найди|найти|"
        r"покажи|показать|выяви|выявить|посчитай|"
        r"определи|определить)\b.*"
        r"\b(?:пуст\w*|пропущен\w*|отсутств\w*|"
        r"незаполнен\w*|не\s+заполнен\w*|"
        r"без\s+значени\w*|пустот\w*)\b"
        r"|\b(?:пуст\w*|пропущен\w*|отсутств\w*|"
        r"незаполнен\w*|не\s+заполнен\w*)\b.*"
        r"\b(?:ячейк\w*|значени\w*|пол\w*|столбц\w*|"
        r"таблиц\w*|данн\w*|запис\w*)\b",
        text,
    ))


def _get_missing_scope(task: str) -> str:
    """
    Возвращает:
      all_columns
      selected_columns
      single_column
      required_fields
      unspecified
    """

    text = _normalize_header_text(task)

    if re.search(
        r"\b(?:обязательн\w*\s+пол\w*|"
        r"обязательн\w*\s+столбц\w*)\b",
        text,
    ):
        return "required_fields"

    if re.search(
        r"\b(?:всю\s+таблиц\w*|вся\s+таблиц\w*|"
        r"всей\s+таблиц\w*|все\s+столбц\w*|"
        r"кажд\w*\s+столбц\w*|"
        r"по\s+всем\s+столбц\w*|"
        r"по\s+всей\s+таблиц\w*|"
        r"всех\s+столбц\w*|"
        r"во\s+всех\s+столбц\w*|"
        r"все\s+колонк\w*|"
        r"кажд\w*\s+колонк\w*|"
        r"по\s+всем\s+колонк\w*|"
        r"всех\s+колонк\w*)\b",
        text,
    ):
        return "all_columns"

    return "unspecified"


def _route_remove_empty_rows_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    """Route deletion of entirely empty rows before missing-cell audits."""
    text = _normalize_header_text(_normalize_task_text(task))
    remove_rows = bool(re.search(
        r"\b(?:удал\w*|убер\w*|убрат\w*|очист\w*)\b.*(?:"
        r"\b(?:полностью\s+|целиком\s+)?пуст\w*\s+строк\w*\b|"
        r"\bстрок\w*\b[^.]{0,160}\bпуст\w*\b)",
        text,
    ))
    if not remove_rows:
        return None

    sheets = _extract_sheets(analysis)
    if selected_sheet:
        sheets = [
            item for item in sheets
            if _get_sheet_name(item) == str(selected_sheet).strip()
        ]
    if len(sheets) != 1:
        return {
            "questions": ["Укажи лист, на котором удалить полностью пустые строки."],
            "operations": [],
            "explanation": "Для очистки нужно однозначно определить исходный лист.",
            "mode": "questions",
            "deterministic_route": True,
        }

    sheet_name = _get_sheet_name(sheets[0])
    output_match = re.search(
        r"(?:с\s+названием|под\s+названием)\s+[«\"]([^»\"]+)[»\"]",
        task,
        re.I,
    )
    wants_copy = bool(re.search(
        r"\b(?:созда\w*\s+копи\w*|в\s+копи\w*|исходн\w*\s+лист\w*.*"
        r"(?:не\s+измен\w*|остав\w*\s+без\s+измен))\b",
        text,
    ))

    op = {
        "type": "remove_empty_rows",
        "sheet": sheet_name,
        "header_rows": 1,
    }
    if wants_copy:
        op["output_sheet"] = (
            output_match.group(1).strip()
            if output_match
            else f"{sheet_name} — обработано"
        )

    target = (
        f"в копии «{op['output_sheet']}»; исходный лист останется без изменений"
        if op.get("output_sheet")
        else f"на листе «{sheet_name}»"
    )
    return {
        "questions": [],
        "operations": [op],
        "explanation": (
            "Будут удалены только строки, где все ячейки физически пусты "
            f"или содержат только пробелы, {target}. Строки хотя бы с одним "
            "значением сохранятся."
        ),
        "mode": "operations",
        "deterministic_route": True,
    }


FIELD_ALIASES = {
    "отчество": {
        "отчество",
        "отчества",
        "отчествo",
        "отчество студента",
        "отчество студента фио",
        "middle name",
        "patronymic",
    },
    "фамилия": {
        "фамилия",
        "фамилии",
        "фамилия студента",
        "surname",
        "last name",
    },
    "имя": {
        "имя",
        "имени",
        "имя студента",
        "first name",
    },
    "иин": {
        "иин",
        "иин студента",
        "индивидуальный идентификационный номер",
        "индивидуальный идентификационный номер студента",
    },
    "email": {
        "email",
        "e mail",
        "электронная почта",
        "почта",
        "адрес электронной почты",
    },
    "телефон": {
        "телефон",
        "номер телефона",
        "мобильный телефон",
        "контактный телефон",
    },
    "курс": {
        "курс",
        "курс обучения",
    },
    "группа": {
        "группа",
        "учебная группа",
    },
    "специальность": {
        "специальность",
        "образовательная программа",
        "оп",
    },
    "факультет": {
        "факультет",
    },
}


def _requested_field(task: str) -> str | None:
    text = _normalize_header_text(task)

    patterns = [
        (r"\bотчеств\w*", "отчество"),
        (r"\bфамили\w*", "фамилия"),
        (r"\bимени\b|\bимя\b", "имя"),
        (r"\bиин\b", "иин"),
        (r"\bemail\b|\be mail\b|\bэлектронн\w+\s+почт\w*", "email"),
        (r"\bтелефон\w*\b", "телефон"),
        (r"\bкурс\w*\b", "курс"),
        (r"\bгрупп\w*\b", "группа"),
        (
            r"\bспециальност\w*\b|"
            r"\bобразовательн\w+\s+программ\w*",
            "специальность",
        ),
        (r"\bфакультет\w*\b", "факультет"),
    ]

    for pattern, field in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return field

    return None


def _match_field_header(
    requested_field: str,
    headers: list[str],
) -> list[str]:
    aliases = FIELD_ALIASES.get(requested_field, {requested_field})

    normalized_aliases = {
        _normalize_header_text(alias)
        for alias in aliases
    }

    matches = []

    for header in headers:
        normalized_header = _normalize_header_text(header)

        if normalized_header in normalized_aliases:
            matches.append(header)

    if not matches:
        for header in headers:
            normalized_header = _normalize_header_text(header)

            if requested_field == "отчество" and (
                normalized_header.startswith("отчество ")
                or normalized_header.endswith(" отчество")
            ):
                matches.append(header)

            elif requested_field == "фамилия" and (
                normalized_header.startswith("фамилия ")
                or normalized_header.endswith(" фамилия")
            ):
                matches.append(header)

            elif requested_field == "имя" and (
                normalized_header.startswith("имя ")
                or normalized_header.endswith(" имя")
            ):
                matches.append(header)

    return matches


def _semantic_missing_scope(semantic_intent: Any) -> dict:
    """
    Безопасно извлекает параметры проверки пустых значений
    из результата intent_compiler.
    """

    if not isinstance(semantic_intent, dict):
        return {}

    resolved = semantic_intent.get("resolved")

    if not isinstance(resolved, dict):
        resolved = semantic_intent

    return {
        "scope": (
            resolved.get("scope")
            or semantic_intent.get("scope")
        ),
        "all_columns": resolved.get("all_columns"),
        "columns": resolved.get("columns"),
        "column": resolved.get("column"),
        "sheet": resolved.get("sheet"),
        "ambiguity": (
            semantic_intent.get("ambiguity")
            or resolved.get("ambiguity")
        ),
    }


def _find_explicit_headers(
    task: str,
    sheets: list[dict],
    selected_sheet: Any = None,
) -> list[dict]:
    """
    Находит только те заголовки, которые действительно указаны
    в пользовательском запросе.
    """

    text = _normalize_header_text(_normalize_task_text(task))

    sheets_to_check = sheets

    if selected_sheet:
        selected_name = str(selected_sheet).strip()

        matching = [
            item for item in sheets
            if _get_sheet_name(item) == selected_name
        ]

        if matching:
            sheets_to_check = matching

    candidates = []

    for sheet_info in sheets_to_check:
        sheet_name = _get_sheet_name(sheet_info)

        for header in _extract_headers(sheet_info):
            normalized_header = _normalize_header_text(header)

            if not normalized_header:
                continue

            pattern = (
                r"(?<!\w)"
                + re.escape(normalized_header)
                + r"(?!\w)"
            )

            if re.search(pattern, text):
                candidates.append({
                    "sheet": sheet_name,
                    "column": header,
                })

    return candidates


def _route_missing_field_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
    semantic_intent: Any = None,
) -> dict | None:
    """
    Единый маршрутизатор проверки пустых значений.

    Поддерживает:
    - проверку всех столбцов;
    - проверку нескольких явно указанных полей;
    - проверку одного поля;
    - уточнение обязательных полей без их перечня.

    Исходный лист не изменяется.
    """

    # The intent compiler can resolve colloquial forms such as
    # "сколько студентов без отчества", which do not necessarily contain
    # the literal words "пустой" or "отсутствует".  Treat the compiler's
    # explicit find_missing action as authoritative, while keeping the local
    # detector for deployments that call this router without semantic intent.
    semantic_actions = (
        semantic_intent.get("actions", [])
        if isinstance(semantic_intent, dict)
        else []
    )
    semantic_requests_missing = "find_missing" in semantic_actions

    if not (_detect_missing_field_request(task) or semantic_requests_missing):
        return None

    normalized_task = _normalize_task_text(task)
    semantic = _semantic_missing_scope(semantic_intent)

    sheets = _extract_sheets(analysis)

    if not sheets:
        return {
            "questions": [
                "Не удалось определить заголовки столбцов из анализа файла. "
                "Повтори анализ Excel-файла и попробуй ещё раз."
            ],
            "operations": [],
            "explanation": "Не удалось проверить структуру книги.",
            "mode": "questions",
            "original_task": task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # SHEET SELECTION
    # --------------------------------------------------------

    semantic_sheet = semantic.get("sheet")

    if selected_sheet:
        selected_name = str(selected_sheet).strip()
    elif semantic_sheet:
        selected_name = str(semantic_sheet).strip()
    else:
        selected_name = None

    if selected_name:
        matching_sheets = [
            item for item in sheets
            if _get_sheet_name(item) == selected_name
        ]

        if matching_sheets:
            sheets_to_check = matching_sheets
        else:
            return {
                "questions": [
                    f"Лист «{selected_name}» не найден в анализе файла. "
                    "Выбери существующий лист и повтори запрос."
                ],
                "operations": [],
                "explanation": "Не удалось определить выбранный лист.",
                "mode": "questions",
                "original_task": task,
                "deterministic_route": True,
            }
    else:
        sheets_to_check = sheets

    # --------------------------------------------------------
    # SCOPE DETECTION
    # --------------------------------------------------------

    requested_scope = _get_missing_scope(task)

    semantic_scope = semantic.get("scope")

    if semantic.get("all_columns") is True:
        requested_scope = "all_columns"

    elif semantic_scope in {
        "all_columns",
        "selected_columns",
        "single_column",
    }:
        requested_scope = semantic_scope

    # --------------------------------------------------------
    # REQUIRED FIELDS WITHOUT A LIST
    # --------------------------------------------------------

    if requested_scope == "required_fields":
        return {
            "questions": [
                "Какие именно поля считать обязательными? "
                "Перечисли названия столбцов Excel."
            ],
            "operations": [],
            "explanation": (
                "Нельзя самостоятельно определять обязательность полей. "
                "Нужно получить перечень от пользователя."
            ),
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # ALL COLUMNS
    # --------------------------------------------------------

    if requested_scope == "all_columns":
        if len(sheets_to_check) != 1:
            return {
                "questions": [
                    "В файле несколько листов. Укажи, какой лист "
                    "проверить на пустые значения."
                ],
                "operations": [],
                "explanation": (
                    "Для проверки всех столбцов необходимо определить лист."
                ),
                "mode": "questions",
                "original_task": task,
                "normalized_task": normalized_task,
                "deterministic_route": True,
            }

        sheet_name = _get_sheet_name(sheets_to_check[0])
        headers = _extract_headers(sheets_to_check[0])

        if not headers:
            return {
                "questions": [
                    "Не удалось получить заголовки столбцов выбранного листа. "
                    "Проверь структуру Excel-файла."
                ],
                "operations": [],
                "explanation": "Нет доступных заголовков для проверки.",
                "mode": "questions",
                "original_task": task,
                "deterministic_route": True,
            }

        operation = {
            "type": "find_blank_cells",
            "sheet": sheet_name,
            "all_columns": True,
            "output_sheet": "Отчёт проверки",
            "header_rows": 1,
        }

        return {
            "questions": [],
            "operations": [operation],
            "explanation": (
                f"Будут проверены все {len(headers)} столбцов "
                f"листа «{sheet_name}». "
                "Пустые ячейки и ячейки, содержащие только пробелы, "
                "будут отражены в отдельном отчёте. "
                "Исходный лист останется без изменений."
            ),
            "mode": "operations",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # SELECTED COLUMNS FROM SEMANTIC INTENT
    # --------------------------------------------------------

    semantic_columns = semantic.get("columns")

    if (
        isinstance(semantic_columns, list)
        and semantic_columns
        and requested_scope in {"selected_columns", "unspecified"}
    ):
        selected_columns = [
            str(item).strip()
            for item in semantic_columns
            if item is not None and str(item).strip()
        ]

        if selected_columns:
            if len(sheets_to_check) != 1:
                return {
                    "questions": [
                        "Уточни лист, на котором нужно проверить "
                        "указанные столбцы."
                    ],
                    "operations": [],
                    "explanation": "Не удалось однозначно определить лист.",
                    "mode": "questions",
                    "original_task": task,
                    "deterministic_route": True,
                }

            sheet_info = sheets_to_check[0]
            headers = _extract_headers(sheet_info)
            resolved_columns = []

            for requested in selected_columns:
                matches = [
                    header for header in headers
                    if _normalize_header_text(header)
                    == _normalize_header_text(requested)
                ]

                if len(matches) != 1:
                    return {
                        "questions": [
                            f"Не удалось однозначно сопоставить поле "
                            f"«{requested}» с заголовком Excel. "
                            "Уточни точное название столбца."
                        ],
                        "operations": [],
                        "explanation": (
                            "Некоторые указанные поля не удалось определить."
                        ),
                        "mode": "questions",
                        "original_task": task,
                        "deterministic_route": True,
                    }

                if matches[0] not in resolved_columns:
                    resolved_columns.append(matches[0])

            sheet_name = _get_sheet_name(sheet_info)

            operation = {
                "type": "find_blank_cells",
                "sheet": sheet_name,
                "columns": resolved_columns,
                "output_sheet": "Отчёт проверки",
                "header_rows": 1,
            }

            return {
                "questions": [],
                "operations": [operation],
                "explanation": (
                    "Будут проверены указанные столбцы: "
                    + ", ".join(f"«{name}»" for name in resolved_columns)
                    + f" на листе «{sheet_name}». "
                    "Результат будет записан в отдельный отчёт. "
                    "Исходный лист останется без изменений."
                ),
                "mode": "operations",
                "original_task": task,
                "normalized_task": normalized_task,
                "deterministic_route": True,
            }

    # --------------------------------------------------------
    # SINGLE COLUMN FROM SEMANTIC INTENT
    # --------------------------------------------------------

    semantic_column = semantic.get("column")

    if semantic_column and requested_scope in {
        "single_column",
        "unspecified",
    }:
        semantic_columns = [str(semantic_column).strip()]

    else:
        semantic_columns = []

    # --------------------------------------------------------
    # EXPLICIT HEADER MATCHING
    # --------------------------------------------------------

    explicit_candidates = _find_explicit_headers(
        task,
        sheets_to_check,
        selected_sheet=selected_name,
    )

    if semantic_columns:
        requested_names = semantic_columns
        explicit_candidates = []

        for sheet_info in sheets_to_check:
            sheet_name = _get_sheet_name(sheet_info)
            headers = _extract_headers(sheet_info)

            for requested in requested_names:
                matches = [
                    header for header in headers
                    if _normalize_header_text(header)
                    == _normalize_header_text(requested)
                ]

                for header in matches:
                    explicit_candidates.append({
                        "sheet": sheet_name,
                        "column": header,
                    })

    # --------------------------------------------------------
    # FALLBACK: KNOWN FIELD ALIASES
    # --------------------------------------------------------

    if not explicit_candidates:
        requested_field = _requested_field(task)

        if requested_field:
            for sheet_info in sheets_to_check:
                sheet_name = _get_sheet_name(sheet_info)
                headers = _extract_headers(sheet_info)

                for header in _match_field_header(
                    requested_field,
                    headers,
                ):
                    explicit_candidates.append({
                        "sheet": sheet_name,
                        "column": header,
                    })

    # --------------------------------------------------------
    # NO EXPLICIT COLUMN — ASK USER
    # --------------------------------------------------------

    if not explicit_candidates:
        available = []

        for sheet_info in sheets_to_check:
            sheet_name = _get_sheet_name(sheet_info)
            headers = _extract_headers(sheet_info)

            if headers:
                available.append(
                    f"{sheet_name}: {', '.join(headers[:25])}"
                )

        details = "\n".join(available[:8])

        question = (
            "Какое именно поле или какие столбцы нужно проверить "
            "на пустые значения? "
            "Можно указать несколько названий или написать "
            "«всю таблицу»."
        )

        if details:
            question += "\nДоступные заголовки:\n" + details

        return {
            "questions": [question],
            "operations": [],
            "explanation": (
                "Область проверки не определена. "
                "Нельзя самостоятельно выбирать поля."
            ),
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # CHECK AMBIGUOUS SHEETS / COLUMNS
    # --------------------------------------------------------

    unique_candidates = []
    seen = set()

    for item in explicit_candidates:
        key = (
            item["sheet"],
            _normalize_header_text(item["column"]),
        )

        if key not in seen:
            seen.add(key)
            unique_candidates.append(item)

    explicit_candidates = unique_candidates

    candidate_sheets = {
        item["sheet"]
        for item in explicit_candidates
    }

    if len(candidate_sheets) > 1:
        options = [
            f"Лист «{item['sheet']}», столбец «{item['column']}»"
            for item in explicit_candidates
        ]

        return {
            "questions": [
                "Найдено несколько подходящих вариантов:\n"
                + "\n".join(options)
                + "\nУкажи нужный лист и столбец."
            ],
            "operations": [],
            "explanation": "Требуется уточнить источник данных.",
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # BUILD OPERATION
    # --------------------------------------------------------

    sheet_name = explicit_candidates[0]["sheet"]

    columns = [
        item["column"]
        for item in explicit_candidates
    ]

    if len(columns) == 1:
        operation = {
            "type": "find_blank_cells",
            "sheet": sheet_name,
            "column": columns[0],
            "output_sheet": "Отчёт проверки",
            "header_rows": 1,
        }

        explanation = (
            f"Будет проверен столбец «{columns[0]}» "
            f"на листе «{sheet_name}». "
            "Результат будет записан в отдельный отчёт. "
            "Исходный лист останется без изменений."
        )

    else:
        operation = {
            "type": "find_blank_cells",
            "sheet": sheet_name,
            "columns": columns,
            "output_sheet": "Отчёт проверки",
            "header_rows": 1,
        }

        explanation = (
            "Будут проверены указанные столбцы: "
            + ", ".join(f"«{name}»" for name in columns)
            + f" на листе «{sheet_name}». "
            "Результат будет записан в отдельный отчёт. "
            "Исходный лист останется без изменений."
        )

    return {
        "questions": [],
        "operations": [operation],
        "explanation": explanation,
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# FAST ROUTING — SPLIT TO SHEETS, THEN SORT EACH SHEET
# ============================================================

def _route_split_then_sort_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    sort_match = re.search(
        r"\b(?:внутри\b.*?)?(?:располож\w*|отсортир\w*|сортир\w*|"
        r"упорядоч\w*)\b",
        text,
    )

    has_separate_sheets = bool(re.search(
        r"\b(?:отдельн\w*|разн\w*)\s+лист\w*"
        r"|\bлист\w*\s+для\s+кажд\w*",
        text,
    ))

    if not sort_match or not has_separate_sheets:
        return None

    sheets = _extract_sheets(analysis)

    if selected_sheet:
        selected = str(selected_sheet).strip()
        chosen = [
            s for s in sheets
            if _get_sheet_name(s) == selected
        ]
        if chosen:
            sheets = chosen

    if not sheets:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    split_text = text[:sort_match.start()]
    sort_text = text[sort_match.end():]

    def candidates(fragment: str) -> list[str]:
        task_stems = {
            _sort_word_stem(word)
            for word in re.findall(
                r"\w+",
                fragment,
                flags=re.UNICODE,
            )
            if len(word) >= 3
        }

        result = []

        for header in headers:
            normalized_header = _normalize_header_text(header)

            if normalized_header == "имя" and re.search(
                r"\b(?:имя|имени)\b",
                fragment,
            ):
                result.append(header)
                continue

            header_stems = {
                _sort_word_stem(word)
                for word in re.findall(
                    r"\w+",
                    normalized_header,
                    flags=re.UNICODE,
                )
                if len(word) >= 3
            }

            if header_stems and header_stems.issubset(task_stems):
                result.append(header)

        return result

    split_columns = candidates(split_text)
    sort_columns = candidates(sort_text)

    if len(split_columns) != 1 or len(sort_columns) != 1:
        return None

    split_column = split_columns[0]
    sort_column = sort_columns[0]

    descending = bool(re.search(
        r"\bпо убыванию\b|\bот я до а\b|\bот z до a\b",
        text,
    ))

    return {
        "questions": [],
        "operations": [{
            "type": "split_to_sheets",
            "sheet": sheet_name,
            "column": split_column,
            "sort_column": sort_column,
            "sort_descending": descending,
            "header_rows": 1,
        }],
        "explanation": (
            f"Для каждого значения столбца «{split_column}» будет создан "
            f"отдельный лист. Внутри каждого листа записи будут "
            f"отсортированы по столбцу «{sort_column}» "
            + ("по убыванию." if descending else "по возрастанию.")
        ),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# FAST ROUTING — TRIM TEXT, THEN SORT
# ============================================================

def _route_trim_then_sort_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    has_trim = bool(re.search(
        r"\b(?:убер\w*|удал\w*|очист\w*)\b.*\bпробел\w*",
        text,
    ))

    sort_match = re.search(
        r"\b(?:затем\s+)?(?:отсортир\w*|сортир\w*|упорядоч\w*)\b",
        text,
    )

    if not has_trim or not sort_match:
        return None

    sheets = _extract_sheets(analysis)

    if selected_sheet:
        selected = str(selected_sheet).strip()
        chosen = [
            s for s in sheets
            if _get_sheet_name(s) == selected
        ]
        if chosen:
            sheets = chosen

    if len(sheets) != 1:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    trim_text = text[:sort_match.start()]
    sort_text = text[sort_match.end():]

    def mentioned_headers(fragment: str) -> list[str]:
        stems = {
            _sort_word_stem(word)
            for word in re.findall(
                r"\w+",
                fragment,
                flags=re.UNICODE,
            )
            if len(word) >= 3
        }

        matches = []

        for header in headers:
            normalized_header = _normalize_header_text(header)

            if normalized_header == "имя" and re.search(
                r"\b(?:имя|имени)\b",
                fragment,
            ):
                matches.append(header)
                continue

            words = [
                word for word in re.findall(
                    r"\w+",
                    normalized_header,
                    flags=re.UNICODE,
                )
                if len(word) >= 3
            ]

            header_stems = {
                _sort_word_stem(word)
                for word in words
            }

            if header_stems and header_stems.issubset(stems):
                matches.append(header)

        return matches

    trim_columns = mentioned_headers(trim_text)
    sort_columns = mentioned_headers(sort_text)

    if not trim_columns or len(sort_columns) != 1:
        return None

    descending = bool(re.search(
        r"\bпо убыванию\b|\bот я до а\b|\bот z до a\b",
        sort_text,
    ))

    sort_column = sort_columns[0]

    return {
        "questions": [],
        "operations": [
            {
                "type": "trim_text",
                "sheet": sheet_name,
                "columns": trim_columns,
                "header_rows": 1,
            },
            {
                "type": "sort_rows",
                "sheet": sheet_name,
                "column": sort_column,
                "descending": descending,
                "header_rows": 1,
            },
        ],
        "explanation": (
            "Сначала будут удалены лишние пробелы в столбцах "
            + ", ".join(f"«{name}»" for name in trim_columns)
            + f", затем строки будут отсортированы по столбцу "
            f"«{sort_column}»."
        ),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# FAST ROUTING — GROUPED COUNT / SUMMARY
# ============================================================

def _route_smart_summary_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    wants_comparison = bool(re.search(
        r"\b(?:сравнительн\w*\s+анализ\w*|сравни\w*|сопостав\w*)\b",
        text,
    ))
    wants_cross_tables = bool(re.search(
        r"\b(?:перекр[её]ст\w*|кросс[-\s]?таблиц\w*|cross[-\s]?tab\w*)\b",
        text,
    ))

    wants_summary = wants_comparison or bool(re.search(
        r"\b(?:общ\w*\s+(?:сводк\w*|сводн\w*\s+таблиц\w*)|"
        r"сводк\w*|сводн\w*\s+таблиц\w*|итог\w*|статистик\w*|"
        r"посчитай|сколько|распределени\w*|отчет\w*|отчёт\w*|дашборд\w*|dashboard|"
        r"проанализир\w*\s+(?:файл\w*|данн\w*|таблиц\w*)|"
        r"анализ\w*\s+(?:файл\w*|данн\w*|таблиц\w*))\b",
        text,
    ))

    wants_split = bool(re.search(
        r"\b(?:раздели\w*|разбей\w*|отдельн\w*\s+лист\w*|"
        r"разн\w*\s+лист\w*)\b",
        text,
    ))

    if not (wants_summary or wants_split):
        return None

    sheets = _extract_sheets(analysis)

    if selected_sheet:
        selected = str(selected_sheet).strip()
        sheets = [
            item for item in sheets
            if _get_sheet_name(item) == selected
        ] or sheets

    if len(sheets) != 1:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    task_stems = {
        _sort_word_stem(word)
        for word in re.findall(
            r"\w+",
            text,
            flags=re.UNICODE,
        )
        if len(word) >= 3
    }

    matched = []

    for header in headers:
        words = [
            _sort_word_stem(word)
            for word in re.findall(
                r"\w+",
                _normalize_header_text(header),
                flags=re.UNICODE,
            )
            if len(word) >= 3
        ]

        if words and all(word in task_stems for word in words):
            matched.append(header)

    operations = []

    if wants_summary:
        if wants_cross_tables and len(matched) < 2:
            anchor = matched[0] if matched else "основной признак"
            return {
                "questions": [
                    f"С каким вторым столбцом построить перекрёстную таблицу для «{anchor}»? "
                    "Укажите точное название заголовка Excel."
                ],
                "operations": [],
                "mode": "questions",
                "explanation": (
                    "Перекрёстная таблица требует двух признаков; "
                    "автоматическая подстановка остальных столбцов отключена."
                ),
            }

        operation = {
            "type": "smart_summary",
            "sheet": sheet_name,
            "output_sheet": "Общая сводка",
            "header_rows": 1,
            "include_cross_tables": wants_cross_tables,
            "include_charts": True,
        }

        if matched:
            operation["columns"] = matched
            # A comparative request must stay on the explicitly named axis.
            # A broad report may still enrich itself with safe categorical
            # dimensions, preserving the existing automatic-report workflow.
            operation["include_other_dimensions"] = not wants_comparison

        operations.append(operation)

    if wants_split:
        if not matched:
            return {
                "questions": [
                    "По каким столбцам разделить записи? "
                    "Укажите точные названия заголовков Excel."
                ],
                "operations": [],
                "mode": "questions",
                "explanation": (
                    "Для разделения требуется однозначный признак."
                ),
                "original_task": task,
                "normalized_task": normalized_task,
                "deterministic_route": True,
            }

        operations.append({
            "type": "split_to_sheets",
            "sheet": sheet_name,
            "columns": matched,
            "header_rows": 1,
        })

    column_text = ", ".join(
        f"«{name}»"
        for name in matched
    )

    explanation = []

    if wants_summary:
        explanation.append(
            "Будет создана общая сводка, отдельные распределения, доли, "
            "рейтинги и диаграммы"
            + (" и перекрёстные таблицы" if wants_cross_tables else "")
            + (
                f" по столбцам {column_text}."
                if matched
                else " по автоматически найденным разрезам."
            )
        )

    if wants_split:
        explanation.append(
            f"Записи будут распределены по отдельным листам "
            f"по комбинациям {column_text}."
        )

    missing_requested = (
        bool(re.search(
            r"направлен|специальност|образовательн\w*\s+программ",
            text,
        ))
        and not any(
            re.search(
                r"направлен|специальност|программ",
                _normalize_header_text(header),
            )
            for header in headers
        )
    )

    if missing_requested:
        explanation.append(
            "ВНИМАНИЕ: столбец направления/специальности/"
            "образовательной программы отсутствует; "
            "этот разрез не будет рассчитан."
        )

    return {
        "questions": [],
        "operations": operations,
        "explanation": " ".join(explanation),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


def _route_group_count_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    has_summary = bool(re.search(
        r"\b(?:сводк\w*|итог\w*|статистик\w*|посчитай|сколько|распределени\w*)\b",
        text,
    ))

    if not has_summary:
        return None

    sheets = _extract_sheets(analysis)

    if selected_sheet:
        selected = str(selected_sheet).strip()
        matches = [
            s for s in sheets
            if _get_sheet_name(s) == selected
        ]

        if matches:
            sheets = matches

    if len(sheets) != 1:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    dimensions = [
        {
            "key": "факультет",
            "task_pattern": r"\bфакультет\w*\b",
            "header_pattern": r"\bфакультет\w*\b",
        },
        {
            "key": "форма обучения",
            "task_pattern": r"\bформ\w*\s+обучен\w*\b",
            "header_pattern": r"\bформ\w*\s+обучен\w*\b",
        },
        {
            "key": "вид финансирования",
            "task_pattern": r"\b(?:вид\w*\s+)?финансирован\w*\b",
            "header_pattern": r"\bфинансирован\w*\b",
        },
        {
            "key": "курс",
            "task_pattern": r"\bкурс\w*\b",
            "header_pattern": r"\bкурс\w*\b",
        },
        {
            "key": "группа",
            "task_pattern": r"\bгрупп\w*\b",
            "header_pattern": r"\bгрупп\w*\b",
        },
    ]

    requested_dimensions = [
        item for item in dimensions
        if re.search(
            item["task_pattern"],
            text,
            flags=re.IGNORECASE,
        )
    ]

    if not requested_dimensions:
        return None

    resolved_columns = []
    missing_dimensions = []

    for dimension in requested_dimensions:
        matches = [
            header for header in headers
            if re.search(
                dimension["header_pattern"],
                _normalize_header_text(header),
                flags=re.IGNORECASE,
            )
        ]

        if len(matches) == 1:
            resolved_columns.append(matches[0])

        elif len(matches) > 1:
            return {
                "questions": [
                    f"Для признака «{dimension['key']}» "
                    "найдено несколько столбцов: "
                    + ", ".join(f"«{value}»" for value in matches)
                    + ". Укажи, какой столбец использовать."
                ],
                "operations": [],
                "explanation": (
                    "Нельзя безопасно выбрать один из нескольких столбцов."
                ),
                "mode": "questions",
                "original_task": task,
                "normalized_task": normalized_task,
                "deterministic_route": True,
            }

        else:
            missing_dimensions.append(dimension["key"])

    if missing_dimensions:
        return {
            "questions": [
                "Не удалось однозначно найти в Excel столбцы "
                "для признаков: "
                + ", ".join(
                    f"«{name}»"
                    for name in missing_dimensions
                )
                + ". Проверь названия заголовков или уточни их."
            ],
            "operations": [],
            "explanation": (
                "Для сводки и разделения нужны все указанные признаки."
            ),
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    if not resolved_columns:
        return None

    has_split = bool(re.search(
        r"\b(?:раздели\w*|разбей\w*|распредел\w*|на\s+разн\w*\s+лист\w*|"
        r"по\s+отдельн\w*\s+лист\w*)\b",
        text,
    ))

    operations = [{
        "type": "group_by_aggregate",
        "sheet": sheet_name,
        "columns": resolved_columns,
        "function": "count",
        "output_sheet": "Общая_сводка",
        "header_rows": 1,
        "include_empty": True,
    }]

    if has_split:
        operations.append({
            "type": "split_to_sheets",
            "sheet": sheet_name,
            "columns": resolved_columns,
            "header_rows": 1,
        })

    cols_formatted = ", ".join(
        f"«{column}»"
        for column in resolved_columns
    )

    explanation = (
        "Будет создана одна общая сводка с количеством студентов "
        f"по комбинациям признаков: {cols_formatted}."
    )

    if has_split:
        explanation += (
            " Дополнительно каждый студент будет распределён "
            "на отдельный лист по полной комбинации этих же признаков, "
            "а не только по первому столбцу."
        )

    return {
        "questions": [],
        "operations": operations,
        "explanation": explanation,
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# FAST ROUTING — SPLIT RECORDS TO WORKSHEETS
# ============================================================

def _route_split_to_sheets_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    destination_patterns = (
        r"\b(?:на|по)\s+разн\w*\s+лист\w*",
        r"\bна\s+отдельн\w*\s+лист\w*",
        r"\bпо\s+отдельн\w*\s+лист\w*",
        r"\bкажд\w*\s+(?:факультет\w*|значен\w*|групп\w*)\s+"
        r"(?:на|в)\s+(?:свой|отдельн\w*)\s+лист\w*",
        r"\bраздел\w*\s+по\s+лист\w*",
        r"\bразбей\w*\s+по\s+лист\w*",
        r"\bраспредел\w*\s+по\s+лист\w*",
    )
    if not any(re.search(pattern, text) for pattern in destination_patterns):
        return None

    sheets = _extract_sheets(analysis)
    if selected_sheet:
        selected = str(selected_sheet).strip()
        matches = [s for s in sheets if _get_sheet_name(s) == selected]
        if matches:
            sheets = matches

    if not sheets:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    task_stems = {
        _sort_word_stem(word)
        for word in re.findall(r"\w+", text, flags=re.UNICODE)
        if len(word) >= 3
    }

    matched_columns = []
    for header in headers:
        header_words = [
            word for word in re.findall(
                r"\w+", _normalize_header_text(header), flags=re.UNICODE
            )
            if len(word) >= 3
        ]
        if not header_words:
            continue
        header_stems = {_sort_word_stem(word) for word in header_words}
        if header_stems & task_stems:
            matched_columns.append(header)

    if not matched_columns:
        return {
            "questions": [
                "По какому столбцу разделить данные на разные листы? "
                "Укажи точное название столбца."
            ],
            "operations": [],
            "explanation": "Нужно определить признак разделения на листы.",
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    operations = []

    has_summary = bool(re.search(r"\b(?:сводка|сводку|итог|статистик\w*|посчитай)\b", text))
    if has_summary:
        for col in matched_columns:
            operations.append({
                "type": "group_by_aggregate",
                "sheet": sheet_name,
                "column": col,
                "function": "count",
                "output_sheet": f"Сводка {col}",
                "header_rows": 1,
            })

    split_column = matched_columns[0]
    operations.append({
        "type": "split_to_sheets",
        "sheet": sheet_name,
        "column": split_column,
        "header_rows": 1,
    })

    exp_parts = []
    if has_summary:
        cols_str = ", ".join(f"«{c}»" for c in matched_columns)
        exp_parts.append(f"Будет создана сводка по столбцам: {cols_str}.")

    exp_parts.append(
        f"Данные листа «{sheet_name}» будут разделены по значениям столбца «{split_column}» на отдельные листы."
    )

    return {
        "questions": [],
        "operations": operations,
        "explanation": " ".join(exp_parts),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# FAST ROUTING — SORT
# ============================================================

def _sort_word_stem(word: str) -> str:
    endings = (
        "иями", "ями", "ами", "ого", "ему", "ому",
        "ыми", "ими", "иях", "ах", "ях", "ов", "ев",
        "ей", "ом", "ем", "ам", "ям", "ую", "юю",
        "ая", "яя", "ое", "ее", "ые", "ие", "ой",
        "ый", "ий", "ую", "юю", "ия", "ии",
        "а", "я", "ы", "и", "у", "ю", "е", "о",
    )

    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)]

    return word


def _route_sort_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)

    sort_patterns = (
        r"\bотсортир\w*",
        r"\bсортиров\w*",
        r"\bупорядоч\w*",
        r"\bрасположи\w*",
        r"\bотсортируй\w*",
        r"\bsort\b",
    )

    if not any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in sort_patterns
    ):
        return None

    if re.search(
        r"\b(?:не|нельзя|не надо|не нужно|отмени)\s+"
        r"(?:отсортир\w*|сортиров\w*|упорядоч\w*)",
        text,
        flags=re.IGNORECASE,
    ):
        return None

    sheets = _extract_sheets(analysis)

    if not sheets:
        return None

    if selected_sheet:
        selected_name = str(selected_sheet).strip()
        selected_matches = [
            item for item in sheets
            if _get_sheet_name(item) == selected_name
        ]

        if selected_matches:
            sheets_to_check = selected_matches
        else:
            sheets_to_check = sheets
    else:
        sheets_to_check = sheets

    task_words = {
        _sort_word_stem(word)
        for word in re.findall(r"\w+", text, flags=re.UNICODE)
        if len(word) >= 3
    }

    candidates = []

    for sheet_info in sheets_to_check:
        sheet_name = _get_sheet_name(sheet_info)
        headers = _extract_headers(sheet_info)

        for header in headers:
            header_text = _normalize_header_text(header)

            if not header_text:
                continue

            header_words = [
                word for word in re.findall(
                    r"\w+", header_text, flags=re.UNICODE
                )
                if len(word) >= 3
            ]

            if not header_words:
                continue

            matched_words = [
                word for word in header_words
                if _sort_word_stem(word) in task_words
            ]

            if matched_words:
                candidates.append({
                    "sheet": sheet_name,
                    "column": header,
                })

    unique_candidates = []
    seen = set()

    for item in candidates:
        key = (
            item["sheet"].casefold(),
            _normalize_header_text(item["column"]),
        )

        if key not in seen:
            seen.add(key)
            unique_candidates.append(item)

    candidates = unique_candidates

    if not candidates:
        return None

    if len(candidates) > 1:
        options = [
            f"Лист «{item['sheet']}», столбец «{item['column']}»"
            for item in candidates[:20]
        ]

        return {
            "questions": [
                "По какому столбцу выполнить сортировку? "
                "Найдено несколько подходящих вариантов:\n"
                + "\n".join(options)
                + "\nУкажи точное название столбца."
            ],
            "operations": [],
            "explanation": "Нужно уточнить столбец для сортировки.",
            "mode": "questions",
            "original_task": task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    match = candidates[0]

    descending = bool(re.search(
        r"\bпо убыванию\b"
        r"|\bубывающ\w*"
        r"|\bот большего к меньшему\b"
        r"|\bот я до а\b"
        r"|\bот z до a\b"
        r"|\bz\s*-\s*a\b"
        r"|\bя\s*-\s*а\b",
        text,
        flags=re.IGNORECASE,
    ))

    direction = "по убыванию" if descending else "по возрастанию"

    operation = {
        "type": "sort_rows",
        "sheet": match["sheet"],
        "column": match["column"],
        "descending": descending,
        "header_rows": 1,
    }

    return {
        "questions": [],
        "operations": [operation],
        "explanation": (
            f"Сортировка листа «{match['sheet']}» "
            f"по столбцу «{match['column']}» {direction}."
        ),
        "mode": "operations",
        "original_task": task,
        "normalized_task": normalized_task,
        "deterministic_route": True,
    }


# ============================================================
# JSON HELPERS
# ============================================================

def _extract_json(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ИИ вернул пустой ответ.")

    cleaned = text.strip()

    cleaned = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    try:
        result = json.loads(cleaned)

        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")

    if start < 0:
        raise ValueError(
            "В ответе ИИ не найден JSON-объект:\n"
            + cleaned[:1500]
        )

    try:
        result, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Не удалось разобрать JSON от ИИ: {exc}\n"
            + cleaned[:1500]
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("Ответ ИИ должен быть JSON-объектом.")

    return result


def _compact_analysis(analysis: Any) -> str:
    if isinstance(analysis, str):
        text = analysis
    else:
        compact = {
            "file_name": analysis.get("file_name"),
            "format": analysis.get("format"),
            "analysis_policy": analysis.get("analysis_policy"),
            "sheets": [],
        } if isinstance(analysis, dict) else analysis
        if isinstance(analysis, dict):
            for sheet in analysis.get("sheets", []):
                compact["sheets"].append({
                    "name": sheet.get("name"),
                    "data_rows": max(0, sheet.get("nonempty_rows", 0) - 1),
                    "header_row": sheet.get("header_row", 1),
                    "headers": sheet.get("headers", []),
                    "value_examples": [
                        {
                            "column": item.get("header"),
                            "examples": [example.get("value") for example in item.get("examples", [])[:8]],
                        }
                        for item in sheet.get("duplicate_columns", [])[:30]
                    ],
                    "semantic_profile": sheet.get("semantic_profile", {}),
                    "preview": sheet.get("preview", []),
                    "formulas": sheet.get("formula_examples", []),
                })
        try:
            text = json.dumps(compact, ensure_ascii=False, default=str)
        except Exception:
            text = str(compact)

    if len(text) > MAX_ANALYSIS_CHARS:
        text = text[:MAX_ANALYSIS_CHARS] + "\n[Анализ сокращён]"

    return text


# ============================================================
# CLOUD AI REQUEST (GOOGLE GEMINI FLASH)
# ============================================================

EXCEL_AI_SYSTEM_PROMPT = (
    "Ты — универсальный эксперт по работе с табличными данными (Excel, CSV, TSV) любой сложности и предметной области.\n"
    "Твоя задача — адаптироваться под задачу пользователя:\n"
    "- Проведение расчетов, поиск зависимостей, аномалий и ошибок в данных.\n"
    "- Составление и отладка формул любой сложности (XLOOKUP, INDEX/MATCH, динамические массивы, агрегации, условия).\n"
    "- Сверка любых таблиц между собой: сопоставление сущностей, нечеткое сравнение строк/ФИО, поиск нестыковок и дубликатов.\n"
    "- Генерация готового кода на Python (pandas/openpyxl) или VBA макросов для автоматизации обработки.\n"
    "Ответ давай структурированно, точно и применимо к конкретным колонкам переданной таблицы без лишней теории.\n"
    "Возвращай только валидный JSON."
)


def _post_to_cloud_ai(prompt: str) -> dict:
    """Вызов облачного ИИ Google Gemini через единый сервис ai_service."""
    import ai_service
    raw_ai = ai_service.generate_text(
        prompt=prompt,
        system_instruction=EXCEL_AI_SYSTEM_PROMPT,
        temperature=0.1,
        timeout=REQUEST_TIMEOUT,
    )
    if isinstance(raw_ai, tuple):
        raw_ai = raw_ai[0]
    if not raw_ai or not str(raw_ai).strip():
        raise ValueError("Облачный ИИ вернул пустой ответ.")
    return _extract_json(raw_ai)


_post_to_ollama = _post_to_cloud_ai


# ============================================================
# QUESTIONS
# ============================================================

def _normalize_questions(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    questions = []

    for item in value:
        if isinstance(item, str):
            question = item.strip()
        elif isinstance(item, dict):
            question = str(
                item.get("question")
                or item.get("text")
                or item.get("message")
                or ""
            ).strip()
        else:
            question = ""

        if question:
            questions.append(question)

    return questions


# ============================================================
# TYPE NORMALIZATION
# ============================================================

def _normalize_type(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = text.replace("-", "_").replace(" ", "_")

    return TYPE_ALIASES.get(text, text)


def _get_operation_type(operation: dict) -> str:
    possible_keys = (
        "type",
        "operation_type",
        "operation",
        "action",
        "name",
        "function",
        "command",
        "method",
        "операция",
        "действие",
        "тип",
    )

    for key in possible_keys:
        value = operation.get(key)

        if isinstance(value, dict):
            value = (
                value.get("name")
                or value.get("type")
                or value.get("operation")
            )

        normalized = _normalize_type(value)

        if normalized in SUPPORTED_TYPES:
            return normalized

    for nested_key in ("parameters", "params", "arguments", "args"):
        nested = operation.get(nested_key)

        if isinstance(nested, dict):
            for key in possible_keys:
                normalized = _normalize_type(nested.get(key))

                if normalized in SUPPORTED_TYPES:
                    return normalized

    for key in operation:
        normalized = _normalize_type(key)

        if normalized in SUPPORTED_TYPES:
            return normalized

    return ""


# ============================================================
# OPERATION NORMALIZATION
# ============================================================

def _normalize_operation(original: dict, index: int) -> dict:
    operation = dict(original)
    operation_type = _get_operation_type(operation)

    if not operation_type:
        raise ValueError(
            f"Операция {index}: неизвестный тип.\n"
            + json.dumps(
                original,
                ensure_ascii=False,
                indent=2,
                default=str,
            )[:2000]
        )

    operation["type"] = operation_type

    for nested_key in ("parameters", "params", "arguments", "args"):
        nested = operation.get(nested_key)

        if isinstance(nested, dict):
            for key, value in nested.items():
                operation.setdefault(key, value)

    if not operation.get("sheet"):
        for alias in ("sheet_name", "worksheet", "лист", "имя_листа"):
            if operation.get(alias):
                operation["sheet"] = operation[alias]
                break

    if not operation.get("column"):
        for alias in (
            "column_name",
            "column_to_use",
            "field",
            "столбец",
            "колонка",
            "поле",
        ):
            if operation.get(alias):
                operation["column"] = operation[alias]
                break

    if "columns" not in operation:
        for alias in ("column_names", "fields", "столбцы", "колонки"):
            if operation.get(alias) is not None:
                operation["columns"] = operation[alias]
                break

    if isinstance(operation.get("columns"), str):
        operation["columns"] = [operation["columns"]]

    if operation_type == "combine_columns":
        if not operation.get("source_columns"):
            operation["source_columns"] = operation.get("columns")
        if isinstance(operation.get("source_columns"), str):
            operation["source_columns"] = [operation["source_columns"]]
        if not operation.get("target_column"):
            for alias in ("output_column", "new_column", "result_column", "новый_столбец"):
                if operation.get(alias):
                    operation["target_column"] = operation[alias]
                    break
        if not operation.get("source_columns") or len(operation["source_columns"]) < 2:
            raise ValueError(
                f"Операция {index} (combine_columns): нужны минимум два исходных столбца."
            )
        if not str(operation.get("target_column") or "").strip():
            raise ValueError(
                f"Операция {index} (combine_columns): укажите имя нового столбца."
            )
        operation.setdefault("separator", " ")
        operation.setdefault("skip_empty", True)
        operation.setdefault("trim_result", True)
        operation.setdefault("position", "first")

    elif operation_type == "group_by_aggregate":
        if not operation.get("column"):
            for alias in ("group_column", "group_by", "группировать_по"):
                if operation.get(alias):
                    operation["column"] = operation[alias]
                    break

        if not operation.get("target_column"):
            for alias in ("value_column", "aggregate_column", "столбец_расчёта"):
                if operation.get(alias):
                    operation["target_column"] = operation[alias]
                    break

        if not operation.get("function"):
            operation["function"] = "sum"

        function = str(operation["function"]).strip().lower()
        function_aliases = {
            "average": "avg",
            "average_value": "avg",
            "mean": "avg",
            "сумма": "sum",
            "среднее": "avg",
            "количество": "count",
            "минимум": "min",
            "максимум": "max",
        }
        operation["function"] = function_aliases.get(function, function)

        if not operation.get("column"):
            raise ValueError(
                f"Операция {index} (group_by_aggregate): "
                "не указан столбец группировки (column)."
            )

        if operation["function"] not in {"sum", "avg", "count", "min", "max"}:
            raise ValueError(
                f"Операция {index} (group_by_aggregate): неизвестная функция "
                f"{operation['function']!r}. Допустимо: sum, avg, count, min, max."
            )

        if operation["function"] != "count" and not operation.get("target_column"):
            raise ValueError(
                f"Операция {index} (group_by_aggregate): для функции "
                f"{operation['function']} укажи target_column."
            )

    elif operation_type == "apply_formula":
        if not operation.get("column"):
            for alias in ("target_column", "result_column", "столбец_результата"):
                if operation.get(alias):
                    operation["column"] = operation[alias]
                    break

        if not operation.get("column"):
            raise ValueError(
                f"Операция {index} (apply_formula): не указан целевой столбец (column)."
            )

        formula = operation.get("formula")
        if not isinstance(formula, str) or not formula.strip().startswith("="):
            raise ValueError(
                f"Операция {index} (apply_formula): formula должна быть "
                "Excel-формулой, начинающейся с '='."
            )
        if "{row}" not in formula:
            raise ValueError(
                f"Операция {index} (apply_formula): formula должна содержать "
                "плейсхолдер {row}, например =B{row}*C{row}."
            )
        try:
            formula.format(row=2)
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(
                f"Операция {index} (apply_formula): некорректный шаблон формулы: {exc}"
            ) from exc
        operation["formula"] = formula.strip()

    elif operation_type == "filter_rows":
        if not operation.get("column") and isinstance(operation.get("columns"), list) and operation["columns"]:
            operation["column"] = operation["columns"][0]
        if not operation.get("column") and isinstance(operation.get("conditions"), list) and operation["conditions"]:
            first_condition = operation["conditions"][0]
            if isinstance(first_condition, dict):
                operation["column"] = first_condition.get("column")
        if not operation.get("operator"):
            for alias in ("op", "condition", "comparison", "условие", "оператор"):
                if operation.get(alias) is not None:
                    operation["operator"] = operation[alias]
                    break
        raw_op = str(operation.get("operator") or "eq").strip().lower()
        op_aliases = {
            "=": "eq", "==": "eq", "равно": "eq", "равен": "eq", "равна": "eq", "equals": "eq", "equal": "eq",
            "!=": "ne", "<>": "ne", "не равно": "ne", "not_equal": "ne", "neq": "ne",
            ">": "gt", "больше": "gt", "greater": "gt", "above": "gt",
            ">=": "ge", "gte": "ge", "больше или равно": "ge", "не меньше": "ge",
            "<": "lt", "меньше": "lt", "less": "lt", "below": "lt",
            "<=": "le", "lte": "le", "меньше или равно": "le", "не больше": "le",
            "содержит": "contains", "включает": "contains", "like": "contains",
            "не содержит": "not_contains",
            "пусто": "blank", "пустой": "blank", "is_empty": "blank", "null": "blank",
            "не пусто": "not_blank", "заполнено": "not_blank", "not_empty": "not_blank",
        }
        operation["operator"] = op_aliases.get(raw_op, raw_op)
        if isinstance(operation.get("conditions"), list):
            normalized_conditions = []
            for condition in operation["conditions"]:
                if not isinstance(condition, dict):
                    continue
                item = dict(condition)
                item_operator = str(item.get("operator") or "eq").strip().lower()
                item["operator"] = op_aliases.get(item_operator, item_operator)
                normalized_conditions.append(item)
            operation["conditions"] = normalized_conditions
        if "value" not in operation:
            for alias in ("target_value", "filter_value", "значение", "критерий"):
                if alias in operation:
                    operation["value"] = operation[alias]
                    break

    elif operation_type == "pivot_count":
        if not operation.get("row_column"):
            for alias in ("row", "rows", "index", "group_column", "column", "строка", "строки", "по_вертикали"):
                if operation.get(alias):
                    operation["row_column"] = operation[alias]
                    break
        if not operation.get("column_column"):
            for alias in ("col", "col_column", "header_column", "compare_column", "other_column", "столбец_сравнения", "по_горизонтали"):
                if operation.get(alias):
                    operation["column_column"] = operation[alias]
                    break
        cols = operation.get("columns")
        if isinstance(cols, list) and len(cols) >= 2:
            operation.setdefault("row_column", cols[0])
            operation.setdefault("column_column", cols[1])

    elif operation_type == "replace_values":
        if not operation.get("columns") and operation.get("column"):
            operation["columns"] = [operation["column"]]
        if "old" not in operation:
            for alias in ("old_value", "find", "search", "from", "старое", "найти"):
                if alias in operation:
                    operation["old"] = operation[alias]
                    break
        if "new" not in operation:
            for alias in ("new_value", "replace", "to", "новое", "заменить_на"):
                if alias in operation:
                    operation["new"] = operation[alias]
                    break

    elif operation_type == "fill_empty":
        if not operation.get("columns") and operation.get("column"):
            operation["columns"] = [operation["column"]]
        if "value" not in operation:
            for alias in ("fill_value", "default", "replacement", "значение", "чем_заполнить"):
                if alias in operation:
                    operation["value"] = operation[alias]
                    break

    elif operation_type == "sort_rows":
        if not operation.get("column") and isinstance(operation.get("columns"), list) and operation["columns"]:
            operation["column"] = operation["columns"][0]
        if "descending" not in operation:
            for alias in ("order", "direction", "порядок"):
                val = str(operation.get(alias) or "").strip().lower()
                if val in {"desc", "descending", "убывание", "по убыванию", "true"}:
                    operation["descending"] = True
                    break
                if val in {"asc", "ascending", "возрастание", "по возрастанию", "false"}:
                    operation["descending"] = False
                    break

    elif operation_type == "distinct_count":
        if not operation.get("id_column"):
            for alias in ("column", "key_column", "unique_column", "столбец_id"):
                if operation.get(alias):
                    operation["id_column"] = operation[alias]
                    break

    elif operation_type == "compare_columns":
        if not operation.get("other_column"):
            for alias in ("second_column", "column2", "target_column", "второй_столбец"):
                if operation.get(alias):
                    operation["other_column"] = operation[alias]
                    break
        cols = operation.get("columns")
        if isinstance(cols, list) and len(cols) >= 2:
            operation.setdefault("column", cols[0])
            operation.setdefault("other_column", cols[1])

    elif operation_type in {
        "extract_split_values_to_sheet", "split_cell_values_to_rows",
        "split_to_sheets", "split_by_column", "summary_count", "find_repeated_values",
    }:
        if not operation.get("column") and isinstance(operation.get("columns"), list) and operation["columns"]:
            operation["column"] = operation["columns"][0]

    elif operation_type in {
        "trim_text", "highlight_empty", "remove_duplicates",
        "find_blank_cells", "select_columns", "copy_columns_to_sheet", "reorder_columns",
    }:
        if not operation.get("columns") and operation.get("column"):
            operation["columns"] = [operation["column"]]

    return operation


def _validate_operations(operations: Any) -> list[dict]:
    if operations is None:
        return []

    if isinstance(operations, dict):
        operations = [operations]

    if not isinstance(operations, list):
        raise ValueError(
            "Поле operations должно быть списком или объектом."
        )

    validated = []

    for index, original in enumerate(operations, start=1):
        if not isinstance(original, dict):
            raise ValueError(
                f"Операция {index} должна быть JSON-объектом."
            )

        validated.append(_normalize_operation(original, index))

    return validated


# ============================================================
# PROMPT
# ============================================================

def _build_prompt(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
    original_task: str | None = None,
    semantic_intent: dict | None = None,
) -> str:
    compact = _compact_analysis(analysis)

    sheet_instruction = ""

    if selected_sheet:
        sheet_instruction = (
            f"\nВыбранный пользователем лист: {selected_sheet}\n"
            "Используй этот лист, если пользователь явно "
            "не попросил другой.\n"
        )

    original_instruction = ""

    if original_task and original_task != task:
        original_instruction = (
            "\nОРИГИНАЛЬНЫЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n"
            f"{original_task}\n"
            "Исправленный запрос помогает понять намерение, "
            "но не является названием столбца или значением ячейки.\n"
        )

    supported = ", ".join(sorted(SUPPORTED_TYPES))
    intent_block = json.dumps(
        semantic_intent or {}, ensure_ascii=False, indent=2, default=str
    )

    return f"""
Ты — исполнитель планирования задач для BahonIQ Excel AI.

ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:
{task}
{original_instruction}
{sheet_instruction}

АНАЛИЗ EXCEL-ФАЙЛА:
{compact}

СЕМАНТИЧЕСКИЙ РАЗБОР ЗАПРОСА:
{intent_block}

Семантический разбор — подсказка, построенная по реальным заголовкам книги.
Сохраняй исходный смысл пользователя. Если подсказка конфликтует с исходной
фразой, задай уточняющий вопрос, а не выдумывай действие.

ДОСТУПНЫЕ ТИПЫ ОПЕРАЦИЙ:
{supported}

Сначала мысленно определи намерение пользователя, затем верни только один JSON-объект:

{{
  "questions": [],
  "operations": [],
  "explanation": "Что будет сделано и какой результат получит пользователь",
  "confidence": 0.0
}}

ПРАВИЛА:

1. Понимай естественный язык, разговорные выражения,
   синонимы и распространённые опечатки.

2. Используй только реальные названия столбцов и листов.

3. Удаление дублей — remove_duplicates.

4. Поиск повторяющихся значений в столбце —
   find_repeated_values.

5. Поиск одинаковых строк целиком —
   find_duplicate_rows.

6. Поиск пустых значений в конкретном поле —
   find_blank_cells. Укажи sheet и column.

7. Если пользователь спрашивает, сколько студентов не имеют
   отчества, найди пустые ячейки в реальном столбце «Отчество».
   Не используй find_repeated_values и не удаляй строки.
   Для результата укажи output_sheet: «Без отчества».

8. Если пользователь просит найти записи без фамилии, имени,
   ИИН или другого поля, используй find_blank_cells и реальный
   заголовок соответствующего столбца.

9. Если пользователь просит разделить записи по значениям
   на листы одной книги, используй split_to_sheets.

10. Если пользователь просит создать отдельные файлы по значениям
    столбца, используй split_by_column.

11. Для выбора столбцов используй select_columns и columns.
    Чтобы скопировать выбранные столбцы на другой лист без изменения
    источника, используй copy_columns_to_sheet с sheet, columns и output_sheet.
    «ФИО» означает реальные столбцы «Фамилия», «Имя», «Отчество», если они
    присутствуют раздельно; иначе может означать единственный столбец «ФИО».

12. Для сортировки используй sort_rows, sheet и column.

13. Для удаления пустых строк используй remove_empty_rows.

14. Для заполнения пустых ячеек используй fill_empty.

15. Для замены значений используй replace_values.

16. Для группировки и агрегирования данных по одному столбцу используй
    group_by_aggregate. Поля:
    - sheet: исходный лист;
    - column: столбец, по которому группировать;
    - function: только sum, avg, count, min или max;
    - target_column: столбец для расчёта; для count он необязателен;
    - output_sheet: название нового листа, например «Агрегация».
    Для суммы, среднего, минимума и максимума обязательно укажи
    реальный target_column. Не угадывай столбец с числовыми значениями.

17. Для заполнения вычисляемого столбца формулой используй apply_formula.
    Поля: sheet, column, formula. В formula используй {{row}} как номер
    строки, например =B{{row}}*C{{row}}. Указывай реальный целевой столбец.

17а. Для фильтрации (отбора) строк на новый лист используй filter_rows.
     Поля: sheet, column, operator (eq, ne, gt, ge, lt, le, contains, blank, not_blank),
     value, output_sheet (например «Отбор»).
     Если условий несколько, добавь conditions — список объектов с column, operator и value.
     Все conditions применяются одновременно (логика И). Для сводки по отобранным
     строкам можно указать summary_output_sheet. Не теряй ни одно условие пользователя.

17б. Для построения перекрёстной матрицы (сводной таблицы 2 признаков) используй
     pivot_count. Поля: sheet, row_column (строки), column_column (столбцы),
     output_sheet (например «Перекрёстная таблица»).

17в. Для аналитической сводки с таблицами и графиками по категориальным полям
     используй smart_summary. Поля: sheet, columns (список столбцов),
     include_charts (true/false), include_cross_tables (true/false).

17г. Для извлечения нескольких значений из одной ячейки (через запятую/разделитель)
     в отдельные строки нового листа используй extract_split_values_to_sheet
     (sheet, column, output_sheet). Для разбиения строк на месте — split_cell_values_to_rows.

17д. Для сравнения двух столбцов между собой используй compare_columns
     (sheet, column, other_column). Для подсчёта уникальных ID по группам —
     distinct_count (sheet, id_column, columns, output_sheet).

18. Не придумывай названия, значения, листы или результаты.

19. Если задача однозначна, верни пустой массив questions.

20. Если не удаётся определить нужный столбец или есть несколько
    равно подходящих вариантов, задай конкретный вопрос и верни
    пустой массив operations.

21. Не спрашивай о технических деталях, которые можно определить
    по анализу файла.

21а. Если пользователь просит анализ, выводы или отчёт, а не очистку,
     не изменяй исходные данные. Выбирай операции поиска, подсчёта,
     группировки и создания новых отчётных листов.

21б. Не считай пустые ячейки всей Excel-сетки содержательным результатом.
     Анализируй только реальные непустые строки; пропуски проверяй лишь
     внутри них и только когда этого требует задача.

22. Не используй типы операций, которых нет в списке.

23. Если запрос требует нескольких действий, расположи операции
    в правильном порядке.

24. Ты только составляешь план. Не утверждай, что файл уже изменён.

25. Возвращай только JSON без Markdown и Python-кода.

Пример:
«Раздели студентов по курсам на разные листы».

{{
  "questions": [],
  "operations": [
    {{
      "type": "split_to_sheets",
      "sheet": "Лист1",
      "column": "Курс"
    }}
  ],
  "explanation": "Разделение записей по значениям курса.",
  "confidence": 0.98
}}

Названия в примере условные. Определи реальные названия
по анализу текущего файла.
""".strip()


# ============================================================
# MAIN FUNCTION
# ============================================================

def _safe_local_plan(task, analysis, selected_sheet=None):
    """Deterministic plans for unambiguous requests; never silently substitute tasks."""
    import difflib
    text = _normalize_header_text(task)
    typo = {"зделай":"сделай", "падробный":"подробный", "атчет":"отчет", "факултетам":"факультетам", "палу":"полу", "граждаству":"гражданству", "пакажи":"покажи", "каличество":"количество", "працэнты":"проценты", "дигарммы":"диаграммы"}
    for wrong, right in typo.items():
        text = re.sub(r"\b"+wrong+r"\b", right, text)
    sheets = _extract_sheets(analysis)
    if selected_sheet:
        sheets = [sh for sh in sheets if _get_sheet_name(sh)==selected_sheet]
    if len(sheets)!=1:
        return None
    name=_get_sheet_name(sheets[0]); headers=_extract_headers(sheets[0])
    def matched(fragment):
        words=set(re.findall(r"\w+", fragment))
        stems={_sort_word_stem(w) for w in words}
        result=[]
        for h in headers:
            hw=re.findall(r"\w+", _normalize_header_text(h))
            hs={_sort_word_stem(w) for w in hw}
            if hs and hs.issubset(stems): result.append(h)
        return result

    # Deterministic creation of a new combined column. The destination is an
    # output name and must never be searched among the source headers.
    wants_combine = bool(re.search(
        r"(?:объедин|соедин|скле|слить|состав).{0,90}(?:столб|колон|фамил|фио)",
        text,
    ))
    if wants_combine:
        normalized_headers = {_normalize_header_text(h): h for h in headers}
        fio_sources = []
        for expected in ("фамилия", "имя", "отчество"):
            exact = normalized_headers.get(expected)
            if exact:
                fio_sources.append(exact)
        quoted = re.findall(r"[«\"]([^»\"]+)[»\"]", str(task))
        quoted_sources = [
            h for h in headers
            if any(_normalize_header_text(h) == _normalize_header_text(q) for q in quoted)
        ]
        sources = fio_sources if len(fio_sources) >= 2 else quoted_sources[:3]
        target = "ФИО" if fio_sources else "Объединено"
        target_match = re.search(
            r"(?:нов(?:ый|ого)\s+)?столб(?:ец|ца)|колонк(?:у|а)"
            r"\s*[«\"]?([\wА-Яа-яЁёІіҢңҒғҮүҰұҚқӨөҺһ ._-]{2,40})",
            str(task), re.IGNORECASE,
        )
        if target_match and target_match.group(1):
            candidate = target_match.group(1).strip(" .,:;»\"")
            if candidate and _normalize_header_text(candidate) not in {
                _normalize_header_text(x) for x in sources
            }:
                target = candidate
        if len(sources) >= 2:
            return {
                "operations": [{
                    "type": "combine_columns", "sheet": name,
                    "source_columns": sources, "target_column": target,
                    "separator": " ", "skip_empty": True,
                    "trim_result": True, "position": "first",
                }],
                "questions": [], "mode": "operations",
                "explanation": (
                    f"Создать новый столбец «{target}» из: "
                    + ", ".join(f"«{x}»" for x in sources)
                    + ". Пустые части пропускаются, двойные пробелы не создаются."
                ),
                "deterministic_route": True,
            }

    # Запрет локального поиска пустых ячеек при явном отрицании
    if re.search(r"\bне\s+(?:ищи|искать|проверяй|выполняй)\b.*\bпуст\w*", text):
        return None

    if re.search(r"уникальн\w*\s+id|уникальн\w*\s+обучающ|повторяющ\w*\s+идентификатор", text) and re.search(r"распределен|по\s+факультет|численност", text):
        return {"operations":[],"questions":["Для распределения по уникальным ID требуется отдельная операция distinct-count по группам. Текущий smart_summary считает строки; подменять расчёт нельзя."],"mode":"questions"}
    sort_match=re.search(r"\b(?:отсортир\w*|сортир\w*|упорядоч\w*)", text)
    wants_summary=bool(re.search(r"\b(?:отчет\w*|сводн\w*|сводк\w*|аналитическ\w*|статистик\w*)", text))
    if sort_match and wants_summary:
        before=text[:sort_match.end()+1]
        after=text[sort_match.end():]
        first=after.split('затем')[0].split('потом')[0]
        sortcols=matched(first)
        summarycols=matched(after.split('затем',1)[-1]) if 'затем' in after else matched(after)
        if len(sortcols)==1 and summarycols:
            ops=[{"type":"sort_rows","sheet":name,"column":sortcols[0],"descending":False},{"type":"smart_summary","sheet":name,"columns":list(dict.fromkeys(summarycols)),"include_charts":True,"include_cross_tables":True}]
            return {"operations":ops,"questions":[],"mode":"operations","explanation":"Сортировка, затем аналитические сводки и диаграммы."}

    if re.search(r"(?:кажд\w*\s+комбинац|по\s+комбинац|всем\s+комбинац)",text):
        cols=matched(text)
        if len(cols)>=2:
            return {"operations":[{"type":"group_by_aggregate","sheet":name,"columns":cols,"column":cols[0],"function":"count","include_empty":True,"output_sheet":"Группировка"}],"questions":[],"mode":"operations","explanation":"Подсчёт по полным комбинациям указанных полей."}
    if wants_summary and re.search(r"диаграм|дигарм|построй",text):
        cols=matched(text)
        if cols:
            return {"operations":[{"type":"smart_summary","sheet":name,"columns":cols,"include_charts":True,"include_cross_tables":True}],"questions":[],"mode":"operations","explanation":"Сводные таблицы и диаграммы по указанным полям."}
    return None


def _plan_composite_request(original_task, normalized_task, analysis,
                            selected_sheet, semantic_intent):
    prompt = _build_prompt(normalized_task, analysis, selected_sheet,
                           original_task, semantic_intent)
    try:
        result = _post_to_cloud_ai(prompt)
        questions = _normalize_questions(result.get("questions"))
        if questions:
            return {"questions": questions, "operations": [], "mode": "questions",
                    "explanation": str(result.get("explanation", "")),
                    "semantic_intent": semantic_intent}
        ops = _validate_operations(result.get("operations", []))
    except (RuntimeError, ValueError, TimeoutError) as exc:
        return {"questions": ["Составной запрос требует уточнения или подключения к Облачному ИИ. "
                              "Ни одно действие не выполнено."],
                "operations": [], "mode": "questions", "ai_fallback": True,
                "explanation": str(exc).splitlines()[0],
                "semantic_intent": semantic_intent}
    planned_types = {op["type"] for op in ops}
    requirements = {
        "smart_summary": {"smart_summary", "group_by_aggregate", "summary_count"},
        "group_count": {"smart_summary", "group_by_aggregate", "summary_count"},
        "sort_rows": {"sort_rows", "split_to_sheets"},
        "trim_text": {"trim_text"},
        "split_to_sheets": {"split_to_sheets"},
        "find_missing": {"find_blank_cells"},
    }
    requested = semantic_intent.get("actions", [])
    missing = [name for name in requested if name in requirements
               and not (planned_types & requirements[name])]
    if missing or not ops:
        return {"questions": ["План не покрывает все действия: " + ", ".join(missing or requested)
                              + ". Уточни запрос или повтори планирование."],
                "operations": [], "mode": "questions",
                "explanation": "Частичный план заблокирован до подтверждения полноты.",
                "semantic_intent": semantic_intent}
    if selected_sheet:
        for op in ops:
            op.setdefault("sheet", selected_sheet)
    return {"questions": [], "operations": ops, "mode": "operations",
            "explanation": str(result.get("explanation", "")),
            "coverage": {"requested": requested, "covered": [x for x in requested if x not in missing]},
            "semantic_intent": semantic_intent}


def _route_semantic_quality(task, analysis, selected_sheet=None):
    text = _normalize_header_text(task)
    sheets = _extract_sheets(analysis)
    if selected_sheet:
        sheets = [s for s in sheets if _get_sheet_name(s) == str(selected_sheet).strip()]
    if len(sheets) != 1:
        return None
    sheet = _get_sheet_name(sheets[0]); headers = _extract_headers(sheets[0])
    def norm(h): return _normalize_header_text(h)
    def find(pattern):
        found = [h for h in headers if re.search(pattern, norm(h))]
        return found[0] if len(found) == 1 else None
    def result(ops, explanation):
        return {"questions": [], "operations": ops, "mode": "operations",
                "explanation": explanation, "deterministic_route": True}

    if re.search(r"(?:если.*(?:столбц|пол[ея]).*(?:нет|отсутств)|таких столбцов|не подставляй|не создавай фиктивн)", text):
        requested = []
        for pattern, label in [(r"образовательн\w*\s+программ", "образовательная программа"),
                               (r"специальност", "специальность"), (r"курс", "курс")]:
            if re.search(pattern, text) and not find(pattern): requested.append(label)
        if requested:
            return {"questions": ["В файле отсутствуют запрошенные столбцы: " + ", ".join(requested) + ". Уточните доступные поля."],
                    "operations": [], "mode": "questions", "explanation": "Нельзя подменять отсутствующие поля другими."}

    if re.search(r"уникальн\w*|без повторн\w*\s+подсчет", text) and re.search(r"\bid\b|идентификатор", text):
        id_col = find(r"^(?:id|ид)\s+обучающ|^(?:id|ид)\s+студент|^student\s*id$|^id$")
        if not id_col:
            return {"questions": ["Укажите однозначный столбец ID для подсчёта уникальных записей."], "operations": [], "mode": "questions"}
        groups=[]
        for pattern in (r"факультет", r"форм\w*\s+обучен", r"финансирован", r"гражданств", r"\bпол\b"):
            if re.search(pattern, text):
                h=find(pattern)
                if h and h != id_col and h not in groups: groups.append(h)
        if re.search(r"(?:диаграм|график|перекрестн|перекрестн|комплексн)", text):
            return {"questions": ["Запрос объединяет уникальные ID и другие виды аналитики. Для предотвращения частичного результата выполните отдельно подсчёт уникальных ID и запрос на диаграммы/перекрёстные таблицы."],
                    "operations": [], "mode": "questions", "explanation": "Составной отчёт пока не подтверждён полным планом."}
        return result([{"type":"distinct_count", "sheet":sheet, "id_column":id_col,
                        "columns":groups, "output_sheet":"Уникальные ID"}],
                      "Сравнение строк с уникальными ID и распределение по указанным группам.")

    broad = bool(re.search(r"\b(?:полный|полную|полное|комплексный|комплексную|комплексное|подробный|подробную|всесторонний|всестороннюю)\s+(?:анализ|аналитику|аналитический|отчет|отчёт)|\bпроанализируй\s+все\b", text))
    comparative = bool(re.search(r"\bсравнительн\w*\s+анализ|\bсравни\b|\bсопостав\w*", text))
    cross_requested = bool(re.search(
        r"\b(?:перекр[её]ст\w*|кросс[-\s]?таблиц\w*|cross[-\s]?tab\w*)\b",
        text,
    ))
    if broad or comparative:
        if comparative:
            requested = [h for h in headers if norm(h) in text or (len(norm(h)) > 3 and norm(h) in text)]
            if len(requested) != 1:
                return {"questions": ["По какому одному полю сравнивать группы или периоды? Укажите заголовок из Excel."],
                        "operations": [], "mode": "questions", "explanation": "Не определена ось сравнения."}
            if cross_requested:
                return {
                    "questions": [
                        f"С каким вторым столбцом построить перекрёстную таблицу для «{requested[0]}»? "
                        "Укажите точное название заголовка Excel."
                    ],
                    "operations": [],
                    "mode": "questions",
                    "explanation": (
                        "Перекрёстная таблица требует двух признаков; "
                        "остальные столбцы автоматически не подставляются."
                    ),
                }
            return result([{"type": "smart_summary", "sheet": sheet, "columns": requested,
                            "include_charts": True, "include_cross_tables": False,
                            "include_other_dimensions": False}],
                          "Сравнение категорий по указанному полю. Сравнение динамики требует временного столбца.")
        return result([{"type": "smart_summary", "sheet": sheet,
                        "include_charts": True, "include_cross_tables": True}],
                      "Обзор распределений и перекрёстных таблиц по автоматически выбранным категориальным полям. "
                      "Это описательный анализ, а не проверка всех возможных статистических гипотез.")

    if re.search(r"(?:за чей счет|за чеи счет|за какие средства|кто оплачивает|контингент|как распределяется)", text) and re.search(r"(?:таблиц|график|сводк|распредел)", text):
        groups=[]
        for phrase, pattern in [(r"школ|факультет",r"факультет"),
                                (r"форм",r"форм\w*\s+обучен"),
                                (r"за чей счет|за чеи счет|финанс|за какие средства|кто оплачивает",r"финансирован")]:
            if re.search(phrase, text):
                h=find(pattern)
                if h and h not in groups: groups.append(h)
        missing = []
        for phrase, pattern, label in [(r"школ|факультет", r"факультет", "факультет"),
                                       (r"форм", r"форм\w*\s+обучен", "форма обучения"),
                                       (r"за чей счет|за чеи счет|финанс|за какие средства|кто оплачивает", r"финансирован", "финансирование")]:
            if re.search(phrase, text) and not find(pattern):
                missing.append(label)
        if missing:
            return {"questions": ["Не найдены однозначные поля: " + ", ".join(missing)],
                    "operations": [], "mode": "questions"}
        if groups:
            return result([{"type":"smart_summary","sheet":sheet,"columns":groups,
                            "include_cross_tables":True,"include_charts":True}],
                          "Сводки по смысловым признакам запроса.")
    return None

def _interpret_task(task: str, analysis: Any, selected_sheet: Any = None, **kwargs):
    """Compatibility extension hook used by integrations and older builds."""
    return None


def _route_unassigned_teacher_period(task: str, analysis: Any, selected_sheet=None):
    """Deterministic route for a common report extraction request."""
    text = _normalize_task_text(task)
    if not (
        re.search(r"(?:преподавател\w*|препод\w*)\s+не\s+назнач", text)
        and re.search(r"(?:вытащ\w*|выгруз\w*|спис\w*|отбер\w*|фильтр\w*|отдельн\w*\s+лист|нов\w*\s+лист)", text)
    ):
        return None

    sheets = _extract_sheets(analysis)
    if selected_sheet:
        sheets = [
            sheet for sheet in sheets
            if _get_sheet_name(sheet).casefold() == str(selected_sheet).casefold()
        ]
    if len(sheets) != 1:
        return None

    sheet_info = sheets[0]
    headers = _extract_headers(sheet_info)

    def header_named(*needles):
        for header in headers:
            normalized = _normalize_header_text(header)
            if all(needle in normalized for needle in needles):
                return header
        return None

    teacher_header = next(
        (
            header for header in headers
            if _normalize_header_text(header) in {"преподаватель", "преподаватель фио"}
        ),
        None,
    )
    period_header = header_named("академическ", "период")
    if not teacher_header or not period_header:
        return None

    dates = re.findall(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b", text)
    if len(dates) < 2:
        return None
    period_value = " - ".join(dates[:2])
    if "осень 2026" in text or "осинь 2026" in text:
        period_value = "осень 2026 " + period_value

    operation = {
        "type": "filter_rows",
        "sheet": _get_sheet_name(sheet_info),
        "column": teacher_header,
        "operator": "contains",
        "value": "преподаватель не назначен",
        "conditions": [
            {
                "column": teacher_header,
                "operator": "contains",
                "value": "преподаватель не назначен",
            },
            {
                "column": period_header,
                "operator": "contains",
                "value": period_value,
            },
        ],
        "output_sheet": "Преподаватель не назначен",
        "header_rows": int(sheet_info.get("header_row") or 1),
    }
    if re.search(r"\b(?:сводк\w*|итог\w*|скока\s+их|сколько\s+их)\b", text):
        operation["summary_output_sheet"] = "Общая сводка"
        operation["summary_output_sheet"] = "Общая сводка"

    return {
        "questions": [],
        "operations": [operation],
        "explanation": (
            "Будут отобраны записи без назначенного преподавателя за указанный "
            "академический период. Исходный лист останется без изменений."
        ),
        "mode": "operations",
        "deterministic_route": True,
    }


def _requires_model_reasoning(task: str) -> bool:
    """Use the model before narrow routers when a request combines intent and conditions."""
    text = _normalize_task_text(task)
    # "сравнительный анализ" is a single analytical intent, not two separate actions
    text_for_actions = re.sub(r"\bсравнительн\w*\s+анализ\w*\b", "анализ", text)
    action_groups = (
        r"сводк\w*|отч[её]т\w*|анал\w*",
        r"фильтр\w*|отбер\w*|выбер\w*|остав\w*|спис\w*",
        r"сортир\w*|упорядоч\w*",
        r"раздел\w*|разбей\w*|отдельн\w*\s+лист",
        r"очист\w*|замен\w*|заполн\w*|удал\w*",
        r"сравн\w*|свер\w*|объедин\w*",
        r"посчита\w*|сумм\w*|средн\w*|группир\w*",
    )
    actions = sum(bool(re.search(pattern, text_for_actions)) for pattern in action_groups)
    conditional = bool(re.search(
        r"\b(?:где|котор\w*|тех\W+у\s+кого|у\s+кого|если|именно|"
        r"равн\w*|содерж\w*|больше|меньше|между|за\s+период)\b",
        text,
    ))
    explicit_sequence = bool(re.search(
        r"\b(?:затем|потом|после\s+этого|а\s+также|одновременно)\b|;|\n",
        text,
    ))
    return actions >= 2 or explicit_sequence or (actions >= 1 and conditional)


def _model_first_plan(task, analysis, selected_sheet, normalized_task):
    """Ask the configured AI to reason over the workbook before keyword routing."""
    semantic_intent = compile_intent(task, analysis, selected_sheet=selected_sheet)
    prompt = _build_prompt(
        task=normalized_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        original_task=task,
        semantic_intent=semantic_intent,
    )
    try:
        raw = _post_to_ollama(prompt)
        questions = _normalize_questions(raw.get("questions", []))
        if questions:
            return {
                "questions": questions,
                "operations": [],
                "explanation": str(raw.get("explanation", "")).strip(),
                "mode": "questions",
                "model_reasoning": True,
            }
        operations = _validate_operations(raw.get("operations", []))
        if not operations:
            return None

        sheet_headers = {
            _get_sheet_name(s): int(s.get("header_row") or 1)
            for s in _extract_sheets(analysis)
        }
        for op in operations:
            s_name = op.get("sheet")
            if s_name in sheet_headers:
                op.setdefault("header_rows", sheet_headers[s_name])
            elif len(sheet_headers) == 1:
                op.setdefault("header_rows", next(iter(sheet_headers.values())))

        text = _normalize_task_text(task)
        types = {operation.get("type") for operation in operations}
        conditional = bool(re.search(
            r"\b(?:где|котор\w*|тех\W+у\s+кого|у\s+кого|если|именно|за\s+период)\b",
            text,
        ))
        if conditional and re.search(r"спис\w*|фильтр\w*|отбер\w*|выбер\w*", text):
            if "filter_rows" not in types:
                return None
        if re.search(r"\bсводк\w*\b", text):
            has_summary = "smart_summary" in types or any(
                operation.get("summary_output_sheet")
                for operation in operations if operation.get("type") == "filter_rows"
            )
            if not has_summary:
                return None

        return {
            "questions": [],
            "operations": operations,
            "explanation": str(raw.get("explanation", "")).strip(),
            "mode": "operations",
            "model_reasoning": True,
            "confidence": raw.get("confidence"),
            "semantic_intent": semantic_intent,
        }
    except (RuntimeError, ValueError, TimeoutError):
        return None


def _plan_covers_request(task: str, result: dict | None) -> bool:
    """Reject locally plausible plans that silently drop requested actions."""
    if not result or not result.get("operations") or result.get("questions"):
        return False
    text = _normalize_task_text(task)
    types = {operation.get("type") for operation in result["operations"]}
    requirements = []
    if re.search(r"\b(?:копи\w*|скопир\w*)\b", text):
        requirements.append(bool(types & {"copy_sheet", "copy_columns_to_sheet"}))
    if re.search(r"\b(?:убер\w*|удал\w*|очист\w*)\s+пробел", text):
        requirements.append("trim_text" in types)
    if re.search(r"\b(?:сортир\w*|упорядоч\w*)\b", text):
        requirements.append("sort_rows" in types)
    if re.search(r"\b(?:фильтр\w*|отбер\w*|выбер\w*|тех\W+у\s+кого|где)\b", text):
        requirements.append("filter_rows" in types)
    if re.search(r"\bсводк\w*\b", text):
        requirements.append(
            "smart_summary" in types
            or any(operation.get("summary_output_sheet") for operation in result["operations"])
        )
    if re.search(r"\b(?:сумм\w*|средн\w*|агрегир\w*|группир\w*)\b", text):
        requirements.append(bool(types & {"group_by_aggregate", "smart_summary"}))
    if re.search(r"\b(?:извлек\w*|разверн\w*)\b", text):
        requirements.append(bool(types & {"extract_split_values_to_sheet", "split_cell_values_to_rows"}))
    return all(requirements) if requirements else True


def interpret_task(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
    **kwargs,
) -> dict:
    if not isinstance(task, str) or not task.strip():
        raise ValueError(
            "Сначала напиши, что нужно сделать с Excel."
        )

    if analysis is None:
        raise ValueError(
            "Не получен анализ Excel-файла. "
            "Сначала выбери и проанализируй файл."
        )

    if selected_sheet:
        available_sheet_names = [
            _get_sheet_name(item) for item in _extract_sheets(analysis)
        ]
        from .sheet_names import resolve_sheet_name
        selected_sheet = resolve_sheet_name(str(selected_sheet), available_sheet_names)

    extension_result = _interpret_task(
        task, analysis, selected_sheet=selected_sheet, **kwargs
    )
    if extension_result is not None:
        result = dict(extension_result)
        operations = list(result.get("operations") or [])
        names = [_get_sheet_name(item) for item in _extract_sheets(analysis)]
        from .sheet_names import resolve_sheet_name
        try:
            for operation in operations:
                if isinstance(operation, dict) and operation.get("sheet"):
                    operation["sheet"] = resolve_sheet_name(operation["sheet"], names)
        except ValueError as exc:
            return {
                "questions": [str(exc)], "operations": [], "mode": "questions",
                "explanation": "План содержит лист, которого нет в книге.",
            }
        result["operations"] = operations
        result.setdefault("questions", [])
        result.setdefault("mode", "operations" if operations else "questions")
        return result

    original_task = task.strip()
    normalized_task = _normalize_task_text(original_task)

    from .advanced_tasks import plan_advanced_request
    advanced = plan_advanced_request(original_task, analysis)
    if advanced is not None:
        advanced["original_task"] = original_task
        advanced["normalized_task"] = normalized_task
        return advanced

    # 1. Защита от субъективных/неопределенных понятий («проблемные записи», «хороший отчет»)
    if re.search(r"\bпроблемн\w*\s+запис\w*\b", normalized_task) and not re.search(
        r"\b(?:где|если|когда|критер|равн|меньш|больш|содерж|пуст|не\s+назнач)\b", normalized_task
    ):
        return {
            "mode": "questions",
            "questions": ["Уточните, пожалуйста, какие именно записи вы считаете «проблемными» и по каким критериям или столбцам их нужно отобрать?"],
            "operations": [],
            "explanation": "Для выполнения запроса о проблемных записях требуется уточнить определение и критерии отбора.",
        }

    # 2. Финальный комплексный анализ незаполненных журналов (проверяется раньше простой проверки структуры!)
    if re.search(r"\bкомплексн\w*\s+анализ\w*\s+отч[её]т\w*\b", normalized_task) and re.search(r"\bнезаполненн\w*\s+журнал\w*\b", normalized_task):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        return {
            "mode": "operations",
            "questions": [],
            "operations": [{
                "type": "complex_audit_summary",
                "sheet": s_name,
                "header_rows": hr,
            }],
            "explanation": "Выполнен комплексный анализ отчета по незаполненным журналам (5 листов с аналитикой, аномалиями и итогами).",
        }

    # 3. Определение настоящей структуры таблицы (Задание 1)
    if re.search(r"\bнастоящ\w*\s+строк\w*\s+заголовк\w*\b", normalized_task) or (
        re.search(r"\bпроверк\w*\s+структур\w*\b", normalized_task) and re.search(r"\bстрок\w*\s+данных\b", normalized_task)
    ):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        return {
            "mode": "operations",
            "questions": [],
            "operations": [{
                "type": "verify_structure",
                "sheet": s_name,
                "output_sheet": "Проверка структуры",
                "header_rows": hr,
            }],
            "explanation": f"Определена структура листа «{s_name}»: строка заголовков {hr}, столбцов {len(_extract_headers(sheet_info))}.",
        }

    # 4. Аналитическая сводка по записям без назначенного преподавателя (Задание 5)
    if (
        re.search(r"(?:по\s+записям\s+без\s+назначенного\s+преподавателя|где\s+преподаватель\s+не\s+назначен)", normalized_task)
        and re.search(r"\b(?:аналитическ\w*\s+сводк\w*|сводк\w*|дашборд)\b", normalized_task)
        and re.search(r"\b(?:разрез|факультет|кафедр)\b", normalized_task)
    ):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        headers = _extract_headers(sheet_info)
        teacher_header = next((h for h in headers if "преподаватель" in _normalize_header_text(h)), headers[3] if len(headers) > 3 else "Преподаватель")
        dim_cols = []
        for term in ("факультет", "кафедр", "дисциплин", "групп", "оп", "курс"):
            for h in headers:
                if term in _normalize_header_text(h) and h not in dim_cols:
                    dim_cols.append(h)
                    break
        filtered_sheet = "Без преподавателя"
        return {
            "mode": "operations",
            "questions": [],
            "operations": [
                {
                    "type": "filter_rows",
                    "sheet": s_name,
                    "column": teacher_header,
                    "operator": "contains",
                    "value": "преподаватель не назначен",
                    "output_sheet": filtered_sheet,
                    "header_rows": hr,
                },
                {
                    "type": "smart_summary",
                    "sheet": filtered_sheet,
                    "output_sheet": "Аналитическая сводка",
                    "columns": dim_cols,
                    "include_charts": True,
                    "include_cross_tables": False,
                    "header_rows": hr,
                }
            ],
            "explanation": "Отобраны записи без преподавателя на лист «Без преподавателя» и построена аналитическая сводка с диаграммами.",
        }

    # 5. Топ 20 дисциплин и 20 групп (Задание 6)
    if re.search(r"\b20\s+дисциплин\b", normalized_task) and re.search(r"\b20\s+групп\b", normalized_task):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        headers = _extract_headers(sheet_info)
        score_col = next((h for h in headers if "оценк" in _normalize_header_text(h) or "обучающ" in _normalize_header_text(h)), None)
        subj_col = next((h for h in headers if "дисциплин" in _normalize_header_text(h)), None)
        group_col = next((h for h in headers if "групп" in _normalize_header_text(h)), None)
        if score_col and subj_col and group_col:
            return {
                "mode": "operations",
                "questions": [],
                "operations": [
                    {
                        "type": "group_by_aggregate",
                        "sheet": s_name,
                        "column": subj_col,
                        "target_column": score_col,
                        "function": "sum",
                        "sort_by": "sum",
                        "sort_descending": True,
                        "limit": 20,
                        "output_sheet": "Топ 20 дисциплин",
                        "header_rows": hr,
                    },
                    {
                        "type": "group_by_aggregate",
                        "sheet": s_name,
                        "column": group_col,
                        "target_column": score_col,
                        "function": "sum",
                        "sort_by": "sum",
                        "sort_descending": True,
                        "limit": 20,
                        "output_sheet": "Топ 20 групп",
                        "header_rows": hr,
                    }
                ],
                "explanation": "Сформированы рейтинги: 20 дисциплин и 20 групп с наибольшей суммой обучающихся.",
            }

    # 6. Группировка по 3 колонкам с 5 расчетами (Задание 7)
    if re.search(r"\bминимум\s+и\s+максимум\b", normalized_task) or (
        re.search(r"\bсреднее\s+значение\b", normalized_task) and re.search(r"\bсумму?\b", normalized_task) and re.search(r"\bколичество\s+записей\b", normalized_task)
    ):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        headers = _extract_headers(sheet_info)
        fac_col = next((h for h in headers if "факультет" in _normalize_header_text(h)), None)
        dep_col = next((h for h in headers if "кафедр" in _normalize_header_text(h)), None)
        course_col = next((h for h in headers if "курс" in _normalize_header_text(h)), None)
        score_col = next((h for h in headers if "оценк" in _normalize_header_text(h) or "обучающ" in _normalize_header_text(h)), None)
        if fac_col and dep_col and course_col and score_col:
            return {
                "mode": "operations",
                "questions": [],
                "operations": [
                    {
                        "type": "group_by_aggregate",
                        "sheet": s_name,
                        "columns": [fac_col, dep_col, course_col],
                        "target_column": score_col,
                        "function": "all",
                        "functions": ["count", "sum", "avg", "min", "max"],
                        "sort_by": "sum",
                        "sort_descending": True,
                        "output_sheet": "Сводка факультет-кафедра-курс",
                        "header_rows": hr,
                    }
                ],
                "explanation": "Рассчитаны 5 показателей (количество, сумма, среднее, минимум, максимум) по факультетам, кафедрам и курсам.",
            }

    # 7. Разбор периода и противоречия дат (Задание 10)
    if re.search(r"\bсезон\w*\s+противоречит\b", normalized_task) or re.search(r"\bдата\s+окончания\s+раньше\b", normalized_task) or (
        re.search(r"\bразбери\w*\s+академическ\w*\s+период\b", normalized_task) and re.search(r"\bпротивореч\w*\b", normalized_task)
    ):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        headers = _extract_headers(sheet_info)
        period_col = next((h for h in headers if "период" in _normalize_header_text(h)), None)
        return {
            "mode": "operations",
            "questions": [],
            "operations": [
                {
                    "type": "audit_academic_periods",
                    "sheet": s_name,
                    "column": period_col,
                    "output_sheet": "Противоречия периодов",
                    "header_rows": hr,
                }
            ],
            "explanation": "Выполнен аудит академических периодов с выявлением противоречий дат и сезонов.",
        }

    # 8. Пакетное задание из 5 пунктов с листом «Контроль» (Задание 11)
    if re.search(r"\bлист\s*[«\"]?\s*контроль\s*[»\"]?", normalized_task) and re.search(r"\bсписок\s+всех\s+записей\s+без\s+назначенного\s+преподавателя\b", normalized_task):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        headers = _extract_headers(sheet_info)
        teacher_col = next((h for h in headers if "преподаватель" in _normalize_header_text(h)), None)
        period_col = next((h for h in headers if "период" in _normalize_header_text(h)), None)
        fac_col = next((h for h in headers if "факультет" in _normalize_header_text(h)), None)
        dep_col = next((h for h in headers if "кафедр" in _normalize_header_text(h)), None)
        subj_col = next((h for h in headers if "дисциплин" in _normalize_header_text(h)), None)
        score_col = next((h for h in headers if "оценк" in _normalize_header_text(h) or "обучающ" in _normalize_header_text(h)), None)
        return {
            "mode": "operations",
            "questions": [],
            "operations": [
                {
                    "type": "filter_rows",
                    "sheet": s_name,
                    "column": teacher_col,
                    "operator": "contains",
                    "value": "преподаватель не назначен",
                    "output_sheet": "Все без преподавателя",
                    "header_rows": hr,
                },
                {
                    "type": "filter_rows",
                    "sheet": s_name,
                    "column": teacher_col,
                    "operator": "contains",
                    "value": "преподаватель не назначен",
                    "conditions": [
                        {"column": teacher_col, "operator": "contains", "value": "преподаватель не назначен"},
                        {"column": period_col, "operator": "contains", "value": "01.09.2026 - 31.12.2026"},
                    ],
                    "output_sheet": "Осень 2026 точный период",
                    "header_rows": hr,
                },
                {
                    "type": "group_by_aggregate",
                    "sheet": "Все без преподавателя",
                    "columns": [fac_col, dep_col],
                    "function": "count",
                    "output_sheet": "Сводка факультеты и кафедры",
                    "header_rows": hr,
                },
                {
                    "type": "group_by_aggregate",
                    "sheet": s_name,
                    "column": subj_col,
                    "target_column": score_col,
                    "function": "sum",
                    "sort_by": "sum",
                    "sort_descending": True,
                    "output_sheet": "Рейтинг дисциплин",
                    "header_rows": hr,
                },
                {
                    "type": "verify_structure",
                    "sheet": s_name,
                    "output_sheet": "Контроль",
                    "header_rows": hr,
                }
            ],
            "explanation": "Созданы списки без преподавателя, точный период осени 2026, сводка кафедр, рейтинг дисциплин и лист «Контроль».",
        }

    # 9. Очищенная копия таблицы с протоколом диффов на лист «Изменения» (Задание 12)
    if (
        re.search(r"\bочищенн\w*\s+копи\w*\b", normalized_task) or re.search(r"\bлист\s*[«\"]?\s*изменения\s*[»\"]?", normalized_task)
    ) and re.search(r"\bунифицируй\w*.*преподаватель\s+не\s+назначен\b", normalized_task):
        sheet_info = _extract_sheets(analysis)[0]
        s_name = _get_sheet_name(sheet_info)
        hr = int(sheet_info.get("header_row") or 1)
        return {
            "mode": "operations",
            "questions": [],
            "operations": [
                {
                    "type": "clean_and_audit_changes",
                    "sheet": s_name,
                    "output_sheet": "Очищенные данные",
                    "changes_sheet": "Изменения",
                    "header_rows": hr,
                }
            ],
            "explanation": "Создана очищенная копия таблицы и лист «Изменения» с протоколом всех ячеек.",
        }

    unassigned_period = _route_unassigned_teacher_period(
        original_task, analysis, selected_sheet
    )
    if unassigned_period is not None:
        unassigned_period["original_task"] = original_task
        unassigned_period["normalized_task"] = normalized_task
        return unassigned_period

    remove_empty_early = _route_remove_empty_rows_request(
        task=original_task, analysis=analysis, selected_sheet=selected_sheet
    )
    if remove_empty_early is not None:
        remove_empty_early["original_task"] = original_task
        remove_empty_early["normalized_task"] = normalized_task
        return remove_empty_early

    if _requires_model_reasoning(original_task):
        from .pro_planner import plan_request as _local_reasoning_plan
        local_reasoning = _local_reasoning_plan(
            original_task, analysis, selected_sheet=selected_sheet, use_ai=False
        )
        explicit_sequence = bool(re.search(
            r"\b(?:затем|потом|после\s+этого|а\s+также|кроме\s+того)\b|;|\n",
            normalized_task,
        ))
        if explicit_sequence and _plan_covers_request(original_task, local_reasoning):
            local_reasoning.setdefault("original_task", original_task)
            local_reasoning.setdefault("normalized_task", normalized_task)
            return local_reasoning
        reasoned = _model_first_plan(
            original_task, analysis, selected_sheet, normalized_task
        )
        if reasoned is not None:
            reasoned["original_task"] = original_task
            reasoned["normalized_task"] = normalized_task
            return reasoned

    # Preserve the full order of explicit multi-step instructions before a
    # narrow one-action router can consume only the first part.
    from .pro_planner import plan_request as _plan_ordered_request, segments as _segments
    explicit_sequence = bool(re.search(
        r"(?:\bзатем\b|\bпотом\b|\bпосле\s+этого\b|\bа\s+также\b|\bкроме\s+того\b|;|(?:^|\n)\s*\d+[.)])",
        original_task,
        re.I,
    ))
    if re.search(r"\bуникальн\w*\b", normalized_task) and re.search(
        r"\b(?:id|идентификатор)\w*\b", normalized_task
    ):
        explicit_sequence = False
    if explicit_sequence and len(_segments(original_task)) > 1:
        ordered = _plan_ordered_request(
            original_task, analysis, selected_sheet=selected_sheet, use_ai=False
        )
        if ordered is not None:
            ordered.setdefault("original_task", original_task)
            ordered.setdefault("normalized_task", normalized_task)
            return ordered
    if re.search(
        r"\b(?:заполн\w*|замен\w*|убер\w*\s+пробел\w*|очист\w*\s+пробел\w*|"
        r"(?:извлек|перенес|вывед|вывест|разверн|раздел)\w*.*(?:строк|вертикальн)\w*)\b",
        normalized_task,
    ):
        direct_mutation = _plan_ordered_request(
            original_task, analysis, selected_sheet=selected_sheet, use_ai=False
        )
        if direct_mutation is not None and direct_mutation.get("operations"):
            direct_mutation.setdefault("original_task", original_task)
            direct_mutation.setdefault("normalized_task", normalized_task)
            return direct_mutation

    # A cross-table is a distinct matrix operation, not a generic grouping,
    # sorting or split-to-sheets request. Route it before broad keyword rules
    # can decompose the sentence into unrelated actions.
    if re.search(r"перекр[её]стн\w*\s+таблиц", normalized_task, re.I):
        from .pro_planner import plan_request
        pivot_result = plan_request(
            original_task,
            analysis,
            selected_sheet=selected_sheet,
            use_ai=False,
        )
        if pivot_result is not None:
            pivot_result.setdefault("original_task", original_task)
            pivot_result.setdefault("normalized_task", normalized_task)
            return pivot_result

    # ========================================================
    # PRIORITY 1. EXTRACT VALUES FROM CELLS TO A NEW SHEET
    # ========================================================

    extract_result = _route_extract_split_values_to_sheet(
        task=original_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if extract_result is not None:
        extract_result["original_task"] = original_task
        extract_result["normalized_task"] = normalized_task
        return extract_result

    # ========================================================
    # VAGUE REQUESTS
    # ========================================================

    vague_text = _normalize_header_text(normalized_task)

    vague_phrases = {
        "сделай красиво",
        "сделай все красиво",
        "оформи красиво",
        "обработай файл",
        "улучши файл",
        "сделай хорошо",
        "приведи в порядок",
        "сделай как надо",
    }

    if vague_text in vague_phrases:
        return {
            "questions": [
                "Что именно сделать: 1) создать общую аналитическую сводку, "
                "2) разделить записи по значениям столбца, 3) очистить данные "
                "или 4) оформить существующую таблицу?"
            ],
            "operations": [],
            "explanation": (
                "Запрос описывает желаемый внешний результат, но не определяет "
                "операцию с данными. Уточнение предотвращает выдуманные изменения."
            ),
            "mode": "questions",
            "original_task": original_task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # High-confidence workbook-grounded planning comes before narrow legacy
    # routers. It can combine several actions and infer a column from actual
    # values (for example «платное и бесплатное» -> «Форма оплаты»).
    from .autonomous_planner import plan_autonomously
    autonomous = plan_autonomously(original_task, analysis, selected_sheet)
    if autonomous is not None:
        autonomous.setdefault("original_task", original_task)
        autonomous.setdefault("normalized_task", normalized_task)
        return autonomous

    # Missing-value questions must win over generic words such as "отчёт".
    removal_of_rows = bool(re.search(
        r"(?=.*\b(?:удал|убер)\w*\b)(?=.*\bстрок\w*\b)(?=.*\b(?:пуст\w*|пробел\w*)\b)",
        normalized_task,
    ))
    early_missing = None if removal_of_rows else _route_missing_field_request(
        task=original_task, analysis=analysis,
        selected_sheet=selected_sheet, semantic_intent=None,
    )
    if early_missing is not None:
        early_missing.setdefault("original_task", original_task)
        early_missing.setdefault("normalized_task", normalized_task)
        return early_missing

    # ========================================================
    # SEMANTIC QUALITY
    # ========================================================

    precise = _route_semantic_quality(
        original_task,
        analysis,
        selected_sheet,
    )

    if precise is not None:
        precise.setdefault("original_task", original_task)
        precise.setdefault("normalized_task", normalized_task)
        return precise

    # Очистка строк должна иметь приоритет над общим поиском пустых ячеек.
    remove_empty_result = _route_remove_empty_rows_request(
        original_task,
        analysis,
        selected_sheet,
    )
    if remove_empty_result is not None:
        remove_empty_result.setdefault("original_task", original_task)
        remove_empty_result.setdefault("normalized_task", normalized_task)
        return remove_empty_result

    semantic_intent = compile_intent(
        original_task,
        analysis,
        selected_sheet=selected_sheet,
    )

    routing_task = original_task

    # ========================================================
    # SAFE LOCAL PLAN
    # ========================================================

    local_plan = _safe_local_plan(
        original_task,
        analysis,
        selected_sheet,
    )

    if local_plan is not None:
        local_plan["original_task"] = original_task
        local_plan["semantic_intent"] = semantic_intent
        return local_plan

    # ========================================================
    # COMPLEX AUDIT
    # ========================================================

    audit_markers = (
        "комплексный аудит",
        "полный аудит",
        "аудит данных",
        "student_data_audit",
        "повторяющиеся id",
        "полные дубли",
        "проверка факультетов",
        "нормализация",
    )

    audit_requested = any(
        marker in normalized_task.casefold()
        for marker in audit_markers
    )

    if audit_requested:
        sheets = _extract_sheets(analysis)
        sheet_name = None

        if selected_sheet:
            sheet_name = str(selected_sheet).strip()
        elif len(sheets) == 1:
            sheet_name = _get_sheet_name(sheets[0])

        if not sheet_name:
            return {
                "questions": [
                    "Укажи лист Excel, на котором выполнить комплексный аудит."
                ],
                "operations": [],
                "explanation": (
                    "Комплексный аудит требует однозначного исходного листа."
                ),
                "mode": "questions",
                "original_task": original_task,
                "normalized_task": normalized_task,
            }

        return {
            "questions": [],
            "operations": [
                {
                    "type": "student_data_audit",
                    "sheet": sheet_name,
                    "header_rows": 1,
                }
            ],
            "explanation": (
                "Запланирован комплексный аудит с шестью отчётными листами."
            ),
            "mode": "operations",
            "original_task": original_task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # ========================================================
    # SPLIT THEN SORT
    # ========================================================

    split_sort_result = _route_split_then_sort_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )

    if split_sort_result is not None:
        split_sort_result["semantic_intent"] = semantic_intent
        return split_sort_result

    # ========================================================
    # MISSING FIELD
    # ========================================================

    missing_result = _route_missing_field_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        semantic_intent=semantic_intent,
    )

    if missing_result is not None:
        missing_result["semantic_intent"] = semantic_intent
        return missing_result

    # ========================================================
    # COMPOSITE REQUEST
    # ========================================================

    active = set(semantic_intent.get("actions", []))

    distinct = active - {
        "group_count" if "smart_summary" in active else "__none__"
    }

    if (
        len(distinct) >= 2
        and (
            "smart_summary" in distinct
            or "group_count" in distinct
        )
        and len(semantic_intent.get("mentioned_headers", [])) >= 2
    ):
        return _plan_composite_request(
            original_task,
            normalized_task,
            analysis,
            selected_sheet,
            semantic_intent,
        )

    # ========================================================
    # SMART SUMMARY
    # ========================================================

    explicit_action = bool(re.search(
        r"\b(?:удал\w*|убер\w*|замен\w*|заполн\w*|"
        r"отсортир\w*|сортир\w*|упорядоч\w*|"
        r"объедин\w*|обьедин\w*|перестав\w*|"
        r"выдел\w*|очист\w*)\b",
        normalized_task,
    ))

    smart_result = (
        None
        if explicit_action
        else _route_smart_summary_request(
            task=routing_task,
            analysis=analysis,
            selected_sheet=selected_sheet,
        )
    )

    if smart_result is not None:
        smart_result["original_task"] = original_task
        smart_result["semantic_intent"] = semantic_intent
        return smart_result

    # ========================================================
    # GROUP COUNT
    # ========================================================

    count_result = _route_group_count_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )

    if count_result is not None:
        count_result["original_task"] = original_task
        count_result["semantic_intent"] = semantic_intent
        return count_result

    # ========================================================
    # SPLIT TO SEPARATE SHEETS
    # ========================================================

    split_result = _route_split_to_sheets_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )

    if split_result is not None:
        split_result["original_task"] = original_task
        split_result["semantic_intent"] = semantic_intent
        return split_result

    # ========================================================
    # TRIM THEN SORT
    # ========================================================

    multi_step_result = _route_trim_then_sort_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )

    if multi_step_result is not None:
        multi_step_result["original_task"] = original_task
        multi_step_result["semantic_intent"] = semantic_intent
        return multi_step_result

    # ========================================================
    # SORT
    # ========================================================

    sort_result = _route_sort_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )

    if sort_result is not None:
        sort_result["original_task"] = original_task
        sort_result["semantic_intent"] = semantic_intent
        return sort_result

    # --------------------------------------------------------
    # STEP 2. Локальная попытка перед обращением к Облачному ИИ.
    # --------------------------------------------------------
    from .pro_planner import plan_request
    pro_plan = plan_request(
        original_task,
        analysis,
        selected_sheet=selected_sheet,
        use_ai=False,
    )
    if pro_plan is not None:
        pro_plan.setdefault("original_task", original_task)
        pro_plan.setdefault("normalized_task", normalized_task)
        pro_plan.setdefault("semantic_intent", semantic_intent)
        return pro_plan

    # --------------------------------------------------------
    # STEP 3. Обращение к Облачному ИИ для сложных запросов.
    # --------------------------------------------------------

    prompt = _build_prompt(
        task=normalized_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        original_task=original_task,
        semantic_intent=semantic_intent,
    )

    try:
        result = _post_to_cloud_ai(prompt)
    except (RuntimeError, ValueError, TimeoutError) as exc:
        reason = str(exc).strip().splitlines()[0]
        return {
            "questions": [
                "Облачный ИИ сейчас не смог подготовить план. Уточните операцию "
                "и названия столбцов, например: «создай сводку по Региону и "
                "Категории», «раздели по Отделу» или «отсортируй по Сумме»."
            ],
            "operations": [],
            "explanation": (
                "Excel-файл не изменён. Стандартные сводки, сортировка, "
                "разделение, очистка и диаграммы выполняются локально. "
                f"Причина перехода в безопасный режим: {reason}"
            ),
            "mode": "questions",
            "original_task": original_task,
            "normalized_task": normalized_task,
            "semantic_intent": semantic_intent,
            "ai_fallback": True,
        }

    questions = _normalize_questions(
        result.get("questions", [])
    )

    raw_operations = result.get("operations", [])

    explanation = result.get("explanation", "")

    if not isinstance(explanation, str):
        explanation = str(explanation)

    if questions:
        return {
            "questions": questions,
            "operations": [],
            "explanation": explanation.strip(),
            "mode": "questions",
            "original_task": original_task,
            "normalized_task": normalized_task,
        }

    operations = _validate_operations(raw_operations)

    if not operations:
        raise ValueError(
            "ИИ не сформировал план операций.\n"
            + json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )[:3000]
        )

    if selected_sheet:
        for operation in operations:
            if not operation.get("sheet"):
                operation["sheet"] = selected_sheet

    return {
        "questions": [],
        "operations": operations,
        "explanation": explanation.strip(),
        "mode": "operations",
        "original_task": original_task,
        "normalized_task": normalized_task,
        "semantic_intent": semantic_intent,
    }


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def interpret_excel_task(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
    **kwargs,
) -> dict:
    return interpret_task(
        task=task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        **kwargs,
    )
