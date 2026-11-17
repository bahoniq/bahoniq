from __future__ import annotations

import os
import hashlib
import secrets
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from config import SYSTEMS
from .modules.excel_ai.ai_interpreter import interpret_task
from .modules.excel_ai.analyzer import analyze_workbook
from .modules.excel_ai.operations import execute_operations, plan_operations
from .modules.excel_ai.comparison import _read_book, reconcile_students, save_student_reconciliation_report
from .modules.report_studio.launcher import generate_report, inspect_excel
from .modules.report_studio.fast_inspector import fast_inspect_excel
from .modules.ticket_writer import generate_ticket, generate_ticket_stream
from .modules.phonebook import SEED_CONTACTS
from .modules.code_academy.professional_curriculum import lessons as academy_lessons
from .modules.code_academy.architecture_book import CHAPTERS, chapter_reading, chapter_source
from .modules.code_academy.builder import TEMPLATES
from .modules.code_academy.python_runtime import execute_python
from .modules.code_academy.pathway import run_sql


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_UPLOAD = 50 * 1024 * 1024
SESSION_TTL = 60 * 60
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
from fastapi.middleware.cors import CORSMiddleware

PDF_OPERATIONS = {
    "pdf_word", "word_pdf", "pdf_png", "pdf_jpg", "images_pdf",
    "merge_pdf", "split_pdf", "compress_pdf", "pdf_txt",
}

