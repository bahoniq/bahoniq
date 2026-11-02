"""Semantic workbook profiling used by the planner.

The profile deliberately describes the data that exists.  Empty Excel grid
capacity is not treated as business information.
"""

from __future__ import annotations

from datetime import date, datetime
from numbers import Number
import re


def _kind(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (datetime, date)):
        return "date"
    if isinstance(value, Number):
        return "number"
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", text):
        return "numeric_text"
    return "text"


def enrich_analysis(report):
    """Add compact semantic hints while preserving the legacy schema."""
    for sheet in report.get("sheets", []):
        headers = sheet.get("headers", [])
        preview = sheet.get("preview", [])
        profiles = []
        for index, header in enumerate(headers):
            values = [row[index] for row in preview if index < len(row)]
            nonempty = [value for value in values if _kind(value) != "empty"]
            kinds = {}
            for value in nonempty:
                name = _kind(value)
                kinds[name] = kinds.get(name, 0) + 1
            inferred = max(kinds, key=kinds.get) if kinds else "unknown"
            examples = []
            for value in nonempty:
                if value not in examples:
                    examples.append(value)
                if len(examples) == 3:
                    break
            profiles.append({
                "name": header,
                "position": index + 1,
                "inferred_type": inferred,
                "examples": examples,
            })
        sheet["semantic_profile"] = {
            "data_rows": max(0, sheet.get("nonempty_rows", 0) - 1),
            "columns": profiles,
            "note": "Profile is inferred from representative values.",
        }
    report["analysis_policy"] = (
        "Use actual populated data. Blank grid cells are technical metadata, "
        "not a finding unless the user explicitly asks about missing values."
    )
    return report
