
# -*- coding: utf-8 -*-
"""Компактный генератор аналитических PDF для ANALYTICS AI."""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.platypus import (
    CondPageBreak,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .analytics import analyze_matrix


LOGGER = logging.getLogger(__name__)

PAGE_LIMIT = 18
MAX_NUMERIC_COLUMNS = 8
MAX_CATEGORICAL_COLUMNS = 5
MAX_DATE_COLUMNS = 5
MAX_INSIGHTS = 12
MAX_TABLE_ROWS = 12
MAX_SOURCE_ROWS = 40
FONT_REGULAR = "BahonIQSans"
FONT_BOLD = "BahonIQSans-Bold"

NAVY = colors.HexColor("#183153")
BLUE = colors.HexColor("#2563EB")
PALE_BLUE = colors.HexColor("#EEF4FF")
PALE_GREY = colors.HexColor("#F3F5F8")
TEXT = colors.HexColor("#263238")
MUTED = colors.HexColor("#667085")
BORDER = colors.HexColor("#D9E0E8")
GREEN = colors.HexColor("#16805D")
ORANGE = colors.HexColor("#B76E00")
RED = colors.HexColor("#B42318")


def _register_fonts() -> None:
    """Подключает Unicode-шрифт, чтобы кириллица всегда отображалась."""
    module_dir = Path(__file__).resolve().parent
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        (module_dir / "fonts" / "DejaVuSans.ttf",
         module_dir / "fonts" / "DejaVuSans-Bold.ttf"),
        (windows_dir / "arial.ttf", windows_dir / "arialbd.ttf"),
        (windows_dir / "segoeui.ttf", windows_dir / "segoeuib.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
         Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
        (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    ]
    pair = next(
        ((regular, bold) for regular, bold in candidates
         if regular.is_file() and bold.is_file()),
        None,
    )
    if pair is None:
        raise RuntimeError(
            "Не найден Unicode-шрифт. Установите Arial, Segoe UI, "
            "DejaVu Sans или поместите DejaVuSans.ttf и "
            "DejaVuSans-Bold.ttf в папку fonts рядом с pdf_builder.py."
        )
    regular, bold = pair
    if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))


def _safe_text(value: Any, limit: int = 350) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        text = value.strftime("%d.%m.%Y %H:%M")
    elif isinstance(value, date):
        text = value.strftime("%d.%m.%Y")
    else:
        text = str(value)

    text = text.strip()

    if len(text) > limit:
        text = text[:limit].rstrip() + "…"

    return text


def _escape(value: Any, limit: int = 350) -> str:
    """Экранирует пользовательский текст для ReportLab Paragraph."""

    text = _safe_text(value, limit)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _filename(text: str) -> str:
    text = _safe_text(text, 100)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:80] or "Аналитический_отчёт"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(2, 10000):
        candidate = path.with_name(
            f"{path.stem}_{index}{path.suffix}"
        )
        if not candidate.exists():
            return candidate

    raise RuntimeError("Не удалось подобрать имя для PDF-файла.")


def _format_number(value: Any) -> str:
    if value is None:
        return "—"

    if isinstance(value, bool):
        return "Да" if value else "Нет"

    try:
        number = float(value)
        if number != number or abs(number) == float("inf"):
            return "—"

        if number.is_integer():
            return f"{int(number):,}".replace(",", " ")

        return f"{number:,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError, OverflowError):
        return _safe_text(value, 80)


