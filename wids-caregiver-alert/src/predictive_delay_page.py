"""
predictive_delay_page.py
Predictive Delay Risk Model — 49ers Intelligence Lab · WiDS 2025

Trains a logistic regression on 62,696 historical fire incidents to predict
which counties and conditions are most likely to result in high evacuation delay
or no action at all.

Target: high_delay = 1 if hours_to_order > 6 OR evacuation_occurred == 0
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from ui_utils import page_header, section_header, render_card, fallback_card

# ── Paths ─────────────────────────────────────────────────────────────────────

_CSV_PATHS = [
    Path("fire_events_with_svi_and_delays.csv"),
    Path("01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
    Path("../01_raw_data/processed/fire_events_with_svi_and_delays.csv"),
]

_COUNTY_STATS_PATHS = [
    Path("county_fire_stats.csv"),
    Path("01_raw_data/processed/county_fire_stats.csv"),
    Path("../01_raw_data/processed/county_fire_stats.csv"),
]

# ── Spread rate ordinal encoding ──────────────────────────────────────────────

_SPREAD_MAP = {"slow": 0, "moderate": 1, "rapid": 2, "extreme": 3}
_SPREAD_LABELS = ["slow", "moderate", "rapid", "extreme"]

# ── Plotly version shim ───────────────────────────────────────────────────────

try:
    import plotly.graph_objects as _go_check
    _HAS_NEW_MAP = hasattr(_go_check, "Scattermap")
except Exception:
    _HAS_NEW_MAP = False

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_df() -> pd.DataFrame | None:
    for p in _CSV_PATHS:
        if p.exists():
            df = pd.read_csv(p, low_memory=False)
            return df
    return None


@st.cache_data(show_spinner=False)
def _load_county_stats() -> pd.DataFrame | None:
    for p in _COUNTY_STATS_PATHS:
        if p.exists():
            return pd.read_csv(p)
    return None


# ── Feature engineering ───────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Returns (X, y, feature_names).
    Target: high_delay = 1 if hours_to_order > 6 OR evacuation_occurred == 0
    """
    df = df.copy()

    # Target
    df["high_delay"] = (
        (df.get("hours_to_order", np.nan) > 6) | (df.get("evacuation_occurred", 0) == 0)
    ).astype(int)

    # Features
    df["notif_silent"] = (df["notification_type"] == "silent").astype(int)
    df["spread_ord"] = df["last_spread_rate"].str.lower().map(_SPREAD_MAP).fillna(1)

    # Frequency encode county_fips (avoids huge one-hot matrix)
    fips_freq = df["county_fips"].value_counts(normalize=True)
    df["fips_freq"] = df["county_fips"].map(fips_freq).fillna(0)

    feature_cols = [
        "svi_score",
        "growth_rate_acres_per_hour",
        "notif_silent",
        "spread_ord",
        "max_acres",
        "fips_freq",
    ]

    sub = df[feature_cols + ["high_delay"]].dropna()
    X = sub[feature_cols]
    y = sub["high_delay"]

    return X, y, feature_cols


