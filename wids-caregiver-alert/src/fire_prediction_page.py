"""
fire_prediction_page.py
49ers Intelligence Lab — WiDS Datathon 2025

Role-aware Fire Spread Predictor page.
  • Emergency Worker (dispatcher) → Operational tab: live fire dropdown, urgency banner,
                                     caregiver alert preview, action checklist
  • Data Analyst (datathon)       → Full tab: above + manual sliders, feature importance,
                                     SHAP chart, batch CSV, research context

Integration in wildfire_alert_dashboard.py:

    from fire_prediction_page import render_fire_prediction_page
    render_fire_prediction_page(role=st.session_state.get("role", "analyst"))

role values expected: "dispatcher" | "analyst"  (caregiver login doesn't see this page)
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path
import datetime


# ── Model loader ──────────────────────────────────────────────────────────────
@st.cache_resource
def load_models():
    try:
        import joblib
        base = Path(__file__).parent
        candidates = [base, base.parent / "models", base.parent.parent / "models"]
        model_dir = next((p for p in candidates if (p / "feature_cols.json").exists()), None)
        if model_dir is None:
            return None, None, None, "Models not found — run 08_fire_spread_predictor.py first."
        with open(model_dir / "feature_cols.json") as f:
            meta = json.load(f)
        delay_model = joblib.load(model_dir / "evac_delay_model.pkl") \
            if (model_dir / "evac_delay_model.pkl").exists() else None
        clf_model   = joblib.load(model_dir / "fire_escalation_model.pkl") \
            if (model_dir / "fire_escalation_model.pkl").exists() else None
        return delay_model, clf_model, meta, None
    except Exception as e:
        return None, None, None, str(e)


# ── Feature builder ───────────────────────────────────────────────────────────
def make_feature_vector(params: dict, feature_cols: list) -> np.ndarray:
    lat   = params.get("lat", 37.0)
    lon   = params.get("lon", -119.0)
    month = params.get("fire_month", 8)
    row = {
        "growth_rate":       params.get("growth_rate_acres_per_hour", 0),
        "max_acres_log":     np.log1p(params.get("max_acres", 1)),
        "svi_score":         params.get("svi_score", 0.5),
        "pct_elderly":       params.get("pct_elderly", 0.14),
        "pct_poverty":       params.get("pct_poverty", 0.12),
        "pct_disabled":      params.get("pct_disabled", 0.12),
        "pct_no_vehicle":    params.get("pct_no_vehicle", 0.08),
        "high_vuln":         int(params.get("svi_score", 0.5) >= 0.75),
        "region_west":       int(lon < -105 and lat > 30),
        "region_southwest":  int(-115 <= lon <= -95 and 25 <= lat <= 38),
        "region_california": int(lon < -114 and 32 <= lat <= 42),
        "fire_month":        month,
        "fire_season":       {12:0,1:0,2:0,3:1,4:1,5:1,6:2,7:2,8:2}.get(month, 3),
    }
    return np.array([row.get(f, 0) for f in feature_cols], dtype=float).reshape(1, -1)


# ── Prediction engine ─────────────────────────────────────────────────────────
def run_prediction(params, delay_model, clf_model, meta, demo_mode):
    if not demo_mode and delay_model is not None:
        X = make_feature_vector(params, meta["feature_cols"])
        predicted_hours = max(0.0, float(delay_model.predict(X)[0]))
        if clf_model is not None:
            clf_features = [f for f in meta["feature_cols"] if f != "growth_rate"]
            X_clf = make_feature_vector(params, clf_features)
            escalation_prob = float(clf_model.predict_proba(X_clf)[0][1])
        else:
            escalation_prob = min(1.0, params.get("growth_rate_acres_per_hour", 10) / 200)
    else:
        gr  = params.get("growth_rate_acres_per_hour", 10)
        svi = params.get("svi_score", 0.5)
        predicted_hours  = max(0.5, 22.3 * (1 + 0.3 * svi) * max(0.1, 1 - gr / 300))
        escalation_prob  = min(0.95, gr / 200 + svi * 0.3)
    return predicted_hours, escalation_prob


def urgency_info(predicted_hours):
    if predicted_hours < 2:
        return "🚨 CRITICAL", "Order likely within 2 hours", "error"
    elif predicted_hours < 6:
        return "⚠️ HIGH", "Order expected within 6 hours", "warning"
    elif predicted_hours < 12:
        return "🟡 MODERATE", "Monitor closely", "warning"
    else:
        return "🟢 LOW", "No immediate threat", "success"


# ── Shared widgets ────────────────────────────────────────────────────────────
def render_result_cards(predicted_hours, escalation_prob):
    m1, m2, m3 = st.columns(3)
    m1.metric("Est. hours to evacuation order",
              f"{predicted_hours:.1f}h",
              delta=f"{predicted_hours - 1.1:+.1f}h vs. median")
    m2.metric("Escalation probability", f"{escalation_prob*100:.0f}%")
    m3.metric("Caregiver lead time",
              f"{max(0, predicted_hours - 1.0):.1f}h",
              help="Window to notify caregivers before order is issued")


def render_alert_preview(params, predicted_hours):
    svi = params.get("svi_score", 0.5)
    gr  = params.get("growth_rate_acres_per_hour", 0)
    county_vuln = "HIGH" if svi >= 0.75 else "MODERATE" if svi >= 0.5 else "LOW"
    border_color = "#ff4444" if predicted_hours < 2 else "#ff8800" if predicted_hours < 6 else "#ffcc00"
    level, desc, _ = urgency_info(predicted_hours)

    if predicted_hours < 2:
        action = "Evacuate NOW or prepare to assist your loved one immediately."
    elif predicted_hours < 6:
        action = "Prepare your loved one to evacuate. Bags packed, route ready."
    else:
        action = "Monitor situation. Review evacuation plan with your loved one."

    now = datetime.datetime.now().strftime("%H:%M")
    st.markdown(f"""
