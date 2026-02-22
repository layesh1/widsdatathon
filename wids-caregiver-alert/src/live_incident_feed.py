"""
live_incident_feed.py
---------------------
Live incident feed for the WiDS Caregiver Alert Dashboard.
49ers Intelligence Lab — WiDS Datathon 2025

Priority data chain:
  1. geo_events_geoevent.csv  — is_active fires from WiDS dataset (preferred)
  2. NASA FIRMS (VIIRS SNPP)  — fallback for real-time hotspots
  3. Static demo data         — last-resort offline fallback

Designed to be imported by wildfire_alert_dashboard.py and other pages.

Usage:
    from live_incident_feed import get_live_incidents, get_incident_summary

    fires_df = get_live_incidents()   # returns standardized DataFrame
    summary  = get_incident_summary() # returns dict of key stats
"""

import pandas as pd
import numpy as np
import requests
import os
import time
import streamlit as st
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

# Paths (relative to the src/ directory where Streamlit runs)
_HERE = Path(__file__).parent
GEO_EVENTS_PATH = _HERE / "geo_events_geoevent.csv"          # WiDS dataset
GEO_EVENTS_FALLBACK = Path("/01_raw_data/geo_events_geoevent.csv")  # repo root

# NASA FIRMS — free, no key required for CSV area endpoint
FIRMS_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    "/VIIRS_SNPP_NRT/-125,24,-66,50/1"   # continental USA, past 24h
)

# Cache TTL
FIRMS_TTL_SECONDS = 300          # 5 min — FIRMS updates ~every 3 hrs anyway
GEO_EVENTS_TTL_SECONDS = 3600   # 1 hr — WiDS file is static; reload hourly


# ── Standardized schema ───────────────────────────────────────────────────────
# All sources return a DataFrame with these columns:
#   fire_id       str    unique identifier
#   name          str    human-readable fire name
#   lat           float
#   lon           float
#   is_active     bool
#   acreage       float  (NaN if unknown)
#   containment   float  0–100, NaN if unknown
#   date_created  datetime (UTC-aware)
#   source        str    "geo_events" | "firms" | "demo"
#   confidence    str    "high" | "medium" | "low" (FIRMS confidence)
#   notification_type str  e.g. "Evacuation Order", "Warning", "Advisory", ""


# ── Source 1: WiDS geo_events_geoevent.csv ────────────────────────────────────

