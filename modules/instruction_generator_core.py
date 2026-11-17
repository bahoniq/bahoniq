"""Core services for BahonIQ Instruction Generator AI."""
from __future__ import annotations

import base64
import html
import io
import json
import re
from pathlib import Path
from typing import Any

STYLE_PROFILE = {
    "name": "КазНМУ — университетская инструкция",
    "language": "ru",
    "tone": "официально-деловой, ясный, без канцелярской перегрузки",
    "step_pattern": "Краткое действие в повелительной форме, затем ожидаемый результат или важное условие.",
    "caption_pattern": "Рисунок {number}. {description}",
    "rules": [
        "Сохранять названия кнопок и разделов в кавычках-ёлочках.",
        "Не придумывать элементы интерфейса, ссылки, пароли и условия.",
        "Один шаг должен описывать одно законченное действие.",
        "Предупреждения формулировать отдельно и только при наличии в исходном тексте.",
        "Использовать сквозную нумерацию шагов и рисунков.",
    ],
}


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip()).strip()


def normalize_audience(value: Any) -> str:
    """Turns terse comma-separated labels into a presentable document field."""
    text = clean_text(value)
    if not text:
        return ""
    parts = [p.strip().capitalize() for p in re.split(r"[,;]+", text) if p.strip()]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " и " + parts[-1].lower()


def clean_caption(value: Any, number: int) -> str:
    """Removes user-entered 'Рисунок N' to prevent duplicated prefixes."""
    text = clean_text(value)
    text = re.sub(r"^рис(?:унок|\.)?\s*\d+(?:\.\d+)?\s*[.\-–—:]?\s*", "", text, flags=re.I)
    return text.rstrip(" .") or f"Выполнение шага {number}"


def step_heading(step: dict[str, Any]) -> str:
    caption = clean_caption(step.get("caption"), int(step.get("number") or 0))
    if not re.fullmatch(r"Выполнение шага \d+", caption, flags=re.I):
        return caption
    text = re.sub(r"https?://\S+", "", clean_text(step.get("text"))).strip(" .")
    text = re.split(r"(?<=[.!?])\s+", text, 1)[0].strip(" .")
    return (text[:90].rstrip() if text else f"Шаг {step.get('number', '')}")


def fallback_rewrite(text: str) -> str:
    value = clean_text(text)
    if not value:
        return ""
    value = re.sub(r"^(потом|далее|затем|после этого|нужно)\s+", "", value, flags=re.I)
    value = re.sub(r"\bтыкаем\b", "нажмите", value, flags=re.I)
    value = re.sub(r"\bкликаем\b", "нажмите", value, flags=re.I)
    value = value[0].upper() + value[1:]
    if value[-1] not in ".!?":
        value += "."
    return value