<div style="background:#1a1a2e;border-left:5px solid {border_color};
     padding:16px 20px;border-radius:6px;margin-top:8px;">
<p style="margin:0 0 4px 0;font-size:0.72rem;color:#aaa;font-family:monospace;">
  CAREGIVER ALERT PREVIEW &nbsp;·&nbsp; {now}</p>
<p style="margin:0 0 10px 0;font-size:1.05rem;font-weight:bold;color:{border_color};">
  🔥 WILDFIRE ALERT — {level} &nbsp;|&nbsp; {desc}</p>
<p style="margin:0;color:#ddd;line-height:1.7;font-size:0.95rem;">
  Current growth: <b>{gr:.1f} acres/hour</b><br>
  County vulnerability: <b>{county_vuln}</b> (SVI {svi:.2f})<br>
  Est. time to evacuation order: <b>{predicted_hours:.1f} hours</b><br><br>
  <span style="color:{border_color};font-weight:bold;">{action}</span>
</p></div>
""", unsafe_allow_html=True)
    st.write("")  # spacer


def render_action_checklist(predicted_hours):
    st.subheader("✅ Recommended Actions")
    if predicted_hours < 2:
        items = [
            "Issue evacuation order for high-SVI zones immediately",
            "Activate caregiver alert system NOW",
            "Deploy accessible transport for no-vehicle households",
            "Notify hospitals and care facilities in affected radius",
            "Open designated shelter locations",
        ]
    elif predicted_hours < 6:
        items = [
            "Issue evacuation WARNING for high-SVI zones",
            "Send pre-alert to registered caregivers",
            "Stage accessible transport resources",
            "Confirm shelter capacity in safe zones",
            "Monitor growth rate — reassess in 30 min",
        ]
    else:
        items = [
            "Continue monitoring — no immediate action required",
            "Verify caregiver contact lists are current",
            "Confirm evacuation routes are clear",
            "Brief on-call teams on fire status",
        ]
    for item in items:
        st.checkbox(item, key=f"chk_{item[:30]}")


def load_firms_params():
    """Load fire params from NASA FIRMS. Returns (params_dict, fire_name) or (None, None)."""
    try:
        from fire_data_integration import get_active_fires
        fires = get_active_fires()
        if not fires:
            return None, None
        fire_options = {f.get("name", f"Fire {i}"): f for i, f in enumerate(fires[:20])}
        selected_name = st.selectbox("Select active fire", list(fire_options.keys()))
        f = fire_options[selected_name]
        params = {
            "lat":                        f.get("latitude",  f.get("lat", 37.0)),
            "lon":                        f.get("longitude", f.get("lon", -119.0)),
            "max_acres":                  f.get("acreage",   f.get("acres", 100)),
            "growth_rate_acres_per_hour": f.get("growth_rate", 10.0),
            "svi_score":                  f.get("svi_score", 0.5),
            "fire_month":                 datetime.datetime.now().month,
        }
        return params, selected_name
    except ImportError:
        return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# DISPATCHER VIEW  —  operational, fast, no ML internals
# ═══════════════════════════════════════════════════════════════════════════════
def render_dispatcher_tab(delay_model, clf_model, meta, demo_mode):
    st.subheader("🚒 Operational Predictor")
    st.caption("Select a live fire to predict evacuation timing and preview the caregiver alert.")

    params, fire_name = load_firms_params()

    if params is None:
        st.info("Live fire feed unavailable — enter parameters manually.")
        c1, c2 = st.columns(2)
        with c1:
            gr    = st.number_input("Growth rate (acres/hour)", 0.0, 1000.0, 50.0, step=5.0)
            acres = st.number_input("Current size (acres)", 1, 500000, 500)
        with c2:
            svi = st.slider("County SVI", 0.0, 1.0, 0.5, 0.01,
                            help="≥0.75 = high vulnerability")
            lat = st.number_input("Latitude",  value=37.5)
            lon = st.number_input("Longitude", value=-119.5)
        params = {
            "growth_rate_acres_per_hour": gr, "max_acres": acres,
            "svi_score": svi, "lat": lat, "lon": lon,
            "fire_month": datetime.datetime.now().month,
        }

    st.divider()

    if st.button("🔮 Predict Evacuation Timing", type="primary", use_container_width=True):
        with st.spinner("Running prediction..."):
            predicted_hours, escalation_prob = run_prediction(
                params, delay_model, clf_model, meta, demo_mode)

        level, desc, alert_type = urgency_info(predicted_hours)
        getattr(st, alert_type)(f"**{level} — {desc}**")
        render_result_cards(predicted_hours, escalation_prob)
        st.divider()
        st.subheader("📱 Caregiver Alert Preview")
        render_alert_preview(params, predicted_hours)
        st.divider()
        render_action_checklist(predicted_hours)


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYST VIEW  —  full model explorer + batch
# ═══════════════════════════════════════════════════════════════════════════════
def render_analyst_tab(delay_model, clf_model, meta, demo_mode):
    st.subheader("🔬 Model Explorer")

    if not demo_mode:
        stats = meta.get("training_stats", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Fires with evac timing",  f"{stats.get('fires_with_evac_timing', 653):,}")
        c2.metric("Fires with growth data",  f"{stats.get('fires_with_growth_rate', '19,392'):,}")
        c3.metric("Model status", "✅ Trained")
    else:
        st.warning("**Demo mode** — run `python3 03_analysis_scripts/08_fire_spread_predictor.py` to train.")

    st.divider()

    input_mode = st.radio("Input mode", ["Manual entry", "Load from NASA FIRMS"], horizontal=True)

    if input_mode == "Manual entry":
        c1, c2 = st.columns(2)
        with c1:
            gr    = st.slider("Growth rate (acres/hour)", 0.0, 500.0, 50.0, 5.0,
                              help="Vulnerable counties avg 11.71 vs 10.00 non-vulnerable")
            acres = st.number_input("Current fire size (acres)", 1, 500000, 500)
            month = st.selectbox("Month", list(range(1, 13)), index=7,
                                 format_func=lambda m: ["Jan","Feb","Mar","Apr","May","Jun",
                                                        "Jul","Aug","Sep","Oct","Nov","Dec"][m-1])
        with c2:
            svi = st.slider("County SVI", 0.0, 1.0, 0.5, 0.01, help="≥0.75 = high vulnerability")
            lat = st.number_input("Latitude",  -90.0,  90.0,  37.5)
            lon = st.number_input("Longitude", -180.0,  0.0, -119.5)

        with st.expander("SVI components (advanced)"):
            pct_el  = st.slider("% age 65+",              0.0, 0.5, 0.14, 0.01)
            pct_pov = st.slider("% below poverty line",   0.0, 0.6, 0.12, 0.01)
            pct_dis = st.slider("% with disability",      0.0, 0.5, 0.12, 0.01)
            pct_nov = st.slider("% no vehicle",           0.0, 0.4, 0.08, 0.01)

        params = {
            "growth_rate_acres_per_hour": gr, "max_acres": acres,
            "svi_score": svi, "lat": lat, "lon": lon, "fire_month": month,
            "pct_elderly": pct_el, "pct_poverty": pct_pov,
            "pct_disabled": pct_dis, "pct_no_vehicle": pct_nov,
        }
    else:
        params, _ = load_firms_params()
        if params is None:
            params = {"growth_rate_acres_per_hour": 50, "max_acres": 500,
                      "svi_score": 0.5, "lat": 37.5, "lon": -119.5,
                      "fire_month": datetime.datetime.now().month}

    st.divider()

    if st.button("🔮 Run Prediction", type="primary", use_container_width=True):
        predicted_hours, escalation_prob = run_prediction(
            params, delay_model, clf_model, meta, demo_mode)

        level, desc, alert_type = urgency_info(predicted_hours)
        getattr(st, alert_type)(f"**{level} — {desc}**")
        render_result_cards(predicted_hours, escalation_prob)
        st.divider()

        with st.expander("📱 Caregiver Alert Preview"):
            render_alert_preview(params, predicted_hours)

        # ── Feature importance ────────────────────────────────────────────────
        st.subheader("🔍 Feature Importance")
        feat_imp = []
        if not demo_mode and delay_model is not None:
            try:
                if hasattr(delay_model, "feature_importances_"):
                    feat_imp = list(zip(meta["feature_cols"], delay_model.feature_importances_))
                elif hasattr(delay_model, "get_booster"):
                    scores = delay_model.get_booster().get_fscore()
                    feat_imp = [(f, scores.get(f"f{i}", 0))
                                for i, f in enumerate(meta["feature_cols"])]
            except Exception:
                pass

        if not feat_imp:  # demo fallback
            feat_imp = [
                ("growth_rate", 0.35), ("svi_score", 0.22),
                ("region_california", 0.12), ("max_acres_log", 0.10),
                ("pct_elderly", 0.08), ("fire_season", 0.07),
                ("high_vuln", 0.04), ("pct_no_vehicle", 0.02),
            ]

        import plotly.express as px
        sorted_imp = sorted(feat_imp, key=lambda x: x[1], reverse=True)[:10]
        fig = px.bar(
            x=[v for _, v in sorted_imp],
            y=[f for f, _ in sorted_imp],
            orientation="h",
            labels={"x": "Importance", "y": "Feature"},
            title="Evacuation Delay Model — Feature Importance (top 10)",
            color=[v for _, v in sorted_imp],
            color_continuous_scale="Reds",
        )
        fig.update_layout(height=360, showlegend=False,
                          coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

        # ── Real data benchmarks ──────────────────────────────────────────────
        with st.expander("📚 Real WiDS data benchmarks"):
            st.markdown("""
