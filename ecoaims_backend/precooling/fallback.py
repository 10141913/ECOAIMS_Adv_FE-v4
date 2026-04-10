from typing import Any, Dict


def fallback_status(zone: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    p = params or {}
    start_time = p.get("start_time", "-")
    end_time = p.get("end_time", "-")
    duration = p.get("duration", p.get("duration_min", "-"))
    t = p.get("temperature_c", p.get("temperature", "-"))
    rh = p.get("rh_pct", p.get("rh", "-"))
    return {
        "status_today": "Fallback Active",
        "optimization_objective": "Safety-first",
        "confidence_score": 0.0,
        "comfort_risk": "LOW",
        "constraint_status": "SAFE",
        "recommended_energy_source": "Grid",
        "strategy_type": "Fallback",
        "start_time": start_time,
        "end_time": end_time,
        "duration": f"{duration} min" if isinstance(duration, (int, float)) else duration,
        "target_temperature": f"{t} °C" if isinstance(t, (int, float)) else t,
        "target_rh": f"{rh} %" if isinstance(rh, (int, float)) else rh,
    }
