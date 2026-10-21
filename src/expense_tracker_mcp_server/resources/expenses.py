"""
resources/expenses.py — Async MCP resource for browsing monthly expenses.
"""

from fastmcp import Context
from expense_tracker_mcp_server.tools.expenses import list_expenses


async def expenses_for_month(month: str, ctx: Context) -> str:
    """
    Read-only resource returning all expenses for the given month.

    URI: expenses://month/{month}
    Example: expenses://month/2026-07
    """
    return await list_expenses(month=month, limit=100, ctx=ctx)
