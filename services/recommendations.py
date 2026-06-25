"""Recommendation persistence + outcome tracking.

The `recommendations` table is the source of truth for AI suggestions.
Outcomes (did the user accept? how did the trade perform?) are NOT stored
columns — they are derived on demand by joining `transactions` and asking
yfinance for the current price. Same single-source-of-truth rule we use
for cash/holdings in `services/portfolio.py`.
"""
import json
from datetime import datetime
from typing import Optional

from database.connection import get_connection
from services.market_data import get_price


VALID_USER_ACTIONS = ("pending", "accepted", "rejected", "ignored")
VALID_AI_ACTIONS = ("BUY", "SELL", "HOLD")


def save_recommendation(
    ticker: str,
    action: str,
    confidence: int,
    reasoning: str,
    risk_note: str,
    context: dict,
) -> int:
    """Persist a fresh AI recommendation as `pending`. Returns the new row id.

    `context` is the JSON payload we sent the AI — stored verbatim for audit.
    """
    if action not in VALID_AI_ACTIONS:
        raise ValueError(f"action must be one of {VALID_AI_ACTIONS}")
    if not 1 <= confidence <= 5:
        raise ValueError("confidence must be between 1 and 5")

    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO recommendations
            (timestamp, context_json, ticker, action, confidence,
             reasoning, risk_note, user_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (now, json.dumps(context), ticker.upper().strip(), action,
             int(confidence), reasoning, risk_note),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_pending() -> list[dict]:
    """All recommendations awaiting user action, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM recommendations
            WHERE user_action = 'pending'
            ORDER BY timestamp DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_history(limit: int = 100, status_filter: Optional[str] = None) -> list[dict]:
    """Recommendations the user has already acted on, newest first.

    `status_filter` ∈ {accepted, rejected, ignored} or None for all non-pending.
    """
    conn = get_connection()
    try:
        if status_filter:
            if status_filter not in VALID_USER_ACTIONS:
                raise ValueError(f"status_filter must be one of {VALID_USER_ACTIONS}")
            rows = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE user_action = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE user_action != 'pending'
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recommendation(rec_id: int) -> Optional[dict]:
    """Single rec by id, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE id = ?", (rec_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_user_action(rec_id: int, user_action: str) -> None:
    """Mark a rec as accepted/rejected/ignored. Idempotent."""
    if user_action not in VALID_USER_ACTIONS:
        raise ValueError(f"user_action must be one of {VALID_USER_ACTIONS}")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE recommendations SET user_action = ? WHERE id = ?",
            (user_action, rec_id),
        )
        conn.commit()
    finally:
        conn.close()


def recent_with_outcomes(limit: int = 10) -> list[dict]:
    """Past recommendations with a computed `outcome_note` for the AI prompt.

    Joins each recommendation to any transaction that links back to it and
    asks yfinance for the current price so the AI can see how its prior
    advice played out. Newest first.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                r.id, r.timestamp, r.ticker, r.action, r.confidence,
                r.user_action,
                t.action   AS tx_action,
                t.quantity AS tx_qty,
                t.price    AS tx_price,
                t.timestamp AS tx_timestamp
            FROM recommendations r
            LEFT JOIN transactions t ON t.linked_recommendation_id = r.id
            ORDER BY r.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "ticker": r["ticker"],
            "action": r["action"],
            "confidence": r["confidence"],
            "user_action": r["user_action"],
            "outcome_note": _build_outcome_note(dict(r)),
        })
    return out


def _build_outcome_note(row: dict) -> str:
    """Human-readable outcome string for one past recommendation."""
    user_action = row["user_action"]
    if user_action == "pending":
        return "still pending"
    if user_action in ("rejected", "ignored"):
        return user_action

    # accepted — try to attach a P/L narrative
    ticker = row["ticker"]
    ai_action = row["action"]
    tx_action = row["tx_action"]
    tx_price = row["tx_price"]

    if ai_action == "HOLD" or tx_price is None:
        # No trade attached — either it was a HOLD or the user accepted but
        # the trade isn't recorded against this rec yet.
        return "accepted (no linked trade)"

    current = get_price(ticker)
    if current is None:
        return f"accepted ({tx_action} {row['tx_qty']} @ ${tx_price:.2f})"

    change_pct = (current - tx_price) / tx_price * 100
    direction = "+" if change_pct >= 0 else ""
    return (
        f"accepted: {tx_action} {row['tx_qty']} @ ${tx_price:.2f}; "
        f"now ${current:.2f} ({direction}{change_pct:.2f}%)"
    )
