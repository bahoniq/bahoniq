# -*- coding: utf-8 -*-
"""Генератор редактируемой управленческой презентации PowerPoint."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

from .analytics import analyze_matrix


NAVY = RGBColor(24, 49, 83)
BLUE = RGBColor(37, 99, 235)
TEAL = RGBColor(17, 181, 174)
TEXT = RGBColor(38, 50, 56)
MUTED = RGBColor(102, 112, 133)
PALE = RGBColor(238, 244, 255)
WHITE = RGBColor(255, 255, 255)
RED = RGBColor(180, 35, 24)


def _safe(value: Any, limit: int = 220) -> str:
    text = "" if value is None else str(value).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _filename(text: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", _safe(text, 80))
    return re.sub(r"\s+", "_", value).strip("._ ") or "Аналитический_отчёт"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Не удалось подобрать имя для PowerPoint-файла.")


def _set_run(run, size: int, color=TEXT, bold: bool = False) -> None:
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def _add_title(slide, title: str, subtitle: str = "") -> None:
    shape = slide.shapes.add_textbox(Inches(.65), Inches(.35), Inches(12), Inches(.65))
    frame = shape.text_frame
    frame.clear()
    run = frame.paragraphs[0].add_run()
    run.text = _safe(title, 100)
    _set_run(run, 24, NAVY, True)
    if subtitle:
        sub = slide.shapes.add_textbox(Inches(.68), Inches(1.02), Inches(11.8), Inches(.35))
        run = sub.text_frame.paragraphs[0].add_run()
        run.text = _safe(subtitle, 150)
        _set_run(run, 10, MUTED)


def _add_footer(slide, number: int) -> None:
    line = slide.shapes.add_shape(1, Inches(.65), Inches(7.15), Inches(12), Inches(.01))
    line.fill.solid(); line.fill.fore_color.rgb = RGBColor(217, 224, 232)
    line.line.fill.background()
    box = slide.shapes.add_textbox(Inches(11.8), Inches(7.2), Inches(.85), Inches(.22))
    p = box.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    run = p.add_run(); run.text = str(number); _set_run(run, 8, MUTED)


def _add_bullets(slide, items: list[str], x, y, w, h, size: int = 17) -> None:
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.clear(); frame.word_wrap = True
    for index, item in enumerate(items[:6]):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.text = _safe(item, 260)
        p.level = 0
        p.space_after = Pt(10)
        p.font.name = "Arial"; p.font.size = Pt(size); p.font.color.rgb = TEXT


def _add_kpi_cards(slide, values: list[tuple[str, str]]) -> None:
    count = max(1, min(len(values), 4)); card_w = 11.9 / count
    fills = [RGBColor(232, 248, 247), RGBColor(255, 238, 238), RGBColor(255, 247, 224), RGBColor(234, 244, 248)]
    accents = [TEAL, RED, RGBColor(210, 145, 20), RGBColor(42, 129, 147)]
    for index, (value, label) in enumerate(values[:4]):
        x = .7 + index * card_w
        shape = slide.shapes.add_shape(5, Inches(x), Inches(2.25), Inches(card_w - .18), Inches(1.65))
        shape.fill.solid(); shape.fill.fore_color.rgb = fills[index % len(fills)]
        shape.line.color.rgb = RGBColor(217, 224, 232)
        frame = shape.text_frame; frame.clear(); frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run = p.add_run(); run.text = value; _set_run(run, 25, accents[index % len(accents)], True)
        p = frame.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        run = p.add_run(); run.text = label; _set_run(run, 10, MUTED)


def _add_bar_chart(slide, title: str, labels: list[str], values: list[float]) -> None:
    data = ChartData()
    data.categories = [_safe(label, 32) for label in labels[:10]]
    data.add_series(title, [float(v) for v in values[:10]])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED, Inches(.8), Inches(1.45),
        Inches(11.7), Inches(5.35), data,
    ).chart
    chart.has_legend = False
    chart.has_title = True
    chart.chart_title.text_frame.text = _safe(title, 80)
    chart.value_axis.has_major_gridlines = True
    chart.category_axis.reverse_order = True
    chart.plots[0].series[0].format.fill.solid()
    chart.plots[0].series[0].format.fill.fore_color.rgb = TEAL
    chart.plots[0].has_data_labels = True
    chart.plots[0].data_labels.font.size = Pt(10)
    chart.chart_title.text_frame.paragraphs[0].runs[0].font.name = "Arial"


def _add_stacked_chart(slide, title: str, primary: dict, secondary: dict, rows: list) -> bool:
    from collections import Counter, defaultdict
    totals, cross = Counter(), defaultdict(Counter)
    for row in rows:
        try:
            a, b = str(row[primary["index"]]).strip(), str(row[secondary["index"]]).strip()
        except (IndexError, TypeError):
            continue
        if not a or not b or a == "None" or b == "None":
            continue
        totals[a] += 1; cross[a][b] += 1
    groups = [key for key, _ in totals.most_common(8)]
    categories = Counter()
    for key in groups: categories.update(cross[key])
    series_names = [key for key, _ in categories.most_common(6)]
    if len(groups) < 2 or len(series_names) < 2:
        return False
    data = ChartData(); data.categories = [_safe(x, 28) for x in groups]
    for name in series_names:
        data.add_series(_safe(name, 30), [cross[g][name] * 100 / totals[g] for g in groups])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_STACKED_100, Inches(.8), Inches(1.45),
        Inches(11.7), Inches(5.35), data,
    ).chart
    chart.has_legend = True; chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.value_axis.maximum_scale = 1.0
    chart.value_axis.minimum_scale = 0.0
    return True


def build_analytics_pptx(
    matrix: list[list], title: str, output_dir: str | Path | None = None,
    description: str = "", ai_analysis: dict | None = None,
    report_profile: str = "Автоматически", audience: str = "Руководство",
) -> Path:
    """Создаёт краткую презентацию с редактируемым текстом и диаграммами."""
    analysis = analyze_matrix(matrix)
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pptx"))

    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    slide = prs.slides.add_slide(blank)
    band = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(.22))
    band.fill.solid(); band.fill.fore_color.rgb = BLUE; band.line.fill.background()
    box = slide.shapes.add_textbox(Inches(.75), Inches(1.25), Inches(11.8), Inches(1.4))
    run = box.text_frame.paragraphs[0].add_run(); run.text = _safe(title, 160); _set_run(run, 32, NAVY, True)
    sub = f"{report_profile} анализ • Материал для: {audience}"
    box = slide.shapes.add_textbox(Inches(.78), Inches(2.85), Inches(10.8), Inches(.8))
    run = box.text_frame.paragraphs[0].add_run(); run.text = _safe(sub, 240); _set_run(run, 16, MUTED)
    domain = _safe((ai_analysis or {}).get("domain"), 100)
    if domain:
        box = slide.shapes.add_textbox(Inches(.78), Inches(5.7), Inches(5), Inches(.35))
        run = box.text_frame.paragraphs[0].add_run(); run.text = domain; _set_run(run, 11, BLUE, True)

    slide = prs.slides.add_slide(blank); _add_title(slide, "Управленческое резюме")
    summary = _safe((ai_analysis or {}).get("summary"), 520)
    findings = [_safe(x, 260) for x in (ai_analysis or {}).get("findings", [])]
    if summary:
        _add_bullets(slide, [summary] + findings[:4], Inches(.8), Inches(1.35), Inches(11.7), Inches(5.5), 16)
    else:
        _add_bullets(slide, analysis.get("insights", [])[:6], Inches(.8), Inches(1.35), Inches(11.7), Inches(5.5), 16)
    _add_footer(slide, 2)

    slide = prs.slides.add_slide(blank); _add_title(slide, "Ключевые KPI")
    reportable_num = [c for c in analysis.get("numeric_columns", []) if c.get("reportable")]
    reportable_cat = [c for c in analysis.get("categorical_columns", []) if c.get("reportable")]
    chartable = [c for c in reportable_cat if c.get("statistics", {}).get("top_values")]
    dominant_share = max(
        (c.get("statistics", {}).get("top_value_percent", 0) for c in chartable),
        default=0,
    )
    age_stat = next((
        c.get("statistics", {}).get("age_statistics")
        for c in analysis.get("date_columns", [])
        if c.get("statistics", {}).get("age_statistics")
    ), None)
    _add_kpi_cards(slide, [
        (f"{analysis.get('row_count', 0):,}".replace(",", " "), "Записей"),
        (str(len(reportable_cat)), "Разрезов анализа"),
        (f"{dominant_share:.1f}%", "Максимальная доля категории"),
        ((str(age_stat.get("mean")) if age_stat else str(len(reportable_num))),
         "Средний возраст, лет" if age_stat else "Числовых показателей"),
    ])
    _add_footer(slide, 3)

    risks = [_safe(x, 260) for x in (ai_analysis or {}).get("risks", [])]
    if risks:
        slide = prs.slides.add_slide(blank)
        _add_title(slide, "Риски и зоны внимания", "Факты, требующие управленческого решения")
        _add_bullets(slide, risks[:5], Inches(.8), Inches(1.35), Inches(11.7), Inches(5.5), 17)
        _add_footer(slide, 4)

    slide_no = 5 if risks else 4
    chart_columns = [c for c in reportable_cat if 2 <= c.get("statistics", {}).get("unique_count", 0) <= 100]
    for column in chart_columns[:3]:
        top = column.get("statistics", {}).get("top_values", [])[:10]
        if not top: continue
        slide = prs.slides.add_slide(blank); _add_title(slide, _safe(column.get("name"), 80), "Структура и лидирующие категории")
        _add_bar_chart(slide, _safe(column.get("name"), 60), [x.get("value") for x in top], [x.get("count", 0) for x in top])
        _add_footer(slide, slide_no); slide_no += 1

    if len(chart_columns) >= 2:
        for secondary in chart_columns[1:]:
            slide = prs.slides.add_slide(blank)
            _add_title(slide, "Сравнительный анализ", f"{secondary.get('name')} внутри групп {chart_columns[0].get('name')}")
            if _add_stacked_chart(slide, "Сравнение", chart_columns[0], secondary, analysis.get("rows", [])):
                _add_footer(slide, slide_no); slide_no += 1; break
            prs.slides._sldIdLst.remove(prs.slides._sldIdLst[-1])

    recommendations = [_safe(x, 260) for x in (ai_analysis or {}).get("recommendations", [])]
    if recommendations:
        slide = prs.slides.add_slide(blank); _add_title(slide, "Рекомендуемые действия")
        _add_bullets(slide, recommendations[:6], Inches(.8), Inches(1.35), Inches(11.7), Inches(5.5), 17)
        _add_footer(slide, slide_no)
        slide_no += 1

    slide = prs.slides.add_slide(blank)
    _add_title(slide, "Следующие шаги", "Практический переход от анализа к решению")
    next_steps = recommendations[:3] or [
        "Определить ответственных за ключевые показатели.",
        "Зафиксировать целевые значения и срок повторного измерения.",
        "Повторить анализ после обновления данных и сравнить результат.",
    ]
    _add_bullets(slide, next_steps, Inches(.8), Inches(1.4), Inches(11.7), Inches(4.8), 18)
    note = slide.shapes.add_textbox(Inches(.8), Inches(6.35), Inches(11.7), Inches(.35))
    run = note.text_frame.paragraphs[0].add_run()
    run.text = f"Источник: Excel • Профиль: {report_profile} • Аудитория: {audience}"
    _set_run(run, 9, MUTED)
    _add_footer(slide, slide_no)

    prs.save(output_path)
    if not output_path.is_file() or output_path.stat().st_size < 1000:
        raise RuntimeError("PowerPoint не был создан или оказался пустым.")
    return output_path


# ---------------------------------------------------------------------------
# EVIDENCE PRESENTATION 5.0

def _v50_dimensions(analysis: dict) -> list[dict]:
    priority = ("факульт", "финанс", "форма обуч", "пол", "граждан", "национ", "язык")
    result = [c for c in analysis.get("categorical_columns", [])
              if c.get("reportable") and 2 <= c.get("statistics", {}).get("unique_count", 0) <= 100]
    result.sort(key=lambda c: next((i for i, m in enumerate(priority)
                                    if m in str(c.get("name", "")).casefold()), len(priority)))
    return result


def _v50_fact(column: dict, total: int) -> str:
    top = _pro_top_values(column, 2)
    if not top or not total:
        return "Недостаточно данных для интерпретации"
    first = top[0]; count = int(first.get("count", 0) or 0)
    text = f"«{_safe(first.get('value'), 120)}» — {count:,} записей ({count * 100 / total:.1f}%)".replace(",", " ")
    if len(top) > 1:
        gap = count - int(top[1].get("count", 0) or 0)
        text += f"; отрыв от второй категории — {gap:,}".replace(",", " ")
    return text


def _v50_text(slide, text: str, x: float, y: float, w: float, h: float,
              size: int = 18, color=TEXT, bold: bool = False) -> None:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame; frame.clear(); frame.word_wrap = True
    p = frame.paragraphs[0]; p.space_after = Pt(0)
    run = p.add_run(); run.text = _safe(text, 900); _set_run(run, size, color, bold)


def _v50_distribution(slide, column: dict, total: int) -> None:
    values = _pro_top_values(column, 8)
    if not values:
        return
    data = ChartData(); data.categories = [_safe(x.get("value"), 48) for x in values]
    data.add_series("Количество", [int(x.get("count", 0) or 0) for x in values])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(.7), Inches(1.45),
                                   Inches(7.6), Inches(5.25), data).chart
    chart.has_legend = False; chart.value_axis.has_major_gridlines = True
    chart.category_axis.reverse_order = True
    chart.plots[0].series[0].format.fill.solid(); chart.plots[0].series[0].format.fill.fore_color.rgb = TEAL
    chart.plots[0].has_data_labels = True; chart.plots[0].data_labels.font.size = Pt(10)
    _v50_text(slide, "Что установлено", 8.65, 1.65, 3.8, .4, 17, NAVY, True)
    _v50_text(slide, _v50_fact(column, total), 8.65, 2.15, 3.8, 1.35, 17)
    _v50_text(slide, "Как это трактовать", 8.65, 3.75, 3.8, .4, 17, NAVY, True)
    _v50_text(slide,
              "Распределение показывает масштаб групп. Оно не доказывает причину и не означает проблему без плана, динамики и данных о ресурсах.",
              8.65, 4.25, 3.8, 1.65, 15)


def build_analytics_pptx_v50(
    matrix: list[list], title: str, output_dir: str | Path | None = None,
    description: str = "", ai_analysis: dict | None = None,
    report_profile: str = "Автоматически", audience: str = "Руководство",
) -> Path:
    """Creates a concise decision deck in which each claim has a computed basis."""
    analysis = analyze_matrix(matrix); total = int(analysis.get("row_count", 0) or 0)
    dimensions = _v50_dimensions(analysis)
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pptx"))
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5); blank = prs.slide_layouts[6]

    slide = prs.slides.add_slide(blank)
    band = slide.shapes.add_shape(1, 0, 0, Inches(.24), prs.slide_height)
    band.fill.solid(); band.fill.fore_color.rgb = BLUE; band.line.fill.background()
    _v50_text(slide, title, .8, 1.45, 11.5, 1.2, 32, NAVY, True)
    _v50_text(slide, "Анализ контингента для управленческих решений", .82, 2.85, 10.5, .5, 18, MUTED)
    _v50_text(slide, f"{report_profile} анализ. Материал для: {audience}", .82, 5.95, 10.5, .4, 12, MUTED)

    slide = prs.slides.add_slide(blank); _add_title(slide, "Цель и границы анализа")
    _add_bullets(slide, [
        f"Проанализировано {total:,} записей и {len(analysis.get('headers', []))} полей".replace(",", " "),
        "Метод: частотный и долевой анализ категорий, сравнение крупнейших групп, проверка пропусков и дублей",
        "Один срез описывает структуру, но не доказывает рост, снижение или причины различий",
        "Каждый вывод в презентации содержит значение и базу сравнения",
    ], Inches(.85), Inches(1.45), Inches(11.5), Inches(4.9), 18); _add_footer(slide, 2)

    slide = prs.slides.add_slide(blank); _add_title(slide, "Управленческое резюме")
    facts = [_v50_fact(c, total) for c in dimensions[:4]]
    _add_bullets(slide, facts or ["Недостаточно категориальных показателей для резюме"],
                 Inches(.85), Inches(1.4), Inches(11.5), Inches(4.8), 18)
    _v50_text(slide, "Выводы описывают распределение. Причины требуют сравнимого предыдущего периода и плановых значений.",
              .85, 6.1, 11.2, .55, 13, MUTED); _add_footer(slide, 3)

    slide_no = 4
    for column in dimensions:
        slide = prs.slides.add_slide(blank); _add_title(slide, str(column.get("name", "Показатель")))
        _v50_distribution(slide, column, total); _add_footer(slide, slide_no); slide_no += 1

    slide = prs.slides.add_slide(blank); _add_title(slide, "Доказательные выводы")
    _add_bullets(slide, [_v50_fact(c, total) for c in dimensions[:6]],
                 Inches(.85), Inches(1.35), Inches(11.5), Inches(5.5), 17); _add_footer(slide, slide_no); slide_no += 1

    slide = prs.slides.add_slide(blank); _add_title(slide, "Решения и контроль")
    actions = []
    for column in dimensions[:4]:
        name = str(column.get("name", "показатель"))
        actions.append(f"{name}: сопоставить концентрацию с планом и ресурсами; ответственный — деканат; контроль — изменение доли, п.п.")
    _add_bullets(slide, actions, Inches(.85), Inches(1.35), Inches(11.5), Inches(5.2), 16)
    _v50_text(slide, "Следующий отчёт должен показывать абсолютное изменение и изменение доли относительно этого среза.",
              .85, 6.2, 11.3, .5, 13, MUTED); _add_footer(slide, slide_no)

    prs.save(output_path)
    if not output_path.is_file() or output_path.stat().st_size < 1000:
        raise RuntimeError("PowerPoint не был создан или оказался пустым.")
    return output_path


# ---------------------------------------------------------------------------
# PROFESSIONAL PRESENTATION 4.1

def _pro_col(analysis: dict, *markers: str):
    for column in analysis.get("categorical_columns", []) + analysis.get("date_columns", []):
        name = str(column.get("name", "")).casefold()
        if any(marker.casefold() in name for marker in markers):
            return column
    return None


def _pro_top_values(column, limit=8):
    if not column:
        return []
    return list(column.get("statistics", {}).get("top_values", []) or [])[:limit]


def _pro_add_takeaway(slide, text: str) -> None:
    box = slide.shapes.add_textbox(Inches(.85), Inches(6.72), Inches(11.55), Inches(.34))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = _safe(text, 220)
    _set_run(run, 11, NAVY, True)


def _pro_add_chart_with_note(slide, title: str, column, note: str) -> None:
    top = _pro_top_values(column, 9)
    data = ChartData()
    data.categories = [_safe(item.get("value"), 35) for item in top]
    data.add_series(title, [float(item.get("count", 0)) for item in top])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED, Inches(.75), Inches(1.45),
        Inches(8.35), Inches(4.95), data,
    ).chart
    chart.has_legend = False
    chart.value_axis.has_major_gridlines = True
    chart.category_axis.reverse_order = True
    chart.plots[0].series[0].format.fill.solid()
    chart.plots[0].series[0].format.fill.fore_color.rgb = TEAL
    palette = [TEAL, RED, RGBColor(245, 184, 46), RGBColor(42, 129, 147), RGBColor(138, 163, 155)]
    for index, point in enumerate(chart.plots[0].series[0].points):
        point.format.fill.solid(); point.format.fill.fore_color.rgb = palette[index % len(palette)]
    chart.plots[0].has_data_labels = True
    chart.plots[0].data_labels.font.size = Pt(10)
    box = slide.shapes.add_textbox(Inches(9.4), Inches(1.75), Inches(3.1), Inches(3.9))
    frame = box.text_frame
    frame.clear(); frame.word_wrap = True
    p = frame.paragraphs[0]
    run = p.add_run(); run.text = "Вывод"; _set_run(run, 15, BLUE, True)
    p = frame.add_paragraph(); p.space_before = Pt(12)
    run = p.add_run(); run.text = _safe(note, 420); _set_run(run, 16, TEXT)


def _v42_add_donut_with_note(slide, title: str, column, note: str) -> None:
    top = _pro_top_values(column, 7)
    data = ChartData(); data.categories = [_safe(item.get("value"), 35) for item in top]
    data.add_series(title, [float(item.get("count", 0)) for item in top])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.DOUGHNUT, Inches(.85), Inches(1.45),
        Inches(7.8), Inches(5.15), data,
    ).chart
    chart.has_legend = True; chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.font.size = Pt(10)
    chart.plots[0].hole_size = 55
    palette = [TEAL, RED, RGBColor(245, 184, 46), RGBColor(42, 129, 147), RGBColor(138, 163, 155)]
    for index, point in enumerate(chart.plots[0].series[0].points):
        point.format.fill.solid(); point.format.fill.fore_color.rgb = palette[index % len(palette)]
    box = slide.shapes.add_textbox(Inches(9.15), Inches(1.7), Inches(3.15), Inches(4.2))
    frame = box.text_frame; frame.clear(); frame.word_wrap = True
    p = frame.paragraphs[0]; run = p.add_run(); run.text = "Ключевой вывод"; _set_run(run, 15, BLUE, True)
    p = frame.add_paragraph(); p.space_before = Pt(12)
    run = p.add_run(); run.text = _safe(note, 420); _set_run(run, 17, TEXT)


def _pro_findings(analysis: dict, ai_analysis: dict | None) -> list[str]:
    items = []
    for item in (ai_analysis or {}).get("findings", []) or []:
        text = _safe(item, 380)
        if len(text) >= 28 and any(char.isdigit() for char in text):
            items.append(text)
    funding = _pro_col(analysis, "финанс")
    funding_top = _pro_top_values(funding, 20)
    if funding_top:
        own = sum(float(x.get("count", 0)) for x in funding_top if "собствен" in str(x.get("value", "")).casefold())
        grants = sum(float(x.get("count", 0)) for x in funding_top if "грант" in str(x.get("value", "")).casefold())
        total = float(analysis.get("row_count", 0) or 0)
        if total:
            items.append(
                f"Собственные средства: {own:,.0f} обучающихся ({own * 100 / total:.1f}%). "
                f"Грантовые источники: {grants:,.0f} ({grants * 100 / total:.1f}%).".replace(",", " ")
            )
    for column in analysis.get("categorical_columns", []):
        top = _pro_top_values(column, 1)
        if not column.get("reportable") or not top:
            continue
        share = column.get("statistics", {}).get("top_value_percent", 0)
        candidate = (
            f"{column.get('name')}: «{top[0].get('value')}» — "
            f"{top[0].get('count')} записей ({share:.1f}%)."
        )
        if candidate not in items:
            items.append(candidate)
        if len(items) >= 5:
            break
    priority = ("финанс", "факульт", "возраст", "форма обучения", "пол", "граждан")
    items.sort(key=lambda text: next((i for i, marker in enumerate(priority) if marker in text.casefold()), len(priority)))
    return items[:6]


def build_analytics_pptx(
    matrix: list[list], title: str, output_dir: str | Path | None = None,
    description: str = "", ai_analysis: dict | None = None,
    report_profile: str = "Автоматически", audience: str = "Руководство",
) -> Path:
    """Создаёт редактируемую управленческую презентацию с доказательными выводами."""
    analysis = analyze_matrix(matrix)
    output_directory = Path(output_dir).expanduser() if output_dir else Path.home() / "Documents" / "BahonIQ Reports"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = _unique_path(output_directory / (_filename(title) + ".pptx"))
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # 1. Minimal cover
    slide = prs.slides.add_slide(blank)
    background = slide.background.fill; background.solid(); background.fore_color.rgb = NAVY
    accent = slide.shapes.add_shape(1, Inches(.72), Inches(1.0), Inches(.12), Inches(5.2))
    accent.fill.solid(); accent.fill.fore_color.rgb = TEAL; accent.line.fill.background()
    box = slide.shapes.add_textbox(Inches(1.18), Inches(1.35), Inches(10.8), Inches(1.8))
    run = box.text_frame.paragraphs[0].add_run(); run.text = _safe(title, 160); _set_run(run, 38, WHITE, True)
    box = slide.shapes.add_textbox(Inches(1.2), Inches(3.35), Inches(10.4), Inches(1.05))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = _safe(description, 260) or "Контингент, финансирование и возрастная структура"
    _set_run(run, 18, RGBColor(220, 231, 250))
    box = slide.shapes.add_textbox(Inches(1.2), Inches(6.45), Inches(10.5), Inches(.35))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = f"{report_profile} анализ для аудитории: {audience}"
    _set_run(run, 11, RGBColor(175, 201, 255))

    findings = _pro_findings(analysis, ai_analysis)
    summary = _safe((ai_analysis or {}).get("summary"), 650)

    # 2. Executive summary
    slide = prs.slides.add_slide(blank); _add_title(slide, "Управленческое резюме")
    _add_bullets(
        slide, ([summary] if summary else []) + findings[:4],
        Inches(.8), Inches(1.35), Inches(11.7), Inches(5.5), 17,
    )
    _add_footer(slide, 2)

    slide = prs.slides.add_slide(blank); _add_title(slide, "Масштаб анализа")
    _add_kpi_cards(slide, [
        (f"{analysis.get('row_count', 0):,}".replace(",", " "), "обучающихся"),
        (str(len([c for c in analysis.get('categorical_columns', []) if c.get('reportable')])), "аналитических разрезов"),
        (str(len(analysis.get("date_columns", []))), "показателей периода"),
    ])
    _add_footer(slide, 3)

    faculty = _pro_col(analysis, "факультет", "школа")
    funding = _pro_col(analysis, "финанс")
    study_form = _pro_col(analysis, "форма обучения")

    slide_no = 4
    for heading, column in (
        ("Финансирование обучающихся", funding),
        ("Структура по факультетам", faculty),
        ("Формы обучения", study_form),
    ):
        if not column:
            continue
        top = _pro_top_values(column, 1)
        share = column.get("statistics", {}).get("top_value_percent", 0)
        note = (
            f"Крупнейшая категория — «{top[0].get('value')}». "
            f"Она объединяет {top[0].get('count')} записей, или {share:.1f}% от общего числа."
        ) if top else "Данных для вывода недостаточно."
        slide = prs.slides.add_slide(blank); _add_title(slide, heading)
        if "Финанс" in heading:
            _v42_add_donut_with_note(slide, heading, column, note)
        else:
            _pro_add_chart_with_note(slide, heading, column, note)
        _add_footer(slide, slide_no); slide_no += 1

    # Cross comparison
    if faculty and funding:
        slide = prs.slides.add_slide(blank)
        _add_title(slide, "Финансирование внутри факультетов")
        if _add_stacked_chart(slide, "Доли источников финансирования", faculty, funding, analysis.get("rows", [])):
            _pro_add_takeaway(slide, "Сравнение показывает различия структуры финансирования между факультетами")
            _add_footer(slide, slide_no); slide_no += 1
        else:
            prs.slides._sldIdLst.remove(prs.slides._sldIdLst[-1])

    # Age structure
    age_column = next((c for c in analysis.get("date_columns", [])
                       if c.get("statistics", {}).get("age_statistics")), None)
    if age_column:
        age = age_column.get("statistics", {}).get("age_statistics", {})
        groups = age.get("groups", [])
        data = ChartData(); data.categories = [str(x.get("value")) for x in groups]
        data.add_series("Обучающиеся", [float(x.get("count", 0)) for x in groups])
        slide = prs.slides.add_slide(blank); _add_title(slide, "Возрастная структура")
        chart = slide.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED, Inches(.8), Inches(1.45),
            Inches(8.2), Inches(4.9), data,
        ).chart
        chart.has_legend = False; chart.category_axis.reverse_order = True
        chart.plots[0].series[0].format.fill.solid(); chart.plots[0].series[0].format.fill.fore_color.rgb = TEAL
        chart.plots[0].has_data_labels = True
        note = slide.shapes.add_textbox(Inches(9.4), Inches(1.8), Inches(3.0), Inches(3.5))
        run = note.text_frame.paragraphs[0].add_run()
        run.text = f"Средний возраст\n{age.get('mean')} года\n\nДиапазон\n{age.get('min')}–{age.get('max')} лет"
        _set_run(run, 20, NAVY, True)
        _add_footer(slide, slide_no); slide_no += 1

    # Conclusions
    slide = prs.slides.add_slide(blank); _add_title(slide, "Доказательные выводы")
    _add_bullets(slide, findings, Inches(.8), Inches(1.35), Inches(11.7), Inches(5.4), 18)
    _add_footer(slide, slide_no); slide_no += 1

    recommendations = [
        _safe(item, 320) for item in (ai_analysis or {}).get("recommendations", []) or []
        if len(_safe(item, 320)) >= 25
    ] or [
        "Ежемесячно отслеживать структуру финансирования по факультетам и изменение долей.",
        "Учитывать крупнейшие возрастные группы и формы обучения при планировании нагрузки.",
        "Сопоставлять новый отчёт с предыдущим периодом и фиксировать значимые изменения.",
    ]
    slide = prs.slides.add_slide(blank); _add_title(slide, "План действий")
    _add_bullets(slide, recommendations[:5], Inches(.8), Inches(1.35), Inches(11.7), Inches(5.3), 19)
    _pro_add_takeaway(slide, "Ответственный уровень: деканат и руководители учебных подразделений")
    _add_footer(slide, slide_no)

    prs.save(output_path)
    if not output_path.is_file() or output_path.stat().st_size < 1000:
        raise RuntimeError("PowerPoint не был создан или оказался пустым.")
    return output_path


# Public builder: the evidence-first presentation replaces legacy layouts.
build_analytics_pptx = build_analytics_pptx_v50


# ---------------------------------------------------------------------------
# INFOGRAPHIC PRESENTATION 5.1

YELLOW = RGBColor(242, 194, 48)
LIGHT_BG = RGBColor(247, 249, 252)
V51_COLORS = [TEAL, NAVY, RED, YELLOW, RGBColor(91, 143, 249), RGBColor(138, 112, 201)]


def _v51_header(slide, title: str, takeaway: str, number: int) -> None:
    _v50_text(slide, title, .68, .34, 12, .5, 24, NAVY, True)
    _v50_text(slide, takeaway, .7, .9, 11.9, .62, 13, MUTED)
    _add_footer(slide, number)


def _v51_panel(slide, x, y, w, h, title: str = "", fill=LIGHT_BG):
    shape = slide.shapes.add_shape(5, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = RGBColor(222, 228, 235)
    if title:
        _v50_text(slide, title, x+.22, y+.16, w-.44, .35, 12, NAVY, True)
    return shape


def _v51_kpi(slide, x, y, w, value: str, label: str, color) -> None:
    _v51_panel(slide,x,y,w,1.0,"",RGBColor(250,251,253))
    _v50_text(slide,value,x+.18,y+.17,w-.36,.35,21,color,True)
    _v50_text(slide,label,x+.18,y+.60,w-.36,.24,9,MUTED)


def _v51_bar(slide, column, x, y, w, h, limit=8) -> None:
    top=[v for v in _pro_top_values(column,limit)
         if str(v.get("value","")).strip() not in ("", "None")
         and float(v.get("count",0) or 0) > 0]
    if not top:
        _v50_text(slide,"Нет категорий для построения диаграммы",x+.2,y+h/2-.2,w-.4,.4,12,MUTED)
        return
    data=ChartData(); data.categories=[_safe(v.get("value"),42) for v in top]
    data.add_series("Количество",[float(v.get("count",0) or 0) for v in top])
    chart=slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED,Inches(x),Inches(y),Inches(w),Inches(h),data).chart
    chart.has_legend=False; chart.category_axis.reverse_order=True; chart.value_axis.has_major_gridlines=True
    chart.value_axis.major_gridlines.format.line.color.rgb=RGBColor(230,234,239)
    chart.plots[0].series[0].format.fill.solid(); chart.plots[0].series[0].format.fill.fore_color.rgb=TEAL
    for i,p in enumerate(chart.plots[0].series[0].points):
        p.format.fill.solid(); p.format.fill.fore_color.rgb=V51_COLORS[i%4]
    chart.plots[0].has_data_labels=True; chart.plots[0].data_labels.font.size=Pt(9)


def _v51_donut(slide, column, x, y, w, h, limit=6) -> None:
    top=[v for v in _pro_top_values(column,limit)
         if str(v.get("value","")).strip() not in ("", "None")
         and float(v.get("count",0) or 0) > 0]
    if not top:
        _v50_text(slide,"Нет категорий для круговой диаграммы",x+.2,y+h/2-.2,w-.4,.4,12,MUTED)
        return
    data=ChartData(); data.categories=[_safe(v.get("value"),34) for v in top]
    data.add_series("Доля",[float(v.get("count",0) or 0) for v in top])
    chart=slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT,Inches(x),Inches(y),Inches(w),Inches(h),data).chart
    chart.has_legend=True; chart.legend.position=XL_LEGEND_POSITION.BOTTOM; chart.legend.font.size=Pt(8)
    chart.plots[0].hole_size=58
    for i,p in enumerate(chart.plots[0].series[0].points):
        p.format.fill.solid(); p.format.fill.fore_color.rgb=V51_COLORS[i%len(V51_COLORS)]


def _v51_note(slide,x,y,w,h,kicker:str,headline:str,body:str,accent=TEAL) -> None:
    _v51_panel(slide,x,y,w,h,"",WHITE)
    bar=slide.shapes.add_shape(1,Inches(x),Inches(y),Inches(.07),Inches(h))
    bar.fill.solid(); bar.fill.fore_color.rgb=accent; bar.line.fill.background()
    _v50_text(slide,kicker.upper(),x+.22,y+.16,w-.42,.25,9,accent,True)
    _v50_text(slide,headline,x+.22,y+.49,w-.42,.48,15,NAVY,True)
    _v50_text(slide,body,x+.22,y+1.02,w-.42,h-1.14,11,TEXT)


def _v51_top_share(column,total,count=1):
    return sum(float(v.get("count",0) or 0) for v in _pro_top_values(column,count))*100/total if total else 0


def build_analytics_pptx_v51(
    matrix:list[list],title:str,output_dir:str|Path|None=None,description:str="",
    ai_analysis:dict|None=None,report_profile:str="Автоматически",audience:str="Руководство",
) -> Path:
    """Editable PowerPoint matching the 5.1 infographic PDF story for story."""
    analysis=analyze_matrix(matrix); total=int(analysis.get("row_count",0) or 0)
    if total <= 0:
        raise ValueError("В выбранном листе нет строк данных для аналитического отчёта.")
    faculty=_pro_col(analysis,"факультет","школа"); funding=_pro_col(analysis,"финанс")
    study=_pro_col(analysis,"форма обучения"); gender=_pro_col(analysis,"пол")
    citizenship=_pro_col(analysis,"граждан"); language=_pro_col(analysis,"язык")
    age=next((c.get("statistics",{}).get("age_statistics") for c in analysis.get("date_columns",[]) if c.get("statistics",{}).get("age_statistics")),{})
    ft=_pro_top_values(faculty,9); fn=_pro_top_values(funding,10); st=_pro_top_values(study,8); ct=_pro_top_values(citizenship,6)
    own=sum(float(v.get("count",0) or 0) for v in fn if "собствен" in str(v.get("value","")).casefold())
    grants=sum(float(v.get("count",0) or 0) for v in fn if "грант" in str(v.get("value","")).casefold())
    out=Path(output_dir).expanduser() if output_dir else Path.home()/"Documents"/"BahonIQ Reports";out.mkdir(parents=True,exist_ok=True)
    output_path=_unique_path(out/(_filename(title)+".pptx"));prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5);blank=prs.slide_layouts[6]

    # 1 Cover
    slide=prs.slides.add_slide(blank); bg=slide.background.fill;bg.solid();bg.fore_color.rgb=NAVY
    for i,c in enumerate((TEAL,YELLOW,RED)):
        s=slide.shapes.add_shape(1,Inches(.75+i*.13),Inches(1.0),Inches(.09),Inches(5.3));s.fill.solid();s.fill.fore_color.rgb=c;s.line.fill.background()
    _v50_text(slide,title,1.35,1.45,10.8,1.45,36,WHITE,True)
    _v50_text(slide,"Контингент, финансирование, образовательный профиль и управленческие решения",1.37,3.1,10.4,.8,18,RGBColor(220,231,250))
    _v50_text(slide,f"{report_profile} • {audience}",1.37,6.25,10.2,.35,11,RGBColor(175,201,255))

    # 2 Executive dashboard
    slide=prs.slides.add_slide(blank); _v51_header(slide,"Управленческая панель","Основной масштаб формируют Школа Медицины, собственное финансирование и шестилетний бакалавриат.",2)
    _v51_kpi(slide,.7,1.55,2.6,f"{total:,}".replace(","," "),"обучающихся",TEAL)
    _v51_kpi(slide,3.45,1.55,2.6,f"{_v51_top_share(faculty,total):.1f}%","Школа Медицины",NAVY)
    _v51_kpi(slide,6.2,1.55,2.6,f"{own*100/total:.1f}%","собственные средства",RED)
    _v51_kpi(slide,8.95,1.55,2.6,f"{age.get('mean','—')}","средний возраст",YELLOW)
    _v51_panel(slide,.7,2.75,7.55,3.95,"Крупнейшие факультеты");_v51_bar(slide,faculty,.92,3.2,7.05,3.15,6)
    _v51_panel(slide,8.5,2.75,4.1,3.95,"Финансирование");_v51_donut(slide,funding,8.72,3.18,3.65,3.15,5)

    # 3 Faculty
    top3=_v51_top_share(faculty,total,3)
    slide=prs.slides.add_slide(blank);_v51_header(slide,"Факультеты и масштаб нагрузки",f"Школа Медицины — {_v51_top_share(faculty,total):.1f}% контингента; три крупнейших подразделения — {top3:.1f}%.",3)
    _v51_panel(slide,.7,1.55,8.1,5.35,"Рейтинг факультетов");_v51_bar(slide,faculty,.95,2.0,7.6,4.55,8)
    _v51_note(slide,9.05,1.55,3.55,1.45,"Факт",f"Топ-3 = {top3:.1f}%","Контингент заметно сосредоточен в крупнейших подразделениях.",TEAL)
    _v51_note(slide,9.05,3.18,3.55,1.65,"Интерпретация","Нагрузка неоднородна","Единый норматив ресурсов для всех факультетов будет искажать реальную потребность.",NAVY)
    _v51_note(slide,9.05,5.0,3.55,1.9,"Действие","Проверить мощность","Сопоставить число студентов с группами, преподавателями и учебными площадями по трём лидерам.",YELLOW)

    # 4 Funding
    slide=prs.slides.add_slide(blank);_v51_header(slide,"Финансирование контингента",f"Собственные средства — {own*100/total:.1f}%, грантовые источники — {grants*100/total:.1f}%.",4)
    _v51_panel(slide,.7,1.55,5.2,5.35,"Структура источников");_v51_donut(slide,funding,.95,2.0,4.7,4.45,6)
    _v51_note(slide,6.15,1.55,6.45,1.45,"Баланс",f"Разрыв {abs(own-grants)*100/total:.1f} п.п.","Платный контингент превышает грантовый.",RED)
    _v51_note(slide,6.15,3.18,3.1,2.2,"Интерпретация","Финансовая концентрация","Структура влияет на устойчивость набора и объём сопровождения договоров и оплат.",NAVY)
    _v51_note(slide,9.5,3.18,3.1,2.2,"Действие","Контроль по факультетам","Ежемесячно отмечать отклонение доли собственных средств более чем на 3 п.п.",YELLOW)
    _v51_note(slide,6.15,5.65,6.45,1.25,"Метрика контроля","Доля собственных средств, п.п.","",TEAL)

    # 5 Study profile
    slide=prs.slides.add_slide(blank);_v51_header(slide,"Формы и языки обучения",f"Шестилетний бакалавриат — {_v51_top_share(study,total):.1f}%; казахский язык — {_v51_top_share(language,total):.1f}%.",5)
    _v51_panel(slide,.7,1.55,7.5,5.35,"Формы обучения");_v51_bar(slide,study,.95,2.0,7.0,4.55,8)
    _v51_panel(slide,8.45,1.55,4.15,3.15,"Языковой профиль");_v51_donut(slide,language,8.68,1.95,3.7,2.55,4)
    _v51_note(slide,8.45,4.92,4.15,1.98,"Действие","Синхронизировать ресурсы","Проверить клинические базы, преподавателей и материалы по трём языкам для крупнейших программ.",YELLOW)

    # 6 Demographics
    slide=prs.slides.add_slide(blank);foreign=100-_v51_top_share(citizenship,total)
    _v51_header(slide,"Демографический и международный профиль",f"Средний возраст — {age.get('mean','—')} года; женщины — {_v51_top_share(gender,total):.1f}%; иностранные граждане — около {foreign:.1f}%.",6)
    _v51_panel(slide,.7,1.55,3.8,3.35,"Пол");_v51_donut(slide,gender,.93,1.96,3.35,2.7,3)
    _v51_panel(slide,4.75,1.55,3.8,3.35,"Возраст");
    groups=age.get("groups",[]) or []
    if groups:
        temp={"statistics":{"top_values":[{"value":x.get("value"),"count":x.get("count",0)} for x in groups]}}
        _v51_bar(slide,temp,4.98,2.0,3.35,2.65,7)
    _v51_panel(slide,8.8,1.55,3.8,3.35,"Гражданство");_v51_donut(slide,citizenship,9.03,1.96,3.35,2.7,6)
    _v51_note(slide,.7,5.18,5.85,1.72,"Возраст","Сервисная нагрузка","Возрастной профиль определяет спрос на расписание, практику и цифровые сервисы.",TEAL)
    _v51_note(slide,6.8,5.18,5.8,1.72,"Иностранные студенты","Отдельное сопровождение","Проверить языковую адаптацию и сроки обработки документов крупнейших иностранных групп.",RED)

    # 7 Decisions
    slide=prs.slides.add_slide(blank);_v51_header(slide,"Решения и контроль","Каждое действие связано с конкретным фактом и измеримым показателем.",7)
    cards=[
      ("Нагрузка факультетов",f"Топ-3 = {top3:.1f}%","Сопоставить контингент с преподавателями, группами и площадями.","Нагрузка на преподавателя; наполняемость"),
      ("Финансирование",f"Собственные = {own*100/total:.1f}%","Контролировать структуру финансирования внутри факультетов.","Изменение доли, п.п.; просроченные оплаты"),
      ("Образовательный профиль",f"6-летняя программа = {_v51_top_share(study,total):.1f}%","Проверить клинические базы и языковое обеспечение.","Обеспеченность дисциплин и баз"),
      ("Международный контингент",f"Иностранные ≈ {foreign:.1f}%","Проверить адаптацию и сопровождение документов.","Срок ответа; незакрытые обращения"),
    ]
    positions=[(.7,1.55),(6.75,1.55),(.7,4.2),(6.75,4.2)]
    for (name,fact,action,metric),(x,y),accent in zip(cards,positions,V51_COLORS[:4]):
        _v51_note(slide,x,y,5.85,2.3,name,fact,f"Действие: {action}\nКонтроль: {metric}",accent)

    prs.save(output_path)
    if not output_path.is_file() or output_path.stat().st_size<1000: raise RuntimeError("PowerPoint не был создан или оказался пустым.")
    return output_path


build_analytics_pptx = build_analytics_pptx_v51


# ---------------------------------------------------------------------------
# ADAPTIVE INFOGRAPHIC PRESENTATION 5.2

def _v52_dimensions(analysis:dict)->list[dict]:
    result=[]
    for column in analysis.get("categorical_columns",[]):
        stats=column.get("statistics",{}) or {};unique=int(stats.get("unique_count",0) or 0)
        if column.get("reportable") and 2<=unique<=100 and _pro_top_values(column,1): result.append(column)
    result.sort(key=lambda c:(int(c.get("statistics",{}).get("unique_count",0) or 0)>20,-float(c.get("statistics",{}).get("top_value_percent",0) or 0)))
    return result


def _v52_fact(column:dict,total:int):
    top=_pro_top_values(column,3)
    if not top or not total:return "Недостаточно данных для вывода",0.0,0.0
    first=top[0];count=int(first.get("count",0) or 0);share=count*100/total;top3=sum(int(x.get("count",0) or 0) for x in top[:3])*100/total
    text=f"«{_safe(first.get('value'),110)}» — {count:,} записей ({share:.1f}%)".replace(","," ")
    if len(top)>1:text+=f"; разница со второй категорией — {count-int(top[1].get('count',0) or 0):,}".replace(","," ")
    return text,share,top3


def _v52_interpretation(column:dict,share:float,top3:float):
    name=_safe(column.get("name"),80)
    if share>=70:return "Высокая концентрация",f"Одна категория почти полностью определяет показатель «{name}»."
    if share>=45:return "Выраженный лидер",f"В показателе «{name}» есть доминирующая категория, но остальные группы сохраняют заметную долю."
    if top3>=75:return "Три основные группы",f"Большая часть объёма по показателю «{name}» сосредоточена в трёх категориях."
    return "Распределённая структура",f"Показатель «{name}» распределён между несколькими категориями."


def _v52_action(column:dict,share:float):
    name=_safe(column.get("name"),80);leader=_safe((_pro_top_values(column,1) or [{}])[0].get("value"),100)
    if share>=45:return "Проверить лидера",f"Сопоставить категорию «{leader}» с планом, ресурсами и предыдущим периодом. Контроль: изменение количества и доли."
    return "Сравнить группы",f"Проверить причины различий между крупнейшими категориями по показателю «{name}»."


def _v53_story(
    ai_analysis: dict | None, column_name: str,
    column: dict | None = None, total: int = 0,
) -> dict:
    needle = _safe(column_name, 100).casefold().strip()
    for item in (ai_analysis or {}).get("stories", []) or []:
        if not isinstance(item, dict):
            continue
        topic = _safe(item.get("topic"), 100).casefold().strip()
        if needle == topic or needle in topic or topic in needle:
            if column is not None and total:
                top = _pro_top_values(column, 1)
                if not top:
                    continue
                leader = _safe(top[0].get("value"), 180).casefold()
                count = int(top[0].get("count", 0) or 0)
                share = count * 100 / total
                proof = " ".join(
                    _safe(item.get(key), 700)
                    for key in ("headline", "evidence")
                ).casefold().replace("\u00a0", " ")
                compact_proof = re.sub(r"\s+", "", proof)
                count_matches = str(count) in compact_proof
                share_matches = any(
                    token in proof
                    for token in (f"{share:.1f}%", f"{share:.1f} %", f"{share:.2f}%", f"{share:.2f} %")
                )
                if not leader or leader not in proof or not (count_matches or share_matches):
                    continue
            return item
    return {}


def build_analytics_pptx_v52(
    matrix:list[list],title:str,output_dir:str|Path|None=None,description:str="",
    ai_analysis:dict|None=None,report_profile:str="Автоматически",audience:str="Руководство",
)->Path:
    """Domain-neutral deck generated only from columns in the current workbook."""
    analysis=analyze_matrix(matrix);total=int(analysis.get("row_count",0) or 0)
    if total<=0:raise ValueError("В выбранном листе нет строк данных для отчёта.")
    dimensions=_v52_dimensions(analysis)
    out=Path(output_dir).expanduser() if output_dir else Path.home()/"Documents"/"BahonIQ Reports";out.mkdir(parents=True,exist_ok=True)
    display_title=_safe((ai_analysis or {}).get("report_title"),180) or title
    display_subtitle=_safe((ai_analysis or {}).get("report_subtitle"),300) or "Структура, сравнения и доказательные выводы"
    output_path=_unique_path(out/(_filename(display_title)+".pptx"));prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5);blank=prs.slide_layouts[6]

    # Cover
    slide=prs.slides.add_slide(blank);bg=slide.background.fill;bg.solid();bg.fore_color.rgb=NAVY
    for i,c in enumerate((TEAL,YELLOW,RED)):
        s=slide.shapes.add_shape(1,Inches(.75+i*.13),Inches(1),Inches(.09),Inches(5.3));s.fill.solid();s.fill.fore_color.rgb=c;s.line.fill.background()
    _v50_text(slide,display_title,1.35,1.45,10.8,1.45,36,WHITE,True)
    _v50_text(slide,display_subtitle,1.37,3.1,10.4,.8,18,RGBColor(220,231,250))
    _v50_text(slide,f"{report_profile} • {audience}",1.37,6.25,10.2,.35,11,RGBColor(175,201,255))

    # Dashboard
    slide=prs.slides.add_slide(blank);_v51_header(slide,"Обзор набора данных",f"Проанализировано {total:,} строк, {len(analysis.get('headers',[]))} столбцов и {len(dimensions)} категориальных разрезов.".replace(","," "),2)
    numeric=len([c for c in analysis.get("numeric_columns",[]) if c.get("reportable")])
    _v51_kpi(slide,.7,1.55,2.6,f"{total:,}".replace(","," "),"строк данных",TEAL)
    _v51_kpi(slide,3.45,1.55,2.6,str(len(analysis.get("headers",[]))),"столбцов",NAVY)
    _v51_kpi(slide,6.2,1.55,2.6,str(len(dimensions)),"категориальных разрезов",RED)
    _v51_kpi(slide,8.95,1.55,2.6,str(numeric),"числовых показателей",YELLOW)
    if dimensions:
        first=dimensions[0];_v51_panel(slide,.7,2.75,5.85,3.95,_safe(first.get("name"),70))
        (_v51_donut if len(_pro_top_values(first,7))<=5 else _v51_bar)(slide,first,.92,3.18,5.4,3.15,7)
    else:
        _v51_note(slide,.7,2.75,5.85,3.0,"Структура данных","Категориальные разрезы не найдены","Для распределений нужны столбцы с повторяющимися категориями.",YELLOW)
    if len(dimensions)>1:
        second=dimensions[1];_v51_panel(slide,6.75,2.75,5.85,3.95,_safe(second.get("name"),70))
        (_v51_donut if len(_pro_top_values(second,7))<=5 else _v51_bar)(slide,second,6.97,3.18,5.4,3.15,7)

    slide_no=3;decisions=[]
    for column in dimensions[:8]:
        fact,share,top3=_v52_fact(column,total);story=_v53_story(ai_analysis,_safe(column.get("name"),100),column,total)
        headline=_safe(story.get("headline"),150) or _safe(column.get("name"),100)
        evidence=_safe(story.get("evidence"),260) or fact
        interpretation=_safe(story.get("interpretation"),380)
        action=_safe(story.get("action"),320)
        slide=prs.slides.add_slide(blank);_v51_header(slide,headline,evidence,slide_no)
        _v51_panel(slide,.7,1.55,8.1,5.35,"Распределение")
        if len(_pro_top_values(column,10))<=5:_v51_donut(slide,column,.95,2.0,7.6,4.5,6)
        else:_v51_bar(slide,column,.95,2.0,7.6,4.5,9)
        _v51_note(slide,9.05,1.55,3.55,1.45,"Ключевой факт",f"{share:.1f}%",f"Доля крупнейшей категории по показателю «{_safe(column.get('name'),70)}».",TEAL)
        _v51_note(slide,9.05,3.18,3.55,1.65,"Интерпретация Qwen","Что означает результат",interpretation,NAVY)
        if action:_v51_note(slide,9.05,5.0,3.55,1.9,"Обоснованное действие","Следующий шаг",action,YELLOW)
        decisions.append((_safe(column.get("name"),70),f"{share:.1f}%",headline,interpretation));slide_no+=1

    slide=prs.slides.add_slide(blank);_v51_header(slide,"Итоги исследования",_safe((ai_analysis or {}).get("summary"),220),slide_no)
    if decisions:
        positions=[(.7,1.55),(6.75,1.55),(.7,4.2),(6.75,4.2)]
        for (name,share,action_title,action_body),(x,y),accent in zip(decisions[:4],positions,V51_COLORS[:4]):
            _v51_note(slide,x,y,5.85,2.3,name,share,f"{action_title}. {action_body}",accent)
    else:
        _v51_note(slide,.7,1.55,11.9,2.3,"Вывод","Недостаточно категориальных данных","Добавьте столбцы с повторяющимися категориями или выберите другой лист Excel.",YELLOW)
    _v50_text(slide,"Ограничение: один срез описывает текущую структуру, но не подтверждает рост, снижение или причины изменений.",.7,6.85,11.9,.3,9,MUTED)

    prs.save(output_path)
    if not output_path.is_file() or output_path.stat().st_size<1000:raise RuntimeError("PowerPoint не был создан или оказался пустым.")
    return output_path


build_analytics_pptx = build_analytics_pptx_v52
