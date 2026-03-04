"""
caregiver_why_page.py — Why This App? (Caregiver view)
Story-driven, plain-language explanation of the alert gap problem.
"""
import streamlit as st
import plotly.graph_objects as go


def render_caregiver_why_page():
    st.title("💡 Why This App?")
    st.caption("Why official alerts alone aren't enough — especially for caregivers")

    # ── Big stat cards ────────────────────────────────────────────────────────
    st.markdown("### The Alert System Has a Gap")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            "<div style='background:#AA000012;border-left:4px solid #AA0000;"
            "border-radius:8px;padding:1rem;text-align:center'>"
            "<div style='font-size:2.2rem;font-weight:900;color:#AA0000'>3 in 4</div>"
            "<div style='font-size:0.88rem;margin-top:4px'>"
            "wildfires happen with <strong>no public warning</strong> — "
            "no evacuation order, no alert sent</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div style='background:#d9770612;border-left:4px solid #d97706;"
            "border-radius:8px;padding:1rem;text-align:center'>"
            "<div style='font-size:2.2rem;font-weight:900;color:#d97706'>~1 hour</div>"
            "<div style='font-size:0.88rem;margin-top:4px'>"
            "median time between when a fire starts and when an evacuation "
            "<strong>order</strong> is issued — if one is issued at all</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            "<div style='background:#16a34a12;border-left:4px solid #7c3aed;"
            "border-radius:8px;padding:1rem;text-align:center'>"
            "<div style='font-size:2.2rem;font-weight:900;color:#7c3aed'>70%</div>"
            "<div style='font-size:0.88rem;margin-top:4px'>"
            "of the fastest-spreading fires got <strong>no evacuation order</strong> "
            "— the fires most dangerous to slow evacuators</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Timeline graphic ──────────────────────────────────────────────────────
    st.markdown("### What Happens in a Silent Fire")
    st.markdown(
        "A 'silent fire' is one where the alarm system fails — no alert is sent, even as the "
        "fire spreads. Here's the typical timeline:"
    )

    timeline_html = """
    <div style='display:flex;flex-direction:column;gap:0;margin:1rem 0 1.5rem'>
      <div style='display:flex;align-items:flex-start;gap:14px'>
        <div style='display:flex;flex-direction:column;align-items:center'>
          <div style='width:36px;height:36px;border-radius:50%;background:#AA0000;
               color:#fff;display:flex;align-items:center;justify-content:center;
               font-size:1rem;flex-shrink:0'>🔥</div>
          <div style='width:2px;background:#AA000040;flex:1;min-height:40px'></div>
        </div>
        <div style='padding-top:4px'>
          <strong>Fire ignites</strong>
          <div style='font-size:0.82rem;opacity:0.7'>T = 0 minutes</div>
          <div style='font-size:0.85rem'>A fire starts in dry vegetation. Conditions are extreme.</div>
        </div>
      </div>
      <div style='display:flex;align-items:flex-start;gap:14px'>
        <div style='display:flex;flex-direction:column;align-items:center'>
          <div style='width:36px;height:36px;border-radius:50%;background:#d97706;
               color:#fff;display:flex;align-items:center;justify-content:center;
               font-size:1rem;flex-shrink:0'>📡</div>
          <div style='width:2px;background:#AA000040;flex:1;min-height:40px'></div>
        </div>
        <div style='padding-top:4px'>
          <strong>Early signals detected</strong>
          <div style='font-size:0.82rem;opacity:0.7'>T = 30–60 minutes</div>
          <div style='font-size:0.85rem'>Watch Duty, fire cameras, and aircraft detect the fire.
          <strong>99.7% of these fires receive no evacuation action.</strong></div>
        </div>
      </div>
      <div style='display:flex;align-items:flex-start;gap:14px'>
        <div style='display:flex;flex-direction:column;align-items:center'>
          <div style='width:36px;height:36px;border-radius:50%;background:#AA0000;
               color:#fff;display:flex;align-items:center;justify-content:center;
               font-size:1rem;flex-shrink:0'>💨</div>
          <div style='width:2px;background:#AA000040;flex:1;min-height:40px'></div>
        </div>
        <div style='padding-top:4px'>
          <strong>Fire spreads rapidly</strong>
          <div style='font-size:0.82rem;opacity:0.7'>T = 1–3 hours</div>
          <div style='font-size:0.85rem'>Wind-driven fires can spread miles in minutes.
          No alert has been sent. Residents don't know.</div>
        </div>
      </div>
      <div style='display:flex;align-items:flex-start;gap:14px'>
        <div style='display:flex;flex-direction:column;align-items:center'>
          <div style='width:36px;height:36px;border-radius:50%;background:#7c3aed;
               color:#fff;display:flex;align-items:center;justify-content:center;
               font-size:1rem;flex-shrink:0'>👴</div>
          <div style='width:2px;background:transparent;flex:1;min-height:20px'></div>
        </div>
        <div style='padding-top:4px'>
          <strong>Caregivers are left behind</strong>
          <div style='font-size:0.82rem;opacity:0.7'>T = too late</div>
          <div style='font-size:0.85rem'>People caring for elderly, disabled, or medically
          dependent family members need extra time to evacuate — time the system didn't give them.</div>
        </div>
      </div>
    </div>
    """
    st.markdown(timeline_html, unsafe_allow_html=True)

    # ── Simple bar chart ──────────────────────────────────────────────────────
    st.markdown("### Silent vs. Normal Fires — What Actually Gets an Evacuation")

    fig = go.Figure()
    categories = ["Silent fires\n(no public alert)", "Normal fires\n(alert sent)"]
    total = [46053, 16643]
    with_evac = [1, 652]
    no_evac = [46052, 15991]

    fig.add_trace(go.Bar(
        name="Got evacuation action",
        x=categories,
        y=[round(1/46053*100, 3), round(652/16643*100, 1)],
        marker_color="#16a34a",
        text=["1 fire (0.002%)", "652 fires (3.9%)"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="No evacuation action",
        x=categories,
        y=[round(46052/46053*100, 1), round(15991/16643*100, 1)],
        marker_color="#AA0000",
        text=["46,052 fires (99.998%)", "15,991 fires (96.1%)"],
        textposition="inside",
        textfont=dict(color="white"),
    ))

    fig.update_layout(
        barmode="stack",
        yaxis_title="% of fires",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=340,
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Of 46,053 silent fires (2021–2025), only 1 received an evacuation action. "
        "Even for fires with public alerts, 96% still had no evacuation action."
    )

    # ── What this app does ────────────────────────────────────────────────────
    st.divider()
    st.markdown("### What This App Does")

    st.markdown("""
This app uses data from **62,696 wildfire incidents** (2021–2025) to:

1. **Show you fires near your location** — including ones that didn't make the news
2. **Calculate your personal evacuation risk** — based on your county's SVI, fire history, and alert coverage
3. **Connect you to your evacuation plan** — pre-filled with routes and shelter locations
4. **Help emergency workers find you** — if you've registered as a caregiver with mobility or medical needs

**This is not a replacement for 911 or official emergency alerts.** But in the 73% of fires where no official alert is sent, this data can be the early warning that saves lives.
""")

    st.markdown(
        "<div style='background:#AA000010;border:1px solid #AA000030;"
        "border-radius:10px;padding:1.2rem 1.4rem;text-align:center;margin-top:1rem'>"
        "<div style='font-size:1rem;font-weight:700;color:#AA0000;margin-bottom:0.4rem'>"
        "Ready to set up your evacuation plan?</div>"
        "<div style='font-size:0.86rem;opacity:0.8'>"
        "Use the navigation on the left to check fires near you or build your evacuation plan."
        "</div></div>",
        unsafe_allow_html=True,
    )
