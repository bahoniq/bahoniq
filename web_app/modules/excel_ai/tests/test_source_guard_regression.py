import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
from modules.excel_ai.engine import TaskEngine
from modules.excel_ai.workflow import ExcelWorkflow
import modules.excel_ai.workflow as workflow_module

class SourceGuardRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / 'input.xlsx'
        book = Workbook(); book.active.append(['Faculty','Count']); book.active.append(['A', 1]); book.save(self.source); book.close()
        self.workflow = ExcelWorkflow(TaskEngine(root / 'tasks.sqlite3'))
        self.ops = [{'type':'smart_summary','sheet':'Sheet','columns':[1], 'include_charts':True}]

    def test_metadata_change_does_not_invalidate_plan(self):
        task = self.workflow.create_task('report',self.source)
        original = workflow_module.plan_operations
        def touch(*args,**kwargs):
            result = original(*args,**kwargs)
            st = self.source.stat()
            os.utime(self.source, ns=(st.st_atime_ns,st.st_mtime_ns+2_000_000_000))
            return result
        with patch.object(workflow_module,'plan_operations',side_effect=touch):
            plan = self.workflow.prepare(task.id,self.ops)['plan']
        self.assertEqual(plan['source_sha256'],self.workflow._file_fingerprint(self.source))

    def test_real_content_change_blocks_plan(self):
        task = self.workflow.create_task('report',self.source)
        original = workflow_module.plan_operations
        def mutate(*args,**kwargs):
            result = original(*args,**kwargs)
            with self.source.open('ab') as f: f.write(b'changed')
            return result
        with patch.object(workflow_module,'plan_operations',side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError,'SHA-256'):
                self.workflow.prepare(task.id,self.ops)

if __name__=='__main__': unittest.main()
