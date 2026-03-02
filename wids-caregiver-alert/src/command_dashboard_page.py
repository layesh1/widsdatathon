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
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from pathlib import Path


# ── Data loaders ──────────────────────────────────────────────────────────────

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
               Path("01_raw_data/usfa-registry-national.csv")]:
        if p.exists():
            try:
                return pd.read_csv(p, low_memory=False)
            except Exception:
                pass
    return None


def load_geojson_layer(fname):
    for p in [Path(fname), Path(f"wids-caregiver-alert/src/{fname}"),
               Path(f"../{fname}"), Path(f"src/{fname}")]:
        if p.exists():
            return str(p)
    return None


# ── Evacuee status tracker (session state) ───────────────────────────────────

def init_evacuee_tracker():
    """Initialize demo evacuee list in session state."""
    if "evacuee_list" not in st.session_state:
        st.session_state.evacuee_list = pd.DataFrame([
            {"address": "142 Oak St, Paradise, CA",         "name": "Martha Chen",      "mobility": "Elderly",    "phone": "530-555-0101", "status": "Unconfirmed"},
            {"address": "77 Pine Ridge Rd, Magalia, CA",    "name": "Robert Okafor",    "mobility": "Disabled",   "phone": "530-555-0144", "status": "Unconfirmed"},
            {"address": "89 Skyway, Paradise, CA",          "name": "Delores Perez",    "mobility": "Elderly",    "phone": "530-555-0199", "status": "Unconfirmed"},
            {"address": "312 Pentz Rd, Paradise, CA",       "name": "James Whitmore",   "mobility": "No vehicle", "phone": "530-555-0177", "status": "Unconfirmed"},
            {"address": "55 Bille Rd, Paradise, CA",        "name": "Yuki Tanaka",      "mobility": "Disabled",   "phone": "530-555-0155", "status": "Evacuated ✅"},
            {"address": "201 Clark Rd, Chico, CA",          "name": "Gloria Martinez",  "mobility": "Elderly",    "phone": "530-555-0188", "status": "Unconfirmed"},
        ])


# ── Main render ───────────────────────────────────────────────────────────────

