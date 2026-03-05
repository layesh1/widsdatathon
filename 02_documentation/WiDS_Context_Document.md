# 49ers Intelligence Lab
## WiDS Datathon 2025 · Wildfire Caregiver Alert System
### Project Data & Code Reference — Context Document for Future Chats

*Last updated: 2026-03-04 (Session 11)*

---

## Project Overview
This system predicts evacuation delays for vulnerable populations during wildfires and routes proactive alerts to caregivers. It is the 49ers Intelligence Lab's submission to the WiDS Datathon 2025.

**Core Research Question:** Do vulnerable populations (elderly, disabled, low-income) experience systematically longer evacuation delays during wildfires, and can a data-driven alert system reduce those delays?

**Team:** Lena (layesh1) + Nadia (Ncashy)
**Repo:** github.com/layesh1/widsdatathon
**Streamlit Cloud:** share.streamlit.io (auto-deploys on push to main)
**April 2026 conference presentation deadline**

---

## Key Findings

### Real Data Findings (WiDS 2021–2025 dataset — 62,696 fires)
- **62,696 total fire incidents** analyzed (2021–2025)
- Median time from fire start to evacuation order: **1.1 hours** (n=653 fires with confirmed evac actions)
- Mean delay: **22.3 hours** (heavily right-skewed by slow-response fires)
- **90th percentile: 100.3 hours** (6,018 min) — 1 in 10 fires takes over 4 days to get an order
- Hours to warning median: **1.50h** (n=715); hours to advisory median: **6.21h** (n=356)
- Fires in **vulnerable counties grow 17% faster** (11.71 vs 10.00 acres/hour)
- **73.5% of fires are "silent"** — 46,053 of 62,696 events had `notification_type = silent`
- Of 46,053 silent fires, only **1** received an evacuation order
- Of 298 fires classified "extreme" spread rate, **211 (70.8%) received no evacuation action**
- Only **653 of 62,696 fires** (1.04%) ever triggered a formal evacuation order or warning
- Only **4,429 of 62,696 fires** (7.1%) have a confirmed link to any evacuation zone
- **39.8%** of all fire events occur in high-vulnerability counties (SVI ≥ 0.75)
- 41,906 fires had early warning signals with no evacuation action (99.74% no action rate)
- SVI sub-theme strongest correlation with delay: **svi_minority (−0.233)**, svi_housing (−0.159)
- Signal→order delay: **median 3.5h** (211.5 min); P90: 100.3h

### Seasonal and Temporal Patterns
- Peak fire months: **July (13,650 fires)**, August (11,554), June (8,726) — June–Aug = 54% of all fires
- Peak fire ignition hour: **21:00 UTC (9 PM) — 6,131 fires**; nighttime fires hit sleeping vulnerable populations hardest
- Hour window 8 PM–midnight accounts for ~44% of all detections

### Fire Perimeter Quality
- 6,207 perimeter records: 4,139 approved (66.7%), 883 rejected (14.2%), 1,185 pending (19.1%)

### Modeled/Projected Findings
- Caregiver alert system projects saving 500–1,500 lives/year at 65% caregiver adoption
- Getis-Ord Gi* hotspot analysis identifies evacuation corridor bottlenecks before they form
- Impact model: reducing high-SVI alert delay by 4 hours → ~76 additional fires alerted in 2-hr critical window

### Models Used
- **Cox Proportional Hazards** — models time-to-evacuation as function of SVI factors + fire proximity
- **Getis-Ord Gi*** — identifies statistically significant clusters of delayed evacuations
- **Alert classification triage** — prioritizes which vulnerable populations to alert first

---

## Technology Gap This System Addresses

Existing wildfire alert tools (WatchDuty, Genasys Protect, Nixle, Wireless Emergency Alerts):
- Only notify when an official order is already issued — **no pre-order early warning**
- Alert individuals directly — **no caregiver intermediary routing**
- No equity analysis — **no visibility into whether vulnerable populations are systematically underserved**
- Show fires, not populations — **no integration of SVI vulnerability with alert timing**
- No coordination gap index — **no view of single-source vs multi-source reporting by county**
- No silent fire detection — **73.5% of fires never get public alerts at all**

