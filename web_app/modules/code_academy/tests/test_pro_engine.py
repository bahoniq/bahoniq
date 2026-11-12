import unittest

from code_academy.pro_engine import (
    PythonRunner, SQLExpectation, SQLRunner, TestCase, PythonPolicyError,
    validate_python_policy,
)


class PythonRunnerTests(unittest.TestCase):
    def test_real_python_functions_loops_and_input(self):
        code = """def double(value):\n    return value * 2\nprint(double(int(input())))\n"""
        report = PythonRunner().assess(code, (
            TestCase("positive", "4\n", "8"),
            TestCase("negative", "-3\n", "-6", hidden=True),
        ))
        self.assertTrue(report.passed, report)

    def test_wrong_output_fails(self):
        report = PythonRunner().assess("print('wrong')", (TestCase("expected", expected_stdout="right"),))
        self.assertFalse(report.passed)

    def test_dangerous_import_is_rejected(self):
        with self.assertRaises(PythonPolicyError):
            validate_python_policy("import subprocess")


class SQLRunnerTests(unittest.TestCase):
    def test_exact_result_passes(self):
        report = SQLRunner().assess(
            "SELECT title FROM tasks WHERE status='done' ORDER BY id",
            SQLExpectation(columns=("title",), rows=(("SQL",), ("Tkinter",))),
        )
        self.assertTrue(report.passed, report)

    def test_successful_but_wrong_query_fails(self):
        report = SQLRunner().assess(
            "SELECT title FROM tasks ORDER BY id",
            SQLExpectation(columns=("title",), rows=(("SQL",), ("Tkinter",))),
        )
        self.assertFalse(report.passed)

    def test_writes_are_denied(self):
        report = SQLRunner().assess("DELETE FROM tasks", SQLExpectation())
        self.assertFalse(report.passed)


if __name__ == "__main__":
    unittest.main()
