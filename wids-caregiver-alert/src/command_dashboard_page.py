"""
command_dashboard_page.py
Emergency Worker dashboard — dispatcher and field commander view.
Separated from wildfire_alert_dashboard.py for clarity.

What this page does:
  - Live fire map (FIRMS) centered on US, with vulnerable county overlay
  - Vulnerable address tracker: which addresses in active fire zones are NOT confirmed evacuated
  - Fire department resource lookup (USFA) filtered to counties near active fires
  - Real WiDS historical benchmarks for situational awareness
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.figure_factory as ff
from pathlib import Path
import requests

# ── Plotly version shim: 5.x uses Scattermapbox/mapbox; 6.x uses Scattermap/map ──
_HAS_NEW_MAP = hasattr(go, "Scattermap")
_MAP_KEY = "map" if _HAS_NEW_MAP else "mapbox"


def _scatter_map(**kw):
    """Return Scattermap (Plotly 6.x / 5.20+) or Scattermapbox (5.x)."""
    return go.Scattermap(**kw) if _HAS_NEW_MAP else go.Scattermapbox(**kw)


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_svi_centroids():
    """Load SVI + Census county centroids, return merged df."""
    cen_paths = [
        Path("data/CenPop2020_Mean_CO.txt"),
        Path("CenPop2020_Mean_CO.txt"),
        Path("../data/CenPop2020_Mean_CO.txt"),
    ]
    svi_paths = [
        Path("SVI_2022_US_county.csv"),
        Path("01_raw_data/external/SVI_2022_US_county.csv"),
        Path("../01_raw_data/external/SVI_2022_US_county.csv"),
    ]

    cen_df = None
    for p in cen_paths:
        if p.exists():
            try:
                cen_df = pd.read_csv(p)
                cen_df["FIPS"] = (cen_df["STATEFP"].astype(str).str.zfill(2) +
                                   cen_df["COUNTYFP"].astype(str).str.zfill(3))
                break
            except Exception:
                pass

    svi_df = None
    for p in svi_paths:
        if p.exists():
            try:
                svi_df = pd.read_csv(p, low_memory=False,
                                      usecols=["FIPS", "RPL_THEMES", "COUNTY", "ST_ABBR",
                                               "E_AGE65", "E_DISABL", "E_NOVEH", "E_POV150"])
                svi_df["FIPS"] = svi_df["FIPS"].astype(str).str.zfill(5)
                break
            except Exception:
                pass

    if cen_df is not None and svi_df is not None:
        merged = svi_df.merge(cen_df[["FIPS", "LATITUDE", "LONGITUDE"]], on="FIPS", how="left")
        return merged.dropna(subset=["LATITUDE", "LONGITUDE"])
    return None


def load_usfa():
    for p in [Path("usfa-registry-national.csv"),
               Path("src/usfa-registry-national.csv"),
               Path("01_raw_data/usfa-registry-national.csv"),
               Path("../01_raw_data/usfa-registry-national.csv")]:
        if p.exists():
            try:
                return pd.read_csv(p, low_memory=False)
            except Exception:
                pass
    # Try downloading from USFA API as last resort
    try:
        import requests
        from io import StringIO
        r = requests.get(
            "https://apps.usfa.fema.gov/registry/rest/api/v1/firedepartments/download",
            timeout=15,
            headers={"Accept": "text/csv"},
        )
        if r.status_code == 200 and b"," in r.content[:100]:
            df = pd.read_csv(StringIO(r.text), low_memory=False)
            # Cache locally for next time
            try:
                df.to_csv(Path("usfa-registry-national.csv"), index=False)
            except Exception:
                pass
            return df
    except Exception:
        pass
    return None


@st.cache_data(ttl=900, show_spinner=False)
def load_geo_events():
    """Load WiDS wildfire geo events for hexbin (lat/lng columns)."""
    paths = [
        Path("01_raw_data/geo_events_geoevent.csv"),
        Path("../01_raw_data/geo_events_geoevent.csv"),
        Path("geo_events_geoevent.csv"),
    ]
    for p in paths:
        if p.exists():
            try:
                df = pd.read_csv(p, low_memory=False,
                                  usecols=["lat", "lng", "geo_event_type"])
                df = df[df["geo_event_type"] == "wildfire"].copy()
                df = df.rename(columns={"lng": "lon"})
                df = df[df["lat"].between(24, 50) & df["lon"].between(-125, -65)]
                return df[["lat", "lon"]].dropna().reset_index(drop=True)
            except Exception:
                pass
    return pd.DataFrame(columns=["lat", "lon"])


# Approximate state bounding boxes [lat_min, lat_max, lon_min, lon_max]
_STATE_BOUNDS = {
    "CA": (32.5, 42.0, -124.4, -114.1), "OR": (42.0, 46.3, -124.6, -116.5),
    "WA": (45.5, 49.0, -124.8, -117.0), "CO": (37.0, 41.0, -109.1, -102.0),
    "NM": (31.3, 37.0, -109.1, -103.0), "AZ": (31.3, 37.0, -114.8, -109.1),
    "TX": (25.8, 36.5, -106.7, -93.5),  "MT": (44.4, 49.0, -116.1, -104.0),
    "ID": (42.0, 49.0, -117.2, -111.0), "NV": (35.0, 42.0, -120.0, -114.0),
    "FL": (24.5, 31.0, -87.7, -80.0),   "GA": (30.4, 35.0, -85.6, -80.8),
    "NC": (33.8, 36.6, -84.3, -75.5),   "SC": (32.0, 35.2, -83.4, -78.5),
    "LA": (28.9, 33.0, -94.1, -88.8),
}
_STATE_CENTERS = {
    "CA": (37.5, -119.5, 5), "OR": (44.0, -120.5, 6), "WA": (47.5, -120.5, 6),
    "CO": (39.0, -105.5, 6), "NM": (34.5, -106.0, 6), "AZ": (34.0, -111.7, 6),
    "TX": (31.0, -99.0, 5),  "MT": (47.0, -110.0, 6), "ID": (44.0, -114.0, 6),
    "NV": (39.0, -117.0, 6), "FL": (28.0, -83.5, 6),  "GA": (32.5, -83.5, 6),
    "NC": (35.5, -79.5, 6),  "SC": (33.8, -81.0, 6),  "LA": (31.0, -91.5, 6),
}


@st.cache_data(ttl=900, show_spinner=False)
def load_red_flag_warnings():
    """Fetch active Red Flag Warnings from NOAA NWS API.

    Returns a DataFrame with columns:
        zone, headline, onset, expires, lat, lon, description
    Only features with valid polygon/multipolygon geometry are included;
    features with null geometry are skipped.
    """
    url = "https://api.weather.gov/alerts/active?event=Red%20Flag%20Warning"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "WildFireAlertApp/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame(columns=["zone", "headline", "onset", "expires", "lat", "lon", "description"])

    rows = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry")
        props = feature.get("properties", {})

        lat, lon = None, None
        if geometry is not None:
            geo_type = geometry.get("type", "")
            coords = geometry.get("coordinates")
            try:
                if geo_type == "Polygon" and coords:
                    # coords[0] is the outer ring: list of [lon, lat]
                    ring = coords[0]
                    lons = [pt[0] for pt in ring]
                    lats = [pt[1] for pt in ring]
                    lon = sum(lons) / len(lons)
                    lat = sum(lats) / len(lats)
                elif geo_type == "MultiPolygon" and coords:
                    # Flatten all rings across all polygons
                    all_lons, all_lats = [], []
                    for polygon in coords:
                        for ring in polygon:
                            all_lons.extend(pt[0] for pt in ring)
                            all_lats.extend(pt[1] for pt in ring)
                    if all_lons:
                        lon = sum(all_lons) / len(all_lons)
                        lat = sum(all_lats) / len(all_lats)
            except Exception:
                pass

        if lat is None or lon is None:
            continue  # skip features with no usable geometry

        rows.append({
            "zone":        props.get("areaDesc", "Unknown zone"),
            "headline":    props.get("headline", ""),
            "onset":       props.get("onset", ""),
            "expires":     props.get("expires", ""),
            "lat":         lat,
            "lon":         lon,
            "description": props.get("description", ""),
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=600, show_spinner=False)
def load_nifc_active_incidents():
    """Fetch active wildfire incidents from NIFC GeoJSON endpoint.

    Returns a DataFrame with columns:
        name, state, acres, containment_pct, lat, lon, fire_id
    """
    url = (
        "https://opendata.arcgis.com/datasets/"
        "5da472c6d27b4b67970acc7b5044c862_0.geojson"
    )
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "WildFireAlertApp/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame(columns=["name", "state", "acres", "containment_pct", "lat", "lon", "fire_id"])

    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")

        lat, lon = None, None
        if coords and len(coords) >= 2:
            lon, lat = coords[0], coords[1]

        # containment may be stored as a datetime string (ContainmentDateTime) in some versions
        # or as a percentage — handle both gracefully
        containment_raw = props.get("PercentContained") or props.get("ContainmentDateTime")
        try:
            containment_pct = float(containment_raw) if containment_raw is not None else None
            # If value is suspiciously large it's probably a timestamp epoch — ignore it
            if containment_pct is not None and containment_pct > 100:
                containment_pct = None
        except (TypeError, ValueError):
            containment_pct = None

        rows.append({
            "name":            props.get("IncidentName") or props.get("Name", "Unknown"),
            "state":           props.get("POOState") or props.get("State", ""),
            "acres":           props.get("DiscoveryAcres") or props.get("GISAcres") or 0,
            "containment_pct": containment_pct,
            "lat":             lat,
            "lon":             lon,
            "fire_id":         props.get("UniqueFireIdentifier") or props.get("GlobalID", ""),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["acres"] = pd.to_numeric(df["acres"], errors="coerce").fillna(0)
    df["containment_pct"] = pd.to_numeric(df["containment_pct"], errors="coerce")
    # Keep only CONUS bounding box + filter rows missing coordinates
    df = df.dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(15, 72) & df["lon"].between(-180, -50)]
    return df.reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def load_shelter_capacity():
    """Fetch open shelters from FEMA National Shelter System API.

    Returns a DataFrame with columns:
        name, county, state, lat, lon, capacity, occupancy, pct_full
    """
    url = (
        "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/FeatureServer/0/query"
        "?where=1%3D1"
        "&outFields=SHELTER_NAME,COUNTY,STATE,LATITUDE,LONGITUDE,CAPACITY,CURRENT_OCCUPANCY"
        "&f=json"
    )
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "WildFireAlertApp/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame(columns=["name", "county", "state", "lat", "lon",
                                     "capacity", "occupancy", "pct_full"])

    rows = []
    for feature in data.get("features", []):
        attrs = feature.get("attributes", {})
        try:
            cap  = float(attrs.get("CAPACITY")  or 0)
            occ  = float(attrs.get("CURRENT_OCCUPANCY") or 0)
            pct  = round(occ / cap * 100, 1) if cap > 0 else 0.0
        except (TypeError, ValueError):
            cap, occ, pct = 0.0, 0.0, 0.0
        try:
            lat = float(attrs.get("LATITUDE")  or 0) or None
            lon = float(attrs.get("LONGITUDE") or 0) or None
        except (TypeError, ValueError):
            lat, lon = None, None

        rows.append({
            "name":      attrs.get("SHELTER_NAME", "Unknown"),
            "county":    attrs.get("COUNTY", ""),
            "state":     attrs.get("STATE", ""),
            "lat":       lat,
            "lon":       lon,
            "capacity":  cap,
            "occupancy": occ,
            "pct_full":  pct,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(15, 72) & df["lon"].between(-180, -50)]
    return df.reset_index(drop=True)


def _build_hex_data(fire_data, state_filter="All"):
    """Merge historical WiDS geo_events + live NASA FIRMS data for hexbin."""
    frames = []

    # Historical WiDS wildfire events (62k+ points, cached)
    geo = load_geo_events()
    if geo is not None and len(geo) > 0:
        frames.append(geo[["lat", "lon"]])

    # Live NASA FIRMS / WiDS active data passed in from dashboard
    if fire_data is not None and len(fire_data) > 0:
        live = fire_data.copy()
        lat_col = next((c for c in ["lat", "latitude"] if c in live.columns), None)
        lon_col = next((c for c in ["lon", "lng", "longitude"] if c in live.columns), None)
        if lat_col and lon_col:
            sub = live[[lat_col, lon_col]].rename(columns={lat_col: "lat", lon_col: "lon"})
            sub = sub[sub["lat"].between(24, 50) & sub["lon"].between(-125, -65)]
            frames.append(sub)

    if not frames:
        return pd.DataFrame(columns=["lat", "lon"])

    combined = pd.concat(frames, ignore_index=True).dropna()

    if state_filter != "All" and state_filter in _STATE_BOUNDS:
        lat_min, lat_max, lon_min, lon_max = _STATE_BOUNDS[state_filter]
        combined = combined[
            combined["lat"].between(lat_min, lat_max) &
            combined["lon"].between(lon_min, lon_max)
        ]

    return combined.reset_index(drop=True)


def load_geojson_layer(fname):
    for p in [Path(fname), Path(f"wids-caregiver-alert/src/{fname}"),
               Path(f"../{fname}"), Path(f"src/{fname}")]:
        if p.exists():
            return str(p)
    return None


# ── Evacuee status tracker (session state) ───────────────────────────────────

def init_evacuee_tracker(dispatcher_username: str = "dispatcher"):
    """Load evacuee list from Supabase, fall back to session state demo data."""
    try:
        from auth_supabase import get_supabase
        sb = get_supabase()
        res = sb.table("evacuation_status").select("*").eq("reporter_username", dispatcher_username).order("updated_at", desc=True).execute()
        if res.data:
            rows = []
            for r in res.data:
                rows.append({
                    "name":     r.get("person_name", ""),
                    "address":  r.get("note", ""),
                    "mobility": r.get("mobility", "Other"),
                    "phone":    r.get("phone", ""),
                    "status":   "Evacuated ✅" if r.get("status") == "Evacuated" else "Unconfirmed",
                    "db_id":    r.get("id"),
                })
            st.session_state.evacuee_list = pd.DataFrame(rows)
            return
    except Exception:
        pass
    # Fallback demo data
    if "evacuee_list" not in st.session_state:
        st.session_state.evacuee_list = pd.DataFrame([
            {"address": "142 Oak St, Paradise, CA",         "name": "Martha Chen",      "mobility": "Elderly",    "phone": "530-555-0101", "status": "Unconfirmed", "db_id": None},
            {"address": "77 Pine Ridge Rd, Magalia, CA",    "name": "Robert Okafor",    "mobility": "Disabled",   "phone": "530-555-0144", "status": "Unconfirmed", "db_id": None},
            {"address": "89 Skyway, Paradise, CA",          "name": "Delores Perez",    "mobility": "Elderly",    "phone": "530-555-0199", "status": "Unconfirmed", "db_id": None},
            {"address": "312 Pentz Rd, Paradise, CA",       "name": "James Whitmore",   "mobility": "No vehicle", "phone": "530-555-0177", "status": "Unconfirmed", "db_id": None},
            {"address": "55 Bille Rd, Paradise, CA",        "name": "Yuki Tanaka",      "mobility": "Disabled",   "phone": "530-555-0155", "status": "Evacuated ✅", "db_id": None},
            {"address": "201 Clark Rd, Chico, CA",          "name": "Gloria Martinez",  "mobility": "Elderly",    "phone": "530-555-0188", "status": "Unconfirmed", "db_id": None},
        ])


# ── Main render ───────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_wids_top_fires():
    """Load top 10 largest fires from WiDS historical CSV with SVI and delay info."""
    paths = [
        Path("fire_events_with_svi_and_delays.csv"),
        Path("01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
        Path("../01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
    ]
    for p in paths:
        if p.exists():
            try:
                cols = ["name", "county_name", "state", "max_acres", "svi_score",
                        "hours_to_order", "evacuation_occurred", "fire_start"]
                df = pd.read_csv(p, usecols=cols, low_memory=False)
                df = df.dropna(subset=["max_acres"])
                df["max_acres"] = pd.to_numeric(df["max_acres"], errors="coerce")
                df["svi_score"] = pd.to_numeric(df.get("svi_score"), errors="coerce")
                df["hours_to_order"] = pd.to_numeric(df.get("hours_to_order"), errors="coerce")
                top = df.nlargest(10, "max_acres").copy()
                return top
            except Exception:
                pass
    return None


def _render_largest_incidents():
    """Show top-10 largest WiDS fire incidents with SVI and alert gap columns."""
    df = _load_wids_top_fires()
    if df is None or df.empty:
        st.info(
            "No incident data available. Ensure "
            "`01_raw_data/processed/fire_events_with_svi_and_delays.csv` is present, "
            "or connect to a live data feed."
        )
        return

    display = pd.DataFrame({
        "Incident":   df["name"].fillna("Unnamed"),
        "Location":   df.apply(
            lambda r: (
                f"{r['county_name']}, {r['state']}"
                if pd.notna(r.get("county_name")) and pd.notna(r.get("state"))
                else str(r.get("state", "—") or "—")
            ),
            axis=1,
        ),
        "Acres":      df["max_acres"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "—"),
        "SVI":        df["svi_score"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "—"),
        "Alert Gap":  df["hours_to_order"].apply(
            lambda v: f"{v:.1f} h" if pd.notna(v) else "No evac action"
        ),
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Acres":      st.column_config.TextColumn("Acres burned"),
            "SVI":        st.column_config.TextColumn("Social Vulnerability (0–1)"),
            "Alert Gap":  st.column_config.TextColumn("Time to evac order"),
        },
    )
    st.caption(
        "Top 10 fires by max acreage  ·  WiDS 2021–2025  ·  "
        "Alert Gap = hours from fire start to first evacuation order"
    )


def render_command_dashboard(fire_data, fire_source, fire_label):
    st.title("Command Dashboard")
    st.caption(f"Emergency Worker View  ·  {fire_label}  ·  WiDS 2021–2025 Historical Benchmarks")

    init_evacuee_tracker(st.session_state.get("username", "dispatcher"))

    # ── Historical benchmarks (always real) ──────────────────────────────────
    st.subheader("Historical Response Benchmarks  *(WiDS 2021–2025)*")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Median Time to Evac Order",  "1.1h",
              help="653 fires with confirmed evac actions, 2021–2025")
    h2.metric("Worst-Case (90th %ile)",     "100h",
              help="1 in 10 fires takes over 100 hours (4+ days) to get an official order (P90 = 6,018 min)")
    h3.metric("Fires Exceeding 6h",         "20%",    delta="critical window", delta_color="inverse")
    h4.metric("Vuln County Growth Rate",    "11.7 ac/hr", delta="+17% vs non-vuln", delta_color="inverse")

    # ── Fire Perimeter Data Quality ───────────────────────────────────────────
    with st.expander("Fire Perimeter Data Quality (6,207 records)", expanded=False):
        dq1, dq2, dq3, dq4 = st.columns(4)
        dq1.metric("Total Perimeter Records", "6,207",
                   help="GIS fire perimeter records in WiDS dataset")
        dq2.metric("Approved", "4,139",
                   delta="66.7% approved", delta_color="normal",
                   help="Perimeter records with approved status")
        dq3.metric("Rejected", "883",
                   delta="14.2% rejected", delta_color="inverse",
                   help="Perimeter records rejected from official data")
        dq4.metric("Pending Review", "1,185",
                   delta="19.1% pending", delta_color="off",
                   help="Perimeter records still awaiting approval")
        st.caption(
            "33.5% of fire perimeter records are not yet approved (rejected + pending). "
            "Analyses using perimeter shape data should account for this data quality limitation. "
            "Source: fire_perimeters_gis_fireperimeter table, WiDS 2025."
        )

    st.divider()

    # ── Largest Recent Incidents (WiDS historical data) ───────────────────────
    st.subheader("Largest Active Incidents")
    st.caption("Top fires by acreage — WiDS 2021–2025 historical record (active incidents require live feed)")
    _render_largest_incidents()

    st.divider()

    tab_map, tab_nifc, tab_evacuees, tab_resources = st.tabs([
        "Fire Map", "Live NIFC Incidents", "Evacuee Status Tracker", "Fire Dept Resources"
    ])

    # ════════ TAB 1: FIRE MAP ═══════════════════════════════════════════════
    with tab_map:
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 2])
        with col_ctrl1:
            state_filter = st.selectbox("Filter by State",
                ["All", "CA", "OR", "WA", "CO", "NM", "AZ", "TX", "MT", "ID", "NV",
                 "FL", "GA", "NC", "SC", "LA"])
            st.session_state["cmd_state_filter"] = state_filter
        with col_ctrl2:
            svi_threshold = st.slider("Min SVI to highlight", 0.5, 1.0, 0.75, 0.05)
        with col_ctrl3:
            st.caption(
                "Hexagon density map — each cell aggregates nearby fire events. "
                "Blue circles = high-SVI counties.  \n"
                "Full GeoJSON overlays (perimeters, evac zones): see **Evacuation Map** page."
            )

        # Build combined fire dataset: WiDS historical + live NASA FIRMS
        hex_df = _build_hex_data(fire_data, state_filter)
        svi_df = load_svi_centroids()

        # Map center / zoom by state filter (needed below)
        clat, clon, czoom = _STATE_CENTERS.get(state_filter, (39.5, -98.5, 3))

        if len(hex_df) >= 5:
            try:
                hex_fig = ff.create_hexbin_mapbox(
                    data_frame=hex_df,
                    lat="lat",
                    lon="lon",
                    nx_hexagon=40,
                    opacity=0.72,
                    labels={"color": "Fire Events"},
                    show_original_data=False,
                    color_continuous_scale="YlOrRd",
                    min_count=1,
                )
            except Exception:
                # Plotly 6.x removed create_hexbin_mapbox internals — fall to density scatter
                hex_fig = go.Figure(_scatter_map(
                    lat=hex_df["lat"].tolist(),
                    lon=hex_df["lon"].tolist(),
                    mode="markers",
                    marker=dict(size=4, color="#FF4400", opacity=0.25),
                    name="Fire Events",
                    hoverinfo="none",
                ))
        else:
            # Sparse / no data — plain scatter fallback
            hex_fig = go.Figure(_scatter_map(
                lat=hex_df["lat"].tolist() if len(hex_df) else [39.5],
                lon=hex_df["lon"].tolist() if len(hex_df) else [-98.5],
                mode="markers",
                marker=dict(size=6, color="#FF2200", opacity=0.75),
                name="Fire Hotspots",
            ))

        # Overlay vulnerable county centroids
        if svi_df is not None:
            fsvi = svi_df[svi_df["RPL_THEMES"] >= svi_threshold].copy()
            if state_filter != "All" and "ST_ABBR" in fsvi.columns:
                fsvi = fsvi[fsvi["ST_ABBR"] == state_filter]
            if len(fsvi) > 0:
                hex_fig.add_trace(_scatter_map(
                    lat=fsvi["LATITUDE"].tolist(),
                    lon=fsvi["LONGITUDE"].tolist(),
                    mode="markers",
                    marker=dict(size=9, color="#4a90d9", opacity=0.5),
                    name=f"SVI \u2265 {svi_threshold}",
                    text=[
                        f"{r.get('COUNTY', '')}, {r.get('ST_ABBR', '')} \u2014 SVI {r['RPL_THEMES']:.2f}"
                        for _, r in fsvi.iterrows()
                    ],
                    hoverinfo="text",
                ))

        hex_fig.update_layout(
            **{_MAP_KEY: dict(
                style="carto-darkmatter",
                center=dict(lat=clat, lon=clon),
                zoom=czoom,
            )},
            height=560,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#0f0f1a",
            legend=dict(
                bgcolor="rgba(20,20,30,0.85)",
                bordercolor="#444",
                borderwidth=1,
                font=dict(color="#eee"),
                x=0, y=1,
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Fire<br>Events", font=dict(color="#eee")),
                tickfont=dict(color="#eee"),
                thickness=14,
            ),
        )

        # ── Red Flag Warning overlay ──────────────────────────────────────────
        red_flag = load_red_flag_warnings()
        if not red_flag.empty:
            # Filter to state if selected
            if state_filter != "All" and state_filter in _STATE_BOUNDS:
                lat_min, lat_max, lon_min, lon_max = _STATE_BOUNDS[state_filter]
                rf_filtered = red_flag[
                    red_flag["lat"].between(lat_min, lat_max) &
                    red_flag["lon"].between(lon_min, lon_max)
                ]
            else:
                rf_filtered = red_flag

            if not rf_filtered.empty:
                hex_fig.add_trace(_scatter_map(
                    lat=rf_filtered["lat"].tolist(),
                    lon=rf_filtered["lon"].tolist(),
                    mode="markers",
                    marker=dict(
                        symbol="triangle-up",
                        size=14,
                        color="#FF4B4B",
                        opacity=0.9,
                    ),
                    name="Red Flag Warnings",
                    text=[
                        f"<b>{row['zone']}</b><br>{row['headline']}<br>Expires: {row['expires']}"
                        for _, row in rf_filtered.iterrows()
                    ],
                    hoverinfo="text",
                ))

        st.plotly_chart(hex_fig, use_container_width=True)
        st.caption(
            f"{len(hex_df):,} fire events  ·  {fire_label} + WiDS 2021–2025 historical data  ·  "
            f"Blue circles = SVI \u2265 {svi_threshold} counties  ·  "
            f"Red triangles = active Red Flag Warnings"
        )

        # Red Flag Warning summary
        if not red_flag.empty:
            rf_count = len(red_flag)
            st.metric("Active Red Flag Warnings", rf_count,
                      help="Source: NOAA NWS — refreshed every 15 minutes")
            with st.expander("Active Red Flag Warnings", expanded=False):
                display_rf = red_flag[["zone", "headline", "onset", "expires"]].copy()
                display_rf.columns = ["Zone / Area", "Headline", "Onset", "Expires"]
                st.dataframe(display_rf, use_container_width=True, hide_index=True)
                st.caption("Source: NOAA National Weather Service — api.weather.gov")
        else:
            st.caption("No active Red Flag Warnings at this time.")

    # ════════ TAB 2: LIVE NIFC INCIDENTS ════════════════════════════════════
    with tab_nifc:
        st.subheader("Live NIFC Active Fire Incidents")
        st.caption("Source: NIFC National Interagency Fire Center — updated every 10 minutes")

        nifc_df = load_nifc_active_incidents()

        if nifc_df.empty:
            st.info(
                "No NIFC incident data available right now. "
                "The NIFC GeoJSON endpoint may be temporarily unavailable — try again shortly."
            )
        else:
            # KPI metrics
            n1, n2, n3 = st.columns(3)
            total_incidents = len(nifc_df)
            total_acres = nifc_df["acres"].sum()
            valid_cont = nifc_df["containment_pct"].dropna()
            avg_cont = valid_cont.mean() if not valid_cont.empty else None

            n1.metric("Active Incidents", f"{total_incidents:,}",
                      help="Total currently active NIFC-tracked fires")
            n2.metric("Total Acres",      f"{total_acres:,.0f}",
                      help="Sum of reported discovery/GIS acres across all incidents")
            n3.metric("Avg Containment",
                      f"{avg_cont:.0f}%" if avg_cont is not None else "—",
                      help="Average containment % for incidents with reported values")

            st.divider()

            # Scatter map of NIFC incidents
            nifc_map_df = nifc_df.dropna(subset=["lat", "lon"])
            if not nifc_map_df.empty:
                nifc_fig = go.Figure(_scatter_map(
                    lat=nifc_map_df["lat"].tolist(),
                    lon=nifc_map_df["lon"].tolist(),
                    mode="markers",
                    marker=dict(
                        size=10,
                        color="#FF8C00",
                        opacity=0.85,
                    ),
                    name="NIFC Incidents",
                    text=[
                        f"<b>{row['name']}</b><br>State: {row['state']}<br>"
                        f"Acres: {row['acres']:,.0f}<br>"
                        f"Containment: {row['containment_pct']:.0f}%"
                        if pd.notna(row['containment_pct'])
                        else f"<b>{row['name']}</b><br>State: {row['state']}<br>Acres: {row['acres']:,.0f}"
                        for _, row in nifc_map_df.iterrows()
                    ],
                    hoverinfo="text",
                ))
                nifc_fig.update_layout(
                    **{_MAP_KEY: dict(
                        style="carto-darkmatter",
                        center=dict(lat=39.5, lon=-98.5),
                        zoom=3,
                    )},
                    height=460,
                    margin=dict(l=0, r=0, t=0, b=0),
                    paper_bgcolor="#0f0f1a",
                    legend=dict(
                        bgcolor="rgba(20,20,30,0.85)",
                        bordercolor="#444",
                        borderwidth=1,
                        font=dict(color="#eee"),
                        x=0, y=1,
                    ),
                )
                st.plotly_chart(nifc_fig, use_container_width=True)

            # Sortable incidents table
            st.subheader("All Active Incidents")
            table_df = nifc_df[["name", "state", "acres", "containment_pct", "fire_id"]].copy()
            table_df.columns = ["Incident Name", "State", "Acres", "Containment %", "Fire ID"]
            table_df["Acres"] = table_df["Acres"].apply(
                lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
            )
            table_df["Containment %"] = table_df["Containment %"].apply(
                lambda v: f"{v:.0f}%" if pd.notna(v) else "—"
            )
            st.dataframe(table_df, use_container_width=True, hide_index=True)

        st.caption("Source: NIFC National Interagency Fire Center — updated every 10 minutes")

    # ════════ TAB 4: EVACUEE STATUS TRACKER ══════════════════════════════════
    with tab_evacuees:
        st.subheader("Vulnerable Resident Evacuation Status")
        st.markdown(
            "Track whether high-risk individuals in active evacuation zones have been "
            "confirmed as evacuated. Update status as field teams make contact."
        )

        df = st.session_state.evacuee_list.copy()

        # Summary KPIs
        total     = len(df)
        evacuated = (df["status"] == "Evacuated ✅").sum()
        unconf    = total - evacuated

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Tracked Residents", total)
        k2.metric("Confirmed Evacuated",      evacuated, delta=f"{evacuated/total*100:.0f}%")
        k3.metric("Unconfirmed",           unconf,
                  delta="Needs contact" if unconf > 0 else "All confirmed",
                  delta_color="inverse" if unconf > 0 else "normal")

        st.divider()

        # ── Shelter Capacity ─────────────────────────────────────────────────
        st.subheader("Nearby Shelter Capacity")
        shelters = load_shelter_capacity()
        if shelters.empty:
            st.info(
                "FEMA shelter data is not available right now. "
                "The FEMA National Shelter System may not have open shelters in your area, "
                "or the API is temporarily unavailable."
            )
        else:
            # Filter by state if a state is selected in the Fire Map tab
            # We read the state from session_state if set, otherwise show all
            _sel_state = st.session_state.get("cmd_state_filter", "All")
            if _sel_state and _sel_state != "All" and "state" in shelters.columns:
                shelters_view = shelters[
                    shelters["state"].str.upper() == _sel_state.upper()
                ].copy()
            else:
                shelters_view = shelters.copy()

            near_capacity = shelters_view[shelters_view["pct_full"] >= 80]
            if not near_capacity.empty:
                st.warning(
                    f"⚠️ {len(near_capacity)} shelter(s) near capacity (≥ 80% full)"
                )

            # Table
            shelt_table = shelters_view[
                ["name", "county", "state", "capacity", "occupancy", "pct_full"]
            ].copy()
            shelt_table.columns = ["Shelter Name", "County", "State", "Capacity", "Occupancy", "% Full"]
            shelt_table["% Full"] = shelt_table["% Full"].apply(
                lambda v: f"{v:.0f}%" if pd.notna(v) else "—"
            )
            shelt_table["Capacity"]  = shelt_table["Capacity"].apply(
                lambda v: f"{int(v):,}" if pd.notna(v) and v > 0 else "—"
            )
            shelt_table["Occupancy"] = shelt_table["Occupancy"].apply(
                lambda v: f"{int(v):,}" if pd.notna(v) else "—"
            )
            st.dataframe(shelt_table, use_container_width=True, hide_index=True)
            st.caption(
                f"Showing {len(shelters_view):,} open shelter(s)  ·  "
                "Source: FEMA National Shelter System — refreshed every 30 minutes"
            )

        st.divider()

        # Status update controls
        st.markdown("**Update resident status:**")
        for i, row in df.iterrows():
            col_name, col_mob, col_status, col_btn = st.columns([3, 1.5, 2, 1.5])
            with col_name:
                st.markdown(f"**{row['name']}**  \n{row['address']}")
            with col_mob:
                st.caption(row["mobility"])
            with col_status:
                if row["status"] == "Evacuated ✅":
                    st.success("Evacuated ✅")
                else:
                    st.warning("Unconfirmed")
            with col_btn:
                if row["status"] != "Evacuated ✅":
                    if st.button("Mark Evacuated", key=f"evac_{i}"):
                        st.session_state.evacuee_list.at[i, "status"] = "Evacuated ✅"
                        try:
                            from auth_supabase import get_supabase
                            username = st.session_state.get("username", "dispatcher")
                            get_supabase().table("evacuation_status").upsert({
                                "reporter_username": username,
                                "person_name": row["name"],
                                "status": "Evacuated",
                                "note": row.get("address", ""),
                                "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                            }, on_conflict="reporter_username,person_name").execute()
                        except Exception:
                            pass
                        st.rerun()
                else:
                    if st.button("↩️ Undo", key=f"undo_{i}"):
                        st.session_state.evacuee_list.at[i, "status"] = "Unconfirmed"
                        try:
                            from auth_supabase import get_supabase
                            username = st.session_state.get("username", "dispatcher")
                            get_supabase().table("evacuation_status").upsert({
                                "reporter_username": username,
                                "person_name": row["name"],
                                "status": "Not Evacuated",
                                "note": row.get("address", ""),
                                "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                            }, on_conflict="reporter_username,person_name").execute()
                        except Exception:
                            pass
                        st.rerun()

        st.divider()

        # SMS alert controls
        from sms_alert import is_sms_available, send_evacuation_alert
        if is_sms_available():
            with st.expander("Send SMS Evacuation Alerts"):
                st.markdown(
                    "Send an SMS evacuation alert to unconfirmed residents who have a phone number on file."
                )
                unconf_with_phone = df[
                    (df["status"] != "Evacuated ✅") & (df["phone"].astype(str).str.strip() != "")
                ]
                if unconf_with_phone.empty:
                    st.info("No unconfirmed residents with phone numbers.")
                else:
                    county_alert = st.text_input(
                        "County / Incident name for alert message",
                        placeholder="e.g. Butte County",
                        key="sms_county"
                    )
                    shelter_alert = st.text_input(
                        "Shelter name (optional)",
                        placeholder="e.g. Chico Event Center",
                        key="sms_shelter"
                    )
                    lang_alert = st.radio("Alert language", ["English", "Spanish"],
                                          horizontal=True, key="sms_lang")
                    lang_code = "es" if lang_alert == "Spanish" else "en"
                    st.caption(f"{len(unconf_with_phone)} resident(s) eligible for SMS alert")
                    if st.button("Send Evacuation SMS to All", type="primary", key="send_sms_all"):
                        sent, failed = 0, 0
                        for _, r in unconf_with_phone.iterrows():
                            ok = send_evacuation_alert(
                                phone=str(r["phone"]),
                                resident_name=str(r["name"]),
                                county=county_alert or "your area",
                                shelter_name=shelter_alert,
                                lang=lang_code,
                            )
                            if ok:
                                sent += 1
                            else:
                                failed += 1
                        if sent:
                            st.success(f"SMS sent to {sent} resident(s).")
                        if failed:
                            st.warning(f"{failed} message(s) failed — check phone number format.")
        else:
            st.caption(
                "SMS alerts disabled. Add Twilio credentials to `.streamlit/secrets.toml` "
                "under `[twilio]` to enable."
            )

        st.divider()

        # Add new resident
        with st.expander("Add resident to tracker"):
            c1, c2, c3, c4 = st.columns(4)
            new_name    = c1.text_input("Name")
            new_addr    = c2.text_input("Address")
            new_mob     = c3.selectbox("Mobility", ["Elderly", "Disabled", "No vehicle", "Medical equipment", "Other"])
            new_phone   = c4.text_input("Phone")
            if st.button("Add to tracker") and new_name and new_addr:
                new_row = pd.DataFrame([{
                    "address": new_addr, "name": new_name,
                    "mobility": new_mob, "phone": new_phone, "status": "Unconfirmed", "db_id": None
                }])
                st.session_state.evacuee_list = pd.concat(
                    [st.session_state.evacuee_list, new_row], ignore_index=True
                )
                try:
                    from auth_supabase import get_supabase
                    username = st.session_state.get("username", "dispatcher")
                    get_supabase().table("evacuation_status").upsert({
                        "reporter_username": username,
                        "person_name": new_name,
                        "status": "Not Evacuated",
                        "note": new_addr,
                        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                    }, on_conflict="reporter_username,person_name").execute()
                except Exception:
                    pass
                st.rerun()

        # Bulk import from CSV
        with st.expander("Bulk import residents from CSV"):
            st.markdown(
                "Upload a CSV with columns: **name**, **address**, **mobility** *(optional)*, **phone** *(optional)*"
            )
            uploaded_csv = st.file_uploader("Choose CSV file", type=["csv"], key="bulk_upload_csv")
            if uploaded_csv is not None:
                try:
                    bulk_df = pd.read_csv(uploaded_csv)
                    bulk_df.columns = [c.strip().lower() for c in bulk_df.columns]
                    if not {"name", "address"}.issubset(set(bulk_df.columns)):
                        st.error(
                            f"CSV must have at least **name** and **address** columns. "
                            f"Found: {list(bulk_df.columns)}"
                        )
                    else:
                        if "mobility" not in bulk_df.columns:
                            bulk_df["mobility"] = "Other"
                        if "phone" not in bulk_df.columns:
                            bulk_df["phone"] = ""
                        bulk_df = bulk_df[["name", "address", "mobility", "phone"]].fillna("")
                        bulk_df["status"] = "Unconfirmed"
                        bulk_df["db_id"] = None
                        st.caption(f"Preview — {len(bulk_df)} resident(s) found")
                        st.dataframe(
                            bulk_df[["name", "address", "mobility", "phone"]],
                            use_container_width=True, hide_index=True
                        )
                        if st.button("Import all to tracker", key="confirm_bulk_import"):
                            st.session_state.evacuee_list = pd.concat(
                                [st.session_state.evacuee_list, bulk_df], ignore_index=True
                            )
                            try:
                                from auth_supabase import get_supabase
                                username_sb = st.session_state.get("username", "dispatcher")
                                rows_sb = [
                                    {
                                        "reporter_username": username_sb,
                                        "person_name": r["name"],
                                        "status": "Not Evacuated",
                                        "note": r["address"],
                                        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                                    }
                                    for _, r in bulk_df.iterrows()
                                ]
                                get_supabase().table("evacuation_status").upsert(
                                    rows_sb, on_conflict="reporter_username,person_name"
                                ).execute()
                            except Exception:
                                pass
                            st.success(f"Imported {len(bulk_df)} resident(s) to tracker.")
                            st.rerun()
                except Exception as exc:
                    st.error(f"Error reading CSV: {exc}")

        st.caption(
            "In a full deployment, this tracker would sync with the caregiver alert system — "
            "when a caregiver confirms their person has evacuated, status updates automatically here."
        )

    # ════════ TAB 5: FIRE DEPT RESOURCES ════════════════════════════════════
    with tab_resources:
        st.subheader("Fire Department Resources — USFA National Registry")

        usfa_df = load_usfa()
        if usfa_df is None:
            st.info(
                "**USFA National Fire Department Registry not loaded.**\n\n"
                "To enable this tab: download the registry CSV from "
                "[apps.usfa.fema.gov/registry/download](https://apps.usfa.fema.gov/registry/download) "
                "and save it as `usfa-registry-national.csv` in the `src/` directory.\n\n"
                "The app will also attempt to fetch it automatically on startup if the file is absent."
            )
            st.link_button(
                "Download USFA Registry CSV",
                "https://apps.usfa.fema.gov/registry/download",
                help="Save the downloaded file as usfa-registry-national.csv in wids-caregiver-alert/src/"
            )
            # Show summary statistics from USFA quick facts
            st.subheader("USFA Registry — Known Aggregate Statistics")
            u1, u2, u3, u4 = st.columns(4)
            u1.metric("Registered Departments", "27,000+", help="Source: USFA Quick Facts")
            u2.metric("Career Dept Share", "~6%", help="Majority are volunteer")
            u3.metric("Volunteer Dept Share", "~69%", help="USFA 2023 estimate")
            u4.metric("Combination Dept Share", "~25%", help="Career + volunteer mix")

            st.markdown("""
            **Top fire-prone states by department count (USFA estimates):**

            | State | Est. Departments |
            |-------|-----------------|
            | Texas | 1,800+ |
            | Pennsylvania | 1,700+ |
            | New York | 1,600+ |
            | Ohio | 1,500+ |
            | California | 1,000+ |

            Download the full registry CSV to enable filtering, mapping, and county-level resource analysis.
            """)
            return

        usfa_df.columns = [c.lower().strip() for c in usfa_df.columns]

        # Filters
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            states = sorted(usfa_df["hq_state"].dropna().unique()) if "hq_state" in usfa_df.columns else []
            sel_state = st.selectbox("State", ["All"] + states, key="usfa_state")
        with fc2:
            dept_types = ["All"] + sorted(usfa_df["dept_type"].dropna().unique().tolist()) if "dept_type" in usfa_df.columns else ["All"]
            sel_type = st.selectbox("Department Type", dept_types, key="usfa_type")
        with fc3:
            primary_only = st.checkbox("Primary Emergency Mgmt Only")

        # Filter
        fdf = usfa_df.copy()
        if sel_state != "All" and "hq_state" in fdf.columns:
            fdf = fdf[fdf["hq_state"] == sel_state]
        if sel_type != "All" and "dept_type" in fdf.columns:
            fdf = fdf[fdf["dept_type"] == sel_type]
        if primary_only and "primary_agency" in fdf.columns:
            fdf = fdf[fdf["primary_agency"] == True]

        # KPIs
        st.caption(f"Showing {len(fdf):,} of {len(usfa_df):,} departments")
        u1, u2, u3, u4 = st.columns(4)

        stations_col = next((c for c in fdf.columns if "station" in c), None)
        career_col   = next((c for c in fdf.columns if "career" in c and "ff" in c), None)
        vol_col      = next((c for c in fdf.columns if "vol" in c and "ff" in c), None)

        u1.metric("Total Stations",       f"{pd.to_numeric(fdf[stations_col], errors='coerce').sum():,.0f}" if stations_col else "—")
        u2.metric("Career Firefighters",  f"{pd.to_numeric(fdf[career_col],   errors='coerce').sum():,.0f}" if career_col   else "—")
        u3.metric("Volunteer FF",         f"{pd.to_numeric(fdf[vol_col],      errors='coerce').sum():,.0f}" if vol_col      else "—")
        u4.metric("Departments",          f"{len(fdf):,}")

        # Charts
        if "dept_type" in fdf.columns and len(fdf) > 0:
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                type_counts = fdf["dept_type"].value_counts().head(8)
                fig_type = go.Figure(go.Bar(
                    x=type_counts.index, y=type_counts.values,
                    marker_color="#FF6347",
                    text=type_counts.values, textposition="outside"
                ))
                fig_type.update_layout(
                    template="plotly_dark", title="Departments by Type",
                    height=300, margin=dict(l=20,r=10,t=40,b=60),
                    xaxis_tickangle=-20
                )
                st.plotly_chart(fig_type, use_container_width=True)

            with chart_col2:
                if "hq_state" in fdf.columns:
                    state_counts = fdf["hq_state"].value_counts().head(10)
                    fig_state = go.Figure(go.Bar(
                        x=state_counts.index, y=state_counts.values,
                        marker_color="#4a90d9",
                        text=state_counts.values, textposition="outside"
                    ))
                    fig_state.update_layout(
                        template="plotly_dark", title="Top 10 States",
                        height=300, margin=dict(l=20,r=10,t=40,b=40)
                    )
                    st.plotly_chart(fig_state, use_container_width=True)

        # Dept table
        display_cols = [c for c in ["fd_name", "hq_city", "hq_state", "fd_county",
                                     "dept_type", "num_stations"] if c in fdf.columns]
        if display_cols:
            st.dataframe(
                fdf[display_cols].head(200).rename(columns={
                    "fd_name": "Fire dept name", "hq_city": "HQ city",
                    "hq_state": "HQ state", "fd_county": "County",
                    "dept_type": "Dept Type", "num_stations": "Stations"
                }),
                use_container_width=True, hide_index=True
            )
            st.caption(f"Showing top 200 of {len(fdf):,}. Use filters to narrow down.")

        # Vulnerable populations at risk in filtered area
        if sel_state != "All":
            svi_df = load_svi_centroids()
            if svi_df is not None and "ST_ABBR" in svi_df.columns:
                state_svi = svi_df[
                    (svi_df["ST_ABBR"] == sel_state) & (svi_df["RPL_THEMES"] >= 0.75)
                ].nlargest(10, "RPL_THEMES")
                if len(state_svi) > 0:
                    st.subheader(f"High-Priority Vulnerable Populations — {sel_state}")
                    vul_display = state_svi[["COUNTY", "ST_ABBR", "RPL_THEMES", "E_AGE65", "E_DISABL", "E_NOVEH"]].copy()
                    vul_display.columns = ["County", "State", "SVI Score", "Elderly (65+)", "Disabled", "No Vehicle"]
                    st.dataframe(vul_display.round(2), use_container_width=True, hide_index=True)