"""BahonIQ Ticket Writer AI.

Простой локальный редактор обращений: пользователь описывает проблему
обычными словами, а модуль формирует название и грамотный текст заявки.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Any

import tkinter as tk
from tkinter import messagebox

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
    "qwen2.5:7b",
)
REQUEST_TIMEOUT = int(os.getenv("BAHONIQ_TICKET_TIMEOUT", "60"))
UI_DEADLINE_MS = (REQUEST_TIMEOUT + 5) * 1000

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
    # Черновик не должен копировать в заголовок целый абзац.
    title_words = re.findall(r"\S+", title)
    if len(title_words) > 7:
        title = " ".join(title_words[:7]).rstrip(" ,;:-")
    title = _sentence_case(title).rstrip(".")
    description = (
        f"{clean.rstrip('.!?')}.\n\n"
        "Просим проверить указанную ситуацию и предоставить рекомендации "
        "по её устранению."
    )
    return {"title": title, "description": description, "source": "fallback"}


def _available_models() -> list[str]:
    try:
        with _open_local(OLLAMA_TAGS_URL, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return [
        str(item.get("name"))
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]


def _select_model() -> str:
    models = _available_models()
    if not models or OLLAMA_MODEL in models:
        return OLLAMA_MODEL
    qwen = [name for name in models if "qwen" in name.casefold()]
    # Для короткой редакторской задачи небольшая Qwen обычно даёт тот же
    # результат заметно быстрее. Если отдельная модель Ticket Writer не
    # настроена, выбираем самую компактную из установленных Qwen.
    def model_size(name: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*b", name.casefold())
        return float(match.group(1)) if match else 999.0
    return min(qwen, key=model_size) if qwen else models[0]


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
    """Отбрасывает очевидно недостоверный или шаблонно раздутый ответ AI."""
    title_words = re.findall(r"[\w-]+", title, flags=re.UNICODE)
    if not 2 <= len(title_words) <= 7:
        raise ValueError("Qwen сформировала слишком длинное или пустое название.")

    source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", problem))
    result_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", f"{title} {description}"))
    if result_numbers - source_numbers:
        raise ValueError("Qwen добавила число или дату, которых нет в исходном тексте.")

    source = problem.casefold().replace("ё", "е")
    result = description.casefold().replace("ё", "е")
    uncertainty_markers = (
        "как ", "можно ли", "нужно ли", "должен ли", "должна ли",
        "требуется ли", "необходимо ли", "какой ", "какая ", "какие ",
        "почему ", "что делать", "должен применить", "нужно применить",
    )
    asks_question = "?" in problem or any(marker in source for marker in uncertainty_markers)
    preserves_uncertainty = any(marker in result for marker in (
        "просим разъяснить", "просим уточнить", "просим сообщить",
        "требуется ли", "необходимо ли", "можно ли", "каким образом",
        "порядок", "возможность",
    ))
    assertive_markers = (
        "необходимо применить", "обязательно требуется", "должен быть издан",
        "причиной является", "ошибка вызвана", "после перерыва",
    )
    if asks_question and any(marker in result for marker in assertive_markers):
        if not preserves_uncertainty:
            raise ValueError("Qwen превратила вопрос пользователя в утверждение.")

    if len(description) > max(1200, len(problem) * 6):
        raise ValueError("Qwen необоснованно расширила исходное описание.")


def _generate_with_ollama(problem: str) -> dict[str, str]:
    system_prompt = (
        "Ты редактор обращений в техническую поддержку. "
        "Из текста пользователя создай короткую тему и грамотное описание без приветствия. "
        "Тема: 2–7 слов, именная форма, не полное предложение. "
        "Описание: 1–3 коротких абзаца, только суть и нужное действие. "
        "Строго сохраняй смысл, числа, названия и неопределённость исходного текста. "
        "Не выдумывай причины, документы, события, людей или результаты. "
        "Вопрос не превращай в утверждение. Верни только JSON: "
        '{"title":"...","description":"..."}.'
    )
    payload = {
        "model": _select_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": problem},
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "5m",
        "options": {
            "temperature": 0,
            "top_p": 0.8,
            "num_ctx": 1536,
            "num_predict": 180,
        },
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _open_local(request, timeout=REQUEST_TIMEOUT) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama недоступна") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"Ollama не ответила за {REQUEST_TIMEOUT} секунд"
        ) from exc

    content = envelope.get("message", {}).get("content", "")
    data = _extract_json(content)
    title = _clean_text(data.get("title"))
    description = _clean_text(data.get("description"))
    if not title or not description:
        raise ValueError("Qwen не сформировала название или описание.")
    _validate_ai_ticket(problem, title, description)
    return {
        "title": title[:180],
        "description": description,
        "source": "ollama",
    }


def generate_ticket(problem: str) -> dict[str, str]:
    clean = _clean_text(problem)
    if len(clean) < 5:
        raise ValueError("Опишите задачу или проблему хотя бы одним предложением.")
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
        self._generation_id = 0
        self._build()
        self.problem.focus_set()

    def _label(self, parent, text, size=10, bold=False, color=None):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            bg=parent.cget("bg"),
            fg=color or self.theme["text"],
            anchor="w",
        )

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

        # Обычные сочетания и физические keycode Windows. Второй вариант
        # нужен, когда Ctrl+V нажимается при активной русской раскладке.
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
            if str(getattr(event, "keysym", "")).casefold() in {"a", "c", "v", "x"}:
                return None
            action = {
                65: select_all,  # A
                67: copy_text,   # C
                86: paste_text,  # V
                88: cut_text,    # X
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
        title_box.pack(side="left", fill="both", expand=True, padx=22, pady=13)
        tk.Label(
            title_box, text="TICKET WRITER AI", font=("Segoe UI", 18, "bold"),
            bg=NAVY, fg=WHITE, anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_box, text="Грамотное название и описание обращения из обычного текста",
            font=("Segoe UI", 9), bg=NAVY, fg="#DCE8F8", anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        body = tk.Frame(self.window, bg=self.theme["bg"])
        body.pack(fill="both", expand=True, padx=22, pady=18)

        input_card = tk.Frame(
            body, bg=self.theme["card"], highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        input_card.pack(fill="x")
        self._label(input_card, "Опишите задачу или проблему", 11, True).pack(
            fill="x", padx=16, pady=(14, 4)
        )
        self._label(
            input_card,
            "Пишите обычными словами. Модуль не будет придумывать отсутствующие обстоятельства.",
            9, color=self.theme["gray"],
        ).pack(fill="x", padx=16, pady=(0, 8))
        self.problem = tk.Text(
            input_card, height=7, wrap="word", undo=True,
            font=("Segoe UI", 11), relief="flat", bd=0,
            padx=12, pady=10, bg=self.theme["input"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            highlightthickness=1, highlightbackground=self.theme["border"],
        )
        self.problem.pack(fill="x", padx=16, pady=(0, 12))
        self._enable_text_editing(self.problem)

        action_row = tk.Frame(input_card, bg=self.theme["card"])
        action_row.pack(fill="x", padx=16, pady=(0, 14))
        self.generate_button = tk.Button(
            action_row, text="Сформировать текст", command=self._start_generation,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            padx=22, pady=10, cursor="hand2", bg=GREEN, fg=WHITE,
            activebackground=GREEN_DARK, activeforeground=WHITE,
        )
        self.generate_button.pack(side="left")
        tk.Button(
            action_row, text="Очистить", command=self._clear,
            font=("Segoe UI", 10), relief="flat", bd=0,
            padx=18, pady=10, cursor="hand2", bg=self.theme["hover"],
            fg=self.theme["text"], activebackground=self.theme["border"],
        ).pack(side="left", padx=(8, 0))
        self.status = tk.Label(
            action_row, text="Готово к работе", font=("Segoe UI", 9),
            bg=self.theme["card"], fg=self.theme["gray"], anchor="e",
        )
        self.status.pack(side="right", fill="x", expand=True)

        result_card = tk.Frame(
            body, bg=self.theme["card"], highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        result_card.pack(fill="both", expand=True, pady=(14, 0))

        title_row = tk.Frame(result_card, bg=self.theme["card"])
        title_row.pack(fill="x", padx=16, pady=(14, 6))
        self._label(title_row, "Название заявки", 11, True).pack(side="left")
        tk.Button(
            title_row, text="Копировать", command=lambda: self._copy(self.title_text),
            font=("Segoe UI", 9), relief="flat", bd=0, padx=12, pady=5,
            cursor="hand2", bg=SOFT_GREEN, fg=GREEN_DARK,
        ).pack(side="right")
        self.title_text = tk.Text(
            result_card, height=2, wrap="word", font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0, padx=12, pady=9, bg=SOFT_BLUE, fg=NAVY,
            highlightthickness=1, highlightbackground=self.theme["border"],
        )
        self.title_text.pack(fill="x", padx=16)
        self._enable_text_editing(self.title_text)

        description_row = tk.Frame(result_card, bg=self.theme["card"])
        description_row.pack(fill="x", padx=16, pady=(14, 6))
        self._label(description_row, "Описание", 11, True).pack(side="left")
        tk.Button(
            description_row, text="Копировать", command=lambda: self._copy(self.description_text),
            font=("Segoe UI", 9), relief="flat", bd=0, padx=12, pady=5,
            cursor="hand2", bg=SOFT_GREEN, fg=GREEN_DARK,
        ).pack(side="right")
        self.description_text = tk.Text(
            result_card, height=10, wrap="word", font=("Segoe UI", 11),
            relief="flat", bd=0, padx=12, pady=10,
            bg=self.theme["input"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            highlightthickness=1, highlightbackground=self.theme["border"],
        )
        self.description_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))
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
        # Не оставляем пользователя перед пустым экраном: безопасный черновик
        # появляется сразу, а Qwen заменяет его улучшенной версией в фоне.
        draft = _fallback_ticket(problem)
        self._put_result(draft)
        self.generate_button.configure(state="disabled", text="Qwen улучшает...")
        self.status.configure(
            text="Черновик готов. Qwen улучшает формулировки...", fg=GREEN_DARK
        )
        self._generation_id += 1
        generation_id = self._generation_id
        self.window.after(
            UI_DEADLINE_MS,
            lambda: self._expire_generation(generation_id),
        )
        threading.Thread(
            target=self._worker, args=(problem, generation_id), daemon=True
        ).start()

    def _worker(self, problem: str, generation_id: int):
        try:
            result = _generate_with_ollama(_clean_text(problem))
            self.window.after(
                0, lambda: self._show_result(result, generation_id)
            )
        except Exception as exc:
            self.window.after(
                0, lambda: self._keep_draft(exc, generation_id)
            )

    def _put_result(self, result: dict[str, str]):
        self.title_text.delete("1.0", "end")
        self.title_text.insert("1.0", result["title"])
        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", result["description"])

    def _show_result(self, result: dict[str, str], generation_id: int):
        if generation_id != self._generation_id:
            return
        self._generation_id += 1
        self._put_result(result)
        self.generate_button.configure(state="normal", text="Сформировать заново")
        self.status.configure(text="Текст улучшен Qwen", fg=GREEN_DARK)

    def _keep_draft(self, exc: Exception, generation_id: int):
        if generation_id != self._generation_id:
            return
        self._generation_id += 1
        self.generate_button.configure(state="normal", text="Попробовать Qwen снова")
        reason = str(exc).strip().splitlines()[0]
        self.status.configure(
            text=f"Черновик сохранён. Qwen не ответила: {reason}", fg=RED
        )

    def _expire_generation(self, generation_id: int):
        """Не даёт запоздалому ответу перезаписать текст в окне."""
        if generation_id != self._generation_id:
            return
        self._generation_id += 1
        self.generate_button.configure(state="normal", text="Попробовать Qwen снова")
        self.status.configure(
            text="Черновик сохранён. Qwen не ответила за минуту.",
            fg=RED,
        )

    def _show_error(self, exc: Exception):
        self.generate_button.configure(state="normal", text="Сформировать текст")
        self.status.configure(text="Не удалось сформировать текст", fg=RED)
        messagebox.showerror("Ticket Writer AI", str(exc), parent=self.window)

    def _copy(self, widget: tk.Text):
        text = widget.get("1.0", "end").strip()
        if not text:
            return
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.status.configure(text="Текст скопирован", fg=GREEN_DARK)

    def _clear(self):
        self._generation_id += 1
        for widget in (self.problem, self.title_text, self.description_text):
            widget.delete("1.0", "end")
        self.status.configure(text="Готово к работе", fg=self.theme["gray"])
        self.problem.focus_set()


def open_ticket_writer(parent: tk.Misc):
    return TicketWriterWindow(parent)
