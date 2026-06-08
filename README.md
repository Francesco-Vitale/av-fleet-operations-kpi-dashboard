# AV Fleet Operations KPI Dashboard

A portfolio project demonstrating cross-market operational benchmarking for an autonomous vehicle ridepooling deployment — including anomaly detection and a disruption shock simulator.

**Live demo:** *https://av-fleet-operations-kpi-dashboard-ua2o4xvpkmygypfyhtphg4.streamlit.app/*

---

## What this project is

Researching MOIA's operator enablement model, I built a prototype KPI dashboard to explore what cross-market operational benchmarking might look like for an AV ridepooling deployment — including a shock simulator to stress-test KPI thresholds.

The dashboard simulates 30 days of ridepooling operations across two fictional markets:

- **Hamburg** — a mature, stable deployment with one software-update degradation event
- **Oslo** — a newer deployment with visible performance improvement over the 30-day period and a weather spike anomaly

All data is generated in-code using a realistic parametric model (no external files).

---

## KPIs computed and why

| KPI | Formula | Why it matters |
|-----|---------|----------------|
| **Fleet Utilization Rate** | Vehicle hours ÷ (fleet × 24h) | Measures how productively the fleet is deployed; low values indicate idle capacity |
| **Passengers per Vehicle-Hour** | Trips ÷ vehicle hours | Core service efficiency metric — how much value each vehicle-hour delivers |
| **Deadhead Ratio** | Empty km ÷ total service km | Operational waste indicator; high deadhead means poor routing or demand mismatch |
| **On-Time Rate** | Direct from data | Passenger experience proxy; directly tied to operator SLA compliance |
| **Pooling Rate** | Shared trips ÷ total trips | AV ridepooling viability metric; high pooling reduces cost per trip and emissions |
| **Disruption Rate** | Disruptions ÷ trips | Reliability signal for safety/operations teams |
| **Weighted Disruption Score** | Disruptions × severity ÷ trips | Severity-adjusted reliability; penalizes serious incidents over minor ones |

Each KPI has defined thresholds (green / amber / red) and a weight in the **Market Maturity Score** — a 0–100 composite index for quick cross-market comparison.

---

## Dashboard views

### 1. Market Overview (default)
Side-by-side scorecards for each market showing 30-day KPI averages with color-coded status bands and a prominent maturity score.

### 2. KPI Trends
Time-series line chart for any selected KPI, both markets overlaid. Anomaly days (> 2σ from rolling 7-day mean) are flagged as red open circles. Includes a date range slider and a period summary table.

### 3. Operational Shock Simulator
Two sliders simulate a cold-weather event and a fleet maintenance pull. The dashboard computes projected KPI deltas using a linear degradation model and displays them as colored delta badges (↑ / ↓ with %).

---

## How to run locally

**Requirements:** Python 3.9+

```bash
pip install streamlit pandas numpy plotly
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## How to deploy (Streamlit Community Cloud)

1. Push this repo to GitHub (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub account
3. Select the repo, set the main file to `app.py`, click **Deploy**
4. Paste the generated URL above

---

## Project structure

```
.
├── app.py            # Complete Streamlit dashboard (single file, no external data)
└── README.md         # This file
└── requirements.txt  # List of external libraries
```
**View 3 — Shock Simulator:** Sliders set to 40% weather and 20% fleet reduction. Delta badges show On-Time Rate down 3.2% (red) and Disruption Rate up 2.0% (red) for both markets.

