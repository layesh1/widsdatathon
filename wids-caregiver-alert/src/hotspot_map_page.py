"""
hotspot_map_page.py
Getis-Ord Gi* Hotspot Cluster Map — 49ers Intelligence Lab · WiDS 2025

Identifies statistically significant clusters of high-risk, under-served counties
using the Getis-Ord Gi* spatial statistic on SVI × silent-fire-rate.

Hot spots = high-SVI counties with high silent fire rates, surrounded by similar neighbors.
These are the locations where the caregiver alert system is most urgently needed.

Pre-computed from fire_events_with_svi_and_delays.csv (543 counties with ≥10 fires).
Spatial weights: inverse distance, threshold = 2.25 degrees (~250 km).
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path


_DATA_PATHS = [
    Path("01_raw_data/processed/county_gi_star.csv"),
    Path("../01_raw_data/processed/county_gi_star.csv"),
    Path("county_gi_star.csv"),
]

_CLUSTER_COLORS = {
    "Hot Spot (90%+)":    "#FF4444",
    "Hot Spot (80%+)":    "#FF9800",
    "Not Significant":    "#555577",
    "Cold Spot (80%+)":   "#4a90d9",
    "Cold Spot (90%+)":   "#1a5fa8",
}


@st.cache_data(show_spinner=False)
def load_gi_data():
    for p in _DATA_PATHS:
        if p.exists():
            try:
                df = pd.read_csv(p)
                df = df.dropna(subset=["lat", "lon", "gi_star"])
                df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
                df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
                df = df.dropna(subset=["lat", "lon"])
                df = df[df["lat"].between(24, 50) & df["lon"].between(-125, -65)]
                return df
            except Exception:
                pass
    return _build_static_df()


def _classify(z):
    if z >= 1.645:  return "Hot Spot (90%+)"
    if z >= 1.282:  return "Hot Spot (80%+)"
    if z <= -1.645: return "Cold Spot (90%+)"
    if z <= -1.282: return "Cold Spot (80%+)"
    return "Not Significant"


def _build_static_df():
    """Pre-baked top results if CSV not available."""
    rows = [
        {"county_name":"Trinity County",   "state":"California","gi_star":1.51,"svi_score":0.72,"pct_silent":0.88,"total_fires":298,  "lat":40.6,"lon":-123.1,"risk_attr":0.634},
        {"county_name":"Mohave County",    "state":"Arizona",   "gi_star":1.49,"svi_score":0.85,"pct_silent":0.72,"total_fires":374,  "lat":35.0,"lon":-114.1,"risk_attr":0.612},
        {"county_name":"La Paz County",    "state":"Arizona",   "gi_star":1.45,"svi_score":0.92,"pct_silent":0.69,"total_fires":110,  "lat":33.7,"lon":-114.0,"risk_attr":0.635},
        {"county_name":"Humboldt County",  "state":"California","gi_star":1.43,"svi_score":0.83,"pct_silent":0.87,"total_fires":230,  "lat":40.7,"lon":-123.9,"risk_attr":0.722},
        {"county_name":"Jackson County",   "state":"Oregon",    "gi_star":1.42,"svi_score":0.70,"pct_silent":0.87,"total_fires":597,  "lat":42.4,"lon":-122.8,"risk_attr":0.609},
        {"county_name":"Siskiyou County",  "state":"California","gi_star":1.39,"svi_score":0.79,"pct_silent":0.82,"total_fires":467,  "lat":41.6,"lon":-122.5,"risk_attr":0.648},
        {"county_name":"Klamath County",   "state":"Oregon",    "gi_star":1.39,"svi_score":0.84,"pct_silent":0.84,"total_fires":600,  "lat":42.7,"lon":-121.6,"risk_attr":0.706},
        {"county_name":"Del Norte County", "state":"California","gi_star":1.37,"svi_score":0.90,"pct_silent":0.80,"total_fires":107,  "lat":41.7,"lon":-123.9,"risk_attr":0.721},
        {"county_name":"Shasta County",    "state":"California","gi_star":1.35,"svi_score":0.76,"pct_silent":0.82,"total_fires":686,  "lat":40.6,"lon":-122.1,"risk_attr":0.623},
        {"county_name":"Curry County",     "state":"Oregon",    "gi_star":1.33,"svi_score":0.61,"pct_silent":0.81,"total_fires":54,   "lat":42.4,"lon":-124.2,"risk_attr":0.494},
    ]
    df = pd.DataFrame(rows)
    df["cluster"] = df["gi_star"].apply(_classify)
    return df


def render_hotspot_map_page():
    st.title("Getis-Ord Gi* Hotspot Map")
    st.caption(
        "Spatial cluster analysis of evacuation delay risk  ·  WiDS 2021–2025  ·  "
        "543 counties with ≥10 fire events"
    )

    st.markdown("""