app = FastAPI(
    title="BahonIQ Work Center",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers.academy import router as academy_router
app.include_router(academy_router)

from .routers.design_academy import router as design_academy_router
app.include_router(design_academy_router)

from .routers.excel_academy import router as excel_academy_router
app.include_router(excel_academy_router)

from .routers.instruction_generator import router as instruction_generator_router
app.include_router(instruction_generator_router)

from .routers.music import router as music_router
app.include_router(music_router)

# Опциональная защита паролем для публичного облака (задается через BAHONIQ_PASSWORD)
AUTH_PASSWORD = os.getenv("BAHONIQ_PASSWORD", "").strip()
AUTH_COOKIE_NAME = "bahoniq_auth"
AUTH_SECRET = os.getenv("BAHONIQ_SECRET", "bahoniq_prod_auth_secret_salt_2026")
AUTH_TOKEN = (
    hashlib.sha256((AUTH_PASSWORD + AUTH_SECRET).encode("utf-8")).hexdigest()
    if AUTH_PASSWORD
    else ""
)

@app.get("/health")
def health():
    """Лёгкий эндпоинт для пингера (UptimeRobot) и Render health check. Без авторизации."""
    return {"status": "ok", "app": "BahonIQ Work Center"}


# ============================================================
# АНТИ-СОН (KEEP-AWAKE ДЛЯ RENDER FREE TIER)
# ============================================================
def _keep_awake_worker():
    """Фоновый самопинг через внешний домен Render каждые 9 минут."""
    import time
    import urllib.request
    target = os.environ.get("RENDER_EXTERNAL_URL") or "https://bahoniq.onrender.com"
    health_url = f"{target.rstrip('/')}/health"
    time.sleep(45)  # даём серверу 45 секунд на полный старт
    while True:
        try:
            req = urllib.request.Request(
                health_url,
                headers={"User-Agent": "BahonIQ-AntiSleep/1.0"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                pass
        except Exception:
            pass
        time.sleep(540)  # каждые 9 минут (таймаут засыпания Render = 15 мин)


if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
    import threading
    threading.Thread(target=_keep_awake_worker, daemon=True, name="anti-sleep").start()

@app.on_event("startup")
async def startup_sync_telegram_music():
    if os.getenv("TELEGRAM_SESSION") or (STATIC.parent.parent / "telegram_session.txt").exists():
        try:
            from modules.music_core import sync_catalog
            asyncio.create_task(sync_catalog(force=False))
        except Exception:
            pass


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not AUTH_PASSWORD:
        return await call_next(request)
    
    path = request.url.path
    # Разрешаем статику, PWA манифест, service worker, health, эндпоинты авторизации и PWA-оболочку музыки
    if (
        path in {
            "/api/auth/login", "/api/auth/status", "/health",
            "/manifest.json", "/sw.js",
            "/music", "/music/", "/music/manifest.webmanifest", "/music/sw.js"
        }
        or path.startswith("/assets/")
        or path.startswith("/music/assets/")
        or path.startswith("/music/icons/")
        or path.startswith("/api/music/")
    ):
        return await call_next(request)
    
    cookie_val = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_val == AUTH_TOKEN:
        return await call_next(request)
        
    # Если это API-запрос, возвращаем 401
    if path.startswith("/api/"):
        return JSONResponse({"status": "unauthorized", "error": "Требуется авторизация"}, status_code=401)
        
    # Для браузера отдаем страницу входа
    return FileResponse(STATIC / "login.html")

@app.post("/api/auth/login")
async def auth_login(password: str = Form(...)):
    if not AUTH_PASSWORD or password == AUTH_PASSWORD:
        response = JSONResponse({"status": "ok"})
        response.set_cookie(AUTH_COOKIE_NAME, AUTH_TOKEN, max_age=30*24*3600, httponly=True, samesite="lax")
        return response
    raise HTTPException(status_code=403, detail="Неверный пароль")

@app.get("/api/auth/status")
def auth_status(request: Request):
    if not AUTH_PASSWORD:
        return {"auth_required": False, "authenticated": True}
    is_auth = request.cookies.get(AUTH_COOKIE_NAME) == AUTH_TOKEN
    return {"auth_required": True, "authenticated": is_auth}

@app.get("/manifest.json")
def pwa_manifest():
    return FileResponse(STATIC / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js")
def pwa_sw():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript")


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")

MUSIC_STATIC = STATIC / "music"
app.mount("/music/assets", StaticFiles(directory=MUSIC_STATIC), name="music_assets")

@app.get("/music", include_in_schema=False)
@app.get("/music/", include_in_schema=False)
def car_music_app():
    return FileResponse(
        MUSIC_STATIC / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/music/manifest.webmanifest", include_in_schema=False)
def car_music_manifest():
    return FileResponse(
        MUSIC_STATIC / "manifest.webmanifest",
        media_type="application/manifest+json"
    )

@app.get("/music/sw.js", include_in_schema=False)
def car_music_sw():
    return FileResponse(
        MUSIC_STATIC / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/music/", "Cache-Control": "no-cache"}
    )

@app.get("/music/admin", include_in_schema=False)
def car_music_admin():
    return FileResponse(
        MUSIC_STATIC / "admin.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

_sessions: dict[str, dict] = {}
_lock = threading.RLock()
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
NOTES_PATH = DATA / "notes.txt"
PHONEBOOK_PATH = DATA / "phonebook.db"


def _phonebook() -> sqlite3.Connection:
    connection = sqlite3.connect(PHONEBOOK_PATH)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL DEFAULT '', position TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
            city_phone TEXT NOT NULL DEFAULT '', extension TEXT NOT NULL DEFAULT '',
            mobile TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cur_v = (connection.execute("SELECT value FROM app_meta WHERE key='seed_version'").fetchone() or ("0",))[0]
    try:
        cur_int = int(cur_v)
    except Exception:
        cur_int = 0
    if cur_int < 5:
        # Очищаем возможные дубликаты студенческой канцелярии перед обновлением
        connection.execute("DELETE FROM contacts WHERE department LIKE '%05-01-05%'")
        for contact in SEED_CONTACTS:
            existing = connection.execute(
                "SELECT id FROM contacts WHERE lower(name) = lower(?)", (contact[2],)
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE contacts SET department=?, position=?, location=?, city_phone=?, extension=?, mobile=?, email=? WHERE id=?",
                    (contact[0], contact[1], contact[3], contact[4], contact[5], contact[6], contact[7], existing[0])
                )
            else:
                connection.execute(
                    "INSERT INTO contacts (department, position, name, location, city_phone, extension, mobile, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    contact,
                )
        connection.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seed_version', '5')")
        connection.commit()
    return connection


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
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


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
        "modules": ["analytics", "excel", "pdf", "tickets", "notes", "phonebook", "academy"],
    }


@app.post("/api/writer")
@app.post("/api/tickets/generate")
async def tickets_generate(problem: str = Form(...)):
    problem = problem.strip()
    if not problem:
        raise HTTPException(400, "Опишите проблему.")
    try:
        return await run_in_threadpool(generate_ticket, problem)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/tickets/generate_stream")
def tickets_generate_stream(problem: str = Form(...)):
    """Потоковая генерация заявки через SSE (Server-Sent Events)."""
    problem = problem.strip()
    if not problem:
        raise HTTPException(400, "Опишите проблему.")
    return StreamingResponse(
        generate_ticket_stream(problem),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/notes")
def notes_get():
    return {"text": NOTES_PATH.read_text(encoding="utf-8") if NOTES_PATH.exists() else ""}


@app.post("/api/notes")
def notes_save(text: str = Form("")):
    NOTES_PATH.write_text(text, encoding="utf-8")
    return {"status": "saved", "characters": len(text)}


@app.get("/api/phonebook")
def phonebook_list(q: str = ""):
    query = q.strip().casefold()
    with _phonebook() as db:
        rows = db.execute("SELECT id,department,position,name,location,city_phone,extension,mobile,email FROM contacts ORDER BY department,name").fetchall()
    fields = ("id", "department", "position", "name", "location", "city_phone", "extension", "mobile", "email")
    contacts = [dict(zip(fields, row)) for row in rows]
    if query:
        contacts = [item for item in contacts if query in " ".join(str(value) for value in item.values()).casefold()]
    return {"contacts": contacts, "total": len(rows), "shown": len(contacts)}


@app.post("/api/phonebook/save")
def phonebook_save(
    contact_id: int = Form(0), department: str = Form(""), position: str = Form(""),
    name: str = Form(""), location: str = Form(""), city_phone: str = Form(""),
    extension: str = Form(""), mobile: str = Form(""), email: str = Form(""),
):
    values = tuple(value.strip() for value in (department, position, name, location, city_phone, extension, mobile, email))
    if not values[2]:
        raise HTTPException(400, "Укажите ФИО сотрудника.")
    with _phonebook() as db:
        if contact_id:
            db.execute("UPDATE contacts SET department=?,position=?,name=?,location=?,city_phone=?,extension=?,mobile=?,email=? WHERE id=?", (*values, contact_id))
        else:
            cursor = db.execute("INSERT INTO contacts (department,position,name,location,city_phone,extension,mobile,email) VALUES (?,?,?,?,?,?,?,?)", values)
            contact_id = cursor.lastrowid
        db.commit()
    return {"status": "saved", "id": contact_id}


@app.post("/api/phonebook/delete")
def phonebook_delete(contact_id: int = Form(...)):
    with _phonebook() as db:
        cursor = db.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        db.commit()
    if not cursor.rowcount:
        raise HTTPException(404, "Контакт не найден.")
    return {"status": "deleted"}


@app.get("/api/academy/catalog")
def academy_catalog():
    def serialize(items):
        return [asdict(item) for item in items]
    return {
        "python": serialize(academy_lessons("python")),
        "sql": serialize(academy_lessons("sql")),
        "book": [{"index": index, "title": item.title, "section": item.section, "file": item.file} for index, item in enumerate(CHAPTERS)],
        "builder_files": sorted(TEMPLATES),
        "access": "open",
    }


@app.get("/api/academy/book/{chapter_index}")
def academy_book(chapter_index: int):
    if not 0 <= chapter_index < len(CHAPTERS):
        raise HTTPException(404, "Глава не найдена.")
    chapter = CHAPTERS[chapter_index]
    source, line, warning = chapter_source(chapter)
    return {"title": chapter.title, "section": chapter.section, "reading": chapter_reading(chapter), "source": source, "line": line, "warning": warning}


@app.get("/api/academy/builder")
def academy_builder_file(name: str):
    if name not in TEMPLATES:
        raise HTTPException(404, "Файл конструктора не найден.")
    return {"name": name, "source": TEMPLATES[name]}


@app.post("/api/academy/run")
async def academy_run(
    language: str = Form(...),
    code: str = Form(...),
    stdin: str = Form(""),
):
    if len(code) > 100_000:
        raise HTTPException(413, "Код превышает 100 КБ.")
    try:
        if language == "python":
            result = await run_in_threadpool(execute_python, code, stdin, 3, 50_000)
            return {"output": result.stdout, "error": result.stderr, "returncode": result.returncode}
        if language == "sql":
            output = await run_in_threadpool(run_sql, code)
            return {"output": output, "error": "", "returncode": 0}
        raise HTTPException(400, "Неизвестный язык.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


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


@app.post("/api/excel/inspect")
async def excel_inspect(workbook: UploadFile = File(...)):
    """Безопасный краткий предпросмотр структуры до построения плана."""
    directory = Path(tempfile.mkdtemp(prefix="bahoniq_excel_preview_"))
    try:
        source = await _receive(workbook, directory)
        inspection = await run_in_threadpool(fast_inspect_excel, source)
        sheets = []
        for item in inspection.get("sheets", []):
            sheets.append({
                "name": item.get("name", ""),
                "rows": item.get("rows_count", 0),
                "columns": item.get("columns_count", 0),
                "headers": item.get("headers", [])[:30],
                "preview": item.get("preview", [])[:5],
            })
        return {"status": "ready", "sheets": sheets}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@app.post("/api/excel/convert-xls")
async def excel_convert_xls(workbook: UploadFile = File(...)):
    """Мгновенная конвертация старого файла XLS (Excel 97-2003) в современный XLSX в 1 клик."""
    directory = Path(tempfile.mkdtemp(prefix="bahoniq_convert_"))
    try:
        raw_name = Path(workbook.filename or "file.xls").name
        if Path(raw_name).suffix.lower() != ".xls":
            raise HTTPException(400, "Для конвертации выберите файл старого формата .xls (Excel 97-2003).")
        source = directory / raw_name
        size = 0
        with source.open("wb") as stream:
            while chunk := await workbook.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Файл превышает 50 МБ.")
                stream.write(chunk)
        if not size:
            raise HTTPException(400, "Загружен пустой файл.")

        out_name = source.stem + ".xlsx"
        destination = directory / out_name
        from .modules.excel_ai.converter import convert_xls_to_xlsx
        await run_in_threadpool(convert_xls_to_xlsx, source, destination)

        token = uuid.uuid4().hex
        with _lock:
            _sessions[token] = {
                "kind": "excel",
                "created": time.time(),
                "directory": directory,
                "output": destination,
                "complete": True,
            }
        return {
            "status": "ready",
            "download_url": f"/api/download/{token}/excel",
            "filename": out_name,
        }
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, f"Ошибка конвертации XLS: {exc}") from exc


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
        inspection = await run_in_threadpool(fast_inspect_excel, source)
        sheets = [
            {
                "name": item.get("name", ""),
                "rows": item.get("rows_count", 0),
                "columns": item.get("columns_count", 0),
                "headers": item.get("headers", [])[:20],
                "preview": item.get("preview", [])[:15],
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


@app.post("/api/analytics/report")
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
    report_depth: str = Form("Полный аудит (Все категории, 8+ стр)"),
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
            None, report_depth,
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

    if operation == "pdf_txt":
        import fitz
        outputs = []
        for source in sources:
            document = fitz.open(str(source))
            try:
                parts = []
                for num, page in enumerate(document, 1):
                    t = page.get_text()
                    if t.strip():
                        parts.append(f"--- Страница {num} ---\n{t.strip()}")
                output = directory / f"{source.stem}.txt"
                output.write_text("\n\n".join(parts), encoding="utf-8")
                outputs.append(output)
            finally:
                document.close()
        return outputs[0] if len(outputs) == 1 else _zip_outputs(outputs, directory / "PDF_to_TXT.zip")

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
    elif session["kind"] == "reconcile" and kind == "reconcile":
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
        "reconcile": "Сверка_студентов_неповторяющиеся.xlsx",
        "pdf": "Analytics_AI_report.pdf",
        "pptx": "Analytics_AI_report.pptx",
        "pdf_result": path.name if path else "PDF_Center_result",
    }
    return FileResponse(path, filename=names.get(kind, path.name))


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ ЭНДПОИНТЫ v2.0.0
# ============================================================

@app.post("/api/excel/reconcile")
async def excel_reconcile(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    sheet1: str = Form(""),
    sheet2: str = Form(""),
):
    """Интеллектуальная сверка двух списков студентов по ИИН и ФИО."""
    token, directory = _new_session("reconcile")
    try:
        async def _save_upload(upload: UploadFile, prefix: str) -> Path:
            name = Path(upload.filename or "file.xlsx").name
            suffix = Path(name).suffix.lower()
            if suffix not in EXCEL_EXTENSIONS:
                raise HTTPException(400, f"Файл «{name}»: поддерживаются форматы .xls, .xlsx и .xlsm.")
            dest = directory / f"{prefix}{suffix}"
            sz = 0
            with dest.open("wb") as stream:
                while chunk := await upload.read(1024 * 1024):
                    sz += len(chunk)
                    if sz > MAX_UPLOAD:
                        raise HTTPException(413, f"Файл «{name}» превышает 50 МБ.")
                    stream.write(chunk)
            await upload.close()
            if not sz:
                raise HTTPException(400, f"Файл «{name}» пуст.")
            return dest

        src1 = await _save_upload(file1, "file1")
        src2 = await _save_upload(file2, "file2")

        b1 = await run_in_threadpool(_read_book, src1)
        b2 = await run_in_threadpool(_read_book, src2)
        if not b1 or not b2:
            raise HTTPException(400, "В одном из загруженных файлов не найдено листов.")

        s1_name = sheet1 if sheet1 and any(x["name"] == sheet1 for x in b1) else b1[0]["name"]
        s2_name = sheet2 if sheet2 and any(x["name"] == sheet2 for x in b2) else b2[0]["name"]

        result = await run_in_threadpool(reconcile_students, src1, s1_name, src2, s2_name)
        out_excel = directory / "Сверка_студентов_неповторяющиеся.xlsx"
        await run_in_threadpool(save_student_reconciliation_report, result, out_excel)

        with _lock:
            _sessions[token] = {
                "kind": "reconcile",
                "created": time.time(),
                "directory": directory,
                "output": out_excel,
                "complete": True,
            }

        samples_only1 = [
            {"num": idx, "fio": s["fio"], "iin": s["iin"], "kurs": s["kurs"], "fac_spec": s["fac_spec"], "reg": s["region"]}
            for idx, s in enumerate(result["only1"][:20], start=1)
        ]
        samples_only2 = [
            {"num": idx, "fio": s["fio"], "iin": s["iin"], "kurs": s["kurs"], "fac_spec": s["fac_spec"], "dorm": s["dorm"], "room": s["room"]}
            for idx, s in enumerate(result["only2"], start=1)
        ]

        return {
            "status": "completed",
            "session_id": token,
            "download_url": f"/api/download/{token}/reconcile",
            "counts": result["counts"],
            "file1_name": Path(file1.filename or "Файл 1").name,
            "file2_name": Path(file2.filename or "Файл 2").name,
            "sheet1_name": s1_name,
            "sheet2_name": s2_name,
            "samples_only1": samples_only1,
            "samples_only2": samples_only2,
        }
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/excel/process")
async def excel_process(
    workbook: UploadFile = File(...),
    instruction: str = Form(...),
):
    """Единая обработка таблиц через Excel AI: анализ, план и выполнение."""
    token, directory = _new_session("excel")
    try:
        source = await _receive(workbook, directory)
        analysis = await run_in_threadpool(analyze_workbook, source, 5, 5)
        interpretation = await run_in_threadpool(interpret_task, instruction, analysis)
        operations = interpretation.get("operations", [])
        output = directory / ("Excel_AI_result" + source.suffix.lower())
        plan = await run_in_threadpool(plan_operations, source, output, operations)
        result = await run_in_threadpool(execute_operations, plan, True)
        with _lock:
            _sessions[token] = {
                "kind": "excel", "created": time.time(), "directory": directory,
                "output": output, "plan": plan, "complete": True,
            }
        return {
            "status": "completed",
            "session_id": token,
            "download_url": f"/api/download/{token}/excel",
            "changes": result.get("changes", []),
            "operations_count": len(operations),
            "explanation": interpretation.get("explanation", ""),
        }
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/pdf/merge")
async def pdf_merge(files: list[UploadFile] = File(...)):
    """Объединение нескольких PDF-файлов в один."""
    return await pdf_process("merge_pdf", files)


@app.post("/api/pdf/split")
async def pdf_split(
    file: UploadFile = File(...),
    pages: str = Form(""),
):
    """Разделение PDF по диапазону страниц или постранично."""
    token, directory = _new_session("pdf")
    try:
        source = await _receive_any(file, directory, 1)
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(source))
        total = len(reader.pages)
        pages_str = pages.strip()
        if pages_str:
            target_indices = []
            for part in pages_str.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    s, e = part.split("-", 1)
                    target_indices.extend(range(int(s)-1, int(e)))
                else:
                    target_indices.append(int(part)-1)
            target_indices = [idx for idx in target_indices if 0 <= idx < total]
            if not target_indices:
                target_indices = list(range(total))
            writer = PdfWriter()
            for idx in target_indices:
                writer.add_page(reader.pages[idx])
            output = directory / f"{source.stem}_split.pdf"
            with output.open("wb") as f_out:
                writer.write(f_out)
        else:
            outputs = []
            for num, page in enumerate(reader.pages, 1):
                w = PdfWriter()
                w.add_page(page)
                out = directory / f"{source.stem}_{num:03d}.pdf"
                with out.open("wb") as stream:
                    w.write(stream)
                outputs.append(out)
            output = _zip_outputs(outputs, directory / "Split_Pages.zip")

        with _lock:
            _sessions[token] = {
                "kind": "pdf", "created": time.time(), "directory": directory,
                "output": output, "complete": True,
            }
        return {
            "status": "completed",
            "download_url": f"/api/download/{token}/pdf_result",
            "filename": output.name
        }
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/pdf/ask")
async def pdf_ask(
    file: UploadFile = File(...),
    question: str = Form("Сделай краткую выжимку, выдели ключевые факты, даты, суммы и условия."),
):
    """ИИ-Анализ PDF документа через Google Gemini с автоматическим fallback."""
    from ai_service import generate_text
    import fitz

    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(400, "Поддерживаются только файлы формата .pdf.")

    token, directory = _new_session("pdf")
    target = directory / "uploaded.pdf"
    content = await file.read()
    target.write_bytes(content)

    document = fitz.open(str(target))
    try:
        pages_text = []
        for num, page in enumerate(document, 1):
            t = page.get_text()
            if t.strip():
                pages_text.append(f"[Страница {num}]\n{t.strip()}")
        extracted_text = "\n\n".join(pages_text)
    finally:
        document.close()
        shutil.rmtree(directory, ignore_errors=True)

    if not extracted_text.strip():
        raise HTTPException(400, "Не удалось извлечь текст из PDF (возможно, документ содержит только изображения).")

    system_prompt = (
        "Ты — ведущий ИИ-ассистент по анализу документов. Пользователь загрузил PDF и задал вопрос.\n"
        "Твоя задача — дать точный, структурированный, исчерпывающий ответ строго на основе текста документа.\n"
        "Выдели ключевые факты, даты, суммы, условия и риски. Если нужной информации нет в тексте, честно укажи это."
    )
    user_prompt = (
        f"Документ: {file.filename}\n\n"
        f"Вопрос пользователя: {question}\n\n"
        f"Текст документа (первые 40 000 символов):\n{extracted_text[:40000]}"
    )

    answer, provider = await run_in_threadpool(
        generate_text,
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.2,
        return_provider=True,
    )

    return {
        "status": "completed",
        "question": question,
        "filename": file.filename,
        "answer": answer,
        "provider": provider,
    }


@app.post("/api/academy/ask")
async def academy_ask(
    question: str = Form(...),
    mode: str = Form("hint"),
    code: str = Form(""),
    chapter: str = Form(""),
):
    """ИИ-Ментор Code Academy по архитектуре, коду BahonIQ и SOLID."""
    from .modules.code_academy.ai_tutor import ask_tutor_detailed, PROVIDER_LABELS
    try:
        answer, provider = await run_in_threadpool(
            ask_tutor_detailed,
            question=question,
            mode=mode,
            context={"code": code, "lesson": chapter, "area": "Code Academy"},
        )
        return {"status": "completed", "answer": answer, "provider": provider,
                "provider_label": PROVIDER_LABELS.get(provider, provider)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/academy/ask_stream")
def academy_ask_stream(
    question: str = Form(...),
    mode: str = Form("hint"),
    code: str = Form(""),
    chapter: str = Form(""),
):
    """Потоковый ИИ-Ментор Code Academy через SSE (Server-Sent Events)."""
    question = question.strip()
    if not question:
        raise HTTPException(400, "Задайте вопрос ментору.")
    from .modules.code_academy.ai_tutor import ask_tutor_stream
    return StreamingResponse(
        ask_tutor_stream(
            question=question,
            mode=mode,
            context={"code": code, "lesson": chapter, "area": "Code Academy"},
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# PLATONUS WIKI AI — ЕДИНАЯ СЕРВЕРНАЯ БАЗА ЗНАНИЙ (SQLite + Gemini Flash API)
# ============================================================================

@app.get("/api/wiki/tree")
async def wiki_tree_get():
    """Возвращает дерево всех тем (wiki_topics) и заголовков статей (wiki_articles)."""
    from .modules.wiki.service import get_wiki_tree
    return await run_in_threadpool(get_wiki_tree)


@app.get("/api/wiki/articles/{article_id}")
async def wiki_article_get(article_id: int):
    """Возвращает полный текст выбранной статьи базы знаний."""
    from .modules.wiki.service import get_article
    art = await run_in_threadpool(get_article, article_id)
    if not art:
        raise HTTPException(404, "Статья не найдена.")
    return art


@app.put("/api/wiki/articles/{article_id}")
async def wiki_article_put(article_id: int, request: Request):
    """Редактирование заголовка, темы или текста статьи вручную."""
    from .modules.wiki.service import update_article
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
        title = str(body.get("title", "")).strip()
        content = str(body.get("content", "")).strip()
        topic_name = str(body.get("topic_name", "")).strip() or None
        updated = await run_in_threadpool(update_article, article_id, title, content, topic_name)
        return updated
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/wiki/articles/{article_id}")
async def wiki_article_delete(article_id: int):
    """Удаление статьи из базы знаний."""
    from .modules.wiki.service import delete_article
    ok = await run_in_threadpool(delete_article, article_id)
    if not ok:
        raise HTTPException(404, "Статья не найдена.")
    return {"status": "deleted", "id": article_id}


@app.post("/api/wiki/articles")
async def wiki_article_create(request: Request):
    """Ручное добавление текстовой инструкции в базу знаний."""
    from .modules.wiki.service import create_manual_article
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
        title = str(body.get("title", "")).strip()
        content = str(body.get("content", "")).strip()
        topic_name = str(body.get("topic_name", "")).strip() or "Общие инструкции Platonus"
        created = await run_in_threadpool(create_manual_article, title, content, topic_name)
        return created
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/wiki/upload")
async def wiki_upload_post(files: list[UploadFile] = File(...)):
    """Умная пакетная загрузка файлов (.pdf, .docx, .txt) в памяти с ИИ-каталогизацией."""
    from .modules.wiki.service import upload_and_catalog_files
    if not files:
        raise HTTPException(400, "Выберите хотя бы один файл (.pdf, .docx, .txt).")

    allowed_exts = {".pdf", ".docx", ".doc", ".txt", ".md"}
    files_payload: list[tuple[str, bytes]] = []
    for f in files:
        fname = (f.filename or "document.pdf").strip()
        ext = Path(fname).suffix.lower()
        if ext not in allowed_exts:
            continue
        raw_bytes = await f.read()
        if raw_bytes:
            files_payload.append((fname, raw_bytes))

    if not files_payload:
        raise HTTPException(400, "Поддерживаются файлы .pdf, .docx и .txt.")

    try:
        result = await run_in_threadpool(upload_and_catalog_files, files_payload)
        return result
    except Exception as exc:
        raise HTTPException(400, f"Ошибка обработки файлов: {exc}") from exc


@app.post("/api/wiki/ask")
async def wiki_ask_post(request: Request):
    """AI-поиск по базе знаний Platonus и генерация пошагового ответа со ссылками на источники."""
    from .modules.wiki.service import ask_wiki
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        query = str(body.get("query", "")).strip()
    else:
        form = await request.form()
        query = str(form.get("query", "")).strip()

    if not query:
        raise HTTPException(400, "Введите вопрос по Platonus.")

    try:
        res = await run_in_threadpool(ask_wiki, query)
        return res
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app.server:app", host="0.0.0.0", port=8000, reload=False)
