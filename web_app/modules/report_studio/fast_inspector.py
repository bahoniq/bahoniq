import openpyxl
from pathlib import Path

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
                headers = preview[0] if preview else []
                sheets.append({
                    "name": s.name,
                    "rows_count": s.nrows,
                    "columns_count": s.ncols,
                    "headers": headers,
                    "preview": preview[1:] if len(preview) > 1 else [],
                    "matrix": preview
                })
        finally:
            wb.release_resources()
        return {"sheets": sheets}

    # Для .xlsx/.xlsm: только 1 проход в read_only режиме
    wb = openpyxl.load_workbook(filename=str(path), read_only=True, data_only=True)
    sheets = []
    try:
        for ws in wb.worksheets:
            preview = []
            # Берем только первые 20 строк для мгновенного превью
            for row in ws.iter_rows(min_row=1, max_row=20, max_col=20, values_only=True):
                preview.append([str(v) if v is not None else "" for v in row])
            
            headers = preview[0] if preview else []
            # Оцениваем размер без полного обхода
            max_r = ws.max_row or len(preview)
            max_c = ws.max_column or (len(headers) if headers else 0)
            
            sheets.append({
                "name": ws.title,
                "rows_count": max_r,
                "columns_count": max_c,
                "headers": headers,
                "preview": preview[1:] if len(preview) > 1 else [],
                "matrix": preview
            })
    finally:
        wb.close()
        
    return {"sheets": sheets}
