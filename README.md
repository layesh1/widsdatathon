# Wildfire Caregiver Alert System

**49ers Intelligence Lab — WiDS Datathon 2025 | UNC Charlotte**

A data-driven early warning system that detects the "silent window" between fire ignition and official evacuation orders, and routes proactive alerts to caregivers of vulnerable populations before official orders are issued.

---

## The Problem

**73% of US wildfires produce no public alert.** Of 62,696 fire events in the WiDS 2021–2025 dataset, 46,053 were classified `silent` — the public received no notification of any kind. Of those, only **1 received an evacuation order**.

Meanwhile, existing tools (WatchDuty, Nixle, Wireless Emergency Alerts) only notify people *after* an official order is issued. There is no system that:

- Detects the pre-order signal window and routes early alerts to caregivers
- Prioritizes by CDC Social Vulnerability Index (SVI), not just proximity
- Measures equity gaps in alert coverage by county
- Tracks evacuees in real time for dispatchers

**The gap kills people.** 211 of 298 extreme-spread fires (70.8%) received no evacuation action. Vulnerable counties see fires grow 17% faster than average. Median time from fire start to evacuation order: **1.1 hours** — but 1 in 10 fires takes over 32 hours.

---

## Key Statistics (WiDS Dataset, 2021–2025)

| Metric | Value |
|--------|-------|
| Total fire incidents | 62,696 |
| Silent fires (no public alert) | 46,053 (73.5%) |
| Silent fires that received an evacuation order | 1 |
| Fires with early signal, no evacuation action | 41,906 (99.74%) |
| Extreme-spread fires with no evacuation action | 211 / 298 (70.8%) |
| Median time to evacuation order | 1.1 hours |
| 90th percentile time to order | 32.1 hours |
| Fire growth rate in vulnerable counties (vs average) | +17% faster |
| Peak fire month | July (13,650 fires) |
| Peak fire detection hour | 9 pm (6,131 fires) |

---

## Live App

Deployed on Streamlit Cloud — auto-deploys on push to `main`:

