# -*- coding: utf-8 -*-
"""База данных BahonIQ Academy (SQLite) — 4 последовательных этапа обучения и прогресс пользователя."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("bahoniq.academy.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB_APP_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WEB_APP_DIR / "data"
DB_PATH = DATA_DIR / "academy.db"

_db_lock = threading.Lock()


# ============================================================================
# СТРУКТУРА 4 ЭТАПОВ КУРСА BAHONIQ ACADEMY
# ============================================================================

STAGES_SEED: list[dict[str, Any]] = [
    {
        "id": 1,
        "slug": "stage_1_python",
        "title": "Этап 1: Основы Python",
        "subtitle": "База с нуля до файлов и JSON",
        "order_index": 1,
    },
    {
        "id": 2,
        "slug": "stage_2_sql",
        "title": "Этап 2: Базы данных и SQL",
        "subtitle": "Таблицы, запросы и связка с Python",
        "order_index": 2,
    },
    {
        "id": 3,
        "slug": "stage_3_arch_book",
        "title": "Этап 3: Архитектура + PDF-Книга",
        "subtitle": "Устройство BahonIQ от А до Я",
        "order_index": 3,
    },
    {
        "id": 4,
        "slug": "stage_4_polygon",
        "title": "Этап 4: Боевой полигон",
        "subtitle": "Сквозная практика, поиск багов и тесты",
        "order_index": 4,
    },
]


LESSONS_SEED: list[dict[str, Any]] = [
    # ------------------------------------------------------------------------
    # ЭТАП 1: ОСНОВЫ PYTHON (8 УРОКОВ)
    # ------------------------------------------------------------------------
    {
        "stage_id": 1,
        "slug": "py_1_vars_types",
        "order_index": 1,
        "title": "1. Переменные и типы данных (int, float, str, bool)",
        "language": "python",
        "summary": "Хранение данных в памяти: числа, строки и логические флаги на примере карточки студента.",
        "ai_theory": (
            "Представь переменную как подписанную коробку на складе университета. На коробке написано имя (`student_name`), "
            "а внутри лежит значение (`'Алия'`). В Python не нужно заранее объявлять размер коробки — язык сам понимает тип данных:\n\n"
            "• **`str` (строка)** — любой текст в кавычках: `'Информационные системы'`\n"
            "• **`int` (целое число)** — курс или количество кредитов: `3`, `24`\n"
            "• **`float` (дробное число)** — средний балл GPA: `3.75`\n"
            "• **`bool` (логический тип)** — `True` (истина) или `False` (ложь), например допуск к сессии `has_access = True`.\n\n"
            "Пример из реальной жизни BahonIQ:\n"
            "```python\n"
            "student = 'Айдар'\n"
            "course = 2\n"
            "gpa = 3.65\n"
            "is_active = True\n"
            "print(student, course, gpa, is_active)\n"
            "```"
        ),
        "task_prompt": (
            "Создайте 3 переменные:\n"
            "1. `module_name` со строкой `'Platonus Wiki'`\n"
            "2. `articles_count` с целым числом `117`\n"
            "3. `is_online` со значением `True`\n"
            "Выведите их все на экран одной командой `print(module_name, articles_count, is_online)`."
        ),
        "starter_code": (
            "# Создайте три переменные и выведите их через print()\n"
            "module_name = 'Platonus Wiki'\n"
            "articles_count = 117\n"
            "# Добавьте переменную is_online и выведите результат:\n"
        ),
        "expected_hint": "Проверьте, что переменная is_online равна True (с большой буквы без кавычек) и вызван print().",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_2_io_fstrings",
        "order_index": 2,
        "title": "2. Ввод и вывод данных (input, print и f-строки)",
        "language": "python",
        "summary": "Форматирование красивых сообщений и чтение пользовательского ввода.",
        "ai_theory": (
            "Когда программа общается с пользователем, ей нужны два инструмента:\n"
            "1. **`input()`** — принимает текст от пользователя (всегда возвращает строку `str`).\n"
            "2. **`print()` + f-строки (`f'...'`)** — позволяет красиво подставлять переменные прямо внутрь текста в фигурных скобках `{}`.\n\n"
            "Почему `f-строки` — главный стандарт в современном Python? Вместо неудобного склеивания через `+` ты просто ставишь букву `f` перед кавычками:\n"
            "```python\n"
            "user = 'Бахытжан'\n"
            "tickets = 5\n"
            "print(f'Администратор {user} закрыл {tickets} заявок.')\n"
            "```\n"
            "Если нужно превратить введённую строку в число, оберни её в `int()`: `age = int('20')`."
        ),
        "task_prompt": (
            "Даны переменные `teacher = 'Ержан'` и `group = 'ИС-24-1'`. "
            "Используя f-строку, выведите через `print()` точную фразу:\n"
            "`Преподаватель Ержан открыл журнал группы ИС-24-1`"
        ),
        "starter_code": (
            "teacher = 'Ержан'\n"
            "group = 'ИС-24-1'\n\n"
            "# Выведите фразу с помощью f-строки:\n"
            "print(f'...')\n"
        ),
        "expected_hint": "Подставьте {teacher} и {group} внутрь f'Преподаватель {teacher} открыл журнал группы {group}'.",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_3_conditions",
        "order_index": 3,
        "title": "3. Условия и принятие решений (if / elif / else)",
        "language": "python",
        "summary": "Проверка баллов РК, допуска к экзамену и ветвление логики.",
        "ai_theory": (
            "Программа становится умной, когда умеет принимать решения. В АИС Platonus рейтинг допуска считается так: "
            "если балл меньше 50 — студент не допущен; если от 50 до 89 — допущен; если 90 и выше — допущен с отличием.\n\n"
            "В Python для этого используется конструкция `if / elif / else`:\n"
            "```python\n"
            "score = 78\n"
            "if score >= 90:\n"
            "    print('Отлично (A)')\n"
            "elif score >= 50:\n"
            "    print('Допущен к экзамену')\n"
            "else:\n"
            "    print('Недопуск (< 50)')\n"
            "```\n"
            "Обрати внимание на двоеточие `:` в конце условия и отступ в 4 пробела — так Python понимает, какой блок кода относится к условию."
        ),
        "task_prompt": (
            "В переменной `rk_score = 65` хранится балл рубежного контроля. "
            "Напишите условие `if / else`: если `rk_score >= 50`, выведите `'Допуск открыт'`, иначе выведите `'Пересдача'`."
        ),
        "starter_code": (
            "rk_score = 65\n\n"
            "# Напишите проверку if / else ниже:\n"
        ),
        "expected_hint": "Используйте if rk_score >= 50: и внутри блока вызовите print('Допуск открыт').",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_4_loops",
        "order_index": 4,
        "title": "4. Циклы (for и while) — автоматизация рутины",
        "language": "python",
        "summary": "Массовая обработка списков групп и подсчёт показателей без копипаста.",
        "ai_theory": (
            "Представь, что тебе нужно проверить оценки у 300 студентов. Вручную это займёт час, а цикл `for` сделает это за миллисекунду!\n\n"
            "• Цикл **`for`** проходит по каждому элементу списка или диапазона `range()`:\n"
            "```python\n"
            "scores = [85, 92, 74, 100]\n"
            "total = 0\n"
            "for s in scores:\n"
            "    total += s\n"
            "print('Сумма баллов:', total)\n"
            "```\n"
            "• Цикл **`while`** повторяет действия, пока условие истинно (например, пока в очереди есть необработанные файлы)."
        ),
        "task_prompt": (
            "Дан список баллов за занятия: `grades = [80, 90, 75, 95]`. "
            "С помощью цикла `for` посчитайте их сумму в переменную `total` и выведите `total` на экран через `print(total)`."
        ),
        "starter_code": (
            "grades = [80, 90, 75, 95]\n"
            "total = 0\n\n"
            "# Пройдитесь циклом for по списку grades и прибавьте каждый балл к total:\n"
        ),
        "expected_hint": "Внутри цикла for g in grades: используйте total += g, а после цикла вызовите print(total).",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_5_lists",
        "order_index": 5,
        "title": "5. Списки (list): хранение и фильтрация коллекций",
        "language": "python",
        "summary": "Добавление элементов (.append), срезы, длина списка len() и генераторы списков.",
        "ai_theory": (
            "**Список (`list`)** — это упорядоченный ряд элементов в квадратных скобках `[...]`. "
            "В BahonIQ списки используются повсюду: список загруженных PDF-файлов, список учебных групп, список найденных статей.\n\n"
            "Главные операции со списком:\n"
            "• `groups.append('ВМ-24-02')` — добавить элемент в конец\n"
            "• `len(groups)` — узнать количество элементов\n"
            "• `groups[0]` — взять первый элемент (нумерация в Python всегда начинается с `0`!)\n"
            "```python\n"
            "modules = ['Tickets', 'Excel AI', 'Platonus Wiki']\n"
            "modules.append('Code Academy')\n"
            "print(len(modules), modules[0])\n"
            "```"
        ),
        "task_prompt": (
            "Дан список систем: `systems = ['Platonus', 'Telegram', 'Gmail']`. "
            "Добавьте в конец списка элемент `'Salem Office'` с помощью метода `.append()`, "
            "а затем выведите количество элементов списка через `print(len(systems))` и сам список."
        ),
        "starter_code": (
            "systems = ['Platonus', 'Telegram', 'Gmail']\n\n"
            "# Добавьте 'Salem Office' и выведите длину и список:\n"
        ),
        "expected_hint": "Вызовите systems.append('Salem Office'), затем print(len(systems), systems).",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_6_dicts",
        "order_index": 6,
        "title": "6. Словари (dict): структура ключ → значение",
        "language": "python",
        "summary": "Основа JSON и API-ответов сервера: быстрый доступ по ключу.",
        "ai_theory": (
            "Если список хранит значения по номерам (`0, 1, 2`), то **словарь (`dict`)** хранит данные по понятным **ключам** в фигурных скобках `{ключ: значение}`.\n\n"
            "Именно так устроены все ответы нашего FastAPI-сервера и карточки сотрудников:\n"
            "```python\n"
            "staff = {\n"
            "    'name': 'Сейтказы Б.',\n"
            "    'dept': 'Департамент IT',\n"
            "    'ext': '104'\n"
            "}\n"
            "print(staff['name'])       # 'Сейтказы Б.'\n"
            "staff['role'] = 'Admin'    # Добавили новый ключ\n"
            "```"
        ),
        "task_prompt": (
            "Дан словарь `ticket = {'id': 42, 'status': 'open'}`. "
            "Измените значение по ключу `'status'` на `'resolved'`, добавьте ключ `'priority'` со значением `'high'` "
            "и выведите словарь `print(ticket)`."
        ),
        "starter_code": (
            "ticket = {'id': 42, 'status': 'open'}\n\n"
            "# Обновите 'status', добавьте 'priority' и выведите ticket:\n"
        ),
        "expected_hint": "Используйте ticket['status'] = 'resolved' и ticket['priority'] = 'high'.",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_7_functions",
        "order_index": 7,
        "title": "7. Функции (def и return): чистая модульная архитектура",
        "language": "python",
        "summary": "Создание переиспользуемых блоков логики с параметрами и возвратом результата.",
        "ai_theory": (
            "**Функция (`def`)** — это именованный рецепт, который принимает ингредиенты (аргументы), выполняет работу и возвращает готовое блюдо через **`return`**.\n\n"
            "В проекте BahonIQ каждая операция — это функция (`ask_wiki(query)`, `generate_ticket(text)`):\n"
            "```python\n"
            "def calc_rating(rk1, rk2):\n"
            "    avg = (rk1 + rk2) / 2\n"
            "    return round(avg, 1)\n\n"
            "result = calc_rating(80, 95)\n"
            "print('Итоговый рейтинг:', result)\n"
            "```\n"
            "Важно: функция должна **возвращать** результат через `return`, чтобы его можно было передать дальше в API или БД."
        ),
        "task_prompt": (
            "Напишите функцию `calc_final_grade(rd, exam)`, которая принимает балл рейтинга допуска `rd` и балл экзамена `exam`, "
            "возвращает итоговую оценку по формуле `rd * 0.6 + exam * 0.4`. "
            "Вызовите `print(calc_final_grade(80, 90))`."
        ),
        "starter_code": (
            "def calc_final_grade(rd, exam):\n"
            "    # Верните результат по формуле rd * 0.6 + exam * 0.4\n"
            "    pass\n\n"
            "print(calc_final_grade(80, 90))\n"
        ),
        "expected_hint": "Замените pass на return rd * 0.6 + exam * 0.4.",
        "file_path": "",
    },
    {
        "stage_id": 1,
        "slug": "py_8_errors_json",
        "order_index": 8,
        "title": "8. Обработка ошибок (try / except) и работа с JSON",
        "language": "python",
        "summary": "Защита сервера от падений и обмен данными в формате JSON.",
        "ai_theory": (
            "В реальном приложении пользователь может загрузить повреждённый файл или ввести текст вместо числа. "
            "Чтобы программа не упала с красной ошибкой, опасный участок оборачивают в блок **`try / except`**:\n\n"
            "```python\n"
            "import json\n\n"
            "raw_data = '{\"module\": \"Wiki\", \"count\": 117}'\n"
            "try:\n"
            "    data = json.loads(raw_data)  # Превращаем JSON-строку в словарь Python\n"
            "    print('Модуль:', data['module'])\n"
            "except Exception as err:\n"
            "    print('Ошибка разбора JSON:', err)\n"
            "```\n"
            "• `json.loads(str)` — читает JSON-строку в Python-объект.\n"
            "• `json.dumps(obj, ensure_ascii=False)` — превращает словарь обратно в JSON-строку."
        ),
        "task_prompt": (
            "Дана JSON-строка `payload = '{\"topic\": \"РК и ведомости\", \"articles\": 21}'`. "
            "Импортируйте модуль `json`, распарсите строку с помощью `json.loads(payload)` в переменную `info` "
            "и выведите значение ключа `'topic'`."
        ),
        "starter_code": (
            "import json\n\n"
            "payload = '{\"topic\": \"РК и ведомости\", \"articles\": 21}'\n"
            "# Распарсите JSON в переменную info и выведите info['topic']:\n"
        ),
        "expected_hint": "Используйте info = json.loads(payload) и print(info['topic']).",
        "file_path": "",
    },

    # ------------------------------------------------------------------------
    # ЭТАП 2: БАЗЫ ДАННЫХ И SQL НА БАЗЕ SQLITE (7 УРОКОВ)
    # ------------------------------------------------------------------------
    {
        "stage_id": 2,
        "slug": "sql_1_tables_rel",
        "order_index": 1,
        "title": "1. Что такое таблицы, первичные ключи (PK) и связи (FK)",
        "language": "sql",
        "summary": "Знакомство с реляционной базой данных SQLite и первыми таблицами.",
        "ai_theory": (
            "База данных **SQLite** — это надёжное хранилище таблиц, которое живёт прямо в одном файле (например, наш `wiki.db` или `phonebook.db`).\n\n"
            "Каждая таблица состоит из:\n"
            "• **Столбцов (полей)** с чётким типом: `INTEGER` (целое число), `TEXT` (текст), `REAL` (дробное число).\n"
            "• **Первичного ключа (`PRIMARY KEY`)** — уникального `id` каждой строки.\n"
            "• **Внешнего ключа (`FOREIGN KEY`)** — ссылки на `id` в другой таблице (например, `topic_id` в статье ссылается на `id` раздела).\n\n"
            "В нашей учебной базе уже созданы таблицы `students`, `departments` и `tickets`. Попробуем заглянуть в таблицу `departments`!"
        ),
        "task_prompt": (
            "Выполните свой первый SQL-запрос: выведите все столбцы и строки из таблицы `departments` "
            "с помощью команды `SELECT * FROM departments;`."
        ),
        "starter_code": "SELECT * FROM departments;\n",
        "expected_hint": "Оставьте или напишите запрос SELECT * FROM departments; и нажмите проверку.",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_2_create_table",
        "order_index": 2,
        "title": "2. Создание таблиц (CREATE TABLE)",
        "language": "sql",
        "summary": "Проектирование собственной таблицы с автоинкрементом и обязательными полями.",
        "ai_theory": (
            "Чтобы создать таблицу в SQLite, используется команда **`CREATE TABLE IF NOT EXISTS`**:\n\n"
            "```sql\n"
            "CREATE TABLE IF NOT EXISTS wiki_topics (\n"
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    name TEXT NOT NULL,\n"
            "    created_at TEXT\n"
            ");\n"
            "```\n"
            "• `PRIMARY KEY AUTOINCREMENT` — база сама назначает номера `1, 2, 3...` каждой новой записи.\n"
            "• `NOT NULL` — запрещает сохранять пустое значение в этом поле."
        ),
        "task_prompt": (
            "Создайте таблицу ` dorm_rooms ` с тремя полями: "
            "`id INTEGER PRIMARY KEY`, `room_number TEXT NOT NULL`, `capacity INTEGER`, "
            "а второй строкой добавьте `SELECT * FROM departments LIMIT 1;` для проверки."
        ),
        "starter_code": (
            "CREATE TABLE IF NOT EXISTS dorm_rooms (\n"
            "    id INTEGER PRIMARY KEY,\n"
            "    room_number TEXT NOT NULL,\n"
            "    capacity INTEGER\n"
            ");\n"
            "SELECT * FROM departments LIMIT 1;\n"
        ),
        "expected_hint": "Используйте CREATE TABLE IF NOT EXISTS dorm_rooms (...).",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_3_insert",
        "order_index": 3,
        "title": "3. Добавление данных (INSERT INTO)",
        "language": "sql",
        "summary": "Запись новых строк в таблицу и мгновенная проверка результата.",
        "ai_theory": (
            "Когда пользователь нажимает «Сохранить контакт» или «Загрузить инструкцию», бэкенд выполняет команду **`INSERT INTO`**:\n\n"
            "```sql\n"
            "INSERT INTO tickets (title, department, priority, status)\n"
            "VALUES ('Не открывается ведомость РК', 'Офис регистратора', 'high', 'open');\n"
            "```\n"
            "Порядок значений в `VALUES (...)` должен строго совпадать с порядком перечисленных столбцов."
        ),
        "task_prompt": (
            "Добавьте новую запись в таблицу `departments` со столбцами `(id, name, building)` "
            "и значениями `(99, 'Центр цифровых технологий', 'Главный корпус')`, "
            "а затем выведите `SELECT * FROM departments WHERE id = 99;`."
        ),
        "starter_code": (
            "INSERT INTO departments (id, name, building)\n"
            "VALUES (99, 'Центр цифровых технологий', 'Главный корпус');\n\n"
            "SELECT * FROM departments WHERE id = 99;\n"
        ),
        "expected_hint": "Убедитесь, что выполнен INSERT INTO departments и следом SELECT.",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_4_select_where_order",
        "order_index": 4,
        "title": "4. Выборка, фильтрация и сортировка (SELECT, WHERE, ORDER BY)",
        "language": "sql",
        "summary": "Точный поиск нужных студентов и заявок по условиям и ранжированию.",
        "ai_theory": (
            "Самая частая операция в любой системе — выборка данных по фильтру:\n\n"
            "• **`WHERE`** — отбирает только те строки, которые подходят под условие (`gpa >= 3.5`, `status = 'open'`).\n"
            "• **`ORDER BY ... DESC`** — сортирует результат по убыванию (`ASC` — по возрастанию).\n"
            "• **`LIMIT`** — ограничивает число возвращаемых строк.\n\n"
            "```sql\n"
            "SELECT full_name, gpa,faculty\n"
            "FROM students\n"
            "WHERE gpa >= 3.5\n"
            "ORDER BY gpa DESC;\n"
            "```"
        ),
        "task_prompt": (
            "Выберите из таблицы `students` всех студентов с `gpa > 3.2` и отсортируйте их по убыванию `gpa` (`ORDER BY gpa DESC`)."
        ),
        "starter_code": (
            "SELECT * FROM students\n"
            "WHERE gpa > 3.2\n"
            "ORDER BY gpa DESC;\n"
        ),
        "expected_hint": "Используйте WHERE gpa > 3.2 и ORDER BY gpa DESC.",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_5_update_delete",
        "order_index": 5,
        "title": "5. Обновление и удаление записей (UPDATE и DELETE)",
        "language": "sql",
        "summary": "Безопасное изменение статусов и удаление устаревших строк с обязательным WHERE.",
        "ai_theory": (
            "Для изменения существующих данных служит **`UPDATE`**, а для удаления — **`DELETE FROM`**.\n\n"
            "Главное золотое правило разработчика: **всегда пиши `WHERE`!** Без `WHERE` команда изменит или удалит вообще все строки таблицы.\n\n"
            "```sql\n"
            "-- Закрываем конкретный тикет по его id:\n"
            "UPDATE tickets SET status = 'closed' WHERE id = 1;\n\n"
            "-- Удаляем черновик по id:\n"
            "DELETE FROM tickets WHERE id = 999;\n"
            "```"
        ),
        "task_prompt": (
            "Обновите в таблице `tickets` статус на `'closed'` для заявки с `id = 1` (`UPDATE tickets SET status = 'closed' WHERE id = 1;`), "
            "а затем выведите `SELECT * FROM tickets WHERE id = 1;`."
        ),
        "starter_code": (
            "UPDATE tickets SET status = 'closed' WHERE id = 1;\n"
            "SELECT * FROM tickets WHERE id = 1;\n"
        ),
        "expected_hint": "Не забудьте указать WHERE id = 1 в команде UPDATE.",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_6_count_groupby",
        "order_index": 6,
        "title": "6. Агрегация и аналитика (COUNT, AVG, GROUP BY)",
        "language": "sql",
        "summary": "Подсчёт статистики по факультетам и отделам одним запросом.",
        "ai_theory": (
            "Когда в шапке Platonus Wiki AI ты видишь `Разделов: 6 • Инструкций: 117`, эту сводку считает SQL-агрегация:\n\n"
            "• `COUNT(*)` — считает количество строк\n"
            "• `AVG(gpa)` — считает среднее значение\n"
            "• `GROUP BY` — группирует строки по категории (например, по факультету или статусу заявки)\n\n"
            "```sql\n"
            "SELECT status, COUNT(*) AS total\n"
            "FROM tickets\n"
            "GROUP BY status;\n"
            "```"
        ),
        "task_prompt": (
            "Посчитайте количество заявок по каждому статусу в таблице `tickets`: "
            "выберите `status, COUNT(*) AS count` из `tickets` с группировкой `GROUP BY status`."
        ),
        "starter_code": (
            "SELECT status, COUNT(*) AS count\n"
            "FROM tickets\n"
            "GROUP BY status;\n"
        ),
        "expected_hint": "Используйте SELECT status, COUNT(*) AS count FROM tickets GROUP BY status;",
        "file_path": "",
    },
    {
        "stage_id": 2,
        "slug": "sql_7_python_sqlite3",
        "order_index": 7,
        "title": "7. Подключение к SQLite из Python (модуль sqlite3)",
        "language": "python",
        "summary": "Как Python-бэкенд выполняет SQL-запросы с защитой от SQL-инъекций.",
        "ai_theory": (
            "Теперь соединим Этап 1 (Python) и Этап 2 (SQL)! В Python встроен модуль **`sqlite3`**, который позволяет управлять базой прямо из кода:\n\n"
            "```python\n"
            "import sqlite3\n\n"
            "conn = sqlite3.connect(':memory:')  # База в оперативной памяти\n"
            "conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)')\n"
            "# Знак ? защищает от SQL-инъекций:\n"
            "conn.execute('INSERT INTO users (name) VALUES (?)', ('Алия',))\n"
            "rows = conn.execute('SELECT id, name FROM users').fetchall()\n"
            "print(rows)\n"
            "```\n"
            "Именно так работают все сервисы BahonIQ Work Center!"
        ),
        "task_prompt": (
            "Запустите и проверьте Python-скрипт, который создаёт таблицу `modules` в SQLite, "
            "добавляет туда запись `('Platonus Wiki AI', 117)` через параметризованный запрос `?` и выводит результат через `print(rows)`."
        ),
        "starter_code": (
            "import sqlite3\n\n"
            "conn = sqlite3.connect(':memory:')\n"
            "conn.execute('CREATE TABLE modules (title TEXT, articles INTEGER)')\n"
            "conn.execute('INSERT INTO modules VALUES (?, ?)', ('Platonus Wiki AI', 117))\n"
            "rows = conn.execute('SELECT * FROM modules').fetchall()\n"
            "print(rows)\n"
        ),
        "expected_hint": "Запустите код и нажмите «Проверить с ментором».",
        "file_path": "",
    },

    # ------------------------------------------------------------------------
    # ЭТАП 3: АРХИТЕКТУРА BAHONIQ WORK CENTER + PDF-КНИГА «ОТ А ДО Я» (6 УРОКОВ)
    # ------------------------------------------------------------------------
    {
        "stage_id": 3,
        "slug": "arch_1_entrypoints",
        "order_index": 1,
        "title": "1. Точка входа: main.py, launcher.pyw и запуск BahonIQ",
        "language": "python",
        "summary": "Как стартует приложение, инициализируется окружение и перехватываются ошибки.",
        "ai_theory": (
            "Добро пожаловать на **Этап 3 — Архитектура нашего проекта BahonIQ Work Center**!\n\n"
            "Любая профессиональная система начинается с единой точки входа:\n"
            "• **`main.py` и `launcher.pyw`** — отвечают за запуск десктопного приложения (`BahonIQ.exe`), настройку путей `sys.path`, показ Splash-экрана и запись логов ошибок.\n"
            "• **`run_web.py` и `web_app/server.py`** — запускают ASGI-сервер Uvicorn + FastAPI для веб-версии и облака Render.\n\n"
            "Ниже вы можете изучить реальную структуру и выполнить проверку конфигурации проекта."
        ),
        "task_prompt": (
            "Изучите, как в Python определяется корневая папка проекта с помощью `pathlib.Path`. "
            "Напишите код, который создаёт объект `root = Path('/app/bahoniq')`, добавляет к нему подпапку `data_dir = root / 'data'` и выводит `print(data_dir)`."
        ),
        "starter_code": (
            "from pathlib import Path\n\n"
            "root = Path('/app/bahoniq')\n"
            "data_dir = root / 'data'\n"
            "print('Путь к данным:', data_dir)\n"
        ),
        "expected_hint": "Используйте оператор / объекта Path для объединения путей.",
        "file_path": "main.py",
    },
    {
        "stage_id": 3,
        "slug": "arch_2_fastapi_server",
        "order_index": 2,
        "title": "2. Устройство FastAPI-сервера и маршрутов (web_app/server.py)",
        "language": "python",
        "summary": "Как устроены декораторы @app.get / @app.post, CORS и асинхронный пул потоков.",
        "ai_theory": (
            "Сердце веб-платформы BahonIQ — файл **`web_app/server.py`** на фреймворке **FastAPI**.\n\n"
            "Как происходит обработка любого клика в браузере:\n"
            "1. Фронтенд отправляет `fetch('/api/wiki/ask', { method: 'POST', body: ... })`.\n"
            "2. FastAPI находит функцию с декоратором `@app.post('/api/wiki/ask')`.\n"
            "3. Чтобы тяжёлые задачи (чтение PDF или запрос в ИИ) не блокировали других пользователей, сервер вызывает `await run_in_threadpool(...)`.\n"
            "4. Функция возвращает обычный Python-словарь `dict`, который FastAPI автоматически превращает в `JSONResponse`."
        ),
        "task_prompt": (
            "Смоделируем работу обработчика маршрута FastAPI: напишите функцию `handle_health_check()`, "
            "которая возвращает словарь `{'status': 'ok', 'app': 'BahonIQ Work Center', 'version': '2.0.0'}`, и выведите результат её вызова."
        ),
        "starter_code": (
            "def handle_health_check():\n"
            "    return {\n"
            "        'status': 'ok',\n"
            "        'app': 'BahonIQ Work Center',\n"
            "        'version': '2.0.0'\n"
            "    }\n\n"
            "print(handle_health_check())\n"
        ),
        "expected_hint": "Функция должна возвращать словарь со статусом ok.",
        "file_path": "web_app/server.py",
    },
    {
        "stage_id": 3,
        "slug": "arch_3_ai_service",
        "order_index": 3,
        "title": "3. Единое ИИ-ядро проекта (ai_service.py и Gemini Flash 24/7)",
        "language": "python",
        "summary": "Как BahonIQ общается с Google Gemini Flash API, передаёт системные промпты и стримит ответы.",
        "ai_theory": (
            "Все умные модули нашего проекта (Ticket Writer AI, Excel AI, Analytics AI, Platonus Wiki AI и сам ИИ-ментор Academy) "
            "используют единый модуль **`ai_service.py`**.\n\n"
            "Почему это лучшая практика архитектуры (принцип DRY — *Don't Repeat Yourself*):\n"
            "• Ключ `GEMINI_API_KEY` из `.env` читается и инициализируется в одном месте (`get_gemini_client()`).\n"
            "• Функция `generate_text(prompt, system_instruction, temperature)` автоматически перебирает доступные модели семейства Gemini Flash при пиковых нагрузках.\n"
            "• Ни один модуль не зависит от деталей низкоуровневого HTTP-клиента."
        ),
        "task_prompt": (
            "Напишите функцию `build_mentor_prompt(topic, question)`, которая формирует структурированный промпт "
            "с помощью f-строки: `'Тема: <topic> | Вопрос: <question>'` и возвращает его. Выведите результат."
        ),
        "starter_code": (
            "def build_mentor_prompt(topic, question):\n"
            "    return f'Тема: {topic} | Вопрос: {question}'\n\n"
            "print(build_mentor_prompt('Архитектура ИИ', 'Как работает Gemini Flash?'))\n"
        ),
        "expected_hint": "Верните отформатированную f-строку и выведите её через print().",
        "file_path": "ai_service.py",
    },
    {
        "stage_id": 3,
        "slug": "arch_4_sqlite_layer",
        "order_index": 4,
        "title": "4. Архитектура хранения данных (wiki.db, phonebook.db, academy.db)",
        "language": "python",
        "summary": "Потокобезопасная работа с SQLite, внешние ключи и зеркалирование в JSON для облака.",
        "ai_theory": (
            "В проекте BahonIQ базы данных лежат в папке **`web_app/data/`**:\n"
            "• `wiki.db` (`wiki_topics` + `wiki_articles` — 117 инструкций Platonus)\n"
            "• `phonebook.db` (телефонный справочник сотрудников)\n"
            "• `academy.db` (этапы, уроки и ваш прогресс обучения)\n\n"
            "Для защиты от одновременной записи используется `threading.Lock()`, `conn.row_factory = sqlite3.Row` (позволяет обращаться к полям по имени `row['title']`) "
            "и автоматический JSON-снимок (`wiki_seed.json`), чтобы при любом редеплое на Render база мгновенно восстанавливалась без потерь."
        ),
        "task_prompt": (
            "Проверьте работу `sqlite3.Row`: выполните скрипт, который включает `conn.row_factory = sqlite3.Row`, "
            "превращает строку БД в обычный словарь `dict(row)` и выводит его на экран."
        ),
        "starter_code": (
            "import sqlite3\n\n"
            "conn = sqlite3.connect(':memory:')\n"
            "conn.row_factory = sqlite3.Row\n"
            "conn.execute('CREATE TABLE topics (id INT, name TEXT)')\n"
            "conn.execute('INSERT INTO topics VALUES (1, \"Журнал и РК\")')\n"
            "row = conn.execute('SELECT * FROM topics').fetchone()\n"
            "print(dict(row))\n"
        ),
        "expected_hint": "Запустите скрипт и нажмите «Проверить с ментором».",
        "file_path": "web_app/modules/wiki/service.py",
    },
    {
        "stage_id": 3,
        "slug": "arch_5_frontend_spa",
        "order_index": 5,
        "title": "5. Фронтенд без тяжёлых фреймворков (index.html, app.css, app.js)",
        "language": "python",
        "summary": "Как устроена SPA-навигация между модулями, темная тема и обмен с бэкендом через fetch.",
        "ai_theory": (
            "Фронтенд BahonIQ построен по принципу **Zero-Overhead SPA** на чистом HTML5, CSS Variables и модульном JavaScript (`web_app/static/`):\n\n"
            "• **`index.html`** — содержит дашборд (`#dashboardView`) и секции модулей (`<section class='module-page' id='...'>`).\n"
            "• **`app.css`** — управляет темами через CSS-переменные (`:root` для тёмной темы и `body.theme-day` для дневной темы Soft Mist).\n"
            "• **`app.js`** — переключает модули функцией `openModule(modId)`, сохраняет тему в `localStorage` и общается с FastAPI через асинхронный `fetch('/api/...')`."
        ),
        "task_prompt": (
            "Смоделируем сборку ответа API для фронтенда: создайте словарь `ui_state` с ключами "
            "`'theme': 'night'`, `'active_module': 'academy'` и `'completed_lessons': 15`, преобразуйте его в JSON-строку и выведите."
        ),
        "starter_code": (
            "import json\n\n"
            "ui_state = {\n"
            "    'theme': 'night',\n"
            "    'active_module': 'academy',\n"
            "    'completed_lessons': 15\n"
            "}\n"
            "print(json.dumps(ui_state, ensure_ascii=False))\n"
        ),
        "expected_hint": "Выведите JSON-строку с помощью print(json.dumps(...)).",
        "file_path": "web_app/static/app.js",
    },
    {
        "stage_id": 3,
        "slug": "arch_6_deploy_render",
        "order_index": 6,
        "title": "6. Деплой 24/7 на Render, GitHub-пайплайн и генерация PDF-книги",
        "language": "python",
        "summary": "Как обновления из Git попадают в облако Render и как генерируется PDF-книга «От А до Я».",
        "ai_theory": (
            "Финальное звено архитектуры — непрерывное развёртывание (**CI/CD**):\n\n"
            "1. Вы вносите изменения или загружаете новые данные и выполняете `git push origin main`.\n"
            "2. Облачная платформа **Render** автоматически подхватывает свежий коммит из GitHub, устанавливает зависимости из `requirements_web.txt` и перезапускает сервис 24/7.\n"
            "3. И веб-версия (`bahoniq.onrender.com`), и мобильная PWA, и десктоп работают с единой актуальной кодовой базой.\n\n"
            "**Не забудьте нажать кнопку «📘 Сгенерировать мою PDF-книгу (От А до Я)» в верхней панели!** Бэкенд прочитает реальные файлы проекта и соберёт для вас полноценный персональный учебник в PDF."
        ),
        "task_prompt": (
            "Напишите финальную проверку готовности к деплою: функцию `check_deploy_ready(tests_passed, env_configured)`, "
            "которая возвращает `'Готов к деплою на Render!'`, если оба параметра `True`, и вызовите её."
        ),
        "starter_code": (
            "def check_deploy_ready(tests_passed, env_configured):\n"
            "    if tests_passed and env_configured:\n"
            "        return 'Готов к деплою на Render!'\n"
            "    return 'Требуется проверка'\n\n"
            "print(check_deploy_ready(True, True))\n"
        ),
        "expected_hint": "Вызовите print(check_deploy_ready(True, True)).",
        "file_path": "run_web.py",
    },

    # ------------------------------------------------------------------------
    # ЭТАП 4: БОЕВОЙ ПОЛИГОН — БАЗА ТЕСТОВ И СКВОЗНОЙ ПРАКТИКИ (8 ИСПЫТАНИЙ)
    # ------------------------------------------------------------------------
    {
        "stage_id": 4,
        "slug": "poly_1_bug_gpa",
        "order_index": 1,
        "title": "Испытание 1 [Найди баг]: Ошибка расчёта среднего балла РК",
        "language": "python",
        "summary": "Отладка логической ошибки приоритета операторов в формуле расчёта рейтинга.",
        "ai_theory": (
            "**Боевой полигон — Испытание 1 (Поиск бага):**\n\n"
            "Молодой разработчик написал функцию расчёта среднего балла двух рубежных контролей `rk1 = 80` и `rk2 = 90`, "
            "но вместо `85.0` функция выдаёт `125.0`! Найдите и исправьте логическую ошибку в формуле."
        ),
        "task_prompt": (
            "Исправьте ошибку в функции `average_rk(rk1, rk2)`, чтобы для `(80, 90)` она возвращала правильное среднее `85.0`, и выведите результат."
        ),
        "starter_code": (
            "# ВНИМАНИЕ: В коде ниже спрятан баг! Исправьте его:\n"
            "def average_rk(rk1, rk2):\n"
            "    return rk1 + rk2 / 2\n\n"
            "print(average_rk(80, 90))  # Должно вывести 85.0\n"
        ),
        "expected_hint": "Деление выполняется раньше сложения! Возьмите (rk1 + rk2) в круглые скобки.",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_2_ticket_router",
        "order_index": 2,
        "title": "Испытание 2 [Мини-проект]: Авто-маршрутизатор заявок техподдержки",
        "language": "python",
        "summary": "Написание функции классификации тикетов по ключевым словам (как в Ticket Writer AI).",
        "ai_theory": (
            "**Боевой полигон — Испытание 2 (API-логика):**\n\n"
            "В техническую поддержку университета приходят сотни сообщений. Нам нужно автоматически направлять их в нужный отдел по ключевым словам."
        ),
        "task_prompt": (
            "Напишите функцию `route_ticket(text)`:\n"
            "• Если в `text.lower()` есть слово `'пароль'` — верните `'IT-отдел'`\n"
            "• Если есть слово `'ведомость'` или `'рк'` — верните `'Офис регистратора'`\n"
            "• Иначе верните `'Общая поддержка'`.\n"
            "Проверьте функцию вызовом `print(route_ticket('Закрылась ведомость РК-1'))`."
        ),
        "starter_code": (
            "def route_ticket(text):\n"
            "    low = text.lower()\n"
            "    # Напишите логику маршрутизации:\n"
            "    pass\n\n"
            "print(route_ticket('Закрылась ведомость РК-1'))\n"
        ),
        "expected_hint": "Используйте if 'пароль' in low: ... elif 'ведомость' in low or 'рк' in low: ...",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_3_sql_debtors",
        "order_index": 3,
        "title": "Испытание 3 [SQL-практикум]: Отчёт деканата по группе риска",
        "language": "sql",
        "summary": "Составление сложного SQL-запроса с несколькими условиями фильтрации и сортировкой.",
        "ai_theory": (
            "**Боевой полигон — Испытание 3 (SQL для деканата):**\n\n"
            "Деканат запросил список студентов, которым требуется академическая поддержка. "
            "Используйте оператор `AND` или `ORDER BY` для точной выборки из таблицы `students`."
        ),
        "task_prompt": (
            "Напишите SQL-запрос к таблице `students`: выберите все поля для студентов, у которых `gpa < 3.0`, "
            "и отсортируйте список по возрастанию балла (`ORDER BY gpa ASC`)."
        ),
        "starter_code": (
            "-- Напишите SQL-запрос для отбора студентов с gpa < 3.0:\n"
            "SELECT * FROM students\n"
        ),
        "expected_hint": "Добавьте WHERE gpa < 3.0 ORDER BY gpa ASC;",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_4_bug_sql_injection",
        "order_index": 4,
        "title": "Испытание 4 [Найди баг]: Защита поиска от падения и пустых строк",
        "language": "python",
        "summary": "Очистка пользовательского ввода (.strip()) и валидация перед запросом к БД.",
        "ai_theory": (
            "**Боевой полигон — Испытание 4 (Валидация API):**\n\n"
            "В функции поиска `validate_query(q)` забыли очистить строку от пробелов `.strip()`, из-за чего запрос из одних пробелов `'   '` проходит в базу данных."
        ),
        "task_prompt": (
            "Исправьте функцию `validate_query(q)`: очистите строку через `.strip()`. "
            "Если после очистки строка пустая — верните `'Ошибка: пустой запрос'`, иначе верните `f'Поиск: {clean_q}'`. "
            "Выведите результат для `'   '` и `'  РК-1  '`."
        ),
        "starter_code": (
            "def validate_query(q):\n"
            "    clean_q = q.strip()\n"
            "    # Добавьте проверку на пустую строку:\n"
            "    return f'Поиск: {clean_q}'\n\n"
            "print(validate_query('   '))\n"
            "print(validate_query('  РК-1  '))\n"
        ),
        "expected_hint": "Добавьте if not clean_q: return 'Ошибка: пустой запрос' перед основным return.",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_5_reconcile_iin",
        "order_index": 5,
        "title": "Испытание 5 [Алгоритмы BahonIQ]: Сверка списков студентов по ИИН",
        "language": "python",
        "summary": "Реализация реального алгоритма модуля Excel AI — поиск расхождений между двумя базами.",
        "ai_theory": (
            "**Боевой полигон — Испытание 5 (Алгоритм Excel AI):**\n\n"
            "Одно из главных умений модуля Excel AI в BahonIQ — мгновенно находить студентов, которые есть в списке деканата, "
            "но ещё не зарегистрированы в базе Platonus. В Python для этого идеально подходят множества (`set`) и операция вычитания `-`!"
        ),
        "task_prompt": (
            "Даны два списка ИИН: `dean_list` и `platonus_list`. "
            "Найдите ИИН студентов, которые есть в `dean_list`, но отсутствуют в `platonus_list`, "
            "и выведите отсортированный список недостающих ИИН."
        ),
        "starter_code": (
            "dean_list = ['040101500111', '040202500222', '040303500333']\n"
            "platonus_list = ['040101500111', '040303500333']\n\n"
            "# Найдите разницу через set() и выведите результат:\n"
            "missing = sorted(set(dean_list) - set(platonus_list))\n"
            "print('Не найдены в Platonus:', missing)\n"
        ),
        "expected_hint": "Запустите код и проверьте, что найден ИИН '040202500222'.",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_6_sqlite_wiki_search",
        "order_index": 6,
        "title": "Испытание 6 [Python + SQLite]: Мини-движок базы знаний Wiki",
        "language": "python",
        "summary": "Создание таблицы статей, наполнение и поиск по ключевому слову через LIKE.",
        "ai_theory": (
            "**Боевой полигон — Испытание 6 (Сквозная задача Python + SQLite):**\n\n"
            "Соберём в миниатюре поисковый движок Platonus Wiki AI! Используем оператор `LIKE '%слово%'` для поиска инструкций в таблице SQLite."
        ),
        "task_prompt": (
            "Допишите SQL-запрос внутри `conn.execute(...)`, чтобы найти все статьи из таблицы `wiki`, "
            "где `title LIKE '%РК%'`, и выведите найденные строки через `print(found)`."
        ),
        "starter_code": (
            "import sqlite3\n\n"
            "conn = sqlite3.connect(':memory:')\n"
            "conn.execute('CREATE TABLE wiki (id INT, title TEXT)')\n"
            "conn.executemany('INSERT INTO wiki VALUES (?, ?)', [\n"
            "    (1, 'Сведения об общежитиях'),\n"
            "    (2, 'Закрытие ведомостей РК-1 и РК-2'),\n"
            "    (3, 'Загрузка силлабуса УМКД')\n"
            "])\n\n"
            "found = conn.execute(\"SELECT * FROM wiki WHERE title LIKE '%РК%'\").fetchall()\n"
            "print(found)\n"
        ),
        "expected_hint": "Запустите код и убедитесь, что возвращена статья №2 про РК-1 и РК-2.",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_7_json_api_report",
        "order_index": 7,
        "title": "Испытание 7 [Аналитика + JSON]: Генератор сводного отчёта по отделам",
        "language": "python",
        "summary": "Группировка данных словарём в Python и выгрузка готового JSON-отчёта.",
        "ai_theory": (
            "**Боевой полигон — Испытание 7 (Backend Analytics):**\n\n"
            "Перед отправкой данных на фронтенд сервер часто группирует записи и считает итоги в словарь."
        ),
        "task_prompt": (
            "Дан список оценок студентов `scores = [95, 42, 78, 88, 35, 91]`. "
            "Сформируйте словарь `report = {'passed': ..., 'failed': ...}`, где `'passed'` — количество оценок `>= 50`, "
            "а `'failed'` — количество оценок `< 50`. Выведите словарь в формате JSON."
        ),
        "starter_code": (
            "import json\n\n"
            "scores = [95, 42, 78, 88, 35, 91]\n"
            "passed = len([s for s in scores if s >= 50])\n"
            "failed = len([s for s in scores if s < 50])\n"
            "report = {'passed': passed, 'failed': failed}\n"
            "print(json.dumps(report))\n"
        ),
        "expected_hint": "Проверьте, что passed равен 4, а failed равен 2.",
        "file_path": "",
    },
    {
        "stage_id": 4,
        "slug": "poly_8_final_exam",
        "order_index": 8,
        "title": "Испытание 8 [Финальный экзамен]: Полный цикл API + SQLite + JSON",
        "language": "python",
        "summary": "Итоговая комплексная задача, объединяющая Python, функции, SQLite и JSON-ответ.",
        "ai_theory": (
            "**Финальный экзамен BahonIQ Academy!**\n\n"
            "В этой задаче вы объедините все 3 этапа:\n"
            "1. Функции и словари Python (Этап 1)\n"
            "2. Таблицы и SQL-запросы SQLite (Этап 2)\n"
            "3. Формирование структурированного JSON-ответа сервера (Этап 3)."
        ),
        "task_prompt": (
            "Напишите и запустите функцию `get_top_students_json()`, которая создаёт в памяти таблицу `students`, "
            "добавляет 3 студентов, выбирает через `SELECT` тех, у кого `gpa >= 3.5`, и возвращает JSON-строку со списком их имён."
        ),
        "starter_code": (
            "import json\n"
            "import sqlite3\n\n"
            "def get_top_students_json():\n"
            "    conn = sqlite3.connect(':memory:')\n"
            "    conn.execute('CREATE TABLE students (name TEXT, gpa REAL)')\n"
            "    conn.executemany('INSERT INTO students VALUES (?, ?)', [\n"
            "        ('Алия', 3.9),\n"
            "        ('Данияр', 2.8),\n"
            "        ('Тимур', 3.7)\n"
            "    ])\n"
            "    rows = conn.execute('SELECT name FROM students WHERE gpa >= 3.5').fetchall()\n"
            "    names = [r[0] for r in rows]\n"
            "    return json.dumps({'top_students': names}, ensure_ascii=False)\n\n"
            "print(get_top_students_json())\n"
        ),
        "expected_hint": "Запустите код и отправьте решение ментору для завершения курса!",
        "file_path": "",
    },
]


def _get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_academy_db() -> None:
    """Создаёт таблицы курсов, уроков и прогресса пользователя в SQLite."""
    with _db_lock:
        conn = _get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS academy_stages (
                    id INTEGER PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT NOT NULL,
                    order_index INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS academy_lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage_id INTEGER NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    order_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    ai_theory TEXT NOT NULL,
                    task_prompt TEXT NOT NULL,
                    starter_code TEXT NOT NULL,
                    expected_hint TEXT DEFAULT '',
                    file_path TEXT DEFAULT '',
                    FOREIGN KEY (stage_id) REFERENCES academy_stages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS academy_progress (
                    lesson_id INTEGER PRIMARY KEY,
                    completed INTEGER DEFAULT 0,
                    user_code TEXT DEFAULT '',
                    mentor_feedback TEXT DEFAULT '',
                    completed_at TEXT DEFAULT '',
                    FOREIGN KEY (lesson_id) REFERENCES academy_lessons(id) ON DELETE CASCADE
                );
                """
            )
            for st in STAGES_SEED:
                conn.execute(
                    """
                    INSERT INTO academy_stages (id, slug, title, subtitle, order_index)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        slug = excluded.slug,
                        title = excluded.title,
                        subtitle = excluded.subtitle,
                        order_index = excluded.order_index
                    """,
                    (st["id"], st["slug"], st["title"], st["subtitle"], st["order_index"]),
                )

            existing_count = conn.execute("SELECT COUNT(*) AS c FROM academy_lessons").fetchone()["c"]
            if existing_count < len(LESSONS_SEED):
                for idx, les in enumerate(LESSONS_SEED, start=1):
                    conn.execute(
                        """
                        INSERT INTO academy_lessons (
                            id, stage_id, slug, order_index, title, language, summary,
                            ai_theory, task_prompt, starter_code, expected_hint, file_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(slug) DO UPDATE SET
                            stage_id = excluded.stage_id,
                            order_index = excluded.order_index,
                            title = excluded.title,
                            language = excluded.language,
                            summary = excluded.summary,
                            task_prompt = excluded.task_prompt,
                            starter_code = excluded.starter_code,
                            expected_hint = excluded.expected_hint,
                            file_path = excluded.file_path
                        """,
                        (
                            idx,
                            les["stage_id"],
                            les["slug"],
                            les["order_index"],
                            les["title"],
                            les["language"],
                            les["summary"],
                            les["ai_theory"],
                            les["task_prompt"],
                            les["starter_code"],
                            les["expected_hint"],
                            les["file_path"],
                        ),
                    )
            conn.commit()
        finally:
            conn.close()


