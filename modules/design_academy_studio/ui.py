# -*- coding: utf-8 -*-
"""Десктопное окно BahonIQ Design Academy Studio (Tkinter Canvas + AI-наставник Gemini Flash)."""

from __future__ import annotations

import json
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from ai_service import generate_text
from web_app.modules.design_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.design_academy_studio.validation import validate_document


def open_design_academy(parent: tk.Misc | None = None) -> tk.Toplevel:
    """Открывает десктопную студию Design Academy Studio."""
    # Тёмная фирменная палитра BahonIQ
    c_bg = "#060E1B"
    c_side = "#0A1526"
    c_card = "#0F1D33"
    c_border = "#1E3352"
    c_cyan = "#00E5FF"
    c_magenta = "#E879F9"
    c_green = "#00E676"
    c_text = "#F8FAFC"
    c_muted = "#94A3B8"
    c_sub = "#64748B"
    c_canvas_bg = "#0B1220"

    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("BahonIQ — Design Academy Studio")
    win.geometry("1320x860")
    win.minsize(1050, 720)
    win.configure(bg=c_bg)

    # Загружаем данные учебной программы
    curriculum = get_curriculum()
    stages = curriculum.get("stages", [])
    lessons = curriculum.get("lessons", [])

    # Состояние студии
    state = {
        "current_stage": 1,
        "current_lesson_id": "1-1",
        "current_lesson": get_lesson("1-1"),
        "tool": "select",  # select, frame, rect, ellipse, line, text
        "objects": [],  # [{id, type, x, y, width, height, fill, stroke, radius, text, tk_id}]
        "selected_id": None,
        "drag_start": None,
        "history": [],
    }

    # ==================== ВЕРХНЯЯ ШАПКА ====================
    header = tk.Frame(win, bg=c_side, bd=0, highlightthickness=1, highlightbackground=c_border)
    header.pack(fill="x", side="top", padx=0, pady=0)

    title_frame = tk.Frame(header, bg=c_side)
    title_frame.pack(side="left", padx=20, pady=12)

    lbl_title = tk.Label(
        title_frame,
        text="🎨 Design Academy Studio",
        font=("Segoe UI", 16, "bold"),
        fg=c_text,
        bg=c_side,
    )
    lbl_title.pack(side="left")

    lbl_pill = tk.Label(
        title_frame,
        text="  AI-НАСТАВНИК • 24/7  ",
        font=("Segoe UI", 9, "bold"),
        fg=c_magenta,
        bg="#2D123D",
        bd=0,
    )
    lbl_pill.pack(side="left", padx=12)

    lbl_sub = tk.Label(
        title_frame,
        text="— Интерактивное обучение UI/UX дизайну и векторной графике",
        font=("Segoe UI", 10),
        fg=c_muted,
        bg=c_side,
    )
    lbl_sub.pack(side="left")

    # Кнопка открытия веб-версии
    def _open_web():
        webbrowser.open_new_tab("https://bahoniq.onrender.com/#designAcademy")

    btn_web = tk.Button(
        header,
        text="🌐 Открыть в браузере",
        font=("Segoe UI", 9, "bold"),
        bg="#142C4C",
        fg=c_cyan,
        activebackground="#1E3E6A",
        activeforeground=c_cyan,
        bd=0,
        padx=14,
        pady=6,
        cursor="hand2",
        command=_open_web,
    )
    btn_web.pack(side="right", padx=20, pady=12)

    # ==================== ОСНОВНОЙ КОНТЕЙНЕР (3 КОЛОНКИ) ====================
    main_body = tk.Frame(win, bg=c_bg)
    main_body.pack(fill="both", expand=True, padx=12, pady=12)

    # ----- 1. ЛЕВАЯ КОЛОНКА: СПИСОК УРОКОВ -----
    left_panel = tk.Frame(main_body, bg=c_side, width=260, highlightthickness=1, highlightbackground=c_border)
    left_panel.pack(side="left", fill="y", padx=(0, 10))
    left_panel.pack_propagate(False)

    lbl_lessons_head = tk.Label(
        left_panel,
        text="УРОКИ: ЭТАП 1 (Figma)",
        font=("Segoe UI", 10, "bold"),
        fg=c_magenta,
        bg=c_side,
        anchor="w",
    )
    lbl_lessons_head.pack(fill="x", padx=14, pady=(14, 8))

    lesson_canvas = tk.Canvas(left_panel, bg=c_side, bd=0, highlightthickness=0)
    lesson_scroll = tk.Scrollbar(left_panel, orient="vertical", command=lesson_canvas.yview)
    lesson_list_inner = tk.Frame(lesson_canvas, bg=c_side)

    lesson_list_inner.bind(
        "<Configure>", lambda e: lesson_canvas.configure(scrollregion=lesson_canvas.bbox("all"))
    )
    canvas_win = lesson_canvas.create_window((0, 0), window=lesson_list_inner, anchor="nw", width=240)
    lesson_canvas.configure(xscrollcommand=None, yscrollcommand=lesson_scroll.set)

    lesson_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
    lesson_scroll.pack(side="right", fill="y", pady=4)

    lesson_buttons = []

    def select_lesson(lesson_id: str):
        state["current_lesson_id"] = lesson_id
        state["current_lesson"] = get_lesson(lesson_id)
        curr = state["current_lesson"]
        if not curr:
            return

        # Обновляем заголовок урока
        lbl_cur_num.config(text=f"ЭТАП 1 · УРОК {curr.get('number', 1)}")
        lbl_cur_title.config(text=curr.get("title", ""))
        txt_theory.config(state="normal")
        txt_theory.delete("1.0", "end")
        txt_theory.insert("1.0", f"🎯 ЦЕЛЬ УРОКА:\n{curr.get('summary', '')}\n\n"
                                 f"💡 ТЕОРИЯ И ПРАВИЛА:\n{curr.get('theory', '')}\n\n"
                                 f"⚡ ПРАКТИЧЕСКОЕ ЗАДАНИЕ:\n{curr.get('task', '')}")
        txt_theory.config(state="disabled")

        # Подсветка кнопок
        for bid, btn in lesson_buttons:
            if bid == lesson_id:
                btn.config(bg="#2D123D", fg=c_magenta, font=("Segoe UI", 9, "bold"))
            else:
                btn.config(bg=c_side, fg=c_muted, font=("Segoe UI", 9))

        # Очищаем холст для нового урока
        state["objects"].clear()
        state["selected_id"] = None
        redraw_canvas()
        update_layers_list()
        lbl_val_status.config(text="Нажмите «Проверить макет» после выполнения задания.", fg=c_muted)

    for les in lessons:
        lid = les["id"]
        num = les["number"]
        ltitle = les["title"]
        b = tk.Button(
            lesson_list_inner,
            text=f"{num}. {ltitle}",
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
            bg=c_side,
            fg=c_muted,
            activebackground="#1E3352",
            activeforeground=c_text,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
            command=lambda i=lid: select_lesson(i),
        )
        b.pack(fill="x", pady=2)
        lesson_buttons.append((lid, b))

    # ----- 2. ЦЕНТРАЛЬНАЯ КОЛОНКА: СТУДИЯ И ХОЛСТ -----
    center_panel = tk.Frame(main_body, bg=c_card, highlightthickness=1, highlightbackground=c_border)
    center_panel.pack(side="left", fill="both", expand=True, padx=0)

    # Верх урока
    lesson_head_frame = tk.Frame(center_panel, bg=c_card)
    lesson_head_frame.pack(fill="x", padx=16, pady=12)

    lbl_cur_num = tk.Label(
        lesson_head_frame,
        text="ЭТАП 1 · УРОК 1",
        font=("Segoe UI", 9, "bold"),
        fg=c_magenta,
        bg=c_card,
    )
    lbl_cur_num.pack(anchor="w")

    lbl_cur_title = tk.Label(
        lesson_head_frame,
        text="Рабочая область и первый фрейм",
        font=("Segoe UI", 14, "bold"),
        fg=c_text,
        bg=c_card,
    )
    lbl_cur_title.pack(anchor="w", pady=(2, 6))

    # Панель вкладок (Теория / Холст редактора / Проверка)
    tabs_bar = tk.Frame(center_panel, bg=c_card)
    tabs_bar.pack(fill="x", padx=16, pady=(0, 8))

    active_tab = tk.StringVar(value="canvas")

    view_theory = tk.Frame(center_panel, bg=c_card)
    view_canvas = tk.Frame(center_panel, bg=c_card)
    view_review = tk.Frame(center_panel, bg=c_card)

    def switch_tab(tab_name: str):
        active_tab.set(tab_name)
        for name, btn in tab_btns.items():
            if name == tab_name:
                btn.config(bg=c_magenta, fg="#060E1B", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(bg="#1E293B", fg=c_muted, font=("Segoe UI", 9))

        view_theory.pack_forget()
        view_canvas.pack_forget()
        view_review.pack_forget()

        if tab_name == "theory":
            view_theory.pack(fill="both", expand=True, padx=16, pady=8)
        elif tab_name == "canvas":
            view_canvas.pack(fill="both", expand=True, padx=16, pady=8)
        elif tab_name == "review":
            view_review.pack(fill="both", expand=True, padx=16, pady=8)

    tab_btns = {}
    for name, title in [("theory", "1. Изучение и задание"), ("canvas", "2. Векторный холст"), ("review", "3. Проверка макета")]:
        b = tk.Button(
            tabs_bar,
            text=title,
            font=("Segoe UI", 9),
            bg="#1E293B",
            fg=c_muted,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=lambda n=name: switch_tab(n),
        )
        b.pack(side="left", padx=(0, 6))
        tab_btns[name] = b

    # --- Вкладка 1: ТЕОРИЯ ---
    txt_theory = tk.Text(
        view_theory,
        bg="#081120",
        fg=c_text,
        font=("Segoe UI", 11),
        wrap="word",
        bd=0,
        padx=16,
        pady=16,
        highlightthickness=1,
        highlightbackground=c_border,
    )
    txt_theory.pack(fill="both", expand=True)

    # --- Вкладка 2: ВЕКТОРНЫЙ ХОЛСТ ---
    # Панель инструментов редактора
    toolbar = tk.Frame(view_canvas, bg="#081120", highlightthickness=1, highlightbackground=c_border)
    toolbar.pack(fill="x", side="top", pady=(0, 6))

    tool_buttons = {}

    def set_tool(t_name: str):
        state["tool"] = t_name
        for name, btn in tool_buttons.items():
            if name == t_name:
                btn.config(bg=c_cyan, fg="#060E1B", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(bg="#081120", fg=c_muted, font=("Segoe UI", 9))

    tools_spec = [
        ("select", "↖ Выбор"),
        ("frame", "🔲 Фрейм"),
        ("rectangle", "▭ Прямоугольник"),
        ("ellipse", "⬭ Эллипс"),
        ("line", "╱ Линия"),
        ("text", "𝐓 Текст"),
    ]
    for key, label in tools_spec:
        tb = tk.Button(
            toolbar,
            text=label,
            font=("Segoe UI", 9),
            bg="#081120",
            fg=c_muted,
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=lambda k=key: set_tool(k),
        )
        tb.pack(side="left", padx=2, pady=3)
        tool_buttons[key] = tb

    # Кнопки быстрых действий на холсте
    def delete_selected():
        sel = state.get("selected_id")
        if sel:
            state["objects"] = [o for o in state["objects"] if o["id"] != sel]
            state["selected_id"] = None
            redraw_canvas()
            update_layers_list()

    def clear_canvas():
        if messagebox.askyesno("Очистить холст", "Удалить все объекты с текущего холста?"):
            state["objects"].clear()
            state["selected_id"] = None
            redraw_canvas()
            update_layers_list()

    btn_del = tk.Button(
        toolbar,
        text="🗑 Удалить",
        font=("Segoe UI", 9),
        bg="#081120",
        fg="#F87171",
        bd=0,
        padx=10,
        pady=5,
        cursor="hand2",
        command=delete_selected,
    )
    btn_del.pack(side="right", padx=4, pady=3)

    btn_clear = tk.Button(
        toolbar,
        text="Очистить",
        font=("Segoe UI", 9),
        bg="#081120",
        fg=c_muted,
        bd=0,
        padx=10,
        pady=5,
        cursor="hand2",
        command=clear_canvas,
    )
    btn_clear.pack(side="right", padx=4, pady=3)

    # Область рисования: Canvas
    canvas_wrap = tk.Frame(view_canvas, bg=c_canvas_bg, highlightthickness=1, highlightbackground=c_border)
    canvas_wrap.pack(fill="both", expand=True)

    canvas = tk.Canvas(canvas_wrap, bg=c_canvas_bg, bd=0, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Рисование сетки
    def draw_grid():
        canvas.delete("grid_line")
        w = canvas.winfo_width() or 800
        h = canvas.winfo_height() or 500
        for x in range(0, w, 24):
            canvas.create_line(x, 0, x, h, fill="#0F1D33", tags="grid_line")
        for y in range(0, h, 24):
            canvas.create_line(0, y, w, y, fill="#0F1D33", tags="grid_line")
        canvas.tag_lower("grid_line")

    canvas.bind("<Configure>", lambda e: draw_grid())

    # Перерисовка объектов на холсте
    def redraw_canvas():
        canvas.delete("das_obj")
        for obj in state["objects"]:
            oid = obj["id"]
            otype = obj["type"]
            x = obj["x"]
            y = obj["y"]
            w = obj["width"]
            h = obj["height"]
            fill = obj.get("fill", "#1E3352")
            stroke = obj.get("stroke", c_cyan)
            is_sel = (oid == state.get("selected_id"))
            sw = 2 if is_sel else 1
            stk = c_magenta if is_sel else stroke

            if otype in ("frame", "rectangle"):
                canvas.create_rectangle(
                    x, y, x + w, y + h,
                    fill=fill, outline=stk, width=sw,
                    tags=("das_obj", f"obj_{oid}")
                )
                if otype == "frame":
                    canvas.create_text(
                        x + 6, y + 10,
                        text=f"🔲 {obj.get('name', 'Фрейм')}",
                        anchor="w", fill=c_muted,
                        font=("Segoe UI", 8),
                        tags=("das_obj", f"obj_{oid}")
                    )
            elif otype == "ellipse":
                canvas.create_oval(
                    x, y, x + w, y + h,
                    fill=fill, outline=stk, width=sw,
                    tags=("das_obj", f"obj_{oid}")
                )
            elif otype == "line":
                canvas.create_line(
                    x, y, x + w, y + h,
                    fill=stk, width=max(sw, 2),
                    tags=("das_obj", f"obj_{oid}")
                )
            elif otype == "text":
                canvas.create_text(
                    x, y,
                    text=obj.get("text", "Текст"),
                    anchor="nw", fill=c_text,
                    font=("Segoe UI", 12, "bold"),
                    tags=("das_obj", f"obj_{oid}")
                )

    # Обработчики мыши на Canvas
    def on_canvas_down(event):
        t = state["tool"]
        if t == "select":
            # Ищем клик по объекту
            clicked = None
            for obj in reversed(state["objects"]):
                x, y, w, h = obj["x"], obj["y"], obj["width"], obj["height"]
                if x <= event.x <= x + w and y <= event.y <= y + h:
                    clicked = obj
                    break
            state["selected_id"] = clicked["id"] if clicked else None
            state["drag_start"] = (event.x, event.y)
            redraw_canvas()
            update_layers_list()
        else:
            # Создаем новый объект
            new_id = f"das_{len(state['objects'])+1}"
            defaults_map = {
                "frame": {"name": "Фрейм", "w": 360, "h": 220, "fill": "#111C2E", "stroke": "#385170"},
                "rectangle": {"name": "Прямоугольник", "w": 180, "h": 100, "fill": "#162842", "stroke": "#2E4F78"},
                "ellipse": {"name": "Круг", "w": 90, "h": 90, "fill": "#8B5CF6", "stroke": "#C084FC"},
                "line": {"name": "Линия", "w": 120, "h": 2, "fill": c_magenta, "stroke": c_magenta},
                "text": {"name": "Текст", "w": 140, "h": 30, "fill": c_text, "stroke": "none", "text": "Новый интерфейс"},
            }
            spec = defaults_map.get(t, defaults_map["rectangle"])
            new_obj = {
                "id": new_id,
                "type": t,
                "name": spec["name"],
                "x": event.x,
                "y": event.y,
                "width": spec["w"],
                "height": spec["h"],
                "fill": spec["fill"],
                "stroke": spec["stroke"],
                "radius": 8,
                "text": spec.get("text", ""),
            }
            state["objects"].append(new_obj)
            state["selected_id"] = new_id
            set_tool("select")
            redraw_canvas()
            update_layers_list()

    def on_canvas_drag(event):
        if state["tool"] == "select" and state.get("selected_id") and state.get("drag_start"):
            dx = event.x - state["drag_start"][0]
            dy = event.y - state["drag_start"][1]
            for obj in state["objects"]:
                if obj["id"] == state["selected_id"]:
                    obj["x"] += dx
                    obj["y"] += dy
                    break
            state["drag_start"] = (event.x, event.y)
            redraw_canvas()

    def on_canvas_up(event):
        state["drag_start"] = None

    canvas.bind("<ButtonPress-1>", on_canvas_down)
    canvas.bind("<B1-Motion>", on_canvas_drag)
    canvas.bind("<ButtonRelease-1>", on_canvas_up)

    # Нижняя панель действий редактора
    footer_bar = tk.Frame(view_canvas, bg=c_card)
    footer_bar.pack(fill="x", side="bottom", pady=(6, 0))

    def run_desktop_validation():
        curr = state["current_lesson"]
        if not curr:
            return
        doc = {"objects": state["objects"]}
        res = validate_document(doc, curr.get("checks", []))

        # Переходим на вкладку проверки
        switch_tab("review")
        score = res.get("score", 0)
        passed = res.get("passed", False)

        lbl_score_val.config(
            text=f"{score}%",
            fg=c_green if passed else ("#FBBF24" if score > 0 else "#F87171")
        )
        lbl_review_status.config(
            text="✅ Задание успешно выполнено!" if passed else "⚠️ Есть замечания. Исправьте макет согласно списку:",
            fg=c_green if passed else c_text
        )

        txt_review_details.config(state="normal")
        txt_review_details.delete("1.0", "end")
        for idx, r in enumerate(res.get("results", []), 1):
            mark = "✔ [ВЫПОЛНЕНО]" if r.get("passed") else "✖ [НЕ ВЫПОЛНЕНО]"
            txt_review_details.insert("end", f"{idx}. {mark}: {r.get('message', '')}\n")
        txt_review_details.config(state="disabled")

    btn_validate = tk.Button(
        footer_bar,
        text="⚡ Проверить работу",
        font=("Segoe UI", 10, "bold"),
        bg=c_green,
        fg="#060E1B",
        bd=0,
        padx=18,
        pady=8,
        cursor="hand2",
        command=run_desktop_validation,
    )
    btn_validate.pack(side="right")

    lbl_val_status = tk.Label(
        footer_bar,
        text="Изменения сохраняются в текущей сессии.",
        font=("Segoe UI", 9),
        fg=c_muted,
        bg=c_card,
    )
    lbl_val_status.pack(side="left")

    # --- Вкладка 3: ПРОВЕРКА И РЕЗУЛЬТАТЫ ---
    review_head = tk.Frame(view_review, bg=c_card)
    review_head.pack(fill="x", pady=(8, 12))

    lbl_score_val = tk.Label(
        review_head,
        text="0%",
        font=("Segoe UI", 28, "bold"),
        fg=c_magenta,
        bg=c_card,
    )
    lbl_score_val.pack(side="left", padx=(0, 16))

    lbl_review_status = tk.Label(
        review_head,
        text="Нажмите «Проверить работу» на холсте, чтобы получить детальный разбор.",
        font=("Segoe UI", 11, "bold"),
        fg=c_text,
        bg=c_card,
    )
    lbl_review_status.pack(side="left")

    txt_review_details = tk.Text(
        view_review,
        bg="#081120",
        fg=c_text,
        font=("Consolas", 10),
        wrap="word",
        bd=0,
        padx=14,
        pady=14,
        highlightthickness=1,
        highlightbackground=c_border,
    )
    txt_review_details.pack(fill="both", expand=True)

    # ----- 3. ПРАВАЯ КОЛОНКА: СЛОИ И ИИ-НАСТАВНИК -----
    right_panel = tk.Frame(main_body, bg=c_side, width=320, highlightthickness=1, highlightbackground=c_border)
    right_panel.pack(side="right", fill="y", padx=(10, 0))
    right_panel.pack_propagate(False)

    # Блок слоев
    lbl_layers_head = tk.Label(
        right_panel,
        text="СЛОИ ХОЛСТА",
        font=("Segoe UI", 9, "bold"),
        fg=c_cyan,
        bg=c_side,
        anchor="w",
    )
    lbl_layers_head.pack(fill="x", padx=14, pady=(12, 4))

    layers_box = tk.Listbox(
        right_panel,
        bg="#081120",
        fg=c_text,
        selectbackground="#1E3352",
        selectforeground=c_cyan,
        bd=0,
        height=5,
        highlightthickness=1,
        highlightbackground=c_border,
        font=("Segoe UI", 9),
    )
    layers_box.pack(fill="x", padx=14, pady=(0, 12))

    def on_layer_select(event):
        sel = layers_box.curselection()
        if sel:
            idx = sel[0]
            if idx < len(state["objects"]):
                state["selected_id"] = state["objects"][idx]["id"]
                redraw_canvas()

    layers_box.bind("<<ListboxSelect>>", on_layer_select)

    def update_layers_list():
        layers_box.delete(0, "end")
        for obj in state["objects"]:
            otype = obj["type"]
            name = obj.get("name", otype)
            layers_box.insert("end", f"[{otype[:4].upper()}] {name} ({int(obj['width'])}×{int(obj['height'])})")

    # Блок ИИ-наставника
    mentor_frame = tk.Frame(right_panel, bg=c_side)
    mentor_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    lbl_mentor_head = tk.Label(
        mentor_frame,
        text="ИИ-НАСТАВНИК GEMINI",
        font=("Segoe UI", 9, "bold"),
        fg=c_magenta,
        bg=c_side,
        anchor="w",
    )
    lbl_mentor_head.pack(fill="x", pady=(0, 4))

    mentor_mode_var = tk.StringVar(value="hint")
    mentor_mode_box = ttk.Combobox(
        mentor_frame,
        textvariable=mentor_mode_var,
        values=["hint", "explain", "error", "review"],
        state="readonly",
        font=("Segoe UI", 9),
    )
    mentor_mode_box.pack(fill="x", pady=(0, 8))

    txt_mentor_feed = tk.Text(
        mentor_frame,
        bg="#081120",
        fg=c_text,
        font=("Segoe UI", 9),
        wrap="word",
        bd=0,
        height=10,
        highlightthickness=1,
        highlightbackground=c_border,
        padx=8,
        pady=8,
    )
    txt_mentor_feed.pack(fill="both", expand=True, pady=(0, 8))
    txt_mentor_feed.insert("1.0", "🤖 Привет! Я наставник Design Academy Studio. Задайте вопрос по уроку или нажмите кнопку, и я разберу ваш макет на холсте.")
    txt_mentor_feed.config(state="disabled")

    txt_mentor_input = tk.Entry(
        mentor_frame,
        bg="#081120",
        fg=c_text,
        font=("Segoe UI", 9),
        bd=0,
        highlightthickness=1,
        highlightbackground=c_border,
    )
    txt_mentor_input.pack(fill="x", pady=(0, 8), ipady=4)
    txt_mentor_input.insert(0, "Как правильно настроить фрейм?")

    btn_ask_mentor = tk.Button(
        mentor_frame,
        text="Спросить наставника ✨",
        font=("Segoe UI", 9, "bold"),
        bg="#2D123D",
        fg=c_magenta,
        activebackground="#3D1854",
        activeforeground=c_magenta,
        bd=0,
        pady=6,
        cursor="hand2",
    )
    btn_ask_mentor.pack(fill="x")

    def _ask_mentor_thread():
        curr = state["current_lesson"]
        q_text = txt_mentor_input.get().strip()
        mode = mentor_mode_var.get()

        btn_ask_mentor.config(state="disabled", text="Думаю...")
        try:
            compact_objs = [
                {k: o.get(k) for k in ("name", "type", "x", "y", "width", "height", "fill", "stroke")}
                for o in state["objects"][:40]
            ]
            doc = {"objects": state["objects"]}
            val = validate_document(doc, curr.get("checks", [])) if curr else {}

            prompt = (
                f"Урок: {curr.get('title', '')}\n"
                f"Цель: {curr.get('task', '')}\n"
                f"Режим помощи: {mode}\n"
                f"Вопрос ученика: {q_text or 'Разбери мой макет'}\n"
                f"Объекты на холсте: {json.dumps(compact_objs, ensure_ascii=False)}\n"
                f"Техническая валидация: {json.dumps(val, ensure_ascii=False)}\n"
                f"Дай короткий точный совет по дизайну интерфейсов (1-3 абзаца). Сфокусируйся на следующем шаге."
            )
            answer = generate_text(
                prompt=prompt,
                system_instruction="Ты — доброжелательный и профессиональный наставник по UI/UX и векторному дизайну. Отвечай строго по сути.",
                temperature=0.25,
                timeout=30,
            )
        except Exception as ex:
            answer = f"Подсказка: сверьтесь с размерами и положением фрейма на холсте ({ex})."

        def _update_ui():
            txt_mentor_feed.config(state="normal")
            txt_mentor_feed.insert("end", f"\n\n👤 Вы: {q_text or mode}\n🤖 Наставник: {answer.strip()}")
            txt_mentor_feed.see("end")
            txt_mentor_feed.config(state="disabled")
            btn_ask_mentor.config(state="normal", text="Спросить наставника ✨")

        win.after(0, _update_ui)

    btn_ask_mentor.config(command=lambda: threading.Thread(target=_ask_mentor_thread, daemon=True).start())

    # Инициализация первого урока
    set_tool("select")
    switch_tab("canvas")
    select_lesson("1-1")

    return win
