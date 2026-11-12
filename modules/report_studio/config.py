
# -*- coding: utf-8 -*-
"""Основные настройки ANALYTICS AI."""

from pathlib import Path

APP_TITLE = "ANALYTICS AI"
APP_VERSION = "5.1.3 AI-ONLY COMPACT"

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}

DEFAULT_OUTPUT_DIR = (
    Path.home() / "Documents" / "BahonIQ Reports"
)

# Корпоративная цветовая палитра
COLORS = {
    "navy": "#183247",
    "navy_light": "#294A62",
    "background": "#F1F4F7",
    "surface": "#FFFFFF",
    "text": "#253746",
    "muted": "#718096",
    "border": "#D8E0E8",
    "accent": "#2878A5",
    "success": "#23845B",
    "warning": "#B7791F",
    "error": "#C53030",
    "table_alt": "#F4F7FA",
}

# Ограничения на объём аналитики
MAX_RANKING_ITEMS = 10
MAX_CHART_CATEGORIES = 15
MAX_TEXT_LENGTH = 500

# При отсутствии xlrd файлы XLS будут отклоняться
# с понятным сообщением об установке зависимости.
XLS_READER_PACKAGE = "xlrd"
