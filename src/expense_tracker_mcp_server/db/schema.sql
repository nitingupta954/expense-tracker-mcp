-- Expense Tracker MCP Server — PostgreSQL Schema
-- All tables use CREATE TABLE IF NOT EXISTS for idempotent migration.

-- ── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           SERIAL PRIMARY KEY,
    email        TEXT    NOT NULL UNIQUE,
    token_hash   TEXT    NOT NULL,
    salt         TEXT    NOT NULL,
    display_name TEXT,
    created_at   TEXT    NOT NULL,  -- ISO 8601 UTC
    revoked_at   TEXT       -- NULL if active, ISO 8601 UTC if revoked
);

-- ── Categories ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    name       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,  -- ISO 8601 UTC
    UNIQUE(user_id, name)
);

-- ── Expenses ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expenses (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    currency     TEXT    NOT NULL DEFAULT 'INR',
    category_id  INTEGER NOT NULL REFERENCES categories(id),
    description  TEXT,
    expense_date TEXT    NOT NULL,  -- ISO 8601 date (YYYY-MM-DD)
    created_at   TEXT    NOT NULL,  -- ISO 8601 UTC datetime
    updated_at   TEXT    NOT NULL   -- ISO 8601 UTC datetime
);

CREATE INDEX IF NOT EXISTS idx_expenses_date        ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category_id ON expenses(category_id);
CREATE INDEX IF NOT EXISTS idx_expenses_user_id     ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_categories_user_id   ON categories(user_id);

-- ── Budgets ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budgets (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER REFERENCES categories(id),  -- NULL = overall monthly budget
    month       TEXT    NOT NULL,                   -- format: YYYY-MM
    limit_cents INTEGER NOT NULL CHECK(limit_cents > 0),
    UNIQUE(user_id, category_id, month)
);

CREATE INDEX IF NOT EXISTS idx_budgets_month ON budgets(month);
CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON budgets(user_id);