def _compact_number(value: Any) -> str:
    """Читаемая подпись оси без научной нотации."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return _safe_text(value, 40)
    absolute = abs(number)
    for divisor, suffix in (
        (1_000_000_000_000, "трлн"),
        (1_000_000_000, "млрд"),
        (1_000_000, "млн"),
        (1_000, "тыс."),
    ):
        if absolute >= divisor:
            shown = number / divisor
            digits = 0 if abs(shown) >= 100 else 1 if abs(shown) >= 10 else 2
            return f"{shown:.{digits}f}".replace(".", ",") + f" {suffix}"
    return _format_number(number)


def _make_styles():
    _register_fonts()
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitleCustom",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=25,
        leading=31,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=8 * mm,
    ))

    styles.add(ParagraphStyle(
        name="CoverEyebrowCustom",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        tracking=1.2,
        textColor=colors.HexColor("#AFC9FF"),
        spaceAfter=5 * mm,
    ))

    styles.add(ParagraphStyle(
        name="CoverTitleLightCustom",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=27,
        leading=33,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    ))

    styles.add(ParagraphStyle(
        name="CoverSubtitleLightCustom",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#DCE7FA"),
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitleCustom",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=11,
        leading=16,
        textColor=MUTED,
        spaceAfter=5 * mm,
    ))

    styles.add(ParagraphStyle(
        name="SectionCustom",
        parent=styles["Heading1"],
        fontName=FONT_BOLD,
        fontSize=15,
        leading=19,
        textColor=NAVY,
        spaceBefore=5 * mm,
        spaceAfter=3 * mm,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SubsectionCustom",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=10,
        leading=13,
        textColor=BLUE,
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=TEXT,
        spaceAfter=2 * mm,
    ))

    styles.add(ParagraphStyle(
        name="SmallCustom",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    ))

    styles.add(ParagraphStyle(
        name="BulletCustom",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=12,
        leftIndent=4 * mm,
        firstLineIndent=-3 * mm,
        textColor=TEXT,
        spaceAfter=1.5 * mm,
    ))

    styles.add(ParagraphStyle(
        name="CoverKpiCustom",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=17,
        leading=21,
        textColor=NAVY,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="CoverLabelCustom",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=11,
        textColor=MUTED,
        alignment=TA_CENTER,
    ))

    return styles


def _paragraph(text: Any, style, limit: int = 350) -> Paragraph:
    return Paragraph(_escape(text, limit), style)


def _section(title: str, styles) -> list:
    return [
        Paragraph(_escape(title, 100), styles["SectionCustom"]),
        Spacer(1, 1.5 * mm),
    ]


def _bullet(text: Any, styles) -> Paragraph:
    return Paragraph(
        "• " + _escape(text, 500),
        styles["BulletCustom"],
    )


def _table(
    data: list[list[Any]],
    widths: list[float] | None = None,
    font_size: int = 8,
    repeat_rows: int = 1,
) -> Table:
    """Создаёт таблицу с повторяемым заголовком."""

    converted = []

    for row_index, row in enumerate(data):
        converted_row = []

        for value in row:
            if isinstance(value, Paragraph):
                converted_row.append(value)
            elif row_index == 0:
                converted_row.append(Paragraph(
                    f"<b>{_escape(value, 120)}</b>",
                    ParagraphStyle(
                        name="TableHeaderTmp",
                        fontName=FONT_BOLD,
                        fontSize=font_size,
                        leading=font_size + 2,
                        textColor=colors.white,
                    ),
                ))
            else:
                converted_row.append(Paragraph(
                    _escape(value, 180),
                    ParagraphStyle(
                        name="TableCellTmp",
                        fontName=FONT_REGULAR,
                        fontSize=font_size,
                        leading=font_size + 2,
                        textColor=TEXT,
                    ),
                ))

        converted.append(converted_row)

    table = Table(
        converted,
        colWidths=widths,
        repeatRows=repeat_rows,
        hAlign="LEFT",
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, PALE_GREY
        ]),
    ]))

    return table


def _kpi_cards(analysis: dict[str, Any], styles, page_width: float) -> Table:
    reportable_categories = len([
        c for c in analysis.get("categorical_columns", [])
        if c.get("reportable")
    ])
    category_columns = [
        c for c in analysis.get("categorical_columns", [])
        if c.get("reportable") and c.get("statistics", {}).get("top_values")
    ]
    dominant = max(
        category_columns,
        key=lambda c: c.get("statistics", {}).get("top_value_percent", 0),
        default=None,
    )
    dominant_share = (
        dominant.get("statistics", {}).get("top_value_percent", 0)
        if dominant else 0
    )
    age_stat = next((
        c.get("statistics", {}).get("age_statistics")
        for c in analysis.get("date_columns", [])
        if c.get("statistics", {}).get("age_statistics")
    ), None)

    items = [
        (
            analysis.get("row_count", 0),
            "Записей",
        ),
        (
            reportable_categories,
            "Сегментов для анализа",
        ),
        (
            f"{dominant_share:.1f}%".replace(".", ","),
            "Максимальная доля категории",
        ),
        (
            (f"{age_stat.get('mean')}" if age_stat else
             len([c for c in analysis.get("numeric_columns", []) if c.get("reportable")])),
            "Средний возраст, лет" if age_stat else "Числовых показателей",
        ),
    ]

    cards = []

    for value, label in items:
        value_text = _format_number(value)

        cards.append(Table(
            [[Paragraph(
                _escape(value_text, 40),
                styles["CoverKpiCustom"],
            )], [Paragraph(
                _escape(label, 80),
                styles["CoverLabelCustom"],
            )]],
            colWidths=[(page_width - 12 * mm) / 4],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]),
        ))

    row = Table(
        [cards],
        colWidths=[page_width / 4] * 4,
    )

    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ]))

    return row


def _cover_hero(title: str, styles, content_width: float) -> Table:
    """Создаёт цельный титульный блок без вывода пользовательского промпта."""
    content = [
        Paragraph(_escape(title or "Аналитический отчёт", 180), styles["ReportTitleCustom"]),
        Paragraph(
            "Ключевые показатели, структура и сравнение категорий",
            styles["ReportSubtitleCustom"],
        ),
    ]
    table = Table([[content]], colWidths=[content_width], rowHeights=[78 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 11 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11 * mm),
    ]))
    return table


def _chart_image(
    labels: list[str],
    values: list[float],
    width: float = 155 * mm,
    height: float = 70 * mm,
):
    """Создаёт график при наличии matplotlib; иначе возвращает None."""

    if not labels or not values:
        return None

    try:
        import io
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
        plt.rcParams["font.family"] = "DejaVu Sans"

        count = min(len(labels), len(values), 8)
        labels = labels[:count]
        values = values[:count]

        figure, axis = plt.subplots(figsize=(8, 3.4))
        axis.bar(range(count), values, color="#11B5AE")
        axis.set_xticks(range(count))
        axis.set_xticklabels(
            [str(label)[:22] for label in labels],
            rotation=25,
            ha="right",
            fontsize=8,
        )
        axis.grid(axis="y", alpha=0.2)
        axis.set_axisbelow(True)
        figure.tight_layout()

        buffer = io.BytesIO()
        figure.savefig(
            buffer,
            format="png",
            dpi=130,
            bbox_inches="tight",
        )
        plt.close(figure)
        buffer.seek(0)

        return Image(
            buffer,
            width=width,
            height=height,
            kind="proportional",
        )

    except Exception:
        LOGGER.debug("Не удалось построить график.", exc_info=True)
        return None


def _horizontal_chart(labels, values, width=120 * mm, height=66 * mm):
    if not labels or not values:
        return None
    try:
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
        plt.rcParams["font.family"] = "DejaVu Sans"
        count = min(len(labels), len(values), 10)
        labels = [str(x)[:30] for x in labels[:count]][::-1]
        values = [float(x) for x in values[:count]][::-1]
        fig, ax = plt.subplots(figsize=(6.2, 3.5))
        bars = ax.barh(range(count), values, color="#11B5AE")
        ax.set_yticks(range(count)); ax.set_yticklabels(labels, fontsize=7)
        ax.grid(axis="x", alpha=.2); ax.set_axisbelow(True)
        for bar, value in zip(bars, values):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                    f" {value:,.0f}".replace(",", " "), va="center", fontsize=7)
        fig.tight_layout()
        buffer = io.BytesIO(); fig.savefig(buffer, format="png", dpi=150,
                                            bbox_inches="tight", facecolor="white")
        plt.close(fig); buffer.seek(0)
        return Image(buffer, width=width, height=height, kind="proportional")
    except Exception:
        LOGGER.debug("Не удалось построить горизонтальную диаграмму.", exc_info=True)
        return None


def _stacked_share_chart(primary, secondary, rows, width=245 * mm, height=78 * mm):
    """Сравнивает структуру второй категории внутри групп первой."""
    try:
        from collections import Counter, defaultdict
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.family"] = "DejaVu Sans"

        p_index, s_index = primary["index"], secondary["index"]
        totals = Counter()
        cross = defaultdict(Counter)
        for row in rows:
            if p_index >= len(row) or s_index >= len(row):
                continue
            p, s = row[p_index], row[s_index]
            if p is None or s is None or not str(p).strip() or not str(s).strip():
                continue
            p, s = str(p).strip(), str(s).strip()
            totals[p] += 1; cross[p][s] += 1
        primary_values = [key for key, _ in totals.most_common(10)]
        secondary_totals = Counter()
        for key in primary_values:
            secondary_totals.update(cross[key])
        secondary_values = [key for key, _ in secondary_totals.most_common(7)]
        if len(primary_values) < 2 or len(secondary_values) < 2:
            return None

        fig, ax = plt.subplots(figsize=(11.5, 4.1))
        left = [0.0] * len(primary_values)
        palette = ["#11B5AE", "#304B52", "#FF6B6B", "#F2C80F",
                   "#5B8FF9", "#9270CA", "#6DC8EC"]
        for color, value in zip(palette, secondary_values):
            shares = [cross[key][value] * 100 / totals[key] for key in primary_values]
            ax.barh(range(len(primary_values)), shares, left=left,
                    label=value[:38], color=color)
            left = [a + b for a, b in zip(left, shares)]
        ax.set_yticks(range(len(primary_values)))
        ax.set_yticklabels([value[:42] for value in primary_values], fontsize=7)
        ax.set_xlim(0, 100); ax.set_xlabel("Доля внутри группы, %", fontsize=8)
        ax.grid(axis="x", alpha=.2); ax.set_axisbelow(True)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -0.18), ncol=3,
                  fontsize=7, frameon=False)
        fig.tight_layout()
        buffer = io.BytesIO(); fig.savefig(buffer, format="png", dpi=150,
                                            bbox_inches="tight", facecolor="white")
        plt.close(fig); buffer.seek(0)
        return Image(buffer, width=width, height=height, kind="proportional")
    except Exception:
        LOGGER.debug("Не удалось построить сравнительную диаграмму.", exc_info=True)
        return None


def _append_comparative_analysis(
    story: list, analysis: dict, styles, content_width: float
) -> None:
    dimensions = [c for c in analysis.get("categorical_columns", [])
                  if c.get("reportable") and
                  2 <= c.get("statistics", {}).get("unique_count", 0) <= 20]
    if len(dimensions) < 2:
        return
    primary = dimensions[0]
    comparisons = []
    for secondary in dimensions[1:]:
        if secondary.get("statistics", {}).get("unique_count", 0) <= 7:
            chart = _stacked_share_chart(
                primary, secondary, analysis.get("rows", []),
                width=min(content_width, 245 * mm),
            )
            if chart:
                comparisons.append((secondary, chart))
        if len(comparisons) >= 2:
            break
    if not comparisons:
        return
    story.append(CondPageBreak(110 * mm))
    story.extend(_section("Сравнительный анализ", styles))
    for secondary, chart in comparisons:
        story.append(Paragraph(
            f"Структура «{_escape(secondary.get('name'), 70)}» по группам "
            f"«{_escape(primary.get('name'), 70)}»",
            styles["SubsectionCustom"],
        ))
        story.append(chart)
        story.append(Spacer(1, 4 * mm))
def _append_visual_dashboard(
    story: list, analysis: dict, styles, content_width: float
) -> None:
    """Добавляет компактный дашборд и сравнения, подходящие для любой таблицы."""
    charts = []
    for column in analysis.get("categorical_columns", []):
        if not column.get("reportable"):
            continue
        stats = column.get("statistics", {})
        top = stats.get("top_values", [])
        if 2 <= stats.get("unique_count", 0) <= 100 and top:
            chart = _horizontal_chart(
                [item.get("value") for item in top],
                [item.get("count", 0) for item in top],
                width=max(70 * mm, (content_width - 10 * mm) / 2),
            )
            if chart:
                charts.append((str(column.get("name", "Распределение")), chart))
        if len(charts) >= 4:
            break
    if not charts:
        return
    story.append(CondPageBreak(95 * mm))
    story.extend(_section("Визуальный обзор", styles))
    for index in range(0, len(charts), 2):
        pair = charts[index:index + 2]
        cells = []
        for title, chart in pair:
            cells.append([Paragraph(_escape(title, 100), styles["SubsectionCustom"]), chart])
        while len(cells) < 2:
            cells.append(["", ""])
        column_width = (content_width - 4 * mm) / 2
        story.append(Table([[cells[0][0], cells[1][0]], [cells[0][1], cells[1][1]]],
                           colWidths=[column_width, column_width],
                           style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"),
                                             ("BOX", (0,0), (-1,-1), .4, BORDER),
                                             ("INNERGRID", (0,0), (-1,-1), .25, BORDER),
                                             ("LEFTPADDING", (0,0), (-1,-1), 4),
                                             ("RIGHTPADDING", (0,0), (-1,-1), 4)])))
        story.append(Spacer(1, 4 * mm))


def _append_executive_summary(
    story: list, analysis: dict, styles, content_width: float
) -> None:
    story.extend(_section("Управленческое резюме", styles))

    row_count = analysis.get("row_count", 0)
    column_count = analysis.get("column_count", 0)
    categorical_count = len([c for c in analysis.get("categorical_columns", []) if c.get("reportable")])

    story.append(_paragraph(
        f"Проанализировано {row_count} записей по {categorical_count} "
        "содержательным разрезам. Персональные и технические поля "
        "исключены из расчётов.",
        styles["BodyCustom"],
    ))

    story.append(Spacer(1, 3 * mm))
    story.append(_kpi_cards(
        analysis,
        styles,
        content_width,
    ))


def _append_quality_section(story: list, analysis: dict, styles) -> None:
    quality = analysis.get("quality", {})

    story.extend(_section("Качество данных", styles))

    data = [
        ["Проверка", "Результат"],
        ["Пустые ячейки", _format_number(quality.get("empty_cells", 0))],
        ["Доля пустых ячеек, %", _format_number(quality.get("empty_percent", 0))],
        ["Повторяющиеся строки", _format_number(quality.get("duplicate_rows", 0))],
        ["Доля повторов, %", _format_number(quality.get("duplicate_row_percent", 0))],
        ["Потенциальные выбросы", _format_number(quality.get("outlier_count", 0))],
    ]

    story.append(_table(
        data,
        widths=[90 * mm, 65 * mm],
    ))

    constant_columns = quality.get("constant_columns", [])

    if constant_columns:
        story.append(Spacer(1, 2 * mm))
        story.append(_paragraph(
            "Столбцы с единственным значением: "
            + ", ".join(_safe_text(x, 80) for x in constant_columns[:8]),
            styles["SmallCustom"],
        ))


def _append_numeric_section(story: list, analysis: dict, styles) -> None:
    columns = [column for column in analysis.get("numeric_columns", [])
               if column.get("reportable") and not column.get("identifier_like")][
                   :MAX_NUMERIC_COLUMNS]

    if not columns:
        return

    story.extend(_section("Числовые показатели", styles))

    data = [[
        "Показатель",
        "Кол-во",
        "Среднее",
        "Медиана",
        "Минимум",
        "Максимум",
    ]]

    for column in columns:
        stats = column.get("statistics", {})

        data.append([
            _safe_text(column.get("name"), 80),
            _format_number(stats.get("count")),
            _format_number(stats.get("mean")),
            _format_number(stats.get("median")),
            _format_number(stats.get("min")),
            _format_number(stats.get("max")),
        ])

    story.append(_table(
        data,
        widths=[48 * mm, 18 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm],
        font_size=7,
    ))

    outlier_columns = [
        column for column in columns
        if column.get("statistics", {}).get("outlier_count", 0)
    ]

    if outlier_columns:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            "Потенциальные выбросы",
            styles["SubsectionCustom"],
        ))

        outlier_data = [["Показатель", "Количество", "Доля, %"]]

        for column in outlier_columns[:6]:
            stats = column.get("statistics", {})
            outlier_data.append([
                _safe_text(column.get("name"), 80),
                _format_number(stats.get("outlier_count")),
                _format_number(stats.get("outlier_percent")),
            ])

        story.append(_table(
            outlier_data,
            widths=[75 * mm, 30 * mm, 30 * mm],
        ))

    # Только один общий график, чтобы не создавать по странице
    # для каждого числового столбца.
    if columns:
        first = columns[0]
        stats = first.get("statistics", {})

        labels = ["Минимум", "Медиана", "Среднее", "Максимум"]
        values = [
            stats.get("min"),
            stats.get("median"),
            stats.get("mean"),
            stats.get("max"),
        ]

        if all(isinstance(value, (int, float)) for value in values):
            chart = _chart_image(labels, [float(x) for x in values])

            if chart is not None:
                story.append(Spacer(1, 3 * mm))
                story.append(Paragraph(
                    f"Распределение характеристик: {_escape(first.get('name'), 80)}",
                    styles["SubsectionCustom"],
                ))
                story.append(chart)


def _append_categorical_section(story: list, analysis: dict, styles) -> None:
    columns = [column for column in analysis.get("categorical_columns", [])
               if column.get("reportable") and
               2 <= column.get("statistics", {}).get("unique_count", 0) <= 100][
                   :MAX_CATEGORICAL_COLUMNS]

    if not columns:
        return

    story.append(CondPageBreak(120 * mm))
    story.extend(_section("Категориальные распределения", styles))

    for column in columns:
        stats = column.get("statistics", {})
        top_values = stats.get("top_values", [])[:MAX_TABLE_ROWS]

        if not top_values:
            continue

        block = [
            Paragraph(
                _escape(column.get("name"), 100),
                styles["SubsectionCustom"],
            ),
            _paragraph(
                f"Уникальных значений: {stats.get('unique_count', 0)}. "
                f"Доля наиболее частого значения: "
                f"{stats.get('top_value_percent', 0)}%.",
                styles["BodyCustom"],
            ),
        ]

        data = [["Значение", "Количество", "Доля, %"]]

        for item in top_values:
            data.append([
                _safe_text(item.get("value"), 120),
                _format_number(item.get("count")),
                _format_number(item.get("count", 0) * 100 /
                               max(stats.get("count", 1), 1)),
            ])

        block.append(_table(
            data,
            widths=[95 * mm, 28 * mm, 28 * mm],
        ))

        story.append(KeepTogether(block))
        story.append(Spacer(1, 3 * mm))


def _append_date_section(story: list, analysis: dict, styles) -> None:
    columns = analysis.get("date_columns", [])[:MAX_DATE_COLUMNS]

    if not columns:
        return

    story.append(CondPageBreak(80 * mm))
    story.extend(_section("Даты и периоды", styles))

    ordinary_dates = [
        column for column in columns
        if not column.get("statistics", {}).get("age_statistics")
    ]
    data = [[
        "Столбец",
        "Первая дата",
        "Последняя дата",
        "Период, дней",
    ]]

    for column in ordinary_dates:
        stats = column.get("statistics", {})
        data.append([
            _safe_text(column.get("name"), 65),
            _safe_text(stats.get("min"), 30) or "—",
            _safe_text(stats.get("max"), 30) or "—",
            _format_number(stats.get("span_days", 0)),
        ])

    if len(data) > 1:
        story.append(_table(
            data,
            widths=[55 * mm, 35 * mm, 35 * mm, 30 * mm],
            font_size=7,
        ))

    for column in columns:
        age = column.get("statistics", {}).get("age_statistics")
        if not age:
            continue
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Возрастная структура: {_escape(column.get('name'), 80)}",
            styles["SubsectionCustom"],
        ))
        story.append(_paragraph(
            f"Средний возраст: {age.get('mean')} года; диапазон: "
            f"{age.get('min')}–{age.get('max')} лет.",
            styles["BodyCustom"],
        ))
        groups = age.get("groups", [])
        chart = _horizontal_chart(
            [item.get("value") for item in groups],
            [item.get("count", 0) for item in groups],
            width=150 * mm,
        )
        if chart:
            story.append(chart)


def _append_insights_section(story: list, analysis: dict, styles) -> None:
    insights = analysis.get("insights", [])[:MAX_INSIGHTS]

    if not insights:
        return

    story.extend(_section("Основные выводы", styles))

    for insight in insights:
        story.append(_bullet(insight, styles))


def _append_audit_section(story: list, analysis: dict, styles) -> None:
    audit = analysis.get("audit", {})
    if not audit:
        return
    story.extend(_section("Аудиторский вердикт", styles))
    story.append(_paragraph(
        f"{audit.get('decision', 'ОЦЕНКА НЕ СФОРМИРОВАНА')}. "
        f"Индекс качества: {audit.get('score', 0)}/100, класс {audit.get('grade', '—')}. "
        f"Критических замечаний: {audit.get('critical_count', 0)}; "
        f"высокого приоритета: {audit.get('high_count', 0)}.", styles["BodyCustom"]))
    labels = {"critical": "КРИТИЧНО", "high": "ВЫСОКИЙ", "medium": "СРЕДНИЙ", "low": "НИЗКИЙ"}
    for item in audit.get("findings", [])[:12]:
        severity = labels.get(item.get("severity"), "ЗАМЕЧАНИЕ")
        story.append(_bullet(
            f"[{severity}] {item.get('title')}. Факт: {item.get('evidence')} "
            f"Действие: {item.get('action')}", styles))


def _append_ai_section(story: list, ai_analysis: dict | None, styles) -> None:
    if not isinstance(ai_analysis, dict):
        return

    source = str(ai_analysis.get("source") or "").lower()
    summary = _safe_text(ai_analysis.get("summary"), 1800)
    findings = ai_analysis.get("findings", [])
    risks = ai_analysis.get("risks", [])
    recommendations = ai_analysis.get("recommendations", [])
    if not any((summary, findings, risks, recommendations)):
        return

    story.extend(_section("Интерпретация и рекомендации", styles))

    if summary:
        story.append(_paragraph(summary, styles["BodyCustom"], 1800))

    sections = [
        ("Фактические выводы", findings, MAX_INSIGHTS),
        ("Риски и ограничения", risks, 5),
        ("Рекомендации", recommendations, 6),
    ]

    for heading, items, limit in sections:
        if not isinstance(items, (list, tuple)) or not items:
            continue

        story.append(Paragraph(
            _escape(heading, 100),
            styles["SubsectionCustom"],
        ))

        for item in list(items)[:limit]:
            story.append(_bullet(item, styles))


def _append_source_table(
    story: list,
    analysis: dict[str, Any],
    styles,
    page_width: float,
) -> None:
    """Необязательное приложение с исходными данными."""

    headers = analysis.get("headers", [])
    rows = analysis.get("rows", [])

    if not headers or not rows:
        return

    story.append(PageBreak())
    story.extend(_section("Исходные данные — приложение", styles))

    story.append(_paragraph(
        "Этот раздел включён по запросу пользователя. "
        "Для больших таблиц он может существенно увеличить объём PDF.",
        styles["SmallCustom"],
    ))

    # Ограничиваем ширину таблицы и количество столбцов на странице.
    max_columns = min(len(headers), 8)
    display_headers = headers[:max_columns]

    data = [[_safe_text(header, 45) for header in display_headers]]

    limited_rows = rows[:MAX_SOURCE_ROWS]
    for row in limited_rows:
        display_row = []

        for index in range(max_columns):
            value = row[index] if index < len(row) else None
            display_row.append(_safe_text(value, 100))

        data.append(display_row)

    widths = [page_width / max_columns] * max_columns

    story.append(_table(
        data,
        widths=widths,
        font_size=6,
    ))
    if len(rows) > len(limited_rows):
        story.append(Spacer(1, 2 * mm))
        story.append(_paragraph(
            f"Показаны первые {len(limited_rows)} из {len(rows)} строк. "
            "Полный набор остаётся в исходном Excel-файле.", styles["SmallCustom"]))


def _page_decor(canvas, doc) -> None:
    """Добавляет номер страницы и нейтральный нижний колонтитул."""

    canvas.saveState()

    width, _ = doc.pagesize

    if doc.page > 1:
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(
            18 * mm,
            15 * mm,
            width - 18 * mm,
            15 * mm,
        )

        canvas.setFont(FONT_REGULAR, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm,
            10 * mm,
            "Аналитический отчёт",
        )
        canvas.drawRightString(
            width - 18 * mm,
            10 * mm,
            f"Страница {doc.page}",
        )

    canvas.restoreState()


def build_analytics_pdf_infographic(
    matrix: list[list],
    title: str,
    source_name: str = "",
    sheet_name: str = "",
    output_dir: str | Path | None = None,
    description: str = "",
    include_source_table: bool = False,
    orientation: str = "auto",
    ai_analysis: dict | None = None,
    report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> Path:
    """
    Создаёт компактный аналитический PDF.

    Публичная сигнатура сохранена для launcher.py.
    Исходная таблица не добавляется, если include_source_table=False.
    """

    if not isinstance(matrix, (list, tuple)) or not matrix:
        raise ValueError("Невозможно сформировать отчёт: данных нет.")

    analysis = analyze_matrix(matrix)

    if not analysis.get("headers"):
        raise ValueError("Не найдены заголовки таблицы.")

    output_directory = (
        Path(output_dir).expanduser()
        if output_dir
        else Path.home() / "Documents" / "BahonIQ PDF"
    )

    output_directory.mkdir(parents=True, exist_ok=True)

    # Имя файла строится по названию отчёта, а не по техническим
    # метаданным листа или имени исходной книги.
    filename = _filename(title or "Аналитический_отчёт") + ".pdf"
    output_path = _unique_path(output_directory / filename)

    page_size = A4 if orientation.lower() == "portrait" else landscape(A4)

    page_width, page_height = page_size

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=21 * mm,
        title=_safe_text(title, 200) or "Аналитический отчёт",
        author="",
        subject="Аналитический отчёт",
    )

    styles = _make_styles()
    story: list = []

    # Пользовательское описание служит инструкцией аналитическому движку,
    # но не печатается целиком на титульной странице.
    content_width = page_width - 36 * mm
    story.append(Spacer(1, 5 * mm))
    story.append(_cover_hero(title, styles, content_width))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Профиль: {_escape(report_profile, 80)} &nbsp;&nbsp;•&nbsp;&nbsp; "
        f"Аудитория: {_escape(audience, 80)}",
        styles["SmallCustom"],
    ))
    story.append(Spacer(1, 22 * mm))
    story.append(Paragraph(
        f"Дата формирования: {datetime.now().strftime('%d.%m.%Y')}",
        styles["SmallCustom"],
    ))
    story.append(PageBreak())

    # Основные разделы. Каждый добавляется только при наличии данных.
    _append_executive_summary(story, analysis, styles, content_width)
    _append_visual_dashboard(story, analysis, styles, content_width)
    _append_comparative_analysis(story, analysis, styles, content_width)
    _append_numeric_section(story, analysis, styles)
    _append_categorical_section(story, analysis, styles)
    _append_date_section(story, analysis, styles)
    if not (isinstance(ai_analysis, dict) and ai_analysis.get("findings")):
        _append_insights_section(story, analysis, styles)
    _append_ai_section(story, ai_analysis, styles)

    if include_source_table:
        _append_source_table(
            story,
            analysis,
            styles,
            page_width - 36 * mm,
        )

    try:
        doc.build(
            story,
            onFirstPage=_page_decor,
            onLaterPages=_page_decor,
        )
    except Exception:
        LOGGER.exception("Ошибка создания PDF.")
        raise

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF не был создан или оказался пустым.")

    LOGGER.info(
        "Создан PDF: %s; записей=%s; столбцов=%s",
        output_path,
        analysis.get("row_count", 0),
        analysis.get("column_count", 0),
    )

    return output_path


# Публичный генератор переключён на инфографическую версию 4.2.
build_analytics_pdf = build_analytics_pdf_infographic


# ---------------------------------------------------------------------------
# INFOGRAPHIC REPORT 4.2

V42_COLORS = ["#16B8B1", "#F04444", "#F5B82E", "#2A8193", "#8AA39B", "#65C6C0"]


def _v42_figure_image(figure, width: float, height: float):
    import io
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=165, bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(figure)
    buffer.seek(0)
    return Image(buffer, width=width, height=height, kind="proportional")


def _v42_dashboard(analysis: dict[str, Any], width: float, height: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 6.2))
    fig.subplots_adjust(hspace=.55, wspace=.42)
    specs = [
        ("Структура финансирования", _pro_column(analysis, "финанс"), "donut"),
        ("Крупнейшие факультеты", _pro_column(analysis, "факультет", "школа"), "bar"),
        ("Формы обучения", _pro_column(analysis, "форма обучения"), "bar"),
        ("Пол", _pro_column(analysis, "пол"), "donut"),
    ]
    for ax, (title, column, kind) in zip(axes.flat, specs):
        top = _pro_top(column, 7)
        labels = [str(x.get("value", "")) for x in top]
        values = [float(x.get("count", 0)) for x in top]
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color="#183153", pad=12)
        if not values:
            ax.text(.5, .5, "Нет данных", ha="center", va="center")
            ax.axis("off"); continue
        if kind == "donut":
            shown_labels = [label[:24] for label in labels]
            wedges, _ = ax.pie(values, startangle=90, colors=V42_COLORS[:len(values)],
                               wedgeprops={"width": .38, "edgecolor": "white"})
            ax.legend(wedges, shown_labels, loc="center left", bbox_to_anchor=(.92, .5),
                      frameon=False, fontsize=7)
            ax.text(0, 0, f"{sum(values):,.0f}".replace(",", " "), ha="center",
                    va="center", fontsize=14, fontweight="bold", color="#183153")
        else:
            pairs = list(zip(labels[:6], values[:6]))[::-1]
            ax.barh(range(len(pairs)), [x[1] for x in pairs],
                    color=V42_COLORS[:len(pairs)])
            ax.set_yticks(range(len(pairs)))
            ax.set_yticklabels([x[0][:31] for x in pairs], fontsize=7)
            ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
            for index, (_, value) in enumerate(pairs):
                ax.text(value, index, f" {value:,.0f}".replace(",", " "), va="center", fontsize=7)
            for spine in ax.spines.values(): spine.set_visible(False)
    return _v42_figure_image(fig, width, height)


def _v42_finance_dashboard(analysis: dict[str, Any], width: float, height: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collections import Counter, defaultdict
    plt.rcParams["font.family"] = "DejaVu Sans"
    faculty = _pro_column(analysis, "факультет", "школа")
    funding = _pro_column(analysis, "финанс")
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.2), gridspec_kw={"width_ratios": [1, 1.55]})
    top = _pro_top(funding, 8)
    labels = [str(x.get("value", "")) for x in top]
    values = [float(x.get("count", 0)) for x in top]
    axes[0].set_title("Общая структура", loc="left", fontsize=13, fontweight="bold", color="#183153")
    wedges, _ = axes[0].pie(values, startangle=90, colors=V42_COLORS[:len(values)],
                            wedgeprops={"width": .40, "edgecolor": "white"})
    axes[0].legend(wedges, [x[:25] for x in labels], loc="upper center",
                   bbox_to_anchor=(.5, -.02), frameon=False, fontsize=7)
    axes[0].text(0, 0, f"{sum(values):,.0f}".replace(",", " "), ha="center",
                 va="center", fontsize=16, fontweight="bold", color="#183153")
    ax = axes[1]
    ax.set_title("Финансирование внутри факультетов, %", loc="left", fontsize=13,
                 fontweight="bold", color="#183153")
    if faculty and funding:
        fi, mi = faculty.get("index"), funding.get("index")
        totals, cross = Counter(), defaultdict(Counter)
        for row in analysis.get("rows", []):
            if fi >= len(row) or mi >= len(row): continue
            f, m = str(row[fi]).strip(), str(row[mi]).strip()
            if not f or not m or f == "None" or m == "None": continue
            totals[f] += 1; cross[f][m] += 1
        groups = [name for name, _ in totals.most_common(7)]
        categories = Counter()
        for group in groups: categories.update(cross[group])
        series = [name for name, _ in categories.most_common(5)]
        left = [0.0] * len(groups)
        for color, name in zip(V42_COLORS, series):
            shares = [cross[g][name] * 100 / totals[g] for g in groups]
            ax.barh(range(len(groups)), shares, left=left, color=color, label=name[:26])
            left = [a + b for a, b in zip(left, shares)]
        ax.set_yticks(range(len(groups))); ax.set_yticklabels([g[:34] for g in groups], fontsize=7)
        ax.invert_yaxis(); ax.set_xlim(0, 100); ax.grid(axis="x", alpha=.15)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=2, frameon=False, fontsize=6.5)
        for spine in ax.spines.values(): spine.set_visible(False)
    return _v42_figure_image(fig, width, height)


def _v42_profile_dashboard(analysis: dict[str, Any], width: float, height: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(2, 1, figsize=(6.2, 6.2))
    for ax, (title, column, kind) in zip(axes, [
        ("Пол", _pro_column(analysis, "пол"), "donut"),
        ("Гражданство", _pro_column(analysis, "граждан"), "bar"),
    ]):
        top = _pro_top(column, 6); labels = [str(x.get("value", "")) for x in top]
        values = [float(x.get("count", 0)) for x in top]
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color="#183153")
        if kind == "donut" and values:
            wedges, _ = ax.pie(values, startangle=90, colors=V42_COLORS[:len(values)],
                               wedgeprops={"width": .38, "edgecolor": "white"})
            ax.legend(wedges, [x[:22] for x in labels], loc="center left",
                      bbox_to_anchor=(.86, .5), frameon=False, fontsize=7)
        elif values:
            pairs = list(zip(labels, values))[::-1]
            ax.barh(range(len(pairs)), [x[1] for x in pairs], color=V42_COLORS[:len(pairs)])
            ax.set_yticks(range(len(pairs))); ax.set_yticklabels([x[0][:20] for x in pairs], fontsize=7)
            ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
            for spine in ax.spines.values(): spine.set_visible(False)
    fig.tight_layout(h_pad=1.2)
    return _v42_figure_image(fig, width, height)


def _v42_kpi_row(analysis: dict[str, Any], styles, width: float) -> Table:
    age = next((c.get("statistics", {}).get("age_statistics") for c in analysis.get("date_columns", [])
                if c.get("statistics", {}).get("age_statistics")), {})
    funding = _pro_column(analysis, "финанс")
    own = sum(float(x.get("count", 0)) for x in _pro_top(funding, 20)
              if "собствен" in str(x.get("value", "")).casefold())
    total = float(analysis.get("row_count", 0) or 1)
    values = [
        (_format_number(analysis.get("row_count")), "ОБУЧАЮЩИХСЯ", colors.HexColor("#16B8B1")),
        (f"{own * 100 / total:.1f}%", "СОБСТВЕННЫЕ СРЕДСТВА", colors.HexColor("#F04444")),
        (str(age.get("mean", "—")), "СРЕДНИЙ ВОЗРАСТ", colors.HexColor("#F5B82E")),
        (str(len([c for c in analysis.get("categorical_columns", []) if c.get("reportable")])), "РАЗРЕЗОВ", colors.HexColor("#2A8193")),
    ]
    cards = []
    for value, label, color in values:
        cards.append(Table([[Paragraph(str(value), styles["CoverKpiCustom"])],
                            [Paragraph(label, styles["CoverLabelCustom"])]],
                           colWidths=[width / 4 - 3 * mm], rowHeights=[13 * mm, 8 * mm],
                           style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white),
                                             ("LINEABOVE", (0, 0), (-1, 0), 5, color),
                                             ("BOX", (0, 0), (-1, -1), .5, BORDER),
                                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])) )
    table = Table([cards], colWidths=[width / 4] * 4)
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 2),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return table


def build_analytics_pdf_v42(
    matrix: list[list], title: str, source_name: str = "", sheet_name: str = "",
    output_dir: str | Path | None = None, description: str = "",
    include_source_table: bool = False, orientation: str = "auto",
    ai_analysis: dict | None = None, report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> Path:
    """Версия 4.2: инфографический управленческий PDF."""
    if not matrix: raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis = analyze_matrix(matrix)
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pdf"))
    page_size = landscape(A4); page_width, _ = page_size; width = page_width - 30 * mm
    doc = SimpleDocTemplate(str(output_path), pagesize=page_size, leftMargin=15 * mm,
                            rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=15 * mm,
                            title=_safe_text(title, 200), subject="Инфографический аналитический отчёт")
    styles = _make_styles(); story = []
    story.append(_pro_cover(title, description, report_profile, audience, source_name, styles, width))
    story.append(PageBreak())
    story.extend(_section("Ключевые показатели", styles)); story.append(_v42_kpi_row(analysis, styles, width))
    story.append(Spacer(1, 5 * mm)); story.append(_v42_dashboard(analysis, width, 118 * mm))
    story.append(PageBreak())
    story.extend(_section("Финансирование обучающихся", styles))
    findings = _pro_valid_findings(analysis, ai_analysis)
    finance_fact = next((x for x in findings if "Собственные средства" in x), "")
    if finance_fact: story.append(_paragraph(finance_fact, styles["BodyCustom"], 700))
    story.append(_v42_finance_dashboard(analysis, width, 112 * mm))
    story.append(PageBreak())
    story.extend(_section("Факультеты и формы обучения", styles))
    faculty = _pro_column(analysis, "факультет", "школа"); study = _pro_column(analysis, "форма обучения")
    charts = []
    for column in (faculty, study):
        top = _pro_top(column, 9)
        charts.append(_horizontal_chart([x.get("value") for x in top], [x.get("count", 0) for x in top],
                                        width=(width - 8 * mm) / 2, height=105 * mm))
    story.append(Table([[Paragraph("ФАКУЛЬТЕТЫ", styles["SubsectionCustom"]), Paragraph("ФОРМЫ ОБУЧЕНИЯ", styles["SubsectionCustom"])],
                        [charts[0], charts[1]]], colWidths=[width / 2, width / 2],
                       style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                         ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#EAF8F7")),
                                         ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFF1F1")),
                                         ("BOX", (0, 0), (-1, -1), .5, BORDER)])))
    story.append(PageBreak())
    story.extend(_section("Возраст и профиль контингента", styles))
    age = next((c.get("statistics", {}).get("age_statistics") for c in analysis.get("date_columns", [])
                if c.get("statistics", {}).get("age_statistics")), {})
    gender = _pro_column(analysis, "пол"); citizen = _pro_column(analysis, "граждан")
    age_chart = _horizontal_chart([x.get("value") for x in age.get("groups", [])],
                                  [x.get("count", 0) for x in age.get("groups", [])],
                                  width=width * .48, height=100 * mm)
    profile_chart = _v42_profile_dashboard(analysis, width * .48, 100 * mm)
    story.append(Table([[age_chart, profile_chart]], colWidths=[width / 2, width / 2],
                       style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])) )
    story.append(PageBreak())
    story.extend(_section("Выводы и решения", styles))
    recommendations = _pro_recommendations(analysis, ai_analysis)
    left = [Paragraph("ДОКАЗАТЕЛЬНЫЕ ВЫВОДЫ", styles["SubsectionCustom"])] + [_bullet(x, styles) for x in findings[:6]]
    right = [Paragraph("ПЛАН ДЕЙСТВИЙ", styles["SubsectionCustom"])] + [_bullet(f"{i}. {x}", styles) for i, x in enumerate(recommendations, 1)]
    story.append(Table([[left, right]], colWidths=[width * .56, width * .44],
                       style=TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#EAF8F7")),
                                         ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFF6E2")),
                                         ("BOX", (0, 0), (-1, -1), .6, BORDER),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                         ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                         ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                         ("TOPPADDING", (0, 0), (-1, -1), 10),
                                         ("BOTTOMPADDING", (0, 0), (-1, -1), 10)])))
    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


# Итоговая публичная версия генератора.
build_analytics_pdf = build_analytics_pdf_v42


# ---------------------------------------------------------------------------
# PROFESSIONAL REPORT 4.1
# The definition below intentionally replaces the legacy builder above while
# preserving its public signature for launcher.py and the web interface.

def _pro_column(analysis: dict[str, Any], *markers: str) -> dict[str, Any] | None:
    for column in analysis.get("categorical_columns", []) + analysis.get("date_columns", []):
        name = str(column.get("name", "")).casefold()
        if any(marker.casefold() in name for marker in markers):
            return column
    return None


def _pro_top(column: dict[str, Any] | None, limit: int = 8) -> list[dict[str, Any]]:
    if not column:
        return []
    return list(column.get("statistics", {}).get("top_values", []) or [])[:limit]


def _pro_valid_findings(analysis: dict[str, Any], ai_analysis: dict | None) -> list[str]:
    result = []
    if isinstance(ai_analysis, dict):
        for item in ai_analysis.get("findings", []) or []:
            text = _safe_text(item, 550)
            if len(text) >= 28 and any(char.isdigit() for char in text):
                result.append(text)
    funding = _pro_column(analysis, "финанс")
    funding_top = _pro_top(funding, 20)
    if funding_top:
        own = sum(float(x.get("count", 0)) for x in funding_top
                  if "собствен" in str(x.get("value", "")).casefold())
        grants = sum(float(x.get("count", 0)) for x in funding_top
                     if "грант" in str(x.get("value", "")).casefold())
        total = float(analysis.get("row_count", 0) or 0)
        if total and (own or grants):
            result.append(
                f"Собственные средства обеспечивают {_format_number(own)} обучающихся "
                f"({own * 100 / total:.1f}%), грантовые источники — "
                f"{_format_number(grants)} ({grants * 100 / total:.1f}%)."
            )
    for column in analysis.get("categorical_columns", []):
        if not column.get("reportable"):
            continue
        top = _pro_top(column, 1)
        if not top:
            continue
        item = top[0]
        share = column.get("statistics", {}).get("top_value_percent", 0)
        candidate = (
            f"По показателю «{column.get('name')}» лидирует «{item.get('value')}»: "
            f"{_format_number(item.get('count'))} записей, или {share:.1f}%."
        )
        if candidate not in result:
            result.append(candidate)
        if len(result) >= 5:
            break
    priority = ("финанс", "факульт", "возраст", "форма обучения", "пол", "граждан")
    result.sort(key=lambda text: next(
        (index for index, marker in enumerate(priority) if marker in text.casefold()),
        len(priority),
    ))
    return result[:6]


def _pro_recommendations(analysis: dict[str, Any], ai_analysis: dict | None) -> list[str]:
    items = []
    if isinstance(ai_analysis, dict):
        items = [
            _safe_text(item, 550) for item in ai_analysis.get("recommendations", []) or []
            if len(_safe_text(item, 550)) >= 25
        ]
    if items:
        return items[:4]
    return [
        "Деканату вести ежемесячный срез финансирования по факультетам и отслеживать изменение долей в процентных пунктах.",
        "Учебным подразделениям учитывать крупнейшие формы обучения и возрастные группы при планировании нагрузки и сервисов.",
        "Повторять отчёт после каждого обновления контингента и фиксировать изменения относительно предыдущего периода.",
    ]


def _pro_cover(title: str, description: str, report_profile: str, audience: str,
               source_name: str, styles, width: float) -> Table:
    subtitle = _safe_text(description, 320) or (
        "Структура контингента, финансирование, возрастные группы и выводы для принятия решений"
    )
    content = [
        Paragraph("ANALYTICS AI", styles["CoverEyebrowCustom"]),
        Paragraph(_escape(title, 180), styles["CoverTitleLightCustom"]),
        Paragraph(_escape(subtitle, 360), styles["CoverSubtitleLightCustom"]),
        Spacer(1, 14 * mm),
        Paragraph(
            _escape(f"Профиль: {report_profile}    Аудитория: {audience}", 180),
            styles["CoverSubtitleLightCustom"],
        ),
        Paragraph(
            _escape(f"Источник: {source_name or 'Excel'}    Дата: {datetime.now():%d.%m.%Y}", 180),
            styles["CoverSubtitleLightCustom"],
        ),
    ]
    table = Table([[content]], colWidths=[width], rowHeights=[150 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 18 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 22 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 16 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16 * mm),
    ]))
    return table


def _pro_funding_table(analysis: dict[str, Any], faculty: dict | None,
                       funding: dict | None, styles, width: float):
    if not faculty or not funding:
        return None
    rows = analysis.get("rows", [])
    fi, mi = faculty.get("index"), funding.get("index")
    if fi is None or mi is None:
        return None
    from collections import Counter, defaultdict
    totals, groups = Counter(), defaultdict(Counter)
    for row in rows:
        if fi >= len(row) or mi >= len(row):
            continue
        f, m = str(row[fi]).strip(), str(row[mi]).strip()
        if not f or not m or f == "None" or m == "None":
            continue
        totals[f] += 1
        groups[f][m] += 1
    data = [[
        Paragraph("Факультет", styles["SmallCustom"]),
        Paragraph("Обучающихся", styles["SmallCustom"]),
        Paragraph("Основной источник финансирования", styles["SmallCustom"]),
        Paragraph("Доля", styles["SmallCustom"]),
    ]]
    for name, total in totals.most_common(8):
        lead, count = groups[name].most_common(1)[0]
        data.append([
            Paragraph(_escape(name, 80), styles["SmallCustom"]),
            _format_number(total),
            Paragraph(_escape(lead, 80), styles["SmallCustom"]),
            f"{count * 100 / total:.1f}%",
        ])
    table = Table(data, colWidths=[width * .30, width * .13, width * .42, width * .15], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), .35, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _build_analytics_pdf_v41(
    matrix: list[list], title: str, source_name: str = "", sheet_name: str = "",
    output_dir: str | Path | None = None, description: str = "",
    include_source_table: bool = False, orientation: str = "auto",
    ai_analysis: dict | None = None, report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> Path:
    """Создаёт профессиональный управленческий PDF без пустых страниц."""
    if not matrix:
        raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis = analyze_matrix(matrix)
    if not analysis.get("headers"):
        raise ValueError("Не найдены заголовки таблицы.")
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pdf"))
    page_size = landscape(A4)
    page_width, _ = page_size
    doc = SimpleDocTemplate(
        str(output_path), pagesize=page_size, rightMargin=18 * mm,
        leftMargin=18 * mm, topMargin=14 * mm, bottomMargin=17 * mm,
        title=_safe_text(title, 200), subject="Управленческий аналитический отчёт",
    )
    styles = _make_styles()
    width = page_width - 36 * mm
    story: list = [_pro_cover(
        title, description, report_profile, audience, source_name, styles, width
    ), PageBreak()]

    findings = _pro_valid_findings(analysis, ai_analysis)
    recommendations = _pro_recommendations(analysis, ai_analysis)
    summary = _safe_text((ai_analysis or {}).get("summary"), 1500)
    story.extend(_section("Управленческое резюме", styles))
    story.append(_paragraph(
        summary or f"Отчёт охватывает {_format_number(analysis.get('row_count'))} записей. "
        "Основные различия представлены по факультетам, форме обучения, финансированию и возрасту.",
        styles["BodyCustom"], 1600,
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(_kpi_cards(analysis, styles, width))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Ключевые факты", styles["SubsectionCustom"]))
    for item in findings[:4]:
        story.append(_bullet(item, styles))

    faculty = _pro_column(analysis, "факультет", "школа")
    funding = _pro_column(analysis, "финанс")
    study_form = _pro_column(analysis, "форма обучения")
    gender = _pro_column(analysis, "пол")
    citizenship = _pro_column(analysis, "граждан")

    if funding:
        story.append(PageBreak())
        story.extend(_section("Финансирование обучающихся", styles))
        top = _pro_top(funding, 8)
        funding_fact = next((item for item in findings if "собственные средства" in item), "")
        if funding_fact:
            story.append(_paragraph(funding_fact, styles["BodyCustom"], 700))
        chart = _horizontal_chart(
            [x.get("value") for x in top], [x.get("count", 0) for x in top],
            width=width, height=72 * mm,
        )
        if chart:
            story.append(chart)
        table = _pro_funding_table(analysis, faculty, funding, styles, width)
        if table:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Основной источник финансирования по факультетам", styles["SubsectionCustom"]))
            story.append(table)

    if faculty:
        story.append(PageBreak())
        story.extend(_section("Структура по факультетам", styles))
        top = _pro_top(faculty, 10)
        chart = _horizontal_chart(
            [x.get("value") for x in top], [x.get("count", 0) for x in top],
            width=width, height=105 * mm,
        )
        if chart:
            story.append(chart)

    profile_columns = [column for column in (study_form, gender, citizenship) if column]
    if profile_columns:
        story.append(PageBreak())
        story.extend(_section("Профиль контингента", styles))
        cells = []
        for column in profile_columns[:2]:
            top = _pro_top(column, 8)
            cells.append([
                Paragraph(_escape(column.get("name"), 100), styles["SubsectionCustom"]),
                _horizontal_chart(
                    [x.get("value") for x in top], [x.get("count", 0) for x in top],
                    width=(width - 8 * mm) / 2, height=92 * mm,
                ),
            ])
        if len(cells) == 1:
            story.extend(cells[0])
        else:
            story.append(Table(
                [[cells[0][0], cells[1][0]], [cells[0][1], cells[1][1]]],
                colWidths=[width / 2, width / 2],
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
            ))

    date_columns = analysis.get("date_columns", [])
    age = next((c.get("statistics", {}).get("age_statistics") for c in date_columns
                if c.get("statistics", {}).get("age_statistics")), None)
    if age:
        story.append(PageBreak())
        story.extend(_section("Возрастная структура", styles))
        groups = age.get("groups", [])
        chart = _horizontal_chart(
            [x.get("value") for x in groups], [x.get("count", 0) for x in groups],
            width=width, height=92 * mm,
        )
        story.append(_paragraph(
            f"Средний возраст составляет {age.get('mean')} года. "
            f"Диапазон — от {age.get('min')} до {age.get('max')} лет.",
            styles["BodyCustom"],
        ))
        if chart:
            story.append(chart)

    story.append(PageBreak())
    story.extend(_section("Выводы и план действий", styles))
    story.append(Paragraph("Доказательные выводы", styles["SubsectionCustom"]))
    for item in findings:
        story.append(_bullet(item, styles))
    risks = list((ai_analysis or {}).get("risks", []) or [])
    if risks:
        story.append(Paragraph("Зоны внимания", styles["SubsectionCustom"]))
        for item in risks[:3]:
            story.append(_bullet(item, styles))
    story.append(Paragraph("Рекомендуемые действия", styles["SubsectionCustom"]))
    for number, item in enumerate(recommendations, 1):
        story.append(_bullet(f"{number}. {item}", styles))

    if include_source_table:
        story.append(PageBreak())
        _append_source_table(story, analysis, styles, width)

    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


# ---------------------------------------------------------------------------
# PROFESSIONAL EVIDENCE REPORT 5.0

def _evidence_dimensions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns decision-useful dimensions, excluding IDs and free text."""
    priority = ("факульт", "финанс", "форма обуч", "пол", "граждан", "национ", "язык")
    columns = [
        c for c in analysis.get("categorical_columns", [])
        if c.get("reportable") and 2 <= c.get("statistics", {}).get("unique_count", 0) <= 100
    ]
    columns.sort(key=lambda c: next(
        (i for i, marker in enumerate(priority) if marker in str(c.get("name", "")).casefold()),
        len(priority),
    ))
    return columns


