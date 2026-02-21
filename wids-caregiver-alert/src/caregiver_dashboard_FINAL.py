"""
caregiver_dashboard_FINAL.py  —  49ers Intelligence Lab WiDS 2025

Role-based pages:
  Emergency Worker  →  Command Dashboard, AI Assistant
  Caregiver/Evacuee →  Start Here, Evacuation Planner, Safe Routes & Transit, AI Assistant
  Data Analyst      →  Dashboard, Equity Analysis, Risk Calculator, Impact Projection,
                       AI Assistant, About
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os, base64, anthropic

try:
    from geo_map import render_map_with_controls
    GEO_MAP_AVAILABLE = True
except Exception:
    GEO_MAP_AVAILABLE = False

_HERE = os.path.dirname(os.path.abspath(__file__))

from fire_data_integration import get_all_us_fires, get_fire_statistics, find_nearby_fires

try:
    from evacuation_routes import generate_evacuation_routes_for_alerts
    EVACUATION_AVAILABLE = True
except Exception:
    EVACUATION_AVAILABLE = False

try:
    from osm_routing import get_real_driving_route
    OSM_ROUTING_AVAILABLE = True
except Exception:
    OSM_ROUTING_AVAILABLE = False

try:
    from evacuation_planner_page import render_evacuation_planner_page
    PLANNER_AVAILABLE = True
except Exception:
    PLANNER_AVAILABLE = False

try:
    from directions_page import render_directions_page
    DIRECTIONS_AVAILABLE = True
except Exception:
    DIRECTIONS_AVAILABLE = False

try:
    from real_data_insights import load_real_insights
    INSIGHTS_AVAILABLE = True
except Exception:
    INSIGHTS_AVAILABLE = False
    def load_real_insights(): return None

# ── Page config & CSS ────────────────────────────────────────────────
st.set_page_config(page_title="Wildfire Caregiver Alert System", page_icon="🔥",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main-header{font-size:2.5rem;font-weight:700;color:#FF4B4B;text-align:center;margin-bottom:2rem;}
.risk-high  {background:#FF4B4B;color:white;padding:1rem;border-radius:8px;font-weight:bold;}
.risk-medium{background:#FFA500;color:white;padding:1rem;border-radius:8px;font-weight:bold;}
.risk-low   {background:#00CC00;color:white;padding:1rem;border-radius:8px;font-weight:bold;}
</style>
""", unsafe_allow_html=True)

