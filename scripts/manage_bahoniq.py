
import os
import sys
import shutil
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import messagebox


# ============================================================
# BAHONIQ — WORK CENTER
# BACKUP / RESTORE / CHECK / LAUNCH MANAGER
# ============================================================

APP_NAME = "BahonIQ — Work Center"

# Папка, где находится этот файл
APP_DIR = Path(__file__).resolve().parent

# Папка резервных копий
BACKUP_ROOT = APP_DIR.parent / "BahonIQ Backups"

# Максимальное количество backup
MAX_BACKUPS = 10

# Основные файлы проекта
REQUIRED_FILES = [
    "main.py",
    "bootstrap.py",
    "main_window.py",
    "config.py",
    "state.py",
    "rgb.py",
    "settings_service.py",
    "notes.py",
    "cleanup.py",
    "anydesk_service.py",
    "duplicate_window.py",
    "pdf_center.py",
    "launcher.pyw",
    "install_launcher.py",
]


# ============================================================
# СЛУЖЕБНЫЕ ФУНКЦИИ
# ============================================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nНажмите Enter для продолжения...")


def print_header(title):
    clear_screen()

    print("=" * 72)
    print("  BAHONIQ — WORK CENTER")
    print("  BACKUP MANAGER")
    print("=" * 72)
    print()
    print(f"  {title}")
    print("-" * 72)
    print()


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def ensure_backup_root():
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)


def is_backup_folder(path):
    return (
        path.is_dir()
        and path.name.startswith("Backup_")
    )


# ============================================================
# PYTHON 3.14
# ============================================================

