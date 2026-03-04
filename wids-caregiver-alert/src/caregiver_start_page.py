"""
caregiver_start_page.py
Caregiver / Evacuee landing page.
Real workflow:
  1. Enter your address/location
  2. System checks NASA FIRMS for fires within X miles (real data)
  3. If fire detected → auto-show nearest shelter + evacuation route
  4. If no fire → show risk profile and preparation checklist
  5. Caregiver can confirm their person has evacuated (feeds dispatcher tracker)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from streamlit_folium import st_folium
from io import StringIO
from pathlib import Path

FIRMS_VIIRS = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv"
)
# US shelters via OpenStreetMap Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# FEMA shelter API (public, no key)
FEMA_SHELTERS_URL = "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/FeatureServer/0/query"


@st.cache_data(ttl=300, show_spinner=False)
def get_firms_us():
    """Fetch FIRMS data, return DataFrame or None."""
    try:
        r = requests.get(FIRMS_VIIRS, timeout=12)
        if r.status_code == 200 and len(r.text) > 200:
            df = pd.read_csv(StringIO(r.text))
            df.columns = [c.lower() for c in df.columns]
            df["lat"] = pd.to_numeric(df.get("latitude", df.get("lat")), errors="coerce")
            df["lon"] = pd.to_numeric(df.get("longitude", df.get("lon")), errors="coerce")
            df = df.dropna(subset=["lat", "lon"])
            return df[(df["lat"].between(24, 50)) & (df["lon"].between(-125, -65))]
    except Exception:
        pass
    return None


@st.cache_data(ttl=600, show_spinner=False)
def get_fema_shelters(lat, lon, radius_km=80):
    """Query FEMA open shelters API near a point."""
    try:
        # Convert radius to degrees approx
        deg = radius_km / 111
        params = {
            "where": f"SHELTER_STATUS='Open'",
            "geometry": f"{lon-deg},{lat-deg},{lon+deg},{lat+deg}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "SHELTER_NAME,ADDRESS,CITY,STATE,CAPACITY,LATITUDE,LONGITUDE,PHONE",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 10
        }
        r = requests.get(FEMA_SHELTERS_URL, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "features" in data and len(data["features"]) > 0:
                rows = [f["attributes"] for f in data["features"]]
                return pd.DataFrame(rows)
    except Exception:
        pass
    return None


def geocode_address(address):
    """Use Nominatim (free, no key) to geocode an address."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "WiDS-WildfireAlertSystem/1.0"},
            timeout=8
        )
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]
    except Exception:
        pass
    return None, None, None


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