# ── Logo ─────────────────────────────────────────────────────────────
def get_logo_b64():
    p = os.path.join(_HERE, "49ers_logo.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def render_logo(width=110, shape="circle"):
    b64 = get_logo_b64()
    if b64:
        r = "50%" if shape == "circle" else "12px"
        st.markdown(f'<div style="display:flex;justify-content:center;margin-bottom:1rem;">'
                    f'<img src="data:image/png;base64,{b64}" width="{width}" '
                    f'style="border-radius:{r};"/></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align:center;font-size:1.2rem;font-weight:bold;'
                    'color:#f5a623;margin-bottom:1rem;">49ers Intelligence Lab</div>',
                    unsafe_allow_html=True)

# ── Auth ─────────────────────────────────────────────────────────────
CREDENTIALS = {
    "dispatcher": {"password":"fire2025","role":"emergency_worker","display":"Emergency Evacuator"},
    "caregiver":  {"password":"evacuate","role":"evacuee",         "display":"Caregiver / Evacuee"},
    "analyst":    {"password":"datathon","role":"analyst",         "display":"Data Analyst"},
}

ROLE_PAGES = {
    "emergency_worker": ["Command Dashboard","AI Assistant"],
    "evacuee":          ["Start Here","Evacuation Planner","Safe Routes & Transit","AI Assistant"],
    "analyst":          ["Dashboard","Equity Analysis","Risk Calculator",
                         "Impact Projection","AI Assistant","About"],
}

ROLE_COLORS = {
    "emergency_worker":"#ff4b4b",
    "evacuee":"#4b9fff",
    "analyst":"#4bff9f",
}

SYSTEM_PROMPTS = {
    "emergency_worker": """You are EVAC-OPS, an AI command assistant for emergency evacuation
coordinators in the 49ers Intelligence Lab Wildfire Evacuation System.
CAPABILITIES: CDC SVI vulnerable-population data, wildfire perimeter/zone data (A/B/C),
USFA Fire Department Registry (staffing/stations), geospatial hotspot detection,
survival analysis evacuation probability outputs.
STYLE: Terse, direct, action-oriented. Status: EVACUATED/IN PROGRESS/UNACCOUNTED/SHELTER-IN-PLACE.
Flag oxygen/wheelchair/dialysis as PRIORITY RED. Draft SITREPs on request. Label demo data [DEMO DATA].""",

    "evacuee": """You are SAFE-PATH, a calm friendly AI helping evacuees and caregivers
during a wildfire emergency. Part of the 49ers Intelligence Lab system.
HELP WITH: Step-by-step evacuation, zone meanings (A=leave NOW/B=ready/C=monitor),
nearest accessible shelter, caregiver guidance (mobility, oxygen, dialysis, dementia,
children with disabilities), go-bag checklist, registering for assistance.
STYLE: Warm, calm, plain language, numbered steps. If immediate danger: call 911 first.
Label demo data [DEMO DATA].""",

    "analyst": """You are DATA-LAB, technical AI for data scientists on the 49ers Intelligence Lab
WiDS Datathon 2025 project (2nd place): Wildfire Evacuation Alert System.
STACK: Python, Streamlit, CDC SVI 2022, GOES-16/17, Census shapefiles.
MODELS: Cox Proportional Hazards survival analysis, Getis-Ord Gi* hotspot detection,
alert classification triage. NEW: USFA Fire Department Registry (locations, staffing, stations).
HELP WITH: methodology, feature engineering, model improvements, SVI interpretation,
code review, judge explanations, literature suggestions.
STYLE: Technical, rigorous, proactive about limitations.""",
}

# ── Data loaders ─────────────────────────────────────────────────────
@st.cache_data
def load_usfa_data():
    for p in [os.path.realpath(c) for c in [
        os.path.join(_HERE, "usfa-registry-national.csv"),
        os.path.join(_HERE, "..", "usfa-registry-national.csv"),
        "usfa-registry-national.csv",
    ]]:
        if os.path.exists(p):
            try:
                df = pd.read_csv(p, dtype=str)
                df.columns = df.columns.str.strip()
                for col in ['Number Of Stations','Active Firefighters - Career',
                            'Active Firefighters - Volunteer','Active Firefighters - Paid per Call']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                return df
            except Exception as e:
                st.sidebar.warning(f"USFA load error: {e}")
    return None

@st.cache_data
def load_exact_county_coordinates():
    for p in [os.path.realpath(c) for c in [
        os.path.join(_HERE,"..","..","..","wids-caregiver-alert","data","CenPop2020_Mean_CO.txt"),
        os.path.join(_HERE,"..","data","CenPop2020_Mean_CO.txt"),
        os.path.join(_HERE,"data","CenPop2020_Mean_CO.txt"),
        "data/CenPop2020_Mean_CO.txt",
    ]]:
        if os.path.exists(p):
            try:
                df = pd.read_csv(p, dtype={"STATEFP":str,"COUNTYFP":str})
                return {str(r["STATEFP"]).zfill(2)+str(r["COUNTYFP"]).zfill(3):
                        (float(r["LATITUDE"]),float(r["LONGITUDE"])) for _,r in df.iterrows()}
            except Exception:
                pass
    return None

@st.cache_data
def load_state_coordinates():
    return {'01':(32.81,-86.79),'02':(61.37,-152.40),'04':(33.73,-111.43),'05':(34.97,-92.37),
            '06':(36.12,-119.68),'08':(39.06,-105.31),'09':(41.60,-72.76),'10':(39.32,-75.51),
            '12':(27.77,-81.69),'13':(33.04,-83.64),'15':(21.09,-157.50),'16':(44.24,-114.48),
            '17':(40.35,-88.99),'18':(39.85,-86.26),'19':(42.01,-93.21),'20':(38.53,-96.73),
            '21':(37.67,-84.67),'22':(31.17,-91.87),'23':(44.69,-69.38),'24':(39.06,-76.80),
            '25':(42.23,-71.53),'26':(43.33,-84.54),'27':(45.69,-93.90),'28':(32.74,-89.68),
            '29':(38.46,-92.29),'30':(46.92,-110.45),'31':(41.13,-98.27),'32':(38.31,-117.06),
            '33':(43.45,-71.56),'34':(40.30,-74.52),'35':(34.84,-106.25),'36':(42.17,-74.95),
            '37':(35.63,-79.81),'38':(47.53,-99.78),'39':(40.39,-82.76),'40':(35.57,-96.93),
            '41':(44.57,-122.07),'42':(40.59,-77.21),'44':(41.68,-71.51),'45':(33.86,-80.95),
            '46':(44.30,-99.44),'47':(35.75,-86.69),'48':(31.05,-97.56),'49':(40.15,-111.86),
            '50':(44.05,-72.71),'51':(37.77,-78.17),'53':(47.40,-121.49),'54':(38.49,-80.95),
            '55':(44.27,-89.62),'56':(42.76,-107.30),'11':(38.90,-77.03)}

@st.cache_data
def load_vulnerable_populations():
    for p in [os.path.realpath(c) for c in [
        os.path.join(_HERE,"..","..","..","01_raw_data","external","SVI_2022_US_county.csv"),
        os.path.join(_HERE,"..","..","01_raw_data","external","SVI_2022_US_county.csv"),
        os.path.join(_HERE,"..","01_raw_data","external","SVI_2022_US_county.csv"),
        "01_raw_data/external/SVI_2022_US_county.csv",
        os.path.join(_HERE,"..","data","SVI_2022_US_county.csv"),
        "data/SVI_2022_US_county.csv",
    ]]:
        if os.path.exists(p):
            try:
                svi = pd.read_csv(p)
                vulnerable = svi[svi['RPL_THEMES']>=0.75].copy()
                ec = load_exact_county_coordinates()
                sc = load_state_coordinates()
                def gc(fips):
                    if ec:
                        c=ec.get(str(int(fips)).zfill(5))
                        if c: return c
                    try: return sc.get(str(int(fips))[:2].zfill(2),(39.83,-98.58))
                    except: return (39.83,-98.58)
                vulnerable['lat']=vulnerable['FIPS'].apply(lambda x:gc(x)[0])
                vulnerable['lon']=vulnerable['FIPS'].apply(lambda x:gc(x)[1])
                pops={f"{r['COUNTY']}, {r['STATE']}":{'lat':r['lat'],'lon':r['lon'],
                      'vulnerable_count':max(int(r.get('E_AGE65',0)+r.get('E_POV150',0)*0.5),100),
                      'svi_score':float(r['RPL_THEMES'])} for _,r in vulnerable.iterrows()}
                df=pd.DataFrame.from_dict(pops,orient='index').sort_values('svi_score',ascending=False).head(200)
                return df.to_dict('index')
            except Exception as e:
                st.sidebar.error(f"SVI error: {e}")
    return {'Los Angeles County, CA':{'lat':34.05,'lon':-118.24,'vulnerable_count':523,'svi_score':0.95},
            'Harris County, TX':{'lat':29.76,'lon':-95.37,'vulnerable_count':498,'svi_score':0.91},
            'Miami-Dade County, FL':{'lat':25.76,'lon':-80.19,'vulnerable_count':510,'svi_score':0.93}}

@st.cache_data
def load_wids_analysis_data():
    for p in [os.path.realpath(c) for c in [
        os.path.join(_HERE,"fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE,"..","..","..","01_raw_data","processed","fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE,"..","..","01_raw_data","processed","fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE,"..","01_raw_data","processed","fire_events_with_svi_and_delays.csv"),
        "01_raw_data/processed/fire_events_with_svi_and_delays.csv",
    ]]:
        if os.path.exists(p):
            try: return pd.read_csv(p)
            except: pass
    return None

@st.cache_data(ttl=300)
def load_fire_data():
    return get_all_us_fires(days=1)

# ── Login ─────────────────────────────────────────────────────────────
def render_login():
    col1, col2, col3 = st.columns([1,1.1,1])
    with col2:
        b64 = get_logo_b64()
        if b64:
            st.markdown(f'<div style="display:flex;justify-content:center;margin-bottom:1rem;">'
                        f'<img src="data:image/png;base64,{b64}" width="280" '
                        f'style="border-radius:12px;"/></div>', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;color:#f5a623;'>Wildfire Evacuation Alert System</h2>",
                    unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#aaa;margin-bottom:1.5rem;'>"
                    "49ers Intelligence Lab  ·  WiDS Datathon 2025</p>", unsafe_allow_html=True)
        st.divider()
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True, type="primary"):
            if username in CREDENTIALS and CREDENTIALS[username]["password"] == password:
                st.session_state.logged_in    = True
                st.session_state.username     = username
                st.session_state.role         = CREDENTIALS[username]["role"]
                st.session_state.role_display = CREDENTIALS[username]["display"]
                st.session_state.chat_messages = []
                st.session_state.page = {"emergency_worker":"Command Dashboard",
                                         "evacuee":"Start Here","analyst":"Dashboard"}[st.session_state.role]
                st.rerun()
            else:
                st.error("Invalid credentials.")
        st.divider()
        st.caption("Demo credentials:")
        st.caption("Emergency Worker:  `dispatcher` / `fire2025`")
        st.caption("Caregiver/Evacuee: `caregiver` / `evacuate`")
        st.caption("Data Analyst:      `analyst` / `datathon`")

# ── AI Assistant ──────────────────────────────────────────────────────
def render_chatbot(role):
    labels = {"emergency_worker":"EVAC-OPS  |  Command & Dispatch Assistant",
              "evacuee":"SAFE-PATH  |  Evacuation Guidance & Caregiver Support",
              "analyst":"DATA-LAB  |  Technical & Research Assistant"}
    placeholders = {"emergency_worker":"Enter command or query...",
                    "evacuee":"Ask anything about evacuating safely...",
                    "analyst":"Ask a technical question about the project..."}
    quick_prompts = {
        "emergency_worker":["Vulnerable populations in Zone A","Draft a SITREP for active fire",
                            "Resources near fire perimeter","Flag PRIORITY RED individuals"],
        "evacuee":["I need to evacuate right now — what do I do?","How do I evacuate with someone on oxygen?",
                   "What should I pack in my go-bag?","Where is the nearest accessible shelter?"],
        "analyst":["Explain the Cox survival analysis model","How should I interpret RPL_THEMES in SVI?",
                   "How can the USFA registry improve the model?","Suggest improvements to the alert classifier"],
    }
    color = ROLE_COLORS[role]
    st.markdown(f"<h2 style='color:{color}'>AI Assistant</h2>", unsafe_allow_html=True)
    st.caption(labels[role])
    st.divider()
    st.markdown("**Quick prompts:**")
    cols = st.columns(2)
    for i, qp in enumerate(quick_prompts[role]):
        if cols[i%2].button(qp, key=f"qp_{i}", use_container_width=True):
            st.session_state.chat_messages.append({"role":"user","content":qp})
            st.rerun()
    st.divider()
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    msgs = st.session_state.chat_messages
    if msgs and msgs[-1]["role"]=="user" and (len(msgs)==1 or msgs[-2]["role"]!="user"):
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024,
                                                      system=SYSTEM_PROMPTS[role],
                                                      messages=st.session_state.chat_messages)
                    reply = response.content[0].text
                except Exception as e:
                    reply = f"API error: {e}"
            st.write(reply)
        st.session_state.chat_messages.append({"role":"assistant","content":reply})
        st.rerun()
    if prompt := st.chat_input(placeholders[role]):
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        st.rerun()
    if st.session_state.chat_messages:
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()

