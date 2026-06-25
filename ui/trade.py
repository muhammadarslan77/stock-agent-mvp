"""Trade page: buy / sell at live market prices, plus transaction history.

Risk checks (concentration cap, cash, share count) run inline as warnings
AND again on submit. The AI Recommendations page hands accepted picks
off here via `prefill_ticker`, `prefill_qty`, and `pending_rec_id` —
the latter is forwarded to `portfolio.buy()` / `sell()` so the resulting
transaction is linked back to the recommendation row.
"""
import streamlit as st

from config import POPULAR_TICKERS
from services.market_data import get_price
from services.portfolio import (
    PortfolioError,
    buy,
    get_cash_balance,
    get_holding_quantity,
    get_holdings,
    get_transactions,
    sell,
)
from services.profile import profile_exists
from services.risk import check_buy as risk_check_buy
from services.risk import check_sell as risk_check_sell
from utils.formatters import money


def render() -> None:
    st.title("💱 Trade")

    if not profile_exists():
        st.warning("Please set up your **Investment Profile** before trading.")
        return

    prefill_ticker = st.session_state.pop("prefill_ticker", "")
    prefill_qty = st.session_state.pop("prefill_qty", 1)
    pending_rec_id = st.session_state.pop("pending_rec_id", None)
    pending_rec_action = st.session_state.pop("pending_rec_action", None)

    st.metric("Available cash", money(get_cash_balance()))

    if pending_rec_id and pending_rec_action in ("BUY", "SELL"):
        st.info(
            f"Linked to AI recommendation **#{pending_rec_id}** "
            f"({pending_rec_action} {prefill_ticker or '—'})."
        )

    tab_buy, tab_sell, tab_hist = st.tabs(["Buy", "Sell", "Transactions"])
    with tab_buy:
        _buy_panel(
            prefill_ticker,
            prefill_qty,
            pending_rec_id if pending_rec_action == "BUY" else None,
        )
    with tab_sell:
        _sell_panel(
            pending_rec_id if pending_rec_action == "SELL" else None,
        )
    with tab_hist:
        _transactions_table()


def _buy_panel(prefill_ticker: str, prefill_qty: int,
               linked_rec_id: int | None = None) -> None:
    OTHER = "Other…"
    options = sorted(set(POPULAR_TICKERS))
    prefill = prefill_ticker.upper().strip()
    # Preselect the prefill if it's in the shortlist; otherwise route to "Other…".
    if prefill and prefill in options:
        default_idx = options.index(prefill)
    elif prefill:
        default_idx = len(options)  # "Other…"
    else:
        default_idx = options.index("AAPL") if "AAPL" in options else 0

    col1, col2 = st.columns([2, 1])
    with col1:
        choice = st.selectbox(
            "Ticker", options + [OTHER], index=default_idx, key="buy_choice"
        )
        if choice == OTHER:
            ticker = st.text_input(
                "Enter ticker symbol",
                value=prefill if prefill not in options else "",
                placeholder="e.g. BRK-B",
                key="buy_ticker_other",
            ).upper().strip()
        else:
            ticker = choice
    with col2:
        quantity = st.number_input(
            "Quantity", min_value=1, step=1, value=int(prefill_qty), key="buy_qty"
        )

    price = get_price(ticker) if ticker else None

    if ticker and price is None:
        st.error(f"Could not find price for '{ticker}'.")
    elif price is not None:
        st.info(
            f"Current Price: :blue[**{money(price)}**]      \n"
            f"Estimated Total: :blue[**{money(price * quantity)}**]"
        )
        preview_reason = risk_check_buy(ticker, int(quantity), price)
        if preview_reason:
            st.warning(f"⚠️ {preview_reason}")

    if st.button(
        "Buy", type="primary", use_container_width=True, key="buy_btn",
        disabled=(price is None),
    ):
        reason = risk_check_buy(ticker, int(quantity), price or 0.0)
        if reason:
            st.error(reason)
            return
        try:
            result = buy(ticker, int(quantity),
                         linked_recommendation_id=linked_rec_id)
            st.success(
                f"Bought {result['quantity']} × {result['ticker']} "
                f"@ {money(result['price'])} = {money(result['total'])}"
            )
            st.rerun()
        except PortfolioError as e:
            st.error(str(e))


def _sell_panel(linked_rec_id: int | None = None) -> None:
    holdings = get_holdings()
    if not holdings:
        st.info("You don't own any stocks yet.")
        return

    options = [f"{h['ticker']} ({h['quantity']} shares)" for h in holdings]
    choice = st.selectbox("Holding", options, key="sell_choice")
    ticker = choice.split(" ")[0]
    max_qty = get_holding_quantity(ticker)
    quantity = st.number_input(
        "Quantity to sell", min_value=1, max_value=max_qty, step=1, value=1,
        key="sell_qty",
    )

    price = get_price(ticker)
    if price is None:
        st.error(f"Could not fetch price for '{ticker}'.")
    else:
        st.info(
            f"Current Price: :blue[**{money(price)}**]     \n"
            f"Estimated Proceeds: :blue[**{money(price * quantity)}**]"
        )
        preview_reason = risk_check_sell(ticker, int(quantity))
        if preview_reason:
            st.warning(f"⚠️ {preview_reason}")

    if st.button(
        "Sell", type="primary", use_container_width=True, key="sell_btn",
        disabled=(price is None),
    ):
        reason = risk_check_sell(ticker, int(quantity))
        if reason:
            st.error(reason)
            return
        try:
            result = sell(ticker, int(quantity),
                          linked_recommendation_id=linked_rec_id)
            st.success(
                f"Sold {result['quantity']} × {result['ticker']} "
                f"@ {money(result['price'])} = {money(result['total'])}"
            )
            st.rerun()
        except PortfolioError as e:
            st.error(str(e))


def _transactions_table() -> None:
    rows = get_transactions()
    if not rows:
        st.info("No transactions yet.")
        return
    st.dataframe(
        [
            {
                "Date & Time": r["timestamp"].replace("T", " "),
                "Action": r["action"],
                "Ticker": r["ticker"],
                "Quantity": r["quantity"],
                "Price": money(r["price"]),
                "Total": money(r["total"]),
            }
            for r in rows
        ],
        use_container_width=True,
        hide_index=True,
    )
