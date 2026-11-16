# -*- coding: utf-8 -*-
"""Генератор персональной PDF-книги «От А до Я: Python, SQL и Архитектура BahonIQ Work Center».

Использует ReportLab с обязательной регистрацией кириллического TTF-шрифта (DejaVuSans / Arial / Segoe UI),
читает реальные файлы репозитория BahonIQ и формирует структурированную книгу-учебник.
"""

from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai_service import generate_text
from .db import PROJECT_ROOT, get_conn_lessons_all, get_roadmap_data

FONT_REG = "AcademyCyrillic"
FONT_BOLD = "AcademyCyrillic-Bold"


def _register_cyrillic_fonts() -> None:
    """Находит и регистрирует TTF-шрифт с полной поддержкой кириллицы (Windows + Linux Render + matplotlib)."""
    if FONT_REG in pdfmetrics.getRegisteredFontNames():
        return

    candidates: list[tuple[Path, Path]] = []

    # 1. Шрифты DejaVuSans из установленного пакета matplotlib (гарантированно есть и на Render, и на ПК)
    try:
        import matplotlib
        mpl_ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        candidates.append((mpl_ttf / "DejaVuSans.ttf", mpl_ttf / "DejaVuSans-Bold.ttf"))
    except Exception:
        pass

    # 2. Системные шрифты Linux (Render) и Windows
    win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates.extend([
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
         Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
        (win_fonts / "segoeui.ttf", win_fonts / "segoeuib.ttf"),
        (win_fonts / "arial.ttf", win_fonts / "arialbd.ttf"),
    ])

    for reg_path, bold_path in candidates:
        if reg_path.is_file() and bold_path.is_file():
            pdfmetrics.registerFont(TTFont(FONT_REG, str(reg_path)))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold_path)))
            return

    raise RuntimeError("Не найден кириллический TTF-шрифт для генерации PDF.")


def _xml_escape(text: str) -> str:
    """Безопасное экранирование текста для Paragraph в ReportLab."""
    s = str(text or "")
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Превращаем **жирный** в <b>...</b>
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


def _inspect_live_repository() -> list[dict[str, str]]:
    """Читает реальные ключевые файлы репозитория BahonIQ Work Center для раздела архитектуры в книге."""
    files_to_read = [
        ("main.py", "Точка входа десктопного приложения и инициализация Splash-экрана"),
        ("config.py", "Глобальная конфигурация, цветовые палитры тем и список внешних систем"),
        ("ai_service.py", "Единое ИИ-ядро проекта: интеграция с Google Gemini Flash 24/7 и потоковая генерация"),
        ("web_app/server.py", "Главный FastAPI-сервер: маршрутизация всех API-эндпоинтов и статики"),
        ("web_app/modules/wiki/service.py", "Сервис базы знаний Platonus Wiki AI (SQLite + пакетная ИИ-каталогизация + RAG)"),
        ("web_app/modules/code_academy/db.py", "Слой базы данных BahonIQ Academy: 4 этапа обучения и хранение прогресса"),
        ("web_app/static/index.html", "Единый каркас интерфейса (Dashboard + модульные секции)"),
        ("web_app/static/app.js", "Клиентская логика, управление темой и взаимодействие с FastAPI"),
    ]

    inspected: list[dict[str, str]] = []
    for rel_path, role_desc in files_to_read:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.is_file():
            continue
        try:
            raw = full_path.read_text(encoding="utf-8", errors="replace")
            lines = raw.splitlines()
            total_lines = len(lines)
            # Извлекаем сигнатуры функций/классов/маршрутов из реального файла
            signatures = [
                ln.strip() for ln in lines
                if re.match(r"^(@app\.(get|post|put|delete)|def\s+|async\s+def\s+|class\s+)", ln.strip())
            ][:14]
            snippet = "\n".join(lines[:32])
            inspected.append({
                "path": rel_path,
                "role": role_desc,
                "total_lines": str(total_lines),
                "signatures": "\n".join(signatures) if signatures else "Модуль разметки / стилей",
                "snippet": snippet,
            })
        except Exception:
            continue
    return inspected


