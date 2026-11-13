# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except (ImportError, ModuleNotFoundError):
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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
    """Нормализация ключа для произвольного сопоставления."""
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


def norm_fio(fio):
    """Нормализация ФИО для надежного сравнения (включая казахские и латинские символы)."""
    if not fio:
        return ""
    s = str(fio).strip().lower()
    s = s.replace("ё", "е").replace("і", "и").replace("ғ", "г").replace("қ", "к")
    s = s.replace("ң", "н").replace("ө", "о").replace("ұ", "у").replace("ү", "у")
    s = s.replace("һ", "х").replace("ә", "а")
    s = re.sub(r"[^a-zа-я0-9]", "", s)
    return s


def clean_iin(iin):
    """Очистка и валидация ИИН с сохранением ведущих нулей."""
    if iin is None:
        return ""
    s = str(iin).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    # Если Excel прочитал 11-значное число (обрезав ведущий ноль), восстанавливаем ноль
    if len(s) == 11 and s.isdigit():
        s = "0" + s
    return s


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
        raise ValueError("Поддерживаются форматы .xls, .xlsx и .xlsm.")

    result = []

    if extension == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise RuntimeError(
                "Для чтения .xls установи xlrd:\npy -m pip install xlrd"
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

                        if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                            value = None
                        elif cell.ctype == xlrd.XL_CELL_DATE:
                            try:
                                value = xlrd.xldate_as_datetime(value, book.datemode)
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

                result.append({"name": sheet.name, "rows": rows})
        finally:
            book.release_resources()

    else:
        book = load_workbook(path, read_only=True, data_only=True, keep_vba=False)
        try:
            for sheet in book.worksheets:
                rows = [list(row) for row in sheet.iter_rows(values_only=True)]
                result.append({"name": sheet.title, "rows": rows})
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
    width = max(len(raw_headers), max((len(row) for row in rows), default=0))

    headers = []
    for index in range(width):
        value = raw_headers[index] if index < len(raw_headers) else None
        text = _display(value).strip()
        headers.append(text or f"Столбец {index + 1}")

    data_rows = []
    for row_index in range(header_index + 1, len(rows)):
        row = list(rows[row_index])
        row.extend([None] * (width - len(row)))

        if any(not _empty(value) for value in row):
            data_rows.append({"excel_row": row_index + 1, "values": row})

    return {
        "name": sheet["name"],
        "headers": headers,
        "header_index": header_index,
        "rows": data_rows,
    }


def detect_student_columns(headers, sample_rows=None):
    """Автоматическое обнаружение ключевых столбцов студенческой базы данных."""
    iin_col = None
    fio_col = None
    last_name_col = None
    first_name_col = None
    middle_name_col = None

    for h in headers:
        hl = h.strip().lower()
        if not iin_col and re.search(r"^(иин|iin|жсн)$", hl):
            iin_col = h
        elif not iin_col and re.search(r"иин|iin|жсн", hl):
            iin_col = h
        elif not fio_col and re.search(r"^(фио|ф\.и\.о\.|студент|обучающийся|аты-жөні|fio|student|name|full.*name)$", hl):
            fio_col = h
        elif not last_name_col and re.search(r"^(фамилия|тегі|last.*name|surname)$", hl):
            last_name_col = h
        elif not first_name_col and re.search(r"^(имя|аты|first.*name)$", hl):
            first_name_col = h
        elif not middle_name_col and re.search(r"^(отчество|әкесінің.*аты|middle.*name|patronymic)$", hl):
            middle_name_col = h

    # Если ИИН по названию не найден, проверим образцы данных
    if not iin_col and sample_rows:
        for idx, h in enumerate(headers):
            digits_count = 0
            for r in sample_rows[:20]:
                val = str(r["values"][idx] or "").strip()
                if len(val) == 12 and val.isdigit():
                    digits_count += 1
            if digits_count >= 5:
                iin_col = h
                break

    is_split_fio = bool(last_name_col and first_name_col)
    return {
        "iin": iin_col,
        "fio": fio_col,
        "last_name": last_name_col,
        "first_name": first_name_col,
        "middle_name": middle_name_col,
        "is_split_fio": is_split_fio,
    }


def detect_aux_columns(headers):
    """Обнаружение вспомогательных колонок (курс, факультет, общежитие и т.д.)."""
    res = {"kurs": None, "fac_spec": None, "dorm": None, "room": None, "pay": None, "region": None}
    for h in headers:
        hl = h.strip().lower()
        if not res["kurs"] and re.search(r"^(курс|course)$", hl):
            res["kurs"] = h
        elif not res["fac_spec"] and re.search(r"(факультет|специальность|образовательная программа|оп|направление|спец)", hl):
            res["fac_spec"] = h
        elif not res["dorm"] and re.search(r"(общежити|dorm)", hl):
            res["dorm"] = h
        elif not res["room"] and re.search(r"(комнат|room)", hl):
            res["room"] = h
        elif not res["pay"] and re.search(r"(оплат|грант|платн|бюджет)", hl):
            res["pay"] = h
        elif not res["region"] and re.search(r"(область|регион|откуда|район|город)", hl):
            res["region"] = h
    return res


def reconcile_students(path1, sheet1_name, path2, sheet2_name, col_map1=None, col_map2=None):
    """
    Интеллектуальная сверка двух списков студентов.
    Сопоставляет записи по ИИН (основной ключ), а при отсутствии/невалидности ИИН —
    по нормализованному ФИО (резервный ключ).
    """
    path1 = Path(path1).expanduser().resolve()
    path2 = Path(path2).expanduser().resolve()

    if path1 == path2:
        raise ValueError("Выберите два разных файла для сверки.")

    books1 = _read_book(path1)
    books2 = _read_book(path2)

    raw1 = next((item for item in books1 if item["name"] == sheet1_name), None)
    raw2 = next((item for item in books2 if item["name"] == sheet2_name), None)

    if raw1 is None or raw2 is None:
        raise ValueError("Не удалось найти выбранный лист.")

    data1 = _prepare_sheet(raw1)
    data2 = _prepare_sheet(raw2)

    if not data1["headers"] or not data2["headers"]:
        raise ValueError("Один из выбранных листов пуст.")

    headers1 = data1["headers"]
    headers2 = data2["headers"]

    m1 = col_map1 or detect_student_columns(headers1, data1["rows"])
    m2 = col_map2 or detect_student_columns(headers2, data2["rows"])
    aux1 = detect_aux_columns(headers1)
    aux2 = detect_aux_columns(headers2)

    def extract_student_info(item, m, headers, aux):
        vals = item["values"]
        
        # ИИН
        iin = ""
        if m.get("iin") and m["iin"] in headers:
            idx = headers.index(m["iin"])
            iin = clean_iin(vals[idx])

        # ФИО
        fio = ""
        if m.get("is_split_fio") and m.get("last_name") and m.get("first_name"):
            ln_idx = headers.index(m["last_name"])
            fn_idx = headers.index(m["first_name"])
            mn_idx = headers.index(m["middle_name"]) if m.get("middle_name") and m["middle_name"] in headers else None
            parts = [vals[ln_idx], vals[fn_idx]]
            if mn_idx is not None and vals[mn_idx]:
                parts.append(vals[mn_idx])
            fio = " ".join(str(p).strip() for p in parts if p is not None and str(p).strip())
        elif m.get("fio") and m["fio"] in headers:
            fio = str(vals[headers.index(m["fio"])] or "").strip()
        else:
            fio = str(vals[0] or "").strip()

        kurs = str(vals[headers.index(aux["kurs"])] or "") if aux.get("kurs") and aux["kurs"] in headers else ""
        fac_spec = str(vals[headers.index(aux["fac_spec"])] or "") if aux.get("fac_spec") and aux["fac_spec"] in headers else ""
        dorm = str(vals[headers.index(aux["dorm"])] or "") if aux.get("dorm") and aux["dorm"] in headers else ""
        room = str(vals[headers.index(aux["room"])] or "") if aux.get("room") and aux["room"] in headers else ""
        pay = str(vals[headers.index(aux["pay"])] or "") if aux.get("pay") and aux["pay"] in headers else ""
        region = str(vals[headers.index(aux["region"])] or "") if aux.get("region") and aux["region"] in headers else ""

        return {
            "excel_row": item["excel_row"],
            "values": vals,
            "iin": iin,
            "fio": fio,
            "norm_fio": norm_fio(fio),
            "kurs": kurs,
            "fac_spec": fac_spec,
            "dorm": dorm,
            "room": room,
            "pay": pay,
            "region": region,
        }

    students1 = [extract_student_info(r, m1, headers1, aux1) for r in data1["rows"]]
    students2 = [extract_student_info(r, m2, headers2, aux2) for r in data2["rows"]]

    f1_by_iin = {}
    f1_by_fio = {}
    f1_iin_duplicates = defaultdict(list)
    f2_iin_duplicates = defaultdict(list)

    for idx, s in enumerate(students1):
        iin = s["iin"]
        if iin and iin != "000000000000" and len(iin) == 12:
            if iin in f1_by_iin:
                f1_iin_duplicates[iin].append(idx)
            else:
                f1_by_iin[iin] = idx
        if s["norm_fio"]:
            f1_by_fio[s["norm_fio"]] = idx

    f2_seen_iin = {}
    for idx, s in enumerate(students2):
        iin = s["iin"]
        if iin and iin != "000000000000" and len(iin) == 12:
            if iin in f2_seen_iin:
                f2_iin_duplicates[iin].append(idx)
            else:
                f2_seen_iin[iin] = idx

    matched_pairs = []
    matched_f1_idx = set()
    matched_f2_idx = set()
    only2 = []

    for idx2, s2 in enumerate(students2):
        iin2 = s2["iin"]
        nfio2 = s2["norm_fio"]
        matched_idx1 = None

        if iin2 and iin2 != "000000000000" and len(iin2) == 12 and iin2 in f1_by_iin:
            matched_idx1 = f1_by_iin[iin2]
        elif nfio2 and nfio2 in f1_by_fio:
            matched_idx1 = f1_by_fio[nfio2]

        if matched_idx1 is not None and matched_idx1 not in matched_f1_idx:
            matched_pairs.append((students1[matched_idx1], s2))
            matched_f1_idx.add(matched_idx1)
            matched_f2_idx.add(idx2)
        else:
            only2.append(s2)

    only1 = [s1 for idx1, s1 in enumerate(students1) if idx1 not in matched_f1_idx]

    return {
        "file1": str(path1),
        "file2": str(path2),
        "sheet1": data1,
        "sheet2": data2,
        "m1": m1,
        "m2": m2,
        "matched": matched_pairs,
        "only1": only1,
        "only2": only2,
        "f1_iin_duplicates": f1_iin_duplicates,
        "f2_iin_duplicates": f2_iin_duplicates,
        "counts": {
            "total1": len(students1),
            "total2": len(students2),
            "matched": len(matched_pairs),
            "only1": len(only1),
            "only2": len(only2),
            "unique_total": len(only1) + len(only2),
        },
    }


def save_student_reconciliation_report(result, output_path):
    """Создает презентабельный XLSX-отчет по сверке студентов с 5 вкладками."""
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".xlsx":
        raise ValueError("Отчёт должен иметь расширение .xlsx.")

    if output.exists():
        try:
            output.unlink()
        except Exception as e:
            raise PermissionError(f"Файл занят или открыт в другой программе:\n{output}") from e

    output.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    font_title = Font(name="Calibri", size=16, bold=True, color="1F4E78")
    font_subtitle = Font(name="Calibri", size=11, italic=True, color="595959")
    font_section = Font(name="Calibri", size=13, bold=True, color="1F4E78")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=11)
    font_bold = Font(name="Calibri", size=11, bold=True)

    fill_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFC", end_color="F9FAFC", fill_type="solid")
    fill_kpi = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    fill_warn = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    fill_accent1 = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    fill_accent2 = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    border_header = Border(
        left=Side(style="thin", color="FFFFFF"),
        right=Side(style="thin", color="FFFFFF"),
        top=Side(style="medium", color="1F4E78"),
        bottom=Side(style="medium", color="1F4E78"),
    )
    border_box = Border(
        left=Side(style="medium", color="1F4E78"),
        right=Side(style="medium", color="1F4E78"),
        top=Side(style="medium", color="1F4E78"),
        bottom=Side(style="medium", color="1F4E78"),
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

    counts = result["counts"]
    c_tot1 = counts["total1"]
    c_tot2 = counts["total2"]
    c_match = counts["matched"]
    c_only1 = counts["only1"]
    c_only2 = counts["only2"]
    c_uniq = counts["unique_total"]

    # ==================== ЛИСТ 1: СВОДКА СВЕРКИ ====================
    ws_sum = wb.create_sheet("Сводка сверки")
    ws_sum.views.sheetView[0].showGridLines = True

    ws_sum["B2"] = "ОТЧЕТ ПО СВЕРКЕ СПИСКОВ СТУДЕНТОВ"
    ws_sum["B2"].font = font_title
    f1_name = Path(result["file1"]).name
    f2_name = Path(result["file2"]).name
    ws_sum["B3"] = f'Сравнение файлов: "{f1_name}" ({c_tot1} ст.) и "{f2_name}" ({c_tot2} ст.)'
    ws_sum["B3"].font = font_subtitle

    kpis = [
        ("B5", "C6", "Файл 1 (исходный)", f"{c_tot1:,}".replace(",", " "), "Всего в файле 1"),
        ("D5", "E6", "Файл 2 (сверяемый)", f"{c_tot2:,}".replace(",", " "), "Всего в файле 2"),
        ("F5", "G6", "Совпали в обоих", f"{c_match:,}".replace(",", " "), f"{c_match/c_tot1*100:.1f}% от Файла 1" if c_tot1 else ""),
        ("H5", "I6", "НЕ повторяются (всего)", f"{c_uniq:,}".replace(",", " "), "Уникальны для одного списка"),
    ]

    for top_l, bot_r, label, val, sub in kpis:
        c1_let, r1 = top_l[0], int(top_l[1])
        c2_let, r2 = bot_r[0], int(bot_r[1])
        ws_sum.merge_cells(f"{top_l}:{bot_r}")
        cell = ws_sum[top_l]
        cell.value = f"{label}\n{val}\n({sub})"
        cell.font = Font(name="Calibri", size=11, bold=True, color="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = fill_kpi

        for row in range(r1, r2 + 1):
            for col_letter in [c1_let, c2_let]:
                ws_sum[f"{col_letter}{row}"].border = border_box

    ws_sum["B8"] = "Детализация сверки контингента"
    ws_sum["B8"].font = font_section

    table_headers = ["Показатель", "Количество", "% от Файла 1", "% от Файла 2", "Лист с деталями"]
    for col_idx, th in enumerate(table_headers, start=2):
        cell = ws_sum.cell(row=10, column=col_idx, value=th)
        cell.font = font_header
        cell.fill = fill_navy
        cell.alignment = align_header
        cell.border = border_header
    ws_sum.row_dimensions[10].height = 26

    table_data = [
        (f"Всего студентов в Файле 1 ({f1_name})", c_tot1, "100.0%", f"{c_tot1/c_tot2*100:.1f}%" if c_tot2 else "-", "Исходный файл 1"),
        (f"Всего студентов в Файле 2 ({f2_name})", c_tot2, f"{c_tot2/c_tot1*100:.1f}%" if c_tot1 else "-", "100.0%", "Исходный файл 2"),
        ("Совпали в обоих списках (есть и в 1, и в 2)", c_match, f"{c_match/c_tot1*100:.1f}%" if c_tot1 else "-", f"{c_match/c_tot2*100:.1f}%" if c_tot2 else "-", 'Лист "Совпавшие_студенты"'),
        ("НЕ ПОВТОРЯЮТСЯ (всего уникальных записей)", c_uniq, f"{c_uniq/c_tot1*100:.1f}%" if c_tot1 else "-", f"{c_uniq/c_tot2*100:.1f}%" if c_tot2 else "-", 'Лист "Все_неповторяющиеся"'),
        ("   • Есть только в Файле 1 (отсутствуют в Файле 2)", c_only1, f"{c_only1/c_tot1*100:.1f}%" if c_tot1 else "-", "-", 'Лист "Только_в_Файле_1"'),
        ("   • Есть только в Файле 2 (отсутствуют в Файле 1)", c_only2, "-", f"{c_only2/c_tot2*100:.1f}%" if c_tot2 else "-", 'Лист "Только_в_Файле_2"'),
    ]

    for row_offset, row_vals in enumerate(table_data, start=11):
        ws_sum.row_dimensions[row_offset].height = 22
        for col_idx, val in enumerate(row_vals, start=2):
            cell = ws_sum.cell(row=row_offset, column=col_idx, value=val)
            cell.font = font_bold if row_offset in (13, 14) else font_data
            cell.border = border_thin
            if row_offset == 14:
                cell.fill = fill_warn
            elif row_offset % 2 == 1:
                cell.fill = fill_zebra

            if col_idx == 2:
                cell.alignment = align_left
            elif col_idx == 3:
                cell.alignment = align_right
                cell.number_format = "#,##0"
            else:
                cell.alignment = align_center

    ws_sum["B18"] = "Методология и правила сверки:"
    ws_sum["B18"].font = Font(name="Calibri", size=11, bold=True, color="1F4E78")
    notes = [
        "1. Основной ключ сверки: ИИН студента (12 цифр с сохранением ведущих нулей).",
        "2. Резервный ключ: нормализованное ФИО (для студентов без ИИН или с условным кодом).",
        "3. Все несовпадающие студенты вынесены в единый реестр на листе «Все_неповторяющиеся», а также подробно на листах «Только_в_Файле_1» и «Только_в_Файле_2».",
        "4. Исходные файлы не изменялись, сверка произведена в режиме безопасного чтения.",
    ]
    for idx, note in enumerate(notes, start=19):
        ws_sum.cell(row=idx, column=2, value=note).font = font_data

    ws_sum.column_dimensions["A"].width = 3
    ws_sum.column_dimensions["B"].width = 54
    ws_sum.column_dimensions["C"].width = 18
    ws_sum.column_dimensions["D"].width = 16
    ws_sum.column_dimensions["E"].width = 16
    ws_sum.column_dimensions["F"].width = 30
    ws_sum.column_dimensions["G"].width = 16
    ws_sum.column_dimensions["H"].width = 24
    ws_sum.column_dimensions["I"].width = 12

    def format_table_sheet(ws, headers, rows):
        ws.views.sheetView[0].showGridLines = True
        ws.row_dimensions[1].height = 28

        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_navy
            cell.alignment = align_header
            cell.border = border_header

        for r_idx, row_values in enumerate(rows, start=2):
            ws.row_dimensions[r_idx].height = 20
            is_odd = (r_idx % 2 == 1)
            for col_idx, val in enumerate(row_values, start=1):
                cell = ws.cell(row=r_idx, column=col_idx, value=_display(val) if val is not None else "")
                cell.font = font_data
                cell.border = border_thin
                if is_odd:
                    cell.fill = fill_zebra

                h_name = headers[col_idx - 1]
                if h_name in ("№", "Курс", "Комната", "Пол", "Источник"):
                    cell.alignment = align_center
                elif h_name == "ИИН":
                    cell.alignment = align_center
                    cell.number_format = "@"
                else:
                    cell.alignment = align_left

        if rows:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
        ws.freeze_panes = "A2"

        for col_idx, h in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            max_len = len(str(h))
            for r in rows[:150]:
                val = r[col_idx - 1]
                if val is not None:
                    max_len = max(max_len, len(str(val)))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 45)

    # ==================== ЛИСТ 2: ВСЕ НЕПОВТОРЯЮЩИЕСЯ ====================
    ws_all_uniq = wb.create_sheet("Все_неповторяющиеся")
    h_all_uniq = [
        "№", "Источник", "ФИО", "ИИН", "Курс",
        "Факультет / Специальность", "Общежитие / Комната",
        "Обеспеченность общ. / Форма оплаты", "Регион / Примечание"
    ]
    rows_all_uniq = []
    num = 1
    for s1 in result["only1"]:
        dorm_str = s1["dorm"] or "-"
        reg_str = s1["region"] or "-"
        rows_all_uniq.append([
            num, f"Только в Файле 1 ({f1_name})", s1["fio"], s1["iin"], s1["kurs"],
            s1["fac_spec"], dorm_str, s1["pay"] or "-", reg_str
        ])
        num += 1

    for s2 in result["only2"]:
        dorm_parts = [p for p in [s2["dorm"], (f"комн. {s2['room']}" if s2["room"] else "")] if p]
        dorm_str = ", ".join(dorm_parts) if dorm_parts else "-"
        rows_all_uniq.append([
            num, f"Только в Файле 2 ({f2_name})", s2["fio"], s2["iin"], s2["kurs"],
            s2["fac_spec"], dorm_str, s2["pay"] or "-", s2["region"] or "-"
        ])
        num += 1

    format_table_sheet(ws_all_uniq, h_all_uniq, rows_all_uniq)

    for row_idx in range(2, len(rows_all_uniq) + 2):
        cell_src = ws_all_uniq.cell(row=row_idx, column=2)
        if "Файле 1" in str(cell_src.value):
            cell_src.fill = fill_accent1
        else:
            cell_src.fill = fill_accent2

    # ==================== ЛИСТ 3: ТОЛЬКО В ФАЙЛЕ 1 ====================
    ws_only1 = wb.create_sheet("Только_в_Файле_1")
    h_only1 = ["№", "ФИО (определено)", "ИИН (определен)", *result["sheet1"]["headers"]]
    rows_only1 = []
    for idx, s1 in enumerate(result["only1"], start=1):
        rows_only1.append([idx, s1["fio"], s1["iin"], *s1["values"]])
    format_table_sheet(ws_only1, h_only1, rows_only1)

    # ==================== ЛИСТ 4: ТОЛЬКО В ФАЙЛЕ 2 ====================
    ws_only2 = wb.create_sheet("Только_в_Файле_2")
    h_only2 = ["№", "ФИО (определено)", "ИИН (определен)", *result["sheet2"]["headers"]]
    rows_only2 = []
    for idx, s2 in enumerate(result["only2"], start=1):
        rows_only2.append([idx, s2["fio"], s2["iin"], *s2["values"]])
    format_table_sheet(ws_only2, h_only2, rows_only2)

    # ==================== ЛИСТ 5: СОВПАВШИЕ СТУДЕНТЫ ====================
    ws_match = wb.create_sheet("Совпавшие_студенты")
    h_match = [
        "№", "ФИО (Файл 1)", "ФИО (Файл 2)", "ИИН", "Курс",
        "Факультет / Специальность 1", "Специальность 2",
        "Общежитие", "Комната", "Оплата"
    ]
    rows_match = []
    for idx, (s1, s2) in enumerate(result["matched"], start=1):
        iin_val = s1["iin"] or s2["iin"] or ""
        kurs_val = s2["kurs"] or s1["kurs"] or ""
        dorm_val = s2["dorm"] or s1["dorm"] or ""
        room_val = s2["room"] or ""
        pay_val = s2["pay"] or s1["pay"] or ""
        rows_match.append([
            idx, s1["fio"], s2["fio"], iin_val, kurs_val,
            s1["fac_spec"], s2["fac_spec"], dorm_val, room_val, pay_val
        ])
    format_table_sheet(ws_match, h_match, rows_match)

    temp_path = output.with_name(f".{output.stem}.bahoniq_tmp.xlsx")
    if temp_path.exists():
        temp_path.unlink(missing_ok=True)

    try:
        wb.save(temp_path)
        wb.close()

        check = load_workbook(temp_path, read_only=True)
        try:
            if "Сводка сверки" not in check.sheetnames:
                raise RuntimeError("Проверка сгенерированного отчёта не пройдена.")
        finally:
            check.close()

        with open(temp_path, "rb") as src, open(output, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    finally:
        temp_path.unlink(missing_ok=True)

    return output


# ==================== СТАНДАРТНОЕ СОПОСТАВЛЕНИЕ (КЛАССИЧЕСКОЕ) ====================

def compare_books(path1, sheet1_name, column1, path2, sheet2_name, column2):
    """Сопоставляет записи по одному ключу (универсальный режим)."""
    path1 = Path(path1).expanduser().resolve()
    path2 = Path(path2).expanduser().resolve()

    if path1 == path2:
        raise ValueError("Выбери два разных файла для сопоставления.")

    books1 = _read_book(path1)
    books2 = _read_book(path2)

    raw1 = next((item for item in books1 if item["name"] == sheet1_name), None)
    raw2 = next((item for item in books2 if item["name"] == sheet2_name), None)

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
            matched.append([key, rows1[0]["excel_row"], rows2[0]["excel_row"], *rows1[0]["values"], *rows2[0]["values"]])
        elif rows1:
            only1.append([key, rows1[0]["excel_row"], *rows1[0]["values"]])
        elif rows2:
            only2.append([key, rows2[0]["excel_row"], *rows2[0]["values"]])

    blank_keys = []
    for item in blank1:
        blank_keys.append(["Файл 1", item["excel_row"], *item["values"]])
    for item in blank2:
        blank_keys.append(["Файл 2", item["excel_row"], *item["values"]])

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
        cell.fill = PatternFill(fill_type="solid", fgColor="245A40")
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    for column_cells in ws.columns:
        column_index = column_cells[0].column
        max_length = 0
        for cell in column_cells[:300]:
            max_length = max(max_length, len(str(cell.value or "")))
        ws.column_dimensions[get_column_letter(column_index)].width = min(max(max_length + 2, 12), 40)

    return ws


def save_report(result, output_path):
    """Классический отчет для универсального сопоставления по одному столбцу."""
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".xlsx":
        raise ValueError("Отчёт должен иметь расширение .xlsx.")

    if output.exists():
        try:
            output.unlink()
        except Exception as e:
            raise PermissionError(f"Файл уже существует и заблокирован:\n{output}") from e

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

    _write_sheet(book, "Совпадения", ["Ключ", "Строка в файле 1", "Строка в файле 2", *[f"Файл 1 — {h}" for h in result["sheet1"]["headers"]], *[f"Файл 2 — {h}" for h in result["sheet2"]["headers"]]], result["matched"])
    _write_sheet(book, "Только файл 1", ["Ключ", "Строка в файле 1", *result["sheet1"]["headers"]], result["only1"])
    _write_sheet(book, "Только файл 2", ["Ключ", "Строка в файле 2", *result["sheet2"]["headers"]], result["only2"])
    _write_sheet(book, "Повторы ключей", ["Нормализованный ключ", "Количество в файле 1", "Количество в файле 2", "Строки файла 1", "Строки файла 2", "Примечание"], result["duplicate_keys"])
    _write_sheet(book, "Пустые ключи", ["Источник", "Строка", "Данные строки"], [[s, r, " | ".join(str(v or "") for v in vals)] for s, r, *vals in result["blank_keys"]])

    temp_path = output.with_name(f".{output.stem}.bahoniq_tmp.xlsx")
    if temp_path.exists():
        temp_path.unlink(missing_ok=True)

    try:
        book.save(temp_path)
        book.close()

        check = load_workbook(temp_path, read_only=True)
        try:
            if "Сводка" not in check.sheetnames:
                raise RuntimeError("Проверка отчёта не пройдена.")
        finally:
            check.close()

        with open(temp_path, "rb") as src, open(output, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    finally:
        temp_path.unlink(missing_ok=True)

    return output


# ==================== ОКНО ИНТЕРФЕЙСА BAHONIQ ====================

_BaseTopLevel = tk.Toplevel if tk is not None else object

class ExcelComparisonWindow(_BaseTopLevel):
    """Окно сверки студентов и сопоставления Excel-файлов в BahonIQ."""

    def __init__(self, master=None):
        if tk is None:
            raise RuntimeError("Графический интерфейс Tkinter недоступен в headless-окружении (веб-сервер).")
        super().__init__(master)

        self.title("BahonIQ — Сверка студентов и сопоставление Excel")
        self.geometry("960x680")
        self.minsize(800, 560)

        self.mode = tk.StringVar(value="students")  # 'students' или 'single_column'
        self.path1 = tk.StringVar()
        self.path2 = tk.StringVar()
        self.sheet1 = tk.StringVar()
        self.sheet2 = tk.StringVar()
        self.column1 = tk.StringVar()
        self.column2 = tk.StringVar()

        # Параметры сверки студентов
        self.student_iin1 = tk.StringVar()
        self.student_fio1 = tk.StringVar()
        self.student_iin2 = tk.StringVar()
        self.student_fio2 = tk.StringVar()

        self.status = tk.StringVar(value="Выберите два Excel-файла для сверки.")

        self.book1 = []
        self.book2 = []
        self.last_result = None

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        # Header Title
        title_frame = ttk.Frame(outer)
        title_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Label(
            title_frame,
            text="Сверка и сопоставление Excel-файлов",
            font=("Segoe UI", 16, "bold"),
            foreground="#1F4E78",
        ).pack(side="left")

        # Mode Selector
        mode_frame = ttk.LabelFrame(outer, text="  Режим работы  ", padding=(12, 8))
        mode_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12))

        ttk.Radiobutton(
            mode_frame,
            text="Сверка студентов (интеллектуально: по ИИН + ФИО)",
            variable=self.mode,
            value="students",
            command=self._on_mode_change,
        ).pack(side="left", padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="Произвольное сопоставление (по одному выбранному столбцу)",
            variable=self.mode,
            value="single_column",
            command=self._on_mode_change,
        ).pack(side="left")

        # Files selection rows
        self._file_row(outer, 2, "Первый файл:", self.path1, lambda: self._choose_file(1))
        self._file_row(outer, 3, "Второй файл:", self.path2, lambda: self._choose_file(2))

        ttk.Separator(outer).grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)

        # Container for dynamic parameter controls
        self.params_container = ttk.Frame(outer)
        self.params_container.grid(row=5, column=0, columnspan=3, sticky="ew")
        self.params_container.columnconfigure(1, weight=1)

        self._build_students_mode_ui()
        self._build_single_column_mode_ui()

        # Bottom info and actions
        self.hint_label = ttk.Label(
            outer,
            text="",
            wraplength=880,
            foreground="#475569",
            font=("Segoe UI", 9),
        )
        self.hint_label.grid(row=6, column=0, columnspan=3, sticky="w", pady=(12, 8))

        buttons = ttk.Frame(outer)
        buttons.grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)

        self.action_btn = ttk.Button(
            buttons,
            text="Сверить студентов и сохранить отчёт",
            command=self._compare,
        )
        self.action_btn.pack(side="left", ipady=4, ipadx=10)

        # Status Bar
        ttk.Label(
            outer,
            textvariable=self.status,
            relief="sunken",
            anchor="w",
            padding=(8, 4),
        ).grid(row=8, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        self._on_mode_change()

    def _build_students_mode_ui(self):
        self.students_frame = ttk.LabelFrame(self.params_container, text="  Параметры сверки студентов  ", padding=12)
        self.students_frame.columnconfigure(1, weight=1)
        self.students_frame.columnconfigure(3, weight=1)

        # File 1 column
        f1_box = ttk.LabelFrame(self.students_frame, text=" Файл 1 ", padding=10)
        f1_box.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=4)
        f1_box.columnconfigure(1, weight=1)

        ttk.Label(f1_box, text="Лист:").grid(row=0, column=0, sticky="w", pady=3)
        self.st_sheet1_box = ttk.Combobox(f1_box, textvariable=self.sheet1, state="readonly")
        self.st_sheet1_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.st_sheet1_box.bind("<<ComboboxSelected>>", lambda _e: self._auto_detect_student_cols(1))

        ttk.Label(f1_box, text="Столбец ИИН:").grid(row=1, column=0, sticky="w", pady=3)
        self.st_iin1_box = ttk.Combobox(f1_box, textvariable=self.student_iin1, state="readonly")
        self.st_iin1_box.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Label(f1_box, text="Столбец ФИО:").grid(row=2, column=0, sticky="w", pady=3)
        self.st_fio1_box = ttk.Combobox(f1_box, textvariable=self.student_fio1, state="readonly")
        self.st_fio1_box.grid(row=2, column=1, sticky="ew", pady=3)

        # File 2 column
        f2_box = ttk.LabelFrame(self.students_frame, text=" Файл 2 ", padding=10)
        f2_box.grid(row=0, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=4)
        f2_box.columnconfigure(1, weight=1)

        ttk.Label(f2_box, text="Лист:").grid(row=0, column=0, sticky="w", pady=3)
        self.st_sheet2_box = ttk.Combobox(f2_box, textvariable=self.sheet2, state="readonly")
        self.st_sheet2_box.grid(row=0, column=1, sticky="ew", pady=3)
        self.st_sheet2_box.bind("<<ComboboxSelected>>", lambda _e: self._auto_detect_student_cols(2))

        ttk.Label(f2_box, text="Столбец ИИН:").grid(row=1, column=0, sticky="w", pady=3)
        self.st_iin2_box = ttk.Combobox(f2_box, textvariable=self.student_iin2, state="readonly")
        self.st_iin2_box.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Label(f2_box, text="Столбец ФИО:").grid(row=2, column=0, sticky="w", pady=3)
        self.st_fio2_box = ttk.Combobox(f2_box, textvariable=self.student_fio2, state="readonly")
        self.st_fio2_box.grid(row=2, column=1, sticky="ew", pady=3)

    def _build_single_column_mode_ui(self):
        self.single_frame = ttk.LabelFrame(self.params_container, text="  Настройка сопоставления по одному столбцу  ", padding=12)
        self.single_frame.columnconfigure(1, weight=1)

        ttk.Label(self.single_frame, text="Лист первого файла:").grid(row=0, column=0, sticky="w", pady=4)
        self.sheet1_box = ttk.Combobox(self.single_frame, textvariable=self.sheet1, state="readonly")
        self.sheet1_box.grid(row=0, column=1, sticky="ew", pady=4)
        self.sheet1_box.bind("<<ComboboxSelected>>", lambda _e: self._update_columns(1))

        ttk.Label(self.single_frame, text="Ключевой столбец файла 1:").grid(row=1, column=0, sticky="w", pady=4)
        self.column1_box = ttk.Combobox(self.single_frame, textvariable=self.column1, state="readonly")
        self.column1_box.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(self.single_frame, text="Лист второго файла:").grid(row=2, column=0, sticky="w", pady=4)
        self.sheet2_box = ttk.Combobox(self.single_frame, textvariable=self.sheet2, state="readonly")
        self.sheet2_box.grid(row=2, column=1, sticky="ew", pady=4)
        self.sheet2_box.bind("<<ComboboxSelected>>", lambda _e: self._update_columns(2))

        ttk.Label(self.single_frame, text="Ключевой столбец файла 2:").grid(row=3, column=0, sticky="w", pady=4)
        self.column2_box = ttk.Combobox(self.single_frame, textvariable=self.column2, state="readonly")
        self.column2_box.grid(row=3, column=1, sticky="ew", pady=4)

    def _on_mode_change(self):
        mode = self.mode.get()
        if mode == "students":
            self.single_frame.pack_forget()
            self.students_frame.pack(fill="x", expand=True)
            self.action_btn.config(text="Сверить студентов и сохранить отчёт")
            self.hint_label.config(
                text="ℹ️ Режим «Сверка студентов»: сопоставление выполняется сначала по 12-значному ИИН (с сохранением нулей), а для записей без ИИН — по нормализованному ФИО (с поддержкой казахских и латинских символов). Автоматически склеивает раздельные фамилию, имя и отчество."
            )
            if self.book1:
                self._auto_detect_student_cols(1)
            if self.book2:
                self._auto_detect_student_cols(2)
        else:
            self.students_frame.pack_forget()
            self.single_frame.pack(fill="x", expand=True)
            self.action_btn.config(text="Сопоставить и сохранить отчёт")
            self.hint_label.config(
                text="ℹ️ Произвольное сопоставление: сопоставляет строки двух таблиц по одному выбранному столбцу. Повторяющиеся и пустые ключи выводятся на отдельные вкладки."
            )
            if self.book1:
                self._update_columns(1)
            if self.book2:
                self._update_columns(2)

    def _file_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(parent, text="Выбрать…", command=command).grid(row=row, column=2, pady=5)

    def _choose_file(self, number):
        filename = filedialog.askopenfilename(
            parent=self,
            title=f"Выберите Excel-файл {number}",
            filetypes=[("Excel", "*.xls *.xlsx *.xlsm"), ("Все файлы", "*.*")],
        )
        if not filename:
            return

        try:
            sheets = _read_book(filename)
            if not sheets:
                raise ValueError("В книге не найдено листов.")

            sheet_names = [item["name"] for item in sheets]

            if number == 1:
                self.path1.set(filename)
                self.book1 = sheets
                self.sheet1_box["values"] = sheet_names
                self.st_sheet1_box["values"] = sheet_names
                self.sheet1.set(sheet_names[0])
                if self.mode.get() == "students":
                    self._auto_detect_student_cols(1)
                else:
                    self._update_columns(1)
            else:
                self.path2.set(filename)
                self.book2 = sheets
                self.sheet2_box["values"] = sheet_names
                self.st_sheet2_box["values"] = sheet_names
                self.sheet2.set(sheet_names[0])
                if self.mode.get() == "students":
                    self._auto_detect_student_cols(2)
                else:
                    self._update_columns(2)

            self.last_result = None
            self.status.set(f"Файл {number} успешно загружен: {Path(filename).name}")
        except Exception as exc:
            messagebox.showerror("Ошибка чтения файла", str(exc), parent=self)

    def _auto_detect_student_cols(self, number):
        sheets = self.book1 if number == 1 else self.book2
        selected_sheet = self.sheet1.get() if number == 1 else self.sheet2.get()
        iin_var = self.student_iin1 if number == 1 else self.student_iin2
        fio_var = self.student_fio1 if number == 1 else self.student_fio2
        iin_box = self.st_iin1_box if number == 1 else self.st_iin2_box
        fio_box = self.st_fio1_box if number == 1 else self.st_fio2_box

        raw = next((item for item in sheets if item["name"] == selected_sheet), None)
        if raw is None:
            return

        data = _prepare_sheet(raw)
        headers = data["headers"]

        iin_options = ["(нет ИИН)"] + headers
        iin_box["values"] = iin_options

        fio_options = ["(авто / Фамилия + Имя + Отчество)"] + headers
        fio_box["values"] = fio_options

        det = detect_student_columns(headers, data["rows"])

        if det.get("iin"):
            iin_var.set(det["iin"])
        else:
            iin_var.set("(нет ИИН)")

        if det.get("is_split_fio"):
            fio_var.set("(авто / Фамилия + Имя + Отчество)")
        elif det.get("fio"):
            fio_var.set(det["fio"])
        else:
            fio_var.set(headers[0] if headers else "(авто / Фамилия + Имя + Отчество)")

    def _update_columns(self, number):
        sheets = self.book1 if number == 1 else self.book2
        selected = self.sheet1.get() if number == 1 else self.sheet2.get()
        box = self.column1_box if number == 1 else self.column2_box
        variable = self.column1 if number == 1 else self.column2

        raw = next((item for item in sheets if item["name"] == selected), None)
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
            messagebox.showwarning("Не выбраны файлы", "Выберите оба Excel-файла для сопоставления.", parent=self)
            return

        if not self.sheet1.get() or not self.sheet2.get():
            messagebox.showwarning("Не выбраны листы", "Выберите лист для каждой книги.", parent=self)
            return

        if self.mode.get() == "students":
            self._do_student_reconciliation()
        else:
            self._do_classic_comparison()

    def _do_student_reconciliation(self):
        try:
            self.status.set("Выполняется сверка студентов…")
            self.update_idletasks()

            def build_col_map(iin_str, fio_str, sheet_obj):
                headers = sheet_obj["headers"]
                det = detect_student_columns(headers, sheet_obj["rows"])
                m = det.copy()
                if iin_str != "(нет ИИН)" and iin_str in headers:
                    m["iin"] = iin_str
                elif iin_str == "(нет ИИН)":
                    m["iin"] = None

                if fio_str == "(авто / Фамилия + Имя + Отчество)":
                    m["is_split_fio"] = True
                    if not (m.get("last_name") and m.get("first_name")):
                        det2 = detect_student_columns(headers)
                        m["last_name"] = det2.get("last_name") or headers[0]
                        m["first_name"] = det2.get("first_name") or (headers[1] if len(headers) > 1 else headers[0])
                        m["middle_name"] = det2.get("middle_name")
                elif fio_str in headers:
                    m["is_split_fio"] = False
                    m["fio"] = fio_str
                return m

            b1 = _read_book(self.path1.get())
            b2 = _read_book(self.path2.get())
            raw1 = next((item for item in b1 if item["name"] == self.sheet1.get()), None)
            raw2 = next((item for item in b2 if item["name"] == self.sheet2.get()), None)
            d1 = _prepare_sheet(raw1)
            d2 = _prepare_sheet(raw2)

            map1 = build_col_map(self.student_iin1.get(), self.student_fio1.get(), d1)
            map2 = build_col_map(self.student_iin2.get(), self.student_fio2.get(), d2)

            result = reconcile_students(
                self.path1.get(), self.sheet1.get(),
                self.path2.get(), self.sheet2.get(),
                col_map1=map1, col_map2=map2,
            )

            counts = result["counts"]
            f1_name = Path(self.path1.get()).name
            f2_name = Path(self.path2.get()).name

            summary = (
                "Итоги сверки студентов:\n\n"
                f"• Всего в Файле 1 ({f1_name}): {counts['total1']:,}\n"
                f"• Всего в Файле 2 ({f2_name}): {counts['total2']:,}\n"
                f"• Совпали в обоих списках: {counts['matched']:,}\n\n"
                f"⚡ НЕ ПОВТОРЯЮТСЯ (всего): {counts['unique_total']:,}\n"
                f"   ↳ Только в Файле 1: {counts['only1']:,}\n"
                f"   ↳ Только в Файле 2: {counts['only2']:,}\n\n"
                "Сохранить подробный отчет Excel?"
            ).replace(",", " ")

            if not messagebox.askyesno("Подтверждение сохранения", summary, parent=self):
                self.status.set("Сохранение отчёта отменено пользователем.")
                return

            init_name = f"Сверка_студентов_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
            init_dir = str(Path(self.path1.get()).parent)
            output = filedialog.asksaveasfilename(
                parent=self,
                title="Сохранить отчёт сверки студентов",
                defaultextension=".xlsx",
                initialdir=init_dir,
                initialfile=init_name,
                filetypes=[("Excel Workbook", "*.xlsx")],
            )
            if not output:
                self.status.set("Сохранение отчёта отменено.")
                return

            saved = save_student_reconciliation_report(result, output)
            self.last_result = result
            self.status.set(f"Отчёт сверки сохранён: {saved}")

            if messagebox.askyesno("Сверка завершена", f"Отчёт успешно сохранён:\n{saved}\n\nОткрыть готовый файл Excel прямо сейчас?", parent=self):
                try:
                    os.startfile(str(saved))
                except Exception:
                    pass

        except Exception as exc:
            messagebox.showerror("Ошибка сверки студентов", str(exc), parent=self)
            self.status.set("Ошибка сверки студентов.")

    def _do_classic_comparison(self):
        if not self.column1.get() or not self.column2.get():
            messagebox.showwarning("Не выбраны столбцы", "Выберите ключевой столбец для каждой книги.", parent=self)
            return

        try:
            self.status.set("Выполняется сопоставление по ключу…")
            self.update_idletasks()

            result = compare_books(
                self.path1.get(), self.sheet1.get(), self.column1.get(),
                self.path2.get(), self.sheet2.get(), self.column2.get(),
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

            if not messagebox.askyesno("Подтверждение отчёта", summary, parent=self):
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

            if messagebox.askyesno("Сопоставление завершено", f"{summary}\n\nОтчёт:\n{saved}\n\nОткрыть файл?", parent=self):
                try:
                    os.startfile(str(saved))
                except Exception:
                    pass

        except Exception as exc:
            messagebox.showerror("Ошибка сопоставления", str(exc), parent=self)
            self.status.set("Сопоставление не завершено.")
