import openpyxl
from pathlib import Path


def _is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _detect_header_index(matrix):
    """Find the real table header when titles/notes precede the table."""
    best_index, best_score = 0, float("-inf")
    for index, row in enumerate(matrix[:30]):
        populated = [value for value in row if not _is_empty(value)]
        if not populated:
            continue
        text_values = [value for value in populated if isinstance(value, str)]
        unique = len({str(value).strip().casefold() for value in populated})
        score = len(populated) * 2.0 + len(text_values) * 1.5 + unique * 0.5
        if len(populated) == 1:
            score -= 8.0
        elif len(populated) == 2:
            score -= 3.0
        for following in matrix[index + 1:index + 5]:
            count = sum(not _is_empty(value) for value in following)
            if count >= max(1, min(len(populated), 3)):
                score += 2.0
        if score > best_score:
            best_index, best_score = index, score
    return best_index


def _sheet_result(name, rows_count, columns_count, matrix):
    header_index = _detect_header_index(matrix) if matrix else 0
    headers = list(matrix[header_index]) if matrix else []
    while headers and _is_empty(headers[-1]):
        headers.pop()
    return {
        "name": name,
        "rows_count": max(0, max(rows_count, len(matrix)) - header_index - 1),
        "columns_count": max(columns_count, len(headers)),
        "headers": headers,
        "header_row": header_index + 1,
        "preview": matrix[header_index + 1:header_index + 6],
        "matrix": matrix,
    }

def fast_inspect_excel(path: str | Path) -> dict:
    """Быстрый осмотр Excel без двойного открытия и без глубокого аудита."""
    path = Path(path).expanduser().resolve()
    ext = path.suffix.lower()
    
    if ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(str(path), on_demand=True)
        sheets = []
        try:
            for s in wb.sheets():
                preview = []
                for r in range(min(16, s.nrows)):
                    row_vals = [str(s.cell_value(r, c)) if s.cell_value(r, c) != "" else "" for c in range(min(20, s.ncols))]
                    preview.append(row_vals)
                sheets.append(_sheet_result(s.name, s.nrows, s.ncols, preview))
        finally:
            wb.release_resources()
        return {"sheets": sheets}

    # Some exported reports omit worksheet dimension metadata, so read_only
    # incorrectly reports a one-cell sheet. Normal mode gives reliable bounds.
    wb = openpyxl.load_workbook(filename=str(path), read_only=False, data_only=True)
    sheets = []
    try:
        for ws in wb.worksheets:
            preview = []
            original_max_row = ws.max_row or 0
            original_max_col = ws.max_column or 0
            # Берем только первые 20 строк для мгновенного превью
            for row in ws.iter_rows(
                min_row=1,
                max_row=min(original_max_row, 20),
                max_col=min(original_max_col, 20),
                values_only=True,
            ):
                preview.append([str(v) if v is not None else "" for v in row])
            
            # Оцениваем размер без полного обхода
            max_r = max(original_max_row, len(preview))
            max_c = max(original_max_col, len(preview[0]) if preview else 0)
            sheets.append(_sheet_result(ws.title, max_r, max_c, preview))
    finally:
        wb.close()
        
    return {"sheets": sheets}
