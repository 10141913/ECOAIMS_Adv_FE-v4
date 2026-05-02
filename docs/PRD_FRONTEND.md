# ECOAIMS Frontend — Product Requirements Document (PRD)

> **Document ID:** PRD-FE-001  
> **Version:** 1.0.0  
> **Status:** Final  
> **Author:** FE Engineering Team  
> **Last Updated:** 2026-04-24  
> **Repository:** `ECOAIMS_Adv_FE v-4` (Frontend)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Overview](#2-product-overview)
3. [User Personas](#3-user-personas)
4. [Functional Requirements](#4-functional-requirements)
    - 4.1 [Authentication & Security Gateway](#41-authentication--security-gateway)
    - 4.2 [Home Dashboard](#42-home-dashboard)
    - 4.3 [Energy Monitoring](#43-energy-monitoring)
    - 4.4 [Forecasting](#44-forecasting)
    - 4.5 [Energy Optimization](#45-energy-optimization)
    - 4.6 [Precooling / LAEOPF](#46-precooling--laeopf)
    - 4.7 [Battery Management System (BMS)](#47-battery-management-system-bms)
    - 4.8 [Indoor Climate Monitoring](#48-indoor-climate-monitoring)
    - 4.9 [Reports & Analytics](#49-reports--analytics)
    - 4.10 [Settings & Configuration](#410-settings--configuration)
    - 4.11 [About & System Info](#411-about--system-info)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [System Architecture](#6-system-architecture)
7. [Backend Integration & Contract System](#7-backend-integration--contract-system)
8. [Data Flow](#8-data-flow)
9. [Error Handling & Graceful Degradation](#9-error-handling--graceful-degradation)
10. [UI/UX Design Principles](#10-uiux-design-principles)
11. [Security Requirements](#11-security-requirements)
12. [Performance Requirements](#12-performance-requirements)
13. [Testing Strategy](#13-testing-strategy)
14. [Deployment & Operations](#14-deployment--operations)
15. [Glossary](#15-glossary)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

ECOAIMS (Energy Cost Optimization and Artificial Intelligence Management System) is a **Dash/Plotly-based** frontend application that provides a unified, real-time energy management dashboard for commercial buildings. The frontend communicates with a FastAPI backend service to deliver monitoring, forecasting, optimization, precooling, battery management, indoor climate tracking, and reporting capabilities.

This document defines the product requirements from the **Frontend Engineering perspective**, covering all UI components, callback logic, service integrations, error handling patterns, contract validation, and operational characteristics of the application.

### 1.1 Key Objectives

| Objective | Description |
|-----------|-------------|
| **Real-time Monitoring** | Display live energy data from solar PV, wind turbine, battery, grid, and biofuel sources with sub-minute refresh |
| **Intelligent Optimization** | Run energy optimization simulations with configurable priorities (renewable, battery, grid) |
| **Precooling / LAEOPF** | Advanced precooling optimization with thermal, latent, exergy, and psychrometric analysis across multi-zone buildings |
| **Battery Management** | RL-based battery dispatch with DRL tuner and policy proposer |
| **Indoor Climate** | Live sensor feed (temperature, humidity, CO2) with CSV import workflow |
| **Contract System** | Runtime endpoint contract validation, negotiation, and cross-repo evidence chain |
| **Graceful Degradation** | All features degrade gracefully when backend is unavailable, with clear user feedback |

---

## 2. Product Overview

### 2.1 Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| **Framework** | Dash (Plotly) | Enterprise-grade reactive web framework |
| **Language** | Python 3.10+ | Type hints throughout |
| **HTTP Client** | `requests` | Synchronous HTTP calls with timeout management |
| **Charts** | Plotly Graph Objects (`go.Figure`) | Gauges, bar, line, scatter, pie charts |
| **UI Components** | Dash HTML/DCC components | Custom CSS styling |
| **Auth** | PBKDF2 + CAPTCHA (SVG) + CSRF tokens | Session-based with rate limiting |
| **Persistence** | JSON file-based settings | `data/user_settings.json` |
| **Monitoring** | Prometheus metrics endpoint | `/metrics` |
| **Testing** | pytest | 40+ test files |

### 2.2 Application Structure

```
ecoaims_frontend/
├── app.py                          # Application entry point, auth gateway, Flask routes
├── config.py                       # Central configuration (API URLs, colors, limits)
├── layouts/                        # UI layout definitions
│   ├── main_layout.py              # Main shell with 10 tabs + dcc.Store/Interval
│   ├── home_layout.py              # Home/runbook tab
│   ├── dashboard_layout.py         # Monitoring tab
│   ├── forecasting_layout.py       # Forecasting tab
│   ├── optimization_layout.py      # Optimization tab
│   ├── precooling_layout.py        # Precooling/LAEOPF tab
│   ├── bms_layout.py               # BMS tab
│   ├── indoor_layout.py            # Indoor Climate tab
│   ├── reports_layout.py           # Reports tab (1689 lines, largest layout)
│   ├── settings_layout.py          # Settings tab
│   └── about_layout.py             # About tab
├── callbacks/                      # Dash callback registrations
│   ├── readiness_callbacks.py      # Backend readiness polling (2s interval)
│   ├── home_callbacks.py           # Home page logic
│   ├── main_callbacks.py           # Monitoring dashboard logic (909 lines)
│   ├── forecasting_callbacks.py    # Forecasting logic
│   ├── optimization_callbacks.py   # Optimization logic
│   ├── precooling_callbacks.py     # Precooling logic (2405 lines, most complex)
│   ├── precooling_settings_callbacks.py  # Precooling settings (1028 lines)
│   ├── bms_callbacks.py            # BMS logic (1241 lines)
│   ├── indoor_callbacks.py         # Indoor climate logic
│   ├── settings_callbacks.py       # Settings logic
│   ├── about_callbacks.py          # About page logic
│   └── reports_callbacks.py        # Reports logic (embedded in reports_layout.py)
├── services/                       # Backend API integration layer
│   ├── data_service.py             # Core energy data fetching (792 lines)
│   ├── optimization_service.py     # Optimization engine (619 lines)
│   ├── precooling_api.py           # Precooling API wrapper (534 lines)
│   ├── precooling_normalizer.py    # Precooling data normalizer (605 lines)
│   ├── bms_service.py              # BMS simulation service
│   ├── indoor_api.py               # Indoor climate API wrapper
│   ├── reports_api.py              # Reports API wrapper (299 lines)
│   ├── readiness_service.py        # Backend readiness checker (430 lines)
│   ├── live_data_service.py        # Live sensor data from CSV
│   ├── live_state_push_service.py  # Push live state to backend
│   ├── contract_negotiation.py     # Contract negotiation service
│   ├── contract_registry.py        # Contract registry (436 lines)
│   ├── contract_sync.py            # Contract synchronization
│   ├── runtime_contracts.py        # Runtime contract validators
│   ├── runtime_contract_mismatch.py # Contract mismatch builder
│   ├── operational_policy.py       # Feature decision engine
│   ├── monitoring_diag.py          # Monitoring diagnostics
│   ├── monitoring_history_update.py # History seeding
│   ├── optimizer_tuner_api.py      # DRL tuner API
│   ├── policy_proposer_api.py      # Policy proposer API
│   ├── system_runtime_api.py       # Runtime config API
│   ├── settings_service.py         # Settings persistence
│   ├── base_url_service.py         # URL resolution
│   └── http_trace.py               # HTTP tracing headers
├── components/                     # Reusable UI components
│   ├── alerts.py                   # Alert notifications
│   ├── battery.py                  # Battery visual
│   ├── charts.py                   # Trend charts
│   ├── gauges.py                   # Gauge figures
│   ├── impact.py                   # CO2 impact panel
│   ├── renewable_comparison.py     # Renewable comparison cards
│   ├── sensor_health.py            # Sensor health card
│   ├── tables.py                   # Status tables
│   └── precooling/                 # Precooling sub-components
│       ├── header.py, kpi_panel.py, overview_cards.py
│       ├── scenario_lab.py, schedule_panel.py
│       ├── settings_panel.py, thermal_panel.py
│       ├── alerts_panel.py, optimization_panel.py
│       └── styles.py
├── ui/                             # Error/status UI components
│   ├── error_ui.py                 # error_text, status_banner, error_banner, error_figure
│   ├── contract_error_ui.py        # Contract mismatch error rendering
│   ├── contract_negotiation_error.py # Negotiation error rendering
│   └── runtime_contract_banner.py  # Runtime contract mismatch banner
└── tests/                          # Test suite (40+ files)
```

### 2.3 Tab Overview

| # | Tab Name | Route | Primary Function |
|---|----------|-------|-----------------|
| 1 | **Home** | `tab-home` | Runbook, doctor report, contract summary, dispatch builder |
| 2 | **Monitoring** | `tab-monitoring` | Live gauges, trend graphs, CO2 impact, KPI dashboard |
| 3 | **Forecasting** | `tab-forecasting` | Hourly/daily consumption, renewable, accuracy graphs |
| 4 | **Optimization** | `tab-optimization` | Energy optimization with priority/constraint sliders |
| 5 | **Precooling/LAEOPF** | `tab-precooling` | Multi-zone precooling optimization with full analytics |
| 6 | **BMS** | `tab-bms` | Battery SOC, RL dispatch, DRL tuner, policy proposer |
| 7 | **Indoor Climate** | `tab-indoor` | Live sensor feed, CSV import, maintenance mode |
| 8 | **Reports** | `tab-reports` | Precooling impact reports, CSV export, session detail |
| 9 | **Settings** | `tab-settings` | User preferences, runtime config, live energy toggle |
| 10 | **About** | `tab-about` | Runtime info, build ID, contract hash, registry refresh |

---

## 3. User Personas

### 3.1 Building Energy Manager (Primary)

- **Needs:** Real-time energy monitoring, optimization recommendations, precooling schedules, KPI tracking
- **Uses:** Monitoring tab, Optimization tab, Precooling tab, Reports tab
- **Pain points:** Backend downtime, stale data, complex configuration

### 3.2 Facility Operator

- **Needs:** Indoor climate monitoring, CSV data import, maintenance alerts
- **Uses:** Indoor Climate tab, Home tab (runbook)
- **Pain points:** Slow polling, unclear error messages

### 3.3 Energy Researcher / Analyst

- **Needs:** Historical data analysis, forecasting accuracy, precooling impact reports, golden sample export
- **Uses:** Reports tab, Forecasting tab, About tab
- **Pain points:** Insufficient history data, contract version mismatches

### 3.4 System Administrator

- **Needs:** Runtime configuration, backend health monitoring, contract verification
- **Uses:** Settings tab, About tab, Home tab (doctor report)
- **Pain points:** Port misconfiguration, identity mismatches

---

## 4. Functional Requirements

### 4.1 Authentication & Security Gateway

**File:** [`ecoaims_frontend/app.py`](ecoaims_frontend/app.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| AUTH-01 | CAPTCHA challenge on login page | High | SVG-based CAPTCHA generated at `/captcha.svg` with random math expression |
| AUTH-02 | CSRF token validation on login POST | High | Token embedded in login form, validated server-side |
| AUTH-03 | PBKDF2 password hashing | High | SHA256-based PBKDF2 with configurable iterations |
| AUTH-04 | Session management with 720min TTL | High | Flask session with 12-hour expiry |
| AUTH-05 | Rate limiting: 5 attempts per 15min window | High | Per-IP counter with sliding window |
| AUTH-06 | Proxy mode support | Medium | `X-Forwarded-For` header parsing for rate limiting |
| AUTH-07 | HTTPS redirect enforcement | Medium | Configurable via `ENFORCE_HTTPS` env var |
| AUTH-08 | Logout endpoint with session clear | High | `/logout` route destroys session |

**CAPTCHA Implementation Details:**
- Math expression rendered as SVG with random operator (+, -, ×)
- Answer stored in session as `captcha_answer`
- Regenerated on each failed attempt
- Token salted with `captcha_salt` from session

### 4.2 Home Dashboard

**Files:** [`ecoaims_frontend/layouts/home_layout.py`](ecoaims_frontend/layouts/home_layout.py:7), [`ecoaims_frontend/callbacks/home_callbacks.py`](ecoaims_frontend/callbacks/home_callbacks.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| HOME-01 | Generate runbook from backend startup-info | High | Fetches `/api/startup-info`, renders as markdown with fallback |
| HOME-02 | Doctor report with contract change detection | High | Compares current vs previous readiness state, highlights changes |
| HOME-03 | Contract mismatch summary | High | Aggregates mismatches across monitoring/optimization/precooling/reports |
| HOME-04 | Dispatch payload builder | Medium | Builds RL dispatch payload from current energy state |
| HOME-05 | Backend identity display | Low | Shows identity_id, repo_id, server_role, git_sha |

### 4.3 Energy Monitoring

**Files:** [`ecoaims_frontend/layouts/dashboard_layout.py`](ecoaims_frontend/layouts/dashboard_layout.py:4), [`ecoaims_frontend/callbacks/main_callbacks.py`](ecoaims_frontend/callbacks/main_callbacks.py:1), [`ecoaims_frontend/services/data_service.py`](ecoaims_frontend/services/data_service.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| MON-01 | Real-time gauge display for 5 energy sources | High | Solar PV, Wind Turbine, Battery, Grid, Biofuel — each with `create_gauge_figure()` |
| MON-02 | Trend graph with consumption vs renewable | High | Bar chart (consumption) + line chart (renewable) via `create_trend_graph()` |
| MON-03 | CO2 impact panel | High | Calculates CO2 from grid consumption (0.85 kg/kWh), car/LED equivalence |
| MON-04 | Renewable comparison cards | High | 3-hour aggregated comparison for all sources |
| MON-05 | KPI dashboard (6 cards) | High | Peak Load, CO2 Emission, EUI, MAPE, Renewable Fraction, Total Cost |
| MON-06 | Sensor health card | Medium | Active/stale/missing counts with NORMAL/WARNING/CRITICAL status |
| MON-07 | Comparison status banner | High | 5 states: contract mismatch, negotiation blocked, insufficient history, ready, waiting |
| MON-08 | Dashboard caching | Medium | `_dashboard_cache` with TTL to reduce backend load |
| MON-09 | History seeding | Medium | `request_history_seed()` tries multiple candidate URLs |
| MON-10 | Alert notifications | Medium | Stale data, battery low/full, grid low, renewable insufficient |

**Data Adaptation Pipeline:**

```
Backend Response
    │
    ├── energy-data endpoint (canonical)
    │   └── _adapt_energy_data_contract_to_monitoring()
    │       ├── solar: {value, max, value_3h, source}
    │       ├── wind: {value, max, value_3h, source}
    │       ├── grid: {value, max, value_3h, source}
    │       ├── biofuel: {value, max, value_3h, source}
    │       └── battery: {value, max, value_3h, source, soc_pct}
    │
    ├── dashboard/state endpoint (legacy)
    │   └── _adapt_dashboard_state_to_monitoring()
    │       ├── energy_mix_kw / energy_mix_pct
    │       ├── battery SOC from multiple sources
    │       └── state_meta with staleness detection (900s threshold)
    │
    └── Local simulation (fallback)
        └── _generate_local_simulated_energy_data()
            └── Random values within configured limits
```

### 4.4 Forecasting

**Files:** [`ecoaims_frontend/layouts/forecasting_layout.py`](ecoaims_frontend/layouts/forecasting_layout.py:9), [`ecoaims_frontend/callbacks/forecasting_callbacks.py`](ecoaims_frontend/callbacks/forecasting_callbacks.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| FRC-01 | Period selection (hourly/daily) | High | Dropdown with scatter (hourly) or bar (daily) rendering |
| FRC-02 | Consumption forecast graph | High | 24-hour or 7-day consumption projection |
| FRC-03 | Renewable forecast graph | High | Solar PV + Wind Turbine forecast with bell curve |
| FRC-04 | Accuracy comparison graph | High | Past 24 hours actual vs forecast |
| FRC-05 | Graceful degradation on error | High | Falls back to `error_figure()` on exception |

### 4.5 Energy Optimization

**Files:** [`ecoaims_frontend/layouts/optimization_layout.py`](ecoaims_frontend/layouts/optimization_layout.py:4), [`ecoaims_frontend/callbacks/optimization_callbacks.py`](ecoaims_frontend/callbacks/optimization_callbacks.py:1), [`ecoaims_frontend/services/optimization_service.py`](ecoaims_frontend/services/optimization_service.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| OPT-01 | Priority selection (renewable/battery/grid) | High | Dropdown with 3 modes |
| OPT-02 | Battery capacity slider | High | 0-100% range |
| OPT-03 | Grid limit slider | High | 0-100% range |
| OPT-04 | Pie chart: energy source distribution | High | After optimization run |
| OPT-05 | Bar chart: before/after comparison | High | Baseline vs optimized |
| OPT-06 | Recommendation text | High | Human-readable optimization suggestion |
| OPT-07 | Live sensor data integration | High | Merges backend state with CSV sensor data |
| OPT-08 | Circuit breaker pattern | High | `_BREAKER` with fail_max=5, reset_timeout=30s |
| OPT-09 | Adaptive cache with TTL | Medium | `_OPT_CACHE` with 0.2-3.0s TTL based on input volatility |
| OPT-10 | In-flight request deduplication | Medium | `_INFLIGHT` dict with 15s wait timeout |
| OPT-11 | Prometheus metrics export | Medium | Latency histogram, cache stats, circuit breaker stats |
| OPT-12 | Backend cooldown | High | `_BACKEND_DOWN_UNTIL_TS` to avoid hammering |

**Optimization Flow:**

```
User clicks "Run Optimization"
    │
    ├── Check feature decision (effective_feature_decision)
    │   ├── live → proceed with backend
    │   ├── placeholder → use local simulation
    │   └── blocked → show error
    │
    ├── Fetch live state from backend /dashboard/state
    │
    ├── Merge with get_live_sensor_data() (CSV)
    │
    ├── Check cache (_OPT_CACHE)
    │   ├── HIT → return cached result
    │   └── MISS → proceed
    │
    ├── Check in-flight (_INFLIGHT)
    │   ├── DEDUP → wait for existing request
    │   └── NEW → register and proceed
    │
    ├── Call backend POST /optimize
    │   ├── Success → parse response
    │   └── Failure → circuit breaker, fallback to local simulation
    │
    └── Render pie chart + bar chart + recommendation text
```

### 4.6 Precooling / LAEOPF

**Files:** [`ecoaims_frontend/layouts/precooling_layout.py`](ecoaims_frontend/layouts/precooling_layout.py:14), [`ecoaims_frontend/callbacks/precooling_callbacks.py`](ecoaims_frontend/callbacks/precooling_callbacks.py:1) (2405 lines), [`ecoaims_frontend/callbacks/precooling_settings_callbacks.py`](ecoaims_frontend/callbacks/precooling_settings_callbacks.py:1) (1028 lines), [`ecoaims_frontend/services/precooling_api.py`](ecoaims_frontend/services/precooling_api.py:1) (534 lines), [`ecoaims_frontend/services/precooling_normalizer.py`](ecoaims_frontend/services/precooling_normalizer.py:1) (605 lines)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| PRC-01 | Multi-zone discovery and management | High | Floor-zone mapping (floor1/2/3 × zone a/b/c), zone discovery with caching |
| PRC-02 | Status overview with hero card | High | Manual override state, thermal/latent/exergy state, optimization insight |
| PRC-03 | Schedule timeline visualization | High | Gantt-like timeline from schedule data |
| PRC-04 | Scenario comparison cards | High | Multiple scenario cards with KPI comparison |
| PRC-05 | KPI dashboard (8+ metrics) | High | Peak reduction, energy saving, cost saving, CO2 reduction, comfort compliance, battery impact, exergy efficiency, IPEI, SHR |
| PRC-06 | Simulation engine | High | POST to backend `/api/precooling/simulate` with full payload |
| PRC-07 | Candidate ranking and selection | High | Table with selectable rows, apply recommendation |
| PRC-08 | Thermal analysis panel | High | Load before/after, temperature before/after, peak comparison |
| PRC-09 | Latent analysis panel | High | Humidity before/after, latent load analysis |
| PRC-10 | Exergy analysis panel | High | Exergy efficiency, destruction, IPEI |
| PRC-11 | Psychrometric analysis | High | Comfort compliance gauge, psychrometric chart |
| PRC-12 | Objective breakdown figure | High | Weighted objective visualization |
| PRC-13 | Constraint matrix display | High | Active constraints with values |
| PRC-14 | Alerts and audit tables | High | System alerts and audit trail |
| PRC-15 | Manual override controls | High | Request/approve/cancel override with temp/RH/duration/HVAC mode |
| PRC-16 | Action buttons (activate/pause/cancel/rule-based/recompute/stop/advisory) | High | 8 action types with confirmation |
| PRC-17 | Force fallback with confirmation | High | Two-step confirmation dialog |
| PRC-18 | Golden sample export | High | Bundles simulate request + result + doctor report |
| PRC-19 | Selector preview with audit | High | Preview selector recommendations with audit panel |
| PRC-20 | Settings management (60+ fields) | High | 8 sections: general, time_window, comfort_limits, hvac_constraints, building_parameters, energy_coordination, objective_weights, fallback_rules, advanced |
| PRC-21 | Settings validation, save, reset, apply | High | Full CRUD for precooling configuration |
| PRC-22 | Scope management (floor/zone selection) | High | Copy scope from precooling, validate selection |
| PRC-23 | Mode push to backend | Medium | Sync monitoring/advisory/active mode to backend |
| PRC-24 | Running state for simulation buttons | Medium | Disable buttons during simulation, show spinner |

**Precooling Data Normalization (`precooling_normalizer.py`):**

The normalizer uses a flexible key resolution pattern (`_pick()` function) that tries multiple key names to handle backend schema variations:

```python
def _pick(obj, keys, default=None):
    for key in keys:
        if key in obj:
            return obj[key]
    return default
```

| Normalizer | Input | Output |
|------------|-------|--------|
| `normalize_status()` | Raw status dict | Manual override, thermal/latent/exergy state, optimization insight, settings snapshot |
| `normalize_schedule()` | Raw schedule dict | Timeline slots with merged temperature/RH series |
| `normalize_scenarios()` | Raw scenarios dict | Comparison rows, candidates with KPI |
| `normalize_kpi()` | Raw KPI dict | 8+ normalized KPI metrics with fallback defaults |
| `normalize_scenario_kpi()` | Scenario KPI block | Normalized KPI float values |
| `normalize_status_overview()` | Sim result | Status overview with slot times |
| `normalize_alerts()` | Raw alerts | Normalized alert list |
| `normalize_audit()` | Raw audit | Normalized audit list |
| `normalize_simulate_result()` | Raw sim result | Full comparison figures (load/temp/rh before-after, peak bar, cost-vs-co2 scatter, comfort compliance bar), scenario KPI, constraint matrix |

### 4.7 Battery Management System (BMS)

**Files:** [`ecoaims_frontend/layouts/bms_layout.py`](ecoaims_frontend/layouts/bms_layout.py:68), [`ecoaims_frontend/callbacks/bms_callbacks.py`](ecoaims_frontend/callbacks/bms_callbacks.py:1) (1241 lines), [`ecoaims_frontend/services/bms_service.py`](ecoaims_frontend/services/bms_service.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| BMS-01 | SOC gauge visualization | High | Circular gauge with percentage |
| BMS-02 | Voltage/current/temperature monitoring | High | Live text display with color coding |
| BMS-03 | Battery health status | High | Normal/Warning/Critical with auto-stop on overheat |
| BMS-04 | Manual charge/discharge/stop controls | High | 3 buttons with backend POST |
| BMS-05 | RL dispatch execution | High | POST to dispatch endpoint, poll dashboard dispatch + job status |
| BMS-06 | DRL tuner preview | High | POST to `/api/optimizer/tuner/suggest` with context payload |
| BMS-07 | Policy proposer preview | High | POST to `/api/optimizer/policy/propose` with SOC/demand/renewable/tariff/emission context |
| BMS-08 | Dispatch mode selection | High | Batch vs realtime mode |
| BMS-09 | Export mode toggle | Medium | Enable/disable export mode |
| BMS-10 | BMS simulation (fallback) | Medium | `BMSService` class with physics simulation (dt=2s, SOC delta, I²R heating) |
| BMS-11 | History tracking (50-point rolling window) | Low | Timestamped history for trend display |

**BMS Simulation Physics (`bms_service.py`):**

```python
# State: SOC (50%), voltage (48V), current, temperature (25°C), status (Idle)
# Update (dt=2s):
#   SOC_delta = current * dt / capacity
#   voltage = OCV(SOC) - current * internal_resistance
#   temperature += I²R * dt - cooling * (temp - ambient) * dt
# Safety:
#   SOC >= 80% charging → auto-stop
#   SOC <= 20% discharging → auto-stop
#   temp > 45°C → overheated status
```

### 4.8 Indoor Climate Monitoring

**Files:** [`ecoaims_frontend/layouts/indoor_layout.py`](ecoaims_frontend/layouts/indoor_layout.py:1), [`ecoaims_frontend/callbacks/indoor_callbacks.py`](ecoaims_frontend/callbacks/indoor_callbacks.py:1), [`ecoaims_frontend/services/indoor_api.py`](ecoaims_frontend/services/indoor_api.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| IND-01 | Zone selector dropdown | High | Fetches zones from backend on load |
| IND-02 | Live sensor feed (temperature, humidity, CO2) | High | 3 indicator cards with real-time values |
| IND-03 | Freshness badge (3-tier) | High | Green (<3min), Yellow (3-5min), Red (>5min) |
| IND-04 | 24-hour chart | High | Time series for selected zone |
| IND-05 | Adaptive polling with exponential backoff | High | 60s → 120s → 240s max with ±10% jitter |
| IND-06 | CSV import workflow | High | Upload → preview → commit pipeline |
| IND-07 | Maintenance mode banner | High | Check maintenance status, show banner if active |
| IND-08 | Snapshot version display | Low | Shows data version from backend |

**Adaptive Polling Algorithm:**

```python
# Initial interval: 60s
# On no new data: interval = min(interval * 2, 240)  # exponential backoff
# On new data: interval = 60  # reset
# Jitter: ±10% random variation
# Max interval: 240s
```

### 4.9 Reports & Analytics

**Files:** [`ecoaims_frontend/layouts/reports_layout.py`](ecoaims_frontend/layouts/reports_layout.py:903) (1689 lines), [`ecoaims_frontend/services/reports_api.py`](ecoaims_frontend/services/reports_api.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| RPT-01 | Precooling impact report | High | Period/stream/zone/granularity/basis filtering |
| RPT-02 | Impact summary cards | High | Before/after comparison for key metrics |
| RPT-03 | Impact comparison table | High | Scenario comparison with metric columns |
| RPT-04 | Impact comparison figures | High | Bar charts for configurable metrics |
| RPT-05 | Quality panel | High | Data quality indicators with fidelity badge |
| RPT-06 | Trend visualization | High | Time series trend with granularity support |
| RPT-07 | History table | High | Paginated history with session IDs |
| RPT-08 | CSV export | High | Download filtered report as CSV |
| RPT-09 | Session detail modal | High | Opens detail/timeseries for selected session |
| RPT-10 | Ops-watch summary | Medium | Operational watch summary from backend |
| RPT-11 | Bundle downloads | Medium | Download evidence bundles |
| RPT-12 | Gating on backend readiness | High | 6 output states: waiting, not ready, contract mismatch, feature not ready, error, normal |

**Reports Output States:**

| State | Condition | Output |
|-------|-----------|--------|
| Waiting | Backend not ready | `_reports_waiting_outputs()` |
| Not Ready | Readiness check failed | `_reports_backend_not_ready_outputs()` |
| Contract Mismatch | Endpoint contract validation failed | `_reports_contract_mismatch_outputs()` |
| Feature Not Ready | Feature decision blocked | `_reports_feature_not_ready_outputs()` |
| Error | Exception during fetch | `_reports_error_outputs()` |
| Normal | All checks pass | Computed report outputs |

### 4.10 Settings & Configuration

**Files:** [`ecoaims_frontend/layouts/settings_layout.py`](ecoaims_frontend/layouts/settings_layout.py:6), [`ecoaims_frontend/callbacks/settings_callbacks.py`](ecoaims_frontend/callbacks/settings_callbacks.py:1), [`ecoaims_frontend/services/settings_service.py`](ecoaims_frontend/services/settings_service.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| SET-01 | Unit system selection | High | Metric/Imperial toggle |
| SET-02 | Capacity configuration | High | Solar/Wind/Battery capacity inputs |
| SET-03 | Cost configuration | High | Grid/Tariff/Feed-in cost inputs |
| SET-04 | Notification preferences | Medium | Enable/disable alert types |
| SET-05 | Live pusher interval | Medium | Configurable push interval (default 15s) |
| SET-06 | Runtime config panel | Medium | Fetches from `/api/system/runtime-config` |
| SET-07 | Live energy enabled toggle | Medium | Enable/disable live energy file processing |
| SET-08 | Lane mode sync | Medium | Sync lane mode radio with live energy enabled |
| SET-09 | Settings persistence | High | JSON file at `data/user_settings.json` |

### 4.11 About & System Info

**Files:** [`ecoaims_frontend/layouts/about_layout.py`](ecoaims_frontend/layouts/about_layout.py:4), [`ecoaims_frontend/callbacks/about_callbacks.py`](ecoaims_frontend/callbacks/about_callbacks.py:1)

| ID | Requirement | Priority | Implementation |
|----|-------------|----------|----------------|
| ABT-01 | Runtime info display | Low | Base URL, build ID, contract hash |
| ABT-02 | Registry cache refresh | Low | Button to clear and reload contract registry |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| PERF-01 | Dashboard load time | < 3s | From user action to full render |
| PERF-02 | Backend readiness check interval | 2s | `dcc.Interval` in main layout |
| PERF-03 | Monitoring refresh interval | 2s | Dashboard update interval |
| PERF-04 | API timeout (read) | 5s | `timeout_s` parameter in all `_safe_get` calls |
| PERF-05 | API timeout (write) | 10s | POST operations |
| PERF-06 | Cache TTL (optimization) | 0.2-3.0s | Adaptive based on input volatility |
| PERF-07 | Cache TTL (contract negotiation) | 300s | `cache_ttl_s` parameter |
| PERF-08 | Backend cooldown period | 2-5s | Avoid hammering unavailable backends |
| PERF-09 | Max polling interval (indoor) | 240s | Exponential backoff cap |
| PERF-10 | History data points (trend) | 10 | Rolling window max |

### 5.2 Reliability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| REL-01 | Graceful degradation on backend failure | All callbacks wrap in try/except with safe fallback values |
| REL-02 | Circuit breaker for optimization | `_BREAKER` with fail_max=5, reset_timeout=30s |
| REL-03 | Backend cooldown pattern | `_BACKEND_DOWN_UNTIL_TS` in all services |
| REL-04 | In-flight request deduplication | `_INFL
| REL-05 | Adaptive cache with TTL | `_OPT_CACHE` with 0.2-3.0s TTL based on input volatility |
| REL-06 | Self-healing manifest fetch | `_ensure_manifest_for_endpoint()` with cooldown |
| REL-07 | Contract negotiation cache | 300s TTL with version comparison |
| REL-08 | Contract synchronization | `ContractSynchronizationService` (300s) and `ContractVersionSynchronizer` (3600s) |
| REL-09 | Cooldown on registry failures | `_COOLDOWN_UNTIL_TS` with 5s default |
| REL-10 | Readiness polling every 2s | `dcc.Interval` with 10+ state status banner |

### 5.3 Maintainability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| MNT-01 | Modular callback architecture | 12 callback modules, each registered via `register_*_callbacks(app)` pattern |
| MNT-02 | Centralized configuration | `config.py` with all API URLs, colors, limits, mappings |
| MNT-03 | Reusable UI components | `components/` directory with composable chart/gauge/table functions |
| MNT-04 | Service layer abstraction | `services/` directory isolates all HTTP/API logic from UI |
| MNT-05 | Type hints throughout | All functions use Python type hints for IDE support |
| MNT-06 | Comprehensive test suite | 40+ test files covering services, normalizers, UI components |
| MNT-07 | Error UI components | `ui/` directory with standardized error/status rendering |
| MNT-08 | Precooling normalizer pattern | `_pick()` key resolution handles backend schema variations |

### 5.4 Scalability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| SCL-01 | Multi-zone aggregation | Precooling supports floor1/2/3 × zone a/b/c with aggregated KPI |
| SCL-02 | Adaptive polling backoff | Indoor module: 60s → 120s → 240s max with jitter |
| SCL-03 | Dashboard caching | `_dashboard_cache` reduces redundant backend calls |
| SCL-04 | Optimization cache | `_OPT_CACHE` with adaptive TTL based on input volatility |
| SCL-05 | In-flight deduplication | `_INFLIGHT` prevents concurrent duplicate optimization requests |
| SCL-06 | Circuit breaker | Prevents cascading failures when backend is down |

---

## 6. System Architecture

### 6.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Dash Client)                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Dash Application                        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │ │
│  │  │ Layouts  │  │Callbacks │  │Components│  │   UI   │  │ │
│  │  │ (10 tab) │  │ (12 mod) │  │ (8+ comp)│  │(error) │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                    │
│                    ┌──────┴──────┐                             │
│                    │  Services   │                             │
│                    │  (20 files) │                             │
│                    └──────┬──────┘                             │
└───────────────────────────┼─────────────────────────────────────┘
                            │ HTTP (requests library)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ Energy   │ │Precooling│ │   BMS    │ │   Reports      │  │
│  │  Data    │ │  /LAEOPF │ │Dispatch  │ │   / Analytics  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ Startup  │ │  System  │ │Contract  │ │   Monitoring   │  │
│  │  Info    │ │ Runtime  │ │Registry  │ │   Diagnostics  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Component Interaction Model

```
┌──────────────────────────────────────────────────────────────────┐
│                        Dash Callback Cycle                        │
│                                                                    │
│  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐  │
│  │ dcc.    │────▶│ Callback │────▶│ Service  │────▶│ Backend │  │
│  │Interval │     │ Function │     │  Layer   │     │  HTTP   │  │
│  └─────────┘     └────┬─────┘     └──────────┘     └─────────┘  │
│                       │                                            │
│                       ▼                                            │
│                 ┌──────────┐     ┌──────────┐                     │
│                 │ Normalizer│────▶│  Layout  │                     │
│                 │ (if needed)│    │  Update  │                     │
│                 └──────────┘     └──────────┘                     │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 Key Design Patterns

| Pattern | Usage | Files |
|---------|-------|-------|
| **Service Layer** | All HTTP/API logic isolated in `services/` | All service files |
| **Normalizer Pattern** | Backend response normalization with flexible key resolution | `precooling_normalizer.py`, `data_service.py` |
| **Circuit Breaker** | Prevents cascading failures on backend downtime | `optimization_service.py` |
| **Cooldown Pattern** | Avoids hammering unavailable backends | All service files (`_*_DOWN_UNTIL_TS`) |
| **Cache-Aside** | Read-through cache with TTL | `optimization_service.py`, `contract_negotiation.py` |
| **In-flight Dedup** | Prevents duplicate concurrent requests | `optimization_service.py` |
| **Graceful Degradation** | try/except with safe fallback values | All callback files |
| **Factory Function** | `create_app()` pattern for Dash app creation | `app.py` |
| **Module Registration** | `register_*_callbacks(app)` pattern | All callback files |
| **Strategy Pattern** | `effective_feature_decision()` for feature gating | `operational_policy.py` |

---

## 7. Backend Integration & Contract System

### 7.1 API Endpoint Map

| Endpoint | Method | Service | Contract Version |
|----------|--------|---------|-----------------|
| `/api/energy-data` | GET | `data_service.py` | v1.2.0 |
| `/diag/monitoring` | GET | `data_service.py` | v1.0.0 |
| `/dashboard/state` | GET | `data_service.py` | — |
| `/dashboard/kpi` | GET | `data_service.py` | — |
| `/dashboard/live/state` | POST | `live_state_push_service.py` | — |
| `/api/startup-info` | GET | `readiness_service.py` | — |
| `/api/health` | GET | `readiness_service.py` | — |
| `/api/system/status` | GET | `readiness_service.py` | — |
| `/api/system/runtime-config` | GET | `system_runtime_api.py` | — |
| `/api/system/runtime-config/live-energy-file` | POST | `system_runtime_api.py` | — |
| `/optimize` | POST | `optimization_service.py` | — |
| `/api/precooling/zones` | GET | `precooling_api.py` | v1.0.0 |
| `/api/precooling/status` | GET | `precooling_api.py` | — |
| `/api/precooling/schedule` | GET | `precooling_api.py` | — |
| `/api/precooling/scenarios` | GET | `precooling_api.py` | — |
| `/api/precooling/kpi` | GET | `precooling_api.py` | — |
| `/api/precooling/alerts` | GET | `precooling_api.py` | — |
| `/api/precooling/audit` | GET | `precooling_api.py` | — |
| `/api/precooling/simulate` | POST | `precooling_api.py` | — |
| `/api/precooling/selector-preview` | POST | `precooling_api.py` | — |
| `/api/precooling/apply` | POST | `precooling_api.py` | — |
| `/api/precooling/force-fallback` | POST | `precooling_api.py` | — |
| `/api/precooling/settings` | GET/POST | `precooling_api.py` | — |
| `/api/precooling/settings/default` | GET | `precooling_api.py` | — |
| `/api/precooling/settings/validate` | POST | `precooling_api.py` | — |
| `/api/precooling/settings/reset` | POST | `precooling_api.py` | — |
| `/api/precooling/settings/apply` | POST | `precooling_api.py` | — |
| `/api/optimizer/tuner/suggest` | POST | `optimizer_tuner_api.py` | — |
| `/api/optimizer/policy/propose` | POST | `policy_proposer_api.py` | — |
| `/api/reports/precooling-impact` | GET | `reports_api.py` | v1.0.0 |
| `/api/reports/precooling-impact/filter-options` | GET | `reports_api.py` | — |
| `/api/reports/precooling-impact/history` | GET | `reports_api.py` | — |
| `/api/reports/precooling-impact/export-csv` | GET | `reports_api.py` | — |
| `/api/reports/precooling-impact/session-detail` | GET | `reports_api.py` | — |
| `/api/reports/precooling-impact/session-timeseries` | GET | `reports_api.py` | — |
| `/ops/watch` (or variants) | GET | `reports_api.py` | — |
| `/api/indoor/zones` | GET | `indoor_api.py` | — |
| `/api/indoor/latest` | GET | `indoor_api.py` | — |
| `/api/indoor/timeseries` | GET | `indoor_api.py` | — |
| `/api/indoor/csv/preview` | POST | `indoor_api.py` | — |
| `/api/indoor/csv/commit` | POST | `indoor_api.py` | — |
| `/api/indoor/maintenance` | GET | `indoor_api.py` | — |
| `/api/bms/dispatch` | POST | `bms_callbacks.py` | — |
| `/api/bms/control` | POST | `bms_callbacks.py` | — |

### 7.2 Contract System Architecture

The contract system ensures frontend-backend compatibility at runtime through three layers:

**Layer 1: Contract Negotiation** ([`contract_negotiation.py`](ecoaims_frontend/services/contract_negotiation.py:57))

- Sends OPTIONS request to endpoints to discover expected contract versions
- Compares versions using semver (major/minor/patch)
- Returns decision: `proceed`, `block`, `fallback`, or `warn`
- Cache with 300s TTL
- Endpoint map: `/api/energy-data` → v1.2.0, `/diag/monitoring` → v1.0.0

**Layer 2: Contract Registry** ([`contract_registry.py`](ecoaims_frontend/services/contract_registry.py:59))

- Fetches registry index and manifest from backend
- Validates manifest hash for integrity
- Self-healing: fetches missing manifests on demand with cooldown
- Validates payloads against registry schema definitions
- Falls back to runtime validators if registry unavailable

**Layer 3: Runtime Contract Validation** ([`runtime_contracts.py`](ecoaims_frontend/services/runtime_contracts.py:1))

- Validator functions for each endpoint:
  - `validate_energy_data()`: Checks solar/wind/grid/biofuel/battery structure
  - `validate_optimize_response()`: Checks usage dict and recommendation
  - `validate_reports_precooling_impact()`: Checks report structure
  - `validate_precooling_zones()`: Checks zone list structure
- Returns `(is_valid, errors_list)` tuple

**Contract Mismatch UI** ([`runtime_contract_mismatch.py`](ecoaims_frontend/services/runtime_contract_mismatch.py:53))

- `build_runtime_endpoint_contract_mismatch()` creates structured error details
- Includes: endpoint key, expected/actual contract labels, missing fields, operator actions
- Rendered via `render_contract_mismatch_error()` in [`contract_error_ui.py`](ecoaims_frontend/ui/contract_error_ui.py:47)

### 7.3 Cross-Repo Evidence Chain

The frontend maintains a canonical cross-repo evidence chain for auditability:

- **Canonical Proof Contract:** [`docs/canonical_crossrepo_proof_contract.json`](docs/canonical_crossrepo_proof_contract.json)
- **Evidence Bundle Contract:** [`docs/canonical_crossrepo_evidence_bundle_contract.json`](docs/canonical_crossrepo_evidence_bundle_contract.json)
- **Verification Contracts:** Separate verification contracts for proof and evidence bundle
- **Scripts:** `scripts/emit_canonical_crossrepo_evidence_bundle.py`, `scripts/bench_canonical_crossrepo_evidence_bundle.py`, `scripts/run_canonical_integration_chain.py`

### 7.4 HTTP Tracing

**File:** [`http_trace.py`](ecoaims_frontend/services/http_trace.py:10)

Every outgoing HTTP request includes tracing headers:
- `X-ECOAIMS-FE-BUILD`: Build ID from `BUILD_ID` env var or `"dev"`
- `X-ECOAIMS-FE-SESSION`: Session ID from `_SESSION_ID` module variable
- `X-ECOAIMS-FE-VERSION`: Version from `__version__` or `"0.0.0"`

---

## 8. Data Flow

### 8.1 Monitoring Data Flow

```
dcc.Interval (2s)
    │
    ▼
update_dashboard() callback
    │
    ├── get_backend_readiness()
    │   ├── GET /api/health
    │   ├── GET /api/startup-info
    │   ├── GET /diag/monitoring
    │   ├── GET /api/energy-data
    │   └── GET /api/system/status
    │
    ├── effective_feature_decision("monitoring", readiness)
    │
    ├── fetch_real_energy_data()
    │   ├── GET /api/energy-data (canonical)
    │   │   └── _adapt_energy_data_contract_to_monitoring()
    │   ├── GET /dashboard/state (legacy fallback)
    │   │   └── _adapt_dashboard_state_to_monitoring()
    │   └── _generate_local_simulated_energy_data() (last resort)
    │
    ├── fetch_dashboard_kpi()
    │   └── GET /dashboard/kpi?stream_id=...&building_area_m2=...
    │
    ├── get_live_sensor_data()
    │   └── Read CSV files from LIVE_CSV_DIR
    │
    ├── create_gauge_figure() × 5 (solar, wind, battery, grid, biofuel)
    ├── create_trend_graph()
    ├── create_co2_impact_panel()
    ├── create_renewable_comparison_card()
    ├── create_sensor_health_card()
    ├── create_alert_notification()
    └── create_status_table()
```

### 8.2 Precooling Data Flow

```
User selects floor/zone
    │
    ▼
refresh_precooling_zones()
    ├── GET /api/precooling/zones
    ├── Cache zones with fallback
    └── Build floor-zone map
    │
    ▼
refresh_precooling_data() (multi-zone aggregation)
    ├── For each target zone:
    │   ├── GET /api/precooling/status?zone=...
    │   ├── GET /api/precooling/schedule?zone=...
    │   ├── GET /api/precooling/scenarios?zone=...
    │   ├── GET /api/precooling/kpi?zone=...
    │   ├── GET /api/precooling/alerts?zone=...
    │   └── GET /api/precooling/audit?zone=...
    │
    ├── normalize_status() / normalize_schedule() / etc.
    └── Aggregate across zones
    │
    ▼
render_precooling_panels() (34 outputs)
    ├── _hero_card()
    ├── _quick_kpis()
    ├── _explainability_box()
    ├── _timeline_from_schedule()
    ├── _scenario_cards()
    ├── _objective_breakdown_fig()
    ├── _selected_candidate_box()
    ├── _fig_from_sim_or_scenarios() × 6
    ├── _comfort_compliance_gauge_fig()
    └── Tables: alerts, audit, constraint matrix
```

### 8.3 Optimization Data Flow

```
User clicks "Run Optimization"
    │
    ▼
update_optimization_result()
    ├── effective_feature_decision("optimization", readiness)
    ├── Fetch live state from /dashboard/state
    ├── Merge with get_live_sensor_data()
    ├── run_energy_optimization(priority, battery_cap, grid_limit, ...)
    │   ├── Check _OPT_CACHE (adaptive TTL)
    │   ├── Check _INFLIGHT (dedup)
    │   ├── POST /optimize (with circuit breaker)
    │   │   ├── Success → parse response
    │   │   └── Failure → local simulation fallback
    │   └── Update metrics (Prometheus)
    └── Render pie chart + bar chart + recommendation
```

---

## 9. Error Handling & Graceful Degradation

### 9.1 Error UI Components

**File:** [`ecoaims_frontend/ui/error_ui.py`](ecoaims_frontend/ui/error_ui.py:1)

| Component | Function | Usage |
|-----------|----------|-------|
| `error_text()` | Returns plain error string | Text-based fallbacks |
| `status_banner()` | HTML banner with area, title, detail, message | Status indicators |
| `error_banner()` | HTML banner with area, title, detail | Error indicators |
| `error_figure()` | Plotly figure with error message | Chart fallbacks |

### 9.2 Contract Error UI

**File:** [`ecoaims_frontend/ui/contract_error_ui.py`](ecoaims_frontend/ui/contract_error_ui.py:47)

`render_contract_mismatch_error()` renders:
- Endpoint key and contract version comparison
- Missing fields list
- Operator actions with severity indicators
- Expandable raw error details

**File:** [`ecoaims_frontend/ui/contract_negotiation_error.py`](ecoaims_frontend/ui/contract_negotiation_error.py:19)

`render_contract_negotiation_error()` renders:
- Negotiation result summary
- Version comparison (expected vs actual)
- Decision (proceed/block/fallback/warn)
- Raw negotiation details

### 9.3 Graceful Degradation Patterns

**Pattern 1: try/except with fallback values**

Every callback wraps its body in try/except and returns safe fallback values:

```python
try:
    # ... main logic ...
    return output1, output2, ...
except Exception as e:
    logger.error("...")
    return fallback1, fallback2, ...
```

**Pattern 2: Backend cooldown**

```python
if time.time() < _SERVICE_DOWN_UNTIL_TS:
    return None, "Backend cooling down"
# ... make request ...
if failure:
    _SERVICE_DOWN_UNTIL_TS = time.time() + COOLDOWN_S
```

**Pattern 3: Circuit breaker**

```python
if _BREAKER.is_open():
    return local_simulation()
# ... make request ...
if failure:
    _BREAKER.record_failure()
```

**Pattern 4: Multi-tier fallback chain**

```
Backend API → Legacy endpoint → Local simulation → Static defaults
```

### 9.4 Error Classification

The readiness service classifies errors into categories:

| Error Class | Description | User Impact |
|-------------|-------------|-------------|
| `connection` | Network unreachable | All features show "Backend unavailable" |
| `timeout` | Request timed out | Degraded mode with cached data |
| `http_error` | Non-200 response | Feature-specific error banner |
| `contract_mismatch` | Schema validation failed | Contract mismatch banner with details |
| `negotiation_blocked` | Version incompatibility | Feature blocked with upgrade prompt |
| `identity_mismatch` | Backend identity changed | Warning with doctor report |

---

## 10. UI/UX Design Principles

### 10.1 Layout Structure

- **Header:** Application title, logo, navigation tabs
- **Content Area:** Tab-specific content with consistent card-based layout
- **Status Bar:** Backend readiness indicator, contract status
- **Footer:** Version info, build ID

### 10.2 Color Scheme

| Element | Color | Usage |
|---------|-------|-------|
| Solar PV | `#ffd700` (Gold) | Solar gauge, charts |
| Wind Turbine | `#00ced1` (Dark Turquoise) | Wind gauge, charts |
| Battery | `#32cd32` (Lime Green) | Battery gauge, SOC |
| Grid | `#ff6347` (Tomato) | Grid gauge, charts |
| Biofuel | `#8b4513` (Saddle Brown) | Biofuel gauge, charts |
| Tab Border | Unique per tab | Tab indicator |
| Error | `#dc3545` (Red) | Error banners |
| Warning | `#ffc107` (Amber) | Warning banners |
| Success | `#28a745` (Green) | Success indicators |

### 10.3 Responsive Design

- Card-based layout with flexible widths
- Gauges auto-scale to container
- Charts use responsive Plotly layout
- Tables scroll horizontally on overflow

### 10.4 Accessibility

- Color-coded indicators with text labels
- Status badges with clear text
- Error messages with actionable details
- Loading states during async operations

---

## 11. Security Requirements

### 11.1 Authentication

| ID | Requirement | Implementation |
|----|-------------|----------------|
| SEC-01 | Password hashing | PBKDF2 with SHA256, configurable iterations |
| SEC-02 | CAPTCHA on login | SVG-based math expression, regenerated on failure |
| SEC-03 | CSRF protection | Token in login form, validated on POST |
| SEC-04 | Session timeout | 720 minutes (12 hours) |
| SEC-05 | Rate limiting | 5 attempts per 15-minute sliding window per IP |
| SEC-06 | Proxy support | `X-Forwarded-For` header parsing |
| SEC-07 | HTTPS redirect | Configurable via `ENFORCE_HTTPS` env var |

### 11.2 Session Management

- Flask signed cookies for session data
- Session contains: `user`, `login_time`, `captcha_answer`, `captcha_salt`, `csrf_token`
- Session destroyed on logout
- Rate limit counters stored in session

### 11.3 Input Validation

- All API responses validated against contract schemas
- Numeric values parsed with try/except guards
- String inputs sanitized for display
- JSON payloads validated before backend submission

---

## 12. Performance Requirements

### 12.1 Caching Strategy

| Cache | Location | TTL | Invalidation |
|-------|----------|-----|--------------|
| Optimization results | `_OPT_CACHE` | 0.2-3.0s (adaptive) | On new input parameters |
| Dashboard data | `_dashboard_cache` | Per-callback | On interval trigger |
| Contract negotiation | `ContractNegotiationService._cache` | 300s | Time-based expiry |
| Contract registry | `_REGISTRY_CACHE` | Per-request | On refresh action |
| Contract manifests | `_MANIFEST_CACHE`, `_MANIFEST_BY_ID` | Per-request | On refresh action |
| Backend readiness | `_READINESS_CACHE` | Per-interval | On each 2s poll |
| Precooling zones | `_ZONES_CACHE` | Per-session | On manual refresh |

### 12.2 Polling Intervals

| Poll | Interval | Backoff | Module |
|------|----------|---------|--------|
| Backend readiness | 2s | None | `readiness_callbacks.py` |
| Dashboard update | 2s | None | `main_callbacks.py` |
| Indoor sensor feed | 60s (initial) | Exponential to 240s | `indoor_callbacks.py` |
| 1-hour comparison | 3600s | None | `main_layout.py` |
| Live state push | 15s (configurable) | None | `live_state_push_service.py` |

### 12.3 Timeout Configuration

| Operation | Timeout | Context |
|-----------|---------|---------|
| Health check | (1.5s, 2.5s) | Readiness service |
| Startup info | (1.5s, 2.5s) | Readiness service |
| Energy data | (2.5s, 5.0s) | Data service |
| Optimization | (5.0s, 10.0s) | Optimization service |
| Precooling GET | 5.0s | Precooling API |
| Precooling POST | 10.0s | Precooling API |
| Reports GET | 5.0s | Reports API |
| Indoor GET | 5.0s | Indoor API |
| Contract OPTIONS | (2.5s, 5.0s) | Contract negotiation |

---

## 13. Testing Strategy

### 13.1 Test Coverage

The test suite covers 40+ test files across the following categories:

| Category | Test Files | Focus |
|----------|------------|-------|
| **Components** | `test_components.py` | UI component rendering |
| **Contract System** | `test_contract_error_ui.py`, `test_contract_negotiation.py`, `test_contract_registry.py` | Contract validation, negotiation, error UI |
| **Cross-Repo** | `test_crossrepo_evidence_bundle.py`, `test_crossrepo_proof_artifact.py` | Evidence chain verification |
| **Data Service** | `test_data_service_dashboard_state.py`, `test_dashboard_kpi_request_params.py` | Data adaptation, KPI params |
| **Fallback** | `test_fallback_policy.py` | Graceful degradation |
| **Home** | `test_home_doctor_report.py`, `test_home_runbook.py` | Home page features |
| **Live State** | `test_live_state_push_service.py` | State push service |
| **Monitoring** | `test_monitoring_comparison_*.py` (5 files), `test_monitoring_diagnostics.py` | Comparison, diagnostics |
| **Operational Policy** | `test_operational_policy.py` | Feature decision engine |
| **Optimization** | `test_optimization_cache.py`, `test_optimizer_tuner_api.py` | Cache, tuner API |
| **Policy** | `test_policy_proposer_api.py` | Policy proposer API |
| **Precooling** | `test_precooling_*.py` (10 files) | Normalizer, selector, golden sample, override, zone discovery, debug payload |
| **Readiness** | `test_readiness_service.py` | Backend readiness |
| **Reports** | `test_reports_api.py`, `test_reports_backend_contract.py`, `test_reports_gating.py` | Reports API, gating |
| **Runtime** | `test_runtime_endpoint_contracts.py`, `test_runtime_endpoint.py` | Runtime validation |
| **Settings** | `test_settings_precooling_floor_area_save.py` | Settings persistence |

### 13.2 Testing Principles

- Unit tests for service layer functions
- Mock HTTP responses for API-dependent tests
- Normalizer tests with various input shapes
- Error handling tests for all failure modes
- Contract validation tests for schema compliance

---

## 14. Deployment & Operations

### 14.1 Environment Configuration

**File:** [`.env`](.env:1)

| Variable | Purpose | Default |
|----------|---------|---------|
| `API_BASE_URL` | Legacy backend URL | `http://localhost:5050` |
| `ECOAIMS_API_BASE_URL` | Primary backend URL | `http://127.0.0.1:8008` |
| `PRECOOLING_API_BASE_URL` | Precooling backend URL | `http://127.0.0.1:8008` |
| `SECRET_KEY` | Flask session secret | — |
| `PASSWORD` | Login password | — |
| `BUILD_ID` | Build identifier | `dev` |
| `ENFORCE_HTTPS` | HTTPS redirect | `false` |
| `LIVE_DATA_SOURCE` | Data source mode | `hybrid` |

### 14.2 Always-On Services

The frontend supports always-on operation via:
- **macOS:** launchd plist files
- **Linux:** systemd service files
- **Script:** `scripts/gen_always_on_services.py` generates service definitions

### 14.3 Monitoring & Observability

| Feature | Endpoint/File | Description |
|---------|---------------|-------------|
| Prometheus metrics | `/metrics` | Latency histogram, cache stats, circuit breaker stats |
| Runtime info | `/__runtime` | Build ID, base URL, contract hash |
| Monitoring diagnostics | `fetch_monitoring_diag()` | Endpoint health, contract status, data trimming |
| Doctor report | Home tab | Contract change detection, identity verification |
| Backend readiness | 2s polling | 10+ state status banner |

### 14.4 Startup Sequence

```
1. Load .env configuration
2. Initialize Flask app with ProxyFix
3. Register Flask routes (login, logout, captcha, metrics, runtime)
4. Create Dash app instance
5. Register all 12 callback modules in order:
   a. readiness_callbacks (must be first)
   b. home_callbacks
   c. main_callbacks (monitoring)
   d. forecasting_callbacks
   e. optimization_callbacks
   f. settings_callbacks
   g. bms_callbacks
   h. precooling_callbacks
   i. precooling_settings_callbacks
   j. indoor_callbacks
   k. about_callbacks
   l. reports_callbacks (embedded in reports_layout.py)
6. Start Dash server on configured host:port
```

### 14.5 Build & Run

```bash
# Development
python -m ecoaims_frontend.app

# Production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:8050 ecoaims_frontend.app:server

# With always-on services
./scripts/ecoaims_ctl.py start
```

---

## 15. Glossary

| Term | Definition |
|------|------------|
| **CAPTCHA** | Completely Automated Public Turing test to tell Computers and Humans Apart |
| **CSRF** | Cross-Site Request Forgery |
| **DRL** | Deep Reinforcement Learning |
| **EUI** | Energy Use Intensity (kWh/m²/year) |
| **IPEI** | Integrated Performance and Exergy Index |
| **KPI** | Key Performance Indicator |
| **LAEOPF** | Load and Energy Optimization with Precooling Framework |
| **MAPE** | Mean Absolute Percentage Error |
| **PBKDF2** | Password-Based Key Derivation Function 2 |
| **RL** | Reinforcement Learning |
| **SHR** | Sensible Heat Ratio |
| **SOC** | State of Charge |
| **TTL** | Time To Live |

---

## 16. Appendices

### Appendix A: File Size Reference

| File | Lines | Purpose |
|------|-------|---------|
| `precooling_callbacks.py` | 2,405 | Precooling logic (largest file) |
| `reports_layout.py` | 1,689 | Reports layout + callbacks |
| `bms_callbacks.py` | 1,241 | BMS logic |
| `precooling_settings_callbacks.py` | 1,028 | Precooling settings |
| `main_callbacks.py` | 909 | Monitoring dashboard |
| `data_service.py` | 792 | Core data fetching |
| `optimization_service.py` | 619 | Optimization engine |
| `precooling_normalizer.py` | 605 | Precooling normalizer |
| `precooling_api.py` | 534 | Precooling API wrapper |
| `home_callbacks.py` | 516 | Home page logic |
| `readiness_service.py` | 430 | Backend readiness |
| `contract_registry.py` | 436 | Contract registry |
| `app.py` | 1,061 | Application entry point |

### Appendix B: Key Configuration Constants

**File:** [`ecoaims_frontend/config.py`](ecoaims_frontend/config.py:1)

| Constant | Value | Purpose |
|----------|-------|---------|
| `GRID_EMISSION_FACTOR` | 0.85 kg/kWh | CO2 calculation |
| `CAR_DAILY_EMISSION` | 12.6 kg/day | CO2 equivalence |
| `LED_BULB_WATT` | 10 W | Energy equivalence |
| `SENSOR_STALE_THRESHOLD` | 300s | Sensor staleness |
| `MIN_HISTORY_FOR_COMPARISON` | 2 | Minimum history records |
| `ECOAIMS_BACKEND_STATE_STALE_S` | 900s | Backend state staleness |
| `COLORS` | Dict | Source-specific colors |
| `ENERGY_LIMITS` | Dict | Max values per source |

### Appendix C: Error Message Reference

| Error Context | Banner Title | User Action |
|---------------|--------------|-------------|
| Backend connection failed | "Backend Tidak Dapat Dihubungi" | Check backend status, verify URL |
| Contract negotiation blocked | "Kontrak Endpoint Tidak Sesuai" | Update backend to compatible version |
| Runtime contract mismatch | "Ketidaksesuaian Kontrak Runtime" | Check missing fields, contact admin |
| Feature not ready | "Fitur Belum Siap" | Wait for backend readiness |
| Insufficient history | "Data Riwayat Belum Mencukupi" | Wait for more data collection |
| Identity mismatch | "Identitas Backend Berubah" | Verify backend deployment |
| Maintenance mode | "Mode Pemeliharaan Aktif" | Wait for maintenance completion |

### Appendix D: Related Documents

| Document | Location | Description |
|----------|----------|-------------|
| README_FE.MD | [`README_FE.MD`](README_FE.MD) | Frontend setup and usage guide |
| QUICKSTART.md | [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Quick start guide |
| RELEASE_CHECKLIST.md | [`docs/
RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) | Release preparation checklist |
| PATCH_PLAYBOOK.md | [`docs/PATCH_PLAYBOOK.md`](docs/PATCH_PLAYBOOK.md) | Patching procedures |
| PATCHING_GUIDE.md | [`docs/PATCHING_GUIDE.md`](docs/PATCHING_GUIDE.md) | Patching guide |
| PROMETHEUS_GRAFANA.md | [`docs/PROMETHEUS_GRAFANA.md`](docs/PROMETHEUS_GRAFANA.md) | Monitoring setup |
| SECURITY_ZAP.md | [`docs/SECURITY_ZAP.md`](docs/SECURITY_ZAP.md) | Security testing |
| LOAD_TESTING.md | [`docs/LOAD_TESTING.md`](docs/LOAD_TESTING.md) | Load testing results |
| SESSION_NOTES_FE_2026-03-26.md | [`docs/SESSION_NOTES_FE_2026-03-26.md`](docs/SESSION_NOTES_FE_2026-03-26.md) | Session notes |
| Canonical Proof Contract | [`docs/canonical_crossrepo_proof_contract.json`](docs/canonical_crossrepo_proof_contract.json) | Cross-repo proof |
| Evidence Bundle Contract | [`docs/canonical_crossrepo_evidence_bundle_contract.json`](docs/canonical_crossrepo_evidence_bundle_contract.json) | Evidence bundle |
| Prometheus Alerts | [`docs/prometheus/ecoaims_alerts.yml`](docs/prometheus/ecoaims_alerts.yml) | Alert rules |

---

*End of Document — PRD-FE-001 v1.0.0*