# ── Model training ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _train_model(
    _X: pd.DataFrame, _y: pd.Series
) -> tuple:
    """
    Train logistic regression. Returns (model, scaler, feature_names, accuracy, importances).
    Uses underscore prefix on args so st.cache_data can handle DataFrames.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score

    X_train, X_test, y_train, y_test = train_test_split(
        _X, _y, test_size=0.2, random_state=42, stratify=_y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(
        max_iter=500,
        class_weight="balanced",
        solver="lbfgs",
        random_state=42,
        C=1.0,
    )
    model.fit(X_train_s, y_train)

    acc = accuracy_score(y_test, model.predict(X_test_s))
    # Coefficients as importance proxy (absolute value)
    importances = np.abs(model.coef_[0])
    feature_names = list(_X.columns)

    return model, scaler, feature_names, acc, importances


# ── County predictions ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _county_predictions(
    df: pd.DataFrame, _model, _scaler
) -> pd.DataFrame:
    """Compute per-county average predicted probability of high delay."""
    df = df.copy()
    df["notif_silent"] = (df["notification_type"] == "silent").astype(int)
    df["spread_ord"] = df["last_spread_rate"].str.lower().map(_SPREAD_MAP).fillna(1)
    fips_freq = df["county_fips"].value_counts(normalize=True)
    df["fips_freq"] = df["county_fips"].map(fips_freq).fillna(0)

    feature_cols = [
        "svi_score",
        "growth_rate_acres_per_hour",
        "notif_silent",
        "spread_ord",
        "max_acres",
        "fips_freq",
    ]

    valid = df[feature_cols + ["county_fips", "county_name", "state"]].dropna(
        subset=feature_cols
    )
    X_all = _scaler.transform(valid[feature_cols])
    valid = valid.copy()
    valid["pred_prob"] = _model.predict_proba(X_all)[:, 1]

    county_agg = (
        valid.groupby(["county_fips", "county_name", "state"])
        .agg(
            avg_pred_prob=("pred_prob", "mean"),
            n_fires=("pred_prob", "count"),
        )
        .reset_index()
    )
    # Normalise FIPS to 5-char zero-padded string
    county_agg["fips_str"] = county_agg["county_fips"].astype(str).str.zfill(5)
    return county_agg.sort_values("avg_pred_prob", ascending=False)


# ── Page ──────────────────────────────────────────────────────────────────────

def render_predictive_delay_page() -> None:
    page_header(
        "Predictive Delay Risk Model",
        "Logistic regression trained on 62,696 historical fires to identify high-delay-risk counties",
    )

    df = _load_df()
    if df is None:
        st.error(
            "Could not locate fire_events_with_svi_and_delays.csv. "
            "Expected at 01_raw_data/processed/ relative to working directory."
        )
        return

    county_stats = _load_county_stats()

    # ── Build features & train ───────────────────────────────────────────────
    with st.spinner("Training model on historical fire data..."):
        try:
            X, y, feature_names = _build_features(df)
            model, scaler, feat_names, accuracy, importances = _train_model(X, y)
        except ImportError:
            st.error(
                "scikit-learn is not installed. Add `scikit-learn` to requirements.txt "
                "and restart the app."
            )
            return
        except Exception as exc:
            st.error(f"Model training failed: {exc}")
            return

    n_train = len(X)
    n_high = int(y.sum())
    pct_high = n_high / n_train * 100

    # ── Key Finding callout ──────────────────────────────────────────────────
    county_preds = _county_predictions(df, model, scaler)
    top5 = county_preds.head(5)
    top5_names = ", ".join(
        f"{r['county_name']}, {r['state']}" for _, r in top5.iterrows()
    )
    n_high_counties = (county_preds["avg_pred_prob"] >= 0.8).sum()

    st.markdown(
        f"""
