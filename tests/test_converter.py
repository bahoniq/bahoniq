import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'modules' / 'excel_ai' / 'converter.py'
spec = importlib.util.spec_from_file_location('bahoniq_converter', MODULE)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)

class FakeCell:
    def __init__(self, value, kind=1):
        self.value, self.ctype = value, kind

class FakeSheet:
    name = 'Данные'
    nrows = 3
    ncols = 2
    def cell(self, r, c):
        data = [[FakeCell('Факультет'), FakeCell('Количество')],
                [FakeCell('Медицина'), FakeCell(12.0, 2)],
                [FakeCell('Фармация'), FakeCell(8.0, 2)]]
        return data[r][c]

class FakeBook:
    nsheets = 1
    datemode = 0
    def sheet_by_index(self, index):
        return FakeSheet()
    def release_resources(self):
        pass

fake_xlrd = types.SimpleNamespace(
    XL_CELL_EMPTY=0, XL_CELL_BLANK=6, XL_CELL_DATE=3,
    XL_CELL_BOOLEAN=4, XL_CELL_ERROR=5, XL_CELL_NUMBER=2,
    error_text_from_code={}, open_workbook=lambda *a, **kw: FakeBook(),
)

class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source.xls'
        self.source.write_bytes(b'unchanged original')

    def test_convert_values_and_preserve_source(self):
        from openpyxl import load_workbook
        with patch.dict(sys.modules, {'xlrd': fake_xlrd}):
            output = converter.convert_xls_to_xlsx(self.source)
        self.assertEqual(self.source.read_bytes(), b'unchanged original')
        wb = load_workbook(output, read_only=True)
        try:
            self.assertEqual(wb.active['B2'].value, 12)
            self.assertEqual(wb.active['A3'].value, 'Фармация')
        finally:
            wb.close()

    def test_existing_output_never_overwritten(self):
        target = self.source.with_suffix('.xlsx')
        target.write_bytes(b'keep')
        with patch.dict(sys.modules, {'xlrd': fake_xlrd}):
            with self.assertRaises(FileExistsError):
                converter.convert_xls_to_xlsx(self.source)
        self.assertEqual(target.read_bytes(), b'keep')

    def test_invalid_extension(self):
        with patch.dict(sys.modules, {'xlrd': fake_xlrd}):
            with self.assertRaises(ValueError):
                converter.convert_xls_to_xlsx(self.source.with_suffix('.xlsx'))

    def test_detect_changed_source(self):
        def changed(*args, **kwargs):
            self.source.write_bytes(b'changed')
            return FakeBook()
        with patch.dict(sys.modules, {'xlrd': types.SimpleNamespace(**{**vars(fake_xlrd), 'open_workbook': changed})}):
            with self.assertRaisesRegex(RuntimeError, 'изменился'):
                converter.convert_xls_to_xlsx(self.source)
        self.assertFalse(self.source.with_suffix('.xlsx').exists())

if __name__ == '__main__':
    unittest.main()
