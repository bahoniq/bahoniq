import unittest
import tempfile
from pathlib import Path
from code_academy.builder import GuidedProject, TEMPLATES, line_explanation

class BuilderTests(unittest.TestCase):
    def test_template_files(self):
        p=GuidedProject()
        for name in ('main.py','app/application.py','api/task_api.py','models/task.py','services/task_service.py','data/task_repository.py','ui/main_window.py','settings.py','tests/test_service.py'):
            self.assertIn(name,p.files)
    def test_syntax_rejected(self):
        p=GuidedProject()
        with self.assertRaises(SyntaxError):p.update('main.py','def bad(:')
    def test_unknown_file_rejected(self):
        with self.assertRaises(ValueError):GuidedProject().update('../danger.py','print(1)')
    def test_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'project'; p=GuidedProject();p.export(root)
            self.assertEqual((root/'main.py').read_text(encoding='utf-8'),TEMPLATES['main.py'])
            with self.assertRaises(FileExistsError):p.export(root)
    def test_line_explanation(self):
        self.assertIn('Размер',line_explanation('ui/main_window.py','root.geometry("700x450")'))
    def test_update_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            p=GuidedProject();p.update('settings.py','from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Settings:\n    title: str = "Урок"\n    width: int = 800\n    height: int = 500\n    accent: str = "#009246"\n    database_path: str = "tasks.db"\n')
            p.export(Path(d)/'project')
            self.assertIn('width: int = 800',(Path(d)/'project'/'settings.py').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
