
import threading
import tkinter as tk

from tkinter import filedialog, messagebox
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
    is_name_group,
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
        self.window.title("BahonIQ — Мощный поиск дубликатов")
        self.window.geometry("1100x760")
        self.window.minsize(900, 650)
        self.window.configure(bg=self.theme["bg"])
        self.window.transient(self.parent)

        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        # HEADER
        header = tk.Frame(
            self.window,
            bg=self.theme["card"],
            height=72
        )
        header.pack(fill="x", padx=18, pady=(18, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔎  Мощный поиск дубликатов",
            font=("Segoe UI", 18, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        ).pack(side="left", padx=18)

        # FOLDER
        folder_frame = tk.Frame(
            self.window,
            bg=self.theme["card"]
        )
        folder_frame.pack(fill="x", padx=18, pady=(0, 10))

        tk.Label(
            folder_frame,
            text="Папка:",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        ).pack(side="left", padx=(15, 8), pady=12)

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
        self.choose_button.pack(side="right", padx=10)

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
        self.scan_button.pack(side="right", padx=3)

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
        self.stop_button.pack(side="right", padx=3)

        # PROGRESS
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
        self.status.pack(fill="x")

        self.progress = tk.Canvas(
            progress_frame,
            height=8,
            bg=self.theme["border"],
            highlightthickness=0
        )
        self.progress.pack(fill="x", pady=(7, 5))

        # SUMMARY
        self.summary = tk.Label(
            self.window,
            text="",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["text"],
            anchor="w",
            justify="left"
        )
        self.summary.pack(
            fill="x",
            padx=25,
            pady=(0, 8)
        )

        # RESULTS
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

        scrollbar = tk.Scrollbar(result_frame)
        scrollbar.pack(side="right", fill="y")

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

        scrollbar.configure(command=self.results.yview)

        # BOTTOM BUTTONS
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
        self.smart_delete_button.pack(side="left")

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
        self.delete_button.pack(side="right")

    # ========================================================
    # WINDOW CLOSE
    # ========================================================

    def close_window(self):
        if self.scanning:
            answer = messagebox.askyesno(
                "Закрыть окно",
                "Сканирование ещё выполняется. Остановить его и закрыть окно?",
                parent=self.window
            )

            if not answer:
                return

            self.stop_event.set()

        self.window.destroy()

    # ========================================================
    # CHOOSE FOLDER
    # ========================================================

    def choose_folder(self):
        if self.scanning:
            return

        folder = filedialog.askdirectory(
            parent=self.window,
            title="Выберите папку для поиска дубликатов",
            initialdir=str(self.selected_folder)
        )

        if not folder:
            return

        self.selected_folder = Path(folder)
        self.folder_text.configure(text=str(self.selected_folder))

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

        self.scan_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.delete_button.configure(state="disabled")
        self.smart_delete_button.configure(state="disabled")

        self.summary.configure(text="")
        self.progress.delete("all")

        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("end", "⏳ Сканирование...\n\n")
        self.results.configure(state="disabled")

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
                lambda result=duplicates: self.scan_finished(result)
            )

        except Exception as error:
            error_text = str(error)
            self.window.after(
                0,
                lambda text=error_text: self.scan_error(text)
            )

    # ========================================================
    # PROGRESS
    # ========================================================

    def progress_callback(self, current, total, path):
        try:
            self.window.after(
                0,
                lambda c=current, t=total, p=path:
                    self.update_progress(c, t, p)
            )
        except (RuntimeError, tk.TclError):
            pass

    def update_progress(self, current, total, path):
        if not self.scanning:
            return

        filename = Path(path).name

        if total:
            percent = current / total * 100
            self.status.configure(
                text=f"🔎 Проверка {current} из {total} — {percent:.0f}%"
            )

            width = self.progress.winfo_width()
            self.progress.delete("all")
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
                text=f"📂 Просмотр файлов: {current}"
            )

        self.summary.configure(text=f"Текущий файл: {filename}")

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
        self.stop_button.configure(state="disabled")

    # ========================================================
    # FINISHED
    # ========================================================

    def scan_finished(self, duplicates):
        self.scanning = False
        self.duplicates = duplicates

        self.scan_button.configure(state="normal")
        self.choose_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        if self.stop_event.is_set():
            self.status.configure(text="Сканирование остановлено.")
        else:
            self.status.configure(text="Сканирование завершено.")

        self.show_results()

    # ========================================================
    # ERROR
    # ========================================================

    def scan_error(self, error):
        self.scanning = False

        self.scan_button.configure(state="normal")
        self.choose_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        messagebox.showerror(
            "Ошибка",
            f"Не удалось выполнить поиск:\n\n{error}",
            parent=self.window
        )

    # ========================================================
    # RESULTS
    # ========================================================

    def show_results(self):
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.progress.delete("all")

        if not self.duplicates:
            self.results.insert(
                "end",
                "✓ Дубликатов и возможных копий не найдено.\n"
            )
            self.status.configure(text="Сканирование завершено.")
            self.summary.configure(text="Результатов нет.")
            self.results.configure(state="disabled")
            self.delete_button.configure(state="disabled")
            self.smart_delete_button.configure(state="disabled")
            return

        exact_groups = {
            key: items
            for key, items in self.duplicates.items()
            if not is_name_group(key)
        }

        name_groups = {
            key: items
            for key, items in self.duplicates.items()
            if is_name_group(key)
        }

        total_groups = len(self.duplicates)
        total_files = count_duplicate_files(self.duplicates)
        total_size = duplicate_size(self.duplicates)
        removable_paths = get_removable_files(self.duplicates)
        possible_saving = removable_size(self.duplicates)

        self.status.configure(text="✓ Сканирование завершено")

        self.summary.configure(
            text=(
                f"Групп: {total_groups}  •  "
                f"Точные: {len(exact_groups)}  •  "
                f"По имени: {len(name_groups)}\n"
                f"Файлов в группах: {total_files}  •  "
                f"Размер: {format_size(total_size)}  •  "
                f"Размер кандидатов на удаление: "
                f"{format_size(possible_saving)}"
            )
        )

        self.results.insert(
            "end",
            "BAHONIQ — РЕЗУЛЬТАТЫ ПОИСКА\n"
            + "=" * 90 + "\n\n"
        )

        self.results.insert(
            "end",
            "1. ТОЧНЫЕ ДУБЛИКАТЫ\n"
            "Содержимое файлов совпадает по SHA-256.\n"
            + "-" * 90 + "\n"
        )

        if not exact_groups:
            self.results.insert(
                "end",
                "Точных дубликатов не найдено.\n\n"
            )
        else:
            for number, (digest, items) in enumerate(
                exact_groups.items(), start=1
            ):
                self.results.insert(
                    "end",
                    f"\nГРУППА #{number} — {len(items)} файлов\n"
                )
                self.results.insert("end", f"SHA-256: {digest}\n")
                self.results.insert(
                    "end",
                    f"Размер каждого: {format_size(items[0]['size'])}\n"
                )

                for index, item in enumerate(items):
                    mark = "★ ОСТАВИТЬ" if index == 0 else "○ В КОРЗИНУ"
                    self.results.insert(
                        "end",
                        f"{mark:<18} {item['path']}\n"
                    )

                self.results.insert("end", "\n")

        self.results.insert(
            "end",
            "\n2. ВОЗМОЖНЫЕ КОПИИ ПО ИМЕНИ\n"
            "Содержимое этих файлов не подтверждено сравнением SHA-256.\n"
            "Перед удалением внимательно проверьте пути.\n"
            + "-" * 90 + "\n"
        )

        if not name_groups:
            self.results.insert(
                "end",
                "Возможных копий по имени не найдено.\n"
            )
        else:
            for number, (group_key, items) in enumerate(
                name_groups.items(), start=1
            ):
                normalized_name = group_key.removeprefix("NAME::")

                self.results.insert(
                    "end",
                    f"\nГРУППА ПО ИМЕНИ #{number}: {normalized_name}\n"
                )

                for index, item in enumerate(items):
                    mark = "★ ОСТАВИТЬ" if index == 0 else "⚠ КАНДИДАТ"
                    self.results.insert(
                        "end",
                        f"{mark:<18} "
                        f"{format_size(item['size']):>12}  "
                        f"{item['path']}\n"
                    )

                self.results.insert("end", "\n")

        self.results.configure(state="disabled")

        if removable_paths:
            self.delete_button.configure(state="normal")
            self.smart_delete_button.configure(state="normal")
        else:
            self.delete_button.configure(state="disabled")
            self.smart_delete_button.configure(state="disabled")

    # ========================================================
    # SMART SELECT
    # ========================================================

    def smart_select(self):
        if not self.duplicates:
            return

        removable = get_removable_files(self.duplicates)

        if not removable:
            messagebox.showinfo(
                "Автоматический выбор",
                "Нет файлов для перемещения в Корзину.",
                parent=self.window
            )
            return

        size = removable_size(self.duplicates, removable)

        name_candidate_paths = {
            item["path"]
            for key, items in self.duplicates.items()
            if is_name_group(key)
            for item in items[1:]
        }

        name_count = sum(
            1 for path in removable
            if Path(path) in name_candidate_paths
        )

        warning = ""
        if name_count:
            warning = (
                f"\n\nИз них возможных копий только по имени: "
                f"{name_count}.\nИх содержимое может отличаться."
            )

        answer = messagebox.askyesno(
            "Автоматический выбор",
            (
                f"Кандидатов на перемещение в Корзину: {len(removable)}\n"
                f"Общий размер: {format_size(size)}\n"
                f"{warning}\n\n"
                "Из каждой группы будет оставлен первый файл.\n"
                "Просмотреть список и продолжить?"
            ),
            parent=self.window
        )

        if answer:
            self.delete_selected(removable)

    # ========================================================
    # DELETE
    # ========================================================

    def delete_duplicates(self):
        if not self.duplicates:
            return

        removable = get_removable_files(self.duplicates)

        if not removable:
            messagebox.showinfo(
                "Удаление",
                "Нет файлов для перемещения в Корзину.",
                parent=self.window
            )
            return

        self.delete_selected(removable)

    # ========================================================
    # DELETE SELECTED
    # ========================================================

    def delete_selected(self, paths):
        paths = list(dict.fromkeys(Path(path) for path in paths))

        if not paths:
            return

        size = removable_size(self.duplicates, paths)

        name_candidate_paths = {
            item["path"]
            for key, items in self.duplicates.items()
            if is_name_group(key)
            for item in items[1:]
        }

        selected_name_candidates = [
            path for path in paths
            if path in name_candidate_paths
        ]

        warning = ""
        if selected_name_candidates:
            warning = (
                f"\n\nВНИМАНИЕ: {len(selected_name_candidates)} файлов "
                "выбраны как возможные копии только по имени. "
                "Их содержимое может отличаться."
            )

        preview = "\n".join(str(path) for path in paths[:8])

        if len(paths) > 8:
            preview += f"\n... и ещё {len(paths) - 8} файлов"

        answer = messagebox.askyesno(
            "Подтверждение перемещения в Корзину",
            (
                f"Файлов: {len(paths)}\n"
                f"Общий размер: {format_size(size)}"
                f"{warning}\n\n"
                f"Список:\n{preview}\n\n"
                "Продолжить?"
            ),
            parent=self.window
        )

        if not answer:
            return

        self.delete_button.configure(state="disabled")
        self.smart_delete_button.configure(state="disabled")
        self.status.configure(text="Перемещаем файлы в Корзину...")

        deleted, failed = delete_files(paths)

        freed = sum(item.get("size", 0) for item in deleted)

        message = (
            f"Перемещено в Корзину: {len(deleted)}\n"
            f"Размер обработанных файлов: {format_size(freed)}"
        )

        if failed:
            message += f"\n\nНе удалось переместить: {len(failed)}"
            message += "\n" + "\n".join(
                f"{item['path']}: {item['error']}"
                for item in failed[:5]
            )

            if len(failed) > 5:
                message += f"\n... и ещё {len(failed) - 5}"

        messagebox.showinfo(
            "Результат",
            message,
            parent=self.window
        )

        if deleted:
            self.scan()
        else:
            self.show_results()


# ============================================================
# OPEN
# ============================================================

def open_duplicates(parent):
    DuplicateWindow(parent)
