
import json
import re
import urllib.error
import urllib.request
from typing import Any

from .settings import (
    CONTEXT_SIZE,
    MAX_ANALYSIS_CHARS,
    OLLAMA_TAGS_URL,
    OLLAMA_URL,
    PREFERRED_MODEL,
    REQUEST_TIMEOUT,
)
from .intent_compiler import compile_intent


# ============================================================
# BAHONIQ — EXCEL AI INTERPRETER
# ============================================================

OLLAMA_MODEL = PREFERRED_MODEL


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
    "student_data_audit",
    "group_by_aggregate",
    "smart_summary",
    "apply_formula",
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

    # Анализ иногда содержит информацию об одном листе.
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

    # Иногда заголовки присутствуют в первой строке preview.
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
# DETERMINISTIC INTENT ROUTING
# ============================================================

def _detect_missing_field_request(task: str) -> bool:
    """
    Определяет просьбы найти записи, где отсутствует поле.

    Не считает обычный запрос об удалении пустых строк
    запросом о пропущенном значении конкретного поля.
    """
    text = _normalize_header_text(task)

    field_terms = (
        r"отчеств\w*",
        r"фамили\w*",
        r"имен\w*",
        r"иин",
        r"email",
        r"e mail",
        r"почт\w*",
        r"телефон\w*",
        r"номер\w*",
        r"дат\w*",
        r"курс\w*",
        r"специальност\w*",
        r"факультет\w*",
        r"групп\w*",
    )

    field_pattern = r"(?:" + "|".join(field_terms) + r")"

    missing_patterns = (
        r"\bне\s+(?:имеют|имеет|указан\w*|заполнен\w*|содерж\w*)\b",
        r"\bбез\s+" + field_pattern,
        r"\bотсутств\w*",
        r"\bпропущен\w*",
        r"\bнезаполнен\w*",
        r"\bпуст\w*",
        r"\bнет\s+" + field_pattern,
        r"\bсколько\b.*\bне\b",
        r"\bнайди\b.*\bне\b",
        r"\bпокажи\b.*\bне\b",
        r"\bсписок\b.*\bбез\b",
    )

    has_field = re.search(field_pattern, text, flags=re.IGNORECASE)
    has_missing_intent = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in missing_patterns
    )

    return bool(has_field and has_missing_intent)


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

    # Сначала проверяем наиболее специфичные поля.
    patterns = [
        (r"\bотчеств\w*", "отчество"),
        (r"\bфамили\w*", "фамилия"),
        (r"\bимени\b|\bимя\b", "имя"),
        (r"\bиин\b", "иин"),
        (r"\bemail\b|\be mail\b|\bэлектронн\w+\s+почт\w*", "email"),
        (r"\bтелефон\w*\b", "телефон"),
        (r"\bкурс\w*\b", "курс"),
        (r"\bгрупп\w*\b", "группа"),
        (r"\bспециальност\w*\b|\bобразовательн\w+\s+программ\w*", "специальность"),
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

    # Если нет точного совпадения, используем ограниченное
    # сопоставление по словам, но не угадываем при нескольких вариантах.
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


def _route_missing_field_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    """
    Детерминированная обработка понятных запросов о пропущенном поле.

    Возвращает None, если задача не относится к этому типу.
    """
    if not _detect_missing_field_request(task):
        return None

    requested_field = _requested_field(task)

    if not requested_field:
        return {
            "questions": [
                "Какое именно поле нужно проверить на отсутствие значений?"
            ],
            "operations": [],
            "explanation": "Нужно уточнить проверяемое поле.",
            "mode": "questions",
            "original_task": task,
        }

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
        }

    if selected_sheet:
        selected_name = str(selected_sheet).strip()
        matching_sheets = [
            sheet for sheet in sheets
            if _get_sheet_name(sheet) == selected_name
        ]

        if matching_sheets:
            sheets_to_check = matching_sheets
        else:
            sheets_to_check = sheets
    else:
        sheets_to_check = sheets

    candidates = []

    for sheet_info in sheets_to_check:
        sheet_name = _get_sheet_name(sheet_info)
        headers = _extract_headers(sheet_info)

        for header in _match_field_header(requested_field, headers):
            candidates.append({
                "sheet": sheet_name,
                "column": header,
            })

    if not candidates:
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
            f"Не найден однозначный столбец для поля «{requested_field}»."
        )

        if details:
            question += (
                "\nДоступные заголовки:\n"
                + details
                + "\nУкажи, какой из этих столбцов нужно проверить."
            )
        else:
            question += (
                "\nУточни точное название столбца в Excel."
            )

        return {
            "questions": [question],
            "operations": [],
            "explanation": "Не найден подходящий заголовок.",
            "mode": "questions",
            "original_task": task,
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
                + "\nУкажи, какой столбец нужно проверить."
            ],
            "operations": [],
            "explanation": "Требуется уточнить лист или столбец.",
            "mode": "questions",
            "original_task": task,
        }

    match = candidates[0]

    output_names = {
        "отчество": "Без отчества",
        "фамилия": "Без фамилии",
        "имя": "Без имени",
        "иин": "Без ИИН",
        "email": "Без email",
        "телефон": "Без телефона",
        "курс": "Без курса",
        "группа": "Без группы",
        "специальность": "Без специальности",
        "факультет": "Без факультета",
    }

    operation = {
        "type": "find_blank_cells",
        "sheet": match["sheet"],
        "column": match["column"],
        "output_sheet": output_names.get(
            requested_field,
            "Записи без значения",
        ),
        "missing_field": requested_field,
    }

    return {
        "questions": [],
        "operations": [operation],
        "explanation": (
            f"Проверка пустых значений в столбце "
            f"«{match['column']}» на листе «{match['sheet']}». "
            f"Результат: «{operation['output_sheet']}»."
        ),
        "mode": "operations",
        "original_task": task,
        "normalized_task": _normalize_task_text(task),
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
        chosen = [s for s in sheets if _get_sheet_name(s) == selected]
        if chosen:
            sheets = chosen
    if not sheets:
        return None

    # Если лист явно выбран — выше оставлен только он; иначе сохраняем
    # прежнее поведение интерпретатора и берём первый доступный лист.
    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)
    split_text = text[:sort_match.start()]
    sort_text = text[sort_match.end():]

    def candidates(fragment: str) -> list[str]:
        task_stems = {
            _sort_word_stem(word)
            for word in re.findall(r"\w+", fragment, flags=re.UNICODE)
            if len(word) >= 3
        }
        result = []
        for header in headers:
            normalized_header = _normalize_header_text(header)
            if normalized_header == "имя" and re.search(
                r"\b(?:имя|имени)\b", fragment
            ):
                result.append(header)
                continue
            header_stems = {
                _sort_word_stem(word)
                for word in re.findall(
                    r"\w+", normalized_header, flags=re.UNICODE
                ) if len(word) >= 3
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
        sort_text,
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
    """Recognise a two-step cleanup-and-sort instruction.

    Column mentions before the sorting clause belong to trim_text; only the
    text after the sorting verb is considered when choosing the sort column.
    """
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
        chosen = [s for s in sheets if _get_sheet_name(s) == selected]
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
            for word in re.findall(r"\w+", fragment, flags=re.UNICODE)
            if len(word) >= 3
        }
        matches = []
        for header in headers:
            normalized_header = _normalize_header_text(header)
            # Short Russian words do not stem reliably with the generic
            # suffix helper ("имя" / "имени"), so handle this common header
            # by its grammatical forms.
            if normalized_header == "имя" and re.search(
                r"\b(?:имя|имени)\b", fragment
            ):
                matches.append(header)
                continue
            words = [
                word for word in re.findall(
                    r"\w+", normalized_header, flags=re.UNICODE
                ) if len(word) >= 3
            ]
            header_stems = {_sort_word_stem(word) for word in words}
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
    task: str, analysis: Any, selected_sheet: Any = None,
) -> dict | None:
    """Универсальная сводка и разделение по реальным заголовкам книги."""
    normalized_task = _normalize_task_text(task)
    text = _normalize_header_text(normalized_task)
    wants_summary = bool(re.search(
        r"\b(?:общ\w*\s+сводк\w*|сводк\w*|итог\w*|статистик\w*|"
        r"посчитай|сколько|распределени\w*|дашборд\w*|dashboard)\b", text
    ))
    wants_split = bool(re.search(
        r"\b(?:раздели\w*|разбей\w*|отдельн\w*\s+лист\w*|"
        r"разн\w*\s+лист\w*)\b", text
    ))
    if not (wants_summary or wants_split):
        return None

    sheets = _extract_sheets(analysis)
    if selected_sheet:
        selected = str(selected_sheet).strip()
        sheets = [item for item in sheets if _get_sheet_name(item) == selected] or sheets
    if len(sheets) != 1:
        return None
    sheet_info = sheets[0]; sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)
    task_stems = {
        _sort_word_stem(word) for word in re.findall(r"\w+", text, flags=re.UNICODE)
        if len(word) >= 3
    }
    matched = []
    for header in headers:
        words = [
            _sort_word_stem(word)
            for word in re.findall(r"\w+", _normalize_header_text(header), flags=re.UNICODE)
            if len(word) >= 3
        ]
        if words and all(word in task_stems for word in words):
            matched.append(header)

    operations = []
    if wants_summary:
        operation = {
            "type": "smart_summary", "sheet": sheet_name,
            "output_sheet": "Общая сводка", "header_rows": 1,
            "include_cross_tables": True, "include_charts": True,
        }
        if matched:
            operation["columns"] = matched
        operations.append(operation)
    if wants_split:
        if not matched:
            return {
                "questions": [
                    "По каким столбцам разделить записи? Укажите точные названия заголовков Excel."
                ], "operations": [], "mode": "questions",
                "explanation": "Для разделения требуется однозначный признак.",
                "original_task": task, "normalized_task": normalized_task,
                "deterministic_route": True,
            }
        operations.append({
            "type": "split_to_sheets", "sheet": sheet_name,
            "columns": matched, "header_rows": 1,
        })

    column_text = ", ".join(f"«{name}»" for name in matched)
    explanation = []
    if wants_summary:
        explanation.append(
            "Будет создана общая сводка, отдельные распределения, доли, рейтинги, "
            "диаграммы и перекрёстные таблицы" +
            (f" по столбцам {column_text}." if matched else " по автоматически найденным разрезам.")
        )
    if wants_split:
        explanation.append(f"Записи будут распределены по отдельным листам по комбинациям {column_text}.")
    return {
        "questions": [], "operations": operations,
        "explanation": " ".join(explanation), "mode": "operations",
        "original_task": task, "normalized_task": normalized_task,
        "deterministic_route": True,
    }

