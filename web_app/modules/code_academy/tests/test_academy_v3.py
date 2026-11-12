import unittest
import tempfile
from pathlib import Path
from code_academy.studio_core import Workspace, preview_settings, apply_visual_settings, check_project
from code_academy.architecture import read_project_file, describe_code
from code_academy.runners import run_python, run_sql

class AcademyV3Tests(unittest.TestCase):
    def test_project_valid(self):
        w=Workspace();self.assertEqual(check_project(w.project.files),[])
    def test_preview(self):
        self.assertEqual(preview_settings(Workspace().project.files)['WIDTH'],760)
    def test_visual_changes_code(self):
        w=Workspace();s=apply_visual_settings(w.project,'Учебное окно',820,510,'#245E8A','Старт','Добро пожаловать')
        self.assertEqual(s['WIDTH'],820);self.assertEqual(s['BUTTON_TEXT'],'Старт');self.assertIn('820',w.project.files['settings.py'])
        self.assertEqual(check_project(w.project.files),[])
    def test_invalid_color(self):
        with self.assertRaises(ValueError):apply_visual_settings(Workspace().project,'X',700,450,'red','a','b')
    def test_invalid_size(self):
        with self.assertRaises(ValueError):apply_visual_settings(Workspace().project,'X',10,450,'#009246','a','b')
    def test_python_runner(self):self.assertEqual(run_python('x=2\nprint(x+3)'),'5')
    def test_python_blocks_import(self):
        with self.assertRaises(ValueError):run_python('import os')
    def test_sql_query(self):self.assertIn('Алия',run_sql('SELECT name FROM students'))
    def test_sql_write_denied(self):
        with self.assertRaises(Exception):run_sql('DELETE FROM students')
    def test_export_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'new';w=Workspace();w.export(path)
            self.assertTrue((path/'main.py').exists())
            with self.assertRaises(FileExistsError):w.export(path)
    def test_architecture_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):read_project_file('../outside.py',root=temp)
    def test_architecture_readonly(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'main.py';path.write_text('print(42)')
            self.assertEqual(read_project_file('main.py',root=temp),'print(42)')
    def test_describe(self):self.assertIn('start',describe_code('def start(): pass'))
    def test_ui_import(self):
        from code_academy.ui import AcademyWindow, open_code_academy
        self.assertTrue(callable(open_code_academy))

if __name__=='__main__':unittest.main()