> **Method:** Getis-Ord Gi* statistic measures whether high-risk counties are spatially
> clustered. A county with Gi* > 1.645 (90% CI) is a **statistically significant hot spot** —
> surrounded by similar high-risk neighbors. These clusters represent geographic zones
> where the caregiver alert system would have the highest impact per deployment.
    """)

    df = load_gi_data()

    if "cluster" not in df.columns:
        df["cluster"] = df["gi_star"].apply(_classify)

    # Remap cluster labels for display
    df["cluster_display"] = df["gi_star"].apply(_classify)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    hot = df[df["gi_star"] >= 1.282]
    cold = df[df["gi_star"] <= -1.282]
    sig90 = df[df["gi_star"].abs() >= 1.645]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Counties Analyzed", f"{len(df):,}",
              help="Counties with ≥10 fires and valid lat/lon")
    k2.metric("Hot Spot Counties (80%+ CI)", f"{len(hot):,}",
              delta="High-SVI + high silent-fire clusters",
              delta_color="inverse")
    k3.metric("Cold Spot Counties", f"{len(cold):,}",
              delta="Low-risk, well-served areas",
              delta_color="normal")
    k4.metric("Statistically Significant (90%)", f"{len(sig90):,}",
              delta="Robust spatial clusters",
              delta_color="off")

    # ── Map ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Gi* Cluster Map — Where Caregiver Alerts Are Needed Most")

    tier_order = ["Hot Spot (90%+)", "Hot Spot (80%+)", "Not Significant", "Cold Spot (80%+)", "Cold Spot (90%+)"]
    fig = go.Figure()

    for tier in tier_order:
        sub = df[df["cluster_display"] == tier]
        if sub.empty:
            continue
        color = _CLUSTER_COLORS[tier]
        abs_z = sub["gi_star"].abs().clip(upper=3)
        dot_size = (abs_z * 4 + 6).clip(lower=5, upper=18)

        fig.add_trace(go.Scattergeo(
            lat=sub["lat"],
            lon=sub["lon"],
            mode="markers",
            name=tier,
            marker=dict(
                size=dot_size,
                color=color,
                opacity=0.8 if "Hot Spot" in tier or "Cold Spot" in tier else 0.3,
                line=dict(width=0.4, color="#111"),
            ),
            text=sub["county_name"] + ", " + sub["state"].fillna(""),
            customdata=sub[["gi_star", "svi_score", "pct_silent", "total_fires"]].round(3).values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Gi* z-score: %{customdata[0]:.2f}<br>"
                "SVI Score: %{customdata[1]:.2f}<br>"
                "% Silent Fires: %{customdata[2]:.1%}<br>"
                "Total Fires: %{customdata[3]:,}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        template="plotly_dark",
        geo=dict(
            scope="usa",
            showland=True,
            showlakes=True,
            showsubunits=True,
            landcolor="#1a1a2e",
            lakecolor="#0d1117",
            subunitcolor="#333",
            projection=dict(type="albers usa"),
        ),
        legend=dict(
            title="Cluster Type",
            orientation="h",
            y=-0.05,
            x=0.5,
            xanchor="center",
        ),
        height=520,
        margin=dict(l=0, r=0, t=20, b=20),
        title="Getis-Ord Gi* Spatial Clusters of Wildfire Alert Inequity",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Red = statistically significant hot spot (SVI × silent fire rate cluster). "
        "Dot size = Gi* z-score magnitude. "
        "Grey = not statistically significant. Blue = cold spot (well-served)."
    )

    # ── Gi* score chart ───────────────────────────────────────────────────────
    st.divider()
    col_bar, col_explain = st.columns([2, 1])

    with col_bar:
        st.subheader("Top Hot Spot Counties by Gi* Score")
        top_hot = df.nlargest(15, "gi_star")[
            ["county_name", "state", "gi_star", "svi_score", "pct_silent", "total_fires"]
        ].copy()
        top_hot["gi_star"] = top_hot["gi_star"].round(3)
        top_hot["pct_silent"] = (top_hot["pct_silent"] * 100).round(1).astype(str) + "%"
        top_hot["svi_score"] = top_hot["svi_score"].round(3)

        fig_bar = go.Figure(go.Bar(
            x=top_hot["gi_star"],
            y=top_hot["county_name"] + ", " + top_hot["state"],
            orientation="h",
            marker_color="#FF4444",
            text=top_hot["gi_star"].astype(str),
            textposition="outside",
        ))
        fig_bar.add_vline(x=1.645, line_dash="dash", line_color="#FFC107",
                          annotation_text="90% CI threshold (1.645)",
                          annotation_position="top")
        fig_bar.add_vline(x=1.282, line_dash="dot", line_color="#FF9800",
                          annotation_text="80% CI (1.282)",
                          annotation_position="bottom")
        fig_bar.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=180, r=60, t=20, b=40),
            xaxis_title="Gi* z-score",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_explain:
        st.subheader("How to Read Gi*")
        st.markdown("""
