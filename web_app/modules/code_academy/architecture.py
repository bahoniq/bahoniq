"""Read-only browsing of the installed Work Center, with bounded file access."""
import ast
from pathlib import Path

ALLOWED_EXT={'.py','.json','.md','.txt'}
MAX_BYTES=500_000

def project_root():
    return Path(__file__).resolve().parents[2]

def list_project_files(root=None, limit=1000):
    root=Path(root or project_root()).resolve()
    found=[]
    for path in root.rglob('*'):
        if len(found)>=limit: break
        if any(p in {'__pycache__','.git','.venv','venv','node_modules','training','BahonIQ_Results'} for p in path.relative_to(root).parts): continue
        if path.is_file() and path.suffix.lower() in ALLOWED_EXT and not path.is_symlink():
            found.append(path.relative_to(root).as_posix())
    return sorted(found)

def read_project_file(relative,root=None):
    root=Path(root or project_root()).resolve()
    target=(root/relative).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in ALLOWED_EXT or target.is_symlink(): raise ValueError('Файл недоступен для просмотра')
    if not target.is_file() or target.stat().st_size>MAX_BYTES: raise ValueError('Файл слишком большой или отсутствует')
    return target.read_text(encoding='utf-8',errors='replace')

def describe_code(code):
    try: tree=ast.parse(code)
    except SyntaxError as exc: return f'Синтаксическая ошибка: строка {exc.lineno}: {exc.msg}'
    functions=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    classes=[n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]
    imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    return 'Классы: '+(', '.join(classes[:20]) or 'нет')+'\nФункции: '+(', '.join(functions[:30]) or 'нет')+'\nИмпорты из: '+(', '.join(imports[:15]) or 'нет')
