# -*- coding: utf-8 -*-
"""Точка входа BahonIQ Work Center v2.0.0."""

import os
import sys
import traceback
from pathlib import Path

# Убедимся, что корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    try:
        from app.splash import SplashScreen
        from bootstrap import start_app

        # Показываем Splash Screen с быстрой фоновой инициализацией
        splash = SplashScreen(on_complete=start_app)
        splash.show()

    except BaseException:
        error_file = "BahonIQ_error.log"
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                f.write("=== BAHONIQ — ОШИБКА ЗАПУСКА ===\n\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
