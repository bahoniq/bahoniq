
"""BahonIQ Ticket Writer AI.

Простой локальный редактор обращений: пользователь описывает проблему
обычными словами, а модуль формирует название и грамотный текст заявки.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

try:
    import tkinter as tk
    from tkinter import messagebox
except (ImportError, ModuleNotFoundError):
    tk = None
    messagebox = None

from config import WHITE
from services.settings_service import get_theme


OLLAMA_URL = os.getenv(
    "BAHONIQ_TICKET_OLLAMA_URL", "http://127.0.0.1:11434/api/chat"
)
OLLAMA_TAGS_URL = os.getenv(
    "BAHONIQ_TICKET_OLLAMA_TAGS_URL", "http://127.0.0.1:11434/api/tags"
)
OLLAMA_MODEL = os.getenv(
    "BAHONIQ_TICKET_MODEL",
    "qwen2.5:3b",
)
REQUEST_TIMEOUT = int(os.getenv("BAHONIQ_TICKET_TIMEOUT", "180"))

GREEN = "#009246"
GREEN_DARK = "#007A3D"
RED = "#CE2B37"
NAVY = "#183153"
SOFT_GREEN = "#E8F5EE"
SOFT_BLUE = "#EEF4FF"


def _open_local(request: str | urllib.request.Request, timeout: int):
    """Открывает локальную Ollama напрямую, минуя прокси Windows."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _sentence_case(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _fallback_ticket(problem: str) -> dict[str, str]:
    """Безопасный результат без AI: ничего не добавляет к фактам пользователя."""
    clean = _sentence_case(problem)
    first = re.split(r"[.!?\n]", clean, maxsplit=1)[0].strip()
    first = re.sub(r"^(?:добрый день|здравствуйте)[,! ]*", "", first, flags=re.I)
    title = first or "Описание проблемы в информационной системе"

    title_words = re.findall(r"\S+", title)
    if len(title_words) > 10:
        title = " ".join(title_words[:7]).rstrip(" ,;:-")

    title = _sentence_case(title).rstrip(".")
    description = (
        f"{clean.rstrip('.!?')}.\n\n"
        "Просим проверить указанную ситуацию и предоставить рекомендации "
        "по её устранению."
    )
    return {"title": title, "description": description, "source": "fallback"}


