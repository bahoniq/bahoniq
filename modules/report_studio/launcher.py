
# -*- coding: utf-8 -*-
"""Координатор операций ANALYTICS AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from .analytics import analyze_matrix
from .ai_interpreter import generate_ai_analysis
from .excel_reader import read_excel
from .history import add_record
from .pdf_builder import build_analytics_pdf
from .pptx_builder import build_analytics_pptx


LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]


class ReportGenerationError(Exception):
    """Ошибка формирования отчёта."""


def _safe_progress(
    callback: ProgressCallback | None,
    percent: int,
    message: str,
) -> None:
    """Обновляет прогресс, не прерывая работу из-за ошибки UI."""

    if callback is None:
        return

    try:
        callback(percent, message)
    except Exception:
        LOGGER.debug(
            "Не удалось обновить индикатор прогресса.",
            exc_info=True,
        )


def _normalize_ai_result(result: Any) -> dict[str, Any]:
    """Нормализует только подтверждённый ответ Ollama/Qwen."""

    if not isinstance(result, dict):
        raise ReportGenerationError(
            "ИИ-анализ не выполнен: модуль Qwen вернул неизвестный формат."
        )

    normalized = dict(result)

    normalized.setdefault("available", False)
    normalized.setdefault("source", "")
    normalized.setdefault("model", None)
    normalized.setdefault("summary", "")
    normalized.setdefault("findings", [])
    normalized.setdefault("risks", [])
    normalized.setdefault("recommendations", [])
    normalized.setdefault("limitations", [])
    normalized.setdefault("warning", "")

    for key in ("summary", "warning", "source", "model"):
        value = normalized.get(key)

        if value is not None and not isinstance(value, str):
            normalized[key] = str(value)

    for key in (
        "findings",
        "risks",
        "recommendations",
        "limitations",
    ):
        value = normalized.get(key)

        if isinstance(value, str):
            normalized[key] = [value.strip()] if value.strip() else []

        elif isinstance(value, (list, tuple)):
            normalized[key] = [
                str(item).strip()
                for item in value
                if item is not None and str(item).strip()
            ]

        else:
            normalized[key] = []

    normalized["available"] = bool(normalized["available"])

    source = str(normalized.get("source") or "").strip().lower()

    if source not in {"ollama", "fallback"}:
        source = "ollama" if normalized["available"] else "fallback"

    normalized["source"] = source

    return normalized


def _require_real_ai(result: dict[str, Any]) -> None:
    """Запрещает выдавать резервный текст за результат Qwen."""
    if result.get("source") != "ollama" or not result.get("available"):
        diagnostic = str(
            result.get("diagnostic") or result.get("warning") or
            "Ollama/Qwen не вернула подтверждённый результат."
        )
        raise ReportGenerationError(f"ИИ-анализ не выполнен: {diagnostic}")
    if not result.get("summary") or not result.get("findings"):
        raise ReportGenerationError(
            "ИИ-анализ не выполнен: Qwen вернула неполный ответ без выводов."
        )
    stories = result.get("stories")
    if not isinstance(stories, list) or len(stories) < 2:
        raise ReportGenerationError(
            "ИИ-анализ не выполнен: Qwen не сформировала аналитические сюжеты."
        )


def inspect_excel(path: str | Path) -> dict[str, Any]:
    """Читает Excel и возвращает сведения о листах для интерфейса."""

    source_path = Path(path).expanduser()

    try:
        result = read_excel(source_path)

    except Exception as exc:
        raise ReportGenerationError(
            f"Не удалось прочитать Excel-файл "
            f"«{source_path.name}»: {exc}"
        ) from exc

    sheets = []

    for sheet in result.get("sheets", []):
        matrix = sheet.get("matrix", [])
        analysis = analyze_matrix(matrix)

        sheets.append({
            "name": sheet.get("name", ""),
            "row_count": analysis.get("row_count", 0),
            "column_count": analysis.get("column_count", 0),
            "empty_cells": analysis.get("quality", {}).get(
                "empty_cells", 0
            ),
            "warnings": sheet.get("warnings", []),
            "matrix": matrix,
            "analysis": analysis,
        })

    return {
        "path": result.get("path", str(source_path)),
        "format": result.get("format", source_path.suffix.lower()),
        "sheets": sheets,
        "warnings": result.get("warnings", []),
    }


def generate_report(
    source_path: str | Path,
    sheet_name: str,
    title: str = "Аналитический отчёт",
    output_dir: str | Path | None = None,
    description: str = "",
    include_source_table: bool = False,
    orientation: str = "auto",
    output_formats: tuple[str, ...] = ("pdf", "pptx"),
    progress: ProgressCallback | None = None,
    report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> dict[str, Any]:
    """
    Формирует аналитический PDF для выбранного листа.

    Исходный Excel не изменяется. Без подтверждённого ответа Ollama/Qwen
    отчёт не создаётся.
    """

    source_path = Path(source_path).expanduser()
    formats = tuple(dict.fromkeys(
        str(item).strip().lower() for item in output_formats
        if str(item).strip().lower() in {"pdf", "pptx"}
    ))
    if not formats:
        raise ReportGenerationError("Не выбран формат итогового отчёта.")

    def report_progress(percent: int, message: str) -> None:
        _safe_progress(progress, percent, message)

    try:
        report_progress(5, "Чтение исходного Excel-файла")

        if not source_path.exists():
            raise ReportGenerationError(
                f"Файл не найден: «{source_path}»."
            )

        if not source_path.is_file():
            raise ReportGenerationError(
                f"Указанный путь не является файлом: «{source_path}»."
            )

        workbook_data = read_excel(source_path)

        report_progress(25, "Поиск выбранного листа")

        selected_sheet = next(
            (
                sheet for sheet in workbook_data.get("sheets", [])
                if sheet.get("name") == sheet_name
            ),
            None,
        )

        if selected_sheet is None:
            available_sheets = [
                str(sheet.get("name", ""))
                for sheet in workbook_data.get("sheets", [])
            ]

            if available_sheets:
                message = (
                    f"Лист «{sheet_name}» не найден в файле "
                    f"«{source_path.name}». Доступные листы: "
                    f"{', '.join(available_sheets)}."
                )
            else:
                message = (
                    f"В файле «{source_path.name}» "
                    "не обнаружено листов."
                )

            raise ReportGenerationError(message)

        matrix = selected_sheet.get("matrix", [])

        if not isinstance(matrix, (list, tuple)) or not matrix:
            raise ReportGenerationError(
                f"Лист «{sheet_name}» не содержит данных."
            )

        report_progress(40, "Анализ показателей и качества данных")

        analysis = analyze_matrix(matrix)

        report_progress(48, "Подготовка ИИ-интерпретации в Ollama")

        try:
            ai_result = generate_ai_analysis(
                matrix=matrix,
                analytics=analysis,
                title=title,
                description=description,
                report_profile=report_profile,
                audience=audience,
            )
            ai_analysis = _normalize_ai_result(ai_result)
            _require_real_ai(ai_analysis)
        except ReportGenerationError:
            raise
        except Exception as exc:
            LOGGER.exception("Не удалось выполнить ИИ-интерпретацию отчёта.")
            raise ReportGenerationError(
                f"ИИ-анализ Qwen не выполнен. Отчёт не создан. Причина: {exc}"
            ) from exc

        output_path: Path | None = None
        presentation_path: Path | None = None

        if "pdf" in formats:
            report_progress(60, "Верстка профессионального PDF и диаграмм")
            output_path = Path(build_analytics_pdf(
                matrix=matrix, title=title, source_name=source_path.name,
                sheet_name=sheet_name, output_dir=output_dir,
                description=description, include_source_table=include_source_table,
                orientation=orientation, ai_analysis=ai_analysis,
                report_profile=report_profile, audience=audience,
            )).expanduser()
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise ReportGenerationError("PDF не был создан или оказался пустым.")

        if "pptx" in formats:
            report_progress(
                78 if output_path else 60,
                "Сборка редактируемой PowerPoint-презентации",
            )
            presentation_path = Path(build_analytics_pptx(
                matrix=matrix, title=title, output_dir=output_dir,
                description=description, ai_analysis=ai_analysis,
                report_profile=report_profile, audience=audience,
            )).expanduser()
            if not presentation_path.is_file() or presentation_path.stat().st_size == 0:
                raise ReportGenerationError("PowerPoint не был создан или оказался пустым.")

        report_progress(90, "Сохранение записи в историю")

        try:
            add_record(
                source_file=str(source_path.resolve()),
                sheet_name=sheet_name,
                report_title=title,
                output_file=str((output_path or presentation_path).resolve()),
                status="success",
                rows_count=analysis.get("row_count", 0),
                columns_count=analysis.get("column_count", 0),
            )
            history_warning = ""

        except Exception:
            LOGGER.exception(
                "Отчёт создан, но запись в историю не сохранена."
            )
            history_warning = (
                "PDF сформирован, но запись в историю не сохранена."
            )

        warnings = list(workbook_data.get("warnings", []) or [])
        warnings.extend(selected_sheet.get("warnings", []) or [])

        if history_warning:
            warnings.append(history_warning)

        # Причина сбоя ИИ уже выводится отдельным диагностическим блоком UI.
        # Не добавляем её повторно в общий список предупреждений.

        report_progress(100, "Отчёт успешно сформирован")

        return {
            "success": True,
            "source_file": str(source_path.resolve()),
            "sheet_name": sheet_name,
            "output_file": str(output_path.resolve()) if output_path else "",
            "presentation_file": (
                str(presentation_path.resolve()) if presentation_path else ""
            ),
            "output_formats": list(formats),
            "analysis": analysis,
            "ai_analysis": ai_analysis,
            "warnings": warnings,
        }

    except Exception as exc:
        try:
            add_record(
                source_file=str(source_path),
                sheet_name=sheet_name,
                report_title=title,
                status="error",
                message=str(exc),
            )
        except Exception:
            LOGGER.debug(
                "Не удалось записать ошибку в историю отчётов.",
                exc_info=True,
            )

        if isinstance(exc, ReportGenerationError):
            raise

        LOGGER.exception("Ошибка формирования аналитического отчёта.")

        raise ReportGenerationError(
            f"Не удалось сформировать отчёт: {exc}"
        ) from exc
