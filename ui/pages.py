"""Central registry of Streamlit Page objects.

Defining the pages in one place lets other UI modules import them and call
`st.switch_page(...)` without app.py importing them and creating a cycle.
"""
import streamlit as st

from ui.analysis import render as render_analysis
from ui.dashboard import render as render_dashboard
from ui.market import render as render_market
from ui.profile import render as render_profile
from ui.trade import render as render_trade


dashboard_page = st.Page(
    render_dashboard, title="Dashboard", icon="📊", url_path="dashboard", default=True,
)
market_page = st.Page(
    render_market, title="Market", icon="🌐", url_path="market",
)
trade_page = st.Page(
    render_trade, title="Trade", icon="💱", url_path="trade",
)
analysis_page = st.Page(
    render_analysis, title="Analysis", icon="🔬", url_path="analysis",
)
profile_page = st.Page(
    render_profile, title="Profile", icon="🎯", url_path="profile",
)
