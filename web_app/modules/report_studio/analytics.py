
# -*- coding: utf-8 -*-
"""Аналитика данных ANALYTICS AI."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from math import sqrt
from statistics import median
from typing import Any

from .excel_reader import analyze_sheet_matrix


MAX_INSIGHTS = 18
MAX_DISTRIBUTIONS = 10
MAX_RANKINGS = 20
MAX_CATEGORIES = 10
MAX_TOP_VALUES = 10
MAX_AUDIT_FINDINGS = 20

SENSITIVE_HEADER_MARKERS = (
    "фамил", "имя", "отчеств", "фио", "иин", "телефон", "email",
    "e-mail", "адрес", "паспорт", "удостовер", "имя на латинице",
)
IDENTIFIER_HEADER_MARKERS = (
    " id", "id ", "id_", "_id", "идентификатор", "код обуч", "номер записи",
)


def _is_empty(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _display(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        result = value.strftime("%d.%m.%Y %H:%M:%S")
    elif isinstance(value, date):
        result = value.strftime("%d.%m.%Y")
    else:
        result = str(value).strip()

    if len(result) > limit:
        result = result[:limit].rstrip() + "…"

    return result


def _numeric(value: Any) -> float | None:
    """Преобразует числовые значения, не считая bool числом."""

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        try:
            result = float(value)
            if result == result and abs(result) != float("inf"):
                return result
        except (TypeError, ValueError, OverflowError):
            return None

    if isinstance(value, str):
        raw = value.strip().replace("\u00a0", "").replace(" ", "")

        if not raw:
            return None

        # Поддерживаем распространённые десятичные разделители.
        if "," in raw and "." not in raw:
            raw = raw.replace(",", ".")

        try:
            result = float(raw)
            if result == result and abs(result) != float("inf"):
                return result
        except (TypeError, ValueError, OverflowError):
            return None

    return None


def _percent(part: int | float, total: int | float) -> float:
    return round(part * 100 / total, 2) if total else 0.0


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw[:10], fmt).date()
            except ValueError:
                continue
    return None


def _column_role(header: str, unique_count: int, row_count: int) -> str:
    normalized = " " + header.casefold().strip() + " "
    if any(marker in normalized for marker in SENSITIVE_HEADER_MARKERS):
        return "sensitive"
    if any(marker in normalized for marker in IDENTIFIER_HEADER_MARKERS):
        return "identifier"
    if row_count >= 20 and unique_count / row_count >= 0.95:
        return "high_cardinality"
    return "dimension"


def _numeric_identifier_like(header: str) -> bool:
    """Определяет числовые идентификаторы по смыслу заголовка, а не уникальности.

    Непрерывные показатели (население, площадь, сумма, балл и т. п.) почти
    всегда уникальны. Поэтому доля уникальных значений сама по себе не должна
    исключать числовой столбец из аналитики.
    """
    normalized = " " + header.casefold().strip() + " "
    return any(marker in normalized for marker in (
        *SENSITIVE_HEADER_MARKERS,
        *IDENTIFIER_HEADER_MARKERS,
        " иин ", " бин ", " isbn ", " артикул ", " штрихкод ",
        " номер записи ", " регистрационный номер ",
    ))


def _unique_headers(headers: list[str]) -> list[str]:
    """Делает повторяющиеся заголовки уникальными."""

    result: list[str] = []
    counts: Counter[str] = Counter()

    for index, header in enumerate(headers):
        base = header.strip() or f"Столбец {index + 1}"
        counts[base] += 1

        if counts[base] == 1:
            result.append(base)
        else:
            candidate = f"{base} ({counts[base]})"
            while candidate in result:
                counts[base] += 1
                candidate = f"{base} ({counts[base]})"
            result.append(candidate)

    return result


def _quartile(sorted_values: list[float], fraction: float) -> float:
    """Интерполирует квартиль по отсортированному ряду."""

    if not sorted_values:
        return 0.0

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower

    return (
        sorted_values[lower] * (1 - weight)
        + sorted_values[upper] * weight
    )


def _numeric_statistics(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    count = len(ordered)

    if not count:
        return {
            "count": 0,
            "sum": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std_dev": None,
            "range": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "outlier_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "zero_count": 0,
        }

    mean_value = sum(ordered) / count
    q1 = _quartile(ordered, 0.25)
    q3 = _quartile(ordered, 0.75)
    iqr = q3 - q1

    low_limit = q1 - 1.5 * iqr
    high_limit = q3 + 1.5 * iqr

    outlier_count = sum(
        value < low_limit or value > high_limit
        for value in ordered
    )
    extreme_low = q1 - 3 * iqr
    extreme_high = q3 + 3 * iqr
    extreme_outlier_count = sum(
        value < extreme_low or value > extreme_high for value in ordered
    )

    variance = sum(
        (value - mean_value) ** 2 for value in ordered
    ) / count

    return {
        "count": count,
        "sum": round(sum(ordered), 6),
        "min": ordered[0],
        "max": ordered[-1],
        "mean": round(mean_value, 6),
        "median": round(float(median(ordered)), 6),
        "std_dev": round(sqrt(variance), 6),
        "range": round(ordered[-1] - ordered[0], 6),
        "q1": round(q1, 6),
        "q3": round(q3, 6),
        "iqr": round(iqr, 6),
        "outlier_count": outlier_count,
        "outlier_percent": _percent(outlier_count, count),
        "extreme_outlier_count": extreme_outlier_count,
        "positive_count": sum(value > 0 for value in ordered),
        "negative_count": sum(value < 0 for value in ordered),
        "zero_count": sum(value == 0 for value in ordered),
    }


def _numeric_display_metadata(
    header: str, values: list[float], stats: dict[str, Any],
) -> dict[str, Any]:
    """Определяет масштаб и единицы без передачи этой задачи языковой модели."""
    normalized = header.casefold().replace("ё", "е")
    minimum = stats.get("min")
    maximum = stats.get("max")
    percent_marker = any(marker in normalized for marker in (
        "%", "процент", "доля", "урбанизац", "rate", "share", "ratio",
    ))
    if (
        percent_marker and minimum is not None and maximum is not None
        and 0 <= float(minimum) and float(maximum) <= 1.000001
    ):
        return {
            "scale": "ratio", "display_as": "percent", "unit": "%",
            "multiplier": 100.0,
            "note": "Значения хранятся как доли единицы; 0.63 отображается как 63%.",
        }
    if percent_marker:
        return {
            "scale": "percent", "display_as": "percent", "unit": "%",
            "multiplier": 1.0,
        }

    largest = max((abs(float(value)) for value in values), default=0.0)
    if largest >= 1_000_000_000_000:
        divisor, suffix = 1_000_000_000_000.0, "трлн"
    elif largest >= 1_000_000_000:
        divisor, suffix = 1_000_000_000.0, "млрд"
    elif largest >= 1_000_000:
        divisor, suffix = 1_000_000.0, "млн"
    elif largest >= 10_000:
        divisor, suffix = 1_000.0, "тыс."
    else:
        divisor, suffix = 1.0, ""
    return {
        "scale": "number", "display_as": "number", "unit": "",
        "multiplier": 1.0, "chart_divisor": divisor,
        "chart_suffix": suffix,
    }


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)


def _build_audit(row_count, column_count, quality, columns) -> dict[str, Any]:
    """Формирует строгий аудиторский вердикт и приоритеты исправления."""
    findings: list[dict[str, Any]] = []

    def add(severity, code, title, evidence, action):
        findings.append({"severity": severity, "code": code, "title": title,
                         "evidence": evidence, "action": action})

    empty_percent = float(quality.get("empty_percent", 0) or 0)
    duplicate_percent = float(quality.get("duplicate_row_percent", 0) or 0)
    if not row_count:
        add("critical", "EMPTY_DATA", "Нет строк данных", "0 записей.",
            "Остановить использование отчёта и загрузить корректный набор.")
    if row_count and row_count < 10:
        add("medium", "SMALL_SAMPLE", "Крайне малая выборка",
            f"Всего {row_count} записей.", "Не обобщать выводы без расширения выборки.")
    severity = ("critical" if empty_percent >= 30 else "high" if empty_percent >= 10
                else "medium" if empty_percent > 0 else "")
    if severity:
        add(severity, "MISSING_DATA", "Пропуски снижают надёжность",
            f"Пусто {quality.get('empty_cells', 0)} ячеек ({empty_percent}%).",
            "Установить причины пропусков, правила заполнения и владельца данных.")
    if duplicate_percent:
        add("high" if duplicate_percent >= 5 else "medium", "DUPLICATES",
            "Повторные записи искажают агрегаты",
            f"Дубликаты: {quality.get('duplicate_rows', 0)} ({duplicate_percent}%).",
            "Дедуплицировать по бизнес-ключу и пересчитать показатели.")
    if quality.get("duplicate_headers"):
        add("high", "DUPLICATE_HEADERS", "Неоднозначные заголовки",
            ", ".join(quality["duplicate_headers"][:5]),
            "Переименовать поля в источнике; автосуффиксы не исправляют семантику.")
    if quality.get("constant_columns"):
        add("low", "CONSTANT_COLUMNS", "Столбцы не несут аналитической ценности",
            ", ".join(quality["constant_columns"][:8]),
            "Удалить поля из витрины либо документировать их назначение.")
    if quality.get("duplicate_columns"):
        evidence = "; ".join(
            f"{item['column']} совпадает с {item['duplicate_of']}"
            for item in quality["duplicate_columns"][:5]
        )
        add("medium", "DUPLICATE_COLUMNS", "Дублирующие аналитические поля",
            evidence,
            "Оставить один источник признака либо документировать различие полей.")
    for column in columns:
        name = str(column.get("name", "Показатель"))
        mixed = float(column.get("mixed_type_percent", 0) or 0)
        if mixed >= 5:
            add("high", "MIXED_TYPES", f"Смешанные типы: «{name}»",
                f"Значений другого типа: {mixed}%.",
                "Привести столбец к единому типу и проверить отклонённые значения.")
        stats = column.get("statistics", {})
        extreme = int(stats.get("extreme_outlier_count", 0) or 0)
        if extreme:
            add("high", "EXTREME_OUTLIERS", f"Экстремальные значения: «{name}»",
                f"За пределами 3 IQR: {extreme}.",
                "Проверить первичные записи; до проверки не использовать их в KPI.")
        if column.get("identifier_like"):
            add("medium", "NUMERIC_IDENTIFIER", f"Числовой идентификатор: «{name}»",
                "Почти все значения уникальны; арифметика по полю бессмысленна.",
                "Пометить поле как идентификатор и исключить из сумм/средних.")
    penalty = min(45, empty_percent * 1.5) + min(25, duplicate_percent * 2)
    penalty += min(10, len(quality.get("duplicate_headers", [])) * 5)
    penalty += min(10, len(quality.get("constant_columns", [])) * 2)
    penalty += min(6, len(quality.get("duplicate_columns", [])) * 2)
    base_codes = {"MISSING_DATA", "DUPLICATES", "DUPLICATE_HEADERS", "CONSTANT_COLUMNS"}
    penalty += min(20, sum(8 if f["severity"] == "critical" else 5 if f["severity"] == "high" else 2 if f["severity"] == "medium" else 0 for f in findings if f["code"] not in base_codes))
    score = max(0, round(100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    decision = ("ДАННЫЕ ПРИГОДНЫ ДЛЯ РЕШЕНИЙ" if score >= 90 else
                "ПРИГОДНЫ С ОГОВОРКАМИ" if score >= 75 else
                "ТРЕБУЮТ ОЧИСТКИ ДО ИСПОЛЬЗОВАНИЯ" if score >= 60 else
                "НЕПРИГОДНЫ ДЛЯ УПРАВЛЕНЧЕСКИХ РЕШЕНИЙ")
    findings.sort(key=lambda x: (_severity_rank(x["severity"]), x["code"], x["title"]))
    return {"score": score, "grade": grade, "decision": decision,
            "critical_count": sum(f["severity"] == "critical" for f in findings),
            "high_count": sum(f["severity"] == "high" for f in findings),
            "findings": findings[:MAX_AUDIT_FINDINGS]}


def _column_kind(values: list[Any]) -> str:
    """Определяет преобладающий тип непустых значений."""

    nonempty = [value for value in values if not _is_empty(value)]

    if not nonempty:
        return "empty"

    date_count = sum(_parse_date(value) is not None for value in nonempty)

    if date_count / len(nonempty) >= 0.7:
        return "date"

    numeric_count = sum(
        _numeric(value) is not None for value in nonempty
    )

    if numeric_count / len(nonempty) >= 0.7:
        return "numeric"

    return "categorical"


def _categorical_statistics(values: list[Any]) -> dict[str, Any]:
    """Рассчитывает частоты категорий."""

    nonempty = [_display(value) for value in values if not _is_empty(value)]
    counts = Counter(nonempty)
    top = counts.most_common(MAX_TOP_VALUES)

    return {
        "count": len(nonempty),
        "unique_count": len(counts),
        "top_values": [
            {"value": value, "count": count}
            for value, count in top
        ],
        "top_value_percent": (
            _percent(top[0][1], len(nonempty)) if top else 0
        ),
        "diversity_index": (
            round(len(counts) / len(nonempty), 4)
            if nonempty else 0
        ),
        "concentrated": (
            bool(top) and _percent(top[0][1], len(nonempty)) >= 70
        ),
    }


def _date_statistics(values: list[Any], column_name: str = "") -> dict[str, Any]:
    dates = [parsed for value in values if (parsed := _parse_date(value))]

    if not dates:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "unique_count": 0,
            "span_days": 0,
        }

    unique_dates = set(dates)
    minimum = min(dates)
    maximum = max(dates)

    result = {
        "count": len(dates),
        "min": minimum.isoformat(),
        "max": maximum.isoformat(),
        "unique_count": len(unique_dates),
        "span_days": (maximum - minimum).days,
        "year_counts": [
            {"value": str(year), "count": count}
            for year, count in sorted(Counter(item.year for item in dates).items())
        ],
    }
    today = date.today()
    if 1900 <= minimum.year <= today.year and maximum <= today:
        dated_ages = [(item, today.year - item.year -
                       ((today.month, today.day) < (item.month, item.day)))
                      for item in dates]
        valid = [(item, age) for item, age in dated_ages if 14 <= age <= 100]
        ages = [age for _, age in valid]
        if not ages:
            return result
        if "рожд" in column_name.casefold():
            valid_dates = [item for item, _ in valid]
            result["min"] = min(valid_dates).isoformat()
            result["max"] = max(valid_dates).isoformat()
            result["span_days"] = (max(valid_dates) - min(valid_dates)).days
        groups = Counter(
            "до 18" if age < 18 else "18–20" if age <= 20 else
            "21–23" if age <= 23 else "24–29" if age <= 29 else "30 и старше"
            for age in ages
        )
        result["age_statistics"] = {
            "min": min(ages), "max": max(ages),
            "mean": round(sum(ages) / len(ages), 1),
            "valid_count": len(ages),
            "excluded_count": len(dated_ages) - len(ages),
            "groups": [{"value": key, "count": groups.get(key, 0)} for key in
                       ("до 18", "18–20", "21–23", "24–29", "30 и старше")]
        }
    return result


def _build_insights(
    row_count: int,
    column_count: int,
    quality: dict[str, Any],
    numeric_columns: list[dict[str, Any]],
    categorical_columns: list[dict[str, Any]],
    date_columns: list[dict[str, Any]],
) -> list[str]:
    """Создаёт ограниченный список выводов без повторов."""

    insights: list[str] = []

    if row_count:
        insights.append(
            f"Набор содержит {row_count} записей и {column_count} столбцов."
        )

    duplicate_rows = quality.get("duplicate_rows", 0)

    if duplicate_rows:
        insights.append(
            f"Полностью повторяющихся строк: {duplicate_rows}."
        )

    duplicate_headers = quality.get("duplicate_headers", [])

    if duplicate_headers:
        insights.append(
            "Повторяющиеся заголовки исправлены при анализе: "
            + ", ".join(duplicate_headers[:5]) + "."
        )

    constant_columns = quality.get("constant_columns", [])

    if constant_columns:
        insights.append(
            "Постоянные столбцы без разнообразия значений: "
            + ", ".join(constant_columns[:5]) + "."
        )

    for column in [c for c in numeric_columns if c.get("reportable")][:5]:
        name = column["name"]
        stats = column["statistics"]

        if stats.get("mean") is not None:
            insights.append(
                f"«{name}»: среднее {stats['mean']}, "
                f"медиана {stats['median']}, диапазон "
                f"{stats['min']}–{stats['max']}."
            )

        if stats.get("outlier_count", 0):
            insights.append(
                f"В «{name}» обнаружено потенциальных выбросов: "
                f"{stats['outlier_count']} "
                f"({stats.get('outlier_percent', 0)}%)."
            )

    for column in [c for c in categorical_columns if c.get("reportable")][:4]:
        stats = column["statistics"]
        top = stats.get("top_values", [])

        if top:
            insights.append(
                f"В «{column['name']}» чаще всего встречается "
                f"«{top[0]['value']}» — {top[0]['count']} наблюдений "
                f"({stats.get('top_value_percent', 0)}%)."
            )

    for column in date_columns[:3]:
        stats = column["statistics"]

        if stats.get("min") and stats.get("max"):
            insights.append(
                f"Период дат в «{column['name']}»: "
                f"{stats['min']} — {stats['max']} "
                f"({stats['span_days']} дней)."
            )

    return insights[:MAX_INSIGHTS]


def analyze_matrix(matrix: list[list[Any]]) -> dict[str, Any]:
    """
    Анализирует матрицу Excel.

    Сохраняет основные ключи результата для совместимости
    с launcher.py и pdf_builder.py.
    """

    base = analyze_sheet_matrix(matrix)

    headers = _unique_headers(base.get("headers", []))
    rows = base.get("rows", [])
    row_count = len(rows)
    column_count = len(headers)

    if not headers:
        return {
            **base,
            "headers": [],
            "rows": [],
            "row_count": 0,
            "column_count": 0,
            "numeric_columns": [],
            "categorical_columns": [],
            "date_columns": [],
            "quality": {
                "empty_cells": 0,
                "empty_percent": 0,
                "duplicate_rows": 0,
                "duplicate_row_percent": 0,
                "duplicate_headers": [],
                "constant_columns": [],
                "outlier_count": 0,
            },
            "kpis": {
                "records": 0,
                "columns": 0,
                "numeric_columns": 0,
                "empty_cells": 0,
                "fill_percent": 0,
                "outliers": 0,
            },
            "rankings": [],
            "distributions": [],
            "insights": [],
            "audit": {"score": 0, "grade": "F",
                      "decision": "НЕПРИГОДНЫ ДЛЯ УПРАВЛЕНЧЕСКИХ РЕШЕНИЙ",
                      "critical_count": 1, "high_count": 0,
                      "findings": [{"severity": "critical", "code": "EMPTY_DATA",
                                    "title": "Нет данных", "evidence": "Лист пуст.",
                                    "action": "Загрузить корректно структурированный лист."}]},
            "warnings": base.get("warnings", []),
        }

    normalized_rows: list[list[Any]] = []

    for raw_row in rows:
        row = list(raw_row[:column_count])
        row.extend([None] * (column_count - len(row)))

        if not all(_is_empty(value) for value in row):
            normalized_rows.append(row)

    row_count = len(normalized_rows)
    total_cells = row_count * column_count

    empty_cells = sum(
        _is_empty(value)
        for row in normalized_rows
        for value in row
    )

    row_fingerprints = Counter(
        tuple(_display(value, 1000) for value in row)
        for row in normalized_rows
    )

    duplicate_rows = sum(
        count - 1
        for count in row_fingerprints.values()
        if count > 1
    )

    duplicate_headers = [
        header for header, count in Counter(base.get("headers", [])).items()
        if count > 1
    ]

    numeric_columns: list[dict[str, Any]] = []
    categorical_columns: list[dict[str, Any]] = []
    date_columns: list[dict[str, Any]] = []
    rankings: list[dict[str, Any]] = []
    distributions: list[dict[str, Any]] = []
    constant_columns: list[str] = []
    empty_columns: list[str] = []
    total_outliers = 0

    for index, header in enumerate(headers):
        values = [
            row[index] if index < len(row) else None
            for row in normalized_rows
        ]

        nonempty_values = [
            value for value in values if not _is_empty(value)
        ]

        kind = _column_kind(values)
        distinct = {_display(value, 1000) for value in nonempty_values}

        if kind == "empty":
            empty_columns.append(header)
            continue

        if len(distinct) <= 1 and nonempty_values:
            constant_columns.append(header)

        missing_count = sum(_is_empty(value) for value in values)

        common = {
            "name": header,
            "index": index,
            "kind": kind,
            "count": len(nonempty_values),
            "missing_count": missing_count,
            "missing_percent": _percent(missing_count, len(values)),
            "unique_count": len(distinct),
        }
        role = _column_role(header, len(distinct), row_count)
        common["role"] = role
        # Для категорий высокая кардинальность означает, что столбец лучше
        # использовать как подпись объектов, а не как распределение. Для
        # числовых показателей уникальность нормальна и не является причиной
        # исключения из отчёта.
        common["reportable"] = role == "dimension"

        if kind == "numeric":
            numeric_values = [
                parsed for value in nonempty_values
                if (parsed := _numeric(value)) is not None
            ]

            stats = _numeric_statistics(numeric_values)
            total_outliers += stats.get("outlier_count", 0)

            identifier_like = _numeric_identifier_like(header)
            item = {
                **common,
                "role": "identifier" if identifier_like else "measure",
                "reportable": not identifier_like and len(distinct) > 1,
                "mixed_type_percent": _percent(
                    len(nonempty_values) - len(numeric_values), len(nonempty_values)
                ),
                "identifier_like": identifier_like,
                "statistics": stats,
                "display": _numeric_display_metadata(
                    header, numeric_values, stats,
                ),
            }
            numeric_columns.append(item)

            if stats.get("count"):
                rankings.append({
                    "column": header,
                    "min": stats["min"],
                    "max": stats["max"],
                    "mean": stats["mean"],
                    "median": stats["median"],
                    "count": stats["count"],
                })

        elif kind == "date":
            stats = _date_statistics(values, header)

            date_columns.append({
                **common,
                "statistics": stats,
            })

        elif kind == "categorical":
            stats = _categorical_statistics(values)

            item = {
                **common,
                "statistics": stats,
            }
            categorical_columns.append(item)

            if item["reportable"]:
                distributions.append({
                    "column": header,
                    "unique_count": stats["unique_count"],
                    "top_values": stats["top_values"],
                    "top_value_percent": stats["top_value_percent"],
                })

    quality = {
        "empty_cells": empty_cells,
        "empty_percent": _percent(empty_cells, total_cells),
        "duplicate_rows": duplicate_rows,
        "duplicate_row_percent": _percent(duplicate_rows, row_count),
        "duplicate_headers": duplicate_headers,
        "constant_columns": constant_columns,
        "outlier_count": total_outliers,
    }

    # Одинаковые по значениям столбцы не должны превращаться в две почти
    # идентичные страницы отчёта. Сохраняем первый разрез, а последующие
    # помечаем как семантические дубли. Сравнение выполняется по нормализованным
    # значениям всех строк и не зависит от регистра или лишних пробелов.
    duplicate_columns: list[dict[str, str]] = []
    seen_signatures: dict[tuple[str, ...], dict[str, Any]] = {}
    for column in categorical_columns:
        index = int(column.get("index", -1))
        if index < 0:
            continue
        signature = tuple(
            _display(row[index] if index < len(row) else None, 1000)
            .strip().casefold()
            for row in normalized_rows
        )
        original = seen_signatures.get(signature)
        if original is None:
            seen_signatures[signature] = column
            continue
        column["duplicate_of"] = original.get("name")
        column["reportable"] = False
        duplicate_columns.append({
            "column": str(column.get("name", "")),
            "duplicate_of": str(original.get("name", "")),
        })

    # Почти постоянные поля полезны как контроль исключений, но отдельная
    # круговая диаграмма для доли 99–100% не даёт управленческой информации.
    for column in categorical_columns:
        top_share = float(
            (column.get("statistics", {}) or {}).get("top_value_percent", 0) or 0
        )
        column["low_information"] = top_share >= 98.0

    quality["duplicate_columns"] = duplicate_columns

    kpis = {
        "records": row_count,
        "columns": column_count - len(empty_columns),
        "numeric_columns": sum(
            bool(column.get("reportable")) for column in numeric_columns
        ),
        "empty_cells": empty_cells,
        "fill_percent": round(
            100 - quality["empty_percent"], 2
        ) if total_cells else 0,
        "outliers": total_outliers,
    }
    audit = _build_audit(row_count, column_count, quality,
                         numeric_columns + categorical_columns + date_columns)
    kpis["quality_score"] = audit["score"]
    kpis["quality_grade"] = audit["grade"]

    insights = _build_insights(
        row_count=row_count,
        column_count=column_count,
        quality=quality,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        date_columns=date_columns,
    )

    warnings = list(base.get("warnings", []) or [])

    if duplicate_headers:
        warnings.append(
            "В исходной таблице есть повторяющиеся заголовки; "
            "для анализа они сделаны уникальными."
        )

    if total_outliers:
        warnings.append(
            "Выбросы определены статистическим правилом 1,5 IQR; "
            "они требуют проверки и не обязательно являются ошибками."
        )

    if duplicate_columns:
        pairs = ", ".join(
            f"{item['column']} = {item['duplicate_of']}"
            for item in duplicate_columns[:5]
        )
        warnings.append(
            "Обнаружены дублирующие разрезы; повторные страницы исключены: "
            + pairs + "."
        )

    return {
        **base,
        "headers": headers,
        "rows": normalized_rows,
        "row_count": row_count,
        "column_count": column_count,
        "analyzed_column_count": column_count - len(empty_columns),
        "empty_columns": empty_columns,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "date_columns": date_columns,
        "quality": quality,
        "kpis": kpis,
        "rankings": rankings[:MAX_RANKINGS],
        "distributions": distributions[:MAX_DISTRIBUTIONS],
        "insights": insights,
        "audit": audit,
        "warnings": warnings,
    }


def analyze_sheet(
    headers: list[str],
    rows: list[list[Any]],
) -> dict[str, Any]:
    """Совместимость с вызовами, передающими заголовки и строки отдельно."""

    matrix = [list(headers)] + [list(row) for row in rows]
    return analyze_matrix(matrix)
