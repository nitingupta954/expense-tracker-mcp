# Expense Tracker MCP Server

A powerful, highly detailed [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes a full-featured personal expense tracker to any MCP-compatible AI client — including Claude Desktop, Claude Code, and the MCP Inspector. 

Manage your finances through natural language directly in your AI assistant. Add, edit, delete, and query expenses; set monthly budgets; and generate comprehensive spending reports seamlessly.

---

## 🌟 Key Features

- **💸 Natural Language Expense Management**: Add, list, edit, and delete expenses effortlessly using AI prompts (e.g., *"I just spent 500 on dinner, add it to Food"*).
- **🗂️ Intelligent Categorization**: Group expenses into categories. Automatically provisions default categories (Food, Transport, Utilities, Entertainment, Shopping) on user signup.
- **💰 Proactive Budgeting**: Set per-category or overall monthly spending limits. Get overspend warnings directly in your AI chats.
- **📊 Advanced Analytics & Reporting**: View monthly summaries with month-over-month (MoM) spending comparisons and percentage changes.
- **📄 Data Export**: Generate full expense reports exported as Markdown or CSV strings right in your AI assistant's context.
- **🔗 Contextual Resources**: Expose read-only MCP resources for browsing expenses and budget statuses (e.g. `expenses://month/2026-07`).
- **☁️ Cloud-Native Storage**: Uses PostgreSQL for robust, ACID-compliant data storage. Fully prepared for SSE-based cloud deployment.
- **🔐 Secure OAuth Authentication**: Uses Google OAuth for seamless and secure user authentication. Automatically provisions isolated accounts for each user, ensuring your financial data remains private and strictly sandboxed.

---

## 🏗️ Architecture & Stack

- **Framework**: Built on [FastMCP](https://github.com/jlowin/fastmcp), a modern declarative framework for writing MCP servers in Python.
- **Database**: PostgreSQL via the `asyncpg` driver for high-performance, async database operations. Schema migrations execute automatically and idempotently on server startup.
- **Authentication Flow**: 
  1. The MCP Client initializes the connection.
  2. The server requests OAuth authentication via FastMCP's `OAuthProxy`.
  3. The user logs in via Google OAuth.
  4. The `DatabaseGoogleTokenVerifier` intercepts the Google token, extracts the email, and gracefully provisions a new user record in the PostgreSQL database if they don't exist.
  5. Subsequent tool calls securely map to that specific user's `user_id`.

### Database Schema

The PostgreSQL database enforces strong relational integrity. All financial amounts are stored safely as **integer cents** to avoid floating-point math errors.

- **`users`**: Stores OAuth-provisioned accounts with a secure `token_hash` and `salt`.
- **`categories`**: User-specific expense categories (Unique per `user_id` + `name`).
- **`expenses`**: Individual transactions linking a `user_id`, `category_id`, `amount_cents`, and `expense_date`.
- **`budgets`**: Monthly limits (overall or category-specific) tracked by `YYYY-MM`.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Extremely fast Python package installer and resolver)
- PostgreSQL database (Local, Docker, or managed cloud like [Neon](https://neon.tech) or [Supabase](https://supabase.com))
- Google Cloud Console account (for setting up OAuth Credentials)

### 1. Installation

```bash
git clone <repo-url>
cd expense-tracker-mcp-server
uv sync
```

### 2. Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Navigate to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth client ID**.
5. Choose **Web application**.
6. Set the **Authorized redirect URIs** to your deployed server URL (or `http://localhost:8000/callback` if testing locally via SSE).
7. Copy your **Client ID** and **Client Secret**.

### 3. Environment Configuration

Copy the `.env.example` file to `.env` and configure your environment:

```bash
cp .env.example .env
```

| Variable | Requirement | Default | Description |
|----------|-------------|---------|-------------|
| `DATABASE_URL` | **Required** | None | Postgres connection string (e.g. `postgresql://user:pass@localhost:5432/expenses`) |
| `OAUTH_CLIENT_ID` | **Required** | None | Your Google OAuth Client ID |
| `OAUTH_CLIENT_SECRET` | **Required** | None | Your Google OAuth Client Secret |
| `OAUTH_AUTH_URL` | Optional | `https://accounts.google.com/o/oauth2/auth` | Google Auth endpoint |
| `OAUTH_TOKEN_URL` | Optional | `https://oauth2.googleapis.com/token` | Google Token endpoint |
| `EXPENSE_DEFAULT_CURRENCY` | Optional | `INR` | Default currency formatting (e.g., USD, EUR, GBP) |

### 4. Running the Server Locally

```bash
# Run over STDIO (Standard input/output) — For direct Claude Desktop integration
uv run python -m expense_tracker_mcp_server

# Or use the installed CLI script
uv run expense-tracker-mcp

# Development mode with the web-based MCP Inspector UI
uv run fastmcp dev inspector src/expense_tracker_mcp_server/server.py
```

---

## 🤖 Claude Desktop Configuration

To use this server with Claude Desktop over STDIO, add it to your `claude_desktop_config.json` file. 
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "Expense Tracker": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/expense-tracker-mcp-server",
        "expense-tracker-mcp"
      ],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/expenses",
        "EXPENSE_DEFAULT_CURRENCY": "USD"
      }
    }
  }
}
```
*Note: OAuth is typically used for Cloud/SSE deployments. For local STDIO usage, FastMCP may skip authentication depending on the client setup.*

**Restart Claude Desktop** after saving the configuration. The expense tracker tools will appear in the tools panel (the hammer icon).

---

## 🛠️ MCP Capabilities Reference

### Available Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `add_expense` | `amount` (float), `category` (str), `description` (str, opt), `date` (str, opt) | Add a new expense (date defaults to today). |
| `list_expenses` | `month` (str, opt), `category` (str, opt), `limit` (int, opt) | List expenses for a specific month (format: `YYYY-MM`). |
| `update_expense` | `id` (int), `amount` (float, opt), `category` (str, opt), `description` (str, opt), `date` (str, opt) | Edit an existing expense record. |
| `delete_expense` | `id` (int) | Permanently delete an expense record. |
| `list_categories` | — | List all available categories. |
| `set_budget` | `limit_amount` (float), `category` (str, opt), `month` (str, opt) | Set a monthly spending limit (overall or per category). |
| `get_budget_status` | `month` (str, opt) | Show spending vs budget limits with percentage utilized. |
| `get_summary` | `month` (str, opt) | Get a monthly summary with category breakdown & MoM comparison. |
| `export_report` | `month` (str, opt), `format` (str, opt) | Export a full report as a formatted Markdown or CSV string. |

### Available Resources

| URI Template | Description |
|-------------|-------------|
| `expenses://month/{month}` | Read-only view of all expenses for a month (e.g. `expenses://month/2026-07`) |
| `budget://status/{month}` | Read-only view of budget status for a specific month |
| `categories://all` | Read-only list of all available expense categories |

