import os
import sys
import subprocess
from pathlib import Path


# ============================================================
# BAHONIQ — INSTALL LAUNCHER
# Python 3.14
# ============================================================

APP_NAME = "BahonIQ — Work Center"

BASE_DIR = Path(__file__).resolve().parent
LAUNCHER = BASE_DIR / "launcher.pyw"
ICON = BASE_DIR / "BahonIQ.ico"

DESKTOP = Path.home() / "Desktop"

STARTUP = (
    Path(os.environ["APPDATA"])
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)


# ============================================================
# FIND PYTHON 3.14
# ============================================================

def find_python_314():

    candidates = []

    # --------------------------------------------------------
    # 1. Python Launcher for Windows
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
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode == 0:

            path = result.stdout.strip()

            if path and Path(path).exists():
                candidates.append(Path(path))

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. Standard installation locations
    # --------------------------------------------------------

    user = Path.home()

    candidates.extend([
        user / "AppData" / "Local" / "Programs" / "Python" / "Python314" / "python.exe",
        Path("C:/Python314/python.exe"),
        Path("C:/Program Files/Python314/python.exe"),
        Path("C:/Program Files (x86)/Python314/python.exe"),
    ])


    # --------------------------------------------------------
    # Check candidates
    # --------------------------------------------------------

    for python_exe in candidates:

        if not python_exe.exists():
            continue

        try:

            result = subprocess.run(
                [
                    str(python_exe),
                    "-c",
                    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            version = result.stdout.strip()

            if version == "3.14":
                return python_exe

        except Exception:
            continue


    return None


# ============================================================
# CREATE SHORTCUT
# ============================================================

def create_shortcut(
    shortcut_path,
    pythonw,
    launcher,
    working_directory,
    icon_path
):

    shortcut_path = Path(shortcut_path)

    # PowerShell-safe strings
    def ps_escape(value):
        return str(value).replace("'", "''")


    target = ps_escape(pythonw)
    arguments = ps_escape(launcher)
    workdir = ps_escape(working_directory)
    shortcut = ps_escape(shortcut_path)

    if icon_path and Path(icon_path).exists():
        icon = ps_escape(icon_path)
    else:
        icon = target


    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell

$Shortcut = $WshShell.CreateShortcut('{shortcut}')

$Shortcut.TargetPath = '{target}'
$Shortcut.Arguments = '"{arguments}"'
$Shortcut.WorkingDirectory = '{workdir}'
$Shortcut.IconLocation = '{icon}'

$Shortcut.Description = 'BahonIQ — Work Center'
$Shortcut.WindowStyle = 1

$Shortcut.Save()
"""


    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


# ============================================================
# REMOVE OLD BAHONIQ SHORTCUT
# ============================================================

def remove_old_shortcut(folder):

    folder = Path(folder)

    if not folder.exists():
        return

    names = [
        "BahonIQ.lnk",
        "BahonIQ — Work Center.lnk",
        "BahonIQ - Work Center.lnk",
        "BahonIQ Work Center.lnk",
    ]

    for name in names:

        file = folder / name

        try:

            if file.exists():
                file.unlink()

        except Exception:
            pass


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 65)
    print("       BAHONIQ — WORK CENTER")
    print("       УСТАНОВКА ЗАПУСКА")
    print("=" * 65)
    print()

    print("Папка BahonIQ:")
    print(BASE_DIR)
    print()

    # --------------------------------------------------------
    # Check launcher
    # --------------------------------------------------------

    if not LAUNCHER.exists():

        print("ОШИБКА:")
        print("Не найден launcher.pyw")
        print()
        print("Положи install_launcher.py рядом с launcher.pyw")
        input("\nНажмите ENTER...")
        return


    # --------------------------------------------------------
    # Find Python 3.14
    # --------------------------------------------------------

    print("Поиск Python 3.14...")

    python_exe = find_python_314()

    if python_exe is None:

        print()
        print("=" * 65)
        print("ОШИБКА: Python 3.14 НЕ НАЙДЕН")
        print("=" * 65)
        print()
        print("Установщик специально НЕ будет использовать")
        print("Python 3.13, 3.12 или другую версию.")
        print()
        input("Нажмите ENTER...")
        return


    print("Python 3.14 найден:")
    print(python_exe)
    print()


    # --------------------------------------------------------
    # pythonw.exe
    # --------------------------------------------------------

    pythonw = python_exe.with_name("pythonw.exe")


    if not pythonw.exists():

        print("ОШИБКА: не найден pythonw.exe")
        print(pythonw)
        print()

        input("Нажмите ENTER...")
        return


    print("Используется:")
    print(pythonw)
    print()


    # --------------------------------------------------------
    # Create directories
    # --------------------------------------------------------

    DESKTOP.mkdir(
        parents=True,
        exist_ok=True
    )

    STARTUP.mkdir(
        parents=True,
        exist_ok=True
    )


    # --------------------------------------------------------
    # Remove only old BahonIQ shortcuts
    # --------------------------------------------------------

    print("Проверка старых ярлыков...")

    remove_old_shortcut(DESKTOP)
    remove_old_shortcut(STARTUP)


    # --------------------------------------------------------
    # Shortcut paths
    # --------------------------------------------------------

    desktop_shortcut = (
        DESKTOP / "BahonIQ — Work Center.lnk"
    )

    startup_shortcut = (
        STARTUP / "BahonIQ — Work Center.lnk"
    )


    # --------------------------------------------------------
    # Create desktop shortcut
    # --------------------------------------------------------

    print("Создание ярлыка на рабочем столе...")

    create_shortcut(
        desktop_shortcut,
        pythonw,
        LAUNCHER,
        BASE_DIR,
        ICON
    )


    # --------------------------------------------------------
    # Create startup shortcut
    # --------------------------------------------------------

    print("Добавление BahonIQ в автозагрузку...")

    create_shortcut(
        startup_shortcut,
        pythonw,
        LAUNCHER,
        BASE_DIR,
        ICON
    )


    # --------------------------------------------------------
    # Done
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("ГОТОВО!")
    print("=" * 65)
    print()

    print("Python:")
    print(python_exe)
    print()

    print("Запускатель:")
    print(LAUNCHER)
    print()

    print("Ярлык рабочего стола:")
    print(desktop_shortcut)
    print()

    print("Автозагрузка:")
    print(startup_shortcut)
    print()

    if ICON.exists():
        print("Иконка:")
        print(ICON)
    else:
        print("ВНИМАНИЕ:")
        print("BahonIQ.ico пока не найден.")
        print("Ярлык будет использовать стандартную иконку Python.")
        print()

    print()
    print("Теперь BahonIQ запускается:")
    print()
    print("Рабочий стол → BahonIQ → Python 3.14 → BahonIQ")
    print()
    print("Windows → Автозагрузка → BahonIQ → Python 3.14 → BahonIQ")
    print()
    print("CMD при запуске приложения НЕ используется.")
    print()

    input("Нажмите ENTER для закрытия...")


if __name__ == "__main__":
    main()