def _select_model() -> str:
    """Выбирает настроенную модель либо доступную локальную Qwen-модель."""
    try:
        with _open_local(OLLAMA_TAGS_URL, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        models = [
            str(item.get("name") or "").strip()
            for item in data.get("models", [])
            if isinstance(item, dict) and item.get("name")
        ]
        if not models or OLLAMA_MODEL in models:
            return OLLAMA_MODEL
        if "qwen2.5:7b" in models:
            return "qwen2.5:7b"
        qwen = [m for m in models if "qwen" in m.casefold()]
        return qwen[0] if qwen else models[0]
    except Exception:
        return OLLAMA_MODEL


def _extract_json(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Qwen не вернула JSON с текстом заявки.")
        data = json.loads(text[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("Ответ Qwen имеет неверную структуру.")

    return data


def _validate_ai_ticket(problem: str, title: str, description: str) -> None:
    """Проверяет достоверность ответа, не отклоняя нормальные длинные названия."""
    title = _clean_text(title)
    description = _clean_text(description)

    if not title:
        raise ValueError("Qwen не сформировала название заявки.")

    if len(title) > 180:
        raise ValueError("Название заявки превышает допустимые 180 символов.")

    if not description:
        raise ValueError("Qwen не сформировала описание заявки.")

    source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", problem))
    result_numbers = set(
        re.findall(r"\d+(?:[.,]\d+)?", f"{title} {description}")
    )

    if result_numbers - source_numbers:
        raise ValueError(
            "Qwen добавила число или дату, которых нет в исходном тексте."
        )

    source = problem.casefold().replace("ё", "е")
    result = description.casefold().replace("ё", "е")

    uncertainty_markers = (
        "как ", "можно ли", "нужно ли", "должен ли", "должна ли",
        "требуется ли", "необходимо ли", "какой ", "какая ", "какие ",
        "почему ", "что делать", "должен применить", "нужно применить",
    )

    asks_question = (
        "?" in problem
        or any(marker in source for marker in uncertainty_markers)
    )

    preserves_uncertainty = any(marker in result for marker in (
        "просим разъяснить", "просим уточнить", "просим сообщить",
        "требуется ли", "необходимо ли", "можно ли", "каким образом",
        "порядок", "возможность",
    ))

    assertive_markers = (
        "необходимо применить", "обязательно требуется",
        "должен быть издан", "причиной является",
        "ошибка вызвана", "после перерыва",
    )

    if asks_question and any(
        marker in result for marker in assertive_markers
    ):
        if not preserves_uncertainty:
            raise ValueError(
                "Qwen превратила вопрос пользователя в утверждение."
            )

    if len(description) > max(1200, len(problem) * 6):
        raise ValueError(
            "Qwen необоснованно расширила исходное описание."
        )


def _normalise_for_comparison(value: str) -> str:
    return re.sub(r"[^а-яa-z0-9]+", " ", value.casefold().replace("ё", "е")).strip()


def _is_near_copy(problem: str, description: str) -> bool:
    """Определяет ответы, в которых модель лишь скопировала пользовательский текст."""
    source = _normalise_for_comparison(problem)
    result = _normalise_for_comparison(description)
    if not source or not result or len(source) < 45:
        return False

    similarity = SequenceMatcher(None, source, result).ratio()
    source_words = source.split()
    result_words = result.split()
    shared = len(set(source_words) & set(result_words))
    coverage = shared / max(1, len(set(source_words)))
    return similarity >= 0.82 or (coverage >= 0.94 and abs(len(result_words) - len(source_words)) <= 8)


def _finish_sentence(value: Any) -> str:
    """Очищает смысловой блок и завершает его точкой."""
    text = _sentence_case(_clean_text(value)).strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _build_structured_description(data: dict[str, Any]) -> str:
    """Собирает заявку из отдельных фактических блоков ответа небольшой модели."""
    situation = _finish_sentence(data.get("situation"))
    checks = _finish_sentence(data.get("checks"))
    request_text = _clean_text(data.get("request"))
    constraint = _finish_sentence(data.get("constraint"))

    if request_text:
        lowered = request_text.casefold()
        if not lowered.startswith(("просим ", "пожалуйста, ")):
            request_text = "Просим " + request_text[0].lower() + request_text[1:]
        request_text = _finish_sentence(request_text)

    paragraphs = []
    if situation:
        paragraphs.append(situation)
    if checks:
        paragraphs.append(checks)

    final_request = " ".join(
        part for part in (request_text, constraint) if part
    ).strip()
    if final_request:
        paragraphs.append(final_request)

    return "\n\n".join(paragraphs)


def _generate_with_ollama(problem: str, rewrite_attempt: bool = False) -> dict[str, str]:
    system_prompt = (
        "Ты профессиональный редактор заявок в техническую поддержку. "
        "Не пиши готовый сплошной абзац. Разложи исходный текст на отдельные блоки, "
        "чтобы программа сама собрала итоговую заявку. Перепиши каждый блок ясным "
        "деловым языком: меняй порядок слов, устраняй разговорную речь, повторы, "
        "эмоции и двусмысленность. Не копируй исходное предложение целиком. "
        "При этом сохрани все факты, числа, даты, названия, условия, отрицания, "
        "сравнения и неопределённость. Не придумывай причины, решения или факты. "
        "title: 2–10 слов, обязательно отражает проблему или требуемое действие, "
        "а не только объект. Например, не «Расписание студентов», а "
        "«Не отображается расписание у части студентов». "
        "situation: что произошло, с кем/чем, где и при каких условиях. "
        "checks: только уже выполненные пользователем проверки; если их нет — пустая строка. "
        "request: конкретная просьба к поддержке, начиная с действия: проверить, "
        "уточнить, восстановить, исправить или разъяснить. Не используй фразы "
        "«нужно понять» и «является ли проблема». Не объявляй предполагаемую причину фактом. "
        "constraint: что нельзя менять или какое ограничение нужно соблюдать; "
        "если ограничений нет — пустая строка. Для короткого ввода не раздувай текст. "
        "Без приветствия и общих фраз. Верни только JSON: "
        "{\"title\":\"...\",\"situation\":\"...\",\"checks\":\"...\","
        "\"request\":\"...\",\"constraint\":\"...\"}"
    )

    payload = {
        "model": _select_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Переработай текст в профессиональную заявку. Не повторяй его "
                    "дословно. "
                    + (
                        "Предыдущий вариант оказался слишком похож на оригинал. "
                        "Полностью перестрой предложения и порядок изложения, "
                        "сохранив факты. "
                        if rewrite_attempt else ""
                    )
                    + "Исходное описание:\n" + problem
                ),
            },
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "5m",
        "options": {
            "temperature": 0.25,
            "top_p": 0.9,
            "num_ctx": 3072,
            "num_predict": 450,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started_at = time.monotonic()

    try:
        with _open_local(request, timeout=REQUEST_TIMEOUT) as response:
            raw_response = response.read().decode("utf-8")
        envelope = json.loads(raw_response)

    except urllib.error.HTTPError as exc:
        try:
            details = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            details = ""

        raise RuntimeError(
            f"Ollama HTTP {exc.code}" + (f": {details}" if details else "")
        ) from exc

    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(
            f"Не удалось подключиться к Ollama: {reason}"
        ) from exc

    except (TimeoutError, OSError) as exc:
        elapsed = round(time.monotonic() - started_at, 1)
        raise RuntimeError(
            f"Тайм-аут ожидания ответа Ollama ({elapsed} сек.). "
            f"Адрес: {OLLAMA_URL}; модель: {OLLAMA_MODEL}"
        ) from exc

    content = envelope.get("message", {}).get("content", "")
    data = _extract_json(content)

    title = _clean_text(data.get("title"))
    description = _build_structured_description(data)

    # Совместимость с редким ответом старого формата без повторного запроса к модели.
    if not description:
        description = _clean_text(data.get("description"))

    if not title or not description:
        raise ValueError("Qwen не сформировала название или описание.")

    _validate_ai_ticket(problem, title, description)

    if _is_near_copy(problem, description) and not rewrite_attempt:
        return _generate_with_ollama(problem, rewrite_attempt=True)

    if _is_near_copy(problem, description):
        raise ValueError(
            "Qwen дважды почти дословно повторила исходный текст."
        )

    return {
        "title": title[:180],
        "description": description,
        "source": "ollama",
    }


SYSTEM_PROMPT = (
    "Ты — технический специалист по составлению заявок в HelpDesk/Service Desk (система Platonus/Вуз).\n"
    "Твоя задача — мгновенно оформить четкую, сухую рабочую заявку по существу, без «воды».\n\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ любые приветствия: «Здравствуйте», «Добрый день», «Доброе утро», «Уважаемые коллеги» и т.п.\n"
    "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ любые прощания и благодарности: «Заранее спасибо», «С уважением», «Благодарим за помощь» и т.п.\n"
    "3. СРАЗУ СУТЬ И ФАКТЫ: описание должно начинаться строго с сути проблемы/расхождения и завершаться конкретным техническим действием, которое требуется выполнить (актуализировать, исправить в БД, пересчитать, открыть доступ).\n"
    "4. Сохраняй абсолютно все коды, названия дисциплин, семестры, цифры и параметры из текста пользователя.\n\n"
    "ФОРМАТ ОТВЕТА СТРОГО:\n"
    "ТЕМА: <краткая емкая суть инцидента до 10-12 слов>\n"
    "ОПИСАНИЕ: <четкое техническое описание проблемы и требуемое действие>"
)


def _parse_ticket_response(raw_text: str) -> tuple[str, str]:
    text = str(raw_text or "").strip()
    title = ""
    description = ""

    theme_pattern = re.compile(r"ТЕМА\s*:\s*(.*?)(?=\n\s*ОПИСАНИЕ\s*:|\Z)", re.IGNORECASE | re.DOTALL)
    desc_pattern = re.compile(r"ОПИСАНИЕ\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)

    theme_match = theme_pattern.search(text)
    desc_match = desc_pattern.search(text)

    if theme_match and desc_match:
        title = theme_match.group(1).strip()
        description = desc_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines:
            first_line = lines[0]
            title = re.sub(r"^ТЕМА\s*:\s*", "", first_line, flags=re.I).strip()
            rest = "\n".join(lines[1:])
            description = re.sub(r"^ОПИСАНИЕ\s*:\s*", "", rest, flags=re.I).strip()

    # Убираем жесткий срез по 10 словам, чтобы фразы вроде «электронном журнале» не обрезались на полуслове
    title = title.strip().rstrip(".,;:-")
    if len(title) > 180:
        title = title[:180].rsplit(" ", 1)[0].rstrip(".,;:-")

    return title, description


def generate_ticket(problem: str) -> dict[str, str]:
    clean = _clean_text(problem)

    if len(clean) < 5:
        raise ValueError(
            "Опишите задачу или проблему хотя бы одним предложением."
        )

    # 1. Первичный движок: Google Gemini с автоматическим fallback через ai_service
    try:
        from ai_service import generate_text
        raw_text, provider = generate_text(
            prompt=f"Обращение пользователя:\n{clean}",
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            return_provider=True,
        )
        title, description = _parse_ticket_response(raw_text)
        if title and description:
            return {
                "title": title[:180],
                "description": description,
                "source": provider,
            }
    except Exception:
        pass

    # 2. Локальная Ollama при отсутствии интернета / ошибке API
    try:
        return _generate_with_ollama(clean)
    except Exception as exc:
        result = _fallback_ticket(clean)
        result["warning"] = str(exc).strip().splitlines()[0]
        return result


class TicketWriterWindow:
    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self.theme = get_theme()
        self.window = tk.Toplevel(parent)
        self.window.title("Ticket Writer AI")
        self.window.geometry("1040x760")
        self.window.minsize(860, 650)
        self.window.configure(bg=self.theme["bg"])
        self.window.transient(parent)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.window.iconbitmap(icon_path)
            except Exception:
                pass

        self._generation_id = 0
        self._worker_queue: queue.Queue[tuple[str, int, Any]] = queue.Queue()

        # Данные таймера генерации.
        self._generation_started_at: float | None = None
        self._timer_after_id: str | None = None

        self._build()
        self.problem.focus_set()

        # Все обращения к Tkinter выполняются только главным UI-потоком.
        self.window.after(100, self._poll_worker_queue)

    def _label(self, parent, text, size=10, bold=False, color=None):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            bg=parent.cget("bg"),
            fg=color or self.theme["text"],
            anchor="w",
        )

    def _format_elapsed(self, seconds: float) -> str:
        """Форматирует время как минуты:секунды."""
        total_seconds = max(0, int(seconds))
        minutes, secs = divmod(total_seconds, 60)
        return f"{minutes:02d}:{secs:02d}"

    def _start_timer(self, generation_id: int):
        """Запускает отображение времени в главном потоке Tkinter."""
        self._stop_timer()

        self._generation_started_at = time.monotonic()
        self.timer_label.configure(
            text="Генерация: 00:00",
            fg=GREEN_DARK,
        )

        self._update_timer(generation_id)

    def _update_timer(self, generation_id: int):
        """Обновляет таймер каждую секунду, не блокируя интерфейс."""
        if generation_id != self._generation_id:
            return

        if self._generation_started_at is None:
            return

        elapsed = time.monotonic() - self._generation_started_at
        self.timer_label.configure(
            text=f"Генерация: {self._format_elapsed(elapsed)}"
        )

        try:
            self._timer_after_id = self.window.after(
                1000,
                lambda: self._update_timer(generation_id),
            )
        except tk.TclError:
            self._timer_after_id = None

    def _stop_timer(self) -> str:
        """Останавливает таймер и возвращает итоговое время."""
        elapsed_text = "00:00"

        if self._generation_started_at is not None:
            elapsed = time.monotonic() - self._generation_started_at
            elapsed_text = self._format_elapsed(elapsed)

        if self._timer_after_id is not None:
            try:
                self.window.after_cancel(self._timer_after_id)
            except tk.TclError:
                pass

        self._timer_after_id = None
        self._generation_started_at = None

        self.timer_label.configure(
            text=f"Время: {elapsed_text}",
            fg=self.theme["gray"],
        )

        return elapsed_text

    def _enable_text_editing(self, widget: tk.Text):
        """Надёжные операции буфера обмена, включая русскую раскладку Windows."""

        def selected_range():
            try:
                return widget.index("sel.first"), widget.index("sel.last")
            except tk.TclError:
                return None

        def copy_text(event=None):
            bounds = selected_range()
            if bounds:
                text = widget.get(*bounds)
                widget.clipboard_clear()
                widget.clipboard_append(text)
            return "break"

        def cut_text(event=None):
            bounds = selected_range()
            if bounds:
                copy_text()
                widget.delete(*bounds)
            return "break"

        def paste_text(event=None):
            try:
                text = widget.clipboard_get()
            except tk.TclError:
                return "break"

            bounds = selected_range()
            if bounds:
                widget.delete(*bounds)

            widget.insert("insert", text)
            widget.see("insert")
            return "break"

        def select_all(event=None):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
            return "break"

        widget.bind("<Control-v>", paste_text)
        widget.bind("<Control-V>", paste_text)
        widget.bind("<Shift-Insert>", paste_text)
        widget.bind("<Control-c>", copy_text)
        widget.bind("<Control-C>", copy_text)
        widget.bind("<Control-Insert>", copy_text)
        widget.bind("<Control-x>", cut_text)
        widget.bind("<Control-X>", cut_text)
        widget.bind("<Control-a>", select_all)
        widget.bind("<Control-A>", select_all)

        def physical_shortcut(event):
            if str(getattr(event, "keysym", "")).casefold() in {
                "a", "c", "v", "x"
            }:
                return None

            action = {
                65: select_all,
                67: copy_text,
                86: paste_text,
                88: cut_text,
            }.get(getattr(event, "keycode", None))

            return action(event) if action else None

        widget.bind("<Control-KeyPress>", physical_shortcut, add="+")

        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Вырезать", command=cut_text)
        menu.add_command(label="Копировать", command=copy_text)
        menu.add_command(label="Вставить", command=paste_text)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=select_all)

        def show_menu(event):
            widget.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        widget.bind("<Button-3>", show_menu)
        widget._ticket_context_menu = menu

    def _build(self):
        header = tk.Frame(self.window, bg=NAVY, height=82)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Frame(header, width=7, bg=GREEN).pack(side="left", fill="y")

        title_box = tk.Frame(header, bg=NAVY)
        title_box.pack(
            side="left", fill="both", expand=True, padx=22, pady=13
        )

        tk.Label(
            title_box,
            text="TICKET WRITER AI",
            font=("Segoe UI", 18, "bold"),
            bg=NAVY,
            fg=WHITE,
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Грамотное название и описание обращения из обычного текста",
            font=("Segoe UI", 9),
            bg=NAVY,
            fg="#DCE8F8",
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        body = tk.Frame(self.window, bg=self.theme["bg"])
        body.pack(fill="both", expand=True, padx=22, pady=18)

        input_card = tk.Frame(
            body,
            bg=self.theme["card"],
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        input_card.pack(fill="x")

        self._label(
            input_card, "Опишите задачу или проблему", 11, True
        ).pack(fill="x", padx=16, pady=(14, 4))

        self._label(
            input_card,
            "Пишите обычными словами. Модуль не будет придумывать отсутствующие обстоятельства.",
            9,
            color=self.theme["gray"],
        ).pack(fill="x", padx=16, pady=(0, 8))

        self.problem = tk.Text(
            input_card,
            height=7,
            wrap="word",
            undo=True,
            font=("Segoe UI", 11),
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            bg=self.theme["input"],
            fg=self.theme["text"],
            insertbackground=self.theme["text"],
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        self.problem.pack(fill="x", padx=16, pady=(0, 12))
        self._enable_text_editing(self.problem)

        action_row = tk.Frame(input_card, bg=self.theme["card"])
        action_row.pack(fill="x", padx=16, pady=(0, 14))

        self.generate_button = tk.Button(
            action_row,
            text="Сформировать текст",
            command=self._start_generation,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            padx=22,
            pady=10,
            cursor="hand2",
            bg=GREEN,
            fg=WHITE,
            activebackground=GREEN_DARK,
            activeforeground=WHITE,
        )
        self.generate_button.pack(side="left")

        tk.Button(
            action_row,
            text="Очистить",
            command=self._clear,
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            bg=self.theme["hover"],
            fg=self.theme["text"],
            activebackground=self.theme["border"],
        ).pack(side="left", padx=(8, 0))

        # Таймер расположен рядом со статусом.
        self.timer_label = tk.Label(
            action_row,
            text="Время: 00:00",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme["card"],
            fg=self.theme["gray"],
            anchor="e",
        )
        self.timer_label.pack(side="right", padx=(12, 0))

        self.status = tk.Label(
            action_row,
            text="Готово к работе",
            font=("Segoe UI", 9),
            bg=self.theme["card"],
            fg=self.theme["gray"],
            anchor="e",
        )
        self.status.pack(side="right", fill="x", expand=True)

        result_card = tk.Frame(
            body,
            bg=self.theme["card"],
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        result_card.pack(fill="both", expand=True, pady=(14, 0))

        title_row = tk.Frame(result_card, bg=self.theme["card"])
        title_row.pack(fill="x", padx=16, pady=(14, 6))

        self._label(title_row, "Название заявки", 11, True).pack(side="left")

        tk.Button(
            title_row,
            text="Копировать",
            command=lambda: self._copy(self.title_text),
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            bg=SOFT_GREEN,
            fg=GREEN_DARK,
        ).pack(side="right")

        self.title_text = tk.Text(
            result_card,
            height=2,
            wrap="word",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            bd=0,
            padx=12,
            pady=9,
            bg=SOFT_BLUE,
            fg=NAVY,
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        self.title_text.pack(fill="x", padx=16)
        self._enable_text_editing(self.title_text)

        description_row = tk.Frame(result_card, bg=self.theme["card"])
        description_row.pack(fill="x", padx=16, pady=(14, 6))

        self._label(description_row, "Описание", 11, True).pack(side="left")

        tk.Button(
            description_row,
            text="Копировать",
            command=lambda: self._copy(self.description_text),
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            bg=SOFT_GREEN,
            fg=GREEN_DARK,
        ).pack(side="right")

        self.description_text = tk.Text(
            result_card,
            height=10,
            wrap="word",
            font=("Segoe UI", 11),
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            bg=self.theme["input"],
            fg=self.theme["text"],
            insertbackground=self.theme["text"],
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        self.description_text.pack(
            fill="both", expand=True, padx=16, pady=(0, 16)
        )
        self._enable_text_editing(self.description_text)

    def _start_generation(self):
        problem = self.problem.get("1.0", "end").strip()

        if len(problem) < 5:
            messagebox.showwarning(
                "Ticket Writer AI",
                "Опишите задачу или проблему хотя бы одним предложением.",
                parent=self.window,
            )
            return

        # Не выдаём дословный черновик за готовый результат работы AI.
        self.title_text.delete("1.0", "end")
        self.description_text.delete("1.0", "end")

        self.generate_button.configure(
            state="disabled",
            text="BahonIQ AI формирует заявку...",
        )
        self.status.configure(
            text="BahonIQ AI анализирует задачу и структурирует обращение...",
            fg=GREEN_DARK,
        )

        self._generation_id += 1
        generation_id = self._generation_id

        # Таймер запускается одновременно с фоновой генерацией.
        self._start_timer(generation_id)

        threading.Thread(
            target=self._worker,
            args=(problem, generation_id),
            daemon=True,
        ).start()

    def _worker(self, problem: str, generation_id: int):
        """Фоновый поток сначала вызывает облачный BahonIQ AI, затем тихий fallback."""
        try:
            result = generate_ticket(_clean_text(problem))
            self._worker_queue.put(("success", generation_id, result))

        except Exception as exc:
            self._worker_queue.put(("error", generation_id, str(exc)))

    def _poll_worker_queue(self):
        """Получает ответы из очереди в главном потоке Tkinter."""
        try:
            while True:
                kind, generation_id, payload = self._worker_queue.get_nowait()

                if generation_id != self._generation_id:
                    continue

                if kind == "success":
                    self._show_result(payload, generation_id)
                else:
                    self._keep_draft(str(payload), generation_id)

        except queue.Empty:
            pass

        except tk.TclError:
            return

        try:
            if self.window.winfo_exists():
                self.window.after(100, self._poll_worker_queue)
        except tk.TclError:
            return

    def _put_result(self, result: dict[str, str]):
        self.title_text.delete("1.0", "end")
        self.title_text.insert("1.0", result["title"])

        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", result["description"])

    def _show_result(self, result: dict[str, str], generation_id: int):
        if generation_id != self._generation_id:
            return

        elapsed = self._stop_timer()

        self._generation_id += 1
        self._put_result(result)

        source = result.get("source", "gemini")
        engine_label = "BahonIQ AI" if source == "gemini" else "Ollama / Qwen"

        self.generate_button.configure(
            state="normal",
            text="Сформировать заново",
        )
        self.status.configure(
            text=f"Текст успешно сформирован {engine_label} за {elapsed}",
            fg=GREEN_DARK,
        )

    def _keep_draft(self, reason: str, generation_id: int):
        if generation_id != self._generation_id:
            return

        elapsed = self._stop_timer()

        self._generation_id += 1
        self.generate_button.configure(
            state="normal",
            text="Попробовать снова",
        )

        self.title_text.delete("1.0", "end")
        self.description_text.delete("1.0", "end")

        reason = str(reason).strip().splitlines()[0] or "Неизвестная ошибка"

        self.status.configure(
            text=f"Текст не сформирован за {elapsed}. Ошибка: {reason[:150]}",
            fg=RED,
        )

    def _expire_generation(self, generation_id: int):
        """Останавливает отображение ожидания, если метод вызван извне."""
        if generation_id != self._generation_id:
            return

        elapsed = self._stop_timer()

        self._generation_id += 1
        self.generate_button.configure(
            state="normal",
            text="Попробовать снова",
        )
        self.status.configure(
            text=(
                f"Время ожидания истекло за {elapsed}. "
                f"Повторите попытку."
            ),
            fg=RED,
        )

    def _show_error(self, exc: Exception):
        self._stop_timer()
        self.generate_button.configure(
            state="normal",
            text="Сформировать текст",
        )
        self.status.configure(
            text="Не удалось сформировать текст",
            fg=RED,
        )
        messagebox.showerror(
            "Ticket Writer AI",
            str(exc),
            parent=self.window,
        )

    def _copy(self, widget: tk.Text):
        text = widget.get("1.0", "end").strip()

        if not text:
            return

        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.status.configure(
            text="Текст скопирован",
            fg=GREEN_DARK,
        )

    def _clear(self):
        # Инвалидируем старый ответ и останавливаем его таймер.
        self._generation_id += 1
        self._stop_timer()

        for widget in (
            self.problem,
            self.title_text,
            self.description_text,
        ):
            widget.delete("1.0", "end")

        self.generate_button.configure(
            state="normal",
            text="Сформировать текст",
        )
        self.status.configure(
            text="Готово к работе",
            fg=self.theme["gray"],
        )
        self.problem.focus_set()


def open_ticket_writer(parent: tk.Misc):
    return TicketWriterWindow(parent)
