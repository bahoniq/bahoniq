# -*- coding: utf-8 -*-
"""Единый реестр учебной программы A0–B2, тренажёра диалогов и базового словаря."""

from __future__ import annotations

from typing import Any

from .curriculum_a0_a1 import LEVEL_A0, LEVEL_A1
from .curriculum_a2_b2 import LEVEL_A2, LEVEL_B1, LEVEL_B2

LEVELS: list[dict[str, Any]] = [LEVEL_A0, LEVEL_A1, LEVEL_A2, LEVEL_B1, LEVEL_B2]
LEVEL_ORDER = ["A0", "A1", "A2", "B1", "B2"]

DIALOGUES: list[dict[str, Any]] = [
    {
        "id": "dlg-a0-greeting",
        "level": "A0",
        "title": "Знакомство в офисе",
        "situation": "Первый рабочий день: представьтесь коллеге и ответьте на простой вопрос.",
        "turns": [
            {
                "speaker": "Colleague",
                "en": "Hello! My name is Daniyar. What is your name?",
                "ru": "Привет! Меня зовут Данияр. Как тебя зовут?",
                "options": [
                    {"en": "Hello! My name is Arman. Nice to meet you.", "correct": True, "feedback": "Отлично! Вежливое и грамматически полное представление."},
                    {"en": "My name Arman.", "correct": False, "feedback": "Почти! Пропущена связка is: нужно «My name is Arman»."},
                    {"en": "Yes, I am book.", "correct": False, "feedback": "Не подходит по смыслу: вас спросили имя (What is your name?)."},
                ],
            },
            {
                "speaker": "Colleague",
                "en": "Nice to meet you too! Are you ready for the tour?",
                "ru": "Мне тоже приятно познакомиться! Ты готов к экскурсии по офису?",
                "options": [
                    {"en": "Yes, I am ready!", "correct": True, "feedback": "Безупречно! I + am + ready."},
                    {"en": "Yes, I is ready.", "correct": False, "feedback": "С местоимением I всегда используется am, а не is."},
                    {"en": "No, are you.", "correct": False, "feedback": "Нарушен порядок слов и смысл ответа."},
                ],
            },
        ],
    },
    {
        "id": "dlg-a1-cafe",
        "level": "A1",
        "title": "Заказ в городском кафе",
        "situation": "Вы зашли выпить кофе перед работой и уточняете наличие выпечки.",
        "turns": [
            {
                "speaker": "Barista",
                "en": "Good morning! What can I get for you today?",
                "ru": "Доброе утро! Что для вас приготовить сегодня?",
                "options": [
                    {"en": "Can I have a black coffee, please?", "correct": True, "feedback": "Естественная и вежливая формула заказа: Can I have ..., please?"},
                    {"en": "Give coffee me.", "correct": False, "feedback": "Звучит грубо и грамматически неверно. В кафе говорят: Can I have a coffee, please?"},
                    {"en": "I does drink coffee.", "correct": False, "feedback": "С I не используется does, и для заказа лучше сказать Can I have..."},
                ],
            },
            {
                "speaker": "Barista",
                "en": "Sure! Anything else?",
                "ru": "Конечно! Что-нибудь ещё?",
                "options": [
                    {"en": "No, thank you. How much is it?", "correct": True, "feedback": "Точно! Вежливый отказ и вопрос о стоимости (How much is it?)."},
                    {"en": "How many money is it?", "correct": False, "feedback": "Деньги (money) неисчисляемые, а о цене спрашивают просто: How much is it?"},
                ],
            },
        ],
    },
    {
        "id": "dlg-a2-travel",
        "level": "A2",
        "title": "В аэропорту и отеле",
        "situation": "Регистрация в отеле во время командировки.",
        "turns": [
            {
                "speaker": "Receptionist",
                "en": "Good evening! Welcome to Grand Hotel. Do you have a reservation?",
                "ru": "Добрый вечер! Добро пожаловать в Grand Hotel. У вас есть бронь?",
                "options": [
                    {"en": "Yes, I booked a single room yesterday under my last name.", "correct": True, "feedback": "Верно! Чётко использован Past Simple (booked ... yesterday)."},
                    {"en": "Yes, I am book a room yesterday.", "correct": False, "feedback": "Для вчерашнего действия нужен Past Simple: I booked, без am."},
                ],
            },
            {
                "speaker": "Receptionist",
                "en": "Found it! Breakfast starts at 7 AM. Do you need help with your luggage?",
                "ru": "Нашёл! Завтрак начинается в 7 утра. Вам нужна помощь с багажом?",
                "options": [
                    {"en": "Thank you, my bag is light, I can carry it myself.", "correct": True, "feedback": "Отличный естественный ответ уровня A2!"},
                    {"en": "I going take bag.", "correct": False, "feedback": "Пропущены связка и артикли/местоимение."},
                ],
            },
        ],
    },
    {
        "id": "dlg-b1-work-sync",
        "level": "B1",
        "title": "Рабочий созвон по задаче",
        "situation": "Обсуждение статуса задачи и сроков с проектным менеджером.",
        "turns": [
            {
                "speaker": "Project Manager",
                "en": "Hi! Have you had a chance to review the updated specification yet?",
                "ru": "Привет! Тебе уже удалось посмотреть обновлённое ТЗ?",
                "options": [
                    {"en": "Yes, I have already reviewed it, and most points are clear.", "correct": True, "feedback": "Отличное использование Present Perfect (have already reviewed) для результата к текущему моменту!"},
                    {"en": "Yes, I have reviewed it yesterday.", "correct": False, "feedback": "С yesterday нельзя использовать Present Perfect (have reviewed) — только Past Simple или убрать yesterday."},
                ],
            },
            {
                "speaker": "Project Manager",
                "en": "Great. What if the client asks for an extra export format?",
                "ru": "Отлично. А что если клиент попросит ещё один формат выгрузки?",
                "options": [
                    {"en": "If they ask for PDF export, we will need two extra days.", "correct": True, "feedback": "Безупречный First Conditional: If + Present Simple, ... will + V."},
                    {"en": "If they will ask, we will need two days.", "correct": False, "feedback": "После If в условном предложении 1-го типа will не ставится!"},
                ],
            },
        ],
    },
    {
        "id": "dlg-b2-negotiation",
        "level": "B2",
        "title": "Аргументация решения на совещании",
        "situation": "Защита поэтапного запуска системы перед руководством.",
        "turns": [
            {
                "speaker": "Director",
                "en": "Why shouldn't we roll out the new platform to all branches simultaneously?",
                "ru": "Почему бы нам не раскатить новую платформу сразу на все филиалы одновременно?",
                "options": [
                    {"en": "While a full rollout sounds faster, carrying out a two-week pilot will help us figure out hidden bottlenecks without risking daily operations.", "correct": True, "feedback": "Блестяще! Использованы уступка (While...), фразовые глаголы (carry out, figure out) и убедительная деловая аргументация."},
                    {"en": "Because simultaneous rollout is bad and maybe makes big error.", "correct": False, "feedback": "Грамматически слабо и неубедительно для деловой дискуссии уровня B2."},
                ],
            },
        ],
    },
]


