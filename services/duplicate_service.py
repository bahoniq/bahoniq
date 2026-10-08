import hashlib
import os
from pathlib import Path


# ============================================================
# НАСТРОЙКИ
# ============================================================

CHUNK_SIZE = 4 * 1024 * 1024


# ============================================================
# РАЗМЕР ФАЙЛА
# ============================================================

def format_size(size):

    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]

    value = float(size)

    for unit in units:

        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} ПБ"


# ============================================================
# SHA-256
# ============================================================

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


# ============================================================
# СКАНИРОВАНИЕ ФАЙЛОВ
# ============================================================

def collect_files(folder, stop_event=None, progress_callback=None):

    folder = Path(folder)

    files = []

    if not folder.exists():
        return files

    scanned = 0

    for root, dirs, filenames in os.walk(folder):

        # Убираем скрытые/служебные папки
        dirs[:] = [
            d for d in dirs
            if d not in {
                "$RECYCLE.BIN",
                "System Volume Information"
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
                    progress_callback(
                        scanned,
                        None,
                        path
                    )

            except (PermissionError, OSError):

                continue

    return files


# ============================================================
# ПОИСК ДУБЛИКАТОВ
# ============================================================

def find_duplicates(
    folder,
    stop_event=None,
    progress_callback=None
):

    files = collect_files(
        folder,
        stop_event=stop_event,
        progress_callback=progress_callback
    )

    if stop_event and stop_event.is_set():
        return {}

    # --------------------------------------------------------
    # Сначала группируем по размеру
    # --------------------------------------------------------

    by_size = {}

    for item in files:

        size = item["size"]

        if size not in by_size:
            by_size[size] = []

        by_size[size].append(item)

    # --------------------------------------------------------
    # Только одинаковые размеры
    # --------------------------------------------------------

    candidates = []

    for size, items in by_size.items():

        if len(items) > 1:

            candidates.extend(items)

    # --------------------------------------------------------
    # SHA-256
    # --------------------------------------------------------

    duplicates = {}

    total_hashes = len(candidates)
    current_hash = 0

    for item in candidates:

        if stop_event and stop_event.is_set():
            return {}

        path = item["path"]

        hash_value = file_hash(path)

        current_hash += 1

        if progress_callback:

            progress_callback(
                current_hash,
                total_hashes,
                path
            )

        if hash_value is None:
            continue

        if hash_value not in duplicates:

            duplicates[hash_value] = []

        duplicates[hash_value].append(item)

    # --------------------------------------------------------
    # Оставляем только реальные группы
    # --------------------------------------------------------

    duplicates = {

        hash_value: items

        for hash_value, items in duplicates.items()

        if len(items) > 1

    }

    return duplicates


# ============================================================
# КОЛИЧЕСТВО ГРУПП
# ============================================================

def count_duplicates(duplicates):

    return len(duplicates)


# ============================================================
# КОЛИЧЕСТВО ФАЙЛОВ
# ============================================================

def count_duplicate_files(duplicates):

    total = 0

    for items in duplicates.values():

        total += len(items)

    return total


# ============================================================
# ОБЩИЙ РАЗМЕР ВСЕХ ДУБЛИКАТОВ
# ============================================================

def duplicate_size(duplicates):

    total = 0

    for items in duplicates.values():

        for item in items:

            try:
                total += item["size"]

            except Exception:
                pass

    return total


# ============================================================
# РЕАЛЬНО ОСВОБОЖДАЕМОЕ МЕСТО
# ============================================================

def removable_size(duplicates, selected_paths=None):

    total = 0

    selected_paths = set(
        Path(path)
        for path in (selected_paths or [])
    )

    for items in duplicates.values():

        # Если конкретный выбор пользователя
        if selected_paths:

            for item in items:

                if item["path"] in selected_paths:

                    try:
                        total += item["size"]

                    except Exception:
                        pass

            continue

        # По умолчанию оставляем первый файл
        for item in items[1:]:

            try:
                total += item["size"]

            except Exception:
                pass

    return total


# ============================================================
# ПРЕДЛОЖЕНИЕ ФАЙЛОВ ДЛЯ УДАЛЕНИЯ
# ============================================================

def get_removable_files(duplicates):

    removable = []

    for items in duplicates.values():

        if len(items) <= 1:
            continue

        # Первый файл оставляем
        for item in items[1:]:

            removable.append(item["path"])

    return removable


# ============================================================
# УДАЛЕНИЕ
# ============================================================

def delete_files(paths):

    deleted = []
    failed = []

    for path in paths:

        path = Path(path)

        try:

            if not path.exists():
                continue

            size = path.stat().st_size

            path.unlink()

            deleted.append({
                "path": path,
                "size": size
            })

        except (PermissionError, OSError) as error:

            failed.append({
                "path": path,
                "error": str(error)
            })

    return deleted, failed