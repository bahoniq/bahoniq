import json
import re
import urllib.error
import urllib.request
from typing import Any


# ============================================================
# BAHONIQ — EXCEL AI INTERPRETER
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

REQUEST_TIMEOUT = 180
MAX_ANALYSIS_CHARS = 12000


# ============================================================
# OPERATIONS SUPPORTED BY THE EXCEL EXECUTOR
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
}


TYPE_ALIASES = {
    # Empty rows
    "delete_empty_rows": "remove_empty_rows",
    "remove_blank_rows": "remove_empty_rows",
    "delete_blank_rows": "remove_empty_rows",

    # Duplicates
    "deduplicate": "remove_duplicates",
    "deduplicate_rows": "remove_duplicates",
    "drop_duplicates": "remove_duplicates",
    "delete_duplicates": "remove_duplicates",
    "remove_duplicate": "remove_duplicates",

    # Fill empty cells
    "fill_blanks": "fill_empty",
    "fill_empty_cells": "fill_empty",
    "fill_missing": "fill_empty",

    # Text
    "trim": "trim_text",
    "strip": "trim_text",
    "clean_text": "trim_text",

    # Replace
    "replace": "replace_values",
    "replace_text": "replace_values",
    "find_replace": "replace_values",

    # Highlight
    "highlight_blanks": "highlight_empty",
    "highlight_blank_cells": "highlight_empty",

    # Find repeated values
    "find_duplicates": "find_repeated_values",
    "find_repeated": "find_repeated_values",

    # Blank cells
    "find_blanks": "find_blank_cells",
    "find_empty_cells": "find_blank_cells",

    # Sorting
    "sort": "sort_rows",
    "sort_data": "sort_rows",

    # Columns
    "reorder": "reorder_columns",
    "move_columns": "reorder_columns",
    "choose_columns": "select_columns",
    "keep_columns": "select_columns",

    # Split into separate files
    "split": "split_by_column",
    "split_column": "split_by_column",
    "split_into_files": "split_by_column",
    "split_by_value": "split_by_column",

    # Split into sheets in the same workbook
    "split_into_sheets": "split_to_sheets",
    "split_by_course": "split_to_sheets",
    "split_by_value_to_sheets": "split_to_sheets",
    "split_column_to_sheets": "split_to_sheets",
    "split_by_group_to_sheets": "split_to_sheets",

    # Merge
    "merge": "merge_sheets",
    "combine_sheets": "merge_sheets",

    # Summary
    "count": "summary_count",
    "count_rows": "summary_count",
    "statistics": "summary_count",

    # Validation
    "validate": "validate_values",
    "check_values": "validate_values",

    # Compare
    "compare": "compare_columns",
    "compare_values": "compare_columns",
}


# ============================================================
# COMMON RUSSIAN TYPOS AND SYNONYMS
# ============================================================

# These replacements apply to task wording, not workbook data.
# The original task is preserved separately.
WORD_REPLACEMENTS = {
    # Duplicates
    "дудли": "дубли",
    "дублики": "дубли",
    "дублекаты": "дубликаты",
    "дубликты": "дубликаты",
    "дубликат": "дубликаты",
    "дубликатыы": "дубликаты",
    "дупликаты": "дубликаты",
    "дупликат": "дубликаты",
    "дупликаты": "дубликаты",
    "дубля": "дубли",
    "дублей": "дубли",
    "повторы": "дубли",

    # Rows
    "стрки": "строки",
    "строк": "строки",
    "строки": "строки",
    "строчек": "строки",
    "пустые строчки": "пустые строки",
    "пустых строчек": "пустых строк",
    "пустые строки": "пустые строки",

    # Columns
    "столбец": "столбец",
    "столбца": "столбца",
    "столбцы": "столбцы",
    "колонка": "столбец",
    "колонки": "столбцы",

    # Sheets
    "листы": "листы",
    "листов": "листов",
    "листа": "листа",
    "страницы": "листы",

    # Common task words
    "удоли": "удали",
    "удолить": "удалить",
    "удоление": "удаление",
    "удолиь": "удалить",
    "удалть": "удалить",
    "найди": "найди",
    "наити": "найти",
    "поменяй": "замени",
    "замени": "замени",
    "обьедини": "объедини",
    "обьединить": "объединить",
    "раздели": "раздели",
    "разделть": "разделить",
    "сортируй": "отсортируй",
    "отсортируй": "отсортируй",
    "пустых": "пустых",
}


