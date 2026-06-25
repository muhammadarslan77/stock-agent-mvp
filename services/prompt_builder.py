"""Assemble the JSON context + messages we send to the LLM.

This module is deliberately pure data assembly with no network I/O of its
own (yfinance calls are made via `services/market_data` which is cached).
Keeping prompt construction separate from the Groq call makes both
sides easier to reason about and lets us inspect the payload before it
ships.
"""
from __future__ import annotations

import pandas as pd

from config import BASE_DIR
from services.market_data import get_history, get_quotes_bulk
from services.portfolio import get_portfolio_value
from services.profile import get_profile
from services.recommendations import recent_with_outcomes


COMPANIES_CSV = BASE_DIR / "data" / "companies.csv"

WATCHLIST_SIZE = 30          # tickers we expose to the AI beyond current holdings
PAST_REC_LIMIT = 10          # how many prior recs (with outcomes) to include
HISTORY_PERIOD = "1mo"       # short window for the 30d change indicator


SYSTEM_PROMPT = (
    "You are a cautious portfolio advisor for a beginner investor using a "
    "virtual trading account. Your job is to suggest BUY, SELL, or HOLD "
    "actions based on the user's profile, current holdings, available cash, "
    "market indicators, and how your prior recommendations played out.\n\n"
    "Rules:\n"
    "1. Respect the user's risk tolerance. Low = conservative, high = "
    "growth-oriented. Never push a high-risk pick on a low-tolerance user.\n"
    "2. Prefer HOLD over speculative BUY/SELL when the market signal is "
    "unclear. It is better to do nothing than to churn the portfolio.\n"
    "3. Do not recommend a BUY the user cannot afford with the cash on hand.\n"
    "4. Do not recommend a SELL of a ticker the user does not own.\n"
    "5. Learn from past recommendations included below — if a prior call "
    "went badly, reflect that in your confidence.\n\n"
    "Respond ONLY with a JSON object matching exactly this schema:\n"
    "{{\n"
    '  "recommendations": [\n'
    "    {{\n"
    '      "ticker": "<symbol, uppercase>",\n'
    '      "action": "BUY" | "SELL" | "HOLD",\n'
    '      "confidence": <integer 1-5>,\n'
    '      "reasoning": "<one short paragraph, plain language>",\n'
    '      "risk_note": "<one sentence on what could go wrong>"\n'
    "    }}\n"
    "  ]\n"
    "}}\n"
    "Return at most {max_suggestions} items. Do not include any text outside "
    "the JSON object."
)


def build_user_context(max_suggestions: int = 3) -> dict:
    """Assemble the dict we'll JSON-encode into the user message.

    Always callable: missing profile or empty holdings produce a valid
    (but sparse) payload — the AI is told it's a fresh account.
    """
    profile = get_profile() or {}
    pv = get_portfolio_value()

    holdings_payload = [
        {
            "ticker": p["ticker"],
            "quantity": p["quantity"],
            "avg_buy_price": round(p["avg_buy_price"], 2),
            "current_price": round(p["current_price"], 2),
            "market_value": round(p["market_value"], 2),
            "pnl_pct": round(p["pnl_pct"], 2),
        }
        for p in pv["positions"]
    ]

    held_tickers = {p["ticker"] for p in pv["positions"]}
    watchlist_tickers = _pick_watchlist(held_tickers, WATCHLIST_SIZE)
    market_indicators = _build_market_indicators(
        list(held_tickers) + watchlist_tickers
    )

    return {
        "max_suggestions": int(max_suggestions),
        "profile": {
            "goal": profile.get("goal"),
            "target_amount": profile.get("target_amount"),
            "target_date": profile.get("target_date"),
            "risk_tolerance": profile.get("risk_tolerance"),
        },
        "portfolio": {
            "cash_available": round(pv["cash"], 2),
            "holdings_value": round(pv["holdings_value"], 2),
            "total_value": round(pv["total_value"], 2),
            "overall_pnl_pct": round(pv["pnl_pct"], 2),
            "holdings": holdings_payload,
        },
        "market_indicators": market_indicators,
        "past_recommendations": recent_with_outcomes(PAST_REC_LIMIT),
    }


def build_messages(context: dict, max_suggestions: int = 3) -> list[dict]:
    """Groq chat messages: system rules + user JSON payload."""
    system = SYSTEM_PROMPT.format(max_suggestions=int(max_suggestions))
    import json
    user_msg = (
        "Here is the current state of my account. Recommend up to "
        f"{int(max_suggestions)} trades.\n\n"
        f"```json\n{json.dumps(context, indent=2, default=str)}\n```"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _pick_watchlist(exclude: set[str], size: int) -> list[str]:
    """Pick `size` tickers from companies.csv that the user doesn't already own.

    We spread the picks across distinct sectors so the AI sees diversification
    options rather than 30 tech stocks.
    """
    try:
        df = pd.read_csv(COMPANIES_CSV)
    except Exception:
        return []

    df = df[~df["ticker"].isin(exclude)]
    if df.empty:
        return []

    # Round-robin by sector for variety.
    by_sector: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        by_sector.setdefault(row["sector"], []).append(row["ticker"])

    picks: list[str] = []
    while len(picks) < size and by_sector:
        empties = []
        for sector, tickers in by_sector.items():
            if not tickers:
                empties.append(sector)
                continue
            picks.append(tickers.pop(0))
            if len(picks) >= size:
                break
        for s in empties:
            by_sector.pop(s, None)
    return picks


def _build_market_indicators(tickers: list[str]) -> list[dict]:
    """Compact per-ticker market snapshot for the prompt."""
    if not tickers:
        return []
    quotes = get_quotes_bulk(tuple(tickers))
    out = []
    for t in tickers:
        q = quotes.get(t)
        if not q:
            continue
        hist = get_history(t, period=HISTORY_PERIOD)
        change_30d_pct = _change_pct_over_period(hist)
        week_low, week_high = _range_over_period(hist)
        out.append({
            "ticker": t,
            "price": round(q["price"], 2),
            "day_change_pct": round(q["change_pct"], 2),
            "month_change_pct": (
                round(change_30d_pct, 2) if change_30d_pct is not None else None
            ),
            "month_low": round(week_low, 2) if week_low is not None else None,
            "month_high": round(week_high, 2) if week_high is not None else None,
        })
    return out


def _change_pct_over_period(hist: pd.DataFrame):
    if hist is None or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None
    return (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100


def _range_over_period(hist: pd.DataFrame):
    if hist is None or hist.empty or "Close" not in hist:
        return None, None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None, None
    return float(closes.min()), float(closes.max())
