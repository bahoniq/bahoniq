import unittest
from unittest.mock import patch
from modules.instruction_generator_core import generate_instruction, to_html, to_markdown, to_pdf

def sample():
    return {
        "title": "Инструкция",
        "audience": "Студенты",
        "department": "ЦЦУ",
        "intro": "как работать",
        "steps": [{"text": "потом нажать войти", "caption": "Авторизация", "image": ""}],
    }

class TestInstructionGenerator(unittest.TestCase):
    @patch("ai_service.generate_text", side_effect=RuntimeError("offline"))
    def test_fallback_generation(self, mock_ai):
        doc = generate_instruction(sample())
        self.assertEqual(doc["steps"][0]["number"], 1)
        self.assertTrue(doc["steps"][0]["text"].endswith("."))
        self.assertIn("Шаг 1", to_markdown(doc))
        self.assertNotIn("Рисунок", to_markdown(doc))
        self.assertIn("<h2>Шаг 1</h2>", to_html(doc))

    @patch("ai_service.generate_text", side_effect=RuntimeError("offline"))
    def test_pdf_created(self, mock_ai):
        pdf_bytes = to_pdf(generate_instruction(sample()))
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

if __name__ == "__main__":
    unittest.main()
