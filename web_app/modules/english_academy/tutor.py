# -*- coding: utf-8 -*-
"""Персональный ИИ-наставник English Academy Studio.

Использует общий облачный слой BahonIQ (`ai_service.generate_text`) и имеет
полноценный педагогический автономный режим без доступа к ИИ или сети.
"""

from __future__ import annotations

import re
from typing import Any

from ai_service import generate_text
from .curriculum import get_lesson_by_id
from .engine import build_progress_report


SYSTEM_PROMPT = """Ты — персональный наставник по английскому языку в BahonIQ English Academy Studio.
Ученик проходит структурный курс от полного нуля (A0) до уверенного владения (B2).
Строгие правила твоей работы:
1. Всегда объясняй правила и ошибки простым, спокойным и уважительным русским языком, без сложных лингвистических терминов в начале.
2. Опирайся на текущий уровень ученика, текущий урок и его недавние ошибки.
3. Если режим 'hint' (подсказка к заданию) — НИКОГДА не выдавай готовый английский ответ сразу: дай короткую наводящую подсказку в 1–2 предложениях.
4. Если режим 'check_writing' — разбери фразу ученика: что уже хорошо, где ошибка и как звучит естественно по-английски.
5. Если режим 'dialogue' — веди короткий живой диалог на английском строго по уровню ученика (1–2 реплики), не раскрывай готовую реплику ученика до его попытки, а ниже в скобках дай краткий перевод или мягкую коррекцию по-русски, если в ответе ученика была ошибка.
6. Пиши кратко и по делу: не более 3–5 коротких предложений или до 4 коротких пунктов, без длинных простыней текста, если ученик сам не попросил подробный разбор."""


def _build_local_fallback(
    mode: str,
    message: str,
    lesson: dict[str, Any] | None,
    report: dict[str, Any],
    force_offline: bool = False,
) -> dict[str, Any]:
    """Качественный локальный педагогический ответ, когда облачный ИИ недоступен."""
    cur_level = report.get("current_level", "A0")
    next_step = report.get("next_step", {})
    mistakes_cnt = report.get("unresolved_mistakes_count", 0)
    notice = (
        "Автономный режим наставника: облачный ИИ сейчас недоступен, поэтому работает встроенная методическая база курса. Прогресс и все уроки сохраняются штатно."
        if not force_offline
        else "Включён локальный автономный режим без облачного ИИ."
    )

    if mode == "hint":
        if lesson:
            ans = (
                f"Подсказка по теме «{lesson['title']}» ({lesson['level']}): "
                f"проверьте порядок слов (кто -> глагол/связка -> остальное). "
                f"Опора на правило: {lesson.get('rule_name', '')}."
            )
        else:
            ans = "Посмотрите на подлежащее (кто совершает действие): от него зависит выбор связки (am/is/are или do/does) и порядок слов."
    elif mode == "explain":
        if lesson:
            examples = "; ".join(f"{ex['en']} ({ex['ru']})" for ex in lesson.get("examples", [])[:3])
            ans = (
                f"Разберём тему «{lesson['title']}» простыми словами:\n\n"
                f"{lesson.get('simple_explanation', '')}\n\n"
                f"Примеры из урока: {examples}"
            )
        else:
            ans = (
                f"Сейчас ваш уровень — {cur_level}. Главное правило английского предложения: "
                f"в нём почти всегда есть подлежащее (кто?) и сказуемое-глагол (что делает? или связка am/is/are)."
            )
    elif mode == "check_writing":
        clean = message.strip()
        words = [w for w in re.split(r"\s+", clean) if w]
        has_cyr = bool(re.search(r"[а-яёА-ЯЁ]", clean))
        if not clean:
            ans = "Напишите английское предложение для проверки — я проверю порядок слов и базовую грамматику."
        elif has_cyr:
            ans = "В тексте встретились русские буквы. Попробуйте записать мысль полностью латиницей, опираясь на слова текущего урока."
        elif len(words) < 3:
            ans = "Фраза пока слишком короткая для полного предложения. Добавьте подлежащее и глагол (например: I am ready / I work in an office)."
        else:
            starts_cap = clean[0].isupper()
            ends_punct = clean[-1] in ".!?"
            tips = []
            if not starts_cap:
                tips.append("начинайте предложение с заглавной буквы (и местоимение I всегда пишите большой буквой)")
            if not ends_punct:
                tips.append("поставьте точку или вопросительный знак в конце")
            if tips:
                ans = f"Хорошая попытка ({len(words)} сл.)! Рекомендация по оформлению: {', '.join(tips)}."
            else:
                ans = f"Структура выглядит аккуратно ({len(words)} сл.): соблюдены заглавная буква и пунктуация. Сверьте форму глагола с образцом урока."
    elif mode == "dialogue":
        starters = {
            "A0": "Hello! Nice to meet you. How are you today? (Привет! Приятно познакомиться. Как у тебя сегодня дела? — ответьте, например: I am good / I am ready.)",
            "A1": "Hi! Where do you live and what do you usually do in the morning? (Привет! Где ты живёшь и что обычно делаешь утром?)",
            "A2": "Hello! What did you do yesterday, and what are you going to do tomorrow? (Что вы делали вчера и что планируете на завтра?)",
            "B1": "Hi there! Have you ever worked remotely? What do you think about it? (Вы когда-нибудь работали удалённо? Что думаете об этом?)",
            "B2": "Welcome! Could you share a recent challenge at work and how you figured it out? (Расскажите о недавней рабочей задаче и как вы с ней разобрались?)",
        }
        if not message.strip():
            ans = starters.get(cur_level, starters["A0"])
        else:
            ans = (
                f"Good point! Thank you for sharing. Could you tell me one more detail about that? "
                f"(Хорошая реплика! Расскажите ещё одну деталь на уровне {cur_level}.)"
            )
    elif mode == "extra_practice":
        if lesson and lesson.get("examples"):
            ex = lesson["examples"][0]
            ans = (
                f"Дополнительное мини-задание по теме «{lesson['title']}»:\n"
                f"1. Прочитайте вслух образец: «{ex['en']}» ({ex['ru']}).\n"
                f"2. Замените одно слово в этом образце на своё и составьте 2 варианта: утверждение и вопрос."
            )
        else:
            ans = f"Следующий рекомендованный шаг программы: урок «{next_step.get('title', '')}» ({cur_level})."
    else:
        ans = (
            f"Ваш текущий уровень — {cur_level}. "
            f"Следующий урок по плану: «{next_step.get('title', '')}». "
            + (f"Незакрытых ошибок для повторения: {mistakes_cnt}. " if mistakes_cnt else "")
            + "Откройте раздел «Курс» или нажмите «Продолжить обучение» на главной вкладке."
        )

    return {
        "answer": ans,
        "online": False,
        "provider": "Локальный методист (без облачного ИИ)",
        "notice": notice,
    }


