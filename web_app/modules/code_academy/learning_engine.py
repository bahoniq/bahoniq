"""Structured professional lessons, static Python checks and SQL database scenarios."""
from dataclasses import dataclass
import ast
import sqlite3
from typing import Tuple

@dataclass(frozen=True)
class Lesson:
    slug: str
    title: str
    theory: str
    code: str
    walkthrough: str
    task: str
    hint: str
    checks: Tuple[str, ...]
    database: str = ""

PYTHON = [
 Lesson("py-architecture","01 · Точка входа и архитектура", """Цель: понять жизненный цикл настоящего приложения. main.py — точка входа, но бизнес-логика должна жить в сервисах. Модуль импортируется один раз и не должен запускать GUI при импорте. Функция main() организует зависимости. В реальном BahonIQ main.py запускает главное окно, а app/main_window.py создаёт интерфейс.

В этом уроке изучаем import, функции, __name__, pathlib, словари конфигурации, проверки аргументов и обработку ошибок.

Упражнение: измени конфигурацию, добавь проверку имени приложения и объясни, зачем код запуска помещён в if __name__ == '__main__'.""", """from pathlib import Path

APP_NAME = "BahonIQ Training"
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 640


def load_settings():
    # Пока настройки встроены; позже заменим на JSON.
    return {
        "name": APP_NAME,
        "width": DEFAULT_WIDTH,
        "height": DEFAULT_HEIGHT,
        "data_dir": Path("data"),
    }


def validate_settings(settings):
    if not settings["name"].strip():
        raise ValueError("Название не должно быть пустым")
    if settings["width"] < 320:
        raise ValueError("Ширина слишком мала")
    if settings["height"] < 240:
        raise ValueError("Высота слишком мала")
    return True


def describe_application(settings):
    validate_settings(settings)
    return (
        f"{settings['name']}: "
        f"{settings['width']}x{settings['height']}"
    )


def main():
    settings = load_settings()
    print(describe_application(settings))


if __name__ == "__main__":
    main()
""", """Строки 1–5: импорт и константы — конфигурация.
load_settings(): собирает зависимости в одном месте.
validate_settings(): отделяет правила проверки от интерфейса.
describe_application(): возвращает результат, не печатая его.
main(): управляет порядком вызовов.
__name__: предотвращает запуск при обычном импорте.

Архитектура: main.py → app/application.py → services/settings_service.py. Эти файлы создадим на следующем этапе.""", "Добавь настройку theme и проверку допустимых значений 'light'/'dark'. Сохрани существующие функции.", "Используй settings['theme'] и ValueError, не добавляй проверку в main().", ("function:main","function:validate_settings","guard:main","text:theme")),
 Lesson("py-files","02 · JSON, данные и обработка ошибок", """Цель: сохранять данные без потери предыдущих записей. Приложение должно разделять хранилище, бизнес-логику и интерфейс. pathlib создаёт переносимые пути. JSON хранит списки и словари, но не произвольные объекты.

Сначала проверяй существование файла, затем корректность JSON и ожидаемый тип. В реальном приложении для надёжности используют временный файл и атомарную замену.

Практика: добавь валидацию имени и тест на повреждённый JSON.""", """import json
from pathlib import Path

DATA_DIR = Path("training_data")
DATA_FILE = DATA_DIR / "employees.json"


def read_employees(path=DATA_FILE):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as stream:
            result = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("Файл JSON повреждён") from exc
    if not isinstance(result, list):
        raise ValueError("Ожидался список сотрудников")
    return result


def write_employees(items, path=DATA_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(items, stream, ensure_ascii=False, indent=2)


def next_id(items):
    return max((row["id"] for row in items), default=0) + 1


def add_employee(name, department, path=DATA_FILE):
    if not name.strip():
        raise ValueError("Укажите имя")
    items = read_employees(path)
    employee = {"id": next_id(items), "name": name.strip(),
                "department": department.strip()}
    items.append(employee)
    write_employees(items, path)
    return employee


def main():
    item = add_employee("Алия", "IT")
    print("Добавлен:", item)


if __name__ == "__main__":
    main()
""", """read_employees(): чтение с проверкой формата.
write_employees(): создаёт каталог, затем сериализует JSON.
next_id(): генерация идентификатора для учебного примера.
add_employee(): бизнес-правила и сохранение.
main(): демонстрационный сценарий.

Внимание: max(id)+1 не годится для конкурентных записей. В следующем маршруте SQLite решит проблему ключей.""", "Добавь функцию find_employee(items, employee_id), возвращающую запись или None. Не удаляй обработку JSONDecodeError.", "Пройди циклом по items, сравни row['id'] с employee_id.", ("function:read_employees","function:add_employee","function:find_employee","exception:ValueError")),
 Lesson("py-oop","03 · Классы, сервисы и тестируемая логика", """Цель: отделить бизнес-правила от хранения. Dataclass помогает описать объект с типами. Сервис принимает репозиторий через конструктор — это dependency injection. Такой код легче тестировать и менять.

Проверь, как исключения помогают сообщать о неправильном вводе. Не используй глобальные переменные для состояния сервиса.""", """from dataclasses import dataclass


@dataclass
class Employee:
    id: int
    name: str
    department: str


class MemoryRepository:
    def __init__(self):
        self.items = {}
        self.sequence = 0

    def save(self, name, department):
        self.sequence += 1
        employee = Employee(self.sequence, name, department)
        self.items[employee.id] = employee
        return employee

    def all(self):
        return list(self.items.values())


class EmployeeService:
    def __init__(self, repository):
        self.repository = repository

    def add(self, name, department):
        if not name.strip():
            raise ValueError("Имя обязательно")
        if not department.strip():
            raise ValueError("Отдел обязателен")
        return self.repository.save(name.strip(), department.strip())

    def list_employees(self):
        return self.repository.all()


def main():
    service = EmployeeService(MemoryRepository())
    service.add("Алия", "IT")
    service.add("Бек", "HR")
    for employee in service.list_employees():
        print(employee.id, employee.name, employee.department)


if __name__ == "__main__":
    main()
""", """Employee: модель данных.
MemoryRepository: хранение, заменяемое на SQLiteRepository.
EmployeeService: правила валидации.
main: композиция объектов.

Связь с BahonIQ: ui вызывает service, service использует repository, а main связывает их вместе.""", "Добавь метод find_by_department в EmployeeService и реализуй поиск по отделу без изменения модели.", "Используй self.repository.all() и фильтрацию списка.", ("class:Employee","class:EmployeeService","function:main","text:find_by_department")),
 Lesson("py-gui","04 · Tkinter: интерфейс, события и SQLite", """Цель: соединить интерфейс и данные. UI отвечает за ввод и отображение, а не за SQL. В этом примере используется SQLite для сохранения сотрудников. Пример предназначен для запуска в учебном проекте на доверенном компьютере, не в ограниченном редакторе коротких упражнений.

В реальном BahonIQ tkinter.Toplevel создаёт дочернее окно, а обработчик command связывает кнопку с методом. Следи, чтобы долгие задачи не блокировали mainloop().""", """import sqlite3
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

DB_PATH = Path("training_employees.db")


def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS employees ("
                     "id INTEGER PRIMARY KEY, "
                     "name TEXT NOT NULL, "
                     "department TEXT NOT NULL)")


def insert_employee(name, department):
    if not name.strip() or not department.strip():
        raise ValueError("Заполни оба поля")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO employees(name, department) VALUES (?, ?)",
                     (name.strip(), department.strip()))


class EmployeeWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BahonIQ · Учебный менеджер")
        self.geometry("680x460")
        self.name_var = tk.StringVar()
        self.department_var = tk.StringVar()
        tk.Label(self, text="Имя сотрудника").pack(pady=5)
        tk.Entry(self, textvariable=self.name_var).pack(fill="x", padx=24)
        tk.Label(self, text="Отдел").pack(pady=5)
        tk.Entry(self, textvariable=self.department_var).pack(fill="x", padx=24)
        tk.Button(self, text="Добавить", command=self.add).pack(pady=12)
        self.status = tk.Label(self, text="Готово")
        self.status.pack()

    def add(self):
        try:
            insert_employee(self.name_var.get(), self.department_var.get())
        except ValueError as exc:
            messagebox.showerror("Проверка", str(exc))
            return
        self.status.configure(text="Запись добавлена")
        self.name_var.set("")
        self.department_var.set("")


def main():
    initialize_database()
    app = EmployeeWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
""", """initialize_database(): создаёт схему при первом запуске.
insert_employee(): параметризованный SQL защищает от подстановки текста как команды.
EmployeeWindow: интерфейс и события.
add(): читает поля, вызывает слой данных, показывает результат.
mainloop(): запускает цикл обработки событий Tkinter.

Следующий шаг — разделить один файл на main.py, ui/main_window.py, services/employee_service.py, data/repository.py и написать pytest.""", "Добавь кнопку 'Очистить' и метод clear_fields, сбрасывающий оба StringVar.", "Используй tk.Button(..., command=self.clear_fields), затем .set('').", ("class:EmployeeWindow","function:main","text:clear_fields","text:Очистить")),
]

