"""
ui_utils.py — Shared UI utilities for the WiDS Wildfire Alert Dashboard.

Design tokens (60-30-10 color rule):
  60% dominant  → #0d1117 (deep navy bg), #161b22 (surface), #21262d (raised)
  30% secondary → #1e3a5f (slate), #30363d (borders), #8b949e (muted text)
  10% accent    → #FF4B4B (red CTA only), #d4a017 (amber warning), #3fb950 (green safe)

No emojis in any output from this module.
"""
from __future__ import annotations
import streamlit as st


# ── Styled headers ─────────────────────────────────────────────────────────────

def page_header(title: str, caption: str = "") -> None:
    """Styled page title replacing st.title(). Left-aligned, border-bottom."""
    st.markdown(
        f"<h1 style='font-size:24px;font-weight:700;color:#e6edf3;"
        f"border-bottom:1px solid #30363d;padding-bottom:12px;margin-bottom:4px;"
        f"font-family:\"DM Sans\",system-ui,sans-serif;margin-top:0'>{title}</h1>",
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)


def section_header(title: str) -> None:
    """Styled h2-level section header replacing st.subheader()."""
    st.markdown(
        f"<h2 style='font-size:15px;font-weight:600;color:#e6edf3;"
        f"margin-top:1.2rem;margin-bottom:0.3rem;padding-bottom:6px;"
        f"border-bottom:1px solid #30363d22;"
        f"font-family:\"DM Sans\",system-ui,sans-serif'>{title}</h2>",
        unsafe_allow_html=True,
    )


# ── Card component ─────────────────────────────────────────────────────────────

def render_card(
    title: str,
    value: str,
    subtitle: str,
    color: str = "#3fb950",
) -> None:
    """
    Stat card with colored left border.
      color="#FF4B4B"  → danger / critical
      color="#d4a017"  → warning / caution
      color="#3fb950"  → safe / good
      color="#1e3a5f"  → informational
    """
    st.markdown(
        f"""<div style="background:#161b22;border:1px solid #30363d;border-radius:12px;
            padding:20px 18px;border-left:4px solid {color};margin-bottom:6px;">
          <div style="font-size:11px;color:#8b949e;text-transform:uppercase;
               letter-spacing:1px;font-family:'IBM Plex Sans',sans-serif">{title}</div>
          <div style="font-size:28px;font-weight:700;color:#e6edf3;margin:8px 0;
               font-family:'DM Sans',system-ui,sans-serif">{value}</div>
          <div style="font-size:13px;color:#8b949e;font-family:'IBM Plex Sans',sans-serif">{subtitle}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def fallback_card(message: str) -> None:
    """Shown instead of an empty chart to avoid blank space."""
    st.markdown(
        f"""<div style="background:#161b22;border:1px solid #30363d;border-radius:12px;
            padding:32px 18px;text-align:center;">
          <div style="font-size:13px;color:#8b949e">{message}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ── Data source badge ──────────────────────────────────────────────────────────

def data_source_badge(source: str, updated_ago_min: int | None = None) -> None:
    """Small right-aligned badge: data source + last updated timestamp."""
    ts = ""
    if updated_ago_min is not None:
        if updated_ago_min == 0:
            ts = " · just now"
        elif updated_ago_min < 60:
            ts = f" · {updated_ago_min}m ago"
        else:
            h, m = divmod(updated_ago_min, 60)
            ts = f" · {h}h {m}m ago"
    st.markdown(
        f"<div style='text-align:right;font-size:0.68rem;color:#8b949e;"
        f"margin-bottom:6px'>{source}{ts}</div>",
        unsafe_allow_html=True,
    )


# ── Caregiver progress indicator ───────────────────────────────────────────────

def caregiver_progress_html(
    has_risk: bool = False,
    has_alerts: bool = False,
    has_plan: bool = False,
) -> str:
    """Return sidebar progress HTML for caregiver setup completion."""
    steps = [
        ("Risk profile complete", has_risk),
        ("Alert sign-up viewed", has_alerts),
        ("Evacuation plan saved", has_plan),
    ]
    done = sum(1 for _, v in steps if v)
    pct = int(done / len(steps) * 100)
    bar_filled = "\u2588" * done
    bar_empty = "\u2591" * (len(steps) - done)
    items_html = "".join(
        f"<div style='font-size:0.7rem;"
        f"color:{'#3fb950' if v else '#8b949e'};margin:2px 0'>"
        f"{'&#10003;' if v else '&#9675;'}  {label}</div>"
        for label, v in steps
    )
    return (
        f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;"
        f"padding:10px 12px;margin:6px 0'>"
        f"<div style='font-size:0.7rem;color:#8b949e;margin-bottom:4px'>"
        f"Your setup &mdash; {pct}%</div>"
        f"<div style='font-size:0.85rem;letter-spacing:2px;color:#FF4B4B'>{bar_filled}"
        f"<span style='color:#30363d'>{bar_empty}</span></div>"
        f"{items_html}"
        f"</div>"
    )
