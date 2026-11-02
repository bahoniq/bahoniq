
import json
import os
import tkinter as tk
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
        self.geometry("1050x720")
        self.minsize(850, 600)

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

        self._build_ui()
        self._refresh_history()

        def _open_comparison(self):
            """Открывает окно сопоставления двух Excel-файлов."""
            window = ExcelComparisonWindow(self)
            window.transient(self)
            window.focus_set()

    # ========================================================
    # UI
    # ========================================================

    def _open_comparison(self):
        """Открывает окно сопоставления двух Excel-файлов."""
        from .comparison import ExcelComparisonWindow

        window = ExcelComparisonWindow(self)
        window.transient(self)
        window.focus_set()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="BahonIQ Excel AI",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Анализируй таблицы, готовь план и выполняй "
                "операции с подтверждением."
            ),
        ).pack(anchor="w", pady=(0, 10))

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)

        self.task_tab = ttk.Frame(self.tabs, padding=12)
        self.plan_tab = ttk.Frame(self.tabs, padding=12)
        self.history_tab = ttk.Frame(self.tabs, padding=12)

        self.tabs.add(self.task_tab, text="Задание")
        self.tabs.add(self.plan_tab, text="План и результат")
        self.tabs.add(self.history_tab, text="История")

        self._build_task_tab()
        self._build_plan_tab()
        self._build_history_tab()

        ttk.Label(
            outer,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def _enable_text_clipboard(self, widget):
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

        widget.bind("<Control-c>", copy_text)
        widget.bind("<Control-C>", copy_text)
        widget.bind("<Control-x>", cut_text)
        widget.bind("<Control-X>", cut_text)
        widget.bind("<Control-v>", paste_text)
        widget.bind("<Control-V>", paste_text)

        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Вырезать", command=cut_text)
        menu.add_command(label="Копировать", command=copy_text)
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
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="Excel-файл:").grid(
            row=0, column=0, sticky="w", pady=6
        )

        ttk.Entry(
            frame,
            textvariable=self.source_var,
        ).grid(
            row=0, column=1, sticky="ew", padx=8, pady=6
        )

        ttk.Button(
            frame,
            text="Выбрать…",
            command=self._choose_file,
        ).grid(row=0, column=2, pady=6)

        ttk.Label(
            frame,
            text="Опиши задачу своими словами:",
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(12, 4),
        )

        self.instruction_text = tk.Text(
            frame,
            height=8,
            wrap="word",
            undo=True,
        )
        self._enable_text_clipboard(self.instruction_text)

        self.instruction_text.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=(0, 8),
        )

        self.instruction_text.bind(
            "<<Modified>>",
            self._on_instruction_modified,
        )
        self.instruction_text.edit_modified(False)

        ttk.Label(
            frame,
            text=(
                "Пример: найди дубликаты по ИИН, убери пробелы "
                "в ФИО и выдели пустые ячейки в столбце телефона. "
                "ИИ покажет план до выполнения."
            ),
            wraplength=850,
        ).grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 12),
        )

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=6,
        )

        ttk.Button(
            buttons,
            text="Разобрать задачу и подготовить план",
            command=self._prepare,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Очистить описание",
            command=lambda: self.instruction_text.delete(
                "1.0", "end"
            ),
        ).pack(side="left", padx=8)

        ttk.Button(
            buttons,
            text="Сопоставить два Excel-файла",
            command=self._open_comparison,
        ).pack(side="left", padx=8)

        ttk.Label(
            frame,
            text=(
                "После подготовки открой вкладку «План и результат» "
                "и проверь действия ИИ."
            ),
            wraplength=850,
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(8, 0),
        )

    def _build_plan_tab(self):
        frame = self.plan_tab
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.plan_text = tk.Text(
            frame,
            wrap="word",
            height=20,
        )
        self.plan_text.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.plan_text.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.plan_text.configure(
            yscrollcommand=scrollbar.set
        )

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(10, 0),
        )

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

        ttk.Button(
            buttons,
            text="Подтвердить и выполнить",
            command=self._confirm_execute,
        ).pack(side="right")

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
                    "запусти Ollama и установи рекомендуемую модель qwen2.5:7b."
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

            response = self.workflow.confirm_and_execute(
                self.current_task_id,
                confirmed=True,
            )
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
