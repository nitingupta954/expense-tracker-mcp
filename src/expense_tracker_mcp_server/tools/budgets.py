"""
tools/budgets.py — Async MCP tools for budget management.

Tools:
  set_budget        — set or update a monthly spending limit
  get_budget_status — compare actual spending vs limits for a month
"""

import os
from typing import Optional

import asyncpg
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from expense_tracker_mcp_server.db.connection import db_connection
from expense_tracker_mcp_server.db import repository as repo
from expense_tracker_mcp_server.lib.dates import current_month, month_label, month_range
from expense_tracker_mcp_server.lib.models import Amount, Month
from expense_tracker_mcp_server.lib.money import format_money, to_cents

_DEFAULT_CURRENCY = os.environ.get("EXPENSE_DEFAULT_CURRENCY", "INR")


def _get_user_id(ctx: Context) -> int:
    """Extract and validate the authenticated user_id from the context."""
    token = get_access_token()
    if not token or not token.client_id:
        raise ToolError("Authentication required: missing client_id (user ID).")
    try:
        return int(token.client_id)
    except ValueError:
        raise ToolError(f"Invalid client_id format: {token.client_id}")


def _validate_amount_cents(amount: float) -> int:
    try:
        Amount(value=amount)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return to_cents(amount)


def _validate_month(month_str: str) -> str:
    try:
        Month(value=month_str)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return month_str


# ══════════════════════════════════════════════════════════════════════════════
# set_budget
# ══════════════════════════════════════════════════════════════════════════════

async def set_budget(
    limit_amount: float,
    ctx: Context,
    category: Optional[str] = None,
    month: Optional[str] = None,
) -> str:
    """
    Set (or update) a monthly spending budget.

    Call this with a category to set a per-category limit, or without a category
    to set an overall monthly spending cap. Setting a budget for an already-budgeted
    month and category overwrites the previous limit (it does not error).

    Parameters
    ----------
    limit_amount: float
        Maximum allowed spending in the default currency.
        Must be positive with at most 2 decimal places.
    category: str | None
        Category name to budget for. If omitted, sets an overall monthly budget
        that applies to total spending across all categories.
    month: str | None
        Target month in 'YYYY-MM' format. Defaults to the current month.
    """
    limit_cents = _validate_amount_cents(limit_amount)
    month = _validate_month(month) if month else current_month()
    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            category_id: int | None = None
            category_label = "Overall"

            if category:
                cat_row = await repo.get_category_by_name(conn, user_id, category)
                if cat_row is None:
                    all_cats = await repo.get_all_categories(conn, user_id)
                    valid = ", ".join(r["name"] for r in all_cats)
                    raise ToolError(
                        f"Category {category!r} not found. Valid categories: {valid}."
                    )
                category_id = cat_row["id"]
                category_label = cat_row["name"]

            await repo.upsert_budget(conn, user_id, category_id, month, limit_cents)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while setting budget: {exc}") from exc

    label = month_label(month)
    return (
        f"✅ Budget set: {format_money(limit_cents, _DEFAULT_CURRENCY)} "
        f"for {category_label} in {label}."
    )


# ══════════════════════════════════════════════════════════════════════════════
# get_budget_status
# ══════════════════════════════════════════════════════════════════════════════

async def get_budget_status(ctx: Context, month: Optional[str] = None) -> str:
    """
    Show how spending compares to set budgets for a given month.

    Displays each budgeted category with limit, amount spent so far,
    amount remaining, and percentage used. Categories over 90% are
    flagged with a warning. Overall budget (if set) is shown first.

    Parameters
    ----------
    month: str | None
        Target month in 'YYYY-MM' format. Defaults to the current month.
    """
    month = _validate_month(month) if month else current_month()
    date_from, date_to = month_range(month)
    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            budgets = await repo.get_budgets_for_month(conn, user_id, month)
            if not budgets:
                return (
                    f"No budgets set for {month_label(month)}. "
                    "Use set_budget to create one."
                )

            lines = [f"📊 Budget Status — {month_label(month)}", ""]

            budget_rows: list[dict] = []
            for b in budgets:
                cat_id = b["category_id"]
                spent = await repo.sum_expenses_for_period(conn, user_id, date_from, date_to, cat_id)
                limit = b["limit_cents"]
                remaining = limit - spent
                pct = (spent / limit * 100) if limit > 0 else 0.0
                budget_rows.append(
                    {
                        "name": b["category_name"] or "Overall",
                        "limit": limit,
                        "spent": spent,
                        "remaining": remaining,
                        "pct": pct,
                        "is_overall": cat_id is None,
                    }
                )

            # Sort: overall first, then by pct desc.
            budget_rows.sort(key=lambda r: (not r["is_overall"], -r["pct"]))

            for r in budget_rows:
                pct_str = f"{r['pct']:.1f}%"
                bar_filled = int(r["pct"] / 5)  # 20-char bar
                bar = "█" * min(bar_filled, 20) + "░" * (20 - min(bar_filled, 20))
                warning = "  ⚠️  [WARNING — over 90%!]" if r["pct"] >= 90 else ""
                remaining_str = (
                    format_money(r["remaining"], _DEFAULT_CURRENCY)
                    if r["remaining"] >= 0
                    else f"-{format_money(-r['remaining'], _DEFAULT_CURRENCY)} OVER"
                )
                lines += [
                    f"  {'[Overall]' if r['is_overall'] else r['name']}",
                    f"    Limit:     {format_money(r['limit'], _DEFAULT_CURRENCY)}",
                    f"    Spent:     {format_money(r['spent'], _DEFAULT_CURRENCY)} ({pct_str})",
                    f"    Remaining: {remaining_str}{warning}",
                    f"    [{bar}]",
                    "",
                ]
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while fetching budget status: {exc}") from exc

    return "\n".join(lines).rstrip()
