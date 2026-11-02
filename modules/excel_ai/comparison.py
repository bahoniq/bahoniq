
from __future__ import annotations

import re
import os
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


SUPPORTED_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}


def _empty(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _display(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _key(value):
    """Нормализация ключа для сопоставления."""
    if _empty(value):
        return None

    if isinstance(value, bool):
        return str(value).casefold()

    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip().casefold()

    text = str(value).strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text.replace("ё", "е")


def _safe_title(value, existing):
    name = re.sub(r'[\\/*?:\[\]]', "_", str(value)).strip()
    name = (name or "Лист")[:31]
    used = {x.casefold() for x in existing}

    if name.casefold() not in used:
        return name

    base = name
    number = 2
    while True:
        suffix = f"_{number}"
        candidate = base[:31 - len(suffix)] + suffix
        if candidate.casefold() not in used:
            return candidate
        number += 1


def _read_book(path):
    """Возвращает листы: имя, заголовки, строки данных."""
    path = Path(path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден:\n{path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Поддерживаются форматы .xls, .xlsx и .xlsm."
        )

    result = []

    if extension == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise RuntimeError(
                "Для чтения .xls установи xlrd:\n"
                "py -3.14 -m pip install xlrd"
            ) from exc

        book = xlrd.open_workbook(str(path), on_demand=True)
        try:
            for sheet in book.sheets():
                rows = []
                for row_index in range(sheet.nrows):
                    values = []
                    for col_index in range(sheet.ncols):
                        cell = sheet.cell(row_index, col_index)
                        value = cell.value

                        if cell.ctype in (
                            xlrd.XL_CELL_EMPTY,
                            xlrd.XL_CELL_BLANK,
                        ):
                            value = None
                        elif cell.ctype == xlrd.XL_CELL_DATE:
                            try:
                                value = xlrd.xldate_as_datetime(
                                    value, book.datemode
                                )
                            except (ValueError, OverflowError):
                                pass
                        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                            value = bool(value)
                        elif cell.ctype == xlrd.XL_CELL_ERROR:
                            value = f"#XLS_ERROR_{int(value)}"
                        elif cell.ctype == xlrd.XL_CELL_NUMBER:
                            if value.is_integer():
                                value = int(value)

                        values.append(value)
                    rows.append(values)

                result.append({
                    "name": sheet.name,
                    "rows": rows,
                })
        finally:
            book.release_resources()

    else:
        book = load_workbook(
            path,
            read_only=True,
            data_only=True,
            keep_vba=False,
        )
        try:
            for sheet in book.worksheets:
                rows = [
                    list(row)
                    for row in sheet.iter_rows(values_only=True)
                ]
                result.append({
                    "name": sheet.title,
                    "rows": rows,
                })
        finally:
            book.close()

    return result


def _prepare_sheet(sheet):
    """Находит первую непустую строку как заголовок."""
    rows = sheet["rows"]
    header_index = None

    for index, row in enumerate(rows):
        if any(not _empty(value) for value in row):
            header_index = index
            break

    if header_index is None:
        return {
            "name": sheet["name"],
            "headers": [],
            "header_index": None,
            "rows": [],
        }

    raw_headers = rows[header_index]
    width = max(
        len(raw_headers),
        max((len(row) for row in rows), default=0),
    )

    headers = []
    for index in range(width):
        value = (
            raw_headers[index]
            if index < len(raw_headers)
            else None
        )
        text = _display(value).strip()
        headers.append(text or f"Столбец {index + 1}")

    data_rows = []
    for row_index in range(header_index + 1, len(rows)):
        row = list(rows[row_index])
        row.extend([None] * (width - len(row)))

        if any(not _empty(value) for value in row):
            data_rows.append({
                "excel_row": row_index + 1,
                "values": row,
            })

    return {
        "name": sheet["name"],
        "headers": headers,
        "header_index": header_index,
        "rows": data_rows,
    }


def compare_books(path1, sheet1_name, column1,
                  path2, sheet2_name, column2):
    """Сопоставляет записи по ключу, не изменяя исходные файлы."""
    path1 = Path(path1).expanduser().resolve()
    path2 = Path(path2).expanduser().resolve()

    if path1 == path2:
        raise ValueError(
            "Выбери два разных файла для сопоставления."
        )

    books1 = _read_book(path1)
    books2 = _read_book(path2)

    raw1 = next(
        (item for item in books1 if item["name"] == sheet1_name),
        None,
    )
    raw2 = next(
        (item for item in books2 if item["name"] == sheet2_name),
        None,
    )

    if raw1 is None or raw2 is None:
        raise ValueError("Не удалось найти выбранный лист.")

    data1 = _prepare_sheet(raw1)
    data2 = _prepare_sheet(raw2)

    if not data1["headers"] or not data2["headers"]:
        raise ValueError("Один из выбранных листов пуст.")

    if column1 not in data1["headers"]:
        raise ValueError("Столбец-ключ первого файла не найден.")

    if column2 not in data2["headers"]:
        raise ValueError("Столбец-ключ второго файла не найден.")

    index1 = data1["headers"].index(column1)
    index2 = data2["headers"].index(column2)

    groups1 = defaultdict(list)
    groups2 = defaultdict(list)
    blank1 = []
    blank2 = []

    for item in data1["rows"]:
        value = item["values"][index1]
        key = _key(value)
        if key is None:
            blank1.append(item)
        else:
            groups1[key].append(item)

    for item in data2["rows"]:
        value = item["values"][index2]
        key = _key(value)
        if key is None:
            blank2.append(item)
        else:
            groups2[key].append(item)

    matched = []
    only1 = []
    only2 = []
    duplicate_keys = []

    all_keys = set(groups1) | set(groups2)

    for key in sorted(all_keys):
        rows1 = groups1.get(key, [])
        rows2 = groups2.get(key, [])

        if len(rows1) > 1 or len(rows2) > 1:
            duplicate_keys.append([
                key,
                len(rows1),
                len(rows2),
                ", ".join(str(x["excel_row"]) for x in rows1),
                ", ".join(str(x["excel_row"]) for x in rows2),
                "Повторяющийся ключ; автоматически не сопоставлен",
            ])
            continue

        if rows1 and rows2:
            matched.append([
                key,
                rows1[0]["excel_row"],
                rows2[0]["excel_row"],
                *rows1[0]["values"],
                *rows2[0]["values"],
            ])
        elif rows1:
            only1.append([
                key,
                rows1[0]["excel_row"],
                *rows1[0]["values"],
            ])
        elif rows2:
            only2.append([
                key,
                rows2[0]["excel_row"],
                *rows2[0]["values"],
            ])

    blank_keys = []
    for item in blank1:
        blank_keys.append([
            "Файл 1",
            item["excel_row"],
            *item["values"],
        ])
    for item in blank2:
        blank_keys.append([
            "Файл 2",
            item["excel_row"],
            *item["values"],
        ])

    return {
        "file1": str(path1),
        "file2": str(path2),
        "sheet1": data1,
        "sheet2": data2,
        "key1": column1,
        "key2": column2,
        "matched": matched,
        "only1": only1,
        "only2": only2,
        "duplicate_keys": duplicate_keys,
        "blank_keys": blank_keys,
        "counts": {
            "matched": len(matched),
            "only1": len(only1),
            "only2": len(only2),
            "duplicate_keys": len(duplicate_keys),
            "blank_keys": len(blank_keys),
        },
    }


def _write_sheet(book, title, headers, rows):
    ws = book.create_sheet(title)
    ws.append(headers)

    for row in rows:
        ws.append([_display(value) for value in row])

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(
            fill_type="solid",
            fgColor="245A40",
        )
        cell.alignment = Alignment(
            vertical="center",
            wrap_text=True,
        )

    for column_cells in ws.columns:
        column_index = column_cells[0].column
        max_length = 0

        for cell in column_cells[:300]:
            max_length = max(
                max_length,
                len(str(cell.value or "")),
            )

        ws.column_dimensions[
            get_column_letter(column_index)
        ].width = min(max(max_length + 2, 12), 40)

    return ws


def save_report(result, output_path):
    """Создаёт отдельный XLSX-отчёт, не перезаписывая файлы."""
    output = Path(output_path).expanduser().resolve()

    if output.suffix.lower() != ".xlsx":
        raise ValueError("Отчёт должен иметь расширение .xlsx.")

    if output.exists():
        raise FileExistsError(
            f"Файл отчёта уже существует:\n{output}"
        )

    if output == Path(result["file1"]) or output == Path(result["file2"]):
        raise ValueError("Нельзя сохранять отчёт поверх исходного файла.")

    output.parent.mkdir(parents=True, exist_ok=True)

    book = Workbook()
    summary = book.active
    summary.title = "Сводка"

    summary.append(["Показатель", "Количество"])
    for label, key in [
        ("Уникальные совпадения", "matched"),
        ("Только в файле 1", "only1"),
        ("Только в файле 2", "only2"),
        ("Ключи с повторениями", "duplicate_keys"),
        ("Строки с пустым ключом", "blank_keys"),
    ]:
        summary.append([label, result["counts"][key]])

    summary.append([])
    summary.append(["Файл 1", result["file1"]])
    summary.append(["Лист 1", result["sheet1"]["name"]])
    summary.append(["Ключ 1", result["key1"]])
    summary.append(["Файл 2", result["file2"]])
    summary.append(["Лист 2", result["sheet2"]["name"]])
    summary.append(["Ключ 2", result["key2"]])

    _write_sheet(
        book,
        "Совпадения",
        [
            "Ключ",
            "Строка в файле 1",
            "Строка в файле 2",
            *[
                f"Файл 1 — {header}"
                for header in result["sheet1"]["headers"]
            ],
            *[
                f"Файл 2 — {header}"
                for header in result["sheet2"]["headers"]
            ],
        ],
        result["matched"],
    )

    _write_sheet(
        book,
        "Только файл 1",
        [
            "Ключ",
            "Строка в файле 1",
            *result["sheet1"]["headers"],
        ],
        result["only1"],
    )

    _write_sheet(
        book,
        "Только файл 2",
        [
            "Ключ",
            "Строка в файле 2",
            *result["sheet2"]["headers"],
        ],
        result["only2"],
    )

    _write_sheet(
        book,
        "Повторы ключей",
        [
            "Нормализованный ключ",
            "Количество в файле 1",
            "Количество в файле 2",
            "Строки файла 1",
            "Строки файла 2",
            "Примечание",
        ],
        result["duplicate_keys"],
    )

    _write_sheet(
        book,
        "Пустые ключи",
        [
            "Источник",
            "Строка",
            "Данные строки",
        ],
        [
            [source, row, " | ".join(values)]
            for source, row, *values in result["blank_keys"]
        ],
    )

    # Не заменяем существующий файл при публикации.
    temp_path = output.with_name(
        f".{output.stem}.bahoniq_tmp.xlsx"
    )

    if temp_path.exists():
        raise FileExistsError(
            f"Временный файл уже существует:\n{temp_path}"
        )

    try:
        book.save(temp_path)
        book.close()

        check = load_workbook(temp_path, read_only=True)
        try:
            if "Сводка" not in check.sheetnames:
                raise RuntimeError("Проверка отчёта не пройдена.")
        finally:
            check.close()

        # Режим x не перезаписывает существующий файл.
        with open(temp_path, "rb") as src, open(output, "xb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)

    except Exception:
        output.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)

    return output


class ExcelComparisonWindow(tk.Toplevel):
    """Отдельное окно сопоставления двух Excel-файлов."""

    def __init__(self, master):
        super().__init__(master)

        self.title("BahonIQ — Сопоставление Excel")
        self.geometry("900x620")
        self.minsize(760, 520)

        self.path1 = tk.StringVar()
        self.path2 = tk.StringVar()
        self.sheet1 = tk.StringVar()
        self.sheet2 = tk.StringVar()
        self.column1 = tk.StringVar()
        self.column2 = tk.StringVar()
        self.status = tk.StringVar(
            value="Выбери два Excel-файла."
        )

        self.book1 = []
        self.book2 = []
        self.last_result = None

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(
            outer,
            text="Сопоставление двух Excel-файлов",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self._file_row(
            outer, 1, "Первый файл:", self.path1,
            lambda: self._choose_file(1),
        )
        self._file_row(
            outer, 2, "Второй файл:", self.path2,
            lambda: self._choose_file(2),
        )

        ttk.Separator(outer).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=12
        )

        ttk.Label(outer, text="Лист первого файла:").grid(
            row=4, column=0, sticky="w", pady=5
        )
        self.sheet1_box = ttk.Combobox(
            outer, textvariable=self.sheet1, state="readonly"
        )
        self.sheet1_box.grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=5
        )
        self.sheet1_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._update_columns(1)
        )

        ttk.Label(outer, text="Ключевой столбец файла 1:").grid(
            row=5, column=0, sticky="w", pady=5
        )
        self.column1_box = ttk.Combobox(
            outer, textvariable=self.column1, state="readonly"
        )
        self.column1_box.grid(
            row=5, column=1, columnspan=2, sticky="ew", pady=5
        )

        ttk.Label(outer, text="Лист второго файла:").grid(
            row=6, column=0, sticky="w", pady=5
        )
        self.sheet2_box = ttk.Combobox(
            outer, textvariable=self.sheet2, state="readonly"
        )
        self.sheet2_box.grid(
            row=6, column=1, columnspan=2, sticky="ew", pady=5
        )
        self.sheet2_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._update_columns(2)
        )

        ttk.Label(outer, text="Ключевой столбец файла 2:").grid(
            row=7, column=0, sticky="w", pady=5
        )
        self.column2_box = ttk.Combobox(
            outer, textvariable=self.column2, state="readonly"
        )
        self.column2_box.grid(
            row=7, column=1, columnspan=2, sticky="ew", pady=5
        )

        ttk.Label(
            outer,
            text=(
                "Повторяющиеся ключи будут вынесены отдельно и не будут "
                "автоматически сопоставляться. Исходные файлы не изменяются."
            ),
            wraplength=780,
        ).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(12, 8)
        )

        buttons = ttk.Frame(outer)
        buttons.grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=8
        )

        ttk.Button(
            buttons,
            text="Сопоставить и сохранить отчёт",
            command=self._compare,
        ).pack(side="left")

        ttk.Label(
            outer,
            textvariable=self.status,
            relief="sunken",
            anchor="w",
        ).grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _file_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", pady=5
        )
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=8, pady=5
        )
        ttk.Button(
            parent, text="Выбрать…", command=command
        ).grid(row=row, column=2, pady=5)

    def _choose_file(self, number):
        filename = filedialog.askopenfilename(
            parent=self,
            title=f"Выбери Excel-файл {number}",
            filetypes=[
                ("Excel", "*.xls *.xlsx *.xlsm"),
                ("Все файлы", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            sheets = _read_book(filename)
            if not sheets:
                raise ValueError("В книге не найдено листов.")

            if number == 1:
                self.path1.set(filename)
                self.book1 = sheets
                self.sheet1_box["values"] = [
                    item["name"] for item in sheets
                ]
                self.sheet1.set(sheets[0]["name"])
                self._update_columns(1)
            else:
                self.path2.set(filename)
                self.book2 = sheets
                self.sheet2_box["values"] = [
                    item["name"] for item in sheets
                ]
                self.sheet2.set(sheets[0]["name"])
                self._update_columns(2)

            self.last_result = None
            self.status.set(f"Файл {number} загружен для чтения.")
        except Exception as exc:
            messagebox.showerror(
                "Ошибка чтения файла", str(exc), parent=self
            )

    def _update_columns(self, number):
        if number == 1:
            sheets = self.book1
            selected = self.sheet1.get()
            box = self.column1_box
            variable = self.column1
        else:
            sheets = self.book2
            selected = self.sheet2.get()
            box = self.column2_box
            variable = self.column2

        raw = next(
            (item for item in sheets if item["name"] == selected),
            None,
        )
        if raw is None:
            box["values"] = []
            variable.set("")
            return

        data = _prepare_sheet(raw)
        headers = data["headers"]
        box["values"] = headers
        variable.set(headers[0] if headers else "")

    def _compare(self):
        if not self.path1.get() or not self.path2.get():
            messagebox.showwarning(
                "Не выбраны файлы",
                "Выбери оба Excel-файла.",
                parent=self,
            )
            return

        if not all([
            self.sheet1.get(), self.sheet2.get(),
            self.column1.get(), self.column2.get(),
        ]):
            messagebox.showwarning(
                "Не выбраны столбцы",
                "Выбери лист и ключевой столбец для каждой книги.",
                parent=self,
            )
            return

        try:
            result = compare_books(
                self.path1.get(),
                self.sheet1.get(),
                self.column1.get(),
                self.path2.get(),
                self.sheet2.get(),
                self.column2.get(),
            )

            counts = result["counts"]
            summary = (
                "Результаты сопоставления:\n\n"
                f"Совпадения: {counts['matched']}\n"
                f"Только файл 1: {counts['only1']}\n"
                f"Только файл 2: {counts['only2']}\n"
                f"Ключи с повторениями: {counts['duplicate_keys']}\n"
                f"Строки с пустым ключом: {counts['blank_keys']}\n\n"
                "Сохранить отдельный отчёт Excel?"
            )

            if not messagebox.askyesno(
                "Подтверждение отчёта", summary, parent=self
            ):
                self.status.set("Сохранение отчёта отменено.")
                return

            output = filedialog.asksaveasfilename(
                parent=self,
                title="Сохранить отчёт сопоставления",
                defaultextension=".xlsx",
                initialfile="BahonIQ_Сопоставление.xlsx",
                filetypes=[("Excel Workbook", "*.xlsx")],
            )
            if not output:
                self.status.set("Сохранение отчёта отменено.")
                return

            saved = save_report(result, output)
            self.last_result = result
            self.status.set(f"Отчёт сохранён: {saved}")

            messagebox.showinfo(
                "Сопоставление завершено",
                f"{summary}\n\nОтчёт:\n{saved}",
                parent=self,
            )

        except Exception as exc:
            messagebox.showerror(
                "Ошибка сопоставления",
                str(exc),
                parent=self,
            )
            self.status.set("Сопоставление не завершено.")
