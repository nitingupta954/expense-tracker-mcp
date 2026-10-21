"""
Entrypoint: python -m expense_tracker_mcp_server

Starts the Expense Tracker MCP server over stdio transport.
All logging goes to stderr; stdout is reserved for MCP protocol frames.
"""

import logging
import sys


def main() -> None:
    """CLI entrypoint for the expense-tracker-mcp script."""
    try:
        from expense_tracker_mcp_server.server import mcp
        mcp.run()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C — not an error.
        pass
    except Exception as exc:
        logging.critical("Fatal error during server startup: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
