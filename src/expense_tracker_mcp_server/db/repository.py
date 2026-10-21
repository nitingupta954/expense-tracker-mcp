"""
db/repository.py — All async SQL queries for the expense tracker.

Tools are thin (validate → call repo → format). The repo holds all SQL logic.
Every function accepts an explicit asyncpg.Connection so callers control
connection lifecycle and tests can inject pooled connections easily.
"""

from typing import Any

import asyncpg

from expense_tracker_mcp_server.lib.dates import now_iso


# ══════════════════════════════════════════════════════════════════════════════
# Categories
# ══════════════════════════════════════════════════════════════════════════════

async def get_all_categories(conn: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    """Return all categories for the user, ordered by name."""
    return await conn.fetch(
        "SELECT id, name FROM categories WHERE user_id = $1 ORDER BY name",
        user_id
    )


async def get_category_by_name(
    conn: asyncpg.Connection, user_id: int, name: str
) -> asyncpg.Record | None:
    """Case-insensitive lookup of a category by name for the user."""
    return await conn.fetchrow(
        "SELECT id, name FROM categories WHERE user_id = $1 AND LOWER(name) = LOWER($2)",
        user_id, name
    )


# ══════════════════════════════════════════════════════════════════════════════
# Expenses
# ══════════════════════════════════════════════════════════════════════════════

async def insert_expense(
    conn: asyncpg.Connection,
    user_id: int,
    amount_cents: int,
    currency: str,
    category_id: int,
    description: str | None,
    expense_date: str,
) -> int:
    """Insert a new expense row for the user and return its id."""
    now = now_iso()
    expense_id = await conn.fetchval(
        """
        INSERT INTO expenses
            (user_id, amount_cents, currency, category_id, description, expense_date, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        user_id, amount_cents, currency, category_id, description, expense_date, now, now
    )
    return expense_id


async def get_expense_by_id(
    conn: asyncpg.Connection, user_id: int, expense_id: int
) -> asyncpg.Record | None:
    """Fetch a single expense with its category name for the user."""
    return await conn.fetchrow(
        """
        SELECT e.id, e.amount_cents, e.currency, e.description,
               e.expense_date, e.created_at, e.updated_at,
               c.name AS category_name
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE e.id = $1 AND e.user_id = $2
        """,
        expense_id, user_id
    )


async def list_expenses_query(
    conn: asyncpg.Connection,
    user_id: int,
    date_from: str,
    date_to: str,
    category_id: int | None = None,
    limit: int = 20,
) -> list[asyncpg.Record]:
    """List expenses within a date range for the user, optionally filtered by category."""
    if category_id is not None:
        return await conn.fetch(
            """
            SELECT e.id, e.amount_cents, e.currency, e.description,
                   e.expense_date, c.name AS category_name
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            WHERE e.user_id = $1
              AND e.expense_date BETWEEN $2 AND $3
              AND e.category_id = $4
            ORDER BY e.expense_date DESC, e.id DESC
            LIMIT $5
            """,
            user_id, date_from, date_to, category_id, limit
        )
    else:
        return await conn.fetch(
            """
            SELECT e.id, e.amount_cents, e.currency, e.description,
                   e.expense_date, c.name AS category_name
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            WHERE e.user_id = $1
              AND e.expense_date BETWEEN $2 AND $3
            ORDER BY e.expense_date DESC, e.id DESC
            LIMIT $4
            """,
            user_id, date_from, date_to, limit
        )


async def update_expense_row(
    conn: asyncpg.Connection,
    user_id: int,
    expense_id: int,
    fields: dict[str, Any],
) -> None:
    """Update arbitrary fields on an expense row. 'fields' must not be empty."""
    fields["updated_at"] = now_iso()
    
    set_clauses = []
    values = []
    
    # Start parameter numbering at 3 because $1 and $2 are expense_id and user_id
    param_idx = 3
    for k, v in fields.items():
        set_clauses.append(f"{k} = ${param_idx}")
        values.append(v)
        param_idx += 1
        
    set_clause = ", ".join(set_clauses)
    
    await conn.execute(
        f"UPDATE expenses SET {set_clause} WHERE id = $1 AND user_id = $2",
        expense_id, user_id, *values
    )


async def delete_expense_row(conn: asyncpg.Connection, user_id: int, expense_id: int) -> None:
    """Delete an expense by id for the user."""
    await conn.execute("DELETE FROM expenses WHERE id = $1 AND user_id = $2", expense_id, user_id)


async def sum_expenses_for_period(
    conn: asyncpg.Connection,
    user_id: int,
    date_from: str,
    date_to: str,
    category_id: int | None = None,
) -> int:
    """Return total amount_cents for expenses in the given date range for the user."""
    if category_id is not None:
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount_cents), 0) AS total
            FROM expenses
            WHERE user_id = $1
              AND expense_date BETWEEN $2 AND $3
              AND category_id = $4
            """,
            user_id, date_from, date_to, category_id
        )
    else:
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount_cents), 0) AS total
            FROM expenses
            WHERE user_id = $1
              AND expense_date BETWEEN $2 AND $3
            """,
            user_id, date_from, date_to
        )
    return total


async def spending_by_category(
    conn: asyncpg.Connection,
    user_id: int,
    date_from: str,
    date_to: str,
) -> list[asyncpg.Record]:
    """Return per-category spending totals for the period, descending."""
    return await conn.fetch(
        """
        SELECT c.id AS category_id, c.name AS category_name,
               COALESCE(SUM(e.amount_cents), 0) AS total_cents
        FROM categories c
        LEFT JOIN expenses e
               ON e.category_id = c.id
              AND e.user_id = c.user_id
              AND e.expense_date BETWEEN $1 AND $2
        WHERE c.user_id = $3
        GROUP BY c.id, c.name
        HAVING COALESCE(SUM(e.amount_cents), 0) > 0
        ORDER BY total_cents DESC
        """,
        date_from, date_to, user_id
    )


# ══════════════════════════════════════════════════════════════════════════════
# Budgets
# ══════════════════════════════════════════════════════════════════════════════

async def upsert_budget(
    conn: asyncpg.Connection,
    user_id: int,
    category_id: int | None,
    month: str,
    limit_cents: int,
) -> None:
    """Insert or update a budget for (user_id, category_id, month)."""
    # Postgres UNIQUE(user_id, category_id, month) handles ON CONFLICT.
    # Note: Postgres < 15 treats NULLs as distinct in UNIQUE by default.
    # We will work around this by doing a manual SELECT + UPDATE if category_id is NULL.
    if category_id is None:
        row = await conn.fetchrow(
            "SELECT id FROM budgets WHERE user_id = $1 AND category_id IS NULL AND month = $2",
            user_id, month
        )
        if row:
            await conn.execute("UPDATE budgets SET limit_cents = $1 WHERE id = $2", limit_cents, row["id"])
            return

    await conn.execute(
        """
        INSERT INTO budgets (user_id, category_id, month, limit_cents)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, category_id, month)
        DO UPDATE SET limit_cents = EXCLUDED.limit_cents
        """,
        user_id, category_id, month, limit_cents
    )


async def get_budgets_for_month(
    conn: asyncpg.Connection,
    user_id: int,
    month: str,
) -> list[asyncpg.Record]:
    """Return all budgets for the given month (overall + per-category) for the user."""
    return await conn.fetch(
        """
        SELECT b.id, b.category_id, b.month, b.limit_cents,
               c.name AS category_name
        FROM budgets b
        LEFT JOIN categories c ON c.id = b.category_id
        WHERE b.user_id = $1 AND b.month = $2
        ORDER BY b.category_id IS NULL DESC, c.name
        """,
        user_id, month
    )


# ══════════════════════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════════════════════

async def get_user_by_token_hash(conn: asyncpg.Connection, token_hash: str) -> asyncpg.Record | None:
    """
    Fetch user row by the hashed bearer token.
    Returns None if token doesn't match any user.
    """
    return await conn.fetchrow("SELECT id, email, created_at FROM users WHERE token_hash = $1", token_hash)
