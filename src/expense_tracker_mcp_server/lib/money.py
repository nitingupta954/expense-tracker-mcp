"""
lib/money.py — Money conversion and formatting helpers.

All arithmetic uses decimal.Decimal to avoid floating-point rounding bugs
(e.g. 19.995 cents must land on 2000, not 1999).
"""

import os
from decimal import ROUND_HALF_UP, Decimal

# Currency symbol map (extend as needed).
_CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "SGD": "S$",
    "AED": "د.إ",
}

_DEFAULT_CURRENCY = os.environ.get("EXPENSE_DEFAULT_CURRENCY", "INR")


def to_cents(amount: float) -> int:
    """
    Convert a decimal currency amount to integer cents.

    Uses Decimal with ROUND_HALF_UP to avoid floating-point errors.

    >>> to_cents(19.995)
    2000
    >>> to_cents(0.005)
    1
    >>> to_cents(1234.50)
    123450
    """
    d = Decimal(str(amount))
    cents = d * Decimal("100")
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> float:
    """
    Convert integer cents back to a decimal currency float.

    >>> from_cents(123450)
    1234.5
    >>> from_cents(1)
    0.01
    """
    return float(Decimal(cents) / Decimal("100"))


def format_money(cents: int, currency: str | None = None) -> str:
    """
    Format an integer cent value as a human-readable currency string.

    Examples
    --------
    >>> format_money(123450, "INR")
    '₹1,234.50'
    >>> format_money(99, "USD")
    '$0.99'
    """
    if currency is None:
        currency = _DEFAULT_CURRENCY

    amount = from_cents(cents)
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency + " ")
    return f"{symbol}{amount:,.2f}"
