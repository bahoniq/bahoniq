"""API Excel Academy Studio Pro."""
from __future__ import annotations
import io, json, re
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from starlette.concurrency import run_in_threadpool
from ai_service import generate_text
from ..modules.excel_academy_studio.curriculum import get_curriculum, get_lesson
from ..modules.excel_academy_studio.validation import validate_workbook

router=APIRouter(prefix="/api/excel-academy",tags=["Excel Academy Studio"])
@router.get("/curriculum")
def curriculum(): return get_curriculum()
@router.get("/lesson/{lesson_id}")
def lesson(lesson_id:str):
    item=get_lesson(lesson_id)
    if not item: raise HTTPException(404,"Урок не найден")
    return item
@router.post("/validate/{lesson_id}")
async def validate(lesson_id:str,request:Request):
    item=get_lesson(lesson_id)
    if not item: raise HTTPException(404,"Урок не найден")
    body=await request.json(); return validate_workbook(body.get("workbook",{}),item["checks"])

@router.post("/import")
async def import_book(file:UploadFile=File(...)):
    data=await file.read()
    if len(data)>20*1024*1024: raise HTTPException(413,"Файл больше 20 МБ")
    try: wb=load_workbook(io.BytesIO(data),data_only=False)
    except Exception as exc: raise HTTPException(400,f"Не удалось прочитать XLSX: {exc}")
    sheets=[]
    for ws in wb.worksheets[:12]:
        cells={}
        for row in ws.iter_rows(min_row=1,max_row=min(ws.max_row,500),max_col=min(ws.max_column,50)):
            for c in row:
                if c.value is not None:
                    cells[c.coordinate]={"value":c.value,"formula":c.value if isinstance(c.value,str) and c.value.startswith("=") else ""}
        sheets.append({"name":ws.title,"cells":cells})
    return {"name":file.filename,"activeSheet":0,"sheets":sheets or [{"name":"Лист1","cells":{}}],"operations":[],"charts":[],"pivots":[]}

@router.post("/export")
async def export_book(request:Request):
    book=(await request.json()).get("workbook",{}); wb=Workbook(); wb.remove(wb.active)
    for source in book.get("sheets",[])[:20]:
        ws=wb.create_sheet((source.get("name") or "Лист")[:31])
        for addr,item in source.get("cells",{}).items():
            if not re.match(r"^[A-Z]{1,3}[1-9]\d*$",addr): continue
            cell=ws[addr]; cell.value=item.get("formula") or item.get("value")
            style=item.get("style",{})
            if style.get("bold"): cell.font=Font(bold=True,color=(style.get("color") or "000000").replace("#", ""))
            if style.get("background"): cell.fill=PatternFill("solid",fgColor=style["background"].replace("#",""))
            if style.get("align"): cell.alignment=Alignment(horizontal=style["align"])
            if style.get("format")=="currency": cell.number_format='#,##0.00 ₸'
    if not wb.worksheets: wb.create_sheet("Лист1")
    stream=io.BytesIO(); wb.save(stream); stream.seek(0)
    return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":'attachment; filename="Excel_Academy_Result.xlsx"'})

def _mentor_sync(item,question,book,validation):
    compact={"sheets":[{"name":s.get("name"),"cells":dict(list(s.get("cells",{}).items())[:60])} for s in book.get("sheets",[])[:3]],"operations":book.get("operations",[]),"charts":book.get("charts",[])}
    prompt=f"Урок: {item['title']}\nЗадание: {item['task']}\nВопрос: {question}\nКнига: {json.dumps(compact,ensure_ascii=False)}\nПроверка: {json.dumps(validation,ensure_ascii=False)}\nДай короткое объяснение и только один следующий шаг. Не выполняй задание вместо ученика."
    try: return {"answer":str(generate_text(prompt=prompt,system_instruction="Ты профессиональный наставник по Excel. Проверяй адреса, формулы и логику данных.",temperature=.2,timeout=35)).strip(),"provider":"ИИ-наставник"}
    except Exception:
        failed=next((x["message"] for x in validation["results"] if not x["passed"]),"Проверьте условие урока.")
        return {"answer":failed+". Исправьте это и повторите проверку.","provider":"Локальная проверка"}
@router.post("/mentor/{lesson_id}")
async def mentor(lesson_id:str,request:Request):
    item=get_lesson(lesson_id)
    if not item: raise HTTPException(404,"Урок не найден")
    body=await request.json(); book=body.get("workbook",{}); validation=validate_workbook(book,item["checks"])
    return await run_in_threadpool(_mentor_sync,item,str(body.get("question", ""))[:1000],book,validation)
