"""
charts.py — Plotly charts for the TableFlow dashboard.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── Brand colors ──────────────────────────────────────────────────────────────
BURNT_ORANGE  = "#E8591A"
WARM_CREAM    = "#FAF3E8"
CHARCOAL      = "#1C1C1E"
SLATE         = "#4A4A52"
SAGE          = "#7A9E7E"
GOLD          = "#D4A843"
DANGER_RED    = "#C0392B"
BG_DARK       = "#141414"
CARD_BG       = "#1E1E20"
GRID_COLOR    = "#2A2A2E"


def _base_layout(title: str = "", height: int = 380) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=WARM_CREAM, size=14, family="Georgia, serif"), x=0.02),
        height=height,
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        font=dict(color=SLATE, family="'DM Sans', sans-serif", size=11),
        margin=dict(l=48, r=24, t=44, b=44),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=SLATE),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=SLATE),
    )


def wait_time_vs_servers(scan_results: list[dict], current_c: int) -> go.Figure:
    """Bar + line chart: avg wait time across staffing levels."""
    df = pd.DataFrame(scan_results)
    df = df[df["stable"]]

    fig = go.Figure()

    # Bar chart
    fig.add_trace(go.Bar(
        x=df["c"], y=df["Wq"],
        marker_color=[BURNT_ORANGE if c == current_c else "#3A3A3E" for c in df["c"]],
        name="Avg Wait (min)",
        hovertemplate="<b>%{x} servers</b><br>Avg wait: %{y:.1f} min<extra></extra>",
    ))

    # Threshold line at 10 min
    fig.add_hline(y=10, line_dash="dot", line_color=GOLD,
                  annotation_text="10-min target", annotation_font_color=GOLD,
                  annotation_position="top right")

    fig.update_layout(**_base_layout("⏱ Average Wait Time by Staffing Level"))
    fig.update_xaxes(title_text="Number of Servers", dtick=1)
    fig.update_yaxes(title_text="Avg Wait Time (min)")
    return fig


def cost_revenue_chart(cost_rows: list[dict], optimal_c: int) -> go.Figure:
    """Stacked area: staffing cost, revenue captured, net profit by server count."""
    df = pd.DataFrame(cost_rows)
    df = df[df["net"] > -1e9]  # filter unstable

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["c"], y=df["revenue_captured"],
        fill="tozeroy", name="Revenue Captured",
        line=dict(color=SAGE, width=2),
        fillcolor="rgba(122,158,126,0.2)",
        hovertemplate="<b>%{x} servers</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=df["c"], y=df["staffing_cost"],
        fill="tozeroy", name="Staffing Cost",
        line=dict(color=DANGER_RED, width=2),
        fillcolor="rgba(192,57,43,0.15)",
        hovertemplate="<b>%{x} servers</b><br>Cost: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=df["c"], y=df["net"],
        name="Net Profit",
        line=dict(color=GOLD, width=3),
        hovertemplate="<b>%{x} servers</b><br>Net: $%{y:,.0f}<extra></extra>",
    ))

    # Mark optimal
    opt_row = df[df["c"] == optimal_c]
    if not opt_row.empty:
        fig.add_vline(x=optimal_c, line_dash="dot", line_color=BURNT_ORANGE,
                      annotation_text=f"Optimal: {optimal_c} servers",
                      annotation_font_color=BURNT_ORANGE,
                      annotation_position="top right")

    fig.update_layout(**_base_layout("💰 Revenue vs. Staffing Cost"))
    fig.update_xaxes(title_text="Number of Servers", dtick=1)
    fig.update_yaxes(title_text="Amount ($)")
    return fig


def wait_distribution(sim_df: pd.DataFrame) -> go.Figure:
    """Histogram of per-customer wait times from simulation."""
    fig = go.Figure()

    if sim_df.empty:
        return fig

    fig.add_trace(go.Histogram(
        x=sim_df["wait_time_min"],
        nbinsx=30,
        marker_color=BURNT_ORANGE,
        opacity=0.85,
        name="Wait Time",
        hovertemplate="Wait: %{x:.1f} min<br>Count: %{y}<extra></extra>",
    ))

    avg = sim_df["wait_time_min"].mean()
    fig.add_vline(x=avg, line_dash="dash", line_color=GOLD,
                  annotation_text=f"Avg: {avg:.1f} min",
                  annotation_font_color=GOLD)

    fig.update_layout(**_base_layout("📊 Wait Time Distribution (Simulation)"))
    fig.update_xaxes(title_text="Wait Time (min)")
    fig.update_yaxes(title_text="Number of Customers")
    return fig


def queue_animation(snapshots: list[dict]) -> go.Figure:
    """Animated bar chart showing queue length over time."""
    if not snapshots:
        return go.Figure()

    times = [s["time_min"] for s in snapshots]
    queues = [s["queue_length"] for s in snapshots]
    in_svc = [s["in_service"] for s in snapshots]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=times, y=queues,
        fill="tozeroy",
        name="Waiting in Queue",
        line=dict(color=BURNT_ORANGE, width=2),
        fillcolor="rgba(232,89,26,0.25)",
    ))

    fig.add_trace(go.Scatter(
        x=times, y=in_svc,
        fill="tozeroy",
        name="Being Served",
        line=dict(color=SAGE, width=2),
        fillcolor="rgba(122,158,126,0.2)",
    ))

    fig.update_layout(**_base_layout("🎬 Queue Dynamics Over Service Period", height=320))
    fig.update_xaxes(title_text="Time (minutes into service)")
    fig.update_yaxes(title_text="Number of Customers")
    return fig


def utilization_gauge(rho: float, c: int) -> go.Figure:
    """Gauge chart showing server utilization."""
    color = SAGE if rho < 0.7 else GOLD if rho < 0.85 else DANGER_RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(rho * 100, 1),
        number=dict(suffix="%", font=dict(color=WARM_CREAM, size=28)),
        title=dict(text="Server Utilization", font=dict(color=SLATE, size=12)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=SLATE, tickfont=dict(color=SLATE)),
            bar=dict(color=color, thickness=0.6),
            bgcolor=GRID_COLOR,
            borderwidth=0,
            steps=[
                dict(range=[0, 70], color="#1E2820"),
                dict(range=[70, 85], color="#2A2710"),
                dict(range=[85, 100], color="#2A1510"),
            ],
            threshold=dict(line=dict(color=DANGER_RED, width=2), thickness=0.75, value=90),
        ),
    ))

    fig.update_layout(
        height=220,
        paper_bgcolor=CARD_BG,
        font=dict(color=SLATE),
        margin=dict(l=20, r=20, t=40, b=10),
    )
    return fig
