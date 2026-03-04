"""
fire_prediction_page.py

Physically-based wildfire spread prediction using peer-reviewed fire science models.

Scientific references:
  - Van Wagner (1969): A simple fire-growth model. Forestry Chronicle 45(2):103-104.
  - Van Wagner & Pickett (1985): Equations and FORTRAN program for the Canadian Forest
    Fire Weather Index System. Canadian Forestry Service Technical Report 33.
  - Rothermel (1972): A mathematical model for predicting fire spread in wildland fuels.
    USDA Forest Service Research Paper INT-115.
  - Byram (1959): Combustion of forest fuels. In: Davis (ed.) Forest Fire Control and Use.

Live data: Open-Meteo weather + CAMS AQI (free, no API key required).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from math import radians, cos, sin, sqrt, exp, tan, pi, log
from datetime import datetime


# ---------------------------------------------------------------------------
# Open-Meteo API endpoints (free, no API key)
# ---------------------------------------------------------------------------
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
_AQI_URL     = "https://air-quality-api.open-meteo.com/v1/air-quality"
_FIRMS_URL   = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    "c6c38aac4de4e98571b29a73e3527a8c/VIIRS_SNPP_NRT/world/1"
)


# ---------------------------------------------------------------------------
# NFFL Fuel Models — Rothermel (1972), calibrated to BehavePlus 5 tables
# R0 = no-wind, flat-terrain base spread rate (m/min) at reference moisture
# Mx = extinction moisture content (%)
# w0 = available surface fuel load (kg/m2)
# h  = low heat content of fuel (kJ/kg)
# wind_a, wind_b = power-law wind coefficient: phi_W = wind_a * (U / 10 mph)^wind_b
# ---------------------------------------------------------------------------
FUEL_MODELS = {
    "Grass (NFFL 1)": {
        "label":  "Short grass — open grasslands, pastures",
        "R0":     0.18,
        "Mx":     12.0,
        "w0":     0.166,
        "h":      18622,
        "wind_a": 0.40,
        "wind_b": 1.40,
    },
    "Chaparral (NFFL 4)": {
        "label":  "Chaparral — tall shrubs, southern CA/AZ/NM",
        "R0":     0.75,
        "Mx":     20.0,
        "w0":     1.123,
        "h":      18622,
        "wind_a": 0.55,
        "wind_b": 1.30,
    },
    "Southern Rough (NFFL 7)": {
        "label":  "Southern rough — wiregrass, saw palmetto, pine flatwoods",
        "R0":     0.28,
        "Mx":     15.0,
        "w0":     0.553,
        "h":      18622,
        "wind_a": 0.45,
        "wind_b": 1.35,
    },
    "Timber Litter (NFFL 8)": {
        "label":  "Closed timber litter — pine/fir forest floor",
        "R0":     0.05,
        "Mx":     30.0,
        "w0":     0.831,
        "h":      18622,
        "wind_a": 0.25,
        "wind_b": 1.20,
    },
    "Logging Slash (NFFL 11)": {
        "label":  "Light logging slash — post-harvest clearcuts",
        "R0":     0.12,
        "Mx":     25.0,
        "w0":     0.553,
        "h":      18622,
        "wind_a": 0.35,
        "wind_b": 1.25,
    },
}


# ---------------------------------------------------------------------------
# FWI danger classes (Van Wagner 1987 / Canadian Forest Service)
# (lo, hi, label, hex_color, description)
# ---------------------------------------------------------------------------
FWI_DANGER_CLASSES = [
    (0,   12,  "Low",       "#3fb950", "Fires may start but spread slowly; easy control."),
    (12,  25,  "Moderate",  "#d4a017", "Moderate fire activity; patrol and presuppression needed."),
    (25,  38,  "High",      "#FF9800", "High fire intensity; difficult direct attack."),
    (38,  50,  "Very High", "#FF4B4B", "Very intense fire behavior; suppression very difficult."),
    (50,  999, "Extreme",   "#AA0000", "Explosive fire growth; direct attack generally not possible."),
]


# ---------------------------------------------------------------------------
# US EPA AQI categories
# (lo, hi, label, hex_color)
# ---------------------------------------------------------------------------
AQI_CATEGORIES = [
    (0,   50,  "Good",                      "#3fb950"),
    (51,  100, "Moderate",                  "#d4a017"),
    (101, 150, "Unhealthy (Sensitive)",     "#FF9800"),
    (151, 200, "Unhealthy",                 "#FF4B4B"),
    (201, 300, "Very Unhealthy",            "#AA0000"),
    (301, 500, "Hazardous",                 "#7B0000"),
]


# ---------------------------------------------------------------------------
# Historical hotspot clusters (WiDS 2021-2025 + NIFC)
# ---------------------------------------------------------------------------
HISTORICAL_HOTSPOT_CLUSTERS = [
    {"name": "Northern California Foothills",   "lat": 39.8, "lon": -121.5, "risk": 0.92, "vul_svi": 0.68, "state": "CA"},
    {"name": "Southern California Coast Range", "lat": 34.2, "lon": -118.4, "risk": 0.89, "vul_svi": 0.72, "state": "CA"},
    {"name": "Oregon Cascades East Slope",      "lat": 44.1, "lon": -121.2, "risk": 0.78, "vul_svi": 0.61, "state": "OR"},
    {"name": "Colorado Front Range",            "lat": 39.5, "lon": -105.3, "risk": 0.74, "vul_svi": 0.55, "state": "CO"},
    {"name": "New Mexico Jemez Mountains",      "lat": 35.8, "lon": -106.5, "risk": 0.71, "vul_svi": 0.78, "state": "NM"},
    {"name": "Arizona White Mountains",         "lat": 34.0, "lon": -109.8, "risk": 0.70, "vul_svi": 0.74, "state": "AZ"},
    {"name": "Washington East Cascades",        "lat": 47.2, "lon": -120.4, "risk": 0.68, "vul_svi": 0.58, "state": "WA"},
    {"name": "Montana Bitterroot Valley",       "lat": 46.3, "lon": -114.1, "risk": 0.65, "vul_svi": 0.60, "state": "MT"},
    {"name": "Texas Big Bend Region",           "lat": 29.8, "lon": -103.2, "risk": 0.60, "vul_svi": 0.82, "state": "TX"},
    {"name": "Idaho Snake River Plain",         "lat": 43.6, "lon": -116.2, "risk": 0.58, "vul_svi": 0.62, "state": "ID"},
]

GROWTH_CURVES = {
    "fast_escalation": [1, 8, 45, 210, 800, 2500],
    "moderate":        [1, 3, 12, 40,  130, 400],
    "slow":            [1, 1.5, 4, 10,  25,  80],
}


# ===========================================================================
# API helpers
# ===========================================================================

@st.cache_data(ttl=300)
def _fetch_weather(lat, lon):
    """Current weather from Open-Meteo (free, no key). Returns dict or None."""
    try:
        r = requests.get(
            _WEATHER_URL,
            params={
                "latitude": lat, "longitude": lon,
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "wind_speed_10m,wind_direction_10m,precipitation"
                ),
                "wind_speed_unit": "mph",
                "temperature_unit": "celsius",
                "timezone": "auto",
            },
            timeout=8,
        )
        if r.status_code == 200:
            return r.json().get("current", {})
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def _fetch_aqi(lat, lon):
    """Air quality from Open-Meteo / CAMS (free, no key). Returns dict or None."""
    try:
        r = requests.get(
            _AQI_URL,
            params={
                "latitude": lat, "longitude": lon,
                "current": "us_aqi,pm2_5,pm10,dust,carbon_monoxide",
                "timezone": "auto",
            },
            timeout=8,
        )
        if r.status_code == 200:
            return r.json().get("current", {})
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def _geocode(query):
    """Geocode a place name via Nominatim. Returns (lat, lon) or None."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "WiDS-Wildfire-App/1.0"},
            timeout=6,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def _fetch_firms():
    try:
        r = requests.get(_FIRMS_URL, timeout=10)
        if r.status_code == 200:
            from io import StringIO
            df = pd.read_csv(StringIO(r.text))
            df = df[
                df["confidence"].isin(["h", "n", "high", "nominal"]) |
                (pd.to_numeric(df["confidence"], errors="coerce") >= 70)
            ].copy()
            return df, "live"
    except Exception:
        pass
    return None, "unavailable"


