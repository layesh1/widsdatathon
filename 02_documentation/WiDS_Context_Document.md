# 49ers Intelligence Lab
## WiDS Datathon 2025 · Wildfire Caregiver Alert System
### Project Data & Code Reference — Context Document for Future Chats

---

## Project Overview
This system predicts evacuation delays for vulnerable populations during wildfires and routes proactive alerts to caregivers. It is the 49ers Intelligence Lab's submission to the WiDS Datathon 2025, currently in 2nd place.

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
- Vulnerable counties receive orders slightly faster at the median, but face faster-growing fires leaving less real response time
- 39.8% of all fire events occur in high-vulnerability counties (SVI ≥ 0.75)
- **41,906 fires had early warning signals; 99.7% received no evacuation action** (from geo_events_externalgeoevent signal analysis)

### Modeled/Projected Findings
- Caregiver alert system projects saving 500–1,500 lives/year at 65% caregiver adoption
- Getis-Ord Gi* hotspot analysis identifies evacuation corridor bottlenecks before they form

### Models Used
- **Cox Proportional Hazards** — models time-to-evacuation as function of SVI factors + fire proximity
- **Getis-Ord Gi*** — identifies statistically significant clusters of delayed evacuations
- **Alert classification triage** — prioritizes which vulnerable populations to alert first

---