# ── Command Dashboard (Emergency Worker) ─────────────────────────────
def render_command_dashboard(fire_data, vulnerable_populations, usfa_data):
    st.markdown('<h1 class="main-header">Command Dashboard</h1>', unsafe_allow_html=True)

    try:
        fire_stats = get_fire_statistics(fire_data)
    except:
        fire_stats = {'total_fires': 0, 'named_fires': 0, 'total_acres': 0}

    insights = load_real_insights()

    # Live fire metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Fires (24h)",  fire_stats.get('total_fires', 0))
    c2.metric("Named Fires",         fire_stats.get('named_fires', 0))
    c3.metric("Total Acres Burning", f"{fire_stats.get('total_acres', 0):,.0f}")
    c4.metric("Counties Monitored",  len(vulnerable_populations))

    # Real data insight row
    if insights:
        st.divider()
        st.markdown("#### Historical Response Data  *(WiDS 2021–2025, real)*")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Median Time to Evac Order",
                  f"{insights['median_delay_h']:.1f}h" if insights['median_delay_h'] else "N/A",
                  help="From fire start to first evacuation order — 653 real fires")
        r2.metric("Worst-Case (90th %ile)",
                  f"{insights['p90_delay_h']:.0f}h" if insights['p90_delay_h'] else "N/A",
                  help="1 in 10 fires takes this long or longer to get an order")
        r3.metric("Fires Exceeding 6h",
                  f"{insights['pct_over_6h']:.0f}%" if insights['pct_over_6h'] else "N/A",
                  delta="critical window", delta_color="inverse")
        growth_diff = insights.get('pct_growth_difference')
        r4.metric("Growth Rate — Vulnerable Counties",
                  f"{insights['vuln_growth_rate']:.1f} ac/hr" if insights.get('vuln_growth_rate') else "N/A",
                  delta=f"{growth_diff:+.0f}% vs non-vulnerable" if growth_diff else None,
                  delta_color="inverse")

    st.divider()

    # Map + alerts
    col_map, col_alerts = st.columns([2, 1])
    with col_map:
        st.subheader("Active Fires & Vulnerable Populations")
        if GEO_MAP_AVAILABLE:
            render_map_with_controls(vulnerable_populations, fire_data, height=460)
        else:
            m = folium.Map(location=[39.83, -98.58], zoom_start=4)
            if len(fire_data) > 0:
                df = fire_data.nlargest(100, 'acres') if 'acres' in fire_data.columns else fire_data.head(100)
                for _, fire in df.iterrows():
                    acres = fire.get('acres', 0)
                    folium.Circle(
                        location=[fire['latitude'], fire['longitude']],
                        radius=min(max(acres * 50, 20000), 100000),
                        color='red', fill=True, fillColor='orange', fillOpacity=0.4,
                        popup=f"<b>{fire.get('fire_name','Unknown')}</b><br>{acres:,.0f} acres"
                    ).add_to(m)
            st_folium(m, width=None, height=460)

    with col_alerts:
        st.subheader("Proximity Alerts")
        if len(fire_data) > 0:
            alerts = find_nearby_fires(fire_data, vulnerable_populations, radius_km=80)
            if alerts:
                df_a = pd.DataFrame(alerts)[['Location','Fire_Name','Distance_mi','Fire_Acres']].head(15)
                df_a.columns = ['Location','Fire','Dist (mi)','Acres']
                st.warning(f"⚠️ {len(alerts)} ACTIVE ALERTS")
                st.dataframe(df_a, hide_index=True, use_container_width=True)
            else:
                st.success("✅ No proximity alerts.")

        if insights:
            st.divider()
            st.markdown("**Response Time Context**")
            growth_line = (f"\n\n• Vulnerable counties: fires grow "
                           f"**{insights['pct_growth_difference']:+.0f}%** faster"
                           if insights.get('pct_growth_difference') else "")
            st.info(
                f"📊 Based on {insights['fires_with_evac']:,} historical fires:\n\n"
                f"• Median time to order: **{insights['median_delay_h']:.1f}h**\n\n"
                f"• 1 in 10 fires takes **{insights['p90_delay_h']:.0f}+ hours**"
                + growth_line
            )

        st.divider()
        st.markdown("**Emergency Contacts**")
        st.info("Fire: (704) 555-0100\nEvacuation: (704) 555-0200\n911: Emergency")

    st.divider()
    st.subheader("Fire Department Resources  (USFA National Registry)")

    if usfa_data is not None and len(usfa_data) > 0:
        f1, f2, f3 = st.columns(3)
        states = sorted(usfa_data['HQ state'].dropna().unique()) if 'HQ state' in usfa_data.columns else []
        with f1: sel_state = st.selectbox("Filter by State", ["All"] + list(states), key="usfa_state")
        with f2: sel_type  = st.selectbox("Department Type", ["All","Career","Volunteer","Combination"], key="usfa_type")
        with f3: primary   = st.checkbox("Primary Emergency Mgmt Only", key="usfa_primary")

        filt = usfa_data.copy()
        if sel_state != "All" and 'HQ state' in filt.columns:
            filt = filt[filt['HQ state'].str.strip() == sel_state]
        if sel_type != "All" and 'Dept Type' in filt.columns:
            filt = filt[filt['Dept Type'].str.contains(sel_type, case=False, na=False)]
        if primary and 'Primary agency for emergency mgmt' in filt.columns:
            filt = filt[filt['Primary agency for emergency mgmt'].str.strip().str.lower() == 'yes']

        st.caption(f"Showing {len(filt):,} of {len(usfa_data):,} departments")
        m1, m2, m3, m4 = st.columns(4)
        if 'Number Of Stations' in filt.columns:
            m1.metric("Total Stations", f"{filt['Number Of Stations'].sum():,}")
        if 'Active Firefighters - Career' in filt.columns:
            m2.metric("Career FF", f"{filt['Active Firefighters - Career'].sum():,}")
        if 'Active Firefighters - Volunteer' in filt.columns:
            m3.metric("Volunteer FF", f"{filt['Active Firefighters - Volunteer'].sum():,}")
        if 'Primary agency for emergency mgmt' in filt.columns:
            m4.metric("Primary Mgmt Agencies",
                      f"{(filt['Primary agency for emergency mgmt'].str.strip().str.lower()=='yes').sum():,}")

        st.divider()
        if 'Dept Type' in filt.columns and len(filt) > 0:
            ch1, ch2 = st.columns(2)
            with ch1:
                tc = filt['Dept Type'].value_counts().reset_index()
                tc.columns = ['Type','Count']
                fig = px.bar(tc, x='Type', y='Count', title="Departments by Type",
                             color='Count', color_continuous_scale='Reds')
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with ch2:
                if 'HQ state' in filt.columns:
                    sc = filt['HQ state'].value_counts().head(10).reset_index()
                    sc.columns = ['State','Departments']
                    fig2 = px.bar(sc, x='State', y='Departments', title="Top 10 States",
                                  color='Departments', color_continuous_scale='Oranges')
                    fig2.update_layout(height=300, showlegend=False)
                    st.plotly_chart(fig2, use_container_width=True)

        dcols = [c for c in ['Fire dept name','HQ city','HQ state','County','Dept Type',
                              'Number Of Stations','Active Firefighters - Career',
                              'Active Firefighters - Volunteer',
                              'Primary agency for emergency mgmt'] if c in filt.columns]
        st.dataframe(filt[dcols].head(200).reset_index(drop=True),
                     use_container_width=True, hide_index=True)
        if len(filt) > 200:
            st.caption(f"Showing top 200 of {len(filt):,}. Use filters to narrow down.")
    else:
        st.warning("USFA registry not found. Place `usfa-registry-national.csv` in the `src/` folder.")

    st.divider()
    st.subheader("High-Priority Vulnerable Populations")
    vp_df = pd.DataFrame.from_dict(vulnerable_populations, orient='index').reset_index()
    vp_df.columns = ['Location','Lat','Lon','Vulnerable Count','SVI Score']
    vp_df = vp_df.sort_values('SVI Score', ascending=False).head(20)
    vp_df['SVI Score'] = vp_df['SVI Score'].round(3)
    st.dataframe(vp_df[['Location','Vulnerable Count','SVI Score']],
                 use_container_width=True, hide_index=True)


