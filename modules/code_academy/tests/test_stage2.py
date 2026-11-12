import unittest
from code_academy.case_studies import cases
from code_academy.runners import run_python,run_sql
class Stage2Tests(unittest.TestCase):
 def test_all_cases_run(self):
  for kind in ('python','sql'):
   for case in cases(kind):
    with self.subTest(case=case.title):
     actual=(run_python if kind=='python' else run_sql)(case.code)
     self.assertEqual(actual.strip(),case.expected.strip())
 def test_depth(self):
  for kind in ('python','sql'):
   self.assertGreaterEqual(len(cases(kind)),3)
   for case in cases(kind):
    self.assertGreaterEqual(len(case.code.splitlines()),5)
    self.assertGreater(len(case.explain),80)
if __name__=='__main__':unittest.main()
