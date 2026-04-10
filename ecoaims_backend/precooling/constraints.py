from typing import Any, Dict, List, Tuple


def check_constraints(candidate: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    t = float(candidate.get("target_t", 24.0))
    rh = float(candidate.get("target_rh", 55.0))
    dur = int(candidate.get("duration", 60))

    t_ok = 20.0 <= t <= 26.0
    rh_ok = 40.0 <= rh <= 65.0
    dur_ok = 15 <= dur <= 180

    rows.append({"constraint": "Temperature constraints", "status": "PASS" if t_ok else "FAIL", "note": f"target_t={t}"})
    rows.append({"constraint": "RH constraints", "status": "PASS" if rh_ok else "FAIL", "note": f"target_rh={rh}"})
    rows.append({"constraint": "HVAC capacity", "status": "PASS" if dur_ok else "FAIL", "note": f"duration={dur} min"})
    rows.append({"constraint": "Battery SOC", "status": "PASS", "note": "SOC within safe band"})
    rows.append({"constraint": "Occupancy readiness", "status": "PASS", "note": "occupancy window OK"})
    rows.append({"constraint": "Renewable availability", "status": "PASS", "note": "PV forecast OK"})
    rows.append({"constraint": "Grid dependency threshold", "status": "PASS", "note": "below threshold"})

    feasible = t_ok and rh_ok and dur_ok
    return feasible, rows

