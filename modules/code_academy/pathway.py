"""Single progressive route for each language; a Task Manager grows lesson by lesson."""
from dataclasses import dataclass
import ast
import sqlite3
import time
from .pro_engine import PythonRunner, SQLExpectation, SQLRunner, TestCase
from .pro_lessons import acceptance_for

@dataclass(frozen=True)
class Step:
    slug: str
    title: str
    level: int
    theory: str
    code: str
    walkthrough: str
    challenge: str
    hint: str
    tokens: tuple
    mode: str = 'syntax'

P = [
Step('p01','01 · Переменные и вывод',1,'Программа выполняет инструкции сверху вниз. Переменная хранит ссылку на значение, print() показывает его в консоли. Начинаем с названия первой задачи.', 'app_name = "BahonIQ Tasks"\ntask = "Изучить Python"\npriority = 2\nprint(app_name)\nprint("Задача:", task)\nprint("Приоритет:", priority)', '1: имя приложения. 2: текст задачи. 3: целое число. 4–6: вывод значений. = присваивает, а не сравнивает.', 'Измени название приложения, задачу и приоритет. Добавь вывод ещё одной строки.', 'Измени значения справа от =, а затем добавь print().', ('print','task','priority'), 'basic'),
Step('p02','02 · Условия и проверка задачи',1,'Условие позволяет программе принимать решения. Сравнение == не изменяет значение. Двоеточие открывает блок, а отступ задаёт его границы.', 'task = "Изучить Python"\npriority = 2\nif priority >= 3:\n    print("Срочно:", task)\nelif priority == 2:\n    print("Обычная задача:", task)\nelse:\n    print("Низкий приоритет")', '1–2: исходные данные. 3: первое условие. 5: дополнительное. 7: альтернативная ветка. Обрати внимание на четыре пробела.', 'Добавь проверку пустого названия задачи и сообщение пользователю.', 'Используй if not task.strip(): перед проверкой приоритета.', ('if','else','priority'), 'basic'),
Step('p03','03 · Списки и циклы',2,'Одной переменной недостаточно для списка задач. list хранит несколько элементов, for перебирает их по очереди. enumerate даёт номер элемента.', 'tasks = ["Python", "SQL", "Git"]\nprint("Всего задач:", len(tasks))\nfor number, title in enumerate(tasks, start=1):\n    print(number, title)\ntasks.append("Tkinter")\nprint("После добавления:", len(tasks))', '1: список. 2: len. 3–4: цикл с нумерацией. 5: добавление. 6: повторная проверка длины.', 'Добавь ещё две задачи, затем выведи их в обратном порядке.', 'Изучи reversed(tasks) в энциклопедии или используй tasks[::-1].', ('for','tasks','append'), 'syntax'),
Step('p04','04 · Функции и словари',2,'Функция позволяет переиспользовать логику. Словарь хранит поля одной задачи. return возвращает результат вместо печати внутри бизнес-логики.', 'def create_task(title, priority=1):\n    if not title.strip():\n        raise ValueError("Пустая задача")\n    return {"title": title, "priority": priority, "done": False}\n\ntasks = []\ntasks.append(create_task("Python", 2))\nfor task in tasks:\n    print(task["title"], task["priority"])', '1: объявление функции и параметр по умолчанию. 2–3: проверка. 4: создание словаря. 7–9: использование функции.', 'Добавь функцию mark_done(task), меняющую done на True.', 'Функция получает словарь; запиши task["done"] = True.', ('def','return','done'), 'syntax'),
Step('p05','05 · JSON и сохранение',3,'Программа должна сохранять задачи между запусками. JSON представляет список словарей как текст. pathlib позволяет создавать переносимые пути.', 'import json\nfrom pathlib import Path\n\nDATA_FILE = Path("tasks.json")\n\ndef save_tasks(tasks):\n    DATA_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")\n\ndef load_tasks():\n    if not DATA_FILE.exists():\n        return []\n    return json.loads(DATA_FILE.read_text(encoding="utf-8"))', '1–2: библиотеки. 4: путь. 6–7: запись. 9–12: чтение с обработкой отсутствующего файла.', 'Добавь проверку, что после json.loads() получен список.', 'Проверь isinstance(result, list), иначе вызови ValueError.', ('json','Path','save_tasks','load_tasks'), 'syntax'),
Step('p06','06 · Разделяем код на модули',3,'По мере роста приложения main.py не должен содержать всё. Разделяем ответственность: main запускает, service управляет задачами, repository сохраняет.', '# main.py\nfrom services.task_service import TaskService\n\ndef main():\n    service = TaskService()\n    service.add("Изучить Python")\n    print(service.list_all())\n\nif __name__ == "__main__":\n    main()\n\n# services/task_service.py\n# class TaskService: ...', '1–2: точка входа и импорт. 4–7: создание сервиса. 9–10: защита запуска. Последние строки — схема следующего файла.', 'Создай в конструкторе services/task_service.py и реализуй методы add и list_all.', 'Сервис хранит задачи в self.tasks; методы не должны создавать окно Tkinter.', ('import','main','TaskService'), 'syntax'),
Step('p07','07 · Классы и модели',4,'Класс модели описывает одну задачу. Сервис управляет коллекцией. Такой подход отделяет структуру данных от UI.', 'from dataclasses import dataclass\n\n@dataclass\nclass Task:\n    id: int\n    title: str\n    done: bool = False\n\nclass TaskService:\n    def __init__(self):\n        self.tasks = []\n    def add(self, title):\n        task = Task(len(self.tasks) + 1, title)\n        self.tasks.append(task)\n        return task', '1–7: модель Task. 9–15: сервис и состояние. dataclass создаёт стандартный конструктор автоматически.', 'Добавь метод complete(task_id), отмечающий задачу выполненной.', 'Найди задачу по id, затем установи done = True.', ('class','Task','TaskService'), 'syntax'),
Step('p08','08 · Окно Tkinter',4,'Теперь добавляем frontend — окно, которое показывает задачи. UI вызывает сервис, но не должен содержать SQL или бизнес-правила.', 'import tkinter as tk\n\ndef main():\n    root = tk.Tk()\n    root.title("BahonIQ Task Manager")\n    root.geometry("700x450")\n    title = tk.Label(root, text="Мои задачи", font=("Segoe UI", 18))\n    title.pack(pady=15)\n    entry = tk.Entry(root, width=40)\n    entry.pack()\n    tk.Button(root, text="Добавить", command=lambda: print(entry.get())).pack(pady=10)\n    root.mainloop()\n\nif __name__ == "__main__":\n    main()', 'Tk() создаёт окно. Label показывает текст. Entry получает ввод. Button вызывает функцию. mainloop() обрабатывает события.', 'Измени заголовок, размер и цвет кнопки; затем замени print на вызов TaskService.', 'Параметр bg задаёт цвет кнопки, geometry — размер окна.', ('tk.Tk','tk.Button','mainloop'), 'syntax'),
Step('p09','09 · SQLite и репозиторий',5,'SQLite сохраняет данные надёжнее простого JSON для многопользовательских сценариев и сложных запросов. Репозиторий скрывает SQL от UI.', 'import sqlite3\n\ndef create_db(path="tasks.db"):\n    with sqlite3.connect(path) as db:\n        db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER DEFAULT 0)")\n\ndef add_task(path, title):\n    with sqlite3.connect(path) as db:\n        db.execute("INSERT INTO tasks(title) VALUES (?)", (title,))\n\ndef list_tasks(path):\n    with sqlite3.connect(path) as db:\n        return db.execute("SELECT id, title, done FROM tasks").fetchall()', 'connect открывает базу. CREATE TABLE создаёт схему. ? защищает параметры от SQL-инъекций. fetchall читает результат.', 'Добавь функцию complete_task(path, id), которая обновляет done.', 'UPDATE tasks SET done=1 WHERE id=? с параметром (id,).', ('sqlite3','CREATE TABLE','INSERT','SELECT'), 'syntax'),
Step('p10','10 · Настройки, API и тесты',6,'Завершаем проект: config хранит параметры, API предоставляет интерфейс другим приложениям, тесты проверяют сервис независимо от UI. Для HTTP API потребуется FastAPI или другая библиотека.', '# config/settings.py\nfrom dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass Settings:\n    app_name: str = "BahonIQ Task Manager"\n    database_path: str = "tasks.db"\n\n# tests/test_service.py\ndef test_new_task(service):\n    task = service.add("Python")\n    assert task.title == "Python"\n\n# api/routes.py\n# GET /tasks -> список задач\n# POST /tasks -> создание задачи', 'Settings централизует конфигурацию. pytest проверяет контракт. API определяет способы доступа извне; комментарии показывают будущие HTTP-маршруты.', 'Напиши три теста: добавление, пустое название и завершение задачи. Затем спроектируй GET /tasks.', 'Проверь нормальный случай, ошибочный ввод и изменение состояния.', ('Settings','test_','GET','POST'), 'syntax'),
]
S = [
Step('s01','01 · SELECT: знакомство с данными',1,'SQL — язык запросов к реляционным базам. SELECT выбирает столбцы, FROM — таблицу. Начинаем с задач нашего Task Manager.', 'SELECT id, title, status\nFROM tasks\nORDER BY id;', 'SELECT задаёт поля. FROM указывает таблицу. ORDER BY делает результат воспроизводимым.', 'Покажи только title и status; отсортируй по названию.', 'Замени список после SELECT и добавь ORDER BY title.', ('SELECT','FROM'), 'sql'),
Step('s02','02 · WHERE и логика',1,'WHERE фильтрует строки до агрегирования. Используй AND, OR, IN и сравнения.', "SELECT id, title, status\nFROM tasks\nWHERE status = 'open'\nORDER BY id;", 'WHERE status = open оставляет незавершённые задачи.', 'Выбери задачи со статусом done.', 'Замени open на done.', ('WHERE','status'), 'sql'),
Step('s03','03 · COUNT и GROUP BY',2,'COUNT(*) считает строки, GROUP BY формирует группы. Это основа аналитики.', 'SELECT status, COUNT(*) AS total\nFROM tasks\nGROUP BY status\nORDER BY total DESC;', 'COUNT(*) считает записи каждой группы; AS задаёт читаемый заголовок.', 'Посчитай задачи по user_id и отсортируй по количеству.', 'Используй GROUP BY user_id.', ('COUNT','GROUP BY'), 'sql'),
Step('s04','04 · JOIN и связи',3,'В реляционной модели задачи связаны с пользователями по внешнему ключу. JOIN объединяет таблицы.', 'SELECT t.title, u.name\nFROM tasks AS t\nJOIN users AS u ON u.id = t.user_id\nORDER BY u.name;', 't и u — псевдонимы. ON определяет условие связи.', 'Выведи имя пользователя и количество его задач, включая пользователей без задач.', 'Используй LEFT JOIN и GROUP BY u.id.', ('JOIN','ON'), 'sql'),
Step('s05','05 · Создание таблиц и ограничения',4,'CREATE TABLE задаёт схему. PRIMARY KEY уникально определяет строку, FOREIGN KEY связывает таблицы, NOT NULL запрещает отсутствие значения.', 'CREATE TABLE priorities (\n    id INTEGER PRIMARY KEY,\n    name TEXT NOT NULL UNIQUE,\n    rank INTEGER NOT NULL DEFAULT 1\n);', 'Ограничения предотвращают некорректные данные до их попадания в приложение.', 'Добавь CHECK для status со значениями open и done.', 'Используй CHECK(status IN (...)).', ('CREATE TABLE','PRIMARY KEY','CHECK'), 'ddl'),
Step('s06','06 · INSERT, UPDATE, DELETE',4,'Операции изменения данных должны выполняться на учебной копии базы. WHERE в UPDATE и DELETE особенно важен.', "INSERT INTO tasks(title, status, user_id)\nVALUES ('Изучить SQL', 'open', 1);\nUPDATE tasks SET status='done' WHERE id=1;\nDELETE FROM tasks WHERE id=3;", 'INSERT добавляет, UPDATE изменяет, DELETE удаляет. Транзакция позволяет откатить изменения.', 'Добавь запись, измени её статус и проверь SELECT.', 'Выполняй изменения в учебной базе, не в рабочем BahonIQ.', ('INSERT','UPDATE','DELETE'), 'ddl'),
Step('s07','07 · CTE и оконные функции',5,'CTE упрощает сложные запросы. ROW_NUMBER нумерует строки без сворачивания результата.', 'WITH ranked AS (\n    SELECT title, status,\n           ROW_NUMBER() OVER (PARTITION BY status ORDER BY id) AS n\n    FROM tasks\n)\nSELECT * FROM ranked WHERE n <= 2;', 'WITH определяет временное выражение; OVER разбивает строки на окна.', 'Выведи первую задачу каждого статуса.', 'Измени условие n <= 2 на n = 1.', ('WITH','ROW_NUMBER','PARTITION BY'), 'sql'),
Step('s08','08 · Индексы и транзакции',6,'Индексы помогают некоторым запросам; EXPLAIN QUERY PLAN показывает выбранный план. Транзакции обеспечивают атомарность.', "CREATE INDEX idx_tasks_status ON tasks(status);\nEXPLAIN QUERY PLAN SELECT * FROM tasks WHERE status='open';", 'CREATE INDEX добавляет структуру поиска. EXPLAIN QUERY PLAN показывает SCAN или SEARCH.', 'Создай индекс на user_id и сравни планы запроса.', 'EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE user_id=1;', ('INDEX','EXPLAIN'), 'ddl'),
]

