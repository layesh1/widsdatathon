"""
home_page.py — Landing/splash screen for the WiDS Wildfire Caregiver Alert System.

Shown when st.session_state.get("show_home") is not False.
The role buttons set st.session_state.role and dismiss this screen.
"""

import streamlit as st


_HOME_CSS = """
<style>
.home-hero {
    text-align: center;
    padding: 2rem 1rem 1.5rem 1rem;
}
.home-headline {
    font-size: clamp(14px, 2vw, 18px);
    color: #8892a4;
    font-weight: 400;
    margin-bottom: 0.5rem;
}
.home-stat-big {
    font-size: clamp(48px, 8vw, 72px);
    font-weight: 800;
    color: #FF4B4B;
    line-height: 1.05;
    margin: 0.25rem 0;
    letter-spacing: -1px;
}
.home-subline {
    font-size: clamp(14px, 2vw, 18px);
    color: #8892a4;
    font-weight: 400;
    margin-top: 0.5rem;
}
.home-scope {
    font-size: 0.8rem;
    color: #555f6d;
    margin-top: 0.75rem;
}
.home-kpi-grid {
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
    margin: 1.5rem 0 1.75rem 0;
}
.home-kpi {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 18px 22px;
    min-width: 130px;
    text-align: center;
}
.home-kpi-value {
    font-size: 1.7rem;
    font-weight: 800;
    color: #FF4B4B;
    line-height: 1.1;
}
.home-kpi-label {
    font-size: 0.72rem;
    color: #8892a4;
    margin-top: 4px;
    line-height: 1.3;
}
.home-divider {
    border: none;
    border-top: 1px solid #30363d;
    margin: 1rem 0;
}
</style>
"""


def render_home_page():
    """
    Renders the full-page landing/splash screen.
    Returns True if the user picked a role and the caller should st.rerun().
    """
    st.markdown(_HOME_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
<div class="home-hero">
  <div style="font-size:2rem;font-weight:800;color:#e6edf3;margin-bottom:0.15rem;">
    🔥 Wildfire Caregiver Alert System
  </div>
  <div style="font-size:0.85rem;color:#555f6d;margin-bottom:2rem;">
    49ers Intelligence Lab &nbsp;·&nbsp; WiDS Datathon 2025
  </div>

  <div class="home-headline">In high-vulnerability counties, evacuation orders arrive</div>
  <div class="home-stat-big">11.5 HOURS LATER</div>
  <div class="home-subline">than in low-vulnerability counties.</div>
  <div class="home-scope">Across 62,696 wildfires &nbsp;·&nbsp; 2021–2025</div>
</div>
""", unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    st.markdown("""
<div class="home-kpi-grid">
  <div class="home-kpi">
    <div class="home-kpi-value">62,696</div>
    <div class="home-kpi-label">fires analyzed</div>
  </div>
  <div class="home-kpi">
    <div class="home-kpi-value">653</div>
    <div class="home-kpi-label">with confirmed evacuation actions</div>
  </div>
  <div class="home-kpi">
    <div class="home-kpi-value">39.8%</div>
    <div class="home-kpi-label">high-SVI events (vulnerable counties)</div>
  </div>
  <div class="home-kpi">
    <div class="home-kpi-value" style="color:#d4a017;">9×</div>
    <div class="home-kpi-label">disparity ratio vs. low-SVI counties</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<hr class="home-divider">', unsafe_allow_html=True)

    # ── Role buttons ──────────────────────────────────────────────────────────
    st.markdown(
        "<div style='text-align:center;color:#8892a4;font-size:0.82rem;"
        "margin-bottom:0.75rem;'>Enter the dashboard as:</div>",
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        if st.button(
            "🏃 Enter as Caregiver / Evacuee",
            key="home_role_caregiver",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.role = "Caregiver/Evacuee"
            st.session_state.show_home = False
            st.session_state.onboarded = True
            st.session_state.current_page = "Am I Safe?"
            st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        if st.button(
            "🚨 Enter as Emergency Responder",
            key="home_role_responder",
            use_container_width=True,
        ):
            st.session_state.role = "Emergency Worker"
            st.session_state.show_home = False
            st.session_state.onboarded = True
            st.session_state.current_page = "Command"
            st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        if st.button(
            "📊 Enter as Data Analyst",
            key="home_role_analyst",
            use_container_width=True,
        ):
            st.session_state.role = "Data Analyst"
            st.session_state.show_home = False
            st.session_state.onboarded = True
            st.session_state.current_page = "Overview"
            st.rerun()

    st.markdown(
        "<div style='text-align:center;font-size:0.7rem;color:#555f6d;"
        "margin-top:1.25rem;'>Your login role is used by default. "
        "Selecting here overrides it for this session.</div>",
        unsafe_allow_html=True,
    )
