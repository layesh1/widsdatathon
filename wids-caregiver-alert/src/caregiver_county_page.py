"""
caregiver_county_page.py — My County (Caregiver view)
Plain-language local fire risk stats for caregivers.
"""
from pathlib import Path
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def _load_county_data():
    base = Path(__file__).parent.parent.parent / "01_raw_data" / "processed"
    stats = pd.read_csv(base / "county_fire_stats.csv")
    channels = pd.read_csv(base / "county_channel_coverage.csv")
    gi = pd.read_csv(base / "county_gi_star.csv")
    # Normalise merge key
    for df in (stats, channels, gi):
        df["_key"] = df["county_name"].str.strip() + "|" + df["state"].str.strip()
    merged = stats.merge(
        channels[["_key", "n_channels"]],
        on="_key", how="left"
    ).merge(
        gi[["_key", "gi_star", "cluster"]],
        on="_key", how="left"
    )
    return merged


def render_caregiver_county_page():
    st.title("📊 My County")
    st.caption("Local wildfire risk stats — explained in plain language")

    try:
        df = _load_county_data()
    except Exception as e:
        st.error(f"Could not load county data: {e}")
        return

    # Build county list
    counties = sorted(df["county_name"].dropna().unique())
    county_options = [f"{row['county_name']}, {row['state']}" for _, row in
                      df[["county_name", "state"]].drop_duplicates().sort_values(["state", "county_name"]).iterrows()]

    # Default to session state county if caregiver entered their address
    default_idx = 0
    ss_county = st.session_state.get("selected_county", "")
    if ss_county:
        matches = [i for i, c in enumerate(county_options) if ss_county.lower() in c.lower()]
        if matches:
            default_idx = matches[0]

    selected = st.selectbox("Select your county", county_options, index=default_idx)
    county_name, state = selected.rsplit(", ", 1)

    row = df[(df["county_name"] == county_name) & (df["state"] == state)]
    if row.empty:
        st.warning("No data found for this county.")
        return
    row = row.iloc[0]

    pct_silent = row.get("pct_silent", None)
    total_fires = int(row.get("total_fires", 0))
    pct_evac = row.get("pct_evac", None)
    extreme = int(row.get("extreme_fires", 0))
    svi = row.get("svi_score", None)
    pop_age65 = row.get("pop_age65", None)
    pop_disability = row.get("pop_disability", None)
    n_channels = row.get("n_channels", None)
    gi_star = row.get("gi_star", None)
    cluster = row.get("cluster", "Not Significant")

    st.divider()

    # ── Headline stats ────────────────────────────────────────────────────────
    st.subheader(f"🔥 Fire Activity in {county_name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total fires (2021–2025)", f"{total_fires:,}")
    if pct_silent is not None:
        silent_pct = round(pct_silent * 100, 1)
        c2.metric("Fires with NO public alert", f"{silent_pct}%")
    if pct_evac is not None:
        evac_pct = round(pct_evac * 100, 1)
        c3.metric("Fires with evacuation action", f"{evac_pct}%")

    # Plain-language silent fire callout
    if pct_silent is not None:
        ratio_num = round(pct_silent * 10)
        st.info(
            f"**About {ratio_num} out of every 10 fires** in {county_name} "
            f"happened with **no public warning** — no alert, no evacuation order."
        )

    # ── Vulnerability badge ───────────────────────────────────────────────────
    st.divider()
    st.subheader("🏘️ Community Vulnerability")

    if svi is not None:
        if svi >= 0.75:
            badge_color = "#AA0000"
            badge_text = "HIGH VULNERABILITY"
            plain = f"**{county_name} is in the top 25% most vulnerable counties** in the US — meaning residents here have more barriers to evacuating quickly."
        elif svi >= 0.50:
            badge_color = "#d97706"
            badge_text = "MODERATE VULNERABILITY"
            plain = f"**{county_name} has moderate vulnerability.** Some residents may face barriers evacuating quickly."
        else:
            badge_color = "#16a34a"
            badge_text = "LOWER VULNERABILITY"
            plain = f"**{county_name} has relatively lower vulnerability** compared to the national average."

        st.markdown(
            f"<div style='background:{badge_color}18;border-left:4px solid {badge_color};"
            f"padding:0.7rem 1rem;border-radius:6px;margin-bottom:0.6rem'>"
            f"<span style='color:{badge_color};font-weight:700;font-size:0.8rem'>"
            f"SVI: {svi:.2f} — {badge_text}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(plain)

    # Vulnerable population numbers
    pop_items = []
    if pop_age65 and pop_age65 > 0:
        pop_items.append(f"**{int(pop_age65):,}** residents aged 65+")
    if pop_disability and pop_disability > 0:
        pop_items.append(f"**{int(pop_disability):,}** residents with a disability")
    if pop_items:
        st.markdown("In this county: " + " · ".join(pop_items))

    # ── Alert channels ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📡 Alert System Coverage")

    if n_channels is not None and not pd.isna(n_channels):
        n_ch = int(n_channels)
        if n_ch == 1:
            ch_color = "#AA0000"
            ch_label = "⚠️ Concerning — single point of failure"
            ch_plain = f"**Your county has only 1 alert channel.** If that system fails, residents may not receive any warning."
        elif n_ch == 2:
            ch_color = "#d97706"
            ch_label = "Fair — limited redundancy"
            ch_plain = f"**Your county has {n_ch} alert channels.** Some redundancy, but gaps are still possible."
        else:
            ch_color = "#16a34a"
            ch_label = "Good — multiple channels"
            ch_plain = f"**Your county has {n_ch} alert channels** — better coverage reduces the risk of missed alerts."

        st.markdown(
            f"<div style='background:{ch_color}18;border-left:4px solid {ch_color};"
            f"padding:0.7rem 1rem;border-radius:6px;margin-bottom:0.6rem'>"
            f"<span style='color:{ch_color};font-weight:700'>{n_ch} alert channel{'s' if n_ch != 1 else ''}</span>"
            f" &nbsp;·&nbsp; <span style='color:{ch_color};font-size:0.8rem'>{ch_label}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(ch_plain)
    else:
        st.markdown("Alert channel data not available for this county.")

    # ── Hotspot status ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🗺️ Fire Hotspot Status")

    if gi_star is not None and not pd.isna(gi_star):
        cluster_str = str(cluster) if cluster else "Not Significant"
        if "High" in cluster_str:
            st.error(
                f"⚠️ **{county_name} is a statistically significant high-risk hotspot.** "
                f"This county has both high silent fire rates AND high population vulnerability — "
                f"the combination most likely to leave caregivers without warning."
            )
        elif "Low" in cluster_str:
            st.success(
                f"✅ **{county_name} is in a statistically significant low-risk zone** "
                f"based on fire activity and community vulnerability."
            )
        else:
            st.info(
                f"**{county_name} does not fall in a statistically significant hotspot.** "
                f"Risk is present but not clustered compared to neighboring counties."
            )
    else:
        st.info("Hotspot analysis data not available for this county.")

    # ── Extreme fires ─────────────────────────────────────────────────────────
    if extreme > 0:
        st.divider()
        st.subheader("🚀 Fast-Moving Fires")
        st.warning(
            f"**{extreme} extremely fast-spreading fire{'s' if extreme != 1 else ''}** "
            f"{'were' if extreme != 1 else 'was'} recorded in {county_name}. "
            f"These fires can outpace evacuation orders — which is exactly why this app exists."
        )

    # ── Call to action ────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<div style='background:#AA000010;border:1px solid #AA000030;"
        "border-radius:10px;padding:1.2rem 1.4rem;text-align:center'>"
        "<div style='font-size:1.1rem;font-weight:700;color:#AA0000;margin-bottom:0.5rem'>"
        "Register your household for caregiver alerts</div>"
        "<div style='font-size:0.88rem;opacity:0.8'>"
        "Emergency workers use this registry to prioritize evacuation assistance "
        "for people with mobility challenges, medical equipment, or other special needs."
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("")
    if st.button("➕ Add my household to the caregiver registry", type="primary",
                 use_container_width=True):
        st.session_state.current_page = "Am I Safe?"
        st.rerun()
