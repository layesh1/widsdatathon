"""
address_utils.py
Address autocomplete (Photon/Komoot OSM API — free, no key required)
+ saved locations manager for the WiDS Wildfire Caregiver Alert System.
"""
import streamlit as st
import requests
from typing import Optional


# ---------------------------------------------------------------------------
# Photon autocomplete API  (OpenStreetMap data, Komoot-hosted, free, no key)
# ---------------------------------------------------------------------------
_PHOTON_URL = "https://photon.komoot.io/api/"


@st.cache_data(ttl=60, show_spinner=False)
def get_address_suggestions(query: str, limit: int = 6) -> list[dict]:
    """
    Fetch address suggestions from the Photon geocoding API.
    Returns a list of dicts with keys: display, address, lat, lon
    Filtered to US bounding box.
    """
    if not query or len(query.strip()) < 3:
        return []
    try:
        r = requests.get(
            _PHOTON_URL,
            params={
                "q": query,
                "limit": limit,
                "lang": "en",
                # US bounding box: SW corner to NE corner
                "bbox": "-125.0,24.0,-65.0,50.0",
                "osm_tag": "!natural",          # filter out pure nature features
            },
            timeout=4,
        )
        if r.status_code != 200:
            return []
        features = r.json().get("features", [])
        results = []
        for f in features:
            p = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [None, None])
            # Build a human-readable label
            parts = [p.get("name", ""), p.get("street", ""),
                     p.get("housenumber", ""), p.get("city", ""),
                     p.get("state", ""), p.get("country", "")]
            parts = [x for x in parts if x]
            if not parts:
                continue
            display = ", ".join(dict.fromkeys(parts))  # dedup preserving order
            results.append({
                "display": display,
                "address": display,
                "lat": float(coords[1]) if coords[1] else None,
                "lon": float(coords[0]) if coords[0] else None,
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Composite address input with live autocomplete
# ---------------------------------------------------------------------------

def render_address_input(
    label: str = "Address or city",
    key: str = "address_input",
    placeholder: str = "e.g. 7404 Alamance Dr, Charlotte, NC",
    help_text: str = "Type 3+ characters to see address suggestions",
) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Renders a text input with live address suggestions.
    Returns (address_str, lat, lon) — lat/lon are None until user picks a suggestion
    or if geocoding fails.

    Pattern:
    1. User types in text box → on_change callback fetches suggestions
    2. Suggestions appear in a selectbox below
    3. Selecting a suggestion stores coords in session_state
    """
    sug_key   = f"{key}_suggestions"
    chosen_key = f"{key}_chosen"

    # Init session_state
    st.session_state.setdefault(sug_key, [])
    st.session_state.setdefault(chosen_key, None)

    def _on_change():
        q = st.session_state.get(key, "")
        if len(q.strip()) >= 3:
            st.session_state[sug_key] = get_address_suggestions(q)
        else:
            st.session_state[sug_key] = []
        st.session_state[chosen_key] = None  # reset on new input

    st.text_input(
        label,
        key=key,
        placeholder=placeholder,
        help=help_text,
        on_change=_on_change,
        autocomplete="street-address",
    )

    suggestions = st.session_state[sug_key]
    address_str = st.session_state.get(key, "")
    lat, lon = None, None

    if suggestions:
        options = ["-- Select a suggestion --"] + [s["display"] for s in suggestions]
        choice = st.selectbox(
            "Address suggestions",
            options,
            key=f"{key}_selectbox",
            label_visibility="collapsed",
        )
        if choice and choice != "-- Select a suggestion --":
            match = next((s for s in suggestions if s["display"] == choice), None)
            if match:
                address_str = match["address"]
                lat = match["lat"]
                lon = match["lon"]
                st.session_state[chosen_key] = match
                # Push chosen address back into the text input
                st.session_state[key] = address_str
    elif address_str and len(address_str) >= 3 and not suggestions:
        st.caption("No suggestions found — try adding city and state.")

    return address_str, lat, lon


# ---------------------------------------------------------------------------
# Saved locations manager
# ---------------------------------------------------------------------------

def init_saved_locations():
    """Initialize saved_locations in session_state if not present."""
    st.session_state.setdefault("saved_locations", [])


def render_saved_locations_picker(
    label: str = "Or choose a saved location",
    key: str = "saved_loc_picker",
) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Renders a dropdown of saved locations. Returns (address, lat, lon) or (None, None, None).
    """
    init_saved_locations()
    locs = st.session_state.saved_locations
    if not locs:
        return None, None, None

    options = ["-- Use a saved location --"] + [f"📍 {loc['name']}" for loc in locs]
    choice = st.selectbox(label, options, key=key)
    if choice and choice != "-- Use a saved location --":
        name = choice.replace("📍 ", "")
        match = next((l for l in locs if l["name"] == name), None)
        if match:
            return match["address"], match.get("lat"), match.get("lon")
    return None, None, None


def render_save_location_button(
    address: str,
    lat: Optional[float],
    lon: Optional[float],
    key: str = "save_loc",
):
    """
    Renders a 'Save this location' button. If clicked, prompts for a nickname.
    """
    init_saved_locations()
    if not address:
        return

    existing_addresses = [l["address"] for l in st.session_state.saved_locations]
    if address in existing_addresses:
        st.caption("✅ This location is already saved.")
        return

    with st.expander("💾 Save this location for future alerts", expanded=False):
        col_name, col_btn = st.columns([3, 1])
        with col_name:
            nick = st.text_input(
                "Location nickname (e.g. Mom's House)",
                key=f"{key}_name",
                placeholder="Mom's House, Work, Cabin…",
            )
        with col_btn:
            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            if st.button("Save", key=f"{key}_btn", type="primary",
                         disabled=not nick, use_container_width=True):
                st.session_state.saved_locations.append({
                    "name": nick,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                })
                st.success(f"Saved **{nick}** to your locations.")
                st.rerun()


def render_saved_locations_manager(key_prefix: str = "loc_mgr"):
    """
    Full saved-locations management panel: list, add, delete.
    """
    init_saved_locations()
    locs = st.session_state.saved_locations

    if not locs:
        st.caption("No saved locations yet. Search for an address above and save it.")
        return

    st.markdown("**Your saved locations:**")
    for i, loc in enumerate(locs):
        col_icon, col_name, col_del = st.columns([1, 8, 2])
        col_icon.markdown("📍")
        col_name.markdown(f"**{loc['name']}** — {loc['address']}")
        if col_del.button("✕", key=f"{key_prefix}_del_{i}", help="Remove"):
            st.session_state.saved_locations.pop(i)
            st.rerun()
