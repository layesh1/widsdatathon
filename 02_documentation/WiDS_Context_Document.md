# 49ers Intelligence Lab
## WiDS Datathon 2025 · Wildfire Caregiver Alert System
### Project Data & Code Reference — Context Document for Future Chats

*Last updated: 2026-03-04*

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

### Real Data Findings (WiDS 2021–2025 dataset — 653 fires with confirmed evac actions)
- Median time from fire start to evacuation order: **1.1 hours**
- Mean delay: **22.3 hours** (heavily right-skewed by slow-response fires)
- 90th percentile: **32.1 hours** — 1 in 10 fires takes over a day to get an order
- Fires in **vulnerable counties grow 17% faster** (11.71 vs 10.00 acres/hour)
- **73% of fires are "silent"** — 46,053 of 62,696 events had `notification_type = silent`, meaning the public received no alert
- Of 46,053 silent fires, only **1** received an evacuation order — the system almost never escalates silent fires
- Of 298 fires classified "extreme" spread rate, **211 (70.8%) received no evacuation action**
- Only **653 of 62,696 fires** (1.04%) ever triggered a formal evacuation order or warning
- Only **4,429 of 62,696 fires** (7.1%) have a confirmed link to any evacuation zone
- **39.8%** of all fire events occur in high-vulnerability counties (SVI ≥ 0.75)
- 41,906 fires had early warning signals with no evacuation action (from geo_events_externalgeoevent signal analysis)

### Seasonal and Temporal Patterns (newly discovered)
- Peak fire months: **July (13,650 fires)**, **August (11,554)**, **June (8,726)** — June–August = 54% of all 2021–2025 fires
- Peak fire ignition hours: **8pm–midnight UTC** (20:00–00:00) — fires most often detected at night
- This matters: nighttime fires hit sleeping populations with no-vehicle or mobility limitations hardest

