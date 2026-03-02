"""
wildfire_alert_dashboard.py — 49ers Intelligence Lab · WiDS 2025
Main entry point. Wires all page modules together.
"""

import streamlit as st
from live_incident_feed import load_fire_data

st.set_page_config(
    page_title="49ers Intelligence Lab — WiDS 2025",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth ──────────────────────────────────────────────────────────────────────
CREDENTIALS = {
    "dispatcher": {"password": "fire2025", "role": "Emergency Worker"},
    "caregiver":  {"password": "evacuate", "role": "Caregiver/Evacuee"},
    "analyst":    {"password": "datathon", "role": "Data Analyst"},
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role          = None
    st.session_state.username      = None

if not st.session_state.authenticated:
    st.title("🔥 49ers Intelligence Lab — WiDS 2025")
    st.subheader("Wildfire Caregiver Alert System")
    col_login, _ = st.columns([1, 2])
    with col_login:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Sign In", type="primary"):
            if username in CREDENTIALS and CREDENTIALS[username]["password"] == password:
                st.session_state.authenticated = True
                st.session_state.role          = CREDENTIALS[username]["role"]
                st.session_state.username      = username
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.caption("dispatcher / fire2025 · caregiver / evacuate · analyst / datathon")
    st.stop()

role     = st.session_state.role
username = st.session_state.username

# ── Load fire data once (cached 5 min) ───────────────────────────────────────
fire_data, fire_source, fire_label = load_fire_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:10px 0 6px 0;">
        <div style="font-size:2rem">🔥</div>
        <div style="font-weight:700;font-size:0.95rem;color:#FF6347;">49ers Intelligence Lab</div>
        <div style="font-size:0.7rem;color:#888;">WiDS Datathon 2025</div>
    </div>
    """, unsafe_allow_html=True)

    role_colors = {"Emergency Worker": "#FF6347", "Caregiver/Evacuee": "#4a90d9", "Data Analyst": "#9b59b6"}
    st.markdown(
        f"<div style='text-align:center;color:{role_colors[role]};font-weight:600;"
        f"font-size:0.85rem;padding:2px 0;'>{role}</div>"
        f"<div style='text-align:center;color:#888;font-size:0.75rem;margin-bottom:8px;'>"
        f"Logged in as: {username}</div>",
        unsafe_allow_html=True
    )
    st.divider()

    n_fires = len(fire_data)
    st.markdown(
        f"**Incident Feed:** {fire_label}  \n"
        f"{'— ' + str(n_fires) + ' US hotspots (24h)' if n_fires > 0 else '— Checking...'}",
        help="🟢=WiDS local · 🟡=NASA FIRMS live · ⚪=unavailable"
    )
    st.divider()

    # Navigation
    if role == "Emergency Worker":
        pages = ["Command Dashboard", "Fire Predictor", "AI Assistant"]
    elif role == "Caregiver/Evacuee":
        pages = ["Start Here", "Evacuation Planner", "Safe Routes & Transit", "AI Assistant"]
    else:
        pages = ["Dashboard", "Equity Analysis", "Risk Calculator", "Impact Projection",
                 "Coverage Analysis", "Zone Duration", "Fire Predictor", "AI Assistant", "About"]

    if "current_page" not in st.session_state or st.session_state.current_page not in pages:
        st.session_state.current_page = pages[0]

    for page in pages:
        active = st.session_state.current_page == page
        if st.button(page, key=f"nav_{page}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.current_page = page
            st.rerun()

    st.divider()
    if st.button("Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ── Page router ───────────────────────────────────────────────────────────────
page = st.session_state.current_page

if page == "Command Dashboard":
    from command_dashboard_page import render_command_dashboard
    render_command_dashboard(fire_data, fire_source, fire_label)

elif page == "Start Here":
    from caregiver_start_page import render_caregiver_start_page
    render_caregiver_start_page()

elif page == "Evacuation Planner":
    try:
        from evacuation_planner_page import render_evacuation_planner_page
        render_evacuation_planner_page(fire_data=fire_data)
    except ImportError as e:
        st.error(f"Evacuation Planner module not found: {e}")

elif page == "Safe Routes & Transit":
    try:
        from directions_page import render_directions_page
        render_directions_page()
    except ImportError as e:
        st.error(f"Safe Routes module not found: {e}")

elif page == "Dashboard":
    st.title("📊 Analytics Dashboard")
    st.caption(f"Data Analyst View · {fire_label} · WiDS 2021–2025")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fire Events Analyzed", "62,696")
    c2.metric("With Evac Actions", "653")
    c3.metric("Vulnerable Counties", "24,969")
    c4.metric("Median Delay", "1.1h")
    st.divider()
    from real_data_insights import render_real_data_insights
    render_real_data_insights()

elif page == "Equity Analysis":
    try:
        from equity_analysis_page import render_equity_analysis_page
        render_equity_analysis_page()
    except ImportError:
        from real_data_insights import render_real_data_insights
        render_real_data_insights()

elif page == "Risk Calculator":
    from risk_calculator_page import render_risk_calculator_page
    render_risk_calculator_page()

elif page == "Impact Projection":
    from impact_projection_page import render_impact_projection_page
    render_impact_projection_page()

elif page == "Coverage Analysis":
    from coverage_analysis_page import render_coverage_analysis_page
    render_coverage_analysis_page()

elif page == "Zone Duration":
    from zone_duration_page import render_zone_duration_page
    render_zone_duration_page()

elif page == "Fire Predictor":
    from fire_prediction_page import render_fire_prediction_page
    render_fire_prediction_page(role=username)

elif page == "AI Assistant":
    st.title("🤖 AI Assistant")
    persona_map = {
        "Emergency Worker":  ("EVAC-OPS",  "You are EVAC-OPS, an AI assistant for emergency dispatchers. Focus on evacuation operations, fire spread, coordination, and resource deployment. Be direct and concise."),
        "Caregiver/Evacuee": ("SAFE-PATH", "You are SAFE-PATH, a calm guide for caregivers and evacuees. Help them understand their risk and take clear action steps. Be reassuring but honest."),
        "Data Analyst":      ("DATA-LAB",  "You are DATA-LAB, a data science assistant specializing in wildfire analysis and the WiDS dataset. Median delay 1.1h, P90 32h, 653 fires, 39.8% high-SVI, 17% faster growth."),
    }
    persona_name, system_prompt = persona_map.get(role, ("Assistant", "You are a wildfire evacuation assistant."))
    st.subheader(f"Talking to: {persona_name}")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("Ask anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                resp = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=1000,
                    system=system_prompt,
                    messages=st.session_state.messages
                )
                reply = resp.content[0].text
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(f"AI assistant error: {e}")

elif page == "About":
    st.title("About — 49ers Intelligence Lab")
    st.markdown("""
    ## WiDS Datathon 2025 — Wildfire Caregiver Alert System

    **Research Question:** Do vulnerable populations experience systematically longer evacuation
    delays during wildfires, and can a data-driven alert system reduce those delays?

    ### Real Findings *(WiDS 2021–2025)*
    | Metric | Value |
    |--------|-------|
    | Fires analyzed | 62,696 |
    | With confirmed evac actions | 653 |
    | Median time to evacuation order | **1.1 hours** |
    | 90th percentile delay | **32 hours** |
    | High-SVI fire events | **39.8%** |
    | Growth rate — vulnerable counties | **11.71 ac/hr (+17%)** |

    ### Data Sources
    - Genasys Protect · CDC SVI 2022 · NASA FIRMS · NIFC · USFA · FEMA IPAWS

    ### Team
    49ers Intelligence Lab · UNC Charlotte · WiDS Datathon 2025
    """)