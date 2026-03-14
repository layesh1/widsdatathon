"""
proactive_alert_page.py
Proactive Fire Threat Alert — 49ers Intelligence Lab · WiDS 2025

KILLER FEATURE: Predict fire threat to a caregiver's address BEFORE official
evacuation orders are issued.

Core thesis from WiDS dataset:
  - Median signal-to-order delay: 1.1 hours (653 fires with orders)
  - 99.74% of detected fires receive NO evacuation action
  - This page alerts caregivers during that gap using fire physics

External APIs used (all free, no key required except FIRMS):
  - OpenStreetMap Nominatim: address geocoding
  - NASA FIRMS VIIRS NRT: active fire detection within 50 km
  - Open-Meteo: current wind speed / direction / humidity

Spread model: simplified Rothermel (Chaparral fuel, R0 = 0.75 m/min)
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from ui_utils import page_header, section_header, render_card, fallback_card, data_source_badge

# ── Constants ─────────────────────────────────────────────────────────────────

FIRMS_API_KEY = "c6c38aac4de4e98571b29a73e3527a8c"
FIRMS_BASE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    f"{FIRMS_API_KEY}/VIIRS_SNPP_NRT"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Rothermel simplified (Chaparral fuel model)
R0_M_MIN = 0.75       # m/min at zero wind
WIND_A   = 0.55       # wind coefficient
WIND_B   = 1.30       # wind exponent
SEARCH_RADIUS_KM = 50.0

# FEMA/Red Cross evacuation time estimates (hours)
MOBILITY_EVAC_HOURS = {
    "mobile_adult":      0.5,
    "elderly":           1.5,
    "disabled":          2.0,
    "no_vehicle":        3.0,
    "medical_equipment": 4.0,
}

# Historical median signal→order delay from WiDS dataset
MEDIAN_ORDER_DELAY_H = 1.1

# ── Bilingual strings ─────────────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    "page_title":         {"en": "Proactive Fire Alert",   "es": "Alerta Proactiva de Incendio"},
    "page_caption":       {
        "en": "Know about fire threats BEFORE official orders — based on fire physics, not bureaucracy.",
        "es": "Conozca las amenazas de incendio ANTES de las órdenes oficiales — basado en física del fuego.",
    },
    "lang_label":         {"en": "Language / Idioma",  "es": "Language / Idioma"},
    "your_address":       {"en": "Your address or zip code",        "es": "Su dirección o código postal"},
    "monitored_address":  {"en": "Monitored person's address (optional)", "es": "Dirección de la persona vigilada (opcional)"},
    "address_ph":         {"en": "e.g. 1234 Oak St, Chico, CA 95928", "es": "ej. 1234 Oak St, Chico, CA 95928"},
    "monitored_ph":       {"en": "Leave blank if same location",    "es": "Dejar en blanco si es la misma ubicación"},
    "mobility_label":     {"en": "Mobility level",                  "es": "Nivel de movilidad"},
    "mobility_opts":      {
        "en": ["Mobile adult", "Elderly", "Disabled", "No vehicle", "Medical equipment"],
        "es": ["Adulto móvil", "Anciano/a", "Discapacitado/a", "Sin vehículo", "Equipo médico"],
    },
    "check_btn":          {"en": "Check fire status",          "es": "Verificar estado de incendio"},
    "geocoding":          {"en": "Geocoding address...",        "es": "Geocodificando dirección..."},
    "checking_fires":     {"en": "Checking NASA FIRMS...",      "es": "Consultando NASA FIRMS..."},
    "checking_weather":   {"en": "Fetching weather data...",    "es": "Obteniendo datos meteorológicos..."},
    "status_clear":       {"en": "CLEAR",       "es": "DESPEJADO"},
    "status_watch":       {"en": "WATCH",       "es": "VIGILANCIA"},
    "status_elevated":    {"en": "ELEVATED",    "es": "ELEVADO"},
    "status_high":        {"en": "HIGH",        "es": "ALTO"},
    "status_critical":    {"en": "CRITICAL",    "es": "CRITICO"},
    "no_fire_msg":        {"en": "No active fires detected within 50 km. Stay alert and monitor official channels.",
                           "es": "No se detectaron incendios activos en 50 km. Manténgase alerta y monitoree los canales oficiales."},
    "evacuate_now":       {"en": "EVACUATE NOW. Fire front estimated within 1 hour. Official order likely NOT yet issued.",
                           "es": "EVACUE AHORA. Frente de fuego estimado en menos de 1 hora. La orden oficial probablemente AUN NO ha sido emitida."},
    "prepare_leave":      {"en": "Pre-order window. Typical official order takes 1.1 h. Prepare to leave immediately.",
                           "es": "Ventana previa a la orden. La orden oficial típica tarda 1.1 h. Prepárese para salir de inmediato."},
    "begin_prep":         {"en": "Begin preparation. Monitor official channels.",
                           "es": "Comience a prepararse. Monitoree los canales oficiales."},
    "stay_alert":         {"en": "Fire detected in region. Stay alert.",
                           "es": "Incendio detectado en la región. Permanezca alerta."},
    "nearest_fire":       {"en": "Nearest fire",           "es": "Incendio más cercano"},
    "est_arrival":        {"en": "Est. fire front arrival", "es": "Llegada est. del frente"},
    "wind_speed":         {"en": "Wind speed",             "es": "Velocidad del viento"},
    "official_eta":       {"en": "Official order ETA",     "es": "ETA orden oficial"},
    "timeline_title":     {"en": "Preparation Timeline",   "es": "Cronograma de Preparación"},
    "now_label":          {"en": "NOW",                    "es": "AHORA"},
    "alert_issued":       {"en": "Alert issued (this app)", "es": "Alerta emitida (esta app)"},
    "official_order_eta": {"en": "Expected official order (historical median: 1.1 h)",
                           "es": "Orden oficial esperada (mediana histórica: 1.1 h)"},
    "fire_arrival":       {"en": "Estimated fire front arrival",
                           "es": "Llegada estimada del frente de fuego"},
    "leave_by":           {"en": "You should leave by",   "es": "Debe salir a más tardar a"},
    "mobility_note":      {"en": "Based on your mobility level, you need {h:.1f} h to evacuate.",
                           "es": "Según su nivel de movilidad, necesita {h:.1f} h para evacuar."},
    "demo_banner":        {"en": "Live API unavailable — showing DEMO data (mock fire 25 km away).",
                           "es": "API no disponible — mostrando datos DEMO (incendio simulado a 25 km)."},
    "geocode_fail":       {"en": "Could not geocode address. Check spelling and try again.",
                           "es": "No se pudo geocodificar la dirección. Revise la ortografía e intente de nuevo."},
    "address_required":   {"en": "Please enter an address.",
                           "es": "Por favor ingrese una dirección."},
    "data_source":        {"en": "NASA FIRMS VIIRS NRT + Open-Meteo",
                           "es": "NASA FIRMS VIIRS NRT + Open-Meteo"},
    "confidence_note":    {"en": "Only FIRMS detections with confidence >= 50% shown.",
                           "es": "Solo se muestran detecciones FIRMS con confianza >= 50%."},
    "monitored_section":  {"en": "Monitored Person", "es": "Persona Vigilada"},
}


def _t(key: str, lang: str) -> str:
    """Return translated string; fall back to English."""
    return _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("en", key)


# ── Geocoding ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for a free-text address via Nominatim, or None."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "WiDS-Wildfire-Alert/1.0"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


# ── NASA FIRMS fire detection ─────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_firms_near(lat: float, lon: float, radius_km: float = SEARCH_RADIUS_KM) -> pd.DataFrame:
    """
    Fetch VIIRS NRT active fire detections within radius_km of (lat, lon).
    Returns DataFrame with columns: latitude, longitude, confidence, frp, acq_date.
    Falls back to mock data on failure.
    """
    deg = radius_km / 111.0
    lon_min, lat_min = round(lon - deg, 4), round(lat - deg, 4)
    lon_max, lat_max = round(lon + deg, 4), round(lat + deg, 4)
    bbox = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    url = f"{FIRMS_BASE}/{bbox}/1"

    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.text) > 100:
            df = pd.read_csv(StringIO(resp.text))
            df.columns = [c.lower().strip() for c in df.columns]

            # Normalise column names (FIRMS uses different names in different endpoints)
            if "latitude" not in df.columns and "lat" in df.columns:
                df = df.rename(columns={"lat": "latitude", "lon": "longitude"})

            for col in ("latitude", "longitude"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Confidence: VIIRS NRT uses 'l','n','h' or numeric
            if "confidence" in df.columns:
                def _parse_conf(v):
                    if isinstance(v, str):
                        return {"l": 30, "n": 65, "h": 85}.get(v.lower(), 50)
                    try:
                        return float(v)
                    except Exception:
                        return 50
                df["confidence"] = df["confidence"].apply(_parse_conf)
            else:
                df["confidence"] = 65

            df = df.dropna(subset=["latitude", "longitude"])
            df = df[df["confidence"] >= 50]
            return df
    except Exception:
        pass

    # Demo fallback — mock fire 25 km north-northeast
    demo_lat = lat + 0.18
    demo_lon = lon + 0.09
    return pd.DataFrame([{
        "latitude": demo_lat,
        "longitude": demo_lon,
        "confidence": 80,
        "frp": 42.3,
        "acq_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "_demo": True,
    }])


# ── Weather ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def fetch_weather(lat: float, lon: float) -> dict:
    """Return current weather dict: wind_mph, wind_dir_deg, rh_pct. Falls back to defaults."""
    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "wind_speed_10m,wind_direction_10m,relative_humidity_2m",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            },
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            cur = data.get("current", {})
            return {
                "wind_mph":    float(cur.get("wind_speed_10m", 10)),
                "wind_dir":    float(cur.get("wind_direction_10m", 270)),
                "rh_pct":      float(cur.get("relative_humidity_2m", 30)),
            }
    except Exception:
        pass
    return {"wind_mph": 10.0, "wind_dir": 270.0, "rh_pct": 30.0}


# ── Haversine distance ────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Rothermel spread ──────────────────────────────────────────────────────────

def rothermel_spread_km_hr(wind_mph: float) -> float:
    """
    Simplified Rothermel surface fire spread (Chaparral fuel model).
      R = R0 * (1 + phi_W)
      phi_W = wind_a * (wind_mph / 10) ** wind_b
    Returns spread rate in km/hr.
    """
    phi_w = WIND_A * (max(wind_mph, 0) / 10.0) ** WIND_B
    r_m_min = R0_M_MIN * (1.0 + phi_w)
    return r_m_min * 0.06   # m/min → km/hr


# ── Alert classification ──────────────────────────────────────────────────────

def classify_alert(est_hours: Optional[float], lang: str) -> tuple[str, str, str]:
    """
    Return (status_key, bg_color, text_color) based on estimated hours to fire front.
    status_key maps to _STRINGS for the display label.
    """
    if est_hours is None:
        return "status_clear", "#0d3321", "#3fb950"
    if est_hours < 1.0:
        return "status_critical", "#3d0b0b", "#FF4B4B"
    if est_hours < 3.0:
        return "status_high", "#3d2600", "#d4a017"
    if est_hours < 6.0:
        return "status_elevated", "#1a2a00", "#a3c442"
    return "status_watch", "#0d1f3a", "#6fa8dc"


def _alert_message_key(status_key: str) -> str:
    mapping = {
        "status_critical": "evacuate_now",
        "status_high":     "prepare_leave",
        "status_elevated": "begin_prep",
        "status_watch":    "stay_alert",
        "status_clear":    "no_fire_msg",
    }
    return mapping.get(status_key, "no_fire_msg")


# ── Cardinal wind direction ───────────────────────────────────────────────────

def wind_dir_str(deg: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((deg + 11.25) / 22.5) % 16
    return dirs[idx]


# ── Preparation timeline chart ────────────────────────────────────────────────

def _render_timeline(
    now: datetime,
    fire_arrival_h: float,
    evac_time_h: float,
    lang: str,
) -> None:
    """Render a horizontal Plotly Gantt-style timeline."""
    official_order_h = MEDIAN_ORDER_DELAY_H
    leave_by_h = max(0.0, fire_arrival_h - evac_time_h)

    events = [
        (0.0,              _t("now_label", lang),          "#3fb950"),
        (official_order_h, _t("official_order_eta", lang), "#d4a017"),
        (fire_arrival_h,   _t("fire_arrival", lang),       "#FF4B4B"),
    ]

    fig = go.Figure()

    # Timeline bar (background)
    fig.add_shape(
        type="line",
        x0=0, x1=fire_arrival_h * 1.1,
        y0=0, y1=0,
        line=dict(color="#30363d", width=2),
    )

    # Event markers
    for h, label, color in events:
        fig.add_trace(go.Scatter(
            x=[h], y=[0],
            mode="markers+text",
            marker=dict(size=16, color=color, line=dict(color="#0d1117", width=2)),
            text=[f"<b>+{h:.1f}h</b><br>{label}"],
            textposition="top center",
            textfont=dict(size=10, color=color),
            showlegend=False,
            hoverinfo="text",
            hovertext=f"{label} — {now + timedelta(hours=h):%H:%M}",
        ))

    # "Leave by" vertical line
    if leave_by_h > 0:
        fig.add_vline(
            x=leave_by_h,
            line=dict(color="#FF4B4B", width=2, dash="dash"),
            annotation_text=f"{_t('leave_by', lang)}: {now + timedelta(hours=leave_by_h):%H:%M}",
            annotation_font_color="#FF4B4B",
            annotation_font_size=11,
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        height=180,
        margin=dict(l=20, r=20, t=40, b=10),
        xaxis=dict(
            title="Hours from now",
            tickfont=dict(color="#8b949e", size=10),
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(visible=False, range=[-0.5, 0.8]),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Core analysis for one address ─────────────────────────────────────────────

def _analyze_address(
    label: str,
    address: str,
    lang: str,
    mobility_key: str,
) -> None:
    """Run fire proximity analysis for one address and render results."""

    # 1. Geocode
    with st.spinner(_t("geocoding", lang)):
        coords = geocode_address(address)

    if coords is None:
        st.error(_t("geocode_fail", lang))
        return

    addr_lat, addr_lon = coords

    # 2. Fetch FIRMS
    with st.spinner(_t("checking_fires", lang)):
        fires_df = fetch_firms_near(addr_lat, addr_lon)

    is_demo = "_demo" in fires_df.columns and fires_df["_demo"].any()
    if is_demo:
        st.info(_t("demo_banner", lang))

    # 3. Compute distances
    fires_df["dist_km"] = fires_df.apply(
        lambda r: haversine_km(addr_lat, addr_lon, r["latitude"], r["longitude"]),
        axis=1,
    )
    fires_df = fires_df[fires_df["dist_km"] <= SEARCH_RADIUS_KM].copy()

    if fires_df.empty:
        st.markdown(
            f"""<div style="background:#0d3321;border:1px solid #3fb950;border-radius:10px;
                padding:20px 18px;margin:8px 0">
              <div style="font-size:20px;font-weight:700;color:#3fb950">
                {_t('status_clear', lang)}</div>
              <div style="font-size:14px;color:#8b949e;margin-top:8px">
                {_t('no_fire_msg', lang)}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # Nearest fire
    nearest = fires_df.loc[fires_df["dist_km"].idxmin()]
    dist_km = float(nearest["dist_km"])
    fire_lat, fire_lon = float(nearest["latitude"]), float(nearest["longitude"])

    # 4. Fetch weather near fire
    with st.spinner(_t("checking_weather", lang)):
        wx = fetch_weather(fire_lat, fire_lon)

    # 5. Rothermel spread estimate
    spread_km_hr = rothermel_spread_km_hr(wx["wind_mph"])
    est_hours = dist_km / spread_km_hr if spread_km_hr > 0 else 999.0

    # 6. Classify
    status_key, bg_color, text_color = classify_alert(est_hours, lang)
    msg_key = _alert_message_key(status_key)

    # ── Alert box ──────────────────────────────────────────────────────────────
    st.markdown(
        f"""<div style="background:{bg_color};border:1px solid {text_color};
            border-radius:10px;padding:20px 18px;margin:8px 0">
          <div style="font-size:22px;font-weight:800;color:{text_color};
               font-family:'DM Sans',system-ui,sans-serif">
            {_t(status_key, lang)}</div>
          <div style="font-size:14px;color:#e6edf3;margin-top:10px;line-height:1.6">
            {_t(msg_key, lang)}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── KPI cards ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card(
            _t("nearest_fire", lang),
            f"{dist_km:.1f} km",
            f"{len(fires_df)} fires within 50 km",
            color=text_color,
        )
    with c2:
        render_card(
            _t("est_arrival", lang),
            f"{est_hours:.1f} h" if est_hours < 100 else ">100 h",
            f"Spread rate: {spread_km_hr:.1f} km/hr",
            color=text_color,
        )
    with c3:
        render_card(
            _t("wind_speed", lang),
            f"{wx['wind_mph']:.0f} mph",
            f"{wind_dir_str(wx['wind_dir'])} ({wx['wind_dir']:.0f}°) · RH {wx['rh_pct']:.0f}%",
            color="#1e3a5f",
        )
    with c4:
        render_card(
            _t("official_eta", lang),
            "+1.1 h",
            "Historical median (WiDS dataset, n=653)",
            color="#d4a017",
        )

    # ── Preparation timeline (HIGH or CRITICAL) ───────────────────────────────
    if status_key in ("status_critical", "status_high", "status_elevated"):
        section_header(_t("timeline_title", lang))
        evac_h = MOBILITY_EVAC_HOURS.get(mobility_key, 1.0)

        mob_note = _t("mobility_note", lang).replace("{h:.1f}", f"{evac_h:.1f}")
        st.caption(mob_note)

        now = datetime.now()
        _render_timeline(now, est_hours, evac_h, lang)

        leave_by_h = max(0.0, est_hours - evac_h)
        leave_time = now + timedelta(hours=leave_by_h)
        if leave_by_h <= 0:
            st.markdown(
                f"<div style='color:#FF4B4B;font-weight:700;font-size:15px'>"
                f"{_t('leave_by', lang)}: NOW — estimated evacuation window has passed.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='color:#d4a017;font-weight:600;font-size:14px'>"
                f"{_t('leave_by', lang)}: <b>{leave_time:%H:%M}</b></div>",
                unsafe_allow_html=True,
            )

    data_source_badge(_t("data_source", lang))
    st.caption(_t("confidence_note", lang))


# ── Main entry point ──────────────────────────────────────────────────────────

def render_proactive_alert_page() -> None:
    # Language selector
    lang = st.selectbox(
        _STRINGS["lang_label"]["en"],
        options=["en", "es"],
        format_func=lambda v: "English" if v == "en" else "Español",
        key="proactive_alert_lang",
        label_visibility="collapsed",
    )

    page_header(
        _t("page_title", lang),
        _t("page_caption", lang),
    )

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form("proactive_alert_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            your_address = st.text_input(
                _t("your_address", lang),
                placeholder=_t("address_ph", lang),
                key="proactive_your_addr",
            )
        with col_b:
            monitored_address = st.text_input(
                _t("monitored_address", lang),
                placeholder=_t("monitored_ph", lang),
                key="proactive_monitored_addr",
            )

        mob_labels = _t("mobility_opts", lang)
        mob_keys   = list(MOBILITY_EVAC_HOURS.keys())
        mobility_display = st.selectbox(
            _t("mobility_label", lang),
            options=range(len(mob_keys)),
            format_func=lambda i: mob_labels[i],
            key="proactive_mobility",
        )

        submitted = st.form_submit_button(
            _t("check_btn", lang),
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        st.info("Enter your address above and click the button to check for nearby fires." if lang == "en"
                else "Ingrese su dirección arriba y haga clic en el botón para verificar incendios cercanos.")
        return

    mobility_key = mob_keys[mobility_display]

    # ── Analyse primary address ───────────────────────────────────────────────
    if not your_address.strip():
        st.warning(_t("address_required", lang))
        return

    st.markdown("---")
    section_header(_t("your_address", lang) + ": " + your_address)
    _analyze_address("primary", your_address.strip(), lang, mobility_key)

    # ── Analyse monitored address (if provided and different) ─────────────────
    if monitored_address.strip() and monitored_address.strip() != your_address.strip():
        st.markdown("---")
        section_header(_t("monitored_section", lang) + ": " + monitored_address)
        _analyze_address("monitored", monitored_address.strip(), lang, mobility_key)
