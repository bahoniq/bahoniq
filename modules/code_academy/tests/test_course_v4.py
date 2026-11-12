import unittest
from code_academy.course_v4 import lessons
from code_academy.runners import run_python, run_sql

class CourseV4Tests(unittest.TestCase):
    def test_catalog(self):
        self.assertGreaterEqual(len(lessons('python')), 20)
        self.assertGreaterEqual(len(lessons('sql')), 20)
        self.assertEqual(len({x.slug for x in lessons('python')+lessons('sql')}),len(lessons('python')+lessons('sql')))
    def test_all_python_examples(self):
        for lesson in lessons('python'):
            with self.subTest(lesson=lesson.slug):
                result=run_python(lesson.example)
                self.assertEqual(result.strip(),lesson.expected.strip())
    def test_all_sql_examples(self):
        def norm(text):return ' '.join(text.replace('|',' ').replace(';',' ').split())
        for lesson in lessons('sql'):
            with self.subTest(lesson=lesson.slug):
                result=run_sql(lesson.example)
                self.assertEqual(norm(result),norm(lesson.expected))
if __name__=='__main__':unittest.main()