# Replace longer phrases before shorter words.
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
    """
    Нормализует распространённые опечатки в формулировке задачи.

    Важно:
    - исходный запрос не изменяется;
    - функция не применяется к ячейкам Excel;
    - названия столбцов и листов не исправляются отдельно.
    """
    if not isinstance(task, str):
        return ""

    text = task.strip()
    text = re.sub(r"\s+", " ", text)

    # Normalize common phrase-level typos first.
    lower_text = text.lower()

    for wrong, correct in sorted(
        PHRASE_REPLACEMENTS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            r"(?<!\w)" + re.escape(wrong) + r"(?!\w)",
            flags=re.IGNORECASE,
        )
        lower_text = pattern.sub(correct, lower_text)

    # Normalize individual words.
    words = re.findall(r"\w+|[^\w\s]+|\s+", lower_text, flags=re.UNICODE)
    normalized = []

    for word in words:
        if word.isspace() or not re.fullmatch(r"\w+", word, flags=re.UNICODE):
            normalized.append(word)
            continue

        normalized.append(WORD_REPLACEMENTS.get(word, word))

    result = "".join(normalized)
    result = re.sub(r"\s+", " ", result).strip()

    return result


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
        try:
            text = json.dumps(
                analysis,
                ensure_ascii=False,
                default=str,
            )
        except Exception:
            text = str(analysis)

    if len(text) > MAX_ANALYSIS_CHARS:
        text = text[:MAX_ANALYSIS_CHARS] + "\n[Анализ сокращён]"

    return text


# ============================================================
# OLLAMA REQUEST
# ============================================================

