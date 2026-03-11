# 🍽️ TableFlow — Restaurant Staffing Optimizer

> **"How many servers do I actually need right now?"**
> TableFlow answers this question using queueing theory and discrete-event simulation — and translates the math into dollars a restaurant operator can act on.

**[Live Demo →](https://your-streamlit-url-here)** | Built with Python, SimPy, Streamlit, Plotly

---

## The Problem

Every restaurant shift starts with the same guessing game: how many servers do we need on the floor tonight?

Over-staff and your labor costs eat your margin. Under-staff and customers wait too long, abandon their tables, and don't come back. Most operators solve this with gut feel and experience — but gut feel doesn't tell you *exactly* how much revenue you're leaving on the table, or *precisely* how many servers would fix it.

TableFlow models this problem mathematically and gives operators a concrete, data-backed staffing recommendation with a dollar figure attached.

---

## What the App Does

TableFlow is a web dashboard where a restaurant operator inputs their service parameters and gets back:

- **Real-time queueing metrics** — average wait time, server utilization, probability any customer has to wait
- **Staffing recommendation** — the optimal number of servers to maximize net profit
- **Cost vs. revenue tradeoff chart** — shows exactly how profit changes as you add or remove servers
- **Lost revenue estimate** — how much money is walking out the door due to long waits
- **Queue dynamics simulation** — an animated view of how the queue builds and clears over a service period
- **Wait time distribution** — not just the average, but the full spread of how long customers actually wait

The operator doesn't need to know any math. They input numbers they already know (how busy it gets, how fast their servers work, what a cover is worth) and get back a recommendation in plain English.

---

## The Math: M/M/c Queueing Theory

Under the hood, TableFlow models the restaurant floor as an **M/M/c queue** — one of the foundational models in Operations Research.

### What M/M/c means

| Symbol | Meaning | In restaurant terms |
|--------|---------|-------------------|
| First M | Markov/Memoryless arrivals | Customers arrive randomly following a Poisson process |
| Second M | Markov/Memoryless service | Service times are exponentially distributed |
| c | Number of servers | Number of servers on the floor |

### Key parameters

- **λ (lambda)** — arrival rate: how many customers arrive per hour on average
- **μ (mu)** — service rate per server: how many customers one server can handle per hour
- **c** — number of servers
- **ρ (rho)** — server utilization: ρ = λ / (c · μ). Must be < 1 for the queue to be stable (i.e., customers leave faster than they arrive)

### The Erlang C Formula

The core of the model is the **Erlang C formula**, which gives us P(wait) — the probability that an arriving customer has to wait at all:

```
C(c, ρ) = [ (cρ)^c / c! · 1/(1-ρ) ] / [ Σ(k=0 to c-1) (cρ)^k/k! + (cρ)^c/c! · 1/(1-ρ) ]
```

From P(wait), we derive the key performance metrics using **Little's Law** (L = λW):

| Metric | Formula | Meaning |
|--------|---------|---------|
| Lq | C(c,ρ) · ρ / (1-ρ) | Average number of customers waiting in queue |
| Wq | Lq / λ | Average wait time in queue |
| W | Wq + 1/μ | Average total time in system (wait + service) |
| L | λ · W | Average total customers in system (Little's Law) |

### Why this works for restaurants

Customer arrivals at a restaurant approximate a Poisson process well — especially during a defined service period like a dinner rush. Service times vary but are reasonably modeled as exponential. The M/M/c model gives closed-form answers instantly, which is what makes real-time what-if analysis possible.

### Stability condition

A queue is only stable if ρ < 1, meaning servers can keep up with demand. TableFlow detects and flags unstable configurations — a situation where wait times grow without bound and the operator needs to add staff immediately.

---

## The Cost Model

Knowing the average wait time is useful. Knowing what it costs you is actionable.

TableFlow attaches a business model on top of the queueing math:

**Revenue captured** = (potential covers) × (1 - fraction who leave due to long waits) × (revenue per cover)

**Staffing cost** = c × hourly labor cost × service period length

**Net profit** = Revenue captured − Staffing cost

The fraction of customers who leave (balk) is estimated from the average wait relative to the operator's configured tolerance threshold. The model sweeps across all staffing levels from 1 to c+8 and identifies the server count that maximizes net profit — the recommendation shown in the dashboard.

---

## Discrete-Event Simulation with SimPy

The analytical M/M/c model gives exact expected values but no distribution information. To get the full picture — the spread of wait times, the 95th percentile, how the queue evolves minute by minute — TableFlow runs a **discrete-event simulation** using SimPy.

### How it works

1. Customers are generated with inter-arrival times drawn from Exponential(1/λ)
2. Each customer requests a server from a SimPy Resource pool of size c
3. Service duration is drawn from Exponential(1/μ)
4. Every 3 minutes of simulated time, a snapshot records queue length and servers in use
5. After the simulation, per-customer records are aggregated into statistics

### Why both?

The analytical model is instant and exact for expected values. The simulation is slower but gives:
- The full wait time distribution (not just the mean)
- P95 wait time — what the worst 5% of customers experience
- Queue dynamics over time — how the line builds during peak arrival and clears afterward
- Validation that the analytical model's assumptions hold for this parameter set

In practice, the analytical and simulation results agree closely, which builds confidence in the recommendation.

---

## Project Structure

```
tableflow/
├── app.py                    # Streamlit dashboard — entry point
├── environment.yml           # Conda environment (or use pip install)
├── README.md
│
├── sim/
│   ├── __init__.py
│   ├── queue_model.py        # M/M/c analytical model, Erlang C, staffing scan
│   ├── simpy_engine.py       # Discrete-event simulation engine
│   └── cost_model.py         # Revenue and staffing cost calculations
│
├── components/
│   ├── __init__.py
│   └── charts.py             # All Plotly visualizations
│
├── tests/
│   └── test_queue_model.py   # Unit tests: Erlang C, M/M/c metrics, Little's Law
│
└── data/
    └── sample_profile.json   # Restaurant presets (Fast Casual, Fine Dining, etc.)
```

---

## How to Run

### Prerequisites
- Python 3.11+
- pip or conda

### Setup

```bash
# Clone the repo
git clone https://github.com/your-username/tableflow.git
cd tableflow

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install streamlit simpy plotly pandas numpy scipy

# Run the app
streamlit run app.py
```

Opens at `http://localhost:8501`.

### Run tests

```bash
pytest tests/ -v
```

Expected output: 9 tests passing, covering Erlang C correctness, stability detection, Little's Law validation, and monotonicity of wait time vs. server count.

---

## Sample Results

Using the **Casual Sit-Down** preset (λ=20 covers/hr, μ=4 covers/hr/server, $28 revenue/cover):

| Servers | Avg Wait | Utilization | Est. Net / Period |
|---------|----------|-------------|-------------------|
| 3 | Unstable | >100% | — |
| 6 | 8.8 min | 83% | $1,240 |
| **7 (optimal)** | **2.4 min** | **71%** | **$1,890** |
| 10 | 0.1 min | 50% | $1,120 |

Adding one server vs. the 6-server baseline: **+$650 per service period**. At 3 dinner services per day, that's ~$1,950/day in recovered revenue — from one staffing decision.

---

## Presets Included

| Preset | λ | μ | Typical Challenge |
|--------|---|---|-------------------|
| Fast Casual (Chipotle-style) | 40/hr | 15/hr | Speed-sensitive customers, thin margins |
| Casual Sit-Down (Applebee's-style) | 20/hr | 4/hr | Balancing wait tolerance with labor cost |
| Fine Dining | 8/hr | 1.5/hr | Slow service by design, high ticket |
| Coffee Shop (Morning Rush) | 60/hr | 30/hr | Extreme volume, very low balk threshold |

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core language |
| SimPy | Discrete-event simulation |
| Streamlit | Web dashboard |
| Plotly | Interactive charts |
| NumPy / Pandas | Numerical computation and data handling |
| SciPy | Supporting math utilities |
| pytest | Unit testing |

---

## Interview Explanation

> "I modeled a restaurant floor as an M/M/c queue — customers arrive as a Poisson process, service times are exponential, and c is the number of servers. The Erlang C formula gives us the probability any customer waits and the average wait time analytically, in closed form. I sweep across all staffing levels, attach a cost/revenue model to translate wait time into dollars, and surface the profit-maximizing server count. A SimPy simulation runs in parallel to validate the analytical results and generate the full wait time distribution. The whole thing lives in a Streamlit dashboard a restaurant operator can use without knowing any queueing theory."

---

## What's Next

- [ ] Peak Hour Planner — input hourly arrival patterns, get a full-day staffing schedule
- [ ] Multi-station modeling — separate bar, host stand, and kitchen queues
- [ ] Historical data import — upload POS export to auto-calibrate λ and μ
- [ ] Mobile-responsive layout

---

## About

Built by Shamsad Rahman, MSIE candidate specializing in Operations Research, stochastic processes, and production systems. This project applies M/M/c queueing theory from graduate coursework (stochastic models, production systems) to a real operational problem faced by small restaurant operators.