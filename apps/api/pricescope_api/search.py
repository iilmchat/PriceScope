"""Регистронезависимый поиск по подстроке.

SQLite `LOWER()` не понимает кириллицу, поэтому `ILIKE('%...%')` ломается
 на русских названиях. Фильтруем в Python через `casefold()`.
"""


def matches(text: str | None, query: str) -> bool:
    """True, если `query` (без регистра) входит в `text`."""
    if not query:
        return True
    return query.casefold() in (text or "").casefold()
