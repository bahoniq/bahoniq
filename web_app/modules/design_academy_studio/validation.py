"""Детерминированная проверка учебного SVG-документа."""

from __future__ import annotations

from typing import Any


def _objects(document: dict[str, Any], object_type: str | None = None) -> list[dict[str, Any]]:
    items = document.get("objects", []) if isinstance(document, dict) else []
    return [x for x in items if isinstance(x, dict) and (not object_type or x.get("type") == object_type)]


def validate_document(document: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for rule in checks:
        kind, object_type = rule.get("kind"), rule.get("type")
        items = _objects(document, object_type)
        passed, message = False, "Требование не выполнено."
        tol = float(rule.get("tolerance", 0))
        if kind == "type":
            passed = len(items) >= int(rule.get("min", 1)); message = f"Объектов «{object_type}»: {len(items)}"
        elif kind == "size":
            passed = any(abs(float(x.get("width", 0))-rule["width"]) <= tol and abs(float(x.get("height", 0))-rule["height"]) <= tol for x in items)
            message = f"Нужен объект {rule['width']} × {rule['height']} px"
        elif kind == "geometry":
            keys = ("x", "y", "width", "height")
            passed = any(all(abs(float(x.get(k, 0))-float(rule[k])) <= tol for k in keys) for x in items)
            message = "Проверьте X, Y, ширину и высоту объекта"
        elif kind in {"radius", "opacity", "font_size"}:
            key = {"radius": "radius", "opacity": "opacity", "font_size": "fontSize"}[kind]
            passed = any(abs(float(x.get(key, 0))-float(rule["value"])) <= tol for x in items)
            message = f"Параметр {key} должен быть равен {rule['value']}"
        elif kind == "fill":
            passed = any(str(x.get("fill", "")).lower() == str(rule["value"]).lower() for x in items); message = f"Заливка: {rule['value']}"
        elif kind == "stroke":
            passed = any(str(x.get("stroke", "")).lower() == str(rule["value"]).lower() and abs(float(x.get("strokeWidth", 0))-float(rule.get("width", 1))) <= .25 for x in items); message = f"Обводка: {rule['value']}, {rule.get('width', 1)} px"
        elif kind == "aligned_y" and len(items) >= 3:
            passed = max(float(x.get("y", 0)) for x in items)-min(float(x.get("y", 0)) for x in items) <= tol; message = "Три объекта должны находиться на общей горизонтальной оси"
        elif kind == "gap" and len(items) >= 2:
            ordered = sorted(items, key=lambda x: float(x.get("x", 0)))
            gaps = [float(b.get("x", 0))-(float(a.get("x", 0))+float(a.get("width", 0))) for a, b in zip(ordered, ordered[1:])]
            passed = any(abs(g-float(rule["value"])) <= tol for g in gaps); message = f"Промежуток должен быть {rule['value']} px"
        elif kind == "named":
            generic = {"Прямоугольник", "Круг", "Текст", "Фрейм", "Линия", "Группа"}
            passed = sum(1 for x in _objects(document) if x.get("name") and x.get("name") not in generic) >= int(rule.get("min", 1)); message = "Переименуйте слои понятными именами"
        results.append({"passed": passed, "message": message, "rule": kind})
    passed_count = sum(1 for item in results if item["passed"])
    score = round(100 * passed_count / max(len(results), 1))
    return {"passed": score == 100, "score": score, "passed_count": passed_count,
            "total": len(results), "results": results}
