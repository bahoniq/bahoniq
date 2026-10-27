
import ctypes
import hashlib
import os
import re
import sys
from collections import defaultdict
from ctypes import wintypes
from pathlib import Path

CHUNK_SIZE = 4 * 1024 * 1024
NAME_GROUP_PREFIX = "NAME::"


def format_size(size):
    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    value = float(size)

    for unit in units:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} ПБ"


def file_hash(path, chunk_size=CHUNK_SIZE):
    sha256 = hashlib.sha256()

    try:
        with open(path, "rb") as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)

        return sha256.hexdigest()

    except (PermissionError, OSError):
        return None


def normalize_filename(path):
    path = Path(path)
    stem = path.stem.strip()
    suffix = path.suffix.casefold()

    while True:
        previous = stem

        patterns = (
            r"\s*\(\s*\d+\s*\)\s*$",
            r"\s*-\s*копия(?:\s*\(\s*\d+\s*\))?\s*$",
            r"\s*\(\s*копия\s*\)\s*$",
            r"\s*-\s*copy(?:\s*\(\s*\d+\s*\))?\s*$",
            r"\s*\(\s*copy\s*\)\s*$",
        )

        for pattern in patterns:
            stem = re.sub(pattern, "", stem, flags=re.IGNORECASE)

        if stem == previous:
            break

    stem = stem.strip(" ._-")
    return f"{stem.casefold()}{suffix}" if stem else None


def has_copy_suffix(path):
    stem = Path(path).stem.strip()

    patterns = (
        r"\(\s*\d+\s*\)\s*$",
        r"-\s*копия(?:\s*\(\s*\d+\s*\))?\s*$",
        r"\(\s*копия\s*\)\s*$",
        r"-\s*copy(?:\s*\(\s*\d+\s*\))?\s*$",
        r"\(\s*copy\s*\)\s*$",
    )

    return any(
        re.search(pattern, stem, re.IGNORECASE)
        for pattern in patterns
    )


def is_name_group(group_key):
    return str(group_key).startswith(NAME_GROUP_PREFIX)


def collect_files(folder, stop_event=None, progress_callback=None):
    folder = Path(folder)
    files = []

    if not folder.exists():
        return files

    scanned = 0

    for root, dirs, filenames in os.walk(folder):
        dirs[:] = [
            directory for directory in dirs
            if directory not in {
                "$RECYCLE.BIN",
                "System Volume Information",
            }
        ]

        for filename in filenames:
            if stop_event and stop_event.is_set():
                return files

            path = Path(root) / filename

            try:
                if not path.is_file():
                    continue

                stat = path.stat()

                files.append({
                    "path": path,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

                scanned += 1

                if progress_callback:
                    progress_callback(scanned, None, path)

            except (PermissionError, OSError):
                continue

    return files


def find_duplicates(folder, stop_event=None, progress_callback=None):
    files = collect_files(
        folder,
        stop_event=stop_event,
        progress_callback=progress_callback,
    )

    if stop_event and stop_event.is_set():
        return {}

    # 1. Точные совпадения содержимого.
    by_size = defaultdict(list)

    for item in files:
        by_size[item["size"]].append(item)

    candidates = [
        item
        for group in by_size.values()
        if len(group) > 1
        for item in group
    ]

    hash_groups = defaultdict(list)
    total = len(candidates)

    for current, item in enumerate(candidates, start=1):
        if stop_event and stop_event.is_set():
            return {}

        digest = file_hash(item["path"])

        if digest:
            hash_groups[digest].append(item)

        if progress_callback:
            progress_callback(current, total, item["path"])

    duplicates = {
        digest: items
        for digest, items in hash_groups.items()
        if len(items) > 1
    }

    if stop_event and stop_event.is_set():
        return {}

    # 2. Возможные копии по имени. Содержимое может различаться.
    exact_paths = {
        item["path"]
        for group in duplicates.values()
        for item in group
    }

    by_name = defaultdict(list)

    for item in files:
        normalized = normalize_filename(item["path"])

        if normalized:
            by_name[normalized].append(item)

    for normalized, items in by_name.items():
        if len(items) < 2:
            continue

        distinct_names = {
            item["path"].name.casefold()
            for item in items
        }

        if len(distinct_names) < 2:
            continue

        if not any(has_copy_suffix(item["path"]) for item in items):
            continue

        # Не показываем файлы, уже вошедшие в точные дубликаты.
        remaining = [
            item for item in items
            if item["path"] not in exact_paths
        ]

        if len(remaining) < 2:
            continue

        # Сначала основной файл без суффикса копии,
        # затем варианты с суффиксами.
        remaining.sort(
            key=lambda item: (
                has_copy_suffix(item["path"]),
                item["path"].name.casefold(),
                str(item["path"]).casefold(),
            )
        )

        duplicates[NAME_GROUP_PREFIX + normalized] = remaining

    return duplicates


def count_duplicates(duplicates):
    return len(duplicates)


def count_duplicate_files(duplicates):
    return sum(len(items) for items in duplicates.values())


def duplicate_size(duplicates):
    return sum(
        item.get("size", 0)
        for items in duplicates.values()
        for item in items
    )


def get_removable_files(duplicates):
    removable = []

    for items in duplicates.values():
        if len(items) > 1:
            # Оставляем первый файл в каждой группе.
            removable.extend(item["path"] for item in items[1:])

    # Защита от повторного добавления одного пути.
    return list(dict.fromkeys(removable))


def removable_size(duplicates, selected_paths=None):
    removable = get_removable_files(duplicates)

    if selected_paths is not None:
        selected = {Path(path) for path in selected_paths}
        removable = [
            path for path in removable
            if Path(path) in selected
        ]

    total = 0

    for path in removable:
        try:
            total += path.stat().st_size
        except OSError:
            pass

    return total


def _move_to_recycle_bin(path):
    """Перемещает файл в Корзину Windows через системную оболочку."""

    if sys.platform != "win32":
        raise OSError(
            "Перемещение в Корзину поддерживается только в Windows."
        )

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    operation = SHFILEOPSTRUCTW()
    operation.hwnd = None
    operation.wFunc = 3  # FO_DELETE
    operation.pFrom = str(path) + "\0\0"
    operation.pTo = None

    # Разрешить отмену, не показывать системные окна.
    # FOF_ALLOWUNDO сохраняет файл в Корзине.
    operation.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400

    operation.fAnyOperationsAborted = False
    operation.hNameMappings = None
    operation.lpszProgressTitle = None

    result = ctypes.windll.shell32.SHFileOperationW(
        ctypes.byref(operation)
    )

    if result != 0 or operation.fAnyOperationsAborted:
        raise OSError(
            f"Windows не смогла переместить файл в Корзину "
            f"(код {result})."
        )


def delete_files(paths):
    """Перемещает выбранные файлы в Корзину; не удаляет безвозвратно."""

    deleted = []
    failed = []

    for original_path in paths:
        path = Path(original_path)

        try:
            if not path.exists():
                failed.append({
                    "path": path,
                    "error": "Файл уже отсутствует.",
                })
                continue

            size = path.stat().st_size
            _move_to_recycle_bin(path)

            deleted.append({
                "path": path,
                "size": size,
            })

        except (PermissionError, OSError, AttributeError) as error:
            failed.append({
                "path": path,
                "error": str(error),
            })

    return deleted, failed
