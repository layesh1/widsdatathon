"""
irwin_linkage_page.py
IRWIN Incident Linkage — 49ers Intelligence Lab · WiDS 2025

Parses IRWINID and incident metadata from fire_perimeters_gis_fireperimeter.csv
source_extra_data JSON column.  Links each perimeter record to IRWIN-registered
incidents so analysts can cross-reference with NIFC / InciWeb / ICS-209 data.

IRWIN = Integrated Reporting of Wildland-fire Information (USDA / DOI)
4,767 of 6,207 perimeter records have a valid IRWINID (76.8%).
"""

from __future__ import annotations

import json
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path


_PERIMETER_PATHS = [
    Path("01_raw_data/fire_perimeters_gis_fireperimeter.csv"),
    Path("../01_raw_data/fire_perimeters_gis_fireperimeter.csv"),
    Path("fire_perimeters_gis_fireperimeter.csv"),
]

_GACC_FULL = {
    "AICC": "Alaska (AICC)",
    "EACC": "Eastern Area (EACC)",
    "EGBC": "East Great Basin (EGBC)",
    "GBCC": "Great Basin (GBCC)",
    "NRCC": "Northern Rockies (NRCC)",
    "NWCC": "Northwest (NWCC)",
    "ONCC": "Northern California (ONCC)",
    "OSCC": "Southern California (OSCC)",
    "RMCC": "Rocky Mountain (RMCC)",
    "SACC": "Southern Area (SACC)",
    "SWCC": "Southwest (SWCC)",
    "WGBC": "West Great Basin (WGBC)",
}

_INCIDENT_TYPE = {
    "WF": "Wildfire",
    "RX": "Prescribed Fire",
    "CX": "Complex",
    "UF": "Unknown Fire",
}


@st.cache_data(show_spinner=False)
def load_irwin_data() -> pd.DataFrame:
    """Load fire perimeters and parse IRWIN fields from source_extra_data."""
    for p in _PERIMETER_PATHS:
        if p.exists():
            try:
                df = pd.read_csv(p, low_memory=False)
                return _parse_irwin(df)
            except Exception:
                pass
    # No file found — return empty with expected columns
    return pd.DataFrame(columns=[
        "id", "geo_event_id", "approval_status", "source",
        "source_incident_name", "source_acres", "date_created",
        "IRWINID", "IncidentName", "GACC", "GISAcres",
        "IncidentTypeCategory", "GACC_full", "IncidentType_full",
        "inciweb_url",
    ])


def _parse_irwin(df: pd.DataFrame) -> pd.DataFrame:
    """Expand source_extra_data JSON into flat columns."""
    irwin_rows = []
    for _, row in df.iterrows():
        sed = row.get("source_extra_data", "")
        extra: dict = {}
        if pd.notna(sed) and sed and sed not in ("{}", ""):
            try:
                extra = json.loads(sed)
            except Exception:
                pass

        irwin_id = extra.get("IRWINID", "")
        # Strip curly braces from GUID
        if irwin_id:
            irwin_id = irwin_id.strip("{}").upper()

        gacc = extra.get("GACC", "")
        inc_type = extra.get("IncidentTypeCategory", "")
        gis_acres = extra.get("GISAcres", None)

        irwin_rows.append({
            "id":                   row.get("id", ""),
            "geo_event_id":         row.get("geo_event_id", ""),
            "approval_status":      row.get("approval_status", ""),
            "source":               row.get("source", ""),
            "source_incident_name": row.get("source_incident_name", ""),
            "source_acres":         row.get("source_acres", None),
            "date_created":         row.get("date_created", ""),
            "IRWINID":              irwin_id or "",
            "IncidentName":         extra.get("IncidentName", ""),
            "GACC":                 gacc,
            "GISAcres":             gis_acres,
            "IncidentTypeCategory": inc_type,
            "GACC_full":            _GACC_FULL.get(gacc, gacc or "Unknown"),
            "IncidentType_full":    _INCIDENT_TYPE.get(inc_type, inc_type or "Unknown"),
        })

    out = pd.DataFrame(irwin_rows)

    # Build InciWeb search URL by incident name
    def _inciweb(name: str) -> str:
        if not name:
            return ""
        q = name.replace(" ", "+")
        return f"https://inciweb.nwcg.gov/?s={q}"

    out["inciweb_url"] = out["IncidentName"].apply(_inciweb)
    return out


