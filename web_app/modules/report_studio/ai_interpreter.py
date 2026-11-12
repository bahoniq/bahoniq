# -*- coding: utf-8 -*-
"""Интерпретация аналитики ANALYTICS AI через локальную Ollama."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any


LOGGER = logging.getLogger(__name__)

# Локальные запросы к Ollama не должны перехватываться системным прокси Windows
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

OLLAMA_URL = os.getenv(
    "BAHONIQ_OLLAMA_URL",
    "http://localhost:11434/api/generate",
).strip()

OLLAMA_MODEL = os.getenv(
    "BAHONIQ_OLLAMA_MODEL",
    "qwen2.5:3b",
).strip()

try:
    OLLAMA_TIMEOUT = max(
        5,
        int(os.getenv("BAHONIQ_OLLAMA_TIMEOUT", "3600")),
    )
except (TypeError, ValueError):
    OLLAMA_TIMEOUT = 300

MAX_PAYLOAD_LENGTH = 5000
MAX_COLUMNS = 12
MAX_FINDINGS = 10
MAX_RISKS = 5
MAX_RECOMMENDATIONS = 8
MAX_LIMITATIONS = 6
MAX_TEXT_LENGTH = 1200

SENSITIVE_MARKERS = (
    "фамил", "имя", "отчеств", "фио", "иин", "телефон", "email",
    "e-mail", "адрес", "паспорт", "удостовер", "имя на латинице",
)
IDENTIFIER_MARKERS = (" id", "id ", "id_", "_id", "идентификатор", "код обуч")
BANNED_OUTPUT_MARKERS = (
    "пуст", "пропуск", "не заполн", "отсутств", "добавить данн",
    "увеличить количество данных", "имя на латинице",
    "качество данных", "провести анализ", "рекомендуется провести",
)


def _header_role(header: str) -> str:
    normalized = " " + header.casefold().strip() + " "
    if any(marker in normalized for marker in SENSITIVE_MARKERS):
        return "sensitive"
    if any(marker in normalized for marker in IDENTIFIER_MARKERS):
        return "identifier"
    return "business"


def _text(value: Any, limit: int = MAX_TEXT_LENGTH) -> str:
    """Преобразует значение в безопасный ограниченный текст."""

    if value is None:
        return ""

    if isinstance(value, (datetime, date)):
        result = value.isoformat()
    else:
        result = str(value)

    result = result.strip()

    if len(result) > limit:
        result = result[:limit].rstrip() + "…"

    return result


def _number(value: Any) -> float | None:
    """Преобразует число, не считая пустые и булевы значения числами."""

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

        if "," in raw and "." not in raw:
            raw = raw.replace(",", ".")

        try:
            result = float(raw)
            if result == result and abs(result) != float("inf"):
                return result
        except (TypeError, ValueError, OverflowError):
            return None

    return None


def _safe_list(
    value: Any,
    limit: int,
    item_limit: int = 500,
) -> list[str]:
    """Нормализует список текстовых выводов."""

    if isinstance(value, str):
        source = [value]
    elif isinstance(value, (list, tuple)):
        source = list(value)
    else:
        source = []

    result: list[str] = []
    seen: set[str] = set()

    for item in source:
        if isinstance(item, dict):
            item = next(
                (
                    item.get(key)
                    for key in (
                        "text", "value", "finding", "insight", "conclusion",
                        "recommendation", "risk", "описание", "вывод",
                        "рекомендация", "риск", "action", "действие",
                        "evidence", "факт", "interpretation", "интерпретация",
                    )
                    if item.get(key) not in (None, "")
                ),
                item,
            )
        cleaned = _text(item, item_limit)

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

        if len(result) >= limit:
            break

    return result


def _normalize_matrix(matrix: Any) -> list[list[Any]]:
    """Создаёт прямоугольную матрицу, не изменяя оригинал."""

    if not isinstance(matrix, (list, tuple)):
        return []

    rows: list[list[Any]] = []

    for row in matrix:
        if isinstance(row, (list, tuple)):
            rows.append(list(row))
        else:
            rows.append([row])

    while rows and all(
        value is None or (isinstance(value, str) and not value.strip())
        for value in rows[0]
    ):
        rows.pop(0)

    if not rows:
        return []

    width = max((len(row) for row in rows), default=0)

    if width == 0:
        return []

    normalized: list[list[Any]] = []

    for row in rows:
        row = row[:width]
        row.extend([None] * (width - len(row)))
        normalized.append(row)

    while normalized and all(
        value is None or (isinstance(value, str) and not value.strip())
        for value in normalized[-1]
    ):
        normalized.pop()

    return normalized


def _column_name(value: Any, index: int) -> str:
    name = _text(value, 100)
    return name or f"Столбец {index + 1}"


def _column_statistics(
    header: str,
    values: list[Any],
) -> dict[str, Any]:
    """Рассчитывает краткие статистические характеристики столбца."""

    nonempty = [
        value for value in values
        if value is not None
        and not (isinstance(value, str) and not value.strip())
    ]

    result: dict[str, Any] = {
        "name": header,
        "count": len(nonempty),
        "role": _header_role(header),
    }

    if not nonempty:
        result["type"] = "empty"
        return result

    if result["role"] in {"sensitive", "identifier"}:
        result["type"] = result["role"]
        result["reportable"] = False
        return result

    numeric_values = [
        parsed for value in nonempty
        if (parsed := _number(value)) is not None
    ]

    # Классифицируем столбец как числовой, если большинство
    # заполненных значений действительно являются числами.
    if len(numeric_values) / len(nonempty) >= 0.7:
        ordered = sorted(numeric_values)
        count = len(ordered)
        mean = sum(ordered) / count

        result.update({
            "type": "numeric",
            "reportable": True,
            "count": count,
            "min": min(ordered),
            "max": max(ordered),
            "mean": round(mean, 4),
            "sum": round(sum(ordered), 4),
        })

        def _quantile(seq: list[float], q: float) -> float:
            if not seq:
                return 0.0
            if len(seq) == 1:
                return seq[0]
            pos = (len(seq) - 1) * q
            lo = int(pos)
            hi = min(len(seq) - 1, lo + 1)
            frac = pos - lo
            return seq[lo] * (1.0 - frac) + seq[hi] * frac

        median = _quantile(ordered, 0.5)
        q1 = _quantile(ordered, 0.25)
        q3 = _quantile(ordered, 0.75)
        iqr = q3 - q1

        result["median"] = round(median, 4)
        result["q1"] = round(q1, 4)
        result["q3"] = round(q3, 4)
        result["iqr"] = round(iqr, 4)

        if median != 0:
            result["mean_median_gap_percent"] = round((mean - median) / abs(median) * 100, 1)

        if count >= 4 and iqr > 0:
            low_fence = q1 - 1.5 * iqr
            high_fence = q3 + 1.5 * iqr
            low_out = [v for v in ordered if v < low_fence]
            high_out = [v for v in ordered if v > high_fence]
            out_total = len(low_out) + len(high_out)
            if out_total > 0:
                result["outlier_count"] = out_total
                result["outlier_percent"] = round(out_total * 100 / count, 1)
                if high_out:
                    result["high_outliers"] = len(high_out)
                if low_out:
                    result["low_outliers"] = len(low_out)

        if count > 1:
            variance = sum((value - mean) ** 2 for value in ordered) / count
            result["std_dev"] = round(variance ** 0.5, 4)
        else:
            result["std_dev"] = 0

        return result

    # Для остальных столбцов учитываем частоты категорий.
    frequencies: dict[str, int] = {}

    for value in nonempty:
        label = _text(value, 160) or "(пусто)"
        frequencies[label] = frequencies.get(label, 0) + 1

    sorted_freqs = sorted(
        frequencies.items(),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    top_values = sorted_freqs[:8]

    result.update({
        "type": "categorical",
        "unique_count": len(frequencies),
        "top_values": [
            {
                "value": key,
                "count": count,
                "share_percent": round(count * 100 / len(nonempty), 1),
            }
            for key, count in top_values
        ],
    })
    result["reportable"] = not (
        len(nonempty) >= 20 and len(frequencies) / len(nonempty) >= 0.5
    )
    if not result["reportable"]:
        result["type"] = "high_cardinality"
        result["top_values"] = []

    if top_values:
        result["top_value_percent"] = round(
            top_values[0][1] * 100 / len(nonempty),
            2,
        )
        if result["reportable"]:
            result["top3_share_percent"] = round(
                sum(c for _, c in sorted_freqs[:3]) * 100 / len(nonempty),
                1,
            )
            if len(sorted_freqs) >= 2:
                smallest_key, smallest_count = sorted_freqs[-1]
                result["smallest_value"] = {
                    "value": smallest_key,
                    "count": smallest_count,
                    "share_percent": round(smallest_count * 100 / len(nonempty), 1),
                }

    return result


def _compact_analysis(
    matrix: Any,
    analytics: Any = None,
    report_pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Формирует компактный набор статистики без передачи исходных строк."""

    normalized = _normalize_matrix(matrix)

    # launcher может передать в matrix только строки данных, а настоящие
    # заголовки уже находятся в результате analyze_matrix(). В этом случае
    # используем именно проверенную структуру analytics, иначе резервный отчёт
    # получает ложные названия «Столбец 1», «Столбец 2».
    if isinstance(analytics, dict):
        analytics_headers = analytics.get("headers")
        analytics_rows = analytics.get("rows")
        if isinstance(analytics_headers, (list, tuple)) and analytics_headers:
            safe_headers = list(analytics_headers)
            if isinstance(analytics_rows, (list, tuple)):
                normalized = [safe_headers] + [
                    list(row) if isinstance(row, (list, tuple)) else [row]
                    for row in analytics_rows
                ]

    if not normalized:
        return {
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "cross_comparisons": [],
            "metric_by_category": [],
        }

    raw_headers = normalized[0]
    headers = [
        _column_name(value, index)
        for index, value in enumerate(raw_headers)
    ]

    data_rows = normalized[1:]
    row_count = len([
        row for row in data_rows
        if any(
            value is not None
            and not (isinstance(value, str) and not value.strip())
            for value in row
        )
    ])

    width = len(headers)
    columns = []
    display_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(analytics, dict):
        for item in analytics.get("numeric_columns", []) or []:
            if isinstance(item, dict) and isinstance(item.get("display"), dict):
                display_by_name[str(item.get("name") or "")] = dict(item["display"])

    for index, header in enumerate(headers):
        if len(columns) >= MAX_COLUMNS:
            break
        values = [
            row[index] if index < len(row) else None
            for row in data_rows
        ]

        column = _column_statistics(header, values)
        if column.get("type") in {"empty", "sensitive", "identifier"}:
            continue
        column["index"] = index
        if header in display_by_name:
            display = display_by_name[header]
            column["display"] = display
            multiplier = float(display.get("multiplier", 1) or 1)
            if display.get("display_as") == "percent" and multiplier != 1:
                for key in ("min", "max", "mean", "median"):
                    if column.get(key) is not None:
                        column[f"display_{key}"] = round(float(column[key]) * multiplier, 4)
        columns.append(column)

    reportable_dimensions = [
        column for column in columns
        if column.get("type") == "categorical"
        and column.get("reportable")
        and 2 <= int(column.get("unique_count", 0) or 0) <= 25
    ][:5]
    cross_comparisons: list[dict[str, Any]] = []
    for primary in reportable_dimensions[:3]:
        for secondary in reportable_dimensions:
            if primary is secondary:
                continue
            totals: dict[str, int] = {}
            pairs: dict[str, dict[str, int]] = {}
            for row in data_rows:
                try:
                    left = _text(row[primary["index"]], 80)
                    right = _text(row[secondary["index"]], 80)
                except (IndexError, TypeError):
                    continue
                if not left or not right:
                    continue
                totals[left] = totals.get(left, 0) + 1
                pairs.setdefault(left, {})[right] = pairs.setdefault(left, {}).get(right, 0) + 1
            groups = []
            for group, total in sorted(totals.items(), key=lambda x: -x[1])[:6]:
                if not total:
                    continue
                sorted_sub = sorted(pairs[group].items(), key=lambda x: (-x[1], x[0]))
                leader, count = sorted_sub[0]
                groups.append({
                    "group": group,
                    "count": total,
                    "group_share_percent": round(total * 100 / max(1, row_count), 1),
                    "leading_value": leader,
                    "leading_share_percent": round(count * 100 / total, 1),
                    "breakdown": [
                        {
                            "value": sub_val,
                            "count": sub_cnt,
                            "share_percent": round(sub_cnt * 100 / total, 1),
                        }
                        for sub_val, sub_cnt in sorted_sub[:3]
                    ],
                })
            if len(groups) >= 2:
                cross_comparisons.append({
                    "group_by": primary["name"],
                    "compare": secondary["name"],
                    "groups": groups,
                })
            if len(cross_comparisons) >= 6:
                break
        if len(cross_comparisons) >= 6:
            break

    # Многофакторные срезы «Числовой показатель × Категория»
    reportable_numerics = [
        column for column in columns
        if column.get("type") == "numeric" and column.get("reportable")
    ][:4]
    metric_by_category: list[dict[str, Any]] = []
    for num_col in reportable_numerics:
        overall_mean = float(num_col.get("mean") or 0.0)
        overall_sum = float(num_col.get("sum") or 0.0)
        for dim_col in reportable_dimensions[:3]:
            grouped_vals: dict[str, list[float]] = {}
            for row in data_rows:
                try:
                    cat_val = _text(row[dim_col["index"]], 80)
                    num_val = _number(row[num_col["index"]])
                except (IndexError, TypeError):
                    continue
                if not cat_val or num_val is None:
                    continue
                grouped_vals.setdefault(cat_val, []).append(num_val)
            if len(grouped_vals) < 2:
                continue
            group_stats = []
            for g_name, vals in grouped_vals.items():
                s_vals = sorted(vals)
                g_cnt = len(s_vals)
                g_sum = sum(s_vals)
                g_mean = g_sum / g_cnt
                g_med = (
                    s_vals[g_cnt // 2]
                    if g_cnt % 2
                    else (s_vals[g_cnt // 2 - 1] + s_vals[g_cnt // 2]) / 2
                )
                entry: dict[str, Any] = {
                    "group": g_name,
                    "count": g_cnt,
                    "mean": round(g_mean, 2),
                    "median": round(g_med, 2),
                    "sum": round(g_sum, 2),
                }
                if overall_sum > 0 and g_sum >= 0:
                    entry["share_of_sum_percent"] = round(g_sum * 100 / overall_sum, 1)
                if overall_mean != 0:
                    entry["diff_from_mean_percent"] = round(
                        (g_mean - overall_mean) / abs(overall_mean) * 100, 1
                    )
                group_stats.append(entry)
            by_mean = sorted(group_stats, key=lambda x: (-x["mean"], -x["count"]))
            leader = by_mean[0]
            laggard = by_mean[-1]
            summary_item: dict[str, Any] = {
                "metric": num_col["name"],
                "dimension": dim_col["name"],
                "overall_mean": round(overall_mean, 2),
                "leader_group": leader["group"],
                "leader_mean": leader["mean"],
                "laggard_group": laggard["group"],
                "laggard_mean": laggard["mean"],
                "groups": by_mean[:6],
            }
            if laggard["mean"] > 0:
                summary_item["leader_to_laggard_ratio"] = round(
                    leader["mean"] / laggard["mean"], 2
                )
            metric_by_category.append(summary_item)
            if len(metric_by_category) >= 6:
                break
        if len(metric_by_category) >= 6:
            break

    # Передаём только заранее рассчитанные агрегаты.
    # Исходные строки, персональные данные и ключ rows не копируются.
    provided_analytics: dict[str, Any] = {}
    age_summaries: list[dict[str, Any]] = []

    if isinstance(analytics, dict):
        for key in ("row_count", "column_count", "analyzed_column_count"):
            value = analytics.get(key)

            if isinstance(value, (str, int, float, bool)) or value is None:
                provided_analytics[key] = value
        for column in analytics.get("date_columns", []):
            age = column.get("statistics", {}).get("age_statistics")
            if not age:
                continue
            age_summaries.append({
                "name": _text(column.get("name"), 100),
                "mean": age.get("mean"),
                "min": age.get("min"),
                "max": age.get("max"),
                "groups": age.get("groups", [])[:8],
            })

    candidate_topics: list[dict[str, str]] = []
    if isinstance(report_pages, list):
        for page in report_pages[:10]:
            if isinstance(page, dict) and page.get("title"):
                candidate_topics.append({
                    "topic": _text(page.get("title"), 120),
                    "fact": _text(page.get("lead"), 240),
                })

    result_payload: dict[str, Any] = {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "cross_comparisons": cross_comparisons,
        "metric_by_category": metric_by_category,
        "age_summaries": age_summaries,
        "provided_analytics": provided_analytics,
    }
    if candidate_topics:
        result_payload["candidate_topics"] = candidate_topics
    return result_payload


def _build_fallback_analysis(
    compact: dict[str, Any],
    title: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Создаёт честный резервный анализ без локальной модели."""

    row_count = int(compact.get("row_count", 0) or 0)
    column_count = int(compact.get("column_count", 0) or 0)
    columns = compact.get("columns", [])

    if not row_count or not column_count:
        return {
            "available": True,
            "source": "fallback",
            "model": None,
            "summary": (
                "Не удалось подготовить статистическую интерпретацию: "
                "в выбранном диапазоне не обнаружено достаточного объёма данных."
            ),
            "findings": [],
            "risks": [
                "Проверьте, что первая строка содержит заголовки, "
                "а ниже расположены записи."
            ],
            "recommendations": [
                "Проверьте структуру листа и повторите формирование отчёта."
            ],
            "limitations": [
                "Локальная модель ИИ не использовалась.",
                "Резервные выводы основаны только на доступных агрегатах.",
            ],
            "warning": "Использована резервная статистическая интерпретация.",
        }

    summary = (
        f"В наборе данных обнаружено {row_count} записей "
        f"и {column_count} столбцов. "
    )

    findings: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []

    numeric_columns = [
        column for column in columns
        if column.get("type") == "numeric" and column.get("reportable", True)
    ]
    categorical_columns = [
        column for column in columns
        if column.get("type") == "categorical" and column.get("reportable", True)
    ]

    for column in numeric_columns[:3]:
        name = _text(column.get("name", "Показатель"), 100)
        findings.append(
            f"«{name}»: среднее {column.get('mean')}, "
            f"медиана {column.get('median')}, "
            f"диапазон от {column.get('min')} до {column.get('max')}."
        )

    for column in categorical_columns[:5]:
        name = _text(column.get("name", "Категория"), 100)
        top_values = column.get("top_values", [])

        if top_values:
            top = top_values[0]
            findings.append(
                f"По показателю «{name}» лидирует «{_text(top.get('value'), 80)}»: "
                f"{top.get('count')} записей, или {column.get('top_value_percent', 0)}%."
            )

    for age in compact.get("age_summaries", [])[:2]:
        findings.append(
            f"По показателю «{_text(age.get('name'), 80)}» средний возраст "
            f"составляет {age.get('mean')} года, диапазон — "
            f"от {age.get('min')} до {age.get('max')} лет."
        )

    for comparison in compact.get("cross_comparisons", [])[:2]:
        groups = comparison.get("groups", [])
        if not groups:
            continue
        group = groups[0]
        findings.append(
            f"В крупнейшей группе «{_text(group.get('group'), 80)}» "
            f"({group.get('count')} записей) значение "
            f"«{_text(group.get('leading_value'), 80)}» занимает "
            f"{group.get('leading_share_percent')}%."
        )

    # Резервные действия строятся только по фактически найденным показателям.
    # Здесь нет отраслевых фраз про студентов, факультеты или финансирование:
    # один и тот же fallback должен корректно работать с любым Excel-файлом.
    for column in categorical_columns[:3]:
        name = _text(column.get("name", "Категория"), 100)
        top_values = column.get("top_values", [])
        if top_values:
            recommendations.append(
                f"По показателю «{name}» сопоставить две крупнейшие категории "
                "и зафиксировать абсолютную разницу и разницу долей."
            )
    for column in numeric_columns[:3]:
        name = _text(column.get("name", "Показатель"), 100)
        recommendations.append(
            f"По показателю «{name}» проверить объекты с минимальным и "
            "максимальным значением и сопоставить их с медианой."
        )
    if not recommendations:
        recommendations.append(
            "Выбрать содержательный показатель из текущего файла и определить "
            "для него сравниваемые группы и контрольную метрику."
        )

    summary += "Ниже приведены выводы по содержательным показателям набора."

    return {
        "available": True,
        "source": "fallback",
        "model": None,
        "summary": summary,
        "findings": _safe_list(findings, MAX_FINDINGS),
        "risks": _safe_list(risks, MAX_RISKS),
        "recommendations": _safe_list(
            recommendations, MAX_RECOMMENDATIONS
        ),
        "limitations": [],
        "warning": (
            "Использована резервная статистическая интерпретация; "
            "выводы не являются ответом языковой модели."
        ),
    }


def _build_prompt(
    compact: dict[str, Any],
    title: str = "",
    description: str = "",
    report_profile: str = "Автоматически",
    audience: str = "Руководство",
) -> str:
    """Строит промпт только из агрегированной статистики."""

    safe_payload = json.dumps(
        compact,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )

    if len(safe_payload) > MAX_PAYLOAD_LENGTH:
        compact = dict(compact)
        compact_columns = []
        for column in compact.get("columns", [])[:12]:
            compact_columns.append({
                key: value
                for key, value in {
                    "name": _text(column.get("name"), 80),
                    "type": column.get("type"),
                    "count": column.get("count"),
                    "min": column.get("min"),
                    "q1": column.get("q1"),
                    "median": column.get("median"),
                    "mean": column.get("mean"),
                    "q3": column.get("q3"),
                    "max": column.get("max"),
                    "iqr": column.get("iqr"),
                    "sum": column.get("sum"),
                    "mean_median_gap_percent": column.get("mean_median_gap_percent"),
                    "outlier_count": column.get("outlier_count"),
                    "outlier_percent": column.get("outlier_percent"),
                    "display": column.get("display"),
                    "display_min": column.get("display_min"),
                    "display_max": column.get("display_max"),
                    "display_mean": column.get("display_mean"),
                    "display_median": column.get("display_median"),
                    "unique_count": column.get("unique_count"),
                    "top_value_percent": column.get("top_value_percent"),
                    "top3_share_percent": column.get("top3_share_percent"),
                    "smallest_value": column.get("smallest_value"),
                    "top_values": [
                        {
                            "value": _text(item.get("value"), 80),
                            "count": item.get("count"),
                            "share_percent": item.get("share_percent"),
                        }
                        for item in (column.get("top_values", []) or [])[:6]
                        if isinstance(item, dict)
                    ],
                }.items()
                if value not in (None, "", [])
            })
        compact["columns"] = compact_columns
        slim_comparisons = []
        for comp in (compact.get("cross_comparisons") or [])[:2]:
            if not isinstance(comp, dict):
                continue
            groups = [
                {
                    "group": _text(g.get("group"), 60),
                    "leading_value": _text(g.get("leading_value"), 60),
                    "leading_share_percent": g.get("leading_share_percent"),
                }
                for g in (comp.get("groups") or [])[:3]
                if isinstance(g, dict)
            ]
            slim_comparisons.append({
                "group_by": _text(comp.get("group_by"), 60),
                "compare": _text(comp.get("compare"), 60),
                "groups": groups,
            })
        compact["cross_comparisons"] = slim_comparisons
        compact["metric_by_category"] = compact.get("metric_by_category", [])[:2]
        compact["age_summaries"] = compact.get("age_summaries", [])[:2]
        compact["provided_analytics"] = {}
        safe_payload = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    if len(safe_payload) > MAX_PAYLOAD_LENGTH:
        compact["columns"] = compact.get("columns", [])[:8]
        compact["cross_comparisons"] = compact.get("cross_comparisons", [])[:2]
        compact["metric_by_category"] = compact.get("metric_by_category", [])[:2]
        safe_payload = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    safe_title = _text(title, 200) or "Аналитический отчёт"
    safe_description = _text(description, 700)
    safe_profile = _text(report_profile, 80) or "Автоматически"
    safe_audience = _text(audience, 80) or "Руководство"

    return f"""
Ты — ведущий аналитик данных и эксперт по управленческой аналитике. Подготовь
глубокую, доказательную и содержательную интерпретацию статистики на русском языке.

Название отчёта: {safe_title}
Задача пользователя: {safe_description or "Провести комплексный многофакторный анализ показателей, выявить закономерности, лидеров, отстающие сегменты, перекрёстные связи и аномалии."}
Профиль анализа: {safe_profile}
Целевая аудитория: {safe_audience}

Исходная агрегированная статистика для анализа:
{safe_payload}

ВАЖНЫЕ ПРАВИЛА АНАЛИТИКИ (СТРОГИЙ УПРАВЛЕНЧЕСКИЙ СТАНДАРТ):
1. ЗАПРЕТ НА ШАБЛОННЫЕ ТРИВИАЛЬНОСТИ: Категорически запрещено писать пустые шаблонные фразы вроде «Проверить крупнейшую категорию», «Сопоставить объем с планом», «Выраженный лидер» или просто пересказывать очевидные числа с графиков.
2. ФОКУС НА ДЕНЬГАХ, АНОМАЛИЯХ И УПРАВЛЕНЧЕСКИХ РИСКАХ:
   - В поле "interpretation" давай глубокий аналитический смысл: почему этот срез важен для руководства, какие есть скрытые дисбалансы или структурные зависимости.
   - В поле "action" предлагай конкретное, выполнимое управленческое решение с указанием ответственной роли (например: «Финансовому блоку диверсифицировать прием...», «Юридической службе и кураторам проверить 40 условно зачисленных студентов на закрытие академической разницы...»).
3. КРОСС-СВЯЗИ: Ищи взаимное влияние факторов (например, как форма оплаты связана со ступенью обучения или грантами).
4. Игнорируй незаполненные ячейки и технические поля: категорически запрещено употреблять слова с корнями «пуст», «пропуск», «не заполн», «отсутств», «качество данных».
5. Не анализируй идентификаторы, фамилии, имена, отчества и другие технические ID.
6. В поле topic каждого story используй точное название показателя из candidate_topics или columns.
7. Сформируй от 6 до 8 содержательных аналитических сюжетов (stories), чтобы охватить все ключевые содержательные срезы и направления анализа. Для каждого показателя сформулируй профессиональную управленческую интерпретацию и конкретное решение. Никаких пустых шаблонов.

Верни ТОЛЬКО валидный JSON-объект без пояснений и без Markdown-разметки строго в следующем формате:
{{
  "domain": "Предметная область одним коротким словосочетанием",
  "report_title": "Осмысленное название исследования без имени файла",
  "report_subtitle": "Краткий подзаголовок по фактическим показателям и масштабу выборки",
  "research_plan": ["Направление анализа или перекрёстное сравнение и его цель"],
  "summary": "Связное управленческое резюме из 2-3 информативных предложений с ключевыми цифрами и пропорциями",
  "findings": ["4-6 глубоких аналитических выводов с точными числами, долями и сравнением сегментов"],
  "risks": ["До 3 конкретных рисков или диспропорций, строго подтверждённых числами"],
  "recommendations": ["До 4 конкретных практических рекомендаций с привязкой к сегментам"],
  "stories": [
    {{
      "topic": "Точное название показателя из candidate_topics или columns",
      "story_type": "structure|comparison|concentration|cross|numeric",
      "headline": "Краткий ёмкий аналитический заголовок до 60 знаков",
      "evidence": "Точный факт с абсолютными числами, долями % и сравнением групп",
      "interpretation": "Объяснение закономерности или концентрации",
      "limitation": "Граница интерпретации текущего среза",
      "action": "Конкретное управленческое действие или пустая строка"
    }}
  ],
  "limitations": []
}}
""".strip()


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """Восстанавливает обрезанный по лимиту длины JSON-ответ Ollama."""
    start = text.find("{")
    if start < 0:
        return None
    s = text[start:].strip()

    for cut in range(len(s), max(0, len(s) - 600), -1):
        chunk = s[:cut].rstrip().rstrip(",: \t\r\n")
        unescaped_quotes = 0
        i = 0
        while i < len(chunk):
            if chunk[i] == '"':
                unescaped_quotes += 1
            elif chunk[i] == '\\':
                i += 1
            i += 1
        if unescaped_quotes % 2 != 0:
            chunk += '"'
        open_b = chunk.count("[") - chunk.count("]")
        open_c = chunk.count("{") - chunk.count("}")
        attempt = chunk + ("]" * max(0, open_b)) + ("}" * max(0, open_c))
        try:
            res = json.loads(attempt)
            if isinstance(res, dict) and len(res) >= 2:
                return res
        except Exception:
            pass
    return None


def _parse_response(raw: str) -> dict[str, Any]:
    """Извлекает JSON-объект из ответа Ollama, очищая Markdown и случайный текст."""

    text = (raw or "").strip()

    if not text:
        raise ValueError("Ollama вернула пустой ответ.")

    # 1. Удаляем Markdown-теги кодовых блоков (```json ... ```)
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()

    # 2. Прямая попытка распарсить чистый JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 3. Если ИИ добавил текст ДО или ПОСЛЕ JSON, ищем первую { и последнюю }
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        json_str = text[start:end + 1]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. Ремонт оборванного по лимиту длины JSON
    repaired = _repair_truncated_json(text)
    if repaired:
        return repaired

    raise ValueError(f"Не удалось разобрать JSON-ответ Ollama. Сырой ответ ИИ:\n{text[:300]}")


def _select_model_name(requested: str, available: list[str]) -> str:
    """Выбирает запрошенную либо наиболее крупную доступную Qwen-модель."""
    if requested in available:
        return requested
    requested_base = requested.split(":", 1)[0].casefold()
    same_family = [name for name in available
                   if name.split(":", 1)[0].casefold() == requested_base]
    candidates = same_family or [name for name in available
                                 if "qwen" in name.casefold()]
    if not candidates:
        raise RuntimeError(
            "Ollama работает, но подходящая Qwen-модель не установлена. "
            f"Доступные модели: {', '.join(available) or 'нет'}."
        )

    def size_key(name: str) -> float:
        match = re.search(r":(\d+(?:\.\d+)?)b(?:$|-)", name.casefold())
        return float(match.group(1)) if match else 0.0

    return max(candidates, key=size_key)


def _discover_ollama_model(requested: str, timeout: int) -> str:
    parsed = urllib.parse.urlsplit(OLLAMA_URL)
    tags_url = urllib.parse.urlunsplit((
        parsed.scheme or "http",
        parsed.netloc or "localhost:11434",
        "/api/tags", "", "",
    ))
    request = urllib.request.Request(tags_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=min(timeout, 60)) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(
            f"Ollama не отвечает по адресу {tags_url}. "
            "Запустите Ollama и проверьте, что порт 11434 доступен. "
            f"Техническая причина: {type(exc).__name__}: {exc}"
        ) from exc
    available = [str(item.get("name") or item.get("model") or "").strip()
                 for item in payload.get("models", []) if isinstance(item, dict)]
    available = [name for name in available if name]
    return _select_model_name(requested, available)


ANALYTICS_AI_SYSTEM_PROMPT = (
    "Ты — ведущий аналитик и составитель управленческой отчетности. "
    "На основе переданных сводных данных сформируй официальный отчет для руководства:\n"
    "1) Executive Summary (2-3 главных вывода простыми словами);\n"
    "2) Анализ динамики и ключевых показателей (лидеры, отстающие, динамика изменений);\n"
    "3) Выявленные узкие места, риски и расхождения;\n"
    "4) Пошаговая структура слайдов презентации PowerPoint (Заголовок, 3 тезиса, ключевой акцент на цифре);\n"
    "5) Предложения конкретных управленческих решений.\n"
    "Стиль изложения — строгий деловой, структурированный, без общих фраз. "
    "Отвечай ТОЛЬКО валидным JSON-объектом без Markdown-тегов."
)


def _call_ollama(
    prompt: str,
    model: str,
    timeout: int,
) -> str:
    """Отправляет запрос к ИИ (сначала Google Gemini Flash, затем тихий fallback на Ollama)."""

    # 1. Попытка через облачный Gemini Flash
    try:
        import ai_service
        gemini_res = ai_service.generate_text(
            prompt=prompt,
            system_instruction=ANALYTICS_AI_SYSTEM_PROMPT,
            temperature=0.4,
            timeout=35,
        )
        if gemini_res and ("{" in gemini_res and "}" in gemini_res):
            try:
                _parse_response(gemini_res)
                return gemini_res
            except Exception:
                pass
    except Exception as exc:
        LOGGER.info("Gemini Flash пропущен (%s), переход на локальную модель...", exc)

    if not OLLAMA_URL:
        raise RuntimeError("Не задан адрес Ollama.")

    payload = {
        "model": model,
        "system": ANALYTICS_AI_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0.2,
            "num_ctx": 4096,
            "num_predict": 850,
            "repeat_penalty": 1.12,
            "repeat_last_n": 128,
        },
    }

    last_diagnostic = ""
    for attempt in range(2):
        current = dict(payload)
        current["options"] = dict(payload["options"])
        if attempt:
            # Повторная попытка остаётся в строгом JSON-режиме. Снятие
            # format=json приводило к многоязычному тексту и фрагментам кода.
            current["options"]["temperature"] = 0.18
            current["options"]["num_predict"] = 950
            current["options"]["repeat_penalty"] = 1.16
            current["options"]["repeat_last_n"] = 128
            current["prompt"] = prompt + (
                "\n\nПОВТОРНАЯ ПОПЫТКА: верни строго валидный JSON-объект. "
                "Сформируй 4 содержательных findings и 3 аналитических stories. "
                "Сохрани evidence, interpretation и limitation раздельно. "
                "Не повторяй фразы и обязательно закрой все скобки JSON."
            )

        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(current, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if attempt == 0 and "token repeat limit reached" in detail.casefold():
                last_diagnostic = "Qwen зациклилась на длинном ответе; выполняется краткая повторная попытка"
                continue
            if "token repeat limit reached" in detail.casefold():
                raise RuntimeError(
                    "Qwen дважды зациклилась при формировании JSON. "
                    "Перезапустите Ollama и повторите отчёт; данные Excel не повреждены."
                ) from exc
            raise RuntimeError(
                f"Ollama вернула HTTP {exc.code}: {_text(detail, 500)}"
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, OSError)) and "timed out" in str(exc.reason).casefold():
                raise TimeoutError(
                    f"Qwen не завершила ответ за {timeout} секунд."
                ) from exc
            if attempt == 0:
                last_diagnostic = f"URLError: {exc.reason}"
                continue
            raise RuntimeError(
                f"Не удалось подключиться к Ollama: {exc.reason}."
            ) from exc
        except (TimeoutError, OSError) as exc:
            # Не запускаем второй тяжёлый запрос после тайм-аута. Первый
            # процесс Ollama может ещё завершаться в фоне, поэтому повтор
            # лишь создаёт очередь и удваивает ожидание пользователя.
            raise RuntimeError(
                f"Модель не ответила за {timeout} секунд. "
                "Отчёт без ИИ не создавался."
            ) from exc
        try:
            response_data = json.loads(body)
        except json.JSONDecodeError as exc:
            if attempt == 0:
                last_diagnostic = "Некорректный JSON-конверт Ollama"
                continue
            raise RuntimeError("Ollama вернула некорректный ответ.") from exc

        if response_data.get("error"):
            raise RuntimeError(_text(response_data["error"], 500))

        response_text = str(response_data.get("response", "")).strip()
        if not response_text and isinstance(response_data.get("message"), dict):
            response_text = str(response_data["message"].get("content", "")).strip()
        if response_text:
            try:
                _parse_response(response_text)
                return response_text
            except ValueError:
                last_diagnostic = "модель вернула текст вместо JSON"
                continue

        last_diagnostic = (
            f"done_reason={response_data.get('done_reason') or 'не указан'}, "
            f"eval_count={response_data.get('eval_count', 0)}"
        )

    raise RuntimeError(
        "Ollama дважды не вернула корректный JSON. "
        f"Диагностика: {last_diagnostic or 'нет данных'}."
    )


def _normalize_model_result(
    parsed: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    """Проверяет и ограничивает поля ответа модели."""

    def allowed(text: str) -> bool:
        lowered = text.casefold()
        return not any(marker in lowered for marker in BANNED_OUTPUT_MARKERS)

    def recommendation_allowed(text: str) -> bool:
        """Rejects actions that turn a descriptive share into a fake problem."""
        lowered = text.casefold().replace("ё", "е")
        demographic = (
            "гражданств", "национальност", "страны", "страна", "пол ",
            "мужчин", "женщин", "язык обуч", "родной язык",
        )
        unsupported_investigation = (
            "исследовать причин", "изучить причин", "выяснить причин",
            "установить причин", "разобраться в причин", "проверить причин",
        )
        if (
            any(marker in lowered for marker in unsupported_investigation)
            and (
                any(marker in lowered for marker in demographic)
                or "высокой дол" in lowered
                or "преоблада" in lowered
                or "доминир" in lowered
            )
        ):
            return False
        # Форма финансирования не является показателем качества образования.
        if (
            ("качеств" in lowered or "успеваем" in lowered)
            and any(marker in lowered for marker in ("финансирован", "собственных средств", "грант"))
        ):
            return False
        return True

    # Qwen иногда сохраняет корректный JSON, но переводит ключи на русский
    # или помещает результат внутрь analysis/result. Принимаем эти безопасные
    # варианты, чтобы не терять полноценный ответ модели.
    for container_key in ("analysis", "result", "report", "анализ", "результат"):
        nested = parsed.get(container_key)
        if isinstance(nested, dict):
            parsed = nested
            break

    def field(*names: str) -> Any:
        for name in names:
            if name in parsed and parsed.get(name) not in (None, "", []):
                return parsed.get(name)
        return None

    raw_summary = _text(field(
        "summary", "executive_summary", "overview", "резюме",
        "краткое_резюме", "управленческое_резюме", "общий_вывод",
        "аннотация", "итог",
    ), 1200)
    summary = " ".join(
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", raw_summary)
        if part.strip() and allowed(part)
    )

    findings = _safe_list(
        field(
            "findings", "key_findings", "insights", "observations",
            "conclusions", "выводы", "ключевые_выводы", "основные_выводы",
            "наблюдения", "заключения", "факты",
        ), MAX_FINDINGS, 500
    )
    risks = _safe_list(
        field("risks", "риски", "зоны_риска"), MAX_RISKS, 500
    )
    recommendations = _safe_list(
        field(
            "recommendations", "actions", "next_steps", "рекомендации",
            "действия", "следующие_шаги",
        ), MAX_RECOMMENDATIONS, 500
    )
    limitations = _safe_list(
        field("limitations", "ограничения"), MAX_LIMITATIONS, 500
    )
    domain = _text(field("domain", "область", "предметная_область"), 120)
    report_title = _text(field("report_title", "title", "название_отчёта"), 180)
    report_subtitle = _text(field("report_subtitle", "subtitle", "подзаголовок"), 320)
    research_plan = _safe_list(
        field("research_plan", "analysis_plan", "план_исследования", "план_анализа"),
        12, 420,
    )
    stories = []
    raw_stories = field("stories", "analytical_stories", "сюжеты", "аналитические_сюжеты")
    if isinstance(raw_stories, list):
        for raw_story in raw_stories[:10]:
            if not isinstance(raw_story, dict):
                continue
            story = {
                "topic": _text(raw_story.get("topic") or raw_story.get("показатель"), 100),
                "story_type": _text(raw_story.get("story_type") or raw_story.get("тип"), 40),
                "headline": _text(raw_story.get("headline") or raw_story.get("заголовок"), 180),
                "evidence": _text(raw_story.get("evidence") or raw_story.get("факт"), 420),
                "interpretation": _text(raw_story.get("interpretation") or raw_story.get("интерпретация"), 520),
                "limitation": _text(raw_story.get("limitation") or raw_story.get("ограничение"), 420),
                "action": _text(raw_story.get("action") or raw_story.get("действие"), 420),
            }
            if story["topic"] and story["headline"] and story["evidence"]:
                stories.append(story)
    findings = [
        item for item in findings
        if allowed(item) and len(item) >= 10
    ][:MAX_FINDINGS]
    risks = [item for item in risks if allowed(item)][:3]
    recommendations = [
        item for item in recommendations
        if allowed(item) and recommendation_allowed(item)
    ][:4]
    limitations = []

    # Восстановление из cross_comparisons, если Qwen вернула группировки вместо findings
    if not findings and isinstance(parsed.get("cross_comparisons"), list):
        for comp in parsed["cross_comparisons"]:
            if not isinstance(comp, dict):
                continue
            for g in comp.get("groups", []):
                if isinstance(g, dict) and g.get("group") and g.get("leading_value"):
                    share = g.get("leading_share_percent", "")
                    share_text = f" ({share}%)" if share else ""
                    findings.append(f"В категории «{g['group']}» лидирует «{g['leading_value']}»{share_text}.")

    # Восстановление из columns, если Qwen вернула столбцы
    if not findings and isinstance(parsed.get("columns"), list):
        for col in parsed["columns"]:
            if not isinstance(col, dict):
                continue
            name = col.get("name")
            top_vals = col.get("top_values") or []
            if name and top_vals and isinstance(top_vals[0], dict):
                tv = top_vals[0]
                share = tv.get("share_percent", "")
                share_str = f" ({share}%)" if share else ""
                findings.append(f"По показателю «{name}» преобладает «{tv.get('value')}»{share_str}.")

    # Последняя совместимая страховка: некоторые версии Qwen создают свои
    # названия разделов. Извлекаем только содержательные текстовые элементы
    # с числами, не затрагивая технические или персональные поля.
    if not findings:
        recovered: list[str] = []

        def collect(value: Any) -> None:
            if len(recovered) >= 5:
                return
            if isinstance(value, dict):
                for nested_value in value.values():
                    collect(nested_value)
            elif isinstance(value, (list, tuple)):
                for nested_value in value:
                    collect(nested_value)
            elif isinstance(value, str):
                text = _text(value, 500)
                lowered = text.casefold()
                if (
                    text
                    and any(char.isdigit() for char in text)
                    and allowed(text)
                    and not any(marker in lowered for marker in SENSITIVE_MARKERS)
                    and text not in recovered
                ):
                    recovered.append(text)

        collect(parsed)
        findings = [item for item in recovered if len(item) >= 24][:5]

    # Qwen нередко возвращает содержательные данные, но пропускает один из
    # формально обязательных разделов. Не отбрасываем весь ответ: восстанавливаем
    # недостающие представления только из уже сгенерированных моделью фактов.
    if not findings and stories:
        findings = [
            story["evidence"] for story in stories
            if allowed(story.get("evidence", "")) and len(story.get("evidence", "")) >= 10
        ][:MAX_FINDINGS]

    if not summary:
        summary_parts = findings[:2] or [
            story["evidence"] for story in stories[:2] if story.get("evidence")
        ]
        summary = " ".join(summary_parts)

    if len(stories) < 2 and findings:
        existing_evidence = {story.get("evidence", "") for story in stories}
        for index, finding in enumerate(findings, 1):
            if finding in existing_evidence:
                continue
            stories.append({
                "topic": f"Ключевой показатель {index}",
                "story_type": "finding",
                "headline": finding[:180],
                "evidence": finding,
                "interpretation": "Вывод сформирован Qwen на основании переданной агрегированной статистики.",
                "limitation": "Вывод описывает текущий срез и не подтверждает динамику или причины.",
                "action": "",
            })
            if len(stories) >= 2:
                break

    if not summary or not findings:
        raise ValueError(
            "Qwen вернула JSON без содержательных числовых выводов. "
            "Соединение с Ollama установлено, но ответ модели неполный."
        )
    if len(stories) < 2:
        raise ValueError(
            "Qwen вернула слишком мало аналитических фактов для построения отчёта."
        )

    return {
        "available": True,
        "source": "ollama",
        "model": model,
        "domain": domain,
        "report_title": report_title,
        "report_subtitle": report_subtitle,
        "research_plan": research_plan,
        "stories": stories,
        "summary": summary,
        "findings": findings,
        "risks": risks,
        "recommendations": recommendations,
        "limitations": limitations,
        "warning": "",
    }


def generate_ai_analysis(
    matrix: Any,
    analytics: Any = None,
    model: str | None = None,
    timeout: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Формирует интерпретацию через Ollama.

    Если Ollama недоступна или ответ невалиден, возбуждает ошибку.
    Исходные строки Excel не передаются в промпт: используются агрегаты.
    Совместимо с вызовом из launcher.py.
    """

    title = _text(kwargs.get("title", ""), 200)
    description = _text(kwargs.get("description", ""), 700)
    report_profile = _text(kwargs.get("report_profile", "Автоматически"), 80)
    audience = _text(kwargs.get("audience", "Руководство"), 80)

    requested_model = _text(model or OLLAMA_MODEL, 100) or OLLAMA_MODEL

    try:
        timeout_value = max(
            5,
            int(timeout if timeout is not None else OLLAMA_TIMEOUT),
        )
    except (TypeError, ValueError):
        timeout_value = OLLAMA_TIMEOUT

    report_pages = kwargs.get("report_pages")
    compact = _compact_analysis(matrix, analytics, report_pages=report_pages)
    if not compact.get("row_count") or not compact.get("column_count"):
        raise ValueError("Недостаточно данных для ИИ-анализа.")

    try:
        prompt = _build_prompt(
            compact,
            title=title,
            description=description,
            report_profile=report_profile,
            audience=audience,
        )

        try:
            from ai_service import generate_text
            system_instruction = (
                "Ты — ведущий аналитик данных и составитель управленческой отчетности. "
                "Формируй глубокий структурированный анализ строго в формате JSON."
            )
            raw_response, provider = generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.3,
                timeout=timeout_value,
                return_provider=True,
            )
            model_name = f"BahonIQ AI ({provider})" if provider == "gemini" else "Ollama (qwen2.5)"
        except Exception as ai_err:
            LOGGER.warning("ai_service вызов не удался, пробуем прямой Ollama: %s", ai_err)
            model_name = _discover_ollama_model(requested_model, timeout_value)
            raw_response = _call_ollama(
                prompt,
                model=model_name,
                timeout=timeout_value,
            )

        parsed = _parse_response(raw_response)

        return _normalize_model_result(parsed, model_name)

    except Exception as exc:
        diagnostic = (
            "ИИ вернул ответ не в формате JSON."
            if "не удалось разобрать json" in str(exc).casefold()
            else _text(exc, 350)
        )
        LOGGER.error("ИИ-интерпретация не выполнена: %s", diagnostic)
        raise RuntimeError(
            "Не удалось завершить интеллектуальную интерпретацию. "
            "Отчёт без ИИ не создавался. "
            f"Причина: {diagnostic}"
        ) from exc
