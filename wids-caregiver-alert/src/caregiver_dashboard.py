"""
caregiver_dashboard.py
Caregiver role: monitor evacuee's fire status, send evacuation alert.
Distinct from the evacuee — caregiver manages someone else's safety.
"""
import streamlit as st
from user_profile import (
    get_caregiver_evacuee, set_caregiver_evacuee,
    render_evacuee_setup, get_profile,
)


def _haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, sqrt, atan2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def render_caregiver_dashboard(fire_data=None):
    evacuee = get_caregiver_evacuee()

    # ── Setup: who is the caregiver caring for? ───────────────────────────────
    if not evacuee.get("address"):
        st.markdown("### Who are you caring for?")
        st.caption(
            "Add the person you care for to monitor fire risk near their home "
            "and send evacuation alerts when needed."
        )
        render_evacuee_setup()
        return

    name    = evacuee.get("name", "Your evacuee")
    address = evacuee.get("address", "")
    lat     = evacuee.get("lat")
    lon     = evacuee.get("lon")
    phone   = evacuee.get("phone", "")
    age     = evacuee.get("age_group", "")
    mob     = evacuee.get("mobility_limited", False)

    # Header
    col_h1, col_h2 = st.columns([5, 2])
    with col_h1:
        st.markdown(
            f"<div style='margin-bottom:4px'>"
            f"<span style='font-size:1.3rem;font-weight:700;color:#e6edf3'>Monitoring: {name}</span>"
            f"<span style='color:#8b949e;font-size:0.82rem;margin-left:10px'>{address}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_h2:
        if st.button("Edit evacuee info", key="caregiver_edit_evac"):
            set_caregiver_evacuee({})
            st.rerun()

    st.divider()

    # ── Fire status near evacuee ──────────────────────────────────────────────
    st.subheader(f"Fire status near {name}")

    nearby = []
    if lat and fire_data is not None and len(fire_data) > 0:
        try:
            for _, row in fire_data.iterrows():
                rlat = row.get("latitude") or row.get("lat")
                rlon = row.get("longitude") or row.get("lon")
                if rlat and rlon:
                    d = _haversine_km(lat, lon, float(rlat), float(rlon))
                    if d <= 80:
                        nearby.append({**row.to_dict(), "dist_km": round(d, 1)})
        except Exception:
            pass

    firms_nearby = []
    try:
        from nasa_firms_live import fetch_live_fires
        firms_df, _ = fetch_live_fires()
        if firms_df is not None and lat:
            firms_df = firms_df.copy()
            firms_df["dist_km"] = firms_df.apply(
                lambda r: _haversine_km(lat, lon, float(r["latitude"]), float(r["longitude"])), axis=1
            )
            firms_nearby = firms_df[firms_df["dist_km"] <= 80].sort_values("dist_km").head(3).to_dict("records")
    except Exception:
        pass

    all_nearby = nearby[:5] + firms_nearby[:3]
    fires_close = [f for f in all_nearby if f.get("dist_km", 999) < 30]

    if fires_close:
        closest_mi = round(min(f["dist_km"] for f in fires_close) * 0.621, 1)
        st.markdown(
            f"<div style='background:#FF4B4B22;border:2px solid #FF4B4B;border-radius:8px;"
            "padding:14px 18px;font-size:1.05rem;font-weight:700;color:#FF4B4B'>"
            f"Fire activity {closest_mi} miles from {name}. Consider alerting them now.</div>",
            unsafe_allow_html=True,
        )
    elif all_nearby:
        d_mi = round(min(f.get("dist_km", 50) for f in all_nearby) * 0.621, 1)
        st.markdown(
            f"<div style='background:#d4a01722;border:1px solid #d4a017;border-radius:8px;"
            f"padding:12px 16px;font-weight:600;color:#d4a017'>"
            f"Fire activity detected {d_mi} miles from {name}. Monitoring.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='background:#3fb95022;border:1px solid #3fb950;border-radius:8px;"
            f"padding:12px 16px;font-weight:600;color:#3fb950'>"
            f"No fires detected near {name} in the last 24 hours.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Send evacuation alert ─────────────────────────────────────────────────
    st.subheader(f"Send evacuation alert to {name}")

    risk_notes = []
    if mob:          risk_notes.append("mobility limitations")
    if age == "75+": risk_notes.append("age 75+")
    if not phone:    risk_notes.append("no phone on file — add it to enable SMS")

    if risk_notes:
        st.info(f"Note: {name} has {', '.join(risk_notes)}.")

    col_msg, col_btn = st.columns([4, 2])
    with col_msg:
        _default_msg = (
            f"EMERGENCY: A wildfire may be approaching your area. "
            f"Please begin evacuating now. Take medications, ID, and essentials. "
            f"Call 911 if you need transport assistance."
        )
        alert_msg = st.text_area(
            "Alert message",
            value=_default_msg,
            height=100,
            key="caregiver_alert_msg",
        )
    with col_btn:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        send_clicked = st.button(
            f"Send alert to {name}",
            type="primary",
            use_container_width=True,
            key="caregiver_send_alert_btn",
        )

    if send_clicked:
        if phone:
            try:
                from sms_alert import send_sms_alert
                send_sms_alert(phone, alert_msg)
                st.success(f"Alert sent to {name} at {phone}.")
            except Exception:
                st.warning(
                    f"SMS not configured (no Twilio credentials). "
                    f"Message ready to send manually: {phone}"
                )
        else:
            st.error(f"No phone number on file for {name}. Add it in 'Edit evacuee info'.")

    st.divider()

    # ── Evacuee's risk profile ────────────────────────────────────────────────
    st.subheader(f"{name}'s evacuation risk profile")

    risk_factors = []
    if age in ["65–74", "75+"]: risk_factors.append(f"Age {age}")
    if mob:                      risk_factors.append("Mobility limited")

    if risk_factors:
        risk_color = "#FF4B4B"
        st.markdown(
            f"<div style='background:#FF4B4B18;border:1px solid #FF4B4B33;border-radius:8px;"
            f"padding:12px 16px;color:#FF4B4B'>"
            f"<b>Elevated evacuation risk</b> — {', '.join(risk_factors)}.<br>"
            f"<span style='font-size:0.82rem;color:#8b949e'>"
            f"People with mobility limitations evacuate ~40% slower. "
            f"Early alerting is critical — do not wait for official orders.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='background:#3fb95018;border:1px solid #3fb95033;border-radius:8px;"
            f"padding:12px 16px;color:#3fb950'>"
            f"No high-risk demographic factors noted for {name}."
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Evacuee's quick plan ──────────────────────────────────────────────────
    st.subheader(f"Evacuation plan for {name}")
    st.markdown("**Steps to help them evacuate:**")
    steps = []
    if mob:
        steps.append(f"Arrange accessible transport for {name} before an official order")
    steps += [
        f"Ensure {name} has medications and medical supplies packed",
        f"Share their evacuation route with them (or drive them)",
        f"Have their emergency contacts list ready",
        f"Confirm shelter location and accessibility requirements",
    ]
    for i, s in enumerate(steps, 1):
        st.markdown(f"{i}. {s}")
