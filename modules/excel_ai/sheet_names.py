"""Bind references to existing workbook names; never invent source sheets."""
import re


def resolve_sheet_name(value, names):
    names = list(names)
    if value in names:
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Не указан исходный лист.")
    key = lambda s: re.sub(r"\s+", " ", s.strip()).casefold()
    matches = [name for name in names if key(name) == key(value)]
    # Excel truncates names at 31 characters. Accept only the specific
    # extra closing punctuation defect, never an arbitrary prefix/fuzzy match.
    if not matches:
        matches = [name for name in names if len(name) == 31
                   and value.startswith(name)
                   and re.fullmatch(r"[)\]}\s]+", value[len(name):])]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(f"Имя листа {value!r} неоднозначно: {matches!r}.")
    raise ValueError(f"Лист {value!r} не найден. Доступные листы: {', '.join(names)}")
