"""
evacuee_dashboard.py
Unified single-page view for evacuees.
Uses shared user_profile — no repeated address entry.
Shows: fire status + risk level (with demographics) + evacuation plan.
"""
import streamlit as st
import pandas as pd
from user_profile import get_profile, get_risk_multiplier, profile_complete


def _haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, sqrt, atan2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def render_evacuee_dashboard(fire_data=None):
    p = get_profile()

    # ── Profile incomplete ────────────────────────────────────────────────────
    if not p.get("lat"):
        st.info("Your location isn't set yet. Complete your profile to see personalized results.")
        from address_utils import render_address_input
        from user_profile import set_profile
        addr, lat, lon = render_address_input(
            label="Enter your address to get started",
            key="evac_dash_addr",
            placeholder="e.g. 1234 Oak St, Los Angeles, CA",
        )
        if addr and lat:
            existing = {**p, "address": addr, "lat": lat, "lon": lon}
            set_profile(existing)
            st.rerun()
        return

    address   = p.get("address", "")
    lat, lon  = p["lat"], p["lon"]
    risk_mult = get_risk_multiplier()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-size:0.82rem;color:#8b949e;margin-bottom:4px'>"
        f"Monitoring: <b style='color:#e6edf3'>{address}</b> &nbsp;"
        f"<a href='?edit_profile=1' style='color:#FF4B4B;font-size:0.76rem'>Edit location</a></div>",
        unsafe_allow_html=True,
    )

    # Handle profile edit link
    if st.query_params.get("edit_profile") == "1":
        from user_profile import set_profile
        set_profile({})
        st.session_state.onboarded = None
        st.query_params.clear()
        st.rerun()

    # ── Section 1: Am I Safe? ─────────────────────────────────────────────────
    st.subheader("Fire Status Near You")

    nearby_fires = []
    if fire_data is not None and len(fire_data) > 0:
        try:
            for _, row in fire_data.iterrows():
                rlat = row.get("latitude") or row.get("lat")
                rlon = row.get("longitude") or row.get("lon")
                if rlat and rlon:
                    d = _haversine_km(lat, lon, float(rlat), float(rlon))
                    if d <= 80:
                        nearby_fires.append({**row.to_dict(), "dist_km": round(d, 1)})
        except Exception:
            pass

    # Also try NASA FIRMS
    firms_nearby = []
    try:
        from nasa_firms_live import fetch_live_fires
        firms_df, src = fetch_live_fires()
        if firms_df is not None and len(firms_df) > 0:
            firms_df = firms_df.copy()
            firms_df["dist_km"] = firms_df.apply(
                lambda r: _haversine_km(lat, lon, float(r["latitude"]), float(r["longitude"])), axis=1
            )
            firms_nearby = firms_df[firms_df["dist_km"] <= 80].sort_values("dist_km").head(3).to_dict("records")
    except Exception:
        pass

    all_nearby = nearby_fires[:5] + firms_nearby[:3]

    if not all_nearby:
        st.markdown(
            "<div style='background:#3fb95022;border:1px solid #3fb950;border-radius:8px;"
            "padding:14px 18px;font-size:1rem;font-weight:600;color:#3fb950'>"
            "No active fires detected within 50 miles of your location.</div>",
            unsafe_allow_html=True,
        )
    else:
        closest = min(all_nearby, key=lambda x: x.get("dist_km", 999))
        d_km = closest.get("dist_km", 0)
        d_mi = round(d_km * 0.621, 1)
        danger_color = "#FF4B4B" if d_km < 20 else "#d4a017" if d_km < 50 else "#FF9800"
        st.markdown(
            f"<div style='background:{danger_color}22;border:1.5px solid {danger_color};"
            "border-radius:8px;padding:14px 18px;font-size:1rem;font-weight:600;"
            f"color:{danger_color}'>Fire activity detected {d_mi} miles from your location. "
            "Check official evacuation orders for your zone.</div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"Nearby incidents ({len(all_nearby)} within 50 mi)"):
            for f in sorted(all_nearby, key=lambda x: x.get("dist_km", 999)):
                name = f.get("name") or f.get("geo_event_type") or "Fire incident"
                st.markdown(f"- **{name}** — {f.get('dist_km', '?')} km away")

    # ── Section 2: Your Risk Level ────────────────────────────────────────────
    st.divider()
    st.subheader("Your Personal Risk Level")

    # Base risk from SVI (try to look up county SVI from fire data)
    base_risk = 0.45  # default moderate
    county = p.get("county", "")

    # Apply demographic multiplier
    adjusted_risk = min(1.0, base_risk * risk_mult)
    risk_pct = round(adjusted_risk * 100)

    if risk_pct >= 70:
        risk_label, risk_color = "High Risk", "#FF4B4B"
    elif risk_pct >= 45:
        risk_label, risk_color = "Moderate Risk", "#d4a017"
    else:
        risk_label, risk_color = "Lower Risk", "#3fb950"

    col_risk, col_factors = st.columns([2, 3])
    with col_risk:
        st.markdown(
            f"<div style='background:{risk_color}18;border:2px solid {risk_color};"
            f"border-radius:12px;padding:20px;text-align:center'>"
            f"<div style='font-size:2.5rem;font-weight:800;color:{risk_color}'>{risk_pct}%</div>"
            f"<div style='font-size:1rem;font-weight:600;color:{risk_color}'>{risk_label}</div>"
            f"<div style='font-size:0.75rem;color:#8b949e;margin-top:6px'>Evacuation vulnerability score</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_factors:
        st.markdown("**What affects your score:**")
        p_age = p.get("age_group", "18–64")
        p_mob = p.get("mobility_limited", False)
        p_veh = p.get("vehicles", 1)
        p_med = p.get("medical_equipment", False)
        factors = [
            ("Age group", p_age,
             "75+ adds +30% risk; 65–74 adds +15%" if p_age in ["75+", "65–74"] else "Age is not a significant risk factor in your group"),
            ("Mobility", "Limited — higher risk" if p_mob else "No limitations",
             "Mobility limitations increase evacuation time by ~40% (CDC/FEMA)" if p_mob else ""),
            ("Vehicles", f"{p_veh} available",
             "No vehicle significantly raises evacuation risk — consider arranging transport" if p_veh == 0 else ""),
            ("Medical equipment", "Yes — needs planning" if p_med else "None",
             "Equipment-dependent evacuees need extra lead time to arrange transport" if p_med else ""),
        ]
        for factor, value, tip in factors:
            icon = "⚠" if ("risk" in tip.lower() or "higher" in value.lower() or "limited" in value.lower()
                           or "no vehicle" in value.lower() or "needs" in value.lower()) else "✓"
            color = "#d4a017" if icon == "⚠" else "#3fb950"
            st.markdown(
                f"<div style='display:flex;gap:8px;margin-bottom:4px'>"
                f"<span style='color:{color};font-weight:700'>{icon}</span>"
                f"<span><b>{factor}:</b> {value}"
                + (f"<br><span style='font-size:0.77rem;color:#8b949e'>{tip}</span>" if tip else "")
                + "</span></div>",
                unsafe_allow_html=True,
            )

    if risk_mult > 1.2:
        st.warning(
            f"Your demographic profile raises your evacuation vulnerability by "
            f"{round((risk_mult - 1) * 100)}%. We recommend completing your evacuation "
            f"plan and sharing it with your caregiver or family now."
        )

    # ── Section 3: Evacuation Plan ────────────────────────────────────────────
    st.divider()
    st.subheader("Your Evacuation Plan")
    st.caption(f"Based on your address: {address}")

    # Determine zone tier from risk
    zone_label = "A" if risk_pct >= 70 else "B" if risk_pct >= 45 else "C"

    col_plan1, col_plan2 = st.columns(2)
    with col_plan1:
        st.markdown(f"**Your zone:** Zone {zone_label}")
        st.markdown("**Immediate steps if an order is issued:**")
        steps = []
        if p_med:
            steps.insert(0, "Pack medical equipment first (oxygen, medications, supplies)")
        if p_mob:
            steps.append("Arrange accessible transportation now — do not wait for official order")
        if p_veh == 0:
            steps.append("Contact your county's emergency transport line or a caregiver")
        steps += [
            "Take ID, medications, phone charger, 3 days of clothes",
            "Lock your home and turn off utilities",
            f"Head to your nearest shelter (see map below)",
        ]
        for i, s in enumerate(steps, 1):
            st.markdown(f"{i}. {s}")

    with col_plan2:
        st.markdown("**Go-bag checklist:**")
        checklist_items = [
            "Medications (7-day supply)",
            "Photo ID and insurance cards",
            "Phone + charger + portable battery",
            "Cash (small bills)",
            "3 days of water and food",
            "N95 masks",
            "Flashlight and batteries",
            "Copies of important documents",
        ]
        if p_med:
            checklist_items.insert(0, "Medical equipment + supplies")
        if p.get("household_size", 2) > 1:
            checklist_items.append("Items for all household members")
        for item in checklist_items:
            st.checkbox(item, key=f"checklist_{item[:20]}")

    # PDF download
    try:
        from pdf_export import generate_evacuation_plan, REPORTLAB_AVAILABLE
        if REPORTLAB_AVAILABLE:
            _pdf = generate_evacuation_plan(
                county=county or address,
                risk_level=risk_label,
                household={"size": p.get("household_size", 1),
                           "mobility": p_mob,
                           "medical": p_med},
                checklist_items=checklist_items,
            )
            st.download_button(
                "Download your evacuation plan (PDF)",
                data=_pdf,
                file_name="my_evacuation_plan.pdf",
                mime="application/pdf",
                type="primary",
            )
    except Exception:
        pass
