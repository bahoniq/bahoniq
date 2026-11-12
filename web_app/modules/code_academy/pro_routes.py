"""Deep project-based course embedded in each studio, no arbitrary Python execution."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from .learning_engine import PYTHON, SQL, python_checks, sql_checks, run_sql_lesson


def build_routes(academy, kind, parent, palette):
    lessons = PYTHON if kind == 'python' else SQL
    color = palette
    state = {'lesson': 0}
    root = tk.Frame(parent, bg=color['bg'])
    root.pack(fill='both', expand=True)
    left = tk.Frame(root, bg=color['panel'], width=280)
    left.pack(side='left', fill='y', padx=(8, 4), pady=8)
    left.pack_propagate(False)
    tk.Label(left, text='ПРОФЕССИОНАЛЬНЫЙ МАРШРУТ', bg=color['panel'], fg=color['accent'],
             font=('Segoe UI', 10, 'bold'), wraplength=250).pack(anchor='w', padx=12, pady=(14, 10))
    navigation = tk.Listbox(left, bg=color['panel'], fg=color['ink'],
                            selectbackground=color['tag'], selectforeground=color['ink'],
                            bd=0, highlightthickness=0, font=('Segoe UI', 10),
                            activestyle='none', exportselection=False)
    navigation.pack(fill='both', expand=True, padx=10)
    for lesson in lessons:
        navigation.insert('end', lesson.title)
    tk.Label(left, text='Каждый урок: теория, законченный код,\nразбор, практика и проверка.',
             bg=color['panel'], fg=color['muted'], justify='left',
             font=('Segoe UI', 9)).pack(anchor='w', padx=12, pady=12)
    right = tk.Frame(root, bg=color['bg'])
    right.pack(side='left', fill='both', expand=True, padx=(4, 8), pady=8)
    heading = tk.Label(right, text='', bg=color['bg'], fg=color['ink'],
                       font=('Segoe UI', 15, 'bold'), anchor='w')
    heading.pack(fill='x', pady=(0, 8))
    notebook = ttk.Notebook(right)
    notebook.pack(fill='both', expand=True)
    theory_tab = tk.Frame(notebook, bg=color['panel'])
    code_tab = tk.Frame(notebook, bg=color['bg'])
    notebook.add(theory_tab, text='  ТЕОРИЯ И РАЗБОР  ')
    notebook.add(code_tab, text='  РЕДАКТОР И ПРАКТИКА  ')
    theory = tk.Text(theory_tab, bg=color['panel'], fg=color['ink'],
                     font=('Segoe UI', 11), wrap='word', bd=0, padx=18, pady=16,
                     spacing2=5, state='disabled')
    theory.pack(fill='both', expand=True)
    editor = tk.Text(code_tab, bg=color['editor'], fg=color['ink'],
                     insertbackground='white', font=('Consolas', 11), undo=True,
                     wrap='none', bd=0, padx=14, pady=12)
    editor.pack(fill='both', expand=True)
    controls = tk.Frame(right, bg=color['bg'])
    controls.pack(fill='x', pady=(8, 5))
    result = tk.Text(right, height=6, bg=color['panel'], fg=color['ink'],
                     font=('Consolas', 10), wrap='word', bd=0, padx=12, pady=9,
                     state='disabled')
    result.pack(fill='x')

    draft_dir = Path.home() / '.bahoniq_academy' / 'drafts'
    def draft_path():
        return draft_dir / (lessons[state['lesson']].slug + ('.py' if kind=='python' else '.sql'))
    def show(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')
    def save():
        draft_dir.mkdir(parents=True, exist_ok=True)
        draft_path().write_text(editor.get('1.0', 'end-1c'), encoding='utf-8')
        show(result, 'Черновик сохранён в учебном каталоге: ' + str(draft_path()))
    def load(index):
        state['lesson'] = index
        lesson = lessons[index]
        heading.configure(text=lesson.title)
        show(theory, 'ТЕОРИЯ\n\n' + lesson.theory + '\n\nПОСТРОЧНЫЙ РАЗБОР\n\n' + lesson.walkthrough + '\n\nЗАДАНИЕ\n\n' + lesson.task + '\n\nПОДСКАЗКА\n\n' + lesson.hint)
        editor.delete('1.0','end')
        path = draft_path()
        editor.insert('1.0', path.read_text(encoding='utf-8') if path.is_file() else lesson.code)
        show(result, 'Это учебный проект. Python проверяется без исполнения произвольного кода; SQL выполняется только в памяти.')
    def select(event=None):
        if navigation.curselection(): load(navigation.curselection()[0])
    navigation.bind('<<ListboxSelect>>', select)
    def check():
        lesson=lessons[state['lesson']]
        code=editor.get('1.0','end-1c')
        errors=python_checks(code, lesson.checks) if kind=='python' else sql_checks(code,lesson.checks)
        if errors:
            show(result, 'Нужно доработать:\n• ' + '\n• '.join(errors))
        else:
            show(result, 'Проверки структуры пройдены. Важно: это не доказывает правильность поведения программы.\nСледующий шаг — запустить отдельные функциональные тесты.')
    def execute():
        lesson=lessons[state['lesson']]
        if kind=='python':
            errors=python_checks(editor.get('1.0','end-1c'), ())
            show(result, 'Синтаксис Python корректен.\n' if not errors else '\n'.join(errors))
            return
        try:
            show(result, run_sql_lesson(editor.get('1.0','end-1c'), lesson.database))
        except Exception as exc:
            show(result, type(exc).__name__ + ': ' + str(exc))
    def explain_line():
        lesson=lessons[state['lesson']]
        index=int(editor.index('insert').split('.')[0]); line=editor.get(f'{index}.0',f'{index}.end')
        prompt=('Объясни по-русски выбранную строку кода, её синтаксис и связь с проектом. '
                'Сначала дай подсказку, затем предложи практическое изменение. '
                'Текущий урок: '+lesson.title+'\nЗадача: '+lesson.task+'\nСтрока '+str(index)+': '+line)
        academy._ask_from_editor(editor,kind) if not line.strip() else _send_to_tutor(academy,prompt)
    def reset():
        editor.delete('1.0','end')
        editor.insert('1.0',lessons[state['lesson']].code)
        show(result,'Исходный пример восстановлен в редакторе. Сохранённый черновик не удалён.')
    def button(text, callback, primary=False):
        tk.Button(controls,text=text,command=callback,bg=color['accent'] if primary else color['panel'],
                  fg=color['bg'] if primary else color['ink'],relief='flat',bd=0,
                  font=('Segoe UI',9,'bold'),padx=10,pady=8,cursor='hand2').pack(side='left',padx=(0,6))
    button('Проверить',check,True)
    button('Запустить SQL' if kind=='sql' else 'Проверить синтаксис',execute)
    button('Сохранить код',save)
    button('Восстановить',reset)
    button('ИИ · Объясни строку',explain_line)
    navigation.selection_set(0)
    load(0)


def _send_to_tutor(academy, prompt):
    # Reuse the existing tutor entrypoint; it is responsible for the asynchronous request.
    academy.tabs.select(academy.pages['tutor'])
    if hasattr(academy,'tutor_question'):
        academy.tutor_question.delete('1.0','end')
        academy.tutor_question.insert('1.0',prompt)
