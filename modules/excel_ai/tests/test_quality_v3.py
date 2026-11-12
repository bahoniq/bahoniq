import unittest
from openpyxl import Workbook
from modules.excel_ai.ai_interpreter import interpret_task
from modules.excel_ai.operations import _validate_ops, _do

HEADERS=['Факультет','Форма обучения','Вид финансирования','ID обучающегося','Пол','Гражданство','Курс']
ANALYSIS={'sheets':[{'name':'Sheet0','headers':HEADERS}]}
class QualityV3(unittest.TestCase):
 def test_distinct_plan(self):
  r=interpret_task('Сравни общее количество записей с количеством уникальных ID обучающегося. Покажи разницу, а затем подготовь распределение студентов по факультетам с учётом уникальных ID, чтобы повторяющиеся идентификаторы не увеличивали численность.',ANALYSIS)
  self.assertEqual([x['type'] for x in r['operations']],['distinct_count'])
  self.assertEqual(r['operations'][0]['columns'],['Факультет'])
 def test_conversational(self):
  r=interpret_task('Хочу увидеть, как распределяется контингент по школам и факультетам, сколько учится на разных формах и за чей счёт. Сделай понятные таблицы и графики, чтобы можно было быстро сравнить группы.',ANALYSIS)
  self.assertEqual(r['operations'][0]['columns'],['Факультет','Форма обучения','Вид финансирования'])
 def test_missing_columns(self):
  a={'sheets':[{'name':'Sheet0','headers':HEADERS[:-1]}]}
  r=interpret_task('Покажи количество студентов по образовательным программам, специальностям и курсам. Если таких столбцов в файле нет, не подставляй другие показатели и не создавай фиктивные результаты.',a)
  self.assertFalse(r['operations'])
  self.assertIn('отсутствуют',r['questions'][0])
 def test_distinct_execution(self):
  wb=Workbook(); ws=wb.active; ws.title='Sheet0';ws.append(HEADERS)
  ws.append(['A','Очная','Грант','001','М','КЗ',1]);ws.append(['A','Очная','Грант','001','М','КЗ',1]);ws.append(['A','Очная','Грант','002','Ж','КЗ',1]);ws.append(['B','Очная','Грант','002','Ж','КЗ',1]);ws.append(['B','Очная','Грант',None,'Ж','КЗ',1])
  ops=_validate_ops([{'type':'distinct_count','sheet':'Sheet0','id_column':'ID обучающегося','columns':['Факультет']}],wb)
  changes=[];reports={};_do(wb,ops[0],changes,reports)
  self.assertEqual(changes[0]['unique_ids'],2)
  self.assertEqual(changes[0]['cross_group_ids'],1)
  self.assertEqual(changes[0]['blank_ids'],1)
  self.assertEqual(wb['Уникальные ID']['B3'].value,2)
  wb.close()
if __name__=='__main__':unittest.main()