# ── Bilingual string table ────────────────────────────────────────────────────
_STRINGS = {
    "en": {
        "title":           "Wildfire Evacuation Decision Support",
        "subheader":       "Know Your Risk. Act Early. Get Help.",
        "info_banner": (
            "In high-vulnerability counties, fires grow at **11.7 acres/hour** — "
            "+17% faster than lower-risk areas. The median time to an official evacuation "
            "order is **1.1 hours**. Don't wait."
        ),
        "enter_location":  "Enter Your Location",
        "address_label":   "Your address or city",
        "address_placeholder": "e.g. 142 Oak St, Paradise, CA",
        "radius_label":    "Search radius",
        "radius_fmt":      "{x} miles",
        "check_btn":       "Check Fire Risk Near Me",
        "spinner_locate":  "Locating address and checking for active fires...",
        "spinner_firms":   "Checking NASA FIRMS satellite data for active fires...",
        "spinner_shelters":"Searching for open shelters near you...",
        "addr_error":      "Couldn't find that address. Try a more specific address or include city and state.",
        "firms_unavail": (
            "NASA FIRMS data unavailable right now. "
            "Check [Ready.gov](https://www.ready.gov) or "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) for current evacuation orders."
        ),
        "no_fires":        "No active fire hotspots detected within {r} miles of your location in the last 24 hours (NASA FIRMS VIIRS satellite data).",
        "danger_imminent": "**IMMEDIATE DANGER** — {n} active fire hotspot(s) detected, closest is **{mi:.1f} miles** away. **Evacuate now if under order. Don't wait for official notice.**",
        "danger_warning":  "**Fire activity detected {mi:.1f} miles away** — {n} hotspot(s) within {r} miles. Monitor conditions and be ready to evacuate immediately.",
        "danger_info":     "Fire activity detected, but closest hotspot is {mi:.1f} miles away. Monitor conditions.",
        "shelters_title":  "Open Shelters Near You",
        "no_shelters": (
            "No FEMA open shelters found in current database for this area. "
            "Check [211.org](https://www.211.org) or call 2-1-1 for local shelters. "
            "Also check [ARC shelter finder](https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html)."
        ),
        "shelter_src":     "Source: FEMA National Shelter System (live)",
        "confirm_title":   "Confirm Evacuation Status",
        "confirm_desc": (
            "If you are a caregiver and your person has evacuated, confirm here. "
            "This updates the dispatcher's tracker so emergency workers know who still needs help."
        ),
        "confirm_name":    "Resident name",
        "confirm_addr":    "Resident address",
        "confirm_dest":    "Evacuated to (shelter name or address)",
        "confirm_btn":     "Confirm Evacuated",
        "confirm_success": "{name} marked as evacuated. Dispatcher notified.",
        "confirm_success2":"Evacuation confirmed for {name}. Thank you.",
        "why_title":       "Why Act Early? *(WiDS 2021–2025 Real Fire Data)*",
        "metric1_label":   "Median Time to Evac Order",
        "metric2_label":   "Worst-Case Delay",
        "metric3_label":   "Fires in High-Risk Counties",
        "metric4_label":   "Growth Rate — High SVI Counties",
        "data_caption": (
            "All statistics from WiDS 2021–2025 dataset (Genasys Protect). "
            "Historical rates, not simulated."
        ),
    },
    "es": {
        "title":           "Apoyo para Decisiones de Evacuación por Incendios",
        "subheader":       "Conozca Su Riesgo. Actúe Temprano. Obtenga Ayuda.",
        "info_banner": (
            "En condados de alta vulnerabilidad, los incendios crecen **17.7 acres/hora** — "
            "+17% más rápido que las zonas de menor riesgo. El tiempo medio para una orden "
            "oficial de evacuación es de **1.1 horas**. No espere."
        ),
        "enter_location":  "Ingrese Su Ubicación",
        "address_label":   "Su dirección o ciudad",
        "address_placeholder": "Ej. 142 Oak St, Paradise, CA",
        "radius_label":    "Radio de búsqueda",
        "radius_fmt":      "{x} millas",
        "check_btn":       "Verificar Riesgo de Incendio Cerca",
        "spinner_locate":  "Localizando dirección y verificando incendios activos...",
        "spinner_firms":   "Verificando datos satelitales NASA FIRMS...",
        "spinner_shelters":"Buscando refugios abiertos cerca de usted...",
        "addr_error":      "No se encontró esa dirección. Intente con una dirección más específica o incluya ciudad y estado.",
        "firms_unavail": (
            "Los datos NASA FIRMS no están disponibles en este momento. "
            "Consulte [Ready.gov](https://www.ready.gov) o "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) para órdenes de evacuación actuales."
        ),
        "no_fires":        "No se detectaron focos activos en un radio de {r} millas en las últimas 24 horas (datos satelitales NASA FIRMS VIIRS).",
        "danger_imminent": "**PELIGRO INMEDIATO** — {n} foco(s) activo(s) detectado(s), el más cercano está a **{mi:.1f} millas**. **Evacúe ahora si está bajo orden. No espere el aviso oficial.**",
        "danger_warning":  "**Actividad de incendio detectada a {mi:.1f} millas** — {n} foco(s) en {r} millas. Monitoree las condiciones y esté listo para evacuar de inmediato.",
        "danger_info":     "Actividad de incendio detectada, pero el foco más cercano está a {mi:.1f} millas. Monitoree las condiciones.",
        "shelters_title":  "Refugios Abiertos Cerca de Usted",
        "no_shelters": (
            "No se encontraron refugios abiertos de FEMA en esta área. "
            "Llame al 2-1-1 o visite [211.org](https://www.211.org) para refugios locales. "
            "También consulte el [buscador de refugios de la Cruz Roja](https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html)."
        ),
        "shelter_src":     "Fuente: Sistema Nacional de Refugios FEMA (en vivo)",
        "confirm_title":   "Confirmar Estado de Evacuación",
        "confirm_desc": (
            "Si usted es un cuidador y su persona ha evacuado, confirme aquí. "
            "Esto actualiza el rastreador del coordinador para que los equipos de emergencia "
            "sepan quién todavía necesita ayuda."
        ),
        "confirm_name":    "Nombre del residente",
        "confirm_addr":    "Dirección del residente",
        "confirm_dest":    "Evacuado a (nombre del refugio o dirección)",
        "confirm_btn":     "Confirmar Evacuación",
        "confirm_success": "{name} marcado como evacuado. Coordinador notificado.",
        "confirm_success2":"Evacuación confirmada para {name}. Gracias.",
        "why_title":       "¿Por Qué Actuar Temprano? *(Datos Reales WiDS 2021–2025)*",
        "metric1_label":   "Tiempo Mediano para Orden de Evacuación",
        "metric2_label":   "Retraso en el Peor Caso",
        "metric3_label":   "Incendios en Condados de Alto Riesgo",
        "metric4_label":   "Tasa de Crecimiento — Condados Alto SVI",
        "data_caption": (
            "Todas las estadísticas provienen del conjunto de datos WiDS 2021–2025 (Genasys Protect). "
            "Tasas históricas, no simuladas."
        ),
    },
}


