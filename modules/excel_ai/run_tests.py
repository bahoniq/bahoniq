"""Run the bundled tests from an unpacked excel_ai directory or the main app."""
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    # Several older test files install sys.modules stubs. Separate processes
    # keep those stubs from affecting the new compiler and UI regression tests.
    bootstrap = '''import sys, types, unittest
from pathlib import Path
root = Path(sys.argv[1])
modules = types.ModuleType('modules')
modules.__path__ = [str(root.parent)]
sys.modules['modules'] = modules
sys.path.insert(0, str(root.parent))
suite = unittest.defaultTestLoader.loadTestsFromName('modules.excel_ai.' + sys.argv[2])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
'''
    failed = []
    tests = ['tests.' + p.stem for p in sorted((root/'tests').glob('test_*.py'))]
    tests.append('test_regression')
    for module in tests:
        completed = subprocess.run([sys.executable, '-c', bootstrap, str(root), module])
        if completed.returncode:
            failed.append(module)
    print('Failed modules: ' + ', '.join(failed) if failed else 'All test modules passed.')
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