def get_conn_lessons_all() -> list[dict[str, Any]]:
    """Возвращает полный список всех уроков со всеми полями для сборки PDF-книги."""
    init_academy_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.user_code, '') AS user_code
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_progress p ON p.lesson_id = l.id
            ORDER BY l.stage_id ASC, l.order_index ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_roadmap_data() -> dict[str, Any]:
    """Возвращает полную карту 4 этапов, все уроки и статистику прогресса."""
    init_academy_db()
    conn = _get_conn()
    try:
        stages_rows = conn.execute(
            "SELECT * FROM academy_stages ORDER BY order_index ASC"
        ).fetchall()
        lessons_rows = conn.execute(
            """
            SELECT l.id, l.stage_id, l.slug, l.order_index, l.title, l.language,
                   l.summary, l.file_path,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.completed_at, '') AS completed_at
            FROM academy_lessons l
            LEFT JOIN academy_progress p ON p.lesson_id = l.id
            ORDER BY l.stage_id ASC, l.order_index ASC
            """
        ).fetchall()
    finally:
        conn.close()

    by_stage: dict[int, list[dict[str, Any]]] = {}
    total_lessons = 0
    completed_lessons = 0

    for row in lessons_rows:
        item = dict(row)
        item["completed"] = bool(item["completed"])
        total_lessons += 1
        if item["completed"]:
            completed_lessons += 1
        by_stage.setdefault(item["stage_id"], []).append(item)

    stages_out = []
    for st in stages_rows:
        st_dict = dict(st)
        st_lessons = by_stage.get(st["id"], [])
        st_done = sum(1 for x in st_lessons if x["completed"])
        st_total = len(st_lessons)
        st_dict["lessons"] = st_lessons
        st_dict["total_lessons"] = st_total
        st_dict["completed_lessons"] = st_done
        st_dict["percent"] = round((st_done / st_total) * 100) if st_total else 0
        stages_out.append(st_dict)

    overall_percent = round((completed_lessons / total_lessons) * 100) if total_lessons else 0
    return {
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "overall_percent": overall_percent,
        "stages": stages_out,
    }


