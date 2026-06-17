"""Trade page: buy / sell at live market prices, plus transaction history.

Risk checks (concentration cap, cash, share count) run inline as warnings
AND again on submit. Phase 5 will reuse the same `prefill_ticker` /
`prefill_qty` session-state hook from the AI recommendation Accept button.
"""
import streamlit as st

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

    st.metric("Available cash", money(get_cash_balance()))

    tab_buy, tab_sell, tab_hist = st.tabs(["Buy", "Sell", "Transactions"])
    with tab_buy:
        _buy_panel(prefill_ticker, prefill_qty)
    with tab_sell:
        _sell_panel()
    with tab_hist:
        _transactions_table()


def _buy_panel(prefill_ticker: str, prefill_qty: int) -> None:
    col1, col2 = st.columns([2, 1])
    with col1:
        ticker = st.text_input(
            "Ticker", value=prefill_ticker, placeholder="AAPL", key="buy_ticker"
        ).upper().strip()
    with col2:
        quantity = st.number_input(
            "Quantity", min_value=1, step=1, value=int(prefill_qty), key="buy_qty"
        )

    price = get_price(ticker) if ticker else None

    if ticker and price is None:
        st.error(f"Could not find price for '{ticker}'.")
    elif price is not None:
        st.info(
            f"Current price: **{money(price)}**  ·  "
            f"Estimated total: **{money(price * quantity)}**"
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
            result = buy(ticker, int(quantity))
            st.success(
                f"Bought {result['quantity']} × {result['ticker']} "
                f"@ {money(result['price'])} = {money(result['total'])}"
            )
            st.rerun()
        except PortfolioError as e:
            st.error(str(e))


def _sell_panel() -> None:
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
            f"Current price: **{money(price)}**  ·  "
            f"Estimated proceeds: **{money(price * quantity)}**"
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
            result = sell(ticker, int(quantity))
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
                "When": r["timestamp"].replace("T", " "),
                "Action": r["action"],
                "Ticker": r["ticker"],
                "Qty": r["quantity"],
                "Price": money(r["price"]),
                "Total": money(r["total"]),
            }
            for r in rows
        ],
        use_container_width=True,
        hide_index=True,
    )
