"""
real_data_insights.py  —  49ers Intelligence Lab
Loads fire_events_with_svi_and_delays.csv and returns
pre-computed insight dicts for use across all dashboard roles.

Import this in caregiver_dashboard_FINAL.py:
  from real_data_insights import load_real_insights
"""

import pandas as pd
import numpy as np
import os
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))

@st.cache_data(show_spinner=False)
def load_real_insights():
    """
    Returns a dict of real statistics derived from WiDS competition data.
    Falls back to None if file not found.
    """
    paths = [
        os.path.join(_HERE, "fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE, "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE, "..", "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE, "..", "..", "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
        "01_raw_data/processed/fire_events_with_svi_and_delays.csv",
    ]

    df = None
    for p in paths:
        if os.path.exists(os.path.realpath(p)):
            try:
                df = pd.read_csv(os.path.realpath(p), low_memory=False)
                break
            except:
                pass

    if df is None:
        return None

    evac = df[df['evacuation_occurred'] == 1].copy()
    d    = evac['evacuation_delay_hours'].dropna()

    vuln_d   = evac[evac['is_vulnerable'] == 1]['evacuation_delay_hours'].dropna()
    norm_d   = evac[evac['is_vulnerable'] == 0]['evacuation_delay_hours'].dropna()

    vuln_g   = df[df['is_vulnerable'] == 1]['growth_rate_acres_per_hour'].dropna() \
               if 'growth_rate_acres_per_hour' in df.columns else pd.Series()
    norm_g   = df[df['is_vulnerable'] == 0]['growth_rate_acres_per_hour'].dropna() \
               if 'growth_rate_acres_per_hour' in df.columns else pd.Series()

    pct_delay = ((vuln_d.median() - norm_d.median()) / norm_d.median() * 100
                 if len(vuln_d) > 0 and len(norm_d) > 0 and norm_d.median() > 0
                 else None)

    pct_growth = ((vuln_g.median() - norm_g.median()) / norm_g.median() * 100
                  if len(vuln_g) > 0 and len(norm_g) > 0 and norm_g.median() > 0
                  else None)

    return {
        # Raw dataframe for charts
        "df": df,
        "evac_df": evac,

        # Core stats
        "total_fires":            len(df),
        "fires_with_evac":        int(df['evacuation_occurred'].sum()),
        "evac_pct":               float(df['evacuation_occurred'].mean() * 100),
        "vulnerable_fires":       int(df['is_vulnerable'].sum()),
        "vulnerable_pct":         float(df['is_vulnerable'].mean() * 100),

        # Delay stats (real data)
        "median_delay_h":         float(d.median())        if len(d) > 0 else None,
        "mean_delay_h":           float(d.mean())          if len(d) > 0 else None,
        "p90_delay_h":            float(d.quantile(0.90))  if len(d) > 0 else None,
        "p95_delay_h":            float(d.quantile(0.95))  if len(d) > 0 else None,
        "pct_over_6h":            float((d > 6).mean() * 100) if len(d) > 0 else None,
        "n_delay_obs":            len(d),

        # Equity — delay
        "vuln_median_delay_h":    float(vuln_d.median())   if len(vuln_d) > 0 else None,
        "nonvuln_median_delay_h": float(norm_d.median())   if len(norm_d) > 0 else None,
        "pct_delay_difference":   float(pct_delay)         if pct_delay is not None else None,

        # Equity — fire growth
        "vuln_growth_rate":       float(vuln_g.median())   if len(vuln_g) > 0 else None,
        "nonvuln_growth_rate":    float(norm_g.median())   if len(norm_g) > 0 else None,
        "pct_growth_difference":  float(pct_growth)        if pct_growth is not None else None,
        "n_growth_obs":           len(vuln_g) + len(norm_g),

        # Containment
        "median_containment":     float(df['final_containment_pct'].median())
                                  if 'final_containment_pct' in df.columns else None,
    }