**What this system uniquely does:**
1. Detects the "signal gap window" — fire detected, no public alert yet — and routes early alerts to caregivers
2. Prioritizes by SVI vulnerability tier, not just proximity
3. Shows which counties rely on a single reporting agency (coordination fragility)
4. Visualizes the silent notification epidemic using real WiDS data
5. Provides an evacuee tracker for dispatchers synced to Supabase in real time
6. Integrates USFA fire department resources with SVI vulnerability maps at county level
7. Hexagonal density map of 62k+ historical fire events for spatial pattern recognition

---

## Repository Structure
```
widsdatathon-1/          ← local clone path: ~/widsdatathon-1
├── requirements.txt
├── .gitignore
├── 01_raw_data/
│   ├── geo_events_geoevent.csv               ← 62,696 fire events 2021–2025
│   ├── geo_events_geoeventchangelog.csv      ← 1.03M rows, evacuation timing source
│   ├── geo_events_externalgeoevent.csv       ← 1.5M rows, alert channel distribution
│   ├── geo_events_externalgeoeventchangelog.csv
│   ├── evac_zones_gis_evaczone.csv           ← 37,458 evacuation zone polygons (195MB)
│   ├── evac_zones_gis_evaczonechangelog.csv  ← 332MB zone change history
│   ├── evac_zone_status_geo_event_map.csv    ← 4,429 zone-to-fire linkages
│   ├── fire_perimeters_gis_fireperimeter.csv ← 6,207 fire perimeter polygons
│   ├── fire_perimeters_gis_fireperimeterchangelog.csv
│   ├── external/
│   │   └── SVI_2022_US_county.csv            ← CDC Social Vulnerability Index
│   └── processed/
│       ├── fire_events_with_svi_and_delays.csv  ← 15MB, force-committed with git add -f
│       ├── county_fire_stats.csv              ← 1,016 counties; total_fires, pct_silent, etc.
│       ├── county_gi_star.csv                 ← 543 counties; Gi* z-scores
│       ├── county_channel_coverage.csv        ← 732 counties; n_channels
│       ├── evac_zones_map.geojson
│       └── fire_perimeters_approved.geojson
├── 02_documentation/
│   └── WiDS_Context_Document.md             ← this file
├── 03_analysis_scripts/
│   └── 07_build_real_delays.py              ← main data pipeline (~3 min)
└── wids-caregiver-alert/src/                ← Streamlit Cloud main file path
    ├── wildfire_alert_dashboard.py            ← MAIN APP (entry point)
    ├── auth_supabase.py                       ← Custom PBKDF2 auth + forgot credentials
    ├── home_page.py                           ← Splash landing screen (role selector)
    ├── demo_mode.py                           ← Conference demo state (Ventura County scenario)
    ├── nasa_firms_live.py                     ← NASA FIRMS live fire feed module
    ├── pdf_export.py                          ← PDF evacuation plan generator (reportlab)
    ├── command_dashboard_page.py              ← Emergency Worker view (hexbin map + SMS)
    ├── coverage_analysis_page.py             ← Agency Coverage + Alert Channel Equity
    ├── signal_gap_analysis_page.py           ← Signal Gap Analysis (analyst)
    ├── silent_escalation_page.py             ← Silent Fire Tracker (funnel chart)
    ├── hotspot_map_page.py                   ← Getis-Ord Gi* hotspot map
    ├── channel_coverage_page.py              ← Alert channel count map (732 counties)
    ├── county_drilldown_page.py              ← County drill-down (1,016 counties)
    ├── temporal_fire_pattern_page.py         ← Hour/month/heatmap fire patterns
    ├── caregiver_start_page.py               ← Caregiver "Am I Safe?" — 10 languages
    ├── caregiver_county_page.py              ← Caregiver: My County
    ├── caregiver_why_page.py                 ← Caregiver: Why This App?
    ├── dispatcher_risk_zones_page.py         ← Dispatcher: At-Risk Zones
    ├── dispatcher_coverage_page.py           ← Dispatcher: Coverage Gaps
    ├── dispatcher_resources_page.py          ← Dispatcher: Resources (USFA)
    ├── evacuation_planner_page.py            ← Find a Shelter + PDF download
    ├── directions_page.py                    ← OSM routing for evacuation
    ├── fire_prediction_page.py               ← Physics-based fire spread (Van Wagner + Rothermel + FWI)
    ├── impact_projection_page.py             ← Life-saving projection model + delay-reduction slider
    ├── risk_calculator_page.py               ← Personal risk profile tool
    ├── signal_gap_analysis_page.py           ← Signal Gap Analysis (analyst)
    ├── irwin_linkage_page.py                 ← IRWIN incident linkage (4,767/6,207 linked)
    ├── zone_duration_page.py                 ← Zone escalation duration analysis
    ├── chatbot.py                            ← Claude Sonnet AI assistant
    ├── data_governance.py                    ← Data governance page
    ├── sms_alert.py                          ← Twilio SMS module
    ├── ui_utils.py                           ← Shared design system
    ├── live_incident_feed.py                 ← Supabase + NASA FIRMS live feed
    └── requirements.txt                      ← includes reportlab (added session 11)
```

