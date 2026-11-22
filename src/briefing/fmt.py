"""Values formatted for prose (#184): dates, spans of dates, percentages and numbers, in English.

Example::

    f"Searches rose {bf.fmt.percent(0.253, sign=True)} from {bf.fmt.span(start, end)}."
    # 'Searches rose +25% from November 19 to 20.'
"""
from __future__ import annotations

import datetime as dt
import math
import numbers

from briefing._error import BriefingError

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]


def _day(value: object, where: str) -> dt.date:
    """*value* as a date: a date, a datetime (or pandas Timestamp) or an ISO string."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.strip()).date()
        except ValueError:
            pass
    raise BriefingError(f"bf.fmt.{where}: a date, a datetime or an ISO string such as '2026-11-19', not {value!r}.")


def _real(value: object, where: str) -> float:
    if not isinstance(value, numbers.Real) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise BriefingError(f"bf.fmt.{where}: a finite number, not {value!r}.")
    return float(value)


def date(day: object, style: str = "long") -> str:
    """A date as prose: ``"November 19, 2026"``, or ``"Nov 19"`` with ``style="short"``.

    Args:
        day: A date, a datetime, a pandas Timestamp or an ISO string.
        style: ``"long"`` (month, day and year) or ``"short"`` (abbreviated month and day).

    Example::

        bf.fmt.date("2026-11-19")                 # 'November 19, 2026'
        bf.fmt.date("2026-11-19", style="short")  # 'Nov 19'
    """
    d = _day(day, "date")
    if style == "long":
        return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"
    if style == "short":
        return f"{_MONTHS[d.month - 1][:3]} {d.day}"
    raise BriefingError(f"bf.fmt.date: style is 'long' or 'short', not {style!r}.")


def span(start: object, end: object) -> str:
    """Two dates as a span, saying each part once: ``"November 19 to 20"``.

    Args:
        start: The first day.
        end: The last day.

    Example::

        bf.fmt.span("2026-11-19", "2026-11-20")  # 'November 19 to 20'
        bf.fmt.span("2026-11-30", "2026-12-02")  # 'November 30 to December 2'
        bf.fmt.span("2026-12-30", "2027-01-02")  # 'December 30, 2026 to January 2, 2027'
    """
    a, b = _day(start, "span"), _day(end, "span")
    if b < a:
        raise BriefingError(f"bf.fmt.span: end ({b}) is before start ({a}).")
    if a == b:
        return f"{_MONTHS[a.month - 1]} {a.day}"
    if a.year != b.year:
        return f"{date(a)} to {date(b)}"
    if a.month != b.month:
        return f"{_MONTHS[a.month - 1]} {a.day} to {_MONTHS[b.month - 1]} {b.day}"
    return f"{_MONTHS[a.month - 1]} {a.day} to {b.day}"


def number(value: object, digits: int = 0, sign: bool = False) -> str:
    """A number with thousands separators: ``"12,345"``.

    Args:
        value: The number.
        digits: Decimals to show.
        sign: Put ``+`` before a positive number.

    Example::

        bf.fmt.number(12345)                  # '12,345'
        bf.fmt.number(1234.5, digits=1)       # '1,234.5'
        bf.fmt.number(41, sign=True)          # '+41'
    """
    v = _real(value, "number")
    return f"{v:{'+' if sign else ''},.{int(digits)}f}"


def percent(value: object, digits: int = 0, sign: bool = False) -> str:
    """A fraction as a percentage: ``0.253`` is ``"25%"``.

    Args:
        value: The fraction (``0.253`` for 25.3 %).
        digits: Decimals to show.
        sign: Put ``+`` before a positive change.

    Example::

        bf.fmt.percent(0.253)              # '25%'
        bf.fmt.percent(0.253, sign=True)   # '+25%'
        bf.fmt.percent(0.253, digits=1)    # '25.3%'
    """
    v = _real(value, "percent")
    return f"{v * 100:{'+' if sign else ''},.{int(digits)}f}%"


__all__ = ["date", "number", "percent", "span"]
