"""
Configuration settings for the ECO-AIMS Frontend Application.

This module contains constant values used throughout the application,
including styling parameters, update intervals, and simulation limits.
"""

import os

def _getenv_nonempty(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default

# Explicit toggle: allow local simulation fallback when backend is unavailable
ALLOW_LOCAL_SIMULATION_FALLBACK = str(os.getenv("ALLOW_LOCAL_SIMULATION_FALLBACK", "false")).strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

# Strict integration gate: require canonical backend policy endpoint (/api/system/status) and registry.
ECOAIMS_REQUIRE_CANONICAL_POLICY = str(os.getenv("ECOAIMS_REQUIRE_CANONICAL_POLICY", "false")).strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

# App Settings
DEBUG_MODE = str(os.getenv("ECOAIMS_DEBUG_MODE", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}
UPDATE_INTERVAL_MS = 2000  # 2 seconds

# Backend Integration
# Set to True to fetch data from API, False to use simulation
USE_REAL_DATA = str(os.getenv("USE_REAL_DATA", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
# Legacy backend base URL override for Monitoring/Optimization compatibility
API_BASE_URL = _getenv_nonempty("API_BASE_URL")

# Canonical ECOAIMS API (FastAPI)
ECOAIMS_API_BASE_URL = _getenv_nonempty("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008")

# Legacy Precooling Engine Integration (compatibility only)
PRECOOLING_API_BASE_URL = _getenv_nonempty("PRECOOLING_API_BASE_URL") or ECOAIMS_API_BASE_URL
PRECOOLING_REFRESH_INTERVAL_MS = 10000

# Live Sensor Data Configuration
# 'csv' = read from live CSV files
# 'api' = read from backend API
# 'hybrid' = use live data if available (active sensor), otherwise fallback to simulation
LIVE_DATA_SOURCE = 'hybrid' 
LIVE_CSV_DIR = 'output'
LIVE_SUPPLY_FILE = 'live_supply.csv'
LIVE_DEMAND_FILE = 'live_demand.csv'
SENSOR_STALE_THRESHOLD = 60 # seconds

# Monitoring Comparison requires minimum history (records) from canonical energy-data contract
MIN_HISTORY_FOR_COMPARISON = int(os.getenv("ECOAIMS_MIN_HISTORY_FOR_COMPARISON", "12"))
ECOAIMS_CONTRACT_VALIDATION_MODE = str(os.getenv("ECOAIMS_CONTRACT_VALIDATION_MODE", "strict")).strip().lower()
ECOAIMS_ENABLE_CONTRACT_NEGOTIATION = str(os.getenv("ECOAIMS_ENABLE_CONTRACT_NEGOTIATION", "false")).strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

# Sensor Mappings (ID -> Display Name)

CONTRACT_SYSTEM = {
    "enabled": str(os.getenv("ECOAIMS_CONTRACT_NEGOTIATION_ENABLED", os.getenv("ECOAIMS_ENABLE_CONTRACT_NEGOTIATION", "false"))).strip().lower() in {"1", "true", "yes", "y", "on"},
    "mode": str(os.getenv("ECOAIMS_CONTRACT_MODE", os.getenv("ECOAIMS_CONTRACT_VALIDATION_MODE", "lenient"))).strip().lower(),
    "negotiation_required": str(os.getenv("ECOAIMS_CONTRACT_NEGOTIATION_REQUIRED", "false")).strip().lower() in {"1", "true", "yes", "y", "on"},
    "cache_ttl": int(os.getenv("ECOAIMS_CONTRACT_CACHE_TTL", "300")),
    "sync_interval": int(os.getenv("ECOAIMS_CONTRACT_SYNC_INTERVAL", "3600")),
    "fallback_to_simulation": str(os.getenv("ECOAIMS_CONTRACT_FALLBACK_SIMULATION", "true")).strip().lower() in {"1", "true", "yes", "y", "on"},
}

# Sensor Mappings (ID -> Display Name)
SENSOR_MAPPING = {
    'supply': {
        'pv': 'Solar PV',
        'wt': 'Wind Turbine',
        'biofuel': 'Biofuel',
        'grid': 'PLN/Grid',
        'battery': 'Battery'
    },
    'demand': {
        'hvac': 'HVAC',
        'lighting': 'Lighting',
        'pump': 'Pompa',
        'office': 'Peralatan kantor'
    }
}

# Styling Constants
COLORS = {
    'background': '#ecf0f1',
    'header_bg': '#2c3e50',
    'header_text': 'white',
    'text_primary': '#2c3e50',
    'text_secondary': '#7f8c8d',
    'card_bg': 'white',
    'solar': '#f1c40f',
    'wind': '#3498db',
    'biofuel': '#2ecc71',
    'battery': '#9b59b6',
    'grid': '#e74c3c'
}

HEADER_STYLE = {
    'backgroundColor': COLORS['header_bg'],
    'color': COLORS['header_text'],
    'padding': '20px',
    'textAlign': 'center',
    'marginBottom': '20px'
}

CARD_STYLE = {
    'boxShadow': '0 4px 8px 0 rgba(0,0,0,0.2)',
    'transition': '0.3s',
    'borderRadius': '5px',
    'padding': '20px',
    'margin': '10px',
    'backgroundColor': COLORS['card_bg']
}

# Simulation Limits (Max Capacity in kW)
ENERGY_LIMITS = {
    'solar': 100,
    'wind': 150,
    'battery': 200,
    'grid': 100,
    'biofuel': 50
}
