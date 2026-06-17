"""Risk management.

Both checks return None when the trade is allowed, or a human-readable
string explaining why it should be blocked. The UI uses the same
functions for inline previews and for submit-time enforcement.

We deliberately do NOT import this from `services/portfolio.py` —
that would create a circular import. Enforcement happens at the UI
boundary; portfolio also keeps its own cheap defensive checks (cash,
share count) so direct programmatic use can't silently bypass safety.
"""
from typing import Optional

from config import RISK_TIERS
from services.portfolio import (
    get_cash_balance,
    get_holding_quantity,
    get_portfolio_value,
)
from services.profile import get_profile


def check_buy(ticker: str, quantity: int, price: float) -> Optional[str]:
    """Return None if the buy is allowed, else a reason string."""
    profile = get_profile()
    if not profile:
        return "Set up your investor profile first."

    ticker = ticker.upper().strip()
    if not ticker:
        return "Ticker is required."
    if quantity <= 0:
        return "Quantity must be positive."
    if price <= 0:
        return "Could not determine a price for this ticker."

    cost = price * quantity
    cash = get_cash_balance()
    if cost > cash:
        return f"Insufficient cash: need ${cost:,.2f}, have ${cash:,.2f}."

    # Concentration cap from the user's risk tolerance.
    risk = profile["risk_tolerance"]
    cap_pct = RISK_TIERS.get(risk, 0.25)

    # Buying converts cash to shares — total portfolio value is unchanged.
    pv = get_portfolio_value()
    total_after = pv["total_value"]
    existing = next((p for p in pv["positions"] if p["ticker"] == ticker), None)
    new_position_value = (existing["market_value"] if existing else 0.0) + cost

    if total_after > 0 and (new_position_value / total_after) > cap_pct:
        pct = new_position_value / total_after * 100
        return (
            f"This would put {pct:.1f}% of your portfolio in {ticker}. "
            f"Your '{risk}' risk tier caps any single stock at {cap_pct*100:.0f}%."
        )
    return None


def check_sell(ticker: str, quantity: int) -> Optional[str]:
    """Return None if the sell is allowed, else a reason string."""
    profile = get_profile()
    if not profile:
        return "Set up your investor profile first."

    ticker = ticker.upper().strip()
    if not ticker:
        return "Ticker is required."
    if quantity <= 0:
        return "Quantity must be positive."

    held = get_holding_quantity(ticker)
    if quantity > held:
        return f"Cannot sell {quantity} shares; you hold {held}."
    return None
