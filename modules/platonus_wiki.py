# -*- coding: utf-8 -*-
"""Десктопное окно Platonus Wiki AI — премиальный тёмный/дневной интерфейс BahonIQ без белых рамок Treeview."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from services.settings_service import get_theme
from web_app.modules.wiki.service import (
    ask_wiki,
    delete_article,
    get_article,
    get_wiki_tree,
    init_wiki_db,
    upload_and_catalog_files,
)


def open_platonus_wiki(parent: tk.Misc) -> None:
    """Открывает современное двухколоночное окно Platonus Wiki AI."""
    init_wiki_db()
    theme = get_theme()
    is_day = theme.get("bg", "").lower() in ("#f1f5f9", "#e6ecf2", "#e2e8f0", "#ffffff", "#f4f7fa")

    if is_day:
        bg_main = "#E6ECF2"
        bg_sidebar = "#F8FAFC"
        bg_card = "#F4F7FA"
        bg_input = "#FFFFFF"
        bg_topic = "#E2E8F0"
        bg_topic_hover = "#CBD5E1"
        bg_item = "#F8FAFC"
        bg_item_hover = "#E0F2FE"
        bg_item_active = "#BAE6FD"
        fg_text = "#0F172A"
        fg_muted = "#475569"
        fg_sub = "#64748B"
        accent = "#0284C7"
        accent_hover = "#0369A1"
        green_btn = "#0D9488"
        green_hover = "#0F766E"
        border_col = "#CBD5E1"
    else:
        bg_main = "#060E1B"
        bg_sidebar = "#0A1526"
        bg_card = "#0F1D33"
        bg_input = "#081120"
        bg_topic = "#152744"
        bg_topic_hover = "#1D355C"
        bg_item = "#0B1628"
        bg_item_hover = "#142847"
        bg_item_active = "#163B5C"
        fg_text = "#F8FAFC"
        fg_muted = "#A9BDD3"
        fg_sub = "#647D96"
        accent = "#00B4D8"
        accent_hover = "#0096C7"
        green_btn = "#009246"
        green_hover = "#007A3D"
        border_col = "#1E3352"

    win = tk.Toplevel(parent)
    win.title("Platonus Wiki AI — База знаний и инструкций")
    win.geometry("1220x780")
    win.minsize(980, 640)
    win.configure(bg=bg_main)

    # Верхняя полоса брендинга
    top_stripe = tk.Frame(win, bg=accent, height=3)
    top_stripe.pack(fill="x", side="top")

    # Шапка окна
    header = tk.Frame(win, bg=bg_sidebar, padx=22, pady=12, highlightthickness=1, highlightbackground=border_col)
    header.pack(fill="x", side="top")

    title_box = tk.Frame(header, bg=bg_sidebar)
    title_box.pack(side="left")

    tk.Label(
        title_box,
        text="📖  Platonus Wiki AI",
        font=("Segoe UI", 15, "bold"),
        bg=bg_sidebar,
        fg=fg_text,
    ).pack(side="left")

    tk.Label(
        title_box,
        text="   |   Единая база официальных инструкций АИС «Platonus»",
        font=("Segoe UI", 10),
        bg=bg_sidebar,
        fg=fg_muted,
    ).pack(side="left", pady=(2, 0))

    stats_badge = tk.Label(
        header,
        text="Загрузка базы...",
        font=("Segoe UI", 9, "bold"),
        bg=bg_topic,
        fg=accent,
        padx=14,
        pady=5,
    )
    stats_badge.pack(side="right")

    # Главный двухколоночный контейнер
    body = tk.Frame(win, bg=bg_main, padx=16, pady=14)
    body.pack(fill="both", expand=True)

    # =========================================================================
    # ЛЕВАЯ ПАНЕЛЬ: Сайдбар базы знаний (350px) — кастомный тёмный аккордеон
    # =========================================================================
    left_panel = tk.Frame(
        body,
        bg=bg_sidebar,
        width=355,
        padx=14,
        pady=14,
        highlightthickness=1,
        highlightbackground=border_col,
    )
    left_panel.pack(side="left", fill="y", padx=(0, 14))
    left_panel.pack_propagate(False)

    # Кнопка загрузки файлов
    upload_btn = tk.Button(
        left_panel,
        text="＋  Загрузить инструкции (.pdf, .docx, .txt)",
        font=("Segoe UI", 10, "bold"),
        bg=green_btn,
        fg="#FFFFFF",
        activebackground=green_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        pady=10,
        cursor="hand2",
    )
    upload_btn.pack(fill="x", pady=(0, 10))

    # Поле быстрого фильтра по названиям статей
    search_wrap = tk.Frame(
        left_panel,
        bg=bg_input,
        highlightthickness=1,
        highlightbackground=border_col,
        padx=10,
        pady=6,
    )
    search_wrap.pack(fill="x", pady=(0, 10))

    tk.Label(
        search_wrap,
        text="🔍",
        font=("Segoe UI", 9),
        bg=bg_input,
        fg=fg_sub,
    ).pack(side="left", padx=(0, 6))

    search_var = tk.StringVar()
    search_entry = tk.Entry(
        search_wrap,
        textvariable=search_var,
        font=("Segoe UI", 10),
        bg=bg_input,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
        bd=0,
    )
    search_entry.pack(side="left", fill="x", expand=True)

    clear_search_btn = tk.Label(
        search_wrap,
        text="✕",
        font=("Segoe UI", 9, "bold"),
        bg=bg_input,
        fg=fg_sub,
        cursor="hand2",
    )
    clear_search_btn.pack(side="right")
    clear_search_btn.bind("<Button-1>", lambda _e: search_var.set(""))

    # Заголовок дерева + кнопка свернуть/развернуть все
    tree_hdr = tk.Frame(left_panel, bg=bg_sidebar)
    tree_hdr.pack(fill="x", pady=(0, 6))

    tk.Label(
        tree_hdr,
        text="РАЗДЕЛЫ БАЗЫ ЗНАНИЙ",
        font=("Segoe UI", 8, "bold"),
        bg=bg_sidebar,
        fg=fg_sub,
    ).pack(side="left")

    toggle_all_lbl = tk.Label(
        tree_hdr,
        text="Развернуть все",
        font=("Segoe UI", 8, "bold"),
        bg=bg_sidebar,
        fg=accent,
        cursor="hand2",
    )
    toggle_all_lbl.pack(side="right")

    # Прокручиваемый Canvas для тёмного аккордеона разделов и статей
    canvas_wrap = tk.Frame(left_panel, bg=bg_sidebar)
    canvas_wrap.pack(fill="both", expand=True)

    nav_canvas = tk.Canvas(
        canvas_wrap,
        bg=bg_sidebar,
        bd=0,
        highlightthickness=0,
    )
    nav_scrollbar = tk.Scrollbar(
        canvas_wrap,
        orient="vertical",
        command=nav_canvas.yview,
    )
    nav_inner = tk.Frame(nav_canvas, bg=bg_sidebar)

    nav_inner_id = nav_canvas.create_window((0, 0), window=nav_inner, anchor="nw")
    nav_canvas.configure(yscrollcommand=nav_scrollbar.set)

    nav_canvas.pack(side="left", fill="both", expand=True)
    nav_scrollbar.pack(side="right", fill="y")

    def _on_inner_configure(_event: object = None) -> None:
        nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))

    def _on_canvas_configure(event: tk.Event) -> None:
        nav_canvas.itemconfig(nav_inner_id, width=event.width)

    nav_inner.bind("<Configure>", _on_inner_configure)
    nav_canvas.bind("<Configure>", _on_canvas_configure)

    # Состояние разделов (по умолчанию открыт только первый раздел, чтобы не перегружать список из 117 статей)
    expanded_topics: set[int] = set()
    first_load_done = [False]
    selected_article_id: list[int | None] = [None]
    cached_tree_data: dict = {"total_topics": 0, "total_articles": 0, "topics": []}

    # =========================================================================
    # ПРАВАЯ ПАНЕЛЬ: Главное рабочее пространство (AI-поиск + Ответ / Статья)
    # =========================================================================
    right_panel = tk.Frame(
        body,
        bg=bg_card,
        padx=22,
        pady=18,
        highlightthickness=1,
        highlightbackground=border_col,
    )
    right_panel.pack(side="left", fill="both", expand=True)

    # Верхний блок поиска
    ask_title_row = tk.Frame(right_panel, bg=bg_card)
    ask_title_row.pack(fill="x", pady=(0, 8))

    tk.Label(
        ask_title_row,
        text="Умный AI-поиск по инструкциям Platonus",
        font=("Segoe UI", 13, "bold"),
        bg=bg_card,
        fg=fg_text,
    ).pack(side="left")

    tk.Label(
        ask_title_row,
        text="Enter — найти  •  Shift+Enter — новая строка",
        font=("Segoe UI", 9),
        bg=bg_card,
        fg=fg_sub,
    ).pack(side="right")

    # Строка ввода вопроса + Кнопка (сначала пакуем кнопку СПРАВА, чтобы она никогда не обрезалась!)
    query_row = tk.Frame(right_panel, bg=bg_card)
    query_row.pack(fill="x", pady=(0, 10))

    ask_btn = tk.Button(
        query_row,
        text="Найти ответ  ➔",
        font=("Segoe UI", 10, "bold"),
        bg=accent,
        fg="#FFFFFF",
        activebackground=accent_hover,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=20,
        pady=14,
        cursor="hand2",
    )
    ask_btn.pack(side="right", fill="y", padx=(10, 0))

    q_input_border = tk.Frame(
        query_row,
        bg=bg_input,
        highlightthickness=1,
        highlightbackground=border_col,
        padx=12,
        pady=8,
    )
    q_input_border.pack(side="left", fill="both", expand=True)

    q_entry = tk.Text(
        q_input_border,
        height=2,
        font=("Segoe UI", 11),
        bg=bg_input,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
        bd=0,
        wrap="word",
    )
    q_entry.pack(fill="both", expand=True)

    # Быстрые подсказки-чипсы для частых вопросов
    chips_frame = tk.Frame(right_panel, bg=bg_card)
    chips_frame.pack(fill="x", pady=(0, 12))

    tk.Label(
        chips_frame,
        text="Быстрые вопросы:",
        font=("Segoe UI", 9, "bold"),
        bg=bg_card,
        fg=fg_sub,
    ).pack(side="left", padx=(0, 8))

    quick_questions = [
        ("Как добавить РК?", "Как добавить, выставить и закрыть Рубежный контроль (РК-1, РК-2)?"),
        ("Закрепление ППС", "Как закрепить дисциплину за преподавателем в АИС Platonus?"),
        ("Не ставится оценка / НБ", "Почему не ставится оценка или НБ в журнале и как разблокировать?"),
        ("Общежития и корпуса", "Как заполнить сведения об учебных корпусах и общежитиях?"),
        ("Сброс пароля / роли", "Как создать пользователя, назначить роль или сбросить пароль?"),
    ]

    for short_label, full_q in quick_questions:
        chip = tk.Label(
            chips_frame,
            text=short_label,
            font=("Segoe UI", 8, "bold"),
            bg=bg_topic,
            fg=fg_muted,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        chip.pack(side="left", padx=3)
        chip.bind("<Enter>", lambda e, w=chip: w.configure(bg=bg_topic_hover, fg=fg_text))
        chip.bind("<Leave>", lambda e, w=chip: w.configure(bg=bg_topic, fg=fg_muted))
        chip.bind("<Button-1>", lambda e, q=full_q: _run_quick_question(q))

    # Панель управления ответом / открытой инструкцией
    action_bar = tk.Frame(
        right_panel,
        bg=bg_sidebar,
        padx=14,
        pady=8,
        highlightthickness=1,
        highlightbackground=border_col,
    )
    action_bar.pack(fill="x", pady=(0, 8))

    mode_status_lbl = tk.Label(
        action_bar,
        text="●  Готов к поиску по 117 инструкциям",
        font=("Segoe UI", 9, "bold"),
        bg=bg_sidebar,
        fg=accent,
    )
    mode_status_lbl.pack(side="left")

    del_btn = tk.Button(
        action_bar,
        text="🗑 Удалить инструкцию",
        font=("Segoe UI", 9),
        bg=bg_topic,
        fg=fg_muted,
        relief="flat",
        bd=0,
        padx=12,
        pady=4,
        cursor="hand2",
        state="disabled",
    )
    del_btn.pack(side="right", padx=(6, 0))

    copy_btn = tk.Button(
        action_bar,
        text="📋 Скопировать текст",
        font=("Segoe UI", 9, "bold"),
        bg=bg_topic,
        fg=fg_text,
        activebackground=bg_topic_hover,
        activeforeground=fg_text,
        relief="flat",
        bd=0,
        padx=12,
        pady=4,
        cursor="hand2",
    )
    copy_btn.pack(side="right")

    # Область вывода результата с красивым форматированием
    out_wrap = tk.Frame(
        right_panel,
        bg=bg_input,
        highlightthickness=1,
        highlightbackground=border_col,
    )
    out_wrap.pack(fill="both", expand=True)

    out_scroll = tk.Scrollbar(out_wrap, orient="vertical")
    output_text = tk.Text(
        out_wrap,
        font=("Segoe UI", 11),
        bg=bg_input,
        fg=fg_text,
        relief="flat",
        bd=0,
        padx=20,
        pady=18,
        wrap="word",
        spacing1=4,
        spacing2=3,
        spacing3=6,
        yscrollcommand=out_scroll.set,
        state="disabled",
    )
    out_scroll.configure(command=output_text.yview)
    output_text.pack(side="left", fill="both", expand=True)
    out_scroll.pack(side="right", fill="y")

    # Настройка типографики в области ответа
    output_text.tag_configure("h1", font=("Segoe UI", 14, "bold"), foreground=fg_text, spacing1=4, spacing3=10)
    output_text.tag_configure("badge", font=("Segoe UI", 9, "bold"), foreground=accent, spacing3=6)
    output_text.tag_configure("bold", font=("Segoe UI", 11, "bold"), foreground=accent)
    output_text.tag_configure("step_num", font=("Segoe UI", 11, "bold"), foreground=green_btn)
    output_text.tag_configure("muted", font=("Segoe UI", 10), foreground=fg_sub)
    output_text.tag_configure("divider", font=("Segoe UI", 9), foreground=border_col, spacing1=8, spacing3=8)

    def _render_formatted_text(title_str: str, subtitle_str: str, body_str: str, footer_str: str = "") -> None:
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")

        if subtitle_str:
            output_text.insert("end", subtitle_str.upper() + "\n", "badge")
        if title_str:
            output_text.insert("end", title_str + "\n", "h1")
            output_text.insert("end", "─" * 68 + "\n", "divider")

        for line in body_str.splitlines():
            # Выделяем **жирный** текст
            parts = re.split(r"(\*\*[^*]+\*\*)", line)
            for idx, part in enumerate(parts):
                if part.startswith("**") and part.endswith("**"):
                    output_text.insert("end", part[2:-2], "bold")
                else:
                    # Подсветка нумерации шагов в начале строки
                    if idx == 0:
                        m = re.match(r"^(\s*(?:\d+[\.\)]|[•\-]))(\s+.*)$", part)
                        if m:
                            output_text.insert("end", m.group(1), "step_num")
                            output_text.insert("end", m.group(2))
                            continue
                    output_text.insert("end", part)
            output_text.insert("end", "\n")

        if footer_str:
            output_text.insert("end", "\n" + "─" * 68 + "\n", "divider")
            output_text.insert("end", footer_str + "\n", "muted")

        output_text.configure(state="disabled")
        output_text.yview_moveto(0.0)

    def _show_welcome_guide() -> None:
        total_a = cached_tree_data.get("total_articles", 0)
        total_t = cached_tree_data.get("total_topics", 0)
        _render_formatted_text(
            title_str=f"База знаний готова к работе ({total_a} инструкций в {total_t} разделах)",
            subtitle_str="Platonus Wiki AI  •  Интеллектуальный справочник",
            body_str=(
                "Как пользоваться модулем:\n\n"
                "1. **Свободный поиск с ИИ:** введите любой вопрос в поле выше (например: **«как добавить РК»**, "
                "**«как заселить студента в общежитие»** или **«как закрепить дисциплину за ППС»**) и нажмите **Найти ответ**.\n"
                "2. **Чтение инструкций по разделам:** слева расположен каталог всех загруженных инструкций. "
                "Нажмите на название раздела, чтобы раскрыть список, и кликните на любую статью для просмотра её полного текста.\n"
                "3. **Пополнение базы:** нажмите зелёную кнопку **«＋ Загрузить инструкции»** слева вверху, чтобы добавить новые файлы PDF, Word или TXT."
            ),
        )

    # =========================================================================
    # ОТРИСОВКА КАСТОМНОГО АККОРДЕОНА СЛЕВА
    # =========================================================================
    def rebuild_sidebar_accordion(filter_q: str = "") -> None:
        for child in nav_inner.winfo_children():
            child.destroy()

        topics = cached_tree_data.get("topics", [])
        q = filter_q.strip().lower()

        if not first_load_done[0] and topics:
            expanded_topics.add(int(topics[0]["id"]))
            first_load_done[0] = True

        shown_topics = 0
        for topic in topics:
            t_id = int(topic["id"])
            arts = [
                a for a in topic.get("articles", [])
                if not q or q in a["title"].lower() or q in topic["name"].lower()
            ]
            if not arts:
                continue
            shown_topics += 1
            is_open = bool(q) or (t_id in expanded_topics)

            # Блок раздела
            t_block = tk.Frame(nav_inner, bg=bg_sidebar, pady=3)
            t_block.pack(fill="x")

            t_hdr = tk.Frame(
                t_block,
                bg=bg_topic,
                padx=10,
                pady=8,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=border_col,
            )
            t_hdr.pack(fill="x")

            arrow_char = "▾" if is_open else "▸"
            count_lbl = tk.Label(
                t_hdr,
                text=str(len(arts)),
                font=("Segoe UI", 8, "bold"),
                bg=bg_input,
                fg=accent,
                padx=7,
                pady=1,
            )
            count_lbl.pack(side="right", padx=(6, 0))

            t_title_lbl = tk.Label(
                t_hdr,
                text=f"{arrow_char}  {topic['name']}",
                font=("Segoe UI", 9, "bold"),
                bg=bg_topic,
                fg=fg_text,
                anchor="w",
                justify="left",
                wraplength=255,
                cursor="hand2",
            )
            t_title_lbl.pack(side="left", fill="x", expand=True)

            def _toggle_topic(tid: int = t_id) -> None:
                if tid in expanded_topics:
                    expanded_topics.remove(tid)
                else:
                    expanded_topics.add(tid)
                rebuild_sidebar_accordion(search_var.get())

            for w in (t_hdr, t_title_lbl, count_lbl):
                w.bind("<Button-1>", lambda _e, tid=t_id: _toggle_topic(tid))

            if is_open:
                items_box = tk.Frame(t_block, bg=bg_sidebar, padx=4, pady=3)
                items_box.pack(fill="x")

                for art in arts:
                    aid = int(art["id"])
                    is_sel = selected_article_id[0] == aid
                    row_bg = bg_item_active if is_sel else bg_item
                    row_fg = accent if is_sel else fg_muted

                    item_frame = tk.Frame(
                        items_box,
                        bg=row_bg,
                        padx=10,
                        pady=7,
                        cursor="hand2",
                        highlightthickness=1,
                        highlightbackground=accent if is_sel else border_col,
                    )
                    item_frame.pack(fill="x", pady=2)

                    item_lbl = tk.Label(
                        item_frame,
                        text=art["title"],
                        font=("Segoe UI", 9, "bold" if is_sel else "normal"),
                        bg=row_bg,
                        fg=row_fg,
                        anchor="w",
                        justify="left",
                        wraplength=285,
                        cursor="hand2",
                    )
                    item_lbl.pack(fill="x")

                    def _on_enter(_e: object, fr: tk.Frame = item_frame, lb: tk.Label = item_lbl, a_id: int = aid) -> None:
                        if selected_article_id[0] != a_id:
                            fr.configure(bg=bg_item_hover)
                            lb.configure(bg=bg_item_hover, fg=fg_text)

                    def _on_leave(_e: object, fr: tk.Frame = item_frame, lb: tk.Label = item_lbl, a_id: int = aid) -> None:
                        if selected_article_id[0] != a_id:
                            fr.configure(bg=bg_item)
                            lb.configure(bg=bg_item, fg=fg_muted)

                    item_frame.bind("<Enter>", _on_enter)
                    item_lbl.bind("<Enter>", _on_enter)
                    item_frame.bind("<Leave>", _on_leave)
                    item_lbl.bind("<Leave>", _on_leave)

                    item_frame.bind("<Button-1>", lambda _e, a_id=aid: select_article(a_id))
                    item_lbl.bind("<Button-1>", lambda _e, a_id=aid: select_article(a_id))

        if shown_topics == 0:
            tk.Label(
                nav_inner,
                text="По вашему фильтру инструкций не найдено.",
                font=("Segoe UI", 9),
                bg=bg_sidebar,
                fg=fg_sub,
                pady=20,
            ).pack(fill="x")

        nav_inner.update_idletasks()
        nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))

    def reload_tree_from_db() -> None:
        data = get_wiki_tree()
        cached_tree_data.clear()
        cached_tree_data.update(data)
        stats_badge.configure(
            text=f"Разделов: {data['total_topics']}  •  Инструкций: {data['total_articles']}"
        )
        mode_status_lbl.configure(
            text=f"●  В базе активно {data['total_articles']} инструкций"
        )
        rebuild_sidebar_accordion(search_var.get())

    def toggle_all_sections(_event: object = None) -> None:
        all_ids = {int(t["id"]) for t in cached_tree_data.get("topics", [])}
        if len(expanded_topics) == len(all_ids):
            expanded_topics.clear()
            toggle_all_lbl.configure(text="Развернуть все")
        else:
            expanded_topics.update(all_ids)
            toggle_all_lbl.configure(text="Свернуть все")
        rebuild_sidebar_accordion(search_var.get())

    toggle_all_lbl.bind("<Button-1>", toggle_all_sections)
    search_var.trace_add("write", lambda *_: rebuild_sidebar_accordion(search_var.get()))

    # Прокрутка колёсиком мыши в зависимости от положения курсора
    def _on_mousewheel(event: tk.Event) -> None:
        if not win.winfo_exists():
            return
        x_root = event.x_root
        left_x = left_panel.winfo_rootx()
        left_w = left_panel.winfo_width()
        delta = int(-1 * (event.delta / 120))
        if left_x <= x_root <= left_x + left_w:
            nav_canvas.yview_scroll(delta, "units")
        else:
            output_text.yview_scroll(delta, "units")

    win.bind("<MouseWheel>", _on_mousewheel)

    # =========================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ: ОТКРЫТИЕ СТАТЬИ, ПОИСК И ЗАГРУЗКА
    # =========================================================================
    def select_article(aid: int) -> None:
        art = get_article(aid)
        if not art:
            return
        selected_article_id[0] = aid
        del_btn.configure(state="normal", fg="#EF4444")
        mode_status_lbl.configure(text=f"📄  Просмотр инструкции #{aid}")
        rebuild_sidebar_accordion(search_var.get())

        src_info = f"Исходный файл: {art['source_filename']}" if art.get("source_filename") else ""
        _render_formatted_text(
            title_str=art["title"],
            subtitle_str=art["topic_name"],
            body_str=art["content"],
            footer_str=src_info,
        )

    def _run_quick_question(q_text: str) -> None:
        q_entry.delete("1.0", "end")
        q_entry.insert("1.0", q_text)
        on_ask()

    def on_ask() -> None:
        q = q_entry.get("1.0", "end").strip()
        if not q:
            return
        selected_article_id[0] = None
        del_btn.configure(state="disabled", fg=fg_muted)
        rebuild_sidebar_accordion(search_var.get())

        ask_btn.configure(state="disabled", text="⏳ Поиск...")
        mode_status_lbl.configure(text="⏳  ИИ анализирует базу инструкций...")
        _render_formatted_text(
            title_str=f"Вопрос: «{q}»",
            subtitle_str="Поиск по базе знаний Platonus",
            body_str="⏳ Пожалуйста, подождите 2–3 секунды. ИИ сверяет ваш вопрос с загруженными инструкциями...",
        )

        def worker() -> None:
            try:
                res = ask_wiki(q)
                win.after(0, lambda: _display_ai_answer(q, res, None))
            except Exception as exc:
                win.after(0, lambda: _display_ai_answer(q, None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _display_ai_answer(q: str, res: dict | None, err: Exception | None) -> None:
        ask_btn.configure(state="normal", text="Найти ответ  ➔")
        if err:
            mode_status_lbl.configure(text="❌  Ошибка поиска")
            _render_formatted_text("Ошибка выполнения запроса", "Platonus Wiki AI", str(err))
            return

        if not res:
            return
        mode_status_lbl.configure(text="✓  Ответ сформирован строго по базе инструкций")
        srcs = res.get("sources", [])
        footer = ""
        if srcs:
            footer = "Использованные инструкции из вашей базы:\n" + "\n".join(
                f"  • {s['title']}  [{s['topic_name']}]" for s in srcs
            )
        _render_formatted_text(
            title_str=q,
            subtitle_str="Пошаговый ответ по регламенту Platonus",
            body_str=res.get("answer", ""),
            footer_str=footer,
        )

    ask_btn.configure(command=on_ask)
    q_entry.bind("<Return>", lambda e: (on_ask(), "break")[1] if not (e.state & 0x1) else None)

    def on_copy() -> None:
        txt = output_text.get("1.0", "end").strip()
        if not txt:
            return
        win.clipboard_clear()
        win.clipboard_append(txt)
        orig = copy_btn.cget("text")
        copy_btn.configure(text="✓ Скопировано!")
        win.after(1600, lambda: copy_btn.configure(text=orig))

    copy_btn.configure(command=on_copy)

    def on_delete() -> None:
        aid = selected_article_id[0]
        if not aid:
            return
        if messagebox.askyesno("Удаление инструкции", "Удалить выбранную инструкцию из базы знаний?", parent=win):
            delete_article(aid)
            selected_article_id[0] = None
            del_btn.configure(state="disabled", fg=fg_muted)
            reload_tree_from_db()
            _show_welcome_guide()

    del_btn.configure(command=on_delete)

    def on_upload() -> None:
        paths = filedialog.askopenfilenames(
            parent=win,
            title="Выберите файлы инструкций Platonus (.pdf, .docx, .txt)",
            filetypes=[("Инструкции (PDF, Word, TXT)", "*.pdf *.docx *.doc *.txt *.md")],
        )
        if not paths:
            return

        payload: list[tuple[str, bytes]] = []
        for p in paths:
            fp = Path(p)
            try:
                payload.append((fp.name, fp.read_bytes()))
            except Exception:
                pass
        if not payload:
            return

        upload_btn.configure(state="disabled", text=f"⏳ Обработка ({len(payload)} файл.)...")
        mode_status_lbl.configure(text="⏳  ИИ читает файлы и распределяет инструкции по разделам...")

        def worker() -> None:
            try:
                res = upload_and_catalog_files(payload)
                win.after(0, lambda: _on_upload_done(res, None))
            except Exception as exc:
                win.after(0, lambda: _on_upload_done(None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_upload_done(res: dict | None, err: Exception | None) -> None:
        upload_btn.configure(state="normal", text="＋  Загрузить инструкции (.pdf, .docx, .txt)")
        if err:
            messagebox.showerror("Ошибка загрузки", str(err), parent=win)
            return
        reload_tree_from_db()
        created = res.get("articles_created", []) if res else []
        messagebox.showinfo(
            "Загрузка завершена",
            f"Обработано файлов: {res.get('files_processed', 0)}\n"
            f"Добавлено / обновлено инструкций: {len(created)}",
            parent=win,
        )

    upload_btn.configure(command=on_upload)

    reload_tree_from_db()
    _show_welcome_guide()
