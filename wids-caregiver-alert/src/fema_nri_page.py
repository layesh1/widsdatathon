"""
fema_nri_page.py
FEMA National Risk Index Integration — 49ers Intelligence Lab · WiDS 2025

Cross-references FEMA NRI wildfire risk scores with WiDS Social Vulnerability
data to identify counties facing compound risk: high NRI wildfire hazard AND
high social vulnerability.

FEMA NRI API docs: https://hazards.fema.gov/nri/api
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
from pathlib import Path

from ui_utils import page_header, section_header, render_card, fallback_card

# ── Paths ─────────────────────────────────────────────────────────────────────

_COUNTY_STATS_PATHS = [
    Path("county_fire_stats.csv"),
    Path("01_raw_data/processed/county_fire_stats.csv"),
    Path("../01_raw_data/processed/county_fire_stats.csv"),
]

# ── FEMA NRI API ──────────────────────────────────────────────────────────────

_NRI_BASE = "https://hazards.fema.gov/nri/rest/api/nri"
# State IDs for the most wildfire-affected states (FIPS codes as strings)
_TOP_FIRE_STATES = ["06", "41", "53", "16", "32", "04", "35", "08", "30", "49"]

_TIMEOUT = 8  # seconds


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_nri_state(state_fips: str) -> list[dict]:
    """Fetch FEMA NRI county data for one state. Returns list of dicts or []."""
    try:
        url = f"{_NRI_BASE}/county"
        params = {
            "returnFormat": "json",
            "stateId": state_fips,
            "fields": "NRI_ID,COUNTY,STATE,STATEABBRV,WLDF_RISKS,WLDF_RISKR,WLDF_EALB,RPL_THEMES,POPULATION",
            "limit": 200,
        }
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        # Some API versions nest under a key
        for key in ("items", "data", "features"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def _load_nri_top_states() -> pd.DataFrame | None:
    """Attempt to load NRI data for top wildfire states. Returns DataFrame or None."""
    rows: list[dict] = []
    for fips in _TOP_FIRE_STATES:
        rows.extend(_fetch_nri_state(fips))
        if len(rows) >= 300:
            break

    if not rows:
        return None

    df = pd.DataFrame(rows)

    # Normalise column names to upper-case
    df.columns = [c.upper() for c in df.columns]

    needed = ["WLDF_RISKS", "WLDF_RISKR", "COUNTY", "STATE"]
    if not all(c in df.columns for c in needed):
        return None

    # Numeric risk score
    df["WLDF_RISKS"] = pd.to_numeric(df["WLDF_RISKS"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def _load_county_stats() -> pd.DataFrame | None:
    for p in _COUNTY_STATS_PATHS:
        if p.exists():
            return pd.read_csv(p)
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _risk_rating_color(rating: str) -> str:
    rating = str(rating).strip().upper()
    return {
        "VERY HIGH": "#FF4B4B",
        "HIGH": "#d4a017",
        "MEDIUM": "#FFC107",
        "LOW": "#3fb950",
        "VERY LOW": "#1e3a5f",
    }.get(rating, "#8b949e")


_RISK_RANK_VAL = {
    "Very High": 5, "High": 4, "Medium": 3, "Low": 2, "Very Low": 1,
}


# ── Page ──────────────────────────────────────────────────────────────────────

def render_fema_nri_page() -> None:
    page_header(
        "FEMA National Risk Index — Wildfire Risk",
        "Cross-referencing federal risk scores with WiDS Social Vulnerability data",
    )

    # --- Load data -----------------------------------------------------------
    county_stats = _load_county_stats()

    with st.spinner("Contacting FEMA NRI API..."):
        nri_df = _load_nri_top_states()

    api_ok = nri_df is not None and not nri_df.empty

    # ── NRI Overview ---------------------------------------------------------
    section_header("What Is the FEMA National Risk Index?")

    with st.expander("About NRI — click to expand", expanded=False):
        st.markdown(
            """
**The FEMA National Risk Index (NRI)** is a dataset and interactive tool that
identifies which U.S. communities are most at risk from 18 natural hazards,
including wildfires.

