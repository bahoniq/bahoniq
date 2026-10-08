from pathlib import Path
from datetime import datetime
import shutil
import re
import sys
import compileall


# ============================================================
# BAHONIQ — PROJECT ORGANIZER
# ============================================================

ROOT = Path(__file__).resolve().parent
DESKTOP = ROOT.parent
BACKUP_ROOT = DESKTOP / "BahonIQ Backups"

TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_DIR = BACKUP_ROOT / f"Before_Reorganization_{TIMESTAMP}"


# ============================================================
# ФАЙЛЫ, КОТОРЫЕ ПЕРЕНОСИМ
# ============================================================

FILE_MAP = {
    "main_window.py": Path("app/main_window.py"),

    "anydesk_service.py": Path("services/anydesk_service.py"),
    "cleanup.py": Path("services/cleanup.py"),
    "duplicate_service.py": Path("services/duplicate_service.py"),
    "settings_service.py": Path("services/settings_service.py"),

    "duplicate_window.py": Path("modules/duplicate_window.py"),
    "notes.py": Path("modules/notes.py"),
    "pdf_center.py": Path("modules/pdf_center.py"),

    "rgb.py": Path("ui/rgb.py"),

    "install_launcher.py": Path("scripts/install_launcher.py"),
    "manage_bahoniq.py": Path("scripts/manage_bahoniq.py"),
}


# ============================================================
# ИМПОРТЫ
# ============================================================

IMPORT_REPLACEMENTS = {
    # UI
    "from rgb import": "from ui.rgb import",
    "import rgb": "import ui.rgb as rgb",

    # Services
    "from anydesk_service import": "from services.anydesk_service import",
    "import anydesk_service": "import services.anydesk_service as anydesk_service",

    "from cleanup import": "from services.cleanup import",
    "import cleanup": "import services.cleanup as cleanup",

    "from duplicate_service import": "from services.duplicate_service import",
    "import duplicate_service": "import services.duplicate_service as duplicate_service",

    "from settings_service import": "from services.settings_service import",
    "import settings_service": "import services.settings_service as settings_service",

    # Modules
    "from duplicate_window import": "from modules.duplicate_window import",
    "import duplicate_window": "import modules.duplicate_window as duplicate_window",

    "from notes import": "from modules.notes import",
    "import notes": "import modules.notes as notes",

    "from pdf_center import": "from modules.pdf_center import",
    "import pdf_center": "import modules.pdf_center as pdf_center",

    # App
    "from main_window import": "from app.main_window import",
    "import main_window": "import app.main_window as main_window",
}


# ============================================================
# СЛУЖЕБНЫЕ ФАЙЛЫ
# ============================================================

ROOT_FILES = [
    "main.py",
    "bootstrap.py",
    "config.py",
    "state.py",
]


# ============================================================
# СОЗДАНИЕ ПАПОК
# ============================================================

def create_directories():
    folders = [
        "app",
        "services",
        "modules",
        "ui",
        "scripts",
        "data",
        "data/logs",
        "data/cache",
        "data/settings",
        "backups",
    ]

    for folder in folders:
        path = ROOT / folder
        path.mkdir(parents=True, exist_ok=True)

    print("[OK] Папки созданы")


# ============================================================
# __init__.py
# ============================================================

def create_init_files():
    folders = [
        ROOT / "app",
        ROOT / "services",
        ROOT / "modules",
        ROOT / "ui",
        ROOT / "scripts",
    ]

    for folder in folders:
        init_file = folder / "__init__.py"

        if not init_file.exists():
            init_file.write_text(
                "# BahonIQ package\n",
                encoding="utf-8"
            )

    print("[OK] __init__.py созданы")


# ============================================================
# BACKUP
# ============================================================

