"""BahonIQ Code Academy: six integrated learning workspaces."""
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from .studio_core import Workspace
from .architecture import list_project_files, read_project_file, describe_code
from .architecture_book import CHAPTERS, chapter_source
from .architecture_pro import explain_line, explain_block, import_map, safe_copy_target
from .ai_tutor import ask_tutor_detailed, PROVIDER_LABELS
from .mentor_core import MentorSession
from .studio_v4 import build_studio, _enable_editor_shortcuts
from .editor import CodeEditor

GREEN='#009246'; RED='#CE2B37'; DARK='#17352A'; BG='#F3F7F5'; WHITE='#FFFFFF'; INK='#162A23'

class PageRouter:
    def __init__(self,container):self.container=container;self.pages={};self.buttons={};self.current=None
    def add(self,key,title,page,button):self.pages[key]=page;self.buttons[key]=button
    def select(self,page):
        key=next((k for k,v in self.pages.items() if v is page),None)
        if key is None or str(self.buttons[key].cget('state'))=='disabled':return
        for name,frame in self.pages.items():frame.pack_forget();self.buttons[name].config(bg='#20493C' if name!=key else GREEN,fg='white')
        page.pack(fill='both',expand=True);self.current=key
    def set_enabled(self,key,enabled):self.buttons[key].config(state='normal' if enabled else 'disabled')