def _route_group_count_request(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict | None:
    """Builds one combined student-count summary and, when requested,
    partitions the same source rows by the complete set of grouping fields.
    """
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
        matches = [s for s in sheets if _get_sheet_name(s) == selected]
        if matches:
            sheets = matches

    if len(sheets) != 1:
        return None

    sheet_info = sheets[0]
    sheet_name = _get_sheet_name(sheet_info)
    headers = _extract_headers(sheet_info)

    # Поля идут в смысловом порядке, а не в порядке столбцов Excel.
    # Это важно: расположение столбца в начале таблицы не должно
    # заставлять BahonIQ игнорировать остальные признаки группировки.
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
        if re.search(item["task_pattern"], text, flags=re.IGNORECASE)
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
                    f"Для признака «{dimension['key']}» найдено несколько столбцов: "
                    + ", ".join(f"«{value}»" for value in matches)
                    + ". Укажи, какой столбец использовать."
                ],
                "operations": [],
                "explanation": "Нельзя безопасно выбрать один из нескольких столбцов.",
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
                "Не удалось однозначно найти в Excel столбцы для признаков: "
                + ", ".join(f"«{name}»" for name in missing_dimensions)
                + ". Проверь названия заголовков или уточни их."
            ],
            "operations": [],
            "explanation": "Для сводки и разделения нужны все указанные признаки.",
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

    cols_formatted = ", ".join(f"«{column}»" for column in resolved_columns)
    explanation = (
        "Будет создана одна общая сводка с количеством студентов "
        f"по комбинациям признаков: {cols_formatted}."
    )
    if has_split:
        explanation += (
            " Дополнительно каждый студент будет распределён на отдельный лист "
            "по полной комбинации этих же признаков, а не только по первому столбцу."
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
    """Обрабатывает запросы на разделение по листам и составление сводок."""
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

    # 1. Находим ВСЕ столбцы из заголовков Excel, упомянутые в запросе пользователя
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

    # 2. Если пользователь просил сводку/статистику, добавляем операции подсчета
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

    # 3. Добавляем операцию разделения на листы по первому/основному столбцу
    split_column = matched_columns[0]
    operations.append({
        "type": "split_to_sheets",
        "sheet": sheet_name,
        "column": split_column,
        "header_rows": 1,
    })

    # Формируем человекочитаемое описание цепочки действий
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
    """Упрощённо нормализует окончания слов для русских заголовков."""
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
    """
    Создаёт план простой сортировки без обращения к Ollama.
    Если запрос нельзя определить однозначно, возвращает None
    или задаёт уточняющий вопрос.
    """
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

    # Не перехватываем отрицательные или отменяющие команды.
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

    # Если пользователь выбрал лист, в первую очередь работаем с ним.
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

    # Слова из запроса сопоставляем с заголовками,
    # учитывая распространённые русские окончания.
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

            # Для заголовка из нескольких слов достаточно совпадения
            # хотя бы одного слова. Если подходят несколько столбцов,
            # ниже будет запрошено уточнение.
            if matched_words:
                candidates.append({
                    "sheet": sheet_name,
                    "column": header,
                })

    # Убираем повторы одной пары «лист — столбец».
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
        # Не угадываем столбец: оставляем запрос языковой модели.
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
        raise ValueError("Ollama вернула пустой ответ.")

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
            "В ответе Ollama не найден JSON-объект:\n"
            + cleaned[:1500]
        )

    try:
        result, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Не удалось разобрать JSON от Ollama: {exc}\n"
            + cleaned[:1500]
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("Ответ Ollama должен быть JSON-объектом.")

    return result


