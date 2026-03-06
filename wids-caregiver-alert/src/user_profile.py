"""
user_profile.py
Shared user profile store: address + demographics.
One address entered → all pages (Am I Safe, Plan, Risk) auto-populated.
Supports both Evacuee and Caregiver roles.
"""
import streamlit as st
from typing import Optional

PROFILE_KEY = "user_profile"
CAREGIVER_EVACUEE_KEY = "caregiver_evacuee"

_RISK_MULTIPLIERS = {
    "age_75_plus":         1.30,
    "age_65_74":           1.15,
    "mobility_limited":    1.40,
    "no_vehicle":          1.35,
    "medical_equipment":   1.50,
    "solo_household":      1.20,
    "hearing_disability":  1.10,
    "cognitive_disability":1.20,
}


def get_profile() -> dict:
    return st.session_state.get(PROFILE_KEY, {})


def set_profile(data: dict):
    st.session_state[PROFILE_KEY] = data


def profile_complete() -> bool:
    p = get_profile()
    return bool(p.get("address") and p.get("lat"))


def get_risk_multiplier() -> float:
    """Compute cumulative risk multiplier from demographics."""
    p = get_profile()
    if not p:
        return 1.0
    m = 1.0
    age = p.get("age_group", "")
    if age == "75+":         m *= _RISK_MULTIPLIERS["age_75_plus"]
    elif age == "65–74":     m *= _RISK_MULTIPLIERS["age_65_74"]
    if p.get("mobility_limited"):  m *= _RISK_MULTIPLIERS["mobility_limited"]
    if p.get("vehicles", 1) == 0:  m *= _RISK_MULTIPLIERS["no_vehicle"]
    if p.get("medical_equipment"): m *= _RISK_MULTIPLIERS["medical_equipment"]
    if p.get("household_size", 2) == 1: m *= _RISK_MULTIPLIERS["solo_household"]
    disabilities = p.get("disabilities", [])
    if "Hearing" in disabilities:   m *= _RISK_MULTIPLIERS["hearing_disability"]
    if "Cognitive" in disabilities: m *= _RISK_MULTIPLIERS["cognitive_disability"]
    return round(m, 3)


def render_profile_setup(role: str = "Evacuee"):
    """
    Full-page profile setup: address + demographics.
    Shows a Skip button for emergency use.
    Returns True when profile is saved or skipped.
    """
    from address_utils import render_address_input

    st.markdown("""
<style>
.profile-header { font-size:1.5rem; font-weight:700; margin-bottom:0.25rem; }
.profile-sub { color:#8b949e; font-size:0.9rem; margin-bottom:1.5rem; }
.demo-callout {
    background:#161b22; border:1px solid #30363d; border-radius:8px;
    padding:14px 18px; margin-bottom:1rem;
    display:flex; gap:12px; align-items:flex-start;
}
</style>
""", unsafe_allow_html=True)

    st.markdown(f'<div class="profile-header">Set up your profile</div>', unsafe_allow_html=True)

    role_context = {
        "Evacuee": "We'll use your location and household details to give you an instant, personalized fire risk score and evacuation plan — no repeated address entry.",
        "Caregiver": "Set up your profile once. Then add the person you care for so you can monitor their area and send alerts if needed.",
    }.get(role, "")
    st.markdown(f'<div class="profile-sub">{role_context}</div>', unsafe_allow_html=True)

    # Emergency skip
    col_skip, col_info = st.columns([2, 5])
    with col_skip:
        if st.button("In an emergency? Skip setup", key="profile_skip_btn"):
            st.session_state.profile_skipped = True
            st.session_state.onboarded = True
            st.rerun()
    with col_info:
        st.caption("You can complete your profile anytime from the sidebar.")

    st.divider()

    # Step 1: Location
    st.markdown("**Step 1 — Your location**")
    addr, lat, lon = render_address_input(
        label="Your home address",
        key="profile_addr",
        placeholder="e.g. 1234 Oak St, Los Angeles, CA",
        help_text="Type your address — suggestions appear as you type",
    )

    # Manual fallback geocode
    if addr and lat is None:
        try:
            from caregiver_start_page import geocode_address
            with st.spinner("Finding your location..."):
                lat, lon, addr = geocode_address(addr)
        except Exception:
            pass

    if lat:
        st.success(f"Location found: {addr}")

    st.divider()

    # Step 2: Demographics
    st.markdown("**Step 2 — Household & health (used only to calculate your risk level)**")

    col1, col2, col3 = st.columns(3)
    with col1:
        age_group = st.selectbox(
            "Age group",
            ["Under 18", "18–64", "65–74", "75+"],
            index=1,
            key="profile_age",
        )
        household_size = st.selectbox(
            "People in your household",
            [1, 2, 3, 4, 5],
            index=1,
            key="profile_household",
        )
    with col2:
        vehicles = st.selectbox(
            "Vehicles available for evacuation",
            [0, 1, 2, 3],
            index=1,
            key="profile_vehicles",
        )
        mobility_limited = st.checkbox(
            "Mobility limitations (wheelchair, walker, limited movement)",
            key="profile_mobility",
        )
    with col3:
        disabilities = st.multiselect(
            "Disabilities (select all that apply)",
            ["Visual", "Hearing", "Cognitive", "Physical"],
            key="profile_disabilities",
        )
        medical_equipment = st.checkbox(
            "Medical equipment needed (oxygen, dialysis, etc.)",
            key="profile_medical",
        )

    language = st.selectbox(
        "Primary language",
        ["English", "Spanish", "Chinese (Mandarin)", "Tagalog", "Vietnamese",
         "Arabic", "Korean", "Russian", "Portuguese", "French"],
        key="profile_language",
    )

    st.divider()

    # Save button
    if st.button("Save profile and continue", type="primary",
                 disabled=(not addr), key="profile_save_btn"):
        set_profile({
            "address":        addr,
            "lat":            lat,
            "lon":            lon,
            "age_group":      age_group,
            "household_size": household_size,
            "vehicles":       vehicles,
            "mobility_limited": mobility_limited,
            "disabilities":   disabilities,
            "medical_equipment": medical_equipment,
            "language":       language,
        })
        st.session_state.onboarded = True
        st.session_state.profile_skipped = False
        st.rerun()

    if not addr:
        st.caption("Enter your address above to continue.")