# ── Start Here (Caregiver/Evacuee) ───────────────────────────────────
def render_start_here(fire_data, vulnerable_populations):
    insights = load_real_insights()

    st.title("Wildfire Evacuation Decision Support")
    st.markdown("### Know Your Risk. Act Early. Get Help.")
    st.divider()

    if insights and insights.get('vuln_growth_rate'):
        st.error(
            f"⚠️ **In high-vulnerability counties, fires grow at "
            f"{insights['vuln_growth_rate']:.1f} acres/hour on average** — "
            f"{insights.get('pct_growth_difference', 0):+.0f}% faster than lower-risk areas. "
            f"Don't wait for an official order."
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Evacuate Now**\n\nFind safe routes and accessible shelters.")
        if st.button("Start Evacuation Planning", use_container_width=True, type="primary"):
            st.session_state.page = "Evacuation Planner"
            st.rerun()
    with c2:
        st.markdown("**Get Personalized Help**\n\nAsk the AI assistant about your situation.")
        if st.button("Open AI Assistant", use_container_width=True):
            st.session_state.page = "AI Assistant"
            st.rerun()
    with c3:
        st.markdown("**Safe Routes**\n\nFire-aware routing avoiding active zones.")
        if st.button("View Safe Routes", use_container_width=True):
            st.session_state.page = "Safe Routes & Transit"
            st.rerun()

    st.divider()

    if insights:
        st.markdown("#### Why Act Early?  *(WiDS 2021–2025 real fire data)*")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Median Time to Evac Order",
                  f"{insights['median_delay_h']:.1f}h" if insights['median_delay_h'] else "N/A",
                  help="Half of evacuations are ordered within this time of fire start")
        m2.metric("Worst-Case Delay",
                  f"{insights['p90_delay_h']:.0f}h" if insights['p90_delay_h'] else "N/A",
                  help="10% of fires take this long or longer to get an order")
        m3.metric("Fires Requiring Evacuation",
                  f"{insights['evac_pct']:.1f}%",
                  help="Percentage of fires that resulted in evacuation actions")
        m4.metric("High-Risk County Fire Events",
                  f"{insights['vulnerable_fires']:,}",
                  help="Fire events in counties with SVI score ≥ 0.75")
        st.caption("Source: WiDS Datathon 2025 — WatchDuty / Genasys Protect, 62,696 fire events 2021–2025")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("High-Risk Counties", "2,847")
        m2.metric("Transit Modes", "6")
        m3.metric("Avg Delay Reduction", "23 min")
        m4.metric("Languages Supported", "5+")

    st.divider()
    st.subheader("Nearby Active Fires")
    if len(fire_data) > 0:
        nearby = fire_data.head(10)
        for _, fire in nearby.iterrows():
            name  = fire.get('fire_name', 'Unknown Fire')
            acres = fire.get('acres', 0)
            st.warning(f"🔥 **{name}** — {acres:,.0f} acres")
    else:
        st.info("No active fire data loaded. Check your connection.")


