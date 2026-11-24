# -*- coding: utf-8 -*-
"""Прототип десктопного окна BahonIQ на базе web_app + pywebview (Edge WebView2)."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview

PROJECT_ROOT = Path(__file__).resolve().parent


def _pick_free_port(preferred: int = 8010) -> int:
    """Возвращает preferred, если он свободен, иначе любой свободный локальный порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Ждёт, пока локальный сервер начнёт принимать подключения."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main() -> int:
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    port = _pick_free_port(8010)
    config = uvicorn.Config(
        "web_app.server:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_for_port(port):
        print("Не удалось дождаться запуска локального сервера web_app.")
        server.should_exit = True
        return 1

    webview.settings["ALLOW_DOWNLOADS"] = True

    storage_dir = PROJECT_ROOT / "data" / "desktop_webview"
    storage_dir.mkdir(parents=True, exist_ok=True)

    webview.create_window(
        "BahonIQ Work Center",
        f"http://127.0.0.1:{port}",
        width=1360,
        height=860,
        min_size=(960, 640),
    )
    try:
        webview.start(private_mode=False, storage_path=str(storage_dir))
    finally:
        server.should_exit = True
        thread.join(timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
