"""
resources/categories.py — Async MCP resource for browsing all categories.
"""

from fastmcp import Context
from expense_tracker_mcp_server.tools.expenses import list_categories


async def all_categories(ctx: Context) -> str:
    """
    Read-only resource returning all available expense categories.

    URI: categories://all
    """
    return await list_categories(ctx=ctx)
