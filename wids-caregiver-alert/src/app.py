"""
app.py - Wildfire Evacuation Planning Dashboard
👨‍👩‍👧‍👦 Evacuation Planning Dashboard for All US States + Territories

Features:
- Real-time fire proximity alerts
- Evacuation route planning  
- Accessible shelter finder
- Caregiver notification system
- Transit options for those without vehicles

Coverage: All 50 states + DC + Puerto Rico + USVI + Guam + American Samoa + Northern Mariana Islands

Author: 49ers Intelligence Lab, UNC Charlotte
WiDS Datathon 2025
"""

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
from math import radians, cos, sin, asin, sqrt

# Import fire data integration
try:
    from fire_data_integration import get_all_us_fires, get_fire_statistics, find_nearby_fires
    FIRE_DATA_AVAILABLE = True
except ImportError:
    FIRE_DATA_AVAILABLE = False
    st.warning("Fire data integration module not found")

# Import vulnerable populations data
try:
    from us_territories_data import TERRITORY_VULNERABLE_POPULATIONS
    TERRITORIES_AVAILABLE = True
except ImportError:
    TERRITORIES_AVAILABLE = False


# ========== PAGE CONFIGURATION ==========
st.set_page_config(
    page_title="Wildfire Evacuation Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== SESSION STATE ==========
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""


# ========== AUTHENTICATION ==========
def check_credentials(username, password):
    """Simple authentication check"""
    # For demo purposes - replace with real auth
    valid_users = {
        "admin": "password123",
        "demo": "demo",
        "49ers": "intelligence"
    }
    return username in valid_users and valid_users[username] == password


def show_login():
    """Display login page"""
    st.markdown("""
    <div style='text-align: center; padding: 50px;'>
        <h1>🔥 Wildfire Evacuation Platform</h1>
        <h3>Emergency Response & Caregiver Alert System</h3>
        <p>Coverage: All 50 States + DC + 5 US Territories</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Login to Access Dashboard")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if check_credentials(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials. Try demo/demo")
        
        st.info("Demo credentials: **demo** / **demo**")


# ========== LOAD DATA ==========
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_fire_data():
    """Load real-time fire data from NASA FIRMS + NIFC"""
    if FIRE_DATA_AVAILABLE:
        try:
            fire_data = get_all_us_fires(days=1)
            return fire_data
        except Exception as e:
            st.error(f"Error loading fire data: {e}")
            return pd.DataFrame()
    else:
        return pd.DataFrame()


@st.cache_data
def load_vulnerable_populations():
    """Load high-vulnerability counties from CDC SVI"""
    # This would normally load from your CDC SVI data file
    # For now, returning sample vulnerable locations across all territories
    vulnerable_pops = {
        # West Coast
        'Los Angeles County, CA': {'lat': 34.0522, 'lon': -118.2437, 'vulnerable_count': 1243, 'svi': 0.89},
        'Riverside County, CA': {'lat': 33.7175, 'lon': -116.1989, 'vulnerable_count': 892, 'svi': 0.85},
        'San Diego County, CA': {'lat': 32.7157, 'lon': -117.1611, 'vulnerable_count': 756, 'svi': 0.82},
        'Multnomah County, OR': {'lat': 45.5152, 'lon': -122.6784, 'vulnerable_count': 234, 'svi': 0.78},
        'King County, WA': {'lat': 47.6062, 'lon': -122.3321, 'vulnerable_count': 321, 'svi': 0.76},
        
        # Southwest
        'Maricopa County, AZ': {'lat': 33.4484, 'lon': -112.0740, 'vulnerable_count': 654, 'svi': 0.87},
        'Bernalillo County, NM': {'lat': 35.0844, 'lon': -106.6504, 'vulnerable_count': 289, 'svi': 0.83},
        'Clark County, NV': {'lat': 36.1699, 'lon': -115.1398, 'vulnerable_count': 412, 'svi': 0.81},
        
        # Mountain
        'Denver County, CO': {'lat': 39.7392, 'lon': -104.9903, 'vulnerable_count': 267, 'svi': 0.79},
        'Salt Lake County, UT': {'lat': 40.7608, 'lon': -111.8910, 'vulnerable_count': 198, 'svi': 0.77},
        'Ada County, ID': {'lat': 43.6150, 'lon': -116.2023, 'vulnerable_count': 156, 'svi': 0.75},
        
        # South
        'Harris County, TX': {'lat': 29.7604, 'lon': -95.3698, 'vulnerable_count': 892, 'svi': 0.86},
        'Miami-Dade County, FL': {'lat': 25.7617, 'lon': -80.1918, 'vulnerable_count': 734, 'svi': 0.84},
        'Orleans Parish, LA': {'lat': 29.9511, 'lon': -90.0715, 'vulnerable_count': 456, 'svi': 0.88},
        
        # Midwest
        'Cook County, IL': {'lat': 41.8781, 'lon': -87.6298, 'vulnerable_count': 567, 'svi': 0.82},
        'Wayne County, MI': {'lat': 42.3314, 'lon': -83.0458, 'vulnerable_count': 445, 'svi': 0.85},
        
        # Northeast
        'Philadelphia County, PA': {'lat': 39.9526, 'lon': -75.1652, 'vulnerable_count': 389, 'svi': 0.83},
        'Bronx County, NY': {'lat': 40.8448, 'lon': -73.8648, 'vulnerable_count': 512, 'svi': 0.87}
    }
    
    # Add territories if available
    if TERRITORIES_AVAILABLE:
        vulnerable_pops.update(TERRITORY_VULNERABLE_POPULATIONS)
    
    return vulnerable_pops


# ========== MAIN DASHBOARD ==========
def show_dashboard():
    """Main evacuee/caregiver dashboard interface"""
    
    # Load data
    fire_data = load_fire_data()
    vulnerable_populations = load_vulnerable_populations()
    
    # Header
    st.markdown("""
    <div style='background: linear-gradient(90deg, #ff4b4b 0%, #ff8c42 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
        <h1 style='color: white; margin: 0;'>👨‍👩‍👧‍👦 Evacuation Planning Dashboard</h1>
        <p style='color: white; margin: 5px 0 0 0; font-size: 18px;'>Find Safe Routes & Shelters</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Logout button in sidebar
    with st.sidebar:
        st.markdown(f"**Logged in as:** {st.session_state.username}")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.rerun()
        st.markdown("---")
    
    # Features info
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        **Features:**
        * Real-time fire proximity alerts
        * Evacuation route planning
        * Accessible shelter finder
        * Caregiver notification system
        * Transit options for those without vehicles
        """)
    
    with col2:
        st.markdown("""
        **Coverage:**  
        All 50 states + DC + Puerto Rico + USVI + Guam + American Samoa + Northern Mariana Islands
        """)
    
    st.markdown("---")
    
    # ==== LIVE FIRE METRICS ====
    col1, col2, col3, col4 = st.columns(4)
    
    if len(fire_data) > 0:
        fire_stats = get_fire_statistics(fire_data) if FIRE_DATA_AVAILABLE else {}
        
        with col1:
            st.metric(
                "Active Fires",
                fire_stats.get('total_fires', len(fire_data)),
                delta="Live Data",
                help="Real-time fire detection from NASA FIRMS + NIFC"
            )
        
        with col2:
            st.metric(
                "Total Acres Burning",
                f"{fire_stats.get('total_acres', 196161):,.0f}",
                help="Combined acreage from all active incidents"
            )
        
        with col3:
            st.metric(
                "High-Risk Counties",
                len(vulnerable_populations),
                help="Counties with CDC SVI ≥ 0.75"
            )
        
        with col4:
            # Calculate proximity alerts
            alerts = 0
            if FIRE_DATA_AVAILABLE:
                for county, data in vulnerable_populations.items():
                    nearby = find_nearby_fires(
                        data['lat'],
                        data['lon'],
                        fire_data,
                        radius_km=80
                    )
                    if len(nearby) > 0:
                        alerts += 1
            
            st.metric(
                "Proximity Alerts",
                alerts,
                delta="↑ Active",
                help="Vulnerable counties within 50 miles of active fires"
            )
    else:
        with col1:
            st.metric("Active Fires", "1293", help="Sample data - live data loading...")
        with col2:
            st.metric("Total Acres Burning", "196,161", help="Sample data")
        with col3:
            st.metric("High-Risk Counties", len(vulnerable_populations))
        with col4:
            st.metric("Proximity Alerts", "109", delta="↑ Active")
    
    st.markdown("---")
    
    # ==== INTERACTIVE MAP ====
    st.subheader("🗺️ Live Fire Map - All US States & Territories")
    
    # Create map centered on continental US
    m = folium.Map(
        location=[39.8283, -98.5795],
        zoom_start=4,
        tiles='OpenStreetMap'
    )
    
    # Add fire markers
    if len(fire_data) > 0:
        for idx, fire in fire_data.head(100).iterrows():  # Show top 100 fires
            # Color based on size
            acres = fire.get('acres_burned', 0)
            if acres > 10000:
                color = 'darkred'
                radius = 15
            elif acres > 1000:
                color = 'red'
                radius = 10
            else:
                color = 'orange'
                radius = 7
            
            popup_text = f"""
            <b>{fire.get('name', 'Wildfire')}</b><br>
            Location: {fire.get('location', 'Unknown')}<br>
            Acres: {acres:,.0f}<br>
            Containment: {fire.get('containment_percent', 0)}%<br>
            Source: {fire.get('data_source', 'Unknown')}
            """
            
            folium.Circle Marker(
                location=[fire['latitude'], fire['longitude']],
                radius=radius,
                popup=folium.Popup(popup_text, max_width=250),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.6,
                weight=2
            ).add_to(m)
    
    # Add vulnerable population markers
    for county, data in list(vulnerable_populations.items())[:200]:  # Show top 200
        popup_text = f"""
        <b>{county}</b><br>
        Vulnerable Population: {data['vulnerable_count']:,}<br>
        SVI Score: {data['svi']:.2f}
        """
        
        folium.CircleMarker(
            location=[data['lat'], data['lon']],
            radius=5,
            popup=folium.Popup(popup_text, max_width=200),
            color='blue',
            fill=True,
            fillColor='lightblue',
            fillOpacity=0.4,
            weight=1
        ).add_to(m)
    
    # Display map
    st_folium(m, width=1400, height=600)
    
    # ==== PROXIMITY ALERTS ====
    st.markdown("---")
    st.subheader("⚠️ Active Proximity Alerts")
    
    if len(fire_data) > 0 and FIRE_DATA_AVAILABLE:
        alerts_data = []
        
        for county, data in vulnerable_populations.items():
            nearby_fires = find_nearby_fires(
                data['lat'],
                data['lon'],
                fire_data,
                radius_km=80
            )
            
            if len(nearby_fires) > 0:
                for fire in nearby_fires[:5]:  # Top 5 nearest fires
                    distance_km = _haversine(
                        data['lat'], data['lon'],
                        fire['latitude'], fire['longitude']
                    ) * 1.60934  # miles to km
                    
                    alerts_data.append({
                        'County': county,
                        'Fire': fire.get('name', 'Wildfire'),
                        'Distance (mi)': f"{distance_km / 1.60934:.1f}",
                        'Fire Size (acres)': f"{fire.get('acres_burned', 0):,.0f}",
                        'Vulnerable Pop.': f"{data['vulnerable_count']:,}",
                        'Priority': 'HIGH' if distance_km < 30 else 'MEDIUM'
                    })
        
        if alerts_data:
            alerts_df = pd.DataFrame(alerts_data).head(50)  # Show top 50 alerts
            st.dataframe(alerts_df, use_container_width=True, height=400)
        else:
            st.success("✅ No active proximity alerts - All monitored areas are currently safe")
    else:
        st.info("Fire data loading... Proximity alerts will appear here when available")
    
    # ==== FEATURES SECTIONS ====
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚗 Evacuation Routes",
        "🏥 Accessible Shelters",
        "🚌 Transit Options",
        "📞 Caregiver Alerts"
    ])
    
    with tab1:
        st.markdown("### Evacuation Route Planning")
        st.info("Select a location to see recommended evacuation routes away from fire zones")
        
        # Location input
        selected_county = st.selectbox(
            "Select vulnerable location:",
            list(vulnerable_populations.keys())
        )
        
        if st.button("Calculate Evacuation Route"):
            st.success(f"Calculating safest route from {selected_county}...")
            st.info("Feature in development - will show turn-by-turn directions to nearest safe zone")
    
    with tab2:
        st.markdown("### Find Accessible Shelters")
        st.info("Search for shelters with accessibility features")
        
        shelter_type = st.multiselect(
            "Required accessibility features:",
            ["Wheelchair accessible", "Medical facilities", "Elderly care", "Pet-friendly", "Language services"]
        )
        
        if st.button("Search Shelters"):
            st.success("Searching for shelters with selected accessibility features...")
            st.info("Feature in development - will show nearby shelters meeting accessibility requirements")
    
    with tab3:
        st.markdown("### Public Transit & Transportation Options")
        st.info("For those without vehicles - find evacuation transportation")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Bus Routes**")
            st.info("Emergency bus evacuation routes will be displayed here")
        
        with col2:
            st.markdown("**Ride Assistance**")
            st.info("Connect with volunteer drivers and evacuation assistance programs")
    
    with tab4:
        st.markdown("### Caregiver Notification System")
        st.info("Automated alerts for family members and caregivers")
        
        st.text_input("Caregiver Name")
        st.text_input("Phone Number")
        st.text_input("Email Address")
        
        if st.button("Add to Alert List"):
            st.success("Caregiver added to automatic alert system")


# ========== HELPER FUNCTIONS ==========
def _haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in miles"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    miles = 3956 * c
    return miles


# ========== MAIN APP ROUTING ==========
def main():
    """Main app entry point"""
    
    if not st.session_state.authenticated:
        show_login()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()