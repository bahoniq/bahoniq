# -*- coding: utf-8 -*-
"""Комплексная сверка и аудит студенческих баз (режим comprehensive_audit)."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .comparison import _display, _empty, _prepare_sheet, _read_book, clean_iin, norm_fio

REQUIRED_SHEETS = [
    "Итоговая база",
    "Не найдены",
    "Неоднозначные совпадения",
    "Конфликты",
    "Дубликаты",
    "Ошибки данных",
    "Сводка",
]

CONFLICT_WATCH_FIELDS = (
    "Факультет",
    "Специальность",
    "Курс",
    "Задолженность",
)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def is_comprehensive_audit_request(instruction: str) -> bool:
    """Определяет, требует ли инструкция запуска отдельного режима comprehensive_audit."""
    text = (instruction or "").casefold().replace("ё", "е")
    if not text:
        return False

    has_complex = "комплексн" in text and any(w in text for w in ("сверк", "аудит", "провер", "анализ"))
    sheet_mentions = sum(
        1
        for name in ("итоговая база", "не найдены", "неоднозначные", "конфликты", "дубликаты", "ошибки данных", "сводка")
        if name in text
    )
    audit_actions = sum(
        1
        for marker in ("дубликат", "некорректн", "конфликт", "причину", "расхожден")
        if marker in text
    )
    return has_complex or sheet_mentions >= 3 or (sheet_mentions >= 2 and audit_actions >= 2)


def decompose_audit_requirements(instruction: str) -> dict[str, Any]:
    """Декомпозиция требований команды в формальную спецификацию для выполнения и постпроверки."""
    text = (instruction or "").casefold().replace("ё", "е")
    return {
        "mode": "comprehensive_audit",
        "required_sheets": list(REQUIRED_SHEETS),
        "identity_priority": ["iin", "email", "fio"],
        "merge_missing": True,
        "no_auto_conflict_resolution": ("не выбирай" in text and "конфликт" in text) or "конфликт" in text,
        "remove_exact_duplicates": "дубликат" in text,
        "keep_probable_duplicates": "вероятн" in text and "дубликат" in text,
        "validate_iin": "иин" in text,
        "validate_email": any(w in text for w in ("почт", "email", "e-mail")),
        "check_discrepancies": ["Факультет", "Специальность", "Курс", "Задолженность"],
        "require_decision_reason": "причин" in text or True,
        "preserve_sources": True,
    }


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_kazakh_iin(raw_iin: Any) -> tuple[bool, str, str]:
    """Проверяет ИИН РК: 12 цифр, дата рождения, код века/пола (1-6) и контрольный разряд."""
    iin = clean_iin(raw_iin)
    if not iin:
        return False, "", "ИИН отсутствует"
    if not re.fullmatch(r"\d{12}", iin):
        return False, iin, f"Неверный формат ИИН (ожидается 12 цифр, получено: {iin!r})"

    yy = int(iin[0:2])
    mm = int(iin[2:4])
    dd = int(iin[4:6])
    century_code = int(iin[6])

    if century_code not in (1, 2, 3, 4, 5, 6):
        return False, iin, f"Неверный 7-й разряд ИИН (век/пол): {century_code}"

    base_year = 1800 if century_code in (1, 2) else (1900 if century_code in (3, 4) else 2000)
    try:
        date(base_year + yy, mm, dd)
    except ValueError:
        return False, iin, f"Некорректная дата рождения в ИИН ({iin[:6]})"

    digits = [int(ch) for ch in iin]
    w1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    ctrl = sum(d * w for d, w in zip(digits[:11], w1)) % 11
    if ctrl == 10:
        w2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        ctrl = sum(d * w for d, w in zip(digits[:11], w2)) % 11
    if ctrl == 10 or ctrl != digits[11]:
        return False, iin, f"Несовпадение контрольной цифры ИИН (ожидалась {ctrl}, указана {digits[11]})"

    return True, iin, ""


def validate_email_address(raw_email: Any) -> tuple[bool, str, str]:
    """Проверяет корректность синтаксиса email-адреса."""
    email = _display(raw_email).strip()
    if not email:
        return False, "", "Email отсутствует"
    if any(ch.isspace() for ch in email):
        return False, email, "Email содержит пробелы"
    if re.search(r"[а-яА-ЯёЁәіңғүұқөһӘІҢҒҮҰҚӨҺ]", email):
        return False, email, "Email содержит кириллические символы"
    if not EMAIL_RE.fullmatch(email):
        return False, email, f"Некорректный синтаксис email: {email!r}"
    return True, email.casefold(), ""


def _detect_audit_columns(headers: list[str]) -> dict[str, Any]:
    """Определяет стандартные и дополнительные столбцы студенческой таблицы."""
    mapping: dict[str, Any] = {
        "iin": None,
        "fio": None,
        "fio_translit": None,
        "email": None,
        "faculty": None,
        "specialty": None,
        "course": None,
        "debt_direct": None,
        "debt_parts": [],
    }
    for h in headers:
        hl = h.strip().casefold()
        if not mapping["iin"] and ("иин" in hl or "iin" in hl or "жсн" in hl):
            mapping["iin"] = h
        elif not mapping["fio_translit"] and ("транслит" in hl or "латин" in hl):
            mapping["fio_translit"] = h
        elif not mapping["fio"] and ("фио" in hl or hl in ("студент", "обучающийся", "full name")):
            mapping["fio"] = h
        elif not mapping["email"] and any(w in hl for w in ("почт", "email", "e-mail")):
            mapping["email"] = h
        elif not mapping["faculty"] and any(w in hl for w in ("факультет", "школа", "институт")):
            mapping["faculty"] = h
        elif not mapping["specialty"] and any(w in hl for w in ("специальност", "гоп", "образовательн", "направлен")):
            mapping["specialty"] = h
        elif not mapping["course"] and re.search(r"\b(курс|course)\b", hl):
            mapping["course"] = h
        elif not mapping["debt_direct"] and any(w in hl for w in ("сумма долга", "задолженност", "общий долг")):
            mapping["debt_direct"] = h
        elif "баланс" in hl:
            mapping["debt_parts"].append(h)
    return mapping


def _to_number(value: Any) -> float | None:
    if _empty(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _compute_debt(row_dict: dict[str, Any], col_map: dict[str, Any]) -> str:
    if col_map["debt_direct"]:
        num = _to_number(row_dict.get(col_map["debt_direct"]))
        if num is not None:
            return str(int(num)) if num.is_integer() else f"{num:.2f}"
        return _display(row_dict.get(col_map["debt_direct"])).strip()
    if col_map["debt_parts"]:
        nums = [_to_number(row_dict.get(col)) for col in col_map["debt_parts"]]
        valid = [n for n in nums if n is not None]
        if valid:
            total = sum(valid)
            return str(int(total)) if total.is_integer() else f"{total:.2f}"
    return ""


def _normalize_scalar(value: Any) -> str:
    if _empty(value):
        return ""
    num = _to_number(value)
    if num is not None:
        return str(int(num)) if num.is_integer() else f"{num:.2f}"
    return re.sub(r"\s+", " ", _display(value).strip()).casefold().replace("ё", "е")


def _extract_records(sources: list[Path]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Читает все листы из всех файлов и преобразует строки в унифицированные записи."""
    records: list[dict[str, Any]] = []
    extra_headers: list[str] = []
    seen_extra = set()
    file_stats: list[dict[str, Any]] = []

    canonical_skip = {
        "иин", "фио", "фио транслитом", "email", "факультет", "специальность", "курс", "задолженность"
    }

    for file_idx, path in enumerate(sources, 1):
        books = _read_book(path)
        file_row_count = 0
        for raw_sheet in books:
            sheet = _prepare_sheet(raw_sheet)
            headers = sheet["headers"]
            rows = sheet["rows"]
            if not headers or not rows:
                continue
            col_map = _detect_audit_columns(headers)
            for h in headers:
                if h.strip().casefold() not in canonical_skip and h not in seen_extra:
                    seen_extra.add(h)
                    extra_headers.append(h)

            for r in rows:
                file_row_count += 1
                raw_dict = {h: (r["values"][i] if i < len(r["values"]) else None) for i, h in enumerate(headers)}
                raw_iin = raw_dict.get(col_map["iin"]) if col_map["iin"] else None
                iin_ok, iin_clean, iin_err = validate_kazakh_iin(raw_iin)

                raw_email = raw_dict.get(col_map["email"]) if col_map["email"] else None
                email_ok, email_clean, email_err = validate_email_address(raw_email)

                fio_val = _display(raw_dict.get(col_map["fio"])).strip() if col_map["fio"] else ""
                fio_tr_val = _display(raw_dict.get(col_map["fio_translit"])).strip() if col_map["fio_translit"] else ""
                faculty_val = _display(raw_dict.get(col_map["faculty"])).strip() if col_map["faculty"] else ""
                spec_val = _display(raw_dict.get(col_map["specialty"])).strip() if col_map["specialty"] else ""
                course_val = _display(raw_dict.get(col_map["course"])).strip() if col_map["course"] else ""
                debt_val = _compute_debt(raw_dict, col_map)

                rec = {
                    "uid": f"F{file_idx}:{sheet['name']}:{r['excel_row']}",
                    "file_idx": file_idx,
                    "file_name": path.name,
                    "sheet_name": sheet["name"],
                    "row_number": r["excel_row"],
                    "has_iin_col": bool(col_map["iin"]),
                    "iin_raw": _display(raw_iin).strip(),
                    "iin_clean": iin_clean,
                    "iin_valid": iin_ok,
                    "iin_error": iin_err if col_map["iin"] else "",
                    "has_email_col": bool(col_map["email"]),
                    "email_raw": _display(raw_email).strip(),
                    "email_clean": email_clean,
                    "email_valid": email_ok,
                    "email_error": email_err if col_map["email"] else "",
                    "fio": fio_val,
                    "fio_norm": norm_fio(fio_val),
                    "fio_translit": fio_tr_val,
                    "fio_tr_norm": norm_fio(fio_tr_val),
                    "faculty": faculty_val,
                    "specialty": spec_val,
                    "course": course_val,
                    "debt": debt_val,
                    "raw": raw_dict,
                }
                records.append(rec)

        file_stats.append({"file": path.name, "rows": file_row_count})
    return records, extra_headers, file_stats


