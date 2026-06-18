"""Stock Analysis page — basic price view today, AI recommendations in Phase 5.

Reads `prefill_analyze_ticker` from session state so the Market Explorer's
Analyze button can hand off the selected ticker.
"""
import streamlit as st

from services.market_data import get_history, get_price, get_ticker_info
from utils.charts import price_history_line
from utils.formatters import money, percent, signed_money


def render() -> None:
    st.title("🔬 Stock Analysis")
    st.caption("Quick technical snapshot. Full AI-powered recommendations land in Phase 5.")

    prefill = st.session_state.pop("prefill_analyze_ticker", "")
    ticker = st.text_input(
        "Ticker",
        value=prefill,
        placeholder="e.g. AAPL",
        key="analysis_ticker",
    ).upper().strip()

    if not ticker:
        st.info("Enter a ticker — or open the **Market Explorer** and click **Analyze** on any stock.")
        return

    price = get_price(ticker)
    if price is None:
        st.error(f"Could not fetch data for '{ticker}'.")
        return

    info = get_ticker_info(ticker)
    company = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or "—"

    st.subheader(f"{company} ({ticker})")
    st.caption(sector)

    prev_close = info.get("previousClose")
    change = (price - prev_close) if prev_close else 0.0
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", money(price), delta=percent(change_pct))
    c2.metric("Today's Change", signed_money(change))
    c3.metric(
        "52-Week Range",
        f"{money(info.get('fiftyTwoWeekLow', 0))} – {money(info.get('fiftyTwoWeekHigh', 0))}"
        if info.get("fiftyTwoWeekLow") else "—",
    )

    st.divider()

    period = st.radio(
        "Time period",
        ["1mo", "3mo", "6mo", "1y", "2y"],
        index=2,
        horizontal=True,
        key="analysis_period",
    )
    hist = get_history(ticker, period=period)
    if hist.empty:
        st.caption("No history available.")
    else:
        st.plotly_chart(price_history_line(hist), use_container_width=True)

    st.divider()
    st.info(
        "🤖 **Coming in Phase 5:** AI agent will read this chart, your portfolio, "
        "and your risk profile to recommend BUY / SELL / HOLD with reasoning."
    )
