"""
TableFlow — Restaurant Staffing Optimizer
==========================================
Answers the question every restaurant operator has:
"How many servers do I actually need right now?"

Run:  streamlit run app.py
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from components.charts import (
    cost_revenue_chart,
    queue_animation,
    utilization_gauge,
    wait_distribution,
    wait_time_vs_servers,
)
from sim.queue_model import cost_revenue_analysis, mmc_metrics, scan_staffing_levels
from sim.simpy_engine import run_simulation, sim_summary

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TableFlow — Restaurant Staffing Optimizer",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=Playfair+Display:wght@600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #141414;
    color: #C8C8CC;
  }

  /* Header */
  .tf-header {
    background: linear-gradient(135deg, #1C1C1E 0%, #1A1208 100%);
    border-bottom: 1px solid #2A2A2E;
    padding: 2rem 2.5rem 1.5rem;
    margin: -1rem -1rem 2rem -1rem;
  }
  .tf-logo {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 2.2rem;
    font-weight: 700;
    color: #FAF3E8;
    letter-spacing: -0.5px;
  }
  .tf-logo span { color: #E8591A; }
  .tf-tagline {
    font-size: 0.88rem;
    color: #6A6A72;
    margin-top: 2px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  /* Metric cards */
  .metric-card {
    background: #1E1E20;
    border: 1px solid #2A2A2E;
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
    text-align: center;
  }
  .metric-value {
    font-size: 2rem;
    font-weight: 600;
    color: #FAF3E8;
    line-height: 1.1;
  }
  .metric-value.good  { color: #7A9E7E; }
  .metric-value.warn  { color: #D4A843; }
  .metric-value.bad   { color: #C0392B; }
  .metric-label {
    font-size: 0.75rem;
    color: #6A6A72;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-top: 4px;
  }
  .metric-delta {
    font-size: 0.78rem;
    margin-top: 3px;
  }
  .metric-delta.pos { color: #7A9E7E; }
  .metric-delta.neg { color: #C0392B; }

  /* Recommendation banner */
  .rec-banner {
    background: linear-gradient(90deg, #1E1208 0%, #1E1E20 100%);
    border-left: 3px solid #E8591A;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.4rem;
    margin: 1rem 0;
  }
  .rec-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    color: #FAF3E8;
    margin-bottom: 4px;
  }
  .rec-body { font-size: 0.88rem; color: #A0A0A8; line-height: 1.6; }
  .rec-highlight { color: #E8591A; font-weight: 600; }

  /* Section headers */
  .section-header {
    font-family: 'Playfair Display', serif;
    font-size: 1.05rem;
    color: #FAF3E8;
    border-bottom: 1px solid #2A2A2E;
    padding-bottom: 6px;
    margin: 1.5rem 0 0.8rem 0;
  }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background-color: #1A1A1C;
    border-right: 1px solid #2A2A2E;
  }
  [data-testid="stSidebar"] label {
    color: #A0A0A8 !important;
    font-size: 0.83rem !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {
    background-color: #1A1A1C;
    border-radius: 8px;
    padding: 2px;
    gap: 2px;
  }
  .stTabs [data-baseweb="tab"] {
    color: #6A6A72;
    background-color: transparent;
    border-radius: 6px;
    font-size: 0.85rem;
  }
  .stTabs [aria-selected="true"] {
    background-color: #2A2A2E !important;
    color: #FAF3E8 !important;
  }

  /* Stable/unstable badge */
  .badge-stable   { background:#0D1F10; color:#7A9E7E; border:1px solid #2A4A2E; padding:2px 10px; border-radius:20px; font-size:0.78rem; }
  .badge-unstable { background:#1F0D0D; color:#C0392B; border:1px solid #4A2A2A; padding:2px 10px; border-radius:20px; font-size:0.78rem; }

  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1rem; }

  </style>
""",
    unsafe_allow_html=True,
)