def _compact_analysis(analysis: Any) -> str:
    if isinstance(analysis, str):
        text = analysis
    else:
        # Exclude statistics that distract the model from the user's actual
        # data. Keep exact names, representative values and semantic profiles.
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
                    "headers": sheet.get("headers", []),
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
# OLLAMA REQUEST
# ============================================================

def _available_models() -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return [
        item.get("name") for item in data.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]


def _select_model() -> str:
    models = _available_models()
    if not models or OLLAMA_MODEL in models:
        return OLLAMA_MODEL
    # Prefer the strongest installed Qwen model instead of failing merely
    # because the configured tag is absent.
    qwen = [name for name in models if "qwen" in name.casefold()]
    return qwen[0] if qwen else models[0]

def _post_to_ollama(prompt: str) -> dict:
    payload = {
        "model": _select_model(),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты — интеллектуальный помощник BahonIQ Excel AI. "
                    "Понимай естественный русский язык, разговорные "
                    "выражения, синонимы и очевидные опечатки. "
                    "Выбирай реальные листы и столбцы из анализа. "
                    "Не выдумывай отсутствующие заголовки и данные. "
                    "Не используй find_repeated_values для поиска "
                    "пустых или отсутствующих значений. "
                    "Если пользователь ищет записи без значения "
                    "в конкретном поле, используй find_blank_cells. "
                    "Не удаляй данные, если пользователь не просит "
                    "их удалить. Для группировки и расчётов используй "
                    "group_by_aggregate, для формул по строкам — apply_formula. "
                    "Формула должна содержать плейсхолдер {row}, например "
                    "=B{row}*C{row}. При неоднозначности задай вопрос. "
                    "Возвращай только корректный JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "stream": False,
        "format": "json",
        "keep_alive": -1,  # Удерживает модель в VRAM и предотвращает холодный старт
        "options": {
            "temperature": 0,
            "top_p": 0.1,
            "num_ctx": CONTEXT_SIZE,
        },
    }

    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            response_text = response.read().decode("utf-8")

    except urllib.error.HTTPError as exc:
        details = exc.read().decode(
            "utf-8",
            errors="replace",
        )
        raise RuntimeError(
            f"Ollama HTTP {exc.code}: {details[:1200]}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Не удалось подключиться к Ollama. "
            "Проверь, запущена ли Ollama.\n"
            f"Адрес: {OLLAMA_URL}\n"
            f"Причина: {getattr(exc, 'reason', exc)}"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            f"Ollama не ответила за {REQUEST_TIMEOUT} секунд."
        ) from exc

    try:
        envelope = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Ollama вернула некорректный ответ API:\n"
            + response_text[:1500]
        ) from exc

    content = envelope.get("message", {}).get("content", "")

    if not content:
        raise ValueError(
            "Ollama не вернула содержимое ответа:\n"
            + response_text[:1500]
        )

    return _extract_json(content)


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

    # Нормализуем параметры новых операций, не затрагивая старые типы.
    if operation_type == "group_by_aggregate":
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

    original_task = task.strip()
    normalized_task = _normalize_task_text(original_task)

    # Не отправляем заведомо неопределённые короткие пожелания в Ollama.
    # Они не описывают операцию и раньше могли надолго занимать модель.
    vague_text = _normalize_header_text(normalized_task)
    vague_phrases = {
        "сделай красиво", "сделай все красиво", "оформи красиво",
        "обработай файл", "улучши файл", "сделай хорошо",
        "приведи в порядок", "сделай как надо",
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

    semantic_intent = compile_intent(
        original_task,
        analysis,
        selected_sheet=selected_sheet,
    )
    routing_task = original_task

    # --------------------------------------------------------
    # STEP 1. Complex student-data audit has priority over the
    # single-field missing-data shortcut. Otherwise phrases like
    # "find all blanks" can hijack the entire multi-part request.
    # --------------------------------------------------------
    audit_markers = (
        "комплексный аудит", "полный аудит", "аудит данных",
        "student_data_audit", "повторяющиеся id", "полные дубли",
        "проверка факультетов", "нормализация",
    )
    audit_requested = any(marker in normalized_task.casefold() for marker in audit_markers)
    if audit_requested:
        sheets = _extract_sheets(analysis)
        sheet_name = None
        if selected_sheet:
            sheet_name = str(selected_sheet).strip()
        elif len(sheets) == 1:
            sheet_name = _get_sheet_name(sheets[0])
        if not sheet_name:
            return {
                "questions": ["Укажи лист Excel, на котором выполнить комплексный аудит."],
                "operations": [],
                "explanation": "Комплексный аудит требует однозначного исходного листа.",
                "mode": "questions",
                "original_task": original_task,
                "normalized_task": normalized_task,
            }
        return {
            "questions": [],
            "operations": [{"type": "student_data_audit", "sheet": sheet_name, "header_rows": 1}],
            "explanation": "Запланирован комплексный аудит с шестью отчётными листами.",
            "mode": "operations",
            "original_task": original_task,
            "normalized_task": normalized_task,
            "deterministic_route": True,
        }

    # --------------------------------------------------------
    # STEP 1. Fast routing — GROUPED COUNT / SUMMARY (Имеет приоритет)
    # --------------------------------------------------------
    smart_result = _route_smart_summary_request(
        task=routing_task, analysis=analysis, selected_sheet=selected_sheet,
    )
    if smart_result is not None:
        smart_result["original_task"] = original_task
        smart_result["semantic_intent"] = semantic_intent
        return smart_result

    count_result = _route_group_count_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if count_result is not None:
        count_result["original_task"] = original_task
        count_result["semantic_intent"] = semantic_intent
        return count_result

    # Destination wording ("на разных листах") has priority over the verb
    # "сортировать": in this context the user wants partitioning, not ordering.
    split_result = _route_split_to_sheets_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if split_result is not None:
        split_result["original_task"] = original_task
        split_result["semantic_intent"] = semantic_intent
        return split_result

    multi_step_result = _route_trim_then_sort_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if multi_step_result is not None:
        multi_step_result["original_task"] = original_task
        multi_step_result["semantic_intent"] = semantic_intent
        return multi_step_result

    count_result = _route_group_count_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if count_result is not None:
        count_result["original_task"] = original_task
        count_result["semantic_intent"] = semantic_intent
        return count_result

    # Destination wording ("на разных листах") has priority over the verb
    # "сортировать": in this context the user wants partitioning, not ordering.
    split_result = _route_split_to_sheets_request(
        task=routing_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
    )
    if split_result is not None:
        split_result["original_task"] = original_task
        split_result["semantic_intent"] = semantic_intent
        return split_result


    # Быстрая сортировка без вызова Ollama.
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
    # STEP 2. Use Ollama for other natural-language requests.
    # --------------------------------------------------------

    prompt = _build_prompt(
        task=normalized_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        original_task=original_task,
        semantic_intent=semantic_intent,
    )

    result = _post_to_ollama(prompt)

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
