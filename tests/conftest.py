import os
import pytest
from unittest.mock import MagicMock
from fastmcp import Context
from expense_tracker_mcp_server.db.migrate import run_migration
import asyncpg
from contextlib import asynccontextmanager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "postgres://postgres:postgres@localhost:5432/expense_tracker_test")

_ACTIVE_TEST_CONN = None

@pytest.fixture
async def pg_pool():
    """Create a connection pool to the test PostgreSQL database."""
    pool = await asyncpg.create_pool(_TEST_DB_URL, min_size=1, max_size=2)
    yield pool
    await pool.close()

@pytest.fixture
async def mem_conn(pg_pool):
    """
    A single connection, with wiped tables, migrated schema, and a test user.
    """
    global _ACTIVE_TEST_CONN
    async with pg_pool.acquire() as conn:
        _ACTIVE_TEST_CONN = conn
        try:
            # Wipe all tables if they exist
            await conn.execute("DROP TABLE IF EXISTS expenses, budgets, categories, users CASCADE")
            
            # Run migrations
            await run_migration(conn=conn)
            
            # Insert a dummy user and their categories for testing
            await conn.execute(
                "INSERT INTO users (id, email, token_hash, salt, display_name, created_at) "
                "VALUES (1, 'test@local', 'dummy_hash', 'salt', 'Test User', '2026-07-01T00:00:00Z')"
            )
            cats = [
                "Food", "Transport", "Rent", "Entertainment", 
                "Utilities", "Health", "Shopping", "Other"
            ]
            await conn.executemany(
                "INSERT INTO categories (user_id, name, created_at) VALUES ($1, $2, '2026-07-01T00:00:00Z')",
                [(1, name) for name in cats]
            )
            yield conn
        finally:
            _ACTIVE_TEST_CONN = None

@asynccontextmanager
async def _fake_db_connection(db_url=None):
    if _ACTIVE_TEST_CONN is None:
        raise RuntimeError("No active test connection found")
    yield _ACTIVE_TEST_CONN

@pytest.fixture(autouse=True)
def patch_db_connection(mem_conn):
    """Patch db_connection() at the root so any imports get the fake connection."""
    from unittest.mock import patch
    
    targets = [
        "expense_tracker_mcp_server.db.connection.db_connection",
        "expense_tracker_mcp_server.tools.expenses.db_connection",
        "expense_tracker_mcp_server.tools.budgets.db_connection",
        "expense_tracker_mcp_server.tools.reports.db_connection",
    ]
    
    # Only patch attributes that exist in the target modules to avoid AttributeError
    patches = []
    import importlib
    for t in targets:
        module_name, attr_name = t.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, attr_name):
                patches.append(patch(t, _fake_db_connection))
        except ImportError:
            pass
            
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()

@pytest.fixture
def dummy_ctx():
    """Provides a mocked fastmcp.Context with an authenticated client_id (user ID=1)."""
    ctx = MagicMock(spec=Context)
    ctx.client_id = "1"
    return ctx
