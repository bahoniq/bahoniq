# -*- coding: utf-8 -*-
"""Модуль заставки (Splash Screen) BahonIQ Work Center v2.0.0."""

import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk


class SplashScreen:
    """Безрамочный Splash Screen в темном стиле BahonIQ."""

    def __init__(self, on_complete=None):
        self.on_complete = on_complete

        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bahoniq.workcenter.v2")
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg="#121820")

        self.project_dir = Path(__file__).resolve().parent.parent
        self.assets_dir = self.project_dir / "assets"

        ico_path = self.assets_dir / "icon.ico"
        if ico_path.is_file():
            try:
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

        # Размеры окна
        self.width = 580
        self.height = 390

        # Центрирование на экране
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = (screen_h - self.height) // 2
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        self._build_ui()

        # Потоки инициализации
        self.start_time = time.time()
        self.duration = 5.5  # 5.5 секунд демонстрации заставки
        self.is_done = False
        self.ai_status_text = ""

        # Запуск фонового воркера инициализации
        threading.Thread(target=self._initialization_worker, daemon=True).start()
        self._tick_progress()

    def _build_ui(self):
        # Загрузка логотипа
        logo_path = self.assets_dir / "logo.png"
        self.logo_img = None
        if logo_path.is_file():
            try:
                pil_img = Image.open(logo_path).resize((160, 160), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

        # Верхний контейнер с логотипом
        self.center_frame = tk.Frame(self.root, bg="#121820")
        self.center_frame.pack(expand=True, fill="both", padx=20, pady=(25, 10))

        if self.logo_img:
            self.logo_label = tk.Label(self.center_frame, image=self.logo_img, bg="#121820", bd=0)
            self.logo_label.pack(pady=(0, 5))

        self.title_label = tk.Label(
            self.center_frame,
            text="BahonIQ",
            font=("Segoe UI", 20, "bold"),
            fg="#2CE080",
            bg="#121820",
            bd=0,
        )
        self.title_label.pack()

        self.status_label = tk.Label(
            self.center_frame,
            text="Инициализация систем...",
            font=("Segoe UI", 10),
            fg="#7E90A2",
            bg="#121820",
            bd=0,
        )
        self.status_label.pack(pady=(12, 10))

        # Кастомный неоновый прогресс-бар через Canvas
        self.canvas_prog = tk.Canvas(
            self.center_frame,
            width=360,
            height=6,
            bg="#1B2430",
            highlightthickness=0,
            bd=0,
        )
        self.canvas_prog.pack(pady=(0, 8))
        self.prog_rect = self.canvas_prog.create_rectangle(0, 0, 0, 6, fill="#2CE080", outline="")

        # Нижняя плашка
        self.bottom_frame = tk.Frame(self.root, bg="#121820")
        self.bottom_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.ver_label = tk.Label(
            self.bottom_frame,
            text="Версия 2.0.0",
            font=("Segoe UI", 8),
            fg="#4A5B6D",
            bg="#121820",
            bd=0,
        )
        self.ver_label.pack(side="left")

        self.copy_label = tk.Label(
            self.bottom_frame,
            text="© 2026 BahonIQ Work Center",
            font=("Segoe UI", 8),
            fg="#4A5B6D",
            bg="#121820",
            bd=0,
        )
        self.copy_label.pack(side="right")

    def _initialization_worker(self):
        """Фоновая подгрузка модулей и проверка ИИ с выдержкой времени для демонстрации заставки."""
        try:
            # 1. Чтение .env
            from dotenv import load_dotenv
            env_path = self.project_dir / ".env"
            if env_path.is_file():
                load_dotenv(env_path, override=True)
            self._set_status("Инициализация систем BahonIQ Work Center...")
            time.sleep(1.2)

            # 2. Предзагрузка модулей
            self._set_status("Загрузка модулей Excel AI, Analytics AI, PDF Center...")
            import pandas
            import openpyxl
            import ai_service
            time.sleep(1.3)

            # 3. Быстрый пинг ИИ
            self._set_status("Инициализация аналитического ядра BahonIQ AI & Local Node...")
            st = ai_service.check_ai_status()
            if st.get("gemini"):
                self.ai_status_text = "BahonIQ AI: Online"
            elif st.get("ollama"):
                self.ai_status_text = "Ollama Local: Online"
            else:
                self.ai_status_text = "Автономный режим"
            time.sleep(1.3)

            self._set_status(f"Связь установлена ({self.ai_status_text}) • Запуск дашборда...")

            # Выдерживаем общее время до duration (5.5 секунд)
            elapsed = time.time() - self.start_time
            if elapsed < self.duration:
                time.sleep(self.duration - elapsed)

        except Exception as exc:
            print(f"[Splash] Ошибка инициализации: {exc}")
        finally:
            self.is_done = True

    def _set_status(self, text):
        self.root.after(0, lambda: self.status_label.configure(text=text))

    def _tick_progress(self):
        elapsed = time.time() - self.start_time
        target_pct = min(100, int((elapsed / self.duration) * 100))

        if self.is_done and target_pct < 100:
            target_pct = 100

        curr_w = int((target_pct / 100.0) * 360)
        self.canvas_prog.coords(self.prog_rect, 0, 0, curr_w, 6)

        if elapsed >= self.duration and self.is_done:
            self.root.destroy()
            if callable(self.on_complete):
                self.on_complete()
            return

        self.root.after(40, self._tick_progress)

    def show(self):
        self.root.mainloop()
