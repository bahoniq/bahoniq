"""High-confidence workbook-grounded planning for conversational requests."""

from __future__ import annotations

import re
from typing import Any


_STOP = {
    "и", "в", "во", "на", "по", "из", "для", "с", "со", "к", "у",
    "сделай", "создай", "подготовь", "таблицу", "итоговую", "данные",
    "строки", "столбцы", "лист", "новый", "новом", "каждый", "всех",
}


def _norm(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-яёәіңғүұқөһ]+", " ", str(value or "").casefold()).strip()


def _stem(token: str) -> str:
    token = _norm(token)
    for ending in (
        "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими", "ая",
        "яя", "ое", "ее", "ые", "ие", "ов", "ев", "ам", "ям", "ах", "ях",
        "ом", "ем", "ую", "юю", "ых", "их", "ы", "и", "а", "я", "у", "ю", "е", "о",
    ):
        if len(token) - len(ending) >= 4 and token.endswith(ending):
            return token[:-len(ending)]
    return token


def _tokens(value: Any) -> set[str]:
    return {
        _stem(word) for word in _norm(value).split()
        if word not in _STOP and len(_stem(word)) >= 3
    }


def _sheets(analysis: Any) -> list[dict]:
    if isinstance(analysis, dict) and isinstance(analysis.get("sheets"), list):
        return [s for s in analysis["sheets"] if isinstance(s, dict)]
    return []


def _examples(sheet: dict, header: str) -> list[Any]:
    values = []
    for item in sheet.get("duplicate_columns", []):
        if str(item.get("header", "")).casefold() == header.casefold():
            values.extend(example.get("value") for example in item.get("examples", []))
    for item in sheet.get("semantic_profile", {}).get("columns", []):
        if str(item.get("name", "")).casefold() == header.casefold():
            values.extend(item.get("examples", []))
    return [value for value in values if value is not None]


def _column_type(sheet: dict, header: str) -> str:
    for item in sheet.get("semantic_profile", {}).get("columns", []):
        if str(item.get("name", "")).casefold() == header.casefold():
            return str(item.get("inferred_type", ""))
    return ""


def _rank_columns(task: str, sheet: dict) -> list[tuple[float, str, float]]:
    task_norm = _norm(task)
    task_tokens = _tokens(task)
    ranked = []
    for header in sheet.get("headers", []):
        header = str(header)
        header_norm = _norm(header)
        header_tokens = _tokens(header)
        overlap = len(task_tokens & header_tokens)
        score = overlap * 4.0
        if header_norm and header_norm in task_norm:
            score += 8.0
        value_score = 0.0
        for value in _examples(sheet, header)[:20]:
            value_norm = _norm(value)
            if value_norm and value_norm in task_norm:
                value_score += 5.0
            else:
                value_score += len(_tokens(value) & task_tokens) * 1.5
        ranked.append((score + min(value_score, 10.0), header, value_score))
    return sorted(ranked, key=lambda item: (-item[0], item[1].casefold()))


def _direct_mentions(task: str, sheet: dict) -> list[str]:
    task_norm = _norm(task)
    task_tokens = _tokens(task)
    result = []
    for header in sheet.get("headers", []):
        header = str(header)
        header_norm = _norm(header)
        tokens = _tokens(header)
        overlap = len(tokens & task_tokens)
        if header_norm in task_norm or (tokens and overlap / len(tokens) >= 0.6):
            result.append(header)
    return result


def _best_for_phrase(phrase: str, headers: list[str]) -> str | None:
    phrase_tokens = _tokens(phrase)
    scored = []
    for header in headers:
        tokens = _tokens(header)
        overlap = len(tokens & phrase_tokens)
        scored.append((overlap / max(1, len(tokens)), overlap, header))
    best = max(scored, default=(0, 0, None))
    return best[2] if best[1] else None


def _choose_sheet(task: str, analysis: Any, selected_sheet: Any) -> dict | None:
    sheets = _sheets(analysis)
    if selected_sheet:
        for sheet in sheets:
            if str(sheet.get("name", "")).casefold() == str(selected_sheet).strip().casefold():
                return sheet
        return None
    if len(sheets) == 1:
        return sheets[0]
    named = [s for s in sheets if _norm(s.get("name")) in _norm(task)]
    return named[0] if len(named) == 1 else None