---

## Supabase Database

**Project URL:** https://fguvvhqvzifnsihhomcv.supabase.co

### Tables with Data
| Table | Rows | Notes |
|-------|------|-------|
| geo_events_geoevent | 62,696 | Fire events 2021–2025 — main join key |
| geo_events_externalgeoevent | 1,613,995 | Alert channel distribution |
| evac_zone_status_geo_event_map | 4,429 | Links evac zones to fire events |
| evac_zones_gis_evaczone | 37,458 | Evacuation zone polygons |
| fire_events | 62,696 | Uploaded from fire_events_with_svi_and_delays.csv |
| evacuation_status | live | Caregiver evacuee tracker (persistent, role-based) |
| evacuation_changelog | live | Tracks status changes |
| users | live | Custom PBKDF2 auth (username, password_hash, password_salt, email, role) |
| user_events | live | Audit log (LOGIN, LOGOUT, PASSWORD_RESET, etc.) |
| caregiver_access_codes | 3 | EVAC-DEMO2025, DISPATCH-2025, ANALYST-WiDS9 |

### Views (queried by signal_gap_analysis_page.py)
| View | Status | Notes |
|------|--------|-------|
| v_dashboard_kpis | ✅ returns data | incidents_with_signal, pct_missing_action, median_delay_min, p90_delay_min |
| v_delay_benchmark | ✅ returns data | geo_event_id, first_signal_time, first_action_time, mins_signal_to_action |
| v_delay_summary_by_region_source | ✅ returns data | delay by region/agency |
| v_signal_without_action | ✅ returns data | fires with signal, no action |
| v_dangerous_delay_candidates | ⚠️ timeout | query too slow on 1.6M rows — needs index or LIMIT |

### RLS Status
- geo_events_externalgeoevent: RLS disabled (public read)
- evac_zone_status_geo_event_map: RLS disabled (public read)
- geo_events_geoevent: RLS disabled (public read)
- fire_events: RLS disabled, anon insert allowed
- users: RLS enabled — users can only read their own row

### Secrets (Streamlit Cloud + .streamlit/secrets.toml)
```toml
SUPABASE_URL = "https://fguvvhqvzifnsihhomcv.supabase.co"
SUPABASE_ANON_KEY = "eyJ..."   # anon public key — single line, no breaks
ANTHROPIC_API_KEY = "sk-ant-..."
NASA_FIRMS_API_KEY = "your_key"  # optional — DEMO_KEY works for low-traffic
# [twilio]
# account_sid = "..."
# auth_token = "..."
# from_number = "+1..."
```

---

## Dashboard Pages & Role Access

### Navigation Structure

**Caregiver/Evacuee** (5 pages):
| Nav Label | Page File | Description |
|-----------|-----------|-------------|
| Am I Safe? | caregiver_start_page.py | Active fires + 10-language UI |
| Evacuation Plan | evacuation_planner_page.py | Routes, shelters, PDF download |
| Risk Calculator | risk_calculator_page.py | Personal risk profile |
| My County | caregiver_county_page.py | Local fire stats in plain language |
| Why This App? | caregiver_why_page.py | Why official alerts aren't enough |

**Emergency Worker** (5 pages):
| Nav Label | Page File | Description |
|-----------|-----------|-------------|
| Command | command_dashboard_page.py | Live incidents + evacuee tracker + SMS |
| Fire Forecast | fire_prediction_page.py | Physics-based fire spread model |
| At-Risk Zones | dispatcher_risk_zones_page.py | Hotspot map + county drill-down |
| Coverage Gaps | dispatcher_coverage_page.py | Channel coverage + silent escalation |
| Resources | dispatcher_resources_page.py | USFA fire department directory |

