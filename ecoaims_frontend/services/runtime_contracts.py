from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _is_number(x: Any) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def validate_energy_data(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    for k in ["solar", "wind", "battery", "grid", "biofuel"]:
        if k not in payload:
            errors.append(f"missing:{k}")
            continue
        v = payload.get(k)
        if not isinstance(v, dict):
            errors.append(f"{k}:not_object")
            continue
        if "value" not in v or not _is_number(v.get("value")):
            errors.append(f"{k}:value_invalid")
        if "max" not in v or not _is_number(v.get("max")):
            errors.append(f"{k}:max_invalid")
    return len(errors) == 0, errors


def validate_optimize_response(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    dist = payload.get("energy_distribution")
    if not isinstance(dist, dict):
        errors.append("energy_distribution_not_object")
    else:
        if any(k in dist for k in ("solar", "wind", "battery", "grid", "unmet")):
            for k in ["solar", "wind", "battery", "grid"]:
                if k not in dist or not _is_number(dist.get(k)):
                    errors.append(f"energy_distribution:{k}_invalid")
            if "biofuel" in dist and not _is_number(dist.get("biofuel")):
                errors.append("energy_distribution:biofuel_invalid")
        else:
            for k in ["Solar PV", "Wind Turbine", "Battery", "PLN/Grid"]:
                if k not in dist or not _is_number(dist.get(k)):
                    errors.append(f"energy_distribution:{k}_invalid")
            for k in ["Biofuel", "biofuel"]:
                if k in dist and not _is_number(dist.get(k)):
                    errors.append(f"energy_distribution:{k}_invalid")
    rec = payload.get("recommendation")
    status = payload.get("status")
    if not isinstance(rec, str) or not rec.strip():
        if not (isinstance(status, str) and status.strip().lower() in {"success", "ok"}):
            errors.append("recommendation_invalid")
    return len(errors) == 0, errors


def validate_reports_precooling_impact(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    if "basis" not in payload or not isinstance(payload.get("basis"), str):
        errors.append("basis_invalid")
    if "summary" not in payload or not isinstance(payload.get("summary"), dict):
        errors.append("summary_invalid")
    if "scenarios" not in payload or not isinstance(payload.get("scenarios"), list):
        errors.append("scenarios_invalid")
    if "quality" not in payload or not isinstance(payload.get("quality"), dict):
        errors.append("quality_invalid")
    return len(errors) == 0, errors


def validate_reports_precooling_impact_history(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    rows = payload.get("rows")
    if not isinstance(rows, list):
        errors.append("rows_not_list")
    return len(errors) == 0, errors


def validate_reports_precooling_impact_filter_options(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    if not isinstance(payload.get("zones"), list) or not payload.get("zones"):
        errors.append("zones_invalid")
    if not isinstance(payload.get("streams"), list) or not payload.get("streams"):
        errors.append("streams_invalid")
    defaults = payload.get("defaults")
    if defaults is not None and not isinstance(defaults, dict):
        errors.append("defaults_invalid")
    return len(errors) == 0, errors


def validate_reports_precooling_impact_session_detail(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    if not isinstance(payload.get("record"), dict):
        errors.append("record_invalid")
    if not isinstance(payload.get("quality"), dict):
        errors.append("quality_invalid")
    if "before_fidelity" not in payload:
        errors.append("before_fidelity_missing")
    if "after_fidelity" not in payload:
        errors.append("after_fidelity_missing")
    qf = payload.get("quality_flags")
    if qf is not None and not isinstance(qf, list):
        errors.append("quality_flags_invalid")
    return len(errors) == 0, errors


def validate_reports_precooling_impact_session_timeseries(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    if not isinstance(payload.get("timestamps"), list):
        errors.append("timestamps_invalid")
    if not isinstance(payload.get("series"), dict):
        errors.append("series_invalid")
    return len(errors) == 0, errors


def validate_precooling_zones(payload: Any) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload_not_object"]
    zones = payload.get("zones")
    if not isinstance(zones, list) or not zones:
        errors.append("zones_invalid")
        return False, errors
    # Validate minimal shape per zone
    for i, z in enumerate(zones):
        if not isinstance(z, dict):
            errors.append(f"zones[{i}]:not_object")
            continue
        zid = z.get("zone_id") or z.get("id") or z.get("name")
        if not isinstance(zid, str) or not zid.strip():
            errors.append(f"zones[{i}]:zone_id_missing")
    return len(errors) == 0, errors
