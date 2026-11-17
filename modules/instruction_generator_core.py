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


def make_step_title(caption: Any, text: Any, number: int) -> str:
    """
    Creates an automatic concise step title strictly 2 to 7 words in length.
    Examples: 'Авторизация в системе', 'Выбор студента', 'Добавление дисциплины'.
    Never uses the full action description as a heading. Never cuts mid-word.
    """
    cap = clean_text(caption)
    # Strip any 'Рисунок N', 'Шаг N', 'Этап N', 'Выполнение шага N'
    cap = re.sub(r"^(?:рис(?:унок|\.)?|шаг|этап)\s*\d+(?:\.\d+)?\s*[.\-–—:]?\s*", "", cap, flags=re.I)
    cap = re.sub(r"^выполнение\s+шага\s+\d+\s*[.\-–—:]?\s*", "", cap, flags=re.I).strip(" .")

    words = cap.split()
    if 2 <= len(words) <= 7:
        title = " ".join(words)
        return title[0].upper() + title[1:]

    if len(words) == 1:
        w0 = words[0].strip(".,;:«»\"'")
        wl = w0.lower()
        if "авториз" in wl or "вход" in wl:
            return "Авторизация в системе"
        if "студент" in wl:
            return "Выбор студента"
        if "дисциплин" in wl:
            return "Добавление дисциплины"
        if "заявк" in wl:
            return "Работа с заявками"
        if "сохран" in wl:
            return "Сохранение изменений"
        if "профил" in wl:
            return "Переход в профиль"
        if "настрой" in wl:
            return "Параметры и настройки"
        if "поиск" in wl:
            return "Поиск в системе"
        return f"{w0.capitalize()} в системе"

    # If caption is missing or too long, extract a 2-7 word action phrase from text
    raw_text = clean_text(text)
    raw_text = re.sub(r"https?://\S+", "", raw_text)
    raw_text = re.sub(r"^(?:потом|далее|затем|после этого|нужно|необходимо|следует|для этого)\s+", "", raw_text, flags=re.I)

    first_clause = re.split(r"[.!?;]\s+", raw_text)[0].strip()
    words = first_clause.split()

    if len(words) > 7:
        words = words[:6]
        while len(words) > 2 and words[-1].lower().strip("«»\"'.,") in {
            "в", "на", "с", "по", "для", "и", "к", "от", "из", "через", "о", "об", "при", "чтобы",
            "нажимаем", "нажмите", "выбираем", "выберите", "переходим", "перейдите", "открываем", "откройте"
        }:
            words.pop()

    if 2 <= len(words) <= 7:
        title = " ".join(words).strip(".,;:-—– ")
        return title[0].upper() + title[1:]

    if len(words) == 1 and words[0]:
        return f"{words[0].strip('.,;:«»\"\'').capitalize()} в системе"

    return f"Этап {number}"


def clean_caption(value: Any, number: int) -> str:
    """Removes user-entered 'Рисунок N' and 'Выполнение шага N'."""
    text = clean_text(value)
    text = re.sub(r"^рис(?:унок|\.)?\s*\d+(?:\.\d+)?\s*[.\-–—:]?\s*", "", text, flags=re.I)
    text = re.sub(r"^выполнение\s+шага\s+\d+\s*[.\-–—:]?\s*", "", text, flags=re.I).strip(" .")
    return text.rstrip(" .") or f"Этап {number}"


