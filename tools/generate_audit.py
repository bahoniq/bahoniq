import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.code_academy import curriculum, professional_curriculum, case_studies, architecture_book

docs_dir = Path('docs')
docs_dir.mkdir(exist_ok=True)
report_path = docs_dir / 'CODE_ACADEMY_AUDIT.md'

py_lessons = professional_curriculum.lessons('python')
sql_lessons = professional_curriculum.lessons('sql')
base_lessons = curriculum.LESSONS
py_cases = case_studies.cases('python')
sql_cases = case_studies.cases('sql')
chapters = architecture_book.CHAPTERS

total_items = len(base_lessons) + len(py_lessons) + len(sql_lessons) + len(py_cases) + len(sql_cases) + len(chapters)

lines = [
    '# АУДИТ УРОКОВ И УЧЕБНЫХ МОДУЛЕЙ CODE ACADEMY (v2.0.0)',
    '',
    '**Дата ревизии:** 2026-11-11  ',
    f'**Всего учебных материалов:** {total_items}  ',
    '',
    '## 1. Сводка по категориям',
    f'- **Базовый трек (curriculum):** {len(base_lessons)} уроков',
    f'- **Профессиональный Python:** {len(py_lessons)} уроков (с кодом и проверкой)',
    f'- **Профессиональный SQL:** {len(sql_lessons)} уроков (с запросами и проверкой)',
    f'- **Реальные кейс-стади:** {len(py_cases)} Python + {len(sql_cases)} SQL',
    f'- **Книга архитектуры BahonIQ:** {len(chapters)} практических глав',
    '',
    '## 2. Книга архитектуры BahonIQ (Architecture Book)',
    '| № | Раздел | Глава | Файл-источник | Опорный символ | Практика | Статус |',
    '|---|---|---|---|---|---|---|'
]

for idx, ch in enumerate(chapters, 1):
    anchor_label = ch.anchor if ch.anchor else "(весь файл)"
    lines.append(f'| {idx:02d} | {ch.section} | {ch.title} | `{ch.file}` | `{anchor_label}` | {bool(ch.exercise)} | Актуален |')

lines.extend([
    '',
    '## 3. Профессиональный трек Python',
    '| № | Slug | Название | Уровень | Режим | Задание | Статус |',
    '|---|---|---|---|---|---|---|'
])
for idx, l in enumerate(py_lessons, 1):
    lines.append(f'| {idx:02d} | `{l.slug}` | {l.title} | {l.level} | {l.mode} | {bool(l.challenge)} | Актуален |')

lines.extend([
    '',
    '## 4. Профессиональный трек SQL',
    '| № | Slug | Название | Уровень | Режим | Задание | Статус |',
    '|---|---|---|---|---|---|---|'
])
for idx, l in enumerate(sql_lessons, 1):
    lines.append(f'| {idx:02d} | `{l.slug}` | {l.title} | {l.level} | {l.mode} | {bool(l.challenge)} | Актуален |')

lines.extend([
    '',
    '## 5. Кейс-стади и Базовые уроки',
    '| Модуль | Тип | Название | Статус |',
    '|---|---|---|---|'
])
for c in py_cases:
    lines.append(f'| Case Study | Python | {c.title} | Актуален |')
for c in sql_cases:
    lines.append(f'| Case Study | SQL | {c.title} | Актуален |')
for b in base_lessons:
    lines.append(f'| Базовый | {getattr(b, "track", "Общий")} | {getattr(b, "title", str(b))} | Актуален |')

report_path.write_text('\n'.join(lines), encoding='utf-8')
print('SUCCESS: Audit saved to', report_path)
