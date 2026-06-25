"""AI Recommendations page.

Two tabs: Pending (cards with Accept / Reject / Ignore) and History
(table of past recs with computed outcomes). The Generate button calls
the AI engine and the resulting suggestions land in Pending.

Accepting a BUY or SELL hands off to the Trade page via session state
(same `prefill_ticker` / `prefill_qty` mechanism the Market Explorer
already uses), plus an extra `pending_rec_id` so the trade can be
linked back to the recommendation. Accepting a HOLD simply marks the
recommendation as accepted with no trade.
"""
import os

import streamlit as st

from services.ai_engine import AIEngineError, generate_recommendations
from services.market_data import get_price
from services.profile import profile_exists
from services.recommendations import (
    list_history,
    list_pending,
    set_user_action,
)
from utils.formatters import money


ACTION_BADGE = {
    "BUY":  ("🟢", "#10b981"),
    "SELL": ("🔴", "#ef4444"),
    "HOLD": ("🟡", "#f59e0b"),
}


def render() -> None:
    st.title("🤖 AI Recommendations")
    st.caption(
        "The agent reads your portfolio, risk profile, and recent market "
        "indicators, then suggests up to 3 trades. Past recommendations are "
        "fed back so the AI can learn from how its prior calls played out."
    )

    if not profile_exists():
        st.warning("Please set up your **Investment Profile** before requesting recommendations.")
        return

    if not os.environ.get("GROQ_API_KEY"):
        st.error(
            "🔑 **GROQ_API_KEY is not set.** Copy `.env.example` to `.env` "
            "and add your Groq API key, then restart the app."
        )
        return

    _render_generate_button()

    st.divider()

    tab_pending, tab_history = st.tabs(["📥 Pending", "📚 History"])
    with tab_pending:
        _render_pending()
    with tab_history:
        _render_history()


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def _render_generate_button() -> None:
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        clicked = st.button(
            "✨ Generate New Recommendations",
            type="primary",
            use_container_width=True,
            key="generate_recs_btn",
        )
    with col_info:
        st.caption(
            "Calls Groq `llama-3.3-70b-versatile`. Suggestions are saved to "
            "your history and appear in the **Pending** tab below."
        )

    if clicked:
        with st.spinner("Asking the agent for fresh ideas…"):
            try:
                created = generate_recommendations(max_suggestions=3)
                st.success(f"Got {len(created)} new recommendation(s).")
                st.rerun()
            except AIEngineError as e:
                st.error(f"Could not generate recommendations: {e}")


# ---------------------------------------------------------------------------
# Pending tab
# ---------------------------------------------------------------------------
def _render_pending() -> None:
    recs = list_pending()
    if not recs:
        st.info("No pending recommendations. Click **Generate** above to get fresh ideas.")
        return

    for rec in recs:
        _render_rec_card(rec)


def _render_rec_card(rec: dict) -> None:
    ticker = rec["ticker"]
    action = rec["action"]
    confidence = int(rec["confidence"])
    emoji, color = ACTION_BADGE.get(action, ("⚪", "#6b7280"))

    with st.container(border=True):
        head_l, head_r = st.columns([3, 2])
        with head_l:
            st.markdown(
                f"### {emoji} **{action}** · {ticker}"
            )
            st.caption(f"🕒 {_format_timestamp(rec['timestamp'])}")
        with head_r:
            st.markdown(
                f"<div style='text-align:right;'>"
                f"<span style='font-size:0.85rem;color:#6b7280;'>Confidence</span><br>"
                f"<span style='font-size:1.4rem;font-weight:700;color:{color};'>"
                f"{_stars(confidence)}</span><br>"
                f"<span style='font-size:0.8rem;color:#6b7280;'>{confidence} / 5</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Live price for context (cheap thanks to cache)
        live = get_price(ticker)
        if live is not None:
            st.metric(f"{ticker} current price", money(live))

        st.warning(f"⚠️ **Risk:** {rec['risk_note']}")

        with st.expander("🧠 Why this recommendation?"):
            st.write(rec["reasoning"])

        # Action buttons
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button(
                "✅ Accept",
                key=f"accept_{rec['id']}",
                type="primary",
                use_container_width=True,
            ):
                _accept(rec)
        with c2:
            if st.button(
                "❌ Reject",
                key=f"reject_{rec['id']}",
                use_container_width=True,
            ):
                set_user_action(rec["id"], "rejected")
                st.rerun()
        with c3:
            if st.button(
                "⏭ Ignore",
                key=f"ignore_{rec['id']}",
                use_container_width=True,
            ):
                set_user_action(rec["id"], "ignored")
                st.rerun()


def _accept(rec: dict) -> None:
    """Accept handling differs by action type.

    BUY/SELL → mark accepted, hand off to Trade page with prefill.
    HOLD     → just mark accepted (no trade).
    """
    set_user_action(rec["id"], "accepted")

    if rec["action"] == "HOLD":
        st.success(f"Acknowledged HOLD on {rec['ticker']}.")
        st.rerun()
        return

    st.session_state["prefill_ticker"] = rec["ticker"]
    st.session_state["prefill_qty"] = 1
    st.session_state["pending_rec_id"] = int(rec["id"])
    st.session_state["pending_rec_action"] = rec["action"]
    from ui.pages import trade_page  # lazy import to avoid cycle
    st.switch_page(trade_page)


# ---------------------------------------------------------------------------
# History tab
# ---------------------------------------------------------------------------
def _render_history() -> None:
    status = st.selectbox(
        "Filter",
        ["All", "Accepted", "Rejected", "Ignored"],
        key="history_filter",
    )
    status_filter = None if status == "All" else status.lower()
    recs = list_history(limit=200, status_filter=status_filter)
    if not recs:
        st.info("No past recommendations yet.")
        return

    rows = []
    for r in recs:
        rows.append({
            "When":       _format_timestamp(r["timestamp"]),
            "Ticker":     r["ticker"],
            "Action":     r["action"],
            "Confidence": f"{r['confidence']} / 5",
            "Status":     r["user_action"].capitalize(),
            "Risk note":  r["risk_note"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Tiny formatters local to the page
# ---------------------------------------------------------------------------
def _stars(confidence: int) -> str:
    confidence = max(1, min(5, int(confidence)))
    return "★" * confidence + "☆" * (5 - confidence)


def _format_timestamp(ts: str) -> str:
    return ts.replace("T", " ") if ts else "—"
