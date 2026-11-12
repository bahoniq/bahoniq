"""Executable, explicit practice contracts for the active 48/35 lesson route.

The examples in the course remain examples. Practice has a distinct contract;
references here are used by regression tests, not inserted into the editor.
"""
from dataclasses import dataclass
import ast
import sqlite3
import time
from .pro_engine import PythonRunner, TestCase, SQLRunner, task_manager_db


@dataclass(frozen=True)
class Exercise:
    prompt: str
    solution: str
    test: str = ''
    stdin: str = ''


def ex(prompt, solution, test='', stdin=''): return Exercise(prompt, solution, test, stdin)

PYTHON = {
'py01': ex('Создай строки app_name и purpose: непустое имя своего приложения и его назначение. Выведи обе через print().',
    "app_name='Мой проект'\npurpose='Учёт задач'\nprint(app_name, purpose)",
    "assert isinstance(app_name,str) and app_name.strip()\nassert isinstance(purpose,str) and purpose.strip()"),
'py02': ex('Создай четыре переменные: title (str), count (int), price (float), active (bool). Выведи их.',
    "title='Задачи'\ncount=3\nprice=12.5\nactive=True\nprint(title,count,price,active)",
    "assert type(title) is str and type(count) is int and type(price) is float and type(active) is bool"),
'py03': ex('В total запиши 53, в capacity — 8. Вычисли boxes (полные коробки) и remainder (остаток) с // и %. Выведи результаты.',
    'total=53\ncapacity=8\nboxes=total//capacity\nremainder=total%capacity\nprint(boxes,remainder)',
    'assert total==53 and capacity==8 and boxes==6 and remainder==5'),
'py04': ex('В price запиши 250.0, в discount — 12. Вычисли final_price после процентной скидки. Выведи результат.',
    'price=250.0\ndiscount=12\nfinal_price=price*(1-discount/100)\nprint(final_price)',
    'assert price==250 and discount==12 and abs(final_price-220)<0.000001'),
'py05': ex('Создай три сравнения: is_adult для 20 >= 18, is_equal для 5 == 3, is_small для 2 < 7. Выведи их.',
    'is_adult=20>=18\nis_equal=5==3\nis_small=2<7\nprint(is_adult,is_equal,is_small)',
    'assert is_adult is True and is_equal is False and is_small is True'),
'py06': ex('Создай selected_user = None. Через is None вычисли needs_selection и выведи его.',
    'selected_user=None\nneeds_selection=selected_user is None\nprint(needs_selection)',
    'assert selected_user is None and needs_selection is True'),
'py07': ex('Для text = "Academy" вычисли first, last и middle = text[1:-1]. Выведи их.',
    "text='Academy'\nfirst=text[0]\nlast=text[-1]\nmiddle=text[1:-1]\nprint(first,last,middle)",
    "assert text=='Academy' and (first,last,middle)==('A','y','cadem')"),
'py08': ex('Очисти raw = "  Python,SQL,API  ", раздели по запятым и собери result через дефис. Выведи result.',
    "raw='  Python,SQL,API  '\nresult='-'.join(raw.strip().split(','))\nprint(result)",
    "assert result=='Python-SQL-API'"),
'py09': ex('Для name = "Чек" и price = 12.5 создай receipt с помощью f-строки: "Чек: 12.50". Выведи receipt.',
    "name='Чек'\nprice=12.5\nreceipt=f'{name}: {price:.2f}'\nprint(receipt)",
    "assert receipt=='Чек: 12.50'"),
'py10': ex('Закодируй text = "Сәлем" в data UTF-8 и восстанови restored через decode. Выведи restored.',
    "text='Сәлем'\ndata=text.encode('utf-8')\nrestored=data.decode('utf-8')\nprint(restored)",
    "assert type(data) is bytes and restored=='Сәлем' and data==restored.encode('utf-8')"),
'py11': ex('Из raw_price = "12.5" и raw_quantity = "4" вычисли total = 50.0, преобразовав строки в числа.',
    "raw_price='12.5'\nraw_quantity='4'\ntotal=float(raw_price)*int(raw_quantity)\nprint(total)",
    'assert type(total) is float and total==50.0'),
'py12': ex('Прочитай имя через input(), убери пробелы. В name запиши имя или "Без имени" для пустого ввода. Выведи name. Проверка вводит пробелы.',
    "name=input('Имя: ').strip() or 'Без имени'\nprint(name)",
    "assert name=='Без имени'", '   \n'),
'py13': ex('Напиши grade(score): A для 90–100, B для 75–89, C для 60–74, D для 50–59, F ниже 50. Верни строку.',
    "def grade(score):\n    if score>=90: return 'A'\n    elif score>=75: return 'B'\n    elif score>=60: return 'C'\n    elif score>=50: return 'D'\n    return 'F'",
    "assert [grade(x) for x in [0,49,50,59,60,74,75,89,90,100]]==['F','F','D','D','C','C','B','B','A','A']"),
'py14': ex('Напиши can_start(title, priority, done), возвращающую bool: непустое после strip название, priority >= 3 и done=False.',
    'def can_start(title,priority,done):\n    return bool(title.strip()) and priority>=3 and not done',
    "assert can_start('SQL',3,False) is True\nassert can_start(' ',5,False) is False\nassert can_start('SQL',2,False) is False\nassert can_start('SQL',5,True) is False"),
'py15': ex('Создай tasks = ["Python", "SQL"], добавь "API", замени первый элемент на "Git", удали "SQL". Итог: ["Git", "API"].',
    "tasks=['Python','SQL']\ntasks.append('API')\ntasks[0]='Git'\ntasks.remove('SQL')\nprint(tasks)",
    "assert tasks==['Git','API']"),
'py16': ex('Создай size=(800,600), распакуй в width и height. Выведи их.',
    'size=(800,600)\nwidth,height=size\nprint(width,height)',
    'assert type(size) is tuple and width==800 and height==600'),
'py17': ex('Для required={"python","sql"} и known={"python","git"} вычисли missing и common операциями множеств.',
    "required={'python','sql'}\nknown={'python','git'}\nmissing=required-known\ncommon=required&known",
    "assert missing=={'sql'} and common=={'python'}"),
'py18': ex('Создай settings — словарь с title="Academy", width=800, accent="green". Измени accent на "blue".',
    "settings={'title':'Academy','width':800,'accent':'green'}\nsettings['accent']='blue'",
    "assert type(settings) is dict and settings['title']=='Academy' and settings['width']==800 and settings['accent']=='blue'"),
'py19': ex('Через range создай numbers — список от 10 до 0 включительно с шагом -2.',
    'numbers=list(range(10,-1,-2))\nprint(numbers)', 'assert numbers==[10,8,6,4,2,0]'),
'py20': ex('Напиши numbered(items): верни список строк "1. Python", "2. SQL" для соответствующего ввода. Используй enumerate с первого номера.',
    "def numbered(items):\n    return [f'{i}. {title}' for i,title in enumerate(items,1)]",
    "assert numbered(['Python','SQL'])==['1. Python','2. SQL']\nassert numbered([])==[]\nassert numbered(['API'])==['1. API']"),
'py21': ex('Через while перебери числа с 1, пропускай чётные с continue, остановись перед 8 с break. Сохрани нечётные в result.',
    'result=[]\nn=0\nwhile True:\n    n+=1\n    if n>=8: break\n    if n%2==0: continue\n    result.append(n)', 'assert result==[1,3,5,7]'),
'py22': ex('Напиши clean_titles(items), возвращающую через list comprehension очищенные непустые строки.',
    'def clean_titles(items):\n    return [x.strip() for x in items if x.strip()]',
    "assert clean_titles([' A ','',' ','SQL'])==['A','SQL']\nassert clean_titles([])==[]"),
'py23': ex('Напиши discounted(price, percent), возвращающую цену после скидки, округлённую до двух знаков.',
    'def discounted(price,percent):\n    return round(price*(1-percent/100),2)',
    'assert discounted(100,10)==90\nassert discounted(50,0)==50\nassert discounted(19.99,15)==16.99'),
'py24': ex('Напиши describe(title, priority=1, *, author), возвращающую "title|priority|author". author — обязательный именованный параметр.',
    "def describe(title,priority=1,*,author):\n    return f'{title}|{priority}|{author}'",
    "assert describe('SQL',author='A')=='SQL|1|A'\nassert describe('API',3,author='B')=='API|3|B'\ntry:\n    describe('x')\nexcept TypeError: pass\nelse: raise AssertionError('author должен быть обязательным')"),
'py25': ex('Напиши make_adder(offset), возвращающую функцию прибавления offset к переданному числу.',
    'def make_adder(offset):\n    def add(value): return value+offset\n    return add',
    'a=make_adder(3)\nb=make_adder(-2)\nassert a(5)==8 and b(5)==3 and a(1)==4'),
'py26': ex('Напиши order_tasks(items): новый список словарей по priority убыванию, затем title возрастанию. Исходный список не меняй.',
    "def order_tasks(items):\n    return sorted(items,key=lambda x:(-x['priority'],x['title']))",
    "x=[{'title':'B','priority':2},{'title':'C','priority':5},{'title':'A','priority':2}]\ny=list(x)\nassert [a['title'] for a in order_tasks(x)]==['C','A','B'] and x==y"),
'py27': ex('Напиши генератор evens(limit), выдающий 0,2,4… строго меньше limit.',
    'def evens(limit):\n    for n in range(0,limit,2):\n        yield n',
    'assert list(evens(7))==[0,2,4,6]\nassert list(evens(0))==[]\nassert iter(evens(5)) is not None'),
'py28': ex('Напиши parse_number(text): верни int или None при ValueError; используй try/except.',
    'def parse_number(text):\n    try: return int(text)\n    except ValueError: return None',
    "assert parse_number('42')==42 and parse_number('-7')==-7 and parse_number('abc') is None"),
'py29': ex('Создай ValidationError(ValueError) и validate_priority(value): верни число от 1 до 5 включительно, иначе вызови ValidationError.',
    "class ValidationError(ValueError): pass\ndef validate_priority(value):\n    if not 1<=value<=5: raise ValidationError('Приоритет 1–5')\n    return value",
    "assert validate_priority(1)==1 and validate_priority(5)==5\nfor x in [0,6]:\n    try: validate_priority(x)\n    except ValidationError: pass\n    else: raise AssertionError('Ожидалась ошибка диапазона')"),
'py30': ex('Напиши save_lines(path, lines) и read_lines(path) для текстового UTF-8 файла. Возвращай строки без переносов.',
    "from pathlib import Path\ndef save_lines(path,lines):\n    Path(path).write_text('\\n'.join(lines),encoding='utf-8')\ndef read_lines(path):\n    return Path(path).read_text(encoding='utf-8').splitlines()",
    "save_lines('practice.txt',['Сәлем','SQL'])\nassert read_lines('practice.txt')==['Сәлем','SQL']"),
'py31': ex('Напиши encode_tasks(tasks) — JSON-строка и decode_tasks(text) — список; если корень JSON не список, вызови ValueError.',
    "import json\ndef encode_tasks(tasks): return json.dumps(tasks,ensure_ascii=False)\ndef decode_tasks(text):\n    value=json.loads(text)\n    if not isinstance(value,list): raise ValueError('Ожидался список')\n    return value",
    "items=[{'title':'Python','done':False}]\nassert decode_tasks(encode_tasks(items))==items\ntry: decode_tasks('{}')\nexcept ValueError: pass\nelse: raise AssertionError('Нет проверки типа')"),
'py32': ex('Напиши module_path(name): путь пакета вида "services.task_service" преобразуй в "services/task_service.py". Для пустого имени вызови ValueError. Затем попробуй создать эти модули в конструкторе.',
    "def module_path(name):\n    if not name.strip(): raise ValueError('Пустое имя')\n    return name.replace('.','/')+'.py'",
    "assert module_path('services.task_service')=='services/task_service.py'\nassert module_path('main')=='main.py'\ntry: module_path('')\nexcept ValueError: pass\nelse: raise AssertionError('Пустое имя принято')"),
'py33': ex('Создай dataclass Task с id, title, done=False и методом complete(), устанавливающим done=True.',
    'from dataclasses import dataclass\n@dataclass\nclass Task:\n    id:int\n    title:str\n    done:bool=False\n    def complete(self): self.done=True',
    "from dataclasses import is_dataclass\na=Task(1,'SQL')\nassert is_dataclass(a) and a.id==1 and a.title=='SQL' and a.done is False\na.complete()\nassert a.done is True"),
'py34': ex('Создай WindowSettings(width,height) с validate(): верни True, если оба размера положительные; иначе вызови ValueError.',
    "class WindowSettings:\n    def __init__(self,width,height): self.width=width; self.height=height\n    def validate(self):\n        if self.width<=0 or self.height<=0: raise ValueError('Размеры должны быть положительными')\n        return True",
    "assert WindowSettings(800,600).validate() is True\ntry: WindowSettings(0,600).validate()\nexcept ValueError: pass\nelse: raise AssertionError('Неверные размеры приняты')"),
'py35': ex('Создай Service(repository) с add(title): очисти title, пустое отклони ValueError, иначе передай его в repository.add(). Не создавай репозиторий внутри сервиса.',
    "class Service:\n    def __init__(self,repository): self.repository=repository\n    def add(self,title):\n        title=title.strip()\n        if not title: raise ValueError('Пустое название')\n        return self.repository.add(title)",
    "class Fake:\n    def __init__(self): self.items=[]\n    def add(self,x): self.items.append(x); return x\nr=Fake(); s=Service(r)\nassert s.add(' SQL ')=='SQL' and r.items==['SQL']\ntry: s.add(' ')\nexcept ValueError: pass\nelse: raise AssertionError('Пустое название принято')\nassert r.items==['SQL']"),
'py36': ex('Создай Course(lessons), реализуй __len__ и __iter__ по переданной коллекции.',
    'class Course:\n    def __init__(self,lessons): self.lessons=lessons\n    def __len__(self): return len(self.lessons)\n    def __iter__(self): return iter(self.lessons)',
    "c=Course(['Python','SQL'])\nassert len(c)==2 and list(c)==['Python','SQL']\nassert len(Course([]))==0"),
'py37': ex('Напиши аннотированную find_title(items: list[dict], task_id: int) -> str | None. Верни title найденной записи либо None.',
    "def find_title(items:list[dict],task_id:int)->str|None:\n    for item in items:\n        if item['id']==task_id: return item['title']\n    return None",
    "assert find_title([{'id':2,'title':'SQL'}],2)=='SQL'\nassert find_title([],2) is None\nassert find_title.__annotations__.get('return') is not None"),
'py38': ex('Напиши count_statuses(tasks): верни словарь количества записей по полю status, используя Counter.',
    "from collections import Counter\ndef count_statuses(tasks): return dict(Counter(x['status'] for x in tasks))",
    "assert count_statuses([{'status':'open'},{'status':'done'},{'status':'open'}])=={'open':2,'done':1}\nassert count_statuses([])=={}"),
'py39': ex('Напиши add_task(db,title) и list_tasks(db) для sqlite3.Connection. Таблица tasks(id INTEGER PRIMARY KEY,title TEXT). Вставляй title параметром; list_tasks возвращает список названий по id.',
    "def add_task(db,title): db.execute('INSERT INTO tasks(title) VALUES (?)',(title,))\ndef list_tasks(db): return [r[0] for r in db.execute('SELECT title FROM tasks ORDER BY id')]",
    "import sqlite3\ndb=sqlite3.connect(':memory:')\ndb.execute('CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT)')\nadd_task(db,\"O'Reilly\"); add_task(db,'SQL')\nassert list_tasks(db)==[\"O'Reilly\",'SQL']\ndb.close()"),
'py40': ex('Создай TaskService(repository) с create(title): очисти title, пустое отклони ValueError, вызови repository.add(title) и верни его результат.',
    "class TaskService:\n    def __init__(self,repository): self.repository=repository\n    def create(self,title):\n        title=title.strip()\n        if not title: raise ValueError('Пустое название')\n        return self.repository.add(title)",
    "class Repo:\n    def __init__(self): self.values=[]\n    def add(self,title): self.values.append(title); return {'id':len(self.values),'title':title}\nr=Repo(); s=TaskService(r)\nassert s.create(' API ')=={'id':1,'title':'API'}\ntry: s.create(' ')\nexcept ValueError: pass\nelse: raise AssertionError('Ожидалась ошибка')\nassert r.values==['API']"),
'py41': ex('Напиши build_window(tk, on_add): создай tk.Tk(), tk.Entry(root), tk.Button(root,text="Добавить",command=on_add), упакуй виджеты и верни root. mainloop здесь не запускай. Проверка использует учебные виджеты без реального окна.',
    "def build_window(tk,on_add):\n    root=tk.Tk()\n    tk.Entry(root).pack()\n    tk.Button(root,text='Добавить',command=on_add).pack()\n    return root",
    "class Widget:\n    def __init__(self,*args,**kwargs): self.kwargs=kwargs; self.packed=False\n    def pack(self): self.packed=True\nclass FakeTK:\n    def __init__(self): self.widgets=[]\n    def Tk(self): self.root=Widget(); return self.root\n    def Entry(self,root):\n        assert root is self.root\n        w=Widget(); self.widgets.append(w); return w\n    def Button(self,root,**kwargs):\n        assert root is self.root\n        w=Widget(**kwargs); self.widgets.append(w); return w\ntk=FakeTK(); callback=lambda:None\nroot=build_window(tk,callback)\nassert root is tk.root and len(tk.widgets)==2 and all(w.packed for w in tk.widgets)\nassert any(w.kwargs.get('command') is callback for w in tk.widgets)"),
'py42': ex('Напиши on_add(api,title): вызови api.create_task(title) и верни title из полученного словаря. Не используй глобальный API.',
    "def on_add(api,title): return api.create_task(title)['title']",
    "class API:\n    def __init__(self): self.calls=[]\n    def create_task(self,title): self.calls.append(title); return {'title':title.strip()}\na=API()\nassert on_add(a,' SQL ')=='SQL' and a.calls==[' SQL ']"),
'py43': ex('Напиши route(method): GET -> {"status":200,"action":"list"}, POST -> {"status":201,"action":"create"}, PATCH -> {"status":200,"action":"update"}, остальное -> {"status":405}.',
    "def route(method):\n    return {'GET':{'status':200,'action':'list'},'POST':{'status':201,'action':'create'},'PATCH':{'status':200,'action':'update'}}.get(method,{'status':405})",
    "assert route('GET')=={'status':200,'action':'list'}\nassert route('POST')=={'status':201,'action':'create'}\nassert route('PATCH')=={'status':200,'action':'update'}\nassert route('DELETE')=={'status':405}"),
'py44': ex('Создай dataclass Settings: database_path="tasks.db", width=800, height=600, debug=False. Разреши передать другие значения.',
    "from dataclasses import dataclass\n@dataclass\nclass Settings:\n    database_path:str='tasks.db'\n    width:int=800\n    height:int=600\n    debug:bool=False",
    "from dataclasses import is_dataclass\ns=Settings()\nassert is_dataclass(s) and (s.database_path,s.width,s.height,s.debug)==('tasks.db',800,600,False)\nassert Settings(width=900).width==900"),
'py45': ex('Напиши add(a,b) и класс AddTests(unittest.TestCase) с минимум тремя test_-методами: обычные числа, нули, TypeError для числа со строкой. Тесты должны проходить.',
    "import unittest\ndef add(a,b): return a+b\nclass AddTests(unittest.TestCase):\n    def test_normal(self): self.assertEqual(add(2,3),5)\n    def test_zero(self): self.assertEqual(add(0,0),0)\n    def test_error(self):\n        with self.assertRaises(TypeError): add(1,'a')",
    "import unittest\nassert add(2,3)==5 and add(0,0)==0\nsuite=unittest.defaultTestLoader.loadTestsFromTestCase(AddTests)\nassert suite.countTestCases()>=3\nresult=unittest.TestResult(); suite.run(result)\nassert result.wasSuccessful()"),
'py46': ex('Напиши count_tasks(repository), возвращающую число элементов repository.list_all(). Проверь её на своём FakeRepo.',
    "def count_tasks(repository): return len(repository.list_all())\nclass FakeRepo:\n    def list_all(self): return ['Python','SQL']\nassert count_tasks(FakeRepo())==2",
    "class Empty:\n    def list_all(self): return []\nclass Three:\n    def list_all(self): return [1,2,3]\nassert count_tasks(Empty())==0 and count_tasks(Three())==3"),
'py47': ex('Исправь divide(a,b): для ненулевого b верни a/b; для b=0 вызови ValueError с понятным сообщением.',
    "def divide(a,b):\n    if b==0: raise ValueError('Делитель равен нулю')\n    return a/b",
    "assert divide(8,2)==4 and divide(-9,3)==-3\ntry: divide(1,0)\nexcept ValueError as e: assert str(e)\nelse: raise AssertionError('Нет ошибки деления на ноль')"),
'py48': ex('Напиши allowed_dependency(source,target): True для ui→api, api→service, service→repository и service→model; False для обратных направлений и неизвестных пар.',
    "def allowed_dependency(source,target):\n    return (source,target) in {('ui','api'),('api','service'),('service','repository'),('service','model')}",
    "for pair in [('ui','api'),('api','service'),('service','repository'),('service','model')]: assert allowed_dependency(*pair) is True\nfor pair in [('repository','ui'),('api','ui'),('model','service'),('x','y')]: assert allowed_dependency(*pair) is False"),
}

