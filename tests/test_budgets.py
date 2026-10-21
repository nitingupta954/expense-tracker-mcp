"""
tests/test_budgets.py — Async integration tests for budget and reporting tools.
"""

from contextlib import asynccontextmanager

import pytest
from expense_tracker_mcp_server.db.migrate import run_migration


# ── set_budget ────────────────────────────────────────────────────────────────

class TestSetBudget:
    @pytest.mark.asyncio
    async def test_overall_budget(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import set_budget
        result = await set_budget(limit_amount=5000.0, month="2026-07", ctx=dummy_ctx)
        assert "Overall" in result
        assert "₹5,000.00" in result

    @pytest.mark.asyncio
    async def test_category_budget(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import set_budget
        result = await set_budget(limit_amount=1000.0, category="Food", month="2026-07", ctx=dummy_ctx)
        assert "Food" in result
        assert "₹1,000.00" in result

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import set_budget
        await set_budget(limit_amount=1000.0, category="Food", month="2026-07", ctx=dummy_ctx)
        result = await set_budget(limit_amount=2000.0, category="Food", month="2026-07", ctx=dummy_ctx)
        assert "₹2,000.00" in result

    @pytest.mark.asyncio
    async def test_invalid_category_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.budgets import set_budget
        with pytest.raises(ToolError, match="not found"):
            await set_budget(limit_amount=500.0, category="FakeCategory", month="2026-07", ctx=dummy_ctx)


# ── get_budget_status ─────────────────────────────────────────────────────────

class TestGetBudgetStatus:
    @pytest.mark.asyncio
    async def test_no_budget_set(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import get_budget_status
        result = await get_budget_status(month="2020-01", ctx=dummy_ctx)
        assert "No budgets set" in result

    @pytest.mark.asyncio
    async def test_budget_with_zero_expenses(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import get_budget_status, set_budget
        await set_budget(limit_amount=1000.0, category="Food", month="2026-07", ctx=dummy_ctx)
        result = await get_budget_status(month="2026-07", ctx=dummy_ctx)
        assert "Food" in result
        assert "₹1,000.00" in result
        assert "0.0%" in result

    @pytest.mark.asyncio
    async def test_over_90_percent_shows_warning(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import get_budget_status, set_budget
        from expense_tracker_mcp_server.tools.expenses import add_expense
        await set_budget(limit_amount=100.0, category="Food", month="2026-07", ctx=dummy_ctx)
        await add_expense(amount=95.0, category="Food", date="2026-07-10", ctx=dummy_ctx)
        result = await get_budget_status(month="2026-07", ctx=dummy_ctx)
        assert "WARNING" in result or "⚠️" in result

    @pytest.mark.asyncio
    async def test_over_budget_shows_over(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.budgets import get_budget_status, set_budget
        from expense_tracker_mcp_server.tools.expenses import add_expense
        await set_budget(limit_amount=100.0, category="Food", month="2026-07", ctx=dummy_ctx)
        await add_expense(amount=150.0, category="Food", date="2026-07-10", ctx=dummy_ctx)
        result = await get_budget_status(month="2026-07", ctx=dummy_ctx)
        assert "OVER" in result or "WARNING" in result


# ── get_summary ───────────────────────────────────────────────────────────────

class TestGetSummary:
    @pytest.mark.asyncio
    async def test_no_data(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.reports import get_summary
        result = await get_summary(month="2020-01", ctx=dummy_ctx)
        assert "Total" in result

    @pytest.mark.asyncio
    async def test_with_expenses(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        from expense_tracker_mcp_server.tools.reports import get_summary
        await add_expense(amount=500.0, category="Rent", date="2026-07-01", ctx=dummy_ctx)
        await add_expense(amount=200.0, category="Food", date="2026-07-05", ctx=dummy_ctx)
        result = await get_summary(month="2026-07", ctx=dummy_ctx)
        assert "₹700.00" in result
        assert "Rent" in result
        assert "Food" in result

    @pytest.mark.asyncio
    async def test_no_previous_month_data(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        from expense_tracker_mcp_server.tools.reports import get_summary
        await add_expense(amount=100.0, category="Food", date="2026-07-01", ctx=dummy_ctx)
        result = await get_summary(month="2026-07", ctx=dummy_ctx)
        assert "No data for" in result or "June 2026" in result

    @pytest.mark.asyncio
    async def test_mom_comparison(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        from expense_tracker_mcp_server.tools.reports import get_summary
        await add_expense(amount=1000.0, category="Rent", date="2026-06-01", ctx=dummy_ctx)
        await add_expense(amount=1200.0, category="Rent", date="2026-07-01", ctx=dummy_ctx)
        result = await get_summary(month="2026-07", ctx=dummy_ctx)
        assert "%" in result


# ── export_report ─────────────────────────────────────────────────────────────

class TestExportReport:
    @pytest.mark.asyncio
    async def test_markdown_format(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        from expense_tracker_mcp_server.tools.reports import export_report
        await add_expense(amount=300.0, category="Health", date="2026-07-10", ctx=dummy_ctx)
        result = await export_report(month="2026-07", format="markdown", ctx=dummy_ctx)
        assert "# Expense Report" in result
        assert "Health" in result

    @pytest.mark.asyncio
    async def test_csv_format(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        from expense_tracker_mcp_server.tools.reports import export_report
        await add_expense(amount=300.0, category="Health", date="2026-07-10", ctx=dummy_ctx)
        result = await export_report(month="2026-07", format="csv", ctx=dummy_ctx)
        assert "ID,Date,Category" in result
        assert "Health" in result
        assert "300.00" in result