def _collect_data_errors(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Собирает некорректные ИИН, некорректные email и пропуски ключевых идентификаторов."""
    errors: list[dict[str, Any]] = []
    for rec in records:
        if rec["has_iin_col"] and not rec["iin_valid"]:
            errors.append({
                "Источник": f"{rec['file_name']} / {rec['sheet_name']} (стр. {rec['row_number']})",
                "ФИО": rec["fio"] or rec["fio_translit"],
                "ИИН": rec["iin_raw"],
                "Email": rec["email_raw"],
                "Тип ошибки": "Некорректный ИИН",
                "Детали": rec["iin_error"],
                "Причина решения": f"Запись проверена по стандарту 12-значного ИИН РК: {rec['iin_error']}.",
            })
        if rec["has_email_col"] and not rec["email_valid"]:
            errors.append({
                "Источник": f"{rec['file_name']} / {rec['sheet_name']} (стр. {rec['row_number']})",
                "ФИО": rec["fio"] or rec["fio_translit"],
                "ИИН": rec["iin_raw"],
                "Email": rec["email_raw"],
                "Тип ошибки": "Некорректный email",
                "Детали": rec["email_error"],
                "Причина решения": f"Email не прошёл синтаксическую проверку: {rec['email_error']}.",
            })
    return errors


def _deduplicate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Удаляет полные дубликаты и фиксирует вероятные дубликаты для ручной проверки."""
    kept: list[dict[str, Any]] = []
    dup_rows: list[dict[str, Any]] = []

    seen_exact: dict[tuple[Any, ...], dict[str, Any]] = {}
    by_file_fio: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    by_file_email: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for rec in records:
        sig = (
            rec["file_idx"],
            rec["iin_clean"],
            rec["email_clean"],
            rec["fio_norm"],
            _normalize_scalar(rec["faculty"]),
            _normalize_scalar(rec["specialty"]),
            _normalize_scalar(rec["course"]),
            _normalize_scalar(rec["debt"]),
        )
        if sig in seen_exact:
            orig = seen_exact[sig]
            dup_rows.append({
                "Тип дубликата": "Полный дубликат (удалён)",
                "Основная запись": orig["uid"],
                "Дубликат": rec["uid"],
                "ИИН": rec["iin_clean"] or rec["iin_raw"],
                "Email": rec["email_raw"],
                "ФИО": rec["fio"] or rec["fio_translit"],
                "Причина решения": f"Полное совпадение всех ключевых атрибутов с записью {orig['uid']}; дубликат удалён из обработки.",
            })
            continue

        seen_exact[sig] = rec
        kept.append(rec)

        if rec["fio_norm"]:
            by_file_fio[(rec["file_idx"], rec["fio_norm"])].append(rec)
        if rec["email_clean"]:
            by_file_email[(rec["file_idx"], rec["email_clean"])].append(rec)

    flagged_pairs: set[tuple[str, str]] = set()
    for group in list(by_file_fio.values()) + list(by_file_email.values()):
        if len(group) < 2:
            continue
        anchor = group[0]
        for other in group[1:]:
            pair = tuple(sorted((anchor["uid"], other["uid"])))
            if pair in flagged_pairs:
                continue
            flagged_pairs.add(pair)
            dup_rows.append({
                "Тип дубликата": "Вероятный дубликат (на проверку)",
                "Основная запись": anchor["uid"],
                "Дубликат": other["uid"],
                "ИИН": f"{anchor['iin_clean'] or anchor['iin_raw']} / {other['iin_clean'] or other['iin_raw']}",
                "Email": f"{anchor['email_raw']} / {other['email_raw']}",
                "ФИО": f"{anchor['fio']} / {other['fio']}",
                "Причина решения": "Совпадение ФИО или email внутри одного источника при различии прочих полей; сохранено для ручной проверки.",
            })

    return kept, dup_rows


def _compatible_iin(rec: dict[str, Any], card_group: list[dict[str, Any]]) -> bool:
    """Запрещает объединение записей с разными 12-значными ИИН."""
    rec_iin = rec["iin_clean"] if len(rec["iin_clean"]) == 12 else ""
    if not rec_iin:
        return True
    card_iins = {r["iin_clean"] for r in card_group if len(r["iin_clean"]) == 12}
    return not card_iins or rec_iin in card_iins


def _compatible_fio(rec: dict[str, Any], card_group: list[dict[str, Any]]) -> bool:
    """Проверяет совместимость ФИО/транслита при отсутствии совпадения по ИИН."""
    if not rec["fio_norm"] and not rec["fio_tr_norm"]:
        return True
    for r in card_group:
        if rec["fio_norm"] and r["fio_norm"] and rec["fio_norm"] == r["fio_norm"]:
            return True
        if rec["fio_tr_norm"] and r["fio_tr_norm"] and rec["fio_tr_norm"] == r["fio_tr_norm"]:
            return True
    return False


def _identity_candidates(
    rec: dict[str, Any],
    card_index: dict[str, dict[str, list[int]]],
    cards: list[list[dict[str, Any]]],
) -> tuple[list[int], str]:
    """Подбирает карточки-кандидаты по приоритету: ИИН -> Email + ФИО -> нормализованное ФИО/транслит."""
    rec_iin = rec["iin_clean"] if len(rec["iin_clean"]) == 12 else ""
    if rec_iin and rec_iin in card_index["iin"]:
        return card_index["iin"][rec_iin], "Сопоставлено по ИИН"

    if rec["email_valid"] and rec["email_clean"] in card_index["email"]:
        cands = [
            cid for cid in card_index["email"][rec["email_clean"]]
            if _compatible_iin(rec, cards[cid]) and _compatible_fio(rec, cards[cid])
        ]
        if cands:
            return cands, "Сопоставлено по электронной почте и ФИО (ИИН отсутствует или не совпал)"

    if rec["fio_norm"] and rec["fio_norm"] in card_index["fio"]:
        cands = [cid for cid in card_index["fio"][rec["fio_norm"]] if _compatible_iin(rec, cards[cid])]
        if cands:
            return cands, "Сопоставлено по нормализованному ФИО"

    if rec["fio_tr_norm"] and rec["fio_tr_norm"] in card_index["fio_tr"]:
        cands = [cid for cid in card_index["fio_tr"][rec["fio_tr_norm"]] if _compatible_iin(rec, cards[cid])]
        if cands:
            return cands, "Сопоставлено по ФИО транслитом"

    return [], ""


def _index_card(card_id: int, rec: dict[str, Any], card_index: dict[str, dict[str, list[int]]]) -> None:
    if len(rec["iin_clean"]) == 12:
        card_index["iin"].setdefault(rec["iin_clean"], [])
        if card_id not in card_index["iin"][rec["iin_clean"]]:
            card_index["iin"][rec["iin_clean"]].append(card_id)
    if rec["email_valid"] and rec["email_clean"]:
        card_index["email"].setdefault(rec["email_clean"], [])
        if card_id not in card_index["email"][rec["email_clean"]]:
            card_index["email"][rec["email_clean"]].append(card_id)
    if rec["fio_norm"]:
        card_index["fio"].setdefault(rec["fio_norm"], [])
        if card_id not in card_index["fio"][rec["fio_norm"]]:
            card_index["fio"][rec["fio_norm"]].append(card_id)
    if rec["fio_tr_norm"]:
        card_index["fio_tr"].setdefault(rec["fio_tr_norm"], [])
        if card_id not in card_index["fio_tr"][rec["fio_tr_norm"]]:
            card_index["fio_tr"][rec["fio_tr_norm"]].append(card_id)


def _merge_cards_and_detect_conflicts(
    cards: list[list[dict[str, Any]]],
    extra_headers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Строит итоговые карточки без автовыбора при конфликте и формирует лист конфликтов."""
    final_rows: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, Any]] = []

    field_extractors = {
        "ИИН": lambda r: r["iin_clean"] or r["iin_raw"],
        "ФИО": lambda r: r["fio"],
        "ФИО транслитом": lambda r: r["fio_translit"],
        "Email": lambda r: r["email_raw"],
        "Факультет": lambda r: r["faculty"],
        "Специальность": lambda r: r["specialty"],
        "Курс": lambda r: r["course"],
        "Задолженность": lambda r: r["debt"],
    }

    for group in cards:
        # Основная карточка выбирается по приоритету: валидный ИИН -> наибольшая полнота данных
        primary = max(
            group,
            key=lambda r: (
                1 if r["iin_valid"] else 0,
                1 if r["email_valid"] else 0,
                sum(1 for k in field_extractors if field_extractors[k](r)),
                -r["file_idx"],
            ),
        )
        primary_reason = (
            f"Основная карточка {primary['uid']} определена по ИИН"
            if primary["iin_valid"]
            else f"Основная карточка {primary['uid']} определена по email/ФИО (ИИН отсутствует)"
        )

        merged: dict[str, Any] = {
            "Основная карточка": primary["uid"],
            "Источники": ", ".join(r["uid"] for r in group),
        }
        has_conflict = False
        merged_fields = []

        all_fields = list(field_extractors.keys()) + extra_headers
        for field in all_fields:
            vals_by_source: list[tuple[str, str]] = []
            for r in group:
                val = field_extractors[field](r) if field in field_extractors else _display(r["raw"].get(field)).strip()
                if val:
                    vals_by_source.append((r["uid"], val))

            unique_norm: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for uid, val in vals_by_source:
                unique_norm[_normalize_scalar(val)].append((uid, val))

            if not unique_norm:
                merged[field] = ""
            elif len(unique_norm) == 1:
                chosen_val = next(iter(unique_norm.values()))[0][1]
                merged[field] = chosen_val
                prim_val = field_extractors[field](primary) if field in field_extractors else _display(primary["raw"].get(field)).strip()
                if not prim_val and chosen_val:
                    merged_fields.append(field)
            else:
                has_conflict = True
                details = " | ".join(f"{uid}: {val}" for uid, val in vals_by_source)
                merged[field] = f"[КОНФЛИКТ] {details}"
                conflict_rows.append({
                    "Основная карточка": primary["uid"],
                    "ИИН": primary["iin_clean"] or primary["iin_raw"],
                    "ФИО": primary["fio"] or primary["fio_translit"],
                    "Поле конфликта": field,
                    "Категория расхождения": field if field in CONFLICT_WATCH_FIELDS else "Прочие сведения",
                    "Значения по источникам": details,
                    "Причина решения": "Обнаружены различающиеся непустые значения в источниках; автоматический выбор запрещён.",
                })

        reason_parts = [primary_reason]
        if len(group) > 1:
            reason_parts.append(f"объединено записей: {len(group)}")
        if merged_fields:
            reason_parts.append("дополнены поля: " + ", ".join(merged_fields[:6]))
        if has_conflict:
            reason_parts.append("обнаружены конфликты (отмечены без автовыбора)")
        merged["Причина решения"] = "; ".join(reason_parts) + "."
        final_rows.append(merged)

    return final_rows, conflict_rows


def _style_and_write_sheet(wb: Workbook, title: str, headers: list[str], rows: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet(title=title)
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row_idx, item in enumerate(rows, 2):
        for col_idx, h in enumerate(headers, 1):
            val = item.get(h, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            if isinstance(val, str) and val.startswith("[КОНФЛИКТ]"):
                cell.fill = PatternFill("solid", fgColor="FEF3C7")
                cell.font = Font(bold=True, color="92400E")

    for col_idx, h in enumerate(headers, 1):
        max_len = len(str(h))
        for r in rows[:100]:
            max_len = max(max_len, min(60, len(str(r.get(h, "")))))
        ws.column_dimensions[get_column_letter(col_idx)].width = max(14, min(48, max_len + 4))
    ws.freeze_panes = "A2"


def verify_comprehensive_audit_result(
    output_path: Path,
    requirements: dict[str, Any],
    source_hashes_before: dict[str, str],
    sources: list[Path],
    expected_counts: dict[str, int],
) -> dict[str, Any]:
    """Обязательная постпроверка результата на соответствие каждому требованию команды."""
    checks: dict[str, bool] = {}
    errors: list[str] = []

    if not output_path.is_file():
        return {"passed": False, "checks": {"output_exists": False}, "errors": ["Выходной файл не создан."]}

    wb = load_workbook(output_path, read_only=True, data_only=True)
    actual_sheets = list(wb.sheetnames)
    checks["exact_7_sheets"] = actual_sheets == requirements["required_sheets"]
    if not checks["exact_7_sheets"]:
        errors.append(f"Ожидались листы {requirements['required_sheets']}, получены {actual_sheets}.")

    reasons_ok = True
    for sheet_name in requirements["required_sheets"][:-1]:
        if sheet_name not in wb.sheetnames:
            reasons_ok = False
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            reasons_ok = False
            errors.append(f"На листе «{sheet_name}» отсутствует строка заголовков.")
            continue
        headers = [str(x or "") for x in rows[0]]
        if "Причина решения" not in headers:
            reasons_ok = False
            errors.append(f"На листе «{sheet_name}» отсутствует столбец «Причина решения».")
        else:
            r_idx = headers.index("Причина решения")
            for idx, r in enumerate(rows[1:], 2):
                if r_idx >= len(r) or _empty(r[r_idx]):
                    reasons_ok = False
                    errors.append(f"На листе «{sheet_name}» в строке {idx} не заполнена причина решения.")
                    break
    checks["decision_reasons_present"] = reasons_ok

    sources_unchanged = all(_file_sha256(p) == source_hashes_before[str(p)] for p in sources)
    checks["sources_unchanged"] = sources_unchanged
    if not sources_unchanged:
        errors.append("Обнаружено изменение одного из исходных файлов.")

    checks["conflicts_not_auto_resolved"] = True
    if expected_counts.get("conflicts", 0) > 0 and "Конфликты" in wb.sheetnames:
        c_rows = list(wb["Конфликты"].iter_rows(values_only=True))
        if len(c_rows) <= 1:
            checks["conflicts_not_auto_resolved"] = False
            errors.append("Конфликты выявлены, но лист «Конфликты» пуст.")

    wb.close()
    return {
        "passed": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
    }


def run_comprehensive_audit(sources: list[Path], instruction: str, output_path: Path) -> dict[str, Any]:
    """Выполняет комплексную сверку, аудит качества данных и обязательную постпроверку."""
    requirements = decompose_audit_requirements(instruction)
    source_hashes_before = {str(p): _file_sha256(p) for p in sources}

    raw_records, extra_headers, file_stats = _extract_records(sources)
    data_errors = _collect_data_errors(raw_records)
    deduped_records, duplicate_rows = _deduplicate_records(raw_records)

    cards: list[list[dict[str, Any]]] = []
    card_index: dict[str, dict[str, list[int]]] = {"iin": {}, "email": {}, "fio": {}, "fio_tr": {}}
    ambiguous_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []

    # Сначала формируем карточки из самого крупного/основного файла (или первого с ИИН)
    anchor_file_idx = max(
        range(1, len(sources) + 1),
        key=lambda idx: (
            sum(1 for r in deduped_records if r["file_idx"] == idx and r["iin_valid"]),
            sum(1 for r in deduped_records if r["file_idx"] == idx),
        ),
    )

    anchor_records = [r for r in deduped_records if r["file_idx"] == anchor_file_idx]
    other_records = [r for r in deduped_records if r["file_idx"] != anchor_file_idx]

    for rec in anchor_records:
        cands, _ = _identity_candidates(rec, card_index, cards)
        if not cands:
            card_id = len(cards)
            cards.append([rec])
            _index_card(card_id, rec, card_index)
        elif len(cands) == 1:
            cards[cands[0]].append(rec)
            _index_card(cands[0], rec, card_index)
        else:
            ambiguous_rows.append({
                "Источник": rec["uid"],
                "ИИН": rec["iin_clean"] or rec["iin_raw"],
                "Email": rec["email_raw"],
                "ФИО": rec["fio"] or rec["fio_translit"],
                "Кандидаты": ", ".join(cards[c][0]["uid"] for c in cands),
                "Причина решения": f"Найдено {len(cands)} карточек-кандидатов в опорном файле; слияние отложено.",
            })

    matched_other = 0
    for rec in other_records:
        cands, match_reason = _identity_candidates(rec, card_index, cards)
        if not cands:
            card_id = len(cards)
            cards.append([rec])
            _index_card(card_id, rec, card_index)
            unmatched_rows.append({
                "Источник": rec["uid"],
                "ИИН": rec["iin_clean"] or rec["iin_raw"],
                "Email": rec["email_raw"],
                "ФИО": rec["fio"] or rec["fio_translit"],
                "Причина решения": "Совпадение не найдено ни по ИИН, ни по email, ни по нормализованному ФИО/транслиту; добавлен в базу как отдельная карточка.",
            })
        elif len(cands) == 1:
            matched_other += 1
            cards[cands[0]].append(rec)
            _index_card(cands[0], rec, card_index)
        else:
            ambiguous_rows.append({
                "Источник": rec["uid"],
                "ИИН": rec["iin_clean"] or rec["iin_raw"],
                "Email": rec["email_raw"],
                "ФИО": rec["fio"] or rec["fio_translit"],
                "Кандидаты": ", ".join(cards[c][0]["uid"] for c in cands),
                "Причина решения": f"Найдено {len(cands)} карточек-кандидатов ({match_reason}); автоматическое слияние не выполнено.",
            })

    final_rows, conflict_rows = _merge_cards_and_detect_conflicts(cards, extra_headers)

    # Формируем сводку
    exact_dups = sum(1 for d in duplicate_rows if d["Тип дубликата"].startswith("Полный"))
    prob_dups = sum(1 for d in duplicate_rows if d["Тип дубликата"].startswith("Вероятный"))
    invalid_iins = sum(1 for e in data_errors if e["Тип ошибки"] == "Некорректный ИИН")
    invalid_emails = sum(1 for e in data_errors if e["Тип ошибки"] == "Некорректный email")

    summary_rows = [
        {"Показатель": "Загружено файлов", "Значение": len(sources), "Комментарий": ", ".join(f"{s['file']} ({s['rows']} стр.)" for s in file_stats)},
        {"Показатель": "Всего исходных строк", "Значение": len(raw_records), "Комментарий": "Все непустые строки из загруженных книг"},
        {"Показатель": "Карточек в «Итоговая база»", "Значение": len(final_rows), "Комментарий": f"Опорный файл #{anchor_file_idx}"},
        {"Показатель": "Сопоставлено записей из доп. файлов", "Значение": matched_other, "Комментарий": "ИИН -> Email -> ФИО -> Транслит"},
        {"Показатель": "Не найдены", "Значение": len(unmatched_rows), "Комментарий": "Вынесены на лист «Не найдены»"},
        {"Показатель": "Неоднозначные совпадения", "Значение": len(ambiguous_rows), "Комментарий": "Вынесены на лист «Неоднозначные совпадения»"},
        {"Показатель": "Конфликты значений", "Значение": len(conflict_rows), "Комментарий": "Без автоматического выбора, отмечены на листе «Конфликты»"},
        {"Показатель": "Полные дубликаты (удалены)", "Значение": exact_dups, "Комментарий": "Зафиксированы на листе «Дубликаты»"},
        {"Показатель": "Вероятные дубликаты (на проверку)", "Значение": prob_dups, "Комментарий": "Сохранены на листе «Дубликаты»"},
        {"Показатель": "Некорректные ИИН", "Значение": invalid_iins, "Комментарий": "Проверка 12 цифр, даты рождения, века и контрольного разряда"},
        {"Показатель": "Некорректные email", "Значение": invalid_emails, "Комментарий": "Синтаксис, пробелы, кириллица, пустые значения"},
    ]

    wb = Workbook()
    wb.remove(wb.active)

    final_headers = [
        "Основная карточка", "Источники", "ИИН", "ФИО", "ФИО транслитом", "Email",
        "Факультет", "Специальность", "Курс", "Задолженность",
        *extra_headers,
        "Причина решения",
    ]
    _style_and_write_sheet(wb, "Итоговая база", final_headers, final_rows)
    _style_and_write_sheet(wb, "Не найдены", ["Источник", "ИИН", "Email", "ФИО", "Причина решения"], unmatched_rows)
    _style_and_write_sheet(wb, "Неоднозначные совпадения", ["Источник", "ИИН", "Email", "ФИО", "Кандидаты", "Причина решения"], ambiguous_rows)
    _style_and_write_sheet(
        wb,
        "Конфликты",
        ["Основная карточка", "ИИН", "ФИО", "Поле конфликта", "Категория расхождения", "Значения по источникам", "Причина решения"],
        conflict_rows,
    )
    _style_and_write_sheet(wb, "Дубликаты", ["Тип дубликата", "Основная запись", "Дубликат", "ИИН", "Email", "ФИО", "Причина решения"], duplicate_rows)
    _style_and_write_sheet(wb, "Ошибки данных", ["Источник", "ФИО", "ИИН", "Email", "Тип ошибки", "Детали", "Причина решения"], data_errors)
    _style_and_write_sheet(wb, "Сводка", ["Показатель", "Значение", "Комментарий"], summary_rows)

    wb.save(output_path)

    counts = {
        "total_rows": len(raw_records),
        "final_cards": len(final_rows),
        "matched": matched_other,
        "unmatched": len(unmatched_rows),
        "ambiguous": len(ambiguous_rows),
        "conflicts": len(conflict_rows),
        "exact_duplicates": exact_dups,
        "probable_duplicates": prob_dups,
        "invalid_iin": invalid_iins,
        "invalid_email": invalid_emails,
    }
    verification = verify_comprehensive_audit_result(
        output_path=output_path,
        requirements=requirements,
        source_hashes_before=source_hashes_before,
        sources=sources,
        expected_counts=counts,
    )

    return {
        "requirements": requirements,
        "counts": counts,
        "verification": verification,
    }
