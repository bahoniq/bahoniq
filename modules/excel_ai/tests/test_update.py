import sys, types, unittest
from pathlib import Path
from openpyxl import Workbook
PROJECT_ROOT=Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
 sys.path.insert(0,str(PROJECT_ROOT))
try:
 from modules.excel_ai import settings, intent_compiler
except ImportError:
 settings=types.ModuleType('modules.excel_ai.settings')
 for k,v in dict(CONTEXT_SIZE=2048,MAX_ANALYSIS_CHARS=10000,OLLAMA_TAGS_URL='',OLLAMA_URL='',PREFERRED_MODEL='qwen2.5:3b',REQUEST_TIMEOUT=3).items(): setattr(settings,k,v)
 sys.modules['modules.excel_ai.settings']=settings
 compiler=types.ModuleType('modules.excel_ai.intent_compiler')
 compiler.compile_intent=lambda *a,**k: {}
 sys.modules['modules.excel_ai.intent_compiler']=compiler
from modules.excel_ai import ai_interpreter as ai, operations as ops
class Tests(unittest.TestCase):
 def setUp(self):
  self.wb=Workbook(); self.ws=self.wb.active; self.ws.title='Sheet0'
  self.ws.append(['Факультет','Отчество','Сумма','ID обучающегося'])
  self.ws.append(['Медицина',None,100,'1']); self.ws.append(['Медицина','А',200,'2']); self.ws.append(['Право',None,300,'3'])
  self.analysis={'sheets':[{'name':'Sheet0','headers':['Факультет','Отчество','Сумма','ID обучающегося']}]}
 def test_missing_route(self):
  result=ai.interpret_task('Сколько студентов без отчества? Сделай отчёт',self.analysis)
  self.assertEqual(result['operations'][0]['type'],'find_blank_cells')
 def test_missing_execution(self):
  op=ops._validate_ops([{'type':'find_blank_cells','sheet':'Sheet0','column':'Отчество'}],self.wb)[0]
  changes=[];reports={};ops._do(self.wb,op,changes,reports)
  self.assertEqual(changes[0]['blank_cells'],2)
  self.assertEqual(self.wb['Найденные записи']['B6'].value,'Факультет')
 def test_repeated_execution(self):
  op=ops._validate_ops([{'type':'find_repeated_values','sheet':'Sheet0','column':'Факультет'}],self.wb)[0]
  changes=[];reports={};ops._do(self.wb,op,changes,reports)
  self.assertEqual(changes[0]['repeated_values'],1)
  self.assertNotIn('Найденные записи',self.wb.sheetnames)
 def test_summary(self):
  result=ai.interpret_task('Дай отчёт по факультетам в таблицах и диаграммах',self.analysis)
  self.assertEqual(result['operations'][0]['type'],'smart_summary')
 def test_summary_does_not_hijack_sort(self):
  result=ai.interpret_task('Отсортируй по Сумме и сделай отчёт',self.analysis)
  self.assertNotEqual(result.get('operations',[{}])[0].get('type'),'smart_summary')
 def test_split_nonstring(self):
  self.ws['A2']=123
  op=ops._validate_ops([{'type':'split_to_sheets','sheet':'Sheet0','column':'Факультет'}],self.wb)[0]
  changes=[];ops._do(self.wb,op,changes,{})
  self.assertEqual(changes[0]['source_data_rows'],3)
 def test_smart_summary_totals(self):
  op=ops._validate_ops([{'type':'smart_summary','sheet':'Sheet0','columns':['Факультет','Отчество'],'include_charts':True}],self.wb)[0]
  changes=[];ops._do(self.wb,op,changes,{})
  self.assertEqual(changes[0]['rows'],3)
  self.assertGreater(len(changes[0]['cross_sheets']),0)
  self.assertEqual(len(self.wb['Сводка Факультет']._charts),1)
if __name__=='__main__': unittest.main()