def ask_english_tutor(
    state: dict[str, Any],
    mode: str = "chat",
    message: str = "",
    lesson_id: str = "",
    force_offline: bool = False,
) -> dict[str, Any]:
    """Запрос к персональному ИИ-наставнику с автоматическим откатом на локальный режим."""
    report = build_progress_report(state)
    target_lesson_id = lesson_id or state.get("current_lesson_id") or "a0-l1"
    lesson = get_lesson_by_id(target_lesson_id)

    if force_offline:
        return _build_local_fallback(mode, message, lesson, report, force_offline=True)

    recent_mistakes = [
        f"- [{m['skill']}] {m['prompt']} | Ответ ученика: {m['user_answer']} | Эталон: {m['expected']}"
        for m in state.get("mistakes", [])
        if not m.get("resolved")
    ][-5:]

    lesson_ctx = (
        f"Текущий урок: {lesson['id']} — {lesson['title']} (уровень {lesson['level']}). Правило: {lesson.get('rule_name', '')}."
        if lesson
        else f"Текущий уровень: {report.get('current_level', 'A0')}."
    )
    mistakes_ctx = "\n".join(recent_mistakes) if recent_mistakes else "Активных ошибок пока нет."

    mode_instructions = {
        "explain": "Объясни текущую тему урока максимально простым языком для русскоязычного ученика и дай 3 коротких примера с переводом.",
        "hint": "Дай короткую наводящую подсказку по вопросу/ошибке ученика, НЕ раскрывая готовый английский ответ.",
        "check_writing": "Проверь английскую фразу или текст ученика: укажи ошибки простым русским языком, объясни почему так нельзя и покажи естественный вариант.",
        "dialogue": "Проведи шаг живого тренировочного диалога на английском строго на уровне ученика. Если ученик допустил ошибку в своей реплике — мягко поправь по-русски в скобках и продолжи диалог вопросом.",
        "extra_practice": "Составь 2 коротких дополнительных практических задания именно по текущему уроку и недавним ошибкам ученика (без раскрытия ответов сразу).",
        "next_plan": "Сформируй конкретный план следующего занятия на 10–15 минут с учётом прогресса и ошибок ученика.",
        "chat": "Ответь на вопрос ученика понятно, структурно и с примерами по его уровню.",
    }

    prompt = (
        f"Профиль ученика: уровень {report.get('current_level', 'A0')}, пройдено уроков {report.get('completed_lessons', 0)}/{report.get('total_lessons', 0)}.\n"
        f"{lesson_ctx}\n"
        f"Недавние ошибки ученика:\n{mistakes_ctx}\n\n"
        f"Режим запроса: {mode} — {mode_instructions.get(mode, mode_instructions['chat'])}\n"
        f"Сообщение ученика: {message.strip() or 'Помоги по текущему шагу обучения.'}"
    )

    try:
        answer = generate_text(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            timeout=30,
        )
        cleaned = str(answer or "").strip()
        if not cleaned:
            raise RuntimeError("Empty AI response")
        return {
            "answer": cleaned,
            "online": True,
            "provider": "Облачный ИИ-наставник BahonIQ",
            "notice": "",
        }
    except Exception:
        return _build_local_fallback(mode, message, lesson, report, force_offline=False)
