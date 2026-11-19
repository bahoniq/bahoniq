# -*- coding: utf-8 -*-
"""
Управление планировщиком Windows для автоочистки AnyDesk.
Поддерживает расписание:
- Понедельник 09:00 и Четверг 17:30
- Ежедневно (Daily)
"""

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = BASE_DIR / "scripts" / "auto_clean_anydesk.py"

# Находим путь к pythonw.exe (без консольного окна)
PYTHONW_PATH = Path(sys.executable).parent / "pythonw.exe"
if not PYTHONW_PATH.exists():
    PYTHONW_PATH = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"))
if not PYTHONW_PATH.exists():
    PYTHONW_PATH = Path(sys.executable)

TASK_MON = "BahonIQ_AnyDesk_Clean_Mon"
TASK_THU = "BahonIQ_AnyDesk_Clean_Thu"
TASK_DAILY = "BahonIQ_AnyDesk_Clean_Daily"


def install_weekly_schedule() -> bool:
    """Устанавливает автоочистку: Понедельник в 09:00 и Четверг в 17:30."""
    uninstall_all()
    cmd_mon = [
        "schtasks", "/create", "/f",
        "/tn", TASK_MON,
        "/tr", f'"{PYTHONW_PATH}" "{SCRIPT_PATH}"',
        "/sc", "WEEKLY", "/d", "MON",
        "/st", "09:00",
    ]
    cmd_thu = [
        "schtasks", "/create", "/f",
        "/tn", TASK_THU,
        "/tr", f'"{PYTHONW_PATH}" "{SCRIPT_PATH}"',
        "/sc", "WEEKLY", "/d", "THU",
        "/st", "17:30",
    ]
    res_mon = subprocess.run(cmd_mon, capture_output=True, text=True)
    res_thu = subprocess.run(cmd_thu, capture_output=True, text=True)
    return res_mon.returncode == 0 and res_thu.returncode == 0


def install_daily_schedule(time_str: str = "09:00") -> bool:
    """Устанавливает автоочистку: Каждый день в указанное время."""
    uninstall_all()
    cmd = [
        "schtasks", "/create", "/f",
        "/tn", TASK_DAILY,
        "/tr", f'"{PYTHONW_PATH}" "{SCRIPT_PATH}"',
        "/sc", "DAILY",
        "/st", time_str,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0


def uninstall_all() -> bool:
    """Удаляет все созданные задачи автоочистки AnyDesk из планировщика Windows."""
    for task in (TASK_MON, TASK_THU, TASK_DAILY):
        subprocess.run(["schtasks", "/delete", "/tn", task, "/f"], capture_output=True, text=True)
    return True


def get_schedule_status() -> dict:
    """Проверяет текущий статус задач в планировщике Windows."""
    res_mon = subprocess.run(["schtasks", "/query", "/tn", TASK_MON], capture_output=True, text=True)
    res_thu = subprocess.run(["schtasks", "/query", "/tn", TASK_THU], capture_output=True, text=True)
    res_daily = subprocess.run(["schtasks", "/query", "/tn", TASK_DAILY], capture_output=True, text=True)

    has_weekly = (res_mon.returncode == 0 and res_thu.returncode == 0)
    has_daily = (res_daily.returncode == 0)

    if has_weekly:
        mode = "weekly"
        desc = "Пн 09:00 и Чт 17:30"
    elif has_daily:
        mode = "daily"
        desc = "Каждый день в 09:00"
    else:
        mode = "disabled"
        desc = "Отключено"

    return {
        "enabled": has_weekly or has_daily,
        "mode": mode,
        "description": desc,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        if action == "weekly":
            success = install_weekly_schedule()
            print("Расписание (Пн 09:00, Чт 17:30) установлено:", success)
        elif action == "daily":
            success = install_daily_schedule()
            print("Расписание (Каждый день 09:00) установлено:", success)
        elif action == "uninstall":
            uninstall_all()
            print("Расписание удалено.")
        elif action == "status":
            print("Статус:", get_schedule_status())
    else:
        # По умолчанию включаем requested schedule (Пн 09:00, Чт 17:30)
        success = install_weekly_schedule()
        print("Автоочистка установлена (Пн 09:00 и Чт 17:30):", success)