def create_backup():
    print()
    print("Создаю полный backup...")
    print(f"Backup: {BACKUP_DIR}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Копируем только содержимое проекта.
    # Не копируем сам backup, если вдруг он находится внутри проекта.
    for item in ROOT.iterdir():

        if item.name == BACKUP_DIR.name:
            continue

        destination = BACKUP_DIR / item.name

        try:
            if item.is_dir():
                shutil.copytree(
                    item,
                    destination,
                    dirs_exist_ok=True
                )
            else:
                shutil.copy2(
                    item,
                    destination
                )

        except Exception as exc:
            print(
                f"[WARNING] Не удалось скопировать "
                f"{item.name}: {exc}"
            )

    print("[OK] Полный backup создан")


# ============================================================
# ПЕРЕНОС ФАЙЛОВ
# ============================================================

def move_files():
    print()
    print("Переношу Python-файлы...")

    for filename, relative_destination in FILE_MAP.items():

        source = ROOT / filename
        destination = ROOT / relative_destination

        if not source.exists():
            print(f"[SKIP] Не найден: {filename}")
            continue

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.move(
            str(source),
            str(destination)
        )

        print(
            f"[MOVE] {filename} -> "
            f"{relative_destination}"
        )

    print("[OK] Перенос завершён")


# ============================================================
# ИСПРАВЛЕНИЕ ИМПОРТОВ
# ============================================================

def fix_imports():
    print()
    print("Исправляю импорты...")

    python_files = list(ROOT.rglob("*.py"))

    for file_path in python_files:

        # Не трогаем сам организатор
        if file_path.resolve() == Path(__file__).resolve():
            continue

        try:
            text = file_path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        original = text

        for old, new in IMPORT_REPLACEMENTS.items():
            text = text.replace(
                old,
                new
            )

        if text != original:

            file_path.write_text(
                text,
                encoding="utf-8"
            )

            print(
                f"[FIX] {file_path.relative_to(ROOT)}"
            )

    print("[OK] Импорты обработаны")


# ============================================================
# ПРОВЕРКА PYTHON
# ============================================================

def validate_python():
    print()
    print("Проверяю Python-файлы...")

    result = compileall.compile_dir(
        str(ROOT),
        quiet=1,
        maxlevels=10
    )

    if result:
        print("[OK] Синтаксическая проверка пройдена")
        return True

    print("[ERROR] Обнаружены ошибки Python")
    return False


# ============================================================
# ПОКАЗ СТРУКТУРЫ
# ============================================================

def print_structure():
    print()
    print("=" * 65)
    print("НОВАЯ СТРУКТУРА BAHONIQ")
    print("=" * 65)

    folders = [
        "app",
        "services",
        "modules",
        "ui",
        "scripts",
        "data",
        "backups",
    ]

    for folder in folders:

        path = ROOT / folder

        print()
        print(f"[{folder}]")

        if not path.exists():
            continue

        for item in sorted(path.iterdir()):
            if item.name == "__pycache__":
                continue

            prefix = "    "

            if item.is_dir():
                print(
                    prefix + "[DIR]  " + item.name
                )
            else:
                print(
                    prefix + item.name
                )

    print()
    print("[ROOT]")

    for filename in ROOT_FILES:
        path = ROOT / filename

        if path.exists():
            print("    " + filename)

    print("=" * 65)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("BAHONIQ — PROJECT ORGANIZER")
    print("=" * 65)
    print()
    print("Текущий проект:")
    print(ROOT)
    print()
    print("Будет выполнено:")
    print("  1. Создание полного backup")
    print("  2. Создание структуры проекта")
    print("  3. Перенос Python-модулей")
    print("  4. Исправление импортов")
    print("  5. Проверка синтаксиса")
    print()

    answer = input(
        "Начать перестройку? [Y/N]: "
    ).strip().lower()

    if answer not in ("y", "yes", "д", "да"):

        print()
        print("Отменено.")
        return

    print()

    try:

        # 1
        create_backup()

        # 2
        create_directories()

        # 3
        create_init_files()

        # 4
        move_files()

        # 5
        fix_imports()

        # 6
        valid = validate_python()

        # 7
        print_structure()

        print()
        print("=" * 65)

        if valid:
            print("ГОТОВО")
            print()
            print(
                "Проект успешно перестроен."
            )
            print()
            print(
                "Backup находится здесь:"
            )
            print(BACKUP_DIR)
            print()
            print(
                "Теперь попробуй запустить BahonIQ."
            )
        else:
            print(
                "ВНИМАНИЕ: проверка обнаружила проблему."
            )
            print()
            print(
                "Старый проект сохранён в backup:"
            )
            print(BACKUP_DIR)

        print("=" * 65)

    except Exception as exc:

        print()
        print("=" * 65)
        print("ОШИБКА")
        print("=" * 65)
        print()
        print(exc)
        print()
        print(
            "ВАЖНО: backup уже был создан."
        )
        print(BACKUP_DIR)
        print()

    input(
        "\nНажмите Enter для выхода..."
    )


if __name__ == "__main__":
    main()