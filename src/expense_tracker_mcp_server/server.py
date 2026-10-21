"""
Expense Tracker MCP Server

Creates the FastMCP server instance and wires up all tools and resources.
Database migration runs during server lifespan startup (async-safe).
"""

import logging
import sys
import hashlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier, AccessToken

# ── Logging: stderr only (stdout is reserved for MCP stdio protocol frames) ──
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Async lifespan: run migration on startup ─────────────────────────────────
@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncGenerator[None, None]:
    """Run DB migration before the server accepts requests, then yield."""
    from expense_tracker_mcp_server.db.migrate import run_migration
    try:
        await run_migration()
        logger.info("Database migration completed successfully.")
    except Exception as exc:
        logger.critical("Database migration failed — aborting: %s", exc)
        raise SystemExit(1) from exc
    yield  # server is live here


# ── Authentication ─────────────────────────────────────────────────────────────
class DBTokenVerifier(TokenVerifier):
    """Verifies bearer tokens against the users table."""
    async def verify_token(self, token: str) -> AccessToken | None:
        from expense_tracker_mcp_server.db.connection import db_connection
        from expense_tracker_mcp_server.db.repository import get_user_by_token_hash
        
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            async with db_connection() as conn:
                user = await get_user_by_token_hash(conn, token_hash)
                if user:
                    return AccessToken(
                        token=token,
                        client_id=str(user["id"]),
                        subject=user["email"],
                        scopes=[],
                    )
        except Exception as exc:
            logger.error("Token verification failed: %s", exc)
        return None


# ── Create the FastMCP server instance ──────────────────────────────────────
import os
import secrets
from fastmcp.server.auth.oauth_proxy import OAuthProxy

from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from expense_tracker_mcp_server.db.connection import db_connection
from datetime import datetime, timezone

class DatabaseGoogleTokenVerifier(GoogleTokenVerifier):
    async def verify_token(self, token: str):
        access_token = await super().verify_token(token)
        if not access_token:
            logger.warning("Google base verify_token returned None")
            return None
            
        logger.info(f"Google claims received: {access_token.claims}")

        email = access_token.claims.get("email")
        if not email:
            logger.warning(f"No 'email' key in claims. Available keys: {list(access_token.claims.keys())}")
            return None
            
        try:
            async with db_connection() as conn:
                user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
                if user:
                    access_token.client_id = str(user["id"])
                else:
                    now = datetime.now(timezone.utc).isoformat()
                    token_hash = secrets.token_hex(32)   # real, unique per user
                    salt = secrets.token_hex(16)

                    new_id = await conn.fetchval(
                        """
                        INSERT INTO users (email, token_hash, salt, created_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (email) DO NOTHING
                        RETURNING id
                        """,
                        email, token_hash, salt, now,
                    )

                    if new_id is None:
                        # lost the race — another concurrent request created it first
                        user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
                        if user:
                            access_token.client_id = str(user["id"])
                    else:
                        access_token.client_id = str(new_id)
                        cats = ["Food", "Transport", "Utilities", "Entertainment", "Shopping"]
                        for c in cats:
                            await conn.execute(
                                "INSERT INTO categories (user_id, name, created_at) VALUES ($1, $2, $3)",
                                new_id, c, now,
                            )
            logger.info(f"Returning access token with client_id: {access_token.client_id}")
            return access_token
        except Exception as exc:
            logger.error("Token verification failed (oauth user mapping): %s", exc, exc_info=True)
            return None

oauth_kwargs = {}
if os.environ.get("OAUTH_CLIENT_ID"):
    logger.info("Initializing OAuth Proxy for MCP authentication.")
    oauth_kwargs["auth"] = OAuthProxy(
        upstream_authorization_endpoint=os.environ["OAUTH_AUTH_URL"],
        upstream_token_endpoint=os.environ["OAUTH_TOKEN_URL"],
        upstream_client_id=os.environ["OAUTH_CLIENT_ID"],
        upstream_client_secret=os.environ.get("OAUTH_CLIENT_SECRET"),
        base_url="https://expense-tracker-mcp-z53n.onrender.com",
        token_verifier=DatabaseGoogleTokenVerifier(),
        extra_authorize_params={"scope": "openid profile email"},
    )

mcp = FastMCP(
    name="Expense Tracker",
    instructions=(
        "This server lets you manage personal expenses. "
        "You can add, list, update, and delete expenses; "
        "set monthly budgets per category; and generate spending summaries and reports. "
        "All amounts are in the configured default currency (INR by default). "
        "Use list_categories first to see available categories."
    ),
    lifespan=_lifespan,
    **oauth_kwargs
)

# ── Register tools ───────────────────────────────────────────────────────────
from expense_tracker_mcp_server.tools import expenses as _expense_tools  # noqa: E402
from expense_tracker_mcp_server.tools import budgets as _budget_tools    # noqa: E402
from expense_tracker_mcp_server.tools import reports as _report_tools    # noqa: E402

mcp.tool(_expense_tools.add_expense)
mcp.tool(_expense_tools.list_expenses)
mcp.tool(_expense_tools.update_expense)
mcp.tool(_expense_tools.delete_expense)
mcp.tool(_expense_tools.list_categories)
mcp.tool(_budget_tools.set_budget)
mcp.tool(_budget_tools.get_budget_status)
mcp.tool(_report_tools.get_summary)
mcp.tool(_report_tools.export_report)

# ── Register resources ───────────────────────────────────────────────────────
from expense_tracker_mcp_server.resources import expenses as _expense_resources    # noqa: E402
from expense_tracker_mcp_server.resources import budgets as _budget_resources      # noqa: E402
from expense_tracker_mcp_server.resources import categories as _category_resources # noqa: E402

mcp.resource("expenses://month/{month}")(_expense_resources.expenses_for_month)
mcp.resource("budget://status/{month}")(_budget_resources.budget_status_for_month)
mcp.resource("categories://all")(_category_resources.all_categories)

logger.info("Expense Tracker MCP server ready — %d tools registered.", 9)