# Exact query contracts; results are computed independently on fresh fixtures.
SQL = {
'sq01': ex('Покажи title,status всех tasks по id.', 'SELECT title,status FROM tasks ORDER BY id'),
'sq02': ex('Покажи title AS task_title и priority*10 AS priority_score по id.', 'SELECT title AS task_title,priority*10 AS priority_score FROM tasks ORDER BY id'),
'sq03': ex('Покажи id,title открытых задач с priority>=4, по id.', "SELECT id,title FROM tasks WHERE status='open' AND priority>=4 ORDER BY id"),
'sq04': ex('Покажи id,title: задачи user_id=1 со status=done либо priority=5; по id.', "SELECT id,title FROM tasks WHERE user_id=1 AND (status='done' OR priority=5) ORDER BY id"),
'sq05': ex('Покажи title задач с priority BETWEEN 3 AND 5 и title LIKE "%i%", по title.', "SELECT title FROM tasks WHERE priority BETWEEN 3 AND 5 AND title LIKE '%i%' ORDER BY title"),
'sq06': ex('Покажи title,priority двух самых приоритетных задач; при равенстве — title по возрастанию.', 'SELECT title,priority FROM tasks ORDER BY priority DESC,title LIMIT 2'),
'sq07': ex('Покажи уникальные status,priority по status,priority.', 'SELECT DISTINCT status,priority FROM tasks ORDER BY status,priority'),
'sq08': ex('Покажи COUNT(*) total, SUM(priority) sum_p, MIN(priority) min_p, MAX(priority) max_p, ROUND(AVG(priority),2) avg_p.', 'SELECT COUNT(*) total,SUM(priority) sum_p,MIN(priority) min_p,MAX(priority) max_p,ROUND(AVG(priority),2) avg_p FROM tasks'),
'sq09': ex('Покажи user_id,status,COUNT(*) total, группируя по пользователю и статусу. Порядок user_id,status.', 'SELECT user_id,status,COUNT(*) total FROM tasks GROUP BY user_id,status ORDER BY user_id,status'),
'sq10': ex('Покажи user_id,COUNT(*) total для открытых задач; оставь группы с total>=2, по user_id.', "SELECT user_id,COUNT(*) total FROM tasks WHERE status='open' GROUP BY user_id HAVING COUNT(*)>=2 ORDER BY user_id"),
'sq11': ex('Покажи t.title,u.name,u.department, соединив tasks и users; порядок t.id.', 'SELECT t.title,u.name,u.department FROM tasks t JOIN users u ON u.id=t.user_id ORDER BY t.id'),
'sq12': ex('Покажи u.name,COUNT(t.id) total для всех пользователей, включая не имеющих задач; по u.id.', 'SELECT u.name,COUNT(t.id) total FROM users u LEFT JOIN tasks t ON t.user_id=u.id GROUP BY u.id,u.name ORDER BY u.id'),
'sq13': ex('Через самосвязь users найди пары сотрудников одного отдела, a.id<b.id; столбцы first_name,second_name; по обоим id.', 'SELECT a.name first_name,b.name second_name FROM users a JOIN users b ON a.department=b.department AND a.id<b.id ORDER BY a.id,b.id'),
'sq14': ex('Покажи id,title задач выше среднего priority своего пользователя; по id.', 'SELECT t.id,t.title FROM tasks t WHERE t.priority>(SELECT AVG(x.priority) FROM tasks x WHERE x.user_id=t.user_id) ORDER BY t.id'),
'sq15': ex('Покажи name пользователей без done-задач через NOT EXISTS; по id.', "SELECT u.name FROM users u WHERE NOT EXISTS(SELECT 1 FROM tasks t WHERE t.user_id=u.id AND t.status='done') ORDER BY u.id"),
'sq16': ex('Покажи title и status_ru: open→Открыта, done→Завершена; по id.', "SELECT title,CASE status WHEN 'open' THEN 'Открыта' ELSE 'Завершена' END status_ru FROM tasks ORDER BY id"),
'sq17': ex('Покажи UPPER(TRIM(title)) title_clean и LENGTH(title) chars; по id.', 'SELECT UPPER(TRIM(title)) title_clean,LENGTH(title) chars FROM tasks ORDER BY id'),
'sq18': ex('Для фиксированной даты 2026-11-05 покажи начало месяца month_start и дату через 7 дней week_later.', "SELECT date('2026-11-05','start of month') month_start,date('2026-11-05','+7 days') week_later"),
'sq19': ex('Через CTE high отбери priority>=4, затем status,COUNT(*) total по статусу; порядок status.', 'WITH high AS (SELECT * FROM tasks WHERE priority>=4) SELECT status,COUNT(*) total FROM high GROUP BY status ORDER BY status'),
'sq20': ex('Через рекурсивный CTE выведи n от 0 до 10 включительно по возрастанию.', 'WITH RECURSIVE nums(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM nums WHERE n<10) SELECT n FROM nums ORDER BY n'),
'sq21': ex('Объедини UNION имена пользователей отдела Аналитика и пользователя id=1 без повторов; столбец name, по name.', "SELECT name FROM users WHERE department='Аналитика' UNION SELECT name FROM users WHERE id=1 ORDER BY name"),
'sq22': ex('Покажи title,user_id,ROW_NUMBER() AS n внутри user_id по priority DESC,id; итоговый порядок user_id,n.', 'SELECT title,user_id,ROW_NUMBER() OVER(PARTITION BY user_id ORDER BY priority DESC,id) n FROM tasks ORDER BY user_id,n'),
'sq23': ex('Покажи id,priority и running_total — накопительную SUM(priority) по id; порядок id.', 'SELECT id,priority,SUM(priority) OVER(ORDER BY id ROWS UNBOUNDED PRECEDING) running_total FROM tasks ORDER BY id'),
'sq24': ex('Создай categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE).', 'CREATE TABLE categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE)'),
'sq25': ex('Создай records(id INTEGER PRIMARY KEY,status TEXT NOT NULL DEFAULT "open" CHECK status IN(open,done),priority INTEGER NOT NULL DEFAULT 1 CHECK priority BETWEEN 1 AND 5).', "CREATE TABLE records(id INTEGER PRIMARY KEY,status TEXT NOT NULL DEFAULT 'open' CHECK(status IN('open','done')),priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 1 AND 5))"),
'sq26': ex('Создай labels(id INTEGER PRIMARY KEY,name TEXT UNIQUE) и task_labels(task_id REFERENCES tasks(id),label_id REFERENCES labels(id), PRIMARY KEY(task_id,label_id)).', 'CREATE TABLE labels(id INTEGER PRIMARY KEY,name TEXT UNIQUE); CREATE TABLE task_labels(task_id INTEGER REFERENCES tasks(id),label_id INTEGER REFERENCES labels(id),PRIMARY KEY(task_id,label_id))'),
'sq27': ex('Добавь в tasks две строки: (title="Тесты",status="open",priority=4,user_id=1) и (title="Документы",status="done",priority=2,user_id=2).', "INSERT INTO tasks(title,status,priority,user_id) VALUES('Тесты','open',4,1),('Документы','done',2,2)"),
'sq28': ex('Отметь задачу id=1 как done и удали задачу id=6. Остальные записи сохрани.', "UPDATE tasks SET status='done' WHERE id=1; DELETE FROM tasks WHERE id=6"),
'sq29': ex('В транзакции измени priority задачи id=1 на 1, затем ROLLBACK. После отката данные должны совпасть с исходными.', 'BEGIN; UPDATE tasks SET priority=1 WHERE id=1; ROLLBACK;'),
'sq30': ex('Создай индекс idx_tasks_status_priority на tasks(status,priority) в этом порядке.', 'CREATE INDEX idx_tasks_status_priority ON tasks(status,priority)'),
'sq31': ex('Выполни EXPLAIN QUERY PLAN для SELECT * FROM tasks WHERE status="open" ORDER BY priority. В результате нужен план, а не записи задач.', "EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE status='open' ORDER BY priority"),
'sq32': ex('Создай VIEW open_tasks со столбцами id,title,priority для status=open, без SELECT *.', "CREATE VIEW open_tasks AS SELECT id,title,priority FROM tasks WHERE status='open'"),
'sq33': ex('Покажи t.id,t.title,u.name,u.department через связь tasks.user_id→users.id; по t.id.', 'SELECT t.id,t.title,u.name,u.department FROM tasks t JOIN users u ON u.id=t.user_id ORDER BY t.id'),
'sq34': ex('В SQL-редакторе покажи id,title задач пользователя 2 по id. Параметризацию db.execute(sql,(user_id,)) отработай в Python-уроке SQLite.', 'SELECT id,title FROM tasks WHERE user_id=2 ORDER BY id'),
'sq35': ex('Покажи name,total,done,done_pct для всех пользователей. total — COUNT задач, done — выполненных, done_pct — процент до 1 знака либо NULL при total=0. Порядок total DESC,name.', "WITH stats AS(SELECT u.id,u.name,COUNT(t.id) total,SUM(CASE WHEN t.status='done' THEN 1 ELSE 0 END) done FROM users u LEFT JOIN tasks t ON t.user_id=u.id GROUP BY u.id,u.name) SELECT name,total,done,ROUND(100.0*done/NULLIF(total,0),1) done_pct FROM stats ORDER BY total DESC,name"),
}


