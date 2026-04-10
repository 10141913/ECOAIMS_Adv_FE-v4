from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
    return False


def _as_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _as_int(x: Any, default: int) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def _parse_hhmm(value: Any) -> Tuple[bool, int]:
    if not isinstance(value, str):
        return False, 0
    parts = value.strip().split(":")
    if len(parts) != 2:
        return False, 0
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except ValueError:
        return False, 0
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return False, 0
    return True, hh * 60 + mm


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]
    warnings: List[str]
    normalized: Dict[str, Any]


def validate_precooling_settings(cfg: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    raw = _as_dict(cfg)

    general = _as_dict(raw.get("general"))
    time_window = _as_dict(raw.get("time_window"))
    comfort = _as_dict(raw.get("comfort_limits"))
    hvac = _as_dict(raw.get("hvac_constraints"))
    building = _as_dict(raw.get("building_parameters"))
    energy = _as_dict(raw.get("energy_coordination"))
    weights = _as_dict(raw.get("objective_weights"))
    fallback = _as_dict(raw.get("fallback_rules"))
    advanced = _as_dict(raw.get("advanced"))

    default_mode = str(general.get("default_operation_mode") or "monitoring").lower()
    if default_mode not in {"monitoring", "advisory", "auto", "fallback"}:
        errors.append("Default Operation Mode tidak valid")

    default_scenario = str(general.get("default_scenario_type") or "optimized").lower()
    if default_scenario not in {"baseline", "rule-based", "rule_based", "optimized"}:
        errors.append("Default Scenario Type tidak valid")

    ok_e, earliest = _parse_hhmm(time_window.get("earliest_start_time", "05:00"))
    ok_l, latest = _parse_hhmm(time_window.get("latest_start_time", "10:00"))
    if not ok_e:
        errors.append("Earliest Allowed Start Time tidak valid (HH:MM)")
    if not ok_l:
        errors.append("Latest Allowed Start Time tidak valid (HH:MM)")
    if ok_e and ok_l and earliest >= latest:
        errors.append("Earliest Allowed Start Time harus lebih kecil dari Latest Allowed Start Time")

    min_dur = _as_int(time_window.get("min_duration_min"), 30)
    max_dur = _as_int(time_window.get("max_duration_min"), 120)
    if min_dur <= 0:
        errors.append("Minimum Precooling Duration harus > 0")
    if max_dur <= 0:
        errors.append("Maximum Precooling Duration harus > 0")
    if min_dur > max_dur:
        errors.append("Minimum Precooling Duration harus <= Maximum Precooling Duration")

    min_t = _as_float(comfort.get("min_indoor_temp_c"), 22.0)
    max_t = _as_float(comfort.get("max_indoor_temp_c"), 27.0)
    if min_t >= max_t:
        errors.append("Minimum Indoor Temperature harus lebih kecil dari Maximum Indoor Temperature")

    min_rh = _as_float(comfort.get("min_rh_pct"), 45.0)
    max_rh = _as_float(comfort.get("max_rh_pct"), 65.0)
    if min_rh >= max_rh:
        errors.append("Minimum RH harus lebih kecil dari Maximum RH")

    soc_min = _as_float(energy.get("battery_soc_min"), 0.2)
    soc_max = _as_float(energy.get("battery_soc_max"), 0.95)
    if soc_min >= soc_max:
        errors.append("Battery SOC Minimum harus lebih kecil dari Battery SOC Maximum")
    if not (0.0 <= soc_min <= 1.0 and 0.0 <= soc_max <= 1.0):
        errors.append("Battery SOC Minimum/Maximum harus berada dalam rentang 0..1")

    sp_lo = _as_float(hvac.get("setpoint_lower_bound_c"), 20.0)
    sp_hi = _as_float(hvac.get("setpoint_upper_bound_c"), 26.0)
    if sp_lo >= sp_hi:
        errors.append("Setpoint Lower Bound harus lebih kecil dari Setpoint Upper Bound")

    rh_lo = _as_float(hvac.get("rh_lower_bound_pct"), 40.0)
    rh_hi = _as_float(hvac.get("rh_upper_bound_pct"), 70.0)
    if rh_lo >= rh_hi:
        errors.append("RH Lower Bound harus lebih kecil dari RH Upper Bound")

    fb_t = _as_float(fallback.get("fallback_temperature_c"), 25.0)
    fb_rh = _as_float(fallback.get("fallback_rh_pct"), 60.0)
    if not (sp_lo <= fb_t <= sp_hi):
        errors.append("Fallback Temperature harus berada dalam rentang HVAC Setpoint Lower/Upper Bound")
    if not (rh_lo <= fb_rh <= rh_hi):
        errors.append("Fallback RH harus berada dalam rentang HVAC RH Lower/Upper Bound")

    tm_class = str(building.get("thermal_mass_class") or "medium").lower()
    if tm_class not in {"light", "medium", "heavy"}:
        errors.append("Thermal Mass Class tidak valid (light/medium/heavy)")

    w_cost = _as_float(weights.get("weight_cost"), 0.35)
    w_co2 = _as_float(weights.get("weight_co2"), 0.25)
    w_peak = _as_float(weights.get("weight_peak_reduction"), 0.2)
    w_comfort = _as_float(weights.get("weight_comfort"), 0.15)
    w_batt = _as_float(weights.get("weight_battery_health"), 0.05)
    w_sum = w_cost + w_co2 + w_peak + w_comfort + w_batt
    if w_sum <= 0:
        errors.append("Objective Weights tidak boleh semuanya 0")
        w_sum = 1.0
    if abs(w_sum - 1.0) > 0.01:
        warnings.append("Objective Weights tidak berjumlah 1.0, sistem akan menormalkan saat apply")

    normalized = {
        "general": {
            "enable_precooling": _as_bool(general.get("enable_precooling", True)),
            "enable_laeopf_mode": _as_bool(general.get("enable_laeopf_mode", True)),
            "default_operation_mode": default_mode,
            "default_scenario_type": "rule-based" if default_scenario in {"rule_based", "rule-based"} else default_scenario,
        },
        "time_window": {
            "earliest_start_time": str(time_window.get("earliest_start_time", "05:00")),
            "latest_start_time": str(time_window.get("latest_start_time", "10:00")),
            "min_duration_min": min_dur,
            "max_duration_min": max_dur,
            "weekday_profile_enabled": _as_bool(time_window.get("weekday_profile_enabled", True)),
            "weekend_profile_enabled": _as_bool(time_window.get("weekend_profile_enabled", True)),
            "holiday_behavior": str(time_window.get("holiday_behavior") or "weekend").lower(),
        },
        "comfort_limits": {
            "min_indoor_temp_c": min_t,
            "max_indoor_temp_c": max_t,
            "pre_occupancy_target_temp_c": _as_float(comfort.get("pre_occupancy_target_temp_c"), _clamp(24.0, min_t, max_t)),
            "min_rh_pct": min_rh,
            "max_rh_pct": max_rh,
            "pre_occupancy_target_rh_pct": _as_float(comfort.get("pre_occupancy_target_rh_pct"), _clamp(55.0, min_rh, max_rh)),
            "comfort_priority_level": str(comfort.get("comfort_priority_level") or "medium").lower(),
        },
        "hvac_constraints": {
            "cooling_capacity_limit_kw": _as_float(hvac.get("cooling_capacity_limit_kw"), 500.0),
            "minimum_runtime_min": _as_int(hvac.get("minimum_runtime_min"), 15),
            "maximum_runtime_min": _as_int(hvac.get("maximum_runtime_min"), 180),
            "setpoint_lower_bound_c": sp_lo,
            "setpoint_upper_bound_c": sp_hi,
            "rh_lower_bound_pct": rh_lo,
            "rh_upper_bound_pct": rh_hi,
            "anti_short_cycle_enabled": _as_bool(hvac.get("anti_short_cycle_enabled", True)),
            "ramp_limit_enabled": _as_bool(hvac.get("ramp_limit_enabled", False)),
        },
        "building_parameters": {
            "thermal_mass_class": tm_class,
            "floor_area_m2": _as_float(building.get("floor_area_m2"), 1000.0),
            "volume_m3": _as_float(building.get("volume_m3"), 3000.0),
            "u_value_wall": _as_float(building.get("u_value_wall"), 1.5),
            "u_value_roof": _as_float(building.get("u_value_roof"), 1.0),
            "shgc": _as_float(building.get("shgc"), 0.4),
            "ach_infiltration_rate": _as_float(building.get("ach_infiltration_rate"), 0.5),
            "internal_gain_estimate_w_m2": _as_float(building.get("internal_gain_estimate_w_m2"), 10.0),
        },
        "energy_coordination": {
            "prioritize_pv_surplus": _as_bool(energy.get("prioritize_pv_surplus", True)),
            "allow_battery_support": _as_bool(energy.get("allow_battery_support", True)),
            "disallow_grid_only": _as_bool(energy.get("disallow_grid_only", False)),
            "enable_tariff_aware_strategy": _as_bool(energy.get("enable_tariff_aware_strategy", True)),
            "enable_co2_aware_strategy": _as_bool(energy.get("enable_co2_aware_strategy", True)),
            "battery_soc_min": soc_min,
            "battery_soc_max": soc_max,
        },
        "objective_weights": {
            "weight_cost": w_cost,
            "weight_co2": w_co2,
            "weight_peak_reduction": w_peak,
            "weight_comfort": w_comfort,
            "weight_battery_health": w_batt,
            "weight_sum": w_sum,
        },
        "fallback_rules": {
            "enable_fallback": _as_bool(fallback.get("enable_fallback", True)),
            "fallback_start_time": str(fallback.get("fallback_start_time") or "00:00"),
            "fallback_duration_min": _as_int(fallback.get("fallback_duration_min"), 60),
            "fallback_temperature_c": fb_t,
            "fallback_rh_pct": fb_rh,
            "trigger_on_missing_data": _as_bool(fallback.get("trigger_on_missing_data", True)),
            "trigger_on_optimizer_failure": _as_bool(fallback.get("trigger_on_optimizer_failure", True)),
            "trigger_on_battery_constraint": _as_bool(fallback.get("trigger_on_battery_constraint", True)),
            "trigger_on_comfort_risk": _as_bool(fallback.get("trigger_on_comfort_risk", True)),
        },
        "advanced": {
            "enable_latent_model": _as_bool(advanced.get("enable_latent_model", True)),
            "enable_exergy_model": _as_bool(advanced.get("enable_exergy_model", True)),
            "enable_psychrometric_diagnostics": _as_bool(advanced.get("enable_psychrometric_diagnostics", False)),
            "enable_candidate_ranking_debug": _as_bool(advanced.get("enable_candidate_ranking_debug", False)),
            "enable_experimental_scenario_runner": _as_bool(advanced.get("enable_experimental_scenario_runner", False)),
        },
    }

    return ValidationResult(ok=(len(errors) == 0), errors=errors, warnings=warnings, normalized=normalized)


def normalize_weights_for_engine(cfg: Dict[str, Any]) -> Dict[str, float]:
    w = _as_dict(_as_dict(cfg).get("objective_weights"))
    cost = float(w.get("weight_cost") or 0.0)
    co2 = float(w.get("weight_co2") or 0.0)
    peak = float(w.get("weight_peak_reduction") or 0.0)
    comfort = float(w.get("weight_comfort") or 0.0)
    batt = float(w.get("weight_battery_health") or 0.0)
    s = cost + co2 + peak + comfort + batt
    if s <= 0:
        return {"cost": 0.35, "co2": 0.25, "peak": 0.2, "comfort": 0.15, "battery_health": 0.05}
    return {"cost": cost / s, "co2": co2 / s, "peak": peak / s, "comfort": comfort / s, "battery_health": batt / s}

