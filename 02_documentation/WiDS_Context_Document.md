# 49ers Intelligence Lab
## WiDS Datathon 2025 · Wildfire Caregiver Alert System
### Project Data & Code Reference — Context Document for Future Chats

---

## Project Overview
This system predicts evacuation delays for vulnerable populations during wildfires and routes proactive alerts to caregivers. It is the 49ers Intelligence Lab's submission to the WiDS Datathon 2025, currently in 2nd place.

**Core Research Question:** Do vulnerable populations (elderly, disabled, low-income) experience systematically longer evacuation delays during wildfires, and can a data-driven alert system reduce those delays?

---

## Key Findings

### Real Data Findings (WiDS 2021–2025 dataset — 653 fires with confirmed evac actions)
- Median time from fire start to evacuation order: **1.1 hours**
- Mean delay: **22.3 hours** (heavily right-skewed by slow-response fires)
- 90th percentile: **32.1 hours** — 1 in 10 fires takes over a day to get an order
- Fires in **vulnerable counties grow 17% faster** (11.71 vs 10.00 acres/hour)
- Vulnerable counties receive orders slightly faster at the median, but face faster-growing fires leaving less real response time
- 39.8% of all fire events occur in high-vulnerability counties (SVI ≥ 0.75)

### Modeled/Projected Findings
- Caregiver alert system projects saving 500–1,500 lives/year at 65% caregiver adoption
- Getis-Ord Gi* hotspot analysis identifies evacuation corridor bottlenecks before they form

### Models Used
- **Cox Proportional Hazards** — models time-to-evacuation as function of SVI factors + fire proximity. Uses real data from changelog.
- **Getis-Ord Gi*** — identifies statistically significant clusters of delayed evacuations
- **Alert classification triage** — prioritizes which vulnerable populations to alert first

---

## Repository Structure
```
widsdatathon/
├── requirements.txt
├── .gitignore                              ← includes secrets.toml, large GeoJSONs
├── 01_raw_data/
├── 02_documentation/
│   └── WiDS_Context_Document.md           ← THIS FILE
├── 03_analysis_scripts/
│   ├── 01_clean_data.py
│   ├── 02_data_profiling.py
│   ├── 03_eda_timeline.py
│   ├── 04_eda_early_signals.py
│   ├── 05_eda_geographic.py
│   ├── 06_run_all.py
│   └── 07_build_real_delays.py            ← main data pipeline
├── 04_results/
├── 05_visualizations/
├── 06_working_files/
└── wids-caregiver-alert/src/              ← Streamlit Community Cloud points here
    ├── wildfire_alert_dashboard.py        ← MAIN APP
    ├── real_data_insights.py
    ├── geo_map.py
    ├── fire_data_integration.py
    ├── evacuation_planner_page.py
    ├── evacuation_routes.py
    ├── directions_page.py
    ├── osm_routing.py
    ├── transit_and_safezones.py
    ├── us_cities_database.py
    ├── us_territories_data.py
    ├── usfa-registry-national.csv         ← in git (~5MB)
    ├── requirements.txt
    ├── __init__.py
    └── .streamlit/secrets.toml           ← NOT in git
```

---

## Raw Data Files (01_raw_data/)
Large files — do not commit to git. Generate locally and copy processed outputs to src/.

| File | Size | What It Is | Used By |
|------|------|------------|---------|
| evac_zones_gis_evaczone.csv | 195 MB | 37,458 evacuation zone polygons. WKT geometry, status (warnings/advisories/orders), external_status (full strings). Source: Genasys Protect. | preprocess_geo_data.py → evac_zones_map.geojson |
| evac_zone_status_geo_event_map.csv | 330 KB | Links evac zones to fire events. 4,429 rows. uid_v2 + geo_event_id + date_created. | 07_build_real_delays.py |
| evac_zones_gis_evaczonechangelog.csv | 332 MB | Full change history for every evac zone. 68,900 entries. | future: time-to-clear modeling |
| fire_perimeters_gis_fireperimeter.csv | 381 MB | 6,207 fire perimeter polygons from NIFC/FIRIS. 67% approved. | preprocess_geo_data.py → fire_perimeters_approved.geojson |
| geo_events_geoevent.csv | varies | 62,696 fire events 2021–2025. name, is_active, lat/lng, notification_type, date_created. Master join key. | 07_build_real_delays.py, dashboard |
| geo_events_geoeventchangelog.csv | 1.03M rows | JSON changes column. Key fields: data.evacuation_orders (3,430), data.evacuation_warnings (3,966), data.evacuation_advisories (1,618), data.acreage (38,678), data.containment (25,505), radio_traffic_indicates_rate_of_spread (9,157). **Real evacuation timing source.** | 07_build_real_delays.py |
| geo_events_externalgeoevent.csv | 1.5M rows | Alert channel distribution. 63% bots-extra-alerts, 7% bots-alertwest-ai. | future: alert coverage gap |
| geo_events_externalgeoeventchangelog.csv | varies | Cross-references WatchDuty with CAL FIRE, PulsePoint, WildCAD. external_source: 37% wildcad, 34% null, 29% other. | future: agency coverage metric |
| usfa-registry-national.csv | ~5 MB | ~35,000 US fire departments. Name, city, state, county, type, stations, FF counts. **Copy to src/.** | Command Dashboard |