def exercise_for(slug): return PYTHON.get(slug) or SQL.get(slug)


def check_python_exercise(code, slug):
    rule = PYTHON[slug]
    if not code.strip(): return False, 'Напиши решение по условию практики.'
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f'Ошибка синтаксиса, строка {exc.lineno}: {exc.msg}'
    # Lesson techniques are checked as well as runtime results.
    required = {'py09': ast.JoinedStr, 'py20': ast.Call, 'py21': ast.While,
                'py22': ast.ListComp, 'py27': ast.Yield, 'py28': ast.Try,
                'py29': ast.Raise, 'py33': ast.ClassDef, 'py34': ast.ClassDef}
    if slug in required and not any(isinstance(n, required[slug]) for n in ast.walk(tree)):
        return False, 'Используй конструкцию изучаемого урока, указанную в задании.'
    if slug == 'py20' and not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='enumerate' for n in ast.walk(tree)):
        return False, 'В этом упражнении нужен enumerate().'
    if slug == 'py21' and not all(any(isinstance(n,t) for n in ast.walk(tree)) for t in (ast.Break,ast.Continue)):
        return False, 'В этом упражнении нужны break и continue.'
    if slug in {'py01','py02'} and not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='print' for n in ast.walk(tree)):
        return False, 'Добавь вывод через print().'
    marker = '__ACADEMY_PRACTICE_OK__'
    combined = code + '\n\n# Проверка контракта практики\n' + rule.test + f'\nprint({marker!r})\n'
    report = PythonRunner().assess(combined, (TestCase('Контракт '+slug, stdin=rule.stdin),))
    if report.passed and report.cases[0].stdout.rstrip().endswith(marker):
        return True, 'Решение прошло проверки результата и граничных случаев этого урока.'
    details = '\n'.join(c.stderr for c in report.cases if c.stderr)
    return False, 'Решение пока не выполняет условие практики.\n' + (details or report.message)


