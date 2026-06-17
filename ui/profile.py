"""Profile page: define goal, target, risk tolerance, starting cash."""
from datetime import date

import streamlit as st

from config import DEFAULT_STARTING_CASH
from services.profile import get_profile, save_profile


GOALS = ["Retirement", "House deposit", "Wealth growth", "Education", "Other"]


def render() -> None:
    st.title("Investment Profile")
    st.caption("Tell the agent who you are and what you want to achieve.")

    profile = get_profile() or {}
    is_existing = bool(profile)

    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Your name", value=profile.get("name", ""))
            goal = st.selectbox(
                "Investment goal",
                options=GOALS,
                index=_safe_index(GOALS, profile.get("goal", "Retirement")),
            )
            risk = st.select_slider(
                "Risk tolerance",
                options=["low", "medium", "high"],
                value=profile.get("risk_tolerance", "medium"),
                help="Caps maximum share of portfolio in a single stock. "
                     "Low 10% · Medium 25% · High 50%.",
            )
        with col2:
            target_amount = st.number_input(
                "Target amount ($)", min_value=0.0, step=1000.0,
                value=float(profile.get("target_amount") or 100_000.0),
            )
            target_date_default = (
                date.fromisoformat(profile["target_date"])
                if profile.get("target_date")
                else date.today().replace(year=date.today().year + 5)
            )
            target_date = st.date_input("Target date", value=target_date_default)
            starting_cash = st.number_input(
                "Starting virtual cash ($)",
                min_value=100.0, step=500.0,
                value=float(profile.get("starting_cash") or DEFAULT_STARTING_CASH),
                disabled=is_existing,
                help="Locked after first save so cash tracking stays consistent.",
            )

        submitted = st.form_submit_button(
            "Save profile", type="primary", use_container_width=True
        )

    if submitted:
        try:
            save_profile(
                name=name.strip(),
                goal=goal,
                target_amount=float(target_amount),
                target_date=target_date.isoformat(),
                risk_tolerance=risk,
                # Lock starting_cash after first save.
                starting_cash=(float(profile["starting_cash"])
                               if is_existing else float(starting_cash)),
            )
            st.success("Profile saved.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))


def _safe_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0