---

## Processed Outputs (01_raw_data/processed/)
Generated locally — copy GeoJSON files to src/ for dashboard map. Large GeoJSONs are gitignored.

| File | Size | How Made | Notes |
|------|------|----------|-------|
| evac_zones_map.geojson | 32.2 MB | preprocess_geo_data.py — 3 decimal precision, max 50 vertices/ring | **Copy to src/. Gitignored (too large).** |
| fire_perimeters_approved.geojson | 36.1 MB | preprocess_geo_data.py — approved status only | **Copy to src/. Gitignored (too large).** |
| evac_zones_active.geojson | 171 MB | preprocess_geo_data.py intermediate | **Gitignored. Too large for GitHub.** |
| evac_zones_slim.geojson | 98.6 MB | preprocess_geo_data.py intermediate | **Gitignored. Too large for GitHub.** |
| geo_events_summary.csv | 1.5 MB | preprocess_geo_data.py Step 3 | 62,696 rows lightweight lookup |
| fire_events_with_svi_and_delays.csv | 15 MB | 07_build_real_delays.py | **Core analysis dataset. Force-committed with `git add -f`.** 653 fires with real evac timing, 19,392 with growth rates, SVI for all 62,696. |

**Copy GeoJSON and USFA to src/ after generating:**
```bash
cp 01_raw_data/processed/evac_zones_map.geojson wids-caregiver-alert/src/
cp 01_raw_data/processed/fire_perimeters_approved.geojson wids-caregiver-alert/src/
cp 01_raw_data/usfa-registry-national.csv wids-caregiver-alert/src/
```

---

## Critical Join Chain

```
geo_events_geoeventchangelog.csv
  JSON changes → data.evacuation_orders / warnings / advisories
  geo_event_id: normalize float string "22429.0" → "22429" with str(int(float(x)))
        ↓ join on geo_event_id
geo_events_geoevent.csv
  date_created: tz_localize('UTC') — file is timezone-naive
  lat/lng → spatial join to SVI via cKDTree nearest county
        ↓ subtract timestamps → real hours_to_order/warning/advisory

evac_zone_status_geo_event_map.csv (uid_v2 + geo_event_id + date_created)
        ↓ join on uid_v2
evac_zones_gis_evaczone.csv
  external_status: primary — full strings ("Evacuation Order", "Normal", "Advisory")
  status: fallback — plural lowercase ("warnings", "advisories", "orders")
```

| Left | Right | Key |
|------|-------|-----|
| evac_zones_gis_evaczone | evac_zone_status_geo_event_map | uid_v2 |
| evac_zone_status_geo_event_map | geo_events_geoevent | geo_event_id |
| fire_perimeters_gis_fireperimeter | geo_events_geoevent | geo_event_id |
| geo_events_geoevent | SVI_2022_US_county | Spatial: lat/lng → nearest FIPS via cKDTree |
| SVI_2022_US_county | CenPop2020_Mean_CO.txt | FIPS (5-digit) |

---

## Scripts

| Script | Location | What It Does |
|--------|----------|--------------|
| 07_build_real_delays.py | 03_analysis_scripts/ | **Main data pipeline.** Parses 178k changelog JSON rows, extracts real evac timestamps, computes fire growth rates, joins SVI. Outputs fire_events_with_svi_and_delays.csv. ~3 min. Run from repo root. |
| 01_clean_data.py | 03_analysis_scripts/ | Data cleaning |
| 02_data_profiling.py | 03_analysis_scripts/ | Data profiling |
| 03_eda_timeline.py | 03_analysis_scripts/ | Timeline EDA |
| 04_eda_early_signals.py | 03_analysis_scripts/ | Early signals EDA |
| 05_eda_geographic.py | 03_analysis_scripts/ | Geographic patterns EDA |
| 06_run_all.py | 03_analysis_scripts/ | Runs full analysis pipeline |

**Run build_real_delays.py:**
```bash
cd ~/widsdatathon
python3 03_analysis_scripts/07_build_real_delays.py
```

---

## How to Run Dashboard

```bash
cd /Users/lena/widsdatathon/wids-caregiver-alert/src
python3 -m streamlit run wildfire_alert_dashboard.py

# Install dependencies
pip3 install streamlit anthropic folium streamlit-folium plotly pandas numpy shapely scipy lifelines --break-system-packages
```

---

## Streamlit Community Cloud

- **Repo:** github.com/layesh1/widsdatathon
- **Branch:** main
- **Main file:** wids-caregiver-alert/src/wildfire_alert_dashboard.py
- **Logs:** share.streamlit.io → app → Manage app → Logs
- Auto-deploys on every push to main

---

## Dashboard Pages & Role Access

