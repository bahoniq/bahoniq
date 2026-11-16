# -*- coding: utf-8 -*-
"""Модуль Platonus Wiki AI — единая база знаний инструкций Platonus."""

from .service import (
    ask_wiki,
    create_manual_article,
    delete_article,
    get_article,
    get_wiki_tree,
    init_wiki_db,
    update_article,
    upload_and_catalog_files,
)

__all__ = [
    "init_wiki_db",
    "get_wiki_tree",
    "get_article",
    "update_article",
    "delete_article",
    "create_manual_article",
    "upload_and_catalog_files",
    "ask_wiki",
]
