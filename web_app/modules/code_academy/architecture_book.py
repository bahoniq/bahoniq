"""Source-grounded reader for the BahonIQ project. No project source is bundled."""
import json
from dataclasses import dataclass
from pathlib import Path
from .architecture import read_project_file

@dataclass(frozen=True)
class Chapter:
    title: str
    file: str
    anchor: str
    explanation: str
    exercise: str
    section: str = ''
    kind: str = 'symbol'

CATALOG = Path(__file__).with_name('book_catalog.json')

def load_chapters():
    """A finite book about the exact layered app opened in App Builder."""
    specs=(
      ('01. Карта приложения','README.md','', 'Сначала увидим весь маршрут данных: UI → API → Service → Repository → SQLite.', 'Нарисуй направление вызовов и объясни, почему SQL не находится в UI.','I · Общая картина','file'),
      ('02. Точка входа','main.py','def main', 'main.py ничего не знает о кнопках и SQL: он создаёт Application и запускает программу.', 'Объясни защиту if __name__ == "__main__".','I · Общая картина','symbol'),
      ('03. Сборка зависимостей','app/application.py','class Application', 'Application — композиционный корень. Здесь создаются настройки, repository, service, API и окно.', 'Проследи порядок создания объектов и назови зависимость каждого.','I · Общая картина','symbol'),
      ('04. Настройки','settings.py','class Settings', 'Settings хранит изменяемые параметры отдельно от логики и делает их типизированными и неизменяемыми.', 'Добавь безопасную настройку имени базы и объясни frozen=True.','II · Данные и правила','symbol'),
      ('05. Модель Task','models/task.py','class Task', 'Task описывает данные предметной области и не зависит от интерфейса или SQLite.', 'Добавь created_at и реши, какой тип ему нужен.','II · Данные и правила','symbol'),
      ('06. Сериализация модели','models/task.py','def to_dict', 'to_dict превращает модель в контракт для API и интерфейса.', 'Объясни, почему UI получает словарь, а repository работает с Task.','II · Данные и правила','symbol'),
      ('07. Сервис: список','services/task_service.py','def list_tasks', 'Service является центром бизнес-правил и работает через абстракцию repository.', 'Добавь сортировку без Tkinter и SQL в методе.','II · Данные и правила','symbol'),
      ('08. Сервис: создание','services/task_service.py','def create_task', 'Перед сохранением сервис очищает и проверяет данные.', 'Добавь правило максимальной длины и три теста.','II · Данные и правила','symbol'),
      ('09. Сервис: завершение','services/task_service.py','def complete_task', 'Сервис различает отсутствие записи и допустимое изменение состояния.', 'Запрети повторное завершение и выбери тип ошибки.','II · Данные и правила','symbol'),
      ('10. API-контракт','api/task_api.py','class TaskAPI', 'API даёт интерфейсу стабильные операции и скрывает внутренние классы слоёв.', 'Добавь update_title и опиши вход/выход.','III · Границы','symbol'),
      ('11. Repository и соединение','data/task_repository.py','class SQLiteTaskRepository', 'Repository — единственный слой, который знает SQLite и преобразует строки в модели.', 'Объясни, почему путь БД передаётся снаружи.','III · Границы','symbol'),
      ('12. Создание схемы','data/task_repository.py','def _create_schema', 'Схема защищает основные свойства данных ограничениями базы.', 'Добавь CHECK приоритета и миграционный риск.','III · Границы','symbol'),
      ('13. Чтение из SQLite','data/task_repository.py','def list_all', 'SELECT выполняется в repository, а полученные строки превращаются в Task.', 'Добавь фильтр статуса параметром.','III · Границы','symbol'),
      ('14. Параметризованные записи','data/task_repository.py','def add', 'Значения передаются через ?, транзакция завершается контекстным менеджером.', 'Объясни lastrowid и опасность f-строки в SQL.','III · Границы','symbol'),
      ('15. Главное окно','ui/main_window.py','class MainWindow', 'MainWindow создаёт виджеты, хранит состояние интерфейса и вызывает только API.', 'Найди все зависимости окна и убедись, что sqlite3 отсутствует.','IV · Интерфейс','symbol'),
      ('16. Обновление списка','ui/main_window.py','def refresh', 'refresh получает данные через API и полностью обновляет представление.', 'Добавь отображение id, не меняя сервис.','IV · Интерфейс','symbol'),
      ('17. Обработчик кнопки','ui/main_window.py','def add_task', 'Обработчик собирает ввод, вызывает API, показывает ожидаемую ошибку и обновляет UI.', 'Раздели успешную и ошибочную ветвь по шагам.','IV · Интерфейс','symbol'),
      ('18. Тестовая замена БД','tests/test_service.py','class MemoryRepository', 'Fake repository позволяет проверять правила без диска, SQLite и окна.', 'Назови контракт, которому соответствует MemoryRepository.','V · Проверка','symbol'),
      ('19. Три обязательных теста','tests/test_service.py','class ServiceTests', 'Нормальный, ошибочный и изменяющий состояние сценарии доказывают основные правила сервиса.', 'Добавь граничные приоритеты 1, 5, 0 и 6.','V · Проверка','symbol'),
      ('20. Архитектура Tkinter и жизненный цикл окон','app/main_window.py','class MainWindow', 'Разбор архитектуры главного рабочего центра BahonIQ: модульная сетка Tkinter, навигационный сайдбар, динамические виджеты и предотвращение блокировки UI через фоновые потоки.', 'Найди в main_window.py создание сервисного виджета и объясни, почему фоновые задачи не обновляют виджеты напрямую из чужих потоков.','VI · Производственная архитектура BahonIQ','symbol'),
      ('21. AI-Ядро, отказоустойчивость и тихий Fallback','ai_service.py','def generate_text', 'Как устроен гибридный AI-конвейер BahonIQ: первичный вызов облачного Google Gemini Flash с прозрачным перехватом сетевых ошибок/таймаутов и тихим переключением на локальную Ollama без сбоя пользовательского интерфейса.', 'Объясни паттерн Graceful Degradation (плавная деградация) на примере перехвата ошибок Gemini и резервного вызова _call_ollama.','VI · Производственная архитектура BahonIQ','symbol'),
      ('22. Управление состоянием и темами оформления','services/settings_service.py','def get_theme', 'Архитектура централизованного состояния в BahonIQ: безопасное чтение конфигурации, адаптивная палитра темы (Dark/Light) и изоляция настроек от слоя представления.', 'Проследи, как изменение темы в настройках распространяется по всем открываемым окнам системы без перезапуска приложения.','VI · Производственная архитектура BahonIQ','symbol'),
    )
    return tuple(Chapter(*item) for item in specs)
