"""Автоматические тесты для модуля Ticket Writer AI (modules/ticket_writer.py)."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from modules.ticket_writer import (
    SYSTEM_PROMPT,
    _fallback_ticket,
    _parse_ticket_response,
    _postprocess_ticket,
    _validate_ai_ticket,
    generate_ticket,
    generate_ticket_stream,
)


ROOT_DIR = Path(__file__).resolve().parent.parent


class TestTicketWriter(unittest.TestCase):
    def test_system_prompt_rules(self):
        """Системный промпт должен явно защищать вопросы, вежливость и гипотезы."""
        self.assertIn("Можно ли", SYSTEM_PROMPT)
        self.assertIn("Просим", SYSTEM_PROMPT)
        self.assertIn("Требуется", SYSTEM_PROMPT)
        self.assertIn("возможно", SYSTEM_PROMPT.lower())
        self.assertIn("ТЕМА:", SYSTEM_PROMPT)
        self.assertIn("ОПИСАНИЕ:", SYSTEM_PROMPT)

    def test_example_1_preserves_question_and_politeness(self):
        """Пример 1: «Можно ли получить логи...» остаётся вопросом без «Требуется выгрузить»."""
        src = (
            "Добрый день, можно ли получить логи по трем типам приказа общежития. "
            "Номер приказа, фамилии студентов и кем был сформирован приказ?"
        )
        fb = _fallback_ticket(src)
        self.assertIn("лог", fb["title"].lower())
        self.assertIn("общежит", fb["title"].lower())
        self.assertIn("?", fb["description"])
        self.assertIn("можно ли", fb["description"].lower())

        for banned in ("требуется выгрузить", "необходимо выполнить", "выполнить выгрузку", "требуется", "необходимо"):
            self.assertNotIn(banned, fb["title"].lower())
            self.assertNotIn(banned, fb["description"].lower())

        # Даже если модель вернёт жёсткий императив, постобработка обязана его обезвредить
        bad_title, bad_desc = _postprocess_ticket(
            src,
            "Требуется выгрузить логи по приказам общежития",
            "Требуется выгрузить логи по трём типам приказов общежития. Необходимо выполнить выгрузку.",
        )
        self.assertNotIn("требуется", bad_title.lower())
        self.assertNotIn("требуется", bad_desc.lower())
        self.assertNotIn("необходимо", bad_desc.lower())
        self.assertIn("?", bad_desc)
        self.assertIn("можно ли", bad_desc.lower())

    def test_example_2_preserves_uncertainty(self):
        """Пример 2: предположение «возможно» не превращается в установленный факт."""
        src = "У некоторых студентов не отображается расписание, возможно, проблема в настройках группы."
        fb = _fallback_ticket(src)
        self.assertIn("возможно", fb["description"].lower())
        self.assertNotIn("причиной является", fb["description"].lower())
        self.assertNotIn("ошибка вызвана", fb["description"].lower())

        # Если модель попыталась выдать предположение за факт, постобработка возвращает гипотезу
        fixed_title, fixed_desc = _postprocess_ticket(
            src,
            "Ошибка в настройках группы",
            "У некоторых студентов не отображается расписание. Причиной является сбой в настройках группы.",
        )
        self.assertIn("возможно", fixed_desc.lower())
        self.assertNotIn("причиной является", fixed_desc.lower())

    def test_example_3_preserves_polite_check_request(self):
        """Пример 3: «Просим проверить, почему...» не превращается в приказ «Исправить оценку»."""
        src = "Просим проверить, почему оценка не отображается."
        fb = _fallback_ticket(src)
        self.assertIn("просим проверить", fb["description"].lower())
        self.assertNotIn("исправить оценку", fb["title"].lower())
        self.assertNotIn("исправить оценку", fb["description"].lower())
        self.assertNotIn("требуется", fb["description"].lower())

        fixed_title, fixed_desc = _postprocess_ticket(
            src,
            "Исправить оценку в журнале",
            "Требуется исправить оценку, которая не отображается.",
        )
        self.assertIn("просим проверить", fixed_desc.lower())
        self.assertNotIn("исправить оценку", fixed_title.lower())
        self.assertNotIn("требуется", fixed_desc.lower())

    def test_no_invented_numbers_or_facts(self):
        """Валидатор отклоняет ответы, куда модель добавила несуществующие числа или даты."""
        src = "Просим проверить, почему оценка не отображается."
        with self.assertRaises(ValueError):
            _validate_ai_ticket(
                src,
                "Проверка отображения оценки за 2 семестр",
                "Просим проверить, почему оценка 85 не отображается с 15.11.",
            )

    def test_parse_ticket_response(self):
        """Парсер корректно разбирает ответ Gemini в формате ТЕМА / ОПИСАНИЕ."""
        raw = (
            "ТЕМА: Предоставление логов по приказам общежития\n"
            "ОПИСАНИЕ: Добрый день! Можно ли получить логи по трём типам приказов по общежитию "
            "с указанием номера приказа, ФИО студентов и пользователя, сформировавшего приказ?"
        )
        title, desc = _parse_ticket_response(raw)
        self.assertEqual(title, "Предоставление логов по приказам общежития")
        self.assertTrue(desc.startswith("Добрый день! Можно ли получить логи"))
        self.assertTrue(desc.endswith("?"))

    def test_generate_ticket_and_stream_with_mocked_gemini(self):
        """Проверяет полный цикл generate_ticket и generate_ticket_stream."""
        src = "Просим проверить, почему оценка не отображается."
        mock_reply = (
            "ТЕМА: Проверка отображения оценки\n"
            "ОПИСАНИЕ: Просим проверить, почему не отображается оценка."
        )
        with patch("ai_service.generate_text", return_value=(mock_reply, "gemini")):
            res = generate_ticket(src)
            self.assertEqual(res["title"], "Проверка отображения оценки")
            self.assertIn("просим проверить", res["description"].lower())

            events = list(generate_ticket_stream(src))
            self.assertTrue(any('"type": "done"' in ev for ev in events))

    def test_ui_has_no_streaming_or_bahoniq_ai_status_strings(self):
        """В интерфейсе Ticket Writer не должно быть слов «стриминг» и подписи «BahonIQ AI» в статусах."""
        app_js = (ROOT_DIR / "web_app" / "static" / "app.js").read_text(encoding="utf-8")
        # Извлекаем блок TICKET WRITER AI
        start = app_js.index("// ----------------- TICKET WRITER AI -----------------")
        end = app_js.index("// ----------------- PHONEBOOK -----------------", start)
        ticket_block = app_js[start:end]

        self.assertNotIn("стриминг", ticket_block.lower())
        self.assertNotIn("Стриминг", ticket_block)
        self.assertNotIn("BahonIQ AI", ticket_block)
        self.assertIn("Заявка сформирована", ticket_block)

        desktop_py = (ROOT_DIR / "modules" / "ticket_writer.py").read_text(encoding="utf-8")
        win_start = desktop_py.index("class TicketWriterWindow:")
        desktop_ui_code = desktop_py[win_start:]
        self.assertNotIn("стриминг", desktop_ui_code.lower())
        self.assertNotIn("Текст успешно сформирован", desktop_ui_code)
        self.assertIn('"Заявка сформирована"', desktop_ui_code)


if __name__ == "__main__":
    unittest.main()
