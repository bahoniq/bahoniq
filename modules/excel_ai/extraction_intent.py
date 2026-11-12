"""Shared, deterministic recognition of cell lists extracted to a new sheet."""
import re
from .sheet_names import resolve_sheet_name


def norm(value):
    return re.sub(r"\s+", " ", str(value).casefold().replace("ё", "е")).strip()


def is_extraction_request(text):
    text = norm(text)
    destination = re.search(r"\b(?:нов\w*|отдельн\w*|друг\w*)\s+лист\w*", text)
    rows = re.search(r"\b(?:(?:нов\w*|отдельн\w*|кажд\w*)\s+строк\w*|"
                     r"по\s+одному\s+(?:в|на)\s+строк\w*|по\s+строк\w*|вертикаль\w*)", text)
    values = re.search(r"\b(?:id|айди|ид|идентификатор\w*|значени\w*|элемент\w*|"
                       r"номер\w*|ячейк\w*|столб\w*|колонк\w*)\b", text)
    extract = re.search(r'\b(?:извлек\w*|вывед\w*|вывест\w*|перенес\w*|выгруз\w*|развер\w*)\b', text)
    return bool(destination and rows and (values or extract))


def _id_kind(text):
    return 'generic' if re.search(r'\b(?:id|айди|ид|идентификатор\w*)\b', norm(text)) else None


def resolve_extraction(task, schema, selected_sheet=None):
    """Return a resolved operation or a clarification; both are non-mutating."""
    text = norm(task)
    all_sheet_names = [s['sheet'] for s in schema]
    addresses = re.findall(r'\b([A-ZА-Я]\d+)\b', task, re.I)
    if any(a.upper() not in {'A1', 'A2', 'А1', 'А2'} for a in addresses):
        return {'operations': [], 'questions': ['Извлечение создаёт заголовок в A1 и значения '
                'с A2. Уточни задачу без других адресов ячеек.'], 'mode': 'questions',
                'deterministic_route': True}
    if re.search(r'для\s+кажд\w*.*(?:отдельн\w*|свой)\s+лист|'
                 r'кажд\w*\s+(?:id|айди|значени\w*).{0,25}(?:свой|отдельн\w*)\s+лист', text):
        return {'operations': [], 'questions': ['Нужен один новый лист со всеми значениями '
                'по строкам или отдельный лист для каждого значения?'],
                'mode': 'questions', 'deterministic_route': True}
    if re.search(r'\b(?:отсортир\w*|сортиров\w*|уникальн\w*|без\s+дубл\w*|'
                 r'удал\w*\s+(?:дубл\w*|повтор\w*))', text):
        return {'operations': [], 'questions': ['Извлечение сохраняет порядок и повторы. '
                'Подготовь извлечение отдельно, затем задай сортировку или удаление дублей.'],
                'mode': 'questions', 'deterministic_route': True}
    if selected_sheet:
        name = resolve_sheet_name(selected_sheet, [s['sheet'] for s in schema])
        schema = [s for s in schema if s['sheet'] == name]
    else:
        references = re.findall(r'\b(?:на|из|в|с)\s+лист(?:е|а)?\s+[«"]([^»"]+)[»"]', task, re.I)
        if references:
            try:
                names = {resolve_sheet_name(n, all_sheet_names) for n in references}
            except ValueError as exc:
                return {'operations': [], 'questions': [str(exc)], 'mode': 'questions',
                        'deterministic_route': True}
            schema = [s for s in schema if s['sheet'] in names]
        else:
            named = [s for s in schema if re.search(
                r'\b(?:на|из|в|с)\s+лист(?:е|а)?\s+' + re.escape(norm(s['sheet'])) +
                r'(?=$|[\s.,;])', text)]
            if named:
                schema = named
    quoted_columns = re.findall(r'\b(?:столб\w*|колонк\w*)\s+[«"]([^»"]+)[»"]', task, re.I)
    header_text = norm(' '.join(quoted_columns)) if quoted_columns else text
    candidates = []
    for s in schema:
        for header in s['headers']:
            if re.search(r"(?<!\w)" + re.escape(norm(header)) + r"(?!\w)", header_text):
                candidates.append((s['sheet'], header))
    # A full header supersedes a shorter header contained within it.
    candidates = [c for c in candidates if not any(
        c[0] == d[0] and c[1] != d[1] and norm(c[1]) in norm(d[1])
        for d in candidates)]
    if not candidates and re.search(r"\b(?:id|айди|ид|идентификатор\w*)\b", text):
        candidates = [(s['sheet'], h) for s in schema for h in s['headers'] if _id_kind(h)]
    if len(candidates) != 1:
        options = candidates or [(s['sheet'], h) for s in schema for h in s['headers']]
        listing = "; ".join(f"«{s}» → «{h}»" for s, h in options[:20])
        return {'operations': [], 'questions': [
            'Укажи один исходный лист и столбец для извлечения. ' + listing],
            'explanation': 'Источник значений требует уточнения.', 'mode': 'questions',
            'deterministic_route': True}
    sheet, column = candidates[0]
    explicit = re.search(r'(?:созда\w*\s+(?:(?:один|новый|отдельный)\s+)*лист|'
                         r'(?:нов\w*|отдельн\w*)\s+лист\w*)\s+[«"]([^»"]+)[»"]', task, re.I)
    output = explicit.group(1) if explicit else column
    # Same naming algorithm as the executor, including collision suffixes.
    from .operations import _safe_sheet_name
    output = _safe_sheet_name(output, all_sheet_names)
    op = {'type': 'extract_split_values_to_sheet', 'sheet': sheet,
          'column': column, 'output_sheet': output, 'header_rows': 1}
    return {'operations': [op], 'questions': [], 'mode': 'operations',
            'explanation': f'Из «{column}» на листе «{sheet}»: каждое значение '
                           f'в отдельную строку одного нового листа «{output}».',
            'deterministic_route': True}