def render_irwin_linkage_page():
    st.title("IRWIN Incident Linkage")
    st.caption(
        "Cross-reference wildfire perimeter records with IRWIN-registered incidents "
        "· WiDS 2021–2025 · Source: fire_perimeters_gis_fireperimeter"
    )

    st.markdown("""\
> **IRWIN** (Integrated Reporting of Wildland-fire Information) is the authoritative federal \
registry of wildland fire incidents maintained by USDA and DOI. Each incident receives a unique \
GUID (IRWINID) that links perimeter data, ICS-209 reports, resource orders, and InciWeb pages. \
Matching WiDS perimeter records to IRWIN enables cross-agency incident validation and \
integration with USFS / BLM / NPS data pipelines.
""")

    df = load_irwin_data()

    if df.empty:
        st.warning(
            "Perimeter data file not found. Expected: "
            "`01_raw_data/fire_perimeters_gis_fireperimeter.csv`"
        )
        return

    total    = len(df)
    linked   = (df["IRWINID"] != "").sum()
    unlinked = total - linked
    pct      = linked / total * 100 if total else 0

    gacc_counts = df[df["IRWINID"] != ""]["GACC"].value_counts()
    top_gacc     = gacc_counts.index[0] if len(gacc_counts) else "—"
    top_gacc_n   = int(gacc_counts.iloc[0]) if len(gacc_counts) else 0

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Perimeter Records", f"{total:,}")
    k2.metric("IRWIN-Linked Records", f"{linked:,}",
              delta=f"{pct:.1f}% linkage rate")
    k3.metric("Unlinked Records", f"{unlinked:,}",
              delta="No IRWINID in source_extra_data",
              delta_color="inverse")
    k4.metric(f"Top GACC ({top_gacc})", f"{top_gacc_n:,}",
              delta=_GACC_FULL.get(top_gacc, top_gacc),
              delta_color="off")

    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    st.subheader("Incident Explorer")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    linked_only = col_f1.checkbox("IRWIN-linked only", value=True)
    gacc_options = ["All"] + sorted(df["GACC"].dropna().unique().tolist())
    gacc_sel = col_f2.selectbox("GACC Region", gacc_options)

    type_options = ["All"] + sorted(df["IncidentType_full"].dropna().unique().tolist())
    type_sel = col_f3.selectbox("Incident Type", type_options)

    status_options = ["All"] + sorted(df["approval_status"].dropna().unique().tolist())
    status_sel = col_f4.selectbox("Approval Status", status_options)

    search_q = st.text_input(
        "Search incident name",
        placeholder="e.g. Camp Fire, WOOLSEY, Dixie",
    )

    # Apply filters
    fdf = df.copy()
    if linked_only:
        fdf = fdf[fdf["IRWINID"] != ""]
    if gacc_sel != "All":
        fdf = fdf[fdf["GACC"] == gacc_sel]
    if type_sel != "All":
        fdf = fdf[fdf["IncidentType_full"] == type_sel]
    if status_sel != "All":
        fdf = fdf[fdf["approval_status"] == status_sel]
    if search_q.strip():
        q = search_q.strip().lower()
        fdf = fdf[
            fdf["IncidentName"].str.lower().str.contains(q, na=False) |
            fdf["source_incident_name"].str.lower().str.contains(q, na=False)
        ]

    st.caption(f"{len(fdf):,} records match current filters")

    # ── Display table ─────────────────────────────────────────────────────────
    display_cols = {
        "IncidentName":         "Incident Name (IRWIN)",
        "source_incident_name": "Source Name",
        "IRWINID":              "IRWINID",
        "GACC_full":            "GACC Region",
        "IncidentType_full":    "Type",
        "GISAcres":             "GIS Acres",
        "approval_status":      "Approval",
        "date_created":         "Date",
        "geo_event_id":         "Geo Event ID",
    }
    table_df = (
        fdf[list(display_cols.keys())]
        .rename(columns=display_cols)
        .copy()
    )
    # Round acres
    if "GIS Acres" in table_df.columns:
        table_df["GIS Acres"] = pd.to_numeric(table_df["GIS Acres"], errors="coerce").round(1)
    # Truncate date to date only
    if "Date" in table_df.columns:
        table_df["Date"] = table_df["Date"].astype(str).str[:10]

    st.dataframe(table_df.head(500), use_container_width=True, hide_index=True)

    if len(fdf) > 500:
        st.caption("Showing first 500 results. Use filters to narrow results.")

    # ── GACC breakdown ────────────────────────────────────────────────────────
    st.divider()
    col_gacc, col_type = st.columns(2)

    with col_gacc:
        st.subheader("Records by GACC Region")
        gacc_df = (
            df[df["IRWINID"] != ""]["GACC_full"]
            .value_counts()
            .reset_index()
            .rename(columns={"GACC_full": "GACC Region", "count": "Linked Records"})
        )
        st.dataframe(gacc_df, use_container_width=True, hide_index=True)

    with col_type:
        st.subheader("Records by Incident Type")
        type_df = (
            df[df["IRWINID"] != ""]["IncidentType_full"]
            .value_counts()
            .reset_index()
            .rename(columns={"IncidentType_full": "Incident Type", "count": "Records"})
        )
        st.dataframe(type_df, use_container_width=True, hide_index=True)

    # ── InciWeb links ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Look Up Incident on InciWeb")
    st.markdown(
        "Select any incident below to open its InciWeb search page. "
        "InciWeb is the official US interagency incident information system."
    )
    named = df[(df["IRWINID"] != "") & (df["IncidentName"].str.strip() != "")].copy()
    named = named.drop_duplicates("IRWINID").sort_values("IncidentName")

    inc_options = named["IncidentName"].tolist()
    if inc_options:
        selected_inc = st.selectbox("Select incident", inc_options, key="irwin_inc_sel")
        sel_row = named[named["IncidentName"] == selected_inc].iloc[0]
        irwin_url = f"https://inciweb.nwcg.gov/?s={selected_inc.replace(' ', '+')}"
        st.link_button(
            f"Search '{selected_inc}' on InciWeb",
            irwin_url,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("IRWINID", sel_row["IRWINID"])
        c2.metric("GACC", sel_row["GACC_full"])
        c3.metric("GIS Acres", f"{sel_row['GISAcres']:,.1f}" if pd.notna(sel_row["GISAcres"]) else "—")

    # ── Methodology note ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("""\
**Data source:** `fire_perimeters_gis_fireperimeter` table — Genasys Protect WiDS dataset.

**IRWINID** is stored as a GUID (e.g., `7D0E8FF7-6101-4DD3-BF00-7ECE1D6ACA77`) in the \
`source_extra_data` JSON column of each perimeter record.

**Linkage gaps (23.2%)** occur when:
- Fire was mapped but not submitted to IRWIN (small / local fires)
- Source system did not populate the IRWINID field
- Non-wildfire perimeter records (Rx burns, complex boundaries)

**Use cases:** Joining IRWIN-linked records to ICS-209 reports, USFS fuel treatment polygons, \
or NIFC historical fire occurrence data for richer evacuation-delay analysis.
""")
    st.caption(
        "IRWIN linkage computed from source_extra_data JSON in fire_perimeters_gis_fireperimeter.csv. "
        "InciWeb links open search results by incident name. "
        "4,767 / 6,207 records linked (76.8%)."
    )
