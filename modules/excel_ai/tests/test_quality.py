import sys,tempfile,unittest
from pathlib import Path
from openpyxl import Workbook,load_workbook
sys.path.insert(0,'/mnt/data/bahoniq_excel_enhanced')
from modules.excel_ai.operations import plan_operations,execute_operations
class Quality(unittest.TestCase):
 def test_cross_totals_unique_and_charts(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'source.xlsx';out=Path(d)/'out.xlsx'
   wb=Workbook();ws=wb.active;ws.title='Sheet0';ws.append(['Факультет','Направление','ID обучающегося','Пол','Язык обучения','Форма обучения'])
   for i in range(140):ws.append([f'Факультет {i%25}',f'Направление {i%26}',f'ID-{i%120}', 'М' if i%2 else 'Ж','Русский','Очная'])
   wb.save(src);wb.close();original=src.read_bytes()
   plan=plan_operations(src,out,[{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет','Направление','Пол','Язык обучения','Форма обучения'],'include_charts':True,'include_cross_tables':True}])
   result=execute_operations(plan,confirmed=True)
   self.assertEqual(src.read_bytes(),original)
   self.assertEqual(result['reports']['smart_summary']['unique_id_count'],120)
   book=load_workbook(out)
   crosses=result['changes'][0]['cross_sheets'];self.assertGreaterEqual(len(crosses),4)
   for name in crosses:
    sheet=book[name];last=sheet.max_row;lastcol=sheet.max_column
    self.assertEqual(sheet.cell(last,lastcol).value,140)
    self.assertEqual(sum(sheet.cell(r,lastcol).value for r in range(2,last)),140)
    self.assertEqual(sum(sheet.cell(last,c).value for c in range(2,lastcol)),140)
   self.assertGreaterEqual(sum(len(book[name]._charts) for name in book.sheetnames),3)
   book.close()
if __name__=='__main__':unittest.main()
