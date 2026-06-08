"""
MOIA-style AV Fleet Operations KPI Dashboard
Simulates 30 days of ridepooling operations across two markets.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="AV Fleet Operations Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 1. DATA GENERATION ──────────────────────────────────────────────────────

@st.cache_data
def generate_data(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-03-01", periods=30, freq="D")
    records = []

    for market, cfg in {
        "Hamburg": {
            # Mature market: high base, slight degradation mid-month
            "total_trips_base": 420,
            "veh_hours_base": 280,
            "fleet_base": 45,
            "wait_base": 5.2,
            "on_time_base": 0.91,
            "pooling_base": 0.68,
            "deadhead_frac": 0.18,
            "service_km_base": 4800,
            "disruption_base": 3.5,
            "trend": 0.0,          # stable
            "degrade_days": [14, 15, 16],  # software update dip
        },
        "Oslo": {
            # Newer deployment: lower start, clear improvement trend
            "total_trips_base": 210,
            "veh_hours_base": 160,
            "fleet_base": 28,
            "wait_base": 8.1,
            "on_time_base": 0.76,
            "pooling_base": 0.48,
            "deadhead_frac": 0.27,
            "service_km_base": 2600,
            "disruption_base": 6.2,
            "trend": 0.025,        # ~2.5% improvement per day
            "degrade_days": [7],   # bad weather spike
        },
    }.items():
        for i, d in enumerate(dates):
            t = cfg["trend"] * i  # improvement factor

            # Base values with maturity trend
            trips = int(cfg["total_trips_base"] * (1 + t) * rng.normal(1.0, 0.04))
            fleet = cfg["fleet_base"] + (1 if i > 15 else 0)
            veh_hours = cfg["veh_hours_base"] * (1 + t * 0.5) * rng.normal(1.0, 0.03)
            service_km = cfg["service_km_base"] * (1 + t * 0.4) * rng.normal(1.0, 0.04)
            deadhead_km = service_km * cfg["deadhead_frac"] * rng.normal(1.0, 0.06) * (1 - t * 0.3)
            wait_time = cfg["wait_base"] * (1 - t * 0.4) * rng.normal(1.0, 0.05)
            on_time = min(0.99, cfg["on_time_base"] + t * 0.08 + rng.normal(0, 0.02))
            pooling = min(0.95, cfg["pooling_base"] + t * 0.12 + rng.normal(0, 0.025))
            pax_hours = trips * rng.uniform(0.25, 0.40)
            disruptions = max(0, int(cfg["disruption_base"] * (1 - t * 0.5) * rng.normal(1.0, 0.2)))
            sev = rng.uniform(1.8, 3.2) * (1 - t * 0.2)

            # Degradation events
            if i in cfg.get("degrade_days", []):
                trips = int(trips * rng.uniform(0.70, 0.80))
                wait_time *= rng.uniform(1.3, 1.6)
                on_time *= rng.uniform(0.80, 0.90)
                disruptions = int(disruptions * rng.uniform(2.5, 4.0))
                sev = min(5.0, sev * rng.uniform(1.5, 2.0))

            records.append({
                "date": d,
                "market": market,
                "total_trips": max(1, trips),
                "total_vehicle_hours": round(max(10, veh_hours), 1),
                "total_passenger_hours": round(max(1, pax_hours), 1),
                "total_deadhead_km": round(max(0, deadhead_km), 1),
                "total_service_km": round(max(1, service_km), 1),
                "avg_wait_time_min": round(max(1.0, wait_time), 2),
                "on_time_rate": round(min(0.99, max(0.5, on_time)), 3),
                "pooling_rate": round(min(0.95, max(0.2, pooling)), 3),
                "fleet_size": fleet,
                "service_disruptions": disruptions,
                "disruption_severity": round(min(5.0, max(1.0, sev)), 2),
            })

    return pd.DataFrame(records)


def compute_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Derive the 7 operational KPIs from raw data."""
    out = df.copy()
    out["fleet_utilization_rate"] = (
        out["total_vehicle_hours"] / (out["fleet_size"] * 24)
    ).round(4)
    out["passengers_per_vehicle_hour"] = (
        out["total_trips"] / out["total_vehicle_hours"]
    ).round(3)
    out["deadhead_ratio"] = (
        out["total_deadhead_km"] / out["total_service_km"]
    ).round(4)
    out["disruption_rate"] = (
        out["service_disruptions"] / out["total_trips"]
    ).round(5)
    out["weighted_disruption_score"] = (
        out["service_disruptions"] * out["disruption_severity"] / out["total_trips"]
    ).round(5)
    return out