def _resolve_location(query, sess_key_lat, sess_key_lon, default_lat, default_lon):
    """
    Parse a location query string into (lat, lon).
    Tries comma-separated coords first, then Nominatim geocode.
    Updates session_state and returns (lat, lon).
    """
    lat = st.session_state.get(sess_key_lat, default_lat)
    lon = st.session_state.get(sess_key_lon, default_lon)
    if not query:
        return lat, lon
    try:
        parts = query.replace(" ", "").split(",")
        if len(parts) == 2:
            lat = float(parts[0])
            lon = float(parts[1])
            st.session_state[sess_key_lat] = lat
            st.session_state[sess_key_lon] = lon
            return lat, lon
    except ValueError:
        pass
    geo = _geocode(query)
    if geo:
        lat, lon = geo
        st.session_state[sess_key_lat] = lat
        st.session_state[sess_key_lon] = lon
    else:
        st.warning("Could not geocode that location. Try 'City, State' or enter 'lat, lon' directly.")
    return lat, lon


# ===========================================================================
# Canadian Forest Fire Weather Index (FWI) system
# Van Wagner & Pickett (1985), Technical Report 33, Canadian Forest Service
# ===========================================================================

def _ffmc_to_moisture(ffmc):
    """Convert FFMC code to fine fuel moisture content (%)."""
    return 147.2 * (101.0 - ffmc) / (59.5 + ffmc)


def compute_ffmc(T, H, W_kph, ro, ffmc0=85.0):
    """
    Fine Fuel Moisture Code (Van Wagner & Pickett 1985, eq. 1-9).
    T = temperature (C), H = RH (%), W_kph = wind (km/h),
    ro = 24h rainfall (mm), ffmc0 = previous day FFMC.
    """
    mo = _ffmc_to_moisture(ffmc0)
    if ro > 0.5:
        rf = ro - 0.5
        if mo <= 150:
            mo = (mo + 42.5 * rf * exp(-100.0 / (251.0 - mo))
                  * (1.0 - exp(-6.93 / rf)))
        else:
            mo = (mo + 42.5 * rf * exp(-100.0 / (251.0 - mo))
                  * (1.0 - exp(-6.93 / rf))
                  + 0.0015 * (mo - 150.0) ** 2 * sqrt(rf))
        mo = min(mo, 250.0)

    Ed = (0.942 * H ** 0.679 + 11.0 * exp((H - 100.0) / 10.0)
          + 0.18 * (21.1 - T) * (1.0 - exp(-0.115 * H)))
    Ew = (0.618 * H ** 0.753 + 10.0 * exp((H - 100.0) / 10.0)
          + 0.18 * (21.1 - T) * (1.0 - exp(-0.115 * H)))

    if mo > Ed:
        kd = (0.424 * (1.0 - (H / 100.0) ** 1.7)
              + 0.0694 * sqrt(W_kph) * (1.0 - (H / 100.0) ** 8))
        kw = kd * 0.581 * exp(0.0365 * T)
        m = Ed + (mo - Ed) * 10.0 ** (-kw)
    elif mo < Ew:
        kl = (0.424 * (1.0 - ((100.0 - H) / 100.0) ** 1.7)
              + 0.0694 * sqrt(W_kph) * (1.0 - ((100.0 - H) / 100.0) ** 8))
        kw = kl * 0.581 * exp(0.0365 * T)
        m = Ew - (Ew - mo) * 10.0 ** (-kw)
    else:
        m = mo

    return 59.5 * (250.0 - m) / (147.2 + m)