def _fixture(extra=False):
    db = task_manager_db()
    if extra:
        db.execute("INSERT INTO tasks VALUES(20,'Extra','open',2,4)")
        db.execute("INSERT INTO tasks VALUES(21,'New','done',5,2)")
        db.commit()
    return db


def _state(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: tuple(db.execute('SELECT * FROM "'+name+'" ORDER BY 1,2')) for name in tables}


def _constraint_rejected(db, query):
    db.execute('SAVEPOINT practice_check')
    try:
        db.execute(query)
    except sqlite3.IntegrityError:
        return True
    finally:
        db.execute('ROLLBACK TO practice_check'); db.execute('RELEASE practice_check')
    return False


def check_sql_exercise(code, slug):
    rule = SQL[slug]
    try:
        if slug not in {f'sq{i:02}' for i in range(24,33)}:
            for extra in (False,True):
                factory = lambda: _fixture(extra)
                runner = SQLRunner(database_factory=factory)
                expected, actual = runner.execute(rule.solution), runner.execute(code)
                if expected.columns != actual.columns or expected.rows != actual.rows:
                    return False, 'Проверь столбцы, значения и порядок строк: результат не соответствует условию.'
            return True, 'Запрос подтвердился на двух наборах данных.'
        if slug == 'sq31':
            actual = SQLRunner().execute(code)
            if actual.columns != ('id','parent','notused','detail') or not actual.rows:
                return False, 'Нужен результат EXPLAIN QUERY PLAN.'
            expected = SQLRunner().execute(rule.solution)
            return (actual.rows == expected.rows, 'План проверен.' if actual.rows == expected.rows else 'План относится к другому запросу.')
        db = _fixture(); expected_db = _fixture()
        try:
            started = time.monotonic()
            db.set_progress_handler(lambda: int(time.monotonic()-started>3),1000)
            def authorize(action, *args):
                return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            db.executescript(code)
            expected_db.executescript(rule.solution)
            if slug not in {'sq27','sq28','sq29'}:
                for table in ('users','tasks'):
                    if tuple(db.execute('SELECT * FROM '+table+' ORDER BY id')) != tuple(expected_db.execute('SELECT * FROM '+table+' ORDER BY id')):
                        return False, 'Исходные users и tasks не должны изменяться в этом задании.'
            if slug in {'sq27','sq28','sq29'}:
                if _state(db) != _state(expected_db): return False, 'Состояние таблиц не соответствует условию.'
                if slug == 'sq29' and not all(x in code.upper() for x in ('BEGIN','UPDATE','ROLLBACK')):
                    return False, 'Нужна транзакция с UPDATE и ROLLBACK.'
            elif slug == 'sq30':
                if [r[2] for r in db.execute('PRAGMA index_info(idx_tasks_status_priority)')] != ['status','priority']:
                    return False, 'Индекс должен включать status,priority в этом порядке.'
            elif slug == 'sq32':
                cur = db.execute('SELECT * FROM open_tasks ORDER BY id')
                if [x[0] for x in cur.description] != ['id','title','priority'] or cur.fetchall() != expected_db.execute('SELECT * FROM open_tasks ORDER BY id').fetchall():
                    return False, 'Проверь состав столбцов и отбор представления.'
            else:
                for table in ('categories',) if slug=='sq24' else ('records',) if slug=='sq25' else ('labels','task_labels'):
                    actual = list(db.execute(f'PRAGMA table_info({table})'))
                    expected = list(expected_db.execute(f'PRAGMA table_info({table})'))
                    if actual != expected: return False, f'Структура {table} не соответствует условию.'
                if slug == 'sq24':
                    db.execute("INSERT INTO categories VALUES(1,'A')")
                    if not _constraint_rejected(db,"INSERT INTO categories VALUES(2,'A')"): return False,'Нужно UNIQUE для name.'
                if slug == 'sq25':
                    for query in ["INSERT INTO records(status) VALUES('bad')", 'INSERT INTO records(priority) VALUES(6)']:
                        if not _constraint_rejected(db,query): return False,'Ограничения CHECK не действуют.'
                if slug == 'sq26':
                    foreign = list(db.execute('PRAGMA foreign_key_list(task_labels)'))
                    if {(r[2],r[3],r[4]) for r in foreign} != {('tasks','task_id','id'),('labels','label_id','id')}:
                        return False,'Нужны оба внешних ключа.'
            return True, 'Структура, ограничения или изменения учебной базы проверены.'
        finally:
            db.close(); expected_db.close()
    except (sqlite3.Error,ValueError) as exc:
        return False, 'Проверка SQL: ' + str(exc)
