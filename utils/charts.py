"""Plotly chart builders for the dashboard.

Color palette deliberately matches the dark fintech blue/green theme
applied to the whole app in Phase 6.
"""
import pandas as pd
import plotly.graph_objects as go


FINTECH_PALETTE = [
    "#10b981",  # emerald
    "#3b82f6",  # blue
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#06b6d4",  # cyan
    "#84cc16",  # lime
    "#ec4899",  # pink
]


def allocation_pie(positions: list[dict]) -> go.Figure:
    """Donut chart of market value per ticker."""
    labels = [p["ticker"] for p in positions]
    values = [p["market_value"] for p in positions]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=FINTECH_PALETTE),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=True,
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
        legend=dict(orientation="v", x=1.02, y=0.5),
    )
    return fig


def price_history_line(hist: pd.DataFrame, color_by_trend: bool = True) -> go.Figure:
    """Area-filled spline of closing prices for a yfinance OHLCV frame.

    `color_by_trend` switches the line/fill to red when the period closed lower
    than it opened, otherwise emerald — matches the rest of the fintech palette.
    """
    if hist is None or hist.empty or "Close" not in hist:
        return go.Figure()

    closes = hist["Close"].dropna()
    if closes.empty:
        return go.Figure()

    is_up = closes.iloc[-1] >= closes.iloc[0] or not color_by_trend
    line_color = "#10b981" if is_up else "#ef4444"
    fill_color = "rgba(16, 185, 129, 0.12)" if is_up else "rgba(239, 68, 68, 0.12)"

    fig = go.Figure(
        go.Scatter(
            x=closes.index,
            y=closes.values,
            mode="lines",
            line=dict(color=line_color, width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="<b>$%{y:,.2f}</b><br>%{x|%Y-%m-%d}<extra></extra>",
        )
    )
    y_min, y_max = float(closes.min()), float(closes.max())
    pad = max((y_max - y_min) * 0.1, y_max * 0.01, 0.5)
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
        yaxis=dict(
            title="Price ($)",
            tickprefix="$",
            separatethousands=True,
            range=[max(0, y_min - pad), y_max + pad],
        ),
        xaxis=dict(title=""),
        hovermode="x unified",
    )
    return fig


def growth_line(snapshots: list[dict]) -> go.Figure:
    """Line chart of total portfolio value over time."""
    df = pd.DataFrame(snapshots)
    if df.empty:
        return go.Figure()

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    fig = go.Figure(
        go.Scatter(
            x=df["timestamp"],
            y=df["total_value"],
            mode="lines+markers",
            line=dict(color="#10b981", width=3, shape="spline"),
            marker=dict(size=6, color="#10b981"),
            hovertemplate="<b>$%{y:,.2f}</b><br>%{x|%Y-%m-%d %H:%M}<extra></extra>",
        )
    )
    # Clamp y-axis so small variation around the starting cash still reads well.
    y_min, y_max = df["total_value"].min(), df["total_value"].max()
    pad = max((y_max - y_min) * 0.15, y_max * 0.02, 1.0)
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
        yaxis=dict(
            title="Total value ($)",
            tickprefix="$",
            separatethousands=True,
            range=[y_min - pad, y_max + pad],
        ),
        xaxis=dict(title=""),
        hovermode="x unified",
    )
    return fig
