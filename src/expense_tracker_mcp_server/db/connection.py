"""
db/connection.py — Async PostgreSQL connection factory using asyncpg.

Reads DATABASE_URL from the environment.
Every connection pool is configured to work correctly with async tasks.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

logger = logging.getLogger(__name__)

_DEFAULT_DB_URL = "postgres://postgres:postgres@localhost:5432/expense_tracker"


def get_db_url() -> str:
    """Return the resolved Database URL."""
    return os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)

@asynccontextmanager
async def db_connection(
    db_url: str | None = None,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Async context manager that gets an asyncpg connection and closes it
    when done.

    Usage:
        async with db_connection() as conn:
            rows = await conn.fetch("SELECT ...")
    """
    if db_url is None:
        db_url = get_db_url()

    conn = await asyncpg.connect(db_url)
    try:
        yield conn
    finally:
        await conn.close()
