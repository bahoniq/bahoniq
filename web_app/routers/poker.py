"""FastAPI-роутер модуля Poker Club для BahonIQ Work Center."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from poker.poker_routes import dispatch
from poker.poker_state import PokerService

ROOT = Path(__file__).resolve().parents[2]
POKER_STATIC = ROOT / "web_app" / "static" / "poker"
POKER_DATA = ROOT / "data" / "poker_save.json"

SERVICE = PokerService(POKER_DATA)

router = APIRouter(tags=["poker"])


@router.get("/poker", include_in_schema=False)
@router.get("/poker/", include_in_schema=False)
def poker_page():
    return FileResponse(
        POKER_STATIC / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/api/poker/{endpoint}")
async def poker_api_get(endpoint: str, request: Request):
    status, payload = dispatch(SERVICE, "GET", f"/api/poker/{endpoint}", None)
    return JSONResponse(content=payload, status_code=status)


@router.post("/api/poker/{endpoint}")
async def poker_api_post(endpoint: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    status, payload = dispatch(SERVICE, "POST", f"/api/poker/{endpoint}", body)
    return JSONResponse(content=payload, status_code=status)
