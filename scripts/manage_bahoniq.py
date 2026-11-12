
import os
import sys
import shutil
import hashlib
import json
import tempfile
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
MAX_BACKUPS = None  # None = не удалять старые копии автоматически

SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_root():
    """Ищет корень Work center по основным файлам проекта."""
    for parent in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (parent / "main.py").is_file():
            return parent

    # Если main.py не найден, используем папку скрипта.
    return SCRIPT_DIR


APP_DIR = find_project_root()
BACKUP_ROOT = APP_DIR / "BahonIQ Backups"

BACKUP_PREFIX = "Backup_"

IGNORED_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "BahonIQ Backups",
}

IGNORED_FILES = {
    "BahonIQ_error.log",
    "BahonIQ_launcher_error.log",
    "BahonIQ_manager_error.log",
}

REQUIRED_PATHS = [
    "main.py",
    "bootstrap.py",
    "launcher.pyw",
    "app/main_window.py",
    "modules",
    "services",
]


# ============================================================
# СЛУЖЕБНЫЕ ФУНКЦИИ
# ============================================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    try:
        input("\nНажмите Enter для продолжения...")
    except (EOFError, KeyboardInterrupt):
        pass


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
    """Распознаёт только папки резервных копий."""
    try:
        return (
            path.is_dir()
            and path.name.startswith(BACKUP_PREFIX)
            and path.resolve().parent == BACKUP_ROOT.resolve()
        )
    except OSError:
        return False


def is_yes(value):
    return value.strip().lower() in {
        "y", "yes", "д", "да"
    }


def ignore_project_item(directory, names):
    """
    Функция исключения для shutil.copytree().
    Не копирует резервные копии внутрь самих себя.
    """
    ignored = set()

    for name in names:
        if name in IGNORED_NAMES:
            ignored.add(name)
        elif name in IGNORED_FILES:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.add(name)

    return ignored


def get_folder_size(folder):
    total = 0

    for root, dirs, files in os.walk(folder):
        dirs[:] = [
            name for name in dirs
            if name not in IGNORED_NAMES
        ]

        for filename in files:
            try:
                total += (Path(root) / filename).stat().st_size
            except OSError:
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
# PYTHON 3.14
# ============================================================

