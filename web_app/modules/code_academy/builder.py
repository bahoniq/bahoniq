"""Guided, isolated project builder for Code Academy."""
from pathlib import Path
import ast
import json
import re

TEMPLATES = {
 'main.py': '''"""Единственная точка запуска учебного приложения."""\nfrom app.application import Application\n\n\ndef main():\n    Application().run()\n\n\nif __name__ == "__main__":\n    main()\n''',
 'app/__init__.py': '',
 'app/application.py': '''"""Композиционный корень: здесь собираются слои приложения."""\nfrom api.task_api import TaskAPI\nfrom data.task_repository import SQLiteTaskRepository\nfrom services.task_service import TaskService\nfrom settings import Settings\nfrom ui.main_window import MainWindow\n\n\n+class Application:\n    def __init__(self, settings=None):\n        self.settings = settings or Settings()\n        repository = SQLiteTaskRepository(self.settings.database_path)\n        service = TaskService(repository)\n        self.api = TaskAPI(service)\n\n    def run(self):\n        MainWindow(self.api, self.settings).run()\n'''.replace('\n+','\n'),
 'api/__init__.py': '',
 'api/task_api.py': '''"""Стабильный интерфейс между UI и бизнес-логикой."""\n\n\nclass TaskAPI:\n    def __init__(self, service):\n        self.service = service\n\n    def list_tasks(self):\n        return [task.to_dict() for task in self.service.list_tasks()]\n\n    def create_task(self, title, priority=1):\n        return self.service.create_task(title, priority).to_dict()\n\n    def complete_task(self, task_id):\n        return self.service.complete_task(task_id).to_dict()\n''',
 'models/__init__.py': '',
 'models/task.py': '''"""Модель предметной области без Tkinter и SQL."""\nfrom dataclasses import asdict, dataclass\n\n\n@dataclass\nclass Task:\n    id: int | None\n    title: str\n    priority: int = 1\n    done: bool = False\n\n    def to_dict(self):\n        return asdict(self)\n''',
 'services/__init__.py': '',
 'services/task_service.py': '''"""Бизнес-правила приложения."""\nfrom models.task import Task\n\n\nclass TaskService:\n    def __init__(self, repository):\n        self.repository = repository\n\n    def list_tasks(self):\n        return self.repository.list_all()\n\n    def create_task(self, title, priority=1):\n        title = title.strip()\n        if not title:\n            raise ValueError("Название задачи не может быть пустым")\n        if priority not in range(1, 6):\n            raise ValueError("Приоритет должен быть от 1 до 5")\n        return self.repository.add(Task(None, title, priority))\n\n    def complete_task(self, task_id):\n        task = self.repository.get(task_id)\n        if task is None:\n            raise LookupError("Задача не найдена")\n        task.done = True\n        return self.repository.update(task)\n''',
 'data/__init__.py': '',
 'data/task_repository.py': '''"""SQLite-реализация хранения задач."""\nimport sqlite3\nfrom models.task import Task\n\n\nclass SQLiteTaskRepository:\n    def __init__(self, path):\n        self.path = path\n        self._create_schema()\n\n    def _connect(self):\n        return sqlite3.connect(self.path)\n\n    def _create_schema(self):\n        with self._connect() as db:\n            db.execute("""CREATE TABLE IF NOT EXISTS tasks (\n                id INTEGER PRIMARY KEY, title TEXT NOT NULL,\n                priority INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0\n            )""")\n\n    def list_all(self):\n        with self._connect() as db:\n            rows = db.execute("SELECT id,title,priority,done FROM tasks ORDER BY id").fetchall()\n        return [Task(row[0], row[1], row[2], bool(row[3])) for row in rows]\n\n    def get(self, task_id):\n        with self._connect() as db:\n            row = db.execute("SELECT id,title,priority,done FROM tasks WHERE id=?", (task_id,)).fetchone()\n        return Task(row[0], row[1], row[2], bool(row[3])) if row else None\n\n    def add(self, task):\n        with self._connect() as db:\n            cursor = db.execute("INSERT INTO tasks(title,priority,done) VALUES (?,?,?)",\n                                (task.title, task.priority, int(task.done)))\n            task.id = cursor.lastrowid\n        return task\n\n    def update(self, task):\n        with self._connect() as db:\n            db.execute("UPDATE tasks SET title=?,priority=?,done=? WHERE id=?",\n                       (task.title, task.priority, int(task.done), task.id))\n        return task\n''',
 'ui/__init__.py': '',
 'ui/main_window.py': '''"""Tkinter-интерфейс: отображает данные и вызывает API."""\nimport tkinter as tk\nfrom tkinter import messagebox\n\n\nclass MainWindow:\n    def __init__(self, api, settings):\n        self.api = api\n        self.settings = settings\n        self.root = tk.Tk()\n        self.root.title(settings.title)\n        self.root.geometry(f"{settings.width}x{settings.height}")\n        self.entry = tk.Entry(self.root, width=42)\n        self.entry.pack(pady=16)\n        tk.Button(self.root, text="Добавить", bg=settings.accent, fg="white",\n                  command=self.add_task).pack()\n        self.listbox = tk.Listbox(self.root, width=70, height=15)\n        self.listbox.pack(padx=20, pady=16, fill="both", expand=True)\n        self.refresh()\n\n    def refresh(self):\n        self.listbox.delete(0, "end")\n        for task in self.api.list_tasks():\n            mark = "✓" if task["done"] else "•"\n            self.listbox.insert("end", f'{mark} {task["title"]} · P{task["priority"]}')\n\n    def add_task(self):\n        try:\n            self.api.create_task(self.entry.get())\n            self.entry.delete(0, "end")\n            self.refresh()\n        except ValueError as exc:\n            messagebox.showerror("Проверка данных", str(exc))\n\n    def run(self):\n        self.root.mainloop()\n''',
 'settings.py': '''"""Типизированные настройки приложения."""\nfrom dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass Settings:\n    title: str = "Task Academy"\n    width: int = 760\n    height: int = 520\n    accent: str = "#009246"\n    database_path: str = "tasks.db"\n''',
 'tests/__init__.py': '',
 'tests/test_service.py': '''"""Тесты бизнес-логики без запуска интерфейса."""\nimport unittest\nfrom models.task import Task\nfrom services.task_service import TaskService\n\n\nclass MemoryRepository:\n    def __init__(self): self.items = []\n    def list_all(self): return list(self.items)\n    def add(self, task):\n        task.id = len(self.items) + 1; self.items.append(task); return task\n    def get(self, task_id): return next((x for x in self.items if x.id == task_id), None)\n    def update(self, task): return task\n\n\nclass ServiceTests(unittest.TestCase):\n    def setUp(self): self.service = TaskService(MemoryRepository())\n    def test_create(self): self.assertEqual(self.service.create_task("Python").title, "Python")\n    def test_empty_title(self):\n        with self.assertRaises(ValueError): self.service.create_task("   ")\n    def test_complete(self):\n        task = self.service.create_task("SQL")\n        self.assertTrue(self.service.complete_task(task.id).done)\n\n\nif __name__ == "__main__": unittest.main()\n''',
 'README.md': '''# Task Academy\n\nУчебное слоистое приложение: UI → API → Service → Repository → SQLite.\n\nЗапуск: `python main.py`\nТесты: `python -m unittest discover -s tests -v`\n''',
}
EXPLAIN = {
 'main.py': 'Точка входа: импортирует start() и запускает программу только при прямом запуске файла.',
 'app/application.py': 'Логика запуска: связывает точку входа с пользовательским интерфейсом.',
 'ui/main_window.py': 'Frontend: создаёт окно Tkinter, заголовок, текст и кнопку.',
 'config.py': 'Конфигурация: изменяй TITLE, WIDTH, HEIGHT и ACCENT, чтобы управлять окном.',
 'data/.gitkeep': 'Папка data предназначена для учебных данных и будущей базы SQLite.',
}