# ── Load presets ──────────────────────────────────────────────────────────────
PRESETS_PATH = Path("data/sample_profile.json")
with open(PRESETS_PATH) as f:
    PRESETS = json.load(f)["presets"]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="tf-header">
  <div class="tf-logo">Table<span>Flow</span></div>
  <div class="tf-tagline">Restaurant Staffing Intelligence · Powered by Queueing Theory</div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🍽️ Restaurant Profile")

    preset_choice = st.selectbox(
        "Load a preset",
        ["Custom"] + list(PRESETS.keys()),
        help="Start from a preset or configure manually below.",
    )

    if preset_choice != "Custom":
        p = PRESETS[preset_choice]
        st.caption(f"*{p['description']}*")
    else:
        p = PRESETS["Casual Sit-Down (Applebee's-style)"]  # defaults

    st.divider()
    st.markdown("**Arrival & Service**")

    lam = st.slider(
        "Arrival rate (covers/hour)",
        5,
        120,
        p["lam"] if preset_choice != "Custom" else 20,
        help="How many customers arrive per hour on average",
    )
    mu = st.slider(
        "Service rate per server (covers/hour)",
        0.50,
        60.0,
        float(p["mu"]) if preset_choice != "Custom" else 4.0,
        step=0.50,
        help="How many customers one server can handle per hour",
    )
    c = st.slider(
        "Current servers on floor", 1, 15, p["c"] if preset_choice != "Custom" else 5
    )

    st.divider()
    st.markdown("**Business Parameters**")

    hourly_labor = st.number_input(
        "Hourly labor cost per server ($)",
        10,
        60,
        p["hourly_labor_cost"] if preset_choice != "Custom" else 22,
    )
    rev_per_cover = st.number_input(
        "Revenue per cover ($)",
        5,
        200,
        p["revenue_per_cover"] if preset_choice != "Custom" else 28,
    )
    tables = st.slider(
        "Number of tables", 5, 60, p["tables"] if preset_choice != "Custom" else 20
    )
    covers_per_table = st.slider(
        "Avg covers per table",
        1,
        6,
        p["covers_per_table"] if preset_choice != "Custom" else 2,
    )
    max_wait_balk = st.slider(
        "Max wait before customer leaves (min)",
        3,
        45,
        p["max_wait_balk"] if preset_choice != "Custom" else 20,
    )
    operating_hrs = st.slider(
        "Service period (hours)",
        1,
        8,
        p["operating_hours"] if preset_choice != "Custom" else 4,
    )

    st.divider()
    run_sim = st.button(
        "▶ Run Full Simulation", use_container_width=True, type="primary"
    )

# ── Core calculations ─────────────────────────────────────────────────────────
metrics = mmc_metrics(lam, mu, c)
scan = scan_staffing_levels(lam, mu, c_min=1, c_max=min(20, c + 8))

# Build cost rows for all staffing levels
cost_rows = []
for row in scan:
    cr = cost_revenue_analysis(
        row,
        row["c"],
        hourly_labor,
        rev_per_cover,
        covers_per_table,
        tables,
        max_wait_balk,
        operating_hrs,
    )
    cr["c"] = row["c"]
    cr["stable"] = row["stable"]
    cost_rows.append(cr)

# Find optimal server count (max net profit among stable configs)
stable_cost = [r for r in cost_rows if r["stable"] and r["net"] > -1e9]
optimal_c = max(stable_cost, key=lambda x: x["net"])["c"] if stable_cost else c
current_cost = next((r for r in cost_rows if r["c"] == c), {})


# ── KPI cards ─────────────────────────────────────────────────────────────────
def color_class(val, good_thresh, warn_thresh, lower_is_better=True):
    if lower_is_better:
        return (
            "good" if val <= good_thresh else ("warn" if val <= warn_thresh else "bad")
        )
    return "good" if val >= good_thresh else ("warn" if val >= warn_thresh else "bad")


if metrics["stable"]:
    wq_color = color_class(metrics["Wq"], 10, 20)
    rho_color = color_class(metrics["rho"] * 100, 70, 85)
    stable_badge = '<span class="badge-stable">✓ Queue Stable</span>'
else:
    wq_color = rho_color = "bad"
    stable_badge = '<span class="badge-unstable">⚠ Queue Unstable — Add Servers</span>'

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    wq_display = f"{metrics['Wq']:.1f}" if metrics["stable"] else "∞"
    st.markdown(
        f"""
    <div class="metric-card">
      <div class="metric-value {wq_color}">{wq_display}</div>
      <div class="metric-label">Avg Wait (min)</div>
    </div>""",
        unsafe_allow_html=True,
    )

