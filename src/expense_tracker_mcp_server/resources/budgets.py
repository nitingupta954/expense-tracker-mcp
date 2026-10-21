"""
resources/budgets.py — Async MCP resource for browsing budget status.
"""

from fastmcp import Context
from expense_tracker_mcp_server.tools.budgets import get_budget_status


async def budget_status_for_month(month: str, ctx: Context) -> str:
    """
    Read-only resource returning budget status for the given month.

    URI: budget://status/{month}
    Example: budget://status/2026-07
    """
    return await get_budget_status(ctx=ctx, month=month)
