import io
import unittest
from unittest.mock import patch
from PIL import Image as PILImage
from modules.instruction_generator_core import (
    generate_instruction,
    to_html,
    to_markdown,
    to_pdf,
    make_step_title,
)

def sample():
    return {
        "title": "Инструкция по работе с порталом",
        "audience": "Студенты",
        "department": "ЦЦУ",
        "intro": "как работать",
        "steps": [{"text": "потом нажать войти в систему", "caption": "Авторизация", "image": ""}],
    }

class TestInstructionGenerator(unittest.TestCase):
    @patch("ai_service.generate_text", side_effect=RuntimeError("offline"))
    def test_fallback_generation(self, mock_ai):
        doc = generate_instruction(sample())
        self.assertEqual(doc["steps"][0]["number"], 1)
        self.assertTrue(doc["steps"][0]["text"].endswith("."))
        self.assertIn("Авторизация в системе", to_markdown(doc))
        self.assertIn("<h2>1. Авторизация в системе</h2>", to_html(doc))

    @patch("ai_service.generate_text", side_effect=RuntimeError("offline"))
    def test_pdf_created(self, mock_ai):
        pdf_bytes = to_pdf(generate_instruction(sample()))
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    @patch("ai_service.generate_text", side_effect=RuntimeError("offline"))
    def test_caption_and_audience_are_normalized(self, mock_ai):
        data = sample()
        data["audience"] = "деканат,студенты"
        data["steps"][0]["caption"] = "Рисунок 1. Авторизация"
        doc = generate_instruction(data)
        self.assertEqual(doc["audience"], "Деканат и студенты")
        self.assertEqual(doc["steps"][0]["caption"], "Авторизация в системе")

    def test_make_step_title_word_count(self):
        samples = [
            ("Авторизация", "", 1, "Авторизация в системе"),
            ("Выбор студента", "", 2, "Выбор студента"),
            ("Добавление дисциплины", "", 3, "Добавление дисциплины"),
            ("Рисунок 4. Подтверждение данных", "", 4, "Подтверждение данных"),
            ("", "переходим во вкладку заявки и подтверждаем документ", 5, "Переходим во вкладку заявки и подтверждаем документ"),
        ]
        for cap, txt, num, expected in samples:
            res = make_step_title(cap, txt, num)
            words = res.split()
            self.assertGreaterEqual(len(words), 2, f"Too short: {res}")
            self.assertLessEqual(len(words), 7, f"Too long: {res}")
            if expected:
                self.assertEqual(res, expected)

    def test_html_export_structure(self):
        doc = sample()
        doc["steps"][0]["image"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        html_out = to_html(doc)
        self.assertIn("16cm", html_out)
        self.assertIn("11cm", html_out)
        self.assertIn("1.15pt", html_out)
        self.assertIn("screenshot-img", html_out)
        self.assertIn("<b>Рисунок 1.</b> Авторизация в системе", html_out)

    def test_pdf_borders_on_all_5_pages(self):
        try:
            import fitz
        except ImportError:
            return

        h_im = PILImage.new("RGB", (1600, 900), color=(100, 150, 200))
        h_buf = io.BytesIO()
        h_im.save(h_buf, format="PNG")
        import base64
        h_data = "data:image/png;base64," + base64.b64encode(h_buf.getvalue()).decode("ascii")

        doc = {
            "title": "Инструкция по работе с порталом",
            "steps": [
                {"number": i, "text": f"Выполните необходимое регламентное действие этапа {i} в системе.", "caption": f"Этап {i}", "image": h_data}
                for i in range(1, 9)
            ]
        }
        pdf_bytes = to_pdf(doc)
        doc_fitz = fitz.open(stream=pdf_bytes, filetype="pdf")
        self.assertGreaterEqual(len(doc_fitz), 5)
        for i, page in enumerate(doc_fitz):
            rects = [d for d in page.get_drawings() if any(item[0] == "re" for item in d.get("items", []))]
            self.assertGreaterEqual(len(rects), 1, f"Missing border rectangle on page {i+1}")

if __name__ == "__main__":
    unittest.main()
