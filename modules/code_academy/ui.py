# -*- coding: utf-8 -*-
"""Десктопное окно BahonIQ Academy (Строгая тёмная тема + 4 этапа + Живой ИИ-ментор Gemini Flash + PDF-книга От А до Я)."""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from ai_service import generate_text
from web_app.modules.code_academy.db import (
    get_lesson_by_id,
    get_roadmap_data,
    init_academy_db,
    save_lesson_theory,
    save_user_attempt,
)
from web_app.modules.code_academy.pdf_book_generator import build_academy_pdf_book
from web_app.routers.academy import (
    _execute_lesson_code,
    _generate_live_theory_sync,
    _mentor_evaluate_code_sync,
)


def open_code_academy(parent: tk.Misc | None = None) -> tk.Toplevel:
    """Открывает поэтапную AI-платформу обучения BahonIQ Academy в строгом тёмном стиле."""
    init_academy_db()

    # Строгая фирменная тёмная палитра BahonIQ Work Center (никаких белых блоков!)
    bg_main = "#060E1B"
    bg_sidebar = "#0A1526"
    bg_card = "#0F1D33"
    bg_input = "#081120"
    bg_tab = "#13233E"
    bg_tab_active = "#163B5C"
    bg_item = "#0B1628"
    bg_item_hover = "#142847"
    bg_item_active = "#183A5A"
    fg_text = "#F8FAFC"
    fg_muted = "#A9BDD3"
    fg_sub = "#647D96"
    accent = "#00B4D8"
    accent_hover = "#0096C7"
    green_btn = "#009246"
    green_hover = "#007A3D"
    amber_col = "#F59E0B"
    border_col = "#1E3352"

    win = tk.Toplevel(parent)
    win.title("BahonIQ Academy — AI-Платформа обучения (Gemini Flash 24/7)")
    win.geometry("1360x840")
    win.minsize(1060, 680)
    win.configure(bg=bg_main)

    # Верхняя неоновая полоса
    tk.Frame(win, bg=accent, height=3).pack(fill="x", side="top")

    # =========================================================================
    # 1. ШАПКА: Заголовок + Визуальный прогресс-бар по 4 этапам + Кнопка PDF-книги
    # =========================================================================
    header = tk.Frame(win, bg=bg_sidebar, padx=20, pady=12, highlightthickness=1, highlightbackground=border_col)
    header.pack(fill="x", side="top")

    title_col = tk.Frame(header, bg=bg_sidebar)
    title_col.pack(side="left")

    title_row = tk.Frame(title_col, bg=bg_sidebar)
    title_row.pack(anchor="w")

    tk.Label(
        title_row,
        text="🎓  BahonIQ Academy",
        font=("Segoe UI", 16, "bold"),
        bg=bg_sidebar,
        fg=fg_text,
    ).pack(side="left")

    tk.Label(
        title_row,
        text="  GEMINI FLASH 24/7  ",
        font=("Segoe UI", 8, "bold"),
        bg=bg_tab_active,
        fg=accent,
        padx=8,
        pady=2,
    ).pack(side="left", padx=(10, 0))

    tk.Label(
        title_col,
        text="Поэтапное обучение с живым ИИ-наставником: Основы Python • SQL и SQLite • Архитектура проекта • Боевой полигон",
        font=("Segoe UI", 9),
        bg=bg_sidebar,
        fg=fg_muted,
    ).pack(anchor="w", pady=(2, 0))

    # Правая часть шапки: Кнопка PDF-книги + Прогресс-бар
    right_hdr = tk.Frame(header, bg=bg_sidebar)
    right_hdr.pack(side="right")

    pdf_btn = tk.Button(
        right_hdr,
        text="📘  Сгенерировать мою PDF-книгу (От А до Я)",
        font=("Segoe UI", 10, "bold"),
        bg=green_btn,
        fg="#FFFFFF",
        activebackground=green_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=16,
        pady=9,
        cursor="hand2",
    )
    pdf_btn.pack(side="right", padx=(16, 0))

    prog_box = tk.Frame(right_hdr, bg=bg_sidebar)
    prog_box.pack(side="right")

    prog_lbl = tk.Label(
        prog_box,
        text="Общий прогресс: 0 / 29 (0%)",
        font=("Segoe UI", 9, "bold"),
        bg=bg_sidebar,
        fg=accent,
    )
    prog_lbl.pack(anchor="e", pady=(0, 4))

    prog_canvas = tk.Canvas(prog_box, width=210, height=8, bg=bg_input, bd=0, highlightthickness=1, highlightbackground=border_col)
    prog_canvas.pack(anchor="e")
    prog_rect = prog_canvas.create_rectangle(0, 0, 0, 8, fill=green_btn, width=0)

    # =========================================================================
    # 2. ПАНЕЛЬ 4 ОБЯЗАТЕЛЬНЫХ ЭТАПОВ
    # =========================================================================
    stages_bar = tk.Frame(win, bg=bg_main, padx=16, pady=10)
    stages_bar.pack(fill="x", side="top")
    for c_idx in range(4):
        stages_bar.grid_columnconfigure(c_idx, weight=1, uniform="stagecol")

    # =========================================================================
    # 3. ОСНОВНАЯ 3-КОЛОНОЧНАЯ РАБОЧАЯ ОБЛАСТЬ
    # =========================================================================
    workspace = tk.Frame(win, bg=bg_main, padx=16, pady=4)
    workspace.pack(fill="both", expand=True)

    # --- Левая колонка: Темы выбранного этапа (280px) ---
    left_col = tk.Frame(workspace, bg=bg_sidebar, width=285, padx=12, pady=12, highlightthickness=1, highlightbackground=border_col)
    left_col.pack(side="left", fill="y", padx=(0, 12))
    left_col.pack_propagate(False)

    stage_side_lbl = tk.Label(
        left_col,
        text="ТЕМЫ ЭТАПА 1",
        font=("Segoe UI", 8, "bold"),
        bg=bg_sidebar,
        fg=fg_sub,
    )
    stage_side_lbl.pack(anchor="w", pady=(0, 6))

    search_wrap = tk.Frame(left_col, bg=bg_input, highlightthickness=1, highlightbackground=border_col, padx=8, pady=5)
    search_wrap.pack(fill="x", pady=(0, 8))

    tk.Label(search_wrap, text="🔍", font=("Segoe UI", 9), bg=bg_input, fg=fg_sub).pack(side="left", padx=(0, 5))
    filter_var = tk.StringVar()
    tk.Entry(
        search_wrap,
        textvariable=filter_var,
        font=("Segoe UI", 9),
        bg=bg_input,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
        bd=0,
    ).pack(side="left", fill="x", expand=True)

    lessons_canvas_wrap = tk.Frame(left_col, bg=bg_sidebar)
    lessons_canvas_wrap.pack(fill="both", expand=True)

    lessons_canvas = tk.Canvas(lessons_canvas_wrap, bg=bg_sidebar, bd=0, highlightthickness=0)
    lessons_scroll = tk.Scrollbar(lessons_canvas_wrap, orient="vertical", command=lessons_canvas.yview)
    lessons_inner = tk.Frame(lessons_canvas, bg=bg_sidebar)

    lessons_inner_id = lessons_canvas.create_window((0, 0), window=lessons_inner, anchor="nw")
    lessons_canvas.configure(yscrollcommand=lessons_scroll.set)
    lessons_canvas.pack(side="left", fill="both", expand=True)
    lessons_scroll.pack(side="right", fill="y")

    lessons_inner.bind("<Configure>", lambda _e: lessons_canvas.configure(scrollregion=lessons_canvas.bbox("all")))
    lessons_canvas.bind("<Configure>", lambda e: lessons_canvas.itemconfig(lessons_inner_id, width=e.width))

    # --- Правая колонка: Встроенный чат «Задать вопрос по уроку» (310px) ---
    right_col = tk.Frame(workspace, bg=bg_sidebar, width=315, padx=14, pady=14, highlightthickness=1, highlightbackground=border_col)
    right_col.pack(side="right", fill="y", padx=(12, 0))
    right_col.pack_propagate(False)

    tk.Label(
        right_col,
        text="💬  Чат с ИИ-ментором",
        font=("Segoe UI", 12, "bold"),
        bg=bg_sidebar,
        fg=fg_text,
    ).pack(anchor="w")

    tk.Label(
        right_col,
        text="Видит ваш текущий урок, задачу и код",
        font=("Segoe UI", 8),
        bg=bg_sidebar,
        fg=fg_sub,
    ).pack(anchor="w", pady=(0, 8))

    # Быстрые кнопки вопросов ментору
    quick_q_frame = tk.Frame(right_col, bg=bg_sidebar)
    quick_q_frame.pack(fill="x", pady=(0, 8))

    chat_input_wrap = tk.Frame(right_col, bg=bg_sidebar)
    chat_input_wrap.pack(side="bottom", fill="x", pady=(8, 0))

    chat_send_btn = tk.Button(
        chat_input_wrap,
        text="Спросить ИИ-ментора  ➔",
        font=("Segoe UI", 9, "bold"),
        bg=accent,
        fg="#FFFFFF",
        activebackground=accent_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        pady=8,
        cursor="hand2",
    )
    chat_send_btn.pack(side="bottom", fill="x", pady=(6, 0))

    chat_entry = tk.Text(
        chat_input_wrap,
        height=3,
        font=("Segoe UI", 9),
        bg=bg_input,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
        bd=0,
        padx=8,
        pady=6,
        wrap="word",
        highlightthickness=1,
        highlightbackground=border_col,
    )
    chat_entry.pack(side="top", fill="x")

    chat_log = tk.Text(
        right_col,
        font=("Segoe UI", 9),
        bg=bg_input,
        fg=fg_text,
        relief="flat",
        bd=0,
        padx=10,
        pady=10,
        wrap="word",
        state="disabled",
        highlightthickness=1,
        highlightbackground=border_col,
    )
    chat_log.pack(fill="both", expand=True)
    chat_log.tag_configure("user", font=("Segoe UI", 9, "bold"), foreground=accent, spacing1=6, spacing3=2)
    chat_log.tag_configure("ai_hdr", font=("Segoe UI", 9, "bold"), foreground=green_btn, spacing1=6, spacing3=2)
    chat_log.tag_configure("ai_body", font=("Segoe UI", 9), foreground=fg_text, spacing3=6)

    def _append_chat(sender: str, message: str) -> None:
        chat_log.configure(state="normal")
        if sender == "user":
            chat_log.insert("end", f"Вы:\n", "user")
            chat_log.insert("end", f"{message}\n\n", "ai_body")
        else:
            chat_log.insert("end", f"ИИ-ментор Gemini Flash:\n", "ai_hdr")
            chat_log.insert("end", f"{message}\n\n", "ai_body")
        chat_log.configure(state="disabled")
        chat_log.yview_moveto(1.0)

    _append_chat("ai", "Привет! Я твой живой наставник по курсу. Если непонятна строка кода или нужна подсказка — напиши мне!")

    # --- Центральная колонка: Теория + Задание + Редактор + Проверка ментором ---
    center_col = tk.Frame(workspace, bg=bg_card, padx=18, pady=14, highlightthickness=1, highlightbackground=border_col)
    center_col.pack(side="left", fill="both", expand=True)

    # Шапка урока
    les_top = tk.Frame(center_col, bg=bg_card)
    les_top.pack(fill="x", pady=(0, 8))

    regen_btn = tk.Button(
        les_top,
        text="🔄 Объяснить иначе (ИИ)",
        font=("Segoe UI", 9, "bold"),
        bg=bg_tab,
        fg=accent,
        activebackground=bg_tab_active,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=12,
        pady=6,
        cursor="hand2",
    )
    regen_btn.pack(side="right")

    les_meta_box = tk.Frame(les_top, bg=bg_card)
    les_meta_box.pack(side="left", fill="x", expand=True)

    les_stage_pill = tk.Label(
        les_meta_box,
        text="ЭТАП 1  •  В ПРОЦЕССЕ",
        font=("Segoe UI", 8, "bold"),
        bg=bg_card,
        fg=accent,
    )
    les_stage_pill.pack(anchor="w")

    les_title_lbl = tk.Label(
        les_meta_box,
        text="Загрузка урока...",
        font=("Segoe UI", 14, "bold"),
        bg=bg_card,
        fg=fg_text,
        anchor="w",
    )
    les_title_lbl.pack(anchor="w", pady=(2, 0))

    # 1. Живая теория + Практическое задание (верхняя прокручиваемая панель)
    theory_wrap = tk.Frame(center_col, bg=bg_input, highlightthickness=1, highlightbackground=border_col)
    theory_wrap.pack(fill="both", expand=True, pady=(0, 10))

    theory_scroll = tk.Scrollbar(theory_wrap, orient="vertical")
    theory_text = tk.Text(
        theory_wrap,
        height=10,
        font=("Segoe UI", 10),
        bg=bg_input,
        fg=fg_text,
        relief="flat",
        bd=0,
        padx=14,
        pady=12,
        wrap="word",
        spacing1=3,
        spacing2=2,
        spacing3=5,
        yscrollcommand=theory_scroll.set,
        state="disabled",
    )
    theory_scroll.configure(command=theory_text.yview)
    theory_text.pack(side="left", fill="both", expand=True)
    theory_scroll.pack(side="right", fill="y")

    theory_text.tag_configure("sec", font=("Segoe UI", 9, "bold"), foreground=accent, spacing1=4, spacing3=4)
    theory_text.tag_configure("bold", font=("Segoe UI", 10, "bold"), foreground=accent)
    theory_text.tag_configure("code", font=("Consolas", 9), background="#11223B", foreground="#E2E8F0")
    theory_text.tag_configure("task_box", font=("Segoe UI", 10, "bold"), foreground="#10B981", spacing1=8, spacing3=4)

    # 2. Редактор кода
    editor_hdr = tk.Frame(center_col, bg=bg_card)
    editor_hdr.pack(fill="x", pady=(0, 4))

    lang_lbl = tk.Label(
        editor_hdr,
        text="РЕДАКТОР КОДА  •  PYTHON 3",
        font=("Segoe UI", 8, "bold"),
        bg=bg_card,
        fg=green_btn,
    )
    lang_lbl.pack(side="left")

    reset_btn = tk.Label(
        editor_hdr,
        text="Сбросить стартовый код",
        font=("Segoe UI", 8, "underline"),
        bg=bg_card,
        fg=fg_sub,
        cursor="hand2",
    )
    reset_btn.pack(side="right")

    code_editor = tk.Text(
        center_col,
        height=8,
        font=("Consolas", 11),
        bg=bg_input,
        fg="#E2E8F0",
        insertbackground=accent,
        relief="flat",
        bd=0,
        padx=12,
        pady=10,
        wrap="none",
        undo=True,
        highlightthickness=1,
        highlightbackground=border_col,
    )
    code_editor.pack(fill="x", pady=(0, 8))

    # 3. Кнопки действий (Запустить / Проверить с ментором / Следующий урок)
    actions_row = tk.Frame(center_col, bg=bg_card)
    actions_row.pack(fill="x", pady=(0, 8))

    run_btn = tk.Button(
        actions_row,
        text="▶  Запустить код",
        font=("Segoe UI", 9, "bold"),
        bg=bg_tab,
        fg=fg_text,
        activebackground=bg_tab_active,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        cursor="hand2",
    )
    run_btn.pack(side="left", padx=(0, 8))

    check_btn = tk.Button(
        actions_row,
        text="✨  Проверить с ментором",
        font=("Segoe UI", 10, "bold"),
        bg=green_btn,
        fg="#FFFFFF",
        activebackground=green_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=18,
        pady=8,
        cursor="hand2",
    )
    check_btn.pack(side="left", padx=(0, 8))

    next_btn = tk.Button(
        actions_row,
        text="Следующий урок  ➔",
        font=("Segoe UI", 9, "bold"),
        bg=accent,
        fg="#FFFFFF",
        activebackground=accent_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        cursor="hand2",
    )

    # 4. Нижняя панель: Консоль вывода + Разбор ошибок от ИИ-ментора
    verdict_wrap = tk.Frame(center_col, bg=bg_input, highlightthickness=1, highlightbackground=border_col)
    verdict_wrap.pack(fill="both", expand=True)

    verdict_scroll = tk.Scrollbar(verdict_wrap, orient="vertical")
    verdict_text = tk.Text(
        verdict_wrap,
        height=7,
        font=("Segoe UI", 10),
        bg=bg_input,
        fg=fg_text,
        relief="flat",
        bd=0,
        padx=14,
        pady=10,
        wrap="word",
        yscrollcommand=verdict_scroll.set,
        state="disabled",
    )
    verdict_scroll.configure(command=verdict_text.yview)
    verdict_text.pack(side="left", fill="both", expand=True)
    verdict_scroll.pack(side="right", fill="y")

    verdict_text.tag_configure("pass_hdr", font=("Segoe UI", 10, "bold"), foreground="#10B981", spacing3=4)
    verdict_text.tag_configure("fail_hdr", font=("Segoe UI", 10, "bold"), foreground=amber_col, spacing3=4)
    verdict_text.tag_configure("console_hdr", font=("Segoe UI", 9, "bold"), foreground=fg_sub, spacing3=2)
    verdict_text.tag_configure("mono", font=("Consolas", 9), foreground=fg_muted, spacing3=6)

    # =========================================================================
    # ЛОГИКА СОСТОЯНИЯ И ВЗАИМОДЕЙСТВИЯ
    # =========================================================================
    state_rm: dict = {"stages": [], "total_lessons": 29, "completed_lessons": 0, "overall_percent": 0}
    active_stage_id = [1]
    active_lesson: list[dict | None] = [None]

    def _set_verdict_content(header_str: str, is_pass: bool | None, console_str: str, mentor_str: str) -> None:
        verdict_text.configure(state="normal")
        verdict_text.delete("1.0", "end")
        if console_str:
            verdict_text.insert("end", "ВЫВОД ПРОГРАММЫ (КОНСОЛЬ):\n", "console_hdr")
            verdict_text.insert("end", console_str.strip() + "\n\n", "mono")
        if header_str:
            tag = "pass_hdr" if is_pass is True else ("fail_hdr" if is_pass is False else "console_hdr")
            verdict_text.insert("end", header_str + "\n", tag)
        if mentor_str:
            verdict_text.insert("end", mentor_str.strip() + "\n")
        verdict_text.configure(state="disabled")

    def _render_theory_and_task(les: dict) -> None:
        theory_text.configure(state="normal")
        theory_text.delete("1.0", "end")

        theory_text.insert("end", "1 · ЖИВОЕ ОБЪЯСНЕНИЕ МЕНТОРА (ТЕОРИЯ)\n", "sec")
        raw_t = les.get("ai_theory") or ""
        for line in raw_t.splitlines():
            if line.strip().startswith("```"):
                continue
            parts = re.split(r"(\*\*[^*]+\*\*)", line)
            for p in parts:
                if p.startswith("**") and p.endswith("**"):
                    theory_text.insert("end", p[2:-2], "bold")
                else:
                    theory_text.insert("end", p)
            theory_text.insert("end", "\n")

        if les.get("repo_source_preview"):
            theory_text.insert("end", f"\n📂 РЕАЛЬНЫЙ ФАЙЛ ПРОЕКТА BAHONIQ ({les.get('file_path')}):\n", "sec")
            theory_text.insert("end", les["repo_source_preview"][:1500] + "\n", "code")

        theory_text.insert("end", "\n2 · ПРАКТИЧЕСКАЯ ЗАДАЧА НА ЗАКРЕПЛЕНИЕ:\n", "task_box")
        theory_text.insert("end", (les.get("task_prompt") or "") + "\n")

        theory_text.configure(state="disabled")
        theory_text.yview_moveto(0.0)

    def render_all_navigation() -> None:
        done = state_rm.get("completed_lessons", 0)
        tot = state_rm.get("total_lessons", 29)
        pct = state_rm.get("overall_percent", 0)
        prog_lbl.configure(text=f"Общий прогресс: {done} / {tot} ({pct}%)")
        prog_canvas.coords(prog_rect, 0, 0, int(2.1 * pct), 8)

        # Отрисовка 4 карточек этапов
        for w in stages_bar.winfo_children():
            w.destroy()

        for idx, st in enumerate(state_rm.get("stages", [])):
            sid = int(st["id"])
            is_act = sid == active_stage_id[0]
            card_bg = bg_tab_active if is_act else bg_card
            b_col = accent if is_act else border_col

            st_card = tk.Frame(
                stages_bar,
                bg=card_bg,
                padx=12,
                pady=8,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=b_col,
            )
            st_card.grid(row=0, column=idx, sticky="nsew", padx=4)

            top_r = tk.Frame(st_card, bg=card_bg)
            top_r.pack(fill="x")

            l1 = tk.Label(top_r, text=f"ЭТАП {st['order_index']}", font=("Segoe UI", 8, "bold"), bg=card_bg, fg=accent)
            l1.pack(side="left")

            l2 = tk.Label(
                top_r,
                text=f"{st['completed_lessons']}/{st['total_lessons']}",
                font=("Segoe UI", 8, "bold"),
                bg=bg_input,
                fg=fg_muted,
                padx=6,
            )
            l2.pack(side="right")

            short_t = re.sub(r"^Этап\s+\d+:\s*", "", st["title"])
            l3 = tk.Label(st_card, text=short_t, font=("Segoe UI", 10, "bold"), bg=card_bg, fg=fg_text, anchor="w")
            l3.pack(fill="x", pady=(2, 0))

            l4 = tk.Label(st_card, text=st["subtitle"], font=("Segoe UI", 8), bg=card_bg, fg=fg_muted, anchor="w")
            l4.pack(fill="x")

            for widget in (st_card, top_r, l1, l2, l3, l4):
                widget.bind("<Button-1>", lambda _e, s_id=sid: switch_stage(s_id))

        render_lessons_sidebar(filter_var.get())

    def render_lessons_sidebar(filter_q: str = "") -> None:
        for w in lessons_inner.winfo_children():
            w.destroy()

        st_obj = next((s for s in state_rm.get("stages", []) if int(s["id"]) == active_stage_id[0]), None)
        if not st_obj:
            return
        stage_side_lbl.configure(text=st_obj["title"].upper())

        q = filter_q.strip().lower()
        for les in st_obj.get("lessons", []):
            if q and q not in les["title"].lower() and q not in les["summary"].lower():
                continue
            lid = int(les["id"])
            is_sel = bool(active_lesson[0] and int(active_lesson[0]["id"]) == lid)
            is_done = bool(les.get("completed"))

            r_bg = bg_item_active if is_sel else bg_item
            r_fg = fg_text if is_sel else fg_muted
            mark = "✓" if is_done else str(les["order_index"])
            mark_fg = "#10B981" if is_done else accent

            row = tk.Frame(
                lessons_inner,
                bg=r_bg,
                padx=10,
                pady=8,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=accent if is_sel else border_col,
            )
            row.pack(fill="x", pady=3)

            m_lbl = tk.Label(row, text=mark, font=("Segoe UI", 9, "bold"), bg=r_bg, fg=mark_fg, width=2)
            m_lbl.pack(side="left", anchor="n")

            t_lbl = tk.Label(
                row,
                text=les["title"],
                font=("Segoe UI", 9, "bold" if is_sel else "normal"),
                bg=r_bg,
                fg=r_fg,
                anchor="w",
                justify="left",
                wraplength=215,
                cursor="hand2",
            )
            t_lbl.pack(side="left", fill="x", expand=True)

            for widget in (row, m_lbl, t_lbl):
                widget.bind("<Button-1>", lambda _e, l_id=lid: select_lesson_id(l_id))

        lessons_inner.update_idletasks()
        lessons_canvas.configure(scrollregion=lessons_canvas.bbox("all"))

    filter_var.trace_add("write", lambda *_: render_lessons_sidebar(filter_var.get()))

    def switch_stage(sid: int) -> None:
        active_stage_id[0] = sid
        st_obj = next((s for s in state_rm.get("stages", []) if int(s["id"]) == sid), None)
        if st_obj and st_obj.get("lessons"):
            first_inc = next((x for x in st_obj["lessons"] if not x.get("completed")), st_obj["lessons"][0])
            select_lesson_id(int(first_inc["id"]))
        else:
            render_all_navigation()

    def select_lesson_id(lid: int) -> None:
        les = get_lesson_by_id(lid)
        if not les:
            return
        active_lesson[0] = les
        active_stage_id[0] = int(les["stage_id"])

        status_txt = "✓ ПРОЙДЕНО" if les.get("completed") else "В ПРОЦЕССЕ"
        les_stage_pill.configure(
            text=f"{les['stage_title'].upper()}  •  {status_txt}",
            fg="#10B981" if les.get("completed") else accent,
        )
        les_title_lbl.configure(text=les["title"])
        lang_lbl.configure(
            text="РЕДАКТОР КОДА  •  SQLITE / SQL" if les["language"] == "sql" else "РЕДАКТОР КОДА  •  PYTHON 3"
        )

        _render_theory_and_task(les)

        code_editor.delete("1.0", "end")
        code_editor.insert("1.0", les.get("user_code") or les.get("starter_code") or "")

        if les.get("completed") and les.get("next_lesson_id"):
            next_btn.pack(side="left", padx=(0, 8))
        else:
            next_btn.pack_forget()

        if les.get("mentor_feedback"):
            _set_verdict_content(
                "✓ РАЗБОР ОТ ИИ-МЕНТОРА:" if les.get("completed") else "💡 ПОДСКАЗКА ОТ ИИ-МЕНТОРА:",
                bool(les.get("completed")),
                "",
                les["mentor_feedback"],
            )
        else:
            _set_verdict_content("Нажмите «▶ Запустить код» или «✨ Проверить с ментором».", None, "", "")

        render_all_navigation()

    def on_reset_code(_event: object = None) -> None:
        if not active_lesson[0]:
            return
        code_editor.delete("1.0", "end")
        code_editor.insert("1.0", active_lesson[0].get("starter_code") or "")

    reset_btn.bind("<Button-1>", on_reset_code)

    def on_run_code() -> None:
        if not active_lesson[0]:
            return
        code = code_editor.get("1.0", "end").strip()
        lang = active_lesson[0]["language"]
        run_btn.configure(state="disabled", text="⏳ Запуск...")

        def worker() -> None:
            res = _execute_lesson_code(lang, code)
            out = (res.get("stdout") or "") + ("\n" + res["stderr"] if res.get("stderr") else "")
            win.after(0, lambda: _on_run_done(out.strip() or "(Код выполнился без вывода)"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_done(out_str: str) -> None:
        run_btn.configure(state="normal", text="▶  Запустить код")
        _set_verdict_content("", None, out_str, "")

    run_btn.configure(command=on_run_code)

    def on_check_mentor() -> None:
        if not active_lesson[0]:
            return
        les = active_lesson[0]
        code = code_editor.get("1.0", "end").strip()
        check_btn.configure(state="disabled", text="⏳ Ментор анализирует код...")
        _set_verdict_content("⏳ ИИ-ментор Gemini Flash проверяет ваше решение...", None, "", "Пожалуйста, подождите 2–3 секунды...")

        def worker() -> None:
            exec_res = _execute_lesson_code(les["language"], code)
            eval_res = _mentor_evaluate_code_sync(les, code, exec_res)
            save_user_attempt(int(les["id"]), code, eval_res["feedback"], eval_res["passed"])
            rm = get_roadmap_data()
            win.after(0, lambda: _on_check_done(exec_res, eval_res, rm))

        threading.Thread(target=worker, daemon=True).start()

    def _on_check_done(exec_res: dict, eval_res: dict, rm: dict) -> None:
        check_btn.configure(state="normal", text="✨  Проверить с ментором")
        state_rm.clear()
        state_rm.update(rm)

        passed = bool(eval_res.get("passed"))
        out = ((exec_res.get("stdout") or "") + ("\n" + exec_res["stderr"] if exec_res.get("stderr") else "")).strip()
        hdr = "🎉 ОТЛИЧНО! УРОК ЗАСЧИТАН ИИ-МЕНТОРОМ:" if passed else "💡 РАЗБОР ОШИБКИ И ПОДСКАЗКА ОТ ИИ-МЕНТОРА:"
        _set_verdict_content(hdr, passed, out, eval_res.get("feedback") or "")

        if active_lesson[0]:
            if passed:
                active_lesson[0]["completed"] = True
                les_stage_pill.configure(text=f"{active_lesson[0]['stage_title'].upper()}  •  ✓ ПРОЙДЕНО", fg="#10B981")
                if active_lesson[0].get("next_lesson_id"):
                    next_btn.pack(side="left", padx=(0, 8))
        render_all_navigation()

    check_btn.configure(command=on_check_mentor)

    def on_next_lesson() -> None:
        if active_lesson[0] and active_lesson[0].get("next_lesson_id"):
            select_lesson_id(int(active_lesson[0]["next_lesson_id"]))

    next_btn.configure(command=on_next_lesson)

    def on_regen_theory() -> None:
        if not active_lesson[0]:
            return
        les = active_lesson[0]
        regen_btn.configure(state="disabled", text="⏳ ИИ пишет пример...")

        def worker() -> None:
            try:
                fresh = _generate_live_theory_sync(les)
                if fresh:
                    save_lesson_theory(int(les["id"]), fresh)
                    les["ai_theory"] = fresh
            except Exception:
                pass
            win.after(0, _on_regen_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_regen_done() -> None:
        regen_btn.configure(state="normal", text="🔄 Объяснить иначе (ИИ)")
        if active_lesson[0]:
            _render_theory_and_task(active_lesson[0])

    regen_btn.configure(command=on_regen_theory)

    # Встроенный чат с ментором
    def send_chat_q(custom_q: str | None = None) -> None:
        q = (custom_q if custom_q is not None else chat_entry.get("1.0", "end")).strip()
        if not q or not active_lesson[0]:
            return
        if custom_q is None:
            chat_entry.delete("1.0", "end")
        _append_chat("user", q)
        chat_send_btn.configure(state="disabled", text="⏳ Ментор отвечает...")

        les = active_lesson[0]
        curr_code = code_editor.get("1.0", "end").strip()

        def worker() -> None:
            try:
                ans = generate_text(
                    prompt=(
                        f"Урок: {les['title']} ({les['stage_title']})\n"
                        f"Задание: {les['task_prompt']}\n"
                        f"Код ученика:\n{curr_code}\n\n"
                        f"Вопрос ученика: {q}"
                    ),
                    system_instruction=(
                        "Ты — дружелюбный ИИ-наставник BahonIQ Academy. Отвечай понятно, коротко и по существу "
                        "в контексте текущего урока и кода ученика."
                    ),
                    temperature=0.3,
                    timeout=35,
                )
                win.after(0, lambda: _on_chat_ans(str(ans).strip()))
            except Exception as exc:
                win.after(0, lambda: _on_chat_ans(f"Ошибка: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_chat_ans(ans_str: str) -> None:
        chat_send_btn.configure(state="normal", text="Спросить ИИ-ментора  ➔")
        _append_chat("ai", ans_str)

    chat_send_btn.configure(command=lambda: send_chat_q(None))
    chat_entry.bind("<Return>", lambda e: (send_chat_q(None), "break")[1] if not (e.state & 0x1) else None)

    for lbl_txt, q_txt in [
        ("На другом примере", "Объясни эту тему ещё проще на другом жизненном примере."),
        ("Подсказка", "Дай небольшую наводящую подсказку по задаче, не раскрывая весь код."),
        ("Разбери мой код", "Объясни, что делает каждая строчка в моём текущем коде."),
    ]:
        b = tk.Label(
            quick_q_frame,
            text=lbl_txt,
            font=("Segoe UI", 8, "bold"),
            bg=bg_tab,
            fg=fg_muted,
            padx=7,
            pady=3,
            cursor="hand2",
        )
        b.pack(side="left", padx=(0, 4))
        b.bind("<Button-1>", lambda _e, qt=q_txt: send_chat_q(qt))

    # Генерация персональной PDF-книги «От А до Я»
    def on_export_pdf() -> None:
        save_path = filedialog.asksaveasfilename(
            parent=win,
            title="Сохранить персональную PDF-книгу «От А до Я»",
            defaultextension=".pdf",
            initialfile="BahonIQ_Academy_Book_A_to_Z.pdf",
            filetypes=[("PDF-документ", "*.pdf")],
        )
        if not save_path:
            return

        pdf_btn.configure(state="disabled", text="⏳ Генерирую PDF-книгу...")

        def worker() -> None:
            try:
                pdf_bytes = build_academy_pdf_book()
                Path(save_path).write_bytes(pdf_bytes)
                win.after(0, lambda: _on_pdf_done(save_path, None))
            except Exception as exc:
                win.after(0, lambda: _on_pdf_done("", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_pdf_done(saved_file: str, err: Exception | None) -> None:
        pdf_btn.configure(state="normal", text="📘  Сгенерировать мою PDF-книгу (От А до Я)")
        if err:
            messagebox.showerror("Ошибка генерации PDF", str(err), parent=win)
            return
        if messagebox.askyesno(
            "PDF-книга готова!",
            f"Персональная книга-учебник «От А до Я» успешно сохранена:\n{saved_file}\n\nОткрыть PDF-книгу сейчас?",
            parent=win,
        ):
            try:
                os.startfile(saved_file)  # type: ignore[attr-defined]
            except Exception:
                pass

    pdf_btn.configure(command=on_export_pdf)

    # Первичная загрузка данных
    rm_init = get_roadmap_data()
    state_rm.update(rm_init)
    first_st = rm_init.get("stages", [{}])[0]
    first_lessons = first_st.get("lessons", [])
    if first_lessons:
        first_inc = next((x for x in first_lessons if not x.get("completed")), first_lessons[0])
        select_lesson_id(int(first_inc["id"]))
    else:
        render_all_navigation()

    return win