def steps(language):
    from .professional_curriculum import lessons
    return lessons(language)

def check_python(code, step):
    from .exercises import PYTHON, check_python_exercise
    if step.slug in PYTHON:
        return check_python_exercise(code, step.slug)
    rule=acceptance_for(step.slug)
    if not rule or not rule.python_cases:
        try: ast.parse(code)
        except SyntaxError as e:return False,f'Ошибка синтаксиса, строка {e.lineno}: {e.msg}'
        report=PythonRunner().assess(code,(TestCase('Код выполняется без исключений'),))
        details='\n'.join(case.stderr.strip() for case in report.cases if case.stderr)
        return report.passed,report.message+('\n'+details if details else '')
    cases=rule.python_cases
    report=PythonRunner().assess(code,cases)
    details=[]
    for case in report.cases:
        details.append(('✓ ' if case.passed else '✕ ')+case.name)
        if not case.passed and case.stderr: details.append(case.stderr.strip())
    return report.passed, report.message+('\n'+'\n'.join(details) if details else '')

def demo_db():
    db=sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript("""CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,department TEXT NOT NULL);
    INSERT INTO users VALUES(1,'Алия','Разработка'),(2,'Бек','Аналитика'),(3,'Дана','Поддержка'),(4,'Марат','Аналитика');
    CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,status TEXT NOT NULL,priority INTEGER NOT NULL,user_id INTEGER REFERENCES users(id));
    INSERT INTO tasks VALUES(1,'Python','open',5,1),(2,'SQL','done',4,1),(3,'Git','open',3,2),(4,'API','open',5,2),(5,'Tkinter','done',2,1),(6,'Отчёт','open',4,3);""")
    return db

