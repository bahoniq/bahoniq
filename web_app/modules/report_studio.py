# -*- coding: utf-8 -*-
"""ANALYTICS AI — пакетное создание PDF из Excel (.xlsx/.xlsm)."""
from __future__ import annotations

import os
import re
import sys
import queue
import threading
import subprocess
import tkinter as tk
from pathlib import Path
from datetime import datetime, date
from xml.sax.saxutils import escape
from tkinter import ttk, filedialog, messagebox

from openpyxl import load_workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

try:
    from services.settings_service import get_theme
except ImportError:
    try:
        from settings_service import get_theme
    except ImportError:
        get_theme = None

APP_TITLE = "ANALYTICS AI"
SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}
GREEN, DARK_GREEN, RED, WHITE = "#008C55", "#07533D", "#D8203B", "#FFFFFF"


def _theme_colors():
    defaults = {
        "bg": "#EDF2F5", "card": "#FFFFFF", "text": "#173044",
        "muted": "#667B8B", "button": GREEN, "border": "#D4E0E8",
        "entry": "#FFFFFF",
    }
    try:
        source = get_theme() if callable(get_theme) else {}
        if not isinstance(source, dict):
            return defaults
        aliases = {
            "bg": ("background", "window_bg"),
            "card": ("panel", "frame", "surface"),
            "text": ("fg", "foreground"),
            "muted": ("secondary_text", "subtext"),
            "button": ("accent", "primary"),
            "border": ("outline",),
            "entry": ("input_bg", "field"),
        }
        result = defaults.copy()
        for key in defaults:
            if isinstance(source.get(key), str) and source[key].strip():
                result[key] = source[key]
            else:
                for alias in aliases[key]:
                    if isinstance(source.get(alias), str) and source[alias]:
                        result[key] = source[alias]
                        break
        return result
    except Exception:
        return defaults


def _open_workbook(path):
    return load_workbook(
        filename=path, read_only=True, data_only=True, keep_links=False
    )


def _safe_filename(value, max_length=100):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value).strip())
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "Отчёт")[:max_length]


def _unique_pdf_path(folder, stem):
    candidate = folder / f"{_safe_filename(stem)}.pdf"
    number = 2
    while candidate.exists():
        candidate = folder / f"{_safe_filename(stem)}_{number}.pdf"
        number += 1
    return candidate


def _verify_pdf(path):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f"PDF не найден после генерации:\n{path.resolve()}")
    size = path.stat().st_size
    if size < 8:
        raise RuntimeError(f"PDF пустой или повреждён ({size} байт):\n{path.resolve()}")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise RuntimeError(f"Некорректная сигнатура PDF:\n{path.resolve()}")
    return size


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _read_sheet(ws, header_row):
    if header_row < 1:
        raise ValueError("Строка заголовков должна быть не меньше 1.")
    max_column, max_row = ws.max_column or 1, ws.max_row or 0
    if header_row > max_row:
        raise ValueError(
            f"Строка заголовков {header_row} находится за пределами листа "
            f"(строк: {max_row})."
        )
    raw = next(ws.iter_rows(
        min_row=header_row, max_row=header_row, min_col=1,
        max_col=max_column, values_only=True
    ), ())
    headers = [
        _cell_text(value).strip() or f"Столбец {i}"
        for i, value in enumerate(raw, 1)
    ]
    rows, empty_cells = [], 0
    for values in ws.iter_rows(
        min_row=header_row + 1, max_row=max_row, min_col=1,
        max_col=max_column, values_only=True
    ):
        values = list(values)
        if all(_is_empty(value) for value in values):
            continue
        values.extend([None] * max(0, len(headers) - len(values)))
        values = values[:len(headers)]
        empty_cells += sum(_is_empty(value) for value in values)
        rows.append(values)
    return headers, rows, empty_cells


def _numeric_stats(headers, rows):
    result = []
    for col, header in enumerate(headers):
        vals = [
            row[col] for row in rows
            if col < len(row) and isinstance(row[col], (int, float))
            and not isinstance(row[col], bool)
        ]
        if vals:
            result.append({
                "name": header, "count": len(vals), "sum": sum(vals),
                "min": min(vals), "max": max(vals),
                "average": sum(vals) / len(vals),
            })
    return result


