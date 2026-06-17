"""SQLite connection helper."""
import sqlite3

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection. Rows behave like dicts via sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
