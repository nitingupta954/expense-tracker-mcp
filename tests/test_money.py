"""
tests/test_money.py — Unit tests for lib/money.py helpers.

Focus on rounding edge cases where raw float math fails.
"""

import pytest

from expense_tracker_mcp_server.lib.money import format_money, from_cents, to_cents


class TestToCents:
    def test_basic(self):
        assert to_cents(1.00) == 100

    def test_half_rupee(self):
        assert to_cents(0.50) == 50

    def test_rounding_half_up_edge_case(self):
        # 19.995 should round UP to 2000 cents, not down to 1999
        assert to_cents(19.995) == 2000

    def test_rounding_zero_point_zero_zero_five(self):
        # 0.005 should round UP to 1 cent, not down to 0
        assert to_cents(0.005) == 1

    def test_large_amount(self):
        assert to_cents(1234.50) == 123450

    def test_zero_decimal(self):
        assert to_cents(100.0) == 10000

    def test_floating_representation(self):
        # 0.1 + 0.2 = 0.30000000000000004 in raw float — must handle correctly
        assert to_cents(0.10) == 10
        assert to_cents(0.20) == 20


class TestFromCents:
    def test_basic(self):
        assert from_cents(100) == 1.0

    def test_fractional(self):
        assert from_cents(1) == 0.01

    def test_round_trip(self):
        for amount in [10.5, 0.99, 1234.56, 0.01]:
            assert from_cents(to_cents(amount)) == pytest.approx(amount, abs=0.01)


class TestFormatMoney:
    def test_inr_symbol(self):
        result = format_money(123450, "INR")
        assert result == "₹1,234.50"

    def test_usd_symbol(self):
        result = format_money(99, "USD")
        assert result == "$0.99"

    def test_zero(self):
        result = format_money(0, "INR")
        assert result == "₹0.00"

    def test_unknown_currency_fallback(self):
        result = format_money(500, "XYZ")
        assert "5.00" in result
        assert "XYZ" in result
