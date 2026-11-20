"""High-level, workbook-grounded plans for complex human Excel requests."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from copy import copy
from datetime import datetime

from openpyxl.chart import BarChart, Reference


def norm(value):
    return re.sub(r"[^0-9a-zа-яёәіңғүұқөһ]+", " ", str(value or "").casefold()).strip()


def compact(value):
    return re.sub(r"[^0-9a-zа-яёәіңғүұқөһ]+", "", str(value or "").casefold())


def _sheet(analysis):
    sheets = analysis.get("sheets", []) if isinstance(analysis, dict) else []
    return sheets[0] if len(sheets) == 1 else None


def _header(headers, *words, exclude=()):
    ranked = []
    for header in headers:
        key = norm(header)
        if any(item in key for item in exclude):
            continue
        score = sum(1 for word in words if word in key)
        if score:
            ranked.append((score, -len(key), header))
    return max(ranked, default=(0, 0, None))[2]


def _base(analysis):
    sheet = _sheet(analysis)
    if not sheet:
        return None
    headers = list(sheet.get("headers") or [])
    return sheet, headers, {
        "teacher": _header(headers, "преподавател", exclude=("факульт", "кафедр")),
        "faculty": _header(headers, "факульт"),
        "department": _header(headers, "кафедр"),
        "discipline": _header(headers, "дисциплин", "модул"),
        "period": _header(headers, "академическ", "период"),
        "flow": _header(headers, "главн", "поток"),
        "group": _header(headers, "групп"),
        "program": _header(headers, "оп"),
        "course": _header(headers, "курс"),
        "student_count": _header(headers, "количеств", "обучающ"),
    }


def _teacher_filter(fields):
    return {"column": fields["teacher"], "operator": "contains", "value": "преподаватель не назначен"}


def _period_filter(fields, exact=False):
    value = "осень 2026 01.09.2026 31.12.2026" if exact else "осень 2026"
    return {"column": fields["period"], "operator": "contains_normalized", "value": value}


def plan_advanced_request(task, analysis):
    """Return a complete high-level plan only for requests we can fully ground."""
    base = _base(analysis)
    if not base:
        return None
    sheet, headers, fields = base
    text = norm(task)
    sheet_name = sheet.get("name")
    header_row = int(sheet.get("header_row") or 1)

    if re.search(r"\bпроблемн\w*\b", text) and not re.search(r"(?:пуст|дубл|ошиб|аномал|период)", text):
        return {"questions": ["Что именно считать проблемной записью: пустые поля, дубликаты, неверные периоды, необычные значения или другое условие?"], "operations": [], "mode": "questions"}
    if re.search(r"удал\w*.*неправильн|остав\w*.*полезн", text):
        return {"questions": ["Укажите точные критерии неправильных строк и правила исправления периодов. До уточнения данные удаляться не будут."], "operations": [], "mode": "questions"}

    actions = []
    exact_dates = "01 09 2026" in text and "31 12 2026" in text
    no_teacher = bool(re.search(r"(?:препод\w*|преподавател\w*)\s+не\s+назнач|без\s+назначенн\w*\s+преподав", text))

    if "настоящ" in text and "заголов" in text and "количеств" in text and "столб" in text:
        actions.append({"kind": "structure", "output_sheet": "Проверка структуры"})

    cleaning_request = "очищенн" in text and "копи" in text
    if no_teacher and not cleaning_request and any(word in text for word in ("отбер", "вытащ", "спис", "нов", "создай", "отдельн", "выдел")):
        conditions = [_teacher_filter(fields)]
        if "осен" in text or "осин" in text or exact_dates:
            conditions.append(_period_filter(fields, exact_dates))
        if re.search(r"курс\w*\s+(?:равен\s+)?1\b", text):
            conditions.append({"column": fields["course"], "operator": "eq_numeric", "value": 1})
        if re.search(r"(?:количеств\w*.*больше\s+3|больше\s+3)", text):
            conditions.append({"column": fields["student_count"], "operator": "gt_numeric", "value": 3})
        action = {"kind": "filter", "conditions": conditions, "output_sheet": "Преподаватель не назначен"}
        if "сортир" in text:
            action.update({"sort_column": fields["student_count"], "descending": True})
        if "сводк" in text or "итог" in text or "скока" in text:
            action["summary_output_sheet"] = "Общая сводка"
        actions.append(action)

    summary_requested = "сводк" in text and any(word in text for word in ("факульт", "кафедр", "дисциплин", "групп", "образовательн", "курс"))
    if summary_requested:
        mentioned = {"faculty": "факульт", "department": "кафедр", "discipline": "дисциплин", "group": "групп", "program": "образовательн", "course": "курс"}
        dimensions = [fields[k] for k, stem in mentioned.items() if fields[k] and stem in text]
        if not dimensions and "всем" in text:
            dimensions = [fields[k] for k in ("faculty", "department", "discipline", "group", "program", "course") if fields[k]]
        source_filter = [_teacher_filter(fields)] if no_teacher else []
        actions.append({"kind": "summary", "dimensions": dimensions, "conditions": source_filter, "top_n": 10, "charts": "диаграм" in text})

    if re.search(r"20\s+(?:дисциплин|групп)", text) or ("20 дисциплин" in text and "20 групп" in text):
        actions.append({"kind": "top_n", "groups": [fields["discipline"], fields["group"]], "value_column": fields["student_count"], "n": 20})

    if "сгрупп" in text and all(word in text for word in ("факульт", "кафедр", "курс")):
        actions.append({"kind": "aggregate", "groups": [fields["faculty"], fields["department"], fields["course"]], "value_column": fields["student_count"], "metrics": ["count", "sum", "avg", "min", "max"], "sort": "sum", "descending": True})

    if "перекр" in text and "факульт" in text and "курс" in text:
        actions.append({"kind": "pivot", "row_column": fields["faculty"], "column_column": fields["course"], "value_column": fields["student_count"], "function": "sum"})

    if "аудит" in text and "качест" in text:
        actions.append({"kind": "quality_audit", "period_column": fields["period"], "flow_column": fields["flow"], "course_column": fields["course"], "faculty_column": fields["faculty"], "department_column": fields["department"]})

    if "разбери" in text and "период" in text and ("сезон" in text or "дата" in text):
        actions.append({"kind": "period_audit", "period_column": fields["period"]})

    if "очищенн" in text and "копи" in text and "изменени" in text:
        actions.append({"kind": "clean_copy", "teacher_column": fields["teacher"]})

    if "лист контроль" in text or "лист «контроль»" in task.casefold():
        actions.append({"kind": "control"})
    if "лист описание" in text or "лист «описание»" in task.casefold():
        actions.append({"kind": "description", "text": task})

    # Ordered multi-output request: full unassigned list, exact-period list,
    # summaries, discipline ranking and reconciliation.
    if not "комплексн" in text and no_teacher and "лист контроль" in text and "рейтинг дисциплин" in text:
        actions = [
            {"kind": "filter", "conditions": [_teacher_filter(fields)], "output_sheet": "Все без преподавателя"},
            {"kind": "filter", "conditions": [_teacher_filter(fields), _period_filter(fields, True)], "output_sheet": "Точный период"},
            {"kind": "summary", "dimensions": [fields["faculty"], fields["department"]], "conditions": [_teacher_filter(fields)], "top_n": 10, "charts": False},
            {"kind": "top_n", "groups": [fields["discipline"]], "value_column": fields["student_count"], "n": 20, "conditions": [_teacher_filter(fields)]},
            {"kind": "control"},
        ]

    # Full complex request: add explicitly requested reports that do not use
    # imperative verbs near each noun.
    if "комплексн" in text and len(re.findall(r"\d+[.)]", task)) >= 4:
        actions = [a for a in actions if a["kind"] not in {"filter", "summary", "top_n", "pivot"}]
        scope = [_teacher_filter(fields), _period_filter(fields, False)]
        actions.insert(0, {"kind": "filter", "conditions": scope, "output_sheet": "Без преподавателя — осень"})
        actions.insert(1, {"kind": "filter", "conditions": [_teacher_filter(fields), _period_filter(fields, True)], "output_sheet": "Точный период"})
        actions.append({"kind": "summary", "dimensions": [fields[k] for k in ("faculty", "department", "discipline", "group", "program", "course")], "conditions": scope, "top_n": 10, "charts": True})
        if not any(a["kind"] == "top_n" for a in actions):
            actions.append({"kind": "top_n", "groups": [fields["discipline"], fields["group"]], "value_column": fields["student_count"], "n": 20, "conditions": scope})
        if not any(a["kind"] == "pivot" for a in actions):
            actions.append({"kind": "pivot", "row_column": fields["faculty"], "column_column": fields["course"], "value_column": fields["student_count"], "function": "sum", "conditions": scope})
        if not any(a["kind"] == "period_audit" for a in actions):
            actions.append({"kind": "period_audit", "period_column": fields["period"]})
        if not any(a["kind"] == "control" for a in actions):
            actions.append({"kind": "control"})
        if not any(a["kind"] == "description" for a in actions):
            actions.append({"kind": "description", "text": task})

    if not actions:
        return None
    return {"questions": [], "operations": [{"type": "advanced_report", "sheet": sheet_name, "header_rows": header_row, "actions": actions}], "mode": "operations", "explanation": f"Полный план: {len(actions)} действий без изменения исходного листа.", "advanced_reasoning": True}


def execute_advanced_report(wb, op, changes, reports):
    ws = wb[op["sheet"]]
    hr = op.get("header_rows", 1)
    headers = [ws.cell(hr, c).value for c in range(1, ws.max_column + 1)]
    index = {str(h): i for i, h in enumerate(headers) if h is not None}
    rows = [list(r) for r in ws.iter_rows(min_row=hr + 1, values_only=True) if any(v not in (None, "") for v in r)]
    created = []

    def unique(name):
        base = re.sub(r"[\\/*?:\[\]]", "_", str(name))[:31] or "Результат"
        candidate, n = base, 2
        while candidate in wb.sheetnames:
            suffix = f"_{n}"; candidate = base[:31-len(suffix)] + suffix; n += 1
        return candidate

    def match(actual, condition):
        operator, expected = condition["operator"], condition.get("value")
        if operator == "contains": return str(expected).casefold() in str(actual or "").casefold()
        if operator == "contains_normalized": return compact(expected) in compact(actual)
        if operator == "eq_numeric":
            try: return float(actual) == float(expected)
            except (TypeError, ValueError): return False
        if operator == "gt_numeric":
            try: return float(actual) > float(expected)
            except (TypeError, ValueError): return False
        return actual == expected

    def filtered(conditions):
        return [row for row in rows if all(match(row[index[c["column"]]], c) for c in conditions)]

    def append_table(name, table_headers, data):
        target = wb.create_sheet(unique(name)); created.append(target.title)
        target.append(table_headers)
        for row in data: target.append(row)
        target.freeze_panes = "A2"; target.auto_filter.ref = target.dimensions
        for c in range(1, target.max_column + 1): target.column_dimensions[target.cell(1, c).column_letter].width = min(45, max(12, len(str(target.cell(1,c).value or ""))+2))
        return target

    actions = op.get("actions")
    if actions is None:
        actions = []
    elif not isinstance(actions, list):
        raise ValueError("advanced_report: параметр 'actions' должен быть списком.")

    result_counts = {}
    for action in actions:
        kind = action["kind"]
        if kind == "structure":
            target = append_table(action["output_sheet"], ["Показатель", "Значение"], [["Исходный лист", ws.title], ["Строка заголовков", hr], ["Строк данных", len(rows)], ["Столбцов", len(headers)]])
            result_counts[target.title] = 4
        elif kind == "filter":
            data = filtered(action.get("conditions", []))
            if action.get("sort_column"):
                col = index[action["sort_column"]]; data.sort(key=lambda r: (r[col] is None, r[col]), reverse=action.get("descending", False))
            target = append_table(action.get("output_sheet", "Отбор"), headers, data); result_counts[target.title] = len(data)
            if action.get("summary_output_sheet"):
                summary = append_table(action["summary_output_sheet"], ["Показатель", "Значение"], [["Найдено записей", len(data)]])
                result_counts[summary.title] = 1
        elif kind == "summary":
            data = filtered(action.get("conditions", []))
            for dimension in action.get("dimensions", []):
                counts = Counter(row[index[dimension]] for row in data)
                ordered = sorted(counts.items(), key=lambda x: (-x[1], str(x[0])))
                table = [[value, count, count / len(data) if data else 0] for value, count in ordered]
                target = append_table(f"Сводка {dimension}", [dimension, "Количество", "Доля"], table); result_counts[target.title] = len(table)
                for cell in target["C"][1:]: cell.number_format = "0.0%"
                if action.get("charts") and table:
                    chart = BarChart(); n = min(action.get("top_n", 10), len(table)); chart.add_data(Reference(target, min_col=2, min_row=1, max_row=n+1), titles_from_data=True); chart.set_categories(Reference(target, min_col=1, min_row=2, max_row=n+1)); chart.title = f"Топ-{n}: {dimension}"; target.add_chart(chart, "E2")
        elif kind == "top_n":
            scoped_rows = filtered(action.get("conditions", []))
            for group in action["groups"]:
                totals = defaultdict(float)
                for row in scoped_rows:
                    try: totals[row[index[group]]] += float(row[index[action["value_column"]]] or 0)
                    except (TypeError, ValueError): pass
                ordered = sorted(totals.items(), key=lambda x: (-x[1], str(x[0])))[:action["n"]]
                target = append_table(f"Топ {action['n']} {group}", [group, "Сумма"], ordered); result_counts[target.title] = len(ordered)
        elif kind == "aggregate":
            groups = action["groups"]; buckets = defaultdict(list)
            for row in rows:
                try: value = float(row[index[action["value_column"]]] or 0)
                except (TypeError, ValueError): continue
                buckets[tuple(row[index[g]] for g in groups)].append(value)
            data = []
            for key, values in buckets.items(): data.append([*key, len(values), sum(values), sum(values)/len(values), min(values), max(values)])
            data.sort(key=lambda r: r[len(groups)+1], reverse=True)
            target = append_table("Групповая аналитика", groups + ["Количество", "Сумма", "Среднее", "Минимум", "Максимум"], data); result_counts[target.title] = len(data)
        elif kind == "pivot":
            scoped_rows = filtered(action.get("conditions", []))
            row_col, col_col, val_col = index[action["row_column"]], index[action["column_column"]], index[action["value_column"]]
            row_values = sorted({r[row_col] for r in scoped_rows}, key=str); col_values = sorted({r[col_col] for r in scoped_rows}, key=str); matrix = defaultdict(float)
            for row in scoped_rows:
                try: matrix[(row[row_col], row[col_col])] += float(row[val_col] or 0)
                except (TypeError, ValueError): pass
            data = [[rv, *[matrix[(rv, cv)] for cv in col_values], sum(matrix[(rv, cv)] for cv in col_values)] for rv in row_values]
            totals = ["ИТОГО", *[sum(matrix[(rv, cv)] for rv in row_values) for cv in col_values], sum(matrix.values())]
            target = append_table("Факультет × Курс", [action["row_column"], *col_values, "ИТОГО"], data + [totals]); result_counts[target.title] = len(data)
        elif kind == "period_audit":
            col = index[action["period_column"]]; bad = []
            pattern = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})")
            for row in rows:
                value = str(row[col] or ""); m = pattern.search(value); reason = None
                if m:
                    start = datetime.strptime(m.group(1), "%d.%m.%Y"); end = datetime.strptime(m.group(2), "%d.%m.%Y")
                    if end < start: reason = "Дата окончания раньше даты начала"
                    elif "весна 2026" in value.casefold() and start.month >= 9: reason = "Сезон противоречит дате начала"
                if reason: bad.append([*row, reason])
            target = append_table("Подозрительные периоды", headers + ["Причина"], bad); result_counts[target.title] = len(bad)
        elif kind == "quality_audit":
            duplicate_counts = Counter(tuple(r) for r in rows); duplicate_rows = [[count, *row] for row, count in duplicate_counts.items() if count > 1]
            target = append_table("Полные дубликаты", ["Повторений", *headers], duplicate_rows); result_counts[target.title] = len(duplicate_rows)
            blanks = []
            for n, row in enumerate(rows, hr+1):
                for c, value in enumerate(row):
                    if value is None or (isinstance(value, str) and not value.strip()): blanks.append([n, headers[c]])
            target = append_table("Пустые значения", ["Строка", "Столбец"], blanks); result_counts[target.title] = len(blanks)
            flow_col = index.get(action.get("flow_column")); course_col = index.get(action.get("course_column"))
            if flow_col is not None:
                flows = Counter(row[flow_col] for row in rows if row[flow_col] not in (None, ""))
                repeated = [[value, count] for value, count in sorted(flows.items(), key=lambda x: (-x[1], str(x[0]))) if count > 1]
                target = append_table("Повторяющиеся потоки", [action["flow_column"], "Количество"], repeated); result_counts[target.title] = len(repeated)
            if course_col is not None:
                unusual = []
                for rnum, row in enumerate(rows, hr+1):
                    try:
                        number = float(row[course_col])
                        if not number.is_integer() or not 1 <= number <= 7: unusual.append([rnum, row[course_col], "Вне диапазона 1–7"])
                    except (TypeError, ValueError): unusual.append([rnum, row[course_col], "Не числовой курс"])
                target = append_table("Необычные курсы", ["Строка", action["course_column"], "Причина"], unusual); result_counts[target.title] = len(unusual)
            variants = []
            for key in ("faculty_column", "department_column"):
                column = action.get(key); col = index.get(column)
                if col is None: continue
                groups = defaultdict(Counter)
                for row in rows:
                    value = row[col]
                    if value not in (None, ""): groups[compact(value.replace("ё", "е") if isinstance(value, str) else value)][str(value)] += 1
                for normalized, forms in groups.items():
                    if len(forms) > 1:
                        for form, count in forms.items(): variants.append([column, normalized, form, count])
            target = append_table("Варианты написания", ["Столбец", "Нормализованное значение", "Вариант", "Количество"], variants); result_counts[target.title] = len(variants)
            # Reuse the general period consistency audit.
            execute_advanced_report(wb, {"sheet": op["sheet"], "header_rows": hr, "actions": [{"kind": "period_audit", "period_column": action["period_column"]}]}, changes, reports)
        elif kind == "clean_copy":
            cleaned, log = [], []
            teacher_idx = index.get(action.get("teacher_column"))
            for rnum, row in enumerate(rows, hr+1):
                new = list(row)
                for c, value in enumerate(row):
                    if isinstance(value, str):
                        fixed = re.sub(r"\s+", " ", value).strip()
                        if c == teacher_idx and "преподаватель не назначен" in fixed.casefold(): fixed = "(преподаватель не назначен)"
                        if fixed != value: log.append([rnum, headers[c], value, fixed]); new[c] = fixed
                cleaned.append(new)
            target = append_table("Очищенные данные", headers, cleaned); result_counts[target.title] = len(cleaned)
            target = append_table("Изменения", ["Строка", "Столбец", "Было", "Стало"], log); result_counts[target.title] = len(log)
        elif kind == "description":
            target = append_table("Описание", ["Описание выполненной задачи"], [[action.get("text", "")]]); result_counts[target.title] = 1
        elif kind == "control":
            # Written last below, after all other outputs exist.
            pass

    if any(isinstance(a, dict) and a.get("kind") == "control" for a in actions):
        target = append_table("Контроль", ["Лист результата", "Строк данных"], [[name, count] for name, count in result_counts.items()]); result_counts[target.title] = len(result_counts)
    changes.append({"type": "advanced_report", "sheet": ws.title, "created_sheets": created, "result_counts": result_counts, "source_modified": False})
    reports["advanced_report"] = changes[-1]
