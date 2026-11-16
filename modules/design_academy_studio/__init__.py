# -*- coding: utf-8 -*-
"""Design Academy Studio module for BahonIQ Desktop."""

try:
    from .ui import open_design_academy
except (ImportError, ModuleNotFoundError):
    open_design_academy = None

__all__ = ["open_design_academy"]