# ─── 2. KPI METADATA ─────────────────────────────────────────────────────────

KPI_META = {
    "fleet_utilization_rate": {
        "label": "Fleet Utilization Rate",
        "unit": "",
        "fmt": ".1%",
        "green": 0.35, "amber": 0.25,   # green if ≥ green threshold
        "higher_is_better": True,
        "weight": 1.5,
        "desc": "Vehicle hours in service ÷ total available (fleet × 24h)",
    },
    "passengers_per_vehicle_hour": {
        "label": "Pax / Vehicle-Hour",
        "unit": "",
        "fmt": ".2f",
        "green": 1.5, "amber": 1.0,
        "higher_is_better": True,
        "weight": 2.0,
        "desc": "Trips completed per vehicle-hour — service efficiency",
    },
    "deadhead_ratio": {
        "label": "Deadhead Ratio",
        "unit": "",
        "fmt": ".1%",
        "green": 0.22, "amber": 0.30,   # green if ≤ green threshold
        "higher_is_better": False,
        "weight": 1.5,
        "desc": "Empty-km share of total service km — operational waste",
    },
    "on_time_rate": {
        "label": "On-Time Rate",
        "unit": "",
        "fmt": ".1%",
        "green": 0.88, "amber": 0.80,
        "higher_is_better": True,
        "weight": 2.0,
        "desc": "Share of pickups within promised time window",
    },
    "pooling_rate": {
        "label": "Pooling Rate",
        "unit": "",
        "fmt": ".1%",
        "green": 0.60, "amber": 0.45,
        "higher_is_better": True,
        "weight": 1.5,
        "desc": "Share of trips shared with ≥1 other passenger",
    },
    "disruption_rate": {
        "label": "Disruption Rate",
        "unit": "/trip",
        "fmt": ".4f",
        "green": 0.012, "amber": 0.025,
        "higher_is_better": False,
        "weight": 1.0,
        "desc": "Unplanned service interruptions per trip",
    },
    "weighted_disruption_score": {
        "label": "Wtd. Disruption Score",
        "unit": "/trip",
        "fmt": ".4f",
        "green": 0.030, "amber": 0.060,
        "higher_is_better": False,
        "weight": 1.0,
        "desc": "Disruptions × avg severity per trip — severity-adjusted reliability",
    },
}


def kpi_color(kpi_key: str, value: float) -> str:
    m = KPI_META[kpi_key]
    if m["higher_is_better"]:
        if value >= m["green"]:   return "green"
        if value >= m["amber"]:   return "amber"
        return "red"
    else:
        if value <= m["green"]:   return "green"
        if value <= m["amber"]:   return "amber"
        return "red"


COLOR_HEX = {"green": "#2ECC71", "amber": "#F39C12", "red": "#E74C3C"}


def market_maturity_score(avg_kpis: dict) -> float:
    """Weighted average of normalized KPIs → 0–100 score."""
    total_w = sum(m["weight"] for m in KPI_META.values())
    score = 0.0
    for key, meta in KPI_META.items():
        v = avg_kpis.get(key, 0)
        if meta["higher_is_better"]:
            norm = min(1.0, v / meta["green"])
        else:
            norm = min(1.0, meta["green"] / max(v, 1e-9))
        score += norm * meta["weight"]
    return round(score / total_w * 100, 1)


# ─── 3. STYLING ──────────────────────────────────────────────────────────────

BADGE_CSS = """
<style>
.kpi-card {
    background: #1e1e2e;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    border-left: 4px solid {color};
}
.kpi-label { font-size: 0.78rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-value { font-size: 1.6rem; font-weight: 700; color: {color}; }
.kpi-desc  { font-size: 0.72rem; color: #666; margin-top: 2px; }
.score-box {
    text-align: center;
    padding: 20px;
    border-radius: 12px;
    background: #16213e;
    margin-bottom: 18px;
}
.score-label { font-size: 0.85rem; color: #aaa; }
.score-value { font-size: 3.5rem; font-weight: 900; }
</style>
"""

def kpi_card(label: str, value: str, color: str, desc: str) -> str:
    return f"""
<div class="kpi-card" style="border-left-color:{COLOR_HEX[color]}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value" style="color:{COLOR_HEX[color]}">{value}</div>
  <div class="kpi-desc">{desc}</div>
</div>"""


# ─── 4. MAIN APP ─────────────────────────────────────────────────────────────

raw = generate_data()
df = compute_kpis(raw)

