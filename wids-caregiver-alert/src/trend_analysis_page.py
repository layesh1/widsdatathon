"""
trend_analysis_page.py
Year-over-Year Fire Trend Analysis — 49ers Intelligence Lab · WiDS 2025

Tracks whether signal gaps, evacuation failures, and equity disparities
are improving or worsening from 2021 to 2025.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from ui_utils import page_header, section_header, render_card

# ── CSV loader ────────────────────────────────────────────────────────────────

_CSV_PATHS = [
    Path("fire_events_with_svi_and_delays.csv"),
    Path("01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
    Path("../01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
]

SPREAD_ORDER = {"slow": 0, "moderate": 1, "rapid": 2, "extreme": 3}

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


@st.cache_data(show_spinner=False)
def _load_df() -> pd.DataFrame | None:
    for p in _CSV_PATHS:
        if p.exists():
            df = pd.read_csv(p, low_memory=False)
            df["fire_start"] = pd.to_datetime(df["fire_start"], errors="coerce", utc=True)
            df["year"] = df["fire_start"].dt.year
            df["month"] = df["fire_start"].dt.month
            # Keep only 2021-2025 and rows with a valid year
            df = df[df["year"].between(2021, 2025)].copy()
            return df
    return None


# ── Year-over-year aggregates ─────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _yearly_signal_gap(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("year").agg(
        total=("geo_event_id", "count"),
        silent=(
            "notification_type",
            lambda s: (s == "silent").sum(),
        ),
        no_evac=(
            "evacuation_occurred",
            lambda s: (s == 0).sum(),
        ),
        med_delay=("evacuation_delay_hours", "median"),
    ).reset_index()
    g["pct_silent"] = g["silent"] / g["total"] * 100
    g["pct_no_evac"] = g["no_evac"] / g["total"] * 100
    g["med_delay_h"] = g["med_delay"]
    return g


@st.cache_data(show_spinner=False)
def _yearly_extreme(df: pd.DataFrame) -> pd.DataFrame:
    ext = df[df["last_spread_rate"] == "extreme"].copy()
    g = ext.groupby("year").agg(
        count=("geo_event_id", "count"),
        no_action=(
            "evacuation_occurred",
            lambda s: (s == 0).sum(),
        ),
    ).reset_index()
    g["pct_no_action"] = g["no_action"] / g["count"] * 100
    return g


@st.cache_data(show_spinner=False)
def _yearly_high_svi(df: pd.DataFrame) -> pd.DataFrame:
    hi = df[df["svi_score"] >= 0.75].copy()
    g = hi.groupby("year").agg(
        fires=("geo_event_id", "count"),
        avg_growth=("growth_rate_acres_per_hour", "mean"),
        avg_delay=("evacuation_delay_hours", "mean"),
    ).reset_index()
    return g


@st.cache_data(show_spinner=False)
def _monthly_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["year", "month"]).size().reset_index(name="fires")
    pivot = g.pivot(index="year", columns="month", values="fires").fillna(0)
    # Ensure all months present
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0
    pivot = pivot[sorted(pivot.columns)]
    return pivot


# ── Page render ───────────────────────────────────────────────────────────────

def render_trend_analysis_page() -> None:
    page_header(
        "Year-over-Year Fire Trend Analysis",
        "Are signal gaps and evacuation failures getting worse? · WiDS 2021–2025 · 62,696 incidents",
    )

    df = _load_df()

    if df is None:
        st.error(
            "Could not locate fire_events_with_svi_and_delays.csv. "
            "Expected at 01_raw_data/processed/ relative to the working directory."
        )
        return

    # ── State filter ─────────────────────────────────────────────────────────
    all_states = sorted(df["state"].dropna().unique().tolist())
    col_filter, col_spacer = st.columns([2, 5])
    with col_filter:
        state_choice = st.selectbox(
            "Filter by state (optional)",
            ["All States"] + all_states,
            help="Narrow all charts to a single state",
        )
    if state_choice != "All States":
        df = df[df["state"] == state_choice].copy()
        if df.empty:
            st.warning(f"No data for {state_choice}.")
            return

    years_present = sorted(df["year"].dropna().unique().tolist())
    n_fires = len(df)

    # ── Top KPIs ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card(
            "Fires in Dataset",
            f"{n_fires:,}",
            f"{state_choice} · 2021–2025",
            color="#1e3a5f",
        )
    with c2:
        pct_silent = (df["notification_type"] == "silent").mean() * 100
        render_card(
            "Silent Fires",
            f"{pct_silent:.1f}%",
            "No public notification issued",
            color="#FF4B4B",
        )
    with c3:
        pct_no_evac = (df["evacuation_occurred"] == 0).mean() * 100
        render_card(
            "Fires with No Evac Action",
            f"{pct_no_evac:.1f}%",
            "No order, warning, or advisory",
            color="#d4a017",
        )
    with c4:
        med_d = df["evacuation_delay_hours"].dropna().median()
        render_card(
            "Median Evac Delay",
            f"{med_d:.1f}h" if not np.isnan(med_d) else "N/A",
            "Signal detected → first action",
            color="#d4a017",
        )

    st.markdown("")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. Year-over-year signal gap trends
    # ═══════════════════════════════════════════════════════════════════════
    section_header("Signal Gap Trends by Year")
    st.caption(
        "Are silent fire rates and evacuation failures improving or worsening over time?"
    )

    yoy = _yearly_signal_gap(df)

    tab1, tab2, tab3 = st.tabs(
        ["Silent Fire Rate", "No-Evac-Action Rate", "Median Delay (hours)"]
    )

    _YEAR_COLORS = ["#4a90d9", "#6ab0e8", "#FF9800", "#FF4B4B", "#e83e3e"]

    with tab1:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=yoy["year"].astype(str),
                y=yoy["pct_silent"].round(1),
                marker_color=_YEAR_COLORS[: len(yoy)],
                text=yoy["pct_silent"].round(1).astype(str) + "%",
                textposition="outside",
                name="% Silent",
            )
        )
        fig.update_layout(
            template="plotly_dark",
            title="Silent Fire Rate by Year (%)",
            xaxis_title="Year",
            yaxis_title="% of Fires with No Public Notification",
            height=340,
            margin=dict(l=40, r=20, t=50, b=40),
            yaxis=dict(range=[0, 110]),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "A rising trend means more fires are going unreported to the public year over year."
        )

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(
            go.Bar(
                x=yoy["year"].astype(str),
                y=yoy["pct_no_evac"].round(1),
                marker_color=_YEAR_COLORS[: len(yoy)],
                text=yoy["pct_no_evac"].round(1).astype(str) + "%",
                textposition="outside",
                name="% No Action",
            )
        )
        fig2.update_layout(
            template="plotly_dark",
            title="No-Evacuation-Action Rate by Year (%)",
            xaxis_title="Year",
            yaxis_title="% of Fires with Zero Evacuation Response",
            height=340,
            margin=dict(l=40, r=20, t=50, b=40),
            yaxis=dict(range=[0, 110]),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        # Only fires that had some action (delay is meaningful)
        yoy_delay = (
            df[df["evacuation_delay_hours"].notna()]
            .groupby("year")["evacuation_delay_hours"]
            .median()
            .reset_index()
        )
        yoy_delay.columns = ["year", "med_delay_h"]
        fig3 = go.Figure()
        fig3.add_trace(
            go.Scatter(
                x=yoy_delay["year"].astype(str),
                y=yoy_delay["med_delay_h"].round(2),
                mode="lines+markers+text",
                text=yoy_delay["med_delay_h"].round(1).astype(str) + "h",
                textposition="top center",
                line=dict(color="#FF4B4B", width=2),
                marker=dict(size=10, color="#FF4B4B"),
                name="Median Delay",
            )
        )
        fig3.update_layout(
            template="plotly_dark",
            title="Median Evacuation Delay (hours) by Year",
            xaxis_title="Year",
            yaxis_title="Median Delay (hours)",
            height=340,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(
            "Delay measured from signal detection to first evacuation action (order/warning/advisory). "
            "Only includes fires where at least one action was issued."
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. Extreme fire trends
    # ═══════════════════════════════════════════════════════════════════════
    section_header("Extreme-Spread-Rate Fires by Year")
    st.caption(
        "Fires classified as 'extreme' spread rate — and the share that received no evacuation action."
    )

    ext_df = _yearly_extreme(df)

    if ext_df.empty:
        st.info("No extreme-spread-rate fires in selected dataset.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            fig_ext_count = go.Figure()
            fig_ext_count.add_trace(
                go.Bar(
                    x=ext_df["year"].astype(str),
                    y=ext_df["count"],
                    marker_color="#FF4B4B",
                    text=ext_df["count"],
                    textposition="outside",
                    name="Extreme Fires",
                )
            )
            fig_ext_count.update_layout(
                template="plotly_dark",
                title="Extreme-Spread Fires per Year",
                xaxis_title="Year",
                yaxis_title="Count",
                height=320,
                margin=dict(l=40, r=20, t=50, b=40),
            )
            st.plotly_chart(fig_ext_count, use_container_width=True)

        with col_b:
            fig_ext_pct = go.Figure()
            fig_ext_pct.add_trace(
                go.Bar(
                    x=ext_df["year"].astype(str),
                    y=ext_df["pct_no_action"].round(1),
                    marker_color="#d4a017",
                    text=ext_df["pct_no_action"].round(1).astype(str) + "%",
                    textposition="outside",
                    name="% No Action",
                )
            )
            fig_ext_pct.update_layout(
                template="plotly_dark",
                title="% Extreme Fires with No Evacuation Action",
                xaxis_title="Year",
                yaxis_title="% No Action Taken",
                height=320,
                margin=dict(l=40, r=20, t=50, b=40),
                yaxis=dict(range=[0, 110]),
            )
            st.plotly_chart(fig_ext_pct, use_container_width=True)

        total_ext = ext_df["count"].sum()
        no_act_ext = ext_df["no_action"].sum() if "no_action" in ext_df.columns else (
            (ext_df["pct_no_action"] / 100 * ext_df["count"]).sum()
        )
        st.markdown(
            f"Across all years: **{int(total_ext):,} extreme-spread fires**, "
            f"**{int(no_act_ext):,}** ({no_act_ext / total_ext * 100:.1f}%) received zero evacuation response."
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. High-SVI county fire growth
    # ═══════════════════════════════════════════════════════════════════════
    section_header("High-Vulnerability County Trends (SVI >= 0.75)")
    st.caption(
        "Counties with Social Vulnerability Index >= 0.75 — where vulnerable populations "
        "are concentrated. Are fire growth rates and delays improving?"
    )

    hi_svi = _yearly_high_svi(df)

    if hi_svi.empty or hi_svi["fires"].sum() == 0:
        st.info("No fires in high-SVI counties (>= 0.75) for the current filter.")
    else:
        col_c, col_d = st.columns(2)

        with col_c:
            fig_growth = go.Figure()
            fig_growth.add_trace(
                go.Scatter(
                    x=hi_svi["year"].astype(str),
                    y=hi_svi["avg_growth"].round(2),
                    mode="lines+markers+text",
                    text=hi_svi["avg_growth"].round(1).astype(str),
                    textposition="top center",
                    line=dict(color="#FF9800", width=2),
                    marker=dict(size=10, color="#FF9800"),
                    name="Avg Growth Rate",
                )
            )
            fig_growth.update_layout(
                template="plotly_dark",
                title="Avg Fire Growth Rate in High-SVI Counties<br>(acres/hour)",
                xaxis_title="Year",
                yaxis_title="Avg Growth Rate (acres/hour)",
                height=320,
                margin=dict(l=40, r=20, t=60, b=40),
            )
            st.plotly_chart(fig_growth, use_container_width=True)

        with col_d:
            fig_delay_svi = go.Figure()
            fig_delay_svi.add_trace(
                go.Scatter(
                    x=hi_svi["year"].astype(str),
                    y=hi_svi["avg_delay"].round(2),
                    mode="lines+markers+text",
                    text=hi_svi["avg_delay"].round(1).astype(str) + "h",
                    textposition="top center",
                    line=dict(color="#FF4B4B", width=2),
                    marker=dict(size=10, color="#FF4B4B"),
                    name="Avg Delay",
                )
            )
            fig_delay_svi.update_layout(
                template="plotly_dark",
                title="Avg Evacuation Delay in High-SVI Counties<br>(hours)",
                xaxis_title="Year",
                yaxis_title="Avg Delay (hours)",
                height=320,
                margin=dict(l=40, r=20, t=60, b=40),
            )
            st.plotly_chart(fig_delay_svi, use_container_width=True)

        with st.expander("High-SVI county data by year"):
            st.dataframe(
                hi_svi.rename(
                    columns={
                        "year": "Year",
                        "fires": "Total Fires",
                        "avg_growth": "Avg Growth (acres/h)",
                        "avg_delay": "Avg Delay (h)",
                    }
                ).round(2),
                use_container_width=True,
                hide_index=True,
            )

    # ═══════════════════════════════════════════════════════════════════════
    # 4. Monthly seasonality heatmap (year × month)
    # ═══════════════════════════════════════════════════════════════════════
    section_header("Monthly Fire Seasonality by Year")
    st.caption(
        "Heatmap: rows = year, columns = month. "
        "Darker red = more fires. Is the fire season expanding?"
    )

    pivot = _monthly_heatmap(df)

    if pivot.empty:
        st.info("Insufficient data for seasonality heatmap.")
    else:
        col_labels = [MONTH_NAMES[m] for m in pivot.columns]
        row_labels = [str(y) for y in pivot.index]

        fig_heat = go.Figure(
            go.Heatmap(
                z=pivot.values,
                x=col_labels,
                y=row_labels,
                colorscale=[
                    [0.0, "#0d1117"],
                    [0.2, "#1e3a5f"],
                    [0.5, "#d4a017"],
                    [0.75, "#FF9800"],
                    [1.0, "#FF4B4B"],
                ],
                hovertemplate="Year: %{y}<br>Month: %{x}<br>Fires: %{z:,}<extra></extra>",
                colorbar=dict(title="Fires"),
                text=pivot.values,
                texttemplate="%{text:,}",
                textfont=dict(size=10),
            )
        )
        fig_heat.update_layout(
            template="plotly_dark",
            title="Fire Count Heatmap: Year × Month",
            xaxis_title="Month",
            yaxis_title="Year",
            height=max(240, 60 * len(row_labels) + 80),
            margin=dict(l=60, r=40, t=60, b=40),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        st.caption(
            "A horizontal expansion of the red band toward spring/fall months would indicate "
            "a lengthening fire season — a key climate change signal."
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 5. State-level trend (already applied via filter above; show summary)
    # ═══════════════════════════════════════════════════════════════════════
    if state_choice != "All States":
        section_header(f"State Summary — {state_choice}")
        yoy_state = _yearly_signal_gap(df)
        if not yoy_state.empty:
            fig_state = go.Figure()
            fig_state.add_trace(
                go.Bar(
                    x=yoy_state["year"].astype(str),
                    y=yoy_state["total"],
                    name="Total Fires",
                    marker_color="#4a90d9",
                )
            )
            fig_state.add_trace(
                go.Bar(
                    x=yoy_state["year"].astype(str),
                    y=yoy_state["silent"],
                    name="Silent Fires",
                    marker_color="#FF4B4B",
                )
            )
            fig_state.update_layout(
                template="plotly_dark",
                barmode="overlay",
                title=f"{state_choice}: Total vs Silent Fires by Year",
                xaxis_title="Year",
                yaxis_title="Fire Count",
                height=320,
                margin=dict(l=40, r=20, t=50, b=40),
                legend=dict(orientation="h", y=1.02, x=0),
            )
            st.plotly_chart(fig_state, use_container_width=True)
    else:
        section_header("Top States by Trend Severity")
        top_states = (
            df.groupby("state")
            .agg(
                total=("geo_event_id", "count"),
                silent=("notification_type", lambda s: (s == "silent").sum()),
                no_evac=("evacuation_occurred", lambda s: (s == 0).sum()),
            )
            .reset_index()
        )
        top_states["pct_silent"] = (top_states["silent"] / top_states["total"] * 100).round(1)
        top_states["pct_no_evac"] = (top_states["no_evac"] / top_states["total"] * 100).round(1)
        top_states = top_states.sort_values("pct_silent", ascending=False).head(15)

        fig_states = px.bar(
            top_states,
            x="state",
            y="pct_silent",
            color="pct_silent",
            color_continuous_scale=[[0, "#4a90d9"], [0.5, "#d4a017"], [1, "#FF4B4B"]],
            hover_data={"total": True, "pct_no_evac": True},
            labels={"pct_silent": "% Silent Fires", "state": "State"},
            title="Top 15 States by Silent Fire Rate",
            template="plotly_dark",
        )
        fig_states.update_layout(
            height=360,
            margin=dict(l=40, r=20, t=50, b=60),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_states, use_container_width=True)

    st.caption(
        "Data source: fire_events_with_svi_and_delays.csv · 62,696 wildfire incidents · "
        "WiDS 2021–2025. Use the state filter above to drill into a specific state's trends."
    )
