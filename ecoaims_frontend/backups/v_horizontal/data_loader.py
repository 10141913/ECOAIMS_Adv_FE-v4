import random
from typing import Dict, List, Tuple
import datetime

def get_simulated_energy_data() -> Dict:
    """
    Generates simulated energy data including historical trends for sparklines.
    Returns simulated values for current reading and last 60 minutes history.
    """
    solar_max, wind_max, battery_max, grid_max, bio_max = 100, 150, 200, 100, 50
    
    def generate_history(base_val, max_val, points=12): # 12 points = 60 mins (5 min interval)
        history = []
        val = base_val
        for _ in range(points):
            # Random walk
            change = random.uniform(-5, 5)
            val = max(0, min(max_val, val + change))
            history.append(val)
        return history

    solar_val = random.uniform(0, solar_max)
    wind_val = random.uniform(0, wind_max)
    batt_val = random.uniform(20, 180)
    grid_val = random.uniform(10, 90)
    bio_val = random.uniform(0, bio_max)

    return {
        'solar': {
            'value': solar_val, 'max': solar_max, 
            'history': generate_history(solar_val, solar_max),
            'status': 'Normal' if solar_val > 0 else 'Standby'
        },
        'wind': {
            'value': wind_val, 'max': wind_max,
            'history': generate_history(wind_val, wind_max),
            'status': 'Optimal' if wind_val > 50 else 'Low Wind'
        },
        'battery': {
            'value': batt_val, 'max': battery_max,
            'history': generate_history(batt_val, battery_max),
            'status': 'Discharging' if batt_val > 100 else 'Charging'
        },
        'grid': {
            'value': grid_val, 'max': grid_max,
            'history': generate_history(grid_val, grid_max),
            'status': 'Connected'
        },
        'biofuel': {
            'value': bio_val, 'max': bio_max,
            'history': generate_history(bio_val, bio_max),
            'status': 'Active' if bio_val > 10 else 'Standby'
        }
    }

def update_trend_data(current_data: List[Dict], consumption: float, renewable_supply: float, timestamp: str, max_points: int = 10) -> List[Dict]:
    """
    Updates the historical trend data list.

    Args:
        current_data (List[Dict]): The existing list of data points.
        consumption (float): The new consumption value to add.
        renewable_supply (float): The new renewable supply value to add.
        timestamp (str): The timestamp string for the new value.
        max_points (int, optional): Maximum number of points to keep. Defaults to 10.

    Returns:
        List[Dict]: The updated list of data points.
    """
    current_data.append({
        'time': timestamp, 
        'consumption': consumption,
        'renewable_supply': renewable_supply
    })
    if len(current_data) > max_points:
        current_data.pop(0)
    return current_data
