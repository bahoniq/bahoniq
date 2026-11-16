# -*- coding: utf-8 -*-
"""Десктопное окно BahonIQ Excel Academy Studio (Tkinter + AI-наставник BahonIQ AI)."""

from __future__ import annotations

import json
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from ai_service import generate_text
from web_app.modules.excel_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.excel_academy_studio.validation import validate_workbook


def open_excel_academy(parent: tk.Misc | None = None) -> tk.Toplevel:
    """Открывает десктопную студию Excel Academy Studio."""
    # Тёмная фирменная палитра BahonIQ
    c_bg = "#060E1B"
    c_side = "#0A1526"
    c_card = "#0F1D33"
    c_border = "#1E3352"
    c_emerald = "#10B981"
    c_green = "#22C55E"
    c_cyan = "#06B6D4"
    c_text = "#F8FAFC"
    c_muted = "#94A3B8"
    c_sub = "#64748B"

    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("BahonIQ — Excel Academy Studio (Office & IT Pro)")
    win.geometry("1340x860")
    win.minsize(1050, 720)
    win.configure(bg=c_bg)

    curriculum = get_curriculum()
    stages = curriculum.get("stages", [])
    lessons = curriculum.get("lessons", [])

    state = {
        "current_stage": 1,
        "current_lesson_id": "1-1",
        "current_lesson": get_lesson("1-1") or (lessons[0] if lessons else {}),
        "book": {
            "activeSheet": 0,
            "sheets": [{"name": "Лист1", "cells": {}}],
            "operations": [],
            "charts": [],
            "pivots": [],
        },
    }

    # ==================== ВЕРХНЯЯ ШАПКА ====================
    header = tk.Frame(win, bg=c_side, bd=0, highlightthickness=1, highlightbackground=c_border)
    header.pack(fill="x", side="top", padx=0, pady=0)

    title_frame = tk.Frame(header, bg=c_side)
    title_frame.pack(side="left", padx=20, pady=12)

    lbl_title = tk.Label(
        title_frame,
        text="⊞ Excel Academy Studio",
        font=("Segoe UI", 16, "bold"),
        fg=c_text,
        bg=c_side,
    )
    lbl_title.pack(side="left")

    lbl_pill = tk.Label(
        title_frame,
        text="  OFFICE + IT • PRO  ",
        font=("Segoe UI", 9, "bold"),
        fg="#86EFAC",
        bg="#0B2C1B",
        bd=0,
    )
    lbl_pill.pack(side="left", padx=12)

    lbl_sub = tk.Label(
        title_frame,
        text="— Реестры, сопоставление баз, формулы и аналитика",
        font=("Segoe UI", 10),
        fg=c_muted,
        bg=c_side,
    )
    lbl_sub.pack(side="left")

    def _open_web():
        webbrowser.open_new_tab("https://bahoniq.onrender.com/#excelAcademy")

    btn_web = tk.Button(
        header,
        text="🌐 Открыть в браузере",
        font=("Segoe UI", 9, "bold"),
        bg="#0C2D22",
        fg=c_green,
        activebackground="#14532D",
        activeforeground=c_text,
        relief="flat",
        cursor="hand2",
        padx=12,
        pady=6,
        command=_open_web,
    )
    btn_web.pack(side="right", padx=20, pady=12)

    # ==================== ОСНОВНАЯ РАБОЧАЯ ОБЛАСТЬ (3 КОЛОНКИ) ====================
    body = tk.Frame(win, bg=c_bg)
    body.pack(fill="both", expand=True, padx=12, pady=12)

    # 1. ЛЕВАЯ КОЛОНКА: ЭТАПЫ И УРОКИ
    side_left = tk.Frame(body, bg=c_card, width=280, highlightthickness=1, highlightbackground=c_border)
    side_left.pack(side="left", fill="y", padx=(0, 10))
    side_left.pack_propagate(False)

    lbl_stages_title = tk.Label(
        side_left,
        text="ЭТАПЫ ОБУЧЕНИЯ (6)",
        font=("Segoe UI", 9, "bold"),
        fg=c_muted,
        bg=c_card,
    )
    lbl_stages_title.pack(anchor="w", padx=14, pady=(12, 6))

    stages_scroll = tk.Frame(side_left, bg=c_card)
    stages_scroll.pack(fill="x", padx=10, pady=(0, 8))

    stage_buttons = {}

    def _select_stage(stage_id: int):
        state["current_stage"] = stage_id
        for sid, b in stage_buttons.items():
            if sid == stage_id:
                b.configure(bg="#123525", fg="#DCFCE7", highlightbackground=c_green)
            else:
                b.configure(bg="#0B1728", fg=c_muted, highlightbackground=c_border)
        _render_lessons_list()
        first_lesson = next((l for l in lessons if l.get("stage_id") == stage_id), None)
        if first_lesson:
            _select_lesson(first_lesson["id"])

    for s in stages:
        sid = s["id"]
        stitle = f"{sid}. {s['title']}"
        btn_st = tk.Button(
            stages_scroll,
            text=f"{stitle} ({s.get('lessons', 12)})",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            bg="#0B1728",
            fg=c_muted,
            relief="flat",
            highlightthickness=1,
            highlightbackground=c_border,
            padx=8,
            pady=4,
            cursor="hand2",
            command=lambda i=sid: _select_stage(i),
        )
        btn_st.pack(fill="x", pady=2)
        stage_buttons[sid] = btn_st

    lbl_lessons_title = tk.Label(
        side_left,
        text="СПИСОК УРОКОВ",
        font=("Segoe UI", 9, "bold"),
        fg=c_muted,
        bg=c_card,
    )
    lbl_lessons_title.pack(anchor="w", padx=14, pady=(10, 4))

    lessons_canvas = tk.Canvas(side_left, bg=c_card, bd=0, highlightthickness=0)
    lessons_scrollbar = tk.Scrollbar(side_left, orient="vertical", command=lessons_canvas.yview)
    lessons_inner = tk.Frame(lessons_canvas, bg=c_card)

    lessons_inner.bind("<Configure>", lambda e: lessons_canvas.configure(scrollregion=lessons_canvas.bbox("all")))
    lessons_canvas.create_window((0, 0), window=lessons_inner, anchor="nw", width=255)
    lessons_canvas.configure(yscrollcommand=lessons_scrollbar.set)

    lessons_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
    lessons_scrollbar.pack(side="right", fill="y", pady=(0, 10))

    lesson_widgets = {}

    def _render_lessons_list():
        for w in lessons_inner.winfo_children():
            w.destroy()
        lesson_widgets.clear()

        cur_lessons = [l for l in lessons if l.get("stage_id") == state["current_stage"]]
        for l in cur_lessons:
            lid = l["id"]
            title_text = f"{l.get('number', '')}. {l.get('title', '')}"
            b = tk.Button(
                lessons_inner,
                text=title_text,
                font=("Segoe UI", 9),
                anchor="w",
                bg="#0B1728",
                fg=c_text,
                relief="flat",
                highlightthickness=1,
                highlightbackground=c_border,
                padx=8,
                pady=6,
                cursor="hand2",
                command=lambda id_=lid: _select_lesson(id_),
            )
            b.pack(fill="x", pady=2)
            lesson_widgets[lid] = b

    # 2. ЦЕНТРАЛЬНАЯ КОЛОНКА: УРОК, ЗАДАЧА, СИМУЛЯТОР
    center_panel = tk.Frame(body, bg=c_card, highlightthickness=1, highlightbackground=c_border)
    center_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

    lesson_header = tk.Frame(center_panel, bg=c_side, padx=16, pady=12)
    lesson_header.pack(fill="x")

    lbl_badge = tk.Label(
        lesson_header,
        text="ЭТАП 1 · УРОК 1",
        font=("Segoe UI", 9, "bold"),
        fg=c_green,
        bg=c_side,
    )
    lbl_badge.pack(anchor="w")

    lbl_lesson_title = tk.Label(
        lesson_header,
        text="Загрузка...",
        font=("Segoe UI", 16, "bold"),
        fg=c_text,
        bg=c_side,
    )
    lbl_lesson_title.pack(anchor="w", pady=(2, 2))

    lbl_level = tk.Label(
        lesson_header,
        text="Уровень: Базовый",
        font=("Segoe UI", 9),
        fg=c_cyan,
        bg=c_side,
    )
    lbl_level.pack(anchor="w")

    lbl_lesson_summary = tk.Label(
        lesson_header,
        text="",
        font=("Segoe UI", 9),
        fg=c_muted,
        bg=c_side,
        wraplength=600,
        justify="left",
    )
    lbl_lesson_summary.pack(anchor="w", pady=(4, 0))

    # Вкладки: Теория, Задача, Интерактив
    notebook_frame = tk.Frame(center_panel, bg=c_card, padx=16, pady=12)
    notebook_frame.pack(fill="both", expand=True)

    lbl_task_title = tk.Label(
        notebook_frame,
        text="📌 ПРАКТИЧЕСКОЕ ЗАДАНИЕ:",
        font=("Segoe UI", 11, "bold"),
        fg="#86EFAC",
        bg=c_card,
    )
    lbl_task_title.pack(anchor="w", pady=(0, 4))

    txt_task = tk.Label(
        notebook_frame,
        text="",
        font=("Segoe UI", 10),
        fg=c_text,
        bg="#0B241C",
        padx=12,
        pady=8,
        relief="flat",
        justify="left",
        wraplength=620,
    )
    txt_task.pack(fill="x", pady=(0, 12))

    lbl_theory_title = tk.Label(
        notebook_frame,
        text="💡 ТЕОРИЯ И ПОРЯДОК РАБОТЫ:",
        font=("Segoe UI", 11, "bold"),
        fg=c_text,
        bg=c_card,
    )
    lbl_theory_title.pack(anchor="w", pady=(0, 4))

    txt_theory = tk.Text(
        notebook_frame,
        height=10,
        font=("Segoe UI", 10),
        bg="#081321",
        fg=c_text,
        bd=0,
        highlightthickness=1,
        highlightbackground=c_border,
        padx=12,
        pady=10,
        wrap="word",
    )
    txt_theory.pack(fill="both", expand=True, pady=(0, 12))

    # Панель действий урока
    action_box = tk.Frame(notebook_frame, bg=c_card)
    action_box.pack(fill="x", pady=6)

    btn_launch_web = tk.Button(
        action_box,
        text="▶ Открыть в интерактивном симуляторе таблицы",
        font=("Segoe UI", 10, "bold"),
        bg="#10B981",
        fg="#FFFFFF",
        activebackground="#059669",
        activeforeground="#FFFFFF",
        relief="flat",
        padx=16,
        pady=8,
        cursor="hand2",
        command=_open_web,
    )
    btn_launch_web.pack(side="left", padx=(0, 12))

    btn_validate = tk.Button(
        action_box,
        text="✓ Проверить результат",
        font=("Segoe UI", 10, "bold"),
        bg="#1E3E6A",
        fg="#7DD3FC",
        activebackground="#2563EB",
        activeforeground="#FFFFFF",
        relief="flat",
        padx=16,
        pady=8,
        cursor="hand2",
    )
    btn_validate.pack(side="left")

    lbl_val_result = tk.Label(notebook_frame, text="", font=("Segoe UI", 10), fg=c_muted, bg=c_card)
    lbl_val_result.pack(anchor="w", pady=(6, 0))

    def _do_validate():
        lesson = state["current_lesson"]
        checks = lesson.get("checks", [])
        res = validate_workbook(state["book"], checks)
        score = res.get("score", 0)
        passed = res.get("passed", False)
        if passed:
            lbl_val_result.configure(
                text=f"✓ Проверка пройдена успешно! Оценка: {score}%",
                fg=c_green,
            )
        else:
            lbl_val_result.configure(
                text=f"○ Есть невыполненные условия ({score}%). Откройте симулятор для завершения.",
                fg="#F59E0B",
            )

    btn_validate.configure(command=_do_validate)

    # 3. ПРАВАЯ КОЛОНКА: ИИ-НАСТАВНИК (BahonIQ AI)
    side_right = tk.Frame(body, bg=c_card, width=320, highlightthickness=1, highlightbackground=c_border)
    side_right.pack(side="right", fill="y")
    side_right.pack_propagate(False)

    right_header = tk.Frame(side_right, bg=c_side, padx=14, pady=12)
    right_header.pack(fill="x")

    lbl_mentor_title = tk.Label(
        right_header,
        text="💬 ИИ-наставник",
        font=("Segoe UI", 12, "bold"),
        fg=c_text,
        bg=c_side,
    )
    lbl_mentor_title.pack(anchor="w")

    lbl_mentor_sub = tk.Label(
        right_header,
        text="Видит текущий урок и помогает с логикой формул",
        font=("Segoe UI", 8),
        fg=c_muted,
        bg=c_side,
    )
    lbl_mentor_sub.pack(anchor="w")

    mentor_feed = tk.Text(
        side_right,
        bg="#081321",
        fg=c_text,
        font=("Segoe UI", 9),
        bd=0,
        highlightthickness=1,
        highlightbackground=c_border,
        padx=10,
        pady=10,
        wrap="word",
        state="disabled",
    )
    mentor_feed.pack(fill="both", expand=True, padx=10, pady=10)

    def _mentor_log(msg: str, is_user: bool = False):
        mentor_feed.configure(state="normal")
        prefix = "Вы: " if is_user else "Наставник: "
        mentor_feed.insert("end", f"{prefix}{msg}\n\n")
        mentor_feed.see("end")
        mentor_feed.configure(state="disabled")

    _mentor_log("Привет! Я твой ИИ-наставник по Excel. Если формула не работает или задача непонятна — задай вопрос прямо здесь!")

    ask_frame = tk.Frame(side_right, bg=c_card, padx=10, pady=10)
    ask_frame.pack(fill="x", side="bottom")

    txt_question = tk.Entry(
        ask_frame,
        font=("Segoe UI", 10),
        bg="#081321",
        fg=c_text,
        relief="flat",
        highlightthickness=1,
        highlightbackground=c_border,
    )
    txt_question.pack(fill="x", pady=(0, 6), ipady=4)

    def _ask_mentor():
        q_text = txt_question.get().strip()
        if not q_text:
            return
        txt_question.delete(0, "end")
        _mentor_log(q_text, is_user=True)

        lesson = state["current_lesson"]
        prompt = (
            f"Ты — опытный ИИ-наставник по Excel и таблицам в системе BahonIQ.\n"
            f"Текущий урок: {lesson.get('title')}\n"
            f"Задание: {lesson.get('task')}\n"
            f"Теория: {lesson.get('theory')}\n\n"
            f"Вопрос студента: {q_text}\n"
            f"Дай краткий, понятный и наводящий ответ без сложного академизма."
        )

        def _worker():
            try:
                ans = generate_text(prompt, model="gemini-2.5-flash")
            except Exception as exc:
                ans = f"Не удалось связаться с моделью: {exc}"
            win.after(0, lambda: _mentor_log(ans))

        threading.Thread(target=_worker, daemon=True).start()

    btn_ask = tk.Button(
        ask_frame,
        text="Спросить наставника",
        font=("Segoe UI", 9, "bold"),
        bg=c_emerald,
        fg="#FFFFFF",
        activebackground="#059669",
        activeforeground="#FFFFFF",
        relief="flat",
        cursor="hand2",
        command=_ask_mentor,
    )
    btn_ask.pack(fill="x")
    txt_question.bind("<Return>", lambda e: _ask_mentor())

    def _select_lesson(lesson_id: str):
        lesson = get_lesson(lesson_id)
        if not lesson:
            return
        state["current_lesson_id"] = lesson_id
        state["current_lesson"] = lesson

        lbl_badge.configure(text=f"ЭТАП {lesson.get('stage_id', 1)} · УРОК {lesson.get('number', 1)}")
        lbl_lesson_title.configure(text=lesson.get("title", ""))
        lbl_level.configure(text=f"Уровень сложности: {lesson.get('level', 'Базовый')}")
        lbl_lesson_summary.configure(text=lesson.get("summary", ""))

        txt_task.configure(text=lesson.get("task", ""))
        txt_theory.configure(state="normal")
        txt_theory.delete("1.0", "end")
        theory_parts = []
        if lesson.get("goal"):
            theory_parts.append(f"Цель: {lesson['goal']}")
        if lesson.get("work_situation"):
            theory_parts.append(f"Контекст: {lesson['work_situation']}")
        if lesson.get("theory"):
            theory_parts.append(f"Теория:\n{lesson['theory']}")
        if lesson.get("example"):
            theory_parts.append(f"Пример:\n{lesson['example']}")
        if lesson.get("steps"):
            theory_parts.append("Порядок выполнения:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(lesson["steps"], 1)))
        if lesson.get("common_errors"):
            theory_parts.append("Типичные ошибки:\n" + "\n".join(f"• {e}" for e in lesson["common_errors"]))
        if lesson.get("professional_tip"):
            theory_parts.append(f"Совет профи: {lesson['professional_tip']}")

        theory_content = "\n\n".join(theory_parts)
        txt_theory.insert("1.0", theory_content)
        txt_theory.configure(state="disabled")

        lbl_val_result.configure(text="")

        for lid, b in lesson_widgets.items():
            if lid == lesson_id:
                b.configure(bg="#123525", fg="#DCFCE7", highlightbackground=c_green)
            else:
                b.configure(bg="#0B1728", fg=c_text, highlightbackground=c_border)

    # Инициализация первого этапа и первого урока
    _select_stage(1)
    if lessons:
        _select_lesson(lessons[0]["id"])

    return win
