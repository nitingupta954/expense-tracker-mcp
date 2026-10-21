"""
db/migrate.py — Async schema migration using asyncpg.

Runs schema.sql to initialize or update the PostgreSQL database.
"""

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

async def run_migration(conn: asyncpg.Connection | None = None) -> None:
    """
    Apply schema.sql to the database.

    Parameters
    ----------
    conn:
        An already-open asyncpg connection.
        If None, opens a connection from the environment.
    """
    close_after = False
    if conn is None:
        from expense_tracker_mcp_server.db.connection import get_db_url
        conn = await asyncpg.connect(get_db_url())
        close_after = True

    try:
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.execute(schema_sql)
        logger.info("Schema SQL executed successfully.")
    finally:
        if close_after:
            await conn.close()
