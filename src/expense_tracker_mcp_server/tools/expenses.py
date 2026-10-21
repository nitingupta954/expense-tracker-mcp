"""
tools/expenses.py — Async MCP tools for expense CRUD and category listing.

Each tool:
  1. Validates input (raises ToolError on bad input)
  2. Calls the async repository layer (raises ToolError on DB error)
  3. Returns a human-readable confirmation string
"""

import os
from typing import Optional

import asyncpg
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from expense_tracker_mcp_server.db.connection import db_connection
from expense_tracker_mcp_server.db import repository as repo
from expense_tracker_mcp_server.lib.dates import current_month, month_range, today_iso, month_label
from expense_tracker_mcp_server.lib.models import Amount, ExpenseDate, Month
from expense_tracker_mcp_server.lib.money import format_money, to_cents, from_cents

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


def _validate_amount(amount: float) -> int:
    """Validate and convert a float amount to cents, raising ToolError on failure."""
    try:
        Amount(value=amount)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return to_cents(amount)


def _validate_date(date_str: str) -> str:
    """Validate an ISO date string, raising ToolError on failure."""
    try:
        ExpenseDate(value=date_str)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return date_str


def _validate_month(month_str: str) -> str:
    """Validate a YYYY-MM string, raising ToolError on failure."""
    try:
        Month(value=month_str)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return month_str


async def _resolve_category(conn: asyncpg.Connection, user_id: int, category: str) -> asyncpg.Record:
    """Look up a category by name (case-insensitive). Raises ToolError if not found."""
    row = await repo.get_category_by_name(conn, user_id, category)
    if row is None:
        all_cats = await repo.get_all_categories(conn, user_id)
        valid = ", ".join(r["name"] for r in all_cats)
        raise ToolError(
            f"Category {category!r} not found. Valid categories: {valid}. "
            "Use list_categories to see the full list."
        )
    return row


# ══════════════════════════════════════════════════════════════════════════════
# add_expense
# ══════════════════════════════════════════════════════════════════════════════

async def add_expense(
    amount: float,
    category: str,
    ctx: Context,
    description: Optional[str] = None,
    date: Optional[str] = None,
) -> str:
    """
    Add a new expense entry.

    Parameters
    ----------
    amount: float
        The expense amount in the default currency (e.g. 450.00 for ₹450).
        Must be positive with at most 2 decimal places.
    category: str
        Category name (case-insensitive). Must be one of the existing categories.
        Call list_categories to see all available options.
    description: str | None
        Optional free-text note about the expense (e.g. "Dinner at Taj").
    date: str | None
        The date the expense occurred in ISO 8601 format (YYYY-MM-DD).
        Defaults to today (UTC) if not provided.
    """
    expense_date = _validate_date(date) if date else today_iso()
    amount_cents = _validate_amount(amount)

    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            cat = await _resolve_category(conn, user_id, category)
            expense_id = await repo.insert_expense(
                conn,
                user_id=user_id,
                amount_cents=amount_cents,
                currency=_DEFAULT_CURRENCY,
                category_id=cat["id"],
                description=description,
                expense_date=expense_date,
            )
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while adding expense: {exc}") from exc

    money_str = format_money(amount_cents, _DEFAULT_CURRENCY)
    desc_part = f' — "{description}"' if description else ""
    return (
        f"✅ Added expense #{expense_id}: {money_str} in {cat['name']} "
        f"on {expense_date}{desc_part}."
    )


# ══════════════════════════════════════════════════════════════════════════════
# list_expenses
# ══════════════════════════════════════════════════════════════════════════════

