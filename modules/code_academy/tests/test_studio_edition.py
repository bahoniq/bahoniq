import ast
import queue
import time
import unittest
from code_academy.editor import syntax_tokens, indent_for
from code_academy.exercises import PYTHON, SQL, check_python_exercise, check_sql_exercise
from code_academy.pathway import steps, check_python, check_sql
from code_academy.python_runtime import RunningPython, execute_python


class ActivePracticeTests(unittest.TestCase):
    def test_every_active_lesson_has_contract(self):
        self.assertEqual({s.slug for s in steps('python')}, set(PYTHON))
        self.assertEqual({s.slug for s in steps('sql')}, set(SQL))
        for language in ('python','sql'):
            for s in steps(language):
                rule = (PYTHON if language=='python' else SQL)[s.slug]
                self.assertEqual(s.challenge,rule.prompt)

    def test_all_48_reference_solutions_pass_real_checks(self):
        for step in steps('python'):
            with self.subTest(lesson=step.slug):
                ok,msg=check_python(PYTHON[step.slug].solution,step)
                self.assertTrue(ok,msg)

    def test_trivial_print_cannot_complete_any_python_lesson(self):
        for step in steps('python'):
            with self.subTest(lesson=step.slug):
                self.assertFalse(check_python('print("ничего не решено")',step)[0])

    def test_all_35_sql_references_pass_real_checks(self):
        for step in steps('sql'):
            with self.subTest(lesson=step.slug):
                ok,msg=check_sql(SQL[step.slug].solution,step)
                self.assertTrue(ok,msg)

    def test_select_one_cannot_complete_any_sql_lesson(self):
        for step in steps('sql'):
            with self.subTest(lesson=step.slug):
                self.assertFalse(check_sql('SELECT 1',step)[0])

    def test_incorrect_boundary_fails(self):
        code=PYTHON['py13'].solution.replace('>=90','>90')
        self.assertFalse(check_python_exercise(code,'py13')[0])

    def test_function_hardcoded_for_one_input_fails(self):
        self.assertFalse(check_python_exercise('def discounted(price,percent): return 90','py23')[0])

    def test_valid_alternative_solution_passes(self):
        code='def discounted(price,percent):\n    discount=price*percent/100\n    return round(price-discount,2)'
        self.assertTrue(check_python_exercise(code,'py23')[0])

    def test_sql_missing_where_fails(self):
        self.assertFalse(check_sql_exercise('SELECT id,title FROM tasks ORDER BY id','sq03')[0])

    def test_sql_missing_constraint_fails(self):
        code=SQL['sq25'].solution.replace('CHECK(priority BETWEEN 1 AND 5)','')
        self.assertFalse(check_sql_exercise(code,'sq25')[0])

    def test_sql_attach_denied_and_failure_does_not_poison_next_run(self):
        self.assertFalse(check_sql_exercise("ATTACH ':memory:' AS external;",'sq24')[0])
        self.assertTrue(check_sql_exercise(SQL['sq24'].solution,'sq24')[0])

    def test_sql_ddl_changes_are_ephemeral(self):
        self.assertTrue(check_sql_exercise(SQL['sq27'].solution,'sq27')[0])
        self.assertTrue(check_sql_exercise(SQL['sq27'].solution,'sq27')[0])


class RuntimeTests(unittest.TestCase):
    def test_all_48_examples_run_in_shared_runtime(self):
        for step in steps('python'):
            with self.subTest(lesson=step.slug):
                run=execute_python(step.code)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertFalse(run.reason)

    def test_real_input_and_unicode(self):
        r=execute_python("name=input('Имя: ')\nprint('Сәлем,',name)",stdin='Дана\n')
        self.assertEqual(r.returncode,0)
        self.assertIn('Сәлем, Дана',r.stdout)

    def test_live_input_after_prompt(self):
        r=RunningPython("name=input('READY>')\nprint(name.upper())",interactive=True,timeout=3)
        self.addCleanup(r.stop)
        deadline=time.monotonic()+2
        while 'READY>' not in r.stdout and not r.finished and time.monotonic()<deadline:
            try:r.events.get(timeout=.1)
            except queue.Empty:pass
        self.assertIn('READY>',r.stdout)
        r.send_input('python');r.wait()
        self.assertIn('PYTHON',r.stdout);self.assertEqual(r.returncode,0)

    def test_timeout_stops_loop(self):
        r=execute_python('while True: pass',timeout=.15)
        self.assertIn('времени',r.reason)
        self.assertTrue(r.finished)

    def test_output_limit_stops_flood(self):
        r=execute_python('while True: print("x"*1000)',max_output=1500)
        self.assertIn('вывода',r.reason)
        self.assertLessEqual(len(r.stdout)+len(r.stderr),1500)

    def test_user_stop(self):
        r=RunningPython('input()',interactive=True,timeout=5)
        r.stop();r.wait()
        self.assertIn('пользователем',r.reason)

    def test_runtime_error_keeps_traceback(self):
        r=execute_python('print(1/0)')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('ZeroDivisionError',r.stderr)

    def test_temp_files_do_not_persist_between_runs(self):
        self.assertEqual(execute_python("from pathlib import Path\nPath('draft.txt').write_text('x')").returncode,0)
        self.assertEqual(execute_python("from pathlib import Path\nprint(Path('draft.txt').exists())").stdout.strip(),'False')


class EditorTokenTests(unittest.TestCase):
    def test_python_lexical_categories(self):
        code='if True:\n    print("hello", 42) # note\n'
        tagged=[(tag,code[a:b]) for tag,a,b in syntax_tokens(code)]
        for item in [('keyword','if'),('keyword','True'),('builtin','print'),('string','"hello"'),('number','42'),('comment','# note')]:
            self.assertIn(item,tagged)

    def test_no_keywords_inside_strings_or_comments(self):
        code='"if print 42" # def\n'
        self.assertTrue(all(tag in {'string','comment'} for tag,_,_ in syntax_tokens(code)))

    def test_incomplete_python_is_editable(self):
        for code in ['def foo(', 'text="', 'if True:\n  x=1\n y=2', "'''unfinished"]:
            self.assertIsInstance(syntax_tokens(code),list)

    def test_sql_comments_strings_keywords(self):
        code="SELECT title FROM tasks WHERE title='FROM' -- SELECT\n"
        tagged=[(tag,code[a:b]) for tag,a,b in syntax_tokens(code,'sql')]
        self.assertIn(('string',"'FROM'"),tagged)
        self.assertIn(('comment','-- SELECT'),tagged)
        self.assertIn(('keyword','SELECT'),tagged)

    def test_json_booleans_and_strings(self):
        code='{"active":true,"count":12,"name":"null"}'
        tagged=[(tag,code[a:b]) for tag,a,b in syntax_tokens(code,'json')]
        self.assertIn(('keyword','true'),tagged)
        self.assertIn(('string','"null"'),tagged)
        self.assertIn(('number','12'),tagged)

    def test_autoindent(self):
        self.assertEqual(indent_for('    if x:'),'        ')
        self.assertEqual(indent_for('    print(x)'),'    ')


if __name__=='__main__':unittest.main()
