from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ecoaims_backend.precooling import config_store
from ecoaims_backend.precooling.config_validator import normalize_weights_for_engine, validate_precooling_settings


def get_settings_bundle() -> Dict[str, Any]:
    return config_store.load_bundle()


def get_active_settings() -> Dict[str, Any]:
    bundle = config_store.load_bundle()
    cfg = bundle.get("active")
    if isinstance(cfg, dict):
        return cfg
    return config_store.default_settings()


def get_default_settings() -> Dict[str, Any]:
    return config_store.default_settings()


def validate_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    res = validate_precooling_settings(cfg)
    return {"ok": res.ok, "errors": res.errors, "warnings": res.warnings, "normalized": res.normalized}


def save_settings(cfg: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    res = validate_precooling_settings(cfg)
    if not res.ok:
        return False, {"ok": False, "errors": res.errors, "warnings": res.warnings, "normalized": res.normalized}
    bundle = config_store.set_draft(res.normalized)
    return True, {"ok": True, "bundle": bundle, "warnings": res.warnings}


def reset_settings() -> Dict[str, Any]:
    return config_store.reset_draft_to_default()


def apply_settings() -> Dict[str, Any]:
    bundle = config_store.load_bundle()
    draft = bundle.get("draft")
    if not isinstance(draft, dict):
        draft = config_store.default_settings()
    res = validate_precooling_settings(draft)
    if res.ok:
        bundle = config_store.set_draft(res.normalized)
        bundle = config_store.apply_draft()
    else:
        bundle = config_store.set_draft(res.normalized)
    return {"ok": res.ok, "errors": res.errors, "warnings": res.warnings, "bundle": bundle}


def settings_snapshot_for_ui(cfg: Dict[str, Any]) -> Dict[str, Any]:
    c = cfg if isinstance(cfg, dict) else {}
    tw = c.get("time_window") if isinstance(c.get("time_window"), dict) else {}
    comfort = c.get("comfort_limits") if isinstance(c.get("comfort_limits"), dict) else {}
    weights = c.get("objective_weights") if isinstance(c.get("objective_weights"), dict) else {}
    adv = c.get("advanced") if isinstance(c.get("advanced"), dict) else {}
    return {
        "time_window": {
            "earliest_start_time": tw.get("earliest_start_time"),
            "latest_start_time": tw.get("latest_start_time"),
            "min_duration_min": tw.get("min_duration_min"),
            "max_duration_min": tw.get("max_duration_min"),
        },
        "comfort_limits": {
            "min_indoor_temp_c": comfort.get("min_indoor_temp_c"),
            "max_indoor_temp_c": comfort.get("max_indoor_temp_c"),
            "pre_occupancy_target_temp_c": comfort.get("pre_occupancy_target_temp_c"),
            "min_rh_pct": comfort.get("min_rh_pct"),
            "max_rh_pct": comfort.get("max_rh_pct"),
            "pre_occupancy_target_rh_pct": comfort.get("pre_occupancy_target_rh_pct"),
        },
        "objective_weights": {
            "weight_cost": weights.get("weight_cost"),
            "weight_co2": weights.get("weight_co2"),
            "weight_peak_reduction": weights.get("weight_peak_reduction"),
            "weight_comfort": weights.get("weight_comfort"),
            "weight_battery_health": weights.get("weight_battery_health"),
        },
        "advanced": {
            "enable_latent_model": adv.get("enable_latent_model"),
            "enable_exergy_model": adv.get("enable_exergy_model"),
            "enable_psychrometric_diagnostics": adv.get("enable_psychrometric_diagnostics"),
        },
    }


def merge_simulate_payload(payload: Dict[str, Any], settings: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    p = payload if isinstance(payload, dict) else {}
    cfg = settings if isinstance(settings, dict) else {}
    notes: List[str] = []

    tw = cfg.get("time_window") if isinstance(cfg.get("time_window"), dict) else {}
    comfort = cfg.get("comfort_limits") if isinstance(cfg.get("comfort_limits"), dict) else {}

    window = p.get("window") if isinstance(p.get("window"), dict) else {}
    earliest = window.get("earliest_start") or tw.get("earliest_start_time") or "05:00"
    latest = window.get("latest_start") or tw.get("latest_start_time") or "10:00"
    if window.get("earliest_start") is None:
        notes.append("window.earliest_start menggunakan nilai dari settings")
    if window.get("latest_start") is None:
        notes.append("window.latest_start menggunakan nilai dari settings")

    min_dur = int(tw.get("min_duration_min") or 30)
    max_dur = int(tw.get("max_duration_min") or 120)

    durations = p.get("durations_min")
    if not isinstance(durations, list) or not durations:
        mid = max(min_dur, min(max_dur, int((min_dur + max_dur) / 2)))
        durations = sorted({min_dur, mid, max_dur})
        notes.append("durations_min menggunakan nilai dari settings")

    t_min = float(comfort.get("min_indoor_temp_c") or 22.0)
    t_max = float(comfort.get("max_indoor_temp_c") or 27.0)
    t_range = p.get("target_temp_range")
    if not isinstance(t_range, list) or len(t_range) < 2:
        t_range = [t_min, t_max]
        notes.append("target_temp_range menggunakan nilai dari settings")

    rh_min = float(comfort.get("min_rh_pct") or 45.0)
    rh_max = float(comfort.get("max_rh_pct") or 65.0)
    rh_range = p.get("target_rh_range")
    if not isinstance(rh_range, list) or len(rh_range) < 2:
        rh_range = [rh_min, rh_max]
        notes.append("target_rh_range menggunakan nilai dari settings")

    w_engine = normalize_weights_for_engine(cfg)
    weights = p.get("weights")
    if not isinstance(weights, dict) or not weights:
        weights = {"cost": w_engine["cost"], "co2": w_engine["co2"], "comfort": w_engine["comfort"], "battery_health": w_engine["battery_health"]}
        notes.append("weights menggunakan nilai dari settings")
    else:
        weights = {
            "cost": float(weights.get("cost", w_engine["cost"])),
            "co2": float(weights.get("co2", w_engine["co2"])),
            "comfort": float(weights.get("comfort", w_engine["comfort"])),
            "battery_health": float(weights.get("battery_health", w_engine["battery_health"])),
        }

    merged = {
        **p,
        "window": {"earliest_start": str(earliest), "latest_start": str(latest)},
        "durations_min": durations,
        "target_temp_range": t_range,
        "target_rh_range": rh_range,
        "weights": weights,
    }
    return merged, notes


def fallback_params(settings: Dict[str, Any]) -> Dict[str, Any]:
    cfg = settings if isinstance(settings, dict) else {}
    fb = cfg.get("fallback_rules") if isinstance(cfg.get("fallback_rules"), dict) else {}
    return {
        "start_time": str(fb.get("fallback_start_time") or "00:00"),
        "duration_min": int(fb.get("fallback_duration_min") or 60),
        "temperature_c": float(fb.get("fallback_temperature_c") or 25.0),
        "rh_pct": float(fb.get("fallback_rh_pct") or 60.0),
    }

