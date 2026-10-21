"""
tests/test_expenses.py — Async integration tests for expense CRUD tools.
"""

from contextlib import asynccontextmanager

import pytest
from expense_tracker_mcp_server.db.migrate import run_migration


# ── add_expense ───────────────────────────────────────────────────────────────

class TestAddExpense:
    @pytest.mark.asyncio
    async def test_happy_path(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        result = await add_expense(amount=450.0, category="Food", date="2026-07-01", ctx=dummy_ctx)
        assert "₹450.00" in result
        assert "Food" in result
        assert "2026-07-01" in result

    @pytest.mark.asyncio
    async def test_defaults_to_today(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        result = await add_expense(amount=100.0, category="Transport", ctx=dummy_ctx)
        assert "₹100.00" in result

    @pytest.mark.asyncio
    async def test_invalid_category_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.expenses import add_expense
        with pytest.raises(ToolError, match="not found"):
            await add_expense(amount=100.0, category="Unicorn Category", ctx=dummy_ctx)

    @pytest.mark.asyncio
    async def test_invalid_amount_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.expenses import add_expense
        with pytest.raises(ToolError):
            await add_expense(amount=-50.0, category="Food", ctx=dummy_ctx)

    @pytest.mark.asyncio
    async def test_with_description(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense
        result = await add_expense(amount=200.0, category="Food", description="Lunch", ctx=dummy_ctx)
        assert "Lunch" in result


# ── list_expenses ─────────────────────────────────────────────────────────────

class TestListExpenses:
    @pytest.mark.asyncio
    async def test_no_expenses_returns_friendly_message(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import list_expenses
        result = await list_expenses(month="2020-01", ctx=dummy_ctx)
        assert "No expenses found" in result

    @pytest.mark.asyncio
    async def test_lists_added_expense(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense, list_expenses
        await add_expense(amount=500.0, category="Rent", date="2026-07-01", ctx=dummy_ctx)
        result = await list_expenses(month="2026-07", ctx=dummy_ctx)
        assert "Rent" in result
        assert "₹500.00" in result

    @pytest.mark.asyncio
    async def test_category_filter(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense, list_expenses
        await add_expense(amount=100.0, category="Food", date="2026-07-01", ctx=dummy_ctx)
        await add_expense(amount=200.0, category="Transport", date="2026-07-01", ctx=dummy_ctx)
        result = await list_expenses(month="2026-07", category="Food", ctx=dummy_ctx)
        assert "Food" in result
        assert "Transport" not in result

    @pytest.mark.asyncio
    async def test_limit_is_clamped(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import list_expenses
        result = await list_expenses(month="2026-07", limit=9999, ctx=dummy_ctx)
        assert "No expenses" in result or "Expenses" in result


# ── update_expense ────────────────────────────────────────────────────────────

class TestUpdateExpense:
    @pytest.mark.asyncio
    async def test_happy_path(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense, update_expense
        await add_expense(amount=100.0, category="Food", date="2026-07-01", ctx=dummy_ctx)
        result = await update_expense(id=1, amount=200.0, ctx=dummy_ctx)
        assert "₹200.00" in result

    @pytest.mark.asyncio
    async def test_no_fields_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.expenses import update_expense
        with pytest.raises(ToolError, match="No fields"):
            await update_expense(id=1, ctx=dummy_ctx)

    @pytest.mark.asyncio
    async def test_nonexistent_id_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.expenses import update_expense
        with pytest.raises(ToolError, match="No expense found with id 9999"):
            await update_expense(id=9999, amount=50.0, ctx=dummy_ctx)


# ── delete_expense ────────────────────────────────────────────────────────────

class TestDeleteExpense:
    @pytest.mark.asyncio
    async def test_happy_path(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import add_expense, delete_expense
        await add_expense(amount=300.0, category="Health", date="2026-07-05", ctx=dummy_ctx)
        result = await delete_expense(id=1, ctx=dummy_ctx)
        assert "Deleted" in result
        assert "300" in result

    @pytest.mark.asyncio
    async def test_nonexistent_id_raises_tool_error(self, mem_conn, dummy_ctx):
        from fastmcp.exceptions import ToolError
        from expense_tracker_mcp_server.tools.expenses import delete_expense
        with pytest.raises(ToolError, match="No expense found with id 42"):
            await delete_expense(id=42, ctx=dummy_ctx)


# ── list_categories ───────────────────────────────────────────────────────────

class TestListCategories:
    @pytest.mark.asyncio
    async def test_returns_default_categories(self, mem_conn, dummy_ctx):
        from expense_tracker_mcp_server.tools.expenses import list_categories
        result = await list_categories(ctx=dummy_ctx)
        assert "Food" in result
        assert "Transport" in result
        assert "Health" in result