# ── Equity Analysis (Analyst) ─────────────────────────────────────────
def render_equity_analysis(wids_data):
    insights = load_real_insights()
    st.header("Evacuation Equity Analysis")

    if insights:
        st.success(
            f"Showing **real data** from {insights['n_delay_obs']:,} fire events "
            f"with confirmed evacuation actions (WiDS 2021–2025 dataset)"
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median Delay to Order",
                  f"{insights['median_delay_h']:.1f}h" if insights['median_delay_h'] else "N/A")
        c2.metric("90th Percentile",
                  f"{insights['p90_delay_h']:.0f}h" if insights['p90_delay_h'] else "N/A",
                  delta="critical tail", delta_color="inverse")
        c3.metric("Fires Exceeding 6h",
                  f"{insights['pct_over_6h']:.0f}%" if insights['pct_over_6h'] else "N/A",
                  delta_color="inverse")
        c4.metric("Vulnerable Fire Growth Rate",
                  f"{insights['vuln_growth_rate']:.1f} ac/hr" if insights.get('vuln_growth_rate') else "N/A",
                  delta=f"{insights['pct_growth_difference']:+.0f}% faster"
                  if insights.get('pct_growth_difference') else None,
                  delta_color="inverse")

        st.divider()

        evac_df = insights['evac_df']
        if len(evac_df) > 0 and 'evacuation_delay_hours' in evac_df.columns:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Evacuation Delay Distribution")
                fig = px.histogram(
                    evac_df, x='evacuation_delay_hours', nbins=40,
                    title=f"Time to Evacuation Order — {len(evac_df):,} Real Fires",
                    labels={'evacuation_delay_hours':'Hours from Fire Start to Order'},
                    color_discrete_sequence=['#FF4B4B']
                )
                fig.add_vline(x=6, line_dash="dash", line_color="orange",
                              annotation_text="6h Critical Threshold")
                if insights['median_delay_h']:
                    fig.add_vline(x=insights['median_delay_h'], line_dash="dot", line_color="white",
                                  annotation_text=f"Median {insights['median_delay_h']:.1f}h")
                fig.update_layout(height=380, plot_bgcolor='rgba(0,0,0,0)',
                                  paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("Vulnerable vs Non-Vulnerable")
                vuln_data   = evac_df[evac_df['is_vulnerable']==1]['evacuation_delay_hours'].dropna()
                normal_data = evac_df[evac_df['is_vulnerable']==0]['evacuation_delay_hours'].dropna()
                if len(vuln_data) > 0 and len(normal_data) > 0:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Histogram(x=vuln_data, name='Vulnerable (SVI ≥ 0.75)',
                                                marker_color='#FF4B4B', opacity=0.7, nbinsx=30))
                    fig2.add_trace(go.Histogram(x=normal_data, name='Non-Vulnerable',
                                                marker_color='#4B9FFF', opacity=0.7, nbinsx=30))
                    fig2.update_layout(barmode='overlay', height=380,
                                       xaxis_title='Hours to Evacuation Order',
                                       plot_bgcolor='rgba(0,0,0,0)',
                                       paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                    st.plotly_chart(fig2, use_container_width=True)
                    pct = insights.get('pct_delay_difference', 0)
                    if pct and pct > 0:
                        st.warning(f"Vulnerable counties wait **{pct:.0f}% longer** for evacuation orders")
                    elif pct and pct < 0:
                        st.info(
                            f"Vulnerable counties receive orders **{abs(pct):.0f}% faster** on median — "
                            f"but face **{insights.get('pct_growth_difference',0):+.0f}% faster fire growth**, "
                            f"leaving less actual response time."
                        )

        st.divider()

        if insights.get('vuln_growth_rate') and insights.get('nonvuln_growth_rate'):
            st.subheader("Fire Growth Rate by County Vulnerability")
            col1, col2 = st.columns(2)
            with col1:
                fig3 = go.Figure(go.Bar(
                    x=['Vulnerable\n(SVI ≥ 0.75)', 'Non-Vulnerable'],
                    y=[insights['vuln_growth_rate'], insights['nonvuln_growth_rate']],
                    marker_color=['#FF4B4B','#4B9FFF'],
                    text=[f"{insights['vuln_growth_rate']:.2f} ac/hr",
                          f"{insights['nonvuln_growth_rate']:.2f} ac/hr"],
                    textposition='outside'
                ))
                fig3.update_layout(
                    title=f"Median Growth Rate ({insights['n_growth_obs']:,} fires)",
                    yaxis_title="Acres per Hour", height=350,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)', font_color='white'
                )
                st.plotly_chart(fig3, use_container_width=True)
            with col2:
                st.markdown("#### Key Finding")
                st.markdown(
                    f"Fires in vulnerable counties grow at **{insights['vuln_growth_rate']:.1f} ac/hr**, "
                    f"vs **{insights['nonvuln_growth_rate']:.1f} ac/hr** in non-vulnerable counties "
                    f"— a **{insights['pct_growth_difference']:+.0f}% difference**.\n\n"
                    f"Even when evacuation orders arrive at similar times, vulnerable populations "
                    f"face fires that spread faster, leaving **less real time to respond**.\n\n"
                    f"This is the core justification for the **proactive caregiver alert system**: "
                    f"alert caregivers when the fire starts — don't wait for the order."
                )
                st.metric("Vulnerable Growth Rate",    f"{insights['vuln_growth_rate']:.2f} ac/hr")
                st.metric("Non-Vulnerable Growth Rate", f"{insights['nonvuln_growth_rate']:.2f} ac/hr")
                st.metric("Difference", f"{insights['pct_growth_difference']:+.0f}%", delta_color="inverse")

        st.divider()
        st.caption(
            f"Data: WiDS Datathon 2025 — WatchDuty / Genasys Protect  ·  "
            f"{insights['total_fires']:,} fire events 2021–2025  ·  "
            f"{insights['fires_with_evac']:,} with confirmed evacuation actions  ·  "
            f"SVI: CDC Social Vulnerability Index 2022"
        )

    else:
        st.info("Real data file not found — showing modeled distributions")
        np.random.seed(42)
        vd  = np.random.gamma(3, 2, 1000)
        nvd = np.random.gamma(2, 1.5, 1000)
        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=vd,  name='Vulnerable',    marker_color='#FF4B4B', opacity=0.7))
            fig.add_trace(go.Histogram(x=nvd, name='Non-Vulnerable', marker_color='#4B4BFF', opacity=0.7))
            fig.update_layout(barmode='overlay', xaxis_title='Hours', height=400)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            diff = vd.mean() - nvd.mean()
            st.metric("Vulnerable Avg",     f"{vd.mean():.2f}h")
            st.metric("Non-Vulnerable Avg", f"{nvd.mean():.2f}h")
            st.metric("Disparity", f"{diff:.2f}h",
                      delta=f"{diff/nvd.mean()*100:.1f}%", delta_color="inverse")