def _find_geo_events_file():
    """Locate geo_events_geoevent.csv — check src/ then repo root."""
    for p in [GEO_EVENTS_PATH, GEO_EVENTS_FALLBACK]:
        if p.exists():
            return p
    # Try environment variable override
    env_path = os.environ.get("GEO_EVENTS_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    return None


@st.cache_data(ttl=GEO_EVENTS_TTL_SECONDS, show_spinner=False)
def _load_geo_events_raw():
    """
    Load and lightly parse geo_events_geoevent.csv.
    Returns None if file not found.
    """
    path = _find_geo_events_file()
    if path is None:
        return None

    try:
        df = pd.read_csv(
            path,
            usecols=lambda c: c in {
                "id", "name", "is_active", "latitude", "longitude",
                "notification_type", "date_created", "acreage", "containment",
            },
            low_memory=False,
        )
    except Exception:
        return None

    # Normalize column names
    df = df.rename(columns={
        "id": "fire_id",
        "latitude": "lat",
        "longitude": "lon",
    })

    # Parse dates — file is timezone-naive, treat as UTC
    df["date_created"] = pd.to_datetime(df["date_created"], errors="coerce", utc=False)
    df["date_created"] = df["date_created"].dt.tz_localize("UTC", ambiguous="NaT", nonexistent="NaT")

    # Normalize types
    df["fire_id"] = df["fire_id"].astype(str)
    df["is_active"] = df["is_active"].astype(bool)
    df["acreage"] = pd.to_numeric(df["acreage"], errors="coerce")
    df["containment"] = pd.to_numeric(df["containment"], errors="coerce")
    df["notification_type"] = df["notification_type"].fillna("").astype(str)
    df["confidence"] = "high"   # authoritative source
    df["source"] = "geo_events"

    return df


def _get_geo_events_incidents(active_only=True, days_back=30):
    """
    Return active (or recent) fire incidents from the WiDS geo_events file.

    active_only  — if True, return only is_active == True fires
    days_back    — also include fires updated within this many days even if
                   is_active is False (catches recently-closed incidents)
    """
    df = _load_geo_events_raw()
    if df is None or df.empty:
        return None

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    if active_only:
        mask = df["is_active"] | (
            df["date_created"].notna() & (df["date_created"] >= cutoff)
        )
        df = df[mask].copy()
    
    # Drop rows without coordinates
    df = df.dropna(subset=["lat", "lon"])
    
    # Deduplicate on fire_id
    df = df.drop_duplicates(subset=["fire_id"])

    return df if not df.empty else None


# ── Source 2: NASA FIRMS ───────────────────────────────────────────────────────

@st.cache_data(ttl=FIRMS_TTL_SECONDS, show_spinner=False)
def _fetch_firms():
    """Fetch VIIRS SNPP active fire hotspots from NASA FIRMS (no API key needed)."""
    try:
        resp = requests.get(FIRMS_URL, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
    except Exception:
        return None

    if df.empty or "latitude" not in df.columns:
        return None

    # Map FIRMS columns → standard schema
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})

    # FIRMS confidence: "high", "medium", "low" (or numeric 0-100 for VIIRS)
    if "confidence" in df.columns:
        conf_raw = df["confidence"].astype(str).str.lower()
        def _norm_conf(v):
            if v in ("h", "high"):
                return "high"
            elif v in ("l", "low"):
                return "low"
            else:
                try:
                    pct = int(v)
                    return "high" if pct >= 80 else ("medium" if pct >= 50 else "low")
                except (ValueError, TypeError):
                    return "medium"
        df["confidence"] = conf_raw.map(_norm_conf)
    else:
        df["confidence"] = "medium"

    # Build date from acq_date + acq_time
    if "acq_date" in df.columns and "acq_time" in df.columns:
        df["date_created"] = pd.to_datetime(
            df["acq_date"].astype(str) + " "
            + df["acq_time"].astype(str).str.zfill(4),
            format="%Y-%m-%d %H%M",
            errors="coerce",
            utc=True,
        )
    else:
        df["date_created"] = datetime.now(tz=timezone.utc)

    # Generate a stable fire_id from lat/lon/time
    df["fire_id"] = (
        "firms_"
        + df["lat"].round(3).astype(str)
        + "_"
        + df["lon"].round(3).astype(str)
    )

    df["name"] = "Active Hotspot (" + df["lat"].round(2).astype(str) + ", " + df["lon"].round(2).astype(str) + ")"
    df["is_active"] = True
    df["acreage"] = np.nan
    df["containment"] = np.nan
    df["notification_type"] = ""
    df["source"] = "firms"

    # Keep only high + medium confidence to reduce noise
    df = df[df["confidence"].isin(["high", "medium"])]

    return df[["fire_id", "name", "lat", "lon", "is_active", "acreage",
               "containment", "date_created", "source", "confidence",
               "notification_type"]].drop_duplicates(subset=["fire_id"])


# ── Source 3: Demo / offline fallback ────────────────────────────────────────

def _get_demo_incidents():
    """Minimal hard-coded fallback so the UI never breaks."""
    now = datetime.now(tz=timezone.utc)
    rows = [
        ("demo_1", "Park Fire (Demo)", 39.80, -121.60, True, 429603, 98, "Evacuation Order"),
        ("demo_2", "Bridge Fire (Demo)", 34.31, -117.73, True,  53700,  5, "Evacuation Warning"),
        ("demo_3", "Line Fire (Demo)",   34.18, -117.31, True,  38000, 55, "Advisory"),
        ("demo_4", "Airport Fire (Demo)",33.70, -117.53, False, 23000, 90, ""),
        ("demo_5", "Borel Fire (Demo)",  35.68, -118.86, False, 69361, 99, ""),
    ]
    df = pd.DataFrame(rows, columns=[
        "fire_id", "name", "lat", "lon", "is_active",
        "acreage", "containment", "notification_type",
    ])
    df["date_created"] = now - pd.to_timedelta(
        [2, 5, 10, 30, 60], unit="d"
    )
    df["source"] = "demo"
    df["confidence"] = "medium"
    return df


# ── Public API ────────────────────────────────────────────────────────────────

