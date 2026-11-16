"""Детерминированная проверка учебной рабочей книги."""
from __future__ import annotations
import re

def _cell(book, address):
    sheet=book.get("sheets",[{}])[book.get("activeSheet",0)] if book.get("sheets") else {}
    return sheet.get("cells",{}).get(address,{})
def _cells(book):
    return [c for s in book.get("sheets",[]) for c in s.get("cells",{}).values()]
def validate_workbook(book, checks):
    results=[]; cells=_cells(book); ops=book.get("operations",[]); charts=book.get("charts",[])
    for rule in checks:
        kind,target,exp=rule.get("kind"),rule.get("target"),rule.get("expected"); passed=False; msg="Требование не выполнено"
        c=_cell(book,target) if target and ":" not in target and re.match(r"^[A-Z]+\d+$",target) else {}
        formulas=[str(x.get("formula",x.get("value",""))) for x in cells if str(x.get("formula",x.get("value",""))).startswith("=")]
        if kind=="cell_value": passed=str(c.get("value",""))==str(exp); msg=f"В ячейке {target} должно быть «{exp}»"
        elif kind=="cell_number": passed=float(c.get("value",0) or 0)==float(exp); msg=f"В {target} должно быть число {exp}"
        elif kind=="formula": passed=str(c.get("formula","")).replace(" ","").upper()==str(exp).replace(" ","").upper(); msg=f"Введите формулу {exp} в {target}"
        elif kind=="formula_function": passed=any(str(exp).upper()+"(" in x.upper() for x in formulas); msg=f"Используйте функцию {exp}"
        elif kind=="formula_any": passed=any(any(str(v).upper() in x.upper() for v in exp) for x in formulas); msg="Используйте одну из требуемых функций"
        elif kind=="formula_contains": passed=any(str(exp).upper() in x.upper() for x in formulas); msg=f"Формула должна содержать {exp}"
        elif kind=="formula_count": passed=len(formulas)>=int(exp); msg=f"Нужно минимум {exp} формул"
        elif kind=="sheet": passed=any(s.get("name")==target for s in book.get("sheets",[])); msg=f"Создайте лист «{target}»"
        elif kind=="operation": passed=exp in ops; msg=f"Выполните операцию: {exp}"
        elif kind=="operation_count": passed=len(set(ops))>=int(exp); msg=f"Выполните минимум {exp} разных операций"
        elif kind=="chart": passed=any(x.get("type")==exp for x in charts); msg=f"Создайте диаграмму типа {exp}"
        elif kind=="chart_count": passed=len(charts)>=int(exp); msg=f"Создайте минимум {exp} диаграммы"
        elif kind=="chart_title": passed=any(x.get("title") for x in charts); msg="Добавьте название диаграммы"
        elif kind=="chart_points": passed=any(len(x.get("data",[]))>=int(exp) for x in charts); msg=f"В диаграмме должно быть минимум {exp} точки"
        elif kind=="pivot": passed=bool(book.get("pivots")); msg="Создайте сводную таблицу"
        elif kind=="pivot_fields": passed=any(len(x.get("fields",[]))>=int(exp) for x in book.get("pivots",[])); msg="Добавьте поля строк и значений"
        elif kind in {"used_range","sequence","styled_range","column_width","format","align","styled_cells","analysis_project","dashboard","exam","final_exam"}:
            used=sum(1 for x in cells if x.get("value") not in (None,"")); styled=sum(1 for x in cells if x.get("style"));
            if kind=="used_range": passed=used>=4
            elif kind=="sequence": passed=used>=5
            elif kind in {"styled_range","styled_cells"}: passed=styled>=3
            elif kind in {"column_width","format","align"}: passed=bool(c.get("style")) or bool(book.get("columnWidths"))
            elif kind=="analysis_project": passed=bool(book.get("pivots")) and len(formulas)>=3
            elif kind=="dashboard": passed=len(charts)>=2 and styled>=3
            elif kind=="exam": passed=len(formulas)>=2 and len(ops)>=1 and len(charts)>=1
            elif kind=="final_exam": passed=used>=20 and len(formulas)>=5 and len(charts)>=2
            msg="Выполните все элементы практического задания"
        results.append({"passed":passed,"message":msg,"rule":kind})
    count=sum(x["passed"] for x in results); score=round(100*count/max(1,len(results)))
    return {"passed":score==100,"score":score,"passed_count":count,"total":len(results),"results":results}
