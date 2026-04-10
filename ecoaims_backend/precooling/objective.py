from typing import Any, Dict


def objective_breakdown(weights: Dict[str, Any]) -> Dict[str, float]:
    cost = float(weights.get("cost", 0.35) or 0.0)
    co2 = float(weights.get("co2", 0.25) or 0.0)
    comfort = float(weights.get("comfort", 0.25) or 0.0)
    batt = float(weights.get("battery_health", 0.15) or 0.0)
    peak = max(0.0, 1.0 - (cost + co2 + comfort + batt))
    if peak == 0.0:
        peak = 0.2
    total = cost + co2 + comfort + batt + peak
    return {
        "Cost": round(cost / total, 3),
        "CO2": round(co2 / total, 3),
        "Peak": round(peak / total, 3),
        "Comfort": round(comfort / total, 3),
        "Battery Health": round(batt / total, 3),
    }


def score_candidate(candidate: Dict[str, Any], weights: Dict[str, Any], feasible: bool, shr: float, exergy_eff: float) -> float:
    w = objective_breakdown(weights)
    t = float(candidate.get("target_t", 24.0))
    dur = float(candidate.get("duration", 60.0))
    rh = float(candidate.get("target_rh", 55.0))

    cost_term = max(0.0, 1.0 - (dur / 180.0))
    co2_term = max(0.0, 1.0 - (dur / 240.0))
    peak_term = max(0.0, 1.0 - abs(t - 23.0) / 6.0)
    comfort_term = max(0.0, 1.0 - abs(rh - 55.0) / 20.0)
    batt_term = max(0.0, 1.0 - (dur / 240.0))

    bonus = 0.08 if feasible else -0.25
    adv = 0.04 * (shr - 0.6) + 0.06 * (exergy_eff - 0.7)
    score = (
        w["Cost"] * cost_term
        + w["CO2"] * co2_term
        + w["Peak"] * peak_term
        + w["Comfort"] * comfort_term
        + w["Battery Health"] * batt_term
        + bonus
        + adv
    )
    return round(max(-1.0, min(1.0, score)), 3)