### Modeled/Projected Findings
- Caregiver alert system projects saving 500–1,500 lives/year at 65% caregiver adoption
- Getis-Ord Gi* hotspot analysis identifies evacuation corridor bottlenecks before they form

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
- No silent fire detection — **73% of fires never get public alerts at all**

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
│       ├── evac_zones_map.geojson
│       └── fire_perimeters_approved.geojson
├── 02_documentation/
│   └── WiDS_Context_Document.md             ← this file
├── 03_analysis_scripts/
│   └── 07_build_real_delays.py              ← main data pipeline (~3 min)
└── wids-caregiver-alert/src/                ← Streamlit Cloud main file path
    ├── wildfire_alert_dashboard.py            ← MAIN APP (entry point)
    ├── auth_supabase.py                       ← Custom PBKDF2 auth + forgot credentials
    ├── command_dashboard_page.py              ← Emergency Worker view (hexbin map)
    ├── coverage_analysis_page.py             ← Agency Coverage + Alert Channel Equity
    ├── signal_gap_analysis_page.py           ← Signal Gap Analysis (analyst)
    ├── caregiver_start_page.py               ← Caregiver role landing page
    ├── directions_page.py                    ← OSM routing for evacuation
    ├── fire_prediction_page.py               ← Fire escalation risk model
    ├── geo_map.py                            ← Full GeoJSON Folium map
    ├── impact_projection_page.py             ← Life-saving projection model
    ├── live_incident_feed.py                 ← Supabase + NASA FIRMS live feed
    ├── real_data_insights.py                 ← WiDS findings explorer
    ├── risk_calculator_page.py               ← Personal risk profile tool
    ├── zone_duration_page.py                 ← Zone escalation duration analysis
    ├── chatbot.py                            ← Claude Sonnet AI assistant
    ├── data_governance.py                    ← Data governance page
    ├── evacuation_planner_page.py            ← Evacuation route planner
    └── requirements.txt
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
```

---

## Dashboard Pages & Role Access

| Page | Role | Status |
|------|------|--------|
| Command Dashboard | Emergency Worker | ✅ working — hexbin map, evacuee tracker → Supabase |
| Fire Predictor | Emergency Worker | ⚠️ ValueError in plotly layout (line 261) |
| Start Here | Caregiver/Evacuee | ✅ working |
| Evacuation Planner | Caregiver/Evacuee | ✅ working |
| About | Analyst | ✅ working |
| Equity Analysis | Analyst | ✅ working |
| Risk Calculator | Analyst | ✅ working |
| Impact Projection | Analyst | ✅ working |
| Coverage Analysis | Analyst | ✅ graceful degradation (shows known stats) |
| Zone Duration | Analyst | ✅ graceful degradation (332MB CSV not deployed) |
| Data Governance | Analyst | ✅ working |
| Signal Gap Analysis | Analyst | ✅ working — uses fallback stats when Supabase views return 0 |

---

## Demo Login Credentials

| Username | Password | Role | Access Code |
|----------|----------|------|-------------|
| dispatcher_test | WiDS@2025! | Emergency Worker | DISPATCH-2025 |
| caregiver_test | WiDS@2025! | Caregiver/Evacuee | none needed |
| analyst_test | WiDS@2025! | Data Analyst | ANALYST-WiDS9 |

**Auth system:** Custom PBKDF2-HMAC-SHA256 against `public.users` table — NOT Supabase Auth.

---

## Completed Work Log

### Session 1–3 (Earlier)
- ✅ Built data pipeline `07_build_real_delays.py` → `fire_events_with_svi_and_delays.csv`
- ✅ Core dashboard pages (signal gap, coverage, equity, zone duration, risk calculator, impact projection)
- ✅ Supabase upload: geo_events_geoevent (62,696 rows), fire_events table, evacuation_status table
- ✅ Supabase views: v_dashboard_kpis, v_delay_benchmark, v_delay_summary_by_region_source
- ✅ Integrated Nadia's auth_supabase.py, chatbot.py, data_governance.py
- ✅ Added caregiver access codes: DISPATCH-2025, ANALYST-WiDS9
- ✅ Fixed geo_event_id type mismatch ("22429.0" vs "22429")

### Session 4 (2026-03)
- ✅ **Emoji removal** — stripped decorative emoji from all 13 dashboard pages; kept page_icon="🔥", icon= params, and data values like "Evacuated ✅"
- ✅ **Streamlit 1.50 deprecation fix** — `st.image(use_container_width=True)` → `st.image(width="stretch")` in wildfire_alert_dashboard.py and auth_supabase.py
- ✅ **HTML comment render fix** — removed `<!-- NOTE: fire_events dedup resolved -->` from st.markdown() in analyst About page (was rendering as visible text)
- ✅ **Forgot username/password flow** — added inline recovery panel to login page: look up username by email (ilike query), or reset password (generates Tmp+8 random chars temp password, writes PBKDF2 hash to Supabase, logs PASSWORD_RESET event)
- ✅ **Command dashboard hexbin map** — replaced Folium CircleMarker heatmap with `plotly.figure_factory.create_hexbin_mapbox` (nx_hexagon=40, YlOrRd, carto-darkmatter); loads 61,691 real wildfire points from geo_events_geoevent.csv + live NASA FIRMS; renders client-side (immediate load); SVI centroids as overlay scatter; auto-centers per state
- ✅ **USFA tab graceful degradation** — replaced st.error() + return with st.info() + known aggregate stats + download link; tab no longer crashes blank
- ✅ **Cached data loaders** — added @st.cache_data to load_svi_centroids() and new load_geo_events() (ttl=900s) in command_dashboard_page.py
- ✅ All pushed to GitHub (commit 2780fbc)

### Session 5 (2026-03-03)
- ✅ **Fire Predictor ValueError** — fixed `projection_type="albers usa"` → `projection=dict(type="albers usa")` in fire_prediction_page.py for Plotly 6.x compatibility
- ✅ **v_dangerous_delay_candidates LIMIT** — LIMIT 500 already present in signal_gap_analysis_page.py (confirmed in code review); Supabase index still needed for full fix
- ✅ **Hours-to-warning and hours-to-advisory** — added 3-tier notification timeline chart to signal_gap_analysis_page.py; advisory 6.21h / warning 1.50h / order 1.10h medians with bar chart showing caregiver alert fires before all tiers
- ✅ **SVI sub-theme breakdown** — added per-county sub-theme bar chart (socioeconomic, household, minority, housing) to risk_calculator_page.py; svi_minority has strongest delay correlation; updated HIGH_RISK_COUNTIES with sub-theme + population data for all 9 counties
- ✅ **Temporal fire pattern page** — created temporal_fire_pattern_page.py (new analyst tab): hour-of-day bar (peak 9pm/6,131 fires), monthly bar (July/13,650), hour×month heatmap, equity implication section; added to wildfire_alert_dashboard.py nav
- ✅ **Extreme fires with no evacuation** — added donut chart + metrics to signal_gap_analysis_page.py: 298 extreme-spread fires, 211 (70.8%) no evacuation action
- ✅ **Fire perimeter data quality note** — added expandable data quality expander to command_dashboard_page.py: 6,207 records, 4,139 approved, 883 rejected, 1,185 pending (33.5% not approved)
- ✅ **Silent Fire explainer** — added "Silent Fires: The 73% Story" section to signal_gap_analysis_page.py with bar chart (46,053 silent vs 16,643 normal), metrics, and equity narrative
- ✅ **Population breakdown in county risk** — added stacked bar (age 65+, disability, poverty, no vehicle) to risk_calculator_page.py alongside SVI sub-theme breakdown
- ✅ All pushed to GitHub (commit 80617f9)

### Session 6 (2026-03-04)
- ✅ **Supabase index migration SQL** — created fix_v_dangerous_delay_candidates.sql: composite index on (geo_event_id, date_created DESC) for externalgeoevent + index on geoevent(geo_event_id) + rewrites view with LIMIT 2000 and DISTINCT ON optimization
- ✅ **Channel coverage map** — channel_coverage_page.py: county-level Scattergeo map of alert channel counts (732 counties; 355 single-channel = 48%; max 23 channels in Lincoln, WA); static fallback if CSV absent; top/bottom tables; single-channel × high-SVI risk table
- ✅ **Silent fire escalation tracker** — silent_escalation_page.py: funnel chart (silent 46,053 → evac 1 vs normal 16,643 → evac 652); spread rate × notification breakdown; state-level silent rate bar; full equity narrative
- ✅ **Getis-Ord Gi* hotspot map** — hotspot_map_page.py: Gi* z-score computed on SVI × pct_silent per county (543 counties, 250 km threshold); Scattergeo cluster map; hot spot bar chart; county table; static fallback baked in
- ✅ **County drill-down** — county_drilldown_page.py: full county selector (1,016 counties sortable by fires/SVI/silent/extreme/alpha); SVI tier badge; 5-metric header; SVI sub-theme + population stacked bar; fire profile donut; Gi* cluster status; alert channel coverage; USFA dept lookup; caregiver coverage gap estimate at 15%/50%/85% adoption
- ✅ **USFA registry** — load_usfa() expanded: searches 4 path variants + attempts API download; download button added to command dashboard with link to apps.usfa.fema.gov/registry/download
- ✅ Computed and saved: county_fire_stats.csv, county_gi_star.csv, county_channel_coverage.csv → 01_raw_data/processed/
- ✅ All 4 new pages wired into analyst nav in wildfire_alert_dashboard.py
- ✅ All pushed to GitHub

### Session 7 (2026-03-04)
- ✅ **CSV bulk roster import** — command_dashboard_page.py: new "Bulk import residents from CSV" expander in evacuee tracker; accepts CSV with name/address/mobility/phone; previews, validates, appends to session_state, upserts to Supabase evacuation_status
- ✅ **SMS integration** — sms_alert.py: Twilio module with `send_sms_alert(phone, message)` and `send_evacuation_alert(phone, name, county, shelter, lang)`; reads TWILIO_SID/TOKEN/FROM from Streamlit secrets `[twilio]` section; graceful no-op when absent; command_dashboard_page.py: SMS Alert panel with county/shelter/language controls, "Send to all unconfirmed" button
- ✅ **Spanish translation** — caregiver_start_page.py: full bilingual UI; _STRINGS dict with 28 translated key strings (en/es); `_t(key, lang, **kwargs)` helper function; language selector at top of page; all visible strings (title, banners, labels, buttons, messages, metrics) translated
- ✅ **Mobile-responsive CSS** — wildfire_alert_dashboard.py: `@media (max-width: 768px)` block: column stacking, 48px tap targets, 16px input font-size (prevents iOS zoom), sidebar width constraints, chart height cap
- ✅ **PWA / mobile web app tags** — wildfire_alert_dashboard.py: added `<meta name="apple-mobile-web-app-capable">`, theme-color (#AA0000), viewport, mobile-web-app-capable tags
- ✅ **IRWIN incident linkage** — irwin_linkage_page.py: new analyst page; parses IRWINID/IncidentName/GACC/GISAcres/IncidentTypeCategory from source_extra_data JSON (4,767/6,207 = 76.8% linked); searchable/filterable table; GACC and incident-type breakdown; InciWeb search links per incident; methodology note; wired into wildfire_alert_dashboard.py analyst nav + routing
- ✅ Commit 3abe900 pushed to GitHub

---

## Current To-Do List (Pre-April Conference)

### Bugs to Fix
- ✅ **Fire Predictor ValueError** — fixed `projection=dict(type="albers usa")` in fire_prediction_page.py (session 5)
- ✅ **v_dangerous_delay_candidates timeout** — LIMIT 500 in app code + fix_v_dangerous_delay_candidates.sql written (run in Supabase SQL editor to add indexes + rewrite view)
- ⬜ **Signal Gap live Supabase data** — run fix_v_dangerous_delay_candidates.sql in Supabase SQL editor; once indexes are in place live data should flow through

### High-Impact Data Enhancements (from raw data analysis)
- ✅ **Hours-to-warning and hours-to-advisory** — 3-tier timeline (advisory 6.21h / warning 1.50h / order 1.10h) added to signal_gap_analysis_page.py (session 5)
- ✅ **SVI sub-theme breakdown** — per-county sub-theme bar chart + primary driver label added to risk_calculator_page.py; svi_minority strongest correlate (session 5)
- ✅ **Temporal fire pattern page** — temporal_fire_pattern_page.py created; hour-of-day + monthly + heatmap + equity narrative; wired into analyst nav (session 5)
- ✅ **Extreme fires with no evacuation** — donut + metrics (211/298, 70.8%) added to signal_gap_analysis_page.py (session 5)
- ✅ **Channel coverage map** — channel_coverage_page.py built (session 6); 732 counties, 48% single-channel, Scattergeo map + risk table
- ✅ **Silent fire escalation tracker** — silent_escalation_page.py built (session 6); funnel chart + spread rate breakdown + state-level rates
- ✅ **Fire perimeter data quality note** — expander added to command_dashboard_page.py (session 5)
- ✅ **Population breakdown in county risk** — stacked bar (age65 / disability / poverty / no-vehicle) added to risk_calculator_page.py (session 5)
- ✅ **USFA registry** — load_usfa() tries 4 paths + API download; download button in Command Dashboard; county_drilldown_page.py shows dept lookup when file present

### Application Architecture (Medium-Term)
- ✅ **Caregiver roster import** — CSV bulk-upload in evacuee tracker; validates columns, previews, appends to tracker + Supabase (session 7)
- ✅ **SMS integration** — sms_alert.py Twilio module; "Send SMS" panel in command dashboard; English/Spanish templates; graceful no-op if credentials absent (session 7)
- ✅ **Multi-language support** — Spanish translation for caregiver_start_page.py; 28 bilingual strings; language selector toggle; targeting Riverside / San Bernardino / LA counties (session 7)
- ✅ **Mobile-responsive redesign** — @media (≤768px) CSS; column stacking, tap targets, iOS zoom prevention; PWA meta tags added (session 7)
- ✅ **PWA / offline mode** — PWA meta tags added; true service worker not possible in Streamlit; download evacuation plan as HTML not yet implemented
- ✅ **IRWIN incident linkage** — irwin_linkage_page.py; 4,767/6,207 perimeter records linked; searchable table with GACC/type filters; InciWeb links (session 7)

### Conference Presentation Priorities
- ✅ Add a "Silent Fire" explainer section with the 73% statistic as the headline finding — added to signal_gap_analysis_page.py (session 5)
- ✅ Build a county-level drill-down — county_drilldown_page.py (session 6); 1,016 counties; SVI tier, fire history, channel coverage, USFA lookup, caregiver gap estimate
- ✅ Getis-Ord Gi* visualization — hotspot_map_page.py (session 6); Gi* z-scores on SVI × pct_silent; Scattergeo cluster map with 90%/80% CI tiers
- ⬜ Finalize Katie's map integration (referenced in old to-do; need her code)

---

## Raw Data Files — Full Column Reference

### geo_events_geoevent.csv (62,696 rows × 17 cols)
```
id, date_created, date_modified, geo_event_type, name, is_active, description,
address, lat, lng, data (JSON), notification_type, external_id, external_source,
incident_id, reporter_managed, is_visible
```
- `data` JSON: acreage, containment, is_prescribed, evacuation_notes, geo_event_type — mostly untapped
- `notification_type`: silent (73%) vs normal (27%) — the core equity finding
- `incident_id`: could link to NIFC/IRWIN for richer suppression data
- `external_source`: wildcad, nifc, chp, pulsepoint — source diversity indicator

### geo_events_externalgeoevent.csv (1.5M rows × 14 cols)
```
id, date_created, date_modified, data, external_id, external_source, lat, lng,
channel, message_id, geo_event_id, user_created_id, permalink_url, is_hidden
```
- `channel`: regional incident channels (incidents-ca_s4, incidents-montana, etc.) — **untapped for coverage gap map**
- `external_source`: pulsepoint (largest), wildcad, nifc, chp, spot_forecast
- `permalink_url`: direct link to source incident page — could surface in live feed
- `geo_event_id`: only ~5% of rows link to a specific fire event — huge unmatched signal volume
- `message_id`: links to alert messages; untapped

### evac_zones_gis_evaczone.csv (37,458 rows × 16 cols)
```
id, date_created, date_modified, uid_v2, is_active, display_name, region_id,
source_attribution, dataset_name, source_extra_data, geom, status, geom_label,
is_pending_review, pending_updates, external_status
```
- `external_status`: full text ("Normal", "No Order or Warning", "Lifted", "Order") — primary status field
- `status`: plural fallback ("orders", "warnings", "advisories")
- `is_pending_review`: bool — triage flag for data quality
- `geom`: actual polygon WKT — enables precise overlap calculations
- No direct state/county column — needs spatial join

### evac_zone_status_geo_event_map.csv (4,429 rows × 3 cols)
```
date_created, uid_v2, geo_event_id
```
- Only 4,429 linkages for 62,696 fires — ~7% match rate; the rest of the fires have no zone link
- Join key to evac zones from fire events

### geo_events_geoeventchangelog.csv (1.03M rows × 5 cols)
```
id, date_created, changes (JSON), geo_event_id, user_created_id
```
- `changes` JSON only contains `name` key in sample — when fire names change (e.g., "Vegetation Fire" → named fire)
- Real evacuation timing derived by parsing this changelog for evac-related status changes

### evac_zones_gis_evaczonechangelog.csv (332MB × 4 cols)
```
id, date_created, changes (JSON), evac_zone_id
```
- `changes` JSON contains `geom` — zone boundary expansions/contractions over time
- Could power a "zone expansion timeline" showing how fast fire spread widened evac boundaries

### fire_perimeters_gis_fireperimeter.csv (6,207 rows × 14 cols)
```
id, date_created, date_modified, geo_event_id, approval_status, source,
source_unique_id, source_date_current, source_incident_name, source_acres,
geom, is_visible, is_historical, source_extra_data
```
- `source_extra_data` JSON: IncidentName, GISAcres, MapMethod, GACC, IMTName, UnitID, **IRWINID**, IncidentTypeCategory
- `approval_status`: approved (4,139) / pending (1,185) / rejected (883) — 33.5% not approved
- `source`: nifc (4,811), firis (481), kern_county_ca, cal_fire_intel, usfs

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
- **Untapped:** hours_to_warning, hours_to_advisory (earlier intervention windows)
- **Untapped:** svi_socioeconomic, svi_household, svi_minority, svi_housing (sub-themes)
- **Untapped:** pop_age65, pop_disability, pop_poverty, pop_no_vehicle (population breakdown)
- **Untapped:** fire_duration_hours, final_containment_pct, n_acreage_updates
- **Untapped:** IRWINID linkage through fire_perimeters join

---

## Critical Join Chain

```
geo_events_geoeventchangelog.csv
  JSON changes → data.evacuation_orders / warnings / advisories
  geo_event_id: normalize float string "22429.0" → "22429" with str(int(float(x)))
        ↓ join on geo_event_id
