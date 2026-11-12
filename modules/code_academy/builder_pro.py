"""Project validation and safe editing for the integrated AI App Builder."""
import ast
import json
import re
from pathlib import Path, PurePosixPath
from .studio_core import check_project

MAX_FILE = 100_000
MAX_FILES = 120


def validate_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Укажи относительный путь, например services/tasks.py')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('.', '..') for p in name.split('/')) or name.startswith('/'):
        raise ValueError('Путь должен оставаться внутри учебного проекта')
    if not re.fullmatch(r'[\w./ -]+', name, flags=re.UNICODE):
        raise ValueError('Недопустимые символы имени файла')
    if path.suffix not in ('.py', '.json', '.txt', '.md', '.sql') and path.name != '.gitkeep':
        raise ValueError('Допустимы только .py, .json, .txt, .md и .sql')
    return str(path)


def add_file(project, name, content=''):
    name = validate_name(name)
    if name in project.files: raise ValueError('Файл уже существует')
    if len(project.files) >= MAX_FILES: raise ValueError('Превышен лимит файлов')
    if len(content) > MAX_FILE: raise ValueError('Файл слишком большой')
    if name.endswith('.py'): ast.parse(content, filename=name)
    project.files[name] = content
    return name


def validate_project(files):
    issues = list(check_project(files))
    paths = {str(PurePosixPath(name).with_suffix('')).replace('/', '.') for name in files if name.endswith('.py')}
    packages = {str(PurePosixPath(name).parent).replace('/', '.') for name in files if name.endswith('/__init__.py')}
    for name, source in files.items():
        if not name.endswith('.py'): continue
        try: tree = ast.parse(source, filename=name)
        except SyntaxError: continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                module = node.module
                root = module.split('.')[0]
                if root in {'app', 'ui', 'services', 'models', 'data', 'api', 'utils', 'config'} and module not in paths and module not in packages:
                    issues.append(f'{name}:{node.lineno}: импорт {module} не найден в проекте')
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module.split('.')[0] in {'app','ui','services','models','data','api','utils','config'} and module not in paths and module not in packages:
                        issues.append(f'{name}:{node.lineno}: импорт {module} не найден в проекте')
    return issues


def save_draft(files, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'format': 1, 'files': files}
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def load_draft(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if raw.get('format') != 1 or not isinstance(raw.get('files'), dict): raise ValueError('Неизвестный формат проекта')
    files = raw['files']
    if len(files) > MAX_FILES: raise ValueError('Слишком много файлов')
    clean = {}
    for name, source in files.items():
        validate_name(name)
        if not isinstance(source, str) or len(source) > MAX_FILE: raise ValueError('Некорректный код файла')
        if name.endswith('.py'): ast.parse(source, filename=name)
        clean[name] = source
    return clean
