"""
dispatcher_risk_zones_page.py — At-Risk Zones (Emergency Worker view)
Wraps Hotspot Map (Gi*) and County Drill-Down in dispatcher-framed context.
"""
import streamlit as st


def render_dispatcher_risk_zones_page():
    st.title("⚠️ At-Risk Zones")
    st.caption("Where are vulnerable residents most concentrated — and least protected?")

    st.info(
        "This view combines **statistical hotspot analysis** (Getis-Ord Gi*) with "
        "**county-level drill-down** to help dispatchers identify where to prioritize "
        "evacuation resources. High-risk zones are counties with both high silent fire rates "
        "AND high social vulnerability."
    )

    t1, t2 = st.tabs(["🗺️ Hotspot Map", "🔍 County Details"])

    with t1:
        from hotspot_map_page import render_hotspot_map_page
        render_hotspot_map_page()

    with t2:
        from county_drilldown_page import render_county_drilldown_page
        render_county_drilldown_page()
