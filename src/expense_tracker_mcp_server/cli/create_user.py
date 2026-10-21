import argparse
import asyncio
import hashlib
import secrets
import sys
from datetime import datetime, timezone

import asyncpg

from expense_tracker_mcp_server.db.connection import get_db_url
from expense_tracker_mcp_server.db.migrate import run_migration

DEFAULT_CATEGORIES = [
    "Food",
    "Transport",
    "Rent",
    "Entertainment",
    "Utilities",
    "Health",
    "Shopping",
    "Other",
]

async def create_user_async(email: str, display_name: str | None = None) -> None:
    """Create a new user, seed their default categories, and print their token."""
    # Ensure DB is migrated first
    await run_migration()
    
    db_url = get_db_url()
    conn = await asyncpg.connect(db_url)
    try:
        # Check if email exists
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if existing:
            print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
            sys.exit(1)
                
        # Generate token
        token = secrets.token_urlsafe(32)
        salt = secrets.token_urlsafe(16)
        token_hash = hashlib.sha256((token + salt).encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        
        # Insert user
        user_id = await conn.fetchval(
            "INSERT INTO users (email, token_hash, salt, display_name, created_at) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            email, token_hash, salt, display_name, now
        )
            
        # Seed default categories
        await conn.executemany(
            "INSERT INTO categories (user_id, name, created_at) VALUES ($1, $2, $3)",
            [(user_id, cat, now) for cat in DEFAULT_CATEGORIES]
        )
        
        print("User created successfully!")
        print(f"Email: {email}")
        print(f"User ID: {user_id}")
        if display_name:
            print(f"Display Name: {display_name}")
        print("\n" + "=" * 40)
        print("BEARER TOKEN:")
        print(token)
        print("=" * 40 + "\n")
        print("SAVE THIS TOKEN NOW. It cannot be retrieved later.")
    finally:
        await conn.close()

def main():
    parser = argparse.ArgumentParser(description="Create a new user for the Expense Tracker MCP server.")
    parser.add_argument("email", help="The email address for the new user.")
    parser.add_argument("--name", dest="display_name", help="Optional display name for the user.")
    
    args = parser.parse_args()
    
    asyncio.run(create_user_async(args.email, args.display_name))

if __name__ == "__main__":
    main()