def compute_isi(ffmc, W_kph):
    """
    Initial Spread Index (Van Wagner & Pickett 1985, eq. 1).
    ISI = 0.208 * f(W) * f(F)
    """
    m = _ffmc_to_moisture(ffmc)
    ff = 91.9 * exp(-0.1386 * m) * (1.0 + m ** 5.31 / 49300000.0)
    fw = exp(0.05039 * W_kph)
    return 0.208 * fw * ff


def compute_dmc(T, H, ro, month, dmc0=6.0):
    """Duff Moisture Code (Van Wagner & Pickett 1985, eq. 10-18)."""
    # Day-length factor Le (Table 1, Van Wagner & Pickett 1985)
    Le_table = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0]
    Le = Le_table[max(0, min(month - 1, 11))]

    if ro > 1.5:
        re = 0.92 * ro - 1.27
        mo = 20.0 + exp(5.6348 - dmc0 / 43.43)
        if dmc0 <= 33.0:
            b = 100.0 / (0.5 + 0.3 * dmc0)
        elif dmc0 <= 65.0:
            b = 14.0 - 1.3 * log(max(dmc0, 0.001))
        else:
            b = 6.2 * log(max(dmc0, 0.001)) - 17.2
        mr = mo + 1000.0 * re / (48.77 + b * re)
        pr = max(0.0, 244.72 - 43.43 * log(max(mr - 20.0, 0.001)))
    else:
        pr = dmc0

    K = 1.894 * (T + 1.1) * (100.0 - H) * Le * 1e-6 if T > -1.1 else 0.0
    return pr + 100.0 * K


def compute_dc(T, ro, month, dc0=15.0):
    """Drought Code (Van Wagner & Pickett 1985, eq. 19-26)."""
    Lf_table = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6]
    Lf = Lf_table[max(0, min(month - 1, 11))]

    if ro > 2.8:
        rd = 0.83 * ro - 1.27
        Qo = 800.0 * exp(-dc0 / 400.0)
        Qr = Qo + 3.937 * rd
        dr = max(0.0, 400.0 * log(max(800.0 / Qr, 0.001)))
    else:
        dr = dc0

    Vd = 0.36 * (T + 2.8) + Lf if T > -2.8 else Lf
    return dr + 0.5 * Vd


def compute_bui(dmc, dc):
    """Build-up Index (Van Wagner & Pickett 1985, eq. 27-28)."""
    if dmc <= 0.4 * dc:
        return 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        return dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)


def compute_fwi(isi, bui):
    """Fire Weather Index (Van Wagner & Pickett 1985, eq. 29-30)."""
    fd = 0.626 * bui ** 0.809 + 2.0 if bui <= 80 else 1000.0 / (25.0 + 108.64 * exp(-0.023 * bui))
    B = 0.1 * isi * fd
    return exp(2.72 * (0.434 * log(max(B, 0.001))) ** 0.647) if B > 1.0 else B


def fwi_danger(fwi):
    """Return (label, color, description) for a given FWI value."""
    for lo, hi, label, color, desc in FWI_DANGER_CLASSES:
        if lo <= fwi < hi:
            return label, color, desc
    return "Extreme", "#AA0000", FWI_DANGER_CLASSES[-1][4]


def aqi_label_color(aqi):
    """Return (label, color) for a US AQI value."""
    for lo, hi, label, color in AQI_CATEGORIES:
        if lo <= aqi <= hi:
            return label, color
    return "Hazardous", "#7B0000"


# ===========================================================================
# Rothermel (1972) surface fire spread rate
# ===========================================================================

def _moisture_damping(Mf, Mx):
    """
    Moisture damping coefficient eta_M (Rothermel 1972, eq. 25).
    Mf = fuel moisture (%), Mx = extinction moisture (%).
    Returns 0 when Mf >= Mx (fire will not spread).
    """
    r = min(Mf / max(Mx, 0.01), 1.0)
    return max(0.0, 1.0 - 2.59 * r + 5.11 * r ** 2 - 3.52 * r ** 3)


def compute_spread_rate(fuel_key, wind_mph, slope_deg, fuel_moist_pct):
    """
    Head-fire spread rate in m/min (Rothermel 1972, simplified).

    R = R0 * eta_M * (1 + phi_W + phi_S)

    phi_W = wind_a * (wind_mph / 10)^wind_b   [calibrated to BehavePlus]
    phi_S = 5.275 * tan^2(slope_rad)           [Rothermel 1972, eq. 51]
    """
    fm = FUEL_MODELS[fuel_key]
    eta_M = _moisture_damping(fuel_moist_pct, fm["Mx"])
    if eta_M <= 0.0:
        return 0.0
    phi_W = fm["wind_a"] * (max(wind_mph, 0.0) / 10.0) ** fm["wind_b"]
    phi_S = 5.275 * tan(radians(max(slope_deg, 0.0))) ** 2
    return max(0.0, fm["R0"] * eta_M * (1.0 + phi_W + phi_S))


def byram_intensity(R_m_min, w0_kg_m2, h_kJ_kg=18622):
    """
    Byram (1959) fireline intensity I = h * w * R  [kW/m].
    R_m_min = spread rate (m/min), w0 = fuel load (kg/m2), h = heat content (kJ/kg).
    """
    return h_kJ_kg * w0_kg_m2 * (R_m_min / 60.0)


# ===========================================================================
# Van Wagner (1969) elliptical fire shape
# ===========================================================================

def lw_ratio(wind_mph):
    """
    Fire ellipse length-to-width ratio as a function of 20-ft wind speed (mph).
    Van Wagner (1969), Forestry Chronicle 45(2):103.
    """
    w = max(wind_mph, 0.0)
    return max(1.0, 0.936 * exp(0.2566 * w) + 0.461 * exp(-0.1548 * w) - 0.397)


