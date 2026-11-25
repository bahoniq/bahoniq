# -*- coding: utf-8 -*-
"""English Academy Studio bridge for BahonIQ Desktop."""

from __future__ import annotations

import socket
import threading
import webbrowser


def _ensure_local_web_server(default_port: int = 8012) -> int:
    for p in (8000, 8010, default_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                return p
    import uvicorn

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = int(s.getsockname()[1])

    cfg = uvicorn.Config("web_app.server:app", host="127.0.0.1", port=free_port, log_level="warning")
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    return free_port


def open_english_academy(root=None) -> None:
    port = _ensure_local_web_server()
    webbrowser.open(f"http://127.0.0.1:{port}/#englishAcademy")


__all__ = ["open_english_academy"]