def plan_autonomously(task: str, analysis: Any, selected_sheet: Any = None) -> dict | None:
    """Return only high-confidence plans; otherwise let existing routes continue."""
    text = _norm(task)
    if re.search(r"\bуникальн\w*\b", text) and re.search(r"\b(?:id|идентификатор)\w*\b", text):
        return None
    sheet = _choose_sheet(task, analysis, selected_sheet)
    if not sheet:
        return None
    sheet_name = str(sheet.get("name", "")).strip()
    ranked = _rank_columns(task, sheet)
    mentioned = [header for score, header, _ in ranked if score >= 4.0]
    direct = _direct_mentions(task, sheet)

    copy_intent = bool(re.search(r"\b(?:перенес|перенеси|скопир|вывед|остав|возьм)\w*\b", text))
    if copy_intent and len(direct) >= 2 and re.search(r"\b(?:лист|таблиц)\w*\b", text):
        return {
            "questions": [],
            "operations": [{
                "type": "copy_columns_to_sheet", "sheet": sheet_name,
                "columns": direct, "output_sheet": "Результат",
            }],
            "mode": "operations", "planning_mode": "autonomous",
            "explanation": "Выбраны названные поля и подготовлен отдельный лист результата.",
        }

    action_flags = {
        "count": bool(re.search(r"\b(?:посчита|количеств)\w*\b", text)),
        "compare": bool(re.search(r"\bсравн\w*\b", text)),
        "average": bool(re.search(r"\bсредн\w*\b", text)),
        "split": bool(re.search(r"\bраздел\w*\b", text)),
    }
    # Narrow legacy routes remain authoritative for one simple operation.
    # This layer exists to preserve several actions in one human request.
    if sum(action_flags.values()) < 2 or not mentioned:
        return None

    # Value mentions (for example paid/free) identify a comparison dimension
    # even when the user never names that column.
    value_dimensions = [
        header for score, header, value_score in ranked
        if value_score >= 3.0 and score >= 3.0
    ]
    categorical = [h for h in mentioned if _column_type(sheet, h) != "number"]
    numeric = [h for h in mentioned if _column_type(sheet, h) == "number"]
    group_match = re.search(
        r"\bпо\s+(.+?)(?:,|\b(?:затем|посчита|сравн|сдела|подготов)\w*\b|$)", text
    )
    raw_group_match = re.search(
        r"\bпо\s+(.+?)(?:,|\b(?:затем|посчита|сравн|сдела|подготов)\w*\b|$)",
        str(task).casefold(),
    )
    if raw_group_match:
        group_match = raw_group_match
    group_phrase = group_match.group(1) if group_match else ""
    primary = _best_for_phrase(group_phrase, categorical)
    if primary in value_dimensions:
        primary = None
    if primary is None:
        primary = next((h for h in categorical if h not in value_dimensions), None)
    if primary is None:
        primary = categorical[0] if categorical else mentioned[0]

    operations = []
    if re.search(r"\bраздел\w*\b", text):
        operations.append({
            "type": "split_to_sheets", "sheet": sheet_name,
            "column": primary, "columns": [primary],
        })

    if re.search(r"\b(?:посчита|количеств)\w*\b", text):
        operations.append({
            "type": "group_by_aggregate", "sheet": sheet_name,
            "column": primary, "columns": [primary], "function": "count",
            "include_empty": True, "output_sheet": "Количество по группам",
        })

    average_requested = bool(re.search(r"\bсредн\w*\b", text))
    if average_requested:
        average_match = re.search(r"\bсредн\w*\s+(.+?)(?:,|\bи\b|$)", text)
        target = _best_for_phrase(
            average_match.group(1) if average_match else text,
            [h for h in mentioned if h != primary],
        )
    else:
        target = None
    if average_requested and target:
        operations.append({
            "type": "group_by_aggregate", "sheet": sheet_name,
            "column": primary, "columns": [primary], "function": "avg",
            "target_column": target, "include_empty": False,
            "output_sheet": "Средние по группам",
        })

    comparison = next((h for h in value_dimensions if h != primary), None)
    if comparison and re.search(r"\bсравн\w*\b", text):
        operations.append({
            "type": "pivot_count", "sheet": sheet_name,
            "row_column": primary, "column_column": comparison,
            "include_empty": True, "output_sheet": "Сравнение групп",
        })

    if not operations:
        return None
    return {
        "questions": [], "operations": operations, "mode": "operations",
        "planning_mode": "autonomous", "deterministic_route": True,
        "explanation": f"Самостоятельно выбран лист «{sheet_name}» и поля: {', '.join(dict.fromkeys(mentioned))}.",
    }
