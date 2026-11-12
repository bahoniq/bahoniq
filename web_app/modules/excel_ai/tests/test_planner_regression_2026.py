import unittest
from openpyxl import Workbook
from modules.excel_ai.ai_interpreter import interpret_task
from modules.excel_ai.operations import _validate_ops, _do

class PlannerRegression2026(unittest.TestCase):
    def setUp(self):
        self.analysis={'sheets':[{'name':'Sheet0','headers':['Факультет','Отчество','Сумма','ID обучающегося','Форма обучения']} ]}
        self.wb=Workbook();ws=self.wb.active;ws.title='Sheet0'
        ws.append(self.analysis['sheets'][0]['headers'])
        ws.append(['Медицина',None,100,'1','Очная'])
        ws.append(['Право','А',200,'2','Очная'])
        ws.append(['Медицина',None,300,'3','Заочная'])
        ws.append([None,None,None,None,None])
    def test_missing_with_report(self):
        r=interpret_task('Сколько студентов без отчества? Сделай отчёт',self.analysis)
        self.assertEqual(r['operations'][0]['type'],'find_blank_cells')
    def test_missing_all_columns_route(self):
        r=interpret_task('Проверь всю таблицу на пустые значения и покажи строки с пропусками',self.analysis)
        self.assertEqual(r['operations'][0]['type'],'find_blank_cells')
        self.assertTrue(r['operations'][0]['all_columns'])
    def test_remove_fully_empty_rows_is_not_missing_cell_audit(self):
        task=('Нет, проверять отдельные пустые ячейки не нужно. Создай копию '
              'листа Sheet0 с названием «Обработанные данные». В этой копии '
              'удали только строки, в которых пусты все столбцы или находятся '
              'только пробелы. Исходный лист оставь без изменений.')
        r=interpret_task(task,self.analysis)
        self.assertEqual(r['operations'][0]['type'],'remove_empty_rows')
        self.assertEqual(r['operations'][0]['output_sheet'],'Обработанные данные')
        self.assertNotIn('find_blank_cells',[x['type'] for x in r['operations']])
    def test_remove_empty_rows_copy_preserves_source(self):
        op=_validate_ops([{'type':'remove_empty_rows','sheet':'Sheet0',
                           'output_sheet':'Обработанные данные'}],self.wb)[0]
        changes=[];_do(self.wb,op,changes,{})
        self.assertEqual(self.wb['Sheet0'].max_row,5)
        self.assertEqual(self.wb['Обработанные данные'].max_row,4)
        self.assertEqual(changes[0]['removed_rows'],1)
    def test_sort_and_report(self):
        r=interpret_task('Отсортируй по Сумме и сделай отчёт',self.analysis)
        self.assertEqual([x['type'] for x in r['operations']],['sort_rows','smart_summary'])
    def test_summary(self):
        r=interpret_task('Подготовь отчёт по факультетам с диаграммами',self.analysis)
        self.assertEqual(r['operations'][0]['type'],'smart_summary')
    def test_missing_rows_exclude_empty_tail(self):
        op=_validate_ops([{'type':'find_blank_cells','sheet':'Sheet0','column':'Отчество'}],self.wb)[0]
        changes=[];reports={};_do(self.wb,op,changes,reports)
        self.assertEqual(changes[0]['blank_cells'],2)
        self.assertEqual(self.wb['Найденные записи']['B6'].value,'Факультет')
    def test_repeated_values_no_blank_report(self):
        op=_validate_ops([{'type':'find_repeated_values','sheet':'Sheet0','column':'Факультет'}],self.wb)[0]
        changes=[];_do(self.wb,op,changes,{})
        self.assertEqual(changes[0]['repeated_values'],1)
        self.assertNotIn('Найденные записи',self.wb.sheetnames)
    def test_split_numeric(self):
        self.wb['Sheet0']['A2']=123
        op=_validate_ops([{'type':'split_to_sheets','sheet':'Sheet0','column':'Факультет'}],self.wb)[0]
        changes=[];_do(self.wb,op,changes,{})
        self.assertEqual(changes[0]['source_data_rows'],3)
    def test_no_overwrite_source(self):
        from modules.excel_ai.operations import _validate_paths
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.xlsx';self.wb.save(p)
            with self.assertRaises(ValueError):_validate_paths(p,p)

if __name__=='__main__':unittest.main()
