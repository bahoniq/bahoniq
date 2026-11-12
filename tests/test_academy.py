import unittest
from modules.code_academy.runners import run_python,run_sql
from modules.code_academy.curriculum import LESSONS
class TestAcademy(unittest.TestCase):
 def test_all_examples(self):
  for title,cat,_,code,expected,*_ in LESSONS:
   with self.subTest(title=title): self.assertEqual((run_sql(code) if cat=='SQL' else run_python(code)).strip(),expected.strip())
 def test_no_python_import(self):
  with self.assertRaises(ValueError): run_python('import os')
 def test_no_python_files(self):
  with self.assertRaises(ValueError): run_python('open("file.txt","w")')
 def test_no_sql_write(self):
  with self.assertRaises(Exception): run_sql('DELETE FROM students')
 def test_sql_injection(self):
  with self.assertRaises(Exception): run_sql('SELECT * FROM students; DROP TABLE students')
if __name__=='__main__': unittest.main()