**Gi* z-score** measures whether a county is part of a spatial cluster of similar high-risk values.

| z-score | Interpretation |
|---------|----------------|
| ≥ 1.96  | Hot spot, 95% CI |
| ≥ 1.645 | Hot spot, 90% CI |
| ≥ 1.282 | Hot spot, 80% CI |
| -1.28 to +1.28 | Not significant |
| ≤ -1.645 | Cold spot, 90% CI |

**Input variable:** SVI score × % silent fires
(captures both vulnerability and notification gap simultaneously)

**Threshold:** Counties within ~250 km are considered neighbors.

**Interpretation:** Hot spots are places where vulnerable, under-notified counties
cluster geographically — indicating a regional system failure, not just individual county risk.
        """)

    # ── Hot spot table ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Hot Spot County Details")
    _base_cols = ["county_name", "state", "gi_star", "svi_score", "pct_silent", "total_fires"]
    if "extreme_fires" in df.columns:
        _base_cols.append("extreme_fires")
    hot_display = df[df["gi_star"] >= 1.282].sort_values("gi_star", ascending=False)[_base_cols].copy()
    if "extreme_fires" not in hot_display.columns:
        hot_display["extreme_fires"] = "—"
    hot_display = hot_display.rename(columns={
        "county_name": "County", "state": "State",
        "gi_star": "Gi* Score", "svi_score": "SVI",
        "pct_silent": "% Silent", "total_fires": "Total Fires",
        "extreme_fires": "Extreme Fires",
    })
    hot_display["% Silent"] = (hot_display["% Silent"] * 100).round(1).astype(str) + "%"
    hot_display["Gi* Score"] = hot_display["Gi* Score"].round(3)
    hot_display["SVI"] = hot_display["SVI"].round(3)
    st.dataframe(hot_display.reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("""
**These counties represent the highest-priority deployment zones** for the caregiver alert system:
- High SVI (vulnerable populations)
- High silent-fire rate (no public notification)
- Spatially clustered (regional system failure, not isolated incidents)
    """)

    st.caption(
        "Gi* computed using inverse-distance spatial weights, threshold 250 km (~2.25°). "
        "Input: SVI × pct_silent per county. 543 counties with ≥10 fires analyzed. "
        "Source: fire_events_with_svi_and_delays.csv · WiDS 2021–2025."
    )
