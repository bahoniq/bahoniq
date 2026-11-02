"""Compile conversational Excel requests into a stable semantic intent.

This module never executes a workbook operation.  It identifies actions and
matches phrases to real sheet/header names so deterministic routes and Ollama
receive the same, unambiguous interpretation.
"""

from __future__ import annotations

import re
from typing import Any


def _norm(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _stem(word: str) -> str:
    special = {"имени": "имя", "имя": "имя"}
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


def _sheets(analysis: Any) -> list[dict]:
    if not isinstance(analysis, dict):
        return []
    value = analysis.get("sheets", [])
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [
            {"name": name, **(details if isinstance(details, dict) else {})}
            for name, details in value.items()
        ]
    return []


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


def _header_mentions(text: str, headers: list[str]) -> list[dict]:
    words = re.findall(r"\w+", _norm(text), flags=re.UNICODE)
    stems = [_stem(word) for word in words]
    mentions = []
    for header in headers:
        header_words = re.findall(r"\w+", _norm(header), flags=re.UNICODE)
        header_stems = [_stem(word) for word in header_words]
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
    mentions.sort(key=lambda item: (item["position"], -item["specificity"]))
    return mentions


def compile_intent(
    task: str,
    analysis: Any,
    selected_sheet: Any = None,
) -> dict:
    raw = str(task or "").strip()
    normalized = _norm(raw)
    sheets = _sheets(analysis)
    if selected_sheet:
        selected = str(selected_sheet).strip()
        chosen = [s for s in sheets if str(s.get("name", "")).strip() == selected]
        if chosen:
            sheets = chosen

    schema = []
    all_headers = []
    for sheet in sheets:
        name = str(sheet.get("name") or sheet.get("sheet_name") or "").strip()
        headers = _headers(sheet)
        schema.append({"sheet": name, "headers": headers})
        all_headers.extend(headers)
    # Preserve order while removing repeated labels from several sheets.
    all_headers = list(dict.fromkeys(all_headers))

    split = bool(re.search(
        r"\b(?:раздел\w*|разбей\w*|раскид\w*|распредел\w*)\b"
        r"|\b(?:отдельн\w*|разн\w*)\s+"
        r"лист(?:ы|ах|ам|ами|ов)\b",
        normalized,
    ))
    sort = bool(re.search(
        r"\b(?:сортир\w*|отсортир\w*|располож\w*|упорядоч\w*)\b",
        normalized,
    ))
    # Conversational shorthand: "раскидай по X и там по Y".
    shorthand_sort = split and bool(re.search(r"\b(?:там|внутри)\b.*\bпо\b", normalized))
    count = bool(re.search(
        r"\b(?:посчитай|подсчитай|количеств\w*|сколько)\b", normalized
    ))
    trim = bool(re.search(
        r"\b(?:убер\w*|удал\w*|очист\w*)\b.*\bпробел\w*", normalized
    ))
    missing = bool(re.search(
        r"\b(?:без|пуст\w*|отсутств\w*|не заполн\w*)\b", normalized
    ))

    actions = []
    for name, enabled in (
        ("trim_text", trim),
        ("find_missing", missing),
        ("split_to_sheets", split),
        ("group_count", count),
        ("sort_rows", sort or shorthand_sort),
    ):
        if enabled:
            actions.append(name)

    mentions = _header_mentions(normalized, all_headers)
    mentioned_headers = [item["header"] for item in mentions]
    descending = bool(re.search(
        r"\b(?:по убыванию|от я до а|от z до a)\b", normalized
    ))

    canonical = raw
    resolved = {}
    if split and (sort or shorthand_sort) and len(mentioned_headers) >= 2:
        split_column = mentioned_headers[0]
        sort_column = mentioned_headers[-1]
        resolved = {
            "split_by": split_column,
            "sort_each_sheet_by": sort_column,
            "sort_direction": "descending" if descending else "ascending",
        }
        canonical = (
            f"Разделить данные по столбцу «{split_column}» на отдельные листы. "
            f"Внутри каждого листа отсортировать строки по столбцу "
            f"«{sort_column}» "
            + ("по убыванию." if descending else "по возрастанию.")
        )
    elif split and mentioned_headers:
        resolved = {"split_by": mentioned_headers[0]}
        canonical = (
            f"Разделить данные по столбцу «{mentioned_headers[0]}» "
            "на отдельные листы."
        )
    elif count and mentioned_headers:
        resolved = {"group_by": mentioned_headers[-1], "aggregate": "count"}
        canonical = (
            f"Подсчитать количество записей по столбцу "
            f"«{mentioned_headers[-1]}» и создать отдельный лист со сводкой."
        )

    return {
        "raw_instruction": raw,
        "canonical_instruction": canonical,
        "actions": actions,
        "resolved": resolved,
        "mentioned_headers": mentioned_headers,
        "workbook_schema": schema,
        "constraints": {
            "preserve_source": True,
            "delete_rows": bool(re.search(r"\bудал\w*\s+строк\w*", normalized)),
            "sort_direction": "descending" if descending else "ascending",
        },
        "needs_ai": not bool(actions),
    }
