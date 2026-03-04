"""
dispatcher_resources_page.py — Resources (Emergency Worker view)
Fire department directory from USFA National Registry.
Extracted from command_dashboard_page.py Tab 3.
"""
from pathlib import Path
import streamlit as st
import pandas as pd


@st.cache_data(ttl=3600, show_spinner=False)
def _load_usfa():
    for p in [
        Path("usfa-registry-national.csv"),
        Path("src/usfa-registry-national.csv"),
        Path("01_raw_data/usfa-registry-national.csv"),
        Path("../01_raw_data/usfa-registry-national.csv"),
    ]:
        if p.exists():
            try:
                return pd.read_csv(p, low_memory=False)
            except Exception:
                pass
    # Try USFA API as last resort
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
            try:
                df.to_csv(Path("usfa-registry-national.csv"), index=False)
            except Exception:
                pass
            return df
    except Exception:
        pass
    return None


def render_dispatcher_resources_page():
    st.title("🏠 Resources")
    st.caption("Fire department directory — USFA National Registry")

    usfa_df = _load_usfa()

    if usfa_df is None:
        st.warning(
            "**USFA National Fire Department Registry not loaded.**\n\n"
            "Download the CSV from "
            "[apps.usfa.fema.gov/registry/download](https://apps.usfa.fema.gov/registry/download) "
            "and save it as `usfa-registry-national.csv` in the `src/` directory."
        )
        st.link_button(
            "Download USFA Registry CSV",
            "https://apps.usfa.fema.gov/registry/download",
            help="Save the downloaded file as usfa-registry-national.csv in wids-caregiver-alert/src/",
        )

        # Show known aggregate statistics even without the file
        st.subheader("USFA Registry — Known Aggregate Statistics")
        u1, u2, u3 = st.columns(3)
        u1.metric("Registered Departments", "27,000+", help="Source: USFA Quick Facts")
        u2.metric("Career Firefighters", "~370,000", help="USFA estimate")
        u3.metric("Volunteer Dept Share", "~69%", help="USFA 2023 estimate")

        st.markdown("""
**Top fire-prone states by department count (USFA estimates):**

| State | Est. Departments |
|-------|-----------------|
| Texas | ~2,500 |
| California | ~1,200 |
| Pennsylvania | ~2,200 |
| New York | ~2,000 |
| Ohio | ~1,500 |
""")
        return

    # File loaded — show search interface
    usfa_df.columns = [c.lower().strip() for c in usfa_df.columns]
    st.success(f"Loaded {len(usfa_df):,} fire department records")

    col1, col2 = st.columns(2)
    with col1:
        states = sorted(usfa_df["hq_state"].dropna().unique()) if "hq_state" in usfa_df.columns else []
        sel_state = st.selectbox("State", ["All"] + states, key="usfa_state_res")
    with col2:
        dept_types = (
            ["All"] + sorted(usfa_df["dept_type"].dropna().unique().tolist())
            if "dept_type" in usfa_df.columns else ["All"]
        )
        sel_type = st.selectbox("Department Type", dept_types, key="usfa_type_res")

    search_term = st.text_input("Search by county or department name", key="usfa_search_res")

    fdf = usfa_df.copy()
    if sel_state != "All" and "hq_state" in fdf.columns:
        fdf = fdf[fdf["hq_state"] == sel_state]
    if sel_type != "All" and "dept_type" in fdf.columns:
        fdf = fdf[fdf["dept_type"] == sel_type]
    if search_term:
        mask = pd.Series([False] * len(fdf), index=fdf.index)
        for col in ["dept_name", "hq_county", "hq_city"]:
            if col in fdf.columns:
                mask |= fdf[col].fillna("").str.contains(search_term, case=False, na=False)
        fdf = fdf[mask]

    st.caption(f"Showing {len(fdf):,} of {len(usfa_df):,} departments")

    display_cols = [c for c in [
        "dept_name", "hq_city", "hq_county", "hq_state",
        "dept_type", "num_career", "num_volunteer",
    ] if c in fdf.columns]

    st.dataframe(fdf[display_cols].head(500), use_container_width=True, hide_index=True)
