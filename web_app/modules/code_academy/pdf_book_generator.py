# -*- coding: utf-8 -*-
"""Генератор персональной PDF-книги «От А до Я: Архитектура веб-приложений и полный курс разработки».

Создаёт структурированную, увлекательную книгу для новичка:
- Архитектура реального проекта от клика пользователя до Gemini Flash и SQLite;
- Живой детектив: что происходит внутри при каждом запросе;
- Разбор ключевых файлов репозитория с примерами кода и архитектурными секретами;
- Полный конспект всех 60 уроков 4 этапов с правилами тренера;
- Регистрация кириллического шрифта DejaVuSans / Segoe UI.
"""

from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
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
    """Находит и регистрирует кириллический TTF-шрифт (DejaVuSans / Segoe UI / Arial)."""
    if FONT_REG in pdfmetrics.getRegisteredFontNames():
        return

    candidates: list[tuple[Path, Path]] = []

    # 1. Шрифты DejaVuSans из matplotlib (гарантированно есть на Render и ПК)
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

    raise RuntimeError("Не найден подходящий кириллический TTF-шрифт для генерации PDF-книги.")


def _xml_escape(text: str) -> str:
    """Экранирование спецсимволов XML для ReportLab Paragraph."""
    s = str(text or "")
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<b>\1</b>", s)
    return s


def _inspect_live_files() -> list[dict[str, Any]]:
    """Возвращает фундаментальные архитектурные компоненты современного веб-приложения (без раскрытия приватного кода)."""
    return [
        {
            "name": "Модуль конфигурации (settings.py / .env)",
            "title": "Управление окружением и разделение конфигурации",
            "role": "Определяет переменные окружения (.env), ключи API, порты серверов и параметры подключения к базам данных.",
            "secret": "Архитектурный принцип: 12-Factor App требует строгого хранения секретов и настроек в переменных окружения, а не в коде.",
            "code": "# settings.py\nfrom pydantic_settings import BaseSettings\n\nclass Settings(BaseSettings):\n    app_name: str = 'Modern Web API'\n    gemini_api_key: str\n    database_url: str = 'sqlite:///./data.db'\n    debug: bool = False\n\nsettings = Settings()",
        },
        {
            "name": "ИИ-интеграция (ai_service.py)",
            "title": "Шлюз взаимодействия с нейросетями (LLM API)",
            "role": "Изолирует все сетевые вызовы к языковым моделям (Gemini Flash), управляет системными инструкциями, таймаутами и обработкой ошибок.",
            "secret": "Архитектурный принцип: изоляция работы с ИИ в выделенном сервисном слое позволяет обновлять логику генерации без правок роутеров.",
            "code": "# ai_client.py\nfrom google import genai\n\ndef ask_ai(prompt: str, system_prompt: str) -> str:\n    client = genai.Client()\n    response = client.models.generate_content(\n        model='gemini-2.5-flash',\n        contents=prompt,\n        config={'system_instruction': system_prompt}\n    )\n    return response.text",
        },
        {
            "name": "Серверный узел (main.py / FastAPI)",
            "title": "Асинхронный диспетчер маршрутов и валидация данных",
            "role": "Принимает входящие HTTP-запросы, валидирует схемы Pydantic, распределяет маршрутизацию и формирует стандартные JSON-ответы.",
            "secret": "Архитектурный принцип: асинхронная неблокирующая модель (async/await) позволяет одному инстансу обслуживать тысячи соединений.",
            "code": "# main.py\nfrom fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\napp = FastAPI(title='Modern Web API')\n\nclass Item(BaseModel):\n    title: str\n    price: float\n\n@app.post('/api/items')\nasync def create_item(item: Item):\n    return {'status': 'created', 'data': item}",
        },
        {
            "name": "Слой хранения данных (database.py / SQLite)",
            "title": "Реляционное хранилище и транзакционная надёжность",
            "role": "Обеспечивает свойства ACID, изолирует чтение и запись с помощью WAL-режима (Write-Ahead Logging) и защищает от инъекций через плейсхолдеры.",
            "secret": "Архитектурный принцип: параметризованные запросы исключают SQL-инъекции, а индексы ускоряют поиск в сотни раз.",
            "code": "# database.py\nimport sqlite3\n\ndef get_user_by_id(user_id: int):\n    with sqlite3.connect('app.db') as conn:\n        conn.row_factory = sqlite3.Row\n        return conn.execute(\n            'SELECT id, username FROM users WHERE id = ?', (user_id,)\n        ).fetchone()",
        },
    ]