def _local_to_latlon(lat0, lon0, x_m, y_m, wind_to_deg):
    """
    Convert local fire coordinates (m) to geographic (lat, lon).
    y_m = downwind (positive = toward head), x_m = cross-wind.
    wind_to_deg = direction fire is spreading toward (degrees from North, clockwise).
    """
    theta = radians(wind_to_deg)
    dN = -x_m * sin(theta) + y_m * cos(theta)
    dE =  x_m * cos(theta) + y_m * sin(theta)
    lat = lat0 + dN / 111320.0
    lon = lon0 + dE / (111320.0 * cos(radians(lat0)))
    return lat, lon


def fire_ellipse_polygon(lat0, lon0, wind_to_deg, R_head_m_min, LW, t_min, n_pts=90):
    """
    Build a closed ellipse polygon for fire perimeter at time t_min (minutes).

    Van Wagner (1969) geometry:
      e = sqrt(1 - 1/LW^2)                     eccentricity
      R_back = R_head * (1-e)/(1+e)            backing spread rate
      a = (R_head + R_back)/2 * t              semi-major axis (m)
      b = a / LW                               semi-minor axis (m)
      center_offset = a - R_back * t           ellipse center from ignition (downwind)

    Returns (lats, lons) list of polygon vertices.
    """
    if R_head_m_min <= 0:
        return [lat0], [lon0]

    e = sqrt(max(0.0, 1.0 - 1.0 / (LW ** 2)))
    R_back = R_head_m_min * (1.0 - e) / (1.0 + e)
    a = (R_head_m_min + R_back) / 2.0 * t_min   # semi-major (m)
    b = max(a / LW, 1.0)                          # semi-minor (m)
    center_offset = a - R_back * t_min            # (m), along downwind axis

    lats, lons = [], []
    for i in range(n_pts + 1):
        angle = 2.0 * pi * i / n_pts
        x_local = b * cos(angle)
        y_local = center_offset + a * sin(angle)
        lat, lon = _local_to_latlon(lat0, lon0, x_local, y_local, wind_to_deg)
        lats.append(lat)
        lons.append(lon)
    return lats, lons


def compute_ellipse_area_acres(R_head_m_min, LW, t_min):
    """Ellipse area in acres: pi * a * b."""
    e = sqrt(max(0.0, 1.0 - 1.0 / (LW ** 2)))
    R_back = R_head_m_min * (1.0 - e) / (1.0 + e)
    a = (R_head_m_min + R_back) / 2.0 * t_min
    b = a / LW
    return pi * a * b * 0.000247105


# Time horizons and color ramp (pale yellow -> deep red)
_TIME_HORIZONS = [1, 3, 6, 12, 24]
_ELLIPSE_COLORS = ["#FFF176", "#FFB300", "#FF6F00", "#FF3D00", "#AA0000"]


# ===========================================================================
# Tab 1: Spot Fire Spread
# ===========================================================================

