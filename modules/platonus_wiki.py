# -*- coding: utf-8 -*-
"""Десктопный клиент Platonus Wiki AI — работает строго через единый облачный API (без локальной БД)."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from services.settings_service import get_theme

CLOUD_API_BASE = os.getenv("BAHONIQ_CLOUD_URL", "https://bahoniq.onrender.com").rstrip("/")


def _api_request(method: str, path: str, json_body: dict | None = None, timeout: int = 45) -> dict:
    """Выполняет запрос к единому облачному API BahonIQ."""
    url = f"{CLOUD_API_BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_upload_files(files_payload: list[tuple[str, bytes]], timeout: int = 90) -> dict:
    """Отправляет пакет файлов в облачный эндпоинт POST /api/wiki/upload (multipart/form-data)."""
    import requests
    url = f"{CLOUD_API_BASE}/api/wiki/upload"
    multipart_files = [
        ("files", (fname, fbytes, "application/octet-stream"))
        for fname, fbytes in files_payload
    ]
    resp = requests.post(url, files=multipart_files, timeout=timeout)
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(detail)
    return resp.json()


def open_platonus_wiki(parent: tk.Misc) -> None:
    """Открывает окно Platonus Wiki AI, подключенное к единому серверному API."""
    theme = get_theme()
    bg_main = theme.get("bg", "#0B1526")
    bg_card = theme.get("card", "#122238")
    fg_text = theme.get("text", "#F1F5F9")
    fg_muted = theme.get("gray", "#94A3B8")
    accent = "#00B4D8"

    win = tk.Toplevel(parent)
    win.title("Platonus Wiki AI — Облачная база знаний")
    win.geometry("1120x740")
    win.minsize(920, 620)
    win.configure(bg=bg_main)

    header = tk.Frame(win, bg=bg_card, padx=20, pady=12)
    header.pack(fill="x", side="top")

    tk.Label(
        header,
        text="Platonus Wiki AI",
        font=("Segoe UI", 15, "bold"),
        bg=bg_card,
        fg=fg_text,
    ).pack(side="left")

    stats_lbl = tk.Label(
        header,
        text="Подключение к облачной базе...",
        font=("Segoe UI", 10, "bold"),
        bg=bg_card,
        fg=accent,
        padx=14,
    )
    stats_lbl.pack(side="right")

    body = tk.Frame(win, bg=bg_main, padx=16, pady=14)
    body.pack(fill="both", expand=True)

    left_frame = tk.Frame(body, bg=bg_card, width=310, padx=12, pady=12)
    left_frame.pack(side="left", fill="y", padx=(0, 14))
    left_frame.pack_propagate(False)

    right_frame = tk.Frame(body, bg=bg_card, padx=18, pady=16)
    right_frame.pack(side="left", fill="both", expand=True)

    article_map: dict[str, int] = {}
    cached_tree: dict = {"total_topics": 0, "total_articles": 0, "topics": []}
    current_article_id: list[int | None] = [None]

    def render_tree(filter_q: str = "") -> None:
        stats_lbl.configure(
            text=f"Разделов: {cached_tree.get('total_topics', 0)} • Инструкций: {cached_tree.get('total_articles', 0)}"
        )
        for item in tree.get_children():
            tree.delete(item)
        article_map.clear()

        q = filter_q.strip().lower()
        for topic in cached_tree.get("topics", []):
            arts = [
                a for a in topic.get("articles", [])
                if not q or q in a["title"].lower() or q in topic["name"].lower()
            ]
            if not arts:
                continue
            t_node = tree.insert("", "end", text=f"📁 {topic['name']} ({len(arts)})", open=True)
            for a in arts:
                a_node = tree.insert(t_node, "end", text=f"📄 {a['title']}")
                article_map[a_node] = int(a["id"])

    def fetch_tree_async() -> None:
        def worker() -> None:
            try:
                data = _api_request("GET", "/api/wiki/tree")
                cached_tree.clear()
                cached_tree.update(data)
                win.after(0, lambda: render_tree(search_var.get()))
            except Exception as exc:
                win.after(0, lambda: stats_lbl.configure(text=f"Нет связи с API: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def on_upload_files() -> None:
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

        upload_btn.configure(state="disabled", text="⏳ ИИ разбирает файлы...")

        def worker() -> None:
            try:
                res = _api_upload_files(payload)
                win.after(0, lambda: _on_upload_done(res, None))
            except Exception as exc:
                win.after(0, lambda: _on_upload_done(None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_upload_done(res: dict | None, err: Exception | None) -> None:
        upload_btn.configure(state="normal", text="+ Загрузить инструкции")
        if err:
            messagebox.showerror("Ошибка загрузки", str(err), parent=win)
            return
        fetch_tree_async()
        created = res.get("articles_created", []) if res else []
        messagebox.showinfo(
            "Загрузка завершена",
            f"Обработано файлов: {res.get('files_processed', 0)}\n"
            f"Сохранено инструкций в облачную базу: {len(created)}",
            parent=win,
        )

    upload_btn = tk.Button(
        left_frame,
        text="+ Загрузить инструкции",
        font=("Segoe UI", 10, "bold"),
        bg="#009246",
        fg="#FFFFFF",
        activebackground="#007A3D",
        activeforeground="#FFFFFF",
        relief="flat",
        pady=8,
        cursor="hand2",
        command=on_upload_files,
    )
    upload_btn.pack(fill="x", pady=(0, 10))

    search_var = tk.StringVar()
    search_entry = tk.Entry(
        left_frame,
        textvariable=search_var,
        font=("Segoe UI", 10),
        bg=bg_main,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
    )
    search_entry.pack(fill="x", ipady=5, pady=(0, 8))
    search_var.trace_add("write", lambda *_: render_tree(search_var.get()))

    style = ttk.Style(win)
    style.configure("Wiki.Treeview", rowheight=26, font=("Segoe UI", 9))
    tree = ttk.Treeview(left_frame, show="tree", style="Wiki.Treeview")
    tree.pack(fill="both", expand=True)

    tk.Label(
        right_frame,
        text="Умный поиск по инструкциям Platonus",
        font=("Segoe UI", 12, "bold"),
        bg=bg_card,
        fg=fg_text,
    ).pack(anchor="w")

    q_frame = tk.Frame(right_frame, bg=bg_card, pady=8)
    q_frame.pack(fill="x")

    q_entry = tk.Text(
        q_frame,
        height=3,
        font=("Segoe UI", 11),
        bg=bg_main,
        fg=fg_text,
        insertbackground=fg_text,
        relief="flat",
        padx=10,
        pady=8,
        wrap="word",
    )
    q_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def on_ask() -> None:
        q = q_entry.get("1.0", "end").strip()
        if not q:
            return
        ask_btn.configure(state="disabled", text="Поиск...")
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")
        output_text.insert("1.0", "⏳ Запрос к облачной базе знаний Platonus Wiki AI...")
        output_text.configure(state="disabled")

        def worker() -> None:
            try:
                res = _api_request("POST", "/api/wiki/ask", json_body={"query": q})
                win.after(0, lambda: _show_answer(res, None))
            except Exception as exc:
                win.after(0, lambda: _show_answer(None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _show_answer(res: dict | None, err: Exception | None) -> None:
        ask_btn.configure(state="normal", text="Получить ответ")
        current_article_id[0] = None
        del_btn.configure(state="disabled")
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")
        if err:
            output_text.insert("1.0", f"Ошибка: {err}")
        elif res:
            srcs = res.get("sources", [])
            src_lines = "\n".join(f"• {s['title']} ({s['topic_name']})" for s in srcs)
            full_out = res.get("answer", "")
            if src_lines:
                full_out += f"\n\n────────────────────────────\nСтатьи-источники в базе:\n{src_lines}"
            output_text.insert("1.0", full_out)
        output_text.configure(state="disabled")

    ask_btn = tk.Button(
        q_frame,
        text="Получить ответ",
        font=("Segoe UI", 10, "bold"),
        bg=accent,
        fg="#FFFFFF",
        relief="flat",
        padx=16,
        pady=14,
        cursor="hand2",
        command=on_ask,
    )
    ask_btn.pack(side="right")

    q_entry.bind("<Return>", lambda e: (on_ask(), "break")[1] if not (e.state & 0x1) else None)

    toolbar = tk.Frame(right_frame, bg=bg_card, pady=4)
    toolbar.pack(fill="x")

    def copy_output() -> None:
        txt = output_text.get("1.0", "end").strip()
        if txt:
            win.clipboard_clear()
            win.clipboard_append(txt)
            messagebox.showinfo("Скопировано", "Текст скопирован в буфер обмена.", parent=win)

    def delete_current_art() -> None:
        aid = current_article_id[0]
        if not aid:
            return
        if messagebox.askyesno("Удаление", "Удалить выбранную инструкцию из базы знаний?", parent=win):
            def worker() -> None:
                try:
                    _api_request("DELETE", f"/api/wiki/articles/{aid}")
                    win.after(0, fetch_tree_async)
                except Exception as exc:
                    win.after(0, lambda: messagebox.showerror("Ошибка", str(exc), parent=win))

            threading.Thread(target=worker, daemon=True).start()
            current_article_id[0] = None
            del_btn.configure(state="disabled")
            output_text.configure(state="normal")
            output_text.delete("1.0", "end")
            output_text.configure(state="disabled")

    tk.Button(
        toolbar,
        text="📋 Скопировать ответ / инструкцию",
        font=("Segoe UI", 9, "bold"),
        bg=bg_main,
        fg=fg_text,
        relief="flat",
        padx=12,
        pady=5,
        cursor="hand2",
        command=copy_output,
    ).pack(side="left")

    del_btn = tk.Button(
        toolbar,
        text="🗑 Удалить статью",
        font=("Segoe UI", 9),
        bg=bg_main,
        fg=fg_muted,
        relief="flat",
        padx=12,
        pady=5,
        state="disabled",
        command=delete_current_art,
    )
    del_btn.pack(side="right")

    output_text = tk.Text(
        right_frame,
        font=("Segoe UI", 11),
        bg=bg_main,
        fg=fg_text,
        relief="flat",
        padx=14,
        pady=14,
        wrap="word",
        state="disabled",
    )
    output_text.pack(fill="both", expand=True, pady=(6, 0))

    def on_tree_select(_event: object) -> None:
        sel = tree.selection()
        if not sel:
            return
        aid = article_map.get(sel[0])
        if not aid:
            return

        def worker() -> None:
            try:
                art = _api_request("GET", f"/api/wiki/articles/{aid}")
                win.after(0, lambda: _display_article(art))
            except Exception as exc:
                win.after(0, lambda: messagebox.showerror("Ошибка", str(exc), parent=win))

        threading.Thread(target=worker, daemon=True).start()

    def _display_article(art: dict) -> None:
        current_article_id[0] = int(art["id"])
        del_btn.configure(state="normal")
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")
        header_str = f"РАЗДЕЛ: {art['topic_name']}\nИНСТРУКЦИЯ: {art['title']}\n"
        if art.get("source_filename"):
            header_str += f"ИСХОДНЫЙ ФАЙЛ: {art['source_filename']}\n"
        header_str += "─" * 50 + "\n\n"
        output_text.insert("1.0", header_str + art["content"])
        output_text.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", on_tree_select)

    fetch_tree_async()
