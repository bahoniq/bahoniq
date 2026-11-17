import io
import unittest
from unittest.mock import patch
from PIL import Image as PILImage
from modules.instruction_generator_core import (
    generate_instruction,
    to_html,
    to_markdown,
    to_pdf,
    normalize_screenshot_16_9,
)

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
        self.assertIn("<h2>1. Авторизация</h2>", to_html(doc))

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
        self.assertEqual(doc["steps"][0]["caption"], "Авторизация")

    def test_html_16_9_container(self):
        doc = sample()
        doc["steps"][0]["image"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        html_out = to_html(doc)
        self.assertIn("16cm", html_out)
        self.assertIn("9cm", html_out)
        self.assertIn("1.15pt", html_out)
        self.assertIn("screen-container", html_out)

    def test_normalize_screenshot_16_9(self):
        # Wide image
        im_wide = PILImage.new("RGB", (1920, 1080), color=(100, 100, 100))
        buf_wide = io.BytesIO()
        im_wide.save(buf_wide, format="PNG")
        main_wide, det_wide = normalize_screenshot_16_9(buf_wide.getvalue())
        self.assertIsNotNone(main_wide)
        self.assertIsNone(det_wide)
        res_im = PILImage.open(io.BytesIO(main_wide))
        self.assertAlmostEqual(res_im.width / res_im.height, 16.0 / 9.0, delta=0.01)

        # Tall image (should create detail crop)
        im_tall = PILImage.new("RGB", (600, 1000), color=(100, 100, 100))
        buf_tall = io.BytesIO()
        im_tall.save(buf_tall, format="PNG")
        main_tall, det_tall = normalize_screenshot_16_9(buf_tall.getvalue())
        self.assertIsNotNone(main_tall)
        self.assertIsNotNone(det_tall)

    def test_pdf_borders_on_all_pages(self):
        try:
            import fitz
        except ImportError:
            return
        doc = {
            "title": "Многостраничный тест",
            "steps": [
                {"number": 1, "text": "Шаг 1: действие первое", "caption": "Шаг 1", "image": ""},
                {"number": 2, "text": "Шаг 2: действие второе", "caption": "Шаг 2", "image": ""},
                {"number": 3, "text": "Шаг 3: действие третье", "caption": "Шаг 3", "image": ""},
                {"number": 4, "text": "Шаг 4: действие четвертое", "caption": "Шаг 4", "image": ""},
            ]
        }
        pdf_bytes = to_pdf(doc)
        doc_fitz = fitz.open(stream=pdf_bytes, filetype="pdf")
        self.assertGreaterEqual(len(doc_fitz), 2)
        for i, page in enumerate(doc_fitz):
            rects = [d for d in page.get_drawings() if any(item[0] == "re" for item in d.get("items", []))]
            self.assertGreaterEqual(len(rects), 1, f"Missing border rectangle on page {i+1}")

if __name__ == "__main__":
    unittest.main()