**Data Analyst** (7 combined pages using st.tabs):
| Nav Label | Combined From |
|-----------|---------------|
| Overview | About (existing) |
| Signal Gap | Signal Gap Analysis + Silent Fire Tracker |
| Equity & Risk | Equity Analysis + Coverage Analysis |
| Geographic | Hotspot Map + Channel Coverage + County Drill-Down |
| Fire Patterns | Temporal Fire Patterns + Impact Projection |
| Technical | Data Governance + IRWIN Linkage + Zone Duration |
| Fire Predictor | fire_prediction_page.py |

### Page Status
| Page | Role | Status |
|------|------|--------|
| Home (splash) | All | ✅ shows on first login; role buttons bypass onboarding |
| Command | Emergency Worker | ✅ working — hexbin map, evacuee tracker, SMS, NASA FIRMS live card |
| Fire Forecast | Emergency Worker | ✅ working — Van Wagner ellipse + Rothermel spread + FWI + Open-Meteo |
| At-Risk Zones | Emergency Worker | ✅ working |
| Coverage Gaps | Emergency Worker | ✅ working |
| Resources | Emergency Worker | ✅ working — USFA directory (CSV needed for full lookup) |
| Am I Safe? | Caregiver | ✅ working — 10 languages (EN/ES/ZH/TL/VI/AR/KO/RU/PT/FR) |
| Evacuation Plan | Caregiver | ✅ working — PDF download button (reportlab) |
| Risk Calculator | Caregiver | ✅ working |
| My County | Caregiver | ✅ working |
| Why This App? | Caregiver | ✅ working |
| Overview | Analyst | ✅ working |
| Signal Gap | Analyst | ✅ working — uses fallback stats when Supabase returns 0 |
| Equity & Risk | Analyst | ✅ working |
| Geographic | Analyst | ✅ working |
| Fire Patterns | Analyst | ✅ working — delay reduction slider added |
| Technical | Analyst | ✅ working |
| Fire Predictor | Analyst | ✅ working |

---

## Demo Login Credentials

| Username | Password | Role | Access Code |
|----------|----------|------|-------------|
| dispatcher_test | WiDS@2025! | Emergency Worker | DISPATCH-2025 |
| caregiver_test | WiDS@2025! | Caregiver/Evacuee | none needed |
| analyst_test | WiDS@2025! | Data Analyst | ANALYST-WiDS9 |

**Auth system:** Custom PBKDF2-HMAC-SHA256 against `public.users` table — NOT Supabase Auth.

### Conference Demo Mode
- Toggle "🎬 Demo Mode" in the sidebar to activate a scripted Ventura County, CA scenario
- All pages show a yellow banner; key inputs override to demo values
- `demo_mode.py` → `get_demo_state()` returns full scenario dict
- Demo values: 842 acres, 14.2 ac/hr, SVI=0.82, 12,400 at risk, 8.3h historical delay, WEA only

---

## Completed Work Log

### Sessions 1–10 (Previous)
All previous work through Session 10 (physics-based fire prediction, UI redesign, etc.) is documented in prior context document versions. See git log for full history.

### Session 11 (2026-03-04) — Conference Improvements + Bug Fixes

#### New Modules Created
- ✅ **demo_mode.py** — `get_demo_state()` returns Ventura County scripted scenario (30 keys); `render_demo_banner()` shows yellow banner on every page when demo toggle is active
- ✅ **nasa_firms_live.py** — `fetch_live_fires()` (cached 10 min), `get_most_significant_fire()` with WiDS historical fallback; pulsing `.live-dot` CSS animation; shown at top of Command page
- ✅ **home_page.py** — Full splash landing screen: "11.5 HOURS LATER" hero in 72px red, 4 KPI cards (62,696 / 653 / 39.8% / 9×), 3 role buttons that set `session_state.role` and trigger rerun; shown on first login visit; "← Change role" in sidebar returns to it
- ✅ **pdf_export.py** — `generate_evacuation_plan()` returns `BytesIO` PDF via reportlab; 19-item checklist, risk badge, household profile, emergency contacts; PDF download button added to Evacuation Planner page

