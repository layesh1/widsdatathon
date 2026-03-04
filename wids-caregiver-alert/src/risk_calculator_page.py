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
    from ui_utils import page_header, section_header, render_card

    page_header(
        "Personal Risk Calculator",
        "How much time would you actually have if a wildfire started nearby?  "
        "Uses CDC SVI, WiDS 2021-2025 fire timing, and FEMA evacuation estimates.",
    )

    # ── Hero row — 3 key benchmark cards ─────────────────────────────────────
    h1, h2, h3 = st.columns(3)
    with h1:
        render_card(
            "Median time to evacuation order",
            "1.1 hours",
            "Historical average for fires that received any official action (n=653)",
            "#d4a017",
        )
    with h2:
        render_card(
            "Fire growth in high-vulnerability counties",
            "+17% faster",
            "Fires spread faster in counties with fewer resources and more barriers",
            "#FF4B4B",
        )
    with h3:
        render_card(
            "Worst-case delay (90th percentile)",
            "32 hours",
            "1 in 10 fires gets no evacuation order for over a day",
            "#FF4B4B",
        )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── F-pattern layout: inputs LEFT (2/3), context RIGHT (1/3) ─────────────
    col_in, col_ctx = st.columns([2, 1])

    with col_in:
        section_header("Your location")
        county_choice = st.selectbox(
            "Select your county",
            list(HIGH_RISK_COUNTIES.keys()),
        )
        if county_choice == "Other (enter manually)":
            svi_manual = st.slider(
                "Your county CDC SVI score",
                0.0, 1.0, 0.5, step=0.01,
                help="Find at: cdc.gov/cdc-atsdr-gis/SVI/ — RPL_THEMES column",
            )
            lat_manual = st.number_input("Latitude (optional, for live fire check)", value=37.5)
            lon_manual = st.number_input("Longitude (optional)", value=-120.0)
            county_svi = svi_manual
            county_lat, county_lon = lat_manual, lon_manual
        else:
            info = HIGH_RISK_COUNTIES[county_choice]
            county_svi = info["svi"]
            county_lat, county_lon = info["lat"], info["lon"]

        section_header("Your situation")
        mobility = st.selectbox(
            "Mobility level",
            [
                ("mobile_adult",       "Fully mobile adult"),
                ("elderly_walking",    "Elderly / slow mobility"),
                ("disabled_caregiver", "Disabled, needs caregiver assistance"),
                ("no_vehicle",         "No personal vehicle"),
                ("medical_equipment",  "Medical equipment (O2, dialysis, etc.)"),
            ],
            format_func=lambda x: x[1],
        )
        mobility_key = mobility[0]

        ca, cb = st.columns(2)
        with ca:
            has_caregiver = st.radio(
                "Caregiver who could give early warning?",
                ["Yes, reliably", "Sometimes", "No"],
            )
            distance_to_wui = st.slider(
                "Miles from nearest wildland edge",
                0.5, 25.0, 3.0, step=0.5,
                help="WUI = Wildland-Urban Interface. Lower = higher risk.",
            )
        with cb:
            has_go_bag    = st.checkbox("Go-bag packed and ready")
            has_evac_plan = st.checkbox("Written evacuation plan with route")
            has_alerts_on = st.checkbox("Wireless Emergency Alerts enabled on phone")
            nearby_dependents = st.number_input(
                "Dependents needing help", 0, 10, 0,
            )
            pets_livestock = st.radio(
                "Pets or livestock?",
                ["None", "Small pets", "Large animals / livestock"],
            )

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        # Primary CTA — bottom of input column (Fitts's Law)
        calculate = st.button(
            "Calculate My Risk Profile",
            type="primary",
            use_container_width=True,
            key="calc_btn",
        )

    with col_ctx:
        section_header("What this means")
        st.markdown(
            f"The median time from fire ignition to an evacuation order is "
            f"**{MEDIAN_EVAC_ORDER_H}h**. In high-vulnerability counties, fires "
            f"grow **{(VULNERABLE_GROWTH_MULTIPLIER - 1) * 100:.0f}% faster** — "
            f"and 1 in 10 fires takes over **{P90_EVAC_ORDER_H:.0f} hours** to "
            f"get any official order."
        )
        st.markdown(
            "Higher SVI means fewer cars, less access to warnings, and more "
            "barriers to leaving quickly."
        )

        if county_choice != "Other (enter manually)":
            info = HIGH_RISK_COUNTIES[county_choice]
            svi_val = info.get("svi") or 0.0
            svi_color = (
                "#FF4B4B" if svi_val >= 0.75 else
                "#d4a017" if svi_val >= 0.5 else
                "#3fb950"
            )
            svi_label = (
                "High vulnerability" if svi_val >= 0.75 else
                "Moderate vulnerability" if svi_val >= 0.5 else
                "Lower vulnerability"
            )
            render_card(
                "County SVI score",
                f"{svi_val:.2f}",
                f"{svi_label} — percentile rank (0 = low, 1 = highest)",
                svi_color,
            )

            # Vulnerable population detail — progressive disclosure
            sub_themes = {
                "Socioeconomic": info.get("svi_socioeconomic"),
                "Household":     info.get("svi_household"),
                "Minority":      info.get("svi_minority"),
                "Housing":       info.get("svi_housing"),
            }
            pop_fields = {
                "Age 65+":      info.get("pop_age65"),
                "Disability":   info.get("pop_disability"),
                "Below poverty":info.get("pop_poverty"),
                "No vehicle":   info.get("pop_no_vehicle"),
            }
            with st.expander("County vulnerability detail"):
                if all(v is not None for v in sub_themes.values()):
                    primary_driver = max(sub_themes, key=lambda k: sub_themes[k])
                    max_val = max(sub_themes.values())
                    theme_colors = [
                        "#FF4B4B" if v == max_val else "#4a90d9"
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
                        title=f"SVI sub-themes — {county_choice}",
                        yaxis=dict(range=[0, 1.15], title="Percentile (0–1)"),
                        height=210,
                        margin=dict(l=10, r=10, t=44, b=10),
                    )
                    st.plotly_chart(fig_svi, use_container_width=True)
                    st.caption(
                        f"Primary driver: {primary_driver} ({sub_themes[primary_driver]:.2f}). "
                        "Minority status has the strongest correlation with evacuation delay (WiDS data)."
                    )
                if all(v is not None for v in pop_fields.values()):
                    pop_colors = ["#FF9800", "#4a90d9", "#FF4B4B", "#FFC107"]
                    fig_pop = go.Figure()
                    for (lbl, val), c in zip(pop_fields.items(), pop_colors):
                        fig_pop.add_trace(go.Bar(
                            name=lbl, x=[county_choice], y=[val],
                            marker_color=c, text=[f"{val:,}"], textposition="inside",
                        ))
                    fig_pop.update_layout(
                        template="plotly_dark", barmode="stack",
                        title="Vulnerable population",
                        yaxis_title="Persons",
                        height=190,
                        margin=dict(l=10, r=10, t=40, b=10),
                        legend=dict(orientation="h", y=-0.35),
                    )
                    st.plotly_chart(fig_pop, use_container_width=True)

    # ── Calculation ───────────────────────────────────────────────────────────
    if calculate:
        evac_times    = EVAC_TIME_ESTIMATES[mobility_key]
        dependent_add = nearby_dependents * 0.25
        pet_add       = 0.25 if "Large" in pets_livestock else (0.15 if "Small" in pets_livestock else 0)
        no_bag_add    = 0.5  if not has_go_bag   else 0
        no_plan_add   = 0.25 if not has_evac_plan else 0
        total_evac_time = evac_times["total"] + dependent_add + pet_add + no_bag_add + no_plan_add

        caregiver_lead      = {"Yes, reliably": 0.75, "Sometimes": 0.30, "No": 0.0}[has_caregiver]
        official_order_time = MEDIAN_EVAC_ORDER_H * (VULNERABLE_GROWTH_MULTIPLIER if county_svi >= 0.75 else 1.0)
        time_available      = caregiver_lead + official_order_time
        net_buffer          = time_available - total_evac_time

        risk_score = min(0.98, (
            (county_svi * 0.30) +
            (min(1.0, total_evac_time / 4) * 0.25) +
            ((1 - min(1.0, distance_to_wui / 10)) * 0.20) +
            ((0 if has_alerts_on else 0.1) +
             (0 if has_evac_plan else 0.1) +
             (0 if has_go_bag else 0.05)) +
            (min(1.0, nearby_dependents / 4) * 0.10)
        ))
        label, color = score_to_label(risk_score)

        st.session_state.risk_calculated = True
        st.session_state.risk_results = dict(
            risk_score=risk_score, label=label, color=color,
            total_evac_time=total_evac_time,
            official_order_time=official_order_time,
            net_buffer=net_buffer,
            caregiver_lead=caregiver_lead,
            county_svi=county_svi, county_lat=county_lat, county_lon=county_lon,
            county_choice=county_choice,
            has_go_bag=has_go_bag, has_evac_plan=has_evac_plan,
            has_alerts_on=has_alerts_on, has_caregiver=has_caregiver,
            nearby_dependents=nearby_dependents, pets_livestock=pets_livestock,
            distance_to_wui=distance_to_wui,
            evac_times=evac_times, no_bag_add=no_bag_add, no_plan_add=no_plan_add,
            dependent_add=dependent_add,
        )

    # ── Results section — shown whenever results are in session_state ─────────
    if st.session_state.get("risk_calculated"):
        from ui_utils import section_header as _sh
        res = st.session_state.risk_results

        st.divider()
        _sh("Your risk profile")

        # F-pattern: risk badge LEFT, timeline chart RIGHT
        res_l, res_r = st.columns([1, 1])

        with res_l:
            render_card(
                f"Overall risk — {res['label']}",
                f"{res['risk_score'] * 100:.0f} / 100",
                "Based on county SVI, mobility situation, and preparation level",
                res["color"],
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Time to evacuate",   f"{res['total_evac_time']:.1f}h")
            c2.metric("Expected warning",   f"{res['official_order_time']:.1f}h")
            c3.metric(
                "Safety buffer",
                f"{res['net_buffer']:+.1f}h",
                delta="Adequate" if res["net_buffer"] > 0 else "Insufficient",
                delta_color="normal" if res["net_buffer"] > 0 else "inverse",
            )

        with res_r:
            et = res["evac_times"]
            events = [
                ("Fire ignition",                  0),
                ("Caregiver alert (if enrolled)",  res["caregiver_lead"]),
                ("Official order (median)",        res["official_order_time"]),
                ("You complete evacuation",
                 res["official_order_time"] + et["total"] + res["no_bag_add"] + res["no_plan_add"]),
            ]
            fig_tl = go.Figure()
            for i, (ev, t) in enumerate(events):
                dot_c = "#FF4B4B" if t > res["official_order_time"] else (
                    "#d4a017" if t > 0 else "#8b949e"
                )
                fig_tl.add_trace(go.Scatter(
                    x=[t], y=[i],
                    mode="markers+text",
                    marker=dict(size=14, color=dot_c),
                    text=[ev], textposition="middle right", showlegend=False,
                ))
            fig_tl.add_vrect(
                x0=0, x1=res["official_order_time"],
                fillcolor="rgba(212,160,23,0.08)", line_width=0,
                annotation_text="Pre-order window", annotation_position="top left",
            )
            fig_tl.update_layout(
                template="plotly_dark",
                xaxis_title="Hours from ignition",
                yaxis=dict(showticklabels=False, showgrid=False),
                height=240,
                margin=dict(l=20, r=160, t=10, b=30),
            )
            st.plotly_chart(fig_tl, use_container_width=True)

        # Recommendations — progressive disclosure
        recs = []
        if not res["has_go_bag"]:
            recs.append("Pack a go-bag — saves ~30 min at evacuation. Include medications, documents, 3 days of clothes.")
        if not res["has_evac_plan"]:
            recs.append("Write a route plan — identify 2 routes to the nearest shelter. Saves ~15 min of decision time.")
        if not res["has_alerts_on"]:
            recs.append("Enable Wireless Emergency Alerts in your phone settings. Free, no app needed.")
        if res["has_caregiver"] == "No" and res["county_svi"] >= 0.75:
            recs.append("Enroll in a caregiver network — high-SVI fires grow 17% faster; a caregiver alert adds ~45 min.")
        if res["nearby_dependents"] > 0:
            extra = res["dependent_add"] * 60
            recs.append(f"Your {res['nearby_dependents']} dependent(s) add ~{extra:.0f} min. Start packing earlier than your official threshold.")
        if "Large" in res["pets_livestock"]:
            recs.append("Pre-arrange livestock transport — large animals need a trailer. Identify a neighbor or service now.")
        if res["net_buffer"] < 0:
            recs.append("Your evacuation takes longer than typical warning time. Ensure you have caregiver alert enrollment.")
        if res["distance_to_wui"] < 1.0:
            recs.append("You live within 1 mile of wildland (WUI). Apply ember-resistant vents and clear 100ft of defensible space.")

        if recs:
            with st.expander("Your action recommendations", expanded=True):
                for rec in recs:
                    st.markdown(f"- {rec}")
        else:
            st.success(
                "Preparation level is solid. Keep your go-bag updated seasonally "
                "and review your route plan annually."
            )

        # Live fire check — progressive disclosure
        if res.get("county_lat") and res.get("county_lon"):
            with st.expander("Check for nearby active fires (live NASA FIRMS)"):
                with st.spinner("Checking NASA FIRMS..."):
                    fires = get_nearest_fire_distance(res["county_lat"], res["county_lon"])
                if fires:
                    closest_mi = fires[0][2] * 0.621
                    if closest_mi < 10:
                        st.error(f"Active fire detected {closest_mi:.1f} miles from your county. Review evacuation status now.")
                    elif closest_mi < 50:
                        st.warning(f"Active fire detected {closest_mi:.1f} miles away. Monitor conditions.")
                    else:
                        st.success(f"Nearest active fire is {closest_mi:.1f} miles away. No immediate threat.")
                else:
                    st.info("NASA FIRMS check unavailable. Check firms.modaps.eosdis.nasa.gov directly.")

        st.caption(
            "Risk score uses CDC SVI, WiDS 2021-2025 real fire timing data, and FEMA evacuation time estimates. "
            "Guidance only — always follow official evacuation orders."
        )

        # CTA at page bottom — Fitts's Law (thumb zone)
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(
            "Build My Evacuation Plan",
            type="primary",
            use_container_width=True,
            key="risk_to_plan_cta",
        ):
            st.session_state.current_page = "Evacuation Plan"
            st.rerun()