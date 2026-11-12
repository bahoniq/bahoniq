"""Integrated project builder: files, editing, validation, preview, tutor."""
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from .builder import line_explanation
from .builder_pro import add_file, validate_project, save_draft, load_draft
from .studio_core import preview_settings, apply_visual_settings
from .ai_tutor import ask_tutor
from .editor import CodeEditor

GREEN='#009246'; DARK='#17352A'; BG='#F2F6F4'; BLUE='#234A60'


def build_builder(host):
    page=host.pages['builder']
    root=tk.Frame(page,bg=BG);root.pack(fill='both',expand=True)
    top=tk.Frame(root,bg='#172C27');top.pack(fill='x')
    tk.Label(top,text='AI APP BUILDER  /  PROJECT WORKSPACE',bg='#172C27',fg='#E9F6EF',font=('Segoe UI',15,'bold')).pack(side='left',padx=18,pady=14)
    tk.Label(top,text='Учебная копия · файлы Work Center не изменяются',bg='#172C27',fg='#B4D8C5').pack(side='right',padx=16)
    pan=tk.PanedWindow(root,orient='horizontal',sashwidth=5,bg=BG);pan.pack(fill='both',expand=True,padx=10,pady=10)
    left=tk.Frame(pan,bg='white');pan.add(left,minsize=185,width=240)
    center=tk.Frame(pan,bg='white');pan.add(center,minsize=350,width=600)
    right=tk.Frame(pan,bg='white');pan.add(right,minsize=280,width=350)
    def title(parent,text):tk.Label(parent,text=text,bg='white',fg=DARK,font=('Segoe UI',11,'bold'),anchor='w').pack(fill='x',padx=12,pady=(12,6))
    def button(parent,text,fn,accent=False):return tk.Button(parent,text=text,command=fn,bg=GREEN if accent else '#E9F3ED',fg='white' if accent else DARK,relief='flat',padx=8,pady=7,cursor='hand2')
    title(left,'ФАЙЛЫ ПРОЕКТА')
    tree=ttk.Treeview(left,show='tree',selectmode='browse');tree.pack(fill='both',expand=True,padx=8,pady=5)
    title(center,'РЕДАКТОР PYTHON / SQL / JSON')
    filename=tk.Label(center,text='main.py',bg='white',fg=GREEN,font=('Consolas',11,'bold'));filename.pack(anchor='w',padx=12)
    editor=CodeEditor(center,bg='#142720',fg='#E7F5EC',insertbackground='white',font=('Consolas',11),undo=True,wrap='none',padx=12,pady=10)
    editor.pack(fill='both',expand=True,padx=10,pady=8)
    status=tk.Label(center,text='Готов к работе',bg='white',fg=DARK,anchor='w',wraplength=570,justify='left');status.pack(fill='x',padx=12,pady=5)
    bar=tk.Frame(center,bg='white');bar.pack(fill='x',padx=10,pady=8)
    title(right,'ПОЯСНЕНИЕ КОДА')
    explanation=tk.Text(right,height=7,wrap='word',bg='#EFF7F2',fg=DARK,relief='flat',font=('Segoe UI',10),padx=8,pady=8)
    explanation.pack(fill='x',padx=10)
    title(right,'ПРЕДПРОСМОТР TKINTER')
    canvas=tk.Canvas(right,bg='#E8F0EB',height=170,highlightthickness=0);canvas.pack(fill='x',padx=10,pady=5)
    title(right,'ИИ-НАСТАВНИК')
    question=tk.Text(right,height=3,wrap='word',font=('Segoe UI',10));question.pack(fill='x',padx=10,pady=5)
    question.insert('1.0','Объясни, как связаны файлы проекта, и предложи следующее задание.')
    wait=tk.StringVar(value='180')
    opts=tk.Frame(right,bg='white');opts.pack(fill='x',padx=10,pady=3)
    tk.Label(opts,text='Ожидание, сек:',bg='white',fg=DARK).pack(side='left')
    ttk.Combobox(opts,textvariable=wait,values=['90','180','300','600'],width=7,state='readonly').pack(side='left',padx=5)
    answer=tk.Text(right,wrap='word',bg='#F3F7F4',fg=DARK,font=('Segoe UI',10),padx=8,pady=8)
    answer.pack(fill='both',expand=True,padx=10,pady=8)
    active={'name':'main.py'}
    busy={'value':False}
    def display_answer(text):
        answer.delete('1.0','end');answer.insert('1.0',text)
    def refresh_tree():
        tree.delete(*tree.get_children())
        nodes={'':''}
        for name in sorted(host.workspace.project.files):
            parts=name.split('/');parent='';partial=''
            for part in parts:
                partial=partial+'/'+part if partial else part
                if partial not in nodes:
                    tree.insert(parent,'end',iid=partial,text=part,open=True)
                    nodes[partial]=partial
                parent=partial
    def set_file(name):
        active['name']=name;host.workspace.select(name);filename.config(text=name)
        editor.delete('1.0','end');editor.insert('1.0',host.workspace.project.files[name]);status.config(text='Учебный файл: '+name,fg=DARK)
        editor.set_language(name)
    def save():
        name=active['name'];source=editor.get('1.0','end-1c')
        try:
            if name in host.workspace.project.files:host.workspace.project.update(name,source)
            else:raise ValueError('Файл не найден')
        except (ValueError,SyntaxError) as exc:status.config(text=f'Ошибка: {exc}',fg='#C33540');return False
        status.config(text='Файл сохранён в учебном проекте',fg=GREEN);return True
    def on_select(_=None):
        sel=tree.selection()
        if not sel or sel[0] not in host.workspace.project.files:return
        if editor.get('1.0','end-1c')!=host.workspace.project.files[active['name']]:
            if not messagebox.askyesno('Несохранённый код','Перейти без сохранения?',parent=host.win):return
        set_file(sel[0])
    tree.bind('<<TreeviewSelect>>',on_select)
    def add():
        name=simpledialog.askstring('Новый файл','Например: services/task_service.py',parent=host.win)
        if not name:return
        if not save():return
        try:add_file(host.workspace.project,name)
        except (ValueError,SyntaxError) as exc:messagebox.showerror('Файл',str(exc),parent=host.win);return
        refresh_tree();tree.selection_set(name);set_file(name)
    def check():
        if not save():return
        issues=validate_project(host.workspace.project.files)
        status.config(text='Проверка: '+('OK · синтаксис и локальные импорты' if not issues else f'{len(issues)} проблем'),fg=GREEN if not issues else '#B34D20')
        display_answer('\n'.join(issues) if issues else 'Проверка синтаксиса и локальных импортов пройдена. Это не заменяет функциональные тесты.')
    def export():
        if not save():return
        folder=filedialog.askdirectory(parent=host.win,title='Выбери пустую папку для экспорта')
        if not folder:return
        try:host.workspace.export(folder)
        except (ValueError,OSError) as exc:messagebox.showerror('Экспорт',str(exc),parent=host.win);return
        messagebox.showinfo('Экспорт','Проект сохранён: '+folder,parent=host.win)
    def save_draft_ui():
        if not save():return
        path=filedialog.asksaveasfilename(parent=host.win,defaultextension='.json',filetypes=[('Учебный проект','*.json')])
        if path:
            try:save_draft(host.workspace.project.files,path)
            except OSError as exc:messagebox.showerror('Черновик',str(exc),parent=host.win)
    def load_draft_ui():
        path=filedialog.askopenfilename(parent=host.win,filetypes=[('Учебный проект','*.json')])
        if not path:return
        try:files=load_draft(path)
        except (ValueError,OSError,SyntaxError) as exc:messagebox.showerror('Черновик',str(exc),parent=host.win);return
        host.workspace.project.files=files;refresh_tree();set_file('main.py' if 'main.py' in files else next(iter(files)))
    def explain(_=None):
        index=editor.index('insert').split('.')[0];line=editor.get(f'{index}.0',f'{index}.end')
        explanation.delete('1.0','end');explanation.insert('1.0',f'Строка {index}: {line.strip()}\n\n'+line_explanation(active['name'],line))
    editor.bind('<ButtonRelease-1>',explain);editor.bind('<KeyRelease>',explain)
    def preview():
        if not save():return
        data=preview_settings(host.workspace.project.files)
        canvas.delete('all');w=max(240,canvas.winfo_width()-18)
        canvas.create_rectangle(8,8,w,158,fill='white',outline='#B4C9BE')
        canvas.create_rectangle(8,8,w,37,fill='#DCE8E1',outline='')
        canvas.create_text(18,23,text=data['TITLE'][:34],anchor='w',fill=DARK)
        canvas.create_text(w/2,73,text=data['LABEL_TEXT'][:34],fill=DARK)
        canvas.create_rectangle(w/2-70,91,w/2+70,127,fill=data['ACCENT'],outline='')
        canvas.create_text(w/2,109,text=data['BUTTON_TEXT'][:22],fill='white')
        canvas.create_text(w/2,145,text=f'{data["WIDTH"]} × {data["HEIGHT"]} px',fill='#5A7065')
    def ask():
        if busy['value']:return
        if not save():return
        q=question.get('1.0','end-1c').strip()
        if not q:return
        busy['value']=True;ask_button.config(state='disabled',text='ИИ отвечает...')
        display_answer('Ожидаем ответ Ollama. Интерфейс остаётся доступным.')
        source=editor.get('1.0','end-1c')
        context='\n'.join(sorted(host.workspace.project.files))
        timeout=int(wait.get())
        model=getattr(host,'tutor_model',None)
        model=model.get() if model is not None else 'qwen2.5:3b'
        def worker():
            try:result=ask_tutor('Учебный проект содержит файлы:\n'+context+'\n\n'+q,active['name'],source,model=model,timeout=timeout)
            except Exception as exc:result='ИИ недоступен: '+str(exc)
            def done():
                if host.win.winfo_exists():
                    display_answer(result);busy['value']=False;ask_button.config(state='normal',text='Спросить наставника')
            try:host.win.after(0,done)
            except RuntimeError:pass
        threading.Thread(target=worker,daemon=True).start()
    for name,fn in [('Новый файл',add),('Проверить',check),('Сохранить черновик',save_draft_ui),('Открыть черновик',load_draft_ui),('Экспорт',export)]:
        button(left,name,fn).pack(fill='x',padx=8,pady=3)
    button(bar,'Сохранить файл',save,True).pack(side='left',padx=3)
    button(bar,'Обновить предпросмотр',preview).pack(side='left',padx=3)
    ask_button=button(right,'Спросить наставника',ask,True);ask_button.pack(fill='x',padx=10,pady=4)
    refresh_tree();set_file('main.py');preview()
