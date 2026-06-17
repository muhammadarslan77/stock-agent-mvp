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
