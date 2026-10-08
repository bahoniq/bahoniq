import threading
import tkinter as tk

from tkinter import (
    filedialog,
    messagebox,
)

from pathlib import Path

from config import DOWNLOADS

from services.settings_service import get_theme

from services.duplicate_service import (
    find_duplicates,
    count_duplicates,
    count_duplicate_files,
    duplicate_size,
    removable_size,
    get_removable_files,
    delete_files,
    format_size,
)


class DuplicateWindow:

    def __init__(self, parent):

        self.parent = parent
        self.theme = get_theme()

        self.selected_folder = Path(DOWNLOADS)

        self.duplicates = {}

        self.stop_event = threading.Event()

        self.scanning = False

        self.build()

    # ========================================================
    # WINDOW
    # ========================================================

    def build(self):

        self.window = tk.Toplevel(self.parent)

        self.window.title(
            "BahonIQ — Мощный поиск дубликатов"
        )

        self.window.geometry(
            "1100x760"
        )

        self.window.minsize(
            900,
            650
        )

        self.window.configure(
            bg=self.theme["bg"]
        )

        self.window.transient(
            self.parent
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = tk.Frame(
            self.window,
            bg=self.theme["card"],
            height=72
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(18, 10)
        )

        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🔎  Мощный поиск дубликатов",
            font=("Segoe UI", 18, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        )

        title.pack(
            side="left",
            padx=18
        )

        # ====================================================
        # FOLDER
        # ====================================================

        folder_frame = tk.Frame(
            self.window,
            bg=self.theme["card"]
        )

        folder_frame.pack(
            fill="x",
            padx=18,
            pady=(0, 10)
        )

        folder_label = tk.Label(
            folder_frame,
            text="Папка:",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        )

        folder_label.pack(
            side="left",
            padx=(15, 8),
            pady=12
        )

        self.folder_text = tk.Label(
            folder_frame,
            text=str(self.selected_folder),
            font=("Segoe UI", 9),
            bg=self.theme["card"],
            fg=self.theme["gray"],
            anchor="w"
        )

        self.folder_text.pack(
            side="left",
            fill="x",
            expand=True,
            pady=12
        )

        self.choose_button = tk.Button(
            folder_frame,
            text="📁 Выбрать",
            command=self.choose_folder,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            bg=self.theme["hover"],
            fg=self.theme["text"]
        )

        self.choose_button.pack(
            side="right",
            padx=10
        )

        self.scan_button = tk.Button(
            folder_frame,
            text="🔎 Сканировать",
            command=self.scan,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=7,
            bg="#009246",
            fg="#FFFFFF",
            activebackground="#007A3A",
            activeforeground="#FFFFFF"
        )

        self.scan_button.pack(
            side="right",
            padx=3
        )

        self.stop_button = tk.Button(
            folder_frame,
            text="⛔ Остановить",
            command=self.stop_scan,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            bg="#FDECEC",
            fg="#B30500",
            state="disabled"
        )

        self.stop_button.pack(
            side="right",
            padx=3
        )

        # ====================================================
        # PROGRESS
        # ====================================================

        progress_frame = tk.Frame(
            self.window,
            bg=self.theme["bg"]
        )

        progress_frame.pack(
            fill="x",
            padx=25,
            pady=(0, 5)
        )

        self.status = tk.Label(
            progress_frame,
            text="Готово к сканированию",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["gray"],
            anchor="w"
        )

        self.status.pack(
            fill="x"
        )

        self.progress = tk.Canvas(
            progress_frame,
            height=8,
            bg=self.theme["border"],
            highlightthickness=0
        )

        self.progress.pack(
            fill="x",
            pady=(7, 5)
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        self.summary = tk.Label(
            self.window,
            text="",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["text"],
            anchor="w"
        )

        self.summary.pack(
            fill="x",
            padx=25,
            pady=(0, 8)
        )

        # ====================================================
        # RESULTS
        # ====================================================

        result_frame = tk.Frame(
            self.window,
            bg=self.theme["card"]
        )

        result_frame.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(0, 12)
        )

        scrollbar = tk.Scrollbar(
            result_frame
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.results = tk.Text(
            result_frame,
            font=("Consolas", 10),
            wrap="word",
            bg=self.theme["input"],
            fg=self.theme["text"],
            insertbackground=self.theme["text"],
            relief="flat",
            bd=0,
            padx=15,
            pady=15,
            state="disabled",
            yscrollcommand=scrollbar.set
        )

        self.results.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.configure(
            command=self.results.yview
        )

        # ====================================================
        # DELETE BUTTON
        # ====================================================

        bottom = tk.Frame(
            self.window,
            bg=self.theme["bg"]
        )

        bottom.pack(
            fill="x",
            padx=18,
            pady=(0, 18)
        )

        self.smart_delete_button = tk.Button(
            bottom,
            text="⭐ Выбрать копии автоматически",
            command=self.smart_select,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=9,
            bg="#EFF6FF",
            fg="#2563EB",
            state="disabled"
        )

        self.smart_delete_button.pack(
            side="left"
        )

        self.delete_button = tk.Button(
            bottom,
            text="🗑 Удалить копии",
            command=self.delete_duplicates,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=18,
            pady=9,
            bg="#E10600",
            fg="#FFFFFF",
            activebackground="#B30500",
            activeforeground="#FFFFFF",
            state="disabled"
        )

        self.delete_button.pack(
            side="right"
        )

    # ========================================================
    # CHOOSE FOLDER
    # ========================================================

    def choose_folder(self):

        if self.scanning:
            return

        folder = filedialog.askdirectory(
            parent=self.window,
            title="Выберите папку для поиска дубликатов",
            initialdir=str(
                self.selected_folder
            )
        )

        if not folder:
            return

        self.selected_folder = Path(folder)

        self.folder_text.configure(
            text=str(self.selected_folder)
        )

        self.status.configure(
            text="Папка выбрана. Нажмите «Сканировать»."
        )

    # ========================================================
    # SCAN
    # ========================================================

    def scan(self):

        if self.scanning:
            return

        if not self.selected_folder.exists():

            messagebox.showerror(
                "Ошибка",
                "Выбранная папка не существует.",
                parent=self.window
            )

            return

        self.scanning = True

        self.stop_event.clear()

        self.duplicates = {}

        self.scan_button.configure(
            state="disabled"
        )

        self.choose_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.delete_button.configure(
            state="disabled"
        )

        self.smart_delete_button.configure(
            state="disabled"
        )

        self.summary.configure(
            text=""
        )

        self.results.configure(
            state="normal"
        )

        self.results.delete(
            "1.0",
            "end"
        )

        self.results.insert(
            "end",
            "⏳ Сканирование...\n\n"
        )

        self.results.configure(
            state="disabled"
        )

        thread = threading.Thread(
            target=self.scan_worker,
            daemon=True
        )

        thread.start()

    # ========================================================
    # WORKER
    # ========================================================

    def scan_worker(self):

        try:

            duplicates = find_duplicates(
                self.selected_folder,
                stop_event=self.stop_event,
                progress_callback=self.progress_callback
            )

            self.window.after(
                0,
                lambda: self.scan_finished(
                    duplicates
                )
            )

        except Exception as error:

            self.window.after(
                0,
                lambda: self.scan_error(
                    error
                )
            )

    # ========================================================
    # PROGRESS
    # ========================================================

    def progress_callback(
        self,
        current,
        total,
        path
    ):

        try:

            self.window.after(
                0,
                lambda: self.update_progress(
                    current,
                    total,
                    path
                )
            )

        except Exception:
            pass

    def update_progress(
        self,
        current,
        total,
        path
    ):

        if not self.scanning:
            return

        filename = Path(path).name

        if total:

            percent = (
                current / total
            ) * 100

            self.status.configure(
                text=(
                    f"🔎 Проверка {current} из "
                    f"{total} — {percent:.0f}%"
                )
            )

            width = self.progress.winfo_width()

            self.progress.delete(
                "all"
            )

            self.progress.create_rectangle(
                0,
                0,
                width * current / total,
                8,
                fill="#009246",
                outline=""
            )

        else:

            self.status.configure(
                text=f"📂 Найдено файлов: {current}"
            )

        self.summary.configure(
            text=f"Файл: {filename}"
        )

    # ========================================================
    # STOP
    # ========================================================

    def stop_scan(self):

        if not self.scanning:
            return

        self.stop_event.set()

        self.status.configure(
            text="⛔ Останавливаем сканирование..."
        )

        self.stop_button.configure(
            state="disabled"
        )

    # ========================================================
    # FINISHED
    # ========================================================

    def scan_finished(
        self,
        duplicates
    ):

        self.scanning = False

        self.duplicates = duplicates

        self.scan_button.configure(
            state="normal"
        )

        self.choose_button.configure(
            state="normal"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.show_results()

    # ========================================================
    # ERROR
    # ========================================================

    def scan_error(
        self,
        error
    ):

        self.scanning = False

        self.scan_button.configure(
            state="normal"
        )

        self.choose_button.configure(
            state="normal"
        )

        self.stop_button.configure(
            state="disabled"
        )

        messagebox.showerror(
            "Ошибка",
            f"Не удалось выполнить поиск:\n\n{error}",
            parent=self.window
        )

    # ========================================================
    # RESULTS
    # ========================================================

    def show_results(self):

        self.results.configure(
            state="normal"
        )

        self.results.delete(
            "1.0",
            "end"
        )

        self.progress.delete(
            "all"
        )

        if not self.duplicates:

            self.results.insert(
                "end",
                "✓ Дубликатов не найдено.\n\n"
            )

            self.status.configure(
                text="Сканирование завершено."
            )

            self.summary.configure(
                text="Дубликатов не найдено."
            )

            self.results.configure(
                state="disabled"
            )

            return

        groups = count_duplicates(
            self.duplicates
        )

        files_count = count_duplicate_files(
            self.duplicates
        )

        total_size = duplicate_size(
            self.duplicates
        )

        removable = removable_size(
            self.duplicates
        )

        self.status.configure(
            text="✓ Сканирование завершено"
        )

        self.summary.configure(
            text=(
                f"Групп: {groups}   •   "
                f"Файлов: {files_count}   •   "
                f"Размер: {format_size(total_size)}   •   "
                f"Можно освободить: {format_size(removable)}"
            )
        )

        self.results.insert(
            "end",
            "НАЙДЕННЫЕ ДУБЛИКАТЫ\n"
        )

        self.results.insert(
            "end",
            "=" * 100 + "\n\n"
        )

        group_number = 1

        for hash_value, items in self.duplicates.items():

            group_size = items[0]["size"]

            self.results.insert(
                "end",
                f"📦 ГРУППА #{group_number}  "
                f"({len(items)} копии, "
                f"{format_size(group_size)} каждая)\n"
            )

            self.results.insert(
                "end",
                f"SHA-256: {hash_value}\n"
            )

            self.results.insert(
                "end",
                "-" * 100 + "\n"
            )

            for index, item in enumerate(items):

                if index == 0:

                    mark = "★ ОСТАВИТЬ"

                else:

                    mark = "○ КОПИЯ"

                self.results.insert(
                    "end",
                    f"{mark:<12} "
                    f"{item['path']}\n"
                )

            self.results.insert(
                "end",
                "\n"
            )

            group_number += 1

        self.results.configure(
            state="disabled"
        )

        self.delete_button.configure(
            state="normal"
        )

        self.smart_delete_button.configure(
            state="normal"
        )

    # ========================================================
    # SMART SELECT
    # ========================================================

    def smart_select(self):

        if not self.duplicates:
            return

        removable = get_removable_files(
            self.duplicates
        )

        size = removable_size(
            self.duplicates
        )

        answer = messagebox.askyesno(
            "Автоматический выбор",
            (
                f"Найдено копий для удаления: "
                f"{len(removable)}\n\n"
                f"Будет освобождено примерно: "
                f"{format_size(size)}\n\n"
                "Из каждой группы будет оставлен "
                "первый файл.\n\n"
                "Перейти к удалению?"
            ),
            parent=self.window
        )

        if answer:

            self.delete_selected(
                removable
            )

    # ========================================================
    # DELETE
    # ========================================================

    def delete_duplicates(self):

        if not self.duplicates:
            return

        removable = get_removable_files(
            self.duplicates
        )

        if not removable:
            return

        self.delete_selected(
            removable
        )

    # ========================================================
    # DELETE SELECTED
    # ========================================================

    def delete_selected(
        self,
        paths
    ):

        size = removable_size(
            self.duplicates,
            paths
        )

        answer = messagebox.askyesno(
            "Подтверждение удаления",
            (
                f"Файлов будет удалено: "
                f"{len(paths)}\n\n"
                f"Освободится примерно: "
                f"{format_size(size)}\n\n"
                "Удалить выбранные копии?"
            ),
            parent=self.window
        )

        if not answer:
            return

        deleted, failed = delete_files(
            paths
        )

        message = (
            f"Удалено файлов: {len(deleted)}\n"
            f"Освобождено: "
            f"{format_size(sum(x['size'] for x in deleted))}"
        )

        if failed:

            message += (
                f"\n\nНе удалось удалить: "
                f"{len(failed)}"
            )

        messagebox.showinfo(
            "Готово",
            message,
            parent=self.window
        )

        # После удаления автоматически пересканируем
        self.scan()


# ============================================================
# OPEN
# ============================================================

def open_duplicates(parent):

    DuplicateWindow(parent)