def find_python_314():
    """Ищет python.exe версии 3.14."""

    candidates = []

    try:
        result = subprocess.run(
            [
                "py", "-3.14", "-c",
                "import sys; print(sys.executable)"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            candidates.append(Path(result.stdout.strip()))

    except (OSError, subprocess.SubprocessError):
        pass

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        candidates.append(
            Path(local_app_data)
            / "Programs" / "Python"
            / "Python314" / "python.exe"
        )

    candidates.extend([
        Path("C:/Python314/python.exe"),
        Path("C:/Program Files/Python314/python.exe"),
    ])

    seen = set()

    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            key = str(candidate).lower()

            if key in seen:
                continue
            seen.add(key)

            if not candidate.is_file():
                continue

            result = subprocess.run(
                [
                    str(candidate), "-c",
                    "import sys; print(sys.version_info[:2])"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and "(3, 14)" in result.stdout:
                return candidate

        except (OSError, subprocess.SubprocessError):
            continue

    return None


def find_pythonw_314():
    python_exe = find_python_314()

    if not python_exe:
        return None

    pythonw = python_exe.with_name("pythonw.exe")

    return pythonw if pythonw.is_file() else None


# ============================================================
# BACKUP
# ============================================================

def _manifest(folder):
    """Контрольные суммы всех файлов резервной копии."""
    result = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in IGNORED_NAMES and not (Path(root) / d).is_symlink()]
        for filename in files:
            path = Path(root) / filename
            if path.is_symlink() or filename == ".bahoniq_manifest.json":
                continue
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            result[path.relative_to(folder).as_posix()] = digest.hexdigest()
    return result


def verify_backup(folder):
    manifest_file = Path(folder) / ".bahoniq_manifest.json"
    if not manifest_file.is_file():
        return (Path(folder) / "main.py").is_file()  # Старые копии без манифеста.
    try:
        expected = json.loads(manifest_file.read_text(encoding="utf-8"))
        return expected == _manifest(Path(folder)) and "main.py" in expected
    except (OSError, ValueError):
        return False


def create_backup(label=None):
    """Создаёт проверенную копию, не публикуя незавершённую."""
    staging = None
    try:
        ensure_backup_root()
        if not (APP_DIR / "main.py").is_file():
            print("ОШИБКА: main.py не найден.")
            return None
        timestamp = get_timestamp()
        safe_label = "" if not label else "_" + "".join(c for c in str(label) if c.isalnum() or c in "_- ").strip()
        base = f"{BACKUP_PREFIX}{timestamp}{safe_label}"
        destination = BACKUP_ROOT / base
        counter = 2
        while destination.exists():
            destination = BACKUP_ROOT / f"{base}_{counter}"
            counter += 1
        staging = Path(tempfile.mkdtemp(prefix=".creating_", dir=BACKUP_ROOT))
        shutil.copytree(APP_DIR, staging, dirs_exist_ok=True, ignore=ignore_project_item)
        manifest = _manifest(staging)
        (staging / ".bahoniq_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not verify_backup(staging):
            raise RuntimeError("Проверка контрольных сумм не пройдена")
        staging.rename(destination)
        staging = None
        print(f"✓ Резервная копия проверена: {destination}")
        return destination
    except Exception as error:
        print(f"✗ Не удалось создать резервную копию: {error}")
        return None
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def get_backups():
    """Возвращает список резервных копий от новых к старым."""

    ensure_backup_root()

    backups = [
        item for item in BACKUP_ROOT.iterdir()
        if is_backup_folder(item)
    ]

    backups.sort(
        key=lambda item: item.stat().st_mtime,
        reverse=True
    )

    return backups


def show_backups():
    print_header("СПИСОК РЕЗЕРВНЫХ КОПИЙ")

    try:
        backups = get_backups()
    except OSError as error:
        print(f"Не удалось прочитать каталог копий: {error}")
        pause()
        return

    print(f"Папка копий:\n{BACKUP_ROOT}\n")

    if not backups:
        print("Резервных копий пока нет.")
        pause()
        return

    print(f"Найдено копий: {len(backups)}\n")

    for index, backup in enumerate(backups, start=1):
        try:
            modified = datetime.fromtimestamp(
                backup.stat().st_mtime
            ).strftime("%d.%m.%Y %H:%M:%S")

            size = format_size(get_folder_size(backup))

            print(f"{index}. {backup.name}")
            print(f"   Дата: {modified}")
            print(f"   Размер: {size}\n")

        except OSError:
            print(f"{index}. {backup.name}\n")

    pause()


# ============================================================
# RESTORE
# ============================================================

def restore_backup():
    """
    Восстанавливает файлы из выбранной копии.

    Важно: файлы из копии перезаписывают совпадающие файлы проекта.
    Дополнительные файлы, которых нет в копии, автоматически
    не удаляются. Это сделано для защиты от случайной потери данных.
    """

    print_header("ВОССТАНОВЛЕНИЕ РЕЗЕРВНОЙ КОПИИ")

    try:
        backups = get_backups()
    except OSError as error:
        print(f"Ошибка чтения списка копий: {error}")
        pause()
        return

    if not backups:
        print("Резервные копии не найдены.")
        pause()
        return

    for index, backup in enumerate(backups, start=1):
        modified = datetime.fromtimestamp(
            backup.stat().st_mtime
        ).strftime("%d.%m.%Y %H:%M:%S")

        print(f"{index}. {backup.name} — {modified}")

    print("\n0. Отмена\n")

    choice = input("Выберите номер копии: ").strip()

    if choice == "0":
        return

    try:
        index = int(choice) - 1
        if index < 0 or index >= len(backups):
            raise ValueError
    except ValueError:
        print("Неверный номер.")
        pause()
        return

    selected_backup = backups[index]

    # Проверяем, что выбранная копия действительно принадлежит менеджеру.
    if not is_backup_folder(selected_backup):
        print("ОШИБКА: выбранная папка не распознана как резервная копия.")
        pause()
        return

    if not verify_backup(selected_backup):
        print("ОШИБКА: резервная копия повреждена или отсутствует main.py.")
        print("Восстановление отменено.")
        pause()
        return

    print()
    print(f"Выбрана копия:\n{selected_backup}")
    print()
    print("Перед восстановлением будет создана аварийная копия.")
    print("Совпадающие файлы проекта будут перезаписаны.")
    print("Дополнительные файлы проекта автоматически не удаляются.")
    print()

    confirm = input("Продолжить? (Y/N): ")

    if not is_yes(confirm):
        print("Восстановление отменено.")
        pause()
        return

    print("\nСоздание аварийной копии текущего проекта...\n")

    emergency_backup = create_backup(label="BeforeRestore")

    if emergency_backup is None:
        print("\nАварийная копия не создана. Восстановление остановлено.")
        pause()
        return

    print("\nАварийная копия создана.")
    print("Начинается восстановление...\n")

    try:
        # Защита от попытки восстановить папку в саму себя.
        if selected_backup.resolve().parent != BACKUP_ROOT.resolve():
            raise RuntimeError("Путь резервной копии не прошёл проверку.")

        for item in selected_backup.iterdir():
            if item.name in IGNORED_NAMES or item.name in IGNORED_FILES or item.name == ".bahoniq_manifest.json" or item.is_symlink():
                continue

            destination = APP_DIR / item.name

            # Каталог резервных копий не должен изменяться восстановлением.
            if destination.resolve() == BACKUP_ROOT.resolve():
                continue

            if item.is_dir():
                if destination.exists() and not destination.is_dir():
                    raise RuntimeError(
                        f"Невозможно заменить файл папкой: {destination}"
                    )

                shutil.copytree(
                    item,
                    destination,
                    dirs_exist_ok=True,
                    ignore=ignore_project_item
                )

            elif item.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

        print("\n" + "=" * 72)
        print("ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
        print("=" * 72)
        print("\nСовпадающие файлы восстановлены из выбранной копии.")
        print("Дополнительные файлы проекта не удалялись.")
        print(f"\nАварийная копия: {emergency_backup}")

    except Exception as error:
        print("\nОШИБКА ВОССТАНОВЛЕНИЯ")
        print(str(error))
        print("\nАварийная копия текущего состояния:")
        print(emergency_backup)
        print("\nНе удаляйте аварийную копию.")

    pause()


# ============================================================
# CHECK FILES
# ============================================================

def check_files():
    print_header("ПРОВЕРКА ФАЙЛОВ BAHONIQ")

    print(f"Папка проекта:\n{APP_DIR}\n")
    print(f"Папка резервных копий:\n{BACKUP_ROOT}\n")

    missing = []
    present = []

    for relative_path in REQUIRED_PATHS:
        path = APP_DIR / relative_path

        if path.exists():
            present.append(relative_path)
            print(f"✓ {relative_path}")
        else:
            missing.append(relative_path)
            print(f"✗ {relative_path} — НЕ НАЙДЕН")

    print("\n" + "-" * 72)
    print(f"Найдено: {len(present)}")
    print(f"Отсутствует: {len(missing)}")

    if missing:
        print("\nВНИМАНИЕ: проверьте отсутствующие пути.")
    else:
        print("\n✓ Все проверяемые основные пути найдены.")

    print("\n" + "-" * 72)

    python = find_python_314()
    pythonw = find_pythonw_314()

    if python:
        print(f"\n✓ Python 3.14: {python}")
    else:
        print("\n✗ Python 3.14 не найден")

    if pythonw:
        print(f"✓ pythonw.exe: {pythonw}")
    else:
        print("✗ pythonw.exe не найден")

    pause()


# ============================================================
# LAUNCH BAHONIQ
# ============================================================

def run_bahoniq():
    print_header("ЗАПУСК BAHONIQ")

    pythonw = find_pythonw_314()

    if not pythonw:
        print("Python 3.14 или pythonw.exe не найден.")
        pause()
        return

    launcher = APP_DIR / "launcher.pyw"

    if not launcher.is_file():
        print(f"Файл запуска не найден:\n{launcher}")
        pause()
        return

    print(f"Python: {pythonw}")
    print(f"Launcher: {launcher}\n")

    try:
        startupinfo = None
        creationflags = 0

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        subprocess.Popen(
            [str(pythonw), str(launcher)],
            cwd=str(APP_DIR),
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        print("✓ Команда запуска передана Windows.")

    except Exception as error:
        print("✗ Не удалось запустить BahonIQ.")
        print(str(error))

    pause()


# ============================================================
# QUICK BACKUP
# ============================================================

def quick_backup():
    print_header("СОЗДАНИЕ РЕЗЕРВНОЙ КОПИИ")

    backup = create_backup()

    if backup:
        print("\n✓ Всё готово.")
    else:
        print("\n✗ Копия не создана. Смотрите сообщение об ошибке выше.")

    pause()


# ============================================================
# STATUS
# ============================================================

def show_status():
    print_header("СТАТУС BAHONIQ")

    print(f"Папка проекта:\n{APP_DIR}\n")
    print(f"Папка резервных копий:\n{BACKUP_ROOT}\n")

    try:
        backups = get_backups()
        print(f"Количество резервных копий: {len(backups)}")
        if backups:
            print(f"Последняя копия: {backups[0].name}")
    except OSError as error:
        print(f"Не удалось прочитать список копий: {error}")

    python = find_python_314()

    if python:
        print(f"\n✓ Python 3.14: {python}")
    else:
        print("\n✗ Python 3.14 не найден")

    launcher = APP_DIR / "launcher.pyw"
    main_file = APP_DIR / "main.py"

    print("\n✓ launcher.pyw найден" if launcher.is_file()
          else "\n✗ launcher.pyw отсутствует")

    print("✓ main.py найден" if main_file.is_file()
          else "✗ main.py отсутствует")

    pause()


# ============================================================
# ERROR HANDLER
# ============================================================

def save_error():
    try:
        error_file = APP_DIR / "BahonIQ_manager_error.log"

        with error_file.open("a", encoding="utf-8") as file:
            file.write("\n\n=== BAHONIQ BACKUP MANAGER ERROR ===\n")
            file.write(f"Дата: {datetime.now()}\n\n")
            traceback.print_exc(file=file)

        return error_file

    except Exception:
        return None


# ============================================================
# MENU
# ============================================================

def menu():
    while True:
        print_header("ГЛАВНОЕ МЕНЮ")

        print("  1. Создать резервную копию")
        print("  2. Показать резервные копии")
        print("  3. Восстановить резервную копию")
        print("  4. Проверить файлы")
        print("  5. Запустить BahonIQ")
        print("  6. Статус системы")
        print()
        print("  0. Выход")
        print("\n" + "-" * 72 + "\n")

        choice = input("Выберите действие: ").strip()

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
            print("\nBahonIQ Backup Manager завершён.")
            break
        else:
            print("\nНеверный пункт меню.")
            pause()


# ============================================================
# MAIN
# ============================================================

def main():
    try:
        os.chdir(APP_DIR)

        print(f"Корень проекта: {APP_DIR}")
        print(f"Резервные копии: {BACKUP_ROOT}")

        menu()

    except (KeyboardInterrupt, EOFError):
        print("\nРабота Backup Manager остановлена.")

    except BaseException:
        error_file = save_error()

        print("\n" + "=" * 72)
        print("ОШИБКА BACKUP MANAGER")
        print("=" * 72)

        if error_file:
            print(f"\nПодробный журнал:\n{error_file}")
        else:
            traceback.print_exc()

        try:
            input("\nНажмите Enter для выхода...")
        except (EOFError, KeyboardInterrupt):
            pass


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
