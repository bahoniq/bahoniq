
# -*- coding: utf-8 -*-
"""Координатор операций ANALYTICS AI."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Callable

from .analytics import analyze_matrix
from .ai_interpreter import generate_ai_analysis
from .config import DEFAULT_OUTPUT_DIR
from .excel_reader import read_excel
from .history import add_record
from .pdf_builder import build_analytics_pdf
from .pptx_builder import build_analytics_pptx
from .report_engine import build_report_model


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


def _apply_ai_to_report_model(
    report_model: dict[str, Any], ai_analysis: dict[str, Any]
) -> dict[str, Any]:
    """Makes Qwen's research narrative authoritative; Python keeps numbers."""
    model = dict(report_model)
    if ai_analysis.get("report_title"):
        model["title"] = str(ai_analysis["report_title"])
    if ai_analysis.get("report_subtitle"):
        model["subtitle"] = str(ai_analysis["report_subtitle"])
    if ai_analysis.get("domain"):
        model["domain"] = str(ai_analysis["domain"])
    model["goal"] = str(ai_analysis["summary"])
    model["tasks"] = list(ai_analysis.get("research_plan") or model.get("tasks", []))
    model["findings"] = [
        {"text": str(text), "source": "Qwen"}
        for text in ai_analysis.get("findings", [])
    ]
    model["risks"] = [
        str(text).strip()
        for text in ai_analysis.get("risks", [])
        if str(text).strip()
    ]
    model["recommendations"] = [
        str(text).strip()
        for text in ai_analysis.get("recommendations", [])
        if str(text).strip()
    ]
    model["notes"] = list(dict.fromkeys(
        [*model.get("notes", []), *ai_analysis.get("limitations", [])]
    ))

    stories = [s for s in ai_analysis.get("stories", []) if isinstance(s, dict)]
    pages = []
    used = set()
    originals = list(model.get("pages", []))

    def norm(value: Any) -> str:
        return " ".join(str(value or "").casefold().replace("ё", "е").split())

    stop_words = {
        "структура", "анализ", "динамика", "перекрестный", "срез",
        "группам", "группы", "показатель", "ключевой", "значений",
        "число", "записей", "среднее", "сумма", "медиана",
        "для", "или", "при", "как", "без", "над", "под", "все", "это",
        "его", "она", "они", "доля", "доли", "итог", "итого", "всего",
    }

    def meaningful_tokens(text: str) -> set[str]:
        import re
        words = re.findall(r"[0-9a-zа-яіїєґәіңғүұқөһ]{3,}", norm(text))
        return {w[:5] for w in words if w not in stop_words}

    def bind_story_to_page(story: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
        page = dict(original)
        page["title"] = str(story.get("headline") or page.get("title", ""))
        evidence = str(story.get("evidence") or "").strip()
        interpretation = str(story.get("interpretation") or "").strip()
        page["lead"] = " ".join(x for x in (evidence, interpretation) if x)
        action_text = str(story.get("action") or "").strip()
        limitation_text = str(story.get("limitation") or "").strip()
        if action_text:
            page["action"] = action_text
        if limitation_text:
            page["limitation"] = limitation_text
        additions = [limitation_text, action_text]
        page["note"] = " ".join(
            x for x in [str(page.get("note") or "").strip(), *additions] if x
        )
        return page

    # Qwen определяет состав отчёта, а не просто украшает заголовки всех
    # технически рассчитанных кандидатов. Один story создаёт не более одной
    # страницы; максимум восемь аналитических страниц.
    unmatched_stories = []
    for index, story in enumerate(stories[:8]):
        topic = norm(story.get("topic"))
        if not topic:
            continue
        story_type = norm(story.get("story_type"))
        t_tokens = meaningful_tokens(topic)
        candidates = []
        for position, original in enumerate(originals):
            if position in used:
                continue
            title_key = norm(original.get("title"))
            o_tokens = meaningful_tokens(title_key)
            overlap = len(t_tokens & o_tokens)
            is_substring = (topic in title_key or title_key in topic)
            is_token_match = (
                overlap > 0
                and t_tokens
                and overlap >= min(len(t_tokens), len(o_tokens))
            )
            if is_substring or is_token_match:
                priority = 0
                if topic == title_key:
                    priority -= 50
                elif is_substring:
                    priority -= 15
                priority -= overlap * 12
                if title_key.startswith("структура:") and len(t_tokens) <= 1:
                    priority -= 15
                if title_key.startswith("перекрестный срез:") and (story_type == "cross" or overlap >= 2):
                    priority -= 25
                if title_key.startswith("динамика:") and story_type != "time":
                    priority += 30
                if " по группам:" in title_key and story_type not in {"comparison", "cross", "numeric"} and overlap < 2:
                    priority += 10
                candidates.append((priority, position, original))
        if not candidates:
            unmatched_stories.append(story)
            continue
        _, position, original = min(candidates, key=lambda item: (item[0], item[1]))
        used.add(position)
        pages.append(bind_story_to_page(story, original))

    # Если часть сюжетов использовала обобщённый или свободный topic, связываем
    # их с оставшимися расчётными блоками по упоминанию показателей в тексте.
    if unmatched_stories and len(pages) < 8:
        still_unmatched = []
        for story in unmatched_stories:
            if len(pages) >= 8:
                break
            story_text = norm(f"{story.get('topic', '')} {story.get('headline', '')} {story.get('evidence', '')}")
            s_tokens = meaningful_tokens(story_text)
            best_candidates = []
            for position, original in enumerate(originals):
                if position in used:
                    continue
                title_key = norm(original.get("title"))
                if title_key.startswith("динамика:") and norm(story.get("story_type")) != "time":
                    continue
                o_tokens = meaningful_tokens(title_key)
                lead_tokens = meaningful_tokens(str(original.get("lead") or ""))
                title_overlap = len(s_tokens & o_tokens)
                lead_overlap = len(s_tokens & lead_tokens)
                score = title_overlap * 3 + lead_overlap
                if score > 0:
                    best_candidates.append((-score, position, original))
            if best_candidates:
                _, pos, orig = min(best_candidates, key=lambda item: (item[0], item[1]))
                used.add(pos)
                pages.append(bind_story_to_page(story, orig))
            else:
                still_unmatched.append(story)

        if len(pages) < 2 and still_unmatched:
            for story in still_unmatched:
                if len(pages) >= 8:
                    break
                fallback_orig = next(
                    (
                        (pos, orig) for pos, orig in enumerate(originals)
                        if pos not in used
                        and not norm(orig.get("title")).startswith("динамика:")
                    ),
                    None,
                )
                if not fallback_orig:
                    break
                pos, orig = fallback_orig
                used.add(pos)
                pages.append(bind_story_to_page(story, orig))

    if len(pages) < 2:
        raise ReportGenerationError(
            "Qwen сформировала сюжеты, которые не соответствуют рассчитанным "
            "показателям. Отчёт не создан, чтобы не выдавать шаблонные страницы."
        )
    model["pages"] = pages
    model["ai_analysis"] = ai_analysis
    return model


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
    ai_model: str | None = None,
    report_depth: str = "Полный аудит (Все категории, 8+ стр)",
) -> dict[str, Any]:
    """
    Формирует аналитический PDF для выбранного листа.

    Исходный Excel не изменяется. Свободное задание разбирается через Ollama,
    точный план и общий обзор работают локально. Все числа считает Python.
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

        report_progress(40, "Определение показателей и структуры данных")

        analysis = analyze_matrix(matrix)

        report_progress(48, "Подготовка аналитики и выводов BahonIQ AI")
        try:
            ai_result = generate_ai_analysis(
                matrix=matrix,
                analytics=analysis,
                title=title,
                description=description,
                report_profile=report_profile,
                audience=audience,
                model=ai_model,
            )
            ai_analysis = _normalize_ai_result(ai_result)
            _require_real_ai(ai_analysis)
        except ReportGenerationError:
            raise
        except Exception as exc:
            LOGGER.exception("Не удалось выполнить ИИ-интерпретацию отчёта.")
            raise ReportGenerationError(
                f"ИИ-анализ не выполнен. Отчёт не создан. Причина: {exc}"
            ) from exc

        report_model = {}
        output_path: Path | None = None
        presentation_path: Path | None = None

        folder = Path(output_dir or DEFAULT_OUTPUT_DIR).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".report_", dir=folder) as staging:
            if "pdf" in formats:
                report_progress(68, "Верстка профессионального PDF и диаграмм")
                output_path = Path(build_analytics_pdf(
                    matrix=matrix,
                    title=title,
                    source_name=source_path.name,
                    sheet_name=sheet_name,
                    output_dir=staging,
                    description=description,
                    include_source_table=include_source_table,
                    orientation=orientation,
                    ai_analysis=ai_analysis,
                    report_profile=report_profile,
                    audience=audience,
                    report_depth=report_depth,
                ))
            if "pptx" in formats:
                report_progress(82, "Сборка редактируемой PowerPoint-презентации")
                presentation_path = Path(build_analytics_pptx(
                    matrix=matrix,
                    title=title,
                    output_dir=staging,
                    description=description,
                    ai_analysis=ai_analysis,
                    report_profile=report_profile,
                    audience=audience,
                ))
            for artifact in (output_path, presentation_path):
                if artifact and (not artifact.is_file() or not artifact.stat().st_size):
                    raise ReportGenerationError("Итоговый файл не создан или оказался пустым.")
            if output_path:
                output_path = output_path.replace(folder / output_path.name)
            if presentation_path:
                presentation_path = presentation_path.replace(folder / presentation_path.name)

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
            "report_plan": report_model.get("plan", {}) if isinstance(report_model, dict) else {},
            "report_model": report_model if isinstance(report_model, dict) else {},
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