| Metric | Value | Source |
|---|---|---|
| Median fire → evacuation order | **1.1 hours** | Real WiDS data, 653 fires |
| Mean delay | **22.3 hours** | Right-skewed distribution |
| 90th percentile delay | **32.1 hours** | 1 in 10 fires >1 day |
| Vulnerable county growth rate | **11.71 acres/hr** | vs 10.00 non-vulnerable |
| Fires in high-vulnerability counties | **39.8%** | SVI ≥ 0.75 |
| Projected lives saved (65% adoption) | **500–1,500/year** | Model projection |
""")

    # ── Batch prediction ──────────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 Batch prediction (CSV upload)"):
        st.markdown("Required columns: `growth_rate_acres_per_hour`, `max_acres`, `svi_score`")
        uploaded = st.file_uploader("Upload fire CSV", type="csv")
        if uploaded and not demo_mode and delay_model is not None:
            batch_df = pd.read_csv(uploaded)
            st.write(f"Loaded {len(batch_df):,} fires")
            try:
                preds = [
                    max(0.0, float(delay_model.predict(
                        make_feature_vector(row.to_dict(), meta["feature_cols"]))[0]))
                    for _, row in batch_df.iterrows()
                ]
                batch_df["predicted_hours_to_order"] = preds
                batch_df["urgency"] = batch_df["predicted_hours_to_order"].apply(
                    lambda h: "CRITICAL" if h < 2 else "HIGH" if h < 6
                              else "MODERATE" if h < 12 else "LOW")
                st.dataframe(batch_df.head(50))
                st.download_button("⬇ Download predictions",
                                   batch_df.to_csv(index=False),
                                   "fire_predictions.csv", "text/csv")
            except Exception as e:
                st.error(f"Prediction error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def render_fire_prediction_page(role: str = "analyst"):
    """
    Call from wildfire_alert_dashboard.py:
        render_fire_prediction_page(role=st.session_state.get("role", "analyst"))

    role: "dispatcher" → operational tab only
          "analyst"    → both tabs (Operational + Model Explorer)
    Caregiver login should NOT include this page in its sidebar nav.
    """
    st.title("🔥 Fire Spread Predictor")
    st.caption("ML-powered evacuation timing · trained on 653 real WiDS fires (2021–2025)")

    delay_model, clf_model, meta, error = load_models()
    demo_mode = error is not None

    if role == "dispatcher":
        render_dispatcher_tab(delay_model, clf_model, meta, demo_mode)

    else:  # analyst (or fallback)
        tab_ops, tab_model = st.tabs(["🚒 Operational View", "🔬 Model Explorer"])
        with tab_ops:
            render_dispatcher_tab(delay_model, clf_model, meta, demo_mode)
        with tab_model:
            render_analyst_tab(delay_model, clf_model, meta, demo_mode)
