
# -*- coding: utf-8 -*-
"""История формирования отчётов ANALYTICS AI."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


APP_DIR = Path.home() / "AppData" / "Local" / "BahonIQ" / "ReportStudio"
HISTORY_FILE = APP_DIR / "history.json"
MAX_HISTORY_ITEMS = 500


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_history() -> list[dict[str, Any]]:
    """Безопасно читает историю. Повреждённый файл не перезаписывает."""

    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            return []

        return [
            item for item in data
            if isinstance(item, dict)
        ][:MAX_HISTORY_ITEMS]

    except (OSError, json.JSONDecodeError):
        return []


def _write_history(items: list[dict[str, Any]]) -> None:
    """Атомарно сохраняет историю, чтобы не оставить частичный JSON."""

    APP_DIR.mkdir(parents=True, exist_ok=True)
    items = items[:MAX_HISTORY_ITEMS]

    fd, temporary_name = tempfile.mkstemp(
        prefix="history_",
        suffix=".tmp",
        dir=str(APP_DIR),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                items,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_name, HISTORY_FILE)

    finally:
        try:
            if os.path.exists(temporary_name):
                os.remove(temporary_name)
        except OSError:
            pass


def add_record(
    source_file: str = "",
    sheet_name: str = "",
    report_title: str = "",
    output_file: str = "",
    status: str = "success",
    message: str = "",
    rows_count: int = 0,
    columns_count: int = 0,
) -> dict[str, Any]:
    """Добавляет запись об успешном отчёте или ошибке."""

    record = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "created_at": _now(),
        "source_file": str(source_file),
        "sheet_name": str(sheet_name),
        "report_title": str(report_title),
        "output_file": str(output_file),
        "status": str(status),
        "message": str(message),
        "rows_count": int(rows_count),
        "columns_count": int(columns_count),
    }

    items = _read_history()
    items.insert(0, record)
    _write_history(items)

    return record


def get_history(limit: int | None = 100) -> list[dict[str, Any]]:
    """Возвращает последние записи: новые в начале."""

    items = _read_history()

    if limit is None:
        return items

    return items[:max(0, int(limit))]


def search_history(
    query: str = "",
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Ищет отчёты по имени файла, листу, названию или статусу."""

    query = query.strip().casefold()
    items = _read_history()
    results = []

    for item in items:
        if status and item.get("status") != status:
            continue

        searchable = " ".join([
            str(item.get("source_file", "")),
            str(item.get("sheet_name", "")),
            str(item.get("report_title", "")),
            str(item.get("output_file", "")),
            str(item.get("message", "")),
        ]).casefold()

        if query and query not in searchable:
            continue

        results.append(item)

    return results


def delete_record(record_id: str) -> bool:
    """Удаляет одну запись истории по её ID."""

    items = _read_history()
    filtered = [
        item for item in items
        if str(item.get("id", "")) != str(record_id)
    ]

    if len(filtered) == len(items):
        return False

    _write_history(filtered)
    return True


def clear_history() -> int:
    """Очищает историю и возвращает количество удалённых записей."""

    items = _read_history()
    _write_history([])
    return len(items)


def prune_history() -> int:
    """Удаляет из истории записи, у которых PDF уже отсутствует."""

    items = _read_history()
    kept = []

    for item in items:
        output_file = str(item.get("output_file", ""))

        # Ошибки и записи без пути к PDF сохраняем.
        if item.get("status") != "success" or not output_file:
            kept.append(item)
            continue

        if Path(output_file).is_file():
            kept.append(item)

    removed = len(items) - len(kept)

    if removed:
        _write_history(kept)

    return removed