def find_python_314():
    """
    Ищет Python 3.14.
    Возвращает путь к python.exe или None.
    """

    candidates = []

    # --------------------------------------------------------
    # Через py launcher
    # --------------------------------------------------------

    try:
        result = subprocess.run(
            [
                "py",
                "-3.14",
                "-c",
                "import sys; print(sys.executable)"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            path = result.stdout.strip()

            if path:
                candidate = Path(path)

                if candidate.exists():
                    candidates.append(candidate)

    except Exception:
        pass

    # --------------------------------------------------------
    # Стандартные места установки Python
    # --------------------------------------------------------

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        candidates.extend([
            Path(local_app_data)
            / "Programs"
            / "Python"
            / "Python314"
            / "python.exe",

            Path(local_app_data)
            / "Programs"
            / "Python"
            / "Python314"
            / "pythonw.exe",
        ])

    candidates.extend([
        Path("C:/Python314/python.exe"),
        Path("C:/Python314/pythonw.exe"),
        Path("C:/Program Files/Python314/python.exe"),
        Path("C:/Program Files/Python314/pythonw.exe"),
    ])

    # --------------------------------------------------------
    # Проверка
    # --------------------------------------------------------

    checked = set()

    for candidate in candidates:

        try:
            candidate = candidate.resolve()
        except Exception:
            continue

        if str(candidate).lower() in checked:
            continue

        checked.add(str(candidate).lower())

        if candidate.exists() and candidate.name.lower() == "python.exe":
            return candidate

    return None


def find_pythonw_314():
    """
    Находит pythonw.exe рядом с Python 3.14.
    """

    python_exe = find_python_314()

    if not python_exe:
        return None

    pythonw = python_exe.with_name("pythonw.exe")

    if pythonw.exists():
        return pythonw

    return None


# ============================================================
# BACKUP
# ============================================================

def create_backup(label=None):
    """
    Создаёт полную резервную копию папки Work center.
    """

    ensure_backup_root()

    timestamp = get_timestamp()

    if label:
        folder_name = f"Backup_{timestamp}_{label}"
    else:
        folder_name = f"Backup_{timestamp}"

    backup_dir = BACKUP_ROOT / folder_name

    print(f"Создание backup:")
    print()
    print(f"Источник:")
    print(APP_DIR)
    print()
    print(f"Назначение:")
    print(backup_dir)
    print()

    try:

        ignore = shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "BahonIQ_error.log",
            "BahonIQ_launcher_error.log",
        )

        shutil.copytree(
            APP_DIR,
            backup_dir,
            ignore=ignore
        )

        print()
        print("✓ BACKUP СОЗДАН")
        print()
        print(f"Папка:")
        print(backup_dir)

        cleanup_old_backups()

        return backup_dir

    except Exception as e:

        print()
        print("✗ ОШИБКА СОЗДАНИЯ BACKUP")
        print()
        print(str(e))

        return None


def cleanup_old_backups():
    """
    Оставляет только последние MAX_BACKUPS backup.
    """

    ensure_backup_root()

    backups = [
        item
        for item in BACKUP_ROOT.iterdir()
        if is_backup_folder(item)
    ]

    backups.sort(
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    old_backups = backups[MAX_BACKUPS:]

    for backup in old_backups:

        try:
            shutil.rmtree(backup)

            print(
                f"Удалён старый backup: "
                f"{backup.name}"
            )

        except Exception as e:

            print(
                f"Не удалось удалить "
                f"{backup.name}: {e}"
            )


def get_backups():
    """
    Возвращает список backup от новых к старым.
    """

    ensure_backup_root()

    backups = [
        item
        for item in BACKUP_ROOT.iterdir()
        if is_backup_folder(item)
    ]

    backups.sort(
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return backups


def show_backups():
    print_header("СПИСОК РЕЗЕРВНЫХ КОПИЙ")

    backups = get_backups()

    if not backups:
        print("Резервных копий пока нет.")
        pause()
        return

    print(
        f"Найдено backup: {len(backups)}"
    )
    print()

    for index, backup in enumerate(backups, start=1):

        try:
            size = get_folder_size(backup)

            modified = datetime.fromtimestamp(
                backup.stat().st_mtime
            ).strftime(
                "%d.%m.%Y %H:%M:%S"
            )

            print(
                f"{index:2}. "
                f"{backup.name}"
            )

            print(
                f"     Дата: {modified}"
            )

            print(
                f"     Размер: {format_size(size)}"
            )

            print()

        except Exception:
            print(
                f"{index:2}. {backup.name}"
            )
            print()

    pause()


def get_folder_size(folder):
    total = 0

    for root, dirs, files in os.walk(folder):

        for filename in files:

            try:
                path = Path(root) / filename
                total += path.stat().st_size
            except Exception:
                pass

    return total


def format_size(size):
    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"

    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"

    return f"{size / (1024 ** 3):.2f} GB"


# ============================================================
# RESTORE
# ============================================================

def restore_backup():
    print_header("ВОССТАНОВЛЕНИЕ BACKUP")

    backups = get_backups()

    if not backups:

        print("Backup не найден.")
        print()
        print(
            "Сначала создайте резервную копию."
        )

        pause()
        return

    print("Доступные резервные копии:")
    print()

    for index, backup in enumerate(
        backups,
        start=1
    ):

        try:
            modified = datetime.fromtimestamp(
                backup.stat().st_mtime
            ).strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        except Exception:
            modified = "неизвестно"

        print(
            f"{index}. "
            f"{backup.name}"
        )

        print(
            f"   {modified}"
        )

        print()

    print("0. Отмена")
    print()

    choice = input(
        "Выберите номер backup: "
    ).strip()

    if choice == "0":
        return

    try:
        index = int(choice) - 1

        if index < 0 or index >= len(backups):
            raise ValueError

    except ValueError:

        print()
        print("Неверный номер.")

        pause()
        return

    selected_backup = backups[index]

    print()
    print(
        "Вы выбрали:"
    )
    print(
        selected_backup
    )
    print()

    confirm = input(
        "Перед восстановлением будет "
        "создан аварийный backup текущей версии.\n"
        "Продолжить? (Y/N): "
    ).strip().lower()

    if confirm not in (
        "y",
        "yes",
        "д",
        "да",
    ):
        print()
        print("Восстановление отменено.")
        pause()
        return

    # --------------------------------------------------------
    # Аварийная копия текущего состояния
    # --------------------------------------------------------

    print()
    print(
        "Создание аварийной копии "
        "текущего состояния..."
    )
    print()

    emergency_backup = create_backup(
        label="BeforeRestore"
    )

    if emergency_backup is None:

        print()
        print(
            "ОШИБКА: аварийный backup "
            "создать не удалось."
        )

        print()
        print(
            "Восстановление остановлено "
            "для безопасности."
        )

        pause()
        return

    print()
    print(
        "✓ Аварийный backup создан."
    )

    # --------------------------------------------------------
    # Восстановление
    # --------------------------------------------------------

    print()
    print(
        "Начинается восстановление..."
    )
    print()

    try:

        ignored_names = {
            "__pycache__",
            "BahonIQ_error.log",
            "BahonIQ_launcher_error.log",
        }

        for item in selected_backup.iterdir():

            if item.name in ignored_names:
                continue

            destination = APP_DIR / item.name

            if item.is_dir():

                if destination.exists():

                    shutil.rmtree(
                        destination
                    )

                shutil.copytree(
                    item,
                    destination
                )

            else:

                shutil.copy2(
                    item,
                    destination
                )

        print()
        print("=" * 72)
        print("✓ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
        print("=" * 72)
        print()

        print(
            "Теперь можно запустить BahonIQ."
        )

    except Exception as e:

        print()
        print("=" * 72)
        print("✗ ОШИБКА ВОССТАНОВЛЕНИЯ")
        print("=" * 72)
        print()

        print(str(e))

        print()
        print(
            "Аварийный backup находится здесь:"
        )

        print(
            emergency_backup
        )

    pause()


# ============================================================
# CHECK FILES
# ============================================================

def check_files():
    print_header("ПРОВЕРКА ФАЙЛОВ BAHONIQ")

    print(
        f"Папка проекта:\n{APP_DIR}"
    )

    print()

    missing = []
    present = []

    for filename in REQUIRED_FILES:

        path = APP_DIR / filename

        if path.exists():

            present.append(filename)

            print(
                f"✓ {filename}"
            )

        else:

            missing.append(filename)

            print(
                f"✗ {filename} — НЕ НАЙДЕН"
            )

    print()
    print("-" * 72)
    print()

    print(
        f"Найдено: {len(present)}"
    )

    print(
        f"Отсутствует: {len(missing)}"
    )

    print()

    if missing:

        print(
            "ВНИМАНИЕ: отсутствуют файлы:"
        )

        for filename in missing:
            print(
                f"  - {filename}"
            )

    else:

        print(
            "✓ Все основные файлы на месте."
        )

    print()
    print("-" * 72)
    print()

    python = find_python_314()

    if python:

        print(
            "✓ Python 3.14 найден:"
        )

        print(
            python
        )

    else:

        print(
            "✗ Python 3.14 НЕ НАЙДЕН"
        )

    pythonw = find_pythonw_314()

    print()

    if pythonw:

        print(
            "✓ pythonw.exe найден:"
        )

        print(
            pythonw
        )

    else:

        print(
            "✗ pythonw.exe НЕ НАЙДЕН"
        )

    print()
    pause()


# ============================================================
# LAUNCH BAHONIQ
# ============================================================

def run_bahoniq():
    print_header("ЗАПУСК BAHONIQ")

    pythonw = find_pythonw_314()

    if not pythonw:

        print(
            "✗ Python 3.14 / pythonw.exe "
            "не найден."
        )

        print()
        print(
            "Проверьте установку Python 3.14."
        )

        pause()
        return

    launcher = APP_DIR / "launcher.pyw"

    if not launcher.exists():

        print(
            "✗ launcher.pyw не найден."
        )

        pause()
        return

    print(
        "Python 3.14:"
    )

    print(
        pythonw
    )

    print()

    print(
        "Launcher:"
    )

    print(
        launcher
    )

    print()

    try:

        startupinfo = None

        if os.name == "nt":

            startupinfo = subprocess.STARTUPINFO()

            startupinfo.dwFlags |= (
                subprocess.STARTF_USESHOWWINDOW
            )

        subprocess.Popen(
            [
                str(pythonw),
                str(launcher)
            ],
            cwd=str(APP_DIR),
            startupinfo=startupinfo,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        print()
        print(
            "✓ BahonIQ запущен."
        )

        print()
        print(
            "Окно менеджера можно закрыть."
        )

    except Exception as e:

        print()
        print(
            "✗ Не удалось запустить BahonIQ."
        )

        print()
        print(str(e))

    pause()


# ============================================================
# QUICK BACKUP
# ============================================================

def quick_backup():
    print_header("СОЗДАНИЕ BACKUP")

    backup = create_backup()

    print()

    if backup:

        print(
            "✓ Всё готово."
        )

    else:

        print(
            "✗ Backup не создан."
        )

    pause()


# ============================================================
# ПОЛУЧЕНИЕ СТАТУСА
# ============================================================

def show_status():
    print_header("СТАТУС BAHONIQ")

    print(
        f"Папка программы:"
    )

    print(
        APP_DIR
    )

    print()

    backups = get_backups()

    print(
        f"Количество backup: "
        f"{len(backups)}"
    )

    print()

    python = find_python_314()

    if python:
        print(
            "✓ Python 3.14"
        )
        print(
            f"  {python}"
        )
    else:
        print(
            "✗ Python 3.14 не найден"
        )

    print()

    launcher = APP_DIR / "launcher.pyw"

    if launcher.exists():
        print(
            "✓ launcher.pyw"
        )
    else:
        print(
            "✗ launcher.pyw отсутствует"
        )

    print()

    main_file = APP_DIR / "main.py"

    if main_file.exists():
        print(
            "✓ main.py"
        )
    else:
        print(
            "✗ main.py отсутствует"
        )

    print()

    pause()


# ============================================================
# MENU
# ============================================================

def menu():
    while True:

        print_header(
            "ГЛАВНОЕ МЕНЮ"
        )

        print(
            "  1. Создать backup"
        )

        print(
            "  2. Показать backup"
        )

        print(
            "  3. Восстановить backup"
        )

        print(
            "  4. Проверить файлы"
        )

        print(
            "  5. Запустить BahonIQ"
        )

        print(
            "  6. Статус системы"
        )

        print()

        print(
            "  0. Выход"
        )

        print()
        print("-" * 72)
        print()

        choice = input(
            "Выберите действие: "
        ).strip()

        if choice == "1":

            quick_backup()

        elif choice == "2":

            show_backups()

        elif choice == "3":

            restore_backup()

        elif choice == "4":

            check_files()

        elif choice == "5":

            run_bahoniq()

        elif choice == "6":

            show_status()

        elif choice == "0":

            print()
            print(
                "BahonIQ Backup Manager завершён."
            )

            break

        else:

            print()
            print(
                "Неверный пункт меню."
            )

            pause()


# ============================================================
# ERROR HANDLER
# ============================================================

def save_error():

    try:

        error_file = (
            APP_DIR
            / "BahonIQ_manager_error.log"
        )

        with open(
            error_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "=== BAHONIQ BACKUP MANAGER ERROR ===\n\n"
            )

            f.write(
                f"Дата: "
                f"{datetime.now()}\n\n"
            )

            traceback.print_exc(
                file=f
            )

        return error_file

    except Exception:

        return None


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        os.chdir(APP_DIR)

        menu()

    except KeyboardInterrupt:

        print()
        print()
        print(
            "Операция отменена."
        )

    except BaseException as e:

        error_file = save_error()

        print()
        print("=" * 72)
        print("ОШИБКА BACKUP MANAGER")
        print("=" * 72)
        print()

        print(
            str(e)
        )

        print()

        if error_file:

            print(
                "Подробный лог:"
            )

            print(
                error_file
            )

        print()

        input(
            "Нажмите Enter для выхода..."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()