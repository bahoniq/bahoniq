"""Safe values-only XLS -> XLSX conversion for BahonIQ Excel AI."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def convert_xls_to_xlsx(source, destination=None):
    """Convert XLS cells to a new XLSX without modifying the original.

    Formulas, macros, charts and original formatting are not preserved.
    """
    import xlrd
    from openpyxl import Workbook, load_workbook

    src = Path(source).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() != '.xls':
        raise ValueError('Выберите существующий файл формата .xls')
    dst = Path(destination).expanduser().resolve() if destination else src.with_suffix('.xlsx')
    if dst.suffix.lower() != '.xlsx' or dst == src:
        raise ValueError('Результат должен быть отдельным файлом .xlsx')
    if dst.exists():
        raise FileExistsError(f'Файл уже существует: {dst}')
    if not dst.parent.is_dir():
        raise FileNotFoundError(f'Папка результата отсутствует: {dst.parent}')

    source_stat = src.stat()
    from hashlib import sha256
    def digest(path):
        h = sha256()
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        return h.digest()

    initial_hash = digest(src)
    book = xlrd.open_workbook(str(src), on_demand=True)
    target = Workbook()
    target.remove(target.active)
    fd, tmpname = tempfile.mkstemp(prefix='.bahoniq_convert_', suffix='.xlsx', dir=str(dst.parent))
    os.close(fd)
    tmp = Path(tmpname)
    try:
        for index in range(book.nsheets):
            sheet = book.sheet_by_index(index)
            title = (sheet.name or 'Sheet')[:31]
            base = title
            suffix = 2
            while title.casefold() in {s.casefold() for s in target.sheetnames}:
                tail = f'_{suffix}'
                title = base[:31-len(tail)] + tail
                suffix += 1
            ws = target.create_sheet(title)
            for row_index in range(sheet.nrows):
                values = []
                for col_index in range(sheet.ncols):
                    cell = sheet.cell(row_index, col_index)
                    value = cell.value
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        value = None
                    elif cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate_as_datetime(value, book.datemode)
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        value = bool(value)
                    elif cell.ctype == xlrd.XL_CELL_ERROR:
                        value = xlrd.error_text_from_code.get(value, '#ERROR!')
                    elif cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                        value = int(value)
                    values.append(value)
                ws.append(values)
        if not target.sheetnames:
            target.create_sheet('Sheet1')
        target.save(tmp)
        check = load_workbook(tmp, read_only=True)
        try:
            if len(check.sheetnames) != book.nsheets:
                raise RuntimeError('Количество листов после конвертации не совпадает')
        finally:
            check.close()
        if digest(src) != initial_hash or src.stat().st_size != source_stat.st_size:
            raise RuntimeError('Исходный XLS изменился во время конвертации; результат не сохранён')
        # Atomic no-overwrite publication on same filesystem.
        os.link(tmp, dst)
        return dst
    finally:
        book.release_resources()
        target.close()
        tmp.unlink(missing_ok=True)
