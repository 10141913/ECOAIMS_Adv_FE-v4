import json
import os
import logging
from typing import Dict, Any

# Path to the settings file
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'user_settings.json')

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_SETTINGS = {
    "units": {
        "energy": "kWh",
        "power": "kW",
        "emission": "ton CO2"
    },
    "capacities": {
        "solar_pv": 100,  # kW
        "wind_turbine": 150,  # kW
        "battery": 200  # kWh
    },
    "costs": {
        "electricity_tariff": 1444.70,  # IDR per kWh (Example: PLN Tariff)
        "biofuel_price": 12000,  # IDR per Liter
        "carbon_price": 30000  # IDR per ton CO2
    },
    "notifications": {
        "low_battery": True,
        "grid_outage": True,
        "high_consumption": False
    }
}

def load_settings() -> Dict[str, Any]:
    """
    Loads settings from the JSON file. Returns default settings if file doesn't exist.
    """
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Gagal memuat settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(new_settings: Dict[str, Any]) -> bool:
    """
    Saves the provided settings to the JSON file.
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(new_settings, f, indent=4)
        return True
    except Exception as e:
        logger.warning(f"Gagal menyimpan settings: {e}")
        return False

def get_setting(category: str, key: str) -> Any:
    """
    Retrieves a specific setting value.
    """
    settings = load_settings()
    return settings.get(category, {}).get(key)
