from web_app.modules.excel_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.excel_academy_studio.validation import validate_workbook

def test_complete_curriculum():
    course=get_curriculum()
    assert len(course["stages"])==6
    assert len(course["lessons"])==72
    assert [sum(x["stage_id"]==s["id"] for x in course["lessons"]) for s in course["stages"]]==[12,14,12,12,10,12]

def test_cell_and_formula_validation():
    book={"activeSheet":0,"sheets":[{"name":"Сотрудники","cells":{"E6":{"value":"Уволен"}}}],"operations":[],"charts":[],"pivots":[]}
    assert validate_workbook(book,get_lesson("1-1")["checks"])["passed"]
    book["sheets"][0]["cells"]["D2"]={"formula":"=VLOOKUP(A2,Общежитие!A2:C7,3,FALSE)"}
    assert validate_workbook(book,get_lesson("2-2")["checks"])["passed"]

def test_advanced_entities():
    book={"activeSheet":0,"sheets":[{"name":"Картотека","cells":{"B2":{"formula":"=TRIM(A2)"}}}],"operations":[],"charts":[{"type":"line","data":[1,2,3]}],"pivots":[{"fields":["A","B"]}]}
    assert validate_workbook(book,get_lesson("3-2")["checks"])["passed"]
    assert validate_workbook(book,get_lesson("5-1")["checks"])["passed"]

def test_reconciliation_requires_actual_statuses_and_journal():
    book={"activeSheet":0,"sheets":[
      {"name":"Сверка","cells":{"A1":{"value":"Совпало"},"A2":{"value":"Только в A"},"A3":{"value":"Только в B"}}},
      {"name":"Журнал","cells":{"A1":{"value":"Ключ"},"A2":{"value":"1"},"A3":{"value":"2"}}}],
      "operations":[],"charts":[],"pivots":[]}
    assert validate_workbook(book,[{"kind":"required_texts","expected":["Совпало","Только в A","Только в B"]}])["passed"]
    assert validate_workbook(book,[{"kind":"used_rows_on_sheet","sheet":"Журнал","min":3}])["passed"]