def get_live_incidents(
    active_only=True,
    days_back=30,
    max_firms_hotspots=150,
):
    """
    Return the best available fire incident data.

    Priority:
      1. WiDS geo_events_geoevent.csv  (is_active fires + recent fires)
      2. NASA FIRMS VIIRS hotspots     (fallback)
      3. Static demo data              (last resort)

    Parameters
    ----------
    active_only         Filter to is_active fires (plus recent ones within days_back)
    days_back           Include fires updated within this many days even if inactive
    max_firms_hotspots  Cap FIRMS results to avoid map overload

    Returns
    -------
    pd.DataFrame with standardized columns (see schema above).
    """
    # ── Try primary source ───────────────────────────────────────────────────
    df = _get_geo_events_incidents(active_only=active_only, days_back=days_back)

    if df is not None and not df.empty:
        source_label = "geo_events"
    else:
        # ── Try FIRMS ────────────────────────────────────────────────────────
        df = _fetch_firms()
        if df is not None and not df.empty:
            df = df.head(max_firms_hotspots)
            source_label = "firms"
        else:
            # ── Demo fallback ────────────────────────────────────────────────
            df = _get_demo_incidents()
            source_label = "demo"

    # Ensure standard columns exist
    for col in ["acreage", "containment"]:
        if col not in df.columns:
            df[col] = np.nan

    df = df.reset_index(drop=True)
    return df


def get_incident_summary(df=None):
    """
    Return a summary dict for use in the Command Dashboard KPI row.

    If df is None, calls get_live_incidents() internally.

    Returns keys:
        total_active, evacuation_orders, evac_warnings, advisories,
        source, last_updated, high_confidence_pct
    """
    if df is None:
        df = get_live_incidents()

    now_str = datetime.now(tz=timezone.utc).strftime("%H:%M UTC")

    if df.empty:
        return {
            "total_active": 0,
            "evacuation_orders": 0,
            "evac_warnings": 0,
            "advisories": 0,
            "source": "none",
            "last_updated": now_str,
            "high_confidence_pct": 0.0,
        }

    nt = df["notification_type"].str.lower()

    return {
        "total_active": int(df["is_active"].sum()),
        "evacuation_orders": int(nt.str.contains("order").sum()),
        "evac_warnings": int(nt.str.contains("warning").sum()),
        "advisories": int(nt.str.contains("advi").sum()),
        "source": df["source"].iloc[0] if not df.empty else "unknown",
        "last_updated": now_str,
        "high_confidence_pct": round(
            100 * (df["confidence"] == "high").sum() / max(len(df), 1), 1
        ),
    }


def get_escalating_fires(df=None):
    """
    Return fires with evacuation orders or warnings — highest urgency subset.
    Useful for the caregiver alert triage logic.
    """
    if df is None:
        df = get_live_incidents()
    
    mask = df["notification_type"].str.lower().str.contains(
        "order|warning", na=False
    )
    return df[mask].copy()


# ── Streamlit status badge ────────────────────────────────────────────────────

def render_feed_status_badge(df=None):
    """
    Drop a small status line into the sidebar showing which data source is active.
    Call from wildfire_alert_dashboard.py sidebar section.
    """
    if df is None:
        df = get_live_incidents()
    
    summary = get_incident_summary(df)
    source = summary["source"]

    if source == "geo_events":
        label = "🟢 Live · WiDS Dataset"
        color = "green"
    elif source == "firms":
        label = "🟡 Live · NASA FIRMS"
        color = "orange"
    else:
        label = "🔴 Demo data (offline)"
        color = "red"

    st.sidebar.markdown(
        f"**Incident Feed:** <span style='color:{color}'>{label}</span><br>"
        f"<small>Updated: {summary['last_updated']} · "
        f"{summary['total_active']} active fires</small>",
        unsafe_allow_html=True,
    )


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing live_incident_feed.py ...\n")

    df = get_live_incidents()
    print(f"Source:        {df['source'].iloc[0] if not df.empty else 'none'}")
    print(f"Total fires:   {len(df)}")
    print(f"Active fires:  {df['is_active'].sum()}")

    summary = get_incident_summary(df)
    print("\nSummary:")
    for k, v in summary.items():
        print(f"  {k:<25} {v}")

    print("\nSample rows:")
    print(df[["fire_id", "name", "lat", "lon", "is_active", "notification_type", "source"]].head(10).to_string(index=False))

    escalating = get_escalating_fires(df)
    print(f"\nEscalating (orders/warnings): {len(escalating)} fires")
    if not escalating.empty:
        print(escalating[["name", "notification_type", "acreage", "containment"]].head(5).to_string(index=False))