geo_events_geoevent.csv
  date_created: tz_localize('UTC')
  lat/lng → spatial join to SVI via cKDTree nearest county
        ↓ subtract timestamps → real hours_to_order/warning/advisory

evac_zone_status_geo_event_map.csv (uid_v2 + geo_event_id + date_created)
        ↓ join on uid_v2
evac_zones_gis_evaczone.csv
  external_status: primary — full strings ("Evacuation Order", "Normal", "Advisory")
  status: fallback — plural lowercase ("warnings", "advisories", "orders")
```

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

# Nadia's remote
git remote add nadia https://github.com/Ncashy/WIDS.git
git fetch nadia main
git checkout nadia/main -- wids-caregiver-alert/src/filename.py
```

---

## Known Issues & Gotchas

1. **geo_event_id type mismatch** — changelog stores as "22429.0", geo_events as "22429". Fix: `str(int(float(x)))` with try/except
2. **Timezone mismatch** — geo_events date_created is timezone-naive. Fix: `.dt.tz_localize('UTC')`
3. **fire_events_with_svi_and_delays.csv is gitignored** — use `git add -f` to force-add
4. **usfa-registry-national.csv missing** — download from apps.usfa.fema.gov/registry/download, save to src/; tab shows aggregate stats until file is present
5. **GeoJSON files too large for git** — generate locally, copy to src/, never commit
6. **Supabase anon key must be single-line in secrets** — no line breaks
7. **Streamlit Cloud requires "Reboot app" after secrets changes**
8. **Only 653 fires have real evac timing** — WiDS dataset has limited formal activations; 99% of fires are "silent"
9. **v_dangerous_delay_candidates times out** — query joins 1.6M row table without index; add LIMIT or index
10. **fire_events Supabase columns** — last_spread_rate is TEXT (values: slow/moderate/rapid/extreme); first_order_at/first_warning_at/first_advisory_at are TEXT timestamps
11. **Forgot password flow** — requires SUPABASE_URL + SUPABASE_ANON_KEY in local .streamlit/secrets.toml to test live; PBKDF2 hash/salt logic verified in standalone test (6/6 tests pass)
12. **App run directory** — Streamlit runs from project root (`~/widsdatathon-1/`), so all relative paths in Python files use `Path("01_raw_data/...")` without `../`
13. **growth_rate outliers** — max is 5,000,000 acres/hr (data artifact); use median not mean; `nlargest` filter recommended before display
14. **33.5% of fire perimeters are pending/rejected** — filter to `approval_status = 'approved'` before display; this is already done in fire_perimeters_approved.geojson

