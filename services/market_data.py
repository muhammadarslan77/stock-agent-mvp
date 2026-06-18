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


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner="Fetching live quotes…")
def get_quotes_bulk(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Batched quotes for the Market Explorer.

    One yf.download call → {ticker: {price, prev_close, change, change_pct, volume}}.
    Tickers that fail to resolve are silently skipped.
    """
    if not tickers:
        return {}
    try:
        data = yf.download(
            list(tickers),
            period="2d",
            progress=False,
            auto_adjust=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        return {}
    if data is None or data.empty:
        return {}

    out: dict[str, dict] = {}
    # yfinance returns a flat DataFrame for one ticker and a MultiIndex for many.
    if len(tickers) == 1:
        ticker = tickers[0]
        quote = _extract_quote(data)
        if quote:
            out[ticker] = quote
        return out

    for ticker in tickers:
        try:
            sub = data[ticker]
        except KeyError:
            continue
        quote = _extract_quote(sub)
        if quote:
            out[ticker] = quote
    return out


def _extract_quote(df: pd.DataFrame) -> Optional[dict]:
    """Pull the latest two closes + latest volume from a per-ticker frame."""
    if df is None or df.empty or "Close" not in df:
        return None
    closes = df["Close"].dropna()
    if len(closes) < 2:
        # Fall back to single-day quote (change unknown).
        if len(closes) == 1:
            price = float(closes.iloc[-1])
            volume = float(df["Volume"].dropna().iloc[-1]) if "Volume" in df and not df["Volume"].dropna().empty else 0.0
            return {
                "price": price,
                "prev_close": price,
                "change": 0.0,
                "change_pct": 0.0,
                "volume": volume,
            }
        return None
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    volume = float(df["Volume"].dropna().iloc[-1]) if "Volume" in df and not df["Volume"].dropna().empty else 0.0
    return {
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "volume": volume,
    }


@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_ticker_info(ticker: str) -> dict:
    """Return the yfinance .info dict for a ticker, or {} on failure.

    Used by the Market Explorer detail panel for market cap and 52-week range.
    """
    try:
        info = yf.Ticker(ticker.upper().strip()).info
        return info or {}
    except Exception:
        return {}


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
