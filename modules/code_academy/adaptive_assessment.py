"""Generated competency checks: no fixed answer bank to memorise."""
from __future__ import annotations
from dataclasses import dataclass
import random
from .pro_engine import PythonRunner, SQLExpectation, SQLRunner, TestCase


@dataclass(frozen=True)
class GeneratedTask:
    task_id: str
    track: str
    title: str
    prompt: str
    starter: str
    seed: int
    expected: object


def generate(track: str, seed: int | None = None) -> GeneratedTask:
    rng=random.Random(seed)
    actual_seed=seed if seed is not None else rng.randrange(1,2_000_000_000)
    rng.seed(actual_seed)
    if track=='python':
        factor=rng.choice([2,3,4,5,7]);offset=rng.randint(-9,12)
        values=[rng.randint(-20,40) for _ in range(4)]
        expected='\n'.join(str(value*factor+offset) for value in values)
        prompt=(f'Напиши функцию transform(value), которая возвращает value * {factor} + {offset}. '
                f'Программа должна читать целые числа до конца ввода и печатать результат для каждого. '
                'Не подставляй конкретные тестовые числа: при следующей попытке они изменятся.')
        starter='def transform(value):\n    # напиши решение\n    pass\n\nfor _ in range(4):\n    print(transform(int(input())))\n'
        return GeneratedTask(f'python-{actual_seed}','python','Сгенерированная функция',prompt,starter,actual_seed,
                             TestCase('Скрытые данные','\n'.join(map(str,values))+'\n',expected,hidden=True))
    if track=='sql':
        threshold=rng.choice([2,3,4,5])
        rows=SQLRunner().execute(
            f"SELECT u.name,COUNT(t.id) AS total FROM users u LEFT JOIN tasks t ON t.user_id=u.id AND t.priority>={threshold} GROUP BY u.id,u.name ORDER BY total DESC,u.name",
            explain=False).rows
        prompt=(f'Покажи имя каждого пользователя и количество его задач с приоритетом не ниже {threshold}. '
                'Пользователи без таких задач должны остаться. Столбцы: name, total. '
                'Сортировка: total по убыванию, затем name по возрастанию.')
        return GeneratedTask(f'sql-{actual_seed}','sql','Сгенерированный SQL-отчёт',prompt,'',actual_seed,
                             SQLExpectation(('name','total'),rows))
    raise ValueError('track должен быть python или sql')


def evaluate(task: GeneratedTask, answer: str):
    if task.track=='python':
        report=PythonRunner().assess(answer,(task.expected,))
        return report.passed,report.message
    report=SQLRunner().assess(answer,task.expected)
    return report.passed,report.message
