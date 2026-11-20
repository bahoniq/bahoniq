"""BahonIQ Ticket Writer AI.

Редактор обращений: пользователь описывает вопрос, просьбу или проблему
обычными словами, а модуль бережно приводит текст к грамотному, ясному
деловому виду без искажения смысла, тональности и фактов.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
import os
import logging
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Iterator

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


SYSTEM_PROMPT = (
    "Ты — бережный редактор деловых обращений в службу технической поддержки.\n"
    "Твоя задача — исправить орфографию, пунктуацию, повторы и шероховатости речи, "
    "сделав текст ясным, аккуратным и естественным, но СТРОГО сохранить исходный смысл, "
    "намерение, модальность и степень вежливости автора.\n\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. СОХРАНЯЙ МОДАЛЬНОСТЬ И ВЕЖЛИВОСТЬ:\n"
    "   - Если в исходном тексте вежливый вопрос или просьба («Можно ли…», «Подскажите…», "
    "«Есть ли возможность…») — обязательно сохрани форму вежливого вопроса («Можно ли…?»). "
    "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО превращать «Можно ли…» в «Требуется…», «Необходимо…», «Выполнить…».\n"
    "   - Если в исходном тексте вежливая просьба («Просим…», «Пожалуйста, проверьте…») — "
    "сохрани «Просим…». НЕ заменяй «Просим…» на «Требуется…» или «Необходимо…».\n"
    "   - Если автор здоровается («Добрый день», «Здравствуйте») — сохрани "
    "вежливое приветствие «Добрый день!» или «Здравствуйте!» в начале описания. "
    "Если приветствия в исходном тексте НЕ было — НЕ добавляй его от себя.\n"
    "2. СОХРАНЯЙ ВОПРОСИТЕЛЬНУЮ ФОРМУ:\n"
    "   - Вопрос пользователя должен оставаться вопросом (со знаком вопроса «?»).\n"
    "3. СОХРАНЯЙ ПРЕДПОЛОЖЕНИЯ И НЕОПРЕДЕЛЁННОСТЬ:\n"
    "   - Слова «возможно», «вероятно», «скорее всего», «предположительно», «кажется» "
    "обязательно сохраняй как предположение. НЕ превращай гипотезу пользователя в установленный факт "
    "и не пиши «причиной является…» или «ошибка вызвана…».\n"
    "4. НЕ ДОДУМЫВАЙ ДЕЙСТВИЯ И ФАКТЫ:\n"
    "   - Если пользователь просит только «проверить, почему…» — НЕ проси «исправить», «восстановить» "
    "или «актуализировать». Оставь именно просьбу проверить причину.\n"
    "   - НЕ придумывай технические причины, сроки, номера, названия модулей или действия, "
    "которых не было в исходном тексте.\n"
    "   - НЕ указывай, что какая-то работа или проверка уже выполнена, если автор этого не писал.\n"
    "   - НЕ дублируй одну и ту же мысль разными словами и не раздувай короткое обращение.\n"
    "5. ЗАГОЛОВОК (ТЕМА):\n"
    "   - Короткий (3–9 слов), точный, спокойный, без слов «Требуется» и «Необходимо».\n\n"
    "ФОРМАТ ОТВЕТА СТРОГО (только эти две секции, без комментариев и без markdown):\n"
    "ТЕМА: <короткий точный заголовок>\n"
    "ОПИСАНИЕ: <аккуратно отредактированный текст обращения>"
)


# Маркеры в исходном тексте
_QUESTION_MARKERS = (
    "можно ли",
    "возможно ли",
    "есть ли возможность",
    "подскажите",
    "как можно",
    "каким образом",
)
_POLITE_REQUEST_MARKERS = (
    "просим",
    "прошу",
    "пожалуйста",
)
_UNCERTAINTY_WORDS = (
    "возможно",
    "вероятно",
    "скорее всего",
    "предположительно",
    "похоже",
    "кажется",
    "не исключено",
)
_IMPERATIVE_BANNED_WHEN_POLITE = (
    r"\bтребуется\b",
    r"\bнеобходимо\b",
    r"\bобязательно\s+требуется\b",
    r"\bнадлежит\b",
    r"\bследует\s+выполнить\b",
    r"\bвыполнить\s+выгрузку\b",
)


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


def _source_has_polite_question(problem: str) -> bool:
    low = problem.casefold().replace("ё", "е")
    return any(m in low for m in _QUESTION_MARKERS)


def _source_has_imperative(problem: str) -> bool:
    low = problem.casefold().replace("ё", "е")
    return any(w in low for w in ("требуется", "необходимо", "нужно срочно", "обязательно"))


def _source_uncertainty_word(problem: str) -> str | None:
    low = problem.casefold().replace("ё", "е")
    for w in _UNCERTAINTY_WORDS:
        if w in low:
            return w
    return None


def _source_only_asks_to_check(problem: str) -> bool:
    low = problem.casefold().replace("ё", "е")
    asks_check = any(w in low for w in ("проверить", "посмотреть", "уточнить", "выяснить", "почему"))
    asks_fix = any(w in low for w in ("исправ", "восстанов", "устран", "измен", "удалит", "добав"))
    return asks_check and not asks_fix


def _derive_clean_title(problem: str) -> str:
    """Формирует спокойный деловой заголовок по смыслу исходного текста."""
    clean = _clean_text(problem)
    low = clean.casefold().replace("ё", "е")

    # Убираем приветствия в начале для анализа заголовка
    stripped = re.sub(
        r"^(?:добрый\s+день|здравствуйте|доброе\s+утро|добрый\s+вечер|коллеги)[,!\.\s]*",
        "",
        clean,
        flags=re.I,
    ).strip()
    first_clause = re.split(r"[.!?\n]", stripped, maxsplit=1)[0].strip()

    # Специальные естественные паттерны
    m_logs = re.search(r"можно\s+ли\s+получить\s+логи\s+(.+)", first_clause, flags=re.I)
    if m_logs:
        tail = m_logs.group(1).strip().rstrip(".,;:-?")
        tail = re.sub(r"\bпо\s+трем\s+типам\s+приказа\s+общежития\b", "по приказам общежития", tail, flags=re.I)
        tail = re.sub(r"\bпо\s+трём\s+типам\s+приказа\s+общежития\b", "по приказам общежития", tail, flags=re.I)
        return _sentence_case(f"Предоставление логов {tail}")[:120]

    m_can_get = re.search(r"можно\s+ли\s+(?:получить|выгрузить|предоставить)\s+(.+)", first_clause, flags=re.I)
    if m_can_get:
        tail = m_can_get.group(1).strip().rstrip(".,;:-?")
        return _sentence_case(f"Предоставление данных: {tail}")[:120]

    m_check_why = re.search(r"(?:просим|прошу|пожалуйста)?\s*проверить[,]?\s+почему\s+(.+)", first_clause, flags=re.I)
    if m_check_why:
        tail = m_check_why.group(1).strip().rstrip(".,;:-?")
        return _sentence_case(f"Проверка причины: {tail}")[:120]

    if "не отображается расписание" in low:
        return "Не отображается расписание у студентов"

    # Общая очистка первого предложения под заголовок
    candidate = re.sub(
        r"^(?:можно\s+ли\s+узнать|можно\s+ли|подскажите[,]?\s*пожалуйста|подскажите|просим\s+вас|просим|прошу|пожалуйста)[,\s]*",
        "",
        first_clause,
        flags=re.I,
    ).strip()
    candidate = re.split(r"[,;]\s*(?:возможно|вероятно|скорее всего)\b", candidate, flags=re.I)[0].strip()

    if not candidate:
        candidate = first_clause or "Обращение в техническую поддержку"

    words = re.findall(r"\S+", candidate)
    if len(words) > 9:
        candidate = " ".join(words[:8]).rstrip(" ,;:-")

    return _sentence_case(candidate).rstrip(".!?")


def _refine_Fallback_description(problem: str) -> str:
    """Бережно редактирует текст пользователя без ИИ, сохраняя вопросы, просьбы и гипотезы."""
    clean = _clean_text(problem)
    if not clean:
        return ""

    text = clean

    # Лёгкая литературная правка частых шероховатостей без потери смысла
    # 1. Приветствие: «Добрый день, можно ли...» -> «Добрый день! Можно ли...»
    greet_match = re.match(
        r"^(добрый\s+день|здравствуйте|доброе\s+утро|добрый\s+вечер)\s*[,!.]\s*(.+)$",
        text,
        flags=re.I | re.DOTALL,
    )
    if greet_match:
        greeting = _sentence_case(greet_match.group(1).strip()) + "!"
        rest = _sentence_case(greet_match.group(2).strip())
        text = f"{greeting} {rest}"
    else:
        text = _sentence_case(text)

    # 2. Частный случай склейки оборванного перечисления после вопроса о логах/приказах:
    # «Можно ли получить логи по трем типам приказа общежития. Номер приказа, фамилии студентов и кем был сформирован приказ?»
    pattern_logs = re.compile(
        r"(Можно\s+ли\s+получить\s+логи\s+по\s+тр[её]м\s+типам\s+приказ(?:а|ов)\s+(?:по\s+)?общежития)[.?!]\s*"
        r"Номер\s+приказа,\s*фамилии\s+студентов\s+и\s+кем\s+был\s+сформирован\s+приказ\??",
        flags=re.I,
    )
    if pattern_logs.search(text):
        text = pattern_logs.sub(
            "Можно ли получить логи по трём типам приказов по общежитиям "
            "с указанием номера приказа, ФИО студентов и пользователя, сформировавшего приказ?",
            text,
        )
        text = text.replace("приказов по общежитиям", "приказов по общежитию")

    # 3. Если в исходнике был вопрос («Можно ли...» или «?»), гарантируем знак вопроса в конце вопросительного предложения
    if "?" in clean or _source_has_polite_question(clean):
        if not text.endswith("?") and _source_has_polite_question(clean):
            text = text.rstrip(".!") + "?"
    else:
        if text[-1] not in ".!?":
            text += "."

    return text


def _postprocess_ticket(problem: str, title: str, description: str) -> tuple[str, str]:
    """Исправляет нарушения тональности в ответе модели, не давая превратить просьбу в приказ."""
    clean_prob = _clean_text(problem)
    title = _clean_text(title).strip("«»\"' ").rstrip(".,;:-")
    description = _clean_text(description)

    # Убираем искусственно добавленное приветствие, если в исходном тексте его не было
    prob_low = clean_prob.casefold()
    if not any(g in prob_low for g in ("добрый день", "здравствуйте", "доброе утро", "добрый вечер", "привет")):
        description = re.sub(
            r"^(?:добрый\s+день|здравствуйте|доброе\s+утро|добрый\s+вечер)\s*[!,.]\s*",
            "",
            description,
            flags=re.I,
        ).strip()
        description = _sentence_case(description)

    if not title or len(title) < 3:
        title = _derive_clean_title(clean_prob)

    # 1. Запрет «Требуется / Необходимо» в заголовке и описании, если автор их не писал
    if not _source_has_imperative(clean_prob):
        title = re.sub(r"^(?:требуется|необходимо)\s+", "", title, flags=re.I).strip()
        title = _sentence_case(title)

        # Заменяем жёсткие канцелярские конструкции в описании на вежливые или исходные
        if _source_has_polite_question(clean_prob):
            description = re.sub(
                r"\b(?:требуется|необходимо)\s+(?:выгрузить|предоставить|получить|сформировать)\b",
                "можно ли получить",
                description,
                flags=re.I,
            )
            description = re.sub(
                r"\b(?:просим|нужно)\s+выполнить\s+выгрузку\b",
                "можно ли получить выгрузку",
                description,
                flags=re.I,
            )
        else:
            description = re.sub(
                r"\b(?:требуется|необходимо)\s+(проверить|уточнить|рассмотреть|предоставить|посмотреть)\b",
                r"просим \1",
                description,
                flags=re.I,
            )

        # Удаляем искусственно приписанное в конец предложение вида «Требуется выполнить... / Необходимо исправить...»
        sentences = re.split(r"(?<=[.!?])\s+", description)
        if len(sentences) > 1:
            filtered = []
            for idx, sent in enumerate(sentences):
                s_low = sent.casefold()
                is_added_imperative = any(
                    re.search(pat, s_low) for pat in _IMPERATIVE_BANNED_WHEN_POLITE
                )
                if is_added_imperative and idx == len(sentences) - 1:
                    continue
                filtered.append(sent)
            if filtered:
                description = " ".join(filtered).strip()

        # Если всё ещё остался жёсткий императив («Требуется выгрузить...»), используем бережную редактуру
        desc_low = description.casefold()
        if any(re.search(pat, desc_low) for pat in _IMPERATIVE_BANNED_WHEN_POLITE):
            return _derive_clean_title(clean_prob), _refine_Fallback_description(clean_prob)

    # 2. Если автор задавал вопрос «Можно ли...» или ставил «?», вопрос должен остаться вопросом
    if _source_has_polite_question(clean_prob):
        desc_low = description.casefold()
        has_question_tone = (
            "?" in description
            or "можно ли" in desc_low
            or "возможно ли" in desc_low
            or "есть ли возможность" in desc_low
            or "подскажите" in desc_low
        )
        if not has_question_tone:
            return _derive_clean_title(clean_prob), _refine_Fallback_description(clean_prob)
        if not description.endswith("?") and "можно ли" in desc_low:
            description = description.rstrip(".!") + "?"

    # 3. Если автор высказывал предположение («возможно», «скорее всего», «вероятно»), оно не должно стать фактом
    unc_word = _source_uncertainty_word(clean_prob)
    if unc_word:
        desc_low = description.casefold().replace("ё", "е")
        has_any_uncertainty = any(w in desc_low for w in _UNCERTAINTY_WORDS) or "предполож" in desc_low or "вероятн" in desc_low
        has_false_certainty = any(
            phrase in desc_low
            for phrase in ("причиной является", "ошибка вызвана", "из-за ошибки в настройках", "так как в настройках")
        )
        if has_false_certainty or not has_any_uncertainty:
            return _derive_clean_title(clean_prob), _refine_Fallback_description(clean_prob)

    # 4. Если автор просил только «проверить, почему...», нельзя подменять это на «исправить / устранить»
    if _source_only_asks_to_check(clean_prob):
        desc_low = description.casefold()
        title_low = title.casefold()
        if any(w in title_low for w in ("исправить", "исправление", "устранить", "устранение")) or (
            any(w in desc_low for w in ("исправить оценку", "необходимо исправить", "требуется исправить", "устранить ошибку"))
            and "проверить" not in desc_low
        ):
            return _derive_clean_title(clean_prob), _refine_Fallback_description(clean_prob)

    description = _sentence_case(description)
    if len(title) > 180:
        title = title[:180].rsplit(" ", 1)[0].rstrip(".,;:-")

    return title, description


def _fallback_ticket(problem: str) -> dict[str, str]:
    """Бережный резервный редактор без ИИ: сохраняет смысл, вопросы, просьбы и предположения."""
    title = _derive_clean_title(problem)
    description = _refine_Fallback_description(problem)
    title, description = _postprocess_ticket(problem, title, description)
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
            raise ValueError("Модель не вернула JSON с текстом заявки.")
        data = json.loads(text[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("Ответ модели имеет неверную структуру.")

    return data


def _validate_ai_ticket(problem: str, title: str, description: str) -> None:
    """Проверяет достоверность ответа и отсутствие придуманных чисел/фактов."""
    title = _clean_text(title)
    description = _clean_text(description)

    if not title:
        raise ValueError("Не сформировано название заявки.")

    if len(title) > 180:
        raise ValueError("Название заявки превышает допустимые 180 символов.")

    if not description:
        raise ValueError("Не сформировано описание заявки.")

    source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", problem))
    result_numbers = set(
        re.findall(r"\d+(?:[.,]\d+)?", f"{title} {description}")
    )

    if result_numbers - source_numbers:
        raise ValueError(
            "Добавлено число или дата, которых нет в исходном тексте."
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

    preserves_uncertainty = (
        "?" in description
        or any(marker in result for marker in (
            "просим разъяснить", "просим уточнить", "просим сообщить",
            "просим проверить", "почему", "требуется ли", "необходимо ли",
            "можно ли", "возможно ли", "каким образом", "порядок", "возможность",
        ))
    )

    assertive_markers = (
        "необходимо применить", "обязательно требуется",
        "должен быть издан", "причиной является",
        "ошибка вызвана", "после перерыва",
        "требуется выгрузить", "необходимо выгрузить",
    )

    if asks_question and any(
        marker in result for marker in assertive_markers
    ):
        if not preserves_uncertainty:
            raise ValueError(
                "Вопрос пользователя превращён в жёсткое утверждение."
            )

    if len(description) > max(1200, len(problem) * 6):
        raise ValueError(
            "Описание необоснованно расширено."
        )


def _normalise_for_comparison(value: str) -> str:
    return re.sub(r"[^а-яa-z0-9]+", " ", value.casefold().replace("ё", "е")).strip()


def _is_near_copy(problem: str, description: str) -> bool:
    """Определяет ответы, в которых модель лишь скопировала длинный черновик без редактуры."""
    source = _normalise_for_comparison(problem)
    result = _normalise_for_comparison(description)
    if not source or not result or len(source) < 120:
        return False

    similarity = SequenceMatcher(None, source, result).ratio()
    return similarity >= 0.96


def _finish_sentence(value: Any) -> str:
    """Очищает смысловой блок и завершает его знаком препинания."""
    text = _sentence_case(_clean_text(value)).strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _build_structured_description(data: dict[str, Any]) -> str:
    """Собирает заявку из ответа локальной модели без навязывания чужой модальности."""
    if data.get("description"):
        return _clean_text(data.get("description"))

    situation = _finish_sentence(data.get("situation"))
    checks = _finish_sentence(data.get("checks"))
    request_text = _clean_text(data.get("request"))
    constraint = _finish_sentence(data.get("constraint"))

    if request_text:
        request_text = _sentence_case(request_text)
        if request_text[-1] not in ".!?":
            request_text += "?" if request_text.casefold().startswith("можно ли") else "."

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
    payload = {
        "model": _select_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Обращение пользователя:\n{problem}",
            },
        ],
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.2,
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
        raise RuntimeError("Сервис генерации временно недоступен.") from exc

    except urllib.error.URLError as exc:
        raise RuntimeError("Локальный сервис генерации недоступен.") from exc

    except (TimeoutError, OSError) as exc:
        elapsed = round(time.monotonic() - started_at, 1)
        raise RuntimeError(f"Превышено время ожидания ответа ({elapsed} сек.).") from exc

    content = envelope.get("message", {}).get("content", "")
    title, description = _parse_ticket_response(content)
    if not title or not description:
        data = _extract_json(content)
        title = _clean_text(data.get("title"))
        description = _build_structured_description(data)

    if not title or not description:
        raise ValueError("Не удалось сформировать название или описание.")

    title, description = _postprocess_ticket(problem, title, description)
    _validate_ai_ticket(problem, title, description)

    return {
        "title": title[:180],
        "description": description,
        "source": "ollama",
    }


def _parse_ticket_response(raw_text: str) -> tuple[str, str]:
    text = str(raw_text or "").strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    title = ""
    description = ""

    theme_pattern = re.compile(
        r"(?:^|\n)\s*(?:\*\*|#+\s*)?(?:ТЕМА|ЗАГОЛОВОК|НАЗВАНИЕ(?:\s+ЗАЯВКИ)?)\s*(?:\*\*)?\s*:\s*(.*?)(?=\n\s*(?:\*\*|#+\s*)?ОПИСАНИЕ(?:\s+ЗАЯВКИ)?\s*(?:\*\*)?\s*:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    desc_pattern = re.compile(
        r"(?:^|\n)\s*(?:\*\*|#+\s*)?ОПИСАНИЕ(?:\s+ЗАЯВКИ)?\s*(?:\*\*)?\s*:\s*(.*)",
        re.IGNORECASE | re.DOTALL,
    )

    theme_match = theme_pattern.search(text)
    desc_match = desc_pattern.search(text)

    if theme_match and desc_match:
        title = theme_match.group(1).strip()
        description = desc_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines:
            first_line = lines[0]
            title = re.sub(
                r"^(?:\*\*|#+\s*)?(?:ТЕМА|ЗАГОЛОВОК|НАЗВАНИЕ(?:\s+ЗАЯВКИ)?)\s*(?:\*\*)?\s*:\s*",
                "",
                first_line,
                flags=re.I,
            ).strip()
            rest = "\n".join(lines[1:])
            description = re.sub(
                r"^(?:\*\*|#+\s*)?ОПИСАНИЕ(?:\s+ЗАЯВКИ)?\s*(?:\*\*)?\s*:\s*",
                "",
                rest,
                flags=re.I,
            ).strip()

    title = title.strip("«»\"'* ").rstrip(".,;:-")
    description = description.strip()
    if len(title) > 180:
        title = title[:180].rsplit(" ", 1)[0].rstrip(".,;:-")

    return title, description


def generate_ticket(problem: str) -> dict[str, str]:
    clean = _clean_text(problem)

    if len(clean) < 5:
        raise ValueError(
            "Опишите задачу или проблему хотя бы одним предложением."
        )

    # 1. Основной движок
    try:
        from ai_service import generate_text
        raw_text, provider = generate_text(
            prompt=f"Обращение пользователя:\n{clean}",
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
            return_provider=True,
        )
        title, description = _parse_ticket_response(raw_text)
        if title and description:
            title, description = _postprocess_ticket(clean, title, description)
            _validate_ai_ticket(clean, title, description)
            return {
                "title": title[:180],
                "description": description,
                "source": provider,
            }
    except Exception:
        pass

    return _fallback_ticket(clean)


def generate_ticket_stream(problem: str) -> Iterator[str]:
    """Генерация заявки с потоковой передачей ответа (SSE).

    События:
      data: {"type": "chunk", "text": "..."}\n\n
      data: {"type": "done", "title": "...", "description": "...", "full_text": "..."}\n\n
      data: {"type": "error", "error": "..."}\n\n
    """
    clean = _clean_text(problem)
    if len(clean) < 5:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Опишите задачу или проблему хотя бы одним предложением.'}, ensure_ascii=False)}\n\n"
        return

    try:
        result = generate_ticket(clean)
        title = result["title"][:180]
        description = result["description"]
        yield f"data: {json.dumps({'type': 'chunk', 'text': description}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'title': title, 'description': description, 'full_text': description}, ensure_ascii=False)}\n\n"
    except Exception:
        fb = _fallback_ticket(clean)
        yield f"data: {json.dumps({'type': 'done', 'title': fb['title'], 'description': fb['description'], 'full_text': fb['description']}, ensure_ascii=False)}\n\n"


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
            text="Сформировать заявку",
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
            bg=self.theme["input"],
            fg=self.theme["text"],
            insertbackground=self.theme["text"],
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

        self.title_text.delete("1.0", "end")
        self.description_text.delete("1.0", "end")

        self.generate_button.configure(
            state="disabled",
            text="Формирование заявки...",
        )
        self.status.configure(
            text="Формирование заявки...",
            fg=GREEN_DARK,
        )

        self._generation_id += 1
        generation_id = self._generation_id

        self._start_timer(generation_id)

        threading.Thread(
            target=self._worker,
            args=(problem, generation_id),
            daemon=True,
        ).start()

    def _worker(self, problem: str, generation_id: int):
        """Фоновый поток формирования обращения."""
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

        self._stop_timer()

        self._generation_id += 1
        self._put_result(result)

        self.generate_button.configure(
            state="normal",
            text="Сформировать заново",
        )
        self.status.configure(
            text="Заявка сформирована",
            fg=GREEN_DARK,
        )

    def _keep_draft(self, reason: str, generation_id: int):
        if generation_id != self._generation_id:
            return

        self._stop_timer()

        self._generation_id += 1
        self.generate_button.configure(
            state="normal",
            text="Попробовать снова",
        )

        self.title_text.delete("1.0", "end")
        self.description_text.delete("1.0", "end")

        self.status.configure(
            text="Не удалось сформировать заявку. Проверьте текст обращения и повторите попытку.",
            fg=RED,
        )

    def _expire_generation(self, generation_id: int):
        """Останавливает отображение ожидания, если метод вызван извне."""
        if generation_id != self._generation_id:
            return

        self._stop_timer()

        self._generation_id += 1
        self.generate_button.configure(
            state="normal",
            text="Попробовать снова",
        )
        self.status.configure(
            text="Время ожидания истекло. Повторите попытку.",
            fg=RED,
        )

    def _show_error(self, exc: Exception):
        self._stop_timer()
        self.generate_button.configure(
            state="normal",
            text="Сформировать заявку",
        )
        self.status.configure(
            text="Не удалось сформировать заявку",
            fg=RED,
        )
        messagebox.showerror(
            "Ticket Writer AI",
            "Не удалось сформировать заявку. Проверьте текст обращения и повторите попытку.",
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
            text="Сформировать заявку",
        )
        self.status.configure(
            text="Готово к работе",
            fg=self.theme["gray"],
        )
        self.problem.focus_set()


def open_ticket_writer(parent: tk.Misc):
    return TicketWriterWindow(parent)