SQL = [
 Lesson("sql-schema","01 · Схема базы и ограничения", """Реляционная модель хранит сущности в таблицах. PRIMARY KEY идентифицирует строку, FOREIGN KEY связывает таблицы, NOT NULL запрещает отсутствие значения. Нормализация помогает не дублировать данные.

Изучи схему университета. Таблицы faculties и students связаны внешним ключом. Изменения в этой лаборатории выполняются только во временной базе.""", """SELECT name, sql
FROM sqlite_master
WHERE type = 'table'
  AND name NOT LIKE 'sqlite_%'
ORDER BY name;
""", """SELECT извлекает данные из системной таблицы sqlite_master.
WHERE ограничивает тип объектов и скрывает служебные таблицы.
ORDER BY упорядочивает результат.

Обрати внимание на PRIMARY KEY и REFERENCES в определениях CREATE TABLE.""", "Найди схему таблицы students. Укажи её столбцы и внешний ключ.", "Добавь AND name = 'students' в WHERE.", ("contains:sqlite_master","contains:students"),"university"),
 Lesson("sql-joins","02 · JOIN и агрегирование", """INNER JOIN оставляет строки с совпадением ключей; LEFT JOIN сохраняет все строки слева. COUNT(*) считает строки, COUNT(column) — только непустые значения, COUNT(DISTINCT column) — уникальные непустые значения.

Задача: сравнить факультеты, включая факультеты без студентов. Это требует LEFT JOIN, а не INNER JOIN.""", """SELECT f.name AS faculty,
       COUNT(s.id) AS students_total,
       COUNT(DISTINCT s.id) AS unique_students
FROM faculties AS f
LEFT JOIN students AS s
       ON s.faculty_id = f.id
GROUP BY f.id, f.name
ORDER BY students_total DESC, faculty;
""", """FROM faculties — все факультеты.
LEFT JOIN students — добавляет студентов, но сохраняет факультеты без них.
ON — связь ключей.
COUNT(s.id) — не считает NULL из пустого соединения.
GROUP BY — одна строка на факультет.
ORDER BY — сортировка результата.""", "Добавь HAVING, чтобы показывать только факультеты с минимум двумя студентами.", "HAVING COUNT(s.id) >= 2 после GROUP BY.", ("contains:LEFT JOIN","contains:GROUP BY","contains:HAVING"),"university"),
 Lesson("sql-cte","03 · CTE и оконные функции", """CTE (WITH) делает сложный запрос читаемым. Оконная функция считает показатель по группе без сворачивания строк. ROW_NUMBER() нумерует строки внутри PARTITION BY.

Практика: найди сотрудников с самой высокой зарплатой в каждом отделе. Используй ROW_NUMBER(), чтобы сохранить одну запись на отдел.""", """WITH ranked AS (
    SELECT e.name,
           d.name AS department,
           e.salary,
           ROW_NUMBER() OVER (
               PARTITION BY d.id
               ORDER BY e.salary DESC, e.id
           ) AS position
    FROM employees AS e
    JOIN departments AS d ON d.id = e.department_id
)
SELECT department, name, salary
FROM ranked
WHERE position = 1
ORDER BY department;
""", """WITH ranked: временное имя результата.
JOIN: соединяет сотрудников с отделами.
PARTITION BY: отдельная нумерация для каждого отдела.
ORDER BY внутри OVER: зарплата по убыванию.
WHERE position = 1: оставляет лидера отдела.""", "Измени запрос, чтобы вывести двух самых высокооплачиваемых сотрудников в каждом отделе.", "Замени position = 1 на position <= 2.", ("contains:WITH","contains:ROW_NUMBER","contains:position <= 2"),"company"),
 Lesson("sql-transactions","04 · Транзакции, индексы и план запроса", """Транзакция объединяет операции в логическую единицу. COMMIT фиксирует изменения, ROLLBACK отменяет. Индекс ускоряет некоторые фильтры, но требует памяти и замедляет запись. EXPLAIN QUERY PLAN помогает понять доступ к таблицам.

В лаборатории каждый запуск начинается с чистой временной базы, поэтому можно экспериментировать с индексами без риска для рабочих данных.""", """EXPLAIN QUERY PLAN
SELECT c.name, COUNT(o.id) AS orders_total
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
GROUP BY c.id, c.name
ORDER BY orders_total DESC;
""", """EXPLAIN QUERY PLAN показывает план SQLite.
LEFT JOIN сохраняет клиентов без заказов.
COUNT(o.id) не считает пустую сторону соединения.
GROUP BY группирует заказы по клиенту.

Сравни план до и после индекса на orders(customer_id) в отдельной учебной копии.""", "Добавь фильтр WHERE c.name IS NOT NULL и сохрани группировку.", "Фильтр должен стоять после JOIN, до GROUP BY.", ("contains:EXPLAIN","contains:GROUP BY","contains:WHERE"),"shop"),
]