| Page | Role | Data Sources | Notes |
|------|------|-------------|-------|
| Command Dashboard | Emergency Worker | NASA FIRMS, SVI, USFA, GeoJSON | Real insight row: 1.1h median, 32h P90, 17% growth diff |
| Start Here | Caregiver/Evacuee | fire_events_with_svi_and_delays.csv | Urgency banner with real growth rate + 4 real metrics |
| Evacuation Planner | Caregiver/Evacuee | fire_data, vulnerable_populations | evacuation_planner_page.py module |
| Safe Routes & Transit | Caregiver/Evacuee | OSRM, fire_data | directions_page.py module |
| Dashboard | Analyst | NASA FIRMS, SVI, real insights | Overview map + real data summary panel |
| Equity Analysis | Analyst | fire_events_with_svi_and_delays.csv | Real histograms, growth rate chart, key finding narrative |
| Risk Calculator | Analyst | User inputs | SVI + distance + wind score formula |
| Impact Projection | Analyst | Real baseline + sliders | Uses real 1.1h baseline |
| AI Assistant | All roles | Anthropic claude-sonnet-4-6 | EVAC-OPS / SAFE-PATH / DATA-LAB personas |
| About | Analyst | — | Real findings cited |

---

## Demo Login Credentials

| Username | Password | Role |
|----------|----------|------|
| dispatcher | fire2025 | Emergency Worker |
| caregiver | evacuate | Caregiver/Evacuee |
| analyst | datathon | Data Analyst |

---

## API Keys & Secrets

- Model: claude-sonnet-4-6 · Cost: $3/M input, $15/M output tokens

---

## Map Layers (geo_map.py)

| Layer | Color | Default | Notes |
|-------|-------|---------|-------|
| Fire Perimeters | Red/orange | ON | fire_perimeters_approved.geojson |
| Normal Zones | Faint green | OFF | ~30,000 zones, hidden for performance |
| Watch / Shelter | Yellow | ON | Advisory, pre-evacuation, Be Ready |
| Evacuation Warnings | Orange | ON | Recommended evacuation |
| Evacuation Orders | Red | ON | Mandatory — most important layer |
| Vulnerable Populations | Blue circles | ON | Top 200 high-SVI counties |
| Live Fire Hotspots | Red circles | OFF | NASA FIRMS top 150 active fires |

---

## Git Workflow

```bash
# Standard push
cd ~/widsdatathon
git add -A
git add -f 01_raw_data/processed/fire_events_with_svi_and_delays.csv
git commit -m "your message"
git push layesh1 main

# If large file error → the two oversized GeoJSONs are already gitignored
# If secrets error → go to the GitHub URL in the error and click Allow, then rotate key

# Remotes
# layesh1 = https://github.com/layesh1/widsdatathon (your fork, auto-deploys)
# origin/kleedom = team repo (11 commits behind)
```

---

## Known Issues & Gotchas

1. **geo_event_id type mismatch** — changelog stores as "22429.0", geo_events as "22429". Fix: `str(int(float(x)))` with try/except for NaN rows.
2. **Timezone mismatch** — geo_events date_created is timezone-naive, changelog is UTC-aware. Fix: `.dt.tz_localize('UTC')` on fire_start.
3. **fire_events_with_svi_and_delays.csv is gitignored** — use `git add -f` to force-add it.
4. **usfa-registry-national.csv must be in src/** — copy from 01_raw_data/.
5. **GeoJSON files are too large for git** — generate locally, copy to src/, never commit.
6. **evac_zones_active.geojson and evac_zones_slim.geojson** — removed from git history on 2026-02-21 via filter-branch. Gitignored. Keep locally only.
7. **secrets.toml was in git history** — removed and gitignored on 2026-02-21. Rotate API key.
8. **Only 653 fires have real evac timing** — WiDS dataset has limited formal activations. 19,392 fires have growth rate data. This is real, not simulated.

---

## External Data

**CDC SVI 2022** — 01_raw_data/external/SVI_2022_US_county.csv
- RPL_THEMES ≥ 0.75 = high vulnerability. Themes: RPL_THEME1–4.
- E_AGE65, E_POV150, E_DISABL, E_NOVEH — component estimates. FIPS = join key.

**Census County Centroids** — wids-caregiver-alert/data/CenPop2020_Mean_CO.txt
- STATEFP (2-digit) + COUNTYFP (3-digit) + LATITUDE + LONGITUDE
- Used with scipy cKDTree for fast nearest-county spatial matching

**NASA FIRMS** — fetched at runtime, fire_data_integration.py, TTL=300s, no key needed

---

## Future Work (Pre-April Conference)

- [ ] Agency coverage gap metric — geo_events_externalgeoeventchangelog.csv, multi-agency reporting as severity proxy
- [ ] Alert channel equity — geo_events_externalgeoevent.csv channel data, show manual vs automated coverage by county
- [ ] Live incident feed — replace NASA FIRMS fallback with geo_events_geoevent.csv is_active fires
- [ ] Zone duration analysis — evac_zones_gis_evaczonechangelog.csv, time-in-status per zone
