import random
from typing import Any, Dict


def compute_thermal_state(zone: str, outdoor_temp_c: float, indoor_temp_c: float) -> Dict[str, Any]:
    seed = abs(hash(zone)) % 10_000
    rnd = random.Random(seed)
    thermal_mass = indoor_temp_c - rnd.uniform(0.2, 0.8)
    rebound = indoor_temp_c + rnd.uniform(0.8, 1.8)
    return {
        "current_temp": round(indoor_temp_c, 2),
        "thermal_mass_temp": round(thermal_mass, 2),
        "rebound_temp": round(rebound, 2),
        "delta_to": round(indoor_temp_c - outdoor_temp_c, 2),
    }

