import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from modules.excel_ai.ai_interpreter import interpret_task
from modules.excel_ai.analyzer import analyze_workbook
from modules.excel_ai.intent_compiler import compile_intent
from modules.excel_ai.operations import plan_operations, execute_operations, _validate_ops, _do
from modules.excel_ai.sheet_names import resolve_sheet_name
from modules.excel_ai.task_assistant import rewrite_task, operation_steps


REQUEST = 'выведи каждый айди со столбца айди студентов на новые строки на новые листы'
SHEET = 'Оцифровка дипломов ( по всем го'


class ExtractionAssistantTests(unittest.TestCase):
    def setUp(self):
        self.analysis = {'sheets': [{'name': SHEET, 'headers': ['ИИН', 'Айди выпускников']}]}

    def route(self, text=REQUEST, analysis=None, **kwargs):
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama',
                   side_effect=AssertionError('This request must work offline')):
            return interpret_task(text, analysis or self.analysis, **kwargs)

    def test_original_request(self):
        result = self.route()
        self.assertFalse(result['questions'])
        self.assertEqual(result['operations'], [{'type': 'extract_split_values_to_sheet',
                         'sheet': SHEET, 'column': 'Айди выпускников',
                         'output_sheet': 'Айди выпускников', 'header_rows': 1}])

    def test_conversational_variants(self):
        for verb in ['выведи', 'вывести', 'извлеки', 'извлечь', 'перенеси', 'разверни', 'раздели']:
            for rows in ['на новые строки', 'по одному на строку', 'по строкам', 'вертикально']:
                with self.subTest(verb=verb, rows=rows):
                    result = self.route(f'{verb} ID студентов {rows} на новый лист')
                    self.assertEqual(result['operations'][0]['type'], 'extract_split_values_to_sheet')

    def test_compiler_agrees_with_interpreter(self):
        compiled = compile_intent(REQUEST, self.analysis)
        self.assertIn('extract_split_values_to_sheet', compiled['actions'])
        self.assertNotIn('split_to_sheets', compiled['actions'])

    def test_helper_roundtrip(self):
        result = rewrite_task(REQUEST, self.analysis)
        self.assertEqual(len(result['text'].splitlines()), len(result['operations']))
        self.assertEqual(self.route(result['text'])['operations'], result['operations'])

    def test_unknown_column_is_not_guessed(self):
        result = self.route('выведи телефоны из столбца Телефон по строкам на новый лист')
        self.assertTrue(result['questions'])
        self.assertFalse(result['operations'])

    def test_iin_is_not_student_id(self):
        result = self.route(analysis={'sheets': [{'name': 'S', 'headers': ['ИИН']}]})
        self.assertTrue(result['questions'])

    def test_multiple_id_columns(self):
        a = {'sheets': [{'name': 'S', 'headers': ['ID студента', 'Айди выпускников']}]}
        self.assertTrue(self.route(analysis=a)['questions'])

    def test_exact_header_disambiguates(self):
        a = {'sheets': [{'name': 'S', 'headers': ['ID', 'Айди выпускников']}]}
        result = self.route('выведи Айди выпускников по строкам на новый лист', a)
        self.assertEqual(result['operations'][0]['column'], 'Айди выпускников')

    def test_duplicate_headers_need_clarification(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Айди выпускников'] * 2}]}
        self.assertTrue(self.route(analysis=a)['questions'])

    def test_multiple_sheets_need_clarification(self):
        a = {'sheets': [{'name': s, 'headers': ['Айди выпускников']} for s in ['A', 'B']]}
        self.assertTrue(self.route(analysis=a)['questions'])
        self.assertEqual(self.route(analysis=a, selected_sheet='B')['operations'][0]['sheet'], 'B')

    def test_unknown_selected_sheet_does_not_fall_back(self):
        with self.assertRaises(ValueError):
            self.route(selected_sheet='Missing')

    def test_sheet_name_not_inferred_from_header_or_cell_address(self):
        a = {'sheets': [{'name': s, 'headers': ['Айди выпускников']} for s in ['A', 'B']]}
        text = rewrite_task(REQUEST, a, selected_sheet='B')['text']
        self.assertEqual(self.route(text, a)['operations'][0]['sheet'], 'B')

    def test_unknown_explicit_source_does_not_choose_only_sheet(self):
        self.assertTrue(self.route(REQUEST + ' на листе «Несуществующий»')['questions'])

    def test_conflicting_destinations_need_clarification(self):
        r = self.route('выведи каждый ID на отдельные строки на новый лист и создай '
                       'для каждого ID отдельный лист')
        self.assertTrue(r['questions'])

    def test_second_action_is_preserved_and_targets_result(self):
        r = self.route(REQUEST + ' и удали дубли')
        self.assertEqual([op['type'] for op in r['operations']], ['extract_split_values_to_sheet', 'remove_duplicates'])
        self.assertEqual(r['operations'][1]['sheet'], r['operations'][0]['output_sheet'])

    def test_edited_destination_is_respected(self):
        result = self.route(REQUEST + '. Создать один новый лист «Мои ID».')
        self.assertEqual(result['operations'][0]['output_sheet'], 'Мои ID')

    def test_other_start_cell_not_silently_ignored(self):
        self.assertTrue(self.route(REQUEST + ', начиная с B5')['questions'])

    def test_name_collision_across_all_sheets(self):
        a = {'sheets': self.analysis['sheets'] + [{'name': 'Айди выпускников', 'headers': ['Прочее']}]}
        r = self.route(analysis=a, selected_sheet=SHEET)
        self.assertEqual(r['operations'][0]['output_sheet'], 'Айди выпускников_2')

    def test_truncated_sheet_name(self):
        self.assertEqual(resolve_sheet_name(SHEET + ')', [SHEET]), SHEET)
        self.assertEqual(resolve_sheet_name(' data ', ['Data']), 'Data')

    def test_exact_names_win(self):
        self.assertEqual(resolve_sheet_name(' Data ', ['Data', ' Data ']), ' Data ')
        self.assertEqual(resolve_sheet_name(' Data ', [' Data ']), ' Data ')

    def test_ambiguous_or_invented_sheet_rejected(self):
        for name in ['DATA', 'Missing']:
            with self.assertRaises(ValueError):
                resolve_sheet_name(name, ['Data', ' Data '])
        with self.assertRaises(ValueError):
            resolve_sheet_name(SHEET + 'xyz', [SHEET])

    def test_llm_name_bound_to_workbook(self):
        with patch('modules.excel_ai.ai_interpreter._interpret_task', return_value={
            'operations': [{'type': 'trim_text', 'sheet': SHEET + ')'}]}):
            self.assertEqual(interpret_task('x', self.analysis)['operations'][0]['sheet'], SHEET)

    def test_llm_invented_name_becomes_question(self):
        with patch('modules.excel_ai.ai_interpreter._interpret_task', return_value={
            'operations': [{'type': 'trim_text', 'sheet': 'Missing'}]}):
            r = interpret_task('x', self.analysis)
            self.assertTrue(r['questions'])
            self.assertFalse(r['operations'])

    def test_execution_preserves_strings_order_duplicates_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d)/'source.xlsx', Path(d)/'output.xlsx'
            wb = Workbook(); ws = wb.active; ws.title = SHEET
            ws.append(['ИИН', 'Айди выпускников'])
            ws.append(['000000000001', '{001, 42, 42; 99999999999999999999\n0}'])
            ws.append(['keep', '[7;8]']); ws.append(['keep', None])
            ws.append(['keep', '{=1+1, +text}'])
            ws['A2'].number_format = '@'
            wb.save(source); wb.close()
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            a = analyze_workbook(source)
            r = self.route(analysis=a)
            plan = plan_operations(source, output, r['operations'])
            self.assertEqual(plan['previews'][0]['output_rows'], 9)
            self.assertFalse(output.exists())
            execute_operations(plan, confirmed=True)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            out = load_workbook(output)
            self.assertEqual(out.sheetnames, [SHEET, 'Айди выпускников'])
            values = [row[0] for row in out['Айди выпускников'].iter_rows(min_row=2, values_only=True)]
            self.assertEqual(values, ['001', '42', '42', '99999999999999999999', '0', '7', '8', '=1+1', '+text'])
            self.assertEqual(out['Айди выпускников']['A9'].data_type, 's')
            self.assertEqual(out[SHEET]['A2'].value, '000000000001')
            out.close()

    def test_empty_and_formula_sources_rejected_during_planning(self):
        for value in [None, '{}', '=1+1']:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                wb = Workbook(); wb.active.title = SHEET
                wb.active.append(['ИИН', 'Айди выпускников']); wb.active.append(['x', value])
                p = Path(d)/'s.xlsx'; wb.save(p); wb.close()
                with self.assertRaises(ValueError):
                    plan_operations(p, Path(d)/'o.xlsx', self.route()['operations'])

    def test_direct_plan_repairs_closing_bracket(self):
        wb = Workbook(); wb.active.title = SHEET
        wb.active.append(['ID']); wb.active.append(['{1,2}'])
        ops = _validate_ops([{'type': 'extract_split_values_to_sheet', 'sheet': SHEET + ')', 'column': 'ID'}], wb)
        self.assertEqual(ops[0]['sheet'], SHEET)
        self.assertEqual(_validate_ops(ops, wb), ops)
        wb.close()

    def test_regular_group_split_remains_separate_sheets(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Факультет', 'Айди выпускников']}]}
        result = self.route('Раздели по факультету на отдельные листы', a)
        self.assertEqual(result['operations'][0]['type'], 'split_to_sheets')

    def test_generic_helper_covers_multiple_operations(self):
        steps = operation_steps([{'type': 'trim_text', 'sheet': 'S', 'columns': ['ФИО']},
                                 {'type': 'sort_rows', 'sheet': 'S', 'column': 'ФИО'}])
        self.assertEqual(len(steps), 2)
        self.assertIn('ФИО', steps[0])
        self.assertIn('Отсортировать', steps[1])


if __name__ == '__main__':
    unittest.main()
