"""Portfolio management.

Holdings and cash are *derived* from the `transactions` table — there is
no separate holdings table to keep in sync. Single source of truth.
"""
from datetime import datetime
from typing import Optional

from database.connection import get_connection
from services.market_data import get_price
from services.profile import get_profile


class PortfolioError(Exception):
    """Raised when a portfolio operation cannot be completed."""


def get_cash_balance() -> float:
    """starting_cash − money spent on buys + money received from sells."""
    profile = get_profile()
    if not profile:
        return 0.0
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN action='BUY'  THEN total ELSE 0 END), 0) AS spent,
                COALESCE(SUM(CASE WHEN action='SELL' THEN total ELSE 0 END), 0) AS earned
            FROM transactions
            """
        ).fetchone()
        return float(profile["starting_cash"]) - row["spent"] + row["earned"]
    finally:
        conn.close()


def get_holdings() -> list[dict]:
    """Aggregate net positions per ticker.

    Returns: [{ticker, quantity, avg_buy_price, cost_basis}]
    Tickers with zero net quantity (fully sold) are excluded.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                ticker,
                SUM(CASE WHEN action='BUY' THEN quantity ELSE -quantity END) AS quantity,
                SUM(CASE WHEN action='BUY' THEN total    ELSE 0          END) AS buy_total,
                SUM(CASE WHEN action='BUY' THEN quantity ELSE 0          END) AS buy_qty
            FROM transactions
            GROUP BY ticker
            HAVING quantity > 0
            """
        ).fetchall()
        holdings = []
        for r in rows:
            avg = (r["buy_total"] / r["buy_qty"]) if r["buy_qty"] else 0.0
            qty = int(r["quantity"])
            holdings.append({
                "ticker": r["ticker"],
                "quantity": qty,
                "avg_buy_price": float(avg),
                "cost_basis": float(avg * qty),
            })
        return holdings
    finally:
        conn.close()


def get_holding_quantity(ticker: str) -> int:
    """Net shares held for a single ticker (0 if none)."""
    ticker = ticker.upper().strip()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN action='BUY' THEN quantity ELSE -quantity END), 0) AS qty
            FROM transactions
            WHERE ticker = ?
            """,
            (ticker,),
        ).fetchone()
        return int(row["qty"])
    finally:
        conn.close()


def get_portfolio_value() -> dict:
    """Snapshot of current portfolio state.

    Returns keys: cash, holdings_value, total_value, starting_cash,
    pnl, pnl_pct, positions (list with current_price, market_value, pnl, pnl_pct).
    """
    cash = get_cash_balance()
    holdings = get_holdings()
    positions = []
    holdings_value = 0.0
    for h in holdings:
        # Fall back to avg buy price if yfinance fails — avoids fake portfolio crashes.
        price = get_price(h["ticker"])
        if price is None:
            price = h["avg_buy_price"]
        market_value = price * h["quantity"]
        pnl = market_value - h["cost_basis"]
        pnl_pct = (pnl / h["cost_basis"] * 100) if h["cost_basis"] else 0.0
        positions.append({
            **h,
            "current_price": price,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
        holdings_value += market_value

    total_value = cash + holdings_value
    profile = get_profile()
    starting = float(profile["starting_cash"]) if profile else 0.0
    overall_pnl = total_value - starting
    overall_pnl_pct = (overall_pnl / starting * 100) if starting else 0.0

    return {
        "cash": cash,
        "holdings_value": holdings_value,
        "total_value": total_value,
        "starting_cash": starting,
        "pnl": overall_pnl,
        "pnl_pct": overall_pnl_pct,
        "positions": positions,
    }


def buy(ticker: str, quantity: int,
        linked_recommendation_id: Optional[int] = None) -> dict:
    """Execute a buy at the current market price.

    Raises PortfolioError on bad ticker, bad quantity, or insufficient cash.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise PortfolioError("Ticker is required.")
    if quantity <= 0:
        raise PortfolioError("Quantity must be positive.")

    price = get_price(ticker)
    if price is None:
        raise PortfolioError(f"Could not fetch price for '{ticker}'.")

    total = price * quantity
    cash = get_cash_balance()
    if total > cash:
        raise PortfolioError(
            f"Insufficient cash: need ${total:,.2f}, have ${cash:,.2f}."
        )
    _record_transaction(ticker, "BUY", quantity, price, total, linked_recommendation_id)
    record_snapshot()
    return {"ticker": ticker, "quantity": quantity, "price": price, "total": total}


def sell(ticker: str, quantity: int,
         linked_recommendation_id: Optional[int] = None) -> dict:
    """Execute a sell at the current market price.

    Raises PortfolioError on bad ticker, bad quantity, or insufficient shares.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise PortfolioError("Ticker is required.")
    if quantity <= 0:
        raise PortfolioError("Quantity must be positive.")

    held = get_holding_quantity(ticker)
    if quantity > held:
        raise PortfolioError(f"Cannot sell {quantity} shares; you hold {held}.")

    price = get_price(ticker)
    if price is None:
        raise PortfolioError(f"Could not fetch price for '{ticker}'.")

    total = price * quantity
    _record_transaction(ticker, "SELL", quantity, price, total, linked_recommendation_id)
    record_snapshot()
    return {"ticker": ticker, "quantity": quantity, "price": price, "total": total}


def get_transactions(limit: int = 100) -> list[dict]:
    """Return the most recent transactions, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def record_snapshot() -> None:
    """Take a snapshot of current portfolio state for the growth chart."""
    pv = get_portfolio_value()
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (timestamp, cash, holdings_value, total_value)
            VALUES (?, ?, ?, ?)
            """,
            (now, pv["cash"], pv["holdings_value"], pv["total_value"]),
        )
        conn.commit()
    finally:
        conn.close()


def get_snapshots(limit: int = 365) -> list[dict]:
    """Return portfolio snapshots in chronological order (oldest first)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _record_transaction(ticker: str, action: str, qty: int, price: float,
                        total: float, linked_id: Optional[int]) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO transactions
            (ticker, action, quantity, price, total, timestamp, linked_recommendation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ticker, action, qty, price, total, now, linked_id),
        )
        conn.commit()
    finally:
        conn.close()