def build_academy_pdf_book() -> bytes:
    """Собирает персональную PDF-книгу «От А до Я» в памяти и возвращает байты PDF."""
    _register_cyrillic_fonts()

    roadmap = get_roadmap_data()
    all_lessons = get_conn_lessons_all()
    live_files = _inspect_live_repository()

    # Опциональное резюме архитектуры от Gemini Flash по реальному списку файлов проекта
    files_summary_prompt = "\n".join(
        f"- {f['path']} ({f['total_lines']} строк): {f['role']}" for f in live_files
    )
    ai_arch_intro = (
        "Проект BahonIQ Work Center построен по модульной клиент-серверной архитектуре. "
        "Серверная часть работает на FastAPI (web_app/server.py), хранит структурированные данные в таблицах SQLite "
        "(wiki.db, phonebook.db, academy.db) и обращается к облачной модели Google Gemini Flash через единый шлюз ai_service.py. "
        "Фронтенд реализован как быстрое одностраничное приложение (SPA) в тёмном корпоративном стиле, которое одинаково "
        "работает в браузере на Render и внутри настольного клиента."
    )
    try:
        generated = generate_text(
            prompt=(
                f"Реальные файлы репозитория BahonIQ Work Center:\n{files_summary_prompt}\n\n"
                "Напиши краткое, живое и понятное введение (1 абзац, 5-6 предложений) для учебной книги о том, "
                "как эти файлы связаны между собой и как работает наш проект от клика пользователя до ответа БД и ИИ."
            ),
            system_instruction="Ты — главный архитектор проекта BahonIQ Work Center. Пиши живо, понятно и без воды.",
            temperature=0.2,
            timeout=15,
        )
        if generated and len(str(generated).strip()) > 40:
            ai_arch_intro = str(generated).strip()
    except Exception:
        pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="BahonIQ Academy — Книга разработчика От А до Я",
        author="BahonIQ Work Center & Gemini Flash",
    )

    base_styles = getSampleStyleSheet()
    st_title = ParagraphStyle(
        "BookTitle",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6,
    )
    st_subtitle = ParagraphStyle(
        "BookSub",
        parent=base_styles["Normal"],
        fontName=FONT_REG,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    st_h1 = ParagraphStyle(
        "BookH1",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=15,
        leading=20,
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=12,
        spaceAfter=8,
    )
    st_h2 = ParagraphStyle(
        "BookH2",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=5,
    )
    st_body = ParagraphStyle(
        "BookBody",
        parent=base_styles["Normal"],
        fontName=FONT_REG,
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    st_code = ParagraphStyle(
        "BookCode",
        parent=base_styles["Code"],
        fontName=FONT_REG,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
        borderPadding=6,
        leftIndent=4,
        rightIndent=4,
        spaceBefore=4,
        spaceAfter=8,
    )

    story: list[Any] = []

    # 1. ТИТУЛЬНЫЙ БЛОК И СВОДКА ПРОГРЕССА
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    story.append(Paragraph("BAHONIQ WORK CENTER • AI ACADEMY", st_subtitle))
    story.append(Paragraph("Персональная книга-учебник «От А до Я»", st_title))
    story.append(
        Paragraph(
            f"Полный курс Python, SQL (SQLite) и живой разбор архитектуры проекта BahonIQ Work Center. "
            f"Дата сборки: {now_str}. Пройдено тем: {roadmap['completed_lessons']} из {roadmap['total_lessons']} ({roadmap['overall_percent']}%).",
            st_subtitle,
        )
    )

    # Таблица прогресса по 4 этапам
    table_data = [["Этап программы", "Описание", "Прогресс"]]
    for st in roadmap.get("stages", []):
        table_data.append([
            st["title"],
            st["subtitle"],
            f"{st['completed_lessons']} / {st['total_lessons']} ({st['percent']}%)",
        ])

    t = Table(table_data, colWidths=[62 * mm, 76 * mm, 38 * mm])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT_REG),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ])
    )
    story.append(t)
    story.append(Spacer(1, 12))

    # 2. РАЗДЕЛ АРХИТЕКТУРЫ РЕАЛЬНОГО ПРОЕКТА BAHONIQ WORK CENTER
    story.append(Paragraph("Часть I. Архитектура проекта BahonIQ Work Center (Реальный код)", st_h1))
    story.append(Paragraph(_xml_escape(ai_arch_intro), st_body))

    for f_info in live_files:
        story.append(
            Paragraph(
                _xml_escape(f"Файл: {f_info['path']} ({f_info['total_lines']} строк) — {f_info['role']}"),
                st_h2,
            )
        )
        story.append(
            Paragraph(
                _xml_escape("Ключевые функции, классы и маршруты в этом файле:"),
                st_body,
            )
        )
        story.append(Preformatted(f_info["signatures"][:900], st_code))
        story.append(Paragraph(_xml_escape("Фрагмент реального исходного кода из репозитория:"), st_body))
        story.append(Preformatted(f_info["snippet"][:1100], st_code))

    story.append(PageBreak())

    # 3. ПОЛНЫЙ КОНСПЕКТ ВСЕХ 4 ЭТАПОВ И УРОКОВ (PYTHON, SQL, АРХИТЕКТУРА, ПОЛИГОН)
    story.append(Paragraph("Часть II. Полный учебник по всем 4 этапам программы", st_h1))

    current_stage = None
    for les in all_lessons:
        if les["stage_title"] != current_stage:
            current_stage = les["stage_title"]
            story.append(Spacer(1, 6))
            story.append(Paragraph(_xml_escape(current_stage), st_h1))

        status_mark = "[ПРОЙДЕНО]" if les["completed"] else "[В ПРОЦЕССЕ]"
        story.append(Paragraph(_xml_escape(f"{les['title']} {status_mark}"), st_h2))
        story.append(Paragraph(_xml_escape(les["summary"]), st_body))

        # Очищаем блоки ``` из теории для аккуратной вёрстки в PDF
        theory_clean = re.sub(r"```[a-zA-Z]*", "", les["ai_theory"] or "").strip()
        for para in theory_clean.split("\n\n"):
            p_str = para.strip()
            if p_str:
                story.append(Paragraph(_xml_escape(p_str).replace("\n", "<br/>"), st_body))

        story.append(Paragraph(_xml_escape(f"Практическое задание: {les['task_prompt']}"), st_body))
        code_to_show = (les.get("user_code") or les.get("starter_code") or "").strip()
        if code_to_show:
            story.append(Preformatted(code_to_show[:900], st_code))

    doc.build(story)
    return buf.getvalue()
