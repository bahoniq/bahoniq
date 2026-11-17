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
    value = re.sub(r"^(потом|далее|затем)\s+", "", value, flags=re.I)
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
        "Ты редактор пошаговых инструкций. Работай ТОЛЬКО с фактами черновика. "
        "Запрещено придумывать проверки, предупреждения, обязательные условия, причины, поля, кнопки и действия. "
        "Сохраняй точные названия интерфейса, URL, числа и отрицания. Исправляй только язык, порядок слов и повторы. "
        "Поле note заполняй лишь тогда, когда исходный текст прямо содержит слова «важно», «обязательно», "
        "«примечание» или «обратите внимание»; иначе верни пустую строку. Верни только JSON: "
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
        source_text = clean_text(source.get("text"))
        explicit_note = bool(re.search(r"\b(?:важно|обязательно|примечани[ея]|обратите внимание)\b", source_text, re.I))
        result_steps.append({
            "number": index,
            "text": clean_text(candidate.get("text")) or fallback_rewrite(source.get("text", "")),
            "caption": clean_caption(candidate.get("caption") or source.get("caption"), index),
            "note": clean_text(candidate.get("note")) if explicit_note else "",
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
    toc_items = "".join(f"<li>{step['number']}. {html.escape(step_heading(step))}</li>" for step in doc.get("steps", []))
    blocks = []
    for step in doc.get("steps", []):
        image = f'<img src="{html.escape(step["image"])}" alt="{html.escape(step["caption"])}">' if step.get("image") else ""
        caption = f'<div class="caption"><b>Рисунок {step["number"]}.</b> {html.escape(clean_caption(step["caption"], step["number"]))}</div>' if image else ""
        note = f'<p class="note"><b>Важно:</b> {html.escape(step["note"])}</p>' if step.get("note") else ""
        blocks.append(f'<section><h2>{step["number"]}. {html.escape(step_heading(step))}</h2><p>{html.escape(step["text"])}</p>{note}{image}{caption}</section>')
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{html.escape(doc['title'])}</title><style>
    @page{{size:A4;margin:18mm}}body{{font:12pt "Times New Roman",Times,serif;color:#000;max-width:820px;margin:32px auto;line-height:1.35;border:1px solid #000;padding:36px;box-sizing:border-box}}header{{margin-bottom:28px}}h1{{font-size:16pt;text-align:center;margin:0 0 20px;font-weight:700}}h2{{font-size:13pt;color:#000;margin-top:20px}}.toc{{margin:20px 0 28px;padding:14px 18px;border:1px solid #000}}.toc-title{{font-weight:700;margin-bottom:8px;text-align:center}}.toc ol{{margin:0;padding-left:20px;list-style:none}}.toc li{{margin:5px 0}}img{{display:block;max-width:100%;max-height:520px;object-fit:contain;margin:12px auto 6px;border:1.2px solid #000;padding:0;box-sizing:border-box}}.caption{{text-align:center;font-size:11pt;color:#000}}.note{{margin:8px 0;color:#000}}</style></head><body><header><h1>Инструкция<br>{html.escape(doc['title'])}</h1></header><div class="toc"><div class="toc-title">Содержание</div><ol>{toc_items}</ol></div>{''.join(blocks)}</body></html>'''


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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, CondPageBreak, KeepTogether

    regular_candidates = (
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/timesnewroman.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    )
    bold_candidates = (
        "C:/Windows/Fonts/timesbd.ttf",
        "C:/Windows/Fonts/timesnewromanbold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    )
    regular_path = next((p for p in regular_candidates if Path(p).exists()), None)
    bold_path = next((p for p in bold_candidates if Path(p).exists()), regular_path)
    font, font_bold = "Times-Roman", "Times-Bold"
    if regular_path:
        font, font_bold = "InstructionTimes", "InstructionTimesBold"
        if font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font, regular_path))
        if font_bold not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_bold, bold_path))
        pdfmetrics.registerFontFamily("InstructionTimesFamily", normal=font, bold=font_bold, italic=font, boldItalic=font_bold)
    out = io.BytesIO(); styles = getSampleStyleSheet()
    normal = ParagraphStyle("GSNormal", parent=styles["BodyText"], fontName=font, fontSize=12, leading=14.5, textColor=colors.black, spaceAfter=5)
    title = ParagraphStyle("GSTitle", parent=normal, fontName=font_bold, fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=14)
    contents = ParagraphStyle("GSContents", parent=normal, fontName=font_bold, fontSize=12, leading=18, leftIndent=7*mm, rightIndent=5*mm)
    heading = ParagraphStyle("GSHeading", parent=normal, fontName=font_bold, fontSize=13, leading=16, spaceBefore=7, spaceAfter=4, keepWithNext=True)
    caption = ParagraphStyle("GSCaption", parent=normal, fontSize=11, leading=13, alignment=TA_CENTER, spaceBefore=2, spaceAfter=6)
    note_style = ParagraphStyle("GSNote", parent=normal, fontSize=12, leading=14.5, spaceBefore=2, spaceAfter=6)
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=15*mm, bottomMargin=17*mm, title=doc["title"])
    story = [Spacer(1, 17*mm), Paragraph("Инструкция", title), Paragraph(html.escape(doc["title"]), title), Spacer(1, 5*mm)]
    for step in doc.get("steps", []):
        story.append(Paragraph(f"{step['number']}. {html.escape(step_heading(step))}", contents))
    story += [PageBreak()]
    for step in doc.get("steps", []):
        chunk = [Paragraph(f"{step['number']}. {html.escape(step_heading(step))}", heading), Paragraph(html.escape(step["text"]), normal)]
        if step.get("note"):
            chunk.append(Paragraph(f"<b>Важно:</b> {html.escape(step['note'])}", note_style))
        raw = _image_bytes(step.get("image", ""))
        if raw:
            try:
                from PIL import Image as PILImage
                source = io.BytesIO(raw); im = PILImage.open(source); w, h = im.size
                maxw = 165*mm if w >= h else 96*mm
                maxh = 105*mm
                scale = min(maxw/w, maxh/h)
                picture = Image(io.BytesIO(raw), width=w*scale, height=h*scale)
                frame = Table([[picture]], colWidths=[w*scale], hAlign="CENTER")
                frame.setStyle(TableStyle([("BOX",(0,0),(-1,-1),1.15,colors.black),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
                cap = Paragraph(f"<b>Рисунок {step['number']}.</b> {html.escape(clean_caption(step['caption'], step['number']))}", caption)
                chunk += [Spacer(1, 2*mm), frame, cap]
            except Exception: pass
        story.append(KeepTogether(chunk))
    pdf.build(story, onFirstPage=lambda c,d:_page_decor(c,d,font), onLaterPages=lambda c,d:_page_decor(c,d,font))
    return out.getvalue()


def _page_decor(canvas, doc, font_name: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    canvas.saveState(); canvas.setStrokeColorRGB(0,0,0); canvas.setLineWidth(1)
    canvas.rect(10*mm, 10*mm, A4[0]-20*mm, A4[1]-20*mm)
    canvas.setFont(font_name, 11); canvas.setFillColorRGB(0,0,0)
    canvas.drawCentredString(A4[0]/2, 14*mm, str(doc.page))
    canvas.restoreState()
