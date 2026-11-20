"""Explain the actual proposed operations, without a second model rewriting them."""
import json


def improve_task_text(task, analysis):
    """Использует BahonIQ Облачный ИИ через ai_service."""
    if not isinstance(task, str) or not task.strip():
        raise ValueError('Сначала напиши задачу своими словами.')
    from .ai_interpreter import (
        _post_to_cloud_ai, _extract_sheets, _extract_headers, _get_sheet_name,
    )
    schema = [
        {'sheet': _get_sheet_name(item), 'headers': _extract_headers(item)}
        for item in _extract_sheets(analysis)
    ]
    if not schema:
        raise ValueError('Не удалось определить листы и столбцы Excel-файла.')
    prompt = (
        'Ты — ведущий аналитик и редактор заданий для Excel (система BahonIQ AI). Перепиши обычный пользовательский текст '
        'в ясную, строгую, профессиональную команду для обработки таблицы Excel, не добавляя действий, которых пользователь не просил. '
        'Используй только реальные названия листов и столбцов из схемы. '
        'Не составляй план операций, не пиши код и не утверждай, что файл изменён. '
        'Если данных недостаточно, задай один конкретный вопрос. '
        'Верни только JSON: {"improved_task":"...","explanation":"...","question":""}.\n'
        'Схема Excel: ' + json.dumps(schema, ensure_ascii=False) + '\n'
        'Текст пользователя: ' + task.strip()
    )

    reply = _post_to_cloud_ai(prompt)

    if not isinstance(reply, dict):
        raise ValueError('Не удалось разобрать ответ модели.')
    improved = str(reply.get('improved_task', '')).strip()
    explanation = str(reply.get('explanation', '')).strip()
    question = str(reply.get('question', '')).strip()
    if question and not improved:
        return {'original_task': task.strip(), 'improved_task': '',
                'explanation': explanation, 'question': question}
    if not improved:
        raise ValueError('Модель не вернула улучшенную формулировку.')
    return {'original_task': task.strip(), 'improved_task': improved,
            'explanation': explanation, 'question': question}


LABELS = {
    'copy_sheet': 'Создать копию листа',
    'filter_rows': 'Отобрать строки по условию на новый лист',
    'remove_empty_rows': 'Удалить полностью пустые строки',
    'remove_duplicates': 'Удалить повторные строки по выбранным столбцам',
    'fill_empty': 'Заполнить пустые ячейки',
    'trim_text': 'Убрать лишние пробелы в выбранных столбцах',
    'replace_values': 'Заменить указанные значения',
    'highlight_empty': 'Выделить пустые ячейки',
    'find_duplicate_rows': 'Найти повторяющиеся строки',
    'find_repeated_values': 'Найти повторяющиеся значения',
    'find_blank_cells': 'Найти пустые ячейки и соответствующие строки',
    'sort_rows': 'Отсортировать строки',
    'reorder_columns': 'Переставить столбцы в указанном порядке',
    'select_columns': 'Оставить только выбранные столбцы',
    'copy_columns_to_sheet': 'Скопировать выбранные столбцы на другой лист',
    'split_by_column': 'Создать отдельные файлы по значениям столбца',
    'split_to_sheets': 'Создать отдельные листы по значениям столбца',
    'merge_sheets': 'Объединить указанные листы',
    'summary_count': 'Посчитать записи по значениям столбца',
    'validate_values': 'Проверить значения по указанному правилу',
    'compare_columns': 'Сопоставить значения двух столбцов',
    'student_data_audit': 'Выполнить комплексную проверку данных',
    'group_by_aggregate': 'Сгруппировать данные и рассчитать итог',
    'pivot_count': 'Построить перекрёстную таблицу с количеством записей',
    'apply_formula': 'Записать формулу в выбранный столбец',
    'smart_summary': 'Создать аналитическую сводку',
    'distinct_count': 'Посчитать уникальные значения',
    'split_cell_values_to_rows': 'Развернуть значения ячеек в строки исходного листа',
}
PARAMETERS = {
    'column': 'столбец', 'columns': 'столбцы', 'sheets': 'листы',
    'output_sheet': 'новый лист', 'value': 'значение', 'find': 'найти',
    'replace': 'заменить на', 'old': 'найти', 'new': 'заменить на',
    'ascending': 'по возрастанию', 'descending': 'по убыванию',
    'target_column': 'столбец расчёта', 'function': 'расчёт',
    'formula': 'формула', 'all_columns': 'все столбцы',
    'other_column': 'второй столбец', 'output_dir': 'папка результатов',
    'id_column': 'столбец идентификаторов', 'rule': 'правило',
    'include_charts': 'диаграммы', 'header_rows': 'строк заголовка',
    'operator': 'условие', 'start_row': 'начальная строка', 'delimiter': 'разделитель',
}


