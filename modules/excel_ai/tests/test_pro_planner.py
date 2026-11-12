import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook, load_workbook
from modules.excel_ai.analyzer import analyze_workbook
from modules.excel_ai.ai_interpreter import interpret_task
from modules.excel_ai.pro_planner import plan_request, segments, CATALOG
from modules.excel_ai.task_assistant import rewrite_task
from modules.excel_ai.operations import plan_operations, execute_operations, SUPPORTED_TYPES


class ProPlannerTests(unittest.TestCase):
    def run_book(self, headers, rows, task, sheet='Данные', expected_types=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        source, output = Path(tmp.name)/'input.xlsx', Path(tmp.name)/'output.xlsx'
        wb = Workbook(); wb.active.title = sheet
        wb.active.append(headers)
        for row in rows: wb.active.append(row)
        wb.save(source); wb.close()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        analysis = analyze_workbook(source)
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', side_effect=AssertionError('Must work locally')):
            result = interpret_task(task, analysis)
        self.assertFalse(result.get('questions'), result)
        if expected_types:
            self.assertEqual([op['type'] for op in result['operations']], expected_types)
        plan = plan_operations(source, output, result['operations'])
        self.assertFalse(output.exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
        execute_operations(plan, confirmed=True)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
        out = load_workbook(output); self.addCleanup(out.close)
        return out, plan, result

    def test_sales_clean_then_sum(self):
        out, plan, _ = self.run_book(['Регион', 'Выручка', 'Примечание'],
            [[' Юг ', 10, ' оставить '], ['Юг', 20, ' x '], ['Север', 5, ' y ']],
            'Убери пробелы в столбце Регион, затем посчитай сумму Выручка по Регион',
            expected_types=['trim_text', 'group_by_aggregate'])
        self.assertEqual(out['Данные']['C2'].value, ' оставить ')
        self.assertEqual(dict(out['Агрегация'].iter_rows(min_row=2, max_row=3, values_only=True)), {'Север': 5, 'Юг': 30})

    def test_hr_filter_then_sort_result(self):
        out, _, _ = self.run_book(['Сотрудник', 'Зарплата'], [['A', 300], ['B', 100], ['C', 200]],
            'Оставь строки где Зарплата > 100 на новый лист «Отбор», затем отсортируй результат по Зарплата по убыванию',
            expected_types=['filter_rows', 'sort_rows'])
        self.assertEqual(list(out['Отбор'].values), [('Сотрудник', 'Зарплата'), ('A', 300), ('C', 200)])

    def test_inventory_select_then_sort_rebinds_indices(self):
        out, plan, _ = self.run_book(['Код', 'Товар', 'Остаток'], [['x', 'A', 1], ['y', 'B', 5]],
            'Оставь столбцы Товар и Остаток, затем отсортируй по Остаток по убыванию',
            expected_types=['select_columns', 'sort_rows'])
        self.assertEqual(plan['operations'][1]['column'], 2)
        self.assertEqual(out['Данные']['A2'].value, 'B')

    def test_tags_extract_deduplicate_sort(self):
        out, _, r = self.run_book(['Теги', 'Описание'], [['{beta,alpha,beta}', 'x'], ['gamma;alpha', 'y']],
            'Извлеки Теги по строкам на новый лист «Список», затем удали дубли, затем отсортируй результат по Теги',
            expected_types=['extract_split_values_to_sheet', 'remove_duplicates', 'sort_rows'])
        self.assertEqual([x[0] for x in out['Список'].iter_rows(min_row=2, values_only=True)], ['alpha', 'beta', 'gamma'])
        self.assertEqual(r['operations'][1]['sheet'], 'Список')

    def test_custom_separator_and_offset(self):
        out, _, _ = self.run_book(['Артикулы'], [['001|002|003']],
            'Извлеки Артикулы по строкам на новый лист «Коды», разделитель «|», начиная с A5')
        self.assertEqual(out['Коды']['A4'].value, 'Артикулы')
        self.assertEqual(out['Коды']['A5'].value, '001')

    def test_contacts_replace_only_requested_column(self):
        out, _, _ = self.run_book(['Почта', 'Комментарий'], [['a@old.kz', 'old.kz']],
            'Замени «old.kz» на «new.kz» в столбце Почта')
        self.assertEqual(out['Данные']['A2'].value, 'a@new.kz')
        self.assertEqual(out['Данные']['B2'].value, 'old.kz')

    def test_fill_only_requested_column(self):
        out, _, _ = self.run_book(['Телефон', 'Адрес', 'Код'], [[None, None, '1']],
            'Заполни пустые ячейки в столбце Телефон значением «Не указан»')
        self.assertEqual(out['Данные']['A2'].value, 'Не указан')
        self.assertIsNone(out['Данные']['B2'].value)

    def test_copy_then_clean_only_copy(self):
        out, _, _ = self.run_book(['Товар'], [[' x ']],
            'Скопируй лист на новый лист «Рабочий», затем убери пробелы в столбце Товар')
        self.assertEqual(out['Данные']['A2'].value, ' x ')
        self.assertEqual(out['Рабочий']['A2'].value, 'x')

    def test_copy_fio_columns_with_single_quotes_and_inflected_verb(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        source, output = Path(tmp.name)/'input.xlsx', Path(tmp.name)/'output.xlsx'
        wb = Workbook()
        target = wb.active
        target.title = 'Sheet1'
        data = wb.create_sheet('Контингент')
        data.append(['ID', 'Фамилия', 'Имя', 'Отчество', 'Группа'])
        data.append([1, 'Иванов', 'Иван', 'Иванович', 'A'])
        wb.save(source); wb.close()
        analysis = analyze_workbook(source)
        task = "Переводите данные из столбцов 'Фамилия Имя Отчество' на лист 'Sheet1'"
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama',
                   side_effect=AssertionError('Must work locally')):
            result = interpret_task(task, analysis)
        self.assertFalse(result.get('questions'), result)
        self.assertEqual(result['operations'], [{
            'type': 'copy_columns_to_sheet',
            'sheet': 'Контингент',
            'columns': ['Фамилия', 'Имя', 'Отчество'],
            'output_sheet': 'Sheet1',
            'header_rows': 1,
        }])
        plan = plan_operations(source, output, result['operations'])
        execute_operations(plan, confirmed=True)
        out = load_workbook(output); self.addCleanup(out.close)
        self.assertEqual(list(out['Sheet1'].values), [
            ('Фамилия', 'Имя', 'Отчество'),
            ('Иванов', 'Иван', 'Иванович'),
        ])
        self.assertEqual(out['Контингент']['A2'].value, 1)

    def test_fio_alias_expands_to_three_columns(self):
        a = {'sheets': [
            {'name': 'Sheet1', 'headers': []},
            {'name': 'Люди', 'headers': ['ID', 'Фамилия', 'Имя', 'Отчество']},
        ]}
        result = plan_request('Скопируй ФИО на лист Sheet1', a)
        self.assertFalse(result.get('questions'), result)
        self.assertEqual(result['operations'][0]['columns'],
                         ['Фамилия', 'Имя', 'Отчество'])

    def test_nonempty_destination_is_not_overwritten(self):
        out, _, result = self.run_book(
            ['Фамилия', 'Имя', 'Отчество'],
            [['Иванов', 'Иван', 'Иванович']],
            'Скопируй ФИО на лист Sheet1',
            expected_types=['copy_columns_to_sheet'],
        )
        self.assertEqual(result['operations'][0]['output_sheet'], 'Sheet1')
        self.assertEqual(list(out['Sheet1'].values)[0],
                         ('Фамилия', 'Имя', 'Отчество'))

    def test_numbered_commands(self):
        out, _, _ = self.run_book(['Отдел', 'Оклад'], [[' IT ', 10], [' HR ', 20]],
            '1. Убери пробелы в столбце Отдел\n2. Отсортируй по Оклад по убыванию')
        self.assertEqual(out['Данные']['A2'].value, 'HR')

    def test_group_result_sort(self):
        out, _, _ = self.run_book(['Категория', 'Расход'], [['A', 10], ['B', 30], ['A', 5]],
            'Посчитай сумму Расход по Категория, затем отсортируй результат по Сумма по убыванию')
        self.assertEqual(out['Агрегация']['A2'].value, 'B')

    def test_natural_language_cross_table_is_one_pivot_operation(self):
        out, _, result = self.run_book(
            ['Специализация/Образовательная программа', 'Форма обучения'],
            [['Медицина', 'Очная'], ['Медицина', 'Заочная'],
             ['Медицина', 'Очная'], ['Стоматология', 'Очная']],
            'Построй перекрёстную таблицу: строки — '
            '«Специализация/Образовательная программа», столбцы — '
            '«Форма обучения», значения — количество записей.',
            sheet='Sheet0', expected_types=['pivot_count'])
        self.assertEqual(len(result['operations']), 1)
        ws = out['Перекрёстная таблица']
        self.assertEqual(list(ws.values), [
            ('Специализация/Образовательная программа / Форма обучения',
             'Очная', 'Заочная', 'Всего'),
            ('Медицина', 2, 1, 3),
            ('Стоматология', 1, 0, 1),
            ('Всего', 3, 1, 4),
        ])

    def test_unknown_second_step_never_returns_partial_operations(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        r = plan_request('Убери пробелы в Название, затем отправь файл бухгалтеру', a)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_duplicate_sheet_headers_require_selection(self):
        a = {'sheets': [{'name': s, 'headers': ['Сумма']} for s in ['Продажи', 'Закупки']]}
        r = plan_request('Отсортируй по Сумма', a)
        self.assertTrue(r['questions'])
        r = plan_request('Отсортируй по Сумма', a, selected_sheet='Закупки')
        self.assertEqual(r['operations'][0]['sheet'], 'Закупки')

    def test_quoted_headers_and_values_not_split(self):
        self.assertEqual(segments('Замени «A; затем B» на «C и удали D» в «Название»'),
                         ['Замени «A; затем B» на «C и удали D» в «Название»'])

    def test_catalog_covers_every_executor(self):
        self.assertEqual(set(CATALOG), SUPPORTED_TYPES)

    def test_helper_grounded_preview_on_arbitrary_workbook(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'w.xlsx'; w = Workbook(); w.active.title = 'S'
            w.active.append(['Метки']); w.active.append(['b,a,a']); w.save(p); w.close()
            with patch('modules.excel_ai.ai_interpreter._post_to_ollama', side_effect=AssertionError):
                r = rewrite_task('Извлеки Метки по строкам на новый лист «Метки», затем удали дубли',
                                 analyze_workbook(p), source_path=p)
            self.assertEqual(len(r['operations']), 2)
            self.assertTrue(r['preview'])
            self.assertEqual(list(Path(d).iterdir()), [p])

    def test_llm_semantic_request_is_schema_grounded(self):
        a = {'sheets': [{'name': 'Магазин', 'headers': ['Выручка', 'Регион']}]}
        reply = {'questions': [], 'intent': 'Выручка по регионам', 'steps': [{'clause_index': 1,
            'operations': [{'type': 'group_by_aggregate', 'sheet': 'Магазин', 'column': 'Регион',
                            'target_column': 'Выручка', 'function': 'sum'}]}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=reply) as model:
            r = rewrite_task('Сведи заработанное по территориям', a)
        self.assertFalse(r['questions']); model.assert_called_once()
        self.assertIn('Магазин', model.call_args[0][0])
        self.assertEqual(r['operations'][0]['target_column'], 'Выручка')

    def test_llm_missing_clause_rejected(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        reply = {'steps': [{'clause_index': 1, 'operations': [{'type': 'trim_text', 'sheet': 'S'}]}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=reply):
            r = plan_request('Убери пробелы в Название, затем сделай неизвестное', a, use_ai=True)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_llm_invented_column_rejected(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        reply = {'steps': [{'clause_index': 1, 'operations': [{'type': 'sort_rows', 'sheet': 'S', 'column': 'Возраст'}]}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=reply):
            r = plan_request('Расположи как надо', a, use_ai=True)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_llm_unrequested_deletion_rejected(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        reply = {'steps': [{'clause_index': 1, 'operations': [{'type': 'remove_duplicates', 'sheet': 'S'}]}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=reply):
            r = plan_request('Проанализируй повторы', a, use_ai=True)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_ollama_failure_is_explained(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', side_effect=RuntimeError('Ollama недоступна')):
            r = rewrite_task('Сделай по смыслу как я думаю', a)
        self.assertIn('Ollama недоступна', r['text']); self.assertFalse(r['operations'])

    def test_selected_source_does_not_override_created_result(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Метки', 'Комментарий']}]}
        r = plan_request('Извлеки Метки по строкам на новый лист «Список», затем удали дубли', a, selected_sheet='S')
        self.assertEqual(r['operations'][1]['sheet'], 'Список')

    def test_llm_cannot_override_negation(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        reply = {'steps': [{'clause_index': 1, 'operations': [{'type': 'remove_duplicates', 'sheet': 'S'}]}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=reply):
            r = plan_request('Не удаляй дубли, проанализируй их', a, use_ai=True)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_malformed_model_response_is_clarification(self):
        a = {'sheets': [{'name': 'S', 'headers': ['Название']}]}
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', return_value=['invalid']):
            r = plan_request('Сделай что-нибудь осмысленное', a, use_ai=True)
        self.assertTrue(r['questions']); self.assertFalse(r['operations'])

    def test_dependent_invalid_column_blocks_entire_plan_without_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'s.xlsx'; w = Workbook(); w.active.title = 'S'
            w.active.append(['A', 'B']); w.active.append([1, 2]); w.save(p); w.close()
            with self.assertRaises(ValueError):
                plan_operations(p, Path(d)/'o.xlsx', [
                    {'type': 'select_columns', 'sheet': 'S', 'columns': ['A']},
                    {'type': 'sort_rows', 'sheet': 'S', 'column': 'B'}])
            self.assertEqual(list(Path(d).iterdir()), [p])


if __name__ == '__main__': unittest.main()