def get_all_lessons_flat() -> list[dict[str, Any]]:
    """Возвращает плоский упорядоченный список всех уроков, проверок и экзаменов A0–B2."""
    flat: list[dict[str, Any]] = []
    for lvl in LEVELS:
        for sec in lvl["sections"]:
            for les in sec["lessons"]:
                item = dict(les)
                item["level"] = lvl["code"]
                item["section_id"] = sec["id"]
                item["section_title"] = sec["title"]
                flat.append(item)
    return flat


def get_lesson_by_id(lesson_id: str) -> dict[str, Any] | None:
    for item in get_all_lessons_flat():
        if item["id"] == lesson_id:
            return item
    return None


def get_base_vocabulary() -> list[dict[str, Any]]:
    """Собирает единый базовый словарь курса без дублей с привязкой к уровню и уроку."""
    seen: set[str] = set()
    words: list[dict[str, Any]] = []
    for item in get_all_lessons_flat():
        for v in item.get("vocab", []):
            key = v["word"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            words.append(
                {
                    "id": f"w-{key.replace(' ', '-')}",
                    "word": v["word"],
                    "ipa": v.get("ipa", ""),
                    "ru_hint": v.get("ru_hint", ""),
                    "ru": v["ru"],
                    "example": v.get("example", ""),
                    "topic": v.get("topic", "Общая лексика"),
                    "level": item["level"],
                    "lesson_id": item["id"],
                }
            )
    return words


def get_curriculum_payload() -> dict[str, Any]:
    return {
        "levels": LEVELS,
        "dialogues": DIALOGUES,
        "vocabulary_count": len(get_base_vocabulary()),
        "total_lessons": len(get_all_lessons_flat()),
    }
