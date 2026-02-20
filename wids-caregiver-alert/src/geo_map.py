import streamlit as st
import folium
import json
import os
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
STATUS_COLORS = {"Evacuation Order":"#FF0000","Evacuation Warning":"#FF8C00","Shelter in Place":"#FFD700","Warning":"#FF8C00","Watch":"#FFD700","Normal":"#00AA44","":"#888888"}
STATUS_FILL_OPACITY = {"Evacuation Order":0.55,"Evacuation Warning":0.40,"Shelter in Place":0.35,"Warning":0.40,"Watch":0.30,"Normal":0.08,"":0.10}

def _geojson_path(filename):
    candidates = [os.path.join(_HERE, filename), os.path.join(_HERE,"..","01_raw_data","processed",filename), os.path.join(_HERE,"..","..","01_raw_data","processed",filename)]
    for p in candidates:
        real = os.path.realpath(p)
        if os.path.exists(real): return real
    return None

@st.cache_data(show_spinner=False)
def load_evac_zones():
    path = _geojson_path("evac_zones_map.geojson")
    if not path: return None
    with open(path) as f: return json.load(f)

@st.cache_data(show_spinner=False)
def load_fire_perimeters():
    path = _geojson_path("fire_perimeters_approved.geojson")
    if not path: return None
    with open(path) as f: return json.load(f)

def _status_color(status):
    for key in STATUS_COLORS:
        if key and key.lower() in str(status).lower(): return STATUS_COLORS[key]
    return "#888888"

def _status_opacity(status):
    for key in STATUS_FILL_OPACITY:
        if key and key.lower() in str(status).lower(): return STATUS_FILL_OPACITY[key]
    return 0.10

def build_evacuation_map(vulnerable_populations, fire_data, show_normal_zones=False, selected_state="All", height=550):
    m = folium.Map(location=[39.5,-98.5], zoom_start=4, tiles="CartoDB dark_matter")
    legend_html = """<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:rgba(20,20,30,0.92);padding:12px 16px;border-radius:8px;border:1px solid #444;font-size:12px;color:#eee;"><b>Evacuation Status</b><br><span style="color:#FF0000;">&#9632;</span> Evacuation Order<br><span style="color:#FF8C00;">&#9632;</span> Evacuation Warning<br><span style="color:#FFD700;">&#9632;</span> Watch / Shelter<br><span style="color:#FF6633;">&#9632;</span> Fire Perimeter<br><span style="color:#4B9FFF;">&#9632;</span> Vulnerable Population</div>"""
    m.get_root().html.add_child(folium.Element(legend_html))
    fire_perim_data = load_fire_perimeters()
    if fire_perim_data:
        pg = folium.FeatureGroup(name="Fire Perimeters", show=True)
        for feat in fire_perim_data.get("features", []):
            if not feat or not feat.get("geometry"): continue
            props = feat.get("properties", {})
            name = props.get("name") or "Fire Perimeter"
            date = str(props.get("date_modified",""))[:10]
            folium.GeoJson(feat, style_function=lambda x:{"color":"#FF6633","weight":2,"fillColor":"#FF4400","fillOpacity":0.30}, tooltip=folium.Tooltip(f"<b>{name}</b><br>Updated: {date}")).add_to(pg)
        pg.add_to(m)
    evac_data = load_evac_zones()
    if evac_data:
        og = folium.FeatureGroup(name="Evacuation Orders", show=True)
        wg = folium.FeatureGroup(name="Evacuation Warnings", show=True)
        wtg = folium.FeatureGroup(name="Watch / Shelter", show=True)
        ng = folium.FeatureGroup(name="Normal Zones", show=show_normal_zones)
        for feat in evac_data.get("features", []):
            if not feat or not feat.get("geometry"): continue
            props = feat.get("properties", {})
            status = str(props.get("status","Normal"))
            state = str(props.get("state",""))
            if selected_state != "All" and state != selected_state: continue
            c = _status_color(status); o = _status_opacity(status)
            gl = folium.GeoJson(feat, style_function=lambda x,c=c,o=o:{"color":c,"weight":1.5 if o>0.2 else 0.5,"fillColor":c,"fillOpacity":o}, tooltip=folium.Tooltip(f"{props.get('name','')} — {status} ({state})"))
            s = status.lower()
            if "order" in s: gl.add_to(og)
            elif "warning" in s: gl.add_to(wg)
            elif "watch" in s or "shelter" in s: gl.add_to(wtg)
            elif show_normal_zones: gl.add_to(ng)
        ng.add_to(m); wtg.add_to(m); wg.add_to(m); og.add_to(m)
    if vulnerable_populations:
        vpg = folium.FeatureGroup(name="Vulnerable Populations", show=True)
        for loc, data in list(vulnerable_populations.items())[:300]:
            svi = data.get("svi_score",0)
            folium.CircleMarker(location=[data["lat"],data["lon"]], radius=4+svi*8, color="#4B9FFF", fill=True, fillColor="#4B9FFF", fillOpacity=0.6, weight=1, tooltip=folium.Tooltip(f"<b>{loc}</b><br>Vulnerable: {data.get('vulnerable_count',0):,}<br>SVI: {svi:.3f}")).add_to(vpg)
        vpg.add_to(m)
    if fire_data is not None and len(fire_data)>0 and "latitude" in fire_data.columns:
        hg = folium.FeatureGroup(name="Live Fire Hotspots", show=True)
        display = fire_data.nlargest(150,"acres") if "acres" in fire_data.columns else fire_data.head(150)
        for _,fire in display.iterrows():
            folium.CircleMarker(location=[fire["latitude"],fire["longitude"]], radius=5, color="#FF2200", fill=True, fillColor="#FF6600", fillOpacity=0.85, weight=1, tooltip=folium.Tooltip(f"<b>{fire.get('fire_name','Active Fire')}</b><br>{fire.get('acres',0):,.0f} acres")).add_to(hg)
        hg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m

def render_map_with_controls(vulnerable_populations, fire_data, height=550):
    from streamlit_folium import st_folium
    evac_data = load_evac_zones()
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        states = ["All"]
        if evac_data:
            state_set = set()
            for feat in evac_data.get("features",[]):
                s = feat.get("properties",{}).get("state","")
                if s: state_set.add(s)
            states = ["All"] + sorted(state_set)
        selected_state = st.selectbox("Filter by State", states, key="map_state_filter")
    with col2:
        show_normal = st.checkbox("Show Normal Zones", value=False, key="map_show_normal")
    with col3:
        if evac_data:
            n = len(evac_data.get("features",[]))
            non_normal = sum(1 for f in evac_data.get("features",[]) if f and "normal" not in str(f.get("properties",{}).get("status","")).lower())
            st.caption(f"{n:,} evacuation zones loaded · {non_normal:,} active · Data: Genasys Protect / WiDS 2025")
        else:
            st.caption("GeoJSON not found — copy evac_zones_map.geojson to src/")
    with st.spinner("Rendering map..."):
        m = build_evacuation_map(vulnerable_populations, fire_data, show_normal_zones=show_normal, selected_state=selected_state, height=height)
    st_folium(m, width=None, height=height, returned_objects=[])