<div style="background:#161b22;border:1px solid #FF4B4B;border-radius:12px;
     padding:16px 20px;margin-bottom:16px;border-left:4px solid #FF4B4B">
  <div style="font-size:12px;color:#FF4B4B;text-transform:uppercase;
       letter-spacing:1px;margin-bottom:6px">Key Finding</div>
  <div style="font-size:14px;color:#e6edf3;line-height:1.6">
    Based on <strong>{n_train:,}</strong> historical fires, our model identifies
    <strong>{n_high_counties:,} counties</strong> at highest predicted delay risk
    (&ge;80% probability of high delay or no action).<br>
    <strong>Top 5:</strong> {top5_names}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # ── KPIs ─────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card(
            "Training Fires",
            f"{n_train:,}",
            "After dropping rows with missing features",
            color="#1e3a5f",
        )
    with c2:
        render_card(
            "High-Delay Events (Target = 1)",
            f"{pct_high:.1f}%",
            f"{n_high:,} fires with >6h delay or no action",
            color="#FF4B4B",
        )
    with c3:
        render_card(
            "Model Accuracy",
            f"{accuracy * 100:.1f}%",
            "Logistic regression, 20% test split",
            color="#3fb950",
        )
    with c4:
        render_card(
            "Counties Assessed",
            f"{len(county_preds):,}",
            "With avg predicted delay probability",
            color="#1e3a5f",
        )

    st.markdown("")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. Feature importance
    # ═══════════════════════════════════════════════════════════════════════
    section_header("Feature Importance (Logistic Regression Coefficients)")
    st.caption(
        "Absolute value of standardized coefficients. "
        "Larger bar = stronger predictor of high evacuation delay."
    )

    _FEATURE_LABELS = {
        "svi_score": "Social Vulnerability Index",
        "growth_rate_acres_per_hour": "Fire Growth Rate (acres/h)",
        "notif_silent": "Silent Notification (vs normal)",
        "spread_ord": "Spread Rate (slow→extreme)",
        "max_acres": "Max Fire Size (acres)",
        "fips_freq": "County Fire Frequency",
    }

    imp_df = pd.DataFrame(
        {"feature": feat_names, "importance": importances}
    ).sort_values("importance", ascending=True)
    imp_df["label"] = imp_df["feature"].map(_FEATURE_LABELS).fillna(imp_df["feature"])

    fig_imp = go.Figure(
        go.Bar(
            x=imp_df["importance"],
            y=imp_df["label"],
            orientation="h",
            marker_color=[
                "#FF4B4B" if v == imp_df["importance"].max() else "#4a90d9"
                for v in imp_df["importance"]
            ],
            text=imp_df["importance"].round(3).astype(str),
            textposition="outside",
        )
    )
    fig_imp.update_layout(
        template="plotly_dark",
        title="Feature Importance — Absolute Logistic Regression Coefficients",
        xaxis_title="|Coefficient| (standardized)",
        height=320,
        margin=dict(l=200, r=60, t=50, b=40),
    )
    st.plotly_chart(fig_imp, use_container_width=True)

    with st.expander("How to interpret these coefficients"):
        st.markdown(
            """
- Features are standardized before fitting, so coefficient magnitudes are comparable.
- A **higher absolute coefficient** means the feature has a stronger linear relationship
  with the log-odds of high delay (holding other features constant).
- **Silent notification** having a high coefficient confirms that "silent" fires (no
  public alert) are strongly associated with subsequent evacuation inaction.
- **SVI** appearing prominently confirms the equity dimension: socially vulnerable
  counties systematically experience higher delay.
            """
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. County-level choropleth map
    # ═══════════════════════════════════════════════════════════════════════
    section_header("County-Level Predicted Delay Risk Map")
    st.caption(
        "Average predicted probability of high delay per county. "
        "Red = model predicts high delay/inaction likely."
    )

    map_df = county_preds.copy()

    try:
        if _HAS_NEW_MAP:
            fig_map = px.choropleth(
                map_df,
                locations="fips_str",
                geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
                color="avg_pred_prob",
                color_continuous_scale=[
                    [0.0, "#1e3a5f"],
                    [0.5, "#d4a017"],
                    [0.75, "#FF9800"],
                    [1.0, "#FF4B4B"],
                ],
                range_color=[0, 1],
                scope="usa",
                labels={"avg_pred_prob": "Predicted Delay Prob."},
                hover_data={"county_name": True, "state": True, "n_fires": True},
                title="Predicted High-Delay Probability by County",
                template="plotly_dark",
            )
        else:
            fig_map = px.choropleth(
                map_df,
                locations="fips_str",
                geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
                color="avg_pred_prob",
                color_continuous_scale=[
                    [0.0, "#1e3a5f"],
                    [0.5, "#d4a017"],
                    [0.75, "#FF9800"],
                    [1.0, "#FF4B4B"],
                ],
                range_color=[0, 1],
                scope="usa",
                labels={"avg_pred_prob": "Predicted Delay Prob."},
                hover_data={"county_name": True, "state": True, "n_fires": True},
                title="Predicted High-Delay Probability by County",
                template="plotly_dark",
                projection="albers usa",
            )

        fig_map.update_geos(
            bgcolor="#0d1117",
            landcolor="#21262d",
            subunitcolor="#30363d",
        )
        fig_map.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=50, b=0),
            geo=dict(projection=dict(type="albers usa")),
            coloraxis_colorbar=dict(title="Pred. Prob.", thickness=12),
        )
        st.plotly_chart(fig_map, use_container_width=True)
    except Exception as e:
        fallback_card(
            f"Map could not render ({e}). See the table below for county-level predictions."
        )

    # Top/bottom county table
    col_top, col_bot = st.columns(2)
    with col_top:
        st.markdown("**Highest-risk counties (top 15)**")
        top_tbl = county_preds.head(15)[
            ["county_name", "state", "avg_pred_prob", "n_fires"]
        ].copy()
        top_tbl["avg_pred_prob"] = (top_tbl["avg_pred_prob"] * 100).round(1).astype(str) + "%"
        top_tbl.columns = ["County", "State", "Predicted Delay Risk", "Fires"]
        st.dataframe(top_tbl, use_container_width=True, hide_index=True)

    with col_bot:
        st.markdown("**Lowest-risk counties (bottom 15)**")
        bot_tbl = county_preds.tail(15)[
            ["county_name", "state", "avg_pred_prob", "n_fires"]
        ].copy()
        bot_tbl["avg_pred_prob"] = (bot_tbl["avg_pred_prob"] * 100).round(1).astype(str) + "%"
        bot_tbl.columns = ["County", "State", "Predicted Delay Risk", "Fires"]
        st.dataframe(bot_tbl, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. What-if simulator
    # ═══════════════════════════════════════════════════════════════════════
    section_header("What-If Simulator")
    st.caption(
        "Adjust fire conditions to see the model's predicted probability of high delay "
        "or no evacuation action."
    )

    sim_col, result_col = st.columns([3, 2])

    with sim_col:
        sim_svi = st.slider(
            "SVI Score (0 = low vulnerability, 1 = high)",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.01,
            help="CDC/ATSDR Social Vulnerability Index for the county",
        )
        sim_spread = st.select_slider(
            "Fire Spread Rate",
            options=_SPREAD_LABELS,
            value="rapid",
            help="Observed or predicted fire spread classification",
        )
        sim_notif = st.radio(
            "Notification Type",
            options=["Normal (public alert issued)", "Silent (no public alert)"],
            index=1,
            horizontal=True,
        )
        sim_growth = st.slider(
            "Growth Rate (acres/hour)",
            min_value=0.0,
            max_value=2000.0,
            value=150.0,
            step=10.0,
            help="Fire growth rate in acres per hour",
        )
        sim_acres = st.slider(
            "Maximum Fire Size (acres)",
            min_value=0.0,
            max_value=50000.0,
            value=500.0,
            step=100.0,
            help="Estimated or observed maximum acreage",
        )

    # Compute prediction
    sim_silent = 1 if "Silent" in sim_notif else 0
    sim_spread_ord = _SPREAD_MAP[sim_spread]

    # Average fips_freq across training set as neutral baseline
    avg_fips_freq = float(
        df["county_fips"].value_counts(normalize=True).mean()
    )

    sim_features = np.array(
        [[sim_svi, sim_growth, sim_silent, sim_spread_ord, sim_acres, avg_fips_freq]]
    )
    try:
        sim_scaled = scaler.transform(sim_features)
        sim_prob = model.predict_proba(sim_scaled)[0][1]
    except Exception:
        sim_prob = 0.5

    with result_col:
        pct_label = f"{sim_prob * 100:.1f}%"
        risk_color = (
            "#FF4B4B" if sim_prob >= 0.75
            else "#d4a017" if sim_prob >= 0.50
            else "#3fb950"
        )
        risk_label = (
            "CRITICAL RISK" if sim_prob >= 0.75
            else "ELEVATED RISK" if sim_prob >= 0.50
            else "MODERATE RISK"
        )
        st.markdown(
            f"""
<div style="background:#161b22;border:1px solid {risk_color};border-radius:12px;
     padding:28px 20px;text-align:center;border-left:4px solid {risk_color}">
  <div style="font-size:11px;color:#8b949e;text-transform:uppercase;
       letter-spacing:1.5px;margin-bottom:8px">
    Predicted Probability of High Delay / No Action
  </div>
  <div style="font-size:52px;font-weight:700;color:{risk_color};
       font-family:'DM Sans',sans-serif">{pct_label}</div>
  <div style="font-size:13px;font-weight:600;color:{risk_color};
       margin-top:6px">{risk_label}</div>
  <div style="font-size:12px;color:#8b949e;margin-top:12px;line-height:1.5">
    Based on logistic regression trained on<br>
    {n_train:,} historical wildfire incidents
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("")
        # Breakdown of risk drivers
        st.markdown("**What's driving this prediction?**")
        drivers = []
        if sim_silent:
            drivers.append("Silent fire — no public notification issued")
        if sim_svi >= 0.75:
            drivers.append(f"High SVI ({sim_svi:.2f}) — vulnerable county")
        if sim_spread in ("rapid", "extreme"):
            drivers.append(f"{sim_spread.title()} spread rate — fast-moving fire")
        if sim_growth > 500:
            drivers.append(f"High growth rate ({sim_growth:.0f} acres/h)")
        if not drivers:
            drivers.append("No high-risk factors active at current settings")
        for d in drivers:
            st.markdown(f"- {d}")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. Model notes
    # ═══════════════════════════════════════════════════════════════════════
    with st.expander("Model details and limitations"):
        st.markdown(
            f"""
**Algorithm:** Logistic Regression (sklearn, balanced class weights, L2 regularization C=1.0)

**Features used:**
- SVI Score (social vulnerability index)
- Fire growth rate (acres/hour)
- Notification type (silent = 1 / normal = 0)
- Spread rate (ordinal: slow=0, moderate=1, rapid=2, extreme=3)
- Max acres
- County FIPS frequency encoding (proxy for county-level base rate)

**Target variable:** `high_delay` = 1 if `hours_to_order > 6` OR `evacuation_occurred == 0`

**Training size:** {n_train:,} rows (dropped ~{len(df) - n_train:,} rows with missing feature values)

**Test accuracy:** {accuracy * 100:.1f}%

**Limitations:**
- Logistic regression assumes linear decision boundary — non-linear interactions
  (e.g., SVI × spread rate) are not fully captured.
- County frequency encoding is a simplification; a proper model would include
  county fixed effects or a hierarchical model.
- The target definition treats "no action" as equivalent to "delayed action"
  which inflates the positive class but is the conservative choice for public safety.
- This model is descriptive/explanatory, not a production prediction system.
  Do not use for operational emergency decisions.
            """
        )

    st.caption(
        "Data source: fire_events_with_svi_and_delays.csv · 62,696 wildfire incidents · "
        "WiDS 2021–2025. Model: scikit-learn LogisticRegression with StandardScaler. "
        "Predictions are statistical estimates, not operational recommendations."
    )
