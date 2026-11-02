from __future__ import annotations

import os
import secrets
import shutil
import socket
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from config import SYSTEMS
from .modules.excel_ai.ai_interpreter import interpret_task
from .modules.excel_ai.analyzer import analyze_workbook
from .modules.excel_ai.operations import execute_operations, plan_operations
from .modules.report_studio.launcher import generate_report, inspect_excel


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_UPLOAD = 50 * 1024 * 1024
SESSION_TTL = 60 * 60
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
PDF_OPERATIONS = {
    "pdf_word", "word_pdf", "pdf_png", "pdf_jpg", "images_pdf",
    "merge_pdf", "split_pdf", "compress_pdf",
}

app = FastAPI(title="BahonIQ Work Center", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")

_sessions: dict[str, dict] = {}
_lock = threading.RLock()


def _network_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _cleanup() -> None:
    cutoff = time.time() - SESSION_TTL
    expired = []
    with _lock:
        for token, value in tuple(_sessions.items()):
            if value["created"] < cutoff:
                expired.append(_sessions.pop(token))
    for value in expired:
        shutil.rmtree(value["directory"], ignore_errors=True)


async def _receive(upload: UploadFile, directory: Path) -> Path:
    name = Path(upload.filename or "workbook.xlsx").name
    suffix = Path(name).suffix.lower()
    if suffix not in EXCEL_EXTENSIONS:
        raise HTTPException(400, "Поддерживаются файлы .xls, .xlsx и .xlsm.")
    destination = directory / ("source" + suffix)
    size = 0
    try:
        with destination.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Файл превышает 50 МБ.")
                stream.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if not size:
        raise HTTPException(400, "Загружен пустой файл.")
    return destination


async def _receive_any(upload: UploadFile, directory: Path, index: int) -> Path:
    name = Path(upload.filename or f"file_{index}").name
    destination = directory / f"{index:03d}_{name}"
    size = 0
    try:
        with destination.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, f"Файл «{name}» превышает 50 МБ.")
                stream.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if not size:
        raise HTTPException(400, f"Файл «{name}» пуст.")
    return destination


def _new_session(kind: str) -> tuple[str, Path]:
    token = secrets.token_urlsafe(24)
    directory = Path(tempfile.mkdtemp(prefix=f"workcenter_{kind}_"))
    return token, directory


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    _cleanup()
    return {
        "status": "ready",
        "network_url": f"http://{_network_ip()}:8000",
        "systems": [
            {"icon": icon, "name": name, "url": url}
            for icon, name, url in SYSTEMS
        ],
        "modules": ["analytics", "excel", "pdf"],
    }


