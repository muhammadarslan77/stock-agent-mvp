"""User investment profile: goal, target, risk tolerance, starting cash.

The profile is a single row (id = 1) — MVP is single-user.
"""
from datetime import datetime
from typing import Optional

from database.connection import get_connection


VALID_RISK = ("low", "medium", "high")


def get_profile() -> Optional[dict]:
    """Return the profile as a dict, or None if it hasn't been set yet."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def profile_exists() -> bool:
    return get_profile() is not None


def save_profile(
    name: str,
    goal: str,
    target_amount: float,
    target_date: str,
    risk_tolerance: str,
    starting_cash: float,
) -> None:
    """Insert the profile if missing, otherwise update it.

    `starting_cash` should not change after the first save, because all cash
    math is derived from it. The UI locks the field after first save.
    """
    if risk_tolerance not in VALID_RISK:
        raise ValueError(f"risk_tolerance must be one of {VALID_RISK}")
    if starting_cash <= 0:
        raise ValueError("starting_cash must be positive")
    if not name.strip():
        raise ValueError("name is required")

    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM user_profile WHERE id = 1").fetchone()
        if existing:
            conn.execute(
                """
                UPDATE user_profile
                SET name = ?, goal = ?, target_amount = ?, target_date = ?,
                    risk_tolerance = ?
                WHERE id = 1
                """,
                (name, goal, target_amount, target_date, risk_tolerance),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_profile
                (id, name, goal, target_amount, target_date, risk_tolerance,
                 starting_cash, created_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, goal, target_amount, target_date, risk_tolerance,
                 starting_cash, now),
            )
        conn.commit()
    finally:
        conn.close()