async def list_expenses(
    ctx: Context,
    month: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    List expenses for a given month, with an optional category filter.

    Parameters
    ----------
    month: str | None
        Calendar month in 'YYYY-MM' format. Defaults to the current month.
    category: str | None
        Filter results to a specific category (case-insensitive).
    limit: int
        Maximum number of results to return (1–100). Default 20.
    """
    month = _validate_month(month) if month else current_month()
    limit = max(1, min(limit, 100))
    date_from, date_to = month_range(month)

    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            category_id: int | None = None
            if category:
                cat = await _resolve_category(conn, user_id, category)
                category_id = cat["id"]

            rows = await repo.list_expenses_query(conn, user_id, date_from, date_to, category_id, limit)
            total_cents = await repo.sum_expenses_for_period(conn, user_id, date_from, date_to, category_id)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while listing expenses: {exc}") from exc

    label = month_label(month)
    cat_filter = f" in {category}" if category else ""

    if not rows:
        return f"No expenses found for {label}{cat_filter}."

    lines = [f"📋 Expenses for {label}{cat_filter} (showing up to {limit}):", ""]
    for r in rows:
        desc = f'  "{r["description"]}"' if r["description"] else ""
        lines.append(
            f"  #{r['id']:>4}  {r['expense_date']}  "
            f"{format_money(r['amount_cents'], r['currency']):>12}  "
            f"[{r['category_name']}]{desc}"
        )

    lines += ["", f"Total: {format_money(total_cents, _DEFAULT_CURRENCY)}"]
    if len(rows) == limit:
        lines.append(f"(Showing first {limit} results — increase limit or filter by category to see more.)")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# update_expense
# ══════════════════════════════════════════════════════════════════════════════

async def update_expense(
    id: int,
    ctx: Context,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    date: Optional[str] = None,
) -> str:
    """
    Update one or more fields on an existing expense.

    Parameters
    ----------
    id: int
        The expense ID to update (use list_expenses to find IDs).
    amount: float | None
        New amount. If omitted, keeps the existing value.
    category: str | None
        New category name. If omitted, keeps the existing value.
    description: str | None
        New description text. Pass an empty string "" to clear it.
        If omitted (None), keeps the existing description.
    date: str | None
        New expense date in YYYY-MM-DD format. If omitted, keeps existing.
    """
    if amount is None and category is None and description is None and date is None:
        raise ToolError(
            "No fields provided to update. Supply at least one of: amount, category, description, date."
        )

    user_id = _get_user_id(ctx)
    try:
        async with db_connection() as conn:
            existing = await repo.get_expense_by_id(conn, user_id, id)
            if existing is None:
                raise ToolError(f"No expense found with id {id}.")

            fields: dict = {}
            changes: list[str] = []

            if amount is not None:
                cents = _validate_amount(amount)
                old_str = format_money(existing["amount_cents"], existing["currency"])
                new_str = format_money(cents, _DEFAULT_CURRENCY)
                fields["amount_cents"] = cents
                changes.append(f"amount: {old_str} → {new_str}")

            if category is not None:
                cat = await _resolve_category(conn, user_id, category)
                fields["category_id"] = cat["id"]
                changes.append(f"category: {existing['category_name']} → {cat['name']}")

            if description is not None:
                fields["description"] = description or None
                old_desc = existing["description"] or "(none)"
                new_desc = description or "(none)"
                changes.append(f"description: {old_desc!r} → {new_desc!r}")

            if date is not None:
                validated = _validate_date(date)
                fields["expense_date"] = validated
                changes.append(f"date: {existing['expense_date']} → {validated}")

            await repo.update_expense_row(conn, user_id, id, fields)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while updating expense #{id}: {exc}") from exc

    return f"✅ Updated expense #{id}:\n" + "\n".join(f"  • {c}" for c in changes)


# ══════════════════════════════════════════════════════════════════════════════
# delete_expense
# ══════════════════════════════════════════════════════════════════════════════

async def delete_expense(id: int, ctx: Context) -> str:
    """
    Permanently delete an expense by its ID.

    Parameters
    ----------
    id: int
        The expense ID to delete (use list_expenses to find IDs).
        This action cannot be undone.
    """
    user_id = _get_user_id(ctx)
    try:
        async with db_connection() as conn:
            existing = await repo.get_expense_by_id(conn, user_id, id)
            if existing is None:
                raise ToolError(f"No expense found with id {id}.")

            snapshot = (
                f"{format_money(existing['amount_cents'], existing['currency'])} "
                f"in {existing['category_name']} on {existing['expense_date']}"
            )
            if existing["description"]:
                snapshot += f' ("{existing["description"]}")'

            await repo.delete_expense_row(conn, user_id, id)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Database error while deleting expense #{id}: {exc}") from exc

    return f"🗑️  Deleted expense #{id}: {snapshot}."


# ══════════════════════════════════════════════════════════════════════════════
# list_categories
# ══════════════════════════════════════════════════════════════════════════════

async def list_categories(ctx: Context) -> str:
    """
    List all available expense categories.

    Use the category names returned here when calling add_expense or
    set_budget to ensure correct spelling and casing.
    """
    user_id = _get_user_id(ctx)
    try:
        async with db_connection() as conn:
            rows = await repo.get_all_categories(conn, user_id)
    except Exception as exc:
        raise ToolError(f"Database error while listing categories: {exc}") from exc

    lines = ["📁 Available expense categories:", ""]
    for r in rows:
        lines.append(f"  • {r['name']}")
    return "\n".join(lines)