# ---------------------------------------------------------------------------
# Caregiver: evacuee management (person they are caring for)
# ---------------------------------------------------------------------------

def get_caregiver_evacuee() -> dict:
    return st.session_state.get(CAREGIVER_EVACUEE_KEY, {})


def set_caregiver_evacuee(data: dict):
    st.session_state[CAREGIVER_EVACUEE_KEY] = data


def render_evacuee_setup():
    """
    Caregiver enters information about the person they are caring for.
    Rendered once during caregiver onboarding.
    """
    from address_utils import render_address_input

    st.markdown("**Who are you caring for?**")
    st.caption("Their address and health details let you monitor their fire risk and send evacuation alerts.")

    col1, col2 = st.columns(2)
    with col1:
        evacuee_name = st.text_input(
            "Their name (first name or nickname)",
            key="evacuee_name",
            placeholder="e.g. Mom",
        )
        evacuee_phone = st.text_input(
            "Their phone number (for SMS alerts)",
            key="evacuee_phone",
            placeholder="+1 (555) 000-0000",
        )
    with col2:
        evacuee_age = st.selectbox(
            "Their age group",
            ["Under 18", "18–64", "65–74", "75+"],
            index=2,
            key="evacuee_age",
        )
        evacuee_mobility = st.checkbox(
            "Mobility limitations",
            key="evacuee_mobility",
        )

    addr, lat, lon = render_address_input(
        label="Their home address",
        key="evacuee_addr",
        placeholder="e.g. 5670 Mulholland Dr, Los Angeles, CA",
        help_text="Type their address to see fire risk near them",
    )

    if addr and lat is None:
        try:
            from caregiver_start_page import geocode_address
            with st.spinner("Finding location..."):
                lat, lon, addr = geocode_address(addr)
        except Exception:
            pass

    if lat:
        st.success(f"Found: {addr}")

    if st.button("Save evacuee info", type="primary",
                 disabled=(not evacuee_name or not addr), key="evacuee_save_btn"):
        set_caregiver_evacuee({
            "name":           evacuee_name,
            "phone":          evacuee_phone,
            "age_group":      evacuee_age,
            "mobility_limited": evacuee_mobility,
            "address":        addr,
            "lat":            lat,
            "lon":            lon,
        })
        st.rerun()