def render_command_dashboard(fire_data, fire_source, fire_label):
    st.title("⚡ Command Dashboard")
    st.caption(f"Emergency Worker View  ·  {fire_label}  ·  WiDS 2021–2025 Historical Benchmarks")

    init_evacuee_tracker()

    # ── Historical benchmarks (always real) ──────────────────────────────────
    st.subheader("📊 Historical Response Benchmarks  *(WiDS 2021–2025)*")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Median Time to Evac Order",  "1.1h",
              help="653 fires with confirmed evac actions, 2021–2025")
    h2.metric("Worst-Case (90th %ile)",     "32h",
              help="1 in 10 fires takes over 32h to get an official order")
    h3.metric("Fires Exceeding 6h",         "20%",    delta="critical window", delta_color="inverse")
    h4.metric("Vuln County Growth Rate",    "11.7 ac/hr", delta="+17% vs non-vuln", delta_color="inverse")

    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_map, tab_evacuees, tab_resources = st.tabs([
        "🗺️ Fire Map", "👥 Evacuee Status Tracker", "🚒 Fire Dept Resources"
    ])

    # ════════ TAB 1: FIRE MAP ═══════════════════════════════════════════════
    with tab_map:
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 2])
        with col_ctrl1:
            state_filter = st.selectbox("Filter by State",
                ["All", "CA", "OR", "WA", "CO", "NM", "AZ", "TX", "MT", "ID", "NV",
                 "FL", "GA", "NC", "SC", "LA"])
        with col_ctrl2:
            svi_threshold = st.slider("Min SVI to show (vulnerable counties)", 0.5, 1.0, 0.75, 0.05)
        with col_ctrl3:
            show_perimeters = st.checkbox("Show fire perimeters (GeoJSON)", value=True)
            show_evac_zones = st.checkbox("Show evacuation zones (GeoJSON)", value=True)

        # Build map centered on US
        m = folium.Map(
            location=[39.5, -98.5],
            zoom_start=4,
            tiles="CartoDB dark_matter",
            prefer_canvas=True
        )

        # GeoJSON layers — correct path resolution
        if show_perimeters:
            perim_path = load_geojson_layer("fire_perimeters_approved.geojson")
            if perim_path:
                try:
                    folium.GeoJson(
                        perim_path,
                        name="Fire Perimeters",
                        style_function=lambda f: {
                            "fillColor": "#FF6600", "color": "#FF4400",
                            "weight": 1.5, "fillOpacity": 0.35
                        },
                        tooltip=folium.GeoJsonTooltip(fields=[], aliases=[])
                    ).add_to(m)
                except Exception as e:
                    st.caption(f"⚠️ Fire perimeters: {e}")

        if show_evac_zones:
            evac_path = load_geojson_layer("evac_zones_map.geojson")
            if evac_path:
                try:
                    folium.GeoJson(
                        evac_path,
                        name="Evacuation Zones",
                        style_function=lambda f: {
                            "fillColor": "#FF4444",
                            "color": "#CC0000",
                            "weight": 1,
                            "fillOpacity": 0.25
                        }
                    ).add_to(m)
                except Exception as e:
                    st.caption(f"⚠️ Evac zones: {e}")

        # Live fire hotspots
        n_plotted = 0
        if fire_source != "none" and len(fire_data) > 0:
            plot_df = fire_data.copy()
            if state_filter != "All" and "state" in plot_df.columns:
                plot_df = plot_df[plot_df["state"] == state_filter]

            for _, row in plot_df.head(500).iterrows():
                try:
                    conf = row.get("confidence", "")
                    is_high = (str(conf).lower() in ["h", "high", "n", "nominal"] or
                               (str(conf).isdigit() and int(conf) >= 80))
                    color = "#FF2200" if is_high else "#FF8800"
                    folium.CircleMarker(
                        location=[float(row["lat"]), float(row["lon"])],
                        radius=5 if is_high else 3,
                        color=color, fill=True, fill_color=color,
                        fill_opacity=0.75,
                        tooltip=f"Fire hotspot | Conf: {conf}"
                    ).add_to(m)
                    n_plotted += 1
                except Exception:
                    pass

        # Vulnerable county centroids
        svi_df = load_svi_centroids()
        if svi_df is not None:
            filtered_svi = svi_df[svi_df["RPL_THEMES"] >= svi_threshold]
            if state_filter != "All" and "ST_ABBR" in filtered_svi.columns:
                filtered_svi = filtered_svi[filtered_svi["ST_ABBR"] == state_filter]
            for _, row in filtered_svi.nlargest(300, "RPL_THEMES").iterrows():
                try:
                    folium.CircleMarker(
                        location=[row["LATITUDE"], row["LONGITUDE"]],
                        radius=7,
                        color="#4a90d9", fill=True, fill_color="#4a90d9",
                        fill_opacity=0.35,
                        tooltip=f"{row.get('COUNTY','County')}, {row.get('ST_ABBR','')} — SVI {row['RPL_THEMES']:.2f}"
                    ).add_to(m)
                except Exception:
                    pass

        folium.LayerControl().add_to(m)

        # Legend
        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:#111;
                    padding:10px 14px;border-radius:8px;font-size:12px;color:white;border:1px solid #333;">
            <b>Legend</b><br>
            <span style="color:#FF2200">●</span> High-confidence fire hotspot<br>
            <span style="color:#FF8800">●</span> Moderate fire hotspot<br>
            <span style="color:#4a90d9">●</span> Vulnerable county (SVI ≥ threshold)<br>
            <span style="color:#FF6600">▬</span> Fire perimeter<br>
            <span style="color:#FF4444">▬</span> Evacuation zone
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        map_result = st_folium(m, width="100%", height=560, returned_objects=["last_clicked"])

        # Status line
        if fire_source != "none":
            st.caption(
                f"{fire_label} · {n_plotted} hotspots plotted · "
                f"Blue = SVI ≥ {svi_threshold} counties · "
                "GeoJSON layers load from local src/ directory"
            )
        else:
            st.caption("⚪ No live fire data. Map shows vulnerable county locations only.")

    # ════════ TAB 2: EVACUEE STATUS TRACKER ══════════════════════════════════
    with tab_evacuees:
        st.subheader("👥 Vulnerable Resident Evacuation Status")
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
        k3.metric("⚠️ Unconfirmed",           unconf,
                  delta="Needs contact" if unconf > 0 else "All confirmed",
                  delta_color="inverse" if unconf > 0 else "normal")

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
                    st.warning("Unconfirmed ⚠️")
            with col_btn:
                if row["status"] != "Evacuated ✅":
                    if st.button("✅ Mark Evacuated", key=f"evac_{i}"):
                        st.session_state.evacuee_list.at[i, "status"] = "Evacuated ✅"
                        st.rerun()
                else:
                    if st.button("↩️ Undo", key=f"undo_{i}"):
                        st.session_state.evacuee_list.at[i, "status"] = "Unconfirmed"
                        st.rerun()

        st.divider()

        # Add new resident
        with st.expander("➕ Add resident to tracker"):
            c1, c2, c3, c4 = st.columns(4)
            new_name    = c1.text_input("Name")
            new_addr    = c2.text_input("Address")
            new_mob     = c3.selectbox("Mobility", ["Elderly", "Disabled", "No vehicle", "Medical equipment", "Other"])
            new_phone   = c4.text_input("Phone")
            if st.button("Add to tracker") and new_name and new_addr:
                new_row = pd.DataFrame([{
                    "address": new_addr, "name": new_name,
                    "mobility": new_mob, "phone": new_phone, "status": "Unconfirmed"
                }])
                st.session_state.evacuee_list = pd.concat(
                    [st.session_state.evacuee_list, new_row], ignore_index=True
                )
                st.rerun()

        st.caption(
            "In a full deployment, this tracker would sync with the caregiver alert system — "
            "when a caregiver confirms their person has evacuated, status updates automatically here."
        )

    # ════════ TAB 3: FIRE DEPT RESOURCES ════════════════════════════════════
    with tab_resources:
        st.subheader("🚒 Fire Department Resources — USFA National Registry")

        usfa_df = load_usfa()
        if usfa_df is None:
            st.error("usfa-registry-national.csv not found. Copy it to src/ directory.")
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