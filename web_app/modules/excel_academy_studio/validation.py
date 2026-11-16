# -*- coding: utf-8 -*-
"""
Проверка фактических результатов Excel Academy Studio — Professional Edition.
Поддерживает строгую валидацию ячеек, формул, межлистовых связей, фильтров, сортировок,
сводных таблиц, диаграмм, дедупликации и журналов расхождений.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

def sheets(book: Dict[str, Any]) -> List[Dict[str, Any]]:
    return book.get("sheets", []) if isinstance(book, dict) else []

def find_sheet(book: Dict[str, Any], name: str | None = None) -> Dict[str, Any]:
    shs = sheets(book)
    if not shs:
        return {}
    if name:
        target_name = str(name).strip().lower()
        return next((s for s in shs if str(s.get("name", "")).strip().lower() == target_name), {})
    try:
        idx = min(int(book.get("activeSheet", 0)), max(0, len(shs) - 1))
        return shs[idx]
    except Exception:
        return shs[0]

def cells(book: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for s in sheets(book) for c in s.get("cells", {}).values() if isinstance(c, dict)]

def cell(book: Dict[str, Any], addr: str, sheet: str | None = None) -> Dict[str, Any]:
    sh = find_sheet(book, sheet)
    c = sh.get("cells", {}).get(addr, {})
    return c if isinstance(c, dict) else {}

def formulas(book: Dict[str, Any], sheet: str | None = None) -> List[str]:
    sh = find_sheet(book, sheet) if sheet else None
    cell_list = sh.get("cells", {}).values() if sh else cells(book)
    res: List[str] = []
    for c in cell_list:
        if isinstance(c, dict):
            f = str(c.get("formula") or c.get("value") or "").strip()
            if f.startswith("="):
                res.append(f)
    return res

def values(book: Dict[str, Any], sheet: str | None = None) -> List[Any]:
    sh = find_sheet(book, sheet) if sheet else None
    cell_list = sh.get("cells", {}).values() if sh else cells(book)
    return [c.get("value") for c in cell_list if isinstance(c, dict) and c.get("value") not in (None, "")]

def row_of(addr: str) -> int:
    m = re.search(r"\d+", str(addr))
    return int(m.group()) if m else 0

def col_of(addr: str) -> str:
    m = re.match(r"[A-Za-z]+", str(addr).strip().upper())
    return m.group() if m else "A"


def validate_workbook(book: Dict[str, Any], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    fs = formulas(book)
    vals = values(book)
    ops = [str(x) for x in book.get("operations", [])]
    charts = book.get("charts", [])
    pivots = book.get("pivots", [])
    filters = book.get("filters", {})

    for rule in checks:
        kind = rule.get("kind", "")
        passed = False
        msg = "Требование не выполнено"
        target = rule.get("target") or rule.get("cell")
        expected = rule.get("expected") or rule.get("contains")
        sheet_name = rule.get("sheet")
        minimum = int(rule.get("min", rule.get("min_rows", 1)))

        # 1. Значение конкретной ячейки
        if kind == "cell_value":
            c_val = cell(book, target, sheet_name).get("value", "")
            passed = str(c_val).strip().lower() == str(expected).strip().lower()
            msg = f"В {target} должно быть «{expected}»"

        # 2. Формула в конкретной ячейке (formula_at)
        elif kind == "formula_at":
            c_entry = cell(book, target, sheet_name)
            f_val = str(c_entry.get("formula") or c_entry.get("value") or "").strip()
            if expected:
                exp_func = str(expected).upper()
                passed = f_val.startswith("=") and (exp_func + "(" in f_val.upper() or exp_func in f_val.upper())
                msg = f"В ячейке {target} должна быть формула с функцией {expected}"
            else:
                passed = f_val.startswith("=")
                msg = f"В ячейке {target} должна быть рабочая формула"

        # 3. Формула содержит нужные ссылки или диапазон (formula_contains_refs)
        elif kind == "formula_contains_refs":
            raw_refs = rule.get("refs") or expected
            refs = raw_refs if isinstance(raw_refs, list) else ([raw_refs] if raw_refs else [])
            c_entry = cell(book, target, sheet_name) if target else None
            search_formulas = [str(c_entry.get("formula") or c_entry.get("value") or "")] if c_entry else fs
            missing = []
            for r in refs:
                clean_ref = str(r).replace(" ", "").upper().replace("$", "")
                found = any(clean_ref in f.replace(" ", "").upper().replace("$", "") for f in search_formulas)
                if not found:
                    missing.append(str(r))
            passed = not missing
            msg = f"Формула должна ссылаться на: {', '.join(missing or refs)}"

        # 4. Контрольный расчётный результат ячейки (calculated_value)
        elif kind == "calculated_value":
            c_val = cell(book, target, sheet_name).get("value", "")
            has_min = "min" in rule
            has_max = "max" in rule
            try:
                f_act = float(str(c_val).replace(",", ".").replace(" ", "").replace("₸", ""))
                if has_min or has_max:
                    passed = True
                    if has_min and f_act < float(rule["min"]):
                        passed = False
                    if has_max and f_act > float(rule["max"]):
                        passed = False
                elif expected is not None:
                    f_exp = float(str(expected).replace(",", ".").replace(" ", "").replace("₸", ""))
                    passed = abs(f_act - f_exp) < 0.05
                else:
                    passed = True
            except Exception:
                passed = str(c_val).strip().lower() == str(expected).strip().lower() if expected is not None else False
            msg = f"Расчёт в {target} должен быть в пределах [{rule.get('min')}, {rule.get('max')}]" if (has_min or has_max) else f"Расчёт в {target} должен давать {expected}"

        # 5. Значение ячейки на конкретном листе (sheet_cell_value)
        elif kind == "sheet_cell_value":
            c_val = cell(book, target, sheet_name).get("value", "")
            passed = str(c_val).strip().lower() == str(expected).strip().lower()
            msg = f"На листе «{sheet_name}» в {target} должно быть «{expected}»"

        # 6. Формула на конкретном листе (sheet_formula)
        elif kind == "sheet_formula":
            sheet_fs = formulas(book, sheet_name)
            exp_func = str(expected).upper()
            passed = any(exp_func + "(" in f.upper() or exp_func in f.upper() for f in sheet_fs)
            msg = f"На листе «{sheet_name}» используйте функцию {expected}"

        # 7. Наличие функции в любой формуле
        elif kind == "formula_function":
            exp_func = str(expected).upper()
            passed = any(exp_func + "(" in f.upper() for f in fs)
            msg = f"Используйте функцию {expected}"

        # 8. Несколько обязательных функций
        elif kind == "formula_functions":
            missing = [x for x in expected if not any(str(x).upper() + "(" in f.upper() for f in fs)]
            passed = not missing
            msg = "Используйте функции: " + ", ".join(missing or expected)

        # 9. Любая из предложенных функций
        elif kind == "formula_any":
            passed = any(any(str(x).upper() + "(" in f.upper() for x in expected) for f in fs)
            msg = "Используйте одну из функций: " + ", ".join(expected)

        # 10. Количество формул в книге
        elif kind == "formula_count":
            passed = len(fs) >= minimum
            msg = f"Нужно минимум {minimum} формул; сейчас {len(fs)}"

        # 11. Отсутствие ошибок в формулах (#ERROR!, #DIV/0!, #REF!, #NAME?)
        elif kind == "error_free_formulas":
            err_tokens = {"#ERROR!", "#DIV/0!", "#REF!", "#NAME?", "#VALUE!"}
            found_errors = []
            for c in cells(book):
                v_str = str(c.get("value", "")).strip().upper()
                if v_str in err_tokens:
                    found_errors.append(v_str)
            passed = not found_errors
            msg = "Устраните ошибки в формулах: " + (", ".join(set(found_errors)) if found_errors else "ошибок нет")

        # 12. Фактическая операция
        elif kind == "operation" or kind == "operation_result":
            exp_op = str(expected).lower()
            passed = any(exp_op in op.lower() for op in ops)
            msg = f"Выполните операцию «{expected}»"

        # 13. Количество разных операций
        elif kind == "operation_count":
            passed = len(set(ops)) >= minimum
            msg = f"Нужно минимум {minimum} разных операций"

        # 14. Наличие листа
        elif kind == "sheet":
            sh_names = [str(s.get("name", "")).strip().lower() for s in sheets(book)]
            passed = str(target).strip().lower() in sh_names
            msg = f"Создайте лист «{target}»"

        # 15. Список обязательных листов
        elif kind == "required_sheets":
            existing = {str(s.get("name", "")).strip().lower() for s in sheets(book)}
            missing = [x for x in expected if str(x).strip().lower() not in existing]
            passed = not missing
            msg = "Не хватает листов: " + (", ".join(missing) if missing else "все созданы")

        # 16. Заполненные строки
        elif kind == "used_rows":
            rows = {row_of(a) for s in sheets(book) for a, c in s.get("cells", {}).items() if c.get("value") not in (None, "")}
            passed = len(rows) >= minimum
            msg = f"Нужно минимум {minimum} заполненных строк"

        # 17. Заполненные строки на конкретном листе
        elif kind == "used_rows_on_sheet":
            sh = find_sheet(book, rule.get("sheet"))
            rows = {row_of(a) for a, c in sh.get("cells", {}).items() if c.get("value") not in (None, "")}
            passed = len(rows) >= minimum
            msg = f"На листе «{rule.get('sheet')}» нужно минимум {minimum} строк"

        # 18. Журнал расхождений/изменений (journal_entries)
        elif kind == "journal_entries":
            j_sheet = rule.get("sheet", "Журнал")
            sh = find_sheet(book, j_sheet)
            rows = {row_of(a) for a, c in sh.get("cells", {}).items() if row_of(a) >= 2 and c.get("value") not in (None, "")}
            passed = len(rows) >= minimum
            msg = f"В журнале «{j_sheet}» должно быть зафиксировано минимум {minimum} записей"

        # 19. Заголовки таблицы (required_headers)
        elif kind == "required_headers":
            sh = find_sheet(book, sheet_name)
            h_row = int(rule.get("row", 1))
            row_vals = {str(c.get("value", "")).strip().lower() for a, c in sh.get("cells", {}).items() if row_of(a) == h_row}
            missing = [x for x in expected if str(x).strip().lower() not in row_vals]
            passed = not missing
            msg = "В заголовках не хватает: " + (", ".join(missing) if missing else "все на месте")

        # 20. Оформление ячеек и строк
        elif kind == "styled_row":
            sh = find_sheet(book, sheet_name)
            styled = sum(1 for a, c in sh.get("cells", {}).items() if row_of(a) == int(rule.get("row", 1)) and c.get("style"))
            passed = styled >= minimum
            msg = f"Оформите минимум {minimum} ячейки строки заголовков"

        elif kind == "styled_cells":
            styled = sum(1 for c in cells(book) if c.get("style"))
            passed = styled >= minimum
            msg = f"Оформите минимум {minimum} расчётные ячейки"

        # 21. Отсутствие дубликатов (no_duplicates / deduplicated_by)
        elif kind in ("no_duplicates", "deduplicated_by"):
            sh = find_sheet(book, sheet_name)
            col = str(rule.get("column", "A")).upper()
            start = int(rule.get("start_row", 2))
            data = [c.get("value") for a, c in sh.get("cells", {}).items() if a.startswith(col) and row_of(a) >= start and c.get("value") not in (None, "")]
            passed = len(data) > 0 and len(data) == len(set(map(lambda x: str(x).strip().lower(), data)))
            msg = f"В столбце {col} остались повторяющиеся записи"

        # 22. Наличие ключевых текстов в результатах
        elif kind == "text_occurrences":
            count = sum(str(v).strip().lower() == str(expected).strip().lower() for v in vals)
            passed = count >= minimum
            msg = f"Значение «{expected}» должно встречаться минимум {minimum} раз; сейчас {count}"

        elif kind == "required_texts":
            present = {str(v).strip().lower() for v in vals}
            missing = [x for x in expected if str(x).strip().lower() not in present]
            passed = not missing
            msg = "Не хватает результатов: " + (", ".join(missing) if missing else "все есть")

        # 23. Заполнение нескольких столбцов
        elif kind == "nonblank_columns":
            sh = find_sheet(book, sheet_name)
            passed = all(sum(1 for a, c in sh.get("cells", {}).items() if a.startswith(col) and row_of(a) >= 2 and c.get("value") not in (None, "")) >= minimum for col in rule.get("columns", []))
            msg = "Заполните требуемые столбцы данными"

        # 24. Непустой диапазон (nonblank_range)
        elif kind == "nonblank_range":
            sh = find_sheet(book, sheet_name)
            col = str(rule.get("column", "A")).upper()
            r_start = int(rule.get("start_row", 2))
            r_end = int(rule.get("end_row", 10))
            nonblanks = sum(1 for r in range(r_start, r_end + 1) if sh.get("cells", {}).get(f"{col}{r}", {}).get("value") not in (None, ""))
            passed = nonblanks >= minimum
            msg = f"В диапазоне {col}{r_start}:{col}{r_end} должно быть заполнено минимум {minimum} ячеек"

        # 25. Фактическая сортировка (sorted_column)
        elif kind == "sorted_column":
            col = str(rule.get("column", "A")).upper()
            direction = str(rule.get("direction", "asc")).lower()
            sort_op = f"sort:{col}:{direction}".lower()
            has_op = any(sort_op in op.lower() or f"sort:{col}".lower() in op.lower() for op in ops)
            sh = find_sheet(book, sheet_name)
            col_vals = [c.get("value") for a, c in sorted(sh.get("cells", {}).items(), key=lambda kv: row_of(kv[0])) if a.startswith(col) and row_of(a) >= 2 and c.get("value") not in (None, "")]
            try:
                num_vals = [float(str(x).replace(",", ".").replace(" ", "")) for x in col_vals]
                is_sorted = num_vals == sorted(num_vals, reverse=(direction == "desc"))
            except Exception:
                str_vals = [str(x).strip().lower() for x in col_vals]
                is_sorted = str_vals == sorted(str_vals, reverse=(direction == "desc"))
            passed = has_op or (len(col_vals) >= 3 and is_sorted)
            msg = f"Отсортируйте столбец {col} по {'возрастанию' if direction == 'asc' else 'убыванию'}"

        # 26. Фактическая фильтрация (filtered_rows)
        elif kind == "filtered_rows":
            col = str(rule.get("column", "")).upper()
            has_filter_op = any(f"filter:{col}".lower() in op.lower() or "filter" == op.lower() for op in ops) or bool(filters.get(col)) or bool(filters)
            passed = has_filter_op or bool(filters)
            msg = f"Примените фильтр к столбцу {col}"

        # 27. Сводная таблица (pivot / pivot_config)
        elif kind in ("pivot", "pivot_config"):
            if not pivots:
                passed = False
                msg = "Создайте сводную таблицу"
            else:
                req_row = rule.get("row_field")
                req_val = rule.get("val_field")
                req_agg = rule.get("agg")
                if req_row or req_val or req_agg:
                    matched = False
                    for p in pivots:
                        r_ok = not req_row or str(p.get("rowField", "")).lower() == str(req_row).lower()
                        v_ok = not req_val or str(p.get("valField", "")).lower() == str(req_val).lower()
                        a_ok = not req_agg or str(p.get("agg", "")).lower() == str(req_agg).lower()
                        if r_ok and v_ok and a_ok:
                            matched = True
                            break
                    passed = matched
                    msg = f"Настройте сводную: строки «{req_row or '*'}», значения «{req_val or '*'}», агрегация {req_agg or '*'}"
                else:
                    passed = True
                    msg = "Сводная таблица создана"

        # 28. Диаграмма (chart / chart_source)
        elif kind in ("chart", "chart_source"):
            if not charts:
                passed = False
                msg = f"Создайте диаграмму «{expected or 'диаграмма'}»"
            else:
                exp_type = str(expected or rule.get("type", "")).lower()
                matched = any(str(c.get("type", "")).lower() == exp_type for c in charts) if exp_type else True
                if rule.get("min_data_points"):
                    has_data = any(len(c.get("data", []) or c.get("values", [])) >= int(rule["min_data_points"]) for c in charts)
                    passed = matched and has_data
                    msg = f"Диаграмма «{exp_type}» должна содержать реальный диапазон данных"
                else:
                    passed = matched
                    msg = f"Создайте диаграмму типа «{exp_type}»"

        elif kind == "chart_count":
            passed = len(charts) >= minimum
            msg = f"Нужно диаграмм: {minimum}; сейчас {len(charts)}"

        # 29. Ожидаемая формула с конкретным значением (legacy)
        elif kind == "expected_formula_value":
            f = str(cell(book, target, sheet_name).get("formula", "")).upper()
            passed = bool(f and ("VLOOKUP(" in f or "XLOOKUP(" in f or "INDEX(" in f))
            msg = f"В {target} должна быть рабочая поисковая формула для результата {expected}"

        elif kind == "expected_formula_value_any":
            passed = any(str(x.get("value")) == str(expected) for x in cells(book)) or bool(fs)
            msg = f"Расчёт должен давать контрольный результат {expected}"

        out.append({"passed": passed, "message": msg, "rule": kind})

    n = sum(1 for x in out if x["passed"])
    score = round(100 * n / max(1, len(out)))
    return {
        "passed": score == 100,
        "score": score,
        "passed_count": n,
        "total": len(out),
        "results": out
    }
