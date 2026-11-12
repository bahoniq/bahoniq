import unittest

from code_academy.adaptive_assessment import evaluate, generate
from code_academy.builder import GuidedProject
from code_academy.builder_pro import validate_project
from code_academy.professional_curriculum import PYTHON, SQL


class ProfessionalCurriculumTests(unittest.TestCase):
    def test_route_is_substantial_and_ordered(self):
        self.assertGreaterEqual(len(PYTHON), 45)
        self.assertGreaterEqual(len(SQL), 35)
        self.assertEqual([x.level for x in PYTHON], sorted(x.level for x in PYTHON))
        self.assertEqual([x.level for x in SQL], sorted(x.level for x in SQL))

    def test_python_foundation_types_are_explicit(self):
        titles=' '.join(x.title for x in PYTHON)
        for term in ('int','float','bool','None','str','bytes','list','tuple','set','dict','range'):
            self.assertIn(term,titles)

    def test_builder_contains_all_application_layers(self):
        files=GuidedProject().files
        for name in ('main.py','api/task_api.py','ui/main_window.py','services/task_service.py',
                     'data/task_repository.py','models/task.py','settings.py','tests/test_service.py'):
            self.assertIn(name,files)
        self.assertEqual(validate_project(files),[])

    def test_generated_python_variants_change(self):
        first=generate('python',101)
        second=generate('python',202)
        self.assertNotEqual(first.prompt,second.prompt)
        factor=int(first.prompt.split('value * ')[1].split(' ')[0])
        offset=int(first.prompt.split('+ ')[1].split('.')[0])
        answer=f'def transform(value):\n    return value * {factor} + {offset}\n\nfor _ in range(4):\n    print(transform(int(input())))\n'
        self.assertTrue(evaluate(first,answer)[0])

    def test_generated_sql_solution_is_semantic(self):
        task=generate('sql',303)
        threshold=int(task.prompt.split('не ниже ')[1].split('.')[0])
        answer=("SELECT u.name,COUNT(t.id) AS total FROM users u LEFT JOIN tasks t "
                f"ON t.user_id=u.id AND t.priority>={threshold} GROUP BY u.id,u.name "
                "ORDER BY total DESC,u.name")
        self.assertTrue(evaluate(task,answer)[0])


if __name__=='__main__':unittest.main()
