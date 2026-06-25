"""Market Explorer — Yahoo-Finance style browsing for a curated 200-stock universe.

Flow: load CSV → fetch live quotes in one batched call → display selectable table
→ render a detail panel for the selected row with Buy / Analyze actions.
"""
import pandas as pd
import streamlit as st

from config import BASE_DIR
from services.market_data import get_history, get_quotes_bulk, get_ticker_info
from utils.charts import price_history_line
from utils.formatters import money, percent, signed_money


COMPANIES_CSV = BASE_DIR / "data" / "companies.csv"


SORT_OPTIONS = {
    "Ticker A → Z": ("ticker", True),
    "Price ↑": ("price", True),
    "Price ↓": ("price", False),
    "% Change ↑": ("change_pct", True),
    "% Change ↓": ("change_pct", False),
    "Volume ↓": ("volume", False),
}


@st.cache_data(ttl=86_400, show_spinner=False)
def _load_companies() -> pd.DataFrame:
    """Cached for a day — the seed list rarely changes."""
    return pd.read_csv(COMPANIES_CSV)


def render() -> None:
    st.title("🌐 Market Explorer")
    st.caption(
        "Browse popular US stocks and ETFs · Live Quotes · One-Click Trade. "
    )

    companies = _load_companies()

    # ---- Filter bar ---------------------------------------------------------
    f1, f2, f3, f4 = st.columns([3, 2, 2, 1])
    with f1:
        search = st.text_input(
            "🔎 **Search**",
            placeholder="Ticker or company name",
            key="market_search",
        ).lower().strip()
    with f2:
        sectors = ["All sectors"] + sorted(companies["sector"].unique().tolist())
        sector_filter = st.selectbox("**Sector**", sectors, key="market_sector")
    with f3:
        sort_choice = st.selectbox("**Sort by**", list(SORT_OPTIONS.keys()), key="market_sort")
    with f4:
        st.write("")  # spacer to align with selectbox labels
        if st.button("🔄 **Refresh**", use_container_width=True, key="market_refresh"):
            get_quotes_bulk.clear()
            st.rerun()

    # ---- Apply filters BEFORE fetching to keep the API call small ----------
    filtered = companies.copy()
    if search:
        mask = (
            filtered["ticker"].str.lower().str.contains(search, na=False)
            | filtered["company"].str.lower().str.contains(search, na=False)
            | filtered["industry"].str.lower().str.contains(search, na=False)
        )
        filtered = filtered[mask]
    if sector_filter != "All sectors":
        filtered = filtered[filtered["sector"] == sector_filter]

    if filtered.empty:
        st.info("No stocks match your filters.")
        return

    # ---- Fetch quotes (cached) ---------------------------------------------
    tickers = tuple(filtered["ticker"].tolist())
    quotes = get_quotes_bulk(tickers)

    rows = []
    for _, row in filtered.iterrows():
        q = quotes.get(row["ticker"], {})
        rows.append({
            "ticker": row["ticker"],
            "company": row["company"],
            "sector": row["sector"],
            "industry": row["industry"],
            "price": q.get("price"),
            "change": q.get("change"),
            "change_pct": q.get("change_pct"),
            "volume": q.get("volume"),
        })
    df = pd.DataFrame(rows)

    # ---- Sort ---------------------------------------------------------------
    sort_col, ascending = SORT_OPTIONS[sort_choice]
    df = df.sort_values(sort_col, ascending=ascending, na_position="last").reset_index(drop=True)

    st.caption(f"Showing **{len(df)}** stocks. Click any row to open the detail panel.")

    # ---- Selectable table ---------------------------------------------------
    selection = st.dataframe(
        df,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker", width="small"),
            "company": st.column_config.TextColumn("Company", width="medium"),
            "sector": st.column_config.TextColumn("Sector", width="small"),
            "industry": st.column_config.TextColumn("Industry", width="medium"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "change": st.column_config.NumberColumn("Today", format="%+.2f"),
            "change_pct": st.column_config.NumberColumn("%", format="%+.2f%%"),
            "volume": st.column_config.NumberColumn("Volume", format="%d"),
        },
        hide_index=True,
        use_container_width=True,
        height=520,
        on_select="rerun",
        selection_mode="single-row",
        key="market_table",
    )

    selected_rows = selection.selection.rows if hasattr(selection, "selection") else []
    if not selected_rows:
        st.info("Select a row above to view the stock detail panel.")
        return

    _render_detail_panel(df.iloc[selected_rows[0]])


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------
def _render_detail_panel(row: pd.Series) -> None:
    st.divider()

    ticker = row["ticker"]
    info = get_ticker_info(ticker)

    # ---- Header: company name + big price ----------------------------------
    head_l, head_r = st.columns([3, 2])
    with head_l:
        st.subheader(f"{row['company']} ({ticker})")
        st.caption(f"{row['sector']} · {row['industry']}")
    with head_r:
        if pd.notna(row["price"]):
            st.markdown(
                f"<div style='text-align:right;'>"
                f"<span style='font-size:2rem;font-weight:700;'>{money(row['price'])}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if pd.notna(row["change"]) and pd.notna(row["change_pct"]):
                color = "#10b981" if row["change"] >= 0 else "#ef4444"
                arrow = "▲" if row["change"] >= 0 else "▼"
                st.markdown(
                    f"<div style='text-align:right;color:{color};font-weight:600;'>"
                    f"{arrow} {signed_money(row['change'])} ({percent(row['change_pct'])})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ---- Stat cards --------------------------------------------------------
    prev_close = (
        row["price"] - row["change"]
        if pd.notna(row["price"]) and pd.notna(row["change"])
        else info.get("previousClose")
    )
    market_cap = info.get("marketCap")
    week_low = info.get("fiftyTwoWeekLow")
    week_high = info.get("fiftyTwoWeekHigh")

    s1, s2, s3, s4 = st.columns(4)
    with s1.container(border=True):
        st.metric("Previous Close", money(prev_close) if prev_close else "—")
    with s2.container(border=True):
        st.metric("Volume", _format_volume(row["volume"]))
    with s3.container(border=True):
        st.metric("Market Cap", _format_market_cap(market_cap))
    with s4.container(border=True):
        if week_low and week_high:
            st.metric("52-Week Range", f"{money(week_low)} – {money(week_high)}")
        else:
            st.metric("52-Week Range", "—")

    # ---- 30-day chart ------------------------------------------------------
    st.subheader("30-Day Price History")
    hist = get_history(ticker, period="1mo")
    if hist.empty:
        st.caption("Historical data unavailable.")
    else:
        st.plotly_chart(price_history_line(hist), use_container_width=True)

    # ---- Action buttons ----------------------------------------------------
    st.divider()
    a1, a2 = st.columns(2)
    with a1:
        if st.button(
            "🔬 Analyze",
            type="secondary",
            use_container_width=True,
            key=f"market_analyze_{ticker}",
        ):
            st.session_state["prefill_analyze_ticker"] = ticker
            from ui.pages import analysis_page  # lazy import to avoid cycle
            st.switch_page(analysis_page)
    with a2:
        if st.button(
            "🛒 Buy",
            type="primary",
            use_container_width=True,
            key=f"market_buy_{ticker}",
        ):
            st.session_state["prefill_ticker"] = ticker
            st.session_state["prefill_qty"] = 1
            from ui.pages import trade_page  # lazy import to avoid cycle
            st.switch_page(trade_page)


# ---------------------------------------------------------------------------
# Tiny formatters local to the page
# ---------------------------------------------------------------------------
def _format_market_cap(value) -> str:
    if not value or pd.isna(value):
        return "—"
    value = float(value)
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"


def _format_volume(value) -> str:
    if value is None or pd.isna(value) or value == 0:
        return "—"
    value = float(value)
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M"
    if value >= 1e3:
        return f"{value / 1e3:.1f}K"
    return f"{int(value):,}"
