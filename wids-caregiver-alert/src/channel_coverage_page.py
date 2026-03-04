"""
channel_coverage_page.py
Alert Channel Coverage Map — 49ers Intelligence Lab · WiDS 2025

Shows which counties have multi-channel incident coverage vs single-channel dependency.
Data source: geo_events_externalgeoevent.channel column joined to county via geo_event_id.

Key finding: 732 counties have incident channel data.
Median = 2 channels; max = 23 channels (Lincoln, WA).
Single-channel counties are most at risk if that channel goes offline.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path


# ── Pre-computed county-channel data (from geo_events_externalgeoevent.csv) ──
# Computed by joining externalgeoevent.channel → fire_events via geo_event_id
# 732 counties with at least one incident channel, WiDS 2021–2025

_PROCESSED = Path(__file__).parent / "../../01_raw_data/processed"
_DATA_PATHS = [
    _PROCESSED / "county_channel_coverage.csv",
    Path("01_raw_data/processed/county_channel_coverage.csv"),
    Path("../01_raw_data/processed/county_channel_coverage.csv"),
    Path("county_channel_coverage.csv"),
]


@st.cache_data(show_spinner=False)
def load_channel_data():
    for p in _DATA_PATHS:
        if p.exists():
            try:
                df = pd.read_csv(p)
                df = df.dropna(subset=["lat", "lon"])
                df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
                df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
                df = df.dropna(subset=["lat", "lon"])
                df = df[df["lat"].between(24, 50) & df["lon"].between(-125, -65)]
                return df
            except Exception:
                pass
    return None


def _coverage_tier(n):
    if n >= 5:
        return "Multi-channel (5+)"
    if n >= 3:
        return "Good coverage (3–4)"
    if n == 2:
        return "Dual-channel (2)"
    return "Single-channel (1)"


def render_channel_coverage_page():
    st.title("Alert Channel Coverage Map")
    st.caption(
        "County-level incident notification channel coverage  ·  WiDS 2021–2025  ·  "
        "Source: geo_events_externalgeoevent.channel"
    )

    st.markdown("""
> **Research Question:** Which counties rely on a single alert channel?
> If that channel goes offline, they have **no redundancy** for wildfire notifications.
> Counties with multi-channel coverage (3+) are significantly more resilient.
    """)

    df = load_channel_data()

    if df is None or df.empty:
        st.warning(
            "county_channel_coverage.csv not found. "
            "Run the preprocessing script to regenerate it from geo_events_externalgeoevent.csv."
        )
        _render_static_summary()
        return

    df["coverage_tier"] = df["n_channels"].apply(_coverage_tier)
    df["svi_score"] = pd.to_numeric(df.get("svi_score", pd.Series()), errors="coerce")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Counties with Channel Data", f"{len(df):,}",
              help="Counties with at least one incident alert channel in WiDS data")
    single = (df["n_channels"] == 1).sum()
    k2.metric("Single-Channel Counties", f"{single:,}",
              delta=f"{single/len(df)*100:.0f}% — no redundancy",
              delta_color="inverse")
    multi = (df["n_channels"] >= 3).sum()
    k3.metric("Multi-Channel Counties (3+)", f"{multi:,}",
              delta=f"{multi/len(df)*100:.0f}% — resilient",
              delta_color="normal")
    k4.metric("Max Channels (Lincoln, WA)", "23",
              help="Lincoln County, WA has the most diverse channel coverage in the dataset")

    # ── Map ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("County-Level Channel Coverage")

    color_map = {
        "Single-channel (1)":     "#FF4444",
        "Dual-channel (2)":       "#FF9800",
        "Good coverage (3–4)":    "#FFC107",
        "Multi-channel (5+)":     "#4ade80",
    }
    tier_order = ["Single-channel (1)", "Dual-channel (2)", "Good coverage (3–4)", "Multi-channel (5+)"]

    fig = go.Figure()
    for tier in tier_order:
        sub = df[df["coverage_tier"] == tier]
        if sub.empty:
            continue
        fig.add_trace(go.Scattergeo(
            lat=sub["lat"],
            lon=sub["lon"],
            mode="markers",
            name=tier,
            marker=dict(
                size=sub["n_channels"].clip(upper=12) + 4,
                color=color_map[tier],
                opacity=0.75,
                line=dict(width=0.3, color="#111"),
            ),
            text=sub["county_name"] + ", " + sub["state"].fillna(""),
            customdata=sub[["n_channels", "n_fires_with_channel"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Channels: %{customdata[0]}<br>"
                "Fires with channel data: %{customdata[1]:,}<br>"
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
            title="Coverage Tier",
            orientation="h",
            y=-0.05,
            x=0.5,
            xanchor="center",
        ),
        height=500,
        margin=dict(l=0, r=0, t=20, b=20),
        title="Wildfire Alert Channel Coverage by County",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Dot size = number of unique incident channels. Red = single-channel (no redundancy). "
        "Green = multi-channel (5+ channels)."
    )

    # ── Distribution chart ────────────────────────────────────────────────────
    st.divider()
    col_hist, col_text = st.columns([1, 1])

    with col_hist:
        st.subheader("Channel Count Distribution")
        hist_data = df["n_channels"].value_counts().sort_index().reset_index()
        hist_data.columns = ["n_channels", "county_count"]
        hist_data["color"] = hist_data["n_channels"].apply(
            lambda n: "#FF4444" if n == 1 else ("#FF9800" if n == 2 else ("#FFC107" if n <= 4 else "#4ade80"))
        )
        fig_hist = go.Figure(go.Bar(
            x=hist_data["n_channels"],
            y=hist_data["county_count"],
            marker_color=hist_data["color"],
            text=hist_data["county_count"],
            textposition="outside",
        ))
        fig_hist.update_layout(
            template="plotly_dark",
            xaxis_title="Number of Alert Channels",
            yaxis_title="Counties",
            height=300,
            margin=dict(l=20, r=20, t=20, b=40),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_text:
        st.subheader("What Channel Coverage Means")
        st.markdown(f"""