CHAPTERS=load_chapters()

def chapter_source(chapter, root=None):
    from .builder import TEMPLATES
    if chapter.file in TEMPLATES:
        source = TEMPLATES[chapter.file]
    else:
        work_center_root = Path(__file__).resolve().parent.parent.parent
        real_file = work_center_root / chapter.file
        if real_file.exists():
            source = real_file.read_text(encoding='utf-8', errors='replace')
        else:
            source = read_project_file(chapter.file, root)
    lines=source.splitlines()
    if chapter.anchor.startswith('@line:'):
        line=int(chapter.anchor.split(':',1)[1])
        if not 1<=line<=len(lines):return source,None,'Опорная строка изменилась после создания книги.'
        return source,line,''
    if not chapter.anchor:return source,1,''
    index=next((i for i,s in enumerate(lines) if chapter.anchor in s),None)
    if index is None:return source,None,'Опорный фрагмент не найден в текущем исходнике.'
    return source,index+1,''

def chapter_reading(chapter,root=None):
    """Explain actual file context and AST structure without executing the code."""
    import ast
    source,line,warning=chapter_source(chapter,root)
    lines=source.splitlines()
    out=[chapter.section.upper(),'',chapter.title,'',f'РЕАЛЬНЫЙ ФАЙЛ: {chapter.file}','',
         'ЗАЧЕМ НУЖНА ЭТА ЧАСТЬ','',chapter.explanation,'',
         'КАК ЧИТАТЬ КОД','',
         'Сначала посмотри на имя функции или класса. Затем найди параметры, вызовы, условия и возвращаемое значение. '
         'Сопоставь имена импортов с файлами проекта. Не запускай рабочий исходник ради эксперимента.','']
    try:
        tree=ast.parse(source)
        focus=None
        if chapter.kind=='symbol' and line:
            nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.lineno==line]
            focus=nodes[0] if nodes else None
        if focus:
            out.extend(['СТРУКТУРА ВЫБРАННОГО БЛОКА',''])
            out.append(f'Начало: строка {focus.lineno}; конец: {focus.end_lineno}.')
            if isinstance(focus,(ast.FunctionDef,ast.AsyncFunctionDef)):
                out.append('Аргументы: '+(', '.join(a.arg for a in focus.args.args) or 'нет'))
                out.append('Возврат значения: '+('есть' if any(isinstance(n,ast.Return) for n in ast.walk(focus)) else 'явный return не найден'))
            calls=[]
            for n in ast.walk(focus):
                if isinstance(n,ast.Call):
                    fn=n.func
                    name=fn.id if isinstance(fn,ast.Name) else (fn.attr if isinstance(fn,ast.Attribute) else '')
                    if name and name not in calls:calls.append(name)
            out.append('Вызываемые функции/методы (по именам): '+(', '.join(calls[:22]) if calls else 'не найдены'))
            out.extend(['','ПОСТРОЧНЫЙ ПУТЕВОДИТЕЛЬ',''])
            from .architecture_pro import explain_line
            for n in range(focus.lineno,min(focus.end_lineno,focus.lineno+34)+1):
                if lines[n-1].strip():
                    out.append(f'{n:>4}  {lines[n-1].strip()[:110]}')
                    out.append('      '+explain_line(source,n))
        else:
            out.extend(['ОБЗОР ИМПОРТОВ И ОБЪЯВЛЕНИЙ',''])
            imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
            for n in imports[:15]:out.append(f'Строка {n.lineno}: {lines[n.lineno-1].strip()[:150]}')
            symbols=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))]
            out.extend(['','Основные классы и функции:'])
            for n in symbols[:24]:out.append(f'Строка {n.lineno}: {n.name}')
    except SyntaxError as exc:
        out.extend(['','Не удалось разобрать AST: '+str(exc)])
    out.extend(['','ПРАКТИКА','',chapter.exercise,'',
        'СЛОВАРЬ','',
        'def — объявление функции; class — объявление класса; import — подключение модуля; '
        'self — ссылка на экземпляр; return — возврат результата; try/except — обработка ошибок.'])
    if warning:out.extend(['','ПРИМЕЧАНИЕ',warning])
    return '\n'.join(out)
