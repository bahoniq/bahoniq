"""Russian-language searchable reference, shared by both studios."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Entry:
    name: str
    category: str
    meaning: str
    syntax: str
    example: str
    note: str

PYTHON = [
('print()','Ввод и вывод','Выводит значения в консоль','print(value, sep=" ", end="\\n")','name = "BahonIQ"\nprint("Привет,", name)','Это встроенная функция, а не оператор.'),
('input()','Ввод и вывод','Читает введённую строку','input("Подсказка: ")','name = input("Имя: ")\nprint(name)','Результат всегда строка; для числа используй int().'),
('=','Операторы','Присваивает значение переменной','variable = expression','count = 3\ncount = count + 1','Не путай с ==, который сравнивает.'),
('==','Операторы','Проверяет равенство значений','left == right','age = 18\nprint(age == 18)','Возвращает True или False.'),
('if','Условия','Выполняет блок, если условие истинно','if condition:\n    statement','age = 20\nif age >= 18:\n    print("Доступ")','Двоеточие и отступ обязательны.'),
('elif','Условия','Проверяет дополнительное условие','elif condition:','score = 70\nif score > 90:\n    print("A")\nelif score > 60:\n    print("B")','Используется после if.'),
('else','Условия','Выполняет альтернативный блок','else:','ready = False\nif ready:\n    print("Да")\nelse:\n    print("Нет")','Не принимает собственного условия.'),
('for','Циклы','Перебирает элементы последовательности','for item in iterable:','for item in ["app", "ui"]:\n    print(item)','Для последовательности чисел используй range().'),
('while','Циклы','Повторяет блок, пока условие истинно','while condition:','n = 0\nwhile n < 3:\n    print(n)\n    n += 1','Обязательно предусмотрите завершение цикла.'),
('break','Циклы','Прерывает цикл','break','for n in range(5):\n    if n == 3:\n        break\n    print(n)','Действует на ближайший цикл.'),
('continue','Циклы','Переходит к следующей итерации','continue','for n in range(4):\n    if n == 2:\n        continue\n    print(n)','Не завершает весь цикл.'),
('def','Функции','Объявляет функцию','def name(args):\n    body','def total(a, b):\n    return a + b\nprint(total(2, 3))','Тело функции имеет отступ.'),
('return','Функции','Возвращает результат функции','return expression','def double(n):\n    return n * 2','После return выполнение функции прекращается.'),
('lambda','Функции','Создаёт короткую анонимную функцию','lambda x: expression','double = lambda x: x * 2\nprint(double(3))','Для сложной логики лучше def.'),
('list','Коллекции','Изменяемый упорядоченный список','[item1, item2]','tasks = ["A", "B"]\ntasks.append("C")','Индексы начинаются с нуля.'),
('dict','Коллекции','Хранит пары ключ-значение','{"key": value}','task = {"title": "Учиться"}\nprint(task["title"])','Ключи должны быть хешируемыми.'),
('set','Коллекции','Хранит уникальные элементы','set(iterable)','ids = set([1, 1, 2])\nprint(len(ids))','Порядок элементов не гарантирован.'),
('tuple','Коллекции','Неизменяемая последовательность','(a, b)','point = (10, 20)','Удобна для фиксированных наборов.'),
('len()','Функции','Возвращает длину коллекции','len(collection)','print(len([1, 2, 3]))','Для строки считает количество символов.'),
('range()','Функции','Создаёт последовательность целых чисел','range(start, stop, step)','for i in range(3):\n    print(i)','Конечная граница не включается.'),
('enumerate()','Функции','Возвращает индекс и элемент','enumerate(items, start=0)','for i, v in enumerate(["a", "b"]):\n    print(i, v)','Полезно при обработке списков.'),
('zip()','Функции','Объединяет несколько последовательностей по позициям','zip(a, b)','for a, b in zip([1, 2], [3, 4]):\n    print(a, b)','По умолчанию останавливается на кратчайшей.'),
('import','Модули','Импортирует модуль','import module','import json\nprint(json.dumps({"ok": True}))','Не называй свой файл именем стандартной библиотеки.'),
('from ... import','Модули','Импортирует выбранное имя','from module import name','from pathlib import Path\nprint(Path("data"))','Следи за циклическими импортами.'),
('__name__','Архитектура','Имя текущего модуля','if __name__ == "__main__":','def main():\n    print("Старт")\nif __name__ == "__main__":\n    main()','Позволяет не запускать main при импорте.'),
('class','ООП','Объявляет класс','class Name:','class Task:\n    def __init__(self, title):\n        self.title = title','Класс описывает поведение и состояние объектов.'),
('self','ООП','Ссылка на текущий экземпляр','self.attribute','class Task:\n    def __init__(self, name):\n        self.name = name','Это соглашение об имени первого параметра метода.'),
('try / except','Ошибки','Обрабатывает исключения','try:\n    ...\nexcept ValueError:\n    ...','try:\n    number = int("x")\nexcept ValueError:\n    print("Не число")','Лови конкретные исключения.'),
('raise','Ошибки','Создаёт исключение','raise ValueError(message)','if not "task":\n    raise ValueError("Пусто")','Используется для явной сигнализации об ошибке.'),
('with','Файлы','Управляет ресурсом и закрывает файл','with open(path) as f:','with open("demo.txt", "w") as f:\n    f.write("OK")','Файл закрывается автоматически.'),
('Path','Файлы','Удобная работа с путями','Path("folder") / "file.txt"','from pathlib import Path\np = Path("data") / "tasks.json"','Используй pathlib вместо ручной сборки путей.'),
('json','Файлы','Сериализует и читает JSON','json.dumps(value)','import json\nprint(json.dumps({"id": 1}))','JSON не поддерживает произвольные Python-объекты.'),
('sqlite3','Базы данных','Подключает SQLite к Python','sqlite3.connect(path)','import sqlite3\nconnection = sqlite3.connect(":memory:")','Применяй параметры ?, а не вставку пользовательских значений в SQL.'),
('tkinter','Интерфейс','Стандартная библиотека GUI','import tkinter as tk','import tkinter as tk\nroot = tk.Tk()\nroot.title("Demo")\nroot.mainloop()','GUI нужно запускать в главном потоке.'),
('assert','Тесты','Проверяет предположение в тесте','assert condition','assert 2 + 2 == 4','В production для валидации ввода лучше исключения.'),
('async / await','Асинхронность','Ожидает асинхронные операции','async def f():\n    await operation()','import asyncio\nasync def main():\n    await asyncio.sleep(0)','Не ускоряет CPU-вычисления автоматически.'),
]
SQL = [
('SELECT','Выборка','Выбирает столбцы из таблицы','SELECT columns FROM table;','SELECT title, status FROM tasks;','Не используйте SELECT * без необходимости.'),
('FROM','Выборка','Указывает источник строк','FROM table','SELECT * FROM tasks;','Может включать JOIN и подзапросы.'),
('WHERE','Фильтрация','Отбирает строки по условию','WHERE condition','SELECT * FROM tasks WHERE status = "open";','Выполняется до группировки.'),
('ORDER BY','Сортировка','Сортирует результат','ORDER BY column DESC','SELECT * FROM tasks ORDER BY id DESC;','ASC — по возрастанию, DESC — по убыванию.'),
('LIMIT','Выборка','Ограничивает число строк','LIMIT number','SELECT * FROM tasks LIMIT 10;','Без ORDER BY порядок результата не гарантирован.'),
('DISTINCT','Выборка','Убирает дубликаты строк результата','SELECT DISTINCT column','SELECT DISTINCT status FROM tasks;','Сравнивает все выбранные столбцы.'),
('COUNT()','Агрегация','Считает строки или непустые значения','COUNT(*)','SELECT COUNT(*) FROM tasks;','COUNT(column) пропускает NULL.'),
('SUM()','Агрегация','Суммирует числовые значения','SUM(column)','SELECT SUM(price) FROM orders;','NULL обычно игнорируется.'),
('AVG()','Агрегация','Находит среднее','AVG(column)','SELECT AVG(price) FROM orders;','NULL не участвует в среднем.'),
('MIN() / MAX()','Агрегация','Минимум и максимум','MIN(column), MAX(column)','SELECT MIN(id), MAX(id) FROM tasks;','Применимо и к датам при корректном формате.'),
('GROUP BY','Агрегация','Объединяет строки в группы','GROUP BY column','SELECT status, COUNT(*) FROM tasks GROUP BY status;','Неагрегированные столбцы должны соответствовать группировке.'),
('HAVING','Агрегация','Фильтрует агрегированные группы','HAVING COUNT(*) > 1','SELECT status, COUNT(*) FROM tasks GROUP BY status HAVING COUNT(*) > 1;','WHERE фильтрует строки, HAVING — группы.'),
('INNER JOIN','Связи','Объединяет совпадающие строки таблиц','JOIN b ON a.id = b.a_id','SELECT t.title, u.name FROM tasks t JOIN users u ON t.user_id=u.id;','Строки без совпадений не попадают в результат.'),
('LEFT JOIN','Связи','Сохраняет все строки левой таблицы','LEFT JOIN b ON ...','SELECT u.name, t.title FROM users u LEFT JOIN tasks t ON t.user_id=u.id;','Не найденные значения справа становятся NULL.'),
('ON','Связи','Задаёт условие соединения','ON a.id = b.id','SELECT * FROM tasks t JOIN users u ON t.user_id=u.id;','Без корректного ON возможен декартов результат.'),
('INSERT','Изменения','Добавляет строки','INSERT INTO table(columns) VALUES (...)','INSERT INTO tasks(title,status) VALUES ("Учёба","open");','В учебной базе изменения можно отменять.'),
('UPDATE','Изменения','Изменяет существующие строки','UPDATE table SET column=value WHERE ...','UPDATE tasks SET status="done" WHERE id=1;','Без WHERE изменятся все строки.'),
('DELETE','Изменения','Удаляет строки','DELETE FROM table WHERE ...','DELETE FROM tasks WHERE id=1;','Без WHERE удалятся все строки.'),
('CREATE TABLE','Схема','Создаёт таблицу','CREATE TABLE name(column TYPE)','CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT);','Используй ограничения и ключи.'),
('ALTER TABLE','Схема','Изменяет структуру таблицы','ALTER TABLE table ADD COLUMN ...','ALTER TABLE tasks ADD COLUMN priority INTEGER;','Возможности зависят от СУБД.'),
('PRIMARY KEY','Ключи','Уникальный идентификатор строки','id INTEGER PRIMARY KEY','CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT);','PRIMARY KEY не допускает повторения ключей.'),
('FOREIGN KEY','Ключи','Задаёт ссылку на другую таблицу','FOREIGN KEY(column) REFERENCES table(id)','CREATE TABLE tasks(user_id INTEGER REFERENCES users(id));','В SQLite включай PRAGMA foreign_keys=ON.'),
('NOT NULL','Ограничения','Запрещает NULL','title TEXT NOT NULL','CREATE TABLE tasks(title TEXT NOT NULL);','Пустая строка не равна NULL.'),
('UNIQUE','Ограничения','Запрещает повторения значений','column TEXT UNIQUE','CREATE TABLE users(email TEXT UNIQUE);','NULL может иметь особые правила по СУБД.'),
('WITH / CTE','Продвинутый SQL','Именует промежуточный результат','WITH x AS (SELECT ...) SELECT ...','WITH x AS (SELECT * FROM tasks) SELECT COUNT(*) FROM x;','CTE улучшает читаемость многошагового запроса.'),
('ROW_NUMBER()','Оконные функции','Нумерует строки в окне','ROW_NUMBER() OVER (ORDER BY ...)','SELECT ROW_NUMBER() OVER (ORDER BY id), title FROM tasks;','Не схлопывает строки, как GROUP BY.'),
('PARTITION BY','Оконные функции','Разделяет окно на группы','OVER (PARTITION BY col ORDER BY col2)','SELECT ROW_NUMBER() OVER (PARTITION BY status ORDER BY id) FROM tasks;','Работает внутри OVER.'),
('CREATE INDEX','Оптимизация','Создаёт индекс','CREATE INDEX name ON table(column)','CREATE INDEX idx_status ON tasks(status);','Ускоряет некоторые запросы, но увеличивает стоимость записи.'),
('EXPLAIN QUERY PLAN','Оптимизация','Показывает план запроса SQLite','EXPLAIN QUERY PLAN SELECT ...','EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE status="open";','План не равен точному времени выполнения.'),
('BEGIN / COMMIT','Транзакции','Начинает и подтверждает транзакцию','BEGIN; ... COMMIT;','BEGIN; UPDATE tasks SET status="done" WHERE id=1; COMMIT;','Несколько операций становятся одной логической единицей.'),
('ROLLBACK','Транзакции','Отменяет незавершённую транзакцию','ROLLBACK;','BEGIN; DELETE FROM tasks; ROLLBACK;','Не отменяет уже подтверждённый COMMIT.'),
('IS NULL','NULL','Проверяет отсутствие значения','WHERE column IS NULL','SELECT * FROM tasks WHERE status IS NULL;','= NULL не работает как обычное сравнение.'),
('CASE','Выражения','Выбирает значение по условию','CASE WHEN ... THEN ... ELSE ... END','SELECT CASE WHEN id > 2 THEN "new" ELSE "old" END FROM tasks;','Полезен для вычисляемых категорий.'),
]

def entries(language):
    return [Entry(*row) for row in (PYTHON if language=='python' else SQL)]

def search(language, query):
    q=' '.join(query.lower().split())
    aliases={'вывод':'print','вывести':'print','присвоить':'=','сравнить':'==','цикл':'for','функция':'def','количество':'count','посчитать':'count','сортировка':'order by','объединить':'join','группировка':'group by','создать таблицу':'create table'}
    if q in aliases:q=aliases[q]
    return [e for e in entries(language) if not q or q in (e.name+' '+e.category+' '+e.meaning+' '+e.note).lower()]
