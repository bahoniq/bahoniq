"""Universal, plan-first processing of several Excel workbooks.

The AI may propose a plan, but this module binds every file, sheet and column
to the inspected schema before execution.  Source workbooks are read-only and
the result is always written to a new XLSX file.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from .settings import CONTEXT_SIZE, OLLAMA_URL, PREFERRED_MODEL, REQUEST_TIMEOUT


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}
KAZAKH_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
ID_WORDS = {"id", "ид", "код", "номер", "нөмір", "no", "number", "iin", "иин", "жсн"}
COUNTRY_WORDS = {"страна", "ел", "country"}
NAME_WORDS = {
    "name", "наименование", "название", "атауы", "организация", "ұйым",
    "университет", "университеті", "university", "institution", "organization", "employee",
    "сотрудник", "қызметкер", "товар", "өнім", "product", "клиент", "client",
}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _norm(value) -> str:
    text = _text(value).casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-яәғқңөұүһі]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _detect_language(text: str) -> str:
    if any(char in KAZAKH_LETTERS for char in text):
        return "kk"
    latin = sum("a" <= char.casefold() <= "z" for char in text)
    cyrillic = sum("а" <= char.casefold() <= "я" for char in text)
    return "en" if latin > cyrillic * 1.35 else "ru"


def _header_score(values) -> int:
    nonempty = [_text(value) for value in values if _text(value)]
    if len(nonempty) < 2:
        return -1
    words = set(_norm(" ".join(nonempty)).split())
    known = len(words & (ID_WORDS | COUNTRY_WORDS | NAME_WORDS))
    number_symbol = any(_text(value) == "№" for value in values)
    return known * 10 + int(number_symbol) * 10 + min(len(nonempty), 10)


def _find_header_row(ws) -> int:
    best = (1, -1)
    for row_number in range(1, min(ws.max_row or 1, 30) + 1):
        values = [ws.cell(row_number, col).value for col in range(1, (ws.max_column or 1) + 1)]
        score = _header_score(values)
        if score >= 12:
            return row_number
        if score > best[1]:
            best = (row_number, score)
    if best[1] < 2:
        raise ValueError(f"На листе «{ws.title}» не найдена строка заголовков.")
    return best[0]


def _unique_headers(values) -> list[str]:
    result, used = [], Counter()
    for index, value in enumerate(values, start=1):
        base = _text(value) or f"Column {index}"
        used[base] += 1
        result.append(base if used[base] == 1 else f"{base} ({used[base]})")
    return result


def _sheet_schema(ws) -> dict:
    header_row = _find_header_row(ws)
    headers = _unique_headers([ws.cell(header_row, col).value for col in range(1, ws.max_column + 1)])
    rows = []
    samples = []
    for row_number in range(header_row + 1, ws.max_row + 1):
        values = [_json_value(ws.cell(row_number, col).value) for col in range(1, len(headers) + 1)]
        if not any(value not in (None, "") for value in values):
            continue
        rows.append(values)
        if len(samples) < 5:
            samples.append(values)
    language_text = " ".join(headers + [_text(value) for row in samples for value in row if value is not None])
    return {
        "sheet": ws.title,
        "header_row": header_row,
        "headers": headers,
        "row_count": len(rows),
        "sample_rows": samples,
        "language": _detect_language(language_text),
    }


def analyze_multi_file_sources(paths: Iterable[str | Path]) -> dict:
    resolved = [Path(path).expanduser().resolve() for path in paths]
    if len(resolved) < 2:
        raise ValueError("Для Multi-File AI выбери не менее двух Excel-файлов.")
    if len(set(resolved)) != len(resolved):
        raise ValueError("Один и тот же файл выбран несколько раз.")

    files = []
    for file_index, path in enumerate(resolved):
        if not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Сначала преобразуй «{path.name}» в XLSX/XLSM.")
        wb = load_workbook(path, read_only=False, data_only=True)
        try:
            sheets = []
            for ws in wb.worksheets:
                if (ws.max_row or 0) < 2 or (ws.max_column or 0) < 1:
                    continue
                try:
                    sheets.append(_sheet_schema(ws))
                except ValueError:
                    continue
            if not sheets:
                raise ValueError(f"В файле «{path.name}» не найдена таблица с заголовками.")
            files.append({
                "file_index": file_index,
                "file_name": path.name,
                "path": str(path),
                "sheets": sheets,
            })
        finally:
            wb.close()
    return {"files": files}


def _primary_sheet(file_schema):
    return max(file_schema["sheets"], key=lambda sheet: sheet["row_count"] * max(len(sheet["headers"]), 1))


def _column_by_words(sheet, words, *, exclude=()):
    excluded = set(exclude)
    ranked = []
    for header in sheet["headers"]:
        if header in excluded:
            continue
        norm = _norm(header)
        score = len(set(norm.split()) & words)
        if _text(header) == "№" and words is ID_WORDS:
            score = max(score, 4)
        if score:
            column = sheet["headers"].index(header)
            populated = sum(row[column] not in (None, "") for row in sheet["sample_rows"])
            ranked.append((score, populated, -column, header))
    return max(ranked)[3] if ranked else None


def _mentioned_headers(instruction, schemas):
    normalized = _norm(instruction)
    found = []
    for file_schema in schemas["files"]:
        for sheet in file_schema["sheets"]:
            for header in sheet["headers"]:
                norm = _norm(header)
                if norm and len(norm) >= 3 and norm in normalized and header not in found:
                    found.append(header)
    return found


def _deterministic_plan(instruction: str, schemas: dict):
    """Plan only requests that are structurally unambiguous without Ollama."""
    task = _norm(instruction)
    primary = [(file_schema, _primary_sheet(file_schema)) for file_schema in schemas["files"]]
    mentioned = _mentioned_headers(instruction, schemas)
    append_markers = ("друг под другом", "по вертикали", "объедини строки", "собери строки", "append", "stack")

    normalized_sets = [set(_norm(header) for header in sheet["headers"]) for _, sheet in primary]
    same_schema = all(headers == normalized_sets[0] for headers in normalized_sets[1:])
    if any(marker in task for marker in append_markers) or (same_schema and "объедин" in task):
        common = [header for header in primary[0][1]["headers"] if all(_norm(header) in item for item in normalized_sets[1:])]
        selected = [header for header in common if any(_norm(header) == _norm(value) for value in mentioned)] or common
        if not selected:
            return None
        sources = []
        for file_schema, sheet in primary:
            actual = {_norm(header): header for header in sheet["headers"]}
            sources.append({
                "file_index": file_schema["file_index"],
                "sheet": sheet["sheet"],
                "columns": [{"source": actual[_norm(header)], "output": header} for header in selected],
            })
        return {"mode": "append", "sources": sources, "join_type": None, "keys": [], "output_columns": selected, "deduplicate_by": [], "sort_by": []}

    languages = Counter(sheet["language"] for _, sheet in primary)
    language_request = (
        all(marker in task for marker in ("рус", "казах", "англ"))
        or "трех язык" in task
        or "трёх язык" in task
        or (
            "объедин" in task
            and any(marker in task for marker in ("назван", "наимен", "атау", "name"))
            and any(marker in task for marker in ("стран", "country", " ел"))
        )
    )
    if language_request and all(languages[code] == 1 for code in ("ru", "kk", "en")):
        source_by_language = {sheet["language"]: (file_schema, sheet) for file_schema, sheet in primary}
        keys = {lang: _column_by_words(sheet, ID_WORDS) for lang, (_, sheet) in source_by_language.items()}
        if not all(keys.values()):
            return {"questions": ["По каким столбцам сопоставлять строки трёх файлов? Укажи точные названия ключевых столбцов."]}
        outputs = {"ru": "Название (русский)", "kk": "Атауы (қазақша)", "en": "Name (English)"}
        sources = []
        for lang in ("ru", "kk", "en"):
            file_schema, sheet = source_by_language[lang]
            country = _column_by_words(sheet, COUNTRY_WORDS)
            name = _column_by_words(sheet, NAME_WORDS, exclude=[keys[lang], country])
            if not name:
                return None
            columns = [{"source": name, "output": outputs[lang]}]
            if lang == "ru" and country and ("стран" in task or "country" in task or " ел " in f" {task} "):
                columns.append({"source": country, "output": "Страна"})
            sources.append({
                "file_index": file_schema["file_index"], "sheet": sheet["sheet"],
                "key_columns": [keys[lang]], "columns": columns,
            })
        output_columns = [outputs["ru"], outputs["kk"], outputs["en"]]
        if any(mapping["output"] == "Страна" for source in sources for mapping in source["columns"]):
            output_columns.append("Страна")
        return {"mode": "join", "sources": sources, "join_type": "inner", "keys": ["__source_keys__"], "output_columns": output_columns, "deduplicate_by": [], "sort_by": []}
    return None


def _ollama_plan(instruction: str, schemas: dict) -> dict:
    compact = {"files": []}
    for file_schema in schemas["files"]:
        compact["files"].append({
            "file_index": file_schema["file_index"],
            "file_name": file_schema["file_name"],
            "sheets": [{
                "sheet": sheet["sheet"], "headers": sheet["headers"],
                "row_count": sheet["row_count"], "sample_rows": sheet["sample_rows"][:3],
            } for sheet in file_schema["sheets"]],
        })
    prompt = f"""Пользователь выбрал несколько Excel-файлов и написал задачу:
{instruction}

