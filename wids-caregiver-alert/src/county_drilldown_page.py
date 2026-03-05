"""
county_drilldown_page.py
County-Level Drill-Down — 49ers Intelligence Lab · WiDS 2025

Click a county → see its SVI tier, fire history, active alert channels,
USFA department count, and caregiver coverage estimate.

Conference presentation priority — shows the localized equity story.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path


_PROCESSED = Path(__file__).parent / "../../01_raw_data/processed"
_FIRE_STATS_PATHS = [
    _PROCESSED / "county_fire_stats.csv",
    Path("01_raw_data/processed/county_fire_stats.csv"),
    Path("../01_raw_data/processed/county_fire_stats.csv"),
    Path("county_fire_stats.csv"),
]
_CHANNEL_PATHS = [
    _PROCESSED / "county_channel_coverage.csv",
    Path("01_raw_data/processed/county_channel_coverage.csv"),
    Path("../01_raw_data/processed/county_channel_coverage.csv"),
    Path("county_channel_coverage.csv"),
]
_GI_PATHS = [
    _PROCESSED / "county_gi_star.csv",
    Path("01_raw_data/processed/county_gi_star.csv"),
    Path("../01_raw_data/processed/county_gi_star.csv"),
    Path("county_gi_star.csv"),
]
_USFA_PATHS = [
    Path("usfa-registry-national.csv"),
    Path("src/usfa-registry-national.csv"),
    Path("01_raw_data/usfa-registry-national.csv"),
]


@st.cache_data(show_spinner=False)
def load_all_county_data():
    fire_df = ch_df = gi_df = usfa_df = None

    for p in _FIRE_STATS_PATHS:
        if p.exists():
            try:
                fire_df = pd.read_csv(p, low_memory=False)
                break
            except Exception:
                pass

    for p in _CHANNEL_PATHS:
        if p.exists():
            try:
                ch_df = pd.read_csv(p, low_memory=False)
                break
            except Exception:
                pass

    for p in _GI_PATHS:
        if p.exists():
            try:
                gi_df = pd.read_csv(p, low_memory=False)
                break
            except Exception:
                pass

    for p in _USFA_PATHS:
        if p.exists():
            try:
                usfa_df = pd.read_csv(p, low_memory=False)
                break
            except Exception:
                pass

    return fire_df, ch_df, gi_df, usfa_df


def _svi_tier(svi):
    if svi is None or pd.isna(svi): return "Unknown", "#888"
    if svi >= 0.90: return "Critical (≥0.90)",  "#FF4444"
    if svi >= 0.75: return "High (0.75–0.90)",   "#FF9800"
    if svi >= 0.50: return "Moderate (0.50–0.75)","#FFC107"
    return "Low (<0.50)", "#4ade80"


def _gi_label(z):
    if z is None or pd.isna(z): return "Not analyzed", "#888"
    if z >= 1.645: return "Hot Spot (90%+ CI)", "#FF4444"
    if z >= 1.282: return "Hot Spot (80%+ CI)", "#FF9800"
    if z <= -1.282: return "Cold Spot", "#4a90d9"
    return "Not significant", "#888"


def render_county_drilldown_page():
    st.title("County-Level Drill-Down")
    st.caption(
        "Select a county to see its SVI tier, fire history, alert channel coverage, "
        "USFA fire department resources, and caregiver coverage estimate  ·  WiDS 2021–2025"
    )

    fire_df, ch_df, gi_df, usfa_df = load_all_county_data()

    if fire_df is None:
        st.error(
            "county_fire_stats.csv not found. "
            "Run the preprocessing step to generate it from fire_events_with_svi_and_delays.csv."
        )
        return

    # ── County Selector ───────────────────────────────────────────────────────
    fire_df = fire_df.copy()
    fire_df["county_label"] = fire_df["county_name"] + ", " + fire_df["state"].fillna("")
    fire_df["svi_score"] = pd.to_numeric(fire_df["svi_score"], errors="coerce")

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        sort_by = st.selectbox(
            "Sort counties by",
            ["Most fires", "Highest SVI (most vulnerable)", "Highest % silent fires",
             "Most extreme fires", "Alphabetical"],
            index=0,
        )

    sort_map = {
        "Most fires":                    ("total_fires",   False),
        "Highest SVI (most vulnerable)": ("svi_score",     False),
        "Highest % silent fires":        ("pct_silent",    False),
        "Most extreme fires":            ("extreme_fires", False),
        "Alphabetical":                  ("county_label",  True),
    }
    col, asc = sort_map[sort_by]
    sorted_df = fire_df.sort_values(col, ascending=asc, na_position="last")
    county_options = sorted_df["county_label"].tolist()

    # Default to first high-SVI county
    default_idx = 0
    for i, lbl in enumerate(county_options):
        if "Trinity" in lbl or "Presidio" in lbl or "Cibola" in lbl:
            default_idx = i
            break

    with col_sel1:
        selected = st.selectbox("Select county", county_options, index=default_idx)

    row = fire_df[fire_df["county_label"] == selected].iloc[0]
    county_name = row["county_name"]
    state = row.get("state", "")
    # Derive n_evac from total_fires × pct_evac when column not present
    if "n_evac" in fire_df.columns:
        n_evac_computed = int(row.get("n_evac", 0) or 0)
    else:
        n_evac_computed = int(round(row.get("total_fires", 0) * row.get("pct_evac", 0)))

    # ── Header row ────────────────────────────────────────────────────────────
    st.divider()
    svi_tier_label, svi_color = _svi_tier(row.get("svi_score"))
    st.markdown(
        f"## {county_name}, {state} &nbsp;&nbsp;"
        f"<span style='background:{svi_color};color:#111;padding:3px 10px;border-radius:8px;"
        f"font-size:0.8rem;font-weight:700'>{svi_tier_label}</span>",
        unsafe_allow_html=True,
    )

    # ── KPI strip ─────────────────────────────────────────────────────────────
    h1, h2, h3, h4, h5 = st.columns(5)
    h1.metric("Total Fires", f"{int(row.get('total_fires', 0)):,}",
              help="Total wildfire incidents in WiDS dataset for this county (2021–2025)")
    h2.metric("SVI Score", f"{row.get('svi_score', 'N/A'):.3f}" if pd.notna(row.get("svi_score")) else "N/A",
              delta=svi_tier_label, delta_color="inverse" if row.get("svi_score", 0) >= 0.75 else "off")
    silent_pct = row.get("pct_silent", 0)
    h3.metric("% Silent Fires", f"{silent_pct*100:.1f}%",
              delta="vs 73.5% national avg",
              delta_color="inverse" if silent_pct > 0.735 else "normal")
    h4.metric("Extreme-Spread Fires", f"{int(row.get('extreme_fires', 0)):,}",
              help="Fires classified 'extreme' spread rate by incident commanders")
    evac_pct = row.get("pct_evac", 0)
    h5.metric("Evacuation Rate", f"{evac_pct*100:.2f}%",
              delta=f"{int(row.get('n_evac', 0))} evacuations",
              delta_color="off")

    # ── SVI breakdown ─────────────────────────────────────────────────────────
    st.divider()
    col_svi, col_pop = st.columns(2)

    with col_svi:
        st.subheader("SVI Sub-Theme Breakdown")
        svi_themes = {
            "Socioeconomic":   row.get("svi_socioeconomic"),
            "Household Comp.": row.get("svi_household"),
            "Minority Status": row.get("svi_minority"),
            "Housing Type":    row.get("svi_housing"),
        }
        valid_themes = {k: v for k, v in svi_themes.items() if v is not None and pd.notna(v)}
        if valid_themes:
            max_theme = max(valid_themes, key=lambda k: valid_themes[k])
            bar_colors = ["#FF4444" if k == max_theme else "#4a90d9" for k in valid_themes]
            fig_svi = go.Figure(go.Bar(
                x=list(valid_themes.keys()),
                y=list(valid_themes.values()),
                marker_color=bar_colors,
                text=[f"{v:.2f}" for v in valid_themes.values()],
                textposition="outside",
            ))
            fig_svi.update_layout(
                template="plotly_dark",
                yaxis=dict(range=[0, 1.15], title="Percentile (0–1)"),
                height=220,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_svi, use_container_width=True)
            st.caption(f"Primary driver: **{max_theme}** ({valid_themes[max_theme]:.2f}) — shown in red")
        else:
            st.info("SVI sub-theme data not available for this county.")

    with col_pop:
        st.subheader("Vulnerable Population Composition")
        pop_fields = {
            "Age 65+":      row.get("pop_age65"),
            "Disability":   row.get("pop_disability"),
            "Below Poverty":row.get("pop_poverty"),
            "No Vehicle":   row.get("pop_no_vehicle"),
        }
        valid_pop = {k: int(v) for k, v in pop_fields.items() if v is not None and pd.notna(v)}
        if valid_pop:
            pop_colors = ["#FF9800", "#4a90d9", "#FF4444", "#FFC107"]
            fig_pop = go.Figure()
            for (lbl, val), color in zip(valid_pop.items(), pop_colors):
                fig_pop.add_trace(go.Bar(
                    name=lbl, x=[county_name], y=[val],
                    marker_color=color,
                    text=[f"{val:,}"], textposition="inside",
                ))
            fig_pop.update_layout(
                template="plotly_dark",
                barmode="stack",
                yaxis_title="Persons",
                height=220,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig_pop, use_container_width=True)
        else:
            st.info("Population data not available for this county.")

    # ── Fire history chart ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Fire Profile")

    fp1, fp2, fp3 = st.columns(3)

    # Silent vs normal breakdown
    total = int(row.get("total_fires", 0))
    silent_n = int(round(total * silent_pct))
    normal_n = total - silent_n
    extreme_n = int(row.get("extreme_fires", 0))
    evac_n = n_evac_computed

    fig_fire = go.Figure(go.Pie(
        labels=["Silent (no public alert)", "Normal (public alert)"],
        values=[silent_n, normal_n],
        hole=0.55,
        marker_colors=["#FF4444", "#4a90d9"],
        textinfo="label+percent",
        textfont_size=11,
    ))
    fig_fire.update_layout(
        template="plotly_dark",
        height=220,
        margin=dict(l=5, r=5, t=5, b=5),
        showlegend=False,
        annotations=[dict(
            text=f"{silent_pct*100:.0f}%<br>Silent",
            x=0.5, y=0.5, font_size=13, showarrow=False, font_color="#FF4444"
        )],
    )
    fp1.plotly_chart(fig_fire, use_container_width=True)

    fp2.metric("Total Fires", f"{total:,}")
    fp2.metric("Silent (no alert)", f"{silent_n:,}", delta=f"{silent_pct*100:.1f}%", delta_color="inverse")
    fp2.metric("Extreme spread", f"{extreme_n:,}", delta="highest risk", delta_color="inverse" if extreme_n > 0 else "off")
    fp2.metric("Evacuations", f"{evac_n:,}", delta=f"{evac_pct*100:.2f}% evac rate")

    # Gi* cluster status
    gi_label_txt = "Not analyzed"
    gi_color = "#888"
    if gi_df is not None:
        gi_match = gi_df[gi_df["county_name"].str.lower() == county_name.lower()]
        if not gi_match.empty:
            z = gi_match.iloc[0].get("gi_star")
            gi_label_txt, gi_color = _gi_label(z)
            fp3.metric("Gi* Cluster Status", gi_label_txt,
                       help="Getis-Ord Gi* spatial cluster classification")
            fp3.metric("Gi* z-score", f"{z:.3f}" if pd.notna(z) else "N/A")
        else:
            fp3.metric("Gi* Cluster Status", "Not in analysis",
                       help="County not included (needs ≥10 fires with valid coordinates)")
    else:
        fp3.info("Gi* data not available.")

    # ── Alert channel coverage ────────────────────────────────────────────────
    st.divider()
    st.subheader("Alert Channel Coverage")

    ch_row = None
    if ch_df is not None:
        ch_match = ch_df[ch_df["county_name"].str.lower() == county_name.lower()]
        if not ch_match.empty:
            ch_row = ch_match.iloc[0]

    if ch_row is not None:
        n_ch = int(ch_row.get("n_channels", 0))
        n_fires_ch = int(ch_row.get("n_fires_with_channel", 0))
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Incident Channels", f"{n_ch}",
                   delta="Multi-channel" if n_ch >= 3 else ("Dual" if n_ch == 2 else "Single-channel — no redundancy"),
                   delta_color="normal" if n_ch >= 3 else "inverse")
        cc2.metric("Fires with Channel Data", f"{n_fires_ch:,}")
        pct_covered = n_fires_ch / total * 100 if total > 0 else 0
        cc3.metric("Channel Coverage Rate", f"{pct_covered:.1f}%",
                   help="% of this county's fires that have incident channel data")

        if n_ch == 1:
            st.warning(
                f"**{county_name} relies on a single alert channel.** "
                "If that channel goes offline during a fire, residents receive no automated notification. "
                "Caregiver alert system provides redundancy independent of channel availability."
            )
        elif n_ch >= 5:
            st.success(f"**{county_name} has strong multi-channel coverage ({n_ch} channels).** "
                       "Redundancy is in place for alert routing.")
    else:
        st.info(f"{county_name} has no incident channel data in the WiDS dataset. "
                "It may be served by regional channels not linked to individual fires.")

    # ── USFA fire departments ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Fire Department Resources (USFA)")

    if usfa_df is not None:
        # Try to match county
        county_short = county_name.replace(" County", "").replace(" Parish", "").strip()
        usfa_match = usfa_df[
            usfa_df.apply(lambda r: (
                county_short.lower() in str(r.get("fd_county", "")).lower() or
                county_short.lower() in str(r.get("hq_city", "")).lower()
            ), axis=1)
        ]
        if not usfa_match.empty and state:
            state_col = next((c for c in usfa_df.columns if "state" in c.lower()), None)
            if state_col:
                usfa_match = usfa_match[usfa_match[state_col].str.upper() == state.upper()[:2]]

        if not usfa_match.empty:
            uf1, uf2, uf3 = st.columns(3)
            uf1.metric("Fire Departments", f"{len(usfa_match):,}")
            stations_col = next((c for c in usfa_df.columns if "station" in c.lower()), None)
            if stations_col:
                uf2.metric("Total Stations",
                           f"{pd.to_numeric(usfa_match[stations_col], errors='coerce').sum():,.0f}")
            career_col = next((c for c in usfa_df.columns if "career" in c.lower() and "ff" in c.lower()), None)
            vol_col = next((c for c in usfa_df.columns if "vol" in c.lower() and "ff" in c.lower()), None)
            if career_col and vol_col:
                total_ff = (pd.to_numeric(usfa_match[career_col], errors="coerce").sum() +
                            pd.to_numeric(usfa_match[vol_col], errors="coerce").sum())
                uf3.metric("Total Firefighters", f"{total_ff:,.0f}")

            show_cols = [c for c in ["fd_name", "hq_city", "dept_type", "num_stations"] if c in usfa_df.columns]
            if show_cols:
                st.dataframe(usfa_match[show_cols].rename(columns={
                    "fd_name": "Department", "hq_city": "City",
                    "dept_type": "Type", "num_stations": "Stations"
                }).head(15), use_container_width=True, hide_index=True)
        else:
            st.info(
                f"No USFA registry entries matched for {county_name}. "
                "Download the full registry from [apps.usfa.fema.gov/registry/download]"
                "(https://apps.usfa.fema.gov/registry/download) and save as "
                "`wids-caregiver-alert/src/usfa-registry-national.csv`."
            )
    else:
        st.info(
            "USFA registry not loaded. Download from "
            "[apps.usfa.fema.gov/registry/download](https://apps.usfa.fema.gov/registry/download) "
            "and save as `wids-caregiver-alert/src/usfa-registry-national.csv`."
        )

    # ── Caregiver coverage estimate ───────────────────────────────────────────
    st.divider()
    st.subheader("Estimated Caregiver Coverage Gap")

    age65 = row.get("pop_age65", 0) or 0
    disabled = row.get("pop_disability", 0) or 0
    no_vehicle = row.get("pop_no_vehicle", 0) or 0
    poverty = row.get("pop_poverty", 0) or 0

    # Overlap estimate: ~60% of elderly are also either disabled or in poverty
    # "Need caregiver" = age65 + disabled (deduplicated at ~60% overlap)
    need_caregiver = int(age65 + disabled * 0.4 + no_vehicle * 0.3)
    caregiver_adoption_pct = 0.15  # conservative 15% adoption
    covered = int(need_caregiver * caregiver_adoption_pct)
    gap = need_caregiver - covered

    cg1, cg2, cg3 = st.columns(3)
    cg1.metric("Est. Vulnerable Residents", f"{need_caregiver:,}",
               help="age65 + 40% of disabled + 30% of no-vehicle (deduplicated estimate)")
    cg2.metric("Covered at 15% Adoption", f"{covered:,}",
               delta="conservative estimate", delta_color="off")
    cg3.metric("Coverage Gap", f"{gap:,}",
               delta=f"{gap/need_caregiver*100:.0f}% without caregiver alert",
               delta_color="inverse")

    st.markdown(f"""
At **15% caregiver adoption** (conservative), the alert system would cover
**{covered:,} of {need_caregiver:,}** estimated vulnerable residents in {county_name}.
The remaining **{gap:,} ({gap/need_caregiver*100:.0f}%)** would still rely on official
evacuation orders — which arrive at a median of **1.1 hours** after fire ignition,
often too late for those without vehicles or mobility assistance.

Increasing adoption to **50%** would cover **{int(need_caregiver*0.5):,}** residents.
At **85%** (FEMA IPAWS target) — **{int(need_caregiver*0.85):,}** residents.
    """)

    st.caption(
        "Caregiver coverage estimate uses population data from CDC SVI + WiDS fire events dataset. "
        "Adoption rates are modeled scenarios, not measured values."
    )
