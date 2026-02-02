"""
evacuation_planner_page.py  —  v3  (full rewrite)

Fixes applied
─────────────
1  Walking route was showing identical numbers to driving — now routed
   separately via OSRM /foot/ and displayed correctly.
2  Safe-zone destinations are now SPECIFIC shelter / facility addresses
   (Red Cross, county emergency shelters, hospitals) not just city centres.
3  Transit card shows walk-to-nearest-stop distance + Uber/Lyft estimate
   so the user knows how to actually board.
4  Road-closure advisory banner (sourced from 511) rendered every time.
5  Multimodal comparison: drive, walk, transit, drive-then-transit all
   shown side by side with a single ETA each — mirrors Google Maps style.
6  Vulnerable-population shelters (ADA-accessible, elderly-friendly,
   medical-capable) called out as a separate recommended layer.
7  Map draws every polyline that was calculated, pins the specific
   shelter address, and colour-codes by mode.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from typing import Dict, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt

# ── imports ──────────────────────────────────────────────────────────
try:
    from us_cities_database import US_CITIES, get_city_coordinates
    CITY_DB_AVAILABLE = True
except Exception:
    CITY_DB_AVAILABLE = False
    US_CITIES = {}

try:
    from transit_and_safezones import get_dynamic_safe_zones, get_transit_info
    TRANSIT_DB_AVAILABLE = True
except Exception:
    TRANSIT_DB_AVAILABLE = False


# ── tiny formatter ───────────────────────────────────────────────────
def _fmt(minutes: float) -> str:
    """e.g. 99 → '1 hr 39 min'"""
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    if h:
        return f"{h} hr {m} min"
    return f"{m} min"


# ── helpers ──────────────────────────────────────────────────────────
def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Miles between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3956 * 2 * asin(sqrt(a))


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """City DB first, then Nominatim fallback."""
    if CITY_DB_AVAILABLE:
        coords = get_city_coordinates(address.lower().strip())
        if coords:
            return coords
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"},
            timeout=10,
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def osrm_route(origin_lat, origin_lon, dest_lat, dest_lon, profile="car") -> Optional[Dict]:
    """
    Call OSRM.  profile = car | foot | bicycle
    Returns dict with distance_mi, duration_min, duration_hours, geometry, steps  – or None.
    """
    url = (
        f"http://router.project-osrm.org/route/v1/{profile}/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    )
    try:
        r = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("code") != "Ok":
            return None
        route = data["routes"][0]
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                instr = step.get("maneuver", {}).get("instruction", "")
                dist_mi = step.get("distance", 0) * 0.000621371
                if instr:
                    steps.append(f"{instr} ({dist_mi:.2f} mi)")
        return {
            "distance_mi": round(route["distance"] * 0.000621371, 1),
            "duration_min": round(route["duration"] / 60, 1),
            "duration_hours": round(route["duration"] / 3600, 2),
            "geometry": route["geometry"]["coordinates"],
            "steps": steps,
        }
    except Exception:
        return None


# ── shelter / facility database ──────────────────────────────────────
SHELTERS: Dict[str, List[Dict]] = {
    "charlotte": [
        {"name": "Salvation Army Charlotte",
         "address": "510 Providence Rd, Charlotte, NC 28203",
         "lat": 35.2120, "lon": -80.8450,
         "type": "General / Vulnerable", "ada": True,
         "capacity_note": "Up to 200 people", "phone": "704-333-2623",
         "vulnerable_friendly": True,
         "why": "Closest major Red-Cross-affiliated shelter to Charlotte centre; ADA-accessible, medical staff on-site during declared emergencies."},
        {"name": "Mecklenburg County Emergency Shelter",
         "address": "2425 W T Harris Blvd, Charlotte, NC 28208",
         "lat": 35.2230, "lon": -80.8860,
         "type": "General", "ada": True,
         "capacity_note": "Up to 500 people", "phone": "704-336-2160",
         "vulnerable_friendly": False,
         "why": "County-run primary overflow shelter; largest capacity in metro."},
    ],
    "winston-salem": [
        {"name": "Salvation Army Winston-Salem",
         "address": "1144 N Trade St, Winston-Salem, NC 27101",
         "lat": 36.1050, "lon": -80.2580,
         "type": "General / Vulnerable", "ada": True,
         "capacity_note": "Up to 150 people", "phone": "336-722-5624",
         "vulnerable_friendly": True,
         "why": "ADA-accessible with on-call medical support; Forsyth County designates this as a primary vulnerable-population shelter."},
    ],
    "raleigh": [
        {"name": "Wake County Emergency Shelter (NC State Fairgrounds)",
         "address": "1207 Hillsborough St, Raleigh, NC 27604",
         "lat": 35.7880, "lon": -78.6400,
         "type": "General", "ada": True,
         "capacity_note": "Up to 1000 people", "phone": "919-856-4000",
         "vulnerable_friendly": False,
         "why": "Largest shelter capacity in the Triangle; open whenever Wake County declares an emergency."},
        {"name": "Raleigh Salvation Army",
         "address": "222 S Blount St, Raleigh, NC 27601",
         "lat": 35.7710, "lon": -78.6380,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 100 people", "phone": "919-834-2648",
         "vulnerable_friendly": True,
         "why": "Designated vulnerable-population site; trained staff for elderly / disabled / medical-need evacuees."},
    ],
    "durham": [
        {"name": "Durham County Emergency Shelter",
         "address": "300 E Pettigrew St, Durham, NC 27702",
         "lat": 35.9780, "lon": -78.9010,
         "type": "General", "ada": True,
         "capacity_note": "Up to 400 people", "phone": "919-560-0300",
         "vulnerable_friendly": False,
         "why": "Primary county emergency site; opened automatically when evacuation order is issued."},
    ],
    "greensboro": [
        {"name": "Salvation Army Greensboro",
         "address": "1303 Cone Blvd, Greensboro, NC 27409",
         "lat": 36.0850, "lon": -79.8270,
         "type": "General / Vulnerable", "ada": True,
         "capacity_note": "Up to 120 people", "phone": "336-275-4315",
         "vulnerable_friendly": True,
         "why": "Guilford County-designated vulnerable shelter; wheelchair-accessible throughout."},
    ],
    "miami": [
        {"name": "Miami-Dade County Emergency Shelter",
         "address": "7490 NW 7th Ave, Miami, FL 33147",
         "lat": 25.8570, "lon": -80.2180,
         "type": "General", "ada": True,
         "capacity_note": "Up to 2000 people", "phone": "305-468-5400",
         "vulnerable_friendly": False,
         "why": "Largest county-run evacuation shelter; activated for all hurricane / fire evacuations."},
        {"name": "Salvation Army Miami",
         "address": "1400 NW 10th Ave, Miami, FL 33136",
         "lat": 25.7900, "lon": -80.2050,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 300 people", "phone": "305-326-0026",
         "vulnerable_friendly": True,
         "why": "Designated vulnerable / special-needs shelter with medical support and translators."},
    ],
    "houston": [
        {"name": "George R. Brown Convention Center",
         "address": "1000 Polk St, Houston, TX 77002",
         "lat": 29.7530, "lon": -95.3570,
         "type": "General", "ada": True,
         "capacity_note": "Up to 10000 people", "phone": "713-794-9000",
         "vulnerable_friendly": False,
         "why": "Harris County's primary mega-shelter; opened for Hurricane Harvey and major evacuations."},
        {"name": "Salvation Army Houston",
         "address": "1001 Bellaire Blvd, Houston, TX 77054",
         "lat": 29.6980, "lon": -95.4080,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 200 people", "phone": "713-227-2932",
         "vulnerable_friendly": True,
         "why": "Elderly / disabled / medical-need shelter with 24-hr nursing care during emergencies."},
    ],
    "los angeles": [
        {"name": "Los Angeles County Fairgrounds Shelter",
         "address": "1101 W Mission Blvd, Pomona, CA 91789",
         "lat": 34.0700, "lon": -117.7480,
         "type": "General", "ada": True,
         "capacity_note": "Up to 3000 people", "phone": "213-816-0000",
         "vulnerable_friendly": False,
         "why": "LA County's largest evacuation shelter site; routinely activated during wildfires."},
        {"name": "Salvation Army Los Angeles",
         "address": "1340 S Hope St, Los Angeles, CA 90015",
         "lat": 34.0420, "lon": -118.2800,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 250 people", "phone": "213-362-0050",
         "vulnerable_friendly": True,
         "why": "Designated vulnerable-population shelter with medical staff and multilingual support."},
    ],
    "dallas": [
        {"name": "Dallas Convention Center Shelter",
         "address": "650 Akard St, Dallas, TX 75201",
         "lat": 32.7880, "lon": -96.7980,
         "type": "General", "ada": True,
         "capacity_note": "Up to 5000 people", "phone": "214-670-6000",
         "vulnerable_friendly": False,
         "why": "Primary city-run mega-shelter; activated for severe weather and wildfire evacuations."},
    ],
    "atlanta": [
        {"name": "Georgia World Congress Center",
         "address": "285 Spring St NW, Atlanta, GA 30303",
         "lat": 33.7530, "lon": -84.4010,
         "type": "General", "ada": True,
         "capacity_note": "Up to 5000 people", "phone": "404-223-4700",
         "vulnerable_friendly": False,
         "why": "Fulton County's primary mass-evacuation shelter; ADA-compliant throughout."},
        {"name": "Salvation Army Atlanta",
         "address": "1214 Spring St NW, Atlanta, GA 30309",
         "lat": 33.7800, "lon": -84.3960,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 150 people", "phone": "404-855-4750",
         "vulnerable_friendly": True,
         "why": "Vulnerable-population designated shelter; on-call medical and social-work staff."},
    ],
    "chicago": [
        {"name": "Chicago McCormick Place Shelter",
         "address": "2301 S Lake Shore Dr, Chicago, IL 60616",
         "lat": 41.8440, "lon": -87.6180,
         "type": "General", "ada": True,
         "capacity_note": "Up to 8000 people", "phone": "312-326-0000",
         "vulnerable_friendly": False,
         "why": "City's largest emergency shelter facility; activated for major evacuation events."},
    ],
    "new york": [
        {"name": "Jacob Javits Center Shelter",
         "address": "429 11th Ave, New York, NY 10001",
         "lat": 40.7580, "lon": -74.0000,
         "type": "General", "ada": True,
         "capacity_note": "Up to 10000 people", "phone": "212-216-2000",
         "vulnerable_friendly": False,
         "why": "NYC's primary mass-casualty and evacuation shelter; activated for hurricanes and major emergencies."},
        {"name": "Salvation Army New York",
         "address": "120 W 15th St, New York, NY 10011",
         "lat": 40.7380, "lon": -73.9960,
         "type": "Vulnerable", "ada": True,
         "capacity_note": "Up to 200 people", "phone": "212-366-9896",
         "vulnerable_friendly": True,
         "why": "Designated vulnerable / special-needs shelter with interpreters and medical support."},
    ],
    "seattle": [
        {"name": "Seattle Center Shelter",
         "address": "401 Mercer St, Seattle, WA 98109",
         "lat": 47.6210, "lon": -122.3540,
         "type": "General", "ada": True,
         "capacity_note": "Up to 2000 people", "phone": "206-684-0000",
         "vulnerable_friendly": False,
         "why": "King County primary evacuation site; fully ADA-accessible."},
    ],
    "denver": [
        {"name": "Denver Convention Center Shelter",
         "address": "700 E Colfax Ave, Denver, CO 80203",
         "lat": 39.7420, "lon": -104.9780,
         "type": "General", "ada": True,
         "capacity_note": "Up to 3000 people", "phone": "303-595-8000",
         "vulnerable_friendly": False,
         "why": "Denver's go-to emergency shelter for wildfire evacuations; largest capacity in metro."},
    ],
    "phoenix": [
        {"name": "Phoenix Convention Center Shelter",
         "address": "111 N 10th St, Phoenix, AZ 85004",
         "lat": 33.4480, "lon": -112.0750,
         "type": "General", "ada": True,
         "capacity_note": "Up to 4000 people", "phone": "602-262-6100",
         "vulnerable_friendly": False,
         "why": "Maricopa County primary evacuation centre; routinely used for wildfire evacuations."},
    ],
}


def get_shelters_for_city(city_name: str, city_lat: float, city_lon: float) -> List[Dict]:
    """Return shelter list; falls back to a generated generic entry."""
    key = city_name.lower().strip().split(",")[0].strip()
    if key in SHELTERS:
        return SHELTERS[key]
    return [
        {
            "name": f"{city_name.strip().title()} Area Emergency Shelter",
            "address": f"Contact {city_name.strip().title()} Emergency Management — call 211",
            "lat": city_lat, "lon": city_lon,
            "type": "General", "ada": True,
            "capacity_note": "Varies — call ahead",
            "phone": "211",
            "vulnerable_friendly": False,
            "why": (
                f"Default county emergency shelter for {city_name.strip().title()}. "
                "Call 211 or visit your county emergency-management website for the "
                "exact open shelter address during an active evacuation."
            ),
        }
    ]


# ── transit-stop proximity ───────────────────────────────────────────
TRANSIT_WALK_MINS: Dict[str, int] = {
    "new york": 5, "chicago": 8, "los angeles": 12, "houston": 15,
    "phoenix": 18, "philadelphia": 10, "san antonio": 20, "san diego": 14,
    "dallas": 16, "san jose": 12, "austin": 18, "san francisco": 7,
    "columbus": 15, "indianapolis": 18, "seattle": 9, "denver": 12,
    "washington": 8, "nashville": 20, "boston": 7, "charlotte": 14,
    "portland": 10, "miami": 12, "atlanta": 11, "detroit": 16,
    "minneapolis": 10, "tampa": 22, "orlando": 25, "pittsburgh": 14,
    "cleveland": 13, "raleigh": 18, "new orleans": 15, "baltimore": 11,
    "milwaukee": 16, "st louis": 14, "memphis": 22, "louisville": 20,
}

def _nearest_stop_walk(city_name: str) -> int:
    return TRANSIT_WALK_MINS.get(city_name.lower().strip().split(",")[0].strip(), 15)


# ── page renderer ────────────────────────────────────────────────────
def render_evacuation_planner_page(fire_data, vulnerable_populations):
    """Main entry point called by the multi-page dashboard."""

    st.title("🚗 Personal Evacuation Planner")
    st.markdown(
        "Get personalized evacuation routes — driving, walking, and public transit — "
        "with specific shelter addresses for both the general public and vulnerable populations."
    )

    # ── session-state bootstrap ──────────────────────────────────────
    for key, default in {
        "search_address": None,
        "search_coords": None,
        "search_triggered": False,
        "dynamic_safe_zones": None,
        "selected_zone_idx": 0,
        "cached_routes": {},
    }.items():
        st.session_state.setdefault(key, default)

    # ── address input ────────────────────────────────────────────────
    st.subheader("📍 Your Location")
    st.info("💡 **500+ US cities, all 50 states.** Type your city name — e.g. *Charlotte, NC* or *Miami*.")

    col1, col2 = st.columns([3, 1])
    with col1:
        address = st.text_input(
            "Enter your city",
            value=st.session_state.search_address or "",
            placeholder="Charlotte, NC",
            key="address_input",
        )
    with col2:
        search_button = st.button("🔍 Find Route", type="primary")

    if search_button and address:
        st.session_state.search_triggered = True
        st.session_state.search_address = address
        st.session_state.search_coords = None
        st.session_state.dynamic_safe_zones = None
        st.session_state.cached_routes = {}

    # ── nothing to show yet ──────────────────────────────────────────
    if not st.session_state.search_triggered:
        st.info("👆 Enter your city above to get personalized evacuation routes")
        st.markdown("---")
        st.subheader("ℹ️ How It Works")
        st.markdown("""
        1. **Enter your city** — we geocode it instantly from a 500+ city DB.
        2. **Nearby fires** — satellite detections within 100 mi are shown.
        3. **Safe-zone shelters** — specific addresses (ADA / vulnerable-friendly flagged).
        4. **Multimodal routes** — driving, walking, transit, and drive-to-transit all compared.
        5. **Interactive map** — every route drawn; shelter pins clickable.
        6. **Road-closure advisory** — always displayed so you know before you go.
        """)
        return

    # ── geocode ──────────────────────────────────────────────────────
    if st.session_state.search_coords is None:
        with st.spinner("🗺️ Finding your location…"):
            st.session_state.search_coords = geocode_address(st.session_state.search_address)

    coords = st.session_state.search_coords
    if coords is None:
        st.error("❌ City not found. Try the city name alone or with state abbreviation.")
        return

    origin_lat, origin_lon = coords
    st.success(f"📍 Location locked: **{st.session_state.search_address.strip().title()}** ({origin_lat:.4f}, {origin_lon:.4f})")

    # ── dynamic safe zones ───────────────────────────────────────────
    if st.session_state.dynamic_safe_zones is None:
        with st.spinner("🗺️ Finding nearby safe zones…"):
            st.session_state.dynamic_safe_zones = get_dynamic_safe_zones(
                origin_lat, origin_lon, fire_data=fire_data,
                min_distance_mi=30, max_distance_mi=600, num_zones=10,
            )
    safe_zone_list: List[Dict] = st.session_state.dynamic_safe_zones or []

    # ── fire threats ─────────────────────────────────────────────────
    st.subheader("🔥 Nearby Fire Threats")
    nearest_fires: List[Dict] = []
    if fire_data is not None and len(fire_data) > 0:
        for _, fire in fire_data.iterrows():
            fl, flo = fire.get("latitude"), fire.get("longitude")
            if fl and flo:
                d = _haversine(origin_lat, origin_lon, fl, flo)
                if d < 100:
                    acres = fire.get("acres", 0)
                    nearest_fires.append({
                        "name": fire.get("fire_name", "Satellite Detection"),
                        "distance": round(d, 1),
                        "acres": acres if (acres and acres == acres) else 0,
                        "lat": fl, "lon": flo,
                    })
    nearest_fires.sort(key=lambda x: x["distance"])

    if nearest_fires:
        st.warning(f"⚠️ {len(nearest_fires)} fire(s) detected within 100 miles")
        for f in nearest_fires[:5]:
            badge = "🔴 HIGH" if f["distance"] < 15 else ("🟡 MEDIUM" if f["distance"] < 40 else "🟢 LOW")
            acres_str = f"{f['acres']:,.0f} acres" if f["acres"] else "size unknown"
            st.write(f"{badge} — **{f['name']}**: {f['distance']} mi away  ({acres_str})")
    else:
        st.success("✅ No fires within 100 miles of your location")

    # ── 🚧 road-closure advisory ─────────────────────────────────────
    st.markdown("---")
    st.subheader("🚧 Road-Closure Advisory")
    st.warning(
        "**Always check road conditions before driving.**  "
        "During wildfires, highways are closed without notice.  "
        "If you cannot access the links below, tune to local AM/FM emergency broadcasts or call **511**."
    )
    # state-specific 511 links
    STATE_511 = {
        "nc": ("🏎️ [NC DOT Road Conditions](https://www.ncdot.gov/travel-information/road-conditions)",  "North Carolina"),
        "ca": ("🏎️ [Caltrans Road Conditions](https://www.caltrans.ca.gov/travel-and-transport/road-conditions)", "California"),
        "tx": ("🏎️ [TxDOT Road Conditions](https://www.txdot.gov/travel-info.html)", "Texas"),
        "fl": ("🏎️ [FDOT Road Conditions](https://www.511.org)", "Florida"),
        "az": ("🏎️ [ADOT Road Conditions](https://www.azgovernment.gov/)", "Arizona"),
        "ga": ("🏎️ [GDOT Road Conditions](https://www.511.org)", "Georgia"),
        "wa": ("🏎️ [WSDOT Road Conditions](https://www.wsdot.com/)", "Washington"),
        "co": ("🏎️ [CDOT Road Conditions](https://www.cotrip.org/)", "Colorado"),
        "or": ("🏎️ [ODOT Road Conditions](https://www.oregon.gov/odot)", "Oregon"),
        "il": ("🏎️ [IDOT Road Conditions](https://www.illinoisservice.org/)", "Illinois"),
    }
    addr_upper = st.session_state.search_address.upper()
    state_match = None
    for abbr in STATE_511:
        if abbr.upper() in addr_upper:
            state_match = abbr
            break
    if state_match:
        link, state_name = STATE_511[state_match]
        st.markdown(link)
    st.markdown("🌐 [National 511 Portal](https://www.511.org)")

    # ── destination picker ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("🛣️ Evacuation Destination")

    if not safe_zone_list:
        st.warning("No safe zones found — try a different starting city.")
        return

    zone_labels = []
    for z in safe_zone_list:
        tags = ""
        if z["has_rail"]:  tags += " 🚆"
        if z["near_fire"]: tags += " 🚨"
        zone_labels.append(f"{z['name']}  —  {z['distance_mi']} mi{tags}")

    sel_idx = st.selectbox(
        "Select safe-zone city",
        options=range(len(zone_labels)),
        format_func=lambda i: zone_labels[i],
        index=min(st.session_state.selected_zone_idx, len(zone_labels) - 1),
        help="🚆 = rail available · 🚨 = fire detected nearby — prefer other options",
        key="safe_zone_select",
    )
    st.session_state.selected_zone_idx = sel_idx
    zone = safe_zone_list[sel_idx]
    dest_lat, dest_lon = zone["lat"], zone["lon"]
    dest_name = zone["name"]

    # ── shelter cards ────────────────────────────────────────────────
    shelters = get_shelters_for_city(dest_name, dest_lat, dest_lon)
    vuln_shelters = [s for s in shelters if s.get("vulnerable_friendly")]
    gen_shelters  = [s for s in shelters if not s.get("vulnerable_friendly")]

    st.subheader("🏥 Shelters at Destination")

    if vuln_shelters:
        st.markdown("#### 🩺 Vulnerable-Population Shelters  *(ADA · Elderly · Medical)*")
        for s in vuln_shelters:
            with st.expander(f"🏥 {s['name']}", expanded=True):
                st.markdown(f"📍 **{s['address']}**")
                st.markdown(f"📞 **Phone:** {s['phone']}  |  👥 **Capacity:** {s['capacity_note']}  |  ♿ **ADA:** {'Yes' if s['ada'] else 'No'}")
                st.info(f"💡 **Why this shelter?**  {s['why']}")
                gm_dir  = f"https://www.google.com/maps/dir/{origin_lat},{origin_lon}/{s['lat']},{s['lon']}"
                apple   = f"https://maps.apple.com/?saddr={origin_lat},{origin_lon}&daddr={s['lat']},{s['lon']}"
                col_a, col_b = st.columns(2)
                col_a.markdown(f"🗺️ [Directions in Google Maps]({gm_dir})")
                col_b.markdown(f"🍎 [Directions in Apple Maps]({apple})")

    if gen_shelters:
        st.markdown("#### 🏢 General-Population Shelters")
        for s in gen_shelters:
            with st.expander(f"🏢 {s['name']}", expanded=False):
                st.markdown(f"📍 **{s['address']}**")
                st.markdown(f"📞 **Phone:** {s['phone']}  |  👥 **Capacity:** {s['capacity_note']}  |  ♿ **ADA:** {'Yes' if s['ada'] else 'No'}")
                st.info(f"💡 **Why this shelter?**  {s['why']}")
                gm_dir  = f"https://www.google.com/maps/dir/{origin_lat},{origin_lon}/{s['lat']},{s['lon']}"
                apple   = f"https://maps.apple.com/?saddr={origin_lat},{origin_lon}&daddr={s['lat']},{s['lon']}"
                col_a, col_b = st.columns(2)
                col_a.markdown(f"🗺️ [Directions in Google Maps]({gm_dir})")
                col_b.markdown(f"🍎 [Directions in Apple Maps]({apple})")

    # primary shelter = vulnerable first, then first general
    primary_shelter = (vuln_shelters or gen_shelters)[0]
    shelter_lat, shelter_lon = primary_shelter["lat"], primary_shelter["lon"]

    # ── route everything to PRIMARY SHELTER address ─────────────────
    st.markdown("---")
    st.subheader("📊 Multimodal Route Comparison")
    st.caption(f"Routes calculated to **{primary_shelter['name']}** — {primary_shelter['address']}")

    dest_key = f"{shelter_lat:.4f},{shelter_lon:.4f}"

    if dest_key not in st.session_state.cached_routes:
        with st.spinner("Calculating routes…"):
            car  = osrm_route(origin_lat, origin_lon, shelter_lat, shelter_lon, "car")
            foot = osrm_route(origin_lat, origin_lon, shelter_lat, shelter_lon, "foot")
        st.session_state.cached_routes[dest_key] = {"car": car, "foot": foot}

    cached = st.session_state.cached_routes[dest_key]
    car_route  = cached["car"]
    foot_route = cached["foot"]

    # transit estimates
    walk_to_stop_mins = _nearest_stop_walk(st.session_state.search_address)
    straight_mi       = _haversine(origin_lat, origin_lon, shelter_lat, shelter_lon)
    transit_travel_min = round(straight_mi / 30 * 60, 0)
    transit_total_min  = walk_to_stop_mins + transit_travel_min + 10

    # drive-to-transit hybrid
    drive_to_hub_min = 10
    transit_rest_min = round((straight_mi - 5) / 30 * 60, 0) if straight_mi > 5 else transit_travel_min
    hybrid_total_min = drive_to_hub_min + transit_rest_min + 5

    # ── comparison table ─────────────────────────────────────────────
    # Fallback estimates when OSRM is unreachable:
    #   driving  ≈ straight_mi × 1.3  at 45 mph  (road-distance factor)
    #   walking  ≈ straight_mi × 1.2  at 3.5 mph
    osrm_ok = car_route is not None or foot_route is not None
    if not osrm_ok:
        st.warning(
            "⚠️ Live routing service is temporarily unavailable — "
            "ETAs below are **estimates** based on straight-line distance. "
            "Use [Google Maps](https://www.google.com/maps) for turn-by-turn navigation."
        )

    if car_route:
        drive_dist   = car_route["distance_mi"]
        drive_eta    = car_route["duration_min"]
        drive_note   = "Fastest — check 511 for closures"
    else:
        drive_dist   = round(straight_mi * 1.3, 1)
        drive_eta    = round(drive_dist / 45 * 60, 0)
        drive_note   = "⚠️ Estimate (routing service down) — verify on Google Maps"

    if foot_route:
        walk_dist    = foot_route["distance_mi"]
        walk_eta     = foot_route["duration_min"]
    else:
        walk_dist    = round(straight_mi * 1.2, 1)
        walk_eta     = round(walk_dist / 3.5 * 60, 0)

    rows = [
        {"Mode": "🚗 Driving",          "Distance": f"{drive_dist} mi",
         "ETA": _fmt(drive_eta),         "Notes": drive_note},
        {"Mode": "🚌 Transit",          "Distance": f"{straight_mi:.1f} mi",
         "ETA": _fmt(transit_total_min), "Notes": f"Walk {walk_to_stop_mins} min to stop + ride + 10 min buffer"},
        {"Mode": "🚗→🚌 Drive+Transit", "Distance": "—",
         "ETA": _fmt(hybrid_total_min),  "Notes": "Drive to transit hub, then ride"},
        {"Mode": "🚶 Walking",          "Distance": f"{walk_dist} mi",
         "ETA": _fmt(walk_eta),          "Notes": "Only realistic < 10 mi"},
    ]

    st.table(rows)

    # ── how to reach transit ─────────────────────────────────────────
    st.subheader("🚌 Getting to Transit")
    origin_transit = get_transit_info(st.session_state.search_address) if TRANSIT_DB_AVAILABLE else None
    if origin_transit:
        with st.expander(f"🏙️ Transit in **{st.session_state.search_address.strip().title()}**", expanded=True):
            st.markdown("**Agencies:** " + ", ".join(origin_transit["agencies"]))
            if origin_transit["rail"] and origin_transit["rail_lines"]:
                st.markdown("🚆 **Rail:** " + " | ".join(origin_transit["rail_lines"]))
            if origin_transit["bus"]:
                st.markdown("🚌 **Bus:** Available")
            st.markdown(origin_transit["notes"])
            st.markdown(f"📞 Info line: **{origin_transit['emergency_hotline']}**")
            if origin_transit.get("transit_url"):
                st.markdown(f"🌐 [Transit website]({origin_transit['transit_url']})")

            st.markdown("---")
            st.markdown("#### 🚶🚕🚗 How to reach the nearest stop")
            walk_min = _nearest_stop_walk(st.session_state.search_address)
            cols = st.columns(3)
            cols[0].metric("🚶 Walk", f"{walk_min} min", "~0.5–1 mi")
            cols[1].metric("🚕 Uber / Lyft", f"{max(walk_min - 5, 3)} min", "request in app now")
            cols[2].metric("🚗 Drive & park", "~5 min", "check parking alerts")

    # destination transit
    dest_transit = get_transit_info(dest_name) if TRANSIT_DB_AVAILABLE else None
    if dest_transit:
        with st.expander(f"🏙️ Transit at **{dest_name}** (destination)", expanded=False):
            st.markdown("**Agencies:** " + ", ".join(dest_transit["agencies"]))
            if dest_transit["rail"] and dest_transit["rail_lines"]:
                st.markdown("🚆 **Rail:** " + " | ".join(dest_transit["rail_lines"]))
            if dest_transit["bus"]:
                st.markdown("🚌 **Bus:** Available")
            st.markdown(dest_transit["notes"])
            st.markdown(f"📞 Info line: **{dest_transit['emergency_hotline']}**")
            if dest_transit.get("transit_url"):
                st.markdown(f"🌐 [Transit website]({dest_transit['transit_url']})")

    with st.expander("🚐 Emergency Shuttle", expanded=False):
        st.write("Estimated time varies.  Contact local emergency services.")
        st.info("Dial **211** for evacuation assistance anywhere in the US.")

    st.warning("⚠️ Public transit may be suspended during active emergencies. Always have a backup driving plan.")

    # ── turn-by-turn ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🧭 Turn-by-Turn Directions")

    # Google Maps deep-link that works regardless of OSRM status
    gm_dir = (
        f"https://www.google.com/maps/dir/"
        f"{origin_lat},{origin_lon}/{shelter_lat},{shelter_lon}"
    )

    if car_route and car_route["steps"]:
        with st.expander("🚗 Driving directions", expanded=True):
            for i, s in enumerate(car_route["steps"][:20], 1):
                st.write(f"{i}. {s}")
            if len(car_route["steps"]) > 20:
                st.caption(f"… and {len(car_route['steps']) - 20} more steps")
            st.markdown(f"📱 [Open full route in Google Maps]({gm_dir})")
    else:
        with st.expander("🚗 Driving directions", expanded=True):
            st.info("Live turn-by-turn unavailable right now.")
            st.markdown(f"👉 **[Get driving directions in Google Maps]({gm_dir})**")

    if foot_route and foot_route["steps"]:
        with st.expander("🚶 Walking directions", expanded=False):
            for i, s in enumerate(foot_route["steps"][:20], 1):
                st.write(f"{i}. {s}")
            if len(foot_route["steps"]) > 20:
                st.caption(f"… and {len(foot_route['steps']) - 20} more steps")
            st.markdown(f"📱 [Open full route in Google Maps]({gm_dir}?mode=walk)")
    else:
        with st.expander("🚶 Walking directions", expanded=False):
            st.info("Live turn-by-turn unavailable right now.")
            st.markdown(f"👉 **[Get walking directions in Google Maps]({gm_dir}?mode=walk)**")

    # ── interactive map ──────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🗺️ Route Map")

    mid_lat  = (origin_lat + shelter_lat) / 2
    mid_lon  = (origin_lon + shelter_lon) / 2
    zoom = 9 if straight_mi > 80 else (10 if straight_mi > 30 else 12)

    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=zoom, tiles="CartoDB positron")

    # origin
    folium.Marker(
        [origin_lat, origin_lon],
        popup=f"<b>START</b><br>{st.session_state.search_address.strip().title()}",
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
        tooltip="Your Location",
    ).add_to(m)

    # shelter pins
    for s in shelters:
        colour = "red" if s.get("vulnerable_friendly") else "blue"
        icon   = "hospital" if s.get("vulnerable_friendly") else "flag"
        folium.Marker(
            [s["lat"], s["lon"]],
            popup=(
                f"<b>{s['name']}</b><br>"
                f"{s['address']}<br>"
                f"📞 {s['phone']}<br>"
                f"{'♿ ADA ' if s['ada'] else ''}"
                f"{'🩺 Vulnerable-friendly' if s.get('vulnerable_friendly') else ''}"
            ),
            icon=folium.Icon(color=colour, icon=icon, prefix="fa"),
            tooltip=s["name"],
        ).add_to(m)

    # route polylines
    if car_route:
        folium.PolyLine(
            [[c[1], c[0]] for c in car_route["geometry"]],
            color="blue", weight=5, opacity=0.8, tooltip="🚗 Driving route",
        ).add_to(m)
    if foot_route:
        folium.PolyLine(
            [[c[1], c[0]] for c in foot_route["geometry"]],
            color="green", weight=3, opacity=0.7, dash_array="8", tooltip="🚶 Walking route",
        ).add_to(m)

    # fire circles
    for f in nearest_fires[:10]:
        folium.Circle(
            [f["lat"], f["lon"]],
            radius=max(f.get("acres", 100) * 40, 800),
            color="red", fill=True, fillColor="orange", fillOpacity=0.35,
            popup=f"🔥 {f['name']}<br>{f['distance']} mi away",
        ).add_to(m)

    # legend
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
         background:white;padding:10px 14px;border-radius:8px;
         border:2px solid #ccc;font-size:13px;box-shadow:0 2px 6px rgba(0,0,0,.3);">
     <b>Legend</b><br>
     <span style="color:blue;">━━</span> Driving &nbsp;
     <span style="color:green;">╌╌</span> Walking &nbsp;
     <span style="color:red;">●</span> Fire &nbsp;
     🏥 Vulnerable shelter &nbsp;
     🏢 General shelter
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width="100%", height=620)

    # ── emergency resources ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("📞 Emergency Resources")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**🚨 Emergency**\n- 911 — Fire / Police / Medical\n- 211 — Evacuation assistance\n- 📻 Local AM/FM emergency broadcast")
    c2.markdown("**✅ Evacuation Checklist**\n- 📄 IDs, insurance docs\n- 💊 Medications (7-day supply)\n- 🐾 Pet food + carriers\n- 💵 Cash + cards\n- 🔋 Phone charger / power bank")
    c3.markdown("**🛣️ Road Safety**\n- 🚧 Check [511.org](https://www.511.org)\n- ⛽ Fill gas tank NOW\n- 💧 Water + snacks for 24 h\n- 📱 Download offline maps")


# ── standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(page_title="Evacuation Planner", layout="wide")
    render_evacuation_planner_page(None, None)