@app.post("/api/excel/plan")
async def excel_plan(
    instruction: str = Form(...),
    workbook: UploadFile = File(...),
):
    _cleanup()
    instruction = instruction.strip()
    if not instruction:
        raise HTTPException(400, "Опишите задачу.")
    token, directory = _new_session("excel")
    try:
        source = await _receive(workbook, directory)
        analysis = await run_in_threadpool(
            analyze_workbook, source, 5, 5
        )
        interpretation = await run_in_threadpool(
            interpret_task, instruction, analysis
        )
        if interpretation.get("questions"):
            shutil.rmtree(directory, ignore_errors=True)
            return {
                "status": "questions",
                "questions": interpretation["questions"],
            }
        operations = interpretation.get("operations", [])
        output = directory / ("Excel_AI_result" + source.suffix.lower())
        plan = await run_in_threadpool(
            plan_operations, source, output, operations
        )
        with _lock:
            _sessions[token] = {
                "kind": "excel", "created": time.time(),
                "directory": directory, "output": output, "plan": plan,
            }
        return {
            "status": "planned", "session_id": token,
            "operations": operations,
            "explanation": interpretation.get("explanation", ""),
            "sheet_count": analysis.get("sheet_count", 0),
        }
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/excel/execute")
async def excel_execute(
    session_id: str = Form(...),
    confirmed: bool = Form(...),
):
    if confirmed is not True:
        raise HTTPException(400, "Подтвердите план.")
    with _lock:
        session = _sessions.get(session_id)
        if not session or session["kind"] != "excel":
            raise HTTPException(404, "Сессия не найдена.")
        if session.get("running"):
            raise HTTPException(409, "Задача уже выполняется.")
        session["running"] = True
    try:
        result = await run_in_threadpool(
            execute_operations, session["plan"], True
        )
        session["complete"] = True
        return {
            "status": "completed",
            "download_url": f"/api/download/{session_id}/excel",
            "changes": result.get("changes", []),
        }
    except Exception as exc:
        session["running"] = False
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/analytics/inspect")
async def analytics_inspect(workbook: UploadFile = File(...)):
    _cleanup()
    token, directory = _new_session("analytics")
    try:
        source = await _receive(workbook, directory)
        inspection = await run_in_threadpool(inspect_excel, source)
        sheets = [
            {
                "name": item.get("name", ""),
                "rows": item.get("rows_count", item.get("row_count", 0)),
                "columns": item.get("columns_count", item.get("column_count", 0)),
                "headers": [str(value or "") for value in (item.get("matrix", [[]]) or [[]])[0][:20]],
                "preview": [
                    [str(value) if value is not None else "" for value in row[:20]]
                    for row in (item.get("matrix", []) or [])[1:16]
                ],
            }
            for item in inspection.get("sheets", [])
        ]
        with _lock:
            _sessions[token] = {
                "kind": "analytics", "created": time.time(),
                "directory": directory, "source": source,
            }
        return {"status": "ready", "session_id": token, "sheets": sheets}
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/analytics/generate")
async def analytics_generate(
    session_id: str = Form(...),
    sheet_name: str = Form(...),
    title: str = Form("Аналитический отчёт"),
    description: str = Form(""),
    pdf: bool = Form(True),
    pptx: bool = Form(False),
    include_source_table: bool = Form(False),
    orientation: str = Form("auto"),
    report_profile: str = Form("Автоматически"),
    audience: str = Form("Руководство"),
):
    with _lock:
        session = _sessions.get(session_id)
        if not session or session["kind"] != "analytics":
            raise HTTPException(404, "Сессия не найдена.")
        if session.get("running"):
            raise HTTPException(409, "Отчёт уже формируется.")
        session["running"] = True
    formats = tuple(x for x, enabled in (("pdf", pdf), ("pptx", pptx)) if enabled)
    if not formats:
        session["running"] = False
        raise HTTPException(400, "Выберите PDF или PowerPoint.")
    try:
        result = await run_in_threadpool(
            generate_report,
            session["source"], sheet_name, title,
            session["directory"], description, include_source_table,
            orientation, formats, None, report_profile, audience,
        )
        files = {}
        for key, label in (("output_file", "pdf"), ("presentation_file", "pptx")):
            value = result.get(key)
            if value:
                files[label] = str(Path(value).resolve())
        session["files"] = files
        session["complete"] = True
        return {
            "status": "completed",
            "downloads": {
                label: f"/api/download/{session_id}/{label}"
                for label in files
            },
            "warnings": result.get("warnings", []),
        }
    except Exception as exc:
        session["running"] = False
        raise HTTPException(400, str(exc)) from exc


def _zip_outputs(paths: list[Path], target: Path) -> Path:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.name)
    return target


