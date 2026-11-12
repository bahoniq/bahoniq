# -*- coding: utf-8 -*-
"""Два формата одного отчёта. Таблицы и диаграммы используют общие факты."""
from __future__ import annotations

import re
import textwrap
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from .config import DEFAULT_OUTPUT_DIR
from .report_engine import fmt

NAVY = "183247"
TEAL = "087E8B"
MUTED = "586B7A"
LIGHT = "EDF3F6"
PALETTE = ["087E8B", "2563A6", "E2A03B", "7180A0", "58A59A", "A1B9C6", "C5D1D8"]


def _chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def report_pages(model, include_source_table=False):
    """Единый порядок и одинаковая пагинация содержания обоих форматов."""
    result = [{"kind": "cover", "title": model["title"], "section": "Аналитический отчёт",
               "body": [f"Период: {model['period']}", f"Источник: {model['source_name']}",
                        f"Лист: {model['sheet_name']}", f"Для: {model['audience']}"]}]
    intro = ["Цель: " + model["goal"], f"Объём: {model['row_count']} строк в анализе из {model['source_row_count']} исходных.",
             *["Задача: " + t for t in model["tasks"]]]
    filters = model["plan"].get("filters", [])
    if filters:
        intro.append("Условия отбора: " + "; ".join(f"{f['column']} {f['op']} {f['value']}" for f in filters))
    for i, part in enumerate(_text_chunks(intro, 1000)):
        result.append({"kind": "text", "title": "Введение и план исследования" + (f" ({i+1})" if i else ""),
                       "section": "Введение", "body": part})
    # Защита последнего уровня: основной отчёт остаётся компактным даже если
    # вызывающий код передал слишком много технических кандидатов.
    for page in model["pages"][:8]:
        data = page["table"]
        # Длинные подписи получают отдельные строки, не обрезаются.
        chunks, part, weight = [], [], 0
        for row in data[1:]:
            row_weight = max(1, max((len(str(v)) + 29)//30 for v in row))
            # До восьми коротких категорий помещаются на одной альбомной
            # странице вместе с диаграммой. Не делим один сюжет без нужды.
            if part and (weight + row_weight > 12 or len(part) >= 8):
                chunks.append(part)
                part, weight = [], 0
            part.append(row)
            weight += row_weight
        if part:
            chunks.append(part)
        for i, part in enumerate(chunks or [[]]):
            item = {**page, "kind": "analysis", "table": [data[0]] + part,
                    "title": page["title"] + (f" ({i+1}/{len(chunks)})" if len(chunks) > 1 else "")}
            chart = page.get("chart")
            if len(chunks) > 1 and chart and all(str(row[0]) in chart["labels"] for row in data[1:]):
                selected = [chart["labels"].index(str(row[0])) for row in part]
                item["chart"] = {**chart, "labels": [chart["labels"][j] for j in selected],
                                 "values": [chart["values"][j] for j in selected],
                                 "kind": "bar" if chart["kind"] == "donut" else chart["kind"]}
                item["note"] = page.get("note", "") + " Диаграмма соответствует строкам этой страницы."
            result.append(item)
    for i, part in enumerate(_text_chunks([f"{n+1}. {f['text']}" for n, f in enumerate(model["findings"])], 1050)):
        result.append({"kind": "text", "title": "Выводы" + (f" ({i+1})" if i else ""),
                       "section": "Выводы", "body": part})
    methodology = [*model["notes"],
                   "Выводы описывают загруженные наблюдения. Причины различий и прогноз требуют дополнительных данных.",
                   "Среднее — арифметическое по известным значениям. Показатели сохраняют числовой масштаб ячеек Excel.",
                   "Повторяющиеся строки учитываются как отдельные наблюдения. Уникальные объекты без выбранного ключа не подсчитываются."]
    for i, part in enumerate(_text_chunks(methodology, 1050)):
        result.append({"kind": "text", "title": "Основания и границы выводов" + (f" ({i+1})" if i else ""),
                       "section": "Выводы", "body": part})
    if include_source_table:
        # При большом числе столбцов сохраняем читаемость и весь образец.
        for col in range(0, len(model["headers"]), 4):
            for row in range(0, len(model["sample_rows"]), 8):
                result.append({"kind": "analysis", "title": f"Образец исходных данных: строки {row+1}–{min(row+8, len(model['sample_rows']))}",
                               "section": "Приложение", "lead": f"Столбцы {col+1}–{min(col+4, len(model['headers']))}",
                               "table": [model["headers"][col:col+4]] + [[fmt(v) if v is not None else "" for v in r[col:col+4]]
                                   for r in model["sample_rows"][row:row+8]], "chart": None,
                               "note": "До 40 строк выбранной выборки. Источник не изменён."})
    return result


def _text_chunks(items, budget):
    parts, part, size = [], [], 0
    for item in items:
        for segment in textwrap.wrap(str(item), width=budget, break_long_words=True, replace_whitespace=False) or [""]:
            if part and (size + len(segment) > budget or len(part) >= 8):
                parts.append(part)
                part, size = [], 0
            part.append(segment)
            size += len(segment)
    if part:
        parts.append(part)
    if len(parts) > 1 and len(parts[-1]) == 1 and len(parts[-2]) >= 4:
        parts[-1].insert(0, parts[-2].pop())
    return parts


def _path(model, output_dir, extension):
    folder = Path(output_dir or DEFAULT_OUTPUT_DIR).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", model["title"]).strip(" .")[:90] or "Report"
    return folder / f"{name}_{datetime.now():%Y%m%d_%H%M%S_%f}.{extension}"


def _chart_image(chart):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import font_manager
    from .pdf_builder import _register_fonts, FONT_REGULAR
    from reportlab.pdfbase import pdfmetrics
    _register_fonts()
    font_path = pdfmetrics.getFont(FONT_REGULAR).face.filename
    if isinstance(font_path, bytes):
        font_path = font_path.decode()
    prop = font_manager.FontProperties(fname=font_path, size=10)
    fig = Figure(figsize=(7.2, 4.4), dpi=160, facecolor="white")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    # Полные названия остаются в таблице. Подписи диаграммы должны помещаться.
    labels = [s if len(s) <= 65 else s[:62] + "…" for s in chart["labels"]]
    values = chart["values"]
    if not values or all(v is None for v in values):
        ax.text(.5, .5, "Нет числовых значений", ha="center", fontproperties=prop)
        ax.axis("off")
    elif chart["kind"] == "donut":
        ax.pie(values, labels=None, startangle=90, colors=["#"+c for c in PALETTE],
               wedgeprops={"width": .42, "edgecolor": "white"}, autopct=lambda p: f"{p:.1f}%",
               textprops={"fontproperties": prop})
        ax.legend(["\n".join(textwrap.wrap(x, 28)) for x in labels], loc="lower center", bbox_to_anchor=(.5, -.25),
                  ncol=2 if len(labels) <= 4 else 1, prop=prop, frameon=False)
    elif chart["kind"] == "bar":
        ax.barh(range(len(labels)), [float("nan") if v is None else v for v in values], color="#"+TEAL, height=.6)
        ax.set_yticks(range(len(labels)), ["\n".join(textwrap.wrap(x, 30)) for x in labels], fontproperties=prop)
        ax.invert_yaxis()
        ax.set_xlabel(chart["label"], fontproperties=prop)
        ax.grid(axis="x", color="#dfe6eb", linewidth=.5)
        ax.set_axisbelow(True)
    else:
        numeric = [float("nan") if v is None else v for v in values]
        if chart["kind"] == "line":
            ax.plot(range(len(labels)), numeric, color="#"+TEAL, marker="o", linewidth=2)
        else:
            ax.bar(range(len(labels)), numeric, color="#"+TEAL, width=.65)
        ax.set_xticks(range(len(labels)), ["\n".join(textwrap.wrap(x, 15)) for x in labels], rotation=35 if len(labels)>4 else 0,
                      ha="right" if len(labels)>4 else "center", fontproperties=prop)
        ax.set_ylabel(chart["label"], fontproperties=prop)
        ax.grid(axis="y", color="#dfe6eb", linewidth=.5)
        ax.set_axisbelow(True)
    if chart["kind"] != "donut":
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for tick in ax.get_xticklabels()+ax.get_yticklabels():
            tick.set_fontproperties(prop)
    fig.tight_layout(pad=1.2)
    output = BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight", dpi=160)
    output.seek(0)
    return output


def render_pdf(model, output_dir=None, orientation="auto", include_source_table=False):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib.utils import ImageReader
    from .pdf_builder import _register_fonts, FONT_REGULAR, FONT_BOLD
    _register_fonts()
    size = A4 if orientation == "portrait" else landscape(A4)
    w, h = size
    margin = 38
    path = _path(model, output_dir, "pdf")
    pdf = canvas.Canvas(str(path), pagesize=size)
    pdf.setTitle(model["title"])
    pages = report_pages(model, include_source_table)
    def paragraph(text, x, top, width, maxheight, font=12, color=NAVY, bold=False):
        for fs in range(font, 8, -1):
            style = ParagraphStyle("p", fontName=FONT_BOLD if bold else FONT_REGULAR,
                                   fontSize=fs, leading=fs*1.4, textColor=HexColor("#"+color), splitLongWords=True)
            p = Paragraph(escape(str(text)).replace("\n", "<br/>"), style)
            pw, ph = p.wrap(width, maxheight)
            if ph <= maxheight:
                p.drawOn(pdf, x, top-ph)
                return ph
        raise ValueError("Слишком длинный текст для страницы PDF. Сократите название или описание.")
    for i, page in enumerate(pages):
        pdf.setFillColor(white)
        pdf.rect(0, 0, w, h, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#"+TEAL))
        pdf.rect(margin, h-31, 40, 3, fill=1, stroke=0)
        paragraph(page["section"].upper(), margin, h-44, w-2*margin, 25, 10, MUTED)
        if page["kind"] == "cover":
            paragraph(page["title"], margin, h*.73, w-2*margin, h*.27, 36, NAVY, True)
            y = h*.37
            for line in page["body"]:
                y -= paragraph(line, margin, y, w-2*margin, 65, 13) + 12
        else:
            th = paragraph(page["title"], margin, h-73, w-2*margin, 85, 25, NAVY, True)
            y = h-86-th
            if page["kind"] == "text":
                for line in page["body"]:
                    used = paragraph(line, margin, y, w-2*margin, y-65, 15)
                    y -= used+17
            else:
                used = paragraph(page.get("lead", ""), margin, y, w-2*margin, 85, 12)
                y -= used+16
                chart = page.get("chart")
                chart_width = (w-2*margin)*.56 if chart and w>h else w-2*margin
                table_width = (w-2*margin)*.41 if chart and w>h else w-2*margin
                table_x = w-margin-table_width
                if chart:
                    im = ImageReader(_chart_image(chart))
                    iw, ih = im.getSize()
                    ih = min(260 if w>h else 210, chart_width*ih/iw)
                    pdf.drawImage(im, margin, y-ih, width=chart_width, height=ih, preserveAspectRatio=True, anchor="n")
                    if h>w:
                        y -= ih+18
                cell_style = ParagraphStyle("cell", fontName=FONT_REGULAR, fontSize=10, leading=13, textColor=HexColor("#"+NAVY))
                head_style = ParagraphStyle("head", parent=cell_style, fontName=FONT_BOLD)
                data = [[Paragraph(escape(str(v)), head_style if ri == 0 else cell_style) for v in row] for ri, row in enumerate(page["table"])]
                ncol = len(data[0])
                widths = ([table_width*.5]+[table_width*.5/(ncol-1)]*(ncol-1)) if ncol>1 else [table_width]
                table = Table(data, colWidths=widths)
                table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), HexColor("#"+LIGHT)),
                                           ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 7),
                                           ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 7),
                                           ("BOTTOMPADDING", (0,0), (-1,-1), 7),
                                           ("LINEBELOW", (0,0), (-1,-1), .4, HexColor("#dfe6eb"))]))
                tw, th = table.wrap(table_width, h)
                if th > y-105:
                    raise ValueError("Таблица не помещается в PDF. Выберите альбомную ориентацию или сократите длинные значения категорий.")
                table.drawOn(pdf, table_x, y-th)
                paragraph(page.get("note", ""), margin, 87, w-2*margin, 49, 10, MUTED)
        pdf.setStrokeColor(HexColor("#dfe6eb"))
        pdf.line(margin, 34, w-margin, 34)
        paragraph(f"{model['source_name']} / {model['sheet_name']}", margin, 25, w-2*margin-55, 14, 9, MUTED)
        pdf.setFillColor(HexColor("#"+MUTED))
        pdf.setFont(FONT_REGULAR, 9)
        pdf.drawRightString(w-margin, 15, f"{i+1} / {len(pages)}")
        pdf.showPage()
    pdf.save()
    return path