---

## 💬 Example AI Prompts

Once connected to your AI assistant, try asking:
- *"List my expense categories."*
- *"I just paid my electric bill. Add an expense of $120 to Utilities."*
- *"Set an overall monthly budget of $2000 for this month."*
- *"Show me my budget status for this month. Am I close to my limit in any category?"*
- *"Give me a summary of my spending for July 2026. How does it compare to June?"*
- *"Export my expense report for this month as a CSV so I can put it in Excel."*

---

## ☁️ Cloud Deployment

This server is fully prepared for cloud deployment using Server-Sent Events (SSE) transport over HTTP.

### Docker Deployment (Render, Fly.io, Railway, etc.)
The included `Dockerfile` starts the FastMCP server over SSE transport on port `8000`. 
To deploy, link your GitHub repository to your cloud provider (like Render), and they will automatically build and run the Docker image.

**Critical Deployment Steps**: 
1. Set the `DATABASE_URL` environment variable to your production PostgreSQL connection string.
2. Set your `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` environment variables.
3. Update your Google OAuth Credentials in the Cloud Console to include your deployed URL as an **Authorized redirect URI** (e.g., `https://your-app.onrender.com/callback`).

### FastMCP Cloud
If deploying via the `fastmcp` CLI (e.g., to Prefect Horizon), the project is already configured in `fastmcp.json` to use `sse` transport on port `8000`. 

---

## 🧪 Development & Testing

We use `pytest` for unit testing. The test suite is configured to automatically provision and drop a fresh database schema for isolated testing.

Make sure you have set `TEST_DATABASE_URL` in your `.env` file before running tests.

```bash
# Run all tests with verbose output
uv run pytest tests/ -v
```

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
