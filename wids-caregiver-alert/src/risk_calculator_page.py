"""
risk_calculator_page.py
Real, actionable risk calculator for caregivers and emergency workers.
Uses:
  - CDC SVI component data (RPL_THEME1-4, E_AGE65, E_DISABL, E_NOVEH, E_POV150)
  - WiDS real fire timing data (1.1h median, 32h P90, 17% growth differential)
  - FEMA and Red Cross evacuation time estimates by mobility level
  - NASA FIRMS for current fire proximity
Outputs: Personalized risk score + specific action timeline
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
from pathlib import Path
from datetime import datetime


# ── Real constants from WiDS data ────────────────────────────────────────────
MEDIAN_EVAC_ORDER_H  = 1.1
P90_EVAC_ORDER_H     = 32.0
VULNERABLE_GROWTH_MULTIPLIER = 1.17  # 17% faster in high-SVI counties

# ── FEMA evacuation time estimates by mobility/situation ─────────────────────
# Source: FEMA Evacuation Planning Guide (2019), adjusted for wildfire speed
EVAC_TIME_ESTIMATES = {
    "mobile_adult":       {"pack": 0.25, "load": 0.25, "drive": 0.5, "total": 1.0},   # hours
    "elderly_walking":    {"pack": 0.75, "load": 0.50, "drive": 0.5, "total": 1.75},
    "disabled_caregiver": {"pack": 1.0,  "load": 0.75, "drive": 0.5, "total": 2.25},
    "no_vehicle":         {"pack": 0.5,  "load": 0.5,  "drive": 2.0, "total": 3.0},   # transit time
    "medical_equipment":  {"pack": 1.5,  "load": 1.0,  "drive": 0.5, "total": 3.0},
}

# ── SVI lookup (static table of high-risk counties for reference) ─────────────
# These are the most fire-prone high-SVI counties from WiDS analysis
# Sub-themes: socioeconomic, household composition, minority status, housing type
# Population fields: elderly 65+, disabled, below poverty, no vehicle
HIGH_RISK_COUNTIES = {
    "Butte County, CA":       {
        "svi": 0.78, "lat": 39.7, "lon": -121.6,
        "svi_socioeconomic": 0.77, "svi_household": 0.48, "svi_minority": 0.68, "svi_housing": 0.94,
        "pop_age65": 38852, "pop_disability": 34705, "pop_poverty": 58898, "pop_no_vehicle": 5063,
    },
    "Shasta County, CA":      {
        "svi": 0.72, "lat": 40.6, "lon": -122.1,
        "svi_socioeconomic": 0.61, "svi_household": 0.83, "svi_minority": 0.57, "svi_housing": 0.79,
        "pop_age65": 38339, "pop_disability": 32564, "pop_poverty": 38675, "pop_no_vehicle": 4360,
    },
    "Trinity County, CA":     {
        "svi": 0.89, "lat": 40.6, "lon": -123.1,
        "svi_socioeconomic": 0.77, "svi_household": 0.74, "svi_minority": 0.54, "svi_housing": 0.51,
        "pop_age65": 4396, "pop_disability": 2467, "pop_poverty": 5351, "pop_no_vehicle": 242,
    },
    "Otero County, NM":       {
        "svi": 0.82, "lat": 32.8, "lon": -105.7,
        "svi_socioeconomic": 0.86, "svi_household": 0.92, "svi_minority": 0.89, "svi_housing": 0.87,
        "pop_age65": 11541, "pop_disability": 12610, "pop_poverty": 19882, "pop_no_vehicle": 1166,
    },
    "Cibola County, NM":      {
        "svi": 0.85, "lat": 35.0, "lon": -107.8,
        "svi_socioeconomic": 0.84, "svi_household": 0.95, "svi_minority": 0.98, "svi_housing": 0.96,
        "pop_age65": 4606, "pop_disability": 5602, "pop_poverty": 10094, "pop_no_vehicle": 445,
    },
    "Graham County, AZ":      {
        "svi": 0.81, "lat": 32.9, "lon": -109.9,
        "svi_socioeconomic": 0.70, "svi_household": 0.66, "svi_minority": 0.87, "svi_housing": 0.95,
        "pop_age65": 5401, "pop_disability": 4580, "pop_poverty": 9131, "pop_no_vehicle": 594,
    },
    "Jefferson County, OR":   {
        "svi": 0.77, "lat": 44.6, "lon": -121.2,
        "svi_socioeconomic": 0.78, "svi_household": 0.98, "svi_minority": 0.80, "svi_housing": 0.87,
        "pop_age65": 4798, "pop_disability": 4757, "pop_poverty": 5413, "pop_no_vehicle": 423,
    },
    "Sanders County, MT":     {
        "svi": 0.74, "lat": 47.6, "lon": -115.6,
        "svi_socioeconomic": 0.83, "svi_household": 0.39, "svi_minority": 0.32, "svi_housing": 0.36,
        "pop_age65": 4027, "pop_disability": 2687, "pop_poverty": 3950, "pop_no_vehicle": 311,
    },
    "Presidio County, TX":    {
        "svi": 0.91, "lat": 29.9, "lon": -104.3,
        "svi_socioeconomic": 1.00, "svi_household": 0.97, "svi_minority": 0.98, "svi_housing": 0.72,
        "pop_age65": 1405, "pop_disability": 937, "pop_poverty": 2883, "pop_no_vehicle": 316,
    },
    "Other (enter manually)": {"svi": None, "lat": None, "lon": None},
}


def score_to_label(score):
    if score >= 0.80: return "Critical", "#FF4444"
    if score >= 0.60: return "High", "#FF9800"
    if score >= 0.40: return "Moderate", "#FFC107"
    return "Low-Moderate", "#4CAF50"


def get_nearest_fire_distance(lat, lon):
    """Check NASA FIRMS for nearest active fire."""
    try:
        url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/c6c38aac4de4e98571b29a73e3527a8c/VIIRS_SNPP_NRT/world/1"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            from io import StringIO
            df = pd.read_csv(StringIO(r.text))
            df["lat_f"] = pd.to_numeric(df["latitude"], errors="coerce")
            df["lon_f"] = pd.to_numeric(df["longitude"], errors="coerce")
            df = df.dropna(subset=["lat_f", "lon_f"])
            # Haversine approx
            df["dist_deg"] = np.sqrt((df["lat_f"] - lat)**2 + (df["lon_f"] - lon)**2)
            df["dist_km"]  = df["dist_deg"] * 111
            nearest = df.nsmallest(3, "dist_km")
            return nearest[["lat_f", "lon_f", "dist_km"]].values.tolist()
    except Exception:
        pass
    return None


def render_risk_calculator_page():
    st.title("Personal Risk Calculator")
    st.caption(
        "A real, data-driven tool for caregivers and residents to understand their personal evacuation risk. "
        "Uses CDC SVI data, WiDS 2021–2025 fire timing, and FEMA evacuation time estimates."
    )

    st.markdown("""
    This calculator answers: **"If a wildfire starts nearby, how much time do I actually have — and is it enough?"**

    It combines your personal mobility situation with real fire statistics from the WiDS dataset
    and checks NASA FIRMS for active fires near your location.
    """)

    st.divider()

    # ── SECTION 1: Location & County Vulnerability ───────────────────────────
    st.subheader("1. Your Location & County Risk")

    col1, col2 = st.columns(2)
    with col1:
        county_choice = st.selectbox(
            "Select your county (or choose 'Other')",
            list(HIGH_RISK_COUNTIES.keys())
        )
        if county_choice == "Other (enter manually)":
            svi_manual = st.slider(
                "Your county's CDC SVI score",
                0.0, 1.0, 0.5, step=0.01,
                help="Find at: cdc.gov/cdc-atsdr-gis/SVI/ — RPL_THEMES column"
            )
            lat_manual = st.number_input("Latitude (optional, for live fire check)", value=37.5)
            lon_manual = st.number_input("Longitude (optional)", value=-120.0)
            county_svi = svi_manual
            county_lat, county_lon = lat_manual, lon_manual
        else:
            info = HIGH_RISK_COUNTIES[county_choice]
            county_svi  = info["svi"]
            county_lat  = info["lat"]
            county_lon  = info["lon"]
            st.metric("County SVI Score", f"{county_svi:.2f}",
                      delta="High vulnerability" if county_svi >= 0.75 else "Moderate vulnerability",
                      delta_color="inverse")

            # SVI sub-theme breakdown
            sub_themes = {
                "Socioeconomic": info.get("svi_socioeconomic"),
                "Household\nComposition": info.get("svi_household"),
                "Minority\nStatus": info.get("svi_minority"),
                "Housing\nType": info.get("svi_housing"),
            }
            if all(v is not None for v in sub_themes.values()):
                primary_driver = max(sub_themes, key=lambda k: sub_themes[k])
                theme_colors = [
                    "#FF4444" if v == max(sub_themes.values()) else "#4a90d9"
                    for v in sub_themes.values()
                ]
                fig_svi = go.Figure(go.Bar(
                    x=list(sub_themes.keys()),
                    y=list(sub_themes.values()),
                    marker_color=theme_colors,
                    text=[f"{v:.2f}" for v in sub_themes.values()],
                    textposition="outside",
                ))
                fig_svi.update_layout(
                    template="plotly_dark",
                    title=f"SVI Sub-theme Breakdown — {county_choice}",
                    yaxis=dict(range=[0, 1.15], title="Percentile Rank (0–1)"),
                    height=220,
                    margin=dict(l=10, r=10, t=50, b=10),
                )
                st.plotly_chart(fig_svi, use_container_width=True)
                st.caption(
                    f"Primary vulnerability driver: **{primary_driver.replace(chr(10), ' ')}** "
                    f"({sub_themes[primary_driver]:.2f}). "
                    "WiDS data: minority status dimension has strongest correlation with evacuation delay."
                )

            # Vulnerable population breakdown stacked bar
            pop_fields = {
                "Age 65+": info.get("pop_age65"),
                "Disability": info.get("pop_disability"),
                "Below Poverty": info.get("pop_poverty"),
                "No Vehicle": info.get("pop_no_vehicle"),
            }
            if all(v is not None for v in pop_fields.values()):
                pop_colors = ["#FF9800", "#4a90d9", "#FF4444", "#FFC107"]
                fig_pop = go.Figure()
                for (label, val), color in zip(pop_fields.items(), pop_colors):
                    fig_pop.add_trace(go.Bar(
                        name=label, x=[county_choice], y=[val],
                        marker_color=color,
                        text=[f"{val:,}"], textposition="inside",
                    ))
                fig_pop.update_layout(
                    template="plotly_dark",
                    barmode="stack",
                    title="Vulnerable Population Composition",
                    yaxis_title="Persons",
                    height=220,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", y=-0.2),
                    showlegend=True,
                )
                st.plotly_chart(fig_pop, use_container_width=True)

    with col2:
        st.markdown("**What SVI means for fire risk:**")
        st.markdown(f"""
        - Median fire-to-evac-order time: **{MEDIAN_EVAC_ORDER_H}h** (all counties)
        - In high-SVI counties (like yours): fires grow **{(VULNERABLE_GROWTH_MULTIPLIER-1)*100:.0f}% faster**
        - 1 in 10 fires takes **{P90_EVAC_ORDER_H:.0f}h** to get an official order
        - Higher SVI = less likely to have car, caregiver, or early warning access
        """)

    # ── SECTION 2: Personal Situation ────────────────────────────────────────
    st.divider()
    st.subheader("2. Your Personal Situation")

    col3, col4 = st.columns(2)
    with col3:
        mobility = st.selectbox(
            "Mobility level",
            [
                ("mobile_adult",       "Fully mobile adult"),
                ("elderly_walking",    "Elderly / slow mobility"),
                ("disabled_caregiver", "Disabled, needs caregiver assistance"),
                ("no_vehicle",         "No personal vehicle"),
                ("medical_equipment",  "Medical equipment (O2, dialysis, etc.)"),
            ],
            format_func=lambda x: x[1]
        )
        mobility_key = mobility[0]

        has_caregiver = st.radio(
            "Do you have a caregiver who could give early warning?",
            ["Yes, reliably reachable", "Sometimes", "No"]
        )

        distance_to_wui = st.slider(
            "Distance from nearest wildland edge (miles)",
            0.5, 25.0, 3.0, step=0.5,
            help="WUI = Wildland-Urban Interface. Lower distance = higher risk."
        )

    with col4:
        has_go_bag = st.checkbox("I have a go-bag packed and ready")
        has_evac_plan = st.checkbox("I have a written evacuation plan with route")
        has_alerts_on = st.checkbox("I receive Wireless Emergency Alerts (WEA) on my phone")
        nearby_dependents = st.number_input("Dependents needing assistance (children, elderly, disabled)", 0, 10, 0)
        pets_livestock = st.radio("Pets or livestock?", ["None", "Small pets only", "Large animals / livestock"])

    # ── SECTION 3: Calculate ─────────────────────────────────────────────────
    st.divider()
    if st.button("Calculate My Risk Profile", type="primary"):

        evac_times = EVAC_TIME_ESTIMATES[mobility_key]

        # Additional time factors
        dependent_add   = nearby_dependents * 0.25  # 15 min per dependent
        pet_add         = 0.25 if "Large" in pets_livestock else (0.15 if "Small" in pets_livestock else 0)
        no_bag_add      = 0.5 if not has_go_bag else 0
        no_plan_add     = 0.25 if not has_evac_plan else 0

        total_evac_time = evac_times["total"] + dependent_add + pet_add + no_bag_add + no_plan_add

        # Alert lead time
        caregiver_lead = {"Yes, reliably reachable": 0.75, "Sometimes": 0.30, "No": 0.0}[has_caregiver]
        official_order_time = MEDIAN_EVAC_ORDER_H * (VULNERABLE_GROWTH_MULTIPLIER if county_svi >= 0.75 else 1.0)

        # Distance factor (rough: WUI fire can reach 1-2 mph spread, so distance matters)
        time_before_fire_arrives = distance_to_wui / 1.5  # hours at ~1.5 mph spread

        # Net buffer
        if caregiver_lead > 0:
            time_available = caregiver_lead + official_order_time
        else:
            time_available = official_order_time
        net_buffer = time_available - total_evac_time

        # Overall risk score
        risk_score = (
            (county_svi * 0.30) +
            (min(1.0, total_evac_time / 4) * 0.25) +
            ((1 - min(1.0, distance_to_wui / 10)) * 0.20) +
            ((0 if has_alerts_on else 0.1) +
             (0 if has_evac_plan else 0.1) +
             (0 if has_go_bag else 0.05)) +
            (min(1.0, nearby_dependents / 4) * 0.10)
        )
        risk_score = min(0.98, risk_score)

        label, color = score_to_label(risk_score)

        # ── Display results ──
        st.subheader("Your Risk Profile")

        # Big risk score
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=risk_score * 100,
            title={"text": "Overall Risk Score", "font": {"size": 18}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 40],  "color": "#1a3a1a"},
                    {"range": [40, 60], "color": "#3a2a00"},
                    {"range": [60, 80], "color": "#3a1400"},
                    {"range": [80, 100],"color": "#2a0000"},
                ]
            },
            number={"suffix": " / 100", "font": {"size": 28}}
        ))
        gauge_fig.update_layout(template="plotly_dark", height=250,
                                 margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(gauge_fig, use_container_width=True)

        st.markdown(f"### {label}")

        # Time analysis
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Time needed to evacuate",
            f"{total_evac_time:.2f}h",
            help="Based on your mobility, dependents, and preparation level"
        )
        c2.metric(
            "Expected time before official order",
            f"{official_order_time:.1f}h",
            help=f"WiDS median {MEDIAN_EVAC_ORDER_H}h, adjusted for SVI"
        )
        c3.metric(
            "Safety buffer",
            f"{net_buffer:+.2f}h",
            delta="You have time" if net_buffer > 0 else "You may not have enough time",
            delta_color="normal" if net_buffer > 0 else "inverse"
        )

        # Timeline visualization
        st.subheader("Your Evacuation Timeline")
        events = [
            ("Fire ignition", 0),
            (f"Caregiver alert (if enrolled)", caregiver_lead),
            (f"Official evacuation order (median)", official_order_time),
            (f"You complete evacuation", official_order_time + evac_times["total"] + no_bag_add + no_plan_add),
            (f"90th percentile order delay", P90_EVAC_ORDER_H),
        ]

        fig_tl = go.Figure()
        for i, (event, time) in enumerate(events):
            color_dot = "#FF4444" if time > official_order_time + evac_times["total"] else (
                "#FFC107" if time > official_order_time else "#4a90d9"
            )
            fig_tl.add_trace(go.Scatter(
                x=[time], y=[i],
                mode="markers+text",
                marker=dict(size=14, color=color_dot),
                text=[event],
                textposition="middle right",
                showlegend=False
            ))

        # Danger zone shading
        fig_tl.add_vrect(x0=0, x1=official_order_time,
                          fillcolor="rgba(255,165,0,0.1)", line_width=0,
                          annotation_text="Pre-order window", annotation_position="top left")

        fig_tl.update_layout(
            template="plotly_dark",
            xaxis_title="Hours from Ignition",
            yaxis=dict(showticklabels=False, showgrid=False),
            height=280,
            margin=dict(l=20, r=150, t=20, b=40),
            title="Your Personal Evacuation Timeline"
        )
        st.plotly_chart(fig_tl, use_container_width=True)

        # ── Specific recommendations ──
        st.subheader("Your Action Plan")

        recs = []
        if not has_go_bag:
            recs.append("**Pack a go-bag** — saves ~30 min when ordered to evacuate. Include medications, documents, 3 days clothes.")
        if not has_evac_plan:
            recs.append("**Write a route plan** — pre-identify 2 routes from your home to the nearest shelter. Saves ~15 min of decision time.")
        if not has_alerts_on:
            recs.append("**Enable Wireless Emergency Alerts** (Settings → Notifications → Emergency Alerts). Free, no app needed.")
        if has_caregiver == "No" and county_svi >= 0.75:
            recs.append("**Enroll in a caregiver network** — your high-SVI county means fires grow 17% faster. A caregiver alert adds ~45 min buffer.")
        if nearby_dependents > 0:
            recs.append(f"**Your {nearby_dependents} dependent(s) add ~{dependent_add*60:.0f} min** to evacuation. Start packing earlier than your household's official order threshold.")
        if "Large" in pets_livestock:
            recs.append("**Pre-arrange livestock transport** — large animals need a trailer and loading time. Identify a neighbor or service in advance.")
        if net_buffer < 0:
            recs.append(f"**Your evacuation takes longer than typical warning time.** Consider moving to less fire-prone area, or ensuring you have a caregiver alert enrolled.")
        if distance_to_wui < 1.0:
            recs.append("**You live within 1 mile of wildland** — this is WUI (Wildland-Urban Interface). Apply ember-resistant vents, clear 100ft defensible space.")

        for rec in recs:
            st.markdown(f"- {rec}")

        if not recs:
            st.success("Your preparation level is solid. Keep go-bag updated seasonally and review your route plan annually.")

        # ── Live fire check ──
        if county_lat and county_lon:
            st.divider()
            st.subheader("Nearest Active Fire (Live Check)")
            with st.spinner("Checking NASA FIRMS..."):
                fires = get_nearest_fire_distance(county_lat, county_lon)
            if fires:
                closest_km = fires[0][2]
                closest_mi = closest_km * 0.621
                if closest_mi < 10:
                    st.error(f"Active fire detected **{closest_mi:.1f} miles** from your county centroid — review evacuation status now.")
                elif closest_mi < 50:
                    st.warning(f"Active fire detected **{closest_mi:.1f} miles** from your county. Monitor conditions.")
                else:
                    st.success(f"Nearest active fire is **{closest_mi:.1f} miles** away. No immediate threat.")
            else:
                st.info("NASA FIRMS check unavailable — check firms.modaps.eosdis.nasa.gov directly.")

        st.caption(
            "Risk score uses CDC SVI, WiDS 2021–2025 real fire timing data, and FEMA evacuation time estimates. "
            "This tool provides guidance only. Always follow official evacuation orders."
        )