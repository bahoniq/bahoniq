"""AST-based explanations and import relationships; no code execution."""
import ast
from pathlib import Path


def explain_line(source, line_number):
    lines = source.splitlines()
    if not 1 <= line_number <= len(lines):
        return 'Выбери строку кода.'
    raw = lines[line_number - 1]
    if not raw.strip():
        return 'Пустая строка отделяет логические части программы и облегчает чтение.'
    if raw.lstrip().startswith('#'):
        return 'Комментарий: Python не выполняет этот текст. Он поясняет назначение кода.'
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 'В этом файле есть синтаксическая ошибка; проверь отступы и скобки.'
    matches = [n for n in ast.walk(tree) if hasattr(n, 'lineno') and n.lineno <= line_number <= getattr(n, 'end_lineno', n.lineno)]
    matches.sort(key=lambda n: (getattr(n, 'end_lineno', n.lineno) - n.lineno, -n.lineno))
    node = matches[0] if matches else None
    if isinstance(node, ast.ImportFrom):
        return f'Импорт из модуля {node.module or "текущего пакета"}. Программа получает имена, объявленные в другом файле.'
    if isinstance(node, ast.Import):
        return 'Импорт: подключает модуль, функции и классы которого используются далее.'
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line_number:
        return f'def объявляет {"асинхронную " if isinstance(node, ast.AsyncFunctionDef) else ""}функцию или метод {node.name}(). Тело находится в строках с отступом ниже. Само объявление не запускает тело.'
    if isinstance(node, ast.ClassDef) and node.lineno == line_number:
        return f'class объявляет класс {node.name} — шаблон для создания объектов с атрибутами и методами.'
    if isinstance(node, ast.Return):
        return 'return завершает выполнение функции и возвращает значение вызывающему коду.'
    if isinstance(node, ast.If):
        return 'if проверяет условие. Вложенные строки выполняются, когда условие истинно.'
    if isinstance(node, (ast.For, ast.While)):
        return 'Цикл повторяет вложенный блок: for перебирает элементы, while повторяет действия, пока условие истинно.'
    if isinstance(node, ast.Try):
        return 'try начинает блок обработки ошибок. except позволяет перехватить предусмотренные исключения.'
    if isinstance(node, ast.Call):
        return 'Вызов функции или метода: скобки () означают выполнение с переданными аргументами.'
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return 'Присваивание: значение выражения сохраняется в переменной или атрибуте объекта.'
    return 'Строка входит в логический блок Python. Выдели соседние строки или отправь фрагмент ИИ для контекстного объяснения.'


def explain_block(source, line_number):
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f'Ошибка синтаксиса в строке {exc.lineno}: {exc.msg}', ''
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For, ast.While, ast.Try)) and n.lineno <= line_number <= n.end_lineno]
    if not nodes:
        lines = source.splitlines()
        return explain_line(source, line_number), lines[line_number - 1] if 1 <= line_number <= len(lines) else ''
    node = min(nodes, key=lambda n: n.end_lineno - n.lineno)
    label = f'{type(node).__name__}: строки {node.lineno}–{node.end_lineno}'
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        label += f', имя {node.name}'
    return label + '\n' + explain_line(source, node.lineno), '\n'.join(source.splitlines()[node.lineno - 1:node.end_lineno])


def import_map(source, filename):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend((filename, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append((filename, '.' * node.level + (node.module or '')))
    return sorted(set(result))


def safe_copy_target(workspace, relative):
    root = Path(workspace).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix != '.py':
        raise ValueError('Недопустимый путь учебной копии')
    return candidate