Key metrics used in this page:

| Field | Meaning |
|-------|---------|
| **WLDF_RISKS** | Wildfire Risk Score — composite numeric score (0–100+) |
| **WLDF_RISKR** | Risk Rating — Very Low / Low / Medium / High / Very High |
| **WLDF_EALB** | Expected Annual Loss (Buildings) from wildfire — in USD |
| **RPL_THEMES** | CDC/ATSDR SVI percentile rank (0–1, higher = more vulnerable) |

**Expected Annual Loss (EAL)** is the estimated average economic loss per year
due to a hazard. For wildfire, FEMA estimates EAL based on historical fire
frequency, intensity, and the value of structures exposed.

A county with **Very High NRI wildfire risk AND high SVI** faces *compound
vulnerability*: fires arrive more often and more severely, AND the population
has fewer resources to prepare, respond, and recover.
            """
        )

    # ── KPIs -----------------------------------------------------------------
    if api_ok and county_stats is not None:
        merged = _merge_nri_svi(nri_df, county_stats)
        compound = merged[
            (merged["wldf_risk_rank"] >= 4) & (merged["svi_score"] >= 0.75)
        ]
        high_nri = merged[merged["wldf_risk_rank"] >= 4]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_card(
                "Counties in NRI Dataset",
                f"{len(merged):,}",
                "Matched to WiDS fire stats",
                color="#1e3a5f",
            )
        with c2:
            render_card(
                "High/Very-High Wildfire Risk",
                f"{len(high_nri):,}",
                "Per FEMA NRI rating",
                color="#d4a017",
            )
        with c3:
            render_card(
                "Compound-Vulnerability Counties",
                f"{len(compound):,}",
                "High NRI risk + SVI >= 0.75",
                color="#FF4B4B",
            )
        with c4:
            if len(compound) > 0 and "total_fires" in compound.columns:
                pct_fires = compound["total_fires"].sum() / merged["total_fires"].sum() * 100
                render_card(
                    "Fires in Compound Counties",
                    f"{pct_fires:.1f}%",
                    "Of all fires in matched counties",
                    color="#FF4B4B",
                )
            else:
                render_card(
                    "Compound Counties",
                    f"{len(compound):,}",
                    "Priority intervention targets",
                    color="#FF4B4B",
                )

        st.markdown("")
        _render_nri_charts(merged, compound)

    elif api_ok and county_stats is None:
        _render_nri_only(nri_df)
    else:
        _render_fallback(county_stats)


# ── Sub-renderers ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _merge_nri_svi(nri_df: pd.DataFrame, county_stats: pd.DataFrame) -> pd.DataFrame:
    """Merge NRI data with WiDS county stats on county name + state."""
    nri = nri_df.copy()

    # Standardise join keys
    nri["county_key"] = (
        nri["COUNTY"].str.strip().str.upper()
        + "|"
        + nri.get("STATEABBRV", nri.get("STATE", "")).str.strip().str.upper()
    )
    county_stats["county_key"] = (
        county_stats["county_name"].str.strip().str.upper()
        + "|"
        + county_stats["state"].str.strip().str.upper()
    )

    # Numeric risk score
    nri["WLDF_RISKS"] = pd.to_numeric(nri["WLDF_RISKS"], errors="coerce")

    # Ordinal rank from rating
    nri["wldf_risk_rank"] = (
        nri["WLDF_RISKR"]
        .str.strip()
        .str.title()
        .map(_RISK_RANK_VAL)
        .fillna(0)
        .astype(int)
    )

    merged = county_stats.merge(
        nri[["county_key", "WLDF_RISKS", "WLDF_RISKR", "wldf_risk_rank"]].rename(
            columns={"WLDF_RISKS": "wldf_score", "WLDF_RISKR": "wldf_rating"}
        ),
        on="county_key",
        how="inner",
    )
    return merged


def _render_nri_charts(merged: pd.DataFrame, compound: pd.DataFrame) -> None:
    # ── Scatter: NRI score vs SVI ─────────────────────────────────────────
    section_header("SVI vs NRI Wildfire Risk Score")
    st.caption(
        "Each dot = one county. Top-right quadrant = compound vulnerability: "
        "high wildfire hazard AND high social vulnerability."
    )

    plot_df = merged.dropna(subset=["wldf_score", "svi_score"]).copy()
    plot_df["label"] = plot_df["county_name"] + ", " + plot_df["state"]
    plot_df["is_compound"] = (
        (plot_df["wldf_risk_rank"] >= 4) & (plot_df["svi_score"] >= 0.75)
    )
    plot_df["marker_color"] = plot_df["wldf_rating"].str.strip().str.upper().map(
        {
            "VERY HIGH": "#FF4B4B",
            "HIGH": "#d4a017",
            "MEDIUM": "#FFC107",
            "LOW": "#3fb950",
            "VERY LOW": "#4a90d9",
        }
    ).fillna("#8b949e")

    fig_scatter = go.Figure()

    for rating, color in [
        ("Very High", "#FF4B4B"),
        ("High", "#d4a017"),
        ("Medium", "#FFC107"),
        ("Low", "#3fb950"),
        ("Very Low", "#4a90d9"),
    ]:
        sub = plot_df[plot_df["wldf_rating"].str.strip().str.title() == rating]
        if sub.empty:
            continue
        fig_scatter.add_trace(
            go.Scatter(
                x=sub["wldf_score"],
                y=sub["svi_score"],
                mode="markers",
                name=f"NRI: {rating}",
                marker=dict(color=color, size=7, opacity=0.75),
                customdata=sub[["label", "total_fires", "pct_silent"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "NRI Score: %{x:.1f}<br>"
                    "SVI: %{y:.3f}<br>"
                    "Total Fires: %{customdata[1]:,}<br>"
                    "Silent Rate: %{customdata[2]:.1%}<extra></extra>"
                ),
            )
        )

    # Quadrant lines
    svi_thresh, nri_thresh = 0.75, plot_df["wldf_score"].quantile(0.75)
    fig_scatter.add_hline(
        y=svi_thresh,
        line_dash="dash",
        line_color="#8b949e",
        annotation_text="SVI >= 0.75",
        annotation_position="right",
        annotation_font_color="#8b949e",
    )
    fig_scatter.add_vline(
        x=nri_thresh,
        line_dash="dash",
        line_color="#8b949e",
        annotation_text="NRI 75th pctile",
        annotation_position="top",
        annotation_font_color="#8b949e",
    )

    # Label compound counties
    for _, row in compound.head(10).iterrows():
        if pd.notna(row.get("wldf_score")) and pd.notna(row.get("svi_score")):
            fig_scatter.add_annotation(
                x=row["wldf_score"],
                y=row["svi_score"],
                text=row["county_name"],
                showarrow=True,
                arrowhead=2,
                arrowcolor="#FF4B4B",
                font=dict(size=9, color="#FF4B4B"),
                ax=20,
                ay=-20,
            )

    fig_scatter.update_layout(
        template="plotly_dark",
        title="SVI Score vs FEMA NRI Wildfire Risk Score",
        xaxis_title="FEMA NRI Wildfire Risk Score",
        yaxis_title="CDC/ATSDR SVI Score",
        height=500,
        margin=dict(l=60, r=40, t=60, b=50),
        legend=dict(orientation="h", y=-0.15, x=0),
    )

    # Quadrant annotation box
    fig_scatter.add_annotation(
        x=plot_df["wldf_score"].max() * 0.92,
        y=0.97,
        text="COMPOUND<br>VULNERABILITY",
        showarrow=False,
        font=dict(size=11, color="#FF4B4B"),
        bgcolor="rgba(255,75,75,0.12)",
        bordercolor="#FF4B4B",
        borderwidth=1,
        borderpad=6,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Top compound-vulnerability counties table ─────────────────────────
    section_header("Top Compound-Vulnerability Counties")
    st.caption(
        "Counties with FEMA NRI rating High/Very High AND SVI >= 0.75. "
        "These are the priority intervention targets for proactive caregiver alerts."
    )

    if compound.empty:
        fallback_card(
            "No counties matched both criteria in the current NRI + WiDS merged dataset."
        )
        return

    display_cols = {
        "county_name": "County",
        "state": "State",
        "wldf_rating": "NRI Rating",
        "wldf_score": "NRI Score",
        "svi_score": "SVI Score",
        "total_fires": "Total Fires",
        "pct_silent": "Silent Rate",
        "pct_evac": "Evac Rate",
    }
    avail = [c for c in display_cols if c in compound.columns]
    tbl = compound[avail].rename(columns=display_cols).copy()
    if "Silent Rate" in tbl.columns:
        tbl["Silent Rate"] = (tbl["Silent Rate"] * 100).round(1).astype(str) + "%"
    if "Evac Rate" in tbl.columns:
        tbl["Evac Rate"] = (tbl["Evac Rate"] * 100).round(1).astype(str) + "%"
    if "NRI Score" in tbl.columns:
        tbl["NRI Score"] = tbl["NRI Score"].round(1)
    if "SVI Score" in tbl.columns:
        tbl["SVI Score"] = tbl["SVI Score"].round(3)

    tbl = tbl.sort_values("NRI Score", ascending=False).head(30)
    st.dataframe(tbl, use_container_width=True, hide_index=True)

    # ── Bar: top 15 compound counties by NRI score ────────────────────────
    top15 = tbl.head(15).copy()
    if "County" in top15.columns and "NRI Score" in top15.columns:
        top15["Label"] = top15["County"] + ", " + top15.get("State", "")
        fig_bar = go.Figure(
            go.Bar(
                x=top15["NRI Score"],
                y=top15["Label"],
                orientation="h",
                marker_color="#FF4B4B",
                text=top15["NRI Score"].astype(str),
                textposition="outside",
            )
        )
        fig_bar.update_layout(
            template="plotly_dark",
            title="Top 15 Compound-Vulnerability Counties by NRI Wildfire Score",
            xaxis_title="FEMA NRI Wildfire Risk Score",
            yaxis=dict(autorange="reversed"),
            height=420,
            margin=dict(l=180, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_bar, use_container_width=True)


def _render_nri_only(nri_df: pd.DataFrame) -> None:
    """Render NRI data without WiDS merge (county_fire_stats.csv unavailable)."""
    section_header("FEMA NRI Wildfire Risk — Top Counties")
    st.info(
        "county_fire_stats.csv not found; showing FEMA NRI data without WiDS merge.",
        icon=None,
    )

    df = nri_df.copy()
    df["WLDF_RISKS"] = pd.to_numeric(df.get("WLDF_RISKS", pd.Series()), errors="coerce")
    top = df.dropna(subset=["WLDF_RISKS"]).nlargest(20, "WLDF_RISKS")
    st.dataframe(top[["COUNTY", "STATE", "WLDF_RISKR", "WLDF_RISKS"]].reset_index(drop=True))


def _render_fallback(county_stats: pd.DataFrame | None) -> None:
    """Fallback when FEMA NRI API is unavailable."""
    section_header("FEMA NRI API Unavailable — WiDS-Based Risk Proxy")

    st.warning(
        "The FEMA National Risk Index API did not respond within the timeout window. "
        "This is common when running offline or when FEMA servers are under load. "
        "The analysis below uses WiDS dataset proxy metrics as a stand-in.",
    )

    with st.expander("What would FEMA NRI add?"):
        st.markdown(
            """