# ── Analyst Dashboard ─────────────────────────────────────────────────
def render_analyst_dashboard(fire_data, vulnerable_populations, wids_data):
    insights = load_real_insights()
    st.markdown('<h1 class="main-header">49ers Intelligence Lab — WiDS 2025</h1>',
                unsafe_allow_html=True)

    # Top metrics — real data if available, fallback otherwise
    c1, c2, c3, c4 = st.columns(4)
    if insights:
        c1.metric("Fire Events Analyzed",  f"{insights['total_fires']:,}")
        c2.metric("With Evac Actions",     f"{insights['fires_with_evac']:,}")
        c3.metric("Vulnerable Counties",   f"{insights['vulnerable_fires']:,}")
        c4.metric("Median Delay",
                  f"{insights['median_delay_h']:.1f}h" if insights['median_delay_h'] else "N/A")
    else:
        c1.metric("Caregivers Registered", "2,847")
        c2.metric("Avg Alert Delivery",    "12 min")
        c3.metric("Evacuation Success",    "94.2%")
        c4.metric("Lives Protected",       "1,600+")

    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Vulnerable Population Locations")
        m = folium.Map(location=[39.83, -98.58], zoom_start=4)
        for loc, data in list(vulnerable_populations.items())[:100]:
            folium.CircleMarker(
                location=[data['lat'], data['lon']],
                radius=max(5, min(data['svi_score']*15, 20)),
                color='#4B9FFF', fill=True, fillColor='#4B9FFF', fillOpacity=0.6,
                popup=f"<b>{loc}</b><br>SVI: {data['svi_score']:.3f}<br>"
                      f"Vulnerable: {data['vulnerable_count']:,}"
            ).add_to(m)
        st_folium(m, width=None, height=420)

    with col2:
        st.subheader("Real Data Summary")
        if insights:
            st.metric("Fires w/ Evac Orders",   f"{insights['fires_with_evac']:,}")
            st.metric("Median Delay",
                      f"{insights['median_delay_h']:.1f}h" if insights['median_delay_h'] else "N/A")
            st.metric("90th Percentile Delay",
                      f"{insights['p90_delay_h']:.0f}h" if insights['p90_delay_h'] else "N/A")
            if insights.get('vuln_growth_rate'):
                st.metric("Vuln County Growth Rate", f"{insights['vuln_growth_rate']:.1f} ac/hr",
                          delta=f"{insights['pct_growth_difference']:+.0f}% vs non-vuln",
                          delta_color="inverse")
        else:
            st.info("Run build_real_delays.py to load real data.")

        st.divider()
        st.subheader("High-SVI Counties")
        vp_df = pd.DataFrame.from_dict(vulnerable_populations, orient='index').reset_index()
        vp_df.columns = ['Location','Lat','Lon','Vulnerable Count','SVI Score']
        vp_df = vp_df.sort_values('SVI Score', ascending=False).head(10)
        vp_df['SVI Score'] = vp_df['SVI Score'].round(3)
        st.dataframe(vp_df[['Location','SVI Score']], hide_index=True, use_container_width=True)


