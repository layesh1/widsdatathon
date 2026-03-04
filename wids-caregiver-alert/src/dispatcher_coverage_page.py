"""
dispatcher_coverage_page.py — Coverage Gaps (Emergency Worker view)
Wraps Channel Coverage and Silent Fire Risk in dispatcher-framed context.
"""
import streamlit as st


def render_dispatcher_coverage_page():
    st.title("📡 Coverage Gaps")
    st.caption("Where might residents NOT receive official alerts?")

    st.info(
        "These maps identify counties where the **alert system is weakest**. "
        "Single-channel counties are most at risk of communication failure. "
        "Silent fire escalation shows how often vulnerable populations are left without warning."
    )

    t1, t2 = st.tabs(["📡 Channel Coverage", "🔇 Silent Fire Risk"])

    with t1:
        from channel_coverage_page import render_channel_coverage_page
        render_channel_coverage_page()

    with t2:
        from silent_escalation_page import render_silent_escalation_page
        render_silent_escalation_page()