def _extract_json(raw: str) -> dict[str, Any]:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("ИИ не вернул корректный JSON")
        data = json.loads(value[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("Неверный формат ответа ИИ")
    return data


def generate_instruction(payload: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(payload.get("title")) or "Инструкция"
    audience = normalize_audience(payload.get("audience"))
    department = clean_text(payload.get("department"))
    intro = clean_text(payload.get("intro"))
    source_steps = [s for s in payload.get("steps", []) if clean_text(s.get("text"))]
    if not source_steps:
        raise ValueError("Добавьте хотя бы один заполненный шаг")

    system = (
        "Ты профессиональный составитель эталонных регламентов и официальных инструкций университета КазНМУ. "
        "Твоя задача — взять сырые черновые действия и скриншоты от пользователя и оформить строгую пошаговую инструкцию в безупречном деловом стиле. "
        "Правила оформления:\n"
        "1. Преобразуй разговорную речь ('потом заходим сюда', 'тыкаем на кнопку') в точные пошаговые формулировки в повелительном наклонении: 'Перейдите в раздел «...»', 'Нажмите кнопку «...»', 'В открывшемся окне заполните поле «...»'.\n"
        "2. Все названия интерфейсных элементов, кнопок, вкладок, меню и разделов обязательно оформляй в кавычки-ёлочки «...».\n"
        "3. Один шаг — одно законченное действие с указанием ожидаемого результата.\n"
        "4. К каждому шагу в поле 'caption' укажи емкое, точное название действия для скриншота (например: 'Раздел согласования заявок', 'Форма добавления нового сотрудника'). Не пиши префикс 'Рисунок N' — он проставляется автоматически.\n"
        "5. Если в действии есть предупреждение, нюанс или ошибка — вынеси это в поле 'note' (например: 'Поля, отмеченные звёздочкой, обязательны к заполнению').\n"
        "6. Сохраняй все точные данные, URL, логику и названия из черновика, не выдумывай несуществующих фактов.\n"
        "Верни строго валидный JSON: "
        "{\"title\":\"...\",\"intro\":\"...\",\"steps\":[{\"text\":\"...\",\"caption\":\"...\",\"note\":\"\"}]}"
    )
    prompt = json.dumps({
        "style_profile": STYLE_PROFILE,
        "document": {"title": title, "audience": audience, "department": department, "intro": intro},
        "steps": [{"text": clean_text(s.get("text")), "caption": clean_text(s.get("caption"))} for s in source_steps],
    }, ensure_ascii=False)
    data: dict[str, Any] = {}
    provider = "local-rules"
    try:
        from ai_service import generate_text
        raw = generate_text(prompt, system_instruction=system, temperature=0.1, timeout=120)
        data = _extract_json(raw[0] if isinstance(raw, tuple) else raw)
        provider = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else "ai"
    except Exception:
        data = {}

    ai_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    result_steps = []
    for index, source in enumerate(source_steps, 1):
        candidate = ai_steps[index - 1] if index <= len(ai_steps) and isinstance(ai_steps[index - 1], dict) else {}
        result_steps.append({
            "number": index,
            "text": clean_text(candidate.get("text")) or fallback_rewrite(source.get("text", "")),
            "caption": clean_caption(candidate.get("caption") or source.get("caption"), index),
            "note": clean_text(candidate.get("note")),
            "image": source.get("image", ""),
        })
    return {
        "title": clean_text(data.get("title")) or title,
        "audience": audience,
        "department": department,
        "intro": clean_text(data.get("intro")) or fallback_rewrite(intro),
        "steps": result_steps,
        "provider": provider,
        "style": STYLE_PROFILE["name"],
    }


def to_markdown(doc: dict[str, Any]) -> str:
    lines = [f"# {doc['title']}", ""]
    if doc.get("department"): lines += [f"**Подразделение:** {doc['department']}", ""]
    if doc.get("audience"): lines += [f"**Для кого:** {doc['audience']}", ""]
    if doc.get("intro"): lines += [doc['intro'], ""]
    for step in doc.get("steps", []):
        lines += [f"## Шаг {step['number']}", "", step["text"], ""]
        if step.get("note"): lines += [f"> **Примечание:** {step['note']}", ""]
        if step.get("image"): lines += [f"![{step['caption']}](image-step-{step['number']}.png)", ""]
        lines += [f"*Рисунок {step['number']}. {step['caption']}*", ""] if step.get("image") else []
    return "\n".join(lines).strip() + "\n"


def to_html(doc: dict[str, Any]) -> str:
    blocks = []
    for step in doc.get("steps", []):
        image = f'<img src="{html.escape(step["image"])}" alt="{html.escape(step["caption"])}">' if step.get("image") else ""
        caption = f'<div class="caption">Рисунок {step["number"]}. {html.escape(step["caption"])}</div>' if image else ""
        note = f'<div class="note"><b>Примечание.</b> {html.escape(step["note"])}</div>' if step.get("note") else ""
        blocks.append(f'<section><h2>Шаг {step["number"]}</h2><p>{html.escape(step["text"])}</p>{note}{image}{caption}</section>')
    meta = " · ".join(x for x in (doc.get("department"), doc.get("audience")) if x)
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{html.escape(doc['title'])}</title><style>
    @page{{size:A4;margin:18mm}}body{{font:11pt Arial,sans-serif;color:#17212b;max-width:820px;margin:32px auto;line-height:1.55}}header{{border-bottom:3px solid #009246;margin-bottom:28px}}h1{{font-size:24pt;margin:0 0 8px}}h2{{font-size:15pt;color:#007a3d;margin-top:28px}}.meta,.caption{{color:#66756d}}img{{display:block;max-width:100%;max-height:520px;object-fit:contain;margin:18px auto 8px;border:1px solid #d9e2dc;border-radius:8px;padding:6px;box-sizing:border-box}}.caption{{text-align:center;font-size:9pt}}.note{{background:#eef4ff;border-left:4px solid #2563eb;padding:10px 12px;margin:12px 0}}footer{{margin-top:36px;border-top:1px solid #d9e2dc;padding-top:8px;color:#66756d;font-size:9pt}}</style></head><body><header><h1>{html.escape(doc['title'])}</h1><p class="meta">{html.escape(meta)}</p></header><p>{html.escape(doc.get('intro',''))}</p>{''.join(blocks)}<footer>КазНМУ · Стандартизированная инструкция</footer></body></html>'''


def _image_bytes(value: str) -> bytes | None:
    if not value: return None
    if value.startswith("data:"):
        try: return base64.b64decode(value.split(",", 1)[1])
        except Exception: return None
    try: return Path(value).read_bytes()
    except Exception: return None


def to_pdf(doc: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table,
        TableStyle, CondPageBreak,
    )
    font = "Helvetica"
    for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(fp).exists():
            font = "BahonIQUni"; pdfmetrics.registerFont(TTFont(font, fp)); break
    out = io.BytesIO(); styles = getSampleStyleSheet()
    normal = ParagraphStyle("BNormal", parent=styles["BodyText"], fontName=font, fontSize=10.5, leading=15, spaceAfter=8)
    title = ParagraphStyle("BTitle", parent=normal, fontSize=22, leading=28, alignment=1, textColor=colors.HexColor("#17352A"), spaceAfter=14)
    eyebrow = ParagraphStyle("BEyebrow", parent=normal, fontSize=10, leading=13, alignment=1, textColor=colors.HexColor("#66756D"), spaceAfter=10)
    contents = ParagraphStyle("BContents", parent=normal, fontSize=11, leading=17, leftIndent=8*mm, rightIndent=8*mm)
    heading = ParagraphStyle("BHeading", parent=normal, fontSize=14, leading=18, textColor=colors.HexColor("#007A3D"), spaceBefore=10, spaceAfter=7, keepWithNext=True)
    caption = ParagraphStyle("BCaption", parent=normal, fontSize=8.5, leading=11, textColor=colors.HexColor("#66756D"), alignment=TA_CENTER)
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=22*mm, bottomMargin=18*mm, title=doc["title"])
    story = [Spacer(1, 22*mm), Paragraph("КАЗАХСКИЙ НАЦИОНАЛЬНЫЙ МЕДИЦИНСКИЙ УНИВЕРСИТЕТ", eyebrow), Spacer(1, 5*mm), Paragraph("ИНСТРУКЦИЯ", eyebrow), Paragraph(html.escape(doc["title"]), title)]
    meta = " · ".join(x for x in (doc.get("department"), doc.get("audience")) if x)
    if meta: story += [Paragraph(html.escape(meta), caption), Spacer(1, 7*mm)]
    if doc.get("intro"): story += [Paragraph(html.escape(doc["intro"]), normal), Spacer(1, 8*mm)]
    story += [Paragraph("Содержание", heading)]
    for step in doc.get("steps", []):
        story.append(Paragraph(f"{step['number']}. {html.escape(step_heading(step))}", contents))
    story += [PageBreak()]
    for step in doc.get("steps", []):
        story += [CondPageBreak(55*mm), Paragraph(f"{step['number']}. {html.escape(step_heading(step))}", heading), Paragraph(html.escape(step["text"]), normal)]
        if step.get("note"):
            note_table = Table([[Paragraph(f"<b>Важно.</b> {html.escape(step['note'])}", normal)]], colWidths=[165*mm])
            note_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFF7E6")),("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#D99A23")),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
            story += [note_table, Spacer(1, 3*mm)]
        raw = _image_bytes(step.get("image", ""))
        if raw:
            try:
                from PIL import Image as PILImage
                source = io.BytesIO(raw); im = PILImage.open(source); w, h = im.size
                maxw = 165*mm if w >= h else 92*mm
                maxh = 112*mm
                scale = min(maxw/w, maxh/h)
                picture = Image(io.BytesIO(raw), width=w*scale, height=h*scale)
                frame = Table([[picture]], colWidths=[w*scale + 4*mm], hAlign="CENTER")
                frame.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#AAB8B1")),("LEFTPADDING",(0,0),(-1,-1),2*mm),("RIGHTPADDING",(0,0),(-1,-1),2*mm),("TOPPADDING",(0,0),(-1,-1),2*mm),("BOTTOMPADDING",(0,0),(-1,-1),2*mm)]))
                story += [Spacer(1, 2*mm), frame, Spacer(1, 1.5*mm), Paragraph(f"Рисунок {step['number']}. {html.escape(clean_caption(step['caption'], step['number']))}", caption), Spacer(1, 3*mm)]
            except Exception: pass
    def first_page(canvas, flow_doc):
        _page_decor(canvas, flow_doc, doc, title_page=True)
    def later_page(canvas, flow_doc):
        _page_decor(canvas, flow_doc, doc, title_page=False)
    pdf.build(story, onFirstPage=first_page, onLaterPages=later_page)
    return out.getvalue()


def _page_decor(canvas, doc, instruction: dict[str, Any], title_page: bool = False):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    footer_font = "BahonIQUni" if "BahonIQUni" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    canvas.saveState(); canvas.setStrokeColorRGB(.10,.23,.18); canvas.setLineWidth(.8)
    canvas.rect(10*mm, 10*mm, A4[0]-20*mm, A4[1]-20*mm)
    canvas.setFont(footer_font, 8); canvas.setFillColorRGB(.4,.46,.43)
    department = clean_text(instruction.get("department")) or "КазНМУ"
    canvas.drawString(18*mm, 13*mm, department)
    canvas.drawRightString(A4[0]-18*mm, 13*mm, f"Страница {doc.page}")
    if not title_page:
        canvas.setFont(footer_font, 7.5)
        canvas.drawString(18*mm, A4[1]-14*mm, clean_text(instruction.get("title"))[:80])
        canvas.setStrokeColorRGB(0,.57,.27); canvas.line(18*mm,A4[1]-16*mm,A4[0]-18*mm,A4[1]-16*mm)
    canvas.restoreState()
