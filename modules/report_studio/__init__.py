
# -*- coding: utf-8 -*-
"""ANALYTICS AI."""

from .config import APP_TITLE, APP_VERSION
from .excel_reader import ExcelReadError, read_excel
from .analytics import analyze_matrix, analyze_sheet
from .launcher import (
    ReportGenerationError,
    inspect_excel,
    generate_report,
)
from .pptx_builder import build_analytics_pptx


def open_report_studio(parent):
    """Открывает интерфейс ANALYTICS AI."""

    # Импорт выполняется при открытии окна, чтобы пакет можно было
    # подключать до завершения разработки интерфейса.
    from .ui import open_report_studio as open_window

    return open_window(parent)


__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "ExcelReadError",
    "ReportGenerationError",
    "read_excel",
    "analyze_matrix",
    "analyze_sheet",
    "inspect_excel",
    "generate_report",
    "build_analytics_pptx",
    "open_report_studio",
]