def _register_unicode_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = []
    if sys.platform == "win32":
        candidates.extend([
            ("BahonArial", r"C:\Windows\Fonts\arial.ttf"),
            ("BahonArialUnicode", r"C:\Windows\Fonts\ARIAL.TTF"),
            ("BahonCalibri", r"C:\Windows\Fonts\calibri.ttf"),
        ])
    candidates.extend([
        ("BahonDejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("BahonLiberation",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ])
    for name, filename in candidates:
        if os.path.isfile(filename):
            try:
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, filename))
                return name
            except Exception:
                pass
    raise RuntimeError(
        "Не найден шрифт с поддержкой кириллицы. Установите Arial или DejaVu Sans."
    )


def _p(value, style):
    text = escape(_cell_text(value)).replace("\n", "<br/>")
    return Paragraph(text or " ", style)


def _styles(font):
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="BIQTitle", parent=base["Title"], fontName=font, fontSize=16,
        leading=20, textColor=colors.HexColor(DARK_GREEN),
        alignment=TA_LEFT, spaceAfter=5 * mm,
    ))
    base.add(ParagraphStyle(
        name="BIQSub", parent=base["Normal"], fontName=font, fontSize=8.5,
        leading=11, textColor=colors.HexColor("#536777"), spaceAfter=1.5 * mm,
    ))
    base.add(ParagraphStyle(
        name="BIQBody", parent=base["BodyText"], fontName=font,
        fontSize=7.5, leading=9.5, wordWrap="CJK",
    ))
    base.add(ParagraphStyle(
        name="BIQHead", parent=base["BodyText"], fontName=font,
        fontSize=7.2, leading=8.5, textColor=colors.white, wordWrap="CJK",
    ))
    base.add(ParagraphStyle(
        name="BIQSection", parent=base["Heading2"], fontName=font,
        fontSize=11, leading=14, textColor=colors.HexColor(DARK_GREEN),
        spaceBefore=3 * mm, spaceAfter=2 * mm,
    ))
    return base


def _page_decor(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize
    y = height - 9 * mm
    for color, x in [(GREEN, 0), (WHITE, 18 * mm), (RED, 36 * mm)]:
        canvas.setFillColor(colors.HexColor(color))
        canvas.rect(doc.leftMargin + x, y, 18 * mm, 2 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#D8E2E8"))
    canvas.line(doc.leftMargin, 13 * mm, width - doc.rightMargin, 13 * mm)
    canvas.setFont(doc.report_font, 7)
    canvas.setFillColor(colors.HexColor("#657987"))
    canvas.drawString(doc.leftMargin, 8 * mm, "ANALYTICS AI")
    canvas.drawRightString(width - doc.rightMargin, 8 * mm, f"Страница {doc.page}")
    canvas.restoreState()


def _table(headers, rows, styles, width, repeat_headers=True):
    data = [[_p(value, styles["BIQHead"]) for value in headers]]
    data.extend([[_p(value, styles["BIQBody"]) for value in row] for row in rows])
    count = max(1, len(headers))
    result = Table(
        data, colWidths=[width / count] * count,
        repeatRows=1 if repeat_headers else 0, hAlign="LEFT", splitByRow=1,
    )
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_GREEN)),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CCD9E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F3F7F9")]),
    ]))
    return result


def _make_doc(path, title, source, sheet, orientation, margin=12 * mm):
    font = _register_unicode_font()
    pagesize = A4 if orientation == "Книжная" else landscape(A4)
    doc = SimpleDocTemplate(
        str(path), pagesize=pagesize, rightMargin=margin, leftMargin=margin,
        topMargin=17 * mm, bottomMargin=19 * mm,
        title=title, author="ANALYTICS AI",
    )
    doc.report_font = font
    styles = _styles(font)
    story = [
        Paragraph(escape(title), styles["BIQTitle"]),
        Paragraph(f"<b>Источник:</b> {escape(source)}", styles["BIQSub"]),
        Paragraph(f"<b>Лист:</b> {escape(sheet)}", styles["BIQSub"]),
        Paragraph(f"<b>Дата формирования:</b> {datetime.now():%d.%m.%Y %H:%M}", styles["BIQSub"]),
    ]
    return doc, styles, story


