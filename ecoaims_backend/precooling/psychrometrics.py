from typing import Dict


def compute_humidity_ratio(rh_percent: float, temp_c: float) -> float:
    rh = max(0.0, min(100.0, float(rh_percent))) / 100.0
    return 0.008 + 0.010 * rh + 0.0002 * max(0.0, temp_c - 20.0)


def compute_dew_point_c(rh_percent: float, temp_c: float) -> float:
    rh = max(1e-6, min(100.0, float(rh_percent))) / 100.0
    return temp_c - (1.0 - rh) * 12.0


def psychrometric_state(temp_c: float, rh_percent: float) -> Dict[str, float]:
    return {
        "temp_c": float(temp_c),
        "rh_percent": float(rh_percent),
        "dew_point_c": compute_dew_point_c(rh_percent, temp_c),
        "humidity_ratio": compute_humidity_ratio(rh_percent, temp_c),
    }

