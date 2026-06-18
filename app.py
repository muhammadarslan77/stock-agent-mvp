"""Stock Agent MVP — Streamlit entry point.

Boots the database, loads env vars, registers pages in the sidebar.
Page objects live in `ui/pages.py` so other modules can `st.switch_page` them.
"""
import streamlit as st
from dotenv import load_dotenv

from database.schema import init_db


load_dotenv()
init_db()

st.set_page_config(
    page_title="Stock Agent MVP",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import after set_page_config so Streamlit's session is fully initialized
# before any page modules (and their decorators) load.
from ui.pages import (  # noqa: E402
    analysis_page,
    dashboard_page,
    market_page,
    profile_page,
    trade_page,
)

nav = st.navigation({
    "Overview": [dashboard_page, market_page],
    "Manage": [trade_page, analysis_page, profile_page],
})
nav.run()
