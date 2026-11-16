"""Проверка фактических результатов Excel Academy Studio."""
import re

def sheets(book): return book.get("sheets",[]) if isinstance(book,dict) else []
def find_sheet(book,name=None):
    if name:
        return next((s for s in sheets(book) if s.get("name")==name),{})
    idx=min(int(book.get("activeSheet",0)),max(0,len(sheets(book))-1))
    return sheets(book)[idx] if sheets(book) else {}
def cells(book): return [x for s in sheets(book) for x in s.get("cells",{}).values()]
def cell(book,addr,sheet=None): return find_sheet(book,sheet).get("cells",{}).get(addr,{})
def formulas(book): return [str(x.get("formula") or x.get("value") or "") for x in cells(book) if str(x.get("formula") or x.get("value") or "").startswith("=")]
def values(book): return [x.get("value") for x in cells(book) if x.get("value") not in (None,"")]
def row_of(addr):
    m=re.search(r"\d+",addr); return int(m.group()) if m else 0

def validate_workbook(book,checks):
    out=[]; fs=formulas(book); vals=values(book); ops=book.get("operations",[]); charts=book.get("charts",[])
    for rule in checks:
        kind=rule.get("kind"); passed=False; msg="Требование не выполнено"
        target=rule.get("target"); expected=rule.get("expected"); minimum=int(rule.get("min",rule.get("min_rows",1)))
        if kind=="cell_value":
            passed=str(cell(book,target).get("value",""))==str(expected); msg=f"В {target} должно быть «{expected}»"
        elif kind=="formula_function":
            passed=any(str(expected).upper()+"(" in f.upper() for f in fs); msg=f"Используйте функцию {expected}"
        elif kind=="formula_functions":
            missing=[x for x in expected if not any(str(x).upper()+"(" in f.upper() for f in fs)]; passed=not missing; msg="Используйте функции: "+", ".join(missing or expected)
        elif kind=="formula_any":
            passed=any(any(str(x).upper()+"(" in f.upper() for x in expected) for f in fs); msg="Используйте одну из функций: "+", ".join(expected)
        elif kind=="formula_count": passed=len(fs)>=minimum; msg=f"Нужно минимум {minimum} формул; сейчас {len(fs)}"
        elif kind=="expected_formula_value":
            f=str(cell(book,target).get("formula","")).upper(); passed=bool(f and "VLOOKUP(" in f); msg=f"В {target} должна быть рабочая поисковая формула для результата {expected}"
        elif kind=="expected_formula_value_any":
            passed=any(str(x.get("value"))==str(expected) for x in cells(book)) or bool(fs); msg=f"Расчёт должен давать контрольный результат {expected}"
        elif kind=="operation": passed=expected in ops; msg=f"Выполните операцию «{expected}»"
        elif kind=="operation_count": passed=len(set(ops))>=minimum; msg=f"Нужно минимум {minimum} разных операций"
        elif kind=="sheet": passed=any(s.get("name")==target for s in sheets(book)); msg=f"Создайте лист «{target}»"
        elif kind=="required_sheets":
            names={s.get("name") for s in sheets(book)}; missing=[x for x in expected if x not in names]; passed=not missing; msg="Не хватает листов: "+(", ".join(missing) if missing else "все созданы")
        elif kind=="used_rows":
            rows={row_of(a) for s in sheets(book) for a,c in s.get("cells",{}).items() if c.get("value") not in (None,"")}; passed=len(rows)>=minimum; msg=f"Нужно минимум {minimum} заполненных строк"
        elif kind=="used_rows_on_sheet":
            sh=find_sheet(book,rule.get("sheet")); rows={row_of(a) for a,c in sh.get("cells",{}).items() if c.get("value") not in (None,"")}; passed=len(rows)>=minimum; msg=f"На листе «{rule.get('sheet')}» нужно минимум {minimum} строк"
        elif kind=="styled_row":
            sh=find_sheet(book); styled=sum(1 for a,c in sh.get("cells",{}).items() if row_of(a)==int(rule.get("row",1)) and c.get("style")); passed=styled>=minimum; msg=f"Оформите минимум {minimum} ячейки строки заголовков"
        elif kind=="styled_cells":
            styled=sum(1 for x in cells(book) if x.get("style")); passed=styled>=minimum; msg=f"Оформите минимум {minimum} расчётные ячейки"
        elif kind=="no_duplicates":
            sh=find_sheet(book); col=rule.get("column","A"); start=int(rule.get("start_row",2)); data=[c.get("value") for a,c in sh.get("cells",{}).items() if a.startswith(col) and row_of(a)>=start and c.get("value") not in (None,"")]; passed=len(data)==len(set(map(str,data))); msg=f"В столбце {col} остались дубликаты"
        elif kind=="text_occurrences":
            count=sum(str(v).strip().lower()==str(expected).lower() for v in vals); passed=count>=minimum; msg=f"Значение «{expected}» должно встречаться минимум {minimum} раз; сейчас {count}"
        elif kind=="required_texts":
            present={str(v).strip().lower() for v in vals}; missing=[x for x in expected if str(x).lower() not in present]; passed=not missing; msg="Не хватает результатов: "+(", ".join(missing) if missing else "все есть")
        elif kind=="nonblank_columns":
            sh=find_sheet(book); passed=all(sum(1 for a,c in sh.get("cells",{}).items() if a.startswith(col) and row_of(a)>=2 and c.get("value") not in (None,""))>=minimum for col in rule.get("columns",[])); msg="Заполните требуемые столбцы результатами разделения"
        elif kind=="pivot": passed=bool(book.get("pivots")); msg="Создайте сводную таблицу"
        elif kind=="chart": passed=any(x.get("type")==expected for x in charts); msg=f"Создайте диаграмму «{expected}»"
        elif kind=="chart_count": passed=len(charts)>=minimum; msg=f"Нужно диаграмм: {minimum}; сейчас {len(charts)}"
        out.append({"passed":passed,"message":msg,"rule":kind})
    n=sum(x["passed"] for x in out); score=round(100*n/max(1,len(out)))
    return {"passed":score==100,"score":score,"passed_count":n,"total":len(out),"results":out}
