"""Yahoo Finance wrapper with Streamlit-side caching.

`st.cache_data` makes repeated calls cheap and survives reruns. TTLs are
defined centrally in `config.py`.
"""
from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf

from config import PRICE_CACHE_TTL, HISTORY_CACHE_TTL


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_price(ticker: str) -> Optional[float]:
    """Return the latest closing price for `ticker`, or None on failure."""
    try:
        ticker = ticker.upper().strip()
        data = yf.Ticker(ticker).history(period="1d")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
        return None


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_prices_bulk(tickers: tuple[str, ...]) -> dict[str, float]:
    """Return {ticker: price}. Tickers that fail to resolve are skipped.

    Tuple input (not list) because Streamlit's cache key must be hashable.
    """
    out: dict[str, float] = {}
    for t in tickers:
        price = get_price(t)
        if price is not None:
            out[t] = price
    return out


@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_history(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Return historical OHLCV. Empty DataFrame on failure."""
    try:
        ticker = ticker.upper().strip()
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


def is_valid_ticker(ticker: str) -> bool:
    """Quick existence check — True if yfinance can return a price."""
    return get_price(ticker) is not None
