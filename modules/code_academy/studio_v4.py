"""Unified progressive course and encyclopedia: one lesson, one editor, one clear path."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from .pathway import steps, check_python, check_sql, run_sql
from .encyclopedia import entries, search
from .runners import run_python
from .editor import CodeEditor
from .exercises import exercise_for
from .python_runtime import RunningPython
import queue
import threading

PALETTES={
 'python':dict(bg='#0C1917',panel='#172C27',editor='#091511',accent='#37D38A',ink='#E9F7EF',muted='#A9C7BB',tag='#23493A'),
 'sql':dict(bg='#0C172A',panel='#172C47',editor='#0B1527',accent='#74BEFF',ink='#EAF3FF',muted='#B0C8E4',tag='#254667')}

def _enable_editor_shortcuts(widget):
    """Windows-friendly editing shortcuts and a right-click context menu."""
    def select_all(event=None):
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        widget.see("insert")
        return "break"
    widget.bind("<Control-a>", select_all)
    widget.bind("<Control-A>", select_all)
    for key, virtual in (("c", "<<Copy>>"), ("C", "<<Copy>>"), ("v", "<<Paste>>"), ("V", "<<Paste>>"), ("x", "<<Cut>>"), ("X", "<<Cut>>")):
        widget.bind(f"<Control-{key}>", lambda e, v=virtual: (widget.event_generate(v), "break")[1])

    def physical_shortcut(event):
        key = str(getattr(event, "keysym", "")).casefold()
        if key in {"a", "c", "v", "x"}:
            return None
        code = getattr(event, "keycode", None)
        if code == 65 or key in {"cyrillic_ef", "cyrillic_a"}:
            return select_all(event)
        if code == 67 or key in {"cyrillic_es", "cyrillic_c"}:
            widget.event_generate("<<Copy>>")
            return "break"
        if code == 86 or key in {"cyrillic_em", "cyrillic_v"}:
            widget.event_generate("<<Paste>>")
            return "break"
        if code == 88 or key in {"cyrillic_che", "cyrillic_x"}:
            widget.event_generate("<<Cut>>")
            return "break"
        return None

    widget.bind("<Control-KeyPress>", physical_shortcut, add="+")
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=select_all)
    def popup(event):
        widget.focus_set()
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()
        return "break"
    widget.bind("<Button-3>", popup)
    widget.bind("<Button-2>", popup)
    return widget


def build_studio(academy,kind):
    c=PALETTES[kind];page=academy.pages[kind];page.configure(bg=c['bg'])
    route=steps(kind);state={'index':0,'phase':0,'loaded':False,'run':None,'checking':False,'error':'','callbacks':set()};drafts=Path.home()/'.bahoniq_academy'/'drafts'
    def label(parent,text,size=10,color=None,bold=False):
        return tk.Label(parent,text=text,bg=parent.cget('bg'),fg=color or c['ink'],font=('Segoe UI',size,'bold' if bold else 'normal'),anchor='w')
    def btn(parent,text,cmd,primary=False):
        return tk.Button(parent,text=text,command=cmd,bg=c['accent'] if primary else c['panel'],fg=c['bg'] if primary else c['ink'],font=('Segoe UI',10,'bold'),bd=0,relief='flat',padx=12,pady=9,cursor='hand2')
    header=tk.Frame(page,bg=c['bg']);header.pack(fill='x',padx=18,pady=(12,9))
    label(header,'PYTHON STUDIO' if kind=='python' else 'SQL LABORATORY',20,bold=True).pack(side='left')
    label(header,'ПОСЛЕДОВАТЕЛЬНЫЙ КУРС  ·  TASK MANAGER',10,c['accent'],True).pack(side='right')
    shell=tk.PanedWindow(page,orient='horizontal',bg=c['bg'],sashwidth=7,bd=0)
    shell.pack(fill='both',expand=True,padx=12,pady=(0,12))
    nav=tk.Frame(shell,bg=c['panel']);workspace=tk.Frame(shell,bg=c['bg']);shell.add(nav,minsize=210,width=285);shell.add(workspace,minsize=550)
    workspace.columnconfigure(0,weight=1)
    workspace.rowconfigure(2,weight=1)
    label(nav,'УЧЕБНЫЙ ПУТЬ',11,c['accent'],True).pack(anchor='w',padx=12,pady=(16,8))
    listing=tk.Listbox(nav,bg=c['panel'],fg=c['ink'],selectbackground=c['tag'],selectforeground=c['accent'],activestyle='none',bd=0,highlightthickness=0,font=('Segoe UI',10),exportselection=False)
    listing.pack(fill='both',expand=True,padx=10)
    for step in route:listing.insert('end',f'Ур. {step.level}  ·  {step.title}')
    label(nav,'СПРАВОЧНИК',11,c['accent'],True).pack(anchor='w',padx=12,pady=(12,5))
    btn(nav,'Открыть энциклопедию  ↗',lambda:show_reference()).pack(fill='x',padx=10,pady=(0,8))
    label(nav,'Один урок за раз. Код и прогресс\nсохраняются отдельно.',9,c['muted']).pack(anchor='w',padx=12,pady=(0,15))
    title=label(workspace,'',16,bold=True);title.grid(row=0,column=0,sticky='ew',pady=(0,7))
    phases=['1 · Теория','2 · Разбор','3 · Практика','4 · Проверка','5 · Закрепление']
    phase_bar=tk.Frame(workspace,bg=c['bg']);phase_bar.grid(row=1,column=0,sticky='ew',pady=(0,7))
    main=tk.Frame(workspace,bg=c['panel']);main.grid(row=2,column=0,sticky='nsew')
    lesson_text=tk.Text(main,bg=c['panel'],fg=c['ink'],font=('Segoe UI',11),wrap='word',height=8,bd=0,padx=15,pady=12,spacing2=4,state='disabled')
    lesson_text.pack(fill='both',expand=True)
    lesson_scroll=ttk.Scrollbar(lesson_text,command=lesson_text.yview)
    lesson_text.configure(yscrollcommand=lesson_scroll.set);lesson_scroll.pack(side='right',fill='y')
    _enable_editor_shortcuts(lesson_text)
    edit_frame=tk.Frame(main,bg=c['editor']);editor=CodeEditor(edit_frame,height=12,language=kind,bg=c['editor'],fg=c['ink'],insertbackground='white',font=('Consolas',11),undo=True,wrap='none',bd=0,padx=15,pady=12)
    _enable_editor_shortcuts(editor).pack(fill='both',expand=True)
    result=tk.Text(workspace,height=4,bg=c['panel'],fg=c['ink'],font=('Consolas',10),wrap='word',bd=0,padx=12,pady=9,state='disabled');result.grid(row=3,column=0,sticky='ew',pady=(8,0))
    _enable_editor_shortcuts(result)
    inputbar=tk.Frame(workspace,bg=c['bg'])
    if kind=='python': inputbar.grid(row=4,column=0,sticky='ew',pady=(4,0))
    label(inputbar,'Ввод input():',9).pack(side='left')
    console_input=tk.Entry(inputbar,bg=c['panel'],fg=c['ink'],insertbackground=c['ink'],font=('Consolas',10))
    console_input.pack(side='left',fill='x',expand=True,padx=6)
    controls=tk.Frame(workspace,bg=c['bg']);controls.grid(row=5,column=0,sticky='ew',pady=(8,0))
    def show(w,s):
        w.config(state='normal');w.delete('1.0','end');w.insert('1.0',s)
        if w is lesson_text:
            w.tag_configure('heading',foreground=c['accent'],font=('Segoe UI',11,'bold'),spacing1=12,spacing3=6)
            for number,line in enumerate(s.splitlines(),1):
                if line.strip() and line.strip().isupper() and len(line)<90:
                    w.tag_add('heading',f'{number}.0',f'{number}.end')
        w.config(state='disabled');w.see('1.0')
    def schedule(callback):
        def invoke():
            state['callbacks'].discard(job)
            callback()
        job=editor.after(50,invoke)
        state['callbacks'].add(job)
    def lesson():return route[state['index']]
    def practice():return exercise_for(lesson().slug)
    def challenge():return practice().prompt if practice() else lesson().challenge
    def path():return drafts/(lesson().slug+('.py' if kind=='python' else '.sql'))
    def save(silent=False):
        drafts.mkdir(parents=True,exist_ok=True)
        path().write_text(editor.get('1.0','end-1c'),encoding='utf-8')
        if not silent:show(result,'Черновик сохранён: '+str(path()))
    def switch(index):
        if index<0 or index>=len(route):return
        if state['checking']:
            show(result,'Дождись завершения проверки перед переходом к другому уроку.');return
        if state['loaded']:
            try:save(True)
            except OSError as exc:
                show(result,'Не удалось сохранить текущий урок: '+str(exc));return
        stop()
        state['index']=index;state['phase']=0
        listing.selection_clear(0,'end');listing.selection_set(index);listing.see(index)
        editor.delete('1.0','end');editor.insert('1.0',path().read_text(encoding='utf-8') if path().is_file() else ('# Напиши своё решение здесь. Пример находится во вкладке «Разбор».\n' if kind=='python' else '-- Напиши свой запрос здесь.\n'))
        state['loaded']=True
        refresh();show(result,'Начни с теории, затем перейди к разбору и практике. Изменения сохраняются в учебной папке.')
    def refresh():
        step=lesson();phase=state['phase'];title.config(text=step.title)
        for w in phase_bar.winfo_children():w.destroy()
        for i,text in enumerate(phases):
            b=btn(phase_bar,text,lambda x=i:set_phase(x),i==phase);b.grid(row=i//3,column=i%3,sticky='ew',padx=(0,4),pady=2)
            phase_bar.columnconfigure(i%3,weight=1)
        if phase in (2,3,4):
            edit_frame.pack_forget();lesson_text.pack_forget()
            lesson_text.configure(height=5)
            lesson_text.pack(fill='x');show(lesson_text,'САМОСТОЯТЕЛЬНОЕ ЗАДАНИЕ\n\n'+challenge())
            edit_frame.pack(fill='both',expand=True)
            if phase==2:show(result,'Напиши решение по условию выше. «Запустить» выполняет код, «Проверить» проверяет требования. Подсказка доступна отдельно.')
            if phase==3:show(result,'ПРОВЕРКА: '+challenge()+'\n\nЗапуск показывает поведение кода. Проверка подтверждает выполнение условия.')
            if phase==4:show(result,'ЗАКРЕПЛЕНИЕ: '+challenge()+'\nПопроси ИИ объяснить выбранную строку или проверь решение.')
        else:
            edit_frame.pack_forget();lesson_text.pack(fill='both',expand=True)
            lesson_text.configure(height=8)
            show(lesson_text,('ТЕОРИЯ\n\n'+step.theory if phase==0 else 'ПРИМЕР КОДА\n\n'+step.code+'\n\nПОСТРОЧНЫЙ РАЗБОР\n\n'+step.walkthrough))
    def set_phase(i):state['phase']=i;refresh()
    def append_output(text):
        result.config(state='normal');result.insert('end',text);result.see('end');result.config(state='disabled')
    def stop():
        run=state.get('run')
        if run and not run.finished:run.stop()
    def send_input(event=None):
        run=state.get('run')
        if run and not run.finished:
            try:
                text=console_input.get();run.send_input(text);append_output(text+'\n');console_input.delete(0,'end')
            except ValueError as exc:append_output('\n'+str(exc))
        return 'break'
    console_input.bind('<Return>',send_input)
    btn(inputbar,'Ввести',send_input).pack(side='left')
    btn(inputbar,'Конец ввода',lambda:state['run'].close_input() if state.get('run') else None).pack(side='left',padx=4)
    btn(inputbar,'■ Стоп',stop).pack(side='left')
    def execute():
        if state['checking']:return
        if state.get('run') and not state['run'].finished:
            append_output('\nСначала останови текущую программу.\n');return
        code=editor.get('1.0','end-1c');step=lesson()
        try:
            if kind=='python':
                show(result,'КОНСОЛЬ PYTHON\n')
                run=RunningPython(code,interactive=True,timeout=60)
                state['run']=run;state['error']=''
                def poll():
                    if not editor.winfo_exists():run.stop();return
                    if state.get('run') is not run:return
                    chunks=[];done=False
                    while True:
                        try:stream,value=run.events.get_nowait()
                        except queue.Empty:break
                        if stream=='done':done=True
                        else:chunks.append(value)
                    if chunks:append_output(''.join(chunks))
                    if done:
                        state['error']=run.stderr or run.reason
                        append_output('\n'+(run.reason or f'Завершено. Код выхода: {run.returncode}')+'\n')
                    else:schedule(poll)
                schedule(poll);console_input.focus_set()
            else:
                output=run_sql(code,allow_writes=step.mode=='ddl')
                show(result,'РЕЗУЛЬТАТ SQL\n'+'\n'.join(output))
        except Exception as e:
            state['error']=str(e)
            show(result,type(e).__name__+': '+str(e))

    def check():
        if state['checking'] or (state.get('run') and not state['run'].finished):
            append_output('\nДождись завершения текущего запуска.\n');return
        code=editor.get('1.0','end-1c');step=lesson()
        state['checking']=True
        replies=queue.Queue();show(result,'Проверка решения по условию практики…')
        def worker():
            try:replies.put(check_python(code,step) if kind=='python' else check_sql(code,step))
            except Exception as exc:replies.put((False,type(exc).__name__+': '+str(exc)))
        def poll():
            if not editor.winfo_exists():return
            try:ok,msg=replies.get_nowait()
            except queue.Empty:schedule(poll);return
            state['checking']=False
            if ok and code == editor.get('1.0','end-1c'):
                academy.verified.add(step.slug)
                academy.completed.add('route-'+step.slug);academy._save_progress();academy._update_status()
                if hasattr(academy,'_refresh_practice'):academy._refresh_practice()
            elif ok:
                ok=False;msg='Код изменился во время проверки. Проверь текущую версию ещё раз.'
            show(result,('✓ ' if ok else '✕ ')+msg+'\n\n'+('Урок подтверждён функциональными критериями.' if ok else 'Исправь решение и попробуй снова.'))
            state['error']='' if ok else msg
        threading.Thread(target=worker,daemon=True).start();schedule(poll)
    def show_reference(term=''):
        win=tk.Toplevel(academy.win);win.title(('Python' if kind=='python' else 'SQL')+' · Code Encyclopedia');win.geometry('1050x700');win.configure(bg=c['bg'])
        head=tk.Frame(win,bg=c['bg']);head.pack(fill='x',padx=15,pady=12)
        label(head,'CODE ENCYCLOPEDIA  ·  '+kind.upper(),17,c['accent'],True).pack(side='left')
        search_var=tk.StringVar(value=term);searchbox=tk.Entry(win,textvariable=search_var,font=('Segoe UI',12),bg=c['panel'],fg=c['ink'],insertbackground=c['ink'],bd=0)
        searchbox.pack(fill='x',padx=15,pady=(0,10),ipady=9)
        content=tk.PanedWindow(win,orient='horizontal',bg=c['bg'],sashwidth=6);content.pack(fill='both',expand=True,padx=15,pady=(0,15))
        left=tk.Frame(content,bg=c['panel']);right=tk.Frame(content,bg=c['panel']);content.add(left,minsize=220,width=280);content.add(right,minsize=440)
        matches=tk.Listbox(left,font=('Segoe UI',11),bg=c['panel'],fg=c['ink'],selectbackground=c['tag'],selectforeground=c['accent'],bd=0,highlightthickness=0,exportselection=False);matches.pack(fill='both',expand=True,padx=8,pady=8)
        detail=tk.Text(right,font=('Segoe UI',11),bg=c['panel'],fg=c['ink'],wrap='word',bd=0,padx=18,pady=15,state='disabled');detail.pack(fill='both',expand=True)
        _enable_editor_shortcuts(detail)
        found=[]
        def select(event=None):
            if not matches.curselection():return
            item=found[matches.curselection()[0]]
            show(detail,item.name+'  ·  '+item.category+'\n\n'+item.meaning+'\n\nСИНТАКСИС\n'+item.syntax+'\n\nПРИМЕР\n'+item.example+'\n\nВАЖНО\n'+item.note)
        def update(*_):
            found[:]=search(kind,search_var.get());matches.delete(0,'end')
            for e in found:matches.insert('end',e.name+'  ·  '+e.category)
            if found:matches.selection_set(0);select()
            else:show(detail,'По запросу ничего не найдено.')
        matches.bind('<<ListboxSelect>>',select);search_var.trace_add('write',update);update()
    btn(controls,'▶ Запустить',execute,True).pack(side='left',padx=(0,6))
    btn(controls,'✓ Проверить',check).pack(side='left',padx=(0,6))
    btn(controls,'Сохранить',save).pack(side='left',padx=(0,6))
    btn(controls,'Подсказка',lambda:show(result,lesson().hint)).pack(side='left',padx=(0,6))
    def ask_mentor():
        academy._ask_from_editor(editor,'practice.py' if kind=='python' else 'practice.sql')
        academy.mentor_area.set('Python Studio' if kind=='python' else 'SQL Laboratory')
        academy.mentor_lesson.set(lesson().title)
        academy.mentor_error.set(state['error'][-1600:])
        academy.tutor_mode.set('hint')
        academy.tutor_question.delete('1.0','end');academy.tutor_question.insert('1.0','Дай подсказку без готового решения. Условие: '+challenge())
    btn(controls,'ИИ-наставник',ask_mentor).pack(side='right')
    navbuttons=tk.Frame(workspace,bg=c['bg']);navbuttons.grid(row=6,column=0,sticky='ew',pady=(6,0))
    btn(navbuttons,'← Предыдущий урок',lambda:switch(state['index']-1)).pack(side='left')
    btn(navbuttons,'Следующий урок →',lambda:switch(state['index']+1)).pack(side='right')
    listing.bind('<<ListboxSelect>>',lambda e:switch(listing.curselection()[0]) if listing.curselection() and listing.curselection()[0]!=state['index'] else None)
    editor.bind('<Control-s>',lambda e:(save(), 'break')[1])
    def close_studio():
        stop()
        for job in state['callbacks']:editor.after_cancel(job)
        state['callbacks'].clear()
        if state['loaded']:save(True)
    academy._studio_closers.append(close_studio)
    def open_lesson(slug,phase=0):
        index=next((i for i,s in enumerate(route) if s.slug==slug),None)
        if index is None:return
        if state['checking']:return
        switch(index);set_phase(phase)
    academy._studio_routes[kind]=open_lesson
    def close_page(event):
        if event.widget is page:
            stop()
            if state['loaded']:
                try:save(True)
                except (OSError,tk.TclError):pass
    page.bind('<Destroy>',close_page,add='+')
    switch(0)
