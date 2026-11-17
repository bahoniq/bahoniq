from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from ..modules.instruction_generator import generate_instruction, to_html, to_markdown, to_pdf

router = APIRouter(prefix="/api/instruction-generator", tags=["instruction-generator"])

class InstructionPayload(BaseModel):
    title: str = ""
    audience: str = ""
    department: str = ""
    intro: str = ""
    steps: list[dict] = []

@router.post("/generate")
def generate(payload: InstructionPayload):
    try: return generate_instruction(payload.model_dump())
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@router.post("/export/{kind}")
def export(kind: str, payload: dict):
    try:
        if kind == "pdf": return Response(to_pdf(payload), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="instruction.pdf"'})
        if kind == "html": return Response(to_html(payload).encode("utf-8"), media_type="text/html; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="instruction.html"'})
        if kind == "md": return Response(to_markdown(payload).encode("utf-8"), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="instruction.md"'})
        raise HTTPException(400, "Неизвестный формат")
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