def _create_official_pdf(
    output_path, title, source_name, sheet_name, headers, rows,
    orientation_name, repeat_headers=True, description="",
):
    doc, styles, story = _make_doc(
        output_path, title, source_name, sheet_name, orientation_name
    )
    story.append(Paragraph(f"<b>Количество записей:</b> {len(rows)}", styles["BIQSub"]))
    if description.strip():
        clean = escape(description.replace("\r\n", "\n").replace("\r", "\n")).replace("\n", "<br/>")
        story += [
            Spacer(1, 2 * mm),
            Paragraph("Пожелания к отчёту", styles["BIQSection"]),
            Paragraph(clean, styles["BIQBody"]), Spacer(1, 3 * mm),
        ]
    story += [Spacer(1, 3 * mm), _table(headers, rows, styles, doc.width, repeat_headers)]
    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)


def _create_analytics_pdf(
    output_path, title, source_name, sheet_name, headers, rows,
    empty_cells, orientation_name, description="",
):
    doc, styles, story = _make_doc(
        output_path, title, source_name, sheet_name, orientation_name, 15 * mm
    )
    stats = _numeric_stats(headers, rows)
    summary = [
        ["Показатель", "Значение"],
        ["Количество записей", str(len(rows))],
        ["Количество столбцов", str(len(headers))],
        ["Пустые ячейки в строках данных", str(empty_cells)],
        ["Числовые столбцы", str(len(stats))],
    ]
    story += [Spacer(1, 3 * mm), Paragraph("Общие показатели", styles["BIQSection"])]
    tdata = [[_p(v, styles["BIQHead"] if i == 0 else styles["BIQBody"]) for v in row]
             for i, row in enumerate(summary)]
    table = Table(tdata, colWidths=[doc.width * .65, doc.width * .35], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_GREEN)),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#CCD9E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7F9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Spacer(1, 4 * mm), Paragraph("Статистика числовых столбцов", styles["BIQSection"])]
    if stats:
        matrix = [["Столбец", "Чисел", "Сумма", "Минимум", "Максимум", "Среднее"]]
        for item in stats:
            matrix.append([
                item["name"], str(item["count"]), _cell_text(round(item["sum"], 4)),
                _cell_text(item["min"]), _cell_text(item["max"]),
                _cell_text(round(item["average"], 4)),
            ])
        stat_data = [[_p(v, styles["BIQHead"] if i == 0 else styles["BIQBody"]) for v in row]
                     for i, row in enumerate(matrix)]
        stat_table = Table(
            stat_data, colWidths=[doc.width * r for r in (.25, .10, .17, .14, .14, .20)],
            repeatRows=1, splitByRow=1,
        )
        stat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_GREEN)),
            ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CCD9E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7F9")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(stat_table)
    else:
        story.append(Paragraph("Числовые значения для статистики не обнаружены.", styles["BIQBody"]))
    if description.strip():
        clean = escape(description.replace("\r\n", "\n").replace("\r", "\n")).replace("\n", "<br/>")
        story += [Spacer(1, 4 * mm), Paragraph("Пожелания к отчёту", styles["BIQSection"]),
                  Paragraph(clean, styles["BIQBody"])]
    story += [Spacer(1, 4 * mm), Paragraph(
        "Статистика рассчитана по фактическим числовым значениям выбранного листа.",
        styles["BIQBody"],
    )]
    doc.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)


