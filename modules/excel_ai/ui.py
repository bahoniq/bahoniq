
import json
import os
from copy import deepcopy
import tkinter as tk
import threading
from .comparison import ExcelComparisonWindow
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from .ai_interpreter import interpret_task
from .analyzer import analyze_workbook
from .engine import TaskEngine
from .models import TaskStatus
from .workflow import ExcelWorkflow


class ExcelAIWindow(tk.Toplevel):
    """Excel AI workspace для BahonIQ Work Center."""

    def __init__(self, master, database_path=None):
        super().__init__(master)

        self.title("BahonIQ — Excel AI")
        self.geometry("1120x760")
        self.minsize(920, 650)
        self.configure(bg="#F3F6FA")

        self.project_root = Path(__file__).resolve().parents[2]
        default_db = (
            self.project_root / "data" / "excel_ai" / "tasks.sqlite3"
        )

        self.engine = TaskEngine(database_path or default_db)
        self.workflow = ExcelWorkflow(self.engine)

        self.source_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.operation_var = tk.StringVar(
            value="Заполнить пустые ячейки"
        )
        self.columns_var = tk.StringVar(value="3")
        self.value_var = tk.StringVar(value="Не указано")
        self.instruction_text = None
        self.status_var = tk.StringVar(
            value="Выбери Excel-файл для начала работы."
        )

        self.operations = []
        self.current_task_id = None
        self.current_plan = None
        self.last_analysis = None
        self.last_output_path = None

        self._interpreted_signature = None
        self._prepared_signature = None

        self._configure_styles()
        self._build_ui()
        self._refresh_history()

    # ========================================================
    # UI
    # ========================================================

    def _configure_styles(self):
        """Единая современная тема без внешних UI-зависимостей."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background="#F3F6FA")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("Card.TLabelframe", background="#FFFFFF",
                        bordercolor="#DCE3EC", relief="solid")
        style.configure("Card.TLabelframe.Label", background="#FFFFFF",
                        foreground="#172033", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#F3F6FA", foreground="#243047",
                        font=("Segoe UI", 9))
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#243047",
                        font=("Segoe UI", 9))
        style.configure("Muted.Card.TLabel", background="#FFFFFF", foreground="#64748B",
                        font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#172033",
                        bordercolor="#CBD5E1", lightcolor="#CBD5E1",
                        darkcolor="#CBD5E1", padding=8)
        style.configure("TNotebook", background="#F3F6FA", borderwidth=0)
        style.configure("TNotebook.Tab", background="#E8EDF4", foreground="#526078",
                        padding=(18, 9), font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#FFFFFF")],
                  foreground=[("selected", "#155EEF")])
        style.configure("Secondary.TButton", background="#FFFFFF", foreground="#243047",
                        bordercolor="#CBD5E1", padding=(13, 8),
                        font=("Segoe UI", 9, "bold"))
        style.map("Secondary.TButton", background=[("active", "#F1F5F9")])
        style.configure("Accent.TButton", background="#155EEF", foreground="#FFFFFF",
                        bordercolor="#155EEF", padding=(16, 9),
                        font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#0F4FD6"),
                                                  ("disabled", "#A9BCE8")])
        style.configure("AI.TButton", background="#6D4AFF", foreground="#FFFFFF",
                        bordercolor="#6D4AFF", padding=(16, 9),
                        font=("Segoe UI", 9, "bold"))
        style.map("AI.TButton", background=[("active", "#5935E8")])
        style.configure("Success.TButton", background="#159A67", foreground="#FFFFFF",
                        bordercolor="#159A67", padding=(18, 10),
                        font=("Segoe UI", 10, "bold"))
        style.map("Success.TButton", background=[("active", "#108257"),
                                                   ("disabled", "#A8CFC0")])
        style.configure("Tool.TButton", background="#EEF3F9", foreground="#334155",
                        bordercolor="#D8E1EC", padding=(12, 7),
                        font=("Segoe UI", 9))
        style.map("Tool.TButton", background=[("active", "#E2EAF4")])
        style.configure("Status.TLabel", background="#E9EEF5", foreground="#475569",
                        padding=(10, 7), font=("Segoe UI", 9))
        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                        foreground="#243047", rowheight=30, borderwidth=0,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#E9EEF5", foreground="#334155",
                        relief="flat", padding=(8, 7), font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#DCE8FF")],
                  foreground=[("selected", "#173B7A")])

    def _open_comparison(self):
        """Открывает окно сопоставления двух Excel-файлов."""
        from .comparison import ExcelComparisonWindow

        window = ExcelComparisonWindow(self)
        window.transient(self)
        window.focus_set()

    def _open_smart_merge(self):
        """Открывает безопасное объединение нескольких Excel-файлов."""
        from .smart_merge_ui import SmartMergeWindow

        window = SmartMergeWindow(self)
        window.transient(self)
        window.focus_set()

    def _improve_instruction(self):
        """Переписывает обычное описание в точную Excel-команду через Qwen."""
        instruction = self._get_instruction()
        if not instruction:
            messagebox.showwarning(
                "Нет описания",
                "Сначала напиши задачу своими словами.",
                parent=self,
            )
            return

        source = self.source_var.get().strip()
        if not source:
            messagebox.showwarning(
                "Нет файла",
                "Сначала выбери Excel-файл, чтобы Qwen использовал реальные названия столбцов.",
                parent=self,
            )
            return

        try:
            if not self.last_analysis:
                self.last_analysis = analyze_workbook(source)
        except Exception as exc:
            messagebox.showerror("Анализ файла", str(exc), parent=self)
            return

        self.improve_button.configure(state="disabled", text="BahonIQ AI обрабатывает…")
        self.status_var.set("BahonIQ AI уточняет формулировку задачи. Файл не изменяется…")

        def worker():
            try:
                from .task_assistant import improve_task_text
                reply = improve_task_text(instruction, self.last_analysis)
                improved = reply["improved_task"]
                explanation = reply.get("explanation", "")
                question = reply.get("question", "")
                if question and not improved:
                    raise ValueError(question)
                self.after(0, lambda: self._show_improved_instruction(
                    instruction, improved, explanation
                ))
            except Exception as exc:
                self.after(0, lambda message=str(exc): messagebox.showerror(
                    "Улучшение запроса",
                    "Не удалось улучшить запрос через BahonIQ AI:\n" + message,
                    parent=self,
                ))
            finally:
                self.after(0, self._finish_instruction_improvement)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_instruction_improvement(self):
        self.improve_button.configure(state="normal", text="Улучшить запрос через BahonIQ AI")
        self.status_var.set("Проверь формулировку и подготовь план выполнения.")

    def _show_improved_instruction(self, original, improved, explanation=""):
        """Показывает результат до замены пользовательского текста."""
        dialog = tk.Toplevel(self)
        dialog.title("BahonIQ AI — улучшение запроса")
        dialog.geometry("820x590")
        dialog.minsize(680, 500)
        dialog.configure(bg="#F3F6FA")
        dialog.transient(self)
        dialog.grab_set()

        header = tk.Frame(dialog, bg="#6D4AFF", height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="BahonIQ AI уточнил формулировку", bg="#6D4AFF",
                 fg="#FFFFFF", font=("Segoe UI", 16, "bold")).pack(
                     anchor="w", padx=22, pady=(14, 0))
        tk.Label(header, text="Ничего ещё не выполнено — выбери, какой текст использовать.",
                 bg="#6D4AFF", fg="#E6E0FF", font=("Segoe UI", 9)).pack(
                     anchor="w", padx=22)

        body = ttk.Frame(dialog, style="App.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        ttk.Label(body, text="ТВОЙ ТЕКСТ", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w")
        original_box = tk.Text(body, height=5, wrap="word", font=("Segoe UI", 10),
                               bg="#EEF2F7", fg="#526078", relief="flat", padx=10, pady=8)
        original_box.grid(row=1, column=0, sticky="ew", pady=(5, 14))
        original_box.insert("1.0", original)
        original_box.configure(state="disabled")

        ttk.Label(body, text="ТОЧНАЯ ФОРМУЛИРОВКА — МОЖНО РЕДАКТИРОВАТЬ",
                  font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky="w")
        improved_box = tk.Text(body, height=9, wrap="word", undo=True,
                               font=("Segoe UI", 11), bg="#FFFFFF", fg="#172033",
                               relief="solid", borderwidth=1, padx=10, pady=8,
                               highlightthickness=1, highlightbackground="#B8C6DC",
                               highlightcolor="#6D4AFF")
        improved_box.grid(row=3, column=0, sticky="nsew", pady=(5, 8))
        improved_box.insert("1.0", improved)
        self._enable_text_clipboard(improved_box)

        if explanation:
            ttk.Label(body, text=explanation, wraplength=760,
                      foreground="#64748B").grid(row=4, column=0, sticky="w", pady=(0, 10))

        actions = ttk.Frame(body, style="App.TFrame")
        actions.grid(row=5, column=0, sticky="ew")

        def use_improved():
            value = improved_box.get("1.0", "end-1c").strip()
            if not value:
                messagebox.showwarning("Пустой запрос", "Формулировка не может быть пустой.", parent=dialog)
                return
            self.instruction_text.delete("1.0", "end")
            self.instruction_text.insert("1.0", value)
            self._interpreted_signature = None
            self._prepared_signature = None
            dialog.destroy()
            self.status_var.set("Улучшенный запрос вставлен. Теперь подготовь план.")

        ttk.Button(actions, text="Использовать улучшенный запрос",
                   command=use_improved, style="AI.TButton").pack(side="left")
        ttk.Button(actions, text="Изменить вручную",
                   command=lambda: improved_box.focus_set(),
                   style="Secondary.TButton").pack(side="left", padx=8)
        ttk.Button(actions, text="Отмена", command=dialog.destroy,
                   style="Secondary.TButton").pack(side="left")

    def _insert_example(self, text):
        self.instruction_text.delete("1.0", "end")
        self.instruction_text.insert("1.0", text)
        self.instruction_text.focus_set()

    def _refresh_command_examples(self):
        if not hasattr(self, "example_buttons_frame"):
            return
        for child in self.example_buttons_frame.winfo_children():
            child.destroy()
        headers = []
        if self.last_analysis:
            for sheet in self.last_analysis.get("sheets", []):
                for header in sheet.get("headers", []):
                    if header and header not in headers:
                        headers.append(str(header))
        examples = []
        if len(headers) >= 2:
            examples.append(("Перекрёстная таблица",
                f'Создай перекрёстную таблицу: по вертикали «{headers[0]}», '
                f'по горизонтали «{headers[1]}», внутри количество записей.'))
        if headers:
            examples.append(("Сводка и диаграмма",
                f'Покажи количество записей по столбцу «{headers[0]}» и построй диаграмму.'))
            examples.append(("Проверить пропуски",
                f'Найди пустые значения в столбце «{headers[0]}», ничего не удаляй.'))
        if not examples:
            examples = [("Пример сводки", "Сделай общую сводку и построй подходящие диаграммы.")]
        for label, command in examples[:3]:
            ttk.Button(self.example_buttons_frame, text=label,
                       command=lambda value=command: self._insert_example(value),
                       style="Tool.TButton").pack(side="left", padx=(0, 7))

    def _start_quality_audit(self):
        self._insert_example(
            "Проведи комплексный аудит данных: найди пустые значения, полные дубли, "
            "повторяющиеся идентификаторы и варианты написания. Ничего автоматически не удаляй."
        )
        self.status_var.set("Команда проверки качества вставлена. Разбери её или улучши через Qwen.")

    def _clear_operation_cards(self):
        if hasattr(self, "plan_cards_frame"):
            for child in self.plan_cards_frame.winfo_children():
                child.destroy()

    def _render_operation_cards(self, operations):
        self._clear_operation_cards()
        if not operations or not hasattr(self, "plan_cards_frame"):
            return
        for index, operation in enumerate(operations, start=1):
            card = tk.Frame(self.plan_cards_frame, bg="#FFFFFF",
                            highlightthickness=1, highlightbackground="#D8E1EC")
            card.pack(fill="x", pady=(0, 7))
            badge = tk.Label(card, text=str(index), bg="#155EEF", fg="#FFFFFF",
                             width=3, font=("Segoe UI", 10, "bold"), pady=10)
            badge.pack(side="left", fill="y")
            text = self._describe_operation(operation)
            tk.Label(card, text=text, bg="#FFFFFF", fg="#243047",
                     anchor="w", justify="left", wraplength=850,
                     font=("Segoe UI", 10)).pack(side="left", fill="x",
                                                  expand=True, padx=12, pady=10)

    def _build_ui(self):
        outer = ttk.Frame(self, style="App.TFrame")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg="#142033", height=94)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg="#142033")
        brand.pack(fill="both", expand=True, padx=26, pady=17)
        tk.Label(brand, text="BahonIQ", bg="#142033", fg="#FFFFFF",
                 font=("Segoe UI", 20, "bold")).pack(side="left", anchor="n")
        tk.Label(brand, text="  EXCEL AI", bg="#142033", fg="#6EA8FF",
                 font=("Segoe UI", 12, "bold")).pack(side="left", anchor="n", pady=6)
        tk.Label(brand,
                 text="Сформулируй задачу обычными словами — система покажет точный план до изменения файла",
                 bg="#142033", fg="#B9C5D8", font=("Segoe UI", 9)).pack(
                     side="left", anchor="s", padx=(22, 0), pady=5)

        content = ttk.Frame(outer, style="App.TFrame", padding=(20, 16, 20, 0))
        content.pack(fill="both", expand=True)

        self.tabs = ttk.Notebook(content)
        self.tabs.pack(fill="both", expand=True)

        self.task_tab = ttk.Frame(self.tabs, style="App.TFrame", padding=14)
        self.plan_tab = ttk.Frame(self.tabs, style="App.TFrame", padding=14)
        self.history_tab = ttk.Frame(self.tabs, style="App.TFrame", padding=14)

        self.tabs.add(self.task_tab, text="Задание")
        self.tabs.add(self.plan_tab, text="План и результат")
        self.tabs.add(self.history_tab, text="История")

        self._build_task_tab()
        self._build_plan_tab()
        self._build_history_tab()

        ttk.Label(outer, textvariable=self.status_var, style="Status.TLabel",
                  anchor="w").pack(fill="x", side="bottom")

    def _enable_text_clipboard(self, widget, readonly=False):
        """Копирование, вырезание и вставка текста."""

        def copy_text(event=None):
            try:
                selected = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"

            widget.clipboard_clear()
            widget.clipboard_append(selected)
            return "break"

        def cut_text(event=None):
            if str(widget.cget("state")) == "disabled":
                return "break"

            try:
                selected = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"

            widget.clipboard_clear()
            widget.clipboard_append(selected)
            widget.delete("sel.first", "sel.last")
            return "break"

        def paste_text(event=None):
            if str(widget.cget("state")) == "disabled":
                return "break"

            try:
                text = widget.clipboard_get()
            except tk.TclError:
                return "break"

            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

            widget.insert("insert", text)
            return "break"

        widget.bind("<Control-a>", lambda event: (select_all(), "break")[1])
        widget.bind("<Control-A>", lambda event: (select_all(), "break")[1])
        widget.bind("<Control-c>", copy_text)
        widget.bind("<Control-C>", copy_text)
        if not readonly:
            widget.bind("<Control-x>", cut_text)
            widget.bind("<Control-X>", cut_text)
            widget.bind("<Control-v>", paste_text)
            widget.bind("<Control-V>", paste_text)

        menu = tk.Menu(widget, tearoff=0)
        if not readonly:
            menu.add_command(label="Вырезать", command=cut_text)
        menu.add_command(label="Копировать", command=copy_text)
        if not readonly:
            menu.add_command(label="Вставить", command=paste_text)
        menu.add_separator()

        def select_all():
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")
            widget.focus_set()

        menu.add_command(
            label="Выделить всё",
            command=select_all,
        )

        def show_menu(event):
            widget.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        widget.bind("<Button-3>", show_menu)

    def _build_task_tab(self):
        frame = self.task_tab
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        file_card = ttk.LabelFrame(frame, text="  ИСХОДНЫЙ ФАЙЛ  ",
                                   style="Card.TLabelframe", padding=12)
        file_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        file_card.columnconfigure(1, weight=1)
        ttk.Label(file_card, text="Excel-файл", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(file_card, textvariable=self.source_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Button(file_card, text="Выбрать файл", command=self._choose_file,
                   style="Secondary.TButton").grid(row=0, column=2)

        task_card = ttk.LabelFrame(frame, text="  ЗАДАЧА ДЛЯ EXCEL AI  ",
                                   style="Card.TLabelframe", padding=14)
        task_card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        task_card.columnconfigure(0, weight=1)
        task_card.rowconfigure(1, weight=1)
        ttk.Label(task_card, text="Напиши обычными словами, какой результат тебе нужен.",
                  style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(
                      row=0, column=0, sticky="w", pady=(0, 7))

        self.instruction_text = tk.Text(
            task_card,
            height=10,
            wrap="word",
            undo=True,
            font=("Segoe UI", 11),
            bg="#FBFCFE",
            fg="#172033",
            insertbackground="#155EEF",
            selectbackground="#CFE0FF",
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#D5DDE8",
            highlightcolor="#155EEF",
            padx=12,
            pady=10,
        )
        self._enable_text_clipboard(self.instruction_text)

        self.instruction_text.grid(row=1, column=0, sticky="nsew")

        self.instruction_text.bind(
            "<<Modified>>",
            self._on_instruction_modified,
        )
        self.instruction_text.edit_modified(False)

        ttk.Label(
            task_card,
            text=(
                "Например: покажи, сколько студентов на каждой программе, раздели их по форме обучения и построй диаграмму."
            ),
            style="Muted.Card.TLabel", wraplength=900,
        ).grid(row=2, column=0, sticky="w", pady=(7, 10))

        examples_row = ttk.Frame(task_card, style="Card.TFrame")
        examples_row.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(examples_row, text="Быстрые примеры:",
                  style="Muted.Card.TLabel").pack(side="left", padx=(0, 8))
        self.example_buttons_frame = ttk.Frame(examples_row, style="Card.TFrame")
        self.example_buttons_frame.pack(side="left", fill="x", expand=True)
        self._refresh_command_examples()

        buttons = ttk.Frame(task_card, style="Card.TFrame")
        buttons.grid(row=4, column=0, sticky="ew")

        ttk.Button(
            buttons,
            text="Использовать как написано",
            command=self._prepare,
            style="Accent.TButton",
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Очистить",
            command=lambda: self.instruction_text.delete(
                "1.0", "end"
            ),
            style="Secondary.TButton",
        ).pack(side="left", padx=8)

        self.improve_button = ttk.Button(
            buttons,
            text="Улучшить запрос через BahonIQ AI",
            command=self._improve_instruction,
            style="AI.TButton",
        )
        self.improve_button.pack(side="left")

        tools = ttk.LabelFrame(frame, text="  ДОПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ  ",
                               style="Card.TLabelframe", padding=10)
        tools.grid(row=2, column=0, sticky="ew")

        ttk.Button(
            tools,
            text="Сверить студентов / Сопоставить",
            command=self._open_comparison,
            style="Tool.TButton",
        ).pack(side="left")

        ttk.Button(
            tools,
            text="Объединить файлы",
            command=self._open_smart_merge,
            style="Tool.TButton",
        ).pack(side="left", padx=8)

        self.convert_button = ttk.Button(
            tools, text="Конвертировать XLS → XLSX",
            command=self._convert_xls, style="Tool.TButton")
        self.convert_button.pack(side="left")

        ttk.Button(
            tools, text="Проверить качество данных",
            command=self._start_quality_audit, style="Tool.TButton"
        ).pack(side="left", padx=8)

    def _build_plan_tab(self):
        frame = self.plan_tab
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        cards_box = ttk.LabelFrame(frame, text="  ПЛАН ДЕЙСТВИЙ  ",
                                   style="Card.TLabelframe", padding=10)
        cards_box.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.plan_cards_frame = ttk.Frame(cards_box, style="Card.TFrame")
        self.plan_cards_frame.pack(fill="x")
        ttk.Label(self.plan_cards_frame,
                  text="После разбора здесь появятся понятные шаги выполнения.",
                  style="Muted.Card.TLabel").pack(anchor="w", pady=5)

        self.plan_text = tk.Text(
            frame,
            wrap="word",
            height=20,
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg="#243047",
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#D8E1EC",
            padx=16,
            pady=14,
        )
        self._enable_text_clipboard(self.plan_text, readonly=True)
        self.plan_text.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.plan_text.yview,
        )
        scrollbar.grid(row=1, column=1, sticky="ns")

        self.plan_text.configure(
            yscrollcommand=scrollbar.set
        )

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(10, 0),
        )

        ttk.Button(buttons, text="Копировать результат", command=self._copy_plan_text).pack(side="left", padx=(0, 8))

        ttk.Button(
            buttons,
            text="Обновить историю",
            command=self._refresh_history,
        ).pack(side="left")

        self.open_result_button = ttk.Button(
            buttons,
            text="Открыть результат",
            command=self._open_result,
            state="disabled",
        )
        self.open_result_button.pack(
            side="left",
            padx=(8, 0),
        )

        self.open_result_folder_button = ttk.Button(
            buttons,
            text="Открыть папку с результатом",
            command=self._open_result_folder,
            state="disabled",
        )
        self.open_result_folder_button.pack(
            side="left",
            padx=(8, 0),
        )

        self.execute_button = ttk.Button(
            buttons,
            text="Подтвердить и выполнить",
            command=self._confirm_execute,
            style="Success.TButton",
            state="disabled",
        )
        self.execute_button.pack(side="right")

    def _copy_plan_text(self):
        if not self.plan_text.winfo_exists():
            return
        content = self.plan_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("Текст результата скопирован в буфер обмена.")

    def _set_plan_text(self, text):
        """Безопасно обновляет текст на вкладке результата."""
        if (
            not hasattr(self, "plan_text")
            or not self.plan_text.winfo_exists()
        ):
            return

        self.plan_text.configure(state="normal")
        self.plan_text.delete("1.0", "end")
        self.plan_text.insert("1.0", str(text))
        self.plan_text.see("1.0")

    def _format_duplicate_row_reports(self, reports):
        """Формирует подробный отчёт о дубликатах строк."""
        lines = []

        if not isinstance(reports, dict):
            return lines

        duplicate_reports = reports.get("duplicate_rows", [])

        if isinstance(duplicate_reports, dict):
            duplicate_reports = [duplicate_reports]

        if not isinstance(duplicate_reports, list):
            return lines

        for report in duplicate_reports:
            if not isinstance(report, dict):
                continue

            sheet = report.get("sheet", "Неизвестный лист")
            groups = report.get("duplicate_groups", [])

            if not isinstance(groups, list):
                groups = []

            lines.extend([
                "",
                "=" * 60,
                f"ПОДРОБНЫЙ ОТЧЁТ О ДУБЛИКАТАХ — лист «{sheet}»",
                "=" * 60,
                (
                    "Найдено групп: "
                    f"{report.get('duplicate_groups_count', len(groups))}"
                ),
                (
                    "Повторных строк сверх первого вхождения: "
                    f"{report.get('repeated_rows_count', 0)}"
                ),
                (
                    "Всего строк в группах дубликатов: "
                    f"{report.get('rows_in_duplicate_groups', 0)}"
                ),
                "",
            ])

            if not groups:
                lines.append("Дубликаты строк не найдены.")
                continue

            for group_number, group in enumerate(groups, start=1):
                if not isinstance(group, dict):
                    continue

                rows = group.get("rows", [])
                values = group.get("values", [])

                if not isinstance(rows, list):
                    rows = []

                if not isinstance(values, list):
                    values = []

                row_numbers = ", ".join(
                    str(row_number) for row_number in rows
                )

                lines.extend([
                    f"ГРУППА {group_number}",
                    f"Номера строк: {row_numbers}",
                    "-" * 40,
                ])

                for column_number, value in enumerate(values, start=1):
                    value_text = json.dumps(
                        value,
                        ensure_ascii=False,
                        default=str,
                    )

                    lines.append(
                        f"Столбец {column_number}: {value_text}"
                    )

                lines.append("")

        return lines

    def _build_history_tab(self):
        frame = self.history_tab
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("created", "status", "instruction", "id")

        self.history_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=12,
        )

        for key, label in [
            ("created", "Создано"),
            ("status", "Статус"),
            ("instruction", "Задача"),
            ("id", "ID"),
        ]:
            self.history_tree.heading(key, text=label)

        self.history_tree.column(
            "created", width=145, stretch=False
        )
        self.history_tree.column(
            "status", width=100, stretch=False
        )
        self.history_tree.column("instruction", width=400)
        self.history_tree.column(
            "id", width=180, stretch=False
        )

        self.history_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.history_tree.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.history_tree.configure(
            yscrollcommand=scrollbar.set
        )

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=8,
        )

        ttk.Button(
            buttons,
            text="Обновить",
            command=self._refresh_history,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Показать события",
            command=self._show_events,
        ).pack(side="left", padx=8)

    # ========================================================
    # SELECT FILE
    # ========================================================

    def _choose_file(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Выбери Excel-книгу",
            filetypes=[
                ("Excel-файлы", "*.xls *.xlsx *.xlsm"),
                ("Старый Excel 97–2003", "*.xls"),
                ("Современный Excel", "*.xlsx *.xlsm"),
                ("Все файлы", "*.*"),
            ],
        )

        if not filename:
            return

        self.source_var.set(filename)
        self._invalidate_current_plan(
            "Выбран другой исходный файл."
        )
        self.last_analysis = None

        try:
            report = analyze_workbook(filename)
            self.last_analysis = report
            self._refresh_command_examples()

            lines = [
                f"Файл: {report['file_name']}",
                f"Листов: {report['sheet_count']}",
                (
                    "Строк в используемых диапазонах: "
                    f"{report['totals']['rows_across_sheets']}"
                ),
                f"Пустых ячеек: {report['totals']['blank_cells']}",
                f"Формул: {report['totals']['formulas']}",
                "",
            ]

            for sheet in report["sheets"]:
                lines.append(
                    f"Лист «{sheet['name']}»: {sheet['rows']} строк, "
                    f"{sheet['columns']} столбцов, "
                    f"дубликатов строк: {sheet['duplicate_rows']}, "
                    f"формул: {sheet['formula_count']}"
                )
                lines.append(
                    "Столбцы: " + ", ".join(sheet["headers"][:20])
                )
                lines.append("")

            self._set_plan_text("\n".join(lines))
            self.tabs.select(self.plan_tab)
            self.status_var.set(
                "Анализ завершён. Исходный файл не изменён."
            )

        except Exception as exc:
            messagebox.showerror(
                "Ошибка анализа",
                str(exc),
                parent=self,
            )
            self.status_var.set(
                "Не удалось проанализировать файл."
            )

    def _convert_xls(self):
        """Convert in a worker thread; Tk widgets stay on the UI thread."""
        source = self.source_var.get().strip()
        if not source or Path(source).suffix.lower() != ".xls":
            messagebox.showwarning("Конвертация", "Сначала выбери исходный .xls файл.", parent=self)
            return
        destination = filedialog.asksaveasfilename(
            parent=self, title="Сохранить XLSX", defaultextension=".xlsx",
            initialfile=Path(source).stem + ".xlsx",
            filetypes=[("Excel XLSX", "*.xlsx")],
        )
        if not destination:
            return
        if Path(destination).expanduser().resolve().exists():
            messagebox.showerror("Конвертация", "Файл результата уже существует. Выбери другое имя.", parent=self)
            return
        self.convert_button.configure(state="disabled")
        self.status_var.set("Конвертация XLS в XLSX выполняется...")

        def worker():
            try:
                from .converter import convert_xls_to_xlsx
                result = convert_xls_to_xlsx(source, destination)
            except Exception as exc:
                error = str(exc)
                def failed():
                    self.convert_button.configure(state="normal")
                    self.status_var.set("Ошибка конвертации XLS.")
                    messagebox.showerror("Конвертация XLS", error, parent=self)
                try:
                    self.after(0, failed)
                except tk.TclError:
                    pass
                return

            def finished():
                self.convert_button.configure(state="normal")
                self.source_var.set(str(result))
                self._invalidate_current_plan("XLSX создан. Исходный XLS не изменён.")
                self.last_analysis = None
                messagebox.showinfo(
                    "Конвертация XLS", f"Создан файл:\n{result}\n\nОн выбран для дальнейшей работы.",
                    parent=self,
                )
            try:
                self.after(0, finished)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # ========================================================
    # OPERATION SETTINGS
    # ========================================================

    def _operation_changed(self, _event=None):
        kind = self.operation_var.get()

        if kind == "Удалить пустые строки":
            self.columns_var.set("")
            self.value_var.set("")
            self.value_label.configure(
                text="Значение / параметры:"
            )

        elif kind == "Удалить дубликаты":
            if not self.columns_var.get().strip():
                self.columns_var.set("1")
            self.value_var.set("")
            self.value_label.configure(
                text="Значение / параметры:"
            )

        elif kind == "Очистить пробелы в тексте":
            if not self.columns_var.get().strip():
                self.columns_var.set("1")
            self.value_var.set("")
            self.value_label.configure(
                text="Значение / параметры:"
            )

        elif kind == "Заменить текст":
            if not self.columns_var.get().strip():
                self.columns_var.set("1")
            self.value_var.set("")
            self.value_label.configure(
                text="Что заменить => на что:"
            )

        elif kind == "Выделить пустые ячейки":
            if not self.columns_var.get().strip():
                self.columns_var.set("1")
            self.value_var.set("")
            self.value_label.configure(
                text="Значение / параметры:"
            )

        else:
            if not self.columns_var.get().strip():
                self.columns_var.set("3")
            if not self.value_var.get().strip():
                self.value_var.set("Не указано")
            self.value_label.configure(
                text="Значение для заполнения:"
            )

    def _on_instruction_modified(self, _event=None):
        if not self.instruction_text.edit_modified():
            return

        self.instruction_text.edit_modified(False)

        if (
            self._interpreted_signature is not None
            and self._current_signature()
            != self._interpreted_signature
        ):
            self._invalidate_current_plan(
                "Описание изменено. Перед выполнением "
                "нужно подготовить новый план."
            )

    def _current_signature(self):
        """Подпись текущего задания и пути к исходному файлу."""
        source = self.source_var.get().strip()

        return (
            str(Path(source).expanduser().resolve()) if source else "",
            self._get_instruction(),
        )

    def _apply_rewrite(self):
        """Apply an assistant preview without reusing a stale operation plan."""
        result = getattr(self, "_assistant_result", None) or {}
        if result.get("questions"):
            return
        if getattr(self, "_assistant_signature", None) != self._current_signature():
            messagebox.showinfo(
                "Запрос изменён",
                "Описание или исходный файл изменились. Подготовь подсказку заново.",
                parent=self if isinstance(self, tk.Misc) else None,
            )
            return
        value = self.assistant_text.get("1.0", "end-1c").strip()
        if not value:
            return
        expected = str(result.get("text", "")).strip()
        self.instruction_text.delete("1.0", "end")
        self.instruction_text.insert("1.0", value)
        self.current_plan = None
        self._prepared_signature = None
        if value == expected and result.get("operations"):
            self.operations = deepcopy(result["operations"])
            self._interpreted_signature = self._current_signature()
        else:
            self.operations = []
            self._interpreted_signature = None
        if hasattr(self, "status_var"):
            self.status_var.set("Формулировка применена. Проверь и подготовь план.")

    def _invalidate_current_plan(
        self,
        reason="Описание задания изменено.",
    ):
        """Сбрасывает текущий план, сохраняя историю заданий."""
        self.operations = []
        self.current_task_id = None
        self.current_plan = None
        self._interpreted_signature = None
        self._prepared_signature = None

        if hasattr(self, "execute_button"):
            self.execute_button.configure(state="disabled")
        if hasattr(self, "_clear_operation_cards"):
            self._clear_operation_cards()

        if hasattr(self, "status_var"):
            self.status_var.set(reason)

    def _get_instruction(self):
        if self.instruction_text is None:
            return ""

        return self.instruction_text.get(
            "1.0", "end-1c"
        ).strip()

    def _describe_operation(self, operation):
        sheet = operation.get("sheet", "?")
        kind = operation.get("type")
        columns = operation.get("columns", [])

        labels = {
            "remove_empty_rows": (
                f"{sheet}: удалить полностью пустые строки"
            ),
            "remove_duplicates": (
                f"{sheet}: удалить дубликаты по столбцам {columns}"
            ),
            "find_duplicate_rows": (
                f"{sheet}: найти полные дубликаты строк без удаления"
            ),
            "fill_empty": (
                f"{sheet}: заполнить пустые ячейки {columns} "
                f"значением {operation.get('value')!r}"
            ),
            "trim_text": (
                f"{sheet}: убрать пробелы в столбцах {columns}"
            ),
            "replace_values": (
                f"{sheet}: заменить {operation.get('find')!r} "
                f"на {operation.get('replace')!r} "
                f"в столбцах {columns}"
            ),
            "highlight_empty": (
                f"{sheet}: выделить пустые ячейки в столбцах {columns}"
            ),
            "split_to_sheets": (
                f"{sheet}: создать отдельный лист для каждого значения "
                f"столбца {operation.get('column', '?')}"
            ),
            "pivot_count": (
                f"Создать перекрёстную таблицу на основе листа «{sheet}»\n"
                f"По вертикали: {operation.get('row_column', '?')} · "
                f"По горизонтали: {operation.get('column_column', '?')} · "
                "Значение: количество записей"
            ),
            "group_by_aggregate": (
                f"Сгруппировать данные листа «{sheet}» по "
                f"{', '.join(map(str, columns or [operation.get('column', '?')]))}; "
                f"расчёт: {operation.get('function', 'count')}"
            ),
            "find_blank_cells": (
                f"Проверить пустые значения на листе «{sheet}» без удаления"
            ),
            "student_data_audit": (
                f"Провести комплексную проверку качества данных листа «{sheet}»"
            ),
            "smart_summary": (
                f"{sheet}: создать сравнительную сводку по "
                f"{', '.join(map(str, columns)) or 'автоматически выбранным категориальным полям'}; "
                f"диаграммы — {'да' if operation.get('include_charts') else 'нет'}; "
                f"перекрёстные таблицы — {'да' if operation.get('include_cross_tables') else 'нет'}"
            ),
        }

        return labels.get(kind, f"{sheet}: {kind}")

    # ========================================================
    # INTERPRET TASK
    # ========================================================

    def _interpret_instruction(self):
        instruction = self._get_instruction()

        if not instruction:
            messagebox.showwarning(
                "Описание задачи",
                "Опиши задачу своими словами.",
                parent=self,
            )
            return False

        source = self.source_var.get().strip()

        if not source:
            messagebox.showwarning(
                "Нет файла",
                "Сначала выбери Excel-файл.",
                parent=self,
            )
            return False

        if not self.last_analysis:
            try:
                self.last_analysis = analyze_workbook(source)
            except Exception as exc:
                messagebox.showerror(
                    "Ошибка анализа",
                    str(exc),
                    parent=self,
                )
                return False

        self.operations = []

        try:
            result = interpret_task(
                instruction,
                self.last_analysis,
                selected_sheet=None,
            )

            if result.get("warning"):
                self.status_var.set(result["warning"])

            if result.get("questions"):
                questions = "\n".join(
                    f"• {question}"
                    for question in result["questions"]
                )

                self._set_plan_text(
                    "УТОЧНИ НЕКОТОРЫЕ ДЕТАЛИ\n\n"
                    + questions
                    + "\n\nУточни описание задачи и нажми "
                    "«Разобрать задачу ИИ» ещё раз."
                )

                self.tabs.select(self.plan_tab)
                self.status_var.set(
                    "Нужны уточнения; операции не добавлены."
                )
                return False

            operations = result.get("operations", [])

            if not operations:
                messagebox.showwarning(
                    "Не удалось составить план",
                    "Не найдено поддерживаемых операций. "
                    "Уточни описание задачи.",
                    parent=self,
                )
                return False

            self.operations = operations
            self._render_operation_cards(self.operations)
            self._interpreted_signature = self._current_signature()
            self._prepared_signature = None

            lines = [
                "РАЗБОР ЗАДАЧИ",
                "=" * 50,
                (
                    "Режим: "
                    f"{'ИИ по API' if result.get('mode') == 'api' else 'локальные правила'}"
                ),
                f"Описание: {instruction}",
                f"Результат разбора: {result.get('summary', '')}",
                "",
                "ПРЕДЛОЖЕННЫЕ ОПЕРАЦИИ:",
                *[
                    f"{index}. {self._describe_operation(operation)}"
                    for index, operation in enumerate(
                        self.operations, 1
                    )
                ],
                "",
                "Это только план. Файл пока не изменён.",
                (
                    "Нажми «Подготовить план», проверь итоговый план, "
                    "затем отдельно подтверди выполнение."
                ),
            ]

            if result.get("warning"):
                lines.extend([
                    "",
                    "ПРЕДУПРЕЖДЕНИЕ:",
                    result["warning"],
                ])

            self._set_plan_text("\n".join(lines))
            self.tabs.select(self.plan_tab)

            if result.get("mode") == "api":
                self.status_var.set(
                    "ИИ составил план. Проверь операции перед подготовкой."
                )
            else:
                self.status_var.set(
                    "Использованы локальные правила. Для сложных команд "
                    "используется Облачный ИИ BahonIQ."
                )

            return True

        except Exception as exc:
            messagebox.showerror(
                "Разбор задачи",
                str(exc),
                parent=self,
            )
            self.status_var.set(
                "Не удалось разобрать описание задачи."
            )
            return False

    # ========================================================
    # COLUMNS AND MANUAL OPERATIONS
    # ========================================================

    def _parse_columns(self):
        raw = self.columns_var.get().strip()

        if not raw:
            return []

        try:
            columns = [
                int(part.strip())
                for part in raw.split(",")
            ]
        except ValueError as exc:
            raise ValueError(
                "Введи номера столбцов через запятую, например 1,3."
            ) from exc

        if (
            any(column < 1 for column in columns)
            or len(set(columns)) != len(columns)
        ):
            raise ValueError(
                "Номера столбцов должны быть положительными "
                "и не повторяться."
            )

        return columns

    def _add_operation(self):
        sheet = self.sheet_var.get()

        if not sheet:
            messagebox.showwarning(
                "Выбор листа",
                "Сначала выбери Excel-файл.",
                parent=self,
            )
            return

        kind = self.operation_var.get()

        try:
            columns = self._parse_columns()

            if kind == "Удалить пустые строки":
                operation = {
                    "type": "remove_empty_rows",
                    "sheet": sheet,
                    "header_rows": 1,
                }
                description = f"{sheet}: удалить пустые строки"

            elif kind == "Удалить дубликаты":
                if not columns:
                    raise ValueError(
                        "Укажи столбцы для поиска дубликатов."
                    )

                operation = {
                    "type": "remove_duplicates",
                    "sheet": sheet,
                    "columns": columns,
                    "header_rows": 1,
                }
                description = (
                    f"{sheet}: удалить дубликаты по {columns}"
                )

            elif kind == "Очистить пробелы в тексте":
                if not columns:
                    raise ValueError(
                        "Укажи столбцы для очистки."
                    )

                operation = {
                    "type": "trim_text",
                    "sheet": sheet,
                    "columns": columns,
                    "header_rows": 1,
                }
                description = (
                    f"{sheet}: убрать пробелы в столбцах {columns}"
                )

            elif kind == "Заменить текст":
                if not columns:
                    raise ValueError(
                        "Укажи столбцы для замены."
                    )

                raw = self.value_var.get()

                if "=>" not in raw:
                    raise ValueError(
                        "Введи замену в формате: старый текст => новый текст"
                    )

                find_value, replace_value = raw.split("=>", 1)
                find_value = find_value.strip()
                replace_value = replace_value.strip()

                if not find_value:
                    raise ValueError(
                        "Текст для поиска не может быть пустым."
                    )

                operation = {
                    "type": "replace_values",
                    "sheet": sheet,
                    "columns": columns,
                    "find": find_value,
                    "replace": replace_value,
                    "header_rows": 1,
                }
                description = (
                    f"{sheet}: заменить {find_value!r} "
                    f"на {replace_value!r} в {columns}"
                )

            elif kind == "Выделить пустые ячейки":
                if not columns:
                    raise ValueError(
                        "Укажи столбцы для проверки."
                    )

                operation = {
                    "type": "highlight_empty",
                    "sheet": sheet,
                    "columns": columns,
                    "header_rows": 1,
                }
                description = (
                    f"{sheet}: выделить пустые ячейки в {columns}"
                )

            else:
                if not columns:
                    raise ValueError(
                        "Укажи столбцы для заполнения."
                    )

                value = self.value_var.get()

                if value == "":
                    raise ValueError(
                        "Укажи значение для заполнения."
                    )

                operation = {
                    "type": "fill_empty",
                    "sheet": sheet,
                    "columns": columns,
                    "value": value,
                    "header_rows": 1,
                }
                description = (
                    f"{sheet}: заполнить {columns} "
                    f"значением {value!r}"
                )

            self.operations.append(operation)
            self.operation_list.insert("end", description)
            self.status_var.set(
                f"Добавлена операция №{len(self.operations)}."
            )

        except Exception as exc:
            messagebox.showerror(
                "Параметры операции",
                str(exc),
                parent=self,
            )

    def _remove_operation(self):
        selection = self.operation_list.curselection()

        if not selection:
            return

        index = selection[0]
        self.operation_list.delete(index)
        del self.operations[index]

        self.status_var.set(
            "Операция удалена из текущего плана."
        )

    # ========================================================
    # PREPARE PLAN
    # ========================================================

    def _prepare(self):
        source_text = self.source_var.get().strip()
        instruction = self._get_instruction()

        if not source_text:
            messagebox.showwarning(
                "Нет файла",
                "Сначала выбери Excel-файл.",
                parent=self,
            )
            return

        if not instruction:
            messagebox.showwarning(
                "Нет описания",
                "Напиши краткое описание задания.",
                parent=self,
            )
            return

        signature = self._current_signature()

        if signature != self._interpreted_signature:
            self._invalidate_current_plan(
                "Описание или файл изменились. Формирую новый разбор…"
            )
            self.last_analysis = None

            try:
                self.last_analysis = analyze_workbook(source_text)
            except Exception as exc:
                messagebox.showerror(
                    "Ошибка анализа",
                    str(exc),
                    parent=self,
                )
                self.status_var.set(
                    "Не удалось проанализировать исходный файл."
                )
                return

            if not self._interpret_instruction():
                return

            signature = self._current_signature()

        if not self.operations:
            if not self._interpret_instruction():
                return

        if signature != self._current_signature():
            self._invalidate_current_plan(
                "Данные задания изменились. Повтори подготовку."
            )
            messagebox.showwarning(
                "Задание изменилось",
                "Текст задания или исходный файл изменились. "
                "Разбери задание ещё раз.",
                parent=self,
            )
            return

        try:
            task = self.workflow.create_task(
                instruction,
                source_text,
            )
            self.current_task_id = task.id

            prepared = self.workflow.prepare(
                task.id,
                list(self.operations),
            )

            self.current_plan = prepared["plan"]
            self._prepared_signature = self._current_signature()
            self._render_operation_cards(self.operations)
            self.execute_button.configure(state="normal")

            lines = [
                "ПЛАН EXCEL AI",
                "=" * 50,
                f"Задача: {instruction}",
                f"ID: {task.id}",
                f"Исходный файл: {self.current_plan['source']}",
                f"Выходной файл: {self.current_plan['output']}",
                "",
                "ОПЕРАЦИИ:",
                *self.current_plan["steps"],
                "",
                "Исходный файл будет сохранён без изменений.",
                "Выполнение начнётся только после подтверждения.",
            ]

            if self.last_analysis:
                lines.extend([
                    "",
                    "КРАТКИЙ АНАЛИЗ:",
                    f"Листов: {self.last_analysis['sheet_count']}",
                    f"Формул: {self.last_analysis['totals']['formulas']}",
                    (
                        "Пустых ячеек: "
                        f"{self.last_analysis['totals']['blank_cells']}"
                    ),
                ])

            self._set_plan_text("\n".join(lines))
            self.tabs.select(self.plan_tab)
            self._refresh_history()
            self.status_var.set(
                "План готов и ожидает подтверждения."
            )

        except Exception as exc:
            if hasattr(self, "execute_button"):
                self.execute_button.configure(state="disabled")
            messagebox.showerror(
                "Не удалось подготовить план",
                str(exc),
                parent=self,
            )
            self.status_var.set("Ошибка подготовки плана.")
            self._refresh_history()

    # ========================================================
    # EXECUTE PLAN
    # ========================================================

    def _confirm_execute(self):
        if (
            self._prepared_signature is None
            or self._prepared_signature != self._current_signature()
        ):
            self._invalidate_current_plan(
                "План устарел: описание или исходный файл изменились."
            )
            messagebox.showwarning(
                "План устарел",
                "После подготовки изменилось описание задания или "
                "путь к файлу. Старый план не будет выполнен. "
                "Подготовь новый план.",
                parent=self,
            )
            return

        if not self.current_task_id:
            messagebox.showinfo(
                "Нет плана",
                "Сначала подготовь план задания.",
                parent=self,
            )
            return

        try:
            task = self.engine.get_task(self.current_task_id)

            if task.status != TaskStatus.PLANNED:
                messagebox.showwarning(
                    "План недоступен",
                    f"Текущий статус: {task.status.value}",
                    parent=self,
                )
                return

            plan = self.workflow.get_plan(self.current_task_id)

            approved = messagebox.askyesno(
                "Подтверждение выполнения",
                "Проверь параметры:\n\n"
                f"Источник:\n{plan['source']}\n\n"
                f"Результат:\n{plan['output']}\n\n"
                "Исходный файл не будет перезаписан.\n"
                "Создать резервную копию и выполнить операции?",
                parent=self,
            )

            if not approved:
                self.status_var.set(
                    "Выполнение отменено пользователем."
                )
                return

            self.status_var.set("Обработка выполняется в фоне. Окно доступно.")
            task_id = self.current_task_id
            def worker():
                try:
                    response = self.workflow.confirm_and_execute(task_id, confirmed=True)
                except Exception as exc:
                    error = str(exc)
                    self.after(0, lambda: self._background_execution_error(error))
                    return
                self.after(0, lambda: self._background_execution_done(response))
            threading.Thread(target=worker, daemon=True, name="BahonIQ-Excel-Execute").start()
            return
        except Exception as exc:
            messagebox.showerror("Ошибка запуска", str(exc), parent=self)

    def _background_execution_error(self, error):
        messagebox.showerror("Ошибка выполнения", error, parent=self)
        self.status_var.set("Ошибка выполнения. Проверь историю задания.")
        self._refresh_history()

    def _background_execution_done(self, response):
        try:
            result = response["result"]

            output_path = Path(
                result["output"]
            ).expanduser().resolve()

            if not output_path.is_file():
                raise FileNotFoundError(
                    f"Файл результата не найден: {output_path}"
                )

            self.last_output_path = output_path

            self.open_result_button.configure(state="normal")
            self.open_result_folder_button.configure(state="normal")

            lines = [
                "ВЫПОЛНЕНИЕ ЗАВЕРШЕНО",
                "=" * 50,
                f"Статус: {response['task'].status.value}",
                f"Результат: {result['output']}",
                f"Резервная копия: {result['backup']}",
                "",
                "ИЗМЕНЕНИЯ:",
                json.dumps(
                    result["changes"],
                    ensure_ascii=False,
                    indent=2,
                ),
                *self._format_duplicate_row_reports(
                    result.get("reports", {})
                ),
                "",
                "Проверка итогового файла пройдена.",
                "",
                "Используй кнопки ниже, чтобы открыть результат "
                "или папку с ним.",
            ]

            self._set_plan_text("\n".join(lines))
            self._prepared_signature = None
            self.status_var.set(
                "Готово. Результат сохранён в отдельный файл."
            )
            self._refresh_history()

            messagebox.showinfo(
                "Excel AI",
                f"Обработка завершена.\n\n{output_path}",
                parent=self,
            )

        except Exception as exc:
            messagebox.showerror(
                "Ошибка выполнения",
                str(exc),
                parent=self,
            )
            self.status_var.set(
                "Ошибка выполнения. Проверь историю задания."
            )
            self._refresh_history()

    # ========================================================
    # OPEN RESULT
    # ========================================================

    def _open_result(self):
        """Открывает последний успешно созданный Excel-файл."""
        path = self.last_output_path

        if path is None or not path.is_file():
            messagebox.showwarning(
                "Результат недоступен",
                "Сначала успешно выполни обработку Excel-файла.",
                parent=self,
            )
            return

        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror(
                "Не удалось открыть результат",
                "Файл существует, но Windows не смогла его открыть.\n\n"
                f"{path}\n\n{exc}",
                parent=self,
            )

    def _open_result_folder(self):
        """Открывает папку последнего успешно созданного результата."""
        path = self.last_output_path

        if path is None or not path.is_file():
            messagebox.showwarning(
                "Папка недоступна",
                "Сначала успешно выполни обработку Excel-файла.",
                parent=self,
            )
            return

        try:
            os.startfile(str(path.parent))
        except Exception as exc:
            messagebox.showerror(
                "Не удалось открыть папку",
                f"Папка с результатом:\n{path.parent}\n\n{exc}",
                parent=self,
            )

    # ========================================================
    # HISTORY
    # ========================================================

    def _refresh_history(self):
        if not hasattr(self, "history_tree"):
            return

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            for task in self.engine.list_tasks(limit=200):
                self.history_tree.insert(
                    "",
                    "end",
                    values=(
                        task.created_at.replace("T", " ")[:19],
                        task.status.value,
                        task.instruction,
                        task.id,
                    ),
                )

        except Exception as exc:
            self.status_var.set(
                f"Ошибка загрузки истории: {exc}"
            )

    def _show_events(self):
        selection = self.history_tree.selection()

        if not selection:
            messagebox.showinfo(
                "История",
                "Выбери задание в списке.",
                parent=self,
            )
            return

        values = self.history_tree.item(
            selection[0], "values"
        )

        if len(values) < 4:
            messagebox.showerror(
                "История",
                "Не удалось определить ID задания.",
                parent=self,
            )
            return

        task_id = values[3]

        try:
            history = self.workflow.get_history(task_id)
            task = history["task"]

            lines = [
                f"Задача: {task.instruction}",
                f"Статус: {task.status.value}",
                f"ID: {task.id}",
                "",
                "СОБЫТИЯ",
                "=" * 50,
                "",
            ]

            for event in history["events"]:
                details = event.get("details")

                if details is None:
                    raw_details = event.get(
                        "details_json", "{}"
                    )

                    try:
                        details = json.loads(raw_details)
                    except (TypeError, json.JSONDecodeError):
                        details = raw_details

                if isinstance(details, (dict, list)):
                    details_text = json.dumps(
                        details,
                        ensure_ascii=False,
                        indent=2,
                    )
                else:
                    details_text = str(details)

                lines.extend([
                    (
                        f"{event.get('timestamp', '')} | "
                        f"{event.get('event_type', '')}"
                    ),
                    event.get("message", ""),
                    details_text,
                    "",
                    "-" * 50,
                    "",
                ])

            self._set_plan_text("\n".join(lines))
            self.tabs.select(self.plan_tab)

        except Exception as exc:
            messagebox.showerror(
                "История",
                str(exc),
                parent=self,
            )
