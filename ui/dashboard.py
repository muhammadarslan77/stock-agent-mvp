"""Dashboard page — KPIs, allocation pie, growth chart, holdings, activity."""
import streamlit as st

from services.portfolio import (
    get_portfolio_value,
    get_snapshots,
    get_transactions,
    record_snapshot,
)
from services.profile import get_profile
from utils.charts import allocation_pie, growth_line
from utils.formatters import money, percent, signed_money


def render() -> None:
    st.title("📊 Dashboard")

    profile = get_profile()
    if not profile:
        st.info("👋 Welcome! Set up your **Profile** to begin.")
        return

    pv = get_portfolio_value()

    _render_kpi_cards(pv)
    _render_goal_progress(profile, pv)

    st.divider()

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.subheader("Allocation")
        if pv["positions"]:
            st.plotly_chart(allocation_pie(pv["positions"]), use_container_width=True)
        else:
            st.caption("No holdings yet. Open **Trade** to make your first buy.")

    with col_right:
        st.subheader("Portfolio Growth")
        snapshots = get_snapshots()
        if not snapshots:
            # First load after profile creation — seed the timeline.
            record_snapshot()
            snapshots = get_snapshots()
        if len(snapshots) >= 2:
            st.plotly_chart(growth_line(snapshots), use_container_width=True)
        else:
            st.caption("Make a trade to start tracking growth over time.")

    st.divider()

    col_h, col_a = st.columns([3, 2])
    with col_h:
        st.subheader("Holdings")
        _render_holdings_table(pv["positions"])
    with col_a:
        st.subheader("Recent Activity")
        _render_recent_activity()


def _render_kpi_cards(pv: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1.container(border=True):
        st.metric("Total Value", money(pv["total_value"]), delta=percent(pv["pnl_pct"]))
    with c2.container(border=True):
        st.metric("Cash", money(pv["cash"]))
    with c3.container(border=True):
        st.metric("Holdings", money(pv["holdings_value"]))
    with c4.container(border=True):
        st.metric("Profit / Loss", signed_money(pv["pnl"]))


def _render_goal_progress(profile: dict, pv: dict) -> None:
    target = float(profile.get("target_amount") or 0)
    if target <= 0:
        return
    progress = max(min(pv["total_value"] / target, 1.0), 0.0)
    goal_text = profile.get("goal") or "Goal"
    date_text = profile.get("target_date") or "—"
    st.caption(f"**{goal_text}** — target **{money(target)}** by **{date_text}**")
    st.progress(
        progress,
        text=f"{progress*100:.1f}% toward goal "
             f"({money(pv['total_value'])} / {money(target)})",
    )


def _render_holdings_table(positions: list[dict]) -> None:
    if not positions:
        st.caption("Open **Trade** to make your first buy.")
        return
    st.dataframe(
        [
            {
                "Ticker": p["ticker"],
                "Qty": p["quantity"],
                "Avg cost": money(p["avg_buy_price"]),
                "Price": money(p["current_price"]),
                "Value": money(p["market_value"]),
                "P/L": signed_money(p["pnl"]),
                "P/L %": percent(p["pnl_pct"]),
            }
            for p in positions
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_recent_activity() -> None:
    rows = get_transactions(limit=5)
    if not rows:
        st.caption("No activity yet.")
        return
    for t in rows:
        emoji = "🟢" if t["action"] == "BUY" else "🔴"
        timestamp = t["timestamp"].replace("T", " ")
        st.markdown(
            f"{emoji} **{t['action']}** {t['quantity']} × **{t['ticker']}** "
            f"@ {money(t['price'])}"
        )
        st.caption(timestamp)
