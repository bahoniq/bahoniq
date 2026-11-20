"""Guided project builder with optional threaded AI tutor."""
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .builder import GuidedProject, EXPLAIN, line_explanation
from .ai_tutor import ask_tutor

GREEN='#009246'; RED='#CE2B37'; DARK='#17352A'; BG='#F6F8F7'

class BuilderWindow:
    def __init__(self,parent):
        self.parent=parent
        self.project=GuidedProject()
        self.current='main.py'
        self.busy=False
        self.responses=queue.Queue()
        self.win=tk.Toplevel(parent)
        self.win.title('BahonIQ Code Academy — Конструктор приложений + ИИ-тренер')
        self.win.geometry('1250x820'); self.win.minsize(960,640)
        self.win.configure(bg=BG)
        header=tk.Frame(self.win,bg='white'); header.pack(fill='x')
        tk.Label(header,text='КОНСТРУКТОР ПРИЛОЖЕНИЙ  /  ИИ-ТРЕНЕР',font=('Segoe UI',16,'bold'),fg=GREEN,bg='white').pack(side='left',padx=16,pady=13)
        tk.Button(header,text='Экспорт учебного проекта',command=self.export,bg=GREEN,fg='white',relief='flat',padx=12,pady=7).pack(side='right',padx=12)
        guide=tk.Label(self.win,text='1. Выбери файл  →  2. Изучи код  →  3. Измени параметры  →  4. Проверь синтаксис  →  5. Спроси тренера',bg=BG,fg=DARK,font=('Segoe UI',10))
        guide.pack(anchor='w',padx=16,pady=8)
        pan=tk.PanedWindow(self.win,orient='horizontal',sashwidth=5,bg=BG); pan.pack(fill='both',expand=True,padx=12,pady=(0,12))
        left=tk.Frame(pan,bg='white'); pan.add(left,minsize=200,width=235)
        tk.Label(left,text='УЧЕБНЫЙ ПРОЕКТ',font=('Segoe UI',11,'bold'),bg='white',fg=DARK).pack(anchor='w',padx=12,pady=12)
        self.files=tk.Listbox(left,font=('Consolas',10),selectbackground=GREEN,relief='flat',highlightthickness=0)
        self.files.pack(fill='both',expand=True,padx=8,pady=4)
        for name in self.project.files: self.files.insert('end',name)
        self.files.bind('<<ListboxSelect>>',self.select)
        middle=tk.Frame(pan,bg='white'); pan.add(middle,minsize=390,width=590)
        self.filename=tk.Label(middle,font=('Segoe UI',13,'bold'),bg='white',fg=DARK,anchor='w'); self.filename.pack(fill='x',padx=12,pady=8)
        self.code=tk.Text(middle,font=('Consolas',11),bg='#192B25',fg='#EAF7EF',insertbackground='white',undo=True,wrap='none',padx=10,pady=10)
        self.code.pack(fill='both',expand=True,padx=12)
        self.code.bind('<ButtonRelease-1>',self.explain_line)
        self.code.bind('<KeyRelease>',self.explain_line)
        bar=tk.Frame(middle,bg='white'); bar.pack(fill='x',padx=12,pady=8)
        tk.Button(bar,text='Сохранить учебный код',command=self.save,bg=GREEN,fg='white',relief='flat',padx=10,pady=7).pack(side='left')
        tk.Button(bar,text='Вернуть шаблон',command=self.reset,relief='flat',padx=10,pady=7).pack(side='left',padx=7)
        self.status=tk.Label(middle,text='',bg='white',fg=DARK,anchor='w',wraplength=560,justify='left'); self.status.pack(fill='x',padx=12,pady=(0,8))
        right=tk.Frame(pan,bg='white'); pan.add(right,minsize=290,width=355)
        tk.Label(right,text='ПОСТРОЧНОЕ ОБЪЯСНЕНИЕ',bg='white',fg=DARK,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=12,pady=(12,4))
        self.explain=tk.Text(right,height=7,wrap='word',bg='#F0F7F3',fg=DARK,relief='flat',font=('Segoe UI',10),padx=8,pady=8)
        self.explain.pack(fill='x',padx=12)
        tk.Label(right,text='ИИ-ТРЕНЕР · BAHONIQ AI',bg='white',fg=DARK,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=12,pady=(12,4))
        self.mode=tk.StringVar(value='hint')
        modes=tk.Frame(right,bg='white'); modes.pack(fill='x',padx=12)
        tk.Radiobutton(modes,text='Подскажи',variable=self.mode,value='hint',bg='white').pack(side='left')
        tk.Radiobutton(modes,text='Покажи решение',variable=self.mode,value='solution',bg='white').pack(side='left')
        self.question=tk.Text(right,height=3,wrap='word',font=('Segoe UI',10),relief='solid',bd=1)
        self.question.pack(fill='x',padx=12,pady=6)
        self.question.insert('1.0','Объясни, как изменить заголовок и цвет кнопки.')
        self.ask_button=tk.Button(right,text='Спросить ИИ-тренера',command=self.ask,bg=GREEN,fg='white',relief='flat',pady=8)
        self.ask_button.pack(fill='x',padx=12,pady=4)
        self.answer=tk.Text(right,wrap='word',font=('Segoe UI',10),bg='#F3F7F4',fg=DARK,relief='flat',padx=9,pady=9)
        self.answer.pack(fill='both',expand=True,padx=12,pady=(5,12))
        self.files.selection_set(0); self.show_file('main.py')
        self.win.after(150,self._poll_responses)

    def _set_explanation(self,text):
        self.explain.delete('1.0','end'); self.explain.insert('1.0',text)
    def show_file(self,name):
        self.current=name; self.filename.config(text=name)
        self.code.delete('1.0','end'); self.code.insert('1.0',self.project.files[name])
        self._set_explanation(EXPLAIN.get(name,'Файл учебного проекта.'))
        self.status.config(text='Изменения пока находятся только в учебном редакторе.')
    def select(self,event=None):
        selection=self.files.curselection()
        if not selection:return
        name=self.files.get(selection[0])
        if name!=self.current:
            if self.code.get('1.0','end-1c')!=self.project.files[self.current]:
                if not messagebox.askyesno('Несохранённые изменения','Перейти без сохранения текущего кода?',parent=self.win):
                    self.files.selection_clear(0,'end'); self.files.selection_set(list(self.project.files).index(self.current));return
            self.show_file(name)
    def explain_line(self,event=None):
        line=int(self.code.index('insert').split('.')[0]); content=self.code.get(f'{line}.0',f'{line}.end')
        self._set_explanation(f'Строка {line}: {content.strip()}\n\n{line_explanation(self.current,content)}')
    def save(self):
        try:self.project.update(self.current,self.code.get('1.0','end-1c'))
        except SyntaxError as exc:
            self.status.config(text=f'Ошибка синтаксиса, строка {exc.lineno}: {exc.msg}',fg=RED);return False
        except ValueError as exc:
            self.status.config(text=str(exc),fg=RED);return False
        self.status.config(text='Синтаксис проверен. Код сохранён в памяти учебного проекта.',fg=GREEN)
        return True
    def reset(self):
        from .builder import TEMPLATES
        if messagebox.askyesno('Восстановление','Вернуть исходный код этого учебного файла?',parent=self.win):
            self.code.delete('1.0','end');self.code.insert('1.0',TEMPLATES[self.current]);self.save()
    def export(self):
        if not self.save():return
        folder=filedialog.askdirectory(parent=self.win,title='Выбери НОВУЮ пустую папку для учебного проекта')
        if not folder:return
        try: target=self.project.export(folder)
        except (OSError,ValueError) as exc:messagebox.showerror('Экспорт',str(exc),parent=self.win);return
        messagebox.showinfo('Учебный проект',f'Создано в {target}\nЗапуск: py main.py\nНе запускай неизвестный код без проверки.',parent=self.win)
    def ask(self):
        if self.busy:return
        question=self.question.get('1.0','end-1c').strip()
        if not question:return
        mode='Дай пошаговую подсказку без полного решения.' if self.mode.get()=='hint' else 'Покажи учебное решение и объясни строки.'
        code=self.code.get('1.0','end-1c')
        self.busy=True;self.ask_button.config(state='disabled',text='Тренер отвечает...')
        self.answer.delete('1.0','end');self.answer.insert('1.0','Запрос к Облачному ИИ...')
        def worker():
            try: result=ask_tutor(mode+' '+question,self.current,code,timeout=45)
            except Exception as exc:result=f'Тренер недоступен: {exc}\n\nВстроенные построчные объяснения работают автономно.'
            self.responses.put(result)
        threading.Thread(target=worker,daemon=True).start()

    def _poll_responses(self):
        try:
            while True:
                result=self.responses.get_nowait()
                self.answer.delete('1.0','end');self.answer.insert('1.0',result)
                self.busy=False;self.ask_button.config(state='normal',text='Спросить ИИ-тренера')
        except queue.Empty:pass
        if self.win.winfo_exists():self.win.after(150,self._poll_responses)

def open_builder(parent):return BuilderWindow(parent)
