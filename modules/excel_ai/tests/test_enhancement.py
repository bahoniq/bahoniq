import sys,tempfile,unittest
from pathlib import Path
from openpyxl import Workbook,load_workbook
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root))
from modules.excel_ai.operations import plan_operations,execute_operations
from modules.excel_ai.ai_interpreter import _route_smart_summary_request
class Tests(unittest.TestCase):
 def test_summary(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'in.xlsx';out=Path(d)/'out.xlsx';w=Workbook();ws=w.active;ws.title='Sheet0';ws.append(['Факультет','Форма обучения','ID обучающегося','Вид финансирования','Пол','Гражданство','Дата рождения','Национальность','Язык обучения']);
   for i in range(120):ws.append(['Медицинский' if i%2 else 'Стоматологический','Очная',str(i),'Грант' if i%3 else 'Платно','М' if i%2 else 'Ж','Казахстан',None,'Казах','Русский' if i%2 else 'Казахский'])
   w.save(src);w.close()
   analysis={'sheets':[{'name':'Sheet0','headers':['Факультет','Форма обучения','ID обучающегося','Вид финансирования','Пол','Гражданство','Дата рождения','Национальность','Язык обучения']} ]}
   route=_route_smart_summary_request('Подготовь отчёт по количеству студентов по факультетам и основным направлениям с таблицами и диаграммами',analysis)
   self.assertIsNotNone(route);self.assertTrue(route['operations'][0]['include_other_dimensions']);self.assertIn('отсутствует',route['explanation'])
   plan=plan_operations(src,out,route['operations']);self.assertGreater(len(plan['operations'][0]['columns']),1)
   result=execute_operations(plan,confirmed=True);self.assertGreater(len(result['reports']['smart_summary']['output_sheets']),2)
   book=load_workbook(out);self.assertGreater(sum(len(book[n]._charts) for n in book.sheetnames),1);self.assertTrue(any('Форма' in n for n in book.sheetnames));book.close()
 def test_ui(self):
  ui_path = Path(__file__).resolve().parents[1] / 'ui.py'
  t=ui_path.read_text(encoding='utf-8');self.assertIn('self._enable_text_clipboard(self.plan_text, readonly=True)',t);self.assertIn('Копировать результат',t)
if __name__=='__main__':unittest.main(verbosity=2)
