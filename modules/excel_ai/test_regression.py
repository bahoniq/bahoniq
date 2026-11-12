import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook, load_workbook

spec = importlib.util.spec_from_file_location('ops_under_test', Path(__file__).with_name('operations.py'))
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source.xlsx'
        self.output = Path(self.tmp.name) / 'result.xlsx'
        wb = Workbook(); ws = wb.active; ws.title = 'Sheet0'
        ws.append(['Факультет', 'Направление', 'Студент'])
        for row in [('Медицина','Общая медицина','А'), ('Медицина','Педиатрия','Б'), ('Фармация','Фармация','В'), ('Медицина','Общая медицина','Г')]: ws.append(row)
        wb.save(self.source); wb.close()
    def test_summary_and_source_unchanged(self):
        old = ops._sha(self.source)
        plan = ops.plan_operations(self.source, self.output, [{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет','Направление']}])
        result = ops.execute_operations(plan, confirmed=True)
        self.assertEqual(result['source_sha256'], old)
        self.assertEqual(ops._sha(self.source), old)
        book=load_workbook(self.output)
        self.assertGreaterEqual(len(book.sheetnames),4)
        self.assertEqual(book['Сводка Факультет']['B2'].value,3)
        self.assertGreaterEqual(len(book['Сводка Факультет']._charts),1)
        book.close()
    def test_metadata_only_change_is_allowed(self):
        plan = ops.plan_operations(self.source,self.output,[{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет']}])
        st=self.source.stat(); os.utime(self.source, ns=(st.st_atime_ns, st.st_mtime_ns+2_000_000_000))
        self.assertEqual(ops.execute_operations(plan,confirmed=True)['status'],'completed')
    def test_changed_content_rejected(self):
        plan=ops.plan_operations(self.source,self.output,[{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет']}])
        wb=load_workbook(self.source); wb.active['A2']='Другое'; wb.save(self.source); wb.close()
        with self.assertRaisesRegex(RuntimeError,'изменился'):
            ops.execute_operations(plan,confirmed=True)
        self.assertFalse(self.output.exists())
    def test_blank_cells_operation(self):
        wb=load_workbook(self.source); wb.active['B3']=None; wb.save(self.source); wb.close()
        plan=ops.plan_operations(self.source,self.output,[{'type':'find_blank_cells','sheet':'Sheet0','column':'Направление'}])
        ops.execute_operations(plan,confirmed=True)
        wb=load_workbook(self.output)
        self.assertEqual(wb['Найденные записи']['B4'].value,1)
        wb.close()
    def test_confirmation_required(self):
        plan=ops.plan_operations(self.source,self.output,[{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет']}])
        with self.assertRaises(PermissionError): ops.execute_operations(plan,confirmed=False)

if __name__=='__main__': unittest.main()
