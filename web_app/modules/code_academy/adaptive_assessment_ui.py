"""Small practical assessment UI backed by generated variants."""
import tkinter as tk
from .adaptive_assessment import evaluate,generate
from .editor import CodeEditor

WHITE='#FFFFFF';DARK='#17352A';GREEN='#009246';INK='#142720'


def build_adaptive_assessment(host):
    page=host.pages['tests'];current={'task':None,'track':'python','passed':0}
    head=tk.Frame(page,bg=DARK);head.pack(fill='x')
    tk.Label(head,text='PRACTICAL ASSESSMENT · НОВЫЙ ВАРИАНТ КАЖДУЮ ПОПЫТКУ',bg=DARK,fg='white',font=('Segoe UI',15,'bold')).pack(side='left',padx=18,pady=14)
    tk.Label(head,text='Без базы заучиваемых ответов',bg=DARK,fg='#B4D8C5').pack(side='right',padx=18)
    body=tk.Frame(page,bg=WHITE);body.pack(fill='both',expand=True,padx=18,pady=16)
    top=tk.Frame(body,bg=WHITE);top.pack(fill='x')
    track=tk.StringVar(value='python')
    for value,text in [('python','Python-практика'),('sql','SQL-практика')]:
        tk.Radiobutton(top,text=text,variable=track,value=value,bg=WHITE,fg=DARK,font=('Segoe UI',11,'bold')).pack(side='left',padx=4)
    title=tk.Label(body,text='',bg=WHITE,fg=DARK,font=('Segoe UI',16,'bold'),anchor='w');title.pack(fill='x',pady=(15,5))
    prompt=tk.Label(body,text='',bg='#EDF6F1',fg=DARK,font=('Segoe UI',11),justify='left',anchor='w',wraplength=1100,padx=14,pady=12);prompt.pack(fill='x')
    editor=CodeEditor(body,bg=INK,fg='#E7F5EC',insertbackground='white',font=('Consolas',11),undo=True,wrap='none',padx=14,pady=12);editor.pack(fill='both',expand=True,pady=10)
    feedback=tk.Label(body,text='',bg=WHITE,fg=DARK,font=('Segoe UI',10),justify='left',anchor='w',wraplength=1100);feedback.pack(fill='x')
    ai_box=tk.Label(body,text='',bg='#FFF9E6',fg='#7A5200',font=('Segoe UI',10),justify='left',anchor='w',wraplength=1100,padx=12,pady=8)
    bar=tk.Frame(body,bg=WHITE);bar.pack(fill='x',pady=8)

    def explain_with_ai():
        task = current.get('task')
        answer = editor.get('1.0', 'end-1c')
        last_err = current.get('last_err', '')
        if not task or not last_err:
            feedback.config(text='Сначала проверьте решение, чтобы получить ошибку для анализа.')
            return
        ai_box.config(text='⏳ ИИ-Ментор анализирует ошибку и готовит подсказку...', bg='#FFF9E6', fg='#7A5200')
        ai_box.pack(fill='x', pady=6)

        def worker():
            from .ai_tutor import ask_tutor
            import threading
            q = (
                f"Ученик допустил ошибку в тесте.\n"
                f"Задание: {task.prompt}\n"
                f"Код/запрос ученика:\n{answer}\n"
                f"Сообщение системы проверки: {last_err}\n\n"
                f"Дай понятное развернутое объяснение сути ошибки и 1-2 наводящие подсказки, "
                f"но СТРОГО не пиши готовый правильный ответ."
            )
            try:
                explanation = ask_tutor(
                    q,
                    mode='hint',
                    context={'error': last_err, 'code': answer, 'area': 'Адаптивный тест'}
                )
            except Exception as e:
                explanation = f"Обрати внимание на условие задачи и формат возвращаемых данных. Детали проверки: {last_err}"

            page.after(0, lambda: ai_box.config(
                text=f"💡 ИИ-Разбор ошибки:\n{explanation}",
                bg='#FFF9E6',
                fg='#4A3200'
            ))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def next_task():
        task=generate(track.get());current['task']=task
        current['last_err']=''
        ai_box.pack_forget()
        editor.set_language(track.get())
        title.config(text=task.title+f' · вариант {task.seed}')
        prompt.config(text=task.prompt);editor.delete('1.0','end');editor.insert('1.0',task.starter)
        feedback.config(text='Решение проверяется на скрытых данных. Новый вариант изменит условие и эталон.',fg=DARK)

    def check():
        task=current['task'];answer=editor.get('1.0','end-1c')
        if not task or not answer.strip():return
        ok,message=evaluate(task,answer)
        current['last_err'] = message if not ok else ''
        if ok:
            current['passed']+=1;host.completed.add('adaptive-'+task.track+'-'+str(task.seed));host._save_progress();host._update_status()
            ai_box.pack_forget()
            ai_btn.pack_forget()
        else:
            ai_btn.pack(side='left', padx=8)
        feedback.config(text=('✓ ' if ok else '✕ ')+message+f' · успешно в этой сессии: {current["passed"]}',fg=GREEN if ok else '#B52E38')

    tk.Button(bar,text='Проверить решение',command=check,bg=GREEN,fg='white',relief='flat',padx=16,pady=9).pack(side='left')
    ai_btn=tk.Button(bar,text='💡 ИИ-Разбор ошибки (Ментор)',command=explain_with_ai,bg='#FFF3CD',fg='#664D03',relief='flat',padx=14,pady=9)
    tk.Button(bar,text='Новый неповторяющийся вариант',command=next_task,bg='#E8F5EE',fg=DARK,relief='flat',padx=16,pady=9).pack(side='left',padx=8)
    track.trace_add('write',lambda *_:next_task());next_task()
