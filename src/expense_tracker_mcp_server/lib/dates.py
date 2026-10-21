"""
lib/dates.py — Date and month helper utilities.

All operations use UTC to ensure consistent behaviour regardless of
the server's local timezone.
"""

import calendar
import re
from datetime import date, datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def today_iso() -> str:
    """Return today's UTC date as an ISO 8601 string (YYYY-MM-DD)."""
    return utc_now().date().isoformat()


def now_iso() -> str:
    """Return the current UTC datetime as an ISO 8601 string."""
    return utc_now().isoformat()


def current_month() -> str:
    """Return the current calendar month as 'YYYY-MM'."""
    return utc_now().strftime("%Y-%m")


def is_valid_month(month: str) -> bool:
    """Return True if *month* matches 'YYYY-MM' and is a real calendar month."""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return False
    try:
        year, mo = int(month[:4]), int(month[5:])
        return 1 <= mo <= 12
    except ValueError:
        return False


def month_range(month: str) -> tuple[str, str]:
    """
    Return the (first_date, last_date) ISO strings for the given month.

    Parameters
    ----------
    month: str
        Calendar month in 'YYYY-MM' format.

    Returns
    -------
    tuple[str, str]
        (first_day_iso, last_day_iso)

    Examples
    --------
    >>> month_range("2026-02")
    ('2026-02-01', '2026-02-28')
    >>> month_range("2024-02")   # leap year
    ('2024-02-01', '2024-02-29')
    """
    year, mo = int(month[:4]), int(month[5:])
    _, last_day = calendar.monthrange(year, mo)
    first = date(year, mo, 1).isoformat()
    last = date(year, mo, last_day).isoformat()
    return first, last


def previous_month(month: str) -> str:
    """
    Return the month immediately before the given one.

    >>> previous_month("2026-01")
    '2025-12'
    >>> previous_month("2026-07")
    '2026-06'
    """
    year, mo = int(month[:4]), int(month[5:])
    if mo == 1:
        return f"{year - 1}-12"
    return f"{year}-{mo - 1:02d}"


def month_label(month: str) -> str:
    """
    Return a human-readable month label.

    >>> month_label("2026-07")
    'July 2026'
    """
    year, mo = int(month[:4]), int(month[5:])
    return date(year, mo, 1).strftime("%B %Y")
