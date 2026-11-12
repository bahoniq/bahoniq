# -*- coding: utf-8 -*-
"""Запуск FastAPI веб-сервера BahonIQ Work Center v2.0.0."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("BahonIQ Work Center Web Server v2.0.0")
    print("Запуск на http://0.0.0.0:8000 (доступен локально, в LAN и через туннели)")
    print("OpenAPI Swagger UI: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("web_app.server:app", host="0.0.0.0", port=8000, reload=False)