def _render_spot_fire_spread():
    st.subheader("Spot Fire Spread — Physics-Based Elliptical Growth Model")
    st.markdown(
        "Enter a fire location and conditions. The model uses the **Rothermel (1972)** "
        "surface fire spread rate, the **Van Wagner (1969)** elliptical shape model, "
        "and the **Canadian FWI system** (Van Wagner & Pickett 1985). "
        "Weather is fetched live from **Open-Meteo** (free, no API key)."
    )

    # --- Location input ---
    col_loc, col_hint = st.columns([3, 1])
    with col_loc:
        location_q = st.text_input(
            "Fire location (city/address or lat, lon)",
            placeholder="e.g.  Paradise, CA   or   39.75, -121.60",
            key="spot_location",
        )
    with col_hint:
        st.caption("Lat/lon accepted directly.")

    lat = st.session_state.get("spot_lat", 39.75)
    lon = st.session_state.get("spot_lon", -121.60)

    if location_q:
        lat, lon = _resolve_location(location_q, "spot_lat", "spot_lon", lat, lon)

    # --- Live weather ---
    weather = _fetch_weather(lat, lon)

    if weather:
        w_T     = float(weather.get("temperature_2m",       30.0) or 30.0)
        w_H     = float(weather.get("relative_humidity_2m", 15.0) or 15.0)
        w_wind  = float(weather.get("wind_speed_10m",       15.0) or 15.0)   # mph
        # Open-Meteo reports wind FROM direction (meteorological). Fire spreads TO = FROM + 180.
        w_wfrom = float(weather.get("wind_direction_10m",   270.0) or 270.0)
        w_wto   = (w_wfrom + 180.0) % 360.0
        w_rain  = float(weather.get("precipitation",         0.0) or 0.0)
        st.success(
            f"Live weather: {w_T:.1f} C  |  {w_H:.0f}% RH  |  "
            f"{w_wind:.1f} mph from {w_wfrom:.0f} deg  |  "
            f"{w_rain:.1f} mm rain"
        )
    else:
        w_T, w_H, w_wind, w_wto, w_rain = 30.0, 15.0, 20.0, 90.0, 0.0
        st.info("Live weather unavailable. Default values loaded — enter location above to fetch real data.")

    # --- Condition inputs (pre-filled from weather) ---
    st.markdown("**Adjust conditions if needed:**")
    ci1, ci2, ci3 = st.columns(3)

    with ci1:
        wind_mph     = st.number_input("Wind speed (mph)", 0.0, 100.0,
                                       round(w_wind, 1), step=1.0, key="spot_wind")
        wind_to_deg  = st.number_input(
            "Fire spread direction (deg from N — where fire is moving toward)",
            0.0, 360.0, round(w_wto, 0), step=5.0, key="spot_wdir",
            help="This is 180 deg opposite the meteorological 'wind FROM' direction.",
        )
        slope_deg    = st.slider("Terrain slope (degrees)", 0, 45, 10, key="spot_slope")

    with ci2:
        humidity_pct = st.number_input("Relative humidity (%)", 1.0, 100.0,
                                       round(w_H, 0), step=1.0, key="spot_hum")
        temp_c       = st.number_input("Temperature (C)", -10.0, 55.0,
                                       round(w_T, 1), step=0.5, key="spot_temp")
        rain_24h     = st.number_input("24-hour rainfall (mm)", 0.0, 200.0,
                                       round(w_rain, 1), step=0.5, key="spot_rain")

    with ci3:
        fuel_key = st.selectbox("Fuel model (NFFL)", list(FUEL_MODELS.keys()), key="spot_fuel")
        st.caption(FUEL_MODELS[fuel_key]["label"])
        prev_ffmc = st.number_input(
            "Previous-day FFMC (0–101)",
            0.0, 101.0, 85.0, step=1.0, key="spot_ffmc",
            help="85 = average summer dryness. Lower = wetter. Higher = extreme dryness.",
        )

    if not st.button("Compute Fire Spread", type="primary", key="spot_run"):
        st.caption("Set conditions above and click Compute Fire Spread.")
        return

    # -----------------------------------------------------------------------
    # Computation
    # -----------------------------------------------------------------------
    W_kph   = wind_mph * 1.60934
    month   = datetime.now().month

    # Canadian FWI
    ffmc = compute_ffmc(temp_c, humidity_pct, W_kph, rain_24h, prev_ffmc)
    isi  = compute_isi(ffmc, W_kph)
    dmc  = compute_dmc(temp_c, humidity_pct, rain_24h, month)
    dc   = compute_dc(temp_c, rain_24h, month)
    bui  = compute_bui(dmc, dc)
    fwi  = compute_fwi(isi, bui)
    dlabel, dcolor, ddesc = fwi_danger(fwi)

    # Rothermel spread rate
    # Derive 10-hr fuel moisture proxy from FFMC (Van Wagner 1987 relationship)
    fm_live = _ffmc_to_moisture(ffmc) * 0.5 + 3.0
    fm_live = max(2.0, min(fm_live, FUEL_MODELS[fuel_key]["Mx"] * 0.95))
    R_head  = compute_spread_rate(fuel_key, wind_mph, slope_deg, fm_live)
    LW      = lw_ratio(wind_mph)
    fm_obj  = FUEL_MODELS[fuel_key]
    intensity = byram_intensity(R_head, fm_obj["w0"])

    # Ellipse polygons
    e_val   = sqrt(max(0.0, 1.0 - 1.0 / LW ** 2))
    R_back  = R_head * (1.0 - e_val) / (1.0 + e_val)
    R_flank = (R_head + R_back) / (2.0 * LW)

    polygons = []
    for t_hr, color in zip(_TIME_HORIZONS, _ELLIPSE_COLORS):
        t_min = t_hr * 60.0
        lats_p, lons_p = fire_ellipse_polygon(lat, lon, wind_to_deg, R_head, LW, t_min)
        area = compute_ellipse_area_acres(R_head, LW, t_min)
        polygons.append({
            "t_hr": t_hr, "lats": lats_p, "lons": lons_p,
            "area_acres": area, "color": color,
        })

    # -----------------------------------------------------------------------
    # FWI summary
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("**Canadian Forest Fire Weather Index (Van Wagner & Pickett 1985)**")
    kc = st.columns(6)
    metrics = [
        ("FFMC", f"{ffmc:.1f}", "Fine Fuel Moisture Code (0-101). >85 = extreme fine-fuel dryness."),
        ("ISI",  f"{isi:.1f}",  "Initial Spread Index. Combines FFMC + wind. >15 = high spread potential."),
        ("DMC",  f"{dmc:.1f}",  "Duff Moisture Code. Deep organic layer dryness indicator."),
        ("DC",   f"{dc:.1f}",   "Drought Code. Seasonal cumulative drought stress (deep layers)."),
        ("BUI",  f"{bui:.1f}",  "Build-up Index. Available fuel available for combustion."),
        ("FWI",  f"{fwi:.1f}",  "Fire Weather Index. Overall fire danger rating."),
    ]
    for col, (label, val, hlp) in zip(kc, metrics):
        col.metric(label, val, help=hlp)

    st.markdown(
        f"<div style='background:{dcolor}22;border-left:4px solid {dcolor};"
        f"padding:8px 14px;border-radius:4px;margin:8px 0'>"
        f"<b style='color:{dcolor}'>Fire Danger: {dlabel}</b>"
        f" &nbsp;&mdash;&nbsp; FWI = {fwi:.1f} &nbsp;&mdash;&nbsp; {ddesc}</div>",
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Spread rate summary
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("**Rothermel (1972) Spread Rate and Van Wagner (1969) Ellipse Geometry**")
    sc = st.columns(5)
    sc[0].metric("Head spread rate",  f"{R_head:.3f} m/min", f"{R_head * 60:.0f} m/hr")
    sc[1].metric("Backing spread",    f"{R_back:.3f} m/min",
                 help="Rate of spread in the upwind direction.")
    sc[2].metric("Flank spread",      f"{R_flank:.3f} m/min",
                 help="Spread perpendicular to wind (ellipse semi-minor axis rate).")
    sc[3].metric("L/W ratio",         f"{LW:.1f}:1",
                 help="Ellipse length-to-width. Higher wind = more elongated.")
    sc[4].metric("Byram intensity",   f"{intensity:.0f} kW/m",
                 help="<100 kW/m = manageable; >3000 kW/m = generally uncontrollable (Byram 1959).")

    # -----------------------------------------------------------------------
    # Area table
    # -----------------------------------------------------------------------
    rows = []
    for p in polygons:
        rows.append({
            "Time horizon": f"{p['t_hr']}h",
            "Area (acres)": f"{p['area_acres']:,.0f}",
            "Head spread (m/min)": f"{R_head:.3f}",
            "Byram intensity (kW/m)": f"{intensity:.0f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # Map
    # -----------------------------------------------------------------------
    st.markdown("**Predicted fire perimeters at 1h, 3h, 6h, 12h, 24h**")
    fig = go.Figure()

    # Ellipses — outermost first (so inner ones render on top)
    for poly in reversed(polygons):
        fig.add_trace(go.Scattermapbox(
            lat=poly["lats"],
            lon=poly["lons"],
            mode="lines",
            fill="toself",
            fillcolor=poly["color"] + "28",
            line=dict(color=poly["color"], width=2),
            name=f"{poly['t_hr']}h  ({poly['area_acres']:,.0f} ac)",
            hovertemplate=f"<b>{poly['t_hr']}h perimeter</b><br>Area: {poly['area_acres']:,.0f} acres<extra></extra>",
        ))

    # Ignition point
    fig.add_trace(go.Scattermapbox(
        lat=[lat], lon=[lon],
        mode="markers+text",
        marker=dict(size=10, color="#FF0000"),
        text=["Ignition"],
        textposition="top right",
        name="Ignition point",
        hovertemplate="<b>Ignition point</b><br>%{lat:.4f}, %{lon:.4f}<extra></extra>",
    ))

    # Wind/spread direction arrow (short line segment)
    arr_lat = lat + 0.04 * cos(radians(wind_to_deg))
    arr_lon = lon + 0.04 * sin(radians(wind_to_deg)) / max(cos(radians(lat)), 0.001)
    fig.add_trace(go.Scattermapbox(
        lat=[lat, arr_lat],
        lon=[lon, arr_lon],
        mode="lines",
        line=dict(color="#00BFFF", width=3),
        name=f"Spread direction ({wind_to_deg:.0f} deg)",
        hoverinfo="skip",
    ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=lat, lon=lon),
            zoom=10,
        ),
        template="plotly_dark",
        height=540,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            bgcolor="rgba(13,17,23,0.85)",
            font=dict(color="#e6edf3", size=11),
            x=0.01, y=0.99,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Model assumptions expander
    # -----------------------------------------------------------------------
    with st.expander("Model assumptions and scientific basis"):
        eta_M_val = _moisture_damping(fm_live, fm_obj["Mx"])
        phi_W_val = fm_obj["wind_a"] * (wind_mph / 10.0) ** fm_obj["wind_b"]
        phi_S_val = 5.275 * tan(radians(slope_deg)) ** 2
        st.markdown(f"""
**Spread rate model** — Rothermel (1972) USDA Research Paper INT-115, simplified:

R = R0 x eta_M x (1 + phi_W + phi_S)

| Parameter | Value |
|-----------|-------|
| Fuel model | {fuel_key} |
| Base spread rate R0 | {fm_obj['R0']} m/min |
| 10-hr fuel moisture (FFMC proxy) | {fm_live:.1f}% |
| Extinction moisture Mx | {fm_obj['Mx']:.0f}% |
| Moisture damping eta_M | {eta_M_val:.3f} |
| Wind coefficient phi_W | {phi_W_val:.3f} |
| Slope coefficient phi_S | {phi_S_val:.3f} |
| **Head spread rate R** | **{R_head:.3f} m/min** |

**Ellipse model** — Van Wagner (1969), Forestry Chronicle 45(2):103:

L/W = 0.936 exp(0.2566 w) + 0.461 exp(-0.1548 w) - 0.397  (w = wind mph)

Eccentricity e = sqrt(1 - 1/LW^2), R_back = R_head x (1-e)/(1+e)

**Fire danger rating** — Canadian FWI system (Van Wagner & Pickett 1985, Technical Report 33).

**Limitations:** Assumes uniform fuels and steady-state spread. Spotting, terrain channeling,
and convective columns are not modeled. Byram intensity thresholds from Alexander (1982).
Always defer to the incident commander and official evacuation orders.
""")


# ===========================================================================
# Tab 2: Fire Weather & AQI
# ===========================================================================

def _render_weather_aqi():
    st.subheader("Fire Weather and Air Quality — Live Dashboard")
    st.markdown(
        "Weather from **Open-Meteo** (ECMWF). "
        "Air quality from **CAMS (Copernicus Atmosphere Monitoring Service)** via Open-Meteo. "
        "Free, no API key required."
    )

    col_loc, _ = st.columns([3, 1])
    with col_loc:
        loc_q = st.text_input(
            "Location",
            placeholder="e.g.  Los Angeles, CA   or   34.05, -118.24",
            key="aqi_location",
        )

    lat_a = st.session_state.get("aqi_lat", 34.05)
    lon_a = st.session_state.get("aqi_lon", -118.24)
    if loc_q:
        lat_a, lon_a = _resolve_location(loc_q, "aqi_lat", "aqi_lon", lat_a, lon_a)

    weather = _fetch_weather(lat_a, lon_a)
    aqi_data = _fetch_aqi(lat_a, lon_a)

    # --- Weather cards ---
    if weather:
        st.markdown("**Current Weather Conditions**")
        wc = st.columns(5)
        wc[0].metric("Temperature",     f"{weather.get('temperature_2m', '--'):.1f} C")
        wc[1].metric("Humidity",        f"{weather.get('relative_humidity_2m', '--'):.0f}%")
        wc[2].metric("Wind Speed",      f"{weather.get('wind_speed_10m', '--'):.1f} mph")
        wc[3].metric("Wind Direction",  f"{weather.get('wind_direction_10m', '--'):.0f} deg (FROM)")
        wc[4].metric("24h Precip",      f"{weather.get('precipitation', 0):.1f} mm")

        T    = float(weather.get("temperature_2m",       25) or 25)
        H    = float(weather.get("relative_humidity_2m", 30) or 30)
        W_mph = float(weather.get("wind_speed_10m",      10) or 10)
        W_kph = W_mph * 1.60934
        rain  = float(weather.get("precipitation", 0) or 0)
        month = datetime.now().month

        ffmc  = compute_ffmc(T, H, W_kph, rain)
        isi   = compute_isi(ffmc, W_kph)
        dmc   = compute_dmc(T, H, rain, month)
        dc    = compute_dc(T, rain, month)
        bui   = compute_bui(dmc, dc)
        fwi   = compute_fwi(isi, bui)
        dlabel, dcolor, _ = fwi_danger(fwi)

        st.divider()
        st.markdown("**Canadian FWI Fire Danger Rating (computed from live weather)**")
        fc = st.columns(4)
        fc[0].metric("FFMC", f"{ffmc:.1f}", help=">85 = critical fine-fuel dryness")
        fc[1].metric("ISI",  f"{isi:.1f}",  help=">15 = high initial spread potential")
        fc[2].metric("FWI",  f"{fwi:.1f}",  help="Fire Weather Index (overall danger)")
        fc[3].metric("Danger Class", dlabel)

        st.markdown(
            f"<div style='background:{dcolor}22;border-left:4px solid {dcolor};"
            f"padding:8px 14px;border-radius:4px;margin:8px 0'>"
            f"<b style='color:{dcolor}'>Danger: {dlabel}</b>"
            f" &nbsp;&mdash;&nbsp; FWI = {fwi:.1f}</div>",
            unsafe_allow_html=True,
        )

        if H < 15 and W_mph > 25:
            st.error("Red Flag conditions: humidity below 15% with winds above 25 mph.")
        elif H < 20 or W_mph > 20:
            st.warning("Elevated fire weather: low humidity or elevated winds present.")
    else:
        st.warning("Weather data unavailable. Try entering a valid location above.")

    st.divider()

    # --- AQI cards ---
    if aqi_data:
        st.markdown("**Air Quality Index (US EPA scale — CAMS Copernicus data)**")
        us_aqi = int(aqi_data.get("us_aqi", 0) or 0)
        pm25   = float(aqi_data.get("pm2_5", 0) or 0)
        pm10   = float(aqi_data.get("pm10",  0) or 0)
        dust   = float(aqi_data.get("dust",  0) or 0)
        co     = float(aqi_data.get("carbon_monoxide", 0) or 0)
        alabel, acolor = aqi_label_color(us_aqi)

        st.markdown(
            f"<div style='background:{acolor}22;border-left:4px solid {acolor};"
            f"padding:8px 14px;border-radius:4px;margin-bottom:12px'>"
            f"<b style='color:{acolor}'>US AQI: {us_aqi} — {alabel}</b></div>",
            unsafe_allow_html=True,
        )

        ac = st.columns(4)
        ac[0].metric("PM2.5", f"{pm25:.1f} ug/m3",
                     help="Fine particles (primary wildfire smoke). Safe: <12 ug/m3 (US annual standard).")
        ac[1].metric("PM10",  f"{pm10:.1f} ug/m3",
                     help="Coarse particles. Safe: <54 ug/m3.")
        ac[2].metric("Dust",  f"{dust:.1f} ug/m3",
                     help="Mineral dust and aerosols — elevated during high winds and fire events.")
        ac[3].metric("CO",    f"{co:.0f} ug/m3",
                     help="Carbon monoxide. Wildfire smoke is CO-rich. WHO guideline: <4400 ug/m3 (1h).")

        # AQI scale bar
        scale_fig = go.Figure()
        for lo, hi, lbl, clr in AQI_CATEGORIES:
            scale_fig.add_trace(go.Bar(
                x=[hi - lo], base=lo, y=["AQI"],
                orientation="h",
                marker_color=clr,
                name=lbl, text=lbl,
                textposition="inside",
                hovertemplate=f"{lbl}: {lo}-{hi}<extra></extra>",
            ))
        if us_aqi > 0:
            scale_fig.add_vline(
                x=us_aqi, line_color="white", line_width=3,
                annotation_text=f"Now: {us_aqi}",
                annotation_position="top",
            )
        scale_fig.update_layout(
            template="plotly_dark", height=100, showlegend=False, barmode="stack",
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(range=[0, 300], showticklabels=True),
            yaxis=dict(showticklabels=False),
        )
        st.plotly_chart(scale_fig, use_container_width=True)

        health_guidance = {
            "Good":                  "Air quality is satisfactory. No restrictions for outdoor activity.",
            "Moderate":              "Acceptable. Unusually sensitive people should limit prolonged exertion outdoors.",
            "Unhealthy (Sensitive)": "People with lung disease, older adults, and children: reduce prolonged outdoor exertion.",
            "Unhealthy":             "Everyone may begin to experience effects. Sensitive groups: avoid prolonged outdoor exertion.",
            "Very Unhealthy":        "Health alert: everyone may experience serious effects. Avoid outdoor exertion.",
            "Hazardous":             "Emergency conditions. Entire population likely affected. Stay indoors with windows closed.",
        }
        with st.expander("Health guidance for this AQI level"):
            st.info(health_guidance.get(alabel, "Check local health authorities for guidance."))
    else:
        st.warning("AQI data unavailable. Enter a valid location above.")


# ===========================================================================
# Tab 3: Risk Zone Forecast (historical hotspot clusters, FIRMS overlay)
# ===========================================================================

def _render_risk_zone_forecast():
    st.subheader("Risk Zone Forecast — Historical Hotspot Clusters")
    st.markdown(
        "Hotspot predictions combine **current NASA FIRMS active fire data** with "
        "**historical WiDS ignition patterns** (2021-2025) and seasonal climate signals."
    )

    firms_df, firms_src = _fetch_firms()
    col_meta1, col_meta2, col_meta3 = st.columns(3)
    with col_meta1:
        st.caption(f"Live data: {'NASA FIRMS (live)' if firms_src == 'live' else 'Historical patterns only'}")
    with col_meta2:
        if firms_df is not None:
            st.metric("Active FIRMS hotspots", len(firms_df))
    with col_meta3:
        st.metric("Historical cluster zones", len(HISTORICAL_HOTSPOT_CLUSTERS))

    hotspot_df = pd.DataFrame(HISTORICAL_HOTSPOT_CLUSTERS)

    if firms_df is not None and "latitude" in firms_df.columns:
        firms_us = firms_df[
            pd.to_numeric(firms_df["latitude"],  errors="coerce").between(25, 50) &
            pd.to_numeric(firms_df["longitude"], errors="coerce").between(-125, -65)
        ].copy()
        firms_us["lat_f"] = pd.to_numeric(firms_us["latitude"],  errors="coerce")
        firms_us["lon_f"] = pd.to_numeric(firms_us["longitude"], errors="coerce")
        for i, row in hotspot_df.iterrows():
            nearby = firms_us[
                firms_us["lat_f"].sub(row["lat"]).abs().lt(1.5) &
                firms_us["lon_f"].sub(row["lon"]).abs().lt(1.5)
            ]
            hotspot_df.loc[i, "firms_nearby"] = len(nearby)
            if len(nearby) > 5:
                hotspot_df.loc[i, "risk"] = min(0.98, row["risk"] + 0.05)
    else:
        hotspot_df["firms_nearby"] = 0

    hotspot_df["risk_pct"] = (hotspot_df["risk"] * 100).round(1)
    hotspot_df["priority"] = hotspot_df["risk"].apply(
        lambda r: "Critical" if r >= 0.85 else ("High" if r >= 0.70 else "Moderate")
    )
    hotspot_df["vul_label"] = hotspot_df["vul_svi"].apply(
        lambda s: "Very High" if s >= 0.75 else ("High" if s >= 0.5 else "Moderate")
    )

    fig_map = go.Figure()
    for _, row in hotspot_df.iterrows():
        color = "#FF4444" if row["risk"] >= 0.85 else ("#FF9800" if row["risk"] >= 0.70 else "#FFC107")
        fig_map.add_trace(go.Scattergeo(
            lat=[row["lat"]], lon=[row["lon"]],
            mode="markers+text",
            marker=dict(size=row["risk"] * 30 + 8, color=color, opacity=0.8),
            text=row["name"],
            textposition="top center",
            name=row["name"],
            hovertemplate=(
                f"<b>{row['name']}</b><br>"
                f"Risk: {row['risk_pct']}%<br>"
                f"SVI: {row['vul_label']}<br>"
                "<extra></extra>"
            ),
        ))

    if firms_df is not None and "latitude" in firms_df.columns:
        try:
            fplot = firms_df[
                pd.to_numeric(firms_df["latitude"], errors="coerce").between(25, 50)
            ].head(200)
            fig_map.add_trace(go.Scattergeo(
                lat=pd.to_numeric(fplot["latitude"],  errors="coerce"),
                lon=pd.to_numeric(fplot["longitude"], errors="coerce"),
                mode="markers",
                marker=dict(size=4, color="red", opacity=0.4),
                name="NASA FIRMS (live)",
                hoverinfo="skip",
            ))
        except Exception:
            pass

    fig_map.update_layout(
        template="plotly_dark",
        title="Predicted High-Risk Zones + Live FIRMS Hotspots",
        geo=dict(
            scope="usa", showland=True, showlakes=True,
            showcountries=True, showsubunits=True,
            projection=dict(type="albers usa"),
        ),
        height=480,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.subheader("Ranked Hotspot Zones")
    display_df = hotspot_df[["priority", "name", "state", "risk_pct", "vul_label"]].rename(columns={
        "priority": "Priority", "name": "Zone", "state": "State",
        "risk_pct": "Risk Score (%)", "vul_label": "SVI Vulnerability",
    })
    st.dataframe(
        display_df.sort_values("Risk Score (%)", ascending=False),
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Predicted Growth Curves — Top 3 Zones")
    top3 = hotspot_df.nlargest(3, "risk")
    hours = [0, 1, 3, 6, 12, 24, 48, 72]
    colors_growth = ["#FF4444", "#FF9800", "#FFC107"]

    fig_growth = go.Figure()
    for i, (_, zone) in enumerate(top3.iterrows()):
        curve = (
            "fast_escalation" if zone["risk"] >= 0.85
            else "moderate" if zone["risk"] >= 0.70
            else "slow"
        )
        acres = [0] + GROWTH_CURVES[curve]
        fig_growth.add_trace(go.Scatter(
            x=hours, y=acres,
            mode="lines+markers",
            name=zone["name"],
            line=dict(color=colors_growth[i], width=2),
        ))

    fig_growth.update_layout(
        template="plotly_dark",
        title="Predicted Fire Size Over Time (acres) — Historical Growth Pattern",
        xaxis_title="Hours from Ignition",
        yaxis_title="Predicted Acres",
        height=340,
        margin=dict(l=40, r=10, t=40, b=40),
    )
    st.plotly_chart(fig_growth, use_container_width=True)
    st.caption(
        "Growth curves from NIFC historical data and WiDS fire escalation classification model. "
        "Actual growth depends on real-time wind, humidity, and fuel moisture."
    )


# ===========================================================================
# Main entry point
# ===========================================================================

def render_fire_prediction_page(role="analyst"):
    st.title("Fire Predictor")
    st.caption(
        "Rothermel (1972) surface fire spread  |  Van Wagner (1969) elliptical shape  |  "
        "Canadian FWI system (Van Wagner & Pickett 1985)  |  Open-Meteo live weather + AQI"
    )

    tab1, tab2, tab3 = st.tabs(["Spot Fire Spread", "Fire Weather & AQI", "Risk Zone Forecast"])
    with tab1:
        _render_spot_fire_spread()
    with tab2:
        _render_weather_aqi()
    with tab3:
        _render_risk_zone_forecast()