def run_sql(code, allow_writes=False):
    if not allow_writes:
        result=SQLRunner().execute(code,read_only=True)
        return [' | '.join(result.columns)]+[' | '.join(str(v) for v in row) for row in result.rows]
    db=demo_db()
    try:
        if not allow_writes:
            def guard(action,*_):
                return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE) else sqlite3.SQLITE_DENY
            db.set_authorizer(guard)
        started=time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic()-started>3),1000)
        if allow_writes:
            db.set_authorizer(lambda action,*_: sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK)
        if allow_writes:
            db.executescript(code)
            return ['Операции выполнены в одноразовой учебной базе. Изменения не сохраняются.']
        cur=db.execute(code)
        cols=[d[0] for d in cur.description or []]
        rows=cur.fetchmany(101)
        if len(rows)>100:raise ValueError('Лимит результата: 100 строк')
        return [' | '.join(cols)]+[' | '.join(str(v) for v in row) for row in rows]
    finally:db.close()

def check_sql(code, step):
    from .exercises import SQL, check_sql_exercise
    if step.slug in SQL:
        return check_sql_exercise(code, step.slug)
    rule=acceptance_for(step.slug)
    if not rule or not rule.sql:
        try:
            result=SQLRunner().execute(code,read_only=step.mode!='ddl')
            return True,f'Запрос выполнен: {len(result.rows)} строк. Для этого переходного урока точный эталон ещё не задан.'
        except Exception as exc:
            return False,str(exc)
    report=SQLRunner().assess(code,rule.sql)
    return report.passed,report.message
