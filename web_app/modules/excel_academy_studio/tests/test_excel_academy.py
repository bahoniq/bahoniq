from web_app.modules.excel_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.excel_academy_studio.validation import validate_workbook

def test_complete_curriculum():
    course=get_curriculum()
    assert len(course["stages"])==6
    assert len(course["lessons"])==72
    assert [sum(x["stage_id"]==s["id"] for x in course["lessons"]) for s in course["stages"]]==[12,14,12,12,10,12]

def test_cell_and_formula_validation():
    book={"activeSheet":0,"sheets":[{"name":"Лист1","cells":{"A1":{"value":"Сотрудники"},"B6":{"formula":"=SUM(B2:B5)"}}}],"operations":[],"charts":[],"pivots":[]}
    assert validate_workbook(book,get_lesson("1-1")["checks"])["passed"]
    assert validate_workbook(book,get_lesson("2-2")["checks"])["passed"]

def test_advanced_entities():
    book={"activeSheet":0,"sheets":[{"name":"Лист1","cells":{}}],"operations":["filter"],"charts":[{"type":"bar","data":[1,2,3]}],"pivots":[{"fields":["A","B"]}]}
    assert validate_workbook(book,get_lesson("3-2")["checks"])["passed"]
    assert validate_workbook(book,get_lesson("4-6")["checks"])["passed"]
    assert validate_workbook(book,get_lesson("5-1")["checks"])["passed"]
