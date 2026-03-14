"""
monitored_persons_page.py
Monitored Persons Manager — 49ers Intelligence Lab · WiDS 2025

Allows a caregiver to:
  1. Register and manage people they watch over
  2. Check live fire proximity per person (NASA FIRMS + geocoding)
  3. Track evacuation status (session state + optional Supabase sync)
  4. Send individual or batch SMS alerts via Twilio

Storage precedence (most persistent to least):
  1. Supabase evacuation_status table (if authenticated + connected)
  2. st.session_state.monitored_persons (survives page changes in a session)
  3. In-memory (cleared on browser reload)
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from ui_utils import page_header, section_header, render_card, fallback_card, data_source_badge

# ── Optional dependencies ─────────────────────────────────────────────────────

try:
    from auth_supabase import get_supabase
    _HAS_SUPABASE = True
except ImportError:
    _HAS_SUPABASE = False

try:
    from sms_alert import send_evacuation_alert, is_sms_available
except ImportError:
    def is_sms_available() -> bool:
        return False

    def send_evacuation_alert(
        phone: str,
        resident_name: str,
        county: str,
        shelter_name: str = "",
        lang: str = "en",
    ) -> bool:
        return False

# ── Constants ─────────────────────────────────────────────────────────────────

FIRMS_API_KEY = "c6c38aac4de4e98571b29a73e3527a8c"
FIRMS_BASE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    f"{FIRMS_API_KEY}/VIIRS_SNPP_NRT"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

SEARCH_RADIUS_KM = 50.0
SEARCH_DEG       = SEARCH_RADIUS_KM / 111.0

# FEMA/Red Cross evacuation time estimates
MOBILITY_EVAC_HOURS = {
    "mobile_adult":      0.5,
    "elderly":           1.5,
    "disabled":          2.0,
    "no_vehicle":        3.0,
    "medical_equipment": 4.0,
}

MOBILITY_LABELS = {
    "en": {
        "mobile_adult":      "Mobile adult",
        "elderly":           "Elderly",
        "disabled":          "Disabled",
        "no_vehicle":        "No vehicle",
        "medical_equipment": "Medical equipment",
    },
    "es": {
        "mobile_adult":      "Adulto móvil",
        "elderly":           "Anciano/a",
        "disabled":          "Discapacitado/a",
        "no_vehicle":        "Sin vehículo",
        "medical_equipment": "Equipo médico",
    },
}

EVACUATION_STATUSES = ["not_evacuated", "preparing", "evacuated", "safe_at_shelter"]

STATUS_CONFIG = {
    "not_evacuated":  {"label_en": "Not evacuated", "label_es": "No evacuado",     "color": "#FF4B4B", "border": "#FF4B4B"},
    "preparing":      {"label_en": "Preparing",     "label_es": "Preparándose",    "color": "#d4a017", "border": "#d4a017"},
    "evacuated":      {"label_en": "Evacuated",     "label_es": "Evacuado",        "color": "#3fb950", "border": "#3fb950"},
    "safe_at_shelter":{"label_en": "Safe at shelter","label_es":"Seguro en refugio","color": "#3fb950", "border": "#3fb950"},
}

RELATIONSHIP_LABELS = {
    "en": ["Parent / Guardian", "Client", "Neighbor", "Self"],
    "es": ["Padre / Tutor",     "Cliente", "Vecino/a", "Yo mismo/a"],
}
RELATIONSHIP_KEYS = ["parent", "client", "neighbor", "self"]

# ── Bilingual strings ─────────────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    "page_title":      {"en": "Monitored Persons",        "es": "Personas Monitoreadas"},
    "page_caption":    {"en": "Track evacuation status for everyone in your care.",
                        "es": "Realice seguimiento de la evacuación de todas las personas a su cargo."},
    "lang_label":      {"en": "Language / Idioma",        "es": "Language / Idioma"},
    "add_person":      {"en": "Add person",               "es": "Agregar persona"},
    "name_label":      {"en": "Full name",                "es": "Nombre completo"},
    "address_label":   {"en": "Home address",             "es": "Domicilio"},
    "mobility_label":  {"en": "Mobility level",           "es": "Nivel de movilidad"},
    "phone_label":     {"en": "Phone number (for SMS)",   "es": "Número de teléfono (para SMS)"},
    "phone_ph":        {"en": "+1 555 000 0000",          "es": "+1 555 000 0000"},
    "relationship":    {"en": "Relationship",             "es": "Relación"},
    "lang_pref":       {"en": "Alert language",           "es": "Idioma de alerta"},
    "save_btn":        {"en": "Save person",              "es": "Guardar persona"},
    "no_persons":      {"en": "No monitored persons yet. Use the form above to add someone.",
                        "es": "Aún no hay personas monitoreadas. Use el formulario de arriba para agregar a alguien."},
    "send_alert":      {"en": "Send SMS alert",           "es": "Enviar alerta SMS"},
    "alert_sent":      {"en": "Alert sent to {name}.",    "es": "Alerta enviada a {name}."},
    "alert_failed":    {"en": "SMS failed (check Twilio config).", "es": "SMS fallido (verifique configuración Twilio)."},
    "sms_unavail":     {"en": "SMS not configured. Add Twilio credentials to secrets.toml.",
                        "es": "SMS no configurado. Agregue credenciales de Twilio a secrets.toml."},
    "no_phone":        {"en": "No phone number on file for {name}.", "es": "No hay número de teléfono para {name}."},
    "remove_btn":      {"en": "Remove",                   "es": "Eliminar"},
    "batch_alert_btn": {"en": "Alert all unconfirmed persons",
                        "es": "Alertar a todas las personas no confirmadas"},
    "batch_sent":      {"en": "{n} alerts sent.",         "es": "{n} alertas enviadas."},
    "progress_title":  {"en": "Evacuation progress",     "es": "Progreso de evacuación"},
    "confirmed_safe":  {"en": "{done} of {total} persons confirmed safe.",
                        "es": "{done} de {total} personas confirmadas como seguras."},
    "status_label":    {"en": "Status",                   "es": "Estado"},
    "update_status":   {"en": "Update status",            "es": "Actualizar estado"},
    "fire_proximity":  {"en": "Fire proximity",           "es": "Proximidad del incendio"},
    "checking":        {"en": "Checking...",              "es": "Verificando..."},
    "fires_within":    {"en": "{n} fires within 50 km",   "es": "{n} incendios en 50 km"},
    "no_fires":        {"en": "No fires within 50 km",    "es": "Sin incendios en 50 km"},
    "geocode_fail":    {"en": "Address not found",        "es": "Dirección no encontrada"},
    "evac_time":       {"en": "Needs {h:.1f} h to evacuate", "es": "Necesita {h:.1f} h para evacuar"},
    "last_check":      {"en": "Checked {t}",              "es": "Verificado {t}"},
    "supabase_synced": {"en": "Status synced to database.", "es": "Estado sincronizado con la base de datos."},
    "supabase_fail":   {"en": "Could not sync to database (offline mode).",
                        "es": "No se pudo sincronizar con la base de datos (modo sin conexión)."},
    "demo_banner":     {"en": "NASA FIRMS unavailable — showing demo proximity data.",
                        "es": "NASA FIRMS no disponible — mostrando datos de proximidad de demostración."},
    "address_required":{"en": "Address required.",        "es": "Se requiere dirección."},
    "name_required":   {"en": "Name required.",           "es": "Se requiere nombre."},
}


def _t(key: str, lang: str, **kwargs) -> str:
    s = _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("en", key)
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


# ── Geocoding ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _geocode(address: str) -> Optional[tuple[float, float]]:
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


# ── NASA FIRMS proximity check ────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fire_count_near(lat: float, lon: float) -> tuple[int, bool]:
    """Return (n_fires_within_50km, is_demo)."""
    lon_min = round(lon - SEARCH_DEG, 4)
    lat_min = round(lat - SEARCH_DEG, 4)
    lon_max = round(lon + SEARCH_DEG, 4)
    lat_max = round(lat + SEARCH_DEG, 4)
    bbox = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    url = f"{FIRMS_BASE}/{bbox}/1"

    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200 and len(resp.text) > 100:
            df = pd.read_csv(StringIO(resp.text))
            df.columns = [c.lower().strip() for c in df.columns]
            if "latitude" not in df.columns and "lat" in df.columns:
                df = df.rename(columns={"lat": "latitude", "lon": "longitude"})
            df["latitude"]  = pd.to_numeric(df.get("latitude",  pd.Series(dtype=float)), errors="coerce")
            df["longitude"] = pd.to_numeric(df.get("longitude", pd.Series(dtype=float)), errors="coerce")
            df = df.dropna(subset=["latitude", "longitude"])

            # Confidence normalisation
            if "confidence" in df.columns:
                def _parse_conf(v):
                    if isinstance(v, str):
                        return {"l": 30, "n": 65, "h": 85}.get(v.lower(), 50)
                    try:
                        return float(v)
                    except Exception:
                        return 50
                df["confidence"] = df["confidence"].apply(_parse_conf)
                df = df[df["confidence"] >= 50]

            # Haversine filter
            R = 6371.0
            phi1, lam1 = math.radians(lat), math.radians(lon)
            def _dist(row):
                phi2 = math.radians(row["latitude"])
                dlam = math.radians(row["longitude"] - lon)
                dphi = phi2 - phi1
                a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
                return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            df["dist_km"] = df.apply(_dist, axis=1)
            return int((df["dist_km"] <= SEARCH_RADIUS_KM).sum()), False
    except Exception:
        pass

    # Demo fallback
    return 1, True


# ── Supabase persistence ──────────────────────────────────────────────────────

def _try_load_from_supabase() -> list[dict]:
    """Attempt to load monitored persons from Supabase evacuation_status table."""
    if not _HAS_SUPABASE:
        return []
    try:
        sb = get_supabase()
        user = st.session_state.get("user")
        user_id = user.id if hasattr(user, "id") else user.get("id") if isinstance(user, dict) else None
        if not user_id:
            return []
        result = (
            sb.table("evacuation_status")
            .select("*")
            .eq("caregiver_id", user_id)
            .execute()
        )
        rows = result.data or []
        persons = []
        for r in rows:
            persons.append({
                "id":           r.get("id", _new_id()),
                "name":         r.get("resident_name", ""),
                "address":      r.get("address", ""),
                "mobility":     r.get("mobility", "mobile_adult"),
                "phone":        r.get("phone", ""),
                "relationship": r.get("relationship", "client"),
                "lang":         r.get("lang_pref", "en"),
                "status":       r.get("evac_status", "not_evacuated"),
                "added_at":     r.get("created_at", datetime.utcnow().isoformat()),
            })
        return persons
    except Exception:
        return []


def _try_upsert_supabase(person: dict, caregiver_id: str) -> bool:
    """Upsert one person's evacuation status to Supabase."""
    if not _HAS_SUPABASE:
        return False
    try:
        sb = get_supabase()
        sb.table("evacuation_status").upsert({
            "id":              person["id"],
            "caregiver_id":    caregiver_id,
            "resident_name":   person["name"],
            "address":         person["address"],
            "mobility":        person["mobility"],
            "phone":           person["phone"],
            "relationship":    person["relationship"],
            "lang_pref":       person["lang"],
            "evac_status":     person["status"],
            "updated_at":      datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def _get_caregiver_id() -> Optional[str]:
    user = st.session_state.get("user")
    if hasattr(user, "id"):
        return str(user.id)
    if isinstance(user, dict):
        return str(user.get("id", ""))
    return None


# ── ID helpers ────────────────────────────────────────────────────────────────

def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())


# ── Session state helpers ─────────────────────────────────────────────────────

def _init_persons() -> None:
    """Ensure session_state.monitored_persons exists, loading from Supabase if needed."""
    if "monitored_persons" not in st.session_state:
        loaded = _try_load_from_supabase()
        st.session_state.monitored_persons = loaded if loaded else []
    if "persons_check_cache" not in st.session_state:
        st.session_state.persons_check_cache = {}  # addr → (n_fires, is_demo, timestamp)


def _save_person(person: dict) -> None:
    """Append to session state and upsert to Supabase."""
    st.session_state.monitored_persons.append(person)
    cg_id = _get_caregiver_id()
    if cg_id:
        _try_upsert_supabase(person, cg_id)


def _update_person_status(idx: int, new_status: str, lang: str) -> None:
    persons = st.session_state.monitored_persons
    persons[idx]["status"] = new_status
    cg_id = _get_caregiver_id()
    ok = False
    if cg_id:
        ok = _try_upsert_supabase(persons[idx], cg_id)
    if ok:
        st.toast(_t("supabase_synced", lang))


def _remove_person(idx: int) -> None:
    persons = st.session_state.monitored_persons
    if 0 <= idx < len(persons):
        persons.pop(idx)


# ── Progress bar ──────────────────────────────────────────────────────────────

def _render_progress(persons: list[dict], lang: str) -> None:
    if not persons:
        return
    safe_statuses = {"evacuated", "safe_at_shelter"}
    done = sum(1 for p in persons if p.get("status") in safe_statuses)
    total = len(persons)
    pct = int(done / total * 100) if total else 0

    section_header(_t("progress_title", lang))
    st.progress(pct / 100)
    st.caption(_t("confirmed_safe", lang, done=done, total=total))


# ── Fire proximity badge ──────────────────────────────────────────────────────

def _fire_badge(address: str, lang: str) -> str:
    """Return HTML badge string with cached fire proximity info."""
    cache = st.session_state.get("persons_check_cache", {})
    cached = cache.get(address)
    now = time.time()

    if cached and now - cached["ts"] < 300:
        n, is_demo = cached["n"], cached["demo"]
    else:
        coords = _geocode(address)
        if coords is None:
            return (
                f"<span style='font-size:11px;color:#8b949e'>{_t('geocode_fail', lang)}</span>"
            )
        n, is_demo = _fire_count_near(coords[0], coords[1])
        cache[address] = {"n": n, "demo": is_demo, "ts": now}
        st.session_state.persons_check_cache = cache

    if n == 0:
        color = "#3fb950"
        label = _t("no_fires", lang)
    else:
        color = "#FF4B4B" if n >= 3 else "#d4a017"
        label = _t("fires_within", lang, n=n)

    demo_tag = " (demo)" if is_demo else ""
    return (
        f"<span style='font-size:11px;font-weight:600;color:{color};"
        f"background:{color}22;border:1px solid {color}44;border-radius:4px;"
        f"padding:2px 6px'>{label}{demo_tag}</span>"
    )


# ── Add-person form ───────────────────────────────────────────────────────────

def _render_add_form(lang: str) -> None:
    with st.expander(_t("add_person", lang), expanded=len(st.session_state.monitored_persons) == 0):
        with st.form("add_person_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input(_t("name_label", lang), key="ap_name")
                address = st.text_input(_t("address_label", lang), key="ap_address",
                                        placeholder="e.g. 123 Oak St, Chico, CA")
                mob_labels = list(MOBILITY_LABELS[lang].values())
                mob_keys   = list(MOBILITY_LABELS[lang].keys())
                mob_idx = st.selectbox(
                    _t("mobility_label", lang),
                    options=range(len(mob_keys)),
                    format_func=lambda i: mob_labels[i],
                    key="ap_mobility",
                )
            with col2:
                phone = st.text_input(
                    _t("phone_label", lang),
                    placeholder=_t("phone_ph", lang),
                    key="ap_phone",
                )
                rel_labels = RELATIONSHIP_LABELS[lang]
                rel_idx = st.selectbox(
                    _t("relationship", lang),
                    options=range(len(RELATIONSHIP_KEYS)),
                    format_func=lambda i: rel_labels[i],
                    key="ap_relationship",
                )
                lang_pref = st.selectbox(
                    _t("lang_pref", lang),
                    options=["en", "es"],
                    format_func=lambda v: "English" if v == "en" else "Español",
                    key="ap_lang_pref",
                )

            submitted = st.form_submit_button(_t("save_btn", lang), type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.warning(_t("name_required", lang))
            elif not address.strip():
                st.warning(_t("address_required", lang))
            else:
                person = {
                    "id":           _new_id(),
                    "name":         name.strip(),
                    "address":      address.strip(),
                    "mobility":     mob_keys[mob_idx],
                    "phone":        phone.strip(),
                    "relationship": RELATIONSHIP_KEYS[rel_idx],
                    "lang":         lang_pref,
                    "status":       "not_evacuated",
                    "added_at":     datetime.utcnow().isoformat(),
                }
                _save_person(person)
                st.success(f"Saved: {name.strip()}")
                st.rerun()


# ── Per-person card ───────────────────────────────────────────────────────────

def _render_person_card(idx: int, person: dict, lang: str) -> None:
    name        = person.get("name", "Unknown")
    address     = person.get("address", "")
    mobility    = person.get("mobility", "mobile_adult")
    phone       = person.get("phone", "")
    person_lang = person.get("lang", "en")
    status      = person.get("status", "not_evacuated")
    added_at    = person.get("added_at", "")

    scfg       = STATUS_CONFIG.get(status, STATUS_CONFIG["not_evacuated"])
    status_lbl = scfg[f"label_{lang}"] if f"label_{lang}" in scfg else scfg["label_en"]
    color      = scfg["color"]
    evac_h     = MOBILITY_EVAC_HOURS.get(mobility, 1.0)

    with st.container():
        st.markdown(
            f"""<div style="background:#161b22;border:1px solid #30363d;
                border-left:4px solid {color};border-radius:10px;
                padding:16px 18px;margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <span style="font-size:16px;font-weight:700;color:#e6edf3;
                       font-family:'DM Sans',system-ui,sans-serif">{name}</span>
                  &nbsp;
                  <span style="font-size:11px;color:#8b949e">{address}</span>
                </div>
                <span style="font-size:11px;font-weight:600;color:{color};
                     background:{color}22;border:1px solid {color}44;
                     border-radius:4px;padding:2px 8px">{status_lbl}</span>
              </div>
              <div style="margin-top:8px;display:flex;gap:12px;flex-wrap:wrap">
                <span style="font-size:11px;color:#8b949e">
                  {MOBILITY_LABELS[lang].get(mobility, mobility)} &middot;
                  {_t('evac_time', lang, h=evac_h)}
                </span>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # Fire badge row (lazy — shown inline after initial render)
        badge_key = f"fire_badge_{idx}"
        if st.session_state.get(f"check_fire_{idx}"):
            badge_html = _fire_badge(address, lang) if address else ""
            st.markdown(badge_html, unsafe_allow_html=True)

        col_status, col_sms, col_check, col_del = st.columns([3, 2, 2, 1])

        with col_status:
            status_opts  = EVACUATION_STATUSES
            status_lbls  = [STATUS_CONFIG[s][f"label_{lang}"] if f"label_{lang}" in STATUS_CONFIG[s]
                            else STATUS_CONFIG[s]["label_en"]
                            for s in status_opts]
            current_idx  = status_opts.index(status) if status in status_opts else 0
            new_status = st.selectbox(
                _t("status_label", lang),
                options=range(len(status_opts)),
                index=current_idx,
                format_func=lambda i: status_lbls[i],
                key=f"status_sel_{idx}",
                label_visibility="collapsed",
            )
            if st.button(_t("update_status", lang), key=f"upd_status_{idx}", use_container_width=True):
                _update_person_status(idx, status_opts[new_status], lang)
                st.rerun()

        with col_sms:
            if st.button(_t("send_alert", lang), key=f"sms_{idx}", use_container_width=True):
                if not is_sms_available():
                    st.warning(_t("sms_unavail", lang))
                elif not phone:
                    st.warning(_t("no_phone", lang, name=name))
                else:
                    ok = send_evacuation_alert(
                        phone=phone,
                        resident_name=name,
                        county=address.split(",")[-2].strip() if "," in address else address,
                        lang=person_lang,
                    )
                    if ok:
                        st.success(_t("alert_sent", lang, name=name))
                    else:
                        st.error(_t("alert_failed", lang))

        with col_check:
            if st.button(_t("fire_proximity", lang), key=f"check_{idx}", use_container_width=True):
                st.session_state[f"check_fire_{idx}"] = True
                st.rerun()

        with col_del:
            if st.button(_t("remove_btn", lang), key=f"del_{idx}", use_container_width=True):
                _remove_person(idx)
                st.rerun()


# ── Batch alert ───────────────────────────────────────────────────────────────

def _render_batch_alert(persons: list[dict], lang: str) -> None:
    unconfirmed = [
        p for p in persons
        if p.get("status") not in ("evacuated", "safe_at_shelter") and p.get("phone")
    ]
    if not unconfirmed:
        return

    section_header("Batch Actions")
    col_btn, col_info = st.columns([2, 3])
    with col_btn:
        if st.button(
            _t("batch_alert_btn", lang),
            key="batch_sms_btn",
            type="primary",
            use_container_width=True,
            disabled=not is_sms_available(),
        ):
            sent = 0
            for p in unconfirmed:
                ok = send_evacuation_alert(
                    phone=p["phone"],
                    resident_name=p["name"],
                    county=p["address"].split(",")[-2].strip() if "," in p["address"] else p["address"],
                    lang=p.get("lang", "en"),
                )
                if ok:
                    sent += 1
            st.success(_t("batch_sent", lang, n=sent))

    with col_info:
        if not is_sms_available():
            st.caption(_t("sms_unavail", lang))
        else:
            st.caption(f"{len(unconfirmed)} person(s) without confirmed evacuation.")


# ── Main entry point ──────────────────────────────────────────────────────────

def render_monitored_persons_page() -> None:
    # Language selector
    lang = st.selectbox(
        _STRINGS["lang_label"]["en"],
        options=["en", "es"],
        format_func=lambda v: "English" if v == "en" else "Español",
        key="monitored_lang",
        label_visibility="collapsed",
    )

    page_header(
        _t("page_title", lang),
        _t("page_caption", lang),
    )

    _init_persons()
    persons = st.session_state.monitored_persons

    # ── Progress summary ──────────────────────────────────────────────────────
    if persons:
        _render_progress(persons, lang)
        st.markdown("---")

    # ── Add-person form ───────────────────────────────────────────────────────
    _render_add_form(lang)

    # ── Person cards ──────────────────────────────────────────────────────────
    if not persons:
        fallback_card(_t("no_persons", lang))
        return

    st.markdown("---")
    section_header(
        f"{len(persons)} monitored person{'s' if len(persons) != 1 else ''}"
        if lang == "en"
        else f"{len(persons)} persona{'s' if len(persons) != 1 else ''} monitoreada{'s' if len(persons) != 1 else ''}"
    )

    for i, person in enumerate(persons):
        _render_person_card(i, person, lang)

    # ── Batch alert panel ─────────────────────────────────────────────────────
    st.markdown("---")
    _render_batch_alert(persons, lang)

    data_source_badge("NASA FIRMS VIIRS NRT · Supabase (optional)")
