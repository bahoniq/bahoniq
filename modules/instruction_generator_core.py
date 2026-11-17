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
    steps = doc.get("steps", [])
    toc_items = "".join(f"<li>{step.get('number', i)}. {html.escape(step_heading(step))}</li>" for i, step in enumerate(steps, 1))
    blocks = []
    for i, step in enumerate(steps, 1):
        num = step.get("number", i)
        cap_text = clean_caption(step.get("caption"), num)
        note = f'<p class="note"><b>Важно:</b> {html.escape(step["note"])}</p>' if step.get("note") else ""
        img_html = ""
        if step.get("image"):
            img_html = f'''
            <div class="screen-container">
              <img src="{html.escape(step["image"])}" alt="{html.escape(cap_text)}">
            </div>
            <div class="caption"><b>Рисунок {num}.</b> {html.escape(cap_text)}</div>
            '''
        blocks.append(f'''<section class="step-card">
          <h2>{num}. {html.escape(step_heading(step))}</h2>
          <p>{html.escape(step.get("text", ""))}</p>
          {note}
          {img_html}
        </section>''')

    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{html.escape(doc['title'])}</title><style>
    @page {{
      size: A4;
      margin: 10mm;
    }}
    body {{
      font: 12pt "Times New Roman", Times, "Liberation Serif", serif;
      color: #000;
      max-width: 820px;
      margin: 24px auto;
      line-height: 1.35;
      border: 1.15pt solid #000;
      padding: 32px;
      box-sizing: border-box;
      background: #fff;
    }}
    header {{
      margin-bottom: 24px;
      text-align: center;
    }}
    .super-title {{
      font-size: 15pt;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    h1 {{
      font-size: 16pt;
      margin: 0 0 18px;
      font-weight: 700;
    }}
    .toc {{
      margin: 18px 0 28px;
      padding: 14px 18px;
      border: 1.15pt solid #000;
      background: #fafafa;
    }}
    .toc-title {{
      font-weight: 700;
      margin-bottom: 8px;
      text-align: center;
      font-size: 13pt;
    }}
    .toc ol {{
      margin: 0;
      padding-left: 24px;
      list-style-type: decimal;
    }}
    .toc li {{
      margin: 5px 0;
    }}
    .step-card {{
      margin-bottom: 28px;
      page-break-inside: avoid;
    }}
    h2 {{
      font-size: 13pt;
      color: #000;
      margin: 20px 0 8px;
      font-weight: 700;
    }}
    p {{
      margin: 6px 0;
      text-align: justify;
    }}
    .note {{
      margin: 8px 0;
      padding: 6px 12px;
      background: #f4f4f4;
      border-left: 3px solid #000;
    }}
    .screen-container {{
      width: 16cm;
      height: 9cm;
      max-width: 100%;
      aspect-ratio: 16 / 9;
      background: #ffffff;
      border: 1.15pt solid #000000;
      margin: 12px auto 6px auto;
      display: flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
      overflow: hidden;
    }}
    .screen-container img {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain;
      display: block;
      margin: auto;
    }}
    .caption {{
      text-align: center;
      font-size: 11pt;
      color: #000;
      margin: 4px 0 16px;
    }}
    @media (max-width: 768px) {{
      body {{
        padding: 16px;
        margin: 8px;
      }}
      .screen-container {{
        width: 100%;
        height: auto;
        aspect-ratio: 16 / 9;
      }}
    }}
    </style></head><body><header><div class="super-title">Инструкция</div><h1>{html.escape(doc['title'])}</h1></header><div class="toc"><div class="toc-title">Содержание</div><ol>{toc_items}</ol></div>{''.join(blocks)}</body></html>'''


def _image_bytes(value: str) -> bytes | None:
    if not value: return None
    if value.startswith("data:"):
        try: return base64.b64decode(value.split(",", 1)[1])
        except Exception: return None
    try: return Path(value).read_bytes()
    except Exception: return None


def normalize_screenshot_16_9(raw: bytes) -> tuple[bytes | None, bytes | None]:
    """
    Fits any screenshot into a fixed 16:9 container with pure white background,
    strictly preserving original aspect ratio (never stretched or distorted).
    If the screenshot is vertical/tall, generates an auxiliary zoomed detail crop.
    Returns (main_png_bytes, optional_detail_png_bytes).
    """
    if not raw:
        return None, None
    try:
        from PIL import Image as PILImage
        source = io.BytesIO(raw)
        im = PILImage.open(source)
        w, h = im.size
        if w <= 0 or h <= 0:
            return None, None

        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            im_rgba = im.convert("RGBA")
        else:
            im_rgba = im.convert("RGB")

        target_ratio = 16.0 / 9.0
        img_ratio = w / float(h)
        if img_ratio >= target_ratio:
            cw = w
            ch = int(round(w * 9.0 / 16.0))
            ox = 0
            oy = (ch - h) // 2
        else:
            ch = h
            cw = int(round(h * 16.0 / 9.0))
            ox = (cw - w) // 2
            oy = 0

        bg = PILImage.new("RGB", (cw, ch), (255, 255, 255))
        if im_rgba.mode == "RGBA":
            bg.paste(im_rgba, (ox, oy), mask=im_rgba.getchannel("A"))
        else:
            bg.paste(im_rgba, (ox, oy))

        out_main = io.BytesIO()
        bg.save(out_main, format="PNG")
        main_bytes = out_main.getvalue()

        # If image is vertical / tall, create an enlarged detail crop of the active area
        detail_bytes = None
        if h > w * 1.15:
            crop_h = min(h, int(round(w * 9.0 / 16.0)))
            crop_im = im_rgba.crop((0, 0, w, crop_h))
            crop_cw = w
            crop_ch = int(round(w * 9.0 / 16.0))
            crop_bg = PILImage.new("RGB", (crop_cw, crop_ch), (255, 255, 255))
            if crop_im.mode == "RGBA":
                crop_bg.paste(crop_im, (0, (crop_ch - crop_h) // 2), mask=crop_im.getchannel("A"))
            else:
                crop_bg.paste(crop_im, (0, (crop_ch - crop_h) // 2))
            out_det = io.BytesIO()
            crop_bg.save(out_det, format="PNG")
            detail_bytes = out_det.getvalue()

        return main_bytes, detail_bytes
    except Exception:
        return None, None


def make_border_canvas(font_name: str):
    """
    Creates a Canvas maker that renders a solid 1.15 pt black border and centered page
    number on EVERY page (both even and odd) during save(), guaranteeing consistent borders
    regardless of flowables or page breaks.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    class InstructionBorderCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.pages = []

        def showPage(self):
            self.pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            for page in self.pages:
                self.__dict__.update(page)
                self.saveState()
                self.setStrokeColorRGB(0, 0, 0)
                self.setLineWidth(1.15)
                # Continuous black border: 10 mm from edges on ALL pages (even and odd)
                self.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm)
                self.setFont(font_name, 11)
                self.setFillColorRGB(0, 0, 0)
                # Centered page number at 14 mm from bottom
                self.drawCentredString(A4[0] / 2, 14 * mm, str(self._pageNumber))
                self.restoreState()
                super().showPage()
            super().save()

    return InstructionBorderCanvas


def to_pdf(doc: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether

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

    out = io.BytesIO()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("GSNormal", parent=styles["BodyText"], fontName=font, fontSize=12, leading=14.5, textColor=colors.black, spaceAfter=5)
    title = ParagraphStyle("GSTitle", parent=normal, fontName=font_bold, fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=14)
    contents = ParagraphStyle("GSContents", parent=normal, fontName=font_bold, fontSize=12, leading=18, leftIndent=7*mm, rightIndent=5*mm)
    heading = ParagraphStyle("GSHeading", parent=normal, fontName=font_bold, fontSize=13, leading=16, spaceBefore=7, spaceAfter=4, keepWithNext=True)
    caption = ParagraphStyle("GSCaption", parent=normal, fontSize=11, leading=13, alignment=TA_CENTER, spaceBefore=2, spaceAfter=6)
    note_style = ParagraphStyle("GSNote", parent=normal, fontSize=12, leading=14.5, spaceBefore=2, spaceAfter=6)

    # 16x9 cm image table styling (160mm x 90mm with 1.15pt black border and white background)
    img_tbl_style = TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.15, colors.black),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ])

    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=15*mm, bottomMargin=17*mm, title=doc["title"])
    story = [Spacer(1, 17*mm), Paragraph("Инструкция", title), Paragraph(html.escape(doc["title"]), title), Spacer(1, 5*mm)]
    for i, step in enumerate(doc.get("steps", []), 1):
        num = step.get("number", i)
        story.append(Paragraph(f"{num}. {html.escape(step_heading(step))}", contents))
    story += [PageBreak()]

    for i, step in enumerate(doc.get("steps", []), 1):
        num = step.get("number", i)
        chunk = [
            Paragraph(f"{num}. {html.escape(step_heading(step))}", heading),
            Paragraph(html.escape(step.get("text", "")), normal),
        ]
        if step.get("note"):
            chunk.append(Paragraph(f"<b>Важно:</b> {html.escape(step['note'])}", note_style))

        raw = _image_bytes(step.get("image", ""))
        if raw:
            main_png, detail_png = normalize_screenshot_16_9(raw)
            if main_png:
                try:
                    # Container 16 cm x 9 cm (160mm x 90mm)
                    picture = Image(io.BytesIO(main_png), width=160*mm, height=90*mm)
                    frame = Table([[picture]], colWidths=[160*mm], rowHeights=[90*mm], hAlign="CENTER")
                    frame.setStyle(img_tbl_style)
                    cap_text = clean_caption(step.get("caption"), num)
                    cap = Paragraph(f"<b>Рисунок {num}.</b> {html.escape(cap_text)}", caption)
                    chunk += [Spacer(1, 2*mm), frame, cap]

                    if detail_png:
                        det_pic = Image(io.BytesIO(detail_png), width=160*mm, height=90*mm)
                        det_frame = Table([[det_pic]], colWidths=[160*mm], rowHeights=[90*mm], hAlign="CENTER")
                        det_frame.setStyle(img_tbl_style)
                        det_cap = Paragraph(f"<b>Рисунок {num}.1.</b> {html.escape(cap_text)} (увеличенный фрагмент)", caption)
                        chunk += [Spacer(1, 3*mm), det_frame, det_cap]
                except Exception:
                    pass

        story.append(KeepTogether(chunk))

    pdf.build(story, canvasmaker=make_border_canvas(font))
    return out.getvalue()