with col2:
    rho_display = f"{metrics['rho'] * 100:.0f}%" if metrics["stable"] else ">100%"
    st.markdown(
        f"""
    <div class="metric-card">
      <div class="metric-value {rho_color}">{rho_display}</div>
      <div class="metric-label">Server Utilization</div>
    </div>""",
        unsafe_allow_html=True,
    )

with col3:
    net_val = current_cost.get("net", 0)
    net_color = "good" if net_val > 0 else "bad"
    st.markdown(
        f"""
    <div class="metric-card">
      <div class="metric-value {net_color}">${net_val:,.0f}</div>
      <div class="metric-label">Est. Net / Period</div>
    </div>""",
        unsafe_allow_html=True,
    )

with col4:
    lost = current_cost.get("pct_customers_lost", 0)
    lost_color = color_class(lost, 5, 15)
    st.markdown(
        f"""
    <div class="metric-card">
      <div class="metric-value {lost_color}">{lost:.1f}%</div>
      <div class="metric-label">Est. Customers Lost</div>
    </div>""",
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f"""
    <div class="metric-card">
      <div class="metric-value" style="color:#E8591A">{optimal_c}</div>
      <div class="metric-label">Recommended Servers</div>
    </div>""",
        unsafe_allow_html=True,
    )

# ── Recommendation banner ──────────────────────────────────────────────────────
opt_cost = next((r for r in cost_rows if r["c"] == optimal_c), {})
opt_net = opt_cost.get("net", 0)
delta_net = opt_net - net_val
delta_str = f"+${delta_net:,.0f}" if delta_net > 0 else f"${delta_net:,.0f}"

if optimal_c != c:
    action = "add" if optimal_c > c else "reduce"
    diff = abs(optimal_c - c)
    advice = f"{action} {diff} server{'s' if diff > 1 else ''}"
    st.markdown(
        f"""
    <div class="rec-banner">
      <div class="rec-title">💡 Staffing Recommendation</div>
      <div class="rec-body">
        With <span class="rec-highlight">{c} servers</span>, your avg wait is
        <span class="rec-highlight">{metrics["Wq"]:.1f} min</span> and you're losing an estimated
        <span class="rec-highlight">{lost:.1f}%</span> of potential revenue to long waits or idle staff costs.
        Our model suggests you <span class="rec-highlight">{advice}</span> (→ {optimal_c} total)
        to maximize net profit at an estimated
        <span class="rec-highlight">${opt_net:,.0f}</span> this service period
        (<span class="rec-highlight">{delta_str}</span> vs. current).
      </div>
    </div>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""
    <div class="rec-banner">
      <div class="rec-title">✅ Staffing Looks Optimal</div>
      <div class="rec-body">
        Your current staffing of <span class="rec-highlight">{c} servers</span> appears to be
        the profit-maximizing configuration given your inputs. Avg wait:
        <span class="rec-highlight">{metrics["Wq"]:.1f} min</span>.
      </div>
    </div>""",
        unsafe_allow_html=True,
    )

st.markdown(stable_badge, unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📈 Wait Time Analysis",
        "💰 Cost & Revenue",
        "🎬 Queue Dynamics",
        "📋 Full Metrics Table",
    ]
)

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        fig_wt = wait_time_vs_servers(scan, c)
        st.plotly_chart(fig_wt, use_container_width=True)
    with col_b:
        fig_gauge = utilization_gauge(min(metrics["rho"], 1.0), c)
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.markdown(
            f"""
        <div style="background:#1E1E20;border:1px solid #2A2A2E;border-radius:8px;padding:0.9rem 1rem;font-size:0.82rem;color:#A0A0A8;line-height:1.7;">
          <b style="color:#FAF3E8">M/M/{c} Queue Stats</b><br>
          λ = {lam} covers/hr<br>
          μ = {mu} covers/hr/server<br>
          ρ = {metrics["rho"]:.3f}<br>
          P(wait) = {metrics.get("P_wait", 0) * 100:.1f}%<br>
          Avg in system = {metrics.get("L", 0):.1f} covers
        </div>""",
            unsafe_allow_html=True,
        )

