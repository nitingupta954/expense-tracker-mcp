"""
lib/models.py — Shared Pydantic v2 validation models.

These are used by tools to validate incoming parameters before touching the DB.
"""

import re
from datetime import date as _date
from typing import Annotated

from pydantic import BaseModel, field_validator, model_validator


# ── Primitive constrained types ──────────────────────────────────────────────

class CategoryName(BaseModel):
    """A non-empty category name, max 50 characters."""
    value: Annotated[str, ...]

    @field_validator("value")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Category name must not be empty.")
        if len(v) > 50:
            raise ValueError(f"Category name too long ({len(v)} chars, max 50).")
        return v


class Month(BaseModel):
    """A calendar month in 'YYYY-MM' format."""
    value: str

    @field_validator("value")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}", v):
            raise ValueError(f"Month must be in YYYY-MM format, got: {v!r}")
        year, month = int(v[:4]), int(v[5:])
        if not (1 <= month <= 12):
            raise ValueError(f"Month value {month!r} is out of range 1–12.")
        return v


class ExpenseDate(BaseModel):
    """An ISO 8601 calendar date string (YYYY-MM-DD)."""
    value: str

    @field_validator("value")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            _date.fromisoformat(v)
        except ValueError:
            raise ValueError(
                f"Invalid date {v!r}. Expected ISO 8601 format: YYYY-MM-DD."
            )
        return v


class Amount(BaseModel):
    """A positive monetary amount with at most 2 decimal places."""
    value: float

    @field_validator("value")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Amount must be positive, got {v}.")
        # Reject more than 2 decimal places.
        # Multiply by 100 and check if it's an integer.
        scaled = round(v * 100)
        if abs(scaled - v * 100) > 1e-9:
            raise ValueError(
                f"Amount {v} has more than 2 decimal places. "
                "Please provide a value like 10.50, not 10.505."
            )
        return v
