"""Exercise the real UI callbacks without requiring a desktop display."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
from modules.excel_ai.ui import ExcelAIWindow


class Text:
    def __init__(self, value): self.value = value
    def get(self, *args): return self.value
    def delete(self, *args): self.value = ''
    def insert(self, position, value): self.value = value
    def edit_modified(self, *args): return False


class AssistantUIStateTests(unittest.TestCase):
    def ui(self, edited=None):
        ui = SimpleNamespace()
        ui.instruction_text = Text('Исходная задача')
        ui.assistant_text = Text(edited or '1. Готовая формулировка')
        ui._assistant_result = {'questions': [], 'text': '1. Готовая формулировка',
                                'operations': [{'type': 'trim_text', 'sheet': 'S', 'columns': ['ФИО']}]}
        ui._assistant_signature = ('source.xlsx', 'Исходная задача', 1)
        ui._current_signature = lambda: ('source.xlsx', ui.instruction_text.value, 1)
        ui.status_var = Mock(); ui.apply_rewrite_button = Mock()
        ui.operations = [{'type': 'old'}]
        ui._invalidate_current_plan = lambda reason: ExcelAIWindow._invalidate_current_plan(ui, reason)
        return ui

    def test_unchanged_helper_reuses_exact_operations(self):
        ui = self.ui()
        ExcelAIWindow._apply_rewrite(ui)
        self.assertEqual(ui.operations, ui._assistant_result['operations'])
        self.assertIsNot(ui.operations, ui._assistant_result['operations'])
        self.assertEqual(ui._interpreted_signature, ui._current_signature())
        self.assertIsNone(ui.current_plan)

    def test_edited_helper_requires_new_interpretation(self):
        ui = self.ui('1. Другая задача')
        ExcelAIWindow._apply_rewrite(ui)
        self.assertEqual(ui.instruction_text.value, '1. Другая задача')
        self.assertEqual(ui.operations, [])
        self.assertIsNone(ui._interpreted_signature)

    def test_stale_helper_not_applied(self):
        ui = self.ui(); ui.instruction_text.value = 'Новая задача'
        with patch('modules.excel_ai.ui.messagebox.showinfo') as alert:
            ExcelAIWindow._apply_rewrite(ui)
            alert.assert_called_once()
        self.assertEqual(ui.instruction_text.value, 'Новая задача')

    def test_questions_cannot_be_applied_as_operations(self):
        ui = self.ui(); ui._assistant_result['questions'] = ['Какой столбец?']
        ExcelAIWindow._apply_rewrite(ui)
        self.assertEqual(ui.instruction_text.value, 'Исходная задача')


if __name__ == '__main__':
    unittest.main()
