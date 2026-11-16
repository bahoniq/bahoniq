# -*- coding: utf-8 -*-
"""Excel Academy Studio module for BahonIQ Desktop."""

try:
    from .ui import open_excel_academy
except (ImportError, ModuleNotFoundError):
    open_excel_academy = None

__all__ = ["open_excel_academy"]