**[Open the app](https://widsdatathon.streamlit.app)**

### Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `caregiver_test` | `WiDS@2025!` | Caregiver/Evacuee |
| `dispatcher_test` | `WiDS@2025!` | Emergency Worker |
| `analyst_test` | `WiDS@2025!` | Data Analyst |

---

## App Structure

The app has three role-based views, each with purpose-built navigation:

### Caregiver / Evacuee
| Page | Description |
|------|-------------|
| Am I Safe? | Check active fires near your address (bilingual EN/ES) |
| Evacuation Plan | Routes, shelter locations, go-bag checklist |
| Risk Calculator | Personal risk profile based on your county SVI + fire history |
| My County | Local silent fire rate, SVI tier, alert channel count |
| Why This App? | Plain-language explanation of the alert gap problem |

### Emergency Worker / Dispatcher
| Page | Description |
|------|-------------|
| Command | Live incident map (61,691 WiDS + NASA FIRMS), evacuee tracker, SMS alerts |
| Fire Forecast | Physics-based fire spread model with live weather |
| At-Risk Zones | Gi* hotspot map + county-level drill-down |
| Coverage Gaps | Alert channel coverage + silent fire escalation funnel |
| Resources | USFA national fire department directory |

### Data Analyst
| Page | Description |
|------|-------------|
| Overview | Project background and methodology |
| Signal Gap | Alert failure analysis + silent fire tracker (46,053 fires) |
| Equity & Risk | SVI vulnerability analysis + coverage equity |
| Geographic | Gi* hotspot map, channel coverage, county drill-down |
| Fire Patterns | Temporal patterns — hour-of-day, monthly, heatmap |
| Technical | Data governance, IRWIN linkage, zone duration |
| Fire Predictor | Physics-based fire spread prediction |

---

## Fire Spread Model (Scientific Basis)

The **Fire Forecast** page uses peer-reviewed fire science models:

- **Van Wagner (1969)** — Elliptical fire shape: L/W = 0.936·exp(0.2566·w) + 0.461·exp(-0.1548·w) - 0.397. Computes head, backing, and flank spread rates from eccentricity.
- **Rothermel (1972)** — Surface fire spread rate: R = R₀ × η_M × (1 + φ_W + φ_S). Moisture damping, wind coefficient, and slope coefficient calibrated to BehavePlus NFFL fuel model tables (Grass, Chaparral, Southern Rough, Timber Litter, Logging Slash).
- **Canadian FWI System** (Van Wagner & Pickett 1985) — Full FFMC, ISI, DMC, DC, BUI, FWI computation from live weather. Five danger classes from Low to Extreme.
- **Byram (1959)** — Fireline intensity: I = h × w × R (kW/m). Thresholds for manageable vs. uncontrollable fire.
- **Open-Meteo APIs** (free, no key) — Live ECMWF weather (temperature, RH, wind, precipitation) and CAMS Copernicus air quality (US AQI, PM2.5, PM10, dust, CO).

Fire perimeters are rendered as geographic ellipses at 1h / 3h / 6h / 12h / 24h on an OpenStreetMap base map.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend / App | Streamlit |
| Database | Supabase (PostgreSQL) |
| Auth | Custom PBKDF2-HMAC-SHA256 (260k iterations) |
| Maps | Plotly Scattermapbox (OpenStreetMap, no token), Plotly Scattergeo, Folium |
| Live Fire Data | NASA FIRMS VIIRS |
| Weather / AQI | Open-Meteo + CAMS Copernicus (free, no key) |
| SMS Alerts | Twilio (optional — graceful no-op if unconfigured) |
| Spatial Analysis | scipy cKDTree (nearest-county), Getis-Ord Gi* |
| Data | CDC SVI 2022, USFA Fire Department Registry, NIFC/IRWIN |
| Deployment | Streamlit Cloud (auto-deploy from main) |

---

## Repository Structure

```
widsdatathon-1/
├── README.md
├── requirements.txt
├── 01_raw_data/
│   ├── processed/
│   │   ├── fire_events_with_svi_and_delays.csv   # 62,696 fires, 38 columns
│   │   ├── county_fire_stats.csv                  # 1,016 counties
│   │   ├── county_gi_star.csv                     # 543 counties, Gi* z-scores
│   │   └── county_channel_coverage.csv            # 732 counties, alert channels
│   └── external/
│       └── SVI_2022_US_county.csv                 # CDC Social Vulnerability Index
├── 02_documentation/
│   └── WiDS_Context_Document.md                   # Full project reference
├── 03_analysis_scripts/
│   └── 07_build_real_delays.py                    # Main data pipeline (~3 min)
└── wids-caregiver-alert/src/
    ├── wildfire_alert_dashboard.py                 # App entry point
    ├── fire_prediction_page.py                     # Van Wagner + Rothermel + FWI
    ├── command_dashboard_page.py                   # Hexbin map + evacuee tracker
    ├── signal_gap_analysis_page.py                 # 73% silent fire analysis
    ├── caregiver_start_page.py                     # Bilingual caregiver landing
    ├── risk_calculator_page.py                     # Personal risk profile
    ├── hotspot_map_page.py                         # Gi* hotspot map
    ├── county_drilldown_page.py                    # 1,016-county drill-down
    ├── channel_coverage_page.py                    # Alert channel equity
    ├── silent_escalation_page.py                   # Silent fire funnel
    ├── caregiver_county_page.py                    # My County (caregiver)
    ├── caregiver_why_page.py                       # Why This App? (caregiver)
    ├── dispatcher_risk_zones_page.py               # At-Risk Zones (dispatcher)
    ├── dispatcher_coverage_page.py                 # Coverage Gaps (dispatcher)
    ├── dispatcher_resources_page.py                # USFA Resources (dispatcher)
    ├── ui_utils.py                                 # Shared design system
    ├── sms_alert.py                                # Twilio SMS module
    ├── auth_supabase.py                            # PBKDF2 auth + forgot flow
    └── requirements.txt
```

---

## Running Locally

```bash
git clone https://github.com/layesh1/widsdatathon.git
cd widsdatathon-1/wids-caregiver-alert/src

pip install -r requirements.txt

# Add secrets (Supabase + optional Twilio)
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
SUPABASE_URL = "https://fguvvhqvzifnsihhomcv.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
ANTHROPIC_API_KEY = "sk-ant-..."   # optional, for chatbot

[twilio]
account_sid = "..."   # optional, for SMS alerts
auth_token  = "..."
from_number = "+1..."
EOF

streamlit run wildfire_alert_dashboard.py
```

The app fetches live weather and AQI automatically — no additional API keys required for the fire spread model.

---

## Data Sources

| Source | Description | Records |
|--------|-------------|---------|
| WiDS 2025 Dataset | Fire events, evac zones, alerts, perimeters | 62,696 fires |
| CDC SVI 2022 | County-level Social Vulnerability Index | All US counties |
| NASA FIRMS VIIRS | Live active fire detections | Real-time |
| Open-Meteo / CAMS | Live weather + air quality | Real-time, free |
| USFA Registry | National fire department directory | ~27,000 depts |
| NIFC / IRWIN | Incident perimeters + IRWIN IDs | 6,207 perimeters |

---

## Research Questions

1. Do vulnerable populations (elderly, disabled, low-income, minority) experience systematically longer evacuation delays during wildfires?
2. Can a data-driven caregiver alert system detect the pre-order window and reduce those delays?
3. Which counties have the highest combination of fire risk and alert system fragility?

**Findings:**
- SVI minority sub-theme has the strongest correlation with evacuation delay (r = -0.233)
- 48% of counties have only a single alert channel — single point of failure
- Getis-Ord Gi* identifies statistically significant high-risk clusters in Northern CA, Southern CA, and OR Cascades
- Caregiver alert system projects saving 500–1,500 lives/year at 65% adoption

---

## Conference Presentation

**April 2026** — WiDS Datathon Conference

Headline finding: *73% of US wildfires fire silently. In high-SVI counties where fires grow 17% faster, this silent window is when caregivers need to act — and no existing tool reaches them.*

---

## Team

**Lena** ([@layesh1](https://github.com/layesh1)) + **Nadia** ([@Ncashy](https://github.com/Ncashy))
UNC Charlotte — 49ers Intelligence Lab

Questions: layesh1@charlotte.edu