## Repository Structure
```
widsdatathon-1/          ← local clone path: ~/widsdatathon-1
├── requirements.txt
├── .gitignore
├── 01_raw_data/
│   ├── external/SVI_2022_US_county.csv
│   └── processed/fire_events_with_svi_and_delays.csv  ← 15MB, force-committed with git add -f
├── 02_documentation/
│   └── WiDS_Context_Document.md
├── 03_analysis_scripts/
│   └── 07_build_real_delays.py   ← main data pipeline (~3 min, outputs fire_events_with_svi_and_delays.csv)
└── wids-caregiver-alert/src/     ← Streamlit Cloud main file path
    ├── wildfire_alert_dashboard.py       ← MAIN APP
    ├── auth_supabase.py                  ← Supabase auth (from Nadia)
    ├── signal_gap_analysis_page.py       ← NEW: Signal Gap Analysis page
    ├── data_governance.py                ← from Nadia
    ├── chatbot.py                        ← from Nadia
    ├── real_data_insights.py
    ├── agency_coverage_page.py
    ├── alert_channel_equity_page.py
    ├── caregiver_start_page.py
    ├── command_dashboard_page.py
    ├── coverage_analysis_page.py
    ├── fire_prediction_page.py
    ├── impact_projection_page.py
    ├── live_incident_feed.py
    ├── real_data_insights.py
    ├── risk_calculator_page.py
    ├── zone_duration_page.py
    ├── directions_page.py
    ├── geo_map.py
    ├── fire_data_integration.py
    ├── evacuation_planner_page.py
    ├── usfa-registry-national.csv
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
| caregiver_access_codes | 3 | EVAC-DEMO2025, DISPATCH-2025, ANALYST-WiDS9 |

### Views (queried by signal_gap_analysis_page.py)
| View | Status | Notes |
|------|--------|-------|
| v_dashboard_kpis | ✅ returns data | incidents_with_signal, pct_missing_action, median_delay_min, p90_delay_min |
| v_delay_benchmark | ✅ returns data | geo_event_id, first_signal_time, first_action_time, mins_signal_to_action |
| v_delay_summary_by_region_source | ✅ returns data | delay by region/agency |
| v_signal_without_action | ✅ returns data | fires with signal, no action |
| v_dangerous_delay_candidates | ⚠️ timeout | query too slow on 1.6M rows — needs index or limit |

**Note:** Views pull from geo_events_externalgeoevent (1.6M rows) + evac_zone_status_geo_event_map. The fire_events table is separate and feeds different analysis.

### RLS Status
- geo_events_externalgeoevent: RLS disabled (public read)
- evac_zone_status_geo_event_map: RLS disabled (public read)
- geo_events_geoevent: RLS disabled (public read)
- fire_events: RLS disabled, anon insert allowed

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
| Command Dashboard | Emergency Worker | ✅ working, evacuee tracker → Supabase |
| Fire Predictor | Emergency Worker | ⚠️ ValueError in plotly layout (fire_prediction_page.py line 261) |
| Start Here | Caregiver/Evacuee | ✅ working |
| Evacuation Planner | Caregiver/Evacuee | ✅ working |
| About | Analyst | ✅ working |
| Equity Analysis | Analyst | ✅ working |
| Risk Calculator | Analyst | ✅ working |
| Impact Projection | Analyst | ✅ working |
| Coverage Analysis | Analyst | ✅ graceful degradation (shows known stats) |
| Zone Duration | Analyst | ✅ graceful degradation (332MB CSV not deployed) |
| Fire Predictor | Analyst | ⚠️ same plotly error |
| Data Governance | Analyst | ✅ working (from Nadia) |
| Signal Gap Analysis | Analyst | ✅ working — uses fallback stats when Supabase views return 0 |

---

## Demo Login Credentials

| Username | Password | Role | Access Code |
|----------|----------|------|-------------|
| dispatcher_test | WiDS@2025! | Emergency Worker | DISPATCH-2025 |
| caregiver_test | WiDS@2025! | Caregiver/Evacuee | none needed |
| analyst_test | WiDS@2025! | Data Analyst | ANALYST-WiDS9 |

**Old hardcoded credentials (removed, replaced by Supabase auth):**
dispatcher/fire2025, caregiver/evacuate, analyst/datathon

---

## Current To-Do List (Pre-April Conference)

✅ Fix directions_page.py syntax error (nested f-string line 1301)
✅ Database backend for evacuee tracker (Supabase evacuation_status table)
✅ Zone duration — graceful degradation is sufficient (real stats shown)
✅ Deploy geo_events_geoevent to Supabase (live_incident_feed.py now queries it first)
✅ Integrate Nadia's auth_supabase.py, data_governance.py, chatbot.py
✅ Add Signal Gap Analysis page (analyst role)
✅ Upload fire_events_with_svi_and_delays.csv to Supabase fire_events table (62,696 rows)
✅ Add DISPATCH-2025 and ANALYST-WiDS9 to caregiver_access_codes table

⬜ Fix Fire Predictor ValueError (fire_prediction_page.py line 261, plotly update_layout)
⬜ Combine Lena + Katie maps / faster fire loading — need Katie's code
⬜ Fix v_dangerous_delay_candidates timeout (add index or LIMIT to view query)
⬜ Signal Gap Analysis: wire live Supabase data for the candidates table (currently fallback stats)

---

## Raw Data Files (01_raw_data/)
Large files — do not commit to git (except fire_events_with_svi_and_delays.csv via git add -f).

| File | Size | What It Is |
|------|------|------------|
| evac_zones_gis_evaczone.csv | 195 MB | 37,458 evacuation zone polygons |
| evac_zone_status_geo_event_map.csv | 330 KB | Links evac zones to fire events. 4,429 rows |
| evac_zones_gis_evaczonechangelog.csv | 332 MB | Full zone change history. 68,900 entries |
| fire_perimeters_gis_fireperimeter.csv | 381 MB | 6,207 fire perimeter polygons |
| geo_events_geoevent.csv | varies | 62,696 fire events 2021–2025 |
| geo_events_geoeventchangelog.csv | 1.03M rows | JSON changes. Real evacuation timing source |
| geo_events_externalgeoevent.csv | 1.5M rows | Alert channel distribution |
| geo_events_externalgeoeventchangelog.csv | varies | Cross-references WatchDuty with CAL FIRE etc |
| usfa-registry-national.csv | ~5 MB | ~35,000 US fire departments — copy to src/ |

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
4. **usfa-registry-national.csv must be in src/** — copy from 01_raw_data/
5. **GeoJSON files too large for git** — generate locally, copy to src/, never commit
6. **Supabase anon key must be single-line in secrets** — no line breaks
7. **Streamlit Cloud requires "Reboot app" after secrets changes**
8. **Only 653 fires have real evac timing** — WiDS dataset has limited formal activations. This is real, not simulated
9. **v_dangerous_delay_candidates times out** — query joins 1.6M row table without index
10. **fire_events Supabase columns** — last_spread_rate is TEXT (values: slow/moderate/rapid/extreme); first_order_at/first_warning_at/first_advisory_at are TEXT (timestamps as strings)

---

## External Data

**CDC SVI 2022** — 01_raw_data/external/SVI_2022_US_county.csv
- RPL_THEMES ≥ 0.75 = high vulnerability
- E_AGE65, E_POV150, E_DISABL, E_NOVEH — component estimates. FIPS = join key

**Census County Centroids** — wids-caregiver-alert/data/CenPop2020_Mean_CO.txt
- Used with scipy cKDTree for fast nearest-county spatial matching

**NASA FIRMS** — fetched at runtime, TTL=300s, no key needed
- VIIRS: https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv

---

## Map Layers (geo_map.py)

| Layer | Color | Default |
|-------|-------|---------|
| Fire Perimeters | Red/orange | ON |
| Normal Zones | Faint green | OFF |
| Watch / Shelter | Yellow | ON |
| Evacuation Warnings | Orange | ON |
| Evacuation Orders | Red | ON |
| Vulnerable Populations | Blue circles | ON |
| Live Fire Hotspots | Red circles | OFF |

---

## Live Incident Feed Priority (live_incident_feed.py)
1. 🟢 Supabase geo_events_geoevent (is_active=True, up to 2,000 rows)
2. 🟡 NASA FIRMS VIIRS (live, no key)
3. 🟡 NASA FIRMS MODIS (fallback)
4. ⚪ Empty DataFrame

---

## Signal Gap Analysis Page (signal_gap_analysis_page.py)
- Analyst role only
- Queries: v_dashboard_kpis, v_dangerous_delay_candidates, v_delay_summary_by_region_source
- Falls back to hardcoded stats when Supabase returns 0s: 41,906 signals, 99.7% no action, 3.5h median delay, 100h P90
- The fallback logic: `kpi = FALLBACK_STATS if not raw or raw.get("incidents_with_signal", 0) == 0 else raw`