**Alert channels** are the WatchDuty / incident command radio channels that carry
fire incident notifications. Each channel (`incidents-ca_s4`, `incidents-wa_northwest`, etc.)
represents a regional monitoring system.

**Single-channel counties** ({single:,} total, {single/len(df)*100:.0f}%) have **no redundancy**.
If the regional monitoring system goes offline during a fire, residents receive no notification.

**For vulnerable populations**, this matters most at night — when fires peak (8pm–midnight)
and when human monitoring is thinnest.

**The caregiver alert system bypasses channel dependency** by monitoring raw signal data
directly, independent of which channel is broadcasting the incident.
        """)

    # ── Top counties table ────────────────────────────────────────────────────
    st.divider()
    col_top, col_bottom = st.columns(2)

    with col_top:
        st.subheader("Most-Covered Counties (Top 15)")
        top = df.nlargest(15, "n_channels")[
            ["county_name", "state", "n_channels", "n_fires_with_channel"]
        ].rename(columns={
            "county_name": "County", "state": "State",
            "n_channels": "Alert Channels", "n_fires_with_channel": "Fires w/ Channel"
        })
        st.dataframe(top, use_container_width=True, hide_index=True)

    with col_bottom:
        st.subheader("Single-Channel High-SVI Counties (Most Vulnerable)")
        if "svi_score" in df.columns:
            risk = df[(df["n_channels"] == 1) & (df["svi_score"] >= 0.7)].nlargest(15, "svi_score")[
                ["county_name", "state", "svi_score", "n_fires_with_channel"]
            ].rename(columns={
                "county_name": "County", "state": "State",
                "svi_score": "SVI Score", "n_fires_with_channel": "Fires"
            })
            st.dataframe(risk.round(3), use_container_width=True, hide_index=True)
            st.caption("Single-channel + high SVI = highest equity risk")
        else:
            single_df = df[df["n_channels"] == 1].nlargest(15, "n_fires_with_channel")[
                ["county_name", "state", "n_channels", "n_fires_with_channel"]
            ].rename(columns={
                "county_name": "County", "state": "State",
                "n_channels": "Channels", "n_fires_with_channel": "Fires"
            })
            st.dataframe(single_df, use_container_width=True, hide_index=True)

    st.caption(
        "Data: geo_events_externalgeoevent.channel joined to fire_events by geo_event_id. "
        "732 counties with incident channel data across WiDS 2021–2025 dataset."
    )


def _render_static_summary():
    """Fallback when CSV not available — show pre-computed stats."""
    st.info("Showing pre-computed summary statistics.")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Counties with Channel Data", "732")
    k2.metric("Single-Channel Counties", "355", delta="48% — no redundancy", delta_color="inverse")
    k3.metric("Multi-Channel (5+)", "40", delta="5% — resilient", delta_color="normal")
    k4.metric("Max Channels", "23", delta="Lincoln County, WA")

    st.markdown("""
**Top counties by channel count** (from WiDS 2021–2025 analysis):

| County | State | Channels |
|--------|-------|----------|
| Lincoln County | WA | 23 |
| Washington County | UT | 20 |
| Jackson County | OR | 17 |
| Jefferson County | OR | 17 |
| Lake County | MT | 14 |
| Douglas County | OR | 13 |
| Grant County | OR | 12 |
| Custer County | ID | 11 |
| Butte County | ID | 10 |
| Clark County | WA | 10 |

**355 counties (48%) have only 1 channel** — no redundancy if that channel fails.
    """)
