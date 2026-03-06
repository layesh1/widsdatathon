#streamlit run /Users/nadianarayanan/datathon/widsdatathon/wids-caregiver-alert/src/wildfire_alert_dashboard.py

"""
wildfire_alert_dashboard.py — 49ers Intelligence Lab · WiDS 2025

CHANGES FROM PREVIOUS VERSION
──────────────────────────────
1.  Streamlit default theme preserved — only structural/component CSS added
2.  Emojis removed from all page titles and navigation labels
3.  AI Assistant: open by default on right side; inline Close + Full Screen buttons
4.  AI system prompts: no personal info shared; advisory-only with strong reasoning
5.  Data Analyst gains "Data Governance" page (inline, no extra file needed)
6.  "About" page content centered
7.  Sign-up: Caregiver = self-declaration; Dispatcher/Analyst = requires access code
8.  Evacuation status widget: update for self OR monitored person
9.  AI chat: enhanced UI with avatars, timestamps, suggestions
10. AI chat: persistent history saved per-user to JSON in src directory
11. AI panel: left border via CSS :has(.ai-col-marker) targeting the actual column element
12. Suggestion chips: only shown in fullscreen mode

Test credentials
────────────────
  caregiver_test  | WiDS@2025! | Caregiver/Evacuee
  dispatcher_test | WiDS@2025! | Emergency Worker   (code: DISPATCH-2025)
  analyst_test    | WiDS@2025! | Data Analyst        (code: ANALYST-WiDS9)

Secrets required (.streamlit/secrets.toml)
───────────────────────────────────────────
  SUPABASE_URL      = "https://xxxx.supabase.co"
  SUPABASE_ANON_KEY = "eyJ..."
  ANTHROPIC_API_KEY = "sk-ant-..."
"""

import sys, os, inspect, json
from pathlib import Path
from datetime import datetime

src_dir = Path(__file__).parent.resolve()
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
os.chdir(src_dir)

import streamlit as st

from live_incident_feed import load_fire_data
from ui_utils import caregiver_progress_html, data_source_badge
from demo_mode import get_demo_state, render_demo_banner
from auth_supabase import (
    render_auth_page,
    render_user_profile_sidebar,
    log_page_visit,
    sign_out,
    get_evacuation_plan,
)