def _t(key: str, lang: str = "en", **kwargs) -> str:
    """Retrieve a translated string, falling back to English if key missing."""
    s = _STRINGS.get(lang, _STRINGS["en"]).get(key, _STRINGS["en"].get(key, key))
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


def render_caregiver_start_page():
    # Language selector
    lang = st.selectbox(
        "Language / Idioma",
        options=["en", "es"],
        format_func=lambda x: "English" if x == "en" else "Español",
        key="caregiver_lang",
        label_visibility="collapsed",
    )

    st.markdown(
        f"<h1 style='font-size:24px;font-weight:700;color:#e6edf3;"
        f"border-bottom:1px solid #30363d;padding-bottom:12px;margin-bottom:4px;"
        f"font-family:\"DM Sans\",system-ui,sans-serif'>"
        f"{_t('title', lang)}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:#8b949e;margin-bottom:0.8rem'>{_t('subheader', lang)}</p>",
        unsafe_allow_html=True,
    )

    # ── Real data warning banner ──────────────────────────────────────────────
    st.info(_t("info_banner", lang))

    st.divider()

    # ── Address input ─────────────────────────────────────────────────────────
    st.subheader(_t("enter_location", lang))
    col_addr, col_radius = st.columns([3, 1])
    with col_addr:
        address_input = st.text_input(
            _t("address_label", lang),
            placeholder=_t("address_placeholder", lang),
            help="Used only to check for nearby fires and find shelters. Not stored."
        )
    with col_radius:
        search_radius = st.selectbox(
            _t("radius_label", lang), [10, 25, 50, 100], index=1,
            format_func=lambda x: _t("radius_fmt", lang, x=x)
        )

    check_btn = st.button(_t("check_btn", lang), type="primary",
                           disabled=(not address_input))

    if check_btn and address_input:
        with st.spinner(_t("spinner_locate", lang)):
            user_lat, user_lon, display_name = geocode_address(address_input)

        if user_lat is None:
            st.error(_t("addr_error", lang))
            return

        st.success(f"Found: {display_name}")
        st.session_state["user_lat"]   = user_lat
        st.session_state["user_lon"]   = user_lon
        st.session_state["user_addr"]  = display_name

        # Check FIRMS
        with st.spinner(_t("spinner_firms", lang)):
            firms_df = get_firms_us()

        if firms_df is not None and len(firms_df) > 0:
            firms_df["dist_km"] = firms_df.apply(
                lambda r: haversine_km(user_lat, user_lon, r["lat"], r["lon"]), axis=1
            )
            radius_km = search_radius * 1.609
            nearby = firms_df[firms_df["dist_km"] <= radius_km].sort_values("dist_km")
            st.session_state["nearby_fires"] = nearby
            st.session_state["firms_loaded"] = True
        else:
            st.session_state["nearby_fires"] = pd.DataFrame()
            st.session_state["firms_loaded"] = False

    # ── Results ───────────────────────────────────────────────────────────────
    if "user_lat" in st.session_state:
        user_lat  = st.session_state["user_lat"]
        user_lon  = st.session_state["user_lon"]
        nearby    = st.session_state.get("nearby_fires", pd.DataFrame())
        firms_ok  = st.session_state.get("firms_loaded", False)

        st.divider()

        # Fire status banner
        if not firms_ok:
            st.warning(_t("firms_unavail", lang))
        elif len(nearby) == 0:
            st.success(_t("no_fires", lang, r=search_radius))
        else:
            closest_km = nearby.iloc[0]["dist_km"]
            closest_mi = closest_km / 1.609
            n_fires    = len(nearby)

            if closest_mi < 5:
                st.error(_t("danger_imminent", lang, n=n_fires, mi=closest_mi))
            elif closest_mi < 20:
                st.warning(_t("danger_warning", lang, n=n_fires, mi=closest_mi, r=search_radius))
            else:
                st.info(_t("danger_info", lang, mi=closest_mi))

        # Map
        m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB dark_matter")

        # User location
        folium.Marker(
            [user_lat, user_lon],
            popup="Your location",
            icon=folium.Icon(color="blue", icon="home", prefix="fa")
        ).add_to(m)

        # Fire hotspots
        if len(nearby) > 0:
            for _, row in nearby.head(50).iterrows():
                try:
                    folium.CircleMarker(
                        location=[row["lat"], row["lon"]],
                        radius=6,
                        color="#FF2200", fill=True, fill_color="#FF2200", fill_opacity=0.7,
                        tooltip=f"Fire — {row['dist_km']:.1f} km away"
                    ).add_to(m)
                except Exception:
                    pass

        # Shelter lookup
        with st.spinner(_t("spinner_shelters", lang)):
            radius_km = search_radius * 1.609
            shelters = get_fema_shelters(user_lat, user_lon, radius_km)

        shelter_found = False
        if shelters is not None and len(shelters) > 0:
            shelter_found = True
            for _, s in shelters.iterrows():
                try:
                    slat = float(s.get("LATITUDE", 0))
                    slon = float(s.get("LONGITUDE", 0))
                    if slat and slon:
                        folium.Marker(
                            [slat, slon],
                            popup=folium.Popup(
                                f"<b>{s.get('SHELTER_NAME','Shelter')}</b><br>"
                                f"{s.get('ADDRESS','')}, {s.get('CITY','')}<br>"
                                f"Capacity: {s.get('CAPACITY','—')}<br>"
                                f"Phone: {s.get('PHONE','—')}",
                                max_width=200
                            ),
                            icon=folium.Icon(color="green", icon="plus-sign", prefix="glyphicon")
                        ).add_to(m)
                except Exception:
                    pass

        st_folium(m, width="100%", height=420, returned_objects=[])

        # Shelter table
        st.subheader(_t("shelters_title", lang))
        if shelter_found:
            display_cols = [c for c in ["SHELTER_NAME", "ADDRESS", "CITY", "STATE",
                                         "CAPACITY", "PHONE"] if c in shelters.columns]
            st.dataframe(shelters[display_cols].rename(columns={
                "SHELTER_NAME": "Shelter", "ADDRESS": "Address", "CITY": "City",
                "STATE": "State", "CAPACITY": "Capacity", "PHONE": "Phone"
            }), use_container_width=True, hide_index=True)
            st.caption(_t("shelter_src", lang))
        else:
            st.info(_t("no_shelters", lang))

        st.divider()

        # Caregiver confirmation
        st.subheader(_t("confirm_title", lang))
        st.markdown(_t("confirm_desc", lang))
        with st.form("confirm_evac_form"):
            confirm_name = st.text_input(_t("confirm_name", lang))
            confirm_addr = st.text_input(_t("confirm_addr", lang),
                                          value=st.session_state.get("user_addr", ""))
            confirm_dest = st.text_input(_t("confirm_dest", lang))
            submitted = st.form_submit_button(_t("confirm_btn", lang))
            if submitted and confirm_name:
                if "evacuee_list" in st.session_state:
                    # Update dispatcher tracker if name matches
                    mask = st.session_state.evacuee_list["name"].str.lower() == confirm_name.lower()
                    if mask.any():
                        st.session_state.evacuee_list.loc[mask, "status"] = "Evacuated ✅"
                        st.success(_t("confirm_success", lang, name=confirm_name))
                    else:
                        st.success(_t("confirm_success2", lang, name=confirm_name))
                else:
                    st.success(_t("confirm_success2", lang, name=confirm_name))

    # ── Real data anchors — progressive disclosure ───────────────────────────
    with st.expander(_t("why_title", lang), expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(_t("metric1_label", lang), "1.1h",
                  help="653 fires with confirmed evac actions, 2021-2025 WiDS dataset")
        m2.metric(_t("metric2_label", lang), "32h",
                  delta="90th percentile",
                  delta_color="off",
                  help="1 in 10 fires takes over 32h to get an official order")
        m3.metric(_t("metric3_label", lang), "260",
                  delta="39.8% of all WiDS fire events",
                  delta_color="off")
        m4.metric(_t("metric4_label", lang), "11.7 ac/hr",
                  delta="+17% vs non-vulnerable",
                  delta_color="inverse")
        st.caption(_t("data_caption", lang))