Структура файлов:
{json.dumps(compact, ensure_ascii=False)}

Составь исполнимый план. Поддерживаются только:
1) append — сложить строки файлов друг под другом;
2) join — сопоставить строки файлов по ключевым столбцам и собрать столбцы рядом.

Верни только JSON:
{{
  "questions": [],
  "explanation": "кратко",
  "plan": {{
    "mode": "append или join",
    "join_type": "inner, left или outer; null для append",
    "sources": [{{
      "file_index": 0,
      "sheet": "точное имя листа",
      "key_columns": ["точный заголовок; только для join"],
      "columns": [{{"source": "точный заголовок", "output": "имя итогового столбца"}}]
    }}],
    "output_columns": ["итоговые столбцы в требуемом порядке"],
    "deduplicate_by": ["итоговый столбец; только если просит пользователь"],
    "sort_by": [{{"column": "итоговый столбец", "descending": false}}]
  }}
}}

Правила: используй только реальные file_index, листы и заголовки. Не выдумывай ключ.
Если ключ или требуемые столбцы неоднозначны, верни questions и plan=null.
Не добавляй дедупликацию, сортировку или удаление данных без прямой просьбы.
"""

    # 1. Попытка через единый облачный сервис BahonIQ AI
    try:
        import ai_service
        raw_res = ai_service.generate_text(
            prompt=prompt,
            system_instruction="Ты планировщик BahonIQ Multi-File AI. Возвращай только корректный JSON без Markdown.",
            temperature=0.1,
            timeout=30,
        )
        if raw_res and "{" in raw_res:
            from .ai_interpreter import _clean_json_response
            parsed = _clean_json_response(raw_res)
            if isinstance(parsed, dict) and ("plan" in parsed or "questions" in parsed):
                return parsed
    except Exception:
        pass

    # 2. Локальный фоллбэк на Ollama
    payload = {
        "model": PREFERRED_MODEL,
        "messages": [
            {"role": "system", "content": "Ты планировщик BahonIQ Multi-File AI. Возвращай только корректный JSON и никогда не выдумывай схему."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "keep_alive": -1,
        "options": {"temperature": 0, "top_p": 0.1, "num_ctx": CONTEXT_SIZE, "num_predict": 1200},
    }
    request = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama недоступна или вернула ошибку: {exc}") from exc
    content = envelope.get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Ollama вернула некорректный JSON-план.") from exc


def _schema_lookup(schemas):
    lookup = {}
    for file_schema in schemas["files"]:
        for sheet in file_schema["sheets"]:
            lookup[(file_schema["file_index"], sheet["sheet"])] = sheet
    return lookup


def validate_multi_file_plan(plan: dict, schemas: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("mode") not in {"append", "join"}:
        raise ValueError("План должен содержать mode=append или mode=join.")
    sources = plan.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        raise ValueError("В плане должно быть не менее двух источников.")
    lookup = _schema_lookup(schemas)
    output_names = []
    validated = []
    for source in sources:
        try:
            file_index = int(source["file_index"])
            sheet_name = str(source["sheet"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("У каждого источника нужны file_index и sheet.") from exc
        sheet = lookup.get((file_index, sheet_name))
        if not sheet:
            raise ValueError(f"Источник {file_index}, лист «{sheet_name}» отсутствует в анализе.")
        headers = set(sheet["headers"])
        columns = source.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError(f"Для файла {file_index} не выбраны итоговые столбцы.")
        checked_columns = []
        for mapping in columns:
            src, out = mapping.get("source"), _text(mapping.get("output"))
            if src not in headers or not out:
                raise ValueError(f"Недопустимое сопоставление столбца в файле {file_index}: {mapping!r}")
            checked_columns.append({"source": src, "output": out})
            output_names.append(out)
        keys = source.get("key_columns", [])
        if plan["mode"] == "join":
            if not isinstance(keys, list) or not keys or any(key not in headers for key in keys):
                raise ValueError(f"Для join нужны реальные key_columns файла {file_index}.")
        validated.append({"file_index": file_index, "sheet": sheet_name, "key_columns": list(keys), "columns": checked_columns})

    if plan["mode"] == "append":
        expected = [item["output"] for item in validated[0]["columns"]]
        if any([item["output"] for item in source["columns"]] != expected for source in validated[1:]):
            raise ValueError("Для append каждый источник должен формировать одинаковые итоговые столбцы в одинаковом порядке.")
    elif len({len(source["key_columns"]) for source in validated}) != 1:
        raise ValueError("Для join во всех источниках должно быть одинаковое число ключевых столбцов.")

    ordered_outputs = []
    for name in output_names:
        if name not in ordered_outputs:
            ordered_outputs.append(name)
    requested_order = plan.get("output_columns")
    if requested_order is not None:
        if (
            not isinstance(requested_order, list)
            or len(requested_order) != len(ordered_outputs)
            or set(requested_order) != set(ordered_outputs)
        ):
            raise ValueError("output_columns должен содержать все итоговые столбцы ровно по одному разу.")
        ordered_outputs = list(requested_order)
    allowed = set(ordered_outputs)
    deduplicate_by = plan.get("deduplicate_by") or []
    sort_by = plan.get("sort_by") or []
    if any(name not in allowed for name in deduplicate_by):
        raise ValueError("deduplicate_by ссылается на отсутствующий итоговый столбец.")
    for item in sort_by:
        if not isinstance(item, dict) or item.get("column") not in allowed:
            raise ValueError("sort_by ссылается на отсутствующий итоговый столбец.")
    return {
        "mode": plan["mode"], "join_type": plan.get("join_type") if plan["mode"] == "join" else None,
        "sources": validated, "output_columns": ordered_outputs,
        "deduplicate_by": list(deduplicate_by), "sort_by": list(sort_by),
    }


def plan_multi_file_task(instruction: str, paths: Iterable[str | Path]) -> dict:
    instruction = _text(instruction)
    if not instruction:
        raise ValueError("Опиши, что нужно сделать с выбранными файлами.")
    schemas = analyze_multi_file_sources(paths)
    local = _deterministic_plan(instruction, schemas)
    if isinstance(local, dict) and local.get("questions"):
        return {"questions": local["questions"], "plan": None, "schemas": schemas, "mode": "local"}
    if local:
        plan = validate_multi_file_plan(local, schemas)
        return {"questions": [], "plan": plan, "schemas": schemas, "mode": "local", "explanation": "План однозначно определён по структуре файлов."}
    try:
        response = _ollama_plan(instruction, schemas)
    except (RuntimeError, ValueError) as exc:
        return {
            "questions": [
                "Не удалось однозначно построить план локально. Укажи точные листы, ключевые столбцы для сопоставления и столбцы результата либо запусти Ollama."
            ],
            "plan": None, "schemas": schemas, "mode": "questions", "explanation": str(exc),
        }
    questions = response.get("questions") or []
    if questions:
        return {"questions": [str(item) for item in questions], "plan": None, "schemas": schemas, "mode": "ai", "explanation": _text(response.get("explanation"))}
    plan = validate_multi_file_plan(response.get("plan"), schemas)
    return {"questions": [], "plan": plan, "schemas": schemas, "mode": "ai", "explanation": _text(response.get("explanation"))}


def _read_rows(path, sheet_name, header_row):
    wb = load_workbook(path, read_only=False, data_only=True)
    try:
        ws = wb[sheet_name]
        headers = _unique_headers([ws.cell(header_row, col).value for col in range(1, ws.max_column + 1)])
        rows = []
        for row_number in range(header_row + 1, ws.max_row + 1):
            row = {header: _json_value(ws.cell(row_number, index + 1).value) for index, header in enumerate(headers)}
            if any(value not in (None, "") for value in row.values()):
                rows.append(row)
        return rows
    finally:
        wb.close()


def _execute_append(plan, schemas):
    lookup = _schema_lookup(schemas)
    output_rows = []
    for source in plan["sources"]:
        file_schema = schemas["files"][source["file_index"]]
        sheet = lookup[(source["file_index"], source["sheet"])]
        for row in _read_rows(file_schema["path"], source["sheet"], sheet["header_row"]):
            output_rows.append({mapping["output"]: row.get(mapping["source"]) for mapping in source["columns"]})
    return output_rows


def _execute_join(plan, schemas):
    lookup = _schema_lookup(schemas)
    datasets = []
    for source in plan["sources"]:
        file_schema = schemas["files"][source["file_index"]]
        sheet = lookup[(source["file_index"], source["sheet"])]
        index = {}
        for row in _read_rows(file_schema["path"], source["sheet"], sheet["header_row"]):
            key = tuple(_norm(row.get(column)) for column in source["key_columns"])
            if not all(key):
                continue
            if key in index:
                raise ValueError(f"Ключ {key!r} повторяется в файле «{file_schema['file_name']}». Join остановлен.")
            index[key] = row
        datasets.append((source, index))
    key_sets = [set(index) for _, index in datasets]
    join_type = plan.get("join_type") or "inner"
    if join_type == "left":
        keys = key_sets[0]
    elif join_type == "outer":
        keys = set().union(*key_sets)
    elif join_type == "inner":
        keys = set.intersection(*key_sets)
    else:
        raise ValueError("join_type должен быть inner, left или outer.")
    rows = []
    for key in sorted(keys):
        result = {}
        for source, index in datasets:
            row = index.get(key, {})
            for mapping in source["columns"]:
                value = row.get(mapping["source"])
                output = mapping["output"]
                if output in result and result[output] not in (None, "") and value not in (None, "") and result[output] != value:
                    raise ValueError(f"Конфликт значений итогового столбца «{output}» для ключа {key!r}.")
                if value not in (None, "") or output not in result:
                    result[output] = value
        rows.append(result)
    return rows


def _post_process(rows, plan):
    if plan["deduplicate_by"]:
        seen, unique = set(), []
        for row in rows:
            key = tuple(_norm(row.get(column)) for column in plan["deduplicate_by"])
            if key not in seen:
                seen.add(key)
                unique.append(row)
        rows = unique
    for sort_item in reversed(plan["sort_by"]):
        column = sort_item["column"]
        rows.sort(key=lambda row: (row.get(column) in (None, ""), _norm(row.get(column))), reverse=bool(sort_item.get("descending")))
    return rows


def _write_output(rows, columns, destination):
    wb = Workbook()
    ws = wb.active
    ws.title = "Результат"
    ws.append(columns)
    for row in rows:
        ws.append([row.get(column) for column in columns])
    header_fill = PatternFill("solid", fgColor="1F4E78")
    band_fill = PatternFill("solid", fgColor="DDEBF7")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32
    for row_number in range(2, ws.max_row + 1):
        ws.row_dimensions[row_number].height = 32
        for cell in ws[row_number]:
            cell.font = Font(name="Arial", size=10, color="1F2937")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if row_number % 2 == 0:
                cell.fill = band_fill
    for index, column in enumerate(columns, start=1):
        longest = max([len(_text(column)), *[len(_text(row.get(column))) for row in rows[:200]]], default=12)
        ws.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 14), 48)
    ws.freeze_panes = "A2"
    if rows:
        table = Table(displayName="MultiFileResult", ref=f"A1:{get_column_letter(len(columns))}{ws.max_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(table)
    wb.save(destination)
    wb.close()


def execute_multi_file_plan(plan: dict, schemas: dict, output_path) -> dict:
    validated = validate_multi_file_plan(plan, schemas)
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".xlsx":
        destination = destination.with_suffix(".xlsx")
    sources = {Path(file_schema["path"]).resolve() for file_schema in schemas["files"]}
    if destination in sources:
        raise ValueError("Итоговый файл не может перезаписывать исходный файл.")
    if destination.exists():
        raise FileExistsError("Итоговый файл уже существует. Выбери другое имя.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = _execute_append(validated, schemas) if validated["mode"] == "append" else _execute_join(validated, schemas)
    rows = _post_process(rows, validated)
    _write_output(rows, validated["output_columns"], destination)
    return {
        "output": str(destination), "records": len(rows), "columns": validated["output_columns"],
        "mode": validated["mode"], "source_files": len(validated["sources"]),
    }
