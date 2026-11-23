# -*- coding: utf-8 -*-
"""Универсальный AI Code Interpreter для произвольных Excel-задач (как ChatGPT Data Analysis)."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .comparison import _display, _prepare_sheet, _read_book

BLOCKED_MODULES = {
    "subprocess", "socket", "http", "urllib", "requests", "httpx", "ftplib",
    "smtplib", "ctypes", "multiprocessing", "webbrowser", "tkinter",
}

BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input"}

SYSTEM_PROMPT = (
    "Ты — BahonIQ Excel AI, опытный инженер данных на Python.\n"
    "Пользователь загрузил Excel-файлы и дал произвольную команду.\n"
    "Напиши рабочий Python-скрипт, который точно и полностью выполняет команду.\n\n"
    "ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ СРЕДЫ:\n"
    "1. Доступны ТОЛЬКО стандартная библиотека Python 3 и библиотека `openpyxl`.\n"
    "   Библиотеки `pandas` и `numpy` НЕ установлены — НИКОГДА не импортируй их.\n"
    "   Используй стандартные импорты:\n"
    "   `from openpyxl import Workbook, load_workbook`\n"
    "   `from openpyxl.styles import Font, PatternFill, Alignment, Border, Side`\n"
    "   `from openpyxl.utils import get_column_letter`\n"
    "2. В области видимости скрипта УЖЕ определены переменные:\n"
    "   - `INPUT_FILES`: list[str] — абсолютные пути к загруженным Excel-файлам в порядке загрузки.\n"
    "   - `OUTPUT_FILE`: str — путь, куда нужно сохранить итоговый `.xlsx` (`wb.save(OUTPUT_FILE)`).\n"
    "3. Исходные файлы из `INPUT_FILES` открывай только для чтения и НИКОГДА не перезаписывай.\n"
    "4. Аккуратно обрабатывай `None`, пустые строки, ведущие нули в ИИН/кодах, даты и кириллицу.\n"
    "5. Оформляй итоговые листы аккуратно: жирная шапка, перенос текста, разумная ширина столбцов, `freeze_panes = 'A2'`.\n"
    "6. В конце скрипта заполни словарь `RESULT_SUMMARY`, например:\n"
    "   RESULT_SUMMARY = {\n"
    "       'message': 'Краткое описание выполненной работы',\n"
    "       'stats': {'rows_written': 100, 'sheets_count': 2},\n"
    "       'columns': ['Столбец 1', 'Столбец 2']\n"
    "   }\n\n"
    "ФОРМАТ ОТВЕТА:\n"
    "Верни готовый Python-код внутри блока ```python ... ```.\n"
    "В первой строке комментарием напиши краткое пояснение, например:\n"
    "# EXPLANATION: Сводка по факультетам и топ-20 должников\n"
    "Никакого лишнего текста вне блока ```python ... ``` не пиши."
)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_sources_for_ai(sources: list[Path]) -> list[dict[str, Any]]:
    """Собирает компактную схему всех загруженных книг (листы, заголовки, 4 примера строк)."""
    schemas: list[dict[str, Any]] = []
    for idx, path in enumerate(sources):
        books = _read_book(path)
        sheets_info = []
        for raw_sheet in books:
            sheet = _prepare_sheet(raw_sheet)
            headers = sheet["headers"]
            rows = sheet["rows"]
            sample = []
            for r in rows[:4]:
                sample.append([_display(v)[:80] for v in r["values"][:len(headers)]])
            sheets_info.append({
                "sheet_name": sheet["name"],
                "data_rows_count": len(rows),
                "headers": headers,
                "sample_rows": sample,
            })
        schemas.append({
            "file_index": idx,
            "filename": path.name,
            "sheets": sheets_info,
        })
    return schemas


def _extract_code_and_explanation(raw_text: str) -> tuple[str, str]:
    """Извлекает Python-код и пояснение из ответа Gemini (markdown-блок, JSON или raw Python)."""
    text = (raw_text or "").strip()

    code_match = re.search(r"```python\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if code_match:
        code = code_match.group(1).strip()
        expl_match = re.search(r"^#\s*EXPLANATION:\s*(.+)$", code, flags=re.MULTILINE)
        expl = expl_match.group(1).strip() if expl_match else "Задача выполнена универсальным Excel AI."
        return code, expl

    clean = text
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json|python)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean).strip()

    for candidate in (clean, *(m.group(0) for m in [re.search(r"\{.*\}", clean, flags=re.DOTALL)] if m)):
        try:
            parsed = json.loads(candidate, strict=False)
            if isinstance(parsed, dict) and parsed.get("code"):
                return str(parsed["code"]), str(parsed.get("explanation") or "")
        except Exception:
            pass

    if any(kw in clean for kw in ("import openpyxl", "from openpyxl", "load_workbook", "Workbook(")):
        expl_match = re.search(r"^#\s*EXPLANATION:\s*(.+)$", clean, flags=re.MULTILINE)
        expl = expl_match.group(1).strip() if expl_match else "Задача выполнена универсальным Excel AI."
        return clean, expl

    raise ValueError("Облачный ИИ не вернул корректный Python-код.")


def _validate_ast_safety(code: str) -> None:
    """Проверяет сгенерированный скрипт через AST на запрещённые импорты и вызовы."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    raise ValueError(f"Запрещённый модуль в сгенерированном коде: {root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_MODULES:
                raise ValueError(f"Запрещённый модуль в сгенерированном коде: {root}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                raise ValueError(f"Запрещённый вызов в сгенерированном коде: {node.func.id}")


def _generate_excel_script(
    instruction: str,
    schemas: list[dict[str, Any]],
    previous_error: str | None = None,
    previous_code: str | None = None,
) -> tuple[str, str]:
    """Запрашивает у Gemini Python-скрипт для выполнения задачи."""
    import ai_service

    schema_json = json.dumps(schemas, ensure_ascii=False, indent=2)
    prompt = (
        f"КОМАНДА ПОЛЬЗОВАТЕЛЯ:\n{instruction}\n\n"
        f"СХЕМЫ ЗАГРУЖЕННЫХ ФАЙЛОВ:\n{schema_json}\n"
    )
    if previous_error and previous_code:
        prompt += (
            f"\nПРЕДЫДУЩАЯ ПОПЫТКА ЗАВЕРШИЛАСЬ ОШИБКОЙ:\n{previous_error}\n\n"
            f"ПРЕДЫДУЩИЙ КОД:\n{previous_code}\n\n"
            "Исправь ошибку и верни обновлённый рабочий JSON с полями `explanation` и `code`."
        )

    raw = ai_service.generate_text(
        prompt=prompt,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.1,
        timeout=60,
    )
    if isinstance(raw, tuple):
        raw = raw[0]
    if not raw or not str(raw).strip():
        raise ValueError("Облачный ИИ вернул пустой ответ.")
    return _extract_code_and_explanation(str(raw))


def _run_script_isolated(
    code: str,
    sources: list[Path],
    output_path: Path,
    work_dir: Path,
    timeout: int = 45,
) -> dict[str, Any]:
    """Запускает проверенный код в отдельном процессе с таймаутом и изоляцией."""
    _validate_ast_safety(code)

    runner_path = work_dir / "_ai_excel_job.py"
    header = (
        "# -*- coding: utf-8 -*-\n"
        "import json\n"
        f"INPUT_FILES = {json.dumps([str(p) for p in sources], ensure_ascii=False)}\n"
        f"OUTPUT_FILE = {json.dumps(str(output_path), ensure_ascii=False)}\n"
        "RESULT_SUMMARY = {}\n\n"
    )
    footer = (
        "\n\nprint('__BAHONIQ_SUMMARY__' + json.dumps(RESULT_SUMMARY, ensure_ascii=False, default=str))\n"
    )
    runner_path.write_text(header + code + footer, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(runner_path)],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or f"Exit code {proc.returncode}").strip()
        raise RuntimeError(err[-1800:])

    summary: dict[str, Any] = {}
    for line in (proc.stdout or "").splitlines():
        if line.startswith("__BAHONIQ_SUMMARY__"):
            payload = line[len("__BAHONIQ_SUMMARY__"):].strip()
            try:
                summary = json.loads(payload)
            except Exception:
                summary = {}
    return summary


def verify_universal_output(
    output_path: Path,
    source_hashes_before: dict[str, str],
    sources: list[Path],
) -> dict[str, Any]:
    """Постпроверка: файл создан, валидно открывается, не пуст, исходники не тронуты."""
    errors: list[str] = []
    checks: dict[str, Any] = {}

    checks["output_exists"] = output_path.is_file() and output_path.stat().st_size > 0
    if not checks["output_exists"]:
        errors.append("Итоговый Excel-файл не был создан или пуст.")
        return {"passed": False, "checks": checks, "errors": errors, "sheets": []}

    sheet_stats = []
    non_empty_sheets = 0
    try:
        wb = load_workbook(output_path, read_only=True, data_only=True)
        for name in wb.sheetnames:
            ws = wb[name]
            rows_count = 0
            cols_count = 0
            for r in ws.iter_rows(values_only=True):
                if any(v is not None and str(v).strip() != "" for v in r):
                    rows_count += 1
                    cols_count = max(cols_count, len(r))
            if rows_count > 0:
                non_empty_sheets += 1
            sheet_stats.append({"sheet": name, "rows": rows_count, "cols": cols_count})
        wb.close()
        checks["readable_xlsx"] = True
    except Exception as exc:
        checks["readable_xlsx"] = False
        errors.append(f"Итоговый файл повреждён: {exc}")

    checks["has_data"] = non_empty_sheets > 0
    if not checks["has_data"]:
        errors.append("Итоговый Excel не содержит ни одной заполненной таблицы.")

    checks["sources_unchanged"] = all(_file_sha256(p) == source_hashes_before[str(p)] for p in sources)
    if not checks["sources_unchanged"]:
        errors.append("Обнаружено изменение исходных файлов.")

    return {
        "passed": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "sheets": sheet_stats,
    }


def run_universal_excel_ai(
    sources: list[Path],
    instruction: str,
    output_path: Path,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Универсальный конвейер: инспекция -> генерация кода Gemini -> запуск -> автоисправление -> постпроверка."""
    source_hashes_before = {str(p): _file_sha256(p) for p in sources}
    schemas = inspect_sources_for_ai(sources)

    last_error: str | None = None
    last_code: str | None = None
    explanation = ""
    summary: dict[str, Any] = {}
    verification: dict[str, Any] = {"passed": False, "checks": {}, "errors": ["Не выполнено"], "sheets": []}

    for attempt in range(1, max_attempts + 1):
        try:
            code, explanation = _generate_excel_script(
                instruction=instruction,
                schemas=schemas,
                previous_error=last_error,
                previous_code=last_code,
            )
            last_code = code
            if output_path.exists():
                output_path.unlink()
            summary = _run_script_isolated(
                code=code,
                sources=sources,
                output_path=output_path,
                work_dir=output_path.parent,
            )
            verification = verify_universal_output(output_path, source_hashes_before, sources)
            if verification["passed"]:
                break
            last_error = "; ".join(verification["errors"])
        except Exception as exc:
            last_error = str(exc)
            verification = {
                "passed": False,
                "checks": {"execution": False},
                "errors": [last_error],
                "sheets": [],
            }

    total_rows = sum(s["rows"] for s in verification.get("sheets", []))
    stats = dict(summary.get("stats") or {})
    stats.setdefault("sheets_count", len(verification.get("sheets", [])))
    stats.setdefault("rows_written", total_rows)
    stats.setdefault("source_files", len(sources))

    return {
        "passed": bool(verification.get("passed")),
        "attempts": attempt,
        "message": summary.get("message") or explanation or "Задача выполнена универсальным Excel AI.",
        "stats": stats,
        "added_columns": summary.get("columns") or [],
        "verification": verification,
    }
