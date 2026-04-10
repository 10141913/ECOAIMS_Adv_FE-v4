import math
from typing import Any, Dict, List, Tuple


def simulate_load_profile(duration_min: int, start_time: str) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    start_h = int((start_time or "00:00").split(":")[0])
    for h in range(24):
        base = 80 + 20 * math.sin((h - 8) / 24 * 2 * math.pi)
        load = base
        if start_h <= h < min(24, start_h + max(1, int(duration_min / 60))):
            load = base + 25
        points.append({"hour": f"{h:02d}:00", "load_kw": round(load, 2)})
    return points


def derive_kpis_from_profile(profile: List[Dict[str, Any]]) -> Dict[str, Any]:
    loads = [float(p.get("load_kw", 0.0)) for p in profile]
    peak = max(loads) if loads else 0.0
    energy = sum(loads) / 24.0 * 24.0
    return {"peak_kw": round(peak, 2), "energy_kwh": round(energy, 2)}

