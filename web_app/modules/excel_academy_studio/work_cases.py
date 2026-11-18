"""Real-file assignments and deterministic XLSX validation for Excel Academy."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from openpyxl import load_workbook

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "excel_academy_cases"

CASES = [
    {"id":"registry-cleanup","file":"01_registry_cleanup.xlsx","title":"Очистка реестра сотрудников","area":"Кадры · базовый","brief":"Руководитель прислал выгрузку сотрудников. Приведите ФИО, телефоны и подразделения к единому виду, удалите повторы и оставьте прозрачный журнал исправлений.","deliverables":["Лист «Очищенные данные» — 100 уникальных сотрудников","Лист «Дубликаты» — найденные повторы","Лист «Исправления» — что и почему изменено"]},
    {"id":"student-reconciliation","file":"02_student_reconciliation.xlsx","title":"Сверка деканата и общежития","area":"Учебный офис · базовый","brief":"Есть две выгрузки, и цифры в них не сходятся. Соберите единую сверку по ID и объясните, кто присутствует в обеих базах, а кто только в одной.","deliverables":["Лист «Сверка» со всеми 90 ID","Статусы: «Совпало», «Только в деканате», «Только в общежитии»","Итоги: 65 / 15 / 10"]},
    {"id":"monthly-merge","file":"03_monthly_merge.xlsx","title":"Объединение месячных выгрузок","area":"Операции · средний","brief":"Объедините четыре ежемесячных реестра в одну таблицу, добавьте источник месяца и подготовьте краткую сводку по категориям.","deliverables":["Лист «Общий реестр» — 140 операций без потерь","Колонка с месяцем-источником","Лист «Сводка» по категориям"]},
    {"id":"support-sla","file":"04_support_sla.xlsx","title":"Контроль просроченных заявок","area":"Поддержка · средний","brief":"На контрольную дату 18.11.2026 определите незакрытые заявки с истёкшим сроком и подготовьте управленческую сводку.","deliverables":["Лист «Анализ SLA» с результатом по каждой заявке","Корректное определение риска на 18.11.2026","Лист «Сводка» минимум с четырьмя показателями"]},
    {"id":"budget-variance","file":"05_budget_variance.xlsx","title":"План-факт бюджета","area":"Финансы · продвинутый","brief":"Посчитайте отклонение бюджета в тенге и процентах, выделите существенные отклонения и соберите понятную сводку для руководителя.","deliverables":["Лист «Анализ бюджета» — 48 строк с отклонениями","Лист «Сводка»","Минимум одна диаграмма"]},
    {"id":"student-duplicates","file":"06_student_duplicates.xlsx","title":"Поиск дублей студентов","area":"Картотека · продвинутый","brief":"Найдите точные и вероятные дубли. ID приоритетен; при его отсутствии сравнивайте ФИО, дату рождения и программу. Исходник не изменяйте.","deliverables":["Лист «Очищенные данные» — 90 уникальных записей","Лист «Дубликаты» — минимум 8 выявленных дублей","Указан тип или причина совпадения"]},
    {"id":"department-split","file":"07_department_split.xlsx","title":"Разделение реестра по подразделениям","area":"HR · средний","brief":"Разделите общий реестр на отдельные листы подразделений. Ни один сотрудник не должен потеряться или попасть в чужой лист.","deliverables":["Листы IT, HR, «Финансы», «Академический офис»","Всего 120 уникальных ID","Строки соответствуют своему подразделению"]},
    {"id":"final-exam","file":"08_final_exam.xlsx","title":"Экзамен: аудит студенческих данных","area":"Комплексный кейс · эксперт","brief":"Очистите студенческий реестр, сверьте его с общежитием и подготовьте дашборд и журнал аудита. Это имитация реального задания без пошаговой подсказки.","deliverables":["100 уникальных студентов после очистки","Сверка: 82 / 18 / 8","Лист «Дашборд» с формулами и диаграммой","Лист «Аудит» минимум с пятью записями"]},
]

CASE_BY_ID = {case["id"]: case for case in CASES}

def public_cases() -> list[dict[str, Any]]:
    return [{k:v for k,v in case.items() if k != "file"} for case in CASES]

def source_path(case_id: str) -> Path:
    case = CASE_BY_ID.get(case_id)
    if not case:
        raise KeyError(case_id)
    return DATA_DIR / case["file"]

def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())

def _rows(ws) -> list[dict[str, Any]]:
    headers = [str(c.value or "").strip() for c in ws[1]]
    return [dict(zip(headers, row)) for row in ws.iter_rows(min_row=2, values_only=True) if any(v is not None for v in row)]

def _sheet(wb, name: str):
    wanted = _norm(name)
    return next((ws for ws in wb.worksheets if _norm(ws.title) == wanted), None)

def _result(ok: bool, title: str, message: str, critical: bool=False) -> dict[str, Any]:
    return {"passed":bool(ok), "critical":critical, "title":title, "message":message}

def _find_key(row: dict[str, Any], *needles: str) -> str | None:
    return next((key for key in row if any(n in _norm(key) for n in needles)), None)

def _source_unchanged(submitted, baseline) -> dict[str, Any]:
    errors=[]
    for src in baseline.worksheets:
        dst=_sheet(submitted, src.title)
        if dst is None:
            errors.append(f"нет листа «{src.title}»")
            continue
        for row in src.iter_rows():
            for cell in row:
                if dst[cell.coordinate].value != cell.value:
                    errors.append(f"{src.title}!{cell.coordinate}")
                    if len(errors)>=4: break
            if len(errors)>=4: break
    return _result(not errors,"Исходные данные сохранены", "Исходные листы не изменены." if not errors else "Изменены исходные данные: "+", ".join(errors), True)

def _sheet_rule(wb, name: str, min_rows: int=1):
    ws=_sheet(wb,name); count=len(_rows(ws)) if ws else 0
    return _result(bool(ws and count>=min_rows),f"Лист «{name}»",f"Найдено строк: {count}; требуется не меньше {min_rows}.",True), ws

def _validate_cleanup(wb, _data):
    out=[]; r,clean=_sheet_rule(wb,"Очищенные данные",100); out.append(r)
    r,dups=_sheet_rule(wb,"Дубликаты",8); out.append(r)
    r,fixes=_sheet_rule(wb,"Исправления",8); out.append(r)
    if clean:
        rows=_rows(clean); ids=[str(x.get(_find_key(x,"id") or "")) for x in rows]
        names=[str(x.get(_find_key(x,"фио") or "") or "") for x in rows]
        ok=len(set(ids))==100 and len(ids)==100
        out.append(_result(ok,"Уникальность сотрудников",f"Уникальных ID: {len(set(ids))}; строк: {len(ids)}."))
        tidy=all(n==n.strip() and "  " not in n for n in names)
        out.append(_result(tidy,"Нормализация ФИО","Лишние пробелы в ФИО не найдены." if tidy else "В ФИО остались лишние пробелы."))
    return out

def _status_counts(ws):
    rows=_rows(ws); counts=Counter()
    for row in rows:
        key=_find_key(row,"статус","результат","итог")
        if key: counts[_norm(row.get(key))]+=1
    return counts

def _validate_reconcile(wb, _data):
    r,ws=_sheet_rule(wb,"Сверка",90); out=[r]
    counts=_status_counts(ws) if ws else Counter()
    expected={"совпало":65,"только в деканате":15,"только в общежитии":10}
    out.append(_result(all(counts[k]==v for k,v in expected.items()),"Результат сверки",f"Получено: {dict(counts)}. Ожидается 65 / 15 / 10."))
    return out

def _validate_merge(wb, _data):
    r,ws=_sheet_rule(wb,"Общий реестр",140); out=[r]
    if ws:
        rows=_rows(ws); opkey=_find_key(rows[0],"операц","id") if rows else None
        monthkey=_find_key(rows[0],"месяц","источник") if rows else None
        unique=len({str(x.get(opkey)) for x in rows}) if opkey else 0
        months=Counter(_norm(x.get(monthkey)) for x in rows) if monthkey else Counter()
        out.append(_result(unique==140,"Полнота операций",f"Уникальных операций: {unique} из 140."))
        out.append(_result(len([v for v in months.values() if v==35])>=4,"Месяц-источник",f"Распределение: {dict(months)}."))
    r,_=_sheet_rule(wb,"Сводка",4); out.append(r); return out

def _as_date(v):
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    if isinstance(v,str):
        for fmt in ("%d.%m.%Y","%Y-%m-%d"):
            try:return datetime.strptime(v.strip(),fmt).date()
            except ValueError:pass
    return None

def _validate_sla(wb, baseline_data):
    r,ws=_sheet_rule(wb,"Анализ SLA",100); out=[r]
    if ws:
        source=_rows(baseline_data["Заявки"]); expected={str(x["№"]):(_norm(x["Статус"])!="закрыта" and _as_date(x["Срок"])<date(2026,11,18)) for x in source}
        checked=correct=0
        for row in _rows(ws):
            idkey=_find_key(row,"№","номер","id"); resultkey=_find_key(row,"риск","результат","sla","проср")
            if not idkey or not resultkey or str(row.get(idkey)) not in expected: continue
            checked+=1; text=_norm(row.get(resultkey)); actual=any(x in text for x in ("риск","проср","наруш"))
            correct += actual==expected[str(row.get(idkey))]
        out.append(_result(checked>=95 and correct/checked>=.95 if checked else False,"Расчёт SLA",f"Проверено {checked}; верно {correct}."))
    r,_=_sheet_rule(wb,"Сводка",4); out.append(r); return out

def _validate_budget(wb, _data):
    r,ws=_sheet_rule(wb,"Анализ бюджета",48); out=[r]
    if ws:
        checked=correct=0
        for row in _rows(ws):
            pk=_find_key(row,"план"); fk=_find_key(row,"факт"); dk=_find_key(row,"отклон");
            if not all((pk,fk,dk)): continue
            try:
                checked+=1; correct+=abs(float(row[dk])-(float(row[fk])-float(row[pk])))<.02
            except (TypeError,ValueError): pass
        out.append(_result(checked>=45 and correct>=45,"План-факт",f"Проверено {checked}; верно {correct}."))
    r,_=_sheet_rule(wb,"Сводка",4); out.append(r)
    charts=sum(len(getattr(s,"_charts",[])) for s in wb.worksheets)
    out.append(_result(charts>=1,"Диаграмма",f"Диаграмм в книге: {charts}.")); return out

def _validate_duplicates(wb, _data):
    r,clean=_sheet_rule(wb,"Очищенные данные",90); out=[r]
    if clean:
        rows=_rows(clean); key=_find_key(rows[0],"id") if rows else None
        ids={str(x.get(key)) for x in rows if key and x.get(key) not in (None,"")}
        out.append(_result(len(ids)==90,"Уникальная картотека",f"Уникальных заполненных ID: {len(ids)}."))
    r,_=_sheet_rule(wb,"Дубликаты",8); out.append(r); return out

def _validate_split(wb, _data):
    out=[]; all_ids=[]
    for name in ("IT","HR","Финансы","Академический офис"):
        r,ws=_sheet_rule(wb,name,1); out.append(r)
        if ws:
            rows=_rows(ws); ik=_find_key(rows[0],"id") if rows else None; dk=_find_key(rows[0],"подразд") if rows else None
            all_ids.extend(str(x.get(ik)) for x in rows if ik)
            out.append(_result(all(_norm(x.get(dk))==_norm(name) for x in rows) if dk else False,f"Состав листа «{name}»",f"Строк: {len(rows)}."))
    out.append(_result(len(all_ids)==120 and len(set(all_ids))==120,"Полнота разделения",f"Всего ID: {len(all_ids)}; уникальных: {len(set(all_ids))}.")); return out

def _validate_final(wb, _data):
    out=[]
    r,clean=_sheet_rule(wb,"Очищенные данные",100); out.append(r)
    if clean:
        rows=_rows(clean); key=_find_key(rows[0],"id") if rows else None; ids={str(x.get(key)) for x in rows if key}
        out.append(_result(len(ids)==100,"Очистка студентов",f"Уникальных ID: {len(ids)}."))
    r,rec=_sheet_rule(wb,"Сверка",108); out.append(r)
    counts=_status_counts(rec) if rec else Counter(); expected={"совпало":82,"только в студентах":18,"только в общежитии":8}
    out.append(_result(all(counts[k]==v for k,v in expected.items()),"Комплексная сверка",f"Получено: {dict(counts)}. Ожидается 82 / 18 / 8."))
    r,dash=_sheet_rule(wb,"Дашборд",1); out.append(r)
    formulas=sum(1 for row in dash.iter_rows() for c in row if isinstance(c.value,str) and c.value.startswith("=")) if dash else 0
    charts=sum(len(getattr(s,"_charts",[])) for s in wb.worksheets)
    out.append(_result(formulas>=5 and charts>=1,"Дашборд",f"Формул: {formulas}; диаграмм: {charts}."))
    r,_=_sheet_rule(wb,"Аудит",5); out.append(r); return out

VALIDATORS: dict[str, Callable] = {"registry-cleanup":_validate_cleanup,"student-reconciliation":_validate_reconcile,"monthly-merge":_validate_merge,"support-sla":_validate_sla,"budget-variance":_validate_budget,"student-duplicates":_validate_duplicates,"department-split":_validate_split,"final-exam":_validate_final}

def validate_submission(case_id: str, submitted_path: Path) -> dict[str, Any]:
    baseline=load_workbook(source_path(case_id),data_only=False)
    workbook=load_workbook(submitted_path,data_only=False)
    baseline_data={ws.title:ws for ws in baseline.worksheets}
    results=[_source_unchanged(workbook,baseline)] + VALIDATORS[case_id](workbook,baseline_data)
    score=round(100*sum(x["passed"] for x in results)/len(results))
    passed=score>=80 and not any(x["critical"] and not x["passed"] for x in results)
    return {"passed":passed,"score":score,"results":results,"summary":"Работа принята." if passed else "Работа требует исправлений. Откройте пункты ниже и загрузите файл повторно."}
