
# -*- coding: utf-8 -*-
"""Безопасная самопроверка ANALYTICS AI."""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path


def main() -> int:
    print("=" * 58)
    print("ANALYTICS AI — ПРОВЕРКА МОДУЛЕЙ")
    print("=" * 58)

    try:
        from openpyxl import Workbook
        from .config import APP_TITLE, APP_VERSION
        from .excel_reader import read_excel
        from .analytics import analyze_matrix
        from .pdf_builder import build_analytics_pdf
        from .pptx_builder import build_analytics_pptx
        from .ai_interpreter import (
            _select_model_name, _compact_analysis, _build_prompt,
            _normalize_model_result,
        )

        print(f"[OK] Импорт модулей. {APP_TITLE} {APP_VERSION}")

        selected_model = _select_model_name(
            "qwen2.5:7b", ["qwen2.5:3b", "qwen2.5:7b"]
        )
        if selected_model != "qwen2.5:7b":
            raise RuntimeError("Автовыбор Ollama-модели работает неверно.")

        with tempfile.TemporaryDirectory(prefix="biq_report_test_") as temp:
            temp_dir = Path(temp)
            excel_path = temp_dir / "test_data.xlsx"
            output_dir = temp_dir / "reports"

            # Создаём только временный тестовый Excel.
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Данные"

            sheet.append(["Отдел", "Сотрудники", "План", "Факт"])
            sheet.append(["ИТ", 12, 100, 95])
            sheet.append(["Учебный", 20, 150, 143])
            sheet.append(["ИТ", 15, 120, 118])
            sheet.append(["Финансы", 8, 80, 76])
            sheet.append(["Учебный", 17, 140, 140])
            workbook.save(excel_path)
            workbook.close()

            print("[OK] Временный Excel создан.")

            # Проверяем чтение файла.
            loaded = read_excel(excel_path)

            if not loaded.get("sheets"):
                raise RuntimeError("Excel прочитан, но листы не найдены.")

            matrix = loaded["sheets"][0]["matrix"]

            if len(matrix) < 2:
                raise RuntimeError("В тестовом листе нет строк данных.")

            print(
                f"[OK] Excel прочитан: "
                f"{len(loaded['sheets'])} лист(ов)."
            )

            # Проверяем аналитический движок.
            analysis = analyze_matrix(matrix)

            print(
                f"[OK] Аналитика: {analysis['row_count']} записей, "
                f"{analysis['column_count']} столбцов, "
                f"{len(analysis['numeric_columns'])} числовых показателей."
            )

            if analysis["row_count"] != 5:
                raise RuntimeError(
                    f"Ожидалось 5 записей, получено "
                    f"{analysis['row_count']}."
                )

            if not analysis["numeric_columns"]:
                raise RuntimeError(
                    "Аналитика не распознала числовые столбцы."
                )

            audit = analysis.get("audit", {})
            if not isinstance(audit.get("score"), int):
                raise RuntimeError("Не рассчитан индекс качества данных.")
            if audit.get("grade") not in {"A", "B", "C", "D", "F"}:
                raise RuntimeError("Некорректный класс качества данных.")

            dirty = analyze_matrix([
                ["ID", "Сумма", "Статус"],
                *[[i, 100, "OK"] for i in range(1, 11)],
                [11, 999999, None],
                [11, 999999, None],
            ])
            codes = {item["code"] for item in dirty["audit"]["findings"]}
            if not {"MISSING_DATA", "DUPLICATES", "EXTREME_OUTLIERS"} <= codes:
                raise RuntimeError("Строгий аудит не выявил тестовые дефекты.")

            personal = analyze_matrix([
                ["Фамилия", "ID обучающегося", "Факультет"],
                *[[f"Студент {i}", 10000 + i, "Медицина" if i < 8 else "Фармация"]
                  for i in range(12)],
            ])
            if any(c.get("reportable") for c in personal["numeric_columns"]):
                raise RuntimeError("Идентификатор ошибочно включён в бизнес-статистику.")
            reportable_names = {c["name"] for c in personal["categorical_columns"]
                                if c.get("reportable")}
            if "Фамилия" in reportable_names or "Факультет" not in reportable_names:
                raise RuntimeError("Персональные поля не исключены из отчёта.")

            duplicated = analyze_matrix([
                ["Факультет", "Вид гранта", "Вид финансирования", "Дата"],
                ["Медицина", "Грант", "Грант", "2024-09-01"],
                ["Фармация", "Платно", "Платно", "2025-09-01"],
                ["Медицина", "Грант", "Грант", "2025-09-02"],
            ])
            duplicate_pairs = duplicated.get("quality", {}).get("duplicate_columns", [])
            if not any(item.get("column") == "Вид финансирования" for item in duplicate_pairs):
                raise RuntimeError("Аналитика не выявила дублирующие категориальные поля.")
            financing = next(
                item for item in duplicated["categorical_columns"]
                if item["name"] == "Вид финансирования"
            )
            if financing.get("reportable") or financing.get("duplicate_of") != "Вид гранта":
                raise RuntimeError("Дублирующее поле не исключено из страниц отчёта.")
            date_column = duplicated["date_columns"][0]
            if len(date_column.get("statistics", {}).get("year_counts", [])) != 2:
                raise RuntimeError("Годовая динамика по датам не рассчитана.")

            compact = _compact_analysis(matrix, analysis)
            prompt = _build_prompt(compact, "Тест", "Сравнить группы")
            if '"quality"' in prompt or '"missing"' in prompt:
                raise RuntimeError("ИИ получает технические показатели пустых ячеек.")
            filtered = _normalize_model_result({
                "domain": "тестовые данные",
                "report_title": "Проверка аналитики Qwen",
                "report_subtitle": "Группы, значения и статусы · 5 записей",
                "summary": "Есть 5 записей. Пустые ячейки мешают анализу.",
                "findings": ["Группа ИТ содержит 2 записи.", "Данные отсутствуют."],
                "risks": ["Пропуски снижают качество данных."],
                "recommendations": ["Провести анализ групп.", "Сопоставить план и факт."],
                "stories": [
                    {"topic": "Группа", "headline": "ИТ и Продажи формируют основной объём",
                     "evidence": "ИТ — 2 записи, Продажи — 2 записи.",
                     "interpretation": "Две группы имеют одинаковый масштаб.", "action": ""},
                    {"topic": "Значение", "headline": "Значения различаются между записями",
                     "evidence": "Диапазон значений рассчитан по 5 записям.",
                     "interpretation": "Разброс требует рассмотрения крайних значений.", "action": ""},
                ],
            }, "qwen2.5:7b")
            filtered_text = str(filtered).casefold()
            if any(word in filtered_text for word in ("пуст", "пропуск", "отсутств", "провести анализ")):
                raise RuntimeError("Фильтр ИИ не удалил технические шаблонные выводы.")

            # Регрессия LayoutError: модель может вернуть длинные карточки.
            # Генератор обязан ограничить их и завершить PDF, а не пытаться
            # поместить двухколоночную таблицу выше доступной страницы.
            if filtered.get("stories"):
                filtered["stories"][0]["interpretation"] = (
                    "Подробная интерпретация результата и его ограничений. " * 30
                )
                filtered["stories"][0]["action"] = (
                    "Проверяемое действие с ответственным и контрольным показателем. " * 25
                )

            # Проверяем создание PDF напрямую, без записи в историю.
            pdf_path = build_analytics_pdf(
                matrix=matrix,
                title="Проверка аналитического отчёта",
                source_name=excel_path.name,
                sheet_name="Данные",
                output_dir=output_dir,
                description="Автоматическая проверка модулей BahonIQ.",
                include_source_table=True,
                orientation="auto",
                ai_analysis=filtered,
            )

            if not pdf_path.is_file():
                raise RuntimeError("PDF-файл не найден после создания.")

            with pdf_path.open("rb") as pdf:
                signature = pdf.read(5)

            if signature != b"%PDF-":
                raise RuntimeError("Файл не имеет сигнатуры PDF.")

            print(f"[OK] PDF создан: {pdf_path.name}")
            print(f"[OK] Размер PDF: {pdf_path.stat().st_size:,} байт")

            if pdf_path.stat().st_size < 1000:
                raise RuntimeError("Размер PDF подозрительно мал.")

            # Кириллица должна быть встроена Unicode-шрифтом, а приложение
            # с исходными данными ограничено, чтобы PDF не разрастался.
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
            if "Аналитический отчёт" not in extracted:
                raise RuntimeError("Кириллица в PDF не извлекается корректно.")
            if len(reader.pages) > 18:
                raise RuntimeError("PDF превысил допустимый объём в 18 страниц.")

            pptx_path = build_analytics_pptx(
                matrix=matrix,
                title="Проверка аналитического отчёта",
                output_dir=output_dir,
                description="Автоматическая проверка презентации.",
                ai_analysis=filtered,
            )
            if not pptx_path.is_file() or pptx_path.read_bytes()[:2] != b"PK":
                raise RuntimeError("PowerPoint не создан или повреждён.")
            from pptx import Presentation
            deck = Presentation(str(pptx_path))
            if len(deck.slides) < 3:
                raise RuntimeError("В PowerPoint недостаточно аналитических слайдов.")
            print(f"[OK] PowerPoint создан: {pptx_path.name}")

            print()
            print("РЕЗУЛЬТАТ: ВСЕ ОСНОВНЫЕ ПРОВЕРКИ ПРОЙДЕНЫ.")
            print("Тестовые файлы будут удалены автоматически.")
            return 0

    except Exception as exc:
        print()
        print("[ОШИБКА] Проверка не пройдена.")
        print(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
