import random
from typing import Dict, List, Tuple

def get_simulated_energy_data() -> Dict:
    """
    Generates simulated energy data for the dashboard.
    
    This function mimics an API call to a backend service. It returns random values
    within realistic ranges for solar, wind, battery, and grid power.

    Returns:
        Dict: A dictionary containing:
            - 'solar': {'value': float, 'max': float}
            - 'wind': {'value': float, 'max': float}
            - 'battery': {'value': float, 'max': float}
            - 'grid': {'value': float, 'max': float}
    """
    solar_max, wind_max, battery_max, grid_max, bio_max = 100, 150, 200, 100, 50
    
    # Generate current values
    solar_val = random.uniform(0, solar_max)
    wind_val = random.uniform(0, wind_max)
    batt_val = random.uniform(20, 180)
    grid_val = random.uniform(10, 90)
    bio_val = random.uniform(0, bio_max)

    # Simulate 3-hour aggregated data (roughly 3x current rate with variation)
    # Using variation 0.8 to 1.2 to simulate fluctuation over the period
    def simulate_3h(val):
        return val * 3 * random.uniform(0.8, 1.2)

    return {
        'solar': {'value': solar_val, 'max': solar_max, 'value_3h': simulate_3h(solar_val)},
        'wind': {'value': wind_val, 'max': wind_max, 'value_3h': simulate_3h(wind_val)},
        'battery': {'value': batt_val, 'max': battery_max, 'value_3h': simulate_3h(batt_val)},
        'grid': {'value': grid_val, 'max': grid_max, 'value_3h': simulate_3h(grid_val)},
        'biofuel': {'value': bio_val, 'max': bio_max, 'value_3h': simulate_3h(bio_val)}
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