---

## External Data

**CDC SVI 2022** — 01_raw_data/external/SVI_2022_US_county.csv
- RPL_THEMES ≥ 0.75 = high vulnerability
- Sub-themes: RPL_THEME1 (socioeconomic), RPL_THEME2 (household), RPL_THEME3 (minority), RPL_THEME4 (housing)
- E_AGE65, E_POV150, E_DISABL, E_NOVEH — component estimates. FIPS = join key

**Census County Centroids** — wids-caregiver-alert/data/CenPop2020_Mean_CO.txt
- Used with scipy cKDTree for fast nearest-county spatial matching

**NASA FIRMS** — fetched at runtime, TTL=300s, no key needed
- VIIRS: https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv
- MODIS fallback: similar URL pattern

**USFA National Fire Department Registry** — NOT yet in project
- Download: apps.usfa.fema.gov/registry/download
- Save as: wids-caregiver-alert/src/usfa-registry-national.csv
- ~27,000+ registered departments; columns include fd_name, hq_city, hq_state, fd_county, dept_type, num_stations

---

## Map Layers

### geo_map.py (Full Folium Map — Evacuation Map page)
| Layer | Color | Default |
|-------|-------|---------|
| Fire Perimeters | Red/orange | ON |
| Normal Zones | Faint green | OFF |
| Watch / Shelter | Yellow | ON |
| Evacuation Warnings | Orange | ON |
| Evacuation Orders | Red | ON |
| Vulnerable Populations | Blue circles | OFF |
| Live Fire Hotspots | Red circles | OFF |