st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/MOIA_logo.svg/320px-MOIA_logo.svg.png", width=120)
st.sidebar.title("AV Fleet Ops Dashboard")
view = st.sidebar.radio("View", ["Market Overview", "KPI Trends", "Shock Simulator"])
st.sidebar.markdown("---")
st.sidebar.caption("Simulated 30-day ridepooling data · Two operator markets")

markets = ["Hamburg", "Oslo"]


# ── VIEW 1: Market Overview ───────────────────────────────────────────────────
if view == "Market Overview":
    st.markdown(BADGE_CSS, unsafe_allow_html=True)
    st.title("📊 Market Overview")
    st.caption("30-day period averages · Color bands: 🟢 on-target  🟡 marginal  🔴 below threshold")

    cols = st.columns(2)
    for col, market in zip(cols, markets):
        mdf = df[df["market"] == market]
        avgs = {k: mdf[k].mean() for k in KPI_META}
        score = market_maturity_score(avgs)
        score_color = "#2ECC71" if score >= 75 else ("#F39C12" if score >= 55 else "#E74C3C")

        with col:
            st.subheader(f"🏙️ {market}")
            st.markdown(
                f'<div class="score-box"><div class="score-label">Market Maturity Score</div>'
                f'<div class="score-value" style="color:{score_color}">{score}</div>'
                f'<div class="score-label">/ 100</div></div>',
                unsafe_allow_html=True,
            )
            cards_html = ""
            for key, meta in KPI_META.items():
                val = avgs[key]
                color = kpi_color(key, val)
                fmt_val = format(val, meta["fmt"])
                if meta["unit"]:
                    fmt_val += f" {meta['unit']}"
                cards_html += kpi_card(meta["label"], fmt_val, color, meta["desc"])
            st.markdown(cards_html, unsafe_allow_html=True)