with tab2:
    fig_cr = cost_revenue_chart(cost_rows, optimal_c)
    st.plotly_chart(fig_cr, use_container_width=True)

    col_x, col_y, col_z = st.columns(3)
    with col_x:
        st.metric(
            "Staffing Cost / Period", f"${current_cost.get('staffing_cost', 0):,.0f}"
        )
    with col_y:
        st.metric(
            "Revenue Captured", f"${current_cost.get('revenue_captured', 0):,.0f}"
        )
    with col_z:
        st.metric(
            "Lost Revenue (est.)",
            f"${current_cost.get('lost_revenue', 0):,.0f}",
            delta=f"-{lost:.1f}% customers lost",
            delta_color="inverse",
        )

with tab3:
    if run_sim or "sim_df" in st.session_state:
        if run_sim:
            with st.spinner("Running simulation..."):
                sim_df, snapshots = run_simulation(lam, mu, c, sim_hours=operating_hrs)
                st.session_state["sim_df"] = sim_df
                st.session_state["snapshots"] = snapshots

        sim_df = st.session_state["sim_df"]
        snapshots = st.session_state["snapshots"]
        summary = sim_summary(sim_df)

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Avg Wait (Sim)", f"{summary.get('avg_wait_min', 0):.1f} min")
        col_s2.metric("P95 Wait", f"{summary.get('p95_wait_min', 0):.1f} min")
        col_s3.metric("% Zero Wait", f"{summary.get('pct_zero_wait', 0):.1f}%")
        col_s4.metric("Total Served", summary.get("total_served", 0))

        col_anim, col_hist = st.columns(2)
        with col_anim:
            fig_anim = queue_animation(snapshots)
            st.plotly_chart(fig_anim, use_container_width=True)
        with col_hist:
            fig_dist = wait_distribution(sim_df)
            st.plotly_chart(fig_dist, use_container_width=True)

        # Analytical vs Sim comparison
        st.markdown(
            '<div class="section-header">Analytical vs. Simulation Validation</div>',
            unsafe_allow_html=True,
        )
        comp_df = pd.DataFrame(
            {
                "Metric": ["Avg Wait (min)", "Server Utilization"],
                "M/M/c Analytical": [
                    f"{metrics['Wq']:.2f}" if metrics["stable"] else "∞",
                    f"{metrics['rho'] * 100:.1f}%",
                ],
                "SimPy Simulation": [
                    f"{summary.get('avg_wait_min', 0):.2f}",
                    "—",
                ],
            }
        )
        st.dataframe(comp_df, hide_index=True, use_container_width=True)

    else:
        st.markdown(
            """
        <div style="text-align:center;padding:3rem;color:#4A4A52;">
          <div style="font-size:2.5rem">▶</div>
          <div style="margin-top:0.5rem;font-size:0.9rem">Click <b>Run Full Simulation</b> in the sidebar to generate queue dynamics and wait time distribution.</div>
        </div>""",
            unsafe_allow_html=True,
        )

with tab4:
    all_rows = []
    for row, cr in zip(scan, cost_rows):
        if row["stable"]:
            all_rows.append(
                {
                    "Servers (c)": row["c"],
                    "Utilization (ρ)": f"{row['rho']:.3f}",
                    "P(wait)": f"{row['P_wait'] * 100:.1f}%",
                    "Avg Wait (min)": f"{row['Wq']:.2f}",
                    "Avg in System": f"{row['L']:.2f}",
                    "Staffing Cost ($)": f"{cr['staffing_cost']:,.0f}",
                    "Revenue ($)": f"{cr['revenue_captured']:,.0f}",
                    "Net Profit ($)": f"{cr['net']:,.0f}",
                    "% Lost": f"{cr['pct_customers_lost']:.1f}%",
                    "Optimal ✓": "✓" if row["c"] == optimal_c else "",
                }
            )
        else:
            all_rows.append(
                {
                    "Servers (c)": row["c"],
                    "Utilization (ρ)": f"{row['rho']:.3f}",
                    "P(wait)": "—",
                    "Avg Wait (min)": "∞ (unstable)",
                    "Avg in System": "—",
                    "Staffing Cost ($)": f"{cr['staffing_cost']:,.0f}",
                    "Revenue ($)": "—",
                    "Net Profit ($)": "—",
                    "% Lost": "100%",
                    "Optimal ✓": "",
                }
            )

    st.dataframe(pd.DataFrame(all_rows), hide_index=True, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #2A2A2E;
     font-size:0.75rem;color:#3A3A42;text-align:center;">
  TableFlow · Built with M/M/c Queueing Theory + SimPy · © 2025
</div>
""",
    unsafe_allow_html=True,
)
