import unittest
from code_academy.learning_engine import PYTHON, SQL, SCHEMAS, python_checks, sql_checks, run_sql_lesson

class TestLearningEngine(unittest.TestCase):
    def test_lessons_are_substantive(self):
        for item in PYTHON:
            self.assertGreaterEqual(len(item.code.splitlines()),30)
            self.assertGreater(len(item.theory),180)
            self.assertGreater(len(item.walkthrough),150)
            self.assertGreater(len(item.task),20)
        for item in SQL:
            self.assertTrue(item.database in SCHEMAS)
    def test_python_examples_parse(self):
        for item in PYTHON:
            self.assertEqual(python_checks(item.code,()),[],item.slug)
    def test_python_checks_detect_missing_changes(self):
        for item in PYTHON:
            self.assertTrue(python_checks(item.code,item.checks),item.slug)
    def test_python_checks_reject_syntax(self):
        self.assertTrue(python_checks('def :',()))
    def test_sql_examples_execute(self):
        for item in SQL:
            result=run_sql_lesson(item.code,item.database)
            self.assertTrue(result.strip(),item.slug)
    def test_sql_checks_require_modification(self):
        for item in SQL:
            self.assertTrue(sql_checks(item.code,item.checks),item.slug)
    def test_sql_readonly(self):
        for statement in ('DROP TABLE students','INSERT INTO students(id,name) VALUES (10,\'Test\')','PRAGMA writable_schema=ON'):
            with self.assertRaises(Exception):run_sql_lesson(statement,'university')
    def test_database_scenarios_independent(self):
        self.assertIn('Медицина',run_sql_lesson('SELECT name FROM faculties','university'))
        self.assertIn('IT',run_sql_lesson('SELECT name FROM departments','company'))
        self.assertIn('Алия',run_sql_lesson('SELECT name FROM customers','shop'))
    def test_no_multiple_statements(self):
        with self.assertRaises(Exception):run_sql_lesson('SELECT 1; SELECT 2','shop')

if __name__=='__main__':unittest.main()
