import unittest
from unittest.mock import patch
from modules.excel_ai.ai_interpreter import interpret_task

class ReportRoutingTests(unittest.TestCase):
    def test_typo_report_uses_python_without_ollama(self):
        analysis = {'sheets':[{'name':'Данные','headers':['Факультет','Направление','Студент']} ]}
        query = 'дай отчет по количеству студентов по факультетам и всем основным направлениям вдигарммах и таблицах'
        with patch('modules.excel_ai.ai_interpreter._post_to_ollama', side_effect=AssertionError('Ollama should not be called')):
            result=interpret_task(query,analysis)
        self.assertEqual(result['mode'],'operations')
        self.assertEqual(result['operations'][0]['type'],'smart_summary')
        self.assertTrue(result['operations'][0]['include_charts'])
        self.assertTrue(result['operations'][0]['include_cross_tables'])

if __name__=='__main__': unittest.main()
