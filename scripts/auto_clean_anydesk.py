# -*- coding: utf-8 -*-
"""
BahonIQ — Автоматическая очистка данных AnyDesk по расписанию.
Запускается автономно через Планировщик Windows (Task Scheduler)
или вручную без открытия консольного окна.
"""

import os
import sys
import shutil
import datetime
from pathlib import Path

# Корень проекта
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "anydesk_cleanup.log"

ANYDESK_DATA_FOLDER = Path(os.path.expanduser(r"~\AppData\Roaming\AnyDesk"))


def log_message(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def run_cleanup():
    log_message("=== Запуск автоочистки AnyDesk ===")
    if not ANYDESK_DATA_FOLDER.exists():
        log_message(f"Папка {ANYDESK_DATA_FOLDER} не найдена. Очистка пропущена.")
        return 0, 0

    deleted = 0
    skipped = 0

    try:
        items = list(ANYDESK_DATA_FOLDER.iterdir())
    except Exception as e:
        log_message(f"Ошибка чтения папки: {e}")
        return 0, 0

    for item in items:
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            skipped += 1

    log_message(f"Очистка успешно завершена. Удалено: {deleted}, пропущено: {skipped}")
    return deleted, skipped


if __name__ == "__main__":
    run_cleanup()
