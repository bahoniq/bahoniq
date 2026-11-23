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

from .settings import CONTEXT_SIZE, REQUEST_TIMEOUT


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}
KAZAKH_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
ID_WORDS = {"id", "ид", "код", "номер", "нөмір", "no", "number", "iin", "иин", "жсн"}
COUNTRY_WORDS = {"страна", "ел", "country"}
NAME_WORDS = {
    "name", "наименование", "название", "атауы", "организация", "ұйым",
    "университет", "университеті", "university", "institution", "organization", "employee",
    "сотрудник", "қызметкер", "товар", "өнім", "product", "клиент", "client",
}

STUDENT_KEY_ALIASES = {
    "iin": {"иин", "жсн", "iin", "иин обучающегося", "иин студента"},
    "email": {"почта", "электронная почта", "email", "e mail", "e-mail", "корпоративная почта"},
    "fio": {"фио", "ф и о", "фио обучающегося", "фио студента", "полное имя"},
    "translit": {"фио транслитом", "фио латиницей", "фио латин", "translit fio", "full name latin"},
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
    """Plan only requests that are structurally unambiguous."""
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


def _cloud_ai_plan(instruction: str, schemas: dict) -> dict:
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

    import ai_service
    raw_res = ai_service.generate_text(
        prompt=prompt,
        system_instruction="Ты планировщик BahonIQ Multi-File AI. Возвращай только корректный JSON без Markdown.",
        temperature=0.1,
        timeout=REQUEST_TIMEOUT,
    )
    if isinstance(raw_res, tuple):
        raw_res = raw_res[0]
    if not raw_res:
        raise ValueError("Облачный ИИ вернул пустой ответ.")
    from .ai_interpreter import _extract_json
    return _extract_json(raw_res)


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
        response = _cloud_ai_plan(instruction, schemas)
    except (RuntimeError, ValueError) as exc:
        return {
            "questions": [
                "Не удалось однозначно построить план. Укажи точные листы, ключевые столбцы для сопоставления и столбцы результата."
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


def _student_key_kind(header: str) -> str | None:
    normalized = _norm(header)
    for kind, aliases in STUDENT_KEY_ALIASES.items():
        if normalized in {_norm(alias) for alias in aliases}:
            return kind
    return None


def _student_key(value, kind: str) -> str:
    raw = _text(value)
    if kind == "iin":
        digits = re.sub(r"\D", "", raw)
        return digits.zfill(12) if digits and len(digits) <= 12 else digits
    if kind == "email":
        return re.sub(r"\s+", "", raw).casefold()
    return _norm(raw)


def enrich_student_list(
    target_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
    *,
    target_sheet: str = "",
    reference_sheet: str = "",
) -> dict:
    """Add missing columns from a reference workbook to a target student list.

    Matching is conservative and deterministic: IIN, email, normalized full name,
    then transliterated full name.  A row is enriched only when the selected key
    resolves to exactly one reference row.  Unmatched and ambiguous rows are
    recorded on a separate audit sheet instead of being guessed.
    """
    target = Path(target_path).expanduser().resolve()
    reference = Path(reference_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".xlsx":
        destination = destination.with_suffix(".xlsx")
    if target == reference or destination in {target, reference}:
        raise ValueError("Исходные файлы и итоговый файл должны быть разными.")

    target_wb = load_workbook(target, data_only=False)
    reference_wb = load_workbook(reference, data_only=True, read_only=True)
    try:
        target_ws = target_wb[target_sheet] if target_sheet in target_wb.sheetnames else target_wb.active
        reference_ws = reference_wb[reference_sheet] if reference_sheet in reference_wb.sheetnames else reference_wb.active
        target_header_row = _find_header_row(target_ws)
        reference_header_row = _find_header_row(reference_ws)
        target_headers = _unique_headers([
            target_ws.cell(target_header_row, col).value for col in range(1, target_ws.max_column + 1)
        ])
        reference_headers = _unique_headers([
            reference_ws.cell(reference_header_row, col).value for col in range(1, reference_ws.max_column + 1)
        ])
        target_key_cols = {
            kind: index for index, header in enumerate(target_headers, 1)
            if (kind := _student_key_kind(header))
        }
        reference_key_cols = {
            kind: index for index, header in enumerate(reference_headers, 1)
            if (kind := _student_key_kind(header))
        }
        shared_keys = [kind for kind in ("iin", "email", "fio", "translit") if kind in target_key_cols and kind in reference_key_cols]
        if not shared_keys:
            raise ValueError(
                "Не найден общий ключ. Нужен хотя бы один столбец: ИИН, Почта, ФИО или ФИО транслитом."
            )

        indices = {kind: defaultdict(list) for kind in shared_keys}
        reference_rows = {}
        for row_number, raw_values in enumerate(
            reference_ws.iter_rows(
                min_row=reference_header_row + 1,
                max_col=len(reference_headers),
                values_only=True,
            ),
            start=reference_header_row + 1,
        ):
            values = list(raw_values)
            if not any(value not in (None, "") for value in values):
                continue
            reference_rows[row_number] = values
            for kind in shared_keys:
                key = _student_key(values[reference_key_cols[kind] - 1], kind)
                if key:
                    indices[kind][key].append(row_number)

        existing = {_norm(header) for header in target_headers}
        appended = [
            (index, header) for index, header in enumerate(reference_headers, 1)
            if _norm(header) not in existing
        ]
        if not appended:
            raise ValueError("Во втором файле нет новых столбцов для добавления.")

        first_new_col = target_ws.max_column + 1
        source_header_style = target_ws.cell(target_header_row, 1)
        from copy import copy
        for offset, (_, header) in enumerate(appended):
            cell = target_ws.cell(target_header_row, first_new_col + offset, header)
            cell.font = copy(source_header_style.font)
            cell.fill = copy(source_header_style.fill)
            cell.border = copy(source_header_style.border)
            cell.alignment = copy(source_header_style.alignment)
            cell.number_format = source_header_style.number_format
            cell.protection = copy(source_header_style.protection)

        matched = unmatched = ambiguous = conflicts = 0
        method_counts = Counter()
        audit_rows = []
        for row_number in range(target_header_row + 1, target_ws.max_row + 1):
            if not any(target_ws.cell(row_number, col).value not in (None, "") for col in range(1, len(target_headers) + 1)):
                continue
            candidates_by_kind = []
            for kind in shared_keys:
                key = _student_key(target_ws.cell(row_number, target_key_cols[kind]).value, kind)
                rows = indices[kind].get(key, []) if key else []
                if rows:
                    candidates_by_kind.append((kind, key, rows))

            unique_evidence = [(kind, key, rows[0]) for kind, key, rows in candidates_by_kind if len(rows) == 1]
            unique_rows = {item[2] for item in unique_evidence}
            selected = None
            method = ""
            status = ""
            if len(unique_rows) > 1:
                conflicts += 1
                status = "Конфликт ключей"
            elif len(unique_rows) == 1:
                selected = next(iter(unique_rows))
                method = next(kind for kind, _, ref_row in unique_evidence if ref_row == selected)
            else:
                all_rows = {ref_row for _, _, rows in candidates_by_kind for ref_row in rows}
                if len(all_rows) == 1:
                    selected = next(iter(all_rows))
                    method = next(kind for kind, _, rows in candidates_by_kind if selected in rows)
                elif all_rows:
                    ambiguous += 1
                    status = "Неоднозначное совпадение"
                else:
                    unmatched += 1
                    status = "Не найден"

            if selected is not None:
                matched += 1
                method_counts[method] += 1
                source_values = reference_rows[selected]
                for offset, (source_col, _) in enumerate(appended):
                    target_ws.cell(row_number, first_new_col + offset, source_values[source_col - 1])
            else:
                audit_rows.append([
                    row_number,
                    status,
                    _text(target_ws.cell(row_number, target_key_cols.get("iin", 0)).value) if "iin" in target_key_cols else "",
                    _text(target_ws.cell(row_number, target_key_cols.get("email", 0)).value) if "email" in target_key_cols else "",
                    _text(target_ws.cell(row_number, target_key_cols.get("fio", 0)).value) if "fio" in target_key_cols else "",
                ])

        audit_name = "Отчёт сопоставления"
        if audit_name in target_wb.sheetnames:
            del target_wb[audit_name]
        audit_ws = target_wb.create_sheet(audit_name)
        audit_ws.append(["Показатель", "Значение"])
        audit_ws.append(["Всего строк", matched + unmatched + ambiguous + conflicts])
        audit_ws.append(["Успешно дополнено", matched])
        audit_ws.append(["Не найдено", unmatched])
        audit_ws.append(["Неоднозначных", ambiguous])
        audit_ws.append(["Конфликтов ключей", conflicts])
        audit_ws.append(["Добавлено столбцов", len(appended)])
        audit_ws.append(["Новые столбцы", ", ".join(header for _, header in appended)])
        audit_ws.append(["Методы", ", ".join(f"{kind}: {count}" for kind, count in method_counts.items()) or "Нет"])
        audit_ws.append([])
        audit_ws.append(["Строка исходного файла", "Статус", "ИИН", "Почта", "ФИО"])
        for row in audit_rows:
            audit_ws.append(row)
        audit_ws.freeze_panes = "A12"
        for cell in audit_ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        for cell in audit_ws[11]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        for col, width in {"A": 25, "B": 28, "C": 18, "D": 34, "E": 42}.items():
            audit_ws.column_dimensions[col].width = width

        destination.parent.mkdir(parents=True, exist_ok=True)
        target_wb.save(destination)
        return {
            "output": str(destination),
            "total": matched + unmatched + ambiguous + conflicts,
            "matched": matched,
            "unmatched": unmatched,
            "ambiguous": ambiguous,
            "conflicts": conflicts,
            "added_columns": [header for _, header in appended],
            "methods": dict(method_counts),
            "target_sheet": target_ws.title,
            "reference_sheet": reference_ws.title,
        }
    finally:
        target_wb.close()
        reference_wb.close()