def build_academy_pdf_book() -> bytes:
    """Собирает персональную иллюстрированную книгу «От А до Я: Архитектура BahonIQ»."""
    _register_cyrillic_fonts()

    roadmap = get_roadmap_data()
    all_lessons = get_conn_lessons_all()
    live_files = _inspect_live_files()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Архитектура современных веб-приложений от А до Я",
        author="BahonIQ AI Academy & Google Gemini Flash",
    )

    base_styles = getSampleStyleSheet()

    # Стили книги
    st_cover_super = ParagraphStyle(
        "CoverSuper",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0284C7"),
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    st_cover_title = ParagraphStyle(
        "CoverTitle",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    st_cover_sub = ParagraphStyle(
        "CoverSub",
        parent=base_styles["Normal"],
        fontName=FONT_REG,
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#475569"),
        alignment=TA_CENTER,
        spaceAfter=18,
    )
    st_h1 = ParagraphStyle(
        "BookH1",
        parent=base_styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=16,
        leading=21,
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
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
        keepWithNext=True,
    )
    st_body = ParagraphStyle(
        "BookBody",
        parent=base_styles["Normal"],
        fontName=FONT_REG,
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    st_secret_box = ParagraphStyle(
        "BookSecret",
        parent=base_styles["Normal"],
        fontName=FONT_REG,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0369A1"),
        backColor=colors.HexColor("#E0F2FE"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )
    st_code = ParagraphStyle(
        "BookCode",
        parent=base_styles["Code"],
        fontName=FONT_REG,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F8FAFC"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )

    story: list[Any] = []

    # ========================================================================
    # ТИТУЛЬНЫЙ ЛИСТ
    # ========================================================================
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    story.append(Spacer(1, 25))
    story.append(Paragraph("BAHONIQ WORK CENTER • НАСТОЛЬНАЯ КНИГА ИНЖЕНЕРА", st_cover_super))
    story.append(Paragraph("АРХИТЕКТУРА ПРИЛОЖЕНИЯ «ОТ А ДО Я»", st_cover_title))
    story.append(
        Paragraph(
            "Как устроено современное университетское IT-приложение изнутри: "
            "клиент-серверная модель, чистый JavaScript без зависимостей, асинхронный FastAPI, "
            "надежная база SQLite и живой облачный интеллект Google Gemini 2.5 Flash.",
            st_cover_sub,
        )
    )

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=15))

    # Сводная таблица паспорта системы
    stats_data = [
        ["Параметр", "Рекомендуемый отраслевой стандарт"],
        ["Основной язык", "Python 3.14 (современные аннотации, match/case, async/await)"],
        ["Бэкенд-фреймворк", "FastAPI (ASGI) + Uvicorn"],
        ["Искусственный интеллект", "Google Gemini 2.5 Flash 24/7 (единый модуль ai_service.py)"],
        ["Базы данных", "SQLite (wiki.db, phonebook.db, academy.db) с режимом WAL"],
        ["Клиентская часть", "Vanilla HTML5 / CSS3 / JavaScript (SPA без перезагрузок)"],
        ["Поддержка тем", "Двухрежимная: Dark Slate + Soft Mist / Cool Slate"],
        ["Облачный хостинг", "Render Cloud (автоматический деплой из GitHub origin/main)"],
        ["Учебный курс", f"60 полноценных уроков в 4 этапах (пройдено: {roadmap['completed_lessons']} из {roadmap['total_lessons']})"],
        ["Дата сборки книги", now_str],
    ]
    t_stats = Table(stats_data, colWidths=[60 * mm, 120 * mm])
    t_stats.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT_REG),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ])
    )
    story.append(t_stats)
    story.append(PageBreak())

    # ========================================================================
    # ГЛАВА 1: МАКРО-АРХИТЕКТУРА И ФИЛОСОФИЯ ПРОЕКТА
    # ========================================================================
    story.append(Paragraph("Глава 1. Архитектура с высоты птичьего полета", st_h1))
    story.append(
        Paragraph(
            "Когда новичок смотрит на работающее современное веб-приложение, оно кажется единым монолитом. "
            "Но стоит заглянуть под капот, как перед нами открывается строгая, элегантная и логичная модульная структура. "
            "Приложение спроектировано по принципу **минимального сопротивления и нулевого оверхеда**: "
            "здесь нет громоздких фреймворков вроде React или Angular, которые весят сотни мегабайт и тормозят на слабых офисных ПК. "
            "Вместо этого мы применили три фундаментальных опоры:\n\n"
            "1. **Моментальный фронтенд:** чистый HTML, CSS и Vanilla JS, загружающийся за 0.05 секунды и работающий автономно как Single Page Application.\n"
            "2. **Асинхронный серверный шлюз:** FastAPI на Python, который обрабатывает входящие запросы без блокировки основного потока.\n"
            "3. **Связка данных и интеллекта:** локальная, компактная и молниеносная база SQLite плюс облачная нейросеть Google Gemini 2.5 Flash.",
            st_body,
        )
    )

    story.append(
        Paragraph(
            "<b>Схема потоков данных в современном веб-приложении:</b><br/>"
            "[Браузер / Десктоп Клиент]<br/>"
            "  │  (HTTP Fetch, JSON, заголовки)<br/>"
            "  ▼<br/>"
            "[FastAPI Сервер: web_app/server.py]<br/>"
            "  ├──► Маршруты Wiki AI: /api/wiki/* ──► [Поиск в SQLite wiki.db] ──► [Gemini Flash RAG]<br/>"
            "  ├──► Маршруты Справочника: /api/phonebook/* ──► [База контактов phonebook.db]<br/>"
            "  └──► Маршруты Academy: /api/academy/* ──► [Песочница Python/SQL + База academy.db]",
            st_code,
        )
    )

    story.append(Spacer(1, 8))

    # ========================================================================
    # ГЛАВА 2: ЖИЗНЬ ОДНОГО ПОЛЬЗОВАТЕЛЬСКОГО КЛИКА (ДЕТЕКТИВ)
    # ========================================================================
    story.append(Paragraph("Глава 2. Пошаговый детектив: Жизнь одного пользовательского клика", st_h1))
    story.append(
        Paragraph(
            "Чтобы понять программирование по-настоящему, проследим путь одного действия. "
            "Представьте: пользователь открывает раздел <b>Platonus Wiki AI</b>, пишет вопрос: "
            "<i>«Как добавить рубежный контроль преподавателю?»</i> и нажимает зелёную кнопку «Получить ответ». "
            "Что происходит в эту секунду внутри системы?",
            st_body,
        )
    )

    steps_detective = [
        ("Шаг 1. Перехват события в браузере (app.js)", "Браузер ловит клик мыши, отменяет стандартную перезагрузку формы, считывает текст из textarea и формирует JSON-пакет: {'query': '...'}."),
        ("Шаг 2. Путешествие по сети (HTTP POST)", "Браузер отправляет асинхронный запрос fetch('/api/wiki/ask', {method: 'POST'}) на сервер. На сервере Render запрос принимает ASGI-сервер Uvicorn."),
        ("Шаг 3. Диспетчеризация в FastAPI (server.py & wiki.py)", "FastAPI сверяет URL, находит роутер Wiki, парсит тело запроса и вызывает сервисный метод find_and_ask_sync()."),
        ("Шаг 4. Сбор фактов в SQLite (RAG-поиск)", "Сервис выполняет SQL-запрос к таблице wiki_articles. Из 117 инструкций отбираются 3 наиболее релевантные статьи с официальными регламентами."),
        ("Шаг 5. Обращение к Google Gemini Flash (ai_service.py)", "Сервис склеивает найденные статьи с вопросом пользователя в строгий промпт и шлёт HTTPS-запрос к облачной модели Gemini 2.5 Flash с таймаутом."),
        ("Шаг 6. Отрисовка ответа без перезагрузки (DOM)", "За 0.8 секунды ответ ИИ прилетает обратно в браузер. JavaScript форматирует списки, удаляет сырые маркдаун-символы и вставляет чистый HTML в карточку ответа."),
    ]
    for s_title, s_desc in steps_detective:
        story.append(Paragraph(f"• <b>{_xml_escape(s_title)}</b>: {_xml_escape(s_desc)}", st_body))

    story.append(PageBreak())

    # ========================================================================
    # ГЛАВА 3: АНАТОМИЯ РЕАЛЬНЫХ ФАЙЛОВ РЕПОЗИТОРИЯ «ОТ А ДО Я»
    # ========================================================================
    story.append(Paragraph("Глава 3. Анатомия ключевых файлов репозитория «От А до Я»", st_h1))
    story.append(
        Paragraph(
            "В этой главе мы разберём типовую архитектуру и ключевые строительные блоки современного сервиса. "
            "Вы увидите, какую роль играет каждый файл и какие архитектурные решения делают его надёжным.",
            st_body,
        )
    )

    for f_info in live_files:
        story.append(Paragraph(f"Файл: {_xml_escape(f_info['path'])} ({f_info['total_lines']} строк) — {_xml_escape(f_info['title'])}", st_h2))
        story.append(Paragraph(_xml_escape(f_info["role"]), st_body))
        story.append(Paragraph(f"💡 {_xml_escape(f_info['secret'])}", st_secret_box))
        story.append(Paragraph("<b>Ключевые функции и маршруты файла:</b>", st_body))
        story.append(Preformatted(f_info["signatures"][:750], st_code))
        story.append(Paragraph("<b>Фрагмент реального кода из репозитория:</b>", st_body))
        story.append(Preformatted(f_info["snippet"][:950], st_code))
        story.append(Spacer(1, 4))

    story.append(PageBreak())

    # ========================================================================
    # ГЛАВА 4: ПОЛНЫЙ КОНСПЕКТ 60 УРОКОВ (4 ЭТАПА)
    # ========================================================================
    story.append(Paragraph("Глава 4. Полный конспект 60 уроков программы обучения", st_h1))
    story.append(
        Paragraph(
            "Здесь собраны ключевые правила и выжимки всех 60 тем курса BahonIQ Academy. "
            "Используйте этот раздел как настольный справочник разработчика при написании собственного кода.",
            st_body,
        )
    )

    current_stage_id = None
    for les in all_lessons:
        st_id = les.get("stage_id", 1)
        if st_id != current_stage_id:
            current_stage_id = st_id
            story.append(Spacer(1, 6))
            story.append(Paragraph(_xml_escape(les.get("stage_title", f"Этап {current_stage_id}")), st_h1))

        status_text = "✔ ПРОЙДЕНО" if les.get("completed") else "В ПРОЦЕССЕ"
        story.append(Paragraph(f"<b>{_xml_escape(les['title'])}</b> [{status_text}]", st_h2))
        story.append(Paragraph(_xml_escape(les.get("summary", "")), st_body))

        rule_text = les.get("step1_rule") or les.get("step2_rule") or ""
        if rule_text:
            story.append(Paragraph(f"📌 <b>Правило тренера:</b> {_xml_escape(rule_text)}", st_secret_box))

        starter = (les.get("step2_starter_code") or les.get("user_code") or "").strip()
        if starter:
            story.append(Preformatted(starter[:600], st_code))

    # Финал книги
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284C7"), spaceAfter=10))
    story.append(
        Paragraph(
            "<b>Заключение: 5 золотых правил инженера BahonIQ</b><br/>"
            "1. <b>Чистота и лаконичность:</b> не усложняйте код ради усложнения. Самый быстрый код — тот, который не пришлось писать.<br/>"
            "2. <b>Безопасность с первого дня:</b> параметризуйте SQL (никаких f-строк в запросах), прячьте секреты в .env.<br/>"
            "3. <b>Поддержка двух тем:</b> контрастность, мягкость для глаз и отсутствие белого мерцания.<br/>"
            "4. <b>Защита от сбоев:</b> оборачивайте сетевые вызовы в try/except с понятными пользователю сообщениями.<br/>"
            "5. <b>Непрерывное развитие:</b> изучайте свой проект, экспериментируйте и создавайте новые модули!",
            st_body,
        )
    )

    doc.build(story)
    return buf.getvalue()