def python_checks(code, checks):
    try: tree=ast.parse(code)
    except SyntaxError as exc: return [f"Синтаксис: строка {exc.lineno}: {exc.msg}"]
    functions={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    classes={n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)}
    errors=[]
    for check in checks:
        kind, value=check.split(':',1)
        if kind=='function' and value not in functions: errors.append(f"Не найдена функция {value}()")
        if kind=='class' and value not in classes: errors.append(f"Не найден класс {value}")
        if kind=='text' and value not in code: errors.append(f"Не найдено изменение: {value}")
        if kind=='exception' and value not in code: errors.append(f"Не найдена обработка {value}")
        if kind=='guard' and not any(isinstance(n,ast.Compare) and any(isinstance(v,ast.Constant) and v.value=='__main__' for v in n.comparators) for n in ast.walk(tree)): errors.append('Нет проверки __name__ == "__main__"')
    return errors

SCHEMAS={
 'university': """CREATE TABLE faculties(id INTEGER PRIMARY KEY,name TEXT NOT NULL); CREATE TABLE students(id INTEGER PRIMARY KEY,name TEXT NOT NULL,faculty_id INTEGER REFERENCES faculties(id),course INTEGER); INSERT INTO faculties VALUES(1,'Медицина'),(2,'Фармация'),(3,'Стоматология'); INSERT INTO students VALUES(1,'Алия',1,2),(2,'Бек',1,3),(3,'Дана',2,1),(4,'Ержан',1,2);""",
 'company': """CREATE TABLE departments(id INTEGER PRIMARY KEY,name TEXT NOT NULL); CREATE TABLE employees(id INTEGER PRIMARY KEY,name TEXT NOT NULL,department_id INTEGER REFERENCES departments(id),salary INTEGER NOT NULL); INSERT INTO departments VALUES(1,'IT'),(2,'HR'),(3,'Finance'); INSERT INTO employees VALUES(1,'Алия',1,350000),(2,'Бек',1,420000),(3,'Дана',2,280000),(4,'Ержан',2,310000),(5,'Айша',3,500000);""",
 'shop': """CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL); CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER REFERENCES customers(id),amount INTEGER NOT NULL); INSERT INTO customers VALUES(1,'Алия'),(2,'Бек'),(3,'Дана'); INSERT INTO orders VALUES(1,1,12000),(2,1,4500),(3,2,7000);"""
}

def sql_checks(code, checks):
    normalized=' '.join(code.upper().split())
    return [f"Ожидалась конструкция: {c.split(':',1)[1]}" for c in checks if c.startswith('contains:') and c.split(':',1)[1].upper() not in normalized]

def run_sql_lesson(code, database):
    if len(code)>12000: raise ValueError('Запрос слишком длинный')
    if database not in SCHEMAS: raise ValueError('Неизвестная учебная база')
    con=sqlite3.connect(':memory:')
    try:
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript(SCHEMAS[database])
        # Read-only query API: schema and data mutations are never accepted here.
        def authorizer(action,*args):
            return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY
        con.set_authorizer(authorizer)
        count=[0]
        def progress():
            count[0]+=1
            return 1 if count[0]>150 else 0
        con.set_progress_handler(progress,1000)
        cursor=con.execute(code)
        rows=cursor.fetchmany(101)
        if len(rows)>100: raise ValueError('Максимум 100 строк')
        header=' | '.join(col[0] for col in cursor.description or [])
        return header+'\n'+'\n'.join(' | '.join(str(v) for v in row) for row in rows)
    finally:con.close()