# ── VIEW 2: KPI Trends ────────────────────────────────────────────────────────
elif view == "KPI Trends":
    st.title("📈 KPI Trends")

    kpi_options = {v["label"]: k for k, v in KPI_META.items()}
    selected_label = st.selectbox("KPI", list(kpi_options.keys()))
    selected_kpi = kpi_options[selected_label]

    date_min, date_max = df["date"].min().date(), df["date"].max().date()
    date_range = st.slider(
        "Date range",
        min_value=date_min, max_value=date_max,
        value=(date_min, date_max),
        format="MMM D",
    )

    fdf = df[(df["date"].dt.date >= date_range[0]) & (df["date"].dt.date <= date_range[1])]

    fig = go.Figure()
    palette = {"Hamburg": "#4A9EFF", "Oslo": "#FF6B6B"}

    for market in markets:
        mdf = fdf[fdf["market"] == market].sort_values("date")
        vals = mdf[selected_kpi]

        # Rolling 7-day mean and std for anomaly detection
        roll_mean = vals.rolling(7, min_periods=2).mean()
        roll_std  = vals.rolling(7, min_periods=2).std().fillna(vals.std())
        anomaly_mask = (vals - roll_mean).abs() > 2 * roll_std

        color = palette[market]
        fig.add_trace(go.Scatter(
            x=mdf["date"], y=vals,
            name=market,
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
        # Anomaly dots
        anom_df = mdf[anomaly_mask]
        if not anom_df.empty:
            fig.add_trace(go.Scatter(
                x=anom_df["date"], y=anom_df[selected_kpi],
                name=f"{market} anomaly",
                mode="markers",
                marker=dict(color="#E74C3C", size=12, symbol="circle-open", line=dict(width=2)),
                showlegend=True,
            ))

    meta = KPI_META[selected_kpi]
    # Reference lines
    fig.add_hline(y=meta["green"], line_dash="dot", line_color="#2ECC71",
                  annotation_text="Target", annotation_position="bottom right")
    fig.add_hline(y=meta["amber"], line_dash="dot", line_color="#F39C12",
                  annotation_text="Marginal", annotation_position="bottom right")

    fig.update_layout(
        template="plotly_dark",
        title=f"{meta['label']} over Time",
        xaxis_title="Date",
        yaxis_title=meta["label"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=460,
        margin=dict(t=60),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        f"🔴 **Red circles** = anomaly days (KPI deviated > 2σ from rolling 7-day mean).  "
        f"**Definition:** {meta['desc']}"
    )

    # Summary table
    st.subheader("Period Summary")
    summary_rows = []
    for market in markets:
        mdf = fdf[fdf["market"] == market]
        v = mdf[selected_kpi].mean()
        color = kpi_color(selected_kpi, v)
        summary_rows.append({
            "Market": market,
            "Period Mean": format(v, meta["fmt"]),
            "Min": format(mdf[selected_kpi].min(), meta["fmt"]),
            "Max": format(mdf[selected_kpi].max(), meta["fmt"]),
            "Status": {"green": "✅ On-target", "amber": "⚠️ Marginal", "red": "❌ Below threshold"}[color],
        })
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)


# ── VIEW 3: Shock Simulator ───────────────────────────────────────────────────
elif view == "Shock Simulator":
    st.title("⚡ Operational Shock Simulator")
    st.markdown(
        "This simulates how a cold-weather event or vehicle maintenance pull affects "
        "service quality across markets. Operators can use this view to pre-define contingency "
        "thresholds and SLA buffers."
    )

    col_l, col_r = st.columns([1, 2])
    with col_l:
        weather = st.slider("🌨️ Weather disruption intensity (%)", 0, 100, 0, 5)
        fleet_red = st.slider("🔧 Fleet size reduction (%)", 0, 50, 0, 5)
        st.markdown("---")
        st.caption("**Degradation model (linear)**")
        st.caption("• +1.0% wait time per 1% weather intensity")
        st.caption("• −0.8% on-time rate per 1% weather intensity")
        st.caption("• +0.5% disruption rate per 1% weather intensity")
        st.caption("• −0.6% pooling rate per 1% fleet reduction")
        st.caption("• −0.7% pax/vehicle-hour per 1% fleet reduction")
        st.caption("• +0.4% deadhead ratio per 1% fleet reduction")

    with col_r:
        # Degradation multipliers
        def shocked(base_kpis: dict, w: float, f: float) -> dict:
            w_f, f_f = w / 100, f / 100
            return {
                "fleet_utilization_rate":      base_kpis["fleet_utilization_rate"] * (1 - f_f * 0.5),
                "passengers_per_vehicle_hour": base_kpis["passengers_per_vehicle_hour"] * (1 - f_f * 0.007),
                "deadhead_ratio":              base_kpis["deadhead_ratio"] * (1 + f_f * 0.004),
                "on_time_rate":                base_kpis["on_time_rate"] * (1 - w_f * 0.008),
                "pooling_rate":                base_kpis["pooling_rate"] * (1 - f_f * 0.006),
                "disruption_rate":             base_kpis["disruption_rate"] * (1 + w_f * 0.005),
                "weighted_disruption_score":   base_kpis["weighted_disruption_score"] * (1 + w_f * 0.005),
            }

        def delta_badge(delta_pct: float, higher_is_better: bool) -> str:
            arrow = "↑" if delta_pct > 0 else "↓"
            good  = (delta_pct > 0) == higher_is_better
            color = "#2ECC71" if abs(delta_pct) < 0.5 else ("#2ECC71" if good else "#E74C3C")
            return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.85rem">{arrow} {abs(delta_pct):.1f}%</span>'

        for market in markets:
            mdf = df[df["market"] == market]
            base_avgs = {k: mdf[k].mean() for k in KPI_META}
            shocked_avgs = shocked(base_avgs, weather, fleet_red)

            st.subheader(f"🏙️ {market}")
            header_cols = st.columns([2, 1, 1, 1])
            header_cols[0].markdown("**KPI**")
            header_cols[1].markdown("**Baseline**")
            header_cols[2].markdown("**Projected**")
            header_cols[3].markdown("**Δ**")

            for key, meta in KPI_META.items():
                base_v = base_avgs[key]
                shock_v = shocked_avgs[key]
                # Clamp projected values to sensible ranges
                if meta["higher_is_better"]:
                    shock_v = max(0, min(base_v, shock_v))
                else:
                    shock_v = max(base_v, shock_v)
                delta_pct = (shock_v - base_v) / base_v * 100

                row = st.columns([2, 1, 1, 1])
                row[0].markdown(f"<small>{meta['label']}</small>", unsafe_allow_html=True)
                row[1].markdown(f"`{format(base_v, meta['fmt'])}`")
                row[2].markdown(f"`{format(shock_v, meta['fmt'])}`")
                row[3].markdown(delta_badge(delta_pct, meta["higher_is_better"]), unsafe_allow_html=True)

            st.markdown("")

        if weather == 0 and fleet_red == 0:
            st.info("👆 Adjust the sliders to see projected KPI impact.")
        elif weather > 60 or fleet_red > 30:
            st.warning("⚠️ Severe operational shock detected. Consider activating contingency protocols.")
