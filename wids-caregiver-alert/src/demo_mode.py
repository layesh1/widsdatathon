"""
demo_mode.py — Scripted conference demo state for WiDS 2025 presentation.

Usage in any page:
    from demo_mode import get_demo_state
    demo = get_demo_state() if st.session_state.get("demo_mode") else None
    county = demo["county"] if demo else real_county_value
"""


def get_demo_state() -> dict:
    """
    Returns a fixed scripted scenario dict for the Ventura County, CA demo.
    All values are historically plausible but are a constructed scenario for
    presentation purposes — they are not a live incident.
    """
    return {
        # Location / context
        "county":        "Ventura County, CA",
        "county_short":  "Ventura County",
        "state":         "California",
        "state_abbr":    "CA",
        "year":          2023,
        "incident_name": "Thomas Fire scenario — 12 miles from high-SVI tract",
        "lat":           34.3705,
        "lon":          -119.1391,

        # Fire characteristics
        "fire_size_acres":         842,
        "growth_rate_acres_per_hr": 14.2,
        "spread_rate_label":       "Rapid",
        "containment_pct":         0,

        # Vulnerability / population
        "svi_score":       0.82,
        "population_at_risk": 12_400,
        "is_vulnerable":   True,

        # Evacuation / shelter
        "nearest_shelter": "Ventura County Fairgrounds — 4.1 miles",
        "shelter_address": "10 W Harbor Blvd, Ventura, CA 93001",
        "shelter_distance_mi": 4.1,
        "shelter_ada": True,

        # Alert channel gap
        "channels_available":    ["WEA"],
        "channels_missing":      ["EAS"],
        "channel_gap_note":      "EAS not configured for this county — WEA only",
        "n_channels":            1,
        "channel_gap":           True,

        # Delay data for this county
        "historical_delay_hrs":  8.3,
        "county_median_delay":   8.3,
        "national_median_delay": 1.1,
        "delay_ratio":           round(8.3 / 1.1, 1),

        # Risk calculator outputs
        "risk_level":    "HIGH",
        "risk_score":    0.87,

        # Impact projection
        "additional_fires_alerted":      47,
        "additional_people_protected": 5_640,
        "pct_improvement":               32.0,
        "new_median_delay_hrs":           4.3,
    }


DEMO_BANNER_HTML = """
<div style="background:#d4a017; color:#000; padding:10px 16px; border-radius:8px;
            font-weight:600; margin-bottom:16px;">
🎬 DEMO MODE — Showing scripted scenario: Ventura County, CA wildfire event
</div>
"""


def render_demo_banner():
    """Call at the top of any page to inject the demo banner when demo mode is active."""
    import streamlit as st
    if st.session_state.get("demo_mode"):
        st.markdown(DEMO_BANNER_HTML, unsafe_allow_html=True)