def get_lesson_by_id(lesson_id: int) -> dict[str, Any] | None:
    """Возвращает полный урок вместе с прогрессом пользователя и (для Этапа 3) реальным кодом файла проекта."""
    init_academy_db()
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.user_code, '') AS user_code,
                   COALESCE(p.mentor_feedback, '') AS mentor_feedback
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_progress p ON p.lesson_id = l.id
            WHERE l.id = ?
            """,
            (lesson_id,),
        ).fetchone()
        if not row:
            return None

        next_row = conn.execute(
            """
            SELECT id, title, stage_id FROM academy_lessons
            WHERE (stage_id = ? AND order_index > ?)
               OR (stage_id > ?)
            ORDER BY stage_id ASC, order_index ASC
            LIMIT 1
            """,
            (row["stage_id"], row["order_index"], row["stage_id"]),
        ).fetchone()
    finally:
        conn.close()

    data = dict(row)
    data["completed"] = bool(data["completed"])
    data["next_lesson_id"] = int(next_row["id"]) if next_row else None
    data["next_lesson_title"] = next_row["title"] if next_row else ""

    # Если это урок Этапа 3 с привязкой к реальному файлу репозитория — подгружаем фрагмент живого кода!
    repo_source = ""
    if data.get("file_path"):
        target = PROJECT_ROOT / data["file_path"]
        if target.is_file():
            try:
                raw = target.read_text(encoding="utf-8", errors="replace")
                lines = raw.splitlines()[:95]
                repo_source = "\n".join(lines)
            except Exception:
                repo_source = ""
    data["repo_source_preview"] = repo_source
    return data


def save_lesson_theory(lesson_id: int, ai_theory: str) -> None:
    """Кэширует сгенерированную ИИ-ментором теорию в БД."""
    init_academy_db()
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE academy_lessons SET ai_theory = ? WHERE id = ?",
                (ai_theory.strip(), lesson_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_conn_lessons_all() -> list[dict[str, Any]]:
    """Возвращает полный список всех уроков со всеми полями для сборки PDF-книги."""
    init_academy_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.user_code, '') AS user_code
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_progress p ON p.lesson_id = l.id
            ORDER BY l.stage_id ASC, l.order_index ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_user_attempt(lesson_id: int, user_code: str, mentor_feedback: str, passed: bool) -> None:
    """Сохраняет код пользователя, разбор от ментора и отмечает урок пройденным при успешной проверке."""
    init_academy_db()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = _get_conn()
        try:
            existing = conn.execute(
                "SELECT completed FROM academy_progress WHERE lesson_id = ?",
                (lesson_id,),
            ).fetchone()
            already_completed = bool(existing["completed"]) if existing else False
            final_completed = 1 if (passed or already_completed) else 0

            conn.execute(
                """
                INSERT INTO academy_progress (lesson_id, completed, user_code, mentor_feedback, completed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lesson_id) DO UPDATE SET
                    completed = ?,
                    user_code = excluded.user_code,
                    mentor_feedback = excluded.mentor_feedback,
                    completed_at = CASE WHEN ? = 1 THEN excluded.completed_at ELSE academy_progress.completed_at END
                """,
                (
                    lesson_id,
                    final_completed,
                    user_code,
                    mentor_feedback,
                    now_iso if final_completed else "",
                    final_completed,
                    final_completed,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_conn_lessons_all() -> list[dict[str, Any]]:
    """Возвращает полный список всех уроков со всеми полями для сборки PDF-книги."""
    init_academy_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT l.*, s.title AS stage_title,
                   COALESCE(p.completed, 0) AS completed,
                   COALESCE(p.user_code, '') AS user_code
            FROM academy_lessons l
            JOIN academy_stages s ON s.id = l.stage_id
            LEFT JOIN academy_progress p ON p.lesson_id = l.id
            ORDER BY l.stage_id ASC, l.order_index ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
