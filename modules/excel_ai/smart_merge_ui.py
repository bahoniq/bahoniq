"""Plan-first user interface for universal Multi-File AI."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .smart_merge import execute_multi_file_plan, plan_multi_file_task


class SmartMergeWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Excel AI — Multi-File AI")
        self.geometry("980x760")
        self.minsize(820, 640)
        self.paths = []
        self.plan_result = None
        self.signature = None
        self.result_path = None
        self.status_var = tk.StringVar(value="Выбери два или несколько Excel-файлов.")
        self._build_ui()

    @staticmethod
    def _enable_text_clipboard(widget, readonly=False):
        """Надёжные горячие клавиши и меню буфера обмена для Tk Text."""

        def select_all(event=None):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")
            widget.focus_set()
            return "break"

        def copy_text(event=None):
            try:
                selected = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"
            widget.clipboard_clear()
            widget.clipboard_append(selected)
            widget.update_idletasks()
            return "break"

        def cut_text(event=None):
            if readonly or str(widget.cget("state")) == "disabled":
                return "break"
            try:
                selected = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return "break"
            widget.clipboard_clear()
            widget.clipboard_append(selected)
            widget.update_idletasks()
            widget.delete("sel.first", "sel.last")
            return "break"

        def paste_text(event=None):
            if readonly or str(widget.cget("state")) == "disabled":
                return "break"
            try:
                value = widget.clipboard_get()
            except tk.TclError:
                return "break"
            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            widget.insert("insert", value)
            return "break"

        for sequence in ("<Control-a>", "<Control-A>"):
            widget.bind(sequence, select_all)
        for sequence in ("<Control-c>", "<Control-C>"):
            widget.bind(sequence, copy_text)
        if not readonly:
            for sequence in ("<Control-x>", "<Control-X>"):
                widget.bind(sequence, cut_text)
            for sequence in ("<Control-v>", "<Control-V>"):
                widget.bind(sequence, paste_text)

        menu = tk.Menu(widget, tearoff=0)
        if not readonly:
            menu.add_command(label="Вырезать", command=cut_text)
        menu.add_command(label="Копировать", command=copy_text)
        if not readonly:
            menu.add_command(label="Вставить", command=paste_text)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=select_all)

        def show_menu(event):
            widget.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        widget.bind("<Button-3>", show_menu)

    def _build_ui(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        ttk.Label(outer, text="Multi-File AI", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=("Объединяй строки одинаковых таблиц или сопоставляй разные таблицы по ключу. "
                  "Структура и команда анализируются заново для каждого набора файлов."),
            wraplength=900,
        ).grid(row=1, column=0, sticky="w", pady=(3, 10))

        file_bar = ttk.Frame(outer)
        file_bar.grid(row=2, column=0, sticky="ew")
        ttk.Button(file_bar, text="Выбрать Excel-файлы…", command=self._choose_files).pack(side="left")
        self.file_label = ttk.Label(file_bar, text="Файлы не выбраны")
        self.file_label.pack(side="left", padx=10)

        ttk.Label(outer, text="Опиши результат своими словами:").grid(row=3, column=0, sticky="w", pady=(12, 4))
        self.instruction = tk.Text(outer, height=5, wrap="word", undo=True)
        self._enable_text_clipboard(self.instruction)
        self.instruction.grid(row=4, column=0, sticky="ew")
        self.instruction.bind("<<Modified>>", self._instruction_changed)
        self.instruction.edit_modified(False)

        result_frame = ttk.Frame(outer)
        result_frame.grid(row=5, column=0, sticky="nsew", pady=(10, 0))
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)
        self.text = tk.Text(result_frame, wrap="word", font=("Consolas", 10), state="disabled")
        self._enable_text_clipboard(self.text, readonly=True)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(outer)
        buttons.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.plan_button = ttk.Button(buttons, text="Разобрать задачу и подготовить план", command=self._prepare, state="disabled")
        self.plan_button.pack(side="left")
        self.execute_button = ttk.Button(buttons, text="Подтвердить и выполнить", command=self._execute, state="disabled")
        self.execute_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(buttons, text="Открыть результат", command=self._open_result, state="disabled")
        self.open_button.pack(side="left")
        self.open_folder_button = ttk.Button(
            buttons,
            text="Открыть папку с результатом",
            command=self._open_result_folder,
            state="disabled",
        )
        self.open_folder_button.pack(side="left", padx=8)
        ttk.Label(outer, textvariable=self.status_var, relief="sunken", anchor="w").grid(row=7, column=0, sticky="ew", pady=(10, 0))

    def _set_text(self, value):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.configure(state="disabled")

    def _instruction_value(self):
        return self.instruction.get("1.0", "end-1c").strip()

    def _current_signature(self):
        return (tuple(str(Path(path).resolve()) for path in self.paths), self._instruction_value())

    def _invalidate(self):
        self.plan_result = None
        self.signature = None
        self.execute_button.configure(state="disabled")

    def _instruction_changed(self, _event=None):
        if not self.instruction.edit_modified():
            return
        self.instruction.edit_modified(False)
        if self.signature and self.signature != self._current_signature():
            self._invalidate()
            self.status_var.set("Описание изменено. Подготовь новый план.")

    def _choose_files(self):
        selected = filedialog.askopenfilenames(
            parent=self, title="Выбери Excel-файлы",
            filetypes=[("Excel XLSX/XLSM", "*.xlsx *.xlsm"), ("Все файлы", "*.*")],
        )
        if not selected:
            return
        self.paths = list(selected)
        self._invalidate()
        self.result_path = None
        self.open_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self.file_label.configure(text=f"Выбрано файлов: {len(self.paths)}")
        self.plan_button.configure(state="normal" if len(self.paths) >= 2 else "disabled")
        self._set_text("ВЫБРАННЫЕ ФАЙЛЫ\n" + "=" * 65 + "\n" + "\n".join(f"{i}. {path}" for i, path in enumerate(self.paths, 1)) + "\n\nФайлы пока не изменены.")
        self.status_var.set("Опиши задачу и подготовь план.")

    def _prepare(self):
        instruction = self._instruction_value()
        if not instruction:
            messagebox.showwarning("Описание задачи", "Напиши, что нужно получить из выбранных файлов.", parent=self)
            return
        self.plan_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.status_var.set("Анализирую структуры файлов и строю проверяемый план…")
        paths = list(self.paths)

        def worker():
            try:
                result = plan_multi_file_task(instruction, paths)
            except Exception as exc:
                self.after(0, lambda: self._prepare_failed(str(exc)))
                return
            self.after(0, lambda: self._prepare_done(result))

        threading.Thread(target=worker, daemon=True, name="BahonIQ-MultiFile-Plan").start()

    def _prepare_failed(self, error):
        self.plan_button.configure(state="normal")
        self.status_var.set("Не удалось подготовить план.")
        messagebox.showerror("Multi-File AI", error, parent=self)

    def _prepare_done(self, result):
        self.plan_button.configure(state="normal")
        self.plan_result = result
        self.signature = self._current_signature()
        if result.get("questions"):
            self.execute_button.configure(state="disabled")
            lines = ["НУЖНО УТОЧНЕНИЕ", "=" * 65, *[f"• {item}" for item in result["questions"]]]
            if result.get("explanation"):
                lines.extend(["", "Причина:", result["explanation"]])
            self._set_text("\n".join(lines))
            self.status_var.set("Уточни описание задачи и подготовь план повторно.")
            return
        plan = result["plan"]
        files = {item["file_index"]: item for item in result["schemas"]["files"]}
        lines = [
            "ПЛАН MULTI-FILE AI", "=" * 65,
            f"Режим планирования: {'Облачный ИИ' if result.get('mode') == 'ai' else 'локальная проверяемая логика'}",
            f"Операция: {'объединить строки' if plan['mode'] == 'append' else 'сопоставить таблицы по ключу'}",
        ]
        if plan["mode"] == "join":
            lines.append(f"Тип сопоставления: {plan.get('join_type') or 'inner'}")
        lines.extend(["", "ИСТОЧНИКИ:"])
        for number, source in enumerate(plan["sources"], 1):
            lines.append(f"{number}. {files[source['file_index']]['file_name']} / {source['sheet']}")
            if source.get("key_columns"):
                lines.append("   Ключ: " + ", ".join(source["key_columns"]))
            lines.append("   Столбцы: " + "; ".join(f"{item['source']} → {item['output']}" for item in source["columns"]))
        lines.extend([
            "", "ИТОГОВЫЕ СТОЛБЦЫ:", *[f"• {name}" for name in plan["output_columns"]],
            "", "Исходные файлы не изменятся. Результат будет сохранён в новый XLSX.",
        ])
        self._set_text("\n".join(lines))
        self.execute_button.configure(state="normal")
        self.status_var.set("План готов. Проверь источники, ключи и итоговые столбцы.")

    def _execute(self):
        if not self.plan_result or self.signature != self._current_signature():
            self._invalidate()
            messagebox.showwarning("План устарел", "Файлы или описание изменились. Подготовь новый план.", parent=self)
            return
        destination = filedialog.asksaveasfilename(
            parent=self, title="Сохранить результат Multi-File AI",
            initialdir=str(Path(self.paths[0]).parent), initialfile="Multi_File_AI_Result.xlsx",
            defaultextension=".xlsx", filetypes=[("Excel XLSX", "*.xlsx")],
        )
        if not destination:
            return
        if Path(destination).exists():
            messagebox.showerror("Сохранение", "Файл уже существует. Выбери другое имя.", parent=self)
            return
        approved = messagebox.askyesno(
            "Подтверждение", "Выполнить показанный план и создать отдельный Excel-файл?\n\nИсходные файлы не будут изменены.", parent=self,
        )
        if not approved:
            return
        self.execute_button.configure(state="disabled")
        self.plan_button.configure(state="disabled")
        self.status_var.set("Multi-File AI выполняет подтверждённый план…")
        plan, schemas = self.plan_result["plan"], self.plan_result["schemas"]

        def worker():
            try:
                result = execute_multi_file_plan(plan, schemas, destination)
            except Exception as exc:
                self.after(0, lambda: self._execute_failed(str(exc)))
                return
            self.after(0, lambda: self._execute_done(result))

        threading.Thread(target=worker, daemon=True, name="BahonIQ-MultiFile-Execute").start()

    def _execute_failed(self, error):
        self.plan_button.configure(state="normal")
        self.execute_button.configure(state="normal")
        self.status_var.set("Выполнение остановлено из-за ошибки проверки.")
        messagebox.showerror("Multi-File AI", error, parent=self)

    def _execute_done(self, result):
        self.plan_button.configure(state="normal")
        self.result_path = Path(result["output"])
        self.open_button.configure(state="normal")
        self.open_folder_button.configure(state="normal")
        self._set_text(
            "ВЫПОЛНЕНИЕ ЗАВЕРШЕНО\n" + "=" * 65 +
            f"\nРезультат: {result['output']}\nРежим: {result['mode']}\n"
            f"Файлов: {result['source_files']}\nСтрок: {result['records']}\n"
            f"Столбцы: {', '.join(result['columns'])}\n\nИсходные файлы не изменены."
        )
        self.signature = None
        self.status_var.set("Готово. Новый Excel-файл создан.")
        messagebox.showinfo("Multi-File AI", f"Готово.\n\n{result['output']}", parent=self)

    def _open_result(self):
        if not self.result_path or not self.result_path.is_file():
            messagebox.showwarning("Результат", "Итоговый файл не найден.", parent=self)
            return
        try:
            if os.name == "nt":
                os.startfile(self.result_path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(self.result_path)])
        except Exception as exc:
            messagebox.showerror("Открытие файла", str(exc), parent=self)

    def _open_result_folder(self):
        """Открывает папку результата и по возможности выделяет файл."""
        if not self.result_path or not self.result_path.is_file():
            messagebox.showwarning("Результат", "Итоговый файл не найден.", parent=self)
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(self.result_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(self.result_path)])
            else:
                subprocess.Popen(["xdg-open", str(self.result_path.parent)])
        except Exception as exc:
            messagebox.showerror("Открытие папки", str(exc), parent=self)