def _evidence_table(column: dict[str, Any], total: int, styles, width: float,
                    limit: int = 12) -> Table:
    rows = [[
        Paragraph("Категория", styles["SmallCustom"]),
        Paragraph("Количество", styles["SmallCustom"]),
        Paragraph("Доля", styles["SmallCustom"]),
    ]]
    shown = 0
    for item in _pro_top(column, limit):
        count = int(item.get("count", 0) or 0)
        rows.append([
            Paragraph(_escape(item.get("value"), 240), styles["BodyCustom"]),
            _format_number(count),
            f"{count * 100 / total:.1f}%" if total else "—",
        ])
        shown += count
    other = max(0, total - shown)
    if other and column.get("statistics", {}).get("unique_count", 0) > limit:
        rows.append([
            Paragraph("Прочие категории", styles["BodyCustom"]),
            _format_number(other),
            f"{other * 100 / total:.1f}%" if total else "—",
        ])
    table = Table(rows, colWidths=[width * .68, width * .17, width * .15], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
        ("GRID", (0, 0), (-1, -1), .35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _fact_for(column: dict[str, Any], total: int) -> str:
    top = _pro_top(column, 2)
    if not top or not total:
        return "Недостаточно данных для интерпретации."
    first = top[0]
    count = int(first.get("count", 0) or 0)
    share = count * 100 / total
    if len(top) > 1:
        second = top[1]
        gap = count - int(second.get("count", 0) or 0)
        return (
            f"Крупнейшая категория — «{_safe_text(first.get('value'), 180)}»: "
            f"{_format_number(count)} ({share:.1f}%). Она превышает вторую категорию "
            f"на {_format_number(gap)} записей."
        )
    return f"Категория «{_safe_text(first.get('value'), 180)}» охватывает {_format_number(count)} записей ({share:.1f}%)."


def _verified_findings(analysis: dict[str, Any]) -> list[tuple[str, str]]:
    total = int(analysis.get("row_count", 0) or 0)
    result = []
    for column in _evidence_dimensions(analysis)[:6]:
        result.append((str(column.get("name", "Показатель")), _fact_for(column, total)))
    quality = analysis.get("quality", {}) or {}
    empty = float(quality.get("empty_percent", 0) or 0)
    duplicates = float(quality.get("duplicate_row_percent", 0) or 0)
    result.append(("Качество данных", f"Пустые ячейки: {empty:.1f}%. Дубли строк: {duplicates:.1f}%."))
    return result


def _recommendation_rows(analysis: dict[str, Any]) -> list[list[str]]:
    dims = _evidence_dimensions(analysis)
    rows = []
    for column in dims[:4]:
        fact = _fact_for(column, int(analysis.get("row_count", 0) or 0))
        name = str(column.get("name", "показатель"))
        rows.append([
            fact,
            f"Проверить причины концентрации по показателю «{name}» и сопоставить её с доступной нагрузкой и ресурсами.",
            "Деканат / владелец данных",
            "До следующего обновления данных",
            f"Изменение доли крупнейшей категории по «{name}», п.п.",
        ])
    return rows


def build_analytics_pdf_v50(
    matrix: list[list], title: str, source_name: str = "", sheet_name: str = "",
    output_dir: str | Path | None = None, description: str = "",
    include_source_table: bool = False, orientation: str = "auto",
    ai_analysis: dict | None = None, report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> Path:
    """Evidence-first report: every conclusion is tied to a computed fact."""
    if not matrix:
        raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis = analyze_matrix(matrix)
    total = int(analysis.get("row_count", 0) or 0)
    dimensions = _evidence_dimensions(analysis)
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pdf"))
    page_size = landscape(A4); page_width, _ = page_size; width = page_width - 36 * mm
    doc = SimpleDocTemplate(str(output_path), pagesize=page_size, leftMargin=18 * mm,
                            rightMargin=18 * mm, topMargin=14 * mm, bottomMargin=17 * mm,
                            title=_safe_text(title, 200), subject="Доказательный аналитический отчёт")
    styles = _make_styles(); story: list = []

    # Minimal cover. Never print the prompt or a technical file path here.
    cover = [
        Paragraph("ANALYTICS AI", styles["CoverEyebrowCustom"]),
        Paragraph(_escape(title, 180), styles["CoverTitleLightCustom"]),
        Paragraph("Анализ контингента для принятия управленческих решений", styles["CoverSubtitleLightCustom"]),
        Spacer(1, 18 * mm),
        Paragraph(_escape(f"Профиль: {report_profile}    Аудитория: {audience}", 200), styles["CoverSubtitleLightCustom"]),
        Paragraph(datetime.now().strftime("Дата подготовки: %d.%m.%Y"), styles["CoverSubtitleLightCustom"]),
    ]
    story.append(Table([[cover]], colWidths=[width], rowHeights=[150 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 18 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 18 * mm),
    ])))

    story.append(PageBreak()); story.extend(_section("1. Цель и методология", styles))
    story.append(_paragraph(
        "Цель отчёта — описать структуру контингента, выявить концентрации и сформировать проверяемые управленческие вопросы. "
        "Отчёт не устанавливает причины без временного ряда или дополнительных данных.", styles["BodyCustom"], 900))
    methods = [
        f"Объём анализа: {_format_number(total)} строк и {len(analysis.get('headers', []))} полей.",
        "Метод: частотный и долевой анализ категорий; сравнение крупнейших групп; проверка пропусков и дублей.",
        "Ограничение: один срез данных позволяет описывать структуру, но не доказывает динамику и причинно-следственные связи.",
        "Правило доказательности: каждый вывод ниже содержит показатель, значение и базу сравнения.",
    ]
    for item in methods: story.append(_bullet(item, styles))
    story.append(Spacer(1, 4 * mm)); story.append(_kpi_cards(analysis, styles, width))

    story.append(PageBreak()); story.extend(_section("2. Управленческое резюме", styles))
    for heading, fact in _verified_findings(analysis)[:5]:
        story.append(KeepTogether([
            Paragraph(_escape(heading, 120), styles["SubsectionCustom"]),
            _paragraph(fact, styles["BodyCustom"], 700), Spacer(1, 2 * mm),
        ]))
    story.append(_paragraph(
        "Эти результаты описывают распределение записей. Для объяснения причин нужны данные минимум за два сопоставимых периода, "
        "плановые значения и сведения о ресурсах подразделений.", styles["BodyCustom"], 700))

    section = 3
    for column in dimensions:
        story.append(PageBreak()); story.extend(_section(f"{section}. {column.get('name')}", styles))
        story.append(Paragraph("Результат", styles["SubsectionCustom"]))
        story.append(_paragraph(_fact_for(column, total), styles["BodyCustom"], 900))
        story.append(Spacer(1, 3 * mm)); story.append(_evidence_table(column, total, styles, width))
        story.append(Spacer(1, 4 * mm)); story.append(Paragraph("Интерпретация", styles["SubsectionCustom"]))
        story.append(_paragraph(
            "Концентрация показывает масштаб группы и помогает планировать нагрузку. Сама по себе она не означает проблему. "
            "Управленческая оценка требует сравнения с планом, предыдущим периодом и доступной мощностью.",
            styles["BodyCustom"], 700))
        section += 1

    story.append(PageBreak()); story.extend(_section(f"{section}. Доказательные выводы", styles))
    findings = _verified_findings(analysis)
    data = [[Paragraph("Показатель", styles["SmallCustom"]), Paragraph("Факт и сравнение", styles["SmallCustom"])]]
    for heading, fact in findings:
        data.append([Paragraph(_escape(heading, 120), styles["BodyCustom"]), Paragraph(_escape(fact, 700), styles["BodyCustom"])])
    table = Table(data, colWidths=[width * .24, width * .76], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), .35, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(table)

    story.append(PageBreak()); story.extend(_section(f"{section + 1}. План действий", styles))
    action_data = [[Paragraph(x, styles["SmallCustom"]) for x in
                    ("Основание", "Действие", "Ответственный", "Срок", "Контрольный показатель")]]
    for row in _recommendation_rows(analysis):
        action_data.append([Paragraph(_escape(value, 500), styles["SmallCustom"]) for value in row])
    action = Table(action_data, colWidths=[width*.23, width*.27, width*.14, width*.14, width*.22], repeatRows=1)
    action.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("GRID", (0, 0), (-1, -1), .35, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
                                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(action)
    story.append(Spacer(1, 4 * mm)); story.append(_paragraph(
        "При следующем обновлении отчёт должен сравнивать доли в процентных пунктах и абсолютные изменения с текущим срезом. "
        "Без предыдущего периода формулировки «рост», «снижение» и «тренд» запрещены.", styles["BodyCustom"], 800))

    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


build_analytics_pdf = build_analytics_pdf_v50


# ---------------------------------------------------------------------------
# INFOGRAPHIC ANALYTICS 5.1

V51_PALETTE = ["#11B5AE", "#183153", "#E84C4C", "#F2C230", "#5B8FF9", "#8A70C9"]


def _v51_chart(kind: str, labels: list[str], values: list[float], width: float,
               height: float, title: str = ""):
    """Vector infographic chart with stable BahonIQ styling.

    ReportLab drawings stay sharp at any PDF zoom level.  Do not replace this
    with raster PNG export: large landscape pages make even high-DPI labels
    visibly softer than surrounding text.
    """
    if not labels or not values:
        return Spacer(1, height)
    try:
        import textwrap
        labels = [str(x) for x in labels]
        values = [float(x or 0) for x in values]
        drawing = Drawing(width, height)
        palette = [colors.HexColor(value) for value in V51_PALETTE]
        navy = colors.HexColor("#183153")
        muted = colors.HexColor("#667085")
        grid = colors.HexColor("#E7EBF0")

        if title:
            drawing.add(String(
                2, height - 12, title, fontName=FONT_BOLD,
                fontSize=10, fillColor=navy,
            ))

        if kind == "donut":
            count = min(6, len(values))
            labels, values = labels[:count], values[:count]
            total = sum(values) or 1
            size = min(height - 34, width * .47)
            pie = Doughnut()
            pie.x = 8
            pie.y = max(8, (height - size) / 2 - 4)
            pie.width = size
            pie.height = size
            pie.data = values
            pie.labels = [""] * count
            pie.startAngle = 90
            pie.direction = "clockwise"
            for index in range(count):
                pie.slices[index].fillColor = palette[index % len(palette)]
                pie.slices[index].strokeColor = colors.white
                pie.slices[index].strokeWidth = .8
            drawing.add(pie)
            center_x = pie.x + size / 2
            center_y = pie.y + size / 2
            drawing.add(String(
                center_x, center_y + 4,
                _format_number(sum(values)), fontName=FONT_BOLD,
                fontSize=14, textAnchor="middle", fillColor=navy,
            ))
            drawing.add(String(
                center_x, center_y - 10, "записей", fontName=FONT_REGULAR,
                fontSize=7.5, textAnchor="middle", fillColor=muted,
            ))
            legend_x = size + 30
            legend_y = height - 34
            for index, (label, value) in enumerate(zip(labels, values)):
                y = legend_y - index * 22
                drawing.add(Rect(legend_x, y - 7, 9, 9, fillColor=palette[index % len(palette)], strokeColor=None))
                shown = label if len(label) <= 34 else label[:31] + "…"
                drawing.add(String(
                    legend_x + 14, y, f"{shown} — {value * 100 / total:.1f}%",
                    fontName=FONT_REGULAR, fontSize=7.5,
                    fillColor=navy,
                ))
        elif kind == "gauge":
            total = sum(values) or 1
            left = 8.0
            bar_y = height * .48
            bar_width = width - 16
            for i, (label, value) in enumerate(zip(labels, values)):
                share = value * 100 / total
                segment = bar_width * share / 100
                drawing.add(Rect(left, bar_y, segment, 24, fillColor=palette[i % len(palette)], strokeColor=None))
                if share >= 8:
                    drawing.add(String(
                        left + segment / 2, bar_y + 8, f"{share:.1f}%",
                        fontName=FONT_BOLD, fontSize=8, textAnchor="middle",
                        fillColor=colors.white,
                    ))
                left += segment
        else:
            # Date pages may contain up to twelve annual cohorts.  Keeping the
            # old nine-item cap made the explanatory sentence mention recent
            # years that were silently absent from the chart.
            count = min(12, len(values))
            labels, values = labels[:count], values[:count]
            max_value = max(values) or 1
            top_pad = 24 if title else 8
            bottom_pad = 12
            label_width = width * .37
            plot_x = label_width + 8
            plot_width = width - plot_x - 44
            plot_height = height - top_pad - bottom_pad
            row_height = plot_height / max(count, 1)
            bar_height = min(20, row_height * .58)
            for tick in range(5):
                x = plot_x + plot_width * tick / 4
                drawing.add(Line(x, bottom_pad, x, height - top_pad, strokeColor=grid, strokeWidth=.6))
            for index, (label, value) in enumerate(zip(labels, values)):
                center_y = height - top_pad - row_height * (index + .5)
                bar_y = center_y - bar_height / 2
                bar_width = max(1, plot_width * value / max_value)
                drawing.add(Rect(
                    plot_x, bar_y, bar_width, bar_height,
                    fillColor=palette[index % 4], strokeColor=None,
                ))
                wrapped = textwrap.wrap(label, 34)[:2] or [label]
                if len(wrapped) == 1:
                    drawing.add(String(
                        plot_x - 7, center_y - 3, wrapped[0],
                        fontName=FONT_REGULAR, fontSize=7.6,
                        textAnchor="end", fillColor=navy,
                    ))
                else:
                    drawing.add(String(
                        plot_x - 7, center_y + 2, wrapped[0],
                        fontName=FONT_REGULAR, fontSize=7.1,
                        textAnchor="end", fillColor=navy,
                    ))
                    drawing.add(String(
                        plot_x - 7, center_y - 8, wrapped[1],
                        fontName=FONT_REGULAR, fontSize=7.1,
                        textAnchor="end", fillColor=navy,
                    ))
                drawing.add(String(
                    min(plot_x + bar_width + 5, width - 40), center_y - 3,
                    _compact_number(value), fontName=FONT_REGULAR,
                    fontSize=7.8, fillColor=navy,
                ))
        return drawing
    except Exception:
        LOGGER.exception("V5.1 vector chart failed")
        return Spacer(1, height)


def _v51_top(column, limit=9):
    return list((column or {}).get("statistics", {}).get("top_values", []) or [])[:limit]


def _v51_share(top: list[dict], total: int, count: int = 1) -> float:
    return sum(float(x.get("count", 0) or 0) for x in top[:count]) * 100 / total if total else 0


def _v51_callout(title: str, value: str, note: str, styles, color=PALE_BLUE):
    content = [Paragraph(_escape(title, 80), styles["SmallCustom"]),
               Paragraph(_escape(value, 160), styles["SectionCustom"]),
               Paragraph(_escape(note, 500), styles["BodyCustom"])]
    return Table([[content]], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color), ("BOX", (0, 0), (-1, -1), .6, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))


def _v51_page_title(story: list, number: int, title: str, takeaway: str, styles) -> None:
    story.extend(_section(f"{number}. {title}", styles))
    story.append(_paragraph(takeaway, styles["ReportSubtitleCustom"], 700))


def build_analytics_pdf_v51(
    matrix: list[list], title: str, source_name: str = "", sheet_name: str = "",
    output_dir: str | Path | None = None, description: str = "",
    include_source_table: bool = False, orientation: str = "auto",
    ai_analysis: dict | None = None, report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> Path:
    """BahonIQ infographic report: one page, one analytical story."""
    if not matrix:
        raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis = analyze_matrix(matrix); total = int(analysis.get("row_count", 0) or 0)
    faculty = _pro_column(analysis, "факультет", "школа")
    funding = _pro_column(analysis, "финанс")
    study = _pro_column(analysis, "форма обучения")
    gender = _pro_column(analysis, "пол")
    citizenship = _pro_column(analysis, "граждан")
    language = _pro_column(analysis, "язык")
    age = next((c.get("statistics", {}).get("age_statistics") for c in analysis.get("date_columns", [])
                if c.get("statistics", {}).get("age_statistics")), {})
    out_dir = Path(output_dir).expanduser() if output_dir else Path.home()/"Documents"/"BahonIQ Reports"
    out_dir.mkdir(parents=True, exist_ok=True); output_path = _unique_path(out_dir/(_filename(title)+".pdf"))
    page_size = landscape(A4); page_width, _ = page_size; width = page_width - 30*mm
    doc = SimpleDocTemplate(str(output_path), pagesize=page_size, leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=11*mm, bottomMargin=15*mm, title=_safe_text(title, 200),
                            subject="Инфографический аналитический отчёт")
    styles = _make_styles(); story=[]

    # Cover
    cover = [Paragraph(_escape(title, 180), styles["CoverTitleLightCustom"]),
             Paragraph("Контингент, финансирование, образовательный профиль и управленческие решения",
                       styles["CoverSubtitleLightCustom"]), Spacer(1, 22*mm),
             Paragraph(_escape(f"{report_profile} • {audience}", 180), styles["CoverSubtitleLightCustom"]),
             Paragraph(datetime.now().strftime("%d.%m.%Y"), styles["CoverSubtitleLightCustom"])]
    story.append(Table([[cover]], colWidths=[width], rowHeights=[150*mm], style=TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),NAVY),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),18*mm),("RIGHTPADDING",(0,0),(-1,-1),18*mm)])))

    # Executive dashboard
    story.append(PageBreak()); _v51_page_title(story,1,"Управленческая панель",
        "14 201 обучающийся: основной масштаб формируют Школа Медицины, собственное финансирование и шестилетний бакалавриат.",styles)
    story.append(_v42_kpi_row(analysis, styles, width)); story.append(Spacer(1,3*mm))
    ft, fn, lg = _v51_top(faculty,5), _v51_top(funding,7), _v51_top(language,4)
    left = _v51_chart("bar",[x.get("value") for x in ft],[x.get("count") for x in ft],width*.54,76*mm,"Крупнейшие факультеты")
    right = [_v51_chart("gauge",["Собственные средства","Грантовые источники"],
              [sum(x.get("count",0) for x in fn if "собствен" in str(x.get("value","")).casefold()),
               sum(x.get("count",0) for x in fn if "грант" in str(x.get("value","")).casefold())],width*.42,34*mm,"Баланс финансирования"),
             _v51_chart("donut",[x.get("value") for x in lg],[x.get("count") for x in lg],width*.42,53*mm,"Языки обучения")]
    story.append(Table([[left,right]],colWidths=[width*.56,width*.44],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))

    # Faculty story
    story.append(PageBreak()); ftop=_v51_top(faculty,9); top3=_v51_share(ftop,total,3)
    _v51_page_title(story,2,"Факультеты и масштаб нагрузки",
        f"Школа Медицины объединяет {_format_number(ftop[0].get('count') if ftop else 0)} обучающихся; три крупнейших подразделения формируют {top3:.1f}% контингента.",styles)
    chart=_v51_chart("bar",[x.get("value") for x in ftop],[x.get("count") for x in ftop],width*.66,105*mm)
    side=[_v51_callout("КОНЦЕНТРАЦИЯ",f"{top3:.1f}%","Доля трёх крупнейших подразделений",styles),Spacer(1,3*mm),
          _v51_callout("ИНТЕРПРЕТАЦИЯ","Нагрузка сосредоточена","Планирование аудиторий, преподавателей и сервисов следует начинать с трёх крупнейших подразделений.",styles,colors.HexColor("#EAF8F7")),Spacer(1,3*mm),
          _v51_callout("ДЕЙСТВИЕ","Проверить мощность","Сопоставить контингент с числом групп, преподавателей и доступных учебных площадей по каждому из трёх лидеров.",styles,colors.HexColor("#FFF6E2"))]
    story.append(Table([[chart,side]],colWidths=[width*.68,width*.32],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))

    # Funding story
    story.append(PageBreak()); own=sum(x.get("count",0) for x in fn if "собствен" in str(x.get("value","")).casefold()); grants=sum(x.get("count",0) for x in fn if "грант" in str(x.get("value","")).casefold())
    _v51_page_title(story,3,"Финансирование контингента",
        f"Собственные средства обеспечивают {_format_number(own)} обучающихся ({own*100/total:.1f}%), грантовые источники — {_format_number(grants)} ({grants*100/total:.1f}%).",styles)
    donut=_v51_chart("donut",[x.get("value") for x in fn[:6]],[x.get("count") for x in fn[:6]],width*.42,64*mm)
    gauge=_v51_chart("gauge",["Собственные средства","Гранты"],[own,grants],width*.54,27*mm,"Собственные средства против грантов")
    interpretation=_v51_callout("ИНТЕРПРЕТАЦИЯ",f"Разрыв {abs(own-grants)*100/total:.1f} п.п.","Платный контингент превышает грантовый; это влияет на устойчивость набора и сопровождение оплат.",styles,colors.HexColor("#EAF8F7"))
    action_box=_v51_callout("ДЕЙСТВИЕ","Контроль по факультетам","Отмечать отклонение доли собственных средств более 3 п.п.",styles,colors.HexColor("#FFF6E2"))
    notes=[gauge,Spacer(1,2*mm),Table([[interpretation,action_box]],colWidths=[width*.27,width*.27],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3)]))]
    story.append(Table([[donut,notes]],colWidths=[width*.44,width*.56],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))
    comparison = _stacked_share_chart(faculty, funding, analysis.get("rows", []), width=width, height=45*mm)
    if comparison:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("Финансирование внутри факультетов", styles["SubsectionCustom"]))
        story.append(comparison)

    # Study profile
    story.append(PageBreak()); stop=_v51_top(study,8)
    _v51_page_title(story,4,"Формы и языки обучения",
        f"Шестилетний бакалавриат охватывает {_v51_share(stop,total):.1f}% контингента; казахский язык — {_v51_share(lg,total):.1f}%.",styles)
    formchart=_v51_chart("bar",[x.get("value") for x in stop],[x.get("count") for x in stop],width*.58,100*mm,"Формы обучения")
    langchart=_v51_chart("donut",[x.get("value") for x in lg],[x.get("count") for x in lg],width*.39,67*mm,"Языковой профиль")
    action=_v51_callout("УПРАВЛЕНЧЕСКОЕ ДЕЙСТВИЕ","Синхронизировать ресурсы","Проверить обеспеченность шестилетних программ преподавателями, клиническими базами и материалами на казахском, русском и английском языках.",styles,colors.HexColor("#FFF6E2"))
    story.append(Table([[formchart,[langchart,action]]],colWidths=[width*.60,width*.40],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))

    # Demographic and international profile
    story.append(PageBreak()); gtop=_v51_top(gender,3); ctop=_v51_top(citizenship,6); groups=age.get("groups",[]) or []
    _v51_page_title(story,5,"Демографический и международный профиль",
        f"Средний возраст — {age.get('mean','—')} года; женщины составляют {_v51_share(gtop,total):.1f}%; иностранные граждане — {100-_v51_share(ctop,total):.1f}% при условии, что первая категория — Казахстан.",styles)
    gender_chart=_v51_chart("donut",[x.get("value") for x in gtop],[x.get("count") for x in gtop],width*.31,64*mm,"Пол")
    age_chart=_v51_chart("bar",[x.get("value") for x in groups],[x.get("count") for x in groups],width*.34,64*mm,"Возрастные группы")
    citizen_chart=_v51_chart("donut",[x.get("value") for x in ctop],[x.get("count") for x in ctop],width*.31,64*mm,"Гражданство")
    story.append(Table([[gender_chart,age_chart,citizen_chart]],colWidths=[width*.32,width*.36,width*.32],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))
    story.append(Spacer(1,3*mm)); story.append(Table([[
        _v51_callout("ВОЗРАСТ","Пик учебной нагрузки","Основная возрастная группа определяет спрос на расписание, практику и цифровые сервисы.",styles,colors.HexColor("#EAF8F7")),
        _v51_callout("ИНОСТРАННЫЕ СТУДЕНТЫ","Отдельный сервисный контур","Проверить языковую поддержку, адаптацию и сопровождение документов для крупнейших иностранных групп.",styles,colors.HexColor("#FFF6E2"))]],colWidths=[width/2,width/2],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))

    # Decisions
    story.append(PageBreak()); _v51_page_title(story,6,"Решения и контроль",
        "Каждое действие привязано к конкретному факту и измеримому контрольному показателю.",styles)
    decisions=[
        ("Нагрузка факультетов",f"Топ-3 = {top3:.1f}%","Сопоставить контингент с преподавателями, группами и площадями","Нагрузка на 1 преподавателя; наполняемость групп"),
        ("Финансирование",f"Собственные средства = {own*100/total:.1f}%","Контролировать структуру финансирования по факультетам","Изменение доли, п.п.; просроченные договоры"),
        ("Образовательный профиль",f"6-летний бакалавриат = {_v51_share(stop,total):.1f}%","Проверить ресурсы длительных программ и языковое обеспечение","Обеспеченность дисциплин и клинических баз"),
        ("Международный контингент",f"Иностранные граждане ≈ {100-_v51_share(ctop,total):.1f}%","Проверить адаптацию и сопровождение документов","Срок обработки обращений; доля незакрытых вопросов"),
    ]
    cells=[]
    for name,fact,action,metric in decisions:
        cells.append(_v51_callout(name,fact,f"Действие: {action}\nКонтроль: {metric}",styles,colors.HexColor("#F4F7FB")))
    story.append(Table([[cells[0],cells[1]],[cells[2],cells[3]]],colWidths=[width/2,width/2],rowHeights=[61*mm,61*mm],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])))
    story.append(_paragraph("Ограничение: текущий файл содержит один временной срез. Выводы о росте, снижении и причинах допускаются только после добавления сопоставимого предыдущего периода.",styles["SmallCustom"],700))

    doc.build(story,onFirstPage=_page_decor,onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size==0: raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


build_analytics_pdf = build_analytics_pdf_v51


# ---------------------------------------------------------------------------
# ADAPTIVE INFOGRAPHIC REPORT 5.2

def _v52_dimensions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Selects real categorical dimensions without assuming a business domain."""
    result = []
    low_information = []
    for column in analysis.get("categorical_columns", []):
        stats = column.get("statistics", {}) or {}
        unique = int(stats.get("unique_count", 0) or 0)
        if column.get("reportable") and 2 <= unique <= 100 and _v51_top(column, 1):
            if column.get("duplicate_of"):
                continue
            if column.get("low_information"):
                low_information.append(column)
            else:
                result.append(column)
    result.sort(key=lambda c: (
        int(c.get("statistics", {}).get("unique_count", 0) or 0) > 20,
        -float(c.get("statistics", {}).get("top_value_percent", 0) or 0),
    ))
    # Почти постоянный показатель показываем только когда других содержательных
    # разрезов нет. Иначе он остаётся в аудите как контроль исключений.
    return result or low_information[:1]


def _v52_fact(column: dict[str, Any], total: int) -> tuple[str, float, float]:
    top = _v51_top(column, 3)
    if not top or not total:
        return "Недостаточно данных для вывода.", 0.0, 0.0
    first = top[0]; count = int(first.get("count", 0) or 0)
    share = count * 100 / total
    top3 = sum(int(x.get("count", 0) or 0) for x in top[:3]) * 100 / total
    fact = (f"Крупнейшая категория — «{_safe_text(first.get('value'), 180)}»: "
            f"{_format_number(count)} записей ({share:.1f}%).")
    if len(top) > 1:
        second = int(top[1].get("count", 0) or 0)
        fact += f" Разница со второй категорией — {_format_number(count-second)} записей."
    return fact, share, top3


def _v52_interpretation(column: dict[str, Any], share: float, top3: float) -> tuple[str, str]:
    name = _safe_text(column.get("name"), 100)
    top = _v51_top(column, 1)
    leader = _safe_text(top[0].get("value"), 80) if top else "основной категории"
    if share >= 70:
        return ("Высокая концентрация направления",
                f"В разрезе «{name}» доминирует «{leader}» ({share:.1f}%). Это ключевая опорная группа контингента, определяющая основные процессы и нагрузку.")
    if share >= 45:
        return ("Приоритетный сегмент контингента",
                f"Категория «{leader}» формирует основной профиль по направлению «{name}» ({share:.1f}%), сохраняя при этом значимый объём в альтернативных группах.")
    if top3 >= 75:
        return ("Фокус на ключевых сегментах",
                f"Более 75% объёма по направлению «{name}» приходится на три базовые категории во главе с «{leader}».")
    return ("Диверсифицированная структура",
            f"Направление «{name}» характеризуется сбалансированным распределением по нескольким категориям без резкого доминирования.")


def _v52_action(column: dict[str, Any], share: float) -> tuple[str, str]:
    name = _safe_text(column.get("name"), 100)
    leader = _safe_text((_v51_top(column, 1) or [{}])[0].get("value"), 80)
    if share >= 45:
        return ("Управленческое решение",
                f"Профильным службам и руководству обеспечить адресное ресурсное обеспечение сегмента «{leader}» с оценкой рисков перегрузки инфраструктуры.")
    return ("Управленческое решение",
            f"Кураторам направления «{name}» распределить методические и организационные ресурсы пропорционально долям ключевых групп.")


def _v52_kpis(analysis: dict[str, Any], dimensions: list[dict[str, Any]], styles, width: float, ai_analysis: dict | None = None) -> Table:
    total = int(analysis.get("row_count", 0) or 0)
    
    # Извлекаем осмысленные бизнес-метрики вместо технических колонок
    top_dim = dimensions[0] if dimensions else {}
    top_dim_name = _safe_text(top_dim.get("name"), 25) or "КЛЮЧЕВОЙ РАЗРЕЗ"
    top_share = 0.0
    if top_dim and total:
        top_val = _v51_top(top_dim, 1)
        if top_val:
            top_share = int(top_val[0].get("count", 0) or 0) * 100 / total

    values = [
        (_format_number(total), "ВСЕГО СУБЪЕКТОВ", colors.HexColor("#11B5AE")),
        (f"{len(dimensions)} направл.", "СТРУКТУРНЫХ НАПРАВЛЕНИЙ", NAVY),
        (f"{top_share:.1f}%", f"МАКС. КОНЦЕНТРАЦИЯ ({top_dim_name.upper()})", RED),
        ("Активен", "СТАТУС МОНИТОРИНГА", colors.HexColor("#D29A18")),
    ]
    cells=[]
    for value,label,accent in values:
        cells.append([Paragraph(_escape(value,60),ParagraphStyle("v52k",parent=styles["SectionCustom"],fontSize=16,textColor=accent,alignment=TA_CENTER,spaceBefore=0,spaceAfter=2)),
                      Paragraph(label,ParagraphStyle("v52l",parent=styles["SmallCustom"],alignment=TA_CENTER,fontSize=7))])
    table=Table([cells],colWidths=[width/4]*4,rowHeights=[24*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F7F9FC")),("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.5,BORDER),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    return table


def build_analytics_pdf_v52(
    matrix:list[list], title:str, source_name:str="", sheet_name:str="",
    output_dir:str|Path|None=None, description:str="", include_source_table:bool=False,
    orientation:str="auto", ai_analysis:dict|None=None,
    report_profile:str="Автоматически", audience:str="Руководство",
    report_depth:str="Краткий (C-Level, 3-4 стр)",
) -> Path:
    """Builds a domain-neutral report entirely from the current workbook."""
    if not matrix: raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis=analyze_matrix(matrix); total=int(analysis.get("row_count",0) or 0)
    if total<=0: raise ValueError("В выбранном листе нет строк данных для отчёта.")
    dimensions=_v52_dimensions(analysis)
    out=Path(output_dir).expanduser() if output_dir else Path.home()/"Documents"/"BahonIQ Reports";out.mkdir(parents=True,exist_ok=True)
    output_path=_unique_path(out/(_filename(title)+".pdf"));page_size=landscape(A4);page_width,_=page_size;width=page_width-30*mm
    doc=SimpleDocTemplate(str(output_path),pagesize=page_size,leftMargin=15*mm,rightMargin=15*mm,topMargin=11*mm,bottomMargin=15*mm,title=_safe_text(title,200),subject="Адаптивный аналитический отчёт")
    styles=_make_styles();story=[]

    subtitle=_safe_text(description,300) or "Автоматический анализ структуры, распределений и ключевых концентраций"
    cover=[Paragraph(_escape(title,180),styles["CoverTitleLightCustom"]),Paragraph(_escape(subtitle,320),styles["CoverSubtitleLightCustom"]),Spacer(1,22*mm),Paragraph(_escape(f"{report_profile} • {audience}",180),styles["CoverSubtitleLightCustom"]),Paragraph(datetime.now().strftime("%d.%m.%Y"),styles["CoverSubtitleLightCustom"])]
    story.append(Table([[cover]],colWidths=[width],rowHeights=[150*mm],style=TableStyle([("BACKGROUND",(0,0),(-1,-1),NAVY),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),18*mm),("RIGHTPADDING",(0,0),(-1,-1),18*mm)])))

    # Dashboard uses only dimensions actually found in this workbook.
    story.append(PageBreak()); 
    summary = (ai_analysis or {}).get("summary") if isinstance(ai_analysis, dict) and (ai_analysis or {}).get("summary") else f"Комплексный анализ контингента и структуры: {_format_number(total)} записей по {len(dimensions)} ключевым разрезам."
    _v51_page_title(story,1,"Сводная аналитическая панель",summary,styles);story.append(_v52_kpis(analysis,dimensions,styles,width,ai_analysis));story.append(Spacer(1,4*mm))
    dashboard=[]
    for column in dimensions[:2]:
        top=_v51_top(column,7);kind="donut" if len(top)<=5 else "bar"
        dashboard.append(_v51_chart(kind,[x.get("value") for x in top],[x.get("count") for x in top],width*.48,86*mm,_safe_text(column.get("name"),80)))
    if len(dashboard)==2:
        story.append(Table([dashboard],colWidths=[width/2,width/2],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))
    elif dashboard:
        story.append(dashboard[0])
    else:
        numeric=[c for c in analysis.get("numeric_columns",[]) if c.get("reportable")]
        text="Категориальные разрезы не обнаружены. Доступны числовые показатели: "+", ".join(_safe_text(c.get("name"),60) for c in numeric[:8]) if numeric else "В наборе не обнаружены показатели, пригодные для построения распределений."
        story.append(_v51_callout("СТРУКТУРА ДАННЫХ","Диаграммы не построены",text,styles,colors.HexColor("#F4F7FB")))

    # Ограничение количества детальных страниц в зависимости от глубины отчёта
    depth_str = str(report_depth).lower()
    if "краткий" in depth_str or "c-level" in depth_str or "3-4" in depth_str:
        max_detailed_pages = 2  # Обложка + Dashboard + 2 главных разреза + Выводы = 5 стр
    elif "стандартный" in depth_str or "5-6" in depth_str:
        max_detailed_pages = 4  # Обложка + Dashboard + 4 разреза + Выводы = 7 стр
    else:
        max_detailed_pages = 8  # Полный аудит

    # Фильтруем и ранжируем разрезы: отдаем приоритет тем, где есть сюжеты от ИИ или содержательный разброс
    selected_dims = []
    ai_stories = (ai_analysis or {}).get("stories", []) if isinstance(ai_analysis, dict) else []
    ai_topics = [str(s.get("topic") or "").casefold().strip() for s in ai_stories if isinstance(s, dict)]

    # Сначала те, о которых говорил ИИ
    for column in dimensions:
        c_name = str(column.get("name") or "").casefold().strip()
        if any(t and (t in c_name or c_name in t) for t in ai_topics):
            if column not in selected_dims:
                selected_dims.append(column)

    # Затем остальные
    for column in dimensions:
        if column not in selected_dims:
            selected_dims.append(column)

    page_no=2; decision_rows=[]
    for column in selected_dims[:max_detailed_pages]:
        col_name = _safe_text(column.get("name"), 100)
        fact,share,top3=_v52_fact(column,total)
        interp_title,interp_text=_v52_interpretation(column,share,top3)
        action_title,action_text=_v52_action(column,share)
        if isinstance(ai_analysis, dict):
            for s in ai_analysis.get("stories", []) or []:
                if not isinstance(s, dict): continue
                s_topic = str(s.get("topic") or "").casefold().strip()
                if s_topic and (s_topic in col_name.casefold() or col_name.casefold() in s_topic):
                    if s.get("headline") and len(str(s["headline"])) <= 60 and not str(s["headline"]).lower().startswith("наибольшее"):
                        interp_title = str(s["headline"]).strip()
                    if s.get("interpretation") and len(str(s["interpretation"])) >= 15:
                        interp_text = str(s["interpretation"]).strip()
                    if s.get("action") and len(str(s["action"])) >= 15:
                        action_title = "Управленческое решение"
                        action_text = str(s["action"]).strip()
                    break
        story.append(PageBreak());_v51_page_title(story,page_no,col_name,fact,styles)
        top=_v51_top(column,10);kind="donut" if len(top)<=5 else "bar"
        chart=_v51_chart(kind,[x.get("value") for x in top],[x.get("count") for x in top],width*.65,108*mm)
        side=[_v51_callout("КЛЮЧЕВОЙ ФАКТ",f"{share:.1f}%",f"Доля крупнейшей категории по показателю «{col_name}».",styles),Spacer(1,3*mm),_v51_callout("ИНТЕРПРЕТАЦИЯ",interp_title,interp_text,styles,colors.HexColor("#EAF8F7")),Spacer(1,3*mm),_v51_callout("ДЕЙСТВИЕ",action_title,action_text,styles,colors.HexColor("#FFF6E2"))]
        story.append(Table([[chart,side]],colWidths=[width*.67,width*.33],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])))
        decision_rows.append((col_name,f"{share:.1f}%",action_title,action_text));page_no+=1

    story.append(PageBreak());_v51_page_title(story,page_no,"Выводы и контроль","Итоговые действия сформированы только по показателям, найденным в текущем Excel-файле.",styles)
    if decision_rows:
        cards=[]
        for name,share,action_title,action_text in decision_rows[:4]:
            cards.append(_v51_callout(name,share,f"{action_title}. {action_text}",styles,colors.HexColor("#F4F7FB")))
        while len(cards)<4: cards.append(Spacer(1,1))
        story.append(Table([[cards[0],cards[1]],[cards[2],cards[3]]],colWidths=[width/2,width/2],rowHeights=[61*mm,61*mm],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])))
    else:
        story.append(_v51_callout("ВЫВОД","Недостаточно категориальных данных","Добавьте столбцы с повторяющимися категориями или укажите другой лист Excel.",styles,colors.HexColor("#FFF6E2")))
    story.append(_paragraph("Ограничение: один временной срез описывает текущую структуру, но не подтверждает рост, снижение или причинно-следственные связи.",styles["SmallCustom"],700))
    doc.build(story,onFirstPage=_page_decor,onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size==0: raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


build_analytics_pdf = build_analytics_pdf_v52


# ---------------------------------------------------------------------------
# ADAPTIVE EVIDENCE REPORT 5.3

def _v53_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace("\u00a0", "").replace(" ", "")
            if "," in value and "." not in value:
                value = value.replace(",", ".")
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError, OverflowError):
        return None


def _v53_label_column(analysis: dict[str, Any]) -> dict[str, Any] | None:
    """Выбирает безопасный текстовый столбец для подписей объектов."""
    candidates = []
    for column in analysis.get("categorical_columns", []):
        if column.get("role") in {"sensitive", "identifier"}:
            continue
        unique = int(column.get("unique_count", 0) or 0)
        if unique < 2:
            continue
        name = str(column.get("name", "")).casefold()
        priority = 0 if any(x in name for x in (
            "наимен", "назван", "страна", "регион", "город", "объект",
            "организац", "товар", "продукт", "категор", "подраздел",
        )) else 1
        candidates.append((priority, -unique, column))
    return min(candidates, default=(0, 0, None), key=lambda x: (x[0], x[1]))[2]


def _v53_ranked_values(
    analysis: dict[str, Any], numeric: dict[str, Any], label: dict[str, Any] | None,
    limit: int = 8,
) -> list[tuple[str, float]]:
    rows = analysis.get("rows", []) or []
    n_index = int(numeric.get("index", -1))
    l_index = int(label.get("index", -1)) if label else -1
    pairs = []
    multiplier = float((numeric.get("display", {}) or {}).get("multiplier", 1) or 1)
    for row_no, row in enumerate(rows, 1):
        if n_index < 0 or n_index >= len(row):
            continue
        value = _v53_number(row[n_index])
        if value is None:
            continue
        raw_label = row[l_index] if 0 <= l_index < len(row) else f"Запись {row_no}"
        shown = _safe_text(raw_label, 80) or f"Запись {row_no}"
        pairs.append((shown, value * multiplier))
    pairs.sort(key=lambda item: item[1], reverse=True)
    return pairs[:limit]


def _v53_ai_items(ai_analysis: dict | None, key: str, limit: int = 8) -> list[str]:
    if not isinstance(ai_analysis, dict):
        return []
    result = []
    for item in ai_analysis.get(key, []) or []:
        text = _safe_text(item, 650)
        if text and text not in result:
            result.append(text)
    return result[:limit]


def _v53_ai_for_column(ai_analysis: dict | None, column_name: str) -> str:
    needle = column_name.casefold().strip()
    if not needle:
        return ""
    if needle == "пол":
        for key in ("findings", "risks", "recommendations"):
            for item in _v53_ai_items(ai_analysis, key, 12):
                low = item.casefold()
                if any(k in low for k in ("грант", "оплат", "финанс", "валют", "доход", "бюджет", "поступлен", "собственн")):
                    continue
                if any(g in low for g in ("женск", "мужск", "гендер", "девуш", "юнош", " половой", " по полу")):
                    return item
        return ""
    pattern = re.compile(rf'(?:\A|[^\wа-яА-ЯёЁ]){re.escape(needle)}(?:\Z|[^\wа-яА-ЯёЁ])', re.IGNORECASE)
    for key in ("findings", "risks", "recommendations"):
        for item in _v53_ai_items(ai_analysis, key, 12):
            if pattern.search(item):
                return item
    return ""


def _v54_story_for_column(
    ai_analysis: dict | None, column_name: str,
    column: dict[str, Any] | None = None, total: int = 0,
) -> dict[str, str]:
    """Returns a story only when its headline evidence matches this chart.

    Topic matching alone is unsafe: a model can describe a percentage inside a
    subgroup while the page visualises the whole workbook.  Require the leader
    and either its global count or its global share before replacing page facts.
    """
    if not isinstance(ai_analysis, dict):
        return {}
    needle = column_name.casefold().strip()
    best = {}
    for raw in ai_analysis.get("stories", []) or []:
        if not isinstance(raw, dict):
            continue
        topic = _safe_text(raw.get("topic"), 100)
        topic_folded = topic.casefold().strip()
        if needle == topic_folded or needle in topic_folded or topic_folded in needle:
            if column is not None and total:
                top = _v51_top(column, 1)
                if not top:
                    continue
                leader = _safe_text(top[0].get("value"), 180).casefold()
                count = int(top[0].get("count", 0) or 0)
                share = count * 100 / total
                proof = " ".join(
                    _safe_text(raw.get(key), 700)
                    for key in ("headline", "evidence")
                ).casefold().replace("\u00a0", " ")
                compact_proof = re.sub(r"\s+", "", proof)
                count_matches = str(count) in compact_proof
                share_matches = any(
                    token in proof
                    for token in (
                        f"{share:.1f}%", f"{share:.1f} %",
                        f"{share:.2f}%", f"{share:.2f} %",
                    )
                )
                leader_matches = bool(leader and leader in proof)
                if not leader_matches or not (count_matches or share_matches):
                    continue
            best = {
                "story_type": _safe_text(raw.get("story_type"), 40),
                "headline": _safe_text(raw.get("headline"), 150),
                "evidence": _safe_text(raw.get("evidence"), 300),
                # Карточки находятся рядом с диаграммой. Длинный текст делает
                # единственную строку Table выше страницы, после чего ReportLab
                # выбрасывает LayoutError вместо готового отчёта.
                "interpretation": _safe_text(raw.get("interpretation"), 260),
                "limitation": _safe_text(raw.get("limitation"), 180),
                "action": _safe_text(raw.get("action"), 220),
            }
            break
    return best


def _v53_numeric_takeaway(column: dict[str, Any]) -> str:
    stats = column.get("statistics", {}) or {}
    name = _safe_text(column.get("name"), 100)
    display = column.get("display", {}) or {}
    multiplier = float(display.get("multiplier", 1) or 1)
    suffix = str(display.get("unit") or "")
    def shown(value: Any) -> str:
        if value is None:
            return "—"
        text = _format_number(float(value) * multiplier)
        return text + (suffix if suffix == "%" else (f" {suffix}" if suffix else ""))
    return (
        f"«{name}»: медиана {shown(stats.get('median'))}, среднее "
        f"{shown(stats.get('mean'))}; диапазон от "
        f"{shown(stats.get('min'))} до {shown(stats.get('max'))}."
    )


def _v54_cross_analysis(analysis: dict[str, Any]) -> dict[str, Any] | None:
    """Selects one evidence-rich categorical cross-tab for the report."""
    columns = [
        column for column in analysis.get("categorical_columns", [])
        if column.get("reportable") and not column.get("duplicate_of")
        and not column.get("low_information")
        and 2 <= int(column.get("unique_count", 0) or 0) <= 25
    ]
    rows = analysis.get("rows", []) or []
    if len(columns) < 2 or not rows:
        return None

    def priority(name: str, primary: bool) -> int:
        folded = name.casefold()
        if primary:
            markers = ("факульт", "школ", "подраздел", "программ", "специаль", "степен", "курс", "отдел", "регион")
        else:
            markers = ("финанс", "оплат", "грант", "форм", "пол", "язык", "статус", "граждан")
        return 8 if any(marker in folded for marker in markers) else 0

    best: tuple[float, dict[str, Any]] | None = None
    for primary in columns:
        p_unique = int(primary.get("unique_count", 0) or 0)
        if not 2 <= p_unique <= 20:
            continue
        for secondary in columns:
            if secondary is primary:
                continue
            s_unique = int(secondary.get("unique_count", 0) or 0)
            if not 2 <= s_unique <= 8:
                continue
            pi, si = int(primary["index"]), int(secondary["index"])
            counts: dict[str, Counter] = {}
            global_counts: Counter = Counter()
            for row in rows:
                if pi >= len(row) or si >= len(row):
                    continue
                left = _safe_text(row[pi], 100)
                right = _safe_text(row[si], 100)
                if not left or not right:
                    continue
                counts.setdefault(left, Counter())[right] += 1
                global_counts[right] += 1
            if len(counts) < 2 or len(global_counts) < 2:
                continue
            leaders = []
            for bucket in counts.values():
                total = sum(bucket.values())
                leaders.append(max(bucket.values()) * 100 / total if total else 0)
            variation = max(leaders) - min(leaders) if leaders else 0
            score = priority(str(primary.get("name", "")), True)
            score += priority(str(secondary.get("name", "")), False)
            score += min(12.0, variation / 2)
            score -= max(0, p_unique - 12) * .4
            payload = {
                "primary": primary,
                "secondary": secondary,
                "counts": counts,
                "global_counts": global_counts,
                "variation": round(variation, 1),
            }
            if best is None or score > best[0]:
                best = (score, payload)
    return best[1] if best else None


def _v54_cross_table(cross: dict[str, Any], styles, width: float) -> tuple[Table, str]:
    counts = cross["counts"]
    secondary_values = [name for name, _ in cross["global_counts"].most_common(4)]
    primary_values = sorted(counts, key=lambda name: -sum(counts[name].values()))[:6]
    header = [_safe_text(cross["primary"].get("name"), 35)] + secondary_values + ["Всего"]
    data: list[list[Any]] = [header]
    for primary_value in primary_values:
        bucket = counts[primary_value]
        total = sum(bucket.values())
        row: list[Any] = [_safe_text(primary_value, 45)]
        for secondary_value in secondary_values:
            count = int(bucket.get(secondary_value, 0))
            row.append(f"{_format_number(count)}\n{count * 100 / total:.1f}%" if total else "0")
        row.append(_format_number(total))
        data.append(row)
    col_widths = [width * .28] + [width * .14] * len(secondary_values) + [width * .12]
    table = _table(data, widths=col_widths, font_size=7)
    conclusion = (
        f"Состав по показателю «{_safe_text(cross['secondary'].get('name'), 80)}» "
        f"различается между группами «{_safe_text(cross['primary'].get('name'), 80)}». "
        f"Разброс доли ведущей категории достигает {cross['variation']:.1f} п.п."
    )
    return table, conclusion


def _v54_select_dates(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Keeps only date views that are meaningful for a current snapshot.

    A roster of active students is not a ten-year observation period.  Admission
    dates describe cohorts, while birth dates describe age.  Showing both
    admission date fields usually duplicates the same story, so keep one cohort
    view and one age view.
    """
    columns = analysis.get("date_columns", []) or []
    age_columns = [
        column for column in columns
        if (column.get("statistics", {}) or {}).get("age_statistics")
    ]
    cohort_columns = [
        column for column in columns
        if not (column.get("statistics", {}) or {}).get("age_statistics")
        and 2 <= len((column.get("statistics", {}) or {}).get("year_counts", []) or []) <= 15
    ]

    def cohort_priority(column: dict[str, Any]) -> tuple[int, int]:
        name = str(column.get("name", "")).casefold()
        rank = 0 if "поступ" in name else 1 if "зачис" in name else 2
        years = len((column.get("statistics", {}) or {}).get("year_counts", []) or [])
        return rank, years

    cohort_columns.sort(key=cohort_priority)
    return cohort_columns[:1] + age_columns[:1]


def build_analytics_pdf_v53(
    matrix: list[list], title: str, source_name: str = "", sheet_name: str = "",
    output_dir: str | Path | None = None, description: str = "",
    include_source_table: bool = False, orientation: str = "auto",
    ai_analysis: dict | None = None, report_profile: str = "Автоматически",
    audience: str = "Руководство",
    report_depth: str = "Полный аудит (Все категории, 8+ стр)",
) -> Path:
    """Адаптивный отчёт: страницы определяются показателями текущего файла."""
    if not matrix:
        raise ValueError("Невозможно сформировать отчёт: данных нет.")
    analysis = analyze_matrix(matrix)
    total = int(analysis.get("row_count", 0) or 0)
    if total <= 0:
        raise ValueError("В выбранном листе нет строк данных для отчёта.")

    depth = str(report_depth).casefold()
    dimension_limit = 10 if ("полн" in depth or "8" in depth or "10" in depth) else (4 if "крат" in depth or "3-4" in depth else 6)
    dimensions = _v52_dimensions(analysis)[:dimension_limit]
    numeric = [
        c for c in analysis.get("numeric_columns", [])
        if c.get("reportable") and not c.get("identifier_like")
        and int((c.get("statistics", {}) or {}).get("count", 0) or 0) > 1
    ][:6]
    dates = _v54_select_dates(analysis)
    label_column = _v53_label_column(analysis)

    out = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    out.mkdir(parents=True, exist_ok=True)
    ai_title = _safe_text((ai_analysis or {}).get("report_title"), 180)
    ai_subtitle = _safe_text((ai_analysis or {}).get("report_subtitle"), 380)
    display_title = ai_title or title
    output_path = _unique_path(out / (_filename(display_title) + ".pdf"))
    page_size = landscape(A4)
    page_width, _ = page_size
    width = page_width - 30 * mm
    doc = SimpleDocTemplate(
        str(output_path), pagesize=page_size, leftMargin=15 * mm,
        rightMargin=15 * mm, topMargin=11 * mm, bottomMargin=15 * mm,
        title=_safe_text(display_title, 200), subject="Адаптивный аналитический отчёт",
    )
    styles = _make_styles()
    story = []

    subtitle = ai_subtitle or (
        f"Анализ {total} записей: структура, числовые показатели, "
        "лидеры, отклонения и доказательные выводы"
    )
    visible_profile = _safe_text(report_profile, 120) or "Аналитический отчёт"
    if any(marker in visible_profile.casefold() for marker in ("qwen", "ollama", "ии", "ai")):
        visible_profile = "Аналитический отчёт"
    cover = [
        Paragraph(_escape(display_title, 180), styles["CoverTitleLightCustom"]),
        Paragraph(_escape(subtitle, 420), styles["CoverSubtitleLightCustom"]),
        Spacer(1, 22 * mm),
        Paragraph(_escape(f"{visible_profile} • {audience}", 180), styles["CoverSubtitleLightCustom"]),
        Paragraph(datetime.now().strftime("%d.%m.%Y"), styles["CoverSubtitleLightCustom"]),
    ]
    story.append(Table([[cover]], colWidths=[width], rowHeights=[150 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 18 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 18 * mm),
    ])))

    page_no = 1
    story.append(PageBreak())
    overview = (
        f"Проанализировано {_format_number(total)} строк и "
        f"{int(analysis.get('analyzed_column_count', len(analysis.get('headers', []))) or 0)} содержательных столбцов: найдено "
        f"{len(dimensions)} категориальных разрезов и {len(numeric)} числовых показателей."
    )
    _v51_page_title(story, page_no, "Карта показателей", overview, styles)
    story.append(_v52_kpis(analysis, dimensions, styles, width))
    story.append(Spacer(1, 4 * mm))
    preview = []
    for column in dimensions[:2]:
        top = _v51_top(column, 7)
        preview.append(_v51_chart(
            "donut" if len(top) <= 5 else "bar",
            [x.get("value") for x in top], [x.get("count") for x in top],
            width * .48, 82 * mm, _safe_text(column.get("name"), 90),
        ))
    if len(preview) == 2:
        story.append(Table([preview], colWidths=[width / 2, width / 2], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])))
    elif preview:
        story.append(preview[0])
    elif numeric:
        cards = []
        for column in numeric[:2]:
            stats = column.get("statistics", {}) or {}
            cards.append(_v51_callout(
                _safe_text(column.get("name"), 80),
                _format_number(stats.get("median")),
                f"Медиана; среднее — {_format_number(stats.get('mean'))}",
                styles, colors.HexColor("#F4F7FB"),
            ))
        story.append(Table([cards], colWidths=[width / len(cards)] * len(cards), style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])))

    for column in dimensions:
        page_no += 1
        fact, share, top3 = _v52_fact(column, total)
        story_data = _v54_story_for_column(
            ai_analysis, _safe_text(column.get("name"), 100), column, total,
        )
        ai_text = _safe_text(
            story_data.get("interpretation")
            or _v53_ai_for_column(ai_analysis, _safe_text(column.get("name"), 100)),
            260,
        )
        story.append(PageBreak())
        page_title = story_data.get("headline") or _safe_text(column.get("name"), 100)
        takeaway = story_data.get("evidence") or fact
        _v51_page_title(story, page_no, page_title, takeaway, styles)
        top = _v51_top(column, 10)
        chart = _v51_chart(
            "donut" if len(top) <= 5 else "bar",
            [x.get("value") for x in top], [x.get("count") for x in top],
            width * .64, 108 * mm,
        )
        side = [_v51_callout("КОНЦЕНТРАЦИЯ", f"{share:.1f}%", "Доля крупнейшей категории", styles)]
        if ai_text:
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout(
                    "АНАЛИТИЧЕСКИЙ ВЫВОД", "Что означает результат",
                    _safe_text(ai_text, 180), styles,
                    colors.HexColor("#EAF8F7"),
                ),
            ])
        else:
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout(
                    "ТРИ КРУПНЕЙШИЕ КАТЕГОРИИ", f"{top3:.1f}%",
                    "Совокупная доля трёх крупнейших категорий",
                    styles, colors.HexColor("#F4F7FB"),
                ),
            ])
        if story_data.get("action"):
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout(
                    "ОБОСНОВАННОЕ ДЕЙСТВИЕ", "Следующий шаг",
                    _safe_text(story_data["action"], 150), styles,
                    colors.HexColor("#FFF6E2"),
                ),
            ])
        # На странице с действием ограничение переносится в итоговую логику:
        # пять карточек в одной боковой колонке могут физически не поместиться.
        if story_data.get("limitation") and not story_data.get("action"):
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout(
                    "ГРАНИЦА ВЫВОДА", "Что нельзя утверждать",
                    _safe_text(story_data["limitation"], 180), styles,
                    colors.HexColor("#FFF6E2"),
                ),
            ])
        story.append(Table([[chart, side]], colWidths=[width * .66, width * .34], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])))

    cross = _v54_cross_analysis(analysis)
    if cross:
        page_no += 1
        story.append(PageBreak())
        cross_table, cross_conclusion = _v54_cross_table(cross, styles, width)
        _v51_page_title(
            story, page_no,
            f"{_safe_text(cross['primary'].get('name'), 70)} × {_safe_text(cross['secondary'].get('name'), 70)}",
            cross_conclusion, styles,
        )
        story.append(cross_table)
        story.append(Spacer(1, 5 * mm))
        story.append(_v51_callout(
            "КАК ЧИТАТЬ ТАБЛИЦУ", "Количество и доля внутри строки",
            "Каждая ячейка показывает число записей и долю категории внутри соответствующей группы. "
            "Сравнивайте проценты по строкам, а не только абсолютные значения.",
            styles, colors.HexColor("#EAF8F7"),
        ))

    for column in numeric:
        page_no += 1
        stats = column.get("statistics", {}) or {}
        ranked = _v53_ranked_values(analysis, column, label_column, 9)
        story.append(PageBreak())
        story_data = _v54_story_for_column(
            ai_analysis, _safe_text(column.get("name"), 100), column, total,
        )
        _v51_page_title(
            story, page_no,
            story_data.get("headline") or _safe_text(column.get("name"), 100),
            story_data.get("evidence") or _v53_numeric_takeaway(column), styles,
        )
        if ranked:
            chart = _v51_chart(
                "bar", [x[0] for x in ranked], [x[1] for x in ranked],
                width * .64, 108 * mm,
                "Лидирующие значения" + (f" по «{_safe_text(label_column.get('name'), 60)}»" if label_column else ""),
            )
        else:
            chart = Spacer(1, 108 * mm)
        ai_text = _safe_text(
            story_data.get("interpretation")
            or _v53_ai_for_column(ai_analysis, _safe_text(column.get("name"), 100)),
            260,
        )
        deviation = abs(float(stats.get("mean", 0) or 0) - float(stats.get("median", 0) or 0))
        display = column.get("display", {}) or {}
        multiplier = float(display.get("multiplier", 1) or 1)
        unit = str(display.get("unit") or "")
        def display_value(value: Any) -> str:
            shown = _format_number(float(value or 0) * multiplier)
            return shown + (unit if unit == "%" else (f" {unit}" if unit else ""))
        side = [
            _v51_callout("ЦЕНТР РАСПРЕДЕЛЕНИЯ", display_value(stats.get("median")),
                         f"Медиана; среднее — {display_value(stats.get('mean'))}", styles),
            Spacer(1, 3 * mm),
            _v51_callout("РАЗБРОС", display_value(stats.get("range")),
                         f"Размах; потенциальных выбросов — {int(stats.get('outlier_count', 0) or 0)}", styles, colors.HexColor("#EAF8F7")),
        ]
        if ai_text:
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout("АНАЛИТИЧЕСКИЙ ВЫВОД", display_value(deviation), ai_text,
                             styles, colors.HexColor("#FFF6E2")),
            ])
        if story_data.get("limitation"):
            side.extend([
                Spacer(1, 3 * mm),
                _v51_callout("ГРАНИЦА ВЫВОДА", "Ограничение", story_data["limitation"],
                             styles, colors.HexColor("#F4F7FB")),
            ])
        story.append(Table([[chart, side]], colWidths=[width * .66, width * .34], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])))

    for column in dates:
        page_no += 1
        stats = column.get("statistics", {}) or {}
        story.append(PageBreak())
        age = stats.get("age_statistics", {}) or {}
        year_counts = stats.get("year_counts", []) or []
        takeaway = (
            f"Средний возраст — {age.get('mean', '—')} года; диапазон от "
            f"{age.get('min', '—')} до {age.get('max', '—')} лет."
            if age else (
                f"Среди действующего контингента представлены годы "
                f"{year_counts[0].get('value', '—')}–{year_counts[-1].get('value', '—')}. "
                f"Наибольшее число записей относится к "
                f"{max(year_counts, key=lambda item: int(item.get('count', 0) or 0)).get('value', '—')} году."
                if year_counts else "Недостаточно данных для распределения по годам."
            )
        )
        page_title = (
            _safe_text(column.get("name"), 100)
            if age else f"Распределение действующего контингента по годам: {_safe_text(column.get('name'), 70)}"
        )
        _v51_page_title(story, page_no, page_title, takeaway, styles)
        groups = age.get("groups", []) or []
        if groups:
            chart = _v51_chart("bar", [x.get("value") for x in groups], [x.get("count") for x in groups], width * .62, 105 * mm, "Распределение по группам")
            note = _v51_callout("СРЕДНЕЕ ЗНАЧЕНИЕ", str(age.get("mean", "—")), "Возраст рассчитан только по допустимым датам.", styles, colors.HexColor("#EAF8F7"))
            story.append(Table([[chart, note]], colWidths=[width * .66, width * .34], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
        else:
            if 2 <= len(year_counts) <= 12:
                chart = _v51_chart(
                    "column", [x.get("value") for x in year_counts],
                    [x.get("count") for x in year_counts], width * .66, 100 * mm,
                    "Количество записей по годам",
                )
                note = _v51_callout(
                    "ДЕЙСТВУЮЩИЙ КОНТИНГЕНТ", _format_number(sum(int(x.get("count", 0) or 0) for x in year_counts)),
                    "Диаграмма показывает распределение текущих записей по году события, а не длительность наблюдения.",
                    styles, colors.HexColor("#F4F7FB"),
                )
                story.append(Table([[chart, note]], colWidths=[width * .68, width * .32], style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])))
            else:
                story.append(_v51_callout(
                    "ДАТЫ", "Недостаточно групп",
                    "Для содержательного сравнения по годам нужно не менее двух годовых групп.",
                    styles, colors.HexColor("#F4F7FB"),
                ))

    findings = _v53_ai_items(ai_analysis, "findings", 6)
    risks = _v53_ai_items(ai_analysis, "risks", 4)
    recommendations = _v53_ai_items(ai_analysis, "recommendations", 6)
    if findings or risks or recommendations:
        page_no += 1
        story.append(PageBreak())
        _v51_page_title(story, page_no, "Выводы и решения", "Выводы основаны на рассчитанных показателях текущего набора данных.", styles)
        left = [Paragraph("ДОКАЗАТЕЛЬНЫЕ ВЫВОДЫ", styles["SubsectionCustom"])]
        left.extend(_bullet(x, styles) for x in (findings + risks)[:7])
        right = [Paragraph("ПРОВЕРЯЕМЫЕ ДЕЙСТВИЯ", styles["SubsectionCustom"])]
        right.extend(_bullet(f"{i}. {x}", styles) for i, x in enumerate(recommendations[:6], 1))
        story.append(Table([[left, right]], colWidths=[width * .55, width * .45], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F4F7FB")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FFF6E2")),
            ("BOX", (0, 0), (-1, -1), .5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), .5, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])))

    if include_source_table:
        _append_source_table(story, analysis, styles, width)

    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF не был создан или оказался пустым.")
    return output_path


build_analytics_pdf = build_analytics_pdf_v53