#### Pages Updated
- ✅ **wildfire_alert_dashboard.py** — imports demo_mode; home page gate (`show_home` flag); demo mode toggle + sidebar info; "← Change role" button; `render_demo_banner()` in `_render_page()`; NASA FIRMS live card at top of Command page; all 50 US states in state filter (was only 11)
- ✅ **impact_projection_page.py** — `calculate_impact()` model + `_render_delay_reduction_section()`: 0–12h interactive slider, 3 metric cards, full-curve line chart with current-position vline, methodology callout; appears first in Impact Projection tab
- ✅ **evacuation_planner_page.py** — PDF download section added; auto-detects risk level from nearest fire distance; `📄 Download My Evacuation Plan` button with `type="primary"`
- ✅ **caregiver_start_page.py** — 10 languages added: EN, ES, ZH, TL, VI, AR, KO, RU, PT, FR; all 35 UI strings translated; selector shows flag emoji + native name
- ✅ **requirements.txt** — added `reportlab`

#### Bug Fixes (Session 11)
- ✅ **P90 delay corrected in 6 files** — changed from wrong value of 32h → **100.3h** (6,018 min ÷ 60) across: `risk_calculator_page.py`, `impact_projection_page.py`, `wildfire_alert_dashboard.py` (AI prompt + table), `command_dashboard_page.py`, `caregiver_start_page.py`, `real_data_insights.py`
- ✅ **county_drilldown_page.py UnboundLocalError** — fixed inverted if/else that referenced `n_evac_computed` before assignment when `n_evac` column was present
- ✅ **impact_projection_page.py walrus operator bug** — replaced `(vul_pop_scale := ...) * x` pattern (assigned unused variable, wrong scope) with explicit `vul_pop_remaining` assignment
- ✅ **State filter** — Data Analyst sidebar now shows all 50 US states (previously only 11 western states)
- ✅ All pushed to GitHub (commits 3ef560c, 51feead, current)

---

## Verified Statistics Reference (ground truth from CSV)

| Metric | Value | Source |
|--------|-------|--------|
| Total fire incidents | 62,696 | fire_events_with_svi_and_delays.csv |
| Silent fires (notification_type=silent) | 46,053 (73.5%) | CSV |
| Normal fires | 16,643 (26.5%) | CSV |
| Fires with evacuation actions | 653 (1.04%) | CSV |
| Median hours_to_order | 1.10h | CSV (n=653) |
| Hours to warning median | 1.50h | CSV (n=715) |
| Hours to advisory median | 6.21h | CSV (n=356) |
| **P90 hours_to_order** | **100.3h (6,018 min)** | CSV |
| Signal→order median delay | 3.5h (211.5 min) | CSV |
| Extreme spread fires | 298 | CSV |
| Extreme fires with no evacuation | 211 (70.8%) | CSV |
| Fires with early signal, no action | 41,906 (99.74%) | CSV |
| High-SVI fire events | 39.8% of total | CSV |
| Fire growth — high-SVI counties | 11.71 ac/hr (+17%) | CSV |
| Fire growth — non-vulnerable | 10.00 ac/hr | CSV |
| Monthly peak | July = 13,650 fires | CSV |
| Hour-of-day peak | 21:00 = 6,131 fires | CSV |
| SVI correlation (strongest) | svi_minority = −0.233 | CSV |
| Fire perimeters total | 6,207 | fire_perimeters_gis_fireperimeter.csv |
| Perimeters approved | 4,139 (66.7%) | CSV |
| Perimeters rejected | 883 (14.2%) | CSV |
| Perimeters pending | 1,185 (19.1%) | CSV |

---

## Current To-Do List (Pre-April Conference)

### Remaining Manual Tasks
- ⬜ **Run fix_v_dangerous_delay_candidates.sql in Supabase** — adds indexes, rewrites view with LIMIT 2000; once done live Signal Gap data will flow through
- ⬜ **USFA registry CSV** — download from apps.usfa.fema.gov/registry/download → save as `src/usfa-registry-national.csv`; Resources and county drill-down tabs will auto-populate
- ⬜ **Twilio credentials** — add to `.streamlit/secrets.toml` under `[twilio]` section to enable SMS alerts from Command dashboard
- ⬜ **NASA FIRMS API key** — add `NASA_FIRMS_API_KEY` to secrets for higher rate limits (DEMO_KEY works but is shared/limited)
- ⬜ **Katie's map integration** — need her code

### Future Enhancements
- ⬜ True PWA/offline mode — not achievable in Streamlit; would need Next.js
- ⬜ Zone expansion timeline using evac_zones_gis_evaczonechangelog.csv geom JSON

---

## Raw Data Files — Full Column Reference

