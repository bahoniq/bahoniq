import tempfile
import unittest
from pathlib import Path

from modules.excel_ai import TaskEngine, TaskStatus


class TaskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = TaskEngine(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_create_and_event(self):
        task = self.engine.create_task("Найти пустые ячейки")
        self.assertEqual(task.status, TaskStatus.CREATED)
        self.assertEqual(len(self.engine.get_events(task.id)), 1)

    def test_complete_task(self):
        task = self.engine.create_task("Проверить таблицу")
        for status in (
            TaskStatus.ANALYZING, TaskStatus.PLANNED,
            TaskStatus.QUEUED, TaskStatus.RUNNING,
            TaskStatus.VERIFYING, TaskStatus.COMPLETED,
        ):
            task = self.engine.transition(task.id, status)
        self.assertEqual(task.status, TaskStatus.COMPLETED)

    def test_invalid_transition(self):
        task = self.engine.create_task("Проверить таблицу")
        with self.assertRaises(ValueError):
            self.engine.transition(task.id, TaskStatus.COMPLETED)

    def test_blank_instruction(self):
        with self.assertRaises(ValueError):
            self.engine.create_task("  ")

    def test_recovery_limit(self):
        task = self.engine.create_task("Тест восстановления")
        for status in (
            TaskStatus.ANALYZING, TaskStatus.PLANNED,
            TaskStatus.QUEUED, TaskStatus.RUNNING,
        ):
            task = self.engine.transition(task.id, status)

        for attempt in range(3):
            task = self.engine.transition(task.id, TaskStatus.RECOVERY)
            if attempt < 2:
                task = self.engine.transition(task.id, TaskStatus.QUEUED)
                task = self.engine.transition(task.id, TaskStatus.RUNNING)

        with self.assertRaises(ValueError):
            self.engine.transition(task.id, TaskStatus.RECOVERY)


if __name__ == "__main__":
    unittest.main()
