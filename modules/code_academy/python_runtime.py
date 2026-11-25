"""One real-Python process lifecycle for studio runs and lesson tests.

ВАЖНО: Temporary working directory, минимальный env и AST-проверка ограничивают
случайные побочные эффекты, но НЕ являются полноценной системной песочницей ОС.
"""
from pathlib import Path
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time

_MAX_CONCURRENT_RUNS = 4
_CONCURRENCY_SEM = threading.BoundedSemaphore(_MAX_CONCURRENT_RUNS)
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])


def _sanitize_traceback(text: str, temp_dir: str) -> str:
    """Убирает абсолютные серверные пути из traceback и stderr."""
    if not text:
        return ""
    cleaned = text.replace(temp_dir, "").replace(temp_dir.replace("\\", "/"), "")
    cleaned = cleaned.replace(_PROJECT_ROOT, "<workspace>").replace(_PROJECT_ROOT.replace("\\", "/"), "<workspace>")
    cleaned = re.sub(r'(?i)[a-z]:\\[^\s"\']+[\\/](main\.py)', r'\1', cleaned)
    cleaned = re.sub(r'(?i)(?:/opt|/app|/home|/tmp|/var)/[^\s"\']+/(main\.py)', r'\1', cleaned)
    cleaned = re.sub(r'(?i)[a-z]:\\Users\\[^\\/\s"\']+', r'<user>', cleaned)
    return cleaned


class RunningPython:
    def __init__(self, code, stdin='', interactive=False, timeout=10, max_output=50_000):
        from .pro_engine import validate_python_policy
        validate_python_policy(code, stdin=stdin)
        if not _CONCURRENCY_SEM.acquire(timeout=5):
            raise RuntimeError('Слишком много одновременных запусков Python. Повторите через секунду.')
        self._sem_released = False
        self.events = queue.Queue()
        self.stdout = ''; self.stderr = ''; self.returncode = None
        self.reason = ''; self.max_output = max_output
        self._lock = threading.Lock(); self._done = threading.Event()
        try:
            self._directory = tempfile.TemporaryDirectory(prefix='bahoniq_python_')
            self._temp_dir = self._directory.name
            path = Path(self._temp_dir) / 'main.py'
            path.write_text(code, encoding='utf-8')
            # Минимальное безопасное окружение без секретов (.env / API-ключей)
            env = {
                'PYTHONIOENCODING': 'utf-8',
                'PYTHONUTF8': '1',
                'PATH': os.environ.get('PATH', ''),
            }
            if os.name == 'nt' and 'SYSTEMROOT' in os.environ:
                env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            self.started = time.monotonic()
            # -I ignores PYTHON* environment variables. Force UTF-8 by command
            # line too, so Windows pipes cannot fall back to the ANSI codepage.
            self.process = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', '-u', '-B', str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace', cwd=self._temp_dir,
                env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            if hasattr(self, '_directory'):
                self._directory.cleanup()
            if not self._sem_released:
                self._sem_released = True
                _CONCURRENCY_SEM.release()
            raise
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
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        finally:
            self.close_input()
            for thread in self._readers: thread.join(timeout=2)
            with self._lock:
                self.stderr = _sanitize_traceback(self.stderr, self._temp_dir)
            self.returncode = self.process.returncode
            self.duration_ms = int((time.monotonic()-self.started)*1000)
            self._directory.cleanup()
            if not self._sem_released:
                self._sem_released = True
                _CONCURRENCY_SEM.release()
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