class SheetSelectionDialog(tk.Toplevel):
    def __init__(self, parent, file_path, selected=None, theme=None):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.theme = theme or _theme_colors()
        self.result = None
        self.variables = {}
        self.title(f"Листы книги — {self.file_path.name}")
        self.geometry("460x430")
        self.minsize(360, 300)
        self.configure(bg=self.theme["bg"])
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Выберите листы для обработки",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        ttk.Label(self, text=self.file_path.name).pack(anchor="w", padx=16)
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True, padx=16, pady=10)
        canvas = tk.Canvas(area, highlightthickness=0, bg=self.theme["card"])
        scroll = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        try:
            workbook = _open_workbook(self.file_path)
            try:
                names = list(workbook.sheetnames)
            finally:
                workbook.close()
        except Exception as exc:
            messagebox.showerror("Ошибка Excel", f"Не удалось прочитать книгу:\n{exc}", parent=self)
            self.destroy()
            return

        selected = names[:] if selected is None else selected
        for name in names:
            variable = tk.BooleanVar(value=name in selected)
            self.variables[name] = variable
            ttk.Checkbutton(inner, text=name, variable=variable).pack(anchor="w", padx=8, pady=4)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text="Все", command=lambda: self._all(True)).pack(side="left")
        ttk.Button(bar, text="Снять выбор", command=lambda: self._all(False)).pack(side="left", padx=5)
        ttk.Button(bar, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(bar, text="Применить", command=self._apply).pack(side="right", padx=5)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _all(self, value):
        for variable in self.variables.values():
            variable.set(value)

    def _apply(self):
        chosen = [name for name, variable in self.variables.items() if variable.get()]
        if not chosen:
            messagebox.showwarning("Выбор листов", "Выберите хотя бы один лист.", parent=self)
            return
        self.result = chosen
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class ReportStudio:
    def __init__(self, parent):
        self.parent = parent
        self.theme = _theme_colors()
        self.files = []
        self.events = queue.Queue()
        self.worker = None
        self.running = False
        self.closing = False
        self.last_pdf = None
        self._layout_after_id = None

        self.window = tk.Toplevel(parent)
        self.window.title(APP_TITLE)
        self.window.geometry("1240x820")
        self.window.minsize(820, 640)
        self.window.configure(bg=self.theme["bg"])

        self.mode_var = tk.StringVar(value="official")
        self.title_var = tk.StringVar(value="Отчёт по данным")
        self.orientation_var = tk.StringVar(value="Книжная")
        self.header_row_var = tk.StringVar(value="1")
        self.output_var = tk.StringVar(value=str(Path.home() / "Documents" / "BahonIQ Reports"))
        self.repeat_headers_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Готов к работе")
        self.progress_var = tk.DoubleVar(value=0)

        self._setup_styles()
        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.after(100, self._poll_events)

    def _setup_styles(self):
        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=self.theme["bg"])
        style.configure("Card.TFrame", background=self.theme["card"])
        style.configure("TLabel", background=self.theme["bg"], foreground=self.theme["text"],
                        font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=self.theme["card"], foreground=self.theme["text"],
                        font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.theme["bg"], foreground=self.theme["text"],
                        font=("Segoe UI", 17, "bold"))
        style.configure("Section.TLabel", background=self.theme["card"], foreground=self.theme["text"],
                        font=("Segoe UI", 11, "bold"))
        style.configure("TButton", font=("Segoe UI", 9), padding=(8, 5))
        style.configure("Accent.TButton", background=GREEN, foreground=WHITE, padding=(10, 6))
        style.map("Accent.TButton", background=[("active", DARK_GREEN)], foreground=[("active", WHITE)])
        style.configure("Treeview", background=self.theme["card"], fieldbackground=self.theme["card"],
                        foreground=self.theme["text"], rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Horizontal.TProgressbar", troughcolor=self.theme["border"], background=GREEN)

    def _build_ui(self):
        header = ttk.Frame(self.window, padding=(18, 10))
        header.pack(fill="x")
        row = ttk.Frame(header)
        row.pack(fill="x")
        tk.Label(row, text="◢ BahonIQ", font=("Segoe UI", 16, "bold"),
                 bg=self.theme["bg"], fg=GREEN).pack(side="left")
        tk.Label(row, text="  |  ANALYTICS AI", font=("Segoe UI", 16, "bold"),
                 bg=self.theme["bg"], fg=self.theme["text"]).pack(side="left")
        tk.Label(row, text="Excel → PDF", font=("Segoe UI", 10),
                 bg=self.theme["bg"], fg=self.theme["muted"]).pack(side="right")
        tk.Frame(header, height=4, bg=GREEN).pack(fill="x", pady=(9, 0))

        content = ttk.Frame(self.window, padding=(14, 0, 14, 8))
        content.pack(fill="both", expand=True)
        self.content_frame = content
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)
        self._build_files_panel(content)
        self._build_settings_panel(content)
        self._build_log_panel(content)
        self._layout_content()
        content.bind("<Configure>", self._on_content_resize, add="+")

        footer = ttk.Frame(self.window, padding=(12, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(footer, variable=self.progress_var, maximum=100,
                                        mode="determinate", length=180)
        self.progress.pack(side="left", padx=8)
        actions = ttk.Frame(footer)
        actions.pack(side="right")
        ttk.Button(actions, text="📂 Открыть папку", command=self._open_output_folder).pack(side="left", padx=3)
        self.open_pdf_button = ttk.Button(actions, text="📄 Открыть PDF",
                                          command=self._open_last_pdf, state="disabled")
        self.open_pdf_button.pack(side="left", padx=3)
        self.start_button = ttk.Button(actions, text="▶ Создать PDF", style="Accent.TButton",
                                        command=self._start_processing)
        self.start_button.pack(side="left", padx=3)

    def _build_files_panel(self, parent):
        panel = ttk.Frame(parent, style="Card.TFrame", padding=10)
        self.files_panel = panel
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=0)
        panel.columnconfigure(2, weight=0)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="Выбор Excel-файлов", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7))
        buttons = ttk.Frame(panel, style="Card.TFrame")
        buttons.grid(row=0, column=1, columnspan=2, sticky="e", pady=(0, 7))
        self.add_files_button = ttk.Button(buttons, text="+ Добавить файлы",
                                           style="Accent.TButton", command=self._add_files)
        self.add_files_button.pack(side="left", padx=2)
        ttk.Button(buttons, text="Удалить", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(buttons, text="Очистить", command=self._clear_files).pack(side="left", padx=2)
        self.file_tree = ttk.Treeview(panel, columns=("file", "sheets", "status"),
                                      show="headings", selectmode="extended")
        for key, label in [("file", "Файл"), ("sheets", "Листы для обработки"), ("status", "Статус")]:
            self.file_tree.heading(key, text=label)
        self.file_tree.column("file", width=250, minwidth=140)
        self.file_tree.column("sheets", width=200, minwidth=100)
        self.file_tree.column("status", width=80, minwidth=65)
        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scroll.set)
        self.file_tree.grid(row=1, column=0, columnspan=2, sticky="nsew")
        scroll.grid(row=1, column=2, sticky="ns")
        self.file_tree.bind("<Double-1>", self._edit_selected_sheets)
        ttk.Label(panel, text="Дважды щёлкните по файлу, чтобы выбрать листы.",
                  style="Card.TLabel").grid(row=2, column=0, columnspan=3,
                                            sticky="w", pady=(6, 0))

    def _build_settings_panel(self, parent):
        panel = ttk.Frame(parent, style="Card.TFrame", padding=11)
        self.settings_panel = panel
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="Настройки отчёта", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(panel, text="Режим отчёта", style="Card.TLabel").grid(row=1, column=0, sticky="w")
        modes = ttk.Frame(panel, style="Card.TFrame")
        modes.grid(row=2, column=0, sticky="ew")
        for label, value in [("Официальный", "official"), ("Аналитика", "analytics"), ("Оба", "both")]:
            ttk.Radiobutton(modes, text=label, variable=self.mode_var, value=value).pack(side="left", padx=(0, 5))
        ttk.Label(panel, text="Заголовок отчёта", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", pady=(7, 2))
        ttk.Entry(panel, textvariable=self.title_var).grid(row=4, column=0, sticky="ew")
        line = ttk.Frame(panel, style="Card.TFrame")
        line.grid(row=5, column=0, sticky="ew", pady=(7, 0))
        ttk.Label(line, text="Строка заголовков:", style="Card.TLabel").pack(side="left")
        ttk.Entry(line, textvariable=self.header_row_var, width=5).pack(side="left", padx=5)
        ttk.Label(line, text="Ориентация:", style="Card.TLabel").pack(side="left", padx=(8, 3))
        ttk.Radiobutton(line, text="Книжная", variable=self.orientation_var, value="Книжная").pack(side="left")
        ttk.Radiobutton(line, text="Альбомная", variable=self.orientation_var, value="Альбомная").pack(side="left", padx=4)
        ttk.Checkbutton(panel, text="Повторять заголовки таблицы на страницах",
                        variable=self.repeat_headers_var).grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Label(panel, text="Пожелания к отчёту (будут добавлены в PDF)",
                  style="Card.TLabel").grid(row=7, column=0, sticky="w", pady=(7, 2))
        self.description_text = tk.Text(panel, height=3, wrap="word", font=("Segoe UI", 9),
                                        bg=self.theme["entry"], fg=self.theme["text"],
                                        insertbackground=self.theme["text"], relief="solid", bd=1)
        self.description_text.grid(row=8, column=0, sticky="ew")
        ttk.Label(panel, text="Папка сохранения PDF", style="Card.TLabel").grid(
            row=9, column=0, sticky="w", pady=(7, 2))
        out = ttk.Frame(panel, style="Card.TFrame")
        out.grid(row=10, column=0, sticky="ew")
        out.columnconfigure(0, weight=1)
        ttk.Entry(out, textvariable=self.output_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(out, text="Обзор…", command=self._choose_output).grid(row=0, column=1, padx=(5, 0))
        ttk.Label(panel, text="PDF сохраняются в указанную папку. Существующие файлы не перезаписываются.",
                  style="Card.TLabel", wraplength=360).grid(row=11, column=0, sticky="w", pady=(6, 0))

    def _build_log_panel(self, parent):
        panel = ttk.Frame(parent, style="Card.TFrame", padding=10)
        self.log_panel = panel
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        top = ttk.Frame(panel, style="Card.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(top, text="Журнал обработки", style="Section.TLabel").pack(side="left")
        ttk.Button(top, text="Очистить журнал", command=self._clear_log).pack(side="right")
        self.log_text = tk.Text(panel, height=8, wrap="word", font=("Consolas", 9),
                                bg=self.theme["card"], fg=self.theme["text"],
                                insertbackground=self.theme["text"], relief="flat", padx=7, pady=5)
        logscroll = ttk.Scrollbar(panel, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=logscroll.set)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        logscroll.grid(row=1, column=1, sticky="ns")
        self.log_text.tag_configure("INFO", foreground=GREEN)
        self.log_text.tag_configure("WARNING", foreground="#B77900")
        self.log_text.tag_configure("ERROR", foreground=RED)
        self._log("Готов к обработке. Исходные Excel-файлы не изменяются.")

    def _on_content_resize(self, _event=None):
        if self._layout_after_id:
            try:
                self.window.after_cancel(self._layout_after_id)
            except tk.TclError:
                pass
        self._layout_after_id = self.window.after(80, self._layout_content)

    def _layout_content(self):
        if not hasattr(self, "files_panel") or self.closing:
            return
        self._layout_after_id = None
        width = max(self.content_frame.winfo_width(), self.window.winfo_width())
        for column in (0, 1):
            self.content_frame.columnconfigure(column, weight=0)
        if width < 1120:
            self.content_frame.columnconfigure(0, weight=1)
            self.content_frame.rowconfigure(0, weight=3)
            self.content_frame.rowconfigure(1, weight=0)
            self.content_frame.rowconfigure(2, weight=2)
            self.files_panel.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, 8))
            self.settings_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 8))
            self.log_panel.grid(row=2, column=0, columnspan=2, sticky="nsew")
        else:
            self.content_frame.columnconfigure(0, weight=3)
            self.content_frame.columnconfigure(1, weight=2)
            self.content_frame.rowconfigure(0, weight=3)
            self.content_frame.rowconfigure(1, weight=2)
            self.files_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
            self.settings_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=(0, 8))
            self.log_panel.grid(row=1, column=0, columnspan=2, sticky="nsew")

    def _rebuild_tree(self):
        if not hasattr(self, "file_tree") or not self.file_tree.winfo_exists():
            return
        self.file_tree.delete(*self.file_tree.get_children())
        for index, item in enumerate(self.files):
            path = Path(item["path"])
            sheets = item.get("sheets", [])
            status = item.get("status", "Готов")
            self.file_tree.insert("", "end", iid=str(index),
                                  values=(path.name, ", ".join(sheets), status))

    def _add_files(self):
        if self.running:
            return
        try:
            chosen = filedialog.askopenfilenames(
                parent=self.window, title="Выберите Excel-файлы",
                filetypes=[("Файлы Excel", "*.xlsx *.xlsm"), ("Все файлы", "*.*")],
            )
            if not chosen:
                self._log("Выбор файлов отменён или файлы не выбраны.")
                return
            existing = {str(Path(item["path"]).resolve()).casefold() for item in self.files}
            added = 0
            for filename in chosen:
                path = Path(filename)
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    self._log(f"Пропущен неподдерживаемый формат: {path.name}", "WARNING")
                    continue
                resolved = str(path.resolve()).casefold()
                if resolved in existing:
                    self._log(f"Файл уже добавлен: {path.name}")
                    continue
                try:
                    workbook = _open_workbook(path)
                    try:
                        sheets = list(workbook.sheetnames)
                    finally:
                        workbook.close()
                except Exception as exc:
                    self._log(f"Не удалось прочитать {path.name}: {exc}", "ERROR")
                    continue
                self.files.append({"path": path, "sheets": sheets, "status": "Готов"})
                existing.add(resolved)
                added += 1
                self._log(f"Добавлен: {path.name} ({len(sheets)} листов)")
            self._rebuild_tree()
            if added:
                self._log(f"Добавлено файлов: {added}.")
            else:
                self._log("Новые файлы не добавлены. Проверьте журнал выше.", "WARNING")
        except Exception as exc:
            self._log(f"Ошибка выбора файлов: {type(exc).__name__}: {exc}", "ERROR")
            messagebox.showerror("Ошибка выбора файлов", f"Не удалось выбрать или добавить файлы:\n\n{exc}",
                                 parent=self.window)

    def _remove_selected(self):
        if self.running:
            return
        selected = sorted((int(iid) for iid in self.file_tree.selection()), reverse=True)
        for index in selected:
            if 0 <= index < len(self.files):
                self.files.pop(index)
        self._rebuild_tree()

    def _clear_files(self):
        if self.running:
            return
        self.files.clear()
        self._rebuild_tree()
        self._log("Список файлов очищен.")

    def _edit_selected_sheets(self, _event=None):
        if self.running:
            return
        selection = self.file_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if not 0 <= index < len(self.files):
            return
        item = self.files[index]
        dialog = SheetSelectionDialog(self.window, item["path"], item["sheets"], self.theme)
        self.window.wait_window(dialog)
        if dialog.result is not None:
            item["sheets"] = dialog.result
            self._rebuild_tree()
            self._log(f"{item['path'].name}: выбрано листов — {len(dialog.result)}.")

    def _choose_output(self):
        if self.running:
            return
        folder = filedialog.askdirectory(parent=self.window, title="Выберите папку для PDF",
                                         initialdir=self.output_var.get() or str(Path.home()),
                                         mustexist=False)
        if folder:
            self.output_var.set(folder)

    def _log(self, message, level="INFO"):
        if not hasattr(self, "log_text"):
            return
        try:
            if not self.log_text.winfo_exists():
                return
            self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] [{level}] {message}\n", level)
            self.log_text.see("end")
        except tk.TclError:
            pass

    def _clear_log(self):
        if not self.running:
            self.log_text.delete("1.0", "end")

    def _open_output_folder(self):
        folder = Path(self.output_var.get().strip()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Ошибка открытия папки", f"Папка:\n{folder}\n\n{exc}", parent=self.window)

    def _open_last_pdf(self):
        if not self.last_pdf:
            messagebox.showwarning(APP_TITLE, "Сначала создайте PDF.", parent=self.window)
            return
        path = Path(self.last_pdf)
        if not path.is_file():
            messagebox.showerror("PDF не найден", f"Файл отсутствует:\n{path}", parent=self.window)
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Ошибка открытия PDF", str(exc), parent=self.window)

    def _start_processing(self):
        if self.running:
            return
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Сначала добавьте Excel-файлы.", parent=self.window)
            return
        try:
            header = int(self.header_row_var.get().strip())
            if header < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Настройки", "Укажите номер строки заголовков от 1.", parent=self.window)
            return
        if not self.output_var.get().strip():
            messagebox.showerror("Настройки", "Укажите папку сохранения.", parent=self.window)
            return
        jobs = []
        for item in self.files:
            if not item["sheets"]:
                messagebox.showwarning("Выбор листов", f"Не выбраны листы для {item['path'].name}.",
                                       parent=self.window)
                return
            jobs.append({"path": str(item["path"]), "sheets": list(item["sheets"])})
        config = {
            "jobs": jobs, "mode": self.mode_var.get(),
            "title": self.title_var.get().strip() or "Отчёт по данным",
            "header_row": header, "orientation": self.orientation_var.get(),
            "output_dir": str(Path(self.output_var.get().strip()).expanduser()),
            "repeat_headers": self.repeat_headers_var.get(),
            "description": self.description_text.get("1.0", "end-1c").strip(),
        }
        self.running = True
        self.start_button.configure(state="disabled")
        self.add_files_button.configure(state="disabled")
        self.status_var.set("Выполняется обработка…")
        self.progress_var.set(0)
        self.last_pdf = None
        self.open_pdf_button.configure(state="disabled")
        self._log(f"Начата обработка: файлов — {len(jobs)}, режим — {config['mode']}.")
        self.worker = threading.Thread(target=self._worker_process, args=(config,), daemon=True)
        self.worker.start()

    def _worker_process(self, config):
        jobs = config["jobs"]
        total = max(1, sum(len(job["sheets"]) for job in jobs))
        completed = success = errors = 0
        output_dir = Path(config["output_dir"])
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.events.put(("error", f"Не удалось создать папку {output_dir}: {exc}"))
            self.events.put(("finished", 0, 1))
            return
        for job in jobs:
            path = Path(job["path"])
            try:
                workbook = _open_workbook(path)
            except Exception as exc:
                errors += 1
                self.events.put(("log", f"Не удалось открыть {path.name}: {exc}", "ERROR"))
                completed += len(job["sheets"])
                self.events.put(("progress", completed * 100 / total))
                continue
            try:
                for sheet_name in job["sheets"]:
                    try:
                        if sheet_name not in workbook.sheetnames:
                            raise ValueError(f"Лист «{sheet_name}» больше не существует.")
                        headers, rows, empty = _read_sheet(workbook[sheet_name], config["header_row"])
                        if not headers:
                            raise ValueError("Не удалось определить столбцы.")
                        stem = _safe_filename(f"{path.stem}_{sheet_name}")
                        mode = config["mode"]
                        if mode in ("official", "both"):
                            output = _unique_pdf_path(output_dir, f"{stem}_официальный")
                            _create_official_pdf(
                                output, config["title"], path.name, sheet_name, headers, rows,
                                config["orientation"], config["repeat_headers"], config["description"])
                            size = _verify_pdf(output)
                            success += 1
                            self.events.put(("last_pdf", str(output.resolve())))
                            self.events.put(("log", f"PDF создан и проверен: {output.name}", "INFO"))
                            self.events.put(("log", f"Путь: {output.resolve()}", "INFO"))
                            self.events.put(("log", f"Размер: {size:,} байт", "INFO"))
                        if mode in ("analytics", "both"):
                            output = _unique_pdf_path(output_dir, f"{stem}_аналитика")
                            _create_analytics_pdf(
                                output, f"{config['title']} — аналитика", path.name, sheet_name,
                                headers, rows, empty, config["orientation"], config["description"])
                            size = _verify_pdf(output)
                            success += 1
                            self.events.put(("last_pdf", str(output.resolve())))
                            self.events.put(("log", f"PDF создан и проверен: {output.name}", "INFO"))
                            self.events.put(("log", f"Путь: {output.resolve()}", "INFO"))
                            self.events.put(("log", f"Размер: {size:,} байт", "INFO"))
                        self.events.put(("log", f"{path.name} / {sheet_name}: записей — {len(rows)}, "
                                                 f"пустых ячеек — {empty}.", "INFO"))
                    except Exception as exc:
                        errors += 1
                        self.events.put(("log", f"{path.name} / {sheet_name}: {exc}", "ERROR"))
                    completed += 1
                    self.events.put(("progress", completed * 100 / total))
            finally:
                workbook.close()
        self.events.put(("finished", success, errors))

    def _poll_events(self):
        if self.closing:
            return
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self._log(event[1], event[2])
                elif kind == "progress":
                    self.progress_var.set(event[1])
                elif kind == "error":
                    self._log(event[1], "ERROR")
                elif kind == "last_pdf":
                    self.last_pdf = event[1]
                    self.open_pdf_button.configure(state="normal")
                elif kind == "finished":
                    _, count, errors = event
                    self.running = False
                    self.start_button.configure(state="normal")
                    self.add_files_button.configure(state="normal")
                    self.status_var.set(
                        f"Завершено. PDF создано: {count}; ошибок: {errors}."
                        if errors else f"Готово. PDF создано: {count}."
                    )
                    self._log(f"Обработка завершена. Создано PDF: {count}; ошибок: {errors}.",
                              "WARNING" if errors else "INFO")
                    if count and self.last_pdf:
                        self._log(f"Последний PDF: {self.last_pdf}", "INFO")
        except queue.Empty:
            pass
        if not self.closing:
            try:
                self.window.after(100, self._poll_events)
            except tk.TclError:
                pass

    def _on_close(self):
        if self.running:
            messagebox.showinfo("Обработка выполняется",
                                "Дождитесь завершения обработки перед закрытием окна.",
                                parent=self.window)
            return
        self.closing = True
        if self._layout_after_id:
            try:
                self.window.after_cancel(self._layout_after_id)
            except tk.TclError:
                pass
        self.window.destroy()


def open_report_studio(parent):
    """Открывает ANALYTICS AI из BahonIQ Work Center."""
    return ReportStudio(parent)
