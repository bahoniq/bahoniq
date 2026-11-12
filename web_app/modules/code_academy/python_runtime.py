"""One real-Python process lifecycle for studio runs and lesson tests.

Temporary working directory and policy checks limit accidental effects; these
are not an OS security sandbox. Only run the learner's own trusted code.
"""
from pathlib import Path
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time


class RunningPython:
    def __init__(self, code, stdin='', interactive=False, timeout=10, max_output=50_000):
        from .pro_engine import validate_python_policy
        validate_python_policy(code)
        self.events = queue.Queue()
        self.stdout = ''; self.stderr = ''; self.returncode = None
        self.reason = ''; self.max_output = max_output
        self._lock = threading.Lock(); self._done = threading.Event()
        self._directory = tempfile.TemporaryDirectory(prefix='bahoniq_python_')
        path = Path(self._directory.name) / 'main.py'
        path.write_text(code, encoding='utf-8')
        env = os.environ.copy()
        env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        self.started = time.monotonic()
        try:
            # -I ignores PYTHON* environment variables. Force UTF-8 by command
            # line too, so Windows pipes cannot fall back to the ANSI codepage.
            self.process = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', '-u', '-B', str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace', cwd=self._directory.name,
                env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            self._directory.cleanup(); raise
        self._readers = []
        for stream in ('stdout','stderr'):
            thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
            thread.start(); self._readers.append(thread)
        if stdin:
            self.process.stdin.write(stdin); self.process.stdin.flush()
        if not interactive: self.close_input()
        threading.Thread(target=self._watch, args=(timeout,), daemon=True).start()

    def _read(self, stream):
        pipe = getattr(self.process, stream)
        try:
            while True:
                char = pipe.read(1)
                if not char: break
                with self._lock:
                    count = len(self.stdout) + len(self.stderr)
                    if count >= self.max_output:
                        self.stop('Превышен лимит вывода'); break
                    setattr(self, stream, getattr(self, stream) + char)
                self.events.put((stream, char))
        finally:
            pipe.close()

    def _watch(self, timeout):
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop('Превышен лимит времени выполнения')
            self.process.wait()
        finally:
            self.close_input()
            for thread in self._readers: thread.join(timeout=2)
            self.returncode = self.process.returncode
            self.duration_ms = int((time.monotonic()-self.started)*1000)
            self._directory.cleanup()
            self._done.set(); self.events.put(('done', self.returncode))

    def send_input(self, text):
        if self.process.poll() is not None: raise ValueError('Программа уже завершена.')
        try:
            self.process.stdin.write(text + '\n'); self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise ValueError('Ввод закрыт.') from exc

    def close_input(self):
        try:
            if self.process.stdin and not self.process.stdin.closed: self.process.stdin.close()
        except OSError: pass

    def stop(self, reason='Остановлено пользователем'):
        if self.process.poll() is None:
            self.reason = reason
            try: self.process.kill()
            except OSError: pass

    def wait(self):
        self._done.wait()
        return self

    @property
    def finished(self): return self._done.is_set()


def execute_python(code, stdin='', timeout=3, max_output=50_000):
    return RunningPython(code, stdin=stdin, timeout=timeout, max_output=max_output).wait()