def operation_steps(operations):
    steps = []
    for op in operations:
        kind, sheet = op['type'], op.get('sheet', '')
        if kind == 'extract_split_values_to_sheet':
            column, output = op['column'], op.get('output_sheet', 'Результат')
            sep = f'разделитель «{op["delimiter"]}»' if op.get('delimiter') else 'запятые, точки с запятой и переносы строк'
            start = op.get('start_row', 2)
            steps.append(f'Извлечь значения из столбца «{column}» на листе «{sheet}» '
                         f'на один новый лист «{output}», каждое значение в отдельную строку, начиная с A{start}, '
                         f'разделение: {sep}, убрать внешние скобки и пробелы по краям, '
                         f'заголовок «{op.get("output_header", column)}» в A{start-1}, сохранить порядок, повторы и ведущие нули.')
        elif kind == 'copy_columns_to_sheet':
            cols = ', '.join(f'«{c}»' for c in op.get('columns', []))
            steps.append(
                f'Скопировать столбцы {cols} с листа «{sheet}» на лист '
                f'«{op.get("output_sheet", "Выбранные столбцы")}», сохранив порядок строк, '
                'значения, формулы и оформление; исходный лист не изменять.'
            )
        elif kind == 'sort_rows':
            steps.append(f'Отсортировать строки на листе «{sheet}» по столбцу «{op["column"]}» '
                         + ('по убыванию.' if op.get('descending') else 'по возрастанию.'))
        elif kind in {'trim_text', 'fill_empty', 'highlight_empty', 'remove_duplicates', 'select_columns', 'reorder_columns'}:
            cols = op.get('columns') or ([op['column']] if op.get('column') else [])
            scope = ', '.join(f'«{c}»' for c in cols) if cols else 'все столбцы'
            phrases = {'trim_text': f'Убрать пробелы по краям значений в столбцах {scope}',
                       'fill_empty': f'Заполнить пустые ячейки в столбцах {scope} значением «{op.get("value", "")}»',
                       'highlight_empty': f'Выделить пустые ячейки в столбцах {scope}',
                       'remove_duplicates': f'Удалить дубли строк, сравнивая {scope}',
                       'select_columns': f'Оставить столбцы {scope}',
                       'reorder_columns': f'Переставить столбцы в порядке {scope}'}
            steps.append(phrases[kind] + f' на листе «{sheet}».')
        elif kind == 'replace_values':
            cols = op.get('columns') or ([op['column']] if op.get('column') else ['все'])
            steps.append(f'Заменить «{op["old"]}» на «{op["new"]} в столбцах '
                         + ', '.join(f'«{c}»' for c in cols) + f' на листе «{sheet}».')
        elif kind == 'filter_rows':
            operators = {'eq': 'равно', 'ne': 'не равно', 'gt': 'больше', 'ge': 'не меньше',
                         'lt': 'меньше', 'le': 'не больше', 'contains': 'содержит',
                         'blank': 'пусто', 'not_blank': 'не пусто'}
            steps.append(f'Отобрать строки листа «{sheet}», где «{op["column"]}» '
                         f'{operators[op["operator"]]} {op.get("value", "")}, '
                         f'на новый лист «{op["output_sheet"]}».')
        elif kind == 'group_by_aggregate':
            fn = {'sum': 'сумму', 'avg': 'среднее', 'min': 'минимум', 'max': 'максимум', 'count': 'количество строк'}
            groups = op.get('columns') or [op.get('column')]
            target = f' столбца «{op["target_column"]}»' if op.get('target_column') else ''
            steps.append(f'Посчитать {fn[op.get("function", "sum")]}{target} по '
                         + ', '.join(f'«{c}»' for c in groups) + f' на листе «{sheet}», '
                         f'результат — на лист «{op.get("output_sheet", "Агрегация")}».')
        elif kind == 'copy_sheet':
            steps.append(f'Скопировать лист «{sheet}» на новый лист «{op["output_sheet"]}».')
        else:
            params = '; '.join(f'{PARAMETERS.get(k, k)}: '
                              f'{json.dumps(v, ensure_ascii=False)}'
                              for k, v in op.items() if k not in {'type', 'sheet'})
            steps.append(f'{LABELS.get(kind, kind)}' +
                         (f' на листе «{sheet}»' if sheet else '') +
                         (f'. Параметры: {params}' if params else '') + '.')
    return steps


def rewrite_task(task, analysis, selected_sheet=None, source_path=None):
    from .pro_planner import plan_request
    result = plan_request(task, analysis, selected_sheet, use_ai=True)
    if result.get('questions'):
        return dict(result, text='\n'.join(result['questions']))
    if source_path:
        import tempfile
        from pathlib import Path
        from .operations import plan_operations
        with tempfile.TemporaryDirectory() as directory:
            suffix = '.xlsm' if str(source_path).lower().endswith('.xlsm') else '.xlsx'
            plan = plan_operations(source_path, Path(directory) / ('preview' + suffix), result['operations'])
        result['operations'] = plan['display_operations']
        result['preview'] = plan['previews']
    steps = operation_steps(result.get('operations', []))
    return dict(result, text='\n'.join(f'{i}. {s}' for i, s in enumerate(steps, 1)))
