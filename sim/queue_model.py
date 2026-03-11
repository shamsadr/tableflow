"""
queue_model.py — Analytical M/M/c queueing model + cost/revenue calculations.

Theory:
    Arrivals: Poisson(λ)   Service: Exponential(μ)   Servers: c
    ρ = λ / (c·μ)  — server utilization (must be < 1 for stable queue)
"""

import math
import numpy as np


def erlang_c(c: int, rho: float) -> float:
    """
    Compute Erlang C — probability that an arriving customer must wait.

    Args:
        c:   number of servers
        rho: offered load = λ / (c·μ), must be < 1

    Returns:
        P(wait) ∈ [0, 1]
    """
    if rho >= 1:
        return 1.0  # unstable — everyone waits

    a = c * rho  # total offered load λ/μ

    # Numerator: a^c / c! * 1/(1-rho)
    numerator = (a**c / math.factorial(c)) * (1 / (1 - rho))

    # Denominator: sum_{k=0}^{c-1} a^k/k!  +  numerator
    sum_terms = sum((a**k) / math.factorial(k) for k in range(c))
    denominator = sum_terms + numerator

    return numerator / denominator


def mmc_metrics(lam: float, mu: float, c: int) -> dict:
    """
    Compute standard M/M/c performance metrics.

    Args:
        lam: arrival rate (customers/hour)
        mu:  service rate per server (customers/hour)
        c:   number of servers

    Returns:
        dict with Lq, Wq, L, W, rho, P_wait, stable
    """
    rho = lam / (c * mu)
    stable = rho < 1.0

    if not stable:
        return {
            "stable": False,
            "rho": rho,
            "Lq": float("inf"),
            "Wq": float("inf"),
            "L": float("inf"),
            "W": float("inf"),
            "P_wait": 1.0,
        }

    C = erlang_c(c, rho)

    Lq = C * rho / (1 - rho)          # avg customers waiting in queue
    Wq = Lq / lam                      # avg wait time in queue (hours)
    W  = Wq + 1 / mu                   # avg total time in system (hours)
    L  = lam * W                       # avg customers in system (Little's Law)

    return {
        "stable": True,
        "rho": rho,
        "P_wait": C,
        "Lq": Lq,
        "Wq": Wq * 60,                 # convert to minutes
        "W": W * 60,
        "L": L,
    }


def scan_staffing_levels(
    lam: float,
    mu: float,
    c_min: int = 1,
    c_max: int = 20,
) -> list[dict]:
    """
    Run M/M/c for a range of server counts. Returns list of metric dicts.
    """
    results = []
    for c in range(c_min, c_max + 1):
        m = mmc_metrics(lam, mu, c)
        m["c"] = c
        results.append(m)
    return results


def cost_revenue_analysis(
    metrics: dict,
    c: int,
    hourly_labor_cost: float,
    revenue_per_cover: float,
    covers_per_table: float = 2.0,
    tables: int = 20,
    max_wait_before_balk: float = 15.0,   # minutes — customers leave if > this
    operating_hours: float = 4.0,          # hours per service period
) -> dict:
    """
    Translate queueing metrics into P&L numbers a restaurant owner understands.

    Model:
        - Customers who wait > max_wait_before_balk are lost (balking estimate)
        - Lost customers = lost revenue
        - Staffing cost = c * hourly_labor_cost * operating_hours
        - Net = Revenue captured - Staffing cost
    """
    if not metrics["stable"]:
        return {
            "staffing_cost": c * hourly_labor_cost * operating_hours,
            "revenue_captured": 0,
            "lost_revenue": float("inf"),
            "net": float("-inf"),
            "pct_customers_lost": 1.0,
        }

    # Fraction of customers who experience wait > threshold (exponential approx)
    # P(Wq > t) ≈ P_wait * exp(-(c*mu - lam)*t)
    wq_thresh_hr = max_wait_before_balk / 60
    lam_eff = metrics.get("_lam", 0)  # set externally if needed

    # Simpler conservative estimate: if avg wait > threshold, lose P_wait fraction
    avg_wq_min = metrics["Wq"]
    if avg_wq_min == 0:
        pct_lost = 0.0
    else:
        # logistic-style: fraction lost grows as wait exceeds threshold
        pct_lost = metrics["P_wait"] * min(1.0, avg_wq_min / max_wait_before_balk)

    total_potential_covers = tables * covers_per_table * (operating_hours / (metrics["W"] / 60 + 0.25))
    total_potential_covers = min(total_potential_covers, tables * covers_per_table * 4)  # cap at realistic

    lost_covers = total_potential_covers * pct_lost
    captured_covers = total_potential_covers - lost_covers

    revenue_captured = captured_covers * revenue_per_cover
    lost_revenue = lost_covers * revenue_per_cover
    staffing_cost = c * hourly_labor_cost * operating_hours
    net = revenue_captured - staffing_cost

    return {
        "staffing_cost": round(staffing_cost, 2),
        "revenue_captured": round(revenue_captured, 2),
        "lost_revenue": round(lost_revenue, 2),
        "net": round(net, 2),
        "pct_customers_lost": round(pct_lost * 100, 1),
        "total_potential_covers": round(total_potential_covers),
        "captured_covers": round(captured_covers),
    }