def line_explanation(filename, line):
    text = line.strip()
    if not text: return 'Пустая строка разделяет смысловые блоки кода.'
    if text.startswith('#') or text.startswith('"""'): return 'Комментарий или документация: объясняет назначение кода, не выполняя действие.'
    if text.startswith('import ') or text.startswith('from '): return 'Импорт: подключает функции, классы или настройки из другого файла.'
    if text.startswith('def '): return 'Объявление функции: инструкции внутри неё выполняются при вызове.'
    if text.startswith('if __name__'): return 'Проверка точки входа: код запускается при выполнении этого файла напрямую.'
    if 'geometry(' in text: return 'Размер окна: ширина × высота берутся из объекта Settings.'
    if text.startswith('class '): return 'Класс объединяет состояние и поведение одного слоя приложения.'
    if 'self.api.' in text: return 'UI вызывает публичный API и не обращается к базе данных напрямую.'
    if 'db.execute(' in text: return 'Параметризованный SQL выполняется только в слое repository.'
    if '.title(' in text: return 'Заголовок окна, который пользователь видит в верхней части.'
    if 'tk.Label(' in text: return 'Текстовый элемент интерфейса Tkinter.'
    if 'tk.Button(' in text: return 'Кнопка интерфейса; параметры text, bg, fg отвечают за подпись и цвета.'
    if '.pack(' in text: return 'Размещает элемент внутри окна; pady добавляет вертикальные отступы.'
    if '.mainloop(' in text: return 'Цикл обработки событий: поддерживает окно открытым.'
    if '=' in text: return 'Присваивание: значение справа сохраняется в переменную слева.'
    return 'Эта строка участвует в работе модуля. Спроси ИИ-тренера о её назначении.'

class GuidedProject:
    def __init__(self): self.files = dict(TEMPLATES)
    def update(self, name, content):
        if name not in self.files: raise ValueError('Файл не входит в учебный проект')
        if len(content)>30000: raise ValueError('Слишком большой учебный файл')
        if name.endswith('.py'): ast.parse(content)
        self.files[name] = content
    def export(self, folder):
        root=Path(folder).expanduser().resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError('Для безопасности выбери новую или пустую учебную папку.')
        root.mkdir(parents=True, exist_ok=True)
        for name, content in self.files.items():
            target=(root/name).resolve()
            if not target.is_relative_to(root): raise ValueError('Недопустимый путь')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content, encoding='utf-8')
        return root