def render_pptx(model, output_dir=None, include_source_table=False):
    # Maintenance of the existing desktop app: keep its installed python-pptx dependency.
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = model["title"]
    pages = report_pages(model, include_source_table)
    def text(slide, content, x, y, width, height, size=18, bold=False, color=NAVY):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = 0
        tf.margin_top = tf.margin_bottom = 0
        for i, line in enumerate(str(content).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.name, p.font.size, p.font.bold = "Arial", Pt(size), bold
            p.font.color.rgb = RGBColor.from_string(color)
            p.space_after = Pt(8)
        return box
    for number, page in enumerate(pages, 1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        text(slide, page["section"].upper(), .55, .25, 12.2, .3, 11, color=TEAL)
        if page["kind"] == "cover":
            text(slide, page["title"], .55, 1.5, 12.1, 2.5, 38 if len(page["title"])<100 else 30, True)
            text(slide, "\n".join(page["body"]), .55, 4.2, 12.1, 2.3, 18)
        else:
            text(slide, page["title"], .55, .7, 12.2, .85, 28 if len(page["title"])<100 else 23, True)
            if page["kind"] == "text":
                text(slide, "\n\n".join(page["body"]), .55, 1.85, 12.2, 4.9, 18 if sum(map(len,page["body"]))<900 else 17)
            else:
                text(slide, page.get("lead", ""), .55, 1.7, 12.2, 1, 16)
                chart = page.get("chart")
                if chart and any(v is not None for v in chart["values"]):
                    data = CategoryChartData()
                    data.categories = [s if len(s)<=65 else s[:62]+"…" for s in chart["labels"]]
                    data.add_series(chart["label"], chart["values"])
                    kind = {"bar": XL_CHART_TYPE.BAR_CLUSTERED, "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
                            "line": XL_CHART_TYPE.LINE_MARKERS, "donut": XL_CHART_TYPE.DOUGHNUT}[chart["kind"]]
                    obj = slide.shapes.add_chart(kind, Inches(.55), Inches(2.85), Inches(6.7), Inches(3.6), data).chart
                    obj.font.name, obj.font.size = "Arial", Pt(12)
                    # Некоторые версии python-pptx генерируют отрицательные ID осей.
                    # ECMA-376 ожидает unsignedInt, ссылки crossAx меняются вместе.
                    for axis in obj._chartSpace.xpath(".//c:axId | .//c:crossAx"):
                        axis.set("val", str(abs(int(axis.get("val")))))
                    obj.has_legend = chart["kind"] == "donut"
                    if obj.has_legend:
                        obj.legend.position = XL_LEGEND_POSITION.BOTTOM
                    for series in obj.series:
                        series.format.fill.solid()
                        series.format.fill.fore_color.rgb = RGBColor.from_string(TEAL)
                    if chart["kind"] == "donut":
                        for i, point in enumerate(obj.series[0].points):
                            point.format.fill.solid()
                            point.format.fill.fore_color.rgb = RGBColor.from_string(PALETTE[i%len(PALETTE)])
                    if chart["kind"] == "bar":
                        obj.category_axis.reverse_order = True
                    if chart["kind"] in {"bar", "column"}:
                        known = [v for v in chart["values"] if v is not None]
                        if known and min(known) >= 0:
                            obj.value_axis.minimum_scale = 0
                            if max(known) == 0:
                                obj.value_axis.maximum_scale = 1
                        elif known and max(known) <= 0:
                            obj.value_axis.maximum_scale = 0
                left, width = (7.55, 5.2) if chart else (.55, 12.2)
                rows = page["table"]
                table = slide.shapes.add_table(len(rows), len(rows[0]), Inches(left), Inches(2.85), Inches(width), Inches(3.5)).table
                if len(rows[0]) > 1:
                    table.columns[0].width = Inches(width*.5)
                    for c in list(table.columns)[1:]:
                        c.width = Inches(width*.5/(len(rows[0])-1))
                for ri, row in enumerate(rows):
                    lines = max(max(1, (len(str(v))+27)//28) for v in row)
                    table.rows[ri].height = Inches(max(.35, lines*.21+.14))
                    for ci, value in enumerate(row):
                        cell = table.cell(ri, ci)
                        cell.text = str(value)
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor.from_string(LIGHT if ri==0 else "FFFFFF")
                        cell.margin_left = cell.margin_right = Inches(.08)
                        cell.margin_top = cell.margin_bottom = Inches(.04)
                        for p in cell.text_frame.paragraphs:
                            p.font.name, p.font.size, p.font.bold = "Arial", Pt(14 if chart else 16), ri==0
                            p.font.color.rgb = RGBColor.from_string(NAVY)
                text(slide, page.get("note", ""), .55, 6.55, 12.2, .48, 11, color=MUTED)
        text(slide, f"{model['source_name']} / {model['sheet_name']}", .55, 7.12, 11.5, .2, 9, color=MUTED)
        text(slide, f"{number}/{len(pages)}", 12.05, 7.12, .7, .2, 9, color=MUTED)
        slide.notes_slide.notes_text_frame.text = "Источник: " + model["source_name"] + ", лист " + model["sheet_name"] + ".\n" + "\n".join(page.get("body", [])) + "\n" + page.get("lead", "") + "\n" + page.get("note", "")
    path = _path(model, output_dir, "pptx")
    prs.save(path)
    return path
