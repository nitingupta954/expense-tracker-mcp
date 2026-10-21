"""
tools/reports.py — Async MCP tools for spending summaries and report export.

Tools:
  get_summary   — monthly summary with category breakdown and MoM comparison
  export_report — full report as markdown or CSV string
"""

import csv
import io
import os
from typing import Literal, Optional

import asyncpg
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from expense_tracker_mcp_server.db.connection import db_connection
from expense_tracker_mcp_server.db import repository as repo
from expense_tracker_mcp_server.lib.dates import (
    current_month,
    month_label,
    month_range,
    previous_month,
)
from expense_tracker_mcp_server.lib.models import Month
from expense_tracker_mcp_server.lib.money import format_money, from_cents

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


def _validate_month(month_str: str) -> str:
    try:
        Month(value=month_str)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return month_str


# ══════════════════════════════════════════════════════════════════════════════
# get_summary
# ══════════════════════════════════════════════════════════════════════════════

async def get_summary(ctx: Context, month: Optional[str] = None) -> str:
    """
    Show a monthly spending summary with category breakdown and month-over-month comparison.

    Displays:
    - Total spend for the month
    - Per-category breakdown (amount + % of total), sorted by spend descending
    - Comparison to the previous month's total (e.g. "12% higher than June 2026")

    Parameters
    ----------
    month: str | None
        Target month in 'YYYY-MM' format. Defaults to the current month.
    """
    month = _validate_month(month) if month else current_month()
    date_from, date_to = month_range(month)
    prev_month = previous_month(month)
    prev_from, prev_to = month_range(prev_month)
    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            total_cents = await repo.sum_expenses_for_period(conn, user_id, date_from, date_to)
            prev_total_cents = await repo.sum_expenses_for_period(conn, user_id, prev_from, prev_to)
            category_rows = await repo.spending_by_category(conn, user_id, date_from, date_to)
    except Exception as exc:
        raise ToolError(f"Database error while generating summary: {exc}") from exc

    label = month_label(month)
    prev_label = month_label(prev_month)

    lines = [f"📈 Spending Summary — {label}", ""]
    lines.append(f"  Total: {format_money(total_cents, _DEFAULT_CURRENCY)}")

    # Month-over-month comparison.
    if prev_total_cents == 0:
        lines.append(f"  (No data for {prev_label} to compare against.)")
    elif total_cents == 0:
        lines.append(f"  (No spending recorded for {label} yet.)")
    else:
        diff_pct = (total_cents - prev_total_cents) / prev_total_cents * 100
        direction = "higher" if diff_pct >= 0 else "lower"
        lines.append(
            f"  {abs(diff_pct):.1f}% {direction} than {prev_label} "
            f"({format_money(prev_total_cents, _DEFAULT_CURRENCY)})"
        )

    lines.append("")
    lines.append("  Category Breakdown:")
    lines.append("  " + "-" * 42)

    if not category_rows:
        lines.append("  (No expenses this month.)")
    else:
        for r in category_rows:
            pct = (r["total_cents"] / total_cents * 100) if total_cents > 0 else 0
            lines.append(
                f"  {r['category_name']:<18}  "
                f"{format_money(r['total_cents'], _DEFAULT_CURRENCY):>12}  "
                f"({pct:5.1f}%)"
            )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# export_report
# ══════════════════════════════════════════════════════════════════════════════

async def export_report(
    ctx: Context,
    month: Optional[str] = None,
    format: Literal["markdown", "csv"] = "markdown",
) -> str:
    """
    Export a full spending report for a month as a markdown or CSV string.

    The report includes: all individual expenses, per-category totals,
    and budget status (if budgets are set). The output string can be saved
    to a file by the calling client.

    Parameters
    ----------
    month: str | None
        Target month in 'YYYY-MM' format. Defaults to the current month.
    format: 'markdown' | 'csv'
        Output format. 'markdown' produces a formatted document; 'csv'
        produces a flat spreadsheet-friendly table of individual expenses.
    """
    month = _validate_month(month) if month else current_month()
    date_from, date_to = month_range(month)
    user_id = _get_user_id(ctx)

    try:
        async with db_connection() as conn:
            expenses = await repo.list_expenses_query(conn, user_id, date_from, date_to, limit=10000)
            category_rows = await repo.spending_by_category(conn, user_id, date_from, date_to)
            budgets = await repo.get_budgets_for_month(conn, user_id, month)
            total_cents = await repo.sum_expenses_for_period(conn, user_id, date_from, date_to)

            # Build budget status rows while connection is still open.
            budget_status_rows: list[dict] = []
            for b in budgets:
                cat_id = b["category_id"]
                spent = await repo.sum_expenses_for_period(conn, user_id, date_from, date_to, cat_id)
                limit_c = b["limit_cents"]
                remaining = limit_c - spent
                pct = (spent / limit_c * 100) if limit_c > 0 else 0
                budget_status_rows.append(
                    {
                        "name": b["category_name"] or "Overall",
                        "limit": limit_c,
                        "spent": spent,
                        "remaining": remaining,
                        "pct": pct,
                    }
                )
    except Exception as exc:
        raise ToolError(f"Database error while exporting report: {exc}") from exc

    label = month_label(month)

    if format == "csv":
        return _build_csv(expenses)
    else:
        return _build_markdown(label, expenses, category_rows, budget_status_rows, total_cents)


def _build_csv(expenses) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Date", "Category", "Amount", "Currency", "Description"])
    for e in expenses:
        writer.writerow([
            e["id"],
            e["expense_date"],
            e["category_name"],
            f"{from_cents(e['amount_cents']):.2f}",
            e["currency"],
            e["description"] or "",
        ])
    return buf.getvalue()


def _build_markdown(label, expenses, category_rows, budget_status_rows, total_cents) -> str:
    lines = [
        f"# Expense Report — {label}",
        "",
        f"**Total Spending:** {format_money(total_cents, _DEFAULT_CURRENCY)}",
        "",
        "## Category Breakdown",
        "",
        "| Category | Amount | % of Total |",
        "|----------|--------|------------|",
    ]
    for r in category_rows:
        pct = (r["total_cents"] / total_cents * 100) if total_cents > 0 else 0
        lines.append(
            f"| {r['category_name']} | {format_money(r['total_cents'], _DEFAULT_CURRENCY)} | {pct:.1f}% |"
        )

    if budget_status_rows:
        lines += [
            "",
            "## Budget Status",
            "",
            "| Category | Limit | Spent | Remaining | % Used |",
            "|----------|-------|-------|-----------|--------|",
        ]
        for r in budget_status_rows:
            flag = " ⚠️" if r["pct"] >= 90 else ""
            lines.append(
                f"| {r['name']} | {format_money(r['limit'], _DEFAULT_CURRENCY)} | "
                f"{format_money(r['spent'], _DEFAULT_CURRENCY)} | "
                f"{format_money(r['remaining'], _DEFAULT_CURRENCY)} | {r['pct']:.1f}%{flag} |"
            )

    lines += [
        "",
        "## All Expenses",
        "",
        "| ID | Date | Category | Amount | Description |",
        "|----|------|----------|--------|-------------|",
    ]
    for e in expenses:
        desc = e["description"] or ""
        lines.append(
            f"| {e['id']} | {e['expense_date']} | {e['category_name']} | "
            f"{format_money(e['amount_cents'], e['currency'])} | {desc} |"
        )

    if not expenses:
        lines.append("| — | — | — | — | No expenses recorded |")

    return "\n".join(lines)