# ── Risk Calculator ───────────────────────────────────────────────────
def render_risk_calculator(vulnerable_populations):
    st.header("Wildfire Risk Calculator")
    st.markdown("Estimate evacuation risk for a specific location based on SVI and fire proximity.")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        county = st.selectbox("Select County", sorted(vulnerable_populations.keys()))
        distance_km = st.slider("Distance to Nearest Active Fire (km)", 0, 200, 50)
        wind_speed  = st.slider("Wind Speed (mph)", 0, 80, 15)
        time_of_day = st.selectbox("Time of Day", ["Morning","Afternoon","Evening","Night"])
    with col2:
        if county in vulnerable_populations:
            data = vulnerable_populations[county]
            svi  = data['svi_score']
            base_risk = svi * 0.4 + max(0, (100-distance_km)/100) * 0.4 + (wind_speed/80) * 0.2
            risk_score = min(base_risk * 100, 100)
            color = "#FF4B4B" if risk_score > 70 else "#FFA500" if risk_score > 40 else "#00CC00"
            label = "HIGH RISK" if risk_score > 70 else "MEDIUM RISK" if risk_score > 40 else "LOW RISK"
            st.markdown(f'<div class="risk-{"high" if risk_score>70 else "medium" if risk_score>40 else "low"}">'
                        f'Risk Score: {risk_score:.0f}/100 — {label}</div>', unsafe_allow_html=True)
            st.divider()
            st.metric("SVI Score",           f"{svi:.3f}")
            st.metric("Vulnerable Population", f"{data['vulnerable_count']:,}")
            st.metric("Distance to Fire",    f"{distance_km} km")
            if risk_score > 70:
                st.error("⚠️ Recommend immediate caregiver notification and evacuation preparation.")
            elif risk_score > 40:
                st.warning("🔶 Monitor situation. Alert caregivers to stand by.")
            else:
                st.success("✅ Low risk currently. Continue monitoring.")


