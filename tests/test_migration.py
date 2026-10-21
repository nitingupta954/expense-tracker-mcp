"""
tests/test_migration.py — Async tests for DB schema migration.
"""

import pytest

from expense_tracker_mcp_server.db.migrate import run_migration


@pytest.mark.asyncio
async def test_migration_creates_tables(mem_conn):
    # mem_conn is a Postgres connection provided by conftest
    records = await mem_conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )
    tables = {row["table_name"] for row in records}
    assert "users" in tables
    assert "categories" in tables
    assert "expenses" in tables
    assert "budgets" in tables


@pytest.mark.asyncio
async def test_migration_is_idempotent(mem_conn):
    """Running migration twice should not error."""
    await run_migration(conn=mem_conn)
    # Just check that it didn't mess anything up
    val = await mem_conn.fetchval("SELECT COUNT(*) FROM users")
    assert val == 1  # 1 because of dummy user inserted in conftest
