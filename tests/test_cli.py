import asyncio
from unittest.mock import patch
import pytest

from expense_tracker_mcp_server.cli.create_user import create_user_async

@pytest.mark.asyncio
async def test_create_user(capsys):
    """Test creating a new user via CLI logic."""
    with patch("expense_tracker_mcp_server.cli.create_user.get_db_url") as mock_get_db:
        pass