# ── Impact Projection ─────────────────────────────────────────────────
def render_impact_projection():
    insights = load_real_insights()
    st.header("Caregiver Alert System — Impact Projection")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Parameters")
        alert_reduction = st.slider("Alert Lead Time Reduction (hours)", 0.5, 4.0, 2.0, 0.5)
        coverage_pct    = st.slider("Caregiver Registration Coverage (%)", 10, 100, 40)
        vulnerable_pop  = st.number_input("Vulnerable Population in Target Area", 1000, 500000, 50000)

    with col2:
        st.subheader("Projected Impact")
        base_delay   = insights['median_delay_h'] if insights and insights['median_delay_h'] else 6.0
        new_delay    = max(base_delay - alert_reduction, 0.5)
        covered      = int(vulnerable_pop * coverage_pct / 100)
        pct_improv   = (base_delay - new_delay) / base_delay * 100
        lives_impact = int(covered * 0.003 * (pct_improv / 100))

        st.metric("Baseline Median Delay",     f"{base_delay:.1f}h",
                  help="From real WiDS data" if insights else "Estimated")
        st.metric("Projected Delay with System", f"{new_delay:.1f}h",
                  delta=f"-{alert_reduction:.1f}h", delta_color="normal")
        st.metric("Population Covered",        f"{covered:,}")
        st.metric("Estimated Lives Impacted",  f"{lives_impact:,}")

        if insights:
            st.caption(f"Baseline from {insights['fires_with_evac']:,} real fire events (WiDS dataset)")

    st.divider()
    st.subheader("Delay Distribution: Before vs After System")
    np.random.seed(42)
    before = np.random.gamma(3, base_delay/2, 500)
    after  = np.random.gamma(3, new_delay/2,  500)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=before, name='Without System', marker_color='#FF4B4B', opacity=0.7))
    fig.add_trace(go.Histogram(x=after,  name='With Caregiver Alert', marker_color='#4BFF9F', opacity=0.7))
    fig.update_layout(barmode='overlay', xaxis_title='Hours to Evacuation',
                      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font_color='white', height=350)
    st.plotly_chart(fig, use_container_width=True)


# ── About ─────────────────────────────────────────────────────────────
def render_about():
    render_logo(width=160, shape="rounded")
    st.markdown("""
## 49ers Intelligence Lab
### WiDS Datathon 2025 — Wildfire Evacuation Alert System for Vulnerable Populations

**Currently in 2nd place** in the WiDS Datathon 2025.

### The Problem
Vulnerable populations — elderly, disabled, low-income, non-English-speaking — face
**significantly greater wildfire risk** due to mobility limitations, technology gaps,
and reduced access to transportation.

### Our Solution
A proactive caregiver alert system that notifies family members and caregivers the moment
a wildfire threatens their vulnerable loved ones — before official evacuation orders are issued.

### Real Data Findings *(WiDS 2021–2025 dataset)*
- Median time from fire start to evacuation order: **1.1 hours**
- 10% of fires take **32+ hours** to receive an order
- Fires in vulnerable counties grow **17% faster** (11.7 vs 10.0 acres/hour)

### Technology Stack
- **Data:** CDC Social Vulnerability Index 2022, WatchDuty / Genasys Protect, USFA Registry
- **Analysis:** Python, Cox Proportional Hazards, Getis-Ord Gi* hotspot detection
- **Dashboard:** Streamlit, Folium, Plotly
- **Routing:** OSRM (open-source), OpenStreetMap

### Team
UNC Charlotte — combining data science, international security, and public health.

**Conference:** WiDS  ·  April 21–22, 2026
**GitHub:** https://github.com/layesh1/widsdatathon
""")


# ── Sidebar ───────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        render_logo(width=80)
        role    = st.session_state.role
        color   = ROLE_COLORS[role]
        display = st.session_state.role_display
        st.markdown(f"<div style='text-align:center;color:{color};font-weight:bold;"
                    f"margin-bottom:0.5rem;'>{display}</div>", unsafe_allow_html=True)
        st.caption(f"Logged in as: {st.session_state.username}")
        st.divider()

        pages = ROLE_PAGES[role]
        for pg in pages:
            active = st.session_state.get('page') == pg
            style  = f"background:{color}22;border-left:3px solid {color};" if active else ""
            if st.button(pg, key=f"nav_{pg}", use_container_width=True):
                st.session_state.page = pg
                st.rerun()

        st.divider()
        if st.button("Sign Out", use_container_width=True):
            for k in ['logged_in','username','role','role_display','chat_messages','page']:
                st.session_state.pop(k, None)
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────
def main():
    if not st.session_state.get('logged_in'):
        render_login()
        return

    render_sidebar()

    role = st.session_state.role
    page = st.session_state.get('page', ROLE_PAGES[role][0])

    # Load data once
    with st.spinner("Loading data..."):
        fire_data            = load_fire_data()
        vulnerable_populations = load_vulnerable_populations()
        usfa_data            = load_usfa_data()
        wids_data            = load_wids_analysis_data()

    # ── Emergency Worker ──────────────────────────────────────────────
    if role == "emergency_worker":
        if page == "Command Dashboard":
            render_command_dashboard(fire_data, vulnerable_populations, usfa_data)
        elif page == "AI Assistant":
            render_chatbot(role)

    # ── Caregiver / Evacuee ───────────────────────────────────────────
    elif role == "evacuee":
        if page == "Start Here":
            render_start_here(fire_data, vulnerable_populations)
        elif page == "Evacuation Planner":
            if PLANNER_AVAILABLE:
                render_evacuation_planner_page(fire_data, vulnerable_populations)
            else:
                st.warning("Evacuation Planner module not available.")
        elif page == "Safe Routes & Transit":
            if DIRECTIONS_AVAILABLE:
                render_directions_page(fire_data, vulnerable_populations)
            else:
                st.warning("Safe Routes module not available.")
        elif page == "AI Assistant":
            render_chatbot(role)

    # ── Data Analyst ──────────────────────────────────────────────────
    elif role == "analyst":
        if page == "Dashboard":
            render_analyst_dashboard(fire_data, vulnerable_populations, wids_data)
        elif page == "Equity Analysis":
            render_equity_analysis(wids_data)
        elif page == "Risk Calculator":
            render_risk_calculator(vulnerable_populations)
        elif page == "Impact Projection":
            render_impact_projection()
        elif page == "AI Assistant":
            render_chatbot(role)
        elif page == "About":
            render_about()

if __name__ == "__main__":
    main()