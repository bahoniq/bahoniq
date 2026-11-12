import unittest
from code_academy.encyclopedia import entries, search
from code_academy.pathway import steps, check_python, run_sql

class Stage4Tests(unittest.TestCase):
    def test_reference_depth(self):
        self.assertGreaterEqual(len(entries('python')),30)
        self.assertGreaterEqual(len(entries('sql')),30)
    def test_russian_search(self):
        self.assertEqual(search('python','вывести')[0].name,'print()')
        self.assertEqual(search('sql','количество')[0].name,'COUNT()')
    def test_progression(self):
        for lang in ('python','sql'):
            levels=[x.level for x in steps(lang)]
            self.assertEqual(levels,sorted(levels))
            self.assertEqual(levels[0],1)
            self.assertEqual(levels[-1],6)
    def test_python_examples_syntax(self):
        from code_academy.pro_engine import PythonRunner, TestCase
        for step in steps('python'):
            report=PythonRunner().assess(step.code,(TestCase('Учебный пример'),))
            self.assertTrue(report.passed,(step.slug,report))
    def test_sql_examples(self):
        for step in steps('sql'):
            try:run_sql(step.code,allow_writes=step.mode=='ddl')
            except Exception as e:self.fail(f'{step.slug}: {e}')
    def test_sql_writes_denied_in_select(self):
        with self.assertRaises(Exception):run_sql('DELETE FROM tasks')
    def test_db_is_ephemeral(self):
        run_sql("UPDATE tasks SET status='done' WHERE id=1;",allow_writes=True)
        self.assertIn('open', '\n'.join(run_sql('SELECT status FROM tasks WHERE id=1')))
    def test_invalid_python(self):
        ok,_=check_python('def bad(:',steps('python')[0]);self.assertFalse(ok)