def step_heading(step: dict[str, Any]) -> str:
    num = int(step.get("number") or 1)
    return make_step_title(step.get("caption"), step.get("text"), num)


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
    source_steps = [s for s in payload.get("steps", []) if clean_text(s.get("text")) or s.get("image")]
    if not source_steps:
        raise ValueError("Добавьте хотя бы один заполненный шаг")

    system = (
        "Ты редактор официальных университетских инструкций. Твоя задача — составить строгий регламент по черновику.\n"
        "Правила:\n"
        "1. Для каждого шага обязательно создай КРАТКОЕ НАЗВАНИЕ в поле 'caption' длиной строго 2-7 слов в именительном падеже (например: «Авторизация в системе», «Выбор студента», «Добавление дисциплины», «Сохранение изменений»). Полное описание нельзя использовать как заголовок!\n"
        "2. В поле 'text' напиши четкое пошаговое действие в повелительной форме ('Перейдите в раздел «...»', 'Нажмите кнопку «...»'). Не дублируй краткое название в начале описания.\n"
        "3. Поле 'note' заполняй только если в исходнике прямо указано предупреждение или важное примечание, иначе оставь пустой строкой.\n"
        "Верни строго JSON: {\"title\":\"...\",\"intro\":\"...\",\"steps\":[{\"text\":\"...\",\"caption\":\"...\",\"note\":\"\"}]}"
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
        raw_caption = candidate.get("caption") or source.get("caption") or ""
        short_title = make_step_title(raw_caption, source_text, index)
        action_text = clean_text(candidate.get("text")) or fallback_rewrite(source_text or short_title)
        result_steps.append({
            "number": index,
            "text": action_text,
            "caption": short_title,
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
    for i, step in enumerate(doc.get("steps", []), 1):
        num = step.get("number", i)
        title = make_step_title(step.get("caption"), step.get("text"), num)
        lines += [f"## {num}. {title}", "", step.get("text", ""), ""]
        if step.get("note"): lines += [f"> **Примечание:** {step['note']}", ""]
        if step.get("image"):
            lines += [f"![{title}](image-step-{num}.png)", ""]
            lines += [f"*Рисунок {num}. {title}*", ""]
    return "\n".join(lines).strip() + "\n"


def to_html(doc: dict[str, Any]) -> str:
    steps = doc.get("steps", [])
    toc_items = "".join(
        f"<li>{step.get('number', i)}. {html.escape(make_step_title(step.get('caption'), step.get('text'), step.get('number', i)))}</li>"
        for i, step in enumerate(steps, 1)
    )
    blocks = []
    for i, step in enumerate(steps, 1):
        num = step.get("number", i)
        title = make_step_title(step.get("caption"), step.get("text"), num)
        desc = step.get("text", "")
        # Remove identical repeat of title at the beginning of desc if present
        if desc.lower().startswith(title.lower()):
            desc = re.sub(r"^" + re.escape(title) + r"[.\s:—–-]+", "", desc, flags=re.I).strip()
            if desc:
                desc = desc[0].upper() + desc[1:]

        note = f'<p class="note"><b>Важно:</b> {html.escape(step["note"])}</p>' if step.get("note") else ""
        img_html = ""
        if step.get("image"):
            img_html = f'''
            <div class="screen-box">
              <img class="screenshot-img" src="{html.escape(step["image"])}" alt="{html.escape(title)}">
              <div class="caption"><b>Рисунок {num}.</b> {html.escape(title)}</div>
            </div>
            '''
        blocks.append(f'''<section class="step-card">
          <h2>{num}. {html.escape(title)}</h2>
          <p>{html.escape(desc)}</p>
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
    .screen-box {{
      margin: 14px auto 16px auto;
      text-align: center;
    }}
    .screenshot-img {{
      display: block;
      max-width: 16cm;
      max-height: 11cm;
      width: auto;
      height: auto;
      object-fit: contain;
      margin: 12px auto 6px auto;
      border: 1.15pt solid #000000;
      box-sizing: border-box;
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
      .screenshot-img {{
        max-width: 100%;
        max-height: 280px;
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


def draw_page_border(canvas, doc, font_name: str = "Times-Roman"):
    """
    Renders continuous solid black outer border on EVERY page (both even and odd)
    and draws the centered page number at 14mm from the bottom.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    canvas.saveState()
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(1.15)
    # Continuous black frame on every page: 10 mm from edges
    canvas.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm)
    canvas.setFont(font_name, 11)
    canvas.setFillColorRGB(0, 0, 0)
    # Centered page number at 14 mm from bottom
    canvas.drawCentredString(A4[0] / 2, 14 * mm, str(canvas.getPageNumber()))
    canvas.restoreState()


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

    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=15*mm, bottomMargin=17*mm, title=doc["title"])
    story = [Spacer(1, 17*mm), Paragraph("Инструкция", title), Paragraph(html.escape(doc["title"]), title), Spacer(1, 5*mm)]
    story.append(Paragraph("<b>Содержание</b>", heading))
    story.append(Spacer(1, 2*mm))

    steps = doc.get("steps", [])
    for i, step in enumerate(steps, 1):
        num = step.get("number", i)
        title_text = make_step_title(step.get("caption"), step.get("text"), num)
        story.append(Paragraph(f"{num}. {html.escape(title_text)}", contents))
    story += [PageBreak()]

    for i, step in enumerate(steps, 1):
        num = step.get("number", i)
        title_text = make_step_title(step.get("caption"), step.get("text"), num)
        desc = step.get("text", "")
        # Don't duplicate title in description if description starts with it
        if desc.lower().startswith(title_text.lower()):
            desc = re.sub(r"^" + re.escape(title_text) + r"[.\s:—–-]+", "", desc, flags=re.I).strip()
            if desc:
                desc = desc[0].upper() + desc[1:]

        chunk = [
            Paragraph(f"{num}. {html.escape(title_text)}", heading),
            Paragraph(html.escape(desc), normal),
        ]
        if step.get("note"):
            chunk.append(Paragraph(f"<b>Важно:</b> {html.escape(step['note'])}", note_style))

        raw = _image_bytes(step.get("image", ""))
        if raw:
            try:
                from PIL import Image as PILImage
                source = io.BytesIO(raw)
                im = PILImage.open(source)
                w, h = im.size
                if w > 0 and h > 0:
                    max_w = 160 * mm  # 16 cm
                    max_h = 110 * mm  # 11 cm
                    # Горизонтальное: максимальная ширина 16 см
                    # Вертикальное: максимальная высота 11 см
                    # Строго сохраняем пропорции, без фиксированного контейнера и без белых полей
                    if w >= h:
                        scale = min(max_w / w, max_h / h)
                    else:
                        scale = min(max_h / h, max_w / w)
                    dw = w * scale
                    dh = h * scale

                    picture = Image(io.BytesIO(raw), width=dw, height=dh)
                    frame = Table([[picture]], colWidths=[dw], rowHeights=[dh], hAlign="CENTER")
                    frame.setStyle(TableStyle([
                        ("BOX", (0, 0), (-1, -1), 1.15, colors.black),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]))
                    cap = Paragraph(f"<b>Рисунок {num}.</b> {html.escape(title_text)}", caption)
                    chunk += [Spacer(1, 2*mm), frame, Spacer(1, 1.5*mm), cap]
            except Exception:
                pass

        story.append(KeepTogether(chunk))

    on_page = lambda c, d: draw_page_border(c, d, font)
    pdf.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out.getvalue()
