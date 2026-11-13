
# -*- coding: utf-8 -*-
"""Главный интерфейс ANALYTICS AI."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except (ImportError, ModuleNotFoundError):
    tk = None
    ttk = None
    filedialog = None
    messagebox = None

from .config import APP_TITLE, APP_VERSION, COLORS, DEFAULT_OUTPUT_DIR
from .launcher import inspect_excel, generate_report
from .history import get_history, search_history
from .analytics import SENSITIVE_HEADER_MARKERS, IDENTIFIER_HEADER_MARKERS


DESCRIPTION_TEMPLATES = {
    "Выберите шаблон…": "",
    "Точный план": (
        "Цель: описать показатели, сравнить группы и периоды.\n"
        "Показатели: Название числового столбца (сумма)\n"
        "Группы: Название столбца категории\n"
        "Дата: Название столбца даты\n"
        "Шаг: месяц"
    ),
    "Полный анализ Qwen": (
        "Проведи полный интеллектуальный анализ данных. Самостоятельно выбери "
        "важные показатели, сравнения, аналитические сюжеты и выводы."
    ),
    "Комплексный анализ": (
        "Проведи комплексное исследование имеющихся данных. Самостоятельно "
        "выбери наиболее содержательные показатели и категории, сравни их, "
        "выяви концентрацию и заметные различия. Используй только методы, "
        "которые подтверждаются структурой текущего файла. Не задавай вопросы "
        "о выборе столбцов, графиков или аналитических методов."
    ),
    "Сравнительный анализ": (
        "Провести сравнительный анализ категорий и периодов. Определить лидеров "
        "и аутсайдеров, абсолютные и относительные различия, концентрацию "
        "результатов и наиболее существенные отклонения от среднего уровня."
    ),
    "Динамика и тенденции": (
        "Проанализировать динамику показателей во времени. Выявить рост, снижение, "
        "сезонность, точки резкого изменения и устойчивые тенденции. Отдельно "
        "указать периоды с максимальными и минимальными значениями."
    ),
    "KPI и эффективность": (
        "Оценить выполнение ключевых показателей, результативность и эффективность. "
        "Сопоставить фактические значения между категориями, выделить отклонения, "
        "риски недостижения целей и приоритетные направления улучшения."
    ),
    "Управленческий отчёт": (
        "Подготовить краткий управленческий обзор. Сначала представить ключевые "
        "факты и сравнения, затем риски и проблемные зоны. В завершение дать "
        "конкретные рекомендации с приоритетами и ожидаемым результатом."
    ),
}


class ReportStudio:
    def __init__(self, parent):
        self.parent = parent
        self.source_path = None
        self.workbook_data = None
        self.current_matrix = []
        self.busy = False
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.generation_started_at = None
        self.current_stage = ""

        self.window = tk.Toplevel(parent)
        self.window.title(f"{APP_TITLE} — {APP_VERSION}")
        self.window.geometry("1180x790")
        self.window.minsize(940, 650)
        self.window.configure(bg=COLORS["background"])

        self._configure_style()
        self._build_ui()
        self._center_window()

        self.window.protocol("WM_DELETE_WINDOW", self._close)
        self.window.after(100, self._process_events)

    def _configure_style(self):
        style = ttk.Style(self.window)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "BIQ.TFrame",
            background=COLORS["background"],
        )
        style.configure(
            "BIQ.Surface.TFrame",
            background=COLORS["surface"],
        )
        style.configure(
            "BIQ.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "BIQ.Surface.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "BIQ.Heading.TLabel",
            background=COLORS["background"],
            foreground=COLORS["navy"],
            font=("Segoe UI", 17, "bold"),
        )
        style.configure(
            "BIQ.Subheading.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["navy"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "BIQ.TButton",
            font=("Segoe UI", 9),
            padding=(10, 7),
        )
        style.configure(
            "BIQ.Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 9),
        )
        style.configure(
            "BIQ.Working.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 9),
            foreground="white",
            background=COLORS["accent"],
        )
        style.map(
            "BIQ.Working.TButton",
            foreground=[("disabled", "white")],
            background=[("disabled", COLORS["accent"])],
        )
        style.configure(
            "BIQ.TEntry",
            padding=6,
        )
        style.configure(
            "BIQ.TCombobox",
            padding=5,
        )
        style.configure(
            "BIQ.Horizontal.TProgressbar",
            troughcolor=COLORS["border"],
            background=COLORS["accent"],
        )
        style.configure(
            "BIQ.Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=26,
            font=("Segoe UI", 9),
        )
        style.configure(
            "BIQ.Treeview.Heading",
            background=COLORS["navy"],
            foreground="white",
            font=("Segoe UI", 9, "bold"),
            padding=7,
        )
        style.map(
            "BIQ.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", "white")],
        )

    def _build_ui(self):
        # Верхняя панель
        header = tk.Frame(
            self.window,
            bg=COLORS["navy"],
            height=88,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=COLORS["navy"])
        brand.pack(side="left", fill="both", expand=True, padx=22, pady=13)

        tk.Label(
            brand,
            text="BAHONIQ",
            bg=COLORS["navy"],
            fg="white",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="ANALYTICS AI  •  EXCEL → PDF + POWERPOINT",
            bg=COLORS["navy"],
            fg="#D8E5EE",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            header,
            text=f"Версия {APP_VERSION}",
            bg=COLORS["navy"],
            fg="#D8E5EE",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=22)

        # Основная область
        body = ttk.Frame(self.window, style="BIQ.TFrame", padding=16)
        body.pack(fill="both", expand=True)

        self._build_file_section(body)

        content = ttk.Frame(body, style="BIQ.TFrame")
        content.pack(fill="both", expand=True, pady=(12, 0))

        settings_panel = ttk.Frame(content, style="BIQ.Surface.TFrame")
        settings_panel.pack(side="left", fill="y", padx=(0, 12))
        settings_canvas = tk.Canvas(settings_panel, width=355, height=100,
                                    highlightthickness=0, bg=COLORS["surface"])
        settings_scroll = ttk.Scrollbar(settings_panel, orient="vertical", command=settings_canvas.yview)
        settings_canvas.configure(yscrollcommand=settings_scroll.set)
        settings_scroll.pack(side="right", fill="y")
        settings_canvas.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(settings_canvas, style="BIQ.Surface.TFrame", padding=14)
        settings_window = settings_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda event: settings_canvas.configure(scrollregion=settings_canvas.bbox("all")))
        settings_canvas.bind("<Configure>", lambda event: settings_canvas.itemconfigure(settings_window, width=event.width))

        right = ttk.Frame(content, style="BIQ.Surface.TFrame", padding=12)
        right.pack(side="left", fill="both", expand=True)

        self._build_settings(left)
        self._build_preview(right)

        self._build_status(body)

    def _build_file_section(self, parent):
        panel = ttk.Frame(
            parent,
            style="BIQ.Surface.TFrame",
            padding=14,
        )
        panel.pack(fill="x")

        ttk.Label(
            panel,
            text="Исходный Excel-файл",
            style="BIQ.Subheading.TLabel",
        ).pack(anchor="w")

        row = ttk.Frame(panel, style="BIQ.Surface.TFrame")
        row.pack(fill="x", pady=(8, 0))

        self.file_var = tk.StringVar(value="Файл не выбран")

        ttk.Entry(
            row,
            textvariable=self.file_var,
            state="readonly",
            style="BIQ.TEntry",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(
            row,
            text="Выбрать Excel…",
            style="BIQ.TButton",
            command=self._choose_file,
        ).pack(side="left")

        ttk.Button(
            row,
            text="История",
            style="BIQ.TButton",
            command=self._show_history,
        ).pack(side="left", padx=(8, 0))

        self.file_info_var = tk.StringVar(
            value="Поддерживаемые форматы: XLSX, XLSM, XLS"
        )
        ttk.Label(
            panel,
            textvariable=self.file_info_var,
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w", pady=(7, 0))

    def _build_settings(self, parent):
        ttk.Label(
            parent,
            text="Настройки отчёта",
            style="BIQ.Subheading.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            parent,
            text="Лист Excel",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.sheet_var = tk.StringVar()

        self.sheet_combo = ttk.Combobox(
            parent,
            textvariable=self.sheet_var,
            state="readonly",
            width=31,
            style="BIQ.TCombobox",
        )
        self.sheet_combo.pack(fill="x", pady=(5, 12))
        self.sheet_combo.bind(
            "<<ComboboxSelected>>",
            self._on_sheet_selected,
        )

        ttk.Label(
            parent,
            text="Название отчёта",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.title_var = tk.StringVar(
            value="Аналитический отчёт"
        )

        ttk.Entry(
            parent,
            textvariable=self.title_var,
            style="BIQ.TEntry",
        ).pack(fill="x", pady=(5, 12))

        ttk.Label(
            parent,
            text="Профиль профессионального анализа",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.report_profile_var = tk.StringVar(value="Автоматически")
        self.audience_var = tk.StringVar(value="Руководство")
        ttk.Combobox(
            parent,
            textvariable=self.report_profile_var,
            values=[
                "Автоматически",
                "Управленческий",
                "Образование и деканат",
                "Финансовый",
                "HR и персонал",
                "Академический",
            ],
            state="readonly",
            style="BIQ.TCombobox",
        ).pack(fill="x", pady=(5, 12))

        ttk.Label(
            parent,
            text="Ориентация страницы",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.orientation_var = tk.StringVar(value="Автоматически")

        self.orientation_combo = ttk.Combobox(
            parent,
            textvariable=self.orientation_var,
            values=[
                "Автоматически",
                "Книжная",
                "Альбомная",
            ],
            state="readonly",
            style="BIQ.TCombobox",
        )
        self.orientation_combo.pack(fill="x", pady=(5, 12))

        ttk.Label(
            parent,
            text="Формат результата",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.output_format_var = tk.StringVar(value="Только PDF")
        ttk.Combobox(
            parent,
            textvariable=self.output_format_var,
            values=["Только PDF", "Только PowerPoint", "PDF + PowerPoint"],
            state="readonly",
            style="BIQ.TCombobox",
        ).pack(fill="x", pady=(5, 12))

        ttk.Label(
            parent,
            text="Глубина отчёта",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.report_depth_var = tk.StringVar(value="Полный аудит (Все категории, 8+ стр)")
        ttk.Combobox(
            parent,
            textvariable=self.report_depth_var,
            values=[
                "Полный аудит (Все категории, 8+ стр)",
                "Стандартный (Управленческий, 5-6 стр)",
                "Краткий (C-Level, 3-4 стр)",
            ],
            state="readonly",
            style="BIQ.TCombobox",
        ).pack(fill="x", pady=(5, 12))

        ttk.Label(
            parent,
            text="Движок ИИ-аналитика",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.ai_model_var = tk.StringVar(value="BahonIQ AI (~2-3 сек)")
        self.ai_model_combo = ttk.Combobox(
            parent,
            textvariable=self.ai_model_var,
            values=[
                "BahonIQ AI (~2-3 сек)",
                "Локальная Ollama / Qwen 2.5 (~1-2 мин)",
            ],
            state="readonly",
            style="BIQ.TCombobox",
        )
        self.ai_model_combo.pack(fill="x", pady=(5, 12))

        self.source_table_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            parent,
            text="Добавить образец исходных данных (до 40 строк)",
            variable=self.source_table_var,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            parent,
            text="Задача / план / описание отчёта",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.description_text = tk.Text(
            parent,
            height=5,
            width=32,
            wrap="word",
            font=("Segoe UI", 9),
            bg="white",
            fg=COLORS["text"],
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.description_text.pack(fill="x", pady=(5, 12))
        self._configure_description_editing()
        ttk.Label(
            parent,
            text="Результат: executive summary, аналитические графики, решения.\n"
                 "Анализ выполняет BahonIQ AI с интеллектуальным\n"
                 "фоллбэком на локальную Ollama / Qwen 2.5 при оффлайне.",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        template_row = ttk.Frame(parent, style="BIQ.Surface.TFrame")
        template_row.pack(fill="x", pady=(0, 12))
        self.description_template_var = tk.StringVar(value="Выберите шаблон…")
        ttk.Combobox(
            template_row,
            textvariable=self.description_template_var,
            values=list(DESCRIPTION_TEMPLATES),
            state="readonly",
            width=20,
            style="BIQ.TCombobox",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            template_row,
            text="Вставить шаблон",
            style="BIQ.TButton",
            command=self._insert_description_template,
        ).pack(side="left", padx=(5, 0))

        ttk.Label(
            parent,
            text="Папка сохранения отчётов",
            style="BIQ.Surface.TLabel",
        ).pack(anchor="w")

        self.output_var = tk.StringVar(
            value=str(DEFAULT_OUTPUT_DIR)
        )

        output_row = ttk.Frame(
            parent,
            style="BIQ.Surface.TFrame",
        )
        output_row.pack(fill="x", pady=(5, 12))

        ttk.Entry(
            output_row,
            textvariable=self.output_var,
            style="BIQ.TEntry",
        ).pack(side="left", fill="x", expand=True)

        ttk.Button(
            output_row,
            text="…",
            width=3,
            command=self._choose_output,
        ).pack(side="left", padx=(5, 0))

        self.generate_button = ttk.Button(
            parent,
            text="СФОРМИРОВАТЬ ОТЧЁТ",
            style="BIQ.Primary.TButton",
            command=self._start_generation,
        )
        self.generate_button.pack(fill="x", pady=(4, 7))

        ttk.Button(
            parent,
            text="Открыть папку отчётов",
            style="BIQ.TButton",
            command=self._open_output_folder,
        ).pack(fill="x")

    def _configure_description_editing(self):
        """Добавляет надёжные операции буфера обмена для Windows/Linux."""
        widget = self.description_text

        def copy_text(_event=None):
            try:
                selected = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"
            widget.clipboard_clear()
            widget.clipboard_append(selected)
            return "break"

        def cut_text(_event=None):
            copy_text()
            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            return "break"

        def paste_text(_event=None):
            try:
                value = widget.clipboard_get()
            except tk.TclError:
                return "break"
            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            widget.insert("insert", value)
            widget.see("insert")
            return "break"

        def select_all(_event=None):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
            return "break"

        for sequence in ("<Control-c>", "<Control-C>"):
            widget.bind(sequence, copy_text)
        for sequence in ("<Control-x>", "<Control-X>"):
            widget.bind(sequence, cut_text)
        for sequence in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
            widget.bind(sequence, paste_text)
        for sequence in ("<Control-a>", "<Control-A>"):
            widget.bind(sequence, select_all)

        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Вырезать", command=cut_text)
        menu.add_command(label="Копировать", command=copy_text)
        menu.add_command(label="Вставить", command=paste_text)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=select_all)
        self.description_context_menu = menu

        def show_menu(event):
            widget.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
            return "break"

        widget.bind("<Button-3>", show_menu)

    def _insert_description_template(self):
        template = DESCRIPTION_TEMPLATES.get(
            self.description_template_var.get(), ""
        )
        if not template:
            return
        current = self.description_text.get("1.0", "end-1c").strip()
        if current:
            self.description_text.insert("end", "\n\n" + template)
        else:
            self.description_text.insert("1.0", template)
        self.description_text.focus_set()
        self.description_text.see("end")

    def _build_preview(self, parent):
        top = ttk.Frame(parent, style="BIQ.Surface.TFrame")
        top.pack(fill="x")

        ttk.Label(
            top,
            text="Предпросмотр данных",
            style="BIQ.Subheading.TLabel",
        ).pack(side="left")

        self.preview_info_var = tk.StringVar(
            value="Выберите файл для просмотра"
        )

        ttk.Label(
            top,
            textvariable=self.preview_info_var,
            style="BIQ.Surface.TLabel",
        ).pack(side="right")

        table_frame = ttk.Frame(
            parent,
            style="BIQ.Surface.TFrame",
        )
        table_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.preview_tree = ttk.Treeview(
            table_frame,
            show="headings",
            style="BIQ.Treeview",
        )

        vertical = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.preview_tree.yview,
        )
        horizontal = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.preview_tree.xview,
        )

        self.preview_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )

        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.preview_tree.tag_configure(
            "odd",
            background="#F4F7FA",
        )
        self.preview_tree.tag_configure(
            "even",
            background="#FFFFFF",
        )

        self.preview_warning_var = tk.StringVar(value="")

        ttk.Label(
            parent,
            textvariable=self.preview_warning_var,
            style="BIQ.Surface.TLabel",
            wraplength=650,
        ).pack(anchor="w", pady=(8, 0))

    def _build_status(self, parent):
        status = ttk.Frame(parent, style="BIQ.TFrame")
        status.pack(fill="x", pady=(12, 0))

        self.status_var = tk.StringVar(
            value="Готов к работе"
        )

        ttk.Label(
            status,
            textvariable=self.status_var,
            style="BIQ.TLabel",
        ).pack(side="left", fill="x", expand=True)

        self.progress_var = tk.DoubleVar(value=0)

        self.progress_bar = ttk.Progressbar(
            status,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="BIQ.Horizontal.TProgressbar",
            length=220,
        )
        self.progress_bar.pack(side="right", padx=(10, 0))

    def _center_window(self):
        self.window.update_idletasks()

        width = min(1180, self.window.winfo_screenwidth() - 80)
        height = min(790, self.window.winfo_screenheight() - 100)

        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, (self.window.winfo_screenheight() - height) // 2)

        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _choose_file(self):
        filename = filedialog.askopenfilename(
            parent=self.window,
            title="Выберите Excel-файл",
            filetypes=[
                ("Файлы Excel", "*.xlsx *.xlsm *.xls"),
                ("Все файлы", "*.*"),
            ],
        )

        if not filename:
            return

        if self.busy:
            return

        self.source_path = Path(filename)
        self.file_var.set(str(self.source_path))
        self.file_info_var.set("Чтение структуры Excel…")
        self.status_var.set("Загружаем файл…")
        self.preview_warning_var.set("")
        self.preview_info_var.set("Выполняется чтение")
        self.progress_var.set(0)

        self._clear_preview()

        thread = threading.Thread(
            target=self._inspect_worker,
            args=(str(self.source_path),),
            daemon=True,
        )
        thread.start()

    def _inspect_worker(self, filename):
        try:
            data = inspect_excel(filename)
            self.events.put(("inspect_success", data))
        except Exception as exc:
            self.events.put(("inspect_error", str(exc)))

    def _on_sheet_selected(self, _event=None):
        if not self.workbook_data:
            return

        name = self.sheet_var.get()

        selected = next(
            (
                item for item in self.workbook_data["sheets"]
                if item["name"] == name
            ),
            None,
        )

        if selected:
            self.current_matrix = selected["matrix"]
            self._show_matrix(self.current_matrix)

            analysis = selected["analysis"]
            self.preview_info_var.set(
                f"{analysis['row_count']} записей • "
                f"{len([c for c in analysis.get('categorical_columns', []) if c.get('reportable')])} "
                "содержательных разрезов"
            )

            warnings = selected.get("warnings", [])
            self.preview_warning_var.set(
                ("Предупреждения: " + " ".join(warnings) if warnings else "")
            )

    def _clear_preview(self):
        self.preview_tree.delete(
            *self.preview_tree.get_children()
        )
        self.preview_tree["columns"] = ()

    def _show_matrix(self, matrix):
        self._clear_preview()

        if not matrix:
            return

        headers = [
            str(value).strip() if value is not None else ""
            for value in matrix[0]
        ]

        headers = [
            header or f"Столбец {index + 1}"
            for index, header in enumerate(headers)
        ]

        def private_header(header: str) -> bool:
            normalized = " " + header.casefold().strip() + " "
            return any(marker in normalized for marker in (
                *SENSITIVE_HEADER_MARKERS, *IDENTIFIER_HEADER_MARKERS
            ))

        visible_indices = []
        for index, header in enumerate(headers):
            if private_header(header):
                continue
            sample = [row[index] if index < len(row) else None for row in matrix[1:201]]
            if header.startswith("Столбец ") and not any(
                value is not None and str(value).strip() for value in sample
            ):
                continue
            visible_indices.append(index)
            if len(visible_indices) >= 30:
                break

        headers = [headers[index] for index in visible_indices]
        max_columns = len(headers)

        columns = [f"c{index}" for index in range(max_columns)]
        self.preview_tree["columns"] = columns

        for index, column in enumerate(columns):
            self.preview_tree.heading(
                column,
                text=headers[index],
            )
            self.preview_tree.column(
                column,
                width=130,
                minwidth=80,
                stretch=True,
                anchor="w",
            )

        # Не перегружаем окно слишком большой таблицей.
        for row_index, row in enumerate(matrix[1:201]):
            values = []

            for source_index in visible_indices:
                value = row[source_index] if source_index < len(row) else None
                if value is None:
                    values.append("")
                else:
                    values.append(str(value)[:300])

            values.extend([""] * (max_columns - len(values)))

            self.preview_tree.insert(
                "",
                "end",
                values=values,
                tags=("even" if row_index % 2 == 0 else "odd",),
            )

        total_rows = max(0, len(matrix) - 1)

        if total_rows > 200:
            self.preview_info_var.set(
                f"Показаны первые 200 из {total_rows} записей"
            )

    def _choose_output(self):
        folder = filedialog.askdirectory(
            parent=self.window,
            title="Выберите папку для отчётов",
            initialdir=self.output_var.get() or str(Path.home()),
        )

        if folder:
            self.output_var.set(folder)

    def _start_generation(self):
        if self.busy:
            return

        if not self.source_path or not self.source_path.is_file():
            messagebox.showwarning(
                APP_TITLE,
                "Сначала выберите существующий Excel-файл.",
                parent=self.window,
            )
            return

        if not self.sheet_var.get():
            messagebox.showwarning(
                APP_TITLE,
                "Выберите лист Excel.",
                parent=self.window,
            )
            return

        title = self.title_var.get().strip()

        if not title:
            messagebox.showwarning(
                APP_TITLE,
                "Введите название отчёта.",
                parent=self.window,
            )
            return

        output_dir = self.output_var.get().strip()

        if not output_dir:
            messagebox.showwarning(
                APP_TITLE,
                "Укажите папку сохранения отчётов.",
                parent=self.window,
            )
            return

        try:
            Path(output_dir).expanduser().mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Не удалось подготовить папку:\n{exc}",
                parent=self.window,
            )
            return

        description = self.description_text.get(
            "1.0", "end"
        ).strip()

        orientation_map = {
            "Автоматически": "auto",
            "Книжная": "portrait",
            "Альбомная": "landscape",
        }

        settings = {
            "source_path": str(self.source_path),
            "sheet_name": self.sheet_var.get(),
            "title": title,
            "output_dir": output_dir,
            "description": description,
            "report_profile": self.report_profile_var.get(),
            "audience": self.audience_var.get(),
            "include_source_table": self.source_table_var.get(),
            "orientation": orientation_map.get(
                self.orientation_var.get(), "auto"
            ),
            "report_depth": self.report_depth_var.get(),
            "output_formats": {
                "Только PDF": ("pdf",),
                "Только PowerPoint": ("pptx",),
                "PDF + PowerPoint": ("pdf", "pptx"),
            }.get(self.output_format_var.get(), ("pdf",)),
            "ai_model": (
                "qwen2.5:7b"
                if "7b" in (getattr(self, "ai_model_var", None) and self.ai_model_var.get() or "").lower()
                else "qwen2.5:3b"
            ),
        }

        self.busy = True
        self.generation_started_at = time.monotonic()
        self.current_stage = "Подготовка отчёта"
        self.cancel_event.clear()
        self.generate_button.configure(
            state="disabled",
            style="BIQ.Working.TButton",
            text="ПОДГОТОВКА ДАННЫХ • 00:00",
        )
        self.progress_var.set(0)
        self.status_var.set("Подготовка отчёта…")

        thread = threading.Thread(
            target=self._generation_worker,
            args=(settings,),
            daemon=True,
        )
        thread.start()

    def _generation_worker(self, settings):
        def progress(percent, message):
            self.events.put(("progress", percent, message))

        try:
            result = generate_report(
                source_path=settings["source_path"],
                sheet_name=settings["sheet_name"],
                title=settings["title"],
                output_dir=settings["output_dir"],
                description=settings["description"],
                include_source_table=settings["include_source_table"],
                orientation=settings["orientation"],
                output_formats=settings["output_formats"],
                progress=progress,
                report_profile=settings["report_profile"],
                audience=settings["audience"],
                ai_model=settings.get("ai_model"),
                report_depth=settings.get("report_depth", "Краткий (C-Level, 3-4 стр)"),
            )
            self.events.put(("generation_success", result))
        except Exception as exc:
            self.events.put(("generation_error", str(exc)))

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]

                if kind == "progress":
                    self.progress_var.set(event[1])
                    self.current_stage = event[2]

                elif kind == "inspect_success":
                    self.workbook_data = event[1]
                    names = [
                        item["name"]
                        for item in self.workbook_data["sheets"]
                    ]

                    self.sheet_combo["values"] = names

                    self.file_info_var.set(
                        f"Формат: {self.workbook_data['format']} • "
                        f"Листов: {len(names)}"
                    )

                    if names:
                        self.sheet_var.set(names[0])
                        self._on_sheet_selected()
                        self.status_var.set("Файл готов к анализу")
                    else:
                        self.status_var.set("В файле нет доступных листов")
                        self.preview_warning_var.set(
                            "Не удалось найти листы с данными."
                        )

                    warnings = self.workbook_data.get("warnings", [])

                    if warnings:
                        self.preview_warning_var.set(
                            " ".join(warnings)
                        )

                elif kind == "inspect_error":
                    self.workbook_data = None
                    self.status_var.set("Ошибка чтения файла")
                    messagebox.showerror(
                        APP_TITLE,
                        event[1],
                        parent=self.window,
                    )

                elif kind == "generation_success":
                    self.busy = False
                    self.generation_started_at = None
                    self.generate_button.configure(
                        state="normal",
                        style="BIQ.Primary.TButton",
                        text="СФОРМИРОВАТЬ ОТЧЁТ",
                    )
                    self.window.title(f"{APP_TITLE} — {APP_VERSION}")
                    self.progress_var.set(100)
                    result = event[1]
                    warnings = result.get("warnings", [])
                    ai_result = result.get("ai_analysis", {})
                    ai_completed = ai_result.get("source") == "ollama"
                    self.status_var.set("Аналитический отчёт сформирован и проверен")

                    created = []
                    if result.get("output_file"):
                        created.append("PDF")
                    if result.get("presentation_file"):
                        created.append("PowerPoint")
                    message = (
                        "Отчёт успешно сформирован аналитическим ядром BahonIQ AI.\n"
                        f"Готовые форматы: {', '.join(created)}."
                    )

                    if warnings:
                        message += (
                            "\n\nПредупреждения:\n- "
                            + "\n- ".join(warnings)
                        )

                    primary_file = (
                        result.get("output_file") or
                        result.get("presentation_file")
                    )
                    primary_name = "PDF" if result.get("output_file") else "PowerPoint"
                    open_file = messagebox.askyesno(
                        APP_TITLE,
                        message + f"\n\nОткрыть {primary_name}?",
                        parent=self.window,
                    )

                    if open_file and primary_file:
                        self._open_path(primary_file)

                elif kind == "generation_error":
                    self.busy = False
                    self.generation_started_at = None
                    self.generate_button.configure(
                        state="normal",
                        style="BIQ.Primary.TButton",
                        text="СФОРМИРОВАТЬ ОТЧЁТ",
                    )
                    self.window.title(f"{APP_TITLE} — {APP_VERSION}")
                    error_text = str(event[1])
                    self.status_var.set(
                        "ИИ-анализ не выполнен — отчёт не создан"
                        if "ии-анализ" in error_text.casefold()
                        else "Не удалось сформировать отчёты"
                    )

                    messagebox.showerror(
                        APP_TITLE,
                        error_text,
                        parent=self.window,
                    )

        except queue.Empty:
            pass

        if self.busy and self.generation_started_at is not None:
            elapsed = int(time.monotonic() - self.generation_started_at)
            minutes, seconds = divmod(elapsed, 60)
            stage_lower = self.current_stage.casefold()
            if "разбор" in stage_lower:
                short_stage = "РАЗБОР ЗАДАНИЯ"
                detail = self.current_stage
            elif "чтение" in stage_lower:
                short_stage = "ЧТЕНИЕ EXCEL"
                detail = self.current_stage
            elif "поиск" in stage_lower:
                short_stage = "ПОДГОТОВКА ЛИСТА"
                detail = self.current_stage
            elif "анализ" in stage_lower:
                short_stage = "РАСЧЁТ ПОКАЗАТЕЛЕЙ"
                detail = self.current_stage
            elif "pdf" in stage_lower:
                short_stage = "СОЗДАНИЕ PDF"
                detail = self.current_stage
            elif "powerpoint" in stage_lower:
                short_stage = "СОЗДАНИЕ POWERPOINT"
                detail = self.current_stage
            elif "истори" in stage_lower:
                short_stage = "СОХРАНЕНИЕ РЕЗУЛЬТАТА"
                detail = self.current_stage
            else:
                short_stage = "ПОДГОТОВКА ОТЧЁТА"
                detail = self.current_stage
            timer = f"{minutes:02d}:{seconds:02d}"
            percent = int(self.progress_var.get())
            self.status_var.set(
                f"{detail} • прошло {timer}"
            )
            self.generate_button.configure(
                text=f"{short_stage} • {percent}% • {timer}"
            )
            self.window.title(
                f"{APP_TITLE} — {short_stage} — {timer}"
            )

        if self.window.winfo_exists():
            self.window.after(100, self._process_events)

    def _show_history(self):
        history_window = tk.Toplevel(self.window)
        history_window.title("История отчётов — BahonIQ")
        history_window.geometry("950x480")
        history_window.configure(bg=COLORS["background"])
        history_window.transient(self.window)

        frame = ttk.Frame(
            history_window,
            style="BIQ.Surface.TFrame",
            padding=12,
        )
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        search_var = tk.StringVar()

        search_row = ttk.Frame(frame, style="BIQ.Surface.TFrame")
        search_row.pack(fill="x", pady=(0, 10))

        ttk.Label(
            search_row,
            text="Поиск:",
            style="BIQ.Surface.TLabel",
        ).pack(side="left", padx=(0, 6))

        search_entry = ttk.Entry(
            search_row,
            textvariable=search_var,
            style="BIQ.TEntry",
        )
        search_entry.pack(side="left", fill="x", expand=True)

        columns = (
            "date",
            "source",
            "sheet",
            "status",
            "output",
        )

        tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            style="BIQ.Treeview",
        )

        headings = {
            "date": ("Дата", 145),
            "source": ("Исходный файл", 190),
            "sheet": ("Лист", 110),
            "status": ("Статус", 90),
            "output": ("PDF", 300),
        }

        for column, (heading, width) in headings.items():
            tree.heading(column, text=heading)
            tree.column(column, width=width, minwidth=70)

        tree.pack(fill="both", expand=True)

        def refresh(*_args):
            tree.delete(*tree.get_children())

            for item in search_history(search_var.get()):
                tree.insert(
                    "",
                    "end",
                    iid=item.get("id"),
                    values=(
                        item.get("created_at", ""),
                        Path(item.get("source_file", "")).name,
                        item.get("sheet_name", ""),
                        item.get("status", ""),
                        item.get("output_file", ""),
                    ),
                )

        search_var.trace_add("write", refresh)
        refresh()

        def open_selected(_event=None):
            selection = tree.selection()

            if not selection:
                return

            values = tree.item(selection[0], "values")

            if not values:
                return

            output_file = values[4]

            if output_file and Path(output_file).is_file():
                self._open_path(output_file)
            else:
                messagebox.showinfo(
                    APP_TITLE,
                    "PDF-файл не найден. Возможно, он был перемещён.",
                    parent=history_window,
                )

        tree.bind("<Double-1>", open_selected)

        buttons = ttk.Frame(frame, style="BIQ.Surface.TFrame")
        buttons.pack(fill="x", pady=(10, 0))

        ttk.Button(
            buttons,
            text="Открыть выбранный PDF",
            command=open_selected,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Обновить",
            command=refresh,
        ).pack(side="left", padx=8)

        ttk.Button(
            buttons,
            text="Закрыть",
            command=history_window.destroy,
        ).pack(side="right")

    def _open_output_folder(self):
        folder = Path(self.output_var.get()).expanduser()

        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._open_path(str(folder))
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Не удалось открыть папку:\n{exc}",
                parent=self.window,
            )

    @staticmethod
    def _open_path(path):
        path = str(path)

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _close(self):
        if self.busy:
            close = messagebox.askyesno(
                APP_TITLE,
                "Формирование отчёта ещё выполняется. "
                "Закрыть окно? Задача может продолжить работу в фоне.",
                parent=self.window,
            )
            if not close:
                return

        self.window.destroy()


def open_report_studio(parent):
    """Совместимая точка входа для главного окна Work Center."""

    return ReportStudio(parent)