class AcademyWindow:
    def __init__(self,parent):
        self.parent=parent; self.workspace=Workspace(); self.current_lesson=0;self.quiz_index=0;self.quiz_score=0
        self.progress_path=Path.home()/'.bahoniq_code_academy_progress.json'
        self.completed=self._load_progress()
        self.verified=self._load_verified()
        self._studio_closers=[]
        self._studio_routes={}
        self.win=tk.Toplevel(parent);self.win.title('BahonIQ Code Academy — Studio Edition')
        self.win.geometry('1440x900');self.win.minsize(1050,690);self.win.configure(bg=BG)
        self.win.protocol('WM_DELETE_WINDOW',self._close)
        try:
            ico=Path(__file__).resolve().parents[2]/'assets'/'bahoniq_italy.ico'
            if ico.is_file():self.win.iconbitmap(str(ico))
        except (OSError,tk.TclError):pass
        flag=tk.Frame(self.win,height=5);flag.pack(fill='x')
        for c in (GREEN,'white',RED):tk.Frame(flag,bg=c).pack(side='left',fill='both',expand=True)
        head=tk.Frame(self.win,bg=WHITE);head.pack(fill='x')
        tk.Label(head,text='BahonIQ  /  CODE ACADEMY',bg=WHITE,fg=GREEN,font=('Segoe UI',20,'bold')).pack(side='left',padx=20,pady=13)
        self.status=tk.Label(head,text='',bg=WHITE,fg=DARK,font=('Segoe UI',10));self.status.pack(side='right',padx=20)
        shell=tk.Frame(self.win,bg=BG);shell.pack(fill='both',expand=True)
        nav=tk.Frame(shell,bg='#17352A',width=230);nav.pack(side='left',fill='y');nav.pack_propagate(False)
        content=tk.Frame(shell,bg=WHITE);content.pack(side='left',fill='both',expand=True)
        self.tabs=PageRouter(content)
        self.pages={}
        items=[('python','1 · PYTHON'),('sql','2 · SQL'),('architecture','3 · КНИГА И КОД'),('builder','4 · КОНСТРУКТОР'),('practice','ПРАКТИЧЕСКИЕ ЗАНЯТИЯ'),('tests','ТЕСТЫ И АТТЕСТАЦИЯ'),('tutor','ИИ-НАСТАВНИК')]
        tk.Label(nav,text='УЧЕБНЫЙ МАРШРУТ',bg='#17352A',fg='#8DE3B8',font=('Segoe UI',11,'bold')).pack(fill='x',padx=15,pady=(22,12))
        for key,title in items:
            page=tk.Frame(content,bg=WHITE);self.pages[key]=page
            button=tk.Button(nav,text=title,anchor='w',bg='#20493C',fg='white',bd=0,relief='flat',font=('Segoe UI',10,'bold'),padx=15,pady=13)
            button.config(command=lambda p=page:self.tabs.select(p));button.pack(fill='x',padx=8,pady=2)
            self.tabs.add(key,title,page,button)
        build_studio(self,'python');build_studio(self,'sql');self._build_architecture();self._build_builder();self._build_tutor();self._build_tests();self._update_status()
        from .learning_hub import build_practice_catalogue
        build_practice_catalogue(self)
        self.tabs.select(self.pages['python'])
    def _load_progress(self):
        try:return set(json.loads(self.progress_path.read_text(encoding='utf-8')).get('completed',[]))
        except (OSError,ValueError,TypeError):return set()
    def _close(self):
        try:
            for close in self._studio_closers:close()
        except OSError as exc:
            messagebox.showerror('Черновики',f'Не удалось сохранить черновик: {exc}',parent=self.win)
            return
        self.win.destroy()
    def _save_progress(self):
        try:self.progress_path.write_text(json.dumps({'completed':sorted(self.completed),'verified_practice':sorted(self.verified),'practice_version':2},ensure_ascii=False),encoding='utf-8')
        except OSError:messagebox.showwarning('Прогресс','Не удалось сохранить прогресс',parent=self.win)
    def _load_verified(self):
        try:return set(json.loads(self.progress_path.read_text(encoding='utf-8')).get('verified_practice',[]))
        except (OSError,ValueError,TypeError):return set()
    def _update_status(self):
        from .professional_curriculum import PYTHON,SQL
        py=sum('route-'+x.slug in self.completed for x in PYTHON);sq=sum('route-'+x.slug in self.completed for x in SQL)
        book=sum('book-'+str(i) in self.completed for i in range(len(CHAPTERS)))
        verified=sum(x.slug in self.verified for x in (*PYTHON,*SQL))
        self.status.config(text=f'Python {py}/{len(PYTHON)} · SQL {sq}/{len(SQL)} · Книга {book}/{len(CHAPTERS)} · Практика {verified}/{len(PYTHON)+len(SQL)}')
        # Progress is informational only. Every workspace is available from the
        # first launch, so learners may study in the order that suits them.
        for key in ('python', 'sql', 'architecture', 'builder', 'tutor', 'tests'):
            self.tabs.set_enabled(key, True)
    def _label(self,parent,text,size=11):return tk.Label(parent,text=text,bg=WHITE,fg=DARK,font=('Segoe UI',size,'bold'),anchor='w')
    def _btn(self,parent,text,command,primary=False):return tk.Button(parent,text=text,command=command,bg=GREEN if primary else '#E8F5EE',fg='white' if primary else DARK,relief='flat',padx=12,pady=7,cursor='hand2')
    def _editor(self,parent,height=12):
        return CodeEditor(parent,height=height)
    def _readonly(self,parent,height=6):
        return _enable_editor_shortcuts(tk.Text(parent,height=height,font=('Consolas',10),bg=BG,fg=DARK,wrap='word',padx=10,pady=8))
    def _set(self,widget,text):widget.config(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.config(state='disabled')
    def _build_architecture(self):
        page = self.pages['architecture']
        tabs = ttk.Notebook(page)
        tabs.pack(fill='both', expand=True, padx=10, pady=10)
        book = tk.Frame(tabs, bg=WHITE)
        explorer = tk.Frame(tabs, bg=WHITE)
        tabs.add(book, text='  Книга BahonIQ  ')
        tabs.add(explorer, text='  Architecture Explorer Pro  ')

        # Book: searchable chapter catalog with source-grounded explanatory reading.
        from .architecture_book import chapter_reading
        sidebar = tk.Frame(book, bg=WHITE, width=310)
        sidebar.pack(side='left', fill='y', padx=10, pady=10)
        sidebar.pack_propagate(False)
        self._label(sidebar, 'КНИГА BAHONIQ · ОТ А ДО Я').pack(fill='x', pady=7)
        search_var = tk.StringVar()
        tk.Entry(sidebar, textvariable=search_var, font=('Segoe UI', 11)).pack(fill='x', pady=5)
        counter = tk.Label(sidebar, bg=WHITE, fg=DARK, anchor='w')
        counter.pack(fill='x')
        chapters = tk.Listbox(sidebar, font=('Segoe UI', 10), exportselection=False,
                              selectbackground=GREEN, activestyle='none')
        chapters.pack(fill='both', expand=True)
        visible = []
        content = tk.Frame(book, bg=WHITE)
        content.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        book_title = self._label(content, '', 15)
        book_title.pack(fill='x')
        reading = self._readonly(content, 19)
        reading.pack(fill='both', expand=True, pady=7)
        scroll_reading = ttk.Scrollbar(reading, orient='vertical', command=reading.yview)
        reading.configure(yscrollcommand=scroll_reading.set)
        scroll_reading.pack(side='right', fill='y')
        self._label(content, 'ИСХОДНЫЙ КОД · ТОЛЬКО ЧТЕНИЕ', 10).pack(fill='x')
        book_code = self._editor(content, 13)
        book_code.pack(fill='both', expand=True, pady=6)
        scroll_code = ttk.Scrollbar(book_code, orient='vertical', command=book_code.yview)
        book_code.configure(yscrollcommand=scroll_code.set)
        scroll_code.pack(side='right', fill='y')
        book_code.configure(state='disabled')
        book_current = {'file': '', 'line': 1, 'index': 0}
        def refresh_chapters(*args):
            query=search_var.get().casefold().strip()
            chapters.delete(0,'end');visible.clear()
            for chapter in CHAPTERS:
                if query and query not in (chapter.title+' '+chapter.file+' '+chapter.section).casefold():
                    continue
                visible.append(chapter)
                chapters.insert('end', f'{chapter.section} / {chapter.title}')
            counter.configure(text=f'Глав: {len(visible)} из {len(CHAPTERS)} · файлов: {len(set(c.file for c in CHAPTERS))}')
        def open_chapter(event=None):
            selected=chapters.curselection()
            if not selected:return
            chapter=visible[selected[0]]
            try:
                source,lineno,warning=chapter_source(chapter)
                text=chapter_reading(chapter)
            except (OSError,ValueError) as exc:
                self._set(reading, f'Исходный файл недоступен: {exc}')
                return
            book_title.configure(text=chapter.title)
            self._set(reading,text)
            reading.yview_moveto(0)
            book_code.configure(state='normal')
            book_code.delete('1.0','end')
            book_code.insert('1.0',source)
            book_code.set_language(chapter.file)
            book_code.tag_remove('focus','1.0','end')
            if lineno:
                book_code.tag_add('focus',f'{lineno}.0',f'{lineno}.end')
                book_code.tag_config('focus',background='#35664E')
                book_code.see(f'{lineno}.0')
            book_code.configure(state='disabled')
            book_current.update(file=chapter.file,line=lineno or 1,index=CHAPTERS.index(chapter))
        search_var.trace_add('write',refresh_chapters)
        chapters.bind('<<ListboxSelect>>',open_chapter)
        def move_chapter(delta):
            selected=chapters.curselection()
            if not visible:return
            idx=max(0,min(len(visible)-1,(selected[0] if selected else 0)+delta))
            chapters.selection_clear(0,'end');chapters.selection_set(idx)
            chapters.see(idx);open_chapter()
        nav=tk.Frame(sidebar,bg=WHITE);nav.pack(fill='x',pady=5)
        self._btn(nav,'← Назад',lambda:move_chapter(-1)).pack(side='left')
        self._btn(nav,'Далее →',lambda:move_chapter(1)).pack(side='right')
        self._btn(sidebar,'Открыть в исследователе',lambda:(tabs.select(explorer),select_file(book_current['file'],book_current['line']))).pack(fill='x',pady=6)
        def complete_chapter():
            self.completed.add('book-'+str(book_current['index']));self._save_progress();self._update_status()
            counter.configure(text=counter.cget('text')+' · глава изучена')
        self._btn(sidebar,'✓ Глава прочитана',complete_chapter,True).pack(fill='x',pady=3)
        refresh_chapters()
        if visible:chapters.selection_set(0);open_chapter()

        # Explorer: source browser, deterministic AST explanations, import links, tutor.
        left = tk.Frame(explorer, bg=WHITE, width=290)
        left.pack(side='left', fill='y', padx=8, pady=8)
        left.pack_propagate(False)
        self._label(left, 'ФАЙЛЫ WORK CENTER').pack(fill='x', pady=6)
        tree = ttk.Treeview(left, show='tree')
        tree.pack(fill='both', expand=True)
        right = tk.Frame(explorer, bg=WHITE)
        right.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        self._label(right, 'КОД · НАЖМИ НА СТРОКУ').pack(fill='x')
        source_view = self._editor(right, 18)
        source_view.pack(fill='both', expand=True, pady=6)
        source_view.configure(state='disabled')
        self._label(right, 'ОБЪЯСНЕНИЕ / СВЯЗИ').pack(fill='x')
        details = self._readonly(right, 8)
        details.pack(fill='x', pady=5)
        current = {'name': '', 'source': '', 'line': 1}
        def select_file(relative, lineno=1):
            if not relative:
                return
            try:
                from .builder import TEMPLATES
                source = TEMPLATES[relative] if relative in TEMPLATES else read_project_file(relative)
            except (OSError, ValueError) as exc:
                self._set(details, str(exc))
                return
            current.update(name=relative, source=source, line=lineno)
            source_view.configure(state='normal')
            source_view.delete('1.0', 'end')
            source_view.insert('1.0', source)
            source_view.set_language(relative)
            source_view.configure(state='disabled')
            source_view.see(f'{lineno}.0')
            show_line(lineno)
        def show_line(lineno):
            current['line'] = lineno
            source = current['source']
            name = current['name']
            if not source:
                return
            if name.endswith('.py'):
                text = explain_line(source, lineno)
                deps = import_map(source, name)
                text += '\n\nИМПОРТЫ:\n' + ('\n'.join(f'• {a} → {b}' for a, b in deps[:30]) or 'Нет импортов')
            else:
                text = 'Файл данных или настроек. Выбери Python-файл для AST-разбора.'
            self._set(details, f'{name} · строка {lineno}\n\n{text}')
        def click_line(event=None):
            if current['source']:
                show_line(int(source_view.index('insert').split('.')[0]))
        source_view.bind('<ButtonRelease-1>', click_line)
        def refresh():
            tree.delete(*tree.get_children())
            nodes = {}
            for relative in list_project_files():
                parts = relative.split('/')
                parent = ''
                for i, part in enumerate(parts):
                    key = '/'.join(parts[:i+1])
                    if key not in nodes:
                        nodes[key] = tree.insert(parent, 'end', text=part, values=(key,))
                    parent = nodes[key]
        def selected(event=None):
            node = tree.focus()
            values = tree.item(node, 'values')
            if values and '.' in values[0].split('/')[-1]:
                select_file(values[0])
        tree.bind('<<TreeviewSelect>>', selected)
        def explain_selected_block():
            if not current['name'].endswith('.py'):
                return
            description, code = explain_block(current['source'], current['line'])
            self._set(details, description + '\n\n' + code[:5000])
        def ask_ai():
            if not current['source']:
                return
            description, code = explain_block(current['source'], current['line']) if current['name'].endswith('.py') else ('Файл', current['source'][:1500])
            self.tabs.select(self.pages['tutor'])
            self.tutor_question.delete('1.0', 'end')
            self.tutor_question.insert('1.0', f'Объясни простыми словами этот блок из {current["name"]}, зачем он нужен и как связан с остальным приложением.\n{description}\n```python\n{code[:1700]}\n```')
        def make_copy():
            if not current['name'].endswith('.py'):
                messagebox.showinfo('Учебная копия', 'Выбери Python-файл.', parent=self.win)
                return
            folder = filedialog.askdirectory(parent=self.win, title='Выбери отдельную папку для учебной копии')
            if not folder:
                return
            try:
                target = safe_copy_target(folder, current['name'])
                if target.exists():
                    raise ValueError('Учебная копия уже существует; перезапись запрещена.')
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8') as output:
                    output.write(current['source'])
                messagebox.showinfo('Учебная копия', f'Сохранено: {target}', parent=self.win)
            except (OSError, ValueError) as exc:
                messagebox.showerror('Учебная копия', str(exc), parent=self.win)
        actions = tk.Frame(right, bg=WHITE)
        actions.pack(fill='x', pady=4)
        self._btn(actions, 'Объяснить блок def / class', explain_selected_block).pack(side='left', padx=3)
        self._btn(actions, 'Спросить ИИ', ask_ai, True).pack(side='left', padx=3)
        self._btn(actions, 'Создать учебную копию', make_copy).pack(side='left', padx=3)
        self._btn(left, 'Обновить дерево', refresh).pack(fill='x', pady=7)
        refresh()
        chapters.selection_set(0)
        open_chapter()
    def _build_builder(self):
        from .builder_pro_ui import build_builder
        build_builder(self)
    def _build_tutor(self):
        page = self.pages['tutor']
        self.mentor_session = MentorSession(Path.home() / '.bahoniq_academy' / 'mentor_history.json')
        frame = tk.Frame(page, bg='#EDF3F0')
        frame.pack(fill='both', expand=True)
        banner = tk.Frame(frame, bg='#172C27')
        banner.pack(fill='x')
        tk.Label(banner, text='AI MENTOR  /  УЧЕБНЫЙ НАСТАВНИК', bg='#172C27', fg='white',
                 font=('Segoe UI', 16, 'bold')).pack(side='left', padx=20, pady=16)
        self.mentor_banner = tk.Label(banner, text='Gemini · облако  +  Ollama резерв · история сохраняется', bg='#172C27',
                 fg='#A7D4BD')
        self.mentor_banner.pack(side='right', padx=20)
        panes = tk.PanedWindow(frame, orient='horizontal', sashwidth=6, bg='#EDF3F0')
        panes.pack(fill='both', expand=True, padx=12, pady=12)
        left = tk.Frame(panes, bg=WHITE)
        right = tk.Frame(panes, bg=WHITE)
        panes.add(left, minsize=440, width=800)
        panes.add(right, minsize=300, width=380)
        self._label(left, 'ИСТОРИЯ ОБУЧЕНИЯ', 12).pack(anchor='w', padx=14, pady=(12, 5))
        self.tutor_history = self._readonly(left, 18)
        self.tutor_history.pack(fill='both', expand=True, padx=12, pady=5)
        self._label(left, 'ВОПРОС НАСТАВНИКУ', 11).pack(anchor='w', padx=14, pady=(10, 0))
        self.tutor_question = self._editor(left, 5)
        self.tutor_question.set_language('plain')
        self.tutor_question.pack(fill='x', padx=12, pady=8)
        options = tk.Frame(left, bg=WHITE)
        options.pack(fill='x', padx=12, pady=8)
        self.tutor_mode = tk.StringVar(value='hint')
        ttk.Combobox(options, textvariable=self.tutor_mode, state='readonly', width=18,
                     values=['hint', 'explain', 'review', 'solution', 'quiz']).pack(side='left')
        import os
        self.tutor_model = tk.StringVar(value=os.getenv('OLLAMA_MODEL', 'qwen2.5:7b'))
        tk.Label(options, text='Резерв:', bg=WHITE, fg='#53665D').pack(side='left', padx=(10, 2))
        ttk.Combobox(options, textvariable=self.tutor_model, width=14,
                     values=['qwen2.5:7b', 'qwen2.5:3b']).pack(side='left', padx=(0, 8))
        self.tutor_timeout = tk.StringVar(value='180')
        ttk.Combobox(options, textvariable=self.tutor_timeout, state='readonly', width=6,
                     values=['90', '180', '300', '600']).pack(side='left')
        self.tutor_send = self._btn(options, 'Отправить вопрос', self._send_tutor, True)
        self.tutor_send.pack(side='right')
        self._btn(options, 'Очистить историю', self._clear_mentor).pack(side='right', padx=8)
        self._label(right, 'КОНТЕКСТ УРОКА', 12).pack(anchor='w', padx=12, pady=(12, 6))
        self.mentor_area = tk.StringVar(value='Python Studio')
        self.mentor_lesson = tk.StringVar()
        self.mentor_file = tk.StringVar()
        self.mentor_error = tk.StringVar()
        for caption, variable in [('Раздел', self.mentor_area), ('Тема урока', self.mentor_lesson),
                                  ('Имя файла', self.mentor_file), ('Текст ошибки', self.mentor_error)]:
            tk.Label(right, text=caption, bg=WHITE, fg='#53665D').pack(anchor='w', padx=12, pady=(9, 2))
            ttk.Entry(right, textvariable=variable).pack(fill='x', padx=12)
        tk.Label(right, text='Код для разбора (можно вставить свой)', bg=WHITE,
                 fg='#53665D').pack(anchor='w', padx=12, pady=(12, 3))
        self.mentor_code = self._editor(right, 14)
        self.mentor_code.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self._refresh_mentor_history()

    def _refresh_mentor_history(self):
        lines = []
        for item in self.mentor_session.messages:
            lines.append(('ВЫ: ' if item['role'] == 'user' else 'НАСТАВНИК: ') + item['content'])
        self._set(self.tutor_history, '\n\n'.join(lines) if lines else 'Задай первый вопрос. История сохраняется между запусками.')

    def _clear_mentor(self):
        if messagebox.askyesno('История наставника', 'Очистить историю вопросов и ответов?', parent=self.win):
            self.mentor_session.clear()
            self._refresh_mentor_history()

    def _ask_from_editor(self, editor, filename):
        self.tabs.select(self.pages['tutor'])
        self.mentor_file.set(filename)
        self.mentor_code.set_language(filename)
        self.mentor_code.delete('1.0', 'end')
        self.mentor_code.insert('1.0', editor.get('1.0', 'end-1c')[:6000])
        self.tutor_question.delete('1.0', 'end')
        self.tutor_question.insert('1.0', 'Объясни этот код построчно и предложи упражнение.')

    def _ask_architecture(self, name, viewer):
        if name:
            self._ask_from_editor(viewer, name)
            self.mentor_area.set('Architecture Explorer')

    def _send_tutor(self):
        question = self.tutor_question.get('1.0', 'end-1c').strip()
        if not question:
            return
        context = {'area': self.mentor_area.get(), 'lesson': self.mentor_lesson.get(),
                   'file': self.mentor_file.get(), 'error': self.mentor_error.get(),
                   'code': self.mentor_code.get('1.0', 'end-1c')}
        mode = self.tutor_mode.get()
        model = self.tutor_model.get()
        timeout = int(self.tutor_timeout.get())
        history = list(self.mentor_session.messages)
        self.tutor_send.config(state='disabled')
        self._set(self.tutor_history, 'Ожидание ответа ИИ (Gemini → Ollama)...\n\n' +
                  '\n\n'.join(('ВЫ: ' if m['role']=='user' else 'НАСТАВНИК: ') + m['content'] for m in history))
        def worker():
            try:
                answer, provider = ask_tutor_detailed(question, model=model, timeout=timeout, mode=mode,
                                                      context=context, history=history)
                error = None
            except Exception as exc:
                answer, provider, error = '', '', str(exc)
            def done():
                if not self.win.winfo_exists():
                    return
                self.tutor_send.config(state='normal')
                if provider:
                    self.mentor_banner.config(text=PROVIDER_LABELS.get(provider, provider) + '  ·  история сохраняется')
                if error:
                    messagebox.showwarning('ИИ-наставник', error, parent=self.win)
                else:
                    try:
                        self.mentor_session.add_exchange(question, answer, context)
                    except OSError as exc:
                        messagebox.showwarning('История', str(exc), parent=self.win)
                    self._refresh_mentor_history()
            try:
                self.win.after(0, done)
            except RuntimeError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _build_tests(self):
        from .learning_hub import build_knowledge_quiz
        from .adaptive_assessment_ui import build_adaptive_assessment
        page=self.pages['tests']
        tabs=ttk.Notebook(page);tabs.pack(fill='both',expand=True,padx=10,pady=10)
        knowledge=tk.Frame(tabs);practical=tk.Frame(tabs)
        tabs.add(knowledge,text='  Тесты на понимание  ')
        tabs.add(practical,text='  Практическая аттестация  ')
        build_knowledge_quiz(self,knowledge)
        self.pages['tests']=practical
        build_adaptive_assessment(self)
        self.pages['tests']=page

def open_code_academy(parent):return AcademyWindow(parent)
