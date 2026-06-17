"""Stock Agent MVP — Streamlit entry point.

Boots the database, loads env vars, registers pages in the sidebar.
Each page is implemented in ui/<page>.py and exposes a `render()` function.
"""
import streamlit as st
from dotenv import load_dotenv

from database.schema import init_db
from ui.dashboard import render as render_dashboard
from ui.profile import render as render_profile
from ui.trade import render as render_trade


load_dotenv()
init_db()

st.set_page_config(
    page_title="Stock Agent MVP",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

dashboard_page = st.Page(render_dashboard, title="Dashboard", icon="📊", url_path="dashboard", default=True)
trade_page = st.Page(render_trade, title="Trade", icon="💱", url_path="trade")
profile_page = st.Page(render_profile, title="Profile", icon="🎯", url_path="profile")

nav = st.navigation({
    "Overview": [dashboard_page],
    "Manage": [trade_page, profile_page],
})
nav.run()
