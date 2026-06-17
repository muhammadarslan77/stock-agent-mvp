"""Database schema bootstrap.

`init_db()` is idempotent (CREATE TABLE IF NOT EXISTS) so it is safe
to call on every Streamlit startup.
"""
from database.connection import get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_profile (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    name            TEXT    NOT NULL,
    goal            TEXT,
    target_amount   REAL,
    target_date     TEXT,
    risk_tolerance  TEXT    NOT NULL CHECK (risk_tolerance IN ('low','medium','high')),
    starting_cash   REAL    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                    TEXT    NOT NULL,
    action                    TEXT    NOT NULL CHECK (action IN ('BUY','SELL')),
    quantity                  INTEGER NOT NULL CHECK (quantity > 0),
    price                     REAL    NOT NULL CHECK (price >= 0),
    total                     REAL    NOT NULL,
    timestamp                 TEXT    NOT NULL,
    linked_recommendation_id  INTEGER,
    FOREIGN KEY (linked_recommendation_id) REFERENCES recommendations(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    context_json    TEXT,
    ticker          TEXT,
    action          TEXT    CHECK (action IN ('BUY','SELL','HOLD')),
    confidence      INTEGER CHECK (confidence BETWEEN 1 AND 5),
    reasoning       TEXT,
    risk_note       TEXT,
    user_action     TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (user_action IN ('accepted','rejected','ignored','pending')),
    outcome_note    TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    cash            REAL    NOT NULL,
    holdings_value  REAL    NOT NULL,
    total_value     REAL    NOT NULL
);
"""


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
