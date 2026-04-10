from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

from ecoaims_backend.precooling.storage import now_iso


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _precooling_output_dir() -> str:
    base = os.getenv("ECOAIMS_OUTPUT_DIR", os.path.join(_repo_root(), "output"))
    return os.path.join(base, "precooling")


def _draft_path() -> str:
    return os.path.join(_precooling_output_dir(), "settings.json")


def _active_path() -> str:
    return os.path.join(_precooling_output_dir(), "settings_active.json")


def default_settings() -> Dict[str, Any]:
    return {
        "general": {
            "enable_precooling": True,
            "enable_laeopf_mode": True,
            "default_operation_mode": "monitoring",
            "default_scenario_type": "optimized",
        },
        "time_window": {
            "earliest_start_time": "05:00",
            "latest_start_time": "10:00",
            "min_duration_min": 30,
            "max_duration_min": 120,
            "weekday_profile_enabled": True,
            "weekend_profile_enabled": True,
            "holiday_behavior": "weekend",
        },
        "comfort_limits": {
            "min_indoor_temp_c": 22.0,
            "max_indoor_temp_c": 27.0,
            "pre_occupancy_target_temp_c": 24.0,
            "min_rh_pct": 45.0,
            "max_rh_pct": 65.0,
            "pre_occupancy_target_rh_pct": 55.0,
            "comfort_priority_level": "medium",
        },
        "hvac_constraints": {
            "cooling_capacity_limit_kw": 500.0,
            "minimum_runtime_min": 15,
            "maximum_runtime_min": 180,
            "setpoint_lower_bound_c": 20.0,
            "setpoint_upper_bound_c": 26.0,
            "rh_lower_bound_pct": 40.0,
            "rh_upper_bound_pct": 70.0,
            "anti_short_cycle_enabled": True,
            "ramp_limit_enabled": False,
        },
        "building_parameters": {
            "thermal_mass_class": "medium",
            "floor_area_m2": 1000.0,
            "volume_m3": 3000.0,
            "u_value_wall": 1.5,
            "u_value_roof": 1.0,
            "shgc": 0.4,
            "ach_infiltration_rate": 0.5,
            "internal_gain_estimate_w_m2": 10.0,
        },
        "energy_coordination": {
            "prioritize_pv_surplus": True,
            "allow_battery_support": True,
            "disallow_grid_only": False,
            "enable_tariff_aware_strategy": True,
            "enable_co2_aware_strategy": True,
            "battery_soc_min": 0.2,
            "battery_soc_max": 0.95,
        },
        "objective_weights": {
            "weight_cost": 0.35,
            "weight_co2": 0.25,
            "weight_peak_reduction": 0.2,
            "weight_comfort": 0.15,
            "weight_battery_health": 0.05,
        },
        "fallback_rules": {
            "enable_fallback": True,
            "fallback_start_time": "00:00",
            "fallback_duration_min": 60,
            "fallback_temperature_c": 25.0,
            "fallback_rh_pct": 60.0,
            "trigger_on_missing_data": True,
            "trigger_on_optimizer_failure": True,
            "trigger_on_battery_constraint": True,
            "trigger_on_comfort_risk": True,
        },
        "advanced": {
            "enable_latent_model": True,
            "enable_exergy_model": True,
            "enable_psychrometric_diagnostics": False,
            "enable_candidate_ranking_debug": False,
            "enable_experimental_scenario_runner": False,
        },
    }


def _default_bundle() -> Dict[str, Any]:
    default = default_settings()
    now = now_iso()
    return {
        "version": 1,
        "active": default,
        "draft": default,
        "updated_at": now,
        "applied_at": now,
    }


def load_bundle() -> Dict[str, Any]:
    draft_path = _draft_path()
    active_path = _active_path()

    legacy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precooling_settings.json")
    if os.path.exists(legacy_path) and not os.path.exists(draft_path) and not os.path.exists(active_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                legacy = _as_dict(json.load(f))
            bundle = {
                "version": int(legacy.get("version", 1) or 1),
                "draft": _as_dict(legacy.get("draft", legacy.get("active", {}))) or default_settings(),
                "active": _as_dict(legacy.get("active", legacy.get("draft", {}))) or default_settings(),
                "updated_at": legacy.get("updated_at") or now_iso(),
                "applied_at": legacy.get("applied_at") or now_iso(),
            }
            save_bundle(bundle)
            return bundle
        except Exception:
            pass

    if not os.path.exists(draft_path) or not os.path.exists(active_path):
        bundle = _default_bundle()
        save_bundle(bundle)
        return bundle
    try:
        with open(draft_path, "r", encoding="utf-8") as f:
            draft_data = _as_dict(json.load(f))
        with open(active_path, "r", encoding="utf-8") as f:
            active_data = _as_dict(json.load(f))
        bundle = {
            "version": int(draft_data.get("version", active_data.get("version", 1)) or 1),
            "draft": _as_dict(draft_data.get("draft", draft_data.get("config", draft_data))) or default_settings(),
            "active": _as_dict(active_data.get("active", active_data.get("config", active_data))) or default_settings(),
            "updated_at": draft_data.get("updated_at") or now_iso(),
            "applied_at": active_data.get("applied_at") or draft_data.get("applied_at") or now_iso(),
        }
        if not bundle.get("active") or not bundle.get("draft"):
            bundle = _default_bundle()
            save_bundle(bundle)
        return bundle
    except Exception:
        bundle = _default_bundle()
        save_bundle(bundle)
        return bundle


def save_bundle(bundle: Dict[str, Any]) -> None:
    parent = _precooling_output_dir()
    os.makedirs(parent, exist_ok=True)

    draft_payload = {
        "version": int(bundle.get("version", 1) or 1),
        "draft": _as_dict(bundle.get("draft")) or default_settings(),
        "updated_at": bundle.get("updated_at") or now_iso(),
        "applied_at": bundle.get("applied_at") or now_iso(),
    }
    active_payload = {
        "version": int(bundle.get("version", 1) or 1),
        "active": _as_dict(bundle.get("active")) or default_settings(),
        "applied_at": bundle.get("applied_at") or now_iso(),
    }

    def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(prefix="precooling_settings_", suffix=".json", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    _atomic_write(_draft_path(), draft_payload)
    _atomic_write(_active_path(), active_payload)


def get_active() -> Dict[str, Any]:
    return _as_dict(load_bundle().get("active"))


def get_draft() -> Dict[str, Any]:
    return _as_dict(load_bundle().get("draft"))


def set_draft(cfg: Dict[str, Any]) -> Dict[str, Any]:
    bundle = load_bundle()
    bundle["draft"] = cfg
    bundle["updated_at"] = now_iso()
    save_bundle(bundle)
    return bundle


def reset_draft_to_default() -> Dict[str, Any]:
    bundle = load_bundle()
    bundle["draft"] = default_settings()
    bundle["updated_at"] = now_iso()
    save_bundle(bundle)
    return bundle


def apply_draft() -> Dict[str, Any]:
    bundle = load_bundle()
    bundle["active"] = _as_dict(bundle.get("draft")) or default_settings()
    bundle["applied_at"] = now_iso()
    save_bundle(bundle)
    return bundle