def _post_to_ollama(prompt: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты интеллектуальный помощник BahonIQ Excel AI. "
                    "Понимай запросы на естественном русском языке. "
                    "Самостоятельно анализируй структуру Excel, "
                    "выбирай подходящие листы и столбцы по заголовкам. "
                    "Не требуй от пользователя номера столбца, если "
                    "заголовок можно определить из анализа. "
                    "Не выдумывай несуществующие столбцы. "
                    "Исправляй очевидные опечатки и ошибки ввода "
                    "в запросах пользователя с учётом контекста. "
                    "Понимай разговорные выражения, синонимы и "
                    "неформальные команды. Например, «удали дудли» "
                    "может означать «удали дубли», а «убери повторы» "
                    "может означать удаление дубликатов. "
                    "Не исправляй автоматически реальные названия "
                    "столбцов, листов, имена, коды и значения данных "
                    "на основании догадок. "
                    "Если запрос допускает несколько трактовок и "
                    "выбор влияет на изменение файла, задай вопрос. "
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
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
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

    for nested_key in (
        "parameters",
        "params",
        "arguments",
        "args",
    ):
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

    # Promote parameters from nested objects.
    for nested_key in (
        "parameters",
        "params",
        "arguments",
        "args",
    ):
        nested = operation.get(nested_key)

        if isinstance(nested, dict):
            for key, value in nested.items():
                operation.setdefault(key, value)

    # Normalize worksheet names.
    if not operation.get("sheet"):
        for alias in (
            "sheet_name",
            "worksheet",
            "лист",
            "имя_листа",
        ):
            if operation.get(alias):
                operation["sheet"] = operation[alias]
                break

    # Normalize column names.
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
        for alias in (
            "column_names",
            "fields",
            "столбцы",
            "колонки",
        ):
            if operation.get(alias) is not None:
                operation["columns"] = operation[alias]
                break

    if isinstance(operation.get("columns"), str):
        operation["columns"] = [operation["columns"]]

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

        validated.append(
            _normalize_operation(original, index)
        )

    return validated


# ============================================================
# PROMPT
# ============================================================

def _build_prompt(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
    original_task: str | None = None,
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
            "При необходимости используй его для понимания "
            "исходного смысла. Исправленный запрос помогает "
            "понять намерение, но не является названием столбца "
            "или значением ячейки.\n"
        )

    supported = ", ".join(sorted(SUPPORTED_TYPES))

    return f"""
Ты — исполнитель планирования задач для BahonIQ Excel AI.

ЗАДАЧА ПОЛЬЗОВАТЕЛЯ ПОСЛЕ ИСПРАВЛЕНИЯ ОЧЕВИДНЫХ ОПЕЧАТОК:
{task}
{original_instruction}
{sheet_instruction}

АНАЛИЗ EXCEL-ФАЙЛА:
{compact}

ДОСТУПНЫЕ ТИПЫ ОПЕРАЦИЙ:
{supported}

Верни только один JSON-объект:

{{
  "questions": [],
  "operations": [],
  "explanation": "Краткое объяснение"
}}

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:

1. Понимай естественный язык, разговорные выражения,
   синонимы и распространённые опечатки.

2. Не меняй названия столбцов и листов по догадке.
   Используй реальные названия из анализа файла.

3. Если пользователь просит убрать дубли, используй
   remove_duplicates. Передавай названия столбцов в поле columns,
   если удаление должно учитывать конкретные столбцы.

4. Если пользователь просит найти повторяющиеся значения в конкретном столбце, используй find_repeated_values.

   Если пользователь просит найти одинаковые строки целиком, используй find_duplicate_rows. Сравнивай все столбцы. Не удаляй строки, если пользователь явно не просит удалить дубликаты.

5. Если пользователь просит разделить записи на отдельные листы
   одной книги, используй split_to_sheets. Укажи sheet и column,
   используя название заголовка из анализа.

6. Если пользователь просит создать отдельные Excel-файлы по
   значениям столбца, используй split_by_column.

7. Если пользователь просит выбрать или оставить столбцы,
   используй select_columns и укажи названия в columns.

8. Для сортировки используй sort_rows. Укажи sheet и column,
   а направление сортировки — если оно указано или необходимо.

9. Для удаления пустых строк используй remove_empty_rows.

10. Для заполнения пустых ячеек используй fill_empty и укажи
    столбец и значение заполнения, если это понятно из запроса.

11. Для замены значений используй replace_values. Укажи столбец,
    исходное значение и новое значение.

12. Не придумывай столбцы, листы, значения и результаты.

13. Если задача однозначна, верни пустой массив questions.

14. Если есть несколько равно подходящих столбцов и выбор
    влияет на результат, задай один конкретный вопрос в questions
    и верни пустой массив operations.

15. Не задавай вопросов о технических деталях, которые можно
    определить из анализа файла.

16. Не используй типы, которых нет в списке доступных операций.

17. Не возвращай Python-код и не добавляй текст вне JSON.

18. Если задача требует нескольких действий, расположи операции
    в правильном порядке.

19. Не утверждай, что операция уже выполнена. Ты только
    формируешь план, который затем обработает исполнитель.

20. Если не уверен, что именно хотел сделать пользователь,
    задай уточняющий вопрос вместо потенциально опасного действия.

Пример для задачи «Раздели студентов по курсам на разные листы»:

{{
  "questions": [],
  "operations": [
    {{
      "type": "split_to_sheets",
      "sheet": "Лист1",
      "column": "Курс"
    }}
  ],
  "explanation": "Разделение строк по значениям столбца курса."
}}

Этот пример показывает формат, а не реальные названия столбцов.
Определи их по анализу текущего файла.

Ответ должен быть корректным JSON.
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

    prompt = _build_prompt(
        task=normalized_task,
        analysis=analysis,
        selected_sheet=selected_sheet,
        original_task=original_task,
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