### fire_events_with_svi_and_delays.csv (62,696 rows × 38 cols) — RICHEST DATASET
```
geo_event_id, date_created, geo_event_type, name, is_active, latitude, longitude,
notification_type, fire_start, first_order_at, first_warning_at, first_advisory_at,
max_acres, first_acres, growth_rate_acres_per_hour, n_acreage_updates,
fire_duration_hours, final_containment_pct, last_spread_rate,
hours_to_order, hours_to_warning, hours_to_advisory,
evacuation_delay_hours, evacuation_occurred, exceeds_critical_threshold,
county_fips, county_name, state, svi_score,
svi_socioeconomic, svi_household, svi_minority, svi_housing,
pop_age65, pop_disability, pop_poverty, pop_no_vehicle, is_vulnerable
```

### geo_events_geoevent.csv (62,696 rows × 17 cols)
```
id, date_created, date_modified, geo_event_type, name, is_active, description,
address, lat, lng, data (JSON), notification_type, external_id, external_source,
incident_id, reporter_managed, is_visible
```

### geo_events_externalgeoevent.csv (1.5M rows × 14 cols)
```
id, date_created, date_modified, data, external_id, external_source, lat, lng,
channel, message_id, geo_event_id, user_created_id, permalink_url, is_hidden
```

### fire_perimeters_gis_fireperimeter.csv (6,207 rows × 14 cols)
```
id, date_created, date_modified, geo_event_id, approval_status, source,
source_unique_id, source_date_current, source_incident_name, source_acres,
geom, is_visible, is_historical, source_extra_data
```
- `source_extra_data` JSON: IncidentName, GISAcres, GACC, IRWINID, IncidentTypeCategory
- `approval_status`: approved (4,139) / pending (1,185) / rejected (883)

---

## Known Issues & Gotchas

1. **geo_event_id type mismatch** — changelog stores as "22429.0", geo_events as "22429". Fix: `str(int(float(x)))`
2. **Timezone mismatch** — geo_events date_created is timezone-naive. Fix: `.dt.tz_localize('UTC')`
3. **fire_events_with_svi_and_delays.csv is gitignored** — use `git add -f` to force-add
4. **usfa-registry-national.csv missing** — download from apps.usfa.fema.gov/registry/download, save to src/
5. **Supabase anon key must be single-line in secrets** — no line breaks
6. **Only 653 fires have real evac timing** — WiDS dataset has limited formal activations
7. **v_dangerous_delay_candidates times out** — query joins 1.6M row table without index; run fix_v_dangerous_delay_candidates.sql
8. **growth_rate outliers** — max is 5,000,000 acres/hr (data artifact); use median not mean
9. **33.5% of fire perimeters are pending/rejected** — filter to `approval_status = 'approved'`
10. **P90 is 100.3h, NOT 32h** — 32h was a historical error in several files; corrected in session 11
11. **Home page gate** — `show_home` in session_state controls splash; set to True on first post-login visit; "← Change role" resets it
12. **Demo mode** — `st.session_state.demo_mode` toggle in sidebar; `render_demo_banner()` must be called at top of each page via `_render_page()`

---

## Git Workflow

```bash
cd ~/widsdatathon-1
git add -A
git commit -m "your message"
git pull origin main --no-rebase   # if rejected, pull first
git push origin main

# Force-add large processed file
git add -f 01_raw_data/processed/fire_events_with_svi_and_delays.csv
```

---

## Conference Presentation Narrative

**The headline:** 73.5% of US wildfires are silent — no public alert ever issued. In high-SVI counties where fires grow 17% faster and evacuation orders can take up to 100 hours (P90), caregivers need proactive early warning.

**The gap:** Existing tools (WatchDuty, Nixle, WEA) only alert when the order is already given. There is no system that:
- Detects the pre-order silent window
- Routes alerts to caregivers of vulnerable individuals (not just direct notification)
- Measures and displays equity gaps in alert coverage

**The proof:** 211 extreme-spread fires with no evacuation action. 41,906 fires with early signals and no response. 99.74% of fires where the alert chain never reached the public. P90 delay of 100.3 hours in worst-case counties.

**The solution:** Caregiver Alert System — data-driven triage → proactive SMS to caregivers → real-time evacuee tracking for dispatchers → projected 500–1,500 lives saved/year at 65% adoption.

**Demo flow (conference):** Enable 🎬 Demo Mode → shows Ventura County, CA scenario → 8.3h historical delay vs 1.1h median → WEA-only gap → PDF evacuation plan download → impact slider showing 76 additional fires alerted with 4-hour delay reduction.