When the API is available, this page cross-references:

- **WLDF_RISKR** (Very Low → Very High) — FEMA's wildfire risk rating per county
- **WLDF_EALB** — Expected Annual Loss (Buildings) from wildfire, in USD
- **WLDF_RISKS** — Composite numeric score combining frequency, intensity, and exposure

These metrics come from FEMA's hazard-modeling pipeline, which incorporates:
historical fire perimeters, fuel mapping, weather climatology, and structure exposure.

The *compound vulnerability* analysis (NRI × SVI) identifies counties where federal
hazard risk AND community vulnerability both rank high — the highest-priority targets
for proactive caregiver alert systems.
            """
        )

    if county_stats is None:
        st.error("county_fire_stats.csv also unavailable. No data to display.")
        return

    # Proxy: use pct_silent + svi_score as stand-in for NRI
    section_header("Proxy Compound Vulnerability — WiDS Dataset")
    st.caption(
        "Using silent fire rate (proxy for under-reporting risk) and SVI score. "
        "Counties in the top-right = high silent rate AND high vulnerability."
    )

    df = county_stats.dropna(subset=["svi_score", "pct_silent"]).copy()
    df["label"] = df["county_name"] + ", " + df["state"]
    df["compound"] = (df["svi_score"] >= 0.75) & (df["pct_silent"] >= 0.75)

    fig = go.Figure()
    for compound, color, name in [
        (True, "#FF4B4B", "Compound risk (high SVI + high silent rate)"),
        (False, "#4a90d9", "Other counties"),
    ]:
        sub = df[df["compound"] == compound]
        fig.add_trace(
            go.Scatter(
                x=sub["pct_silent"],
                y=sub["svi_score"],
                mode="markers",
                name=name,
                marker=dict(color=color, size=7, opacity=0.7),
                customdata=sub[["label", "total_fires"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Silent Rate: %{x:.1%}<br>"
                    "SVI: %{y:.3f}<br>"
                    "Total Fires: %{customdata[1]:,}<extra></extra>"
                ),
            )
        )

    fig.add_hline(y=0.75, line_dash="dash", line_color="#8b949e", annotation_text="SVI 0.75")
    fig.add_vline(x=0.75, line_dash="dash", line_color="#8b949e", annotation_text="75% silent")

    fig.update_layout(
        template="plotly_dark",
        title="Silent Fire Rate vs SVI Score (NRI Proxy)",
        xaxis_title="Silent Fire Rate",
        yaxis_title="SVI Score",
        height=460,
        margin=dict(l=60, r=40, t=60, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Top compound proxy table
    compound_df = df[df["compound"]].sort_values("svi_score", ascending=False)
    n_compound = len(compound_df)
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(
            "Counties Analyzed",
            f"{len(df):,}",
            "From county_fire_stats.csv",
            color="#1e3a5f",
        )
    with c2:
        render_card(
            "Compound-Risk Counties (Proxy)",
            f"{n_compound:,}",
            "Silent >= 75% AND SVI >= 0.75",
            color="#FF4B4B",
        )
    with c3:
        if n_compound > 0:
            pct = compound_df["total_fires"].sum() / df["total_fires"].sum() * 100
            render_card(
                "Fires in Compound Counties",
                f"{pct:.1f}%",
                "Of all fires in dataset",
                color="#d4a017",
            )

    if not compound_df.empty:
        st.markdown("")
        section_header("Top Proxy Compound-Vulnerability Counties")
        show = compound_df[
            [c for c in ["county_name", "state", "svi_score", "pct_silent", "total_fires", "pct_evac"]
             if c in compound_df.columns]
        ].head(20).copy()
        if "pct_silent" in show:
            show["pct_silent"] = (show["pct_silent"] * 100).round(1).astype(str) + "%"
        if "pct_evac" in show:
            show["pct_evac"] = (show["pct_evac"] * 100).round(1).astype(str) + "%"
        show = show.rename(
            columns={
                "county_name": "County", "state": "State",
                "svi_score": "SVI Score", "pct_silent": "Silent Rate",
                "total_fires": "Total Fires", "pct_evac": "Evac Rate",
            }
        )
        st.dataframe(show, use_container_width=True, hide_index=True)

    st.caption(
        "Data source: county_fire_stats.csv + WiDS fire_events_with_svi_and_delays.csv. "
        "FEMA NRI data from hazards.fema.gov/nri (API temporarily unavailable). "
        "When API is accessible, this page shows official NRI wildfire risk scores."
    )