st.set_page_config(
    page_title="49ers Intelligence Lab — WiDS 2025",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT STYLES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stButton > button[kind="primary"] { border-left: 3px solid #AA0000 !important; }

.role-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; margin-right: 6px;
}
.brand-block { text-align: center; margin-bottom: 0.6rem; }
.brand-name  { font-size: 1.05rem; font-weight: 700; }
.brand-sub   { font-size: 0.74rem; opacity: 0.65; }

.about-centered { max-width: 760px; margin: 0 auto; text-align: center; }
.about-centered h3    { text-align: left; }
.about-centered table { margin: 0 auto; }

/* ══════════════════════════════════════════════════════
   AI COLUMN SEPARATOR
   Uses :has() to style the actual Streamlit column element
   that contains our .ai-col-marker sentinel div.
   This avoids the broken wrapper-div approach.
   ══════════════════════════════════════════════════════ */
div[data-testid="stColumn"]:has(.ai-col-marker) {
    border-left: 2px solid rgba(170, 0, 0, 0.3) !important;
    padding-left: 20px !important;
}

/* ══════════════════════════════════════════════════════
   ENHANCED AI CHAT PANEL
   ══════════════════════════════════════════════════════ */

.ai-chat-card {
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
}

.ai-chat-header {
    background: linear-gradient(135deg, #AA0000 0%, #cc3300 60%, #e05500 100%);
    padding: 14px 16px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.ai-chat-avatar-bot {
    width: 36px; height: 36px; border-radius: 50%;
    background: rgba(255,255,255,0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
    border: 2px solid rgba(255,255,255,0.4);
}
.ai-chat-header-text { flex: 1; }
.ai-chat-title {
    color: #fff; font-weight: 700; font-size: 0.92rem;
    line-height: 1.2; margin: 0;
}
.ai-chat-subtitle {
    color: rgba(255,255,255,0.75); font-size: 0.68rem;
    margin: 0; line-height: 1.3;
}
.ai-status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 6px #4ade80;
    flex-shrink: 0;
}

.ai-advisory-banner {
    background: rgba(251,191,36,0.12);
    border-bottom: 1px solid rgba(251,191,36,0.3);
    padding: 6px 14px;
    font-size: 0.68rem;
    color: #92400e;
    display: flex; align-items: center; gap: 5px;
}

.ai-session-bar {
    padding: 6px 14px;
    border-bottom: 1px solid rgba(128,128,128,0.1);
    display: flex; justify-content: space-between; align-items: center;
    font-size: 0.65rem; opacity: 0.55;
}

.chat-scroll {
    padding: 12px 14px;
    display: flex; flex-direction: column; gap: 10px;
    overflow-y: auto; max-height: 48vh;
}
.chat-scroll::-webkit-scrollbar { width: 4px; }
.chat-scroll::-webkit-scrollbar-thumb {
    background: rgba(128,128,128,0.25); border-radius: 4px;
}

.msg-row-user      { display: flex; justify-content: flex-end; gap: 8px; align-items: flex-end; }
.msg-row-assistant { display: flex; justify-content: flex-start; gap: 8px; align-items: flex-end; }

.msg-avatar {
    width: 26px; height: 26px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; flex-shrink: 0;
}
.msg-avatar-user { background: #AA000022; border: 1px solid #AA000033; }
.msg-avatar-bot  { background: linear-gradient(135deg,#AA0000,#e05500); color: #fff; }

.msg-bubble-wrap      { display: flex; flex-direction: column; max-width: 85%; }
.msg-bubble-wrap-user { align-items: flex-end; }
.msg-bubble-wrap-bot  { align-items: flex-start; }

.chat-bubble-user {
    background: linear-gradient(135deg, #AA0000 0%, #cc3300 100%);
    color: #fff;
    border-radius: 16px 16px 4px 16px;
    padding: 9px 13px;
    font-size: 0.83rem; line-height: 1.45;
    box-shadow: 0 2px 8px rgba(170,0,0,0.2);
}
.chat-bubble-assistant {
    background: rgba(128,128,128,0.07);
    border: 1px solid rgba(128,128,128,0.15);
    border-radius: 16px 16px 16px 4px;
    padding: 9px 13px;
    font-size: 0.83rem; line-height: 1.45;
}
.msg-meta {
    font-size: 0.6rem; opacity: 0.45;
    margin-top: 3px; padding: 0 4px;
}

.chat-empty-state {
    text-align: center; padding: 28px 16px; opacity: 0.5;
}
.chat-empty-icon { font-size: 2rem; margin-bottom: 6px; }
.chat-empty-text { font-size: 0.78rem; line-height: 1.5; }

/* Chips — only rendered in fullscreen, but style defined globally */
.suggestion-chips {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 10px 14px 4px;
}
.chip {
    background: rgba(170,0,0,0.07);
    border: 1px solid rgba(170,0,0,0.2);
    border-radius: 20px; padding: 4px 11px;
    font-size: 0.7rem; color: #AA0000;
    cursor: pointer; white-space: nowrap;
}

/* ══════════════════════════════════════════════════════
   NAV BUTTON STYLES
   ══════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] .stButton > button {
    text-align: left !important;
    padding: 8px 14px !important;
    font-size: 0.88rem !important;
    margin-bottom: 2px !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    border-left: 3px solid #AA0000 !important;
    background: rgba(170, 0, 0, 0.07) !important;
}

/* ══════════════════════════════════════════════════════
   DARK THEME — 60-30-10 COLOR SYSTEM
   60% deep navy bg | 30% slate surface | 10% red/amber accent
   ══════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');

/* App background */
[data-testid="stAppViewContainer"] > .main,
.main .block-container {
    background-color: #0d1117 !important;
}
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] {
    background-color: #0d1117 !important;
    border-bottom: 1px solid #30363d !important;
}

/* Body typography — color set by config.toml theme, not overridden here */
html, body,
[data-testid="stMarkdownContainer"] > p,
[data-testid="stText"] > p {
    font-family: 'IBM Plex Sans', system-ui, sans-serif !important;
}
h1, h2, h3, h4 {
    font-family: 'DM Sans', system-ui, sans-serif !important;
}
code, pre { font-family: 'JetBrains Mono', monospace !important; }

/* Metric containers — dark surface cards */
[data-testid="metric-container"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #8b949e !important;
    font-size: 0.76rem !important;
}

/* Expanders — surface-raised bg */
[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    color: #8b949e !important;
    font-size: 0.83rem !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: #161b22 !important;
    border-color: #30363d !important;
    color: #e6edf3 !important;
}

/* Tabs — active tab red underline */
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: #FF4B4B !important;
}

/* Primary CTA buttons in main content — red */
.main .stButton > button[kind="primary"] {
    background: #FF4B4B !important;
    border-color: #FF4B4B !important;
    color: #fff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    min-height: 44px !important;
    border-radius: 8px !important;
}

/* Alert boxes */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* Dataframe borders */
[data-testid="stDataFrame"] {
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
}

/* Captions */
[data-testid="stCaptionContainer"] { color: #8b949e !important; }

/* Dividers */
hr { border-color: #30363d !important; }

/* ── Governance cards ── */
.gov-card {
    border: 1px solid rgba(128,128,128,0.2); border-radius: 10px;
    padding: 1rem 1.2rem; margin-bottom: 0.8rem;
}
.gov-alert-critical {
    background: #fff5f5; border-left: 4px solid #e53e3e;
    padding: 0.8rem 1rem; border-radius: 6px; margin: 0.5rem 0;
}
.gov-alert-warning {
    background: #fffbeb; border-left: 4px solid #d97706;
    padding: 0.8rem 1rem; border-radius: 6px; margin: 0.5rem 0;
}
.gov-alert-pass {
    background: #f0fdf4; border-left: 4px solid #16a34a;
    padding: 0.8rem 1rem; border-radius: 6px; margin: 0.5rem 0;
}
.bench-title {
    text-align: center; font-size: 1.05rem; font-weight: 600;
    color: #AA0000; margin: 1.2rem 0 0.8rem; letter-spacing: 0.02em;
}

/* ══════════════════════════════════════════════════════
   MOBILE-RESPONSIVE STYLES
   Targets screens ≤ 768px (phones/small tablets)
   ══════════════════════════════════════════════════════ */
@media (max-width: 768px) {
    /* Stack multi-column layouts vertically */
    div[data-testid="stColumns"] {
        flex-direction: column !important;
    }
    div[data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    /* Larger tap targets for buttons */
    .stButton > button {
        min-height: 48px !important;
        font-size: 1rem !important;
        width: 100% !important;
    }

    /* Prevent iOS input zoom (font-size must be ≥ 16px) */
    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] select,
    div[data-testid="stTextArea"] textarea {
        font-size: 16px !important;
    }

    /* Compact sidebar on mobile */
    section[data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 280px !important;
    }

    /* Slightly smaller chart heights on narrow screens */
    div[data-testid="stPlotlyChart"] {
        max-height: 380px;
    }

    /* Full-width metric tiles */
    div[data-testid="metric-container"] {
        min-width: 140px;
    }
}
</style>
""", unsafe_allow_html=True)

# ── PWA / mobile-web-app meta tags ──────────────────────────────────────────
st.markdown("""
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="WiDS Wildfire Alert">
<meta name="theme-color" content="#AA0000">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# AUTH GATE
# ─────────────────────────────────────────────────────────────────────────────
logo_paths = [
    Path("49ers_logo.png"), Path("logo.png"), Path("assets/logo.png"),
    Path("static/logo.png"), Path("images/logo.png"),
]
render_auth_page(logo_paths=logo_paths)

role     = st.session_state.role
username = st.session_state.username
fire_data, fire_source, fire_label = load_fire_data()

# ─────────────────────────────────────────────────────────────────────────────
# HOME PAGE GATE (Improvement 3)
# Show on first visit after login; also when user clicks "← Change role"
# ─────────────────────────────────────────────────────────────────────────────
if "show_home" not in st.session_state:
    st.session_state.show_home = True   # first visit after login → show splash

if st.session_state.get("show_home"):
    from home_page import render_home_page
    render_home_page()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
if "show_ai_panel" not in st.session_state:
    st.session_state.show_ai_panel = False   # start closed; popup opens it
if "ai_fullscreen" not in st.session_state:
    st.session_state.ai_fullscreen = False
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []
if "ai_show_history" not in st.session_state:
    st.session_state.ai_show_history = False
if "ai_session_start" not in st.session_state:
    st.session_state.ai_session_start = datetime.now().isoformat()
# Chatbot popup: shown once per login session
if "chatbot_greeted" not in st.session_state:
    st.session_state.chatbot_greeted = False
# Shared location opt-in
if "location_prompt_shown" not in st.session_state:
    st.session_state.location_prompt_shown = False
if "user_gps_lat" not in st.session_state:
    st.session_state.user_gps_lat = None
if "user_gps_lon" not in st.session_state:
    st.session_state.user_gps_lon = None

# ─────────────────────────────────────────────────────────────────────────────
# CHAT HISTORY PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────
HISTORY_DIR = src_dir / ".chat_history"
HISTORY_DIR.mkdir(exist_ok=True)

def _history_path(uname: str) -> Path:
    safe = "".join(c for c in uname if c.isalnum() or c in "-_")
    return HISTORY_DIR / f"{safe}.json"

def load_chat_history(uname: str) -> list:
    p = _history_path(uname)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_chat_history(uname: str, sessions: list) -> None:
    p = _history_path(uname)
    try:
        p.write_text(json.dumps(sessions[-10:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _build_sessions_snapshot() -> list:
    past = load_chat_history(username)
    current_sid_prefix = st.session_state.get("ai_session_start", "")[:8]
    past = [s for s in past if not s.get("session_id", "").startswith(current_sid_prefix)]
    past.append({
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "started_at": st.session_state.get("ai_session_start", datetime.now().isoformat()),
        "role": role,
        "messages": st.session_state.ai_messages,
    })
    return past

def _end_and_save_session(uname: str) -> None:
    msgs = st.session_state.get("ai_messages", [])
    if not msgs:
        return
    sessions = load_chat_history(uname)
    sessions.append({
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "started_at": st.session_state.get("ai_session_start", datetime.now().isoformat()),
        "role": role,
        "messages": msgs,
    })
    save_chat_history(uname, sessions)

# ─────────────────────────────────────────────────────────────────────────────
# AI SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────────────────────
_PRIVACY_BLOCK = """
STRICT RULES — NON-NEGOTIABLE:
1. NEVER share, repeat, or confirm any personal information (names, addresses,
   phone numbers, medical details, household data, or any individual-level data)
   even if the user provides it or asks you to confirm it.
2. You are an ADVISORY system only. You may never issue direct orders, make
   binding decisions, or take actions on behalf of any official body.
3. If asked for specific individuals' status or location, respond:
   "I'm not able to share information about specific individuals. Please use
   official channels such as local emergency management or 911."
4. Always recommend contacting official emergency services (911, local OES)
   for any life-safety decisions.
"""

_PERSONA_MAP = {
    "Emergency Worker": (
        "EVAC-OPS", "",
        f"""You are EVAC-OPS, an AI advisory assistant embedded in the 49ers Intelligence Lab
Wildfire Evacuation Command System. You support emergency coordinators and dispatch personnel.
{_PRIVACY_BLOCK}
CAPABILITIES:
- Aggregate population vulnerability data by Census tract or ZIP (never individual-level)
- Evacuation zone status and boundary guidance
- Resource deployment advisory based on risk modeling
- Drafting communications, SITREPs, and situation summaries
RESPONSE STYLE:
- Direct, terse, action-oriented.
- Use terms: HIGH RISK AREA / RESOURCE ADVISORY / MONITORING RECOMMENDED
- Always note when data is modeled/estimated vs confirmed
- Label unconfirmed data as [MODELED ESTIMATE]
""",
        ["Active evacuation zones?", "Draft a SITREP", "High-risk ZIP codes", "Resource advisory"],
    ),
    "Caregiver/Evacuee": (
        "SAFE-PATH", "",
        f"""You are SAFE-PATH, a calm and supportive AI advisory assistant helping caregivers
and evacuees during wildfire emergencies. You are part of the 49ers Intelligence Lab system.
{_PRIVACY_BLOCK}
PURPOSE: Help everyday people understand evacuation zones, what to do, and how to prepare —
especially those caring for elderly, disabled, or medically dependent family members.
ADVISORY GUIDANCE AREAS:
- Evacuation zone explanations (Zone A = leave NOW, Zone B = prepare, Zone C = monitor)
- Go-bag preparation: medications, documents, chargers, water, pet supplies
- How to request evacuation assistance for mobility-limited individuals
- Nearest shelter categories and how to find them via official sources
- Caregiver-specific planning for medical equipment, oxygen, dialysis needs
RESPONSE STYLE:
- Plain language, numbered steps, warm and calm tone.
- If someone describes immediate danger: advise them to call 911 first, immediately.
""",
        ["What's in a go-bag?", "Zone A vs Zone B", "Help for wheelchair users", "Nearest shelter"],
    ),
    "Data Analyst": (
        "DATA-LAB", "",
        f"""You are DATA-LAB, a technical AI advisory assistant for data scientists and analysts
working on the 49ers Intelligence Lab WiDS 2025 project: Wildfire Evacuation Alert System.
{_PRIVACY_BLOCK}
PROJECT CONTEXT:
- Predicts evacuation risk for vulnerable populations during wildfires
- Key stats: median delay 1.1h, P90 delay 100.3h, 653 fires with evac actions,
  39.8% in high-SVI counties, 17% faster growth in vulnerable counties
- Stack: Python, Streamlit, Supabase, Cox survival analysis, Getis-Ord Gi* hotspot detection
DATA GOVERNANCE:
- 7-table schema: geo_events, fire_perimeters, evac_zones, regions, 3 changelog tables
- Critical: only use fire_perimeters where approval_status = 'approved'
- Quality thresholds: containment 0–100%, lat/lng non-null for mapping
RESPONSE STYLE:
- Technical, precise, collaborative. Flag limitations and assumptions proactively.
""",
        ["Cox model AUC?", "SVI correlation query", "Hotspot detection code", "Data schema help"],
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    for lp in logo_paths:
        if lp.exists():
            _, img_col, _ = st.columns([1, 2, 1])
            with img_col:
                st.image(str(lp), width="stretch")
            break
    else:
        st.markdown("<div style='text-align:center;font-size:0.8rem;opacity:0.5'>49ers Intelligence Lab</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='brand-block'>"
        "<div class='brand-name'>49ers Intelligence Lab</div>"
        "<div class='brand-sub'>WiDS Datathon 2025</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    rc = {
        "Emergency Worker": "#AA0000",
        "Evacuee":          "#3d7be8",
        "Caregiver":        "#2ea44f",
        "Caregiver/Evacuee":"#3d7be8",
        "Data Analyst":     "#7b5ea7",
    }.get(role, "#555")
    st.markdown(
        f"<div style='text-align:center;margin-bottom:0.4rem'>"
        f"<span class='role-badge' style='background:{rc}22;color:{rc};border:1px solid {rc}44'>{role}</span>"
        f"<span style='font-size:0.78rem;color:#8892a4'>{username}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    render_user_profile_sidebar(username)
    st.divider()

    n_fires = len(fire_data)
    st.markdown(
        f"**Incident Feed:** {fire_label}  \n"
        f"{'— ' + str(n_fires) + ' US hotspots (24 h)' if n_fires > 0 else '— No active incidents'}",
        help="Green = WiDS local geo_events  ·  Yellow = NASA FIRMS live  ·  Grey = unavailable",
    )
    st.divider()

    # ── Navigation ────────────────────────────────────────────────────────────
    _NAV_CONFIG = {
        "Emergency Worker": [
            ("Command",        "Live incidents & evacuee tracker"),
            ("Fire Forecast",  "Fire spread prediction"),
            ("At-Risk Zones",  "Vulnerable population hotspots"),
            ("Coverage Gaps",  "Where alerts may not reach"),
            ("Resources",      "Fire department directory"),
        ],
        "Evacuee": [
            ("My Safety",      "Fire status near your location"),
            ("My Plan",        "Your personalized evacuation plan"),
            ("My Risk",        "Your vulnerability score with demographics"),
            ("Why This App?",  "Why official alerts aren't enough"),
        ],
        "Caregiver": [
            ("My Evacuee",     "Monitor your evacuee's fire status"),
            ("Send Alert",     "Alert your evacuee to evacuate"),
            ("Resources",      "Fire department & shelter directory"),
            ("Why This App?",  "Why proactive alerts matter"),
        ],
        "Caregiver/Evacuee": [  # legacy fallback
            ("My Safety",      "Fire status near your location"),
            ("My Plan",        "Evacuation plan and shelters"),
            ("My Risk",        "Your vulnerability score"),
            ("Why This App?",  "Why official alerts aren't enough"),
        ],
        "Data Analyst": [
            ("Overview",       "About this project"),
            ("Signal Gap",     "Alert failure & silent fires"),
            ("Equity & Risk",  "Vulnerability analysis"),
            ("Geographic",     "Hotspots, coverage & counties"),
            ("Fire Patterns",  "Temporal & impact analysis"),
            ("Technical",      "Data quality & IRWIN linkage"),
            ("Fire Predictor", "Fire spread forecast"),
        ],
    }

    nav_items = _NAV_CONFIG.get(role, _NAV_CONFIG["Data Analyst"])
    valid_pages = [label for label, _ in nav_items]

    if "current_page" not in st.session_state or st.session_state.current_page not in valid_pages:
        st.session_state.current_page = valid_pages[0]

    for label, desc in nav_items:
        active = st.session_state.current_page == label
        if st.button(label, key=f"nav_{label}", use_container_width=True,
                     type="primary" if active else "secondary",
                     help=desc):
            st.session_state.current_page = label
            log_page_visit(username, label)
            st.rerun()

    # ── Role-specific secondary controls ──────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if role == "Data Analyst":
        with st.expander("Filters", expanded=False):
            st.selectbox(
                "State",
                [
                    "All States",
                    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
                ],
                key="sidebar_state_filter",
            )
            st.slider("Year range", 2021, 2025, (2021, 2025), key="sidebar_year_range")

    elif role == "Caregiver/Evacuee":
        county_val = st.session_state.get("selected_county", "")
        new_county = st.text_input(
            "Your county",
            value=county_val,
            placeholder="e.g. Los Angeles, CA",
            key="sidebar_county_input",
        )
        if new_county != county_val:
            st.session_state.selected_county = new_county
        # Progress indicator
        has_risk = st.session_state.get("risk_calculated", False)
        has_alerts = st.session_state.get("onboarded", False)
        has_plan = st.session_state.get("evacuation_plan_loaded", False)
        st.markdown(caregiver_progress_html(has_risk, has_alerts, has_plan), unsafe_allow_html=True)

    elif role == "Emergency Worker":
        with st.expander("Operational area", expanded=False):
            st.selectbox(
                "Region",
                ["All", "West", "Southwest", "Southeast", "Northeast", "Midwest"],
                key="sidebar_region",
            )
            st.toggle("Live data only", value=False, key="sidebar_live_only")

    st.divider()

    if not st.session_state.show_ai_panel:
        if st.button("Open AI Assistant", key="ai_open_btn", use_container_width=True):
            st.session_state.show_ai_panel = True
            st.rerun()

    st.divider()
    if st.button("Sign Out", key="sign_out_btn", use_container_width=True):
        _end_and_save_session(username)
        sign_out(username)
        st.rerun()

    # ── Change role link (returns to home splash) ──────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("← Change role", key="change_role_btn", use_container_width=True):
        st.session_state.show_home = True
        st.rerun()

    # ── Demo Mode toggle (Improvement 1) ──────────────────────────────────
    st.divider()
    demo_mode = st.toggle("🎬 Demo Mode", value=False, key="demo_mode")
    if demo_mode:
        st.info("📍 Scenario: Ventura County, CA — 2am fire detection near high-SVI neighborhood")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def _render_about():
    st.markdown("<div class='about-centered'>", unsafe_allow_html=True)
    st.title("49ers Intelligence Lab")
    st.caption("WiDS Datathon 2025 · Wildfire Caregiver Alert System")
    st.markdown("""
**Research Question:** Do vulnerable populations experience systematically longer
evacuation delays during wildfires, and can a data-driven alert system reduce those delays?
""")
    st.markdown("### Key Findings (WiDS 2021–2025)")
    st.markdown("""
| Metric | Value |
|--------|-------|
| Fires analyzed | 62,696 |
| With confirmed evacuation actions | 653 |
| Median time to evacuation order | **1.1 hours** |
| 90th-percentile delay | **100 hours** |
| High-SVI fire events | **39.8%** |
| Growth rate — vulnerable counties | **11.71 ac/hr (+17%)** |
""")
    st.markdown("### Data Sources")
    st.markdown("Genasys Protect · CDC SVI 2022 · NASA FIRMS · NIFC · USFA · FEMA IPAWS")
    st.markdown("### Team")
    st.markdown("49ers Intelligence Lab · UNC Charlotte · WiDS Datathon 2025")
    st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ENHANCED AI PANEL
# is_fullscreen : show suggestion chips
# show_border   : inject .ai-col-marker sentinel so CSS applies the border
# ─────────────────────────────────────────────────────────────────────────────
def _render_ai_panel(role: str, *, is_fullscreen: bool = False, show_border: bool = False):
    persona_name, persona_emoji, system_prompt, suggestions = _PERSONA_MAP.get(
        role, ("Assistant", "", "You are a wildfire evacuation advisory assistant.", [])
    )

    msgs = st.session_state.ai_messages
    msg_count = len(msgs)
    session_start = st.session_state.get("ai_session_start", "")
    try:
        start_fmt = datetime.fromisoformat(session_start).strftime("%-I:%M %p")
    except Exception:
        start_fmt = "—"

    # ── Sentinel div — invisible zero-height element that CSS :has() detects ──
    # This is what triggers the border on the parent stColumn without wrapping
    # Streamlit widgets in a broken HTML div.
    if show_border:
        st.markdown("<div class='ai-col-marker' style='height:0;overflow:hidden'></div>",
                    unsafe_allow_html=True)

    # ── Header controls row ───────────────────────────────────────────────────
    hdr_left, hdr_mid, hdr_right = st.columns([4, 2, 2])
    with hdr_left:
        st.markdown(
            f"<div style='padding-top:4px;font-weight:700;font-size:0.9rem'>"
            f"{persona_emoji} AI Assistant"
            f"<span style='font-size:0.68rem;font-weight:400;opacity:0.6;margin-left:6px'>"
            f"{persona_name}</span></div>",
            unsafe_allow_html=True,
        )
    with hdr_mid:
        fs_label = "Exit Full" if st.session_state.ai_fullscreen else "Expand"
        if st.button(fs_label, key="ai_fs_inline", use_container_width=True):
            st.session_state.ai_fullscreen = not st.session_state.ai_fullscreen
            st.rerun()
    with hdr_right:
        if st.button("Close", key="ai_close_inline", use_container_width=True):
            _end_and_save_session(username)
            st.session_state.show_ai_panel = False
            st.session_state.ai_fullscreen = False
            st.rerun()

    # ── Gradient header card ──────────────────────────────────────────────────
    st.markdown(
        f"""<div class="ai-chat-card">
          <div class="ai-chat-header">
            <div class="ai-chat-avatar-bot">{persona_emoji}</div>
            <div class="ai-chat-header-text">
              <div class="ai-chat-title">{persona_name}</div>
              <div class="ai-chat-subtitle">49ers Intelligence Lab · Advisory Only</div>
            </div>
            <div class="ai-status-dot" title="Online"></div>
          </div>
          <div class="ai-advisory-banner">
            Advisory guidance only — not a substitute for 911 or official emergency services
          </div>
          <div class="ai-session-bar">
            <span>Session started {start_fmt}</span>
            <span>{msg_count} message{'s' if msg_count != 1 else ''} this session</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Suggestion chips — FULLSCREEN ONLY ───────────────────────────────────
    if is_fullscreen and not msgs and suggestions:
        chips_html = "".join(f"<span class='chip'>{s}</span>" for s in suggestions)
        st.markdown(
            f"<div style='margin-bottom:6px;font-size:0.7rem;opacity:0.55'>"
            f"Suggested questions:</div>"
            f"<div class='suggestion-chips'>{chips_html}</div>",
            unsafe_allow_html=True,
        )
        chip_cols = st.columns(len(suggestions))
        for i, (col, suggestion) in enumerate(zip(chip_cols, suggestions)):
            with col:
                if st.button(suggestion, key=f"chip_{i}", use_container_width=True,
                             help=f"Ask: {suggestion}"):
                    st.session_state.ai_messages.append({
                        "role": "user", "content": suggestion,
                        "ts": datetime.now().strftime("%H:%M"),
                    })
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                        api_msgs = [{"role": m["role"], "content": m["content"]}
                                    for m in st.session_state.ai_messages]
                        resp = client.messages.create(
                            model="claude-sonnet-4-6", max_tokens=700,
                            system=system_prompt, messages=api_msgs,
                        )
                        reply = resp.content[0].text
                    except Exception as e:
                        reply = f"Error: {e}"
                    st.session_state.ai_messages.append({
                        "role": "assistant", "content": reply,
                        "ts": datetime.now().strftime("%H:%M"),
                    })
                    save_chat_history(username, _build_sessions_snapshot())
                    st.rerun()

    # ── Message bubbles ───────────────────────────────────────────────────────
    if msgs:
        msgs_html = ""
        for m in msgs[-40:]:
            ts      = m.get("ts", "")
            content = m["content"].replace("\n", "<br>")
            if m["role"] == "user":
                msgs_html += f"""
                <div class="msg-row-user">
                  <div class="msg-bubble-wrap msg-bubble-wrap-user">
                    <div class="chat-bubble-user">{content}</div>
                    <div class="msg-meta">{ts}</div>
                  </div>
                  <div class="msg-avatar msg-avatar-user"></div>
                </div>"""
            else:
                msgs_html += f"""
                <div class="msg-row-assistant">
                  <div class="msg-avatar msg-avatar-bot">{persona_emoji}</div>
                  <div class="msg-bubble-wrap msg-bubble-wrap-bot">
                    <div class="chat-bubble-assistant">{content}</div>
                    <div class="msg-meta">{persona_name} · {ts}</div>
                  </div>
                </div>"""
        st.markdown(f"<div class='chat-scroll'>{msgs_html}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='chat-empty-state'>"
            f"<div class='chat-empty-icon'>{persona_emoji}</div>"
            f"<div class='chat-empty-text'>Hi! I'm <strong>{persona_name}</strong>.<br>"
            f"Ask me anything about wildfire evacuation.<br>"
            f"<span style='font-size:0.65rem;opacity:0.6'>"
            f"All responses are advisory guidance only.</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form(key="ai_chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "Message", height=80, placeholder=f"Ask {persona_name} a question…",
            label_visibility="collapsed", key="ai_input_text",
        )
        send_col, clear_col = st.columns([3, 1])
        with send_col:
            send = st.form_submit_button("Send", use_container_width=True, type="primary")
        with clear_col:
            clear = st.form_submit_button("Clear", use_container_width=True)

    if clear:
        _end_and_save_session(username)
        st.session_state.ai_messages = []
        st.session_state.ai_session_start = datetime.now().isoformat()
        st.rerun()

    if send and user_input.strip():
        ts_now = datetime.now().strftime("%H:%M")
        st.session_state.ai_messages.append({
            "role": "user", "content": user_input.strip(), "ts": ts_now,
        })
        try:
            import anthropic
            client   = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
            api_msgs = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state.ai_messages]
            resp     = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=700,
                system=system_prompt, messages=api_msgs,
            )
            reply = resp.content[0].text
        except KeyError:
            reply = "AI Assistant not configured. Add ANTHROPIC_API_KEY to .streamlit/secrets.toml."
        except Exception as e:
            reply = f"Error: {e}"

        st.session_state.ai_messages.append({
            "role": "assistant", "content": reply,
            "ts": datetime.now().strftime("%H:%M"),
        })
        save_chat_history(username, _build_sessions_snapshot())
        st.rerun()

    # ── Past sessions history drawer ──────────────────────────────────────────
    past_sessions = load_chat_history(username)
    displayable = [s for s in past_sessions
                   if not s.get("session_id", "").startswith(
                       st.session_state.get("ai_session_start", "")[:8]
                   )]

    if displayable:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        show_hist = st.toggle(
            f"Past sessions ({len(displayable)} saved)",
            value=st.session_state.ai_show_history,
            key="ai_hist_toggle",
        )
        st.session_state.ai_show_history = show_hist

        if show_hist:
            for i, session in enumerate(reversed(displayable[-5:])):
                sid   = session.get("session_id", f"session_{i}")
                sdate = sid[:8]
                stime = sid[9:13] if len(sid) > 9 else ""
                try:
                    label_dt = datetime.strptime(f"{sdate} {stime}", "%Y%m%d %H%M")
                    label    = label_dt.strftime("%b %-d, %-I:%M %p")
                except Exception:
                    label = sid
                n = len(session.get("messages", []))
                with st.expander(f"{label} — {n} messages"):
                    for m in session.get("messages", []):
                        ts_h = m.get("ts", "")
                        role_label = "You" if m["role"] == "user" else persona_name
                        bubble_style = (
                            "background:rgba(170,0,0,0.08);border-radius:8px;"
                            "padding:6px 10px;margin:3px 0;font-size:0.78rem;"
                        ) if m["role"] == "user" else (
                            "background:rgba(128,128,128,0.07);border-radius:8px;"
                            "padding:6px 10px;margin:3px 0;font-size:0.78rem;"
                        )
                        st.markdown(
                            f"<div style='{bubble_style}'>"
                            f"<span style='font-size:0.62rem;opacity:0.5'>"
                            f"{role_label} {ts_h}</span><br>"
                            f"{m['content']}</div>",
                            unsafe_allow_html=True,
                        )


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING FIRST-RUN FLOW
# Shown once per browser session for non-analyst roles.
# ─────────────────────────────────────────────────────────────────────────────
def _render_onboarding():
    from ui_utils import page_header, render_card, section_header
    from user_profile import render_profile_setup, render_evacuee_setup, get_caregiver_evacuee

    if role in ("Evacuee", "Caregiver", "Caregiver/Evacuee"):
        render_profile_setup(role=role)
        return

    elif role == "Emergency Worker":
        page_header("Welcome — set your operational area")
        st.markdown(
            "Select your primary region before loading the command dashboard. "
            "This filters the incident feed and default map view."
        )
        region = st.selectbox(
            "Primary operational region",
            ["All", "West", "Southwest", "Southeast", "Northeast", "Midwest"],
            key="onboard_region",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            render_card("Active incidents", f"{len(fire_data):,}",
                        fire_label, "#d4a017")
        with col_b:
            render_card("High-SVI counties at risk", "39.8%",
                        "Share of WiDS fire events in vulnerable counties", "#FF4B4B")
        st.markdown("")
        if st.button("Enter Command Dashboard", type="primary", use_container_width=True):
            st.session_state.sidebar_region = region
            st.session_state.onboarded = True
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTER
# ─────────────────────────────────────────────────────────────────────────────
page = st.session_state.current_page


def _render_page():
    # ── Demo banner (Improvement 1) — shown on every page when demo mode is on ──
    render_demo_banner()

    # ── Emergency Worker ──────────────────────────────────────────────────────
    if page == "Command":
        # Improvement 2: NASA FIRMS live fire card at top of Command page
        try:
            from nasa_firms_live import (
                get_most_significant_fire, firms_status_badge,
                render_live_fire_card, LIVE_DOT_CSS,
            )
            st.markdown(LIVE_DOT_CSS, unsafe_allow_html=True)
            live_fire, live_source = get_most_significant_fire()
            st.markdown(firms_status_badge(live_source), unsafe_allow_html=True)
            st.markdown(render_live_fire_card(live_fire, live_source), unsafe_allow_html=True)
        except Exception:
            pass  # graceful degradation — no NASA FIRMS, just show WiDS feed

        from command_dashboard_page import render_command_dashboard
        render_command_dashboard(fire_data, fire_source, fire_label)

    elif page == "Fire Forecast":
        from fire_prediction_page import render_fire_prediction_page
        render_fire_prediction_page(role=username)

    elif page == "At-Risk Zones":
        from dispatcher_risk_zones_page import render_dispatcher_risk_zones_page
        render_dispatcher_risk_zones_page()

    elif page == "Coverage Gaps":
        from dispatcher_coverage_page import render_dispatcher_coverage_page
        render_dispatcher_coverage_page()

    elif page == "Resources":
        from dispatcher_resources_page import render_dispatcher_resources_page
        render_dispatcher_resources_page()

    # ── Evacuee (unified single-address flow) ─────────────────────────────────
    elif page in ("My Safety", "My Plan", "My Risk"):
        from evacuee_dashboard import render_evacuee_dashboard
        render_evacuee_dashboard(fire_data=fire_data)

    # ── Caregiver ─────────────────────────────────────────────────────────────
    elif page == "My Evacuee":
        from caregiver_dashboard import render_caregiver_dashboard
        render_caregiver_dashboard(fire_data=fire_data)

    elif page == "Send Alert":
        from caregiver_dashboard import render_caregiver_dashboard
        render_caregiver_dashboard(fire_data=fire_data)

    # ── Legacy Caregiver/Evacuee pages (kept for backward compat) ────────────
    elif page == "Am I Safe?":
        from caregiver_start_page import render_caregiver_start_page
        render_caregiver_start_page()

    elif page == "Evacuation Plan":
        try:
            from evacuation_planner_page import render_evacuation_planner_page
            sig    = inspect.signature(render_evacuation_planner_page)
            params = list(sig.parameters.keys())
            if "vulnerable_populations" in params and "fire_data" in params:
                render_evacuation_planner_page(fire_data=fire_data, vulnerable_populations=None)
            elif "fire_data" in params:
                render_evacuation_planner_page(fire_data=fire_data)
            else:
                render_evacuation_planner_page()
        except Exception as e:
            st.error(f"Evacuation Planner error: {e}")

    elif page == "Risk Calculator":
        from risk_calculator_page import render_risk_calculator_page
        render_risk_calculator_page()

    elif page == "My County":
        from caregiver_county_page import render_caregiver_county_page
        render_caregiver_county_page()

    elif page == "Why This App?":
        from caregiver_why_page import render_caregiver_why_page
        render_caregiver_why_page()

    # ── Data Analyst ──────────────────────────────────────────────────────────
    elif page == "Overview":
        _render_about()

    elif page == "Signal Gap":
        t1, t2 = st.tabs(["📉 Signal Gap Analysis", "🔇 Silent Fire Tracker"])
        with t1:
            from signal_gap_analysis_page import render_signal_gap_analysis
            render_signal_gap_analysis()
        with t2:
            from silent_escalation_page import render_silent_escalation_page
            render_silent_escalation_page()

    elif page == "Equity & Risk":
        t1, t2 = st.tabs(["⚖️ Equity Analysis", "📡 Coverage Analysis"])
        with t1:
            try:
                from equity_analysis_page import render_equity_analysis_page
                render_equity_analysis_page()
            except ImportError:
                from real_data_insights import render_real_data_insights
                render_real_data_insights()
        with t2:
            from coverage_analysis_page import render_coverage_analysis_page
            render_coverage_analysis_page()

    elif page == "Geographic":
        t1, t2, t3 = st.tabs(["🗺️ Hotspot Map", "📡 Channel Coverage", "🔍 County Drill-Down"])
        with t1:
            from hotspot_map_page import render_hotspot_map_page
            render_hotspot_map_page()
        with t2:
            from channel_coverage_page import render_channel_coverage_page
            render_channel_coverage_page()
        with t3:
            from county_drilldown_page import render_county_drilldown_page
            render_county_drilldown_page()

    elif page == "Fire Patterns":
        t1, t2 = st.tabs(["📅 Temporal Patterns", "📈 Impact Projection"])
        with t1:
            from temporal_fire_pattern_page import render_temporal_fire_patterns
            render_temporal_fire_patterns()
        with t2:
            from impact_projection_page import render_impact_projection_page
            render_impact_projection_page()

    elif page == "Technical":
        t1, t2, t3 = st.tabs(["🔬 Data Governance", "🔗 IRWIN Linkage", "⏱️ Zone Duration"])
        with t1:
            from data_governance import render_data_governance
            render_data_governance()
        with t2:
            from irwin_linkage_page import render_irwin_linkage_page
            render_irwin_linkage_page()
        with t3:
            from zone_duration_page import render_zone_duration_page
            render_zone_duration_page()

    elif page == "Fire Predictor":
        from fire_prediction_page import render_fire_prediction_page
        render_fire_prediction_page(role=username)


# ─────────────────────────────────────────────────────────────────────────────
# CHATBOT POPUP + FLOATING BUTTON
# ─────────────────────────────────────────────────────────────────────────────

# Define onboarding gate early (also used in layout block below)
_needs_onboarding = (
    role != "Data Analyst"
    and st.session_state.get("onboarded") is None
)

# Check URL query param (floating button uses ?chat=open link)
_qp = st.query_params
if _qp.get("chat") == "open":
    st.session_state.show_ai_panel = True
    st.session_state.chatbot_greeted = True
    st.query_params.clear()
    st.rerun()

# First-login chatbot popup: auto-open with a welcome message
if not st.session_state.chatbot_greeted and not _needs_onboarding:
    st.session_state.chatbot_greeted = True
    st.session_state.show_ai_panel = True
    # Inject welcome message into chat
    if not st.session_state.ai_messages:
        _role_display = {
            "Caregiver/Evacuee": "SAFE-PATH",
            "Emergency Worker": "EVAC-OPS",
            "Data Analyst": "DATA-LAB",
        }.get(role, "SAFE-PATH")
        _welcome = {
            "Caregiver/Evacuee": (
                "Hi! I'm SAFE-PATH, your wildfire evacuation assistant.\n\n"
                "I can help you check if fires are near a loved one's home, "
                "find shelters, understand your evacuation zone, and plan next steps.\n\n"
                "**Try asking:** 'Is there a fire near Ventura, CA?' or "
                "'What should I do if I get an evacuation warning?'\n\n"
                "_Close this panel anytime — I'll be a button at the bottom of the screen._"
            ),
            "Emergency Worker": (
                "EVAC-OPS online. Ready for dispatch queries.\n\n"
                "Ask about vulnerable population counts, SVI zones, "
                "evacuation corridors, or resource allocation.\n\n"
                "_Close this panel anytime — I'll be a button at the bottom._"
            ),
            "Data Analyst": (
                "DATA-LAB ready. I can walk you through methodology, "
                "statistical findings, and the WiDS 2021–2025 dataset.\n\n"
                "Ask about the Gi* analysis, SVI correlations, or signal gap statistics.\n\n"
                "_Close this panel anytime — I'll be a button at the bottom._"
            ),
        }.get(role, "Hello! How can I help?")
        from datetime import datetime as _dt
        st.session_state.ai_messages = [{
            "role": "assistant",
            "content": _welcome,
            "ts": _dt.now().strftime("%H:%M"),
        }]

# Floating chat button (shown when AI panel is closed)
# Uses a CSS fixed-position link → sets ?chat=open → Python picks it up above
if not st.session_state.show_ai_panel:
    st.markdown("""
<style>
.chat-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 99999;
    background: #FF4B4B;
    color: #fff !important;
    border-radius: 50px;
    padding: 13px 22px;
    font-size: 0.95rem;
    font-weight: 700;
    text-decoration: none !important;
    box-shadow: 0 4px 18px rgba(255,75,75,0.55);
    letter-spacing: 0.01em;
    transition: background 0.15s;
}
.chat-fab:hover { background: #e03a3a; color: #fff !important; }
</style>
<a class="chat-fab" href="?chat=open">💬 AI Assistant</a>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHARE LOCATION PROMPT (one-time, non-analyst users)
# ─────────────────────────────────────────────────────────────────────────────
if (
    not st.session_state.location_prompt_shown
    and role != "Data Analyst"
    and not _needs_onboarding
):
    st.session_state.location_prompt_shown = True
    st.markdown("""
<style>
.loc-prompt {
    background: #161b22; border: 1.5px solid #30363d; border-radius: 10px;
    padding: 16px 20px; margin-bottom: 16px; display: flex;
    align-items: center; gap: 14px;
}
</style>
<div class="loc-prompt">
  <span style="font-size:1.6rem">📍</span>
  <span style="color:#e6edf3">
    <b>Share your location?</b><br>
    <span style="font-size:0.82rem;color:#8b949e">
      We can automatically detect nearby fires without you typing an address.
      Your location is used only in this session and never stored.
    </span>
  </span>
</div>
""", unsafe_allow_html=True)

    # JavaScript geolocation — posts coords back via query param
    _loc_html = """
<script>
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    function(pos) {
      var lat = pos.coords.latitude.toFixed(5);
      var lon = pos.coords.longitude.toFixed(5);
      var url = window.location.href.split('?')[0] + '?gps=' + lat + ',' + lon;
      window.location.href = url;
    },
    function(err) { /* user denied */ }
  );
}
</script>
"""
    col_yes, col_no, col_blank = st.columns([1, 1, 4])
    with col_yes:
        if st.button("📍 Share location", key="loc_share_yes", type="primary"):
            st.components.v1.html(_loc_html, height=0)
    with col_no:
        if st.button("Skip", key="loc_share_no"):
            pass  # just dismiss

# Check if GPS coords came back via query param
_gps_param = _qp.get("gps", "")
if _gps_param and st.session_state.user_gps_lat is None:
    try:
        _glat, _glon = _gps_param.split(",")
        st.session_state.user_gps_lat = float(_glat)
        st.session_state.user_gps_lon = float(_glon)
        # Also pre-fill the saved address inputs
        st.session_state["user_lat"] = st.session_state.user_gps_lat
        st.session_state["user_lon"] = st.session_state.user_gps_lon
        st.query_params.clear()
        st.success("Location detected — fire check will use your current position.")
        st.rerun()
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
if _needs_onboarding:
    _render_onboarding()

elif st.session_state.show_ai_panel and st.session_state.ai_fullscreen:
    # Full screen AI — chips visible, no border needed
    _render_ai_panel(role, is_fullscreen=True, show_border=False)

elif st.session_state.show_ai_panel:
    # Side-by-side — AI column gets the left-border sentinel, no chips
    main_col, ai_col = st.columns([3, 2], gap="small")
    with main_col:
        _render_page()
    with ai_col:
        _render_ai_panel(role, is_fullscreen=False, show_border=True)

else:
    # AI closed — full-width
    _render_page()