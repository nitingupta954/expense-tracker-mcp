"""
tests/test_dates.py — Unit tests for lib/dates.py helpers.
"""

import pytest

from expense_tracker_mcp_server.lib.dates import (
    is_valid_month,
    month_label,
    month_range,
    previous_month,
)


class TestMonthRange:
    def test_regular_month(self):
        first, last = month_range("2026-07")
        assert first == "2026-07-01"
        assert last == "2026-07-31"

    def test_february_non_leap(self):
        first, last = month_range("2026-02")
        assert first == "2026-02-01"
        assert last == "2026-02-28"

    def test_february_leap_year(self):
        first, last = month_range("2024-02")
        assert first == "2024-02-01"
        assert last == "2024-02-29"

    def test_december(self):
        first, last = month_range("2026-12")
        assert first == "2026-12-01"
        assert last == "2026-12-31"

    def test_april(self):
        _, last = month_range("2026-04")
        assert last == "2026-04-30"


class TestPreviousMonth:
    def test_mid_year(self):
        assert previous_month("2026-07") == "2026-06"

    def test_january_rolls_over(self):
        # January → December of previous year
        assert previous_month("2026-01") == "2025-12"

    def test_march(self):
        assert previous_month("2026-03") == "2026-02"


class TestIsValidMonth:
    def test_valid(self):
        assert is_valid_month("2026-07") is True

    def test_invalid_format(self):
        assert is_valid_month("2026/07") is False
        assert is_valid_month("July 2026") is False

    def test_invalid_month_value(self):
        assert is_valid_month("2026-13") is False
        assert is_valid_month("2026-00") is False


class TestMonthLabel:
    def test_july(self):
        assert month_label("2026-07") == "July 2026"

    def test_january(self):
        assert month_label("2025-01") == "January 2025"

    def test_december(self):
        assert month_label("2025-12") == "December 2025"
