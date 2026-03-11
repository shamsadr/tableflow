"""
simpy_engine.py — Discrete-event simulation of restaurant service using SimPy.

Used to:
1. Validate the analytical M/M/c results
2. Collect per-customer wait time distributions (not available analytically)
3. Power the animated queue visualization
"""

import simpy
import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class CustomerRecord:
    customer_id: int
    arrival_time: float
    service_start: float = 0.0
    departure_time: float = 0.0
    balked: bool = False

    @property
    def wait_time(self) -> float:
        return (self.service_start - self.arrival_time) * 60  # minutes

    @property
    def service_time(self) -> float:
        return (self.departure_time - self.service_start) * 60  # minutes


def run_simulation(
    lam: float,
    mu: float,
    c: int,
    sim_hours: float = 4.0,
    max_wait_balk: float = 15.0,   # minutes — customer leaves if expected wait > this
    random_seed: int = 42,
    snapshot_interval: float = 0.05,  # hours between queue snapshots
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Run a SimPy M/M/c restaurant simulation.

    Args:
        lam:              arrival rate (customers/hour)
        mu:               service rate per server (customers/hour)
        c:                number of servers
        sim_hours:        total simulation duration
        max_wait_balk:    customers balk if queue wait exceeds this (minutes)
        random_seed:      reproducibility
        snapshot_interval: how often to record queue length for animation

    Returns:
        customers_df:  DataFrame with per-customer records
        snapshots:     list of {time, queue_length, in_service} dicts for animation
    """
    rng = np.random.default_rng(random_seed)
    customers: list[CustomerRecord] = []
    snapshots: list[dict] = []
    customer_id = 0

    env = simpy.Environment()
    servers = simpy.Resource(env, capacity=c)

    def customer(env, cid, record):
        # Request a server
        with servers.request() as req:
            arrival = env.now
            yield req
            record.service_start = env.now

            # Simulate service
            service_duration = rng.exponential(1 / mu)
            yield env.timeout(service_duration)
            record.departure_time = env.now

    def arrivals(env):
        nonlocal customer_id
        while True:
            # Inter-arrival time ~ Exponential(λ)
            iat = rng.exponential(1 / lam)
            yield env.timeout(iat)

            customer_id += 1
            rec = CustomerRecord(customer_id=customer_id, arrival_time=env.now)
            customers.append(rec)
            env.process(customer(env, customer_id, rec))

    def snapshot_recorder(env):
        while True:
            snapshots.append({
                "time_min": round(env.now * 60, 2),
                "queue_length": len(servers.queue),
                "in_service": servers.count,
                "utilization": servers.count / c,
            })
            yield env.timeout(snapshot_interval)

    env.process(arrivals(env))
    env.process(snapshot_recorder(env))
    env.run(until=sim_hours)

    # Build dataframe
    completed = [r for r in customers if r.departure_time > 0]
    if not completed:
        return pd.DataFrame(), snapshots

    df = pd.DataFrame([{
        "customer_id": r.customer_id,
        "arrival_time_hr": r.arrival_time,
        "wait_time_min": r.wait_time,
        "service_time_min": r.service_time,
        "total_time_min": r.wait_time + r.service_time,
    } for r in completed])

    return df, snapshots


def sim_summary(df: pd.DataFrame) -> dict:
    """Summarize simulation results into key metrics."""
    if df.empty:
        return {}
    return {
        "avg_wait_min": round(df["wait_time_min"].mean(), 2),
        "p95_wait_min": round(df["wait_time_min"].quantile(0.95), 2),
        "max_wait_min": round(df["wait_time_min"].max(), 2),
        "pct_zero_wait": round((df["wait_time_min"] < 0.5).mean() * 100, 1),
        "avg_service_min": round(df["service_time_min"].mean(), 2),
        "total_served": len(df),
    }