def _pdf_process(operation: str, sources: list[Path], directory: Path) -> Path:
    if operation == "merge_pdf":
        from pypdf import PdfReader, PdfWriter
        if len(sources) < 2:
            raise ValueError("Для объединения выберите минимум два PDF-файла.")
        writer = PdfWriter()
        for source in sources:
            for page in PdfReader(str(source)).pages:
                writer.add_page(page)
        output = directory / "Merged.pdf"
        with output.open("wb") as stream:
            writer.write(stream)
        return output

    if operation == "split_pdf":
        from pypdf import PdfReader, PdfWriter
        outputs = []
        for source in sources:
            reader = PdfReader(str(source))
            for number, page in enumerate(reader.pages, 1):
                writer = PdfWriter(); writer.add_page(page)
                output = directory / f"{source.stem}_{number:03d}.pdf"
                with output.open("wb") as stream:
                    writer.write(stream)
                outputs.append(output)
        return _zip_outputs(outputs, directory / "Split_PDF.zip")

    if operation in {"pdf_png", "pdf_jpg"}:
        import fitz
        extension = "png" if operation == "pdf_png" else "jpg"
        outputs = []
        for source in sources:
            document = fitz.open(str(source))
            try:
                for number, page in enumerate(document, 1):
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    output = directory / f"{source.stem}_{number:03d}.{extension}"
                    if extension == "jpg":
                        pixmap.save(str(output), jpg_quality=90)
                    else:
                        pixmap.save(str(output))
                    outputs.append(output)
            finally:
                document.close()
        return _zip_outputs(outputs, directory / f"PDF_to_{extension.upper()}.zip")

    if operation == "images_pdf":
        from PIL import Image, ImageOps
        pages = []
        try:
            for source in sources:
                with Image.open(source) as image:
                    item = ImageOps.exif_transpose(image)
                    if item.mode in {"RGBA", "LA", "P"}:
                        rgba = item.convert("RGBA")
                        page = Image.new("RGB", rgba.size, "white")
                        page.paste(rgba, mask=rgba.getchannel("A"))
                    else:
                        page = item.convert("RGB")
                    pages.append(page)
            if not pages:
                raise ValueError("Изображения не найдены.")
            output = directory / "Images.pdf"
            pages[0].save(output, "PDF", save_all=True, append_images=pages[1:], resolution=150)
            return output
        finally:
            for page in pages:
                page.close()

    if operation == "compress_pdf":
        import fitz
        outputs = []
        for source in sources:
            output = directory / f"{source.stem}_optimized.pdf"
            document = fitz.open(str(source))
            try:
                document.save(str(output), garbage=4, clean=True, deflate=True,
                              deflate_images=True, deflate_fonts=True, use_objstms=1)
            finally:
                document.close()
            outputs.append(output)
        return outputs[0] if len(outputs) == 1 else _zip_outputs(outputs, directory / "Optimized_PDF.zip")

    if operation == "pdf_word":
        from pdf2docx import Converter
        outputs = []
        for source in sources:
            output = directory / f"{source.stem}.docx"
            converter = Converter(str(source))
            try:
                converter.convert(str(output))
            finally:
                converter.close()
            outputs.append(output)
        return outputs[0] if len(outputs) == 1 else _zip_outputs(outputs, directory / "PDF_to_Word.zip")

    if operation == "word_pdf":
        if os.name != "nt":
            raise RuntimeError("Word → PDF работает на Windows с установленным Microsoft Word.")
        import win32com.client
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False; word.DisplayAlerts = 0
        outputs = []
        try:
            for source in sources:
                output = directory / f"{source.stem}.pdf"
                document = word.Documents.Open(str(source.resolve()), ReadOnly=True)
                try:
                    document.ExportAsFixedFormat(str(output.resolve()), 17)
                finally:
                    document.Close(False)
                outputs.append(output)
        finally:
            word.Quit()
        return outputs[0] if len(outputs) == 1 else _zip_outputs(outputs, directory / "Word_to_PDF.zip")

    raise ValueError("Неизвестная операция PDF Center.")


@app.post("/api/pdf/process")
async def pdf_process(
    operation: str = Form(...),
    files: list[UploadFile] = File(...),
):
    if operation not in PDF_OPERATIONS:
        raise HTTPException(400, "Неизвестная операция PDF Center.")
    token, directory = _new_session("pdf")
    try:
        sources = [await _receive_any(upload, directory, index) for index, upload in enumerate(files, 1)]
        output = await run_in_threadpool(_pdf_process, operation, sources, directory)
        with _lock:
            _sessions[token] = {
                "kind": "pdf", "created": time.time(), "directory": directory,
                "output": output, "complete": True,
            }
        return {"status": "completed", "download_url": f"/api/download/{token}/pdf_result", "filename": output.name}
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True); raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/download/{session_id}/{kind}")
def download(session_id: str, kind: str):
    with _lock:
        session = _sessions.get(session_id)
    if not session or not session.get("complete"):
        raise HTTPException(404, "Результат не найден.")
    if session["kind"] == "excel" and kind == "excel":
        path = Path(session["output"])
    elif session["kind"] == "pdf" and kind == "pdf_result":
        path = Path(session["output"])
    else:
        value = session.get("files", {}).get(kind)
        path = Path(value) if value else Path()
    if not path.is_file():
        raise HTTPException(404, "Файл результата отсутствует.")
    names = {
        "excel": "Excel_AI_result.xlsx",
        "pdf": "Analytics_AI_report.pdf",
        "pptx": "Analytics_AI_report.pptx",
        "pdf_result": path.name if path else "PDF_Center_result",
    }
    return FileResponse(path, filename=names.get(kind, path.name))