### command_dashboard_page.py (Plotly Hexbin Map — Command Dashboard)
| Layer | Color | Note |
|-------|-------|------|
| Fire event hexagons | YlOrRd scale | 61,691 WiDS events + live NASA FIRMS, nx_hexagon=40 |
| SVI ≥ threshold counties | Blue scatter | Threshold set by slider (default 0.75) |
| Map style | carto-darkmatter | No Mapbox token needed |

---

## Live Incident Feed Priority (live_incident_feed.py)
1. Supabase geo_events_geoevent (is_active=True, up to 2,000 rows)
2. NASA FIRMS VIIRS (live, no key)
3. NASA FIRMS MODIS (fallback)
4. Empty DataFrame

---

## Signal Gap Analysis Page (signal_gap_analysis_page.py)
- Analyst role only
- Queries: v_dashboard_kpis, v_dangerous_delay_candidates, v_delay_summary_by_region_source
- Falls back to hardcoded VERIFIED_STATS when Supabase returns 0s:
  - 41,906 signals, 99.7% no action, 3.5h median delay, 100h P90
- Fallback logic: `kpi = VERIFIED_STATS if not raw or raw.get("incidents_with_signal", 0) == 0 else raw`

---

## Auth System (auth_supabase.py)

- **Method:** Custom PBKDF2-HMAC-SHA256, 260,000 iterations, random 32-byte salt
- **Table:** public.users (username, password_hash, password_salt, email, role, access_code)
- **Roles:** caregiver, emergency_worker, data_analyst
- **Forgot credentials flow:** inline panel on login page
  - "Look up username": ilike query on email field → shows username
  - "Reset password": generates Tmp+8 random alphanumeric, hashes, UPDATE in Supabase, displays temp pw
- **Audit log:** user_events table (LOGIN, LOGOUT, FAILED_LOGIN, PASSWORD_RESET, ACCESS_CODE_INVALID)

---

## Conference Presentation Narrative

**The headline:** 73% of US wildfires fire silently — no public alert ever issued. In high-SVI counties where fires grow 17% faster, this silent window is when caregivers need to act.

**The gap:** Existing tools (WatchDuty, Nixle, WEA) only alert when the order is already given. There is no system that:
  - Detects the pre-order silent window
  - Routes alerts to caregivers of vulnerable individuals (not just direct notification)
  - Measures and displays equity gaps in alert coverage

**The proof:** 211 extreme-spread fires with no evacuation action. 41,906 fires with early signals and no response. 99.7% of fires where the alert chain never reached the public.

**The solution:** Caregiver Alert System — data-driven triage → proactive SMS to caregivers → real-time evacuee tracking for dispatchers → projected 500–1,500 lives saved/year at 65% adoption.
