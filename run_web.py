# -*- coding: utf-8 -*-
"""Единая точка запуска веб-сервера BahonIQ с выводом UTF-8."""

import os
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def configure_console():
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except (AttributeError, OSError):
            pass
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def local_addresses():
    """Адреса текущего ПК без жёстко заданного IP и внешнего запроса."""
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        }
        return sorted(ip for ip in addresses if not ip.startswith(("127.", "169.254.")) and ip != "0.0.0.0")
    except OSError:
        return []


def main():
    configure_console()
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if not (PROJECT_ROOT / "web_app" / "server.py").is_file():
        print("Ошибка: помести run_web.py и run_web.bat в корень Work Center, рядом с папкой web_app.", flush=True)
        return 1
    try:
        import uvicorn
    except ImportError:
        print("Ошибка: Uvicorn не установлен в выбранном Python.")
        print(f'Установка: "{sys.executable}" -m pip install -r requirements_web.txt', flush=True)
        return 1

    print("=" * 60)
    print("BAHONIQ WORK CENTER — ВЕБ-СЕРВЕР")
    print("=" * 60)
    print("\n[1] На этом компьютере:")
    print("    http://localhost:8000")
    print("    http://127.0.0.1:8000")
    print("\n[2] Адреса компьютера для доступа из локальной сети:")
    addresses = local_addresses()
    if addresses:
        for address in addresses:
            print(f"    http://{address}:8000")
    else:
        print("    Не удалось определить адрес. Проверь IPv4 через ipconfig.")
    print("\nДокументация API: http://localhost:8000/docs")
    print("Сервер запускается. Готовность: Application startup complete.")
    print("Оставь это окно открытым. Остановка: Ctrl+C.")
    print("=" * 60, flush=True)

    try:
        uvicorn.run("web_app.server:app", host="0.0.0.0", port=8000, reload=False)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
