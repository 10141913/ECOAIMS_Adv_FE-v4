import datetime
import json
from typing import Any, Dict, Tuple

from dash import Input, Output, State, html, no_update

from ecoaims_frontend.services.precooling_api import (
    get_zones,
    get_settings,
    get_settings_default,
    pretty_zone_label,
    post_settings_apply,
    post_settings_reset,
    post_settings_save,
    post_settings_validate,
)
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.utils import get_headers


def _now_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _badge_style(kind: str) -> Dict[str, Any]:
    if kind == "ACTIVE":
        bg = "#27ae60"
    elif kind == "DRAFT":
        bg = "#8e44ad"
    elif kind in {"INVALID", "ERROR"}:
        bg = "#c0392b"
    elif kind == "DIRTY":
        bg = "#e67e22"
    elif kind == "CLEAN":
        bg = "#27ae60"
    elif kind == "VALID":
        bg = "#27ae60"
    else:
        bg = "#7f8c8d"
    return {
        "display": "inline-block",
        "padding": "4px 10px",
        "borderRadius": "999px",
        "backgroundColor": bg,
        "color": "white",
        "fontWeight": "bold",
        "fontSize": "12px",
        "minWidth": "140px",
        "textAlign": "center",
    }


def _checked(value) -> bool:
    return isinstance(value, list) and "enabled" in value


def _cfg_from_form(
    enable_precooling,
    enable_laeopf,
    default_mode,
    default_scenario,
    earliest,
    latest,
    min_dur,
    max_dur,
    weekday,
    weekend,
    holiday_behavior,
    min_temp,
    max_temp,
    target_temp,
    min_rh,
    max_rh,
    target_rh,
    comfort_priority,
    cap_limit,
    min_runtime,
    max_runtime,
    sp_lo,
    sp_hi,
    rh_lo,
    rh_hi,
    anti_short,
    ramp_limit,
    thermal_mass,
    floor_area,
    volume,
    u_wall,
    u_roof,
    shgc,
    ach,
    internal_gain,
    pv,
    batt_support,
    disallow_grid,
    tariff_aware,
    co2_aware,
    soc_min,
    soc_max,
    w_cost,
    w_co2,
    w_peak,
    w_comfort,
    w_battery,
    enable_fallback,
    fb_start,
    fb_dur,
    fb_temp,
    fb_rh,
    trig_missing,
    trig_optim,
    trig_batt,
    trig_comfort,
    adv_latent,
    adv_exergy,
    adv_psy,
    adv_debug,
    adv_runner,
) -> Dict[str, Any]:
    return {
        "general": {
            "enable_precooling": _checked(enable_precooling),
            "enable_laeopf_mode": _checked(enable_laeopf),
            "default_operation_mode": default_mode,
            "default_scenario_type": default_scenario,
        },
        "time_window": {
            "earliest_start_time": earliest,
            "latest_start_time": latest,
            "min_duration_min": min_dur,
            "max_duration_min": max_dur,
            "weekday_profile_enabled": _checked(weekday),
            "weekend_profile_enabled": _checked(weekend),
            "holiday_behavior": holiday_behavior,
        },
        "comfort_limits": {
            "min_indoor_temp_c": min_temp,
            "max_indoor_temp_c": max_temp,
            "pre_occupancy_target_temp_c": target_temp,
            "min_rh_pct": min_rh,
            "max_rh_pct": max_rh,
            "pre_occupancy_target_rh_pct": target_rh,
            "comfort_priority_level": comfort_priority,
        },
        "hvac_constraints": {
            "cooling_capacity_limit_kw": cap_limit,
            "minimum_runtime_min": min_runtime,
            "maximum_runtime_min": max_runtime,
            "setpoint_lower_bound_c": sp_lo,
            "setpoint_upper_bound_c": sp_hi,
            "rh_lower_bound_pct": rh_lo,
            "rh_upper_bound_pct": rh_hi,
            "anti_short_cycle_enabled": _checked(anti_short),
            "ramp_limit_enabled": _checked(ramp_limit),
        },
        "building_parameters": {
            "thermal_mass_class": thermal_mass,
            "floor_area_m2": floor_area,
            "volume_m3": volume,
            "u_value_wall": u_wall,
            "u_value_roof": u_roof,
            "shgc": shgc,
            "ach_infiltration_rate": ach,
            "internal_gain_estimate_w_m2": internal_gain,
        },
        "energy_coordination": {
            "prioritize_pv_surplus": _checked(pv),
            "allow_battery_support": _checked(batt_support),
            "disallow_grid_only": _checked(disallow_grid),
            "enable_tariff_aware_strategy": _checked(tariff_aware),
            "enable_co2_aware_strategy": _checked(co2_aware),
            "battery_soc_min": soc_min,
            "battery_soc_max": soc_max,
        },
        "objective_weights": {
            "weight_cost": w_cost,
            "weight_co2": w_co2,
            "weight_peak_reduction": w_peak,
            "weight_comfort": w_comfort,
            "weight_battery_health": w_battery,
        },
        "fallback_rules": {
            "enable_fallback": _checked(enable_fallback),
            "fallback_start_time": fb_start,
            "fallback_duration_min": fb_dur,
            "fallback_temperature_c": fb_temp,
            "fallback_rh_pct": fb_rh,
            "trigger_on_missing_data": _checked(trig_missing),
            "trigger_on_optimizer_failure": _checked(trig_optim),
            "trigger_on_battery_constraint": _checked(trig_batt),
            "trigger_on_comfort_risk": _checked(trig_comfort),
        },
        "advanced": {
            "enable_latent_model": _checked(adv_latent),
            "enable_exergy_model": _checked(adv_exergy),
            "enable_psychrometric_diagnostics": _checked(adv_psy),
            "enable_candidate_ranking_debug": _checked(adv_debug),
            "enable_experimental_scenario_runner": _checked(adv_runner),
        },
    }


def _form_from_cfg(cfg: Dict[str, Any]):
    c = cfg if isinstance(cfg, dict) else {}
    general = c.get("general") if isinstance(c.get("general"), dict) else {}
    tw = c.get("time_window") if isinstance(c.get("time_window"), dict) else {}
    comfort = c.get("comfort_limits") if isinstance(c.get("comfort_limits"), dict) else {}
    hvac = c.get("hvac_constraints") if isinstance(c.get("hvac_constraints"), dict) else {}
    building = c.get("building_parameters") if isinstance(c.get("building_parameters"), dict) else {}
    energy = c.get("energy_coordination") if isinstance(c.get("energy_coordination"), dict) else {}
    w = c.get("objective_weights") if isinstance(c.get("objective_weights"), dict) else {}
    fb = c.get("fallback_rules") if isinstance(c.get("fallback_rules"), dict) else {}
    adv = c.get("advanced") if isinstance(c.get("advanced"), dict) else {}

    def b(x: Any):
        return ["enabled"] if bool(x) else []

    return (
        b(general.get("enable_precooling", True)),
        b(general.get("enable_laeopf_mode", True)),
        general.get("default_operation_mode", "monitoring"),
        general.get("default_scenario_type", "optimized"),
        tw.get("earliest_start_time", "05:00"),
        tw.get("latest_start_time", "10:00"),
        tw.get("min_duration_min", 30),
        tw.get("max_duration_min", 120),
        b(tw.get("weekday_profile_enabled", True)),
        b(tw.get("weekend_profile_enabled", True)),
        tw.get("holiday_behavior", "weekend"),
        comfort.get("min_indoor_temp_c", 22.0),
        comfort.get("max_indoor_temp_c", 27.0),
        comfort.get("pre_occupancy_target_temp_c", 24.0),
        comfort.get("min_rh_pct", 45.0),
        comfort.get("max_rh_pct", 65.0),
        comfort.get("pre_occupancy_target_rh_pct", 55.0),
        comfort.get("comfort_priority_level", "medium"),
        hvac.get("cooling_capacity_limit_kw", 500.0),
        hvac.get("minimum_runtime_min", 15),
        hvac.get("maximum_runtime_min", 180),
        hvac.get("setpoint_lower_bound_c", 20.0),
        hvac.get("setpoint_upper_bound_c", 26.0),
        hvac.get("rh_lower_bound_pct", 40.0),
        hvac.get("rh_upper_bound_pct", 70.0),
        b(hvac.get("anti_short_cycle_enabled", True)),
        b(hvac.get("ramp_limit_enabled", False)),
        building.get("thermal_mass_class", "medium"),
        building.get("floor_area_m2", 1000.0),
        building.get("volume_m3", 3000.0),
        building.get("u_value_wall", 1.5),
        building.get("u_value_roof", 1.0),
        building.get("shgc", 0.4),
        building.get("ach_infiltration_rate", 0.5),
        building.get("internal_gain_estimate_w_m2", 10.0),
        b(energy.get("prioritize_pv_surplus", True)),
        b(energy.get("allow_battery_support", True)),
        b(energy.get("disallow_grid_only", False)),
        b(energy.get("enable_tariff_aware_strategy", True)),
        b(energy.get("enable_co2_aware_strategy", True)),
        energy.get("battery_soc_min", 0.2),
        energy.get("battery_soc_max", 0.95),
        w.get("weight_cost", 0.35),
        w.get("weight_co2", 0.25),
        w.get("weight_peak_reduction", 0.2),
        w.get("weight_comfort", 0.15),
        w.get("weight_battery_health", 0.05),
        b(fb.get("enable_fallback", True)),
        fb.get("fallback_start_time", "00:00"),
        fb.get("fallback_duration_min", 60),
        fb.get("fallback_temperature_c", 25.0),
        fb.get("fallback_rh_pct", 60.0),
        b(fb.get("trigger_on_missing_data", True)),
        b(fb.get("trigger_on_optimizer_failure", True)),
        b(fb.get("trigger_on_battery_constraint", True)),
        b(fb.get("trigger_on_comfort_risk", True)),
        b(adv.get("enable_latent_model", True)),
        b(adv.get("enable_exergy_model", True)),
        b(adv.get("enable_psychrometric_diagnostics", False)),
        b(adv.get("enable_candidate_ranking_debug", False)),
        b(adv.get("enable_experimental_scenario_runner", False)),
    )


def _safe_equal(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    except Exception:
        return a == b


def _config_status(bundle: Dict[str, Any]) -> Tuple[str, str]:
    active = bundle.get("active") if isinstance(bundle.get("active"), dict) else {}
    draft = bundle.get("draft") if isinstance(bundle.get("draft"), dict) else {}
    applied_at = bundle.get("applied_at") or "-"
    updated_at = bundle.get("updated_at") or "-"
    kind = "ACTIVE" if _safe_equal(active, draft) else "DRAFT"
    suffix = f"applied={applied_at} updated={updated_at}"
    return kind, suffix


def register_precooling_settings_callbacks(app):
    form_states = [
        State("precoolset-enable-precooling", "value"),
        State("precoolset-enable-laeopf", "value"),
        State("precoolset-default-mode", "value"),
        State("precoolset-default-scenario", "value"),
        State("precoolset-earliest", "value"),
        State("precoolset-latest", "value"),
        State("precoolset-min-dur", "value"),
        State("precoolset-max-dur", "value"),
        State("precoolset-weekday", "value"),
        State("precoolset-weekend", "value"),
        State("precoolset-holiday-behavior", "value"),
        State("precoolset-min-temp", "value"),
        State("precoolset-max-temp", "value"),
        State("precoolset-target-temp", "value"),
        State("precoolset-min-rh", "value"),
        State("precoolset-max-rh", "value"),
        State("precoolset-target-rh", "value"),
        State("precoolset-comfort-priority", "value"),
        State("precoolset-cap-limit", "value"),
        State("precoolset-min-runtime", "value"),
        State("precoolset-max-runtime", "value"),
        State("precoolset-sp-lo", "value"),
        State("precoolset-sp-hi", "value"),
        State("precoolset-rh-lo", "value"),
        State("precoolset-rh-hi", "value"),
        State("precoolset-anti-short", "value"),
        State("precoolset-ramp-limit", "value"),
        State("precoolset-thermal-mass", "value"),
        State("precoolset-floor-area", "value"),
        State("precoolset-volume", "value"),
        State("precoolset-u-wall", "value"),
        State("precoolset-u-roof", "value"),
        State("precoolset-shgc", "value"),
        State("precoolset-ach", "value"),
        State("precoolset-internal-gain", "value"),
        State("precoolset-pv", "value"),
        State("precoolset-batt-support", "value"),
        State("precoolset-disallow-grid", "value"),
        State("precoolset-tariff-aware", "value"),
        State("precoolset-co2-aware", "value"),
        State("precoolset-soc-min", "value"),
        State("precoolset-soc-max", "value"),
        State("precoolset-w-cost", "value"),
        State("precoolset-w-co2", "value"),
        State("precoolset-w-peak", "value"),
        State("precoolset-w-comfort", "value"),
        State("precoolset-w-battery", "value"),
        State("precoolset-enable-fallback", "value"),
        State("precoolset-fb-start", "value"),
        State("precoolset-fb-dur", "value"),
        State("precoolset-fb-temp", "value"),
        State("precoolset-fb-rh", "value"),
        State("precoolset-trig-missing", "value"),
        State("precoolset-trig-optim", "value"),
        State("precoolset-trig-batt", "value"),
        State("precoolset-trig-comfort", "value"),
        State("precoolset-adv-latent", "value"),
        State("precoolset-adv-exergy", "value"),
        State("precoolset-adv-psy", "value"),
        State("precoolset-adv-debug", "value"),
        State("precoolset-adv-runner", "value"),
    ]

    def _normalize_floor_value(floor_value: str | None) -> str:
        s = str(floor_value or "").strip()
        return s if s.isdigit() else ""

    def _normalize_zone_values(zones_value) -> list[str]:
        if not isinstance(zones_value, list):
            return []
        out = []
        for z in zones_value:
            zs = str(z or "").strip().lower()
            if zs in {"a", "b", "c"}:
                out.append(zs)
        order = {"a": 0, "b": 1, "c": 2}
        out2 = []
        seen = set()
        for z in sorted(out, key=lambda x: order.get(x, 99)):
            if z in seen:
                continue
            seen.add(z)
            out2.append(z)
        return out2

    def _scope_ids_from_ui(floor_value: str | None, zones_value) -> list[str]:
        floor = _normalize_floor_value(floor_value)
        zones = _normalize_zone_values(zones_value)
        if not floor or not zones:
            return []
        return [f"floor{floor}_{z}" for z in zones]

    def _scope_label_from_ui(floor_value: str | None, zones_value) -> str:
        floor = _normalize_floor_value(floor_value)
        zones = _normalize_zone_values(zones_value)
        if not floor:
            return ""
        if set(zones) == {"a", "b", "c"}:
            return f"floor{floor}_all"
        if len(zones) == 1:
            return f"floor{floor}_{zones[0]}"
        if zones:
            return f"floor{floor}_" + "".join(zones)
        return f"floor{floor}"

    def _normalize_precooling_floor_zone_map(data: Any) -> dict[str, list[str]]:
        base = {"1": ["a"], "2": [], "3": []}
        raw = data if isinstance(data, dict) else {}
        out: dict[str, list[str]] = {"1": list(base["1"]), "2": [], "3": []}
        order = {"a": 0, "b": 1, "c": 2}
        for k, v in raw.items():
            fk = str(k).strip()
            if fk not in out:
                continue
            items = v if isinstance(v, list) else []
            zs: list[str] = []
            for x in items:
                z = str(x).strip().lower()
                if z in order and z not in zs:
                    zs.append(z)
            out[fk] = sorted(zs, key=lambda z: order.get(z, 99))
        return out

    @app.callback(
        Output("precoolset-zone", "value"),
        Input("precoolset-clear-zones-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_zones_clicked(_n):
        return []

    @app.callback(
        Output("precoolset-op-scope-indicator", "children"),
        [
            Input("precooling-floor", "value"),
            Input("precooling-floor-zone-map", "data"),
            Input("precooling-zone", "value"),
        ],
    )
    def render_precooling_scope_indicator(prec_floor_value, prec_map_data, prec_zone_value):
        floor = _normalize_floor_value(str(prec_floor_value)) or "1"
        fm = _normalize_precooling_floor_zone_map(prec_map_data)
        zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not zones:
            zones = _normalize_zone_values(prec_zone_value)
        zones_txt = ", ".join([z.upper() for z in zones]) if zones else "-"
        return f"Scope operasi saat ini: Lantai {floor} / Zone {zones_txt}"

    @app.callback(
        [Output("precoolset-floor", "value"), Output("precoolset-zone", "value", allow_duplicate=True)],
        Input("precoolset-copy-from-precooling-btn", "n_clicks"),
        [
            State("precooling-floor", "value"),
            State("precooling-floor-zone-map", "data"),
            State("precooling-zone", "value"),
        ],
        prevent_initial_call=True,
    )
    def copy_scope_from_precooling(_n, prec_floor_value, prec_map_data, prec_zone_value):
        floor = _normalize_floor_value(str(prec_floor_value)) or "1"
        fm = _normalize_precooling_floor_zone_map(prec_map_data)
        zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not zones:
            zones = _normalize_zone_values(prec_zone_value)
        return floor, zones

    @app.callback(
        Output("precoolset-scope-sync-msg", "children"),
        Input("precoolset-copy-from-precooling-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_copy_feedback(_n):
        return "Scope berhasil disalin dari tab Precooling."

    @app.callback(
        [
            Output("precoolset-use-in-precooling-btn", "disabled"),
            Output("precoolset-use-in-precooling-btn", "title"),
        ],
        [Input("precoolset-floor", "value"), Input("precoolset-zone", "value")],
    )
    def guard_use_in_precooling_btn(floor_value, zones_value):
        floor = _normalize_floor_value(floor_value)
        zones = _normalize_zone_values(zones_value)
        if not floor:
            return True, "Pilih lantai terlebih dahulu."
        if not zones:
            return True, "Pilih minimal 1 zone (A/B/C) terlebih dahulu."
        return False, ""

    @app.callback(
        [
            Output("precooling-floor", "value"),
            Output("precooling-zone", "value", allow_duplicate=True),
            Output("precooling-floor-zone-map", "data", allow_duplicate=True),
        ],
        Input("precoolset-use-in-precooling-btn", "n_clicks"),
        [State("precoolset-floor", "value"), State("precoolset-zone", "value"), State("precooling-floor-zone-map", "data")],
        prevent_initial_call=True,
    )
    def use_settings_scope_in_precooling(_n, floor_value, zones_value, prec_map_data):
        floor = _normalize_floor_value(floor_value) or "1"
        zones = _normalize_zone_values(zones_value)
        fm = _normalize_precooling_floor_zone_map(prec_map_data)
        fm[floor] = list(zones)
        return floor, zones, fm

    @app.callback(
        Output("precoolset-scope-sync-msg", "children", allow_duplicate=True),
        Input("precoolset-use-in-precooling-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_use_feedback(_n):
        return "Scope Settings sudah diterapkan ke tab Precooling."

    @app.callback(
        Output("precoolset-zone-selection-error", "children"),
        [Input("precoolset-floor", "value"), Input("precoolset-zone", "value")],
    )
    def validate_scope_selection(floor_value, zones_value):
        floor = _normalize_floor_value(floor_value)
        zones = _normalize_zone_values(zones_value)
        if not floor:
            return "Pilih lantai terlebih dahulu."
        if not zones:
            return "Pilih minimal 1 zone (A/B/C)."
        return ""

    @app.callback(
        Output("precoolset-zones-store", "data"),
        [Input("backend-readiness-store", "data"), Input("backend-readiness-interval", "n_intervals")],
        [State("precoolset-zones-store", "data"), State("token-store", "data")],
    )
    def refresh_precoolset_zones(readiness, n, cached, token_data):
        prec_headers = get_headers(token_data)
        def _sort_key(zid: str):
            s = str(zid or "").strip()
            if not s:
                return (999, 999, "")
            parts = s.split("_", 1)
            if len(parts) != 2 or not parts[0].lower().startswith("floor"):
                return (999, 999, s)
            try:
                floor = int(parts[0][5:])
            except Exception:
                floor = 999
            z = parts[1].lower()
            order = {"all": 0, "a": 1, "b": 2, "c": 3}.get(z, 99)
            return (floor, order, s)

        base_url = effective_base_url(readiness)
        cache = cached if isinstance(cached, dict) else {}
        cache_base = cache.get("base_url")
        cache_zones = cache.get("zones") if isinstance(cache.get("zones"), list) else []
        if cache_base == base_url and cache_zones and isinstance(n, int) and (n % 30) != 0:
            zone_items = [z for z in cache_zones if isinstance(z, dict) and isinstance(z.get("zone_id"), str)]
            return {"base_url": base_url, "zones": zone_items}

        data, _ = get_zones(base_url=base_url, headers=prec_headers)
        zones = data.get("zones") if isinstance(data, dict) else None
        zones_list = zones if isinstance(zones, list) else []
        zone_items = []
        for z in zones_list:
            if not isinstance(z, dict):
                continue
            zid = z.get("zone_id")
            if not isinstance(zid, str) or not zid.strip():
                continue
            raw_label = z.get("label") if isinstance(z.get("label"), str) and z.get("label").strip() else ""
            label = raw_label if raw_label and raw_label.strip() and raw_label.strip() != zid.strip() else pretty_zone_label(zid.strip())
            zone_items.append({"zone_id": zid.strip(), "label": label or zid.strip()})

        zone_ids_raw = [str(z.get("zone_id") or "").strip() for z in zone_items if isinstance(z, dict)]
        if set(zone_ids_raw) == {"zone_a", "zone_b", "zone_c"}:
            zone_map = {"zone_a": "a", "zone_b": "b", "zone_c": "c"}
            expanded: list[dict[str, str]] = []
            for floor in range(1, 5):
                for zid in zone_ids_raw:
                    short = zone_map.get(zid)
                    if not short:
                        continue
                    new_zid = f"floor{floor}_{short}"
                    expanded.append({"zone_id": new_zid, "label": pretty_zone_label(new_zid)})
            zone_items = expanded

        zone_ids_raw = [str(z.get("zone_id") or "").strip() for z in zone_items if isinstance(z, dict)]
        zone_id_set = set(zone_ids_raw)
        floors: set[int] = set()
        for it in zone_items:
            zid = str(it.get("zone_id") or "").strip()
            if not zid.lower().startswith("floor"):
                continue
            parts = zid.split("_", 1)
            if len(parts) != 2:
                continue
            try:
                floors.add(int(parts[0][5:]))
            except Exception:
                continue
        for floor in sorted(floors):
            zid_all = f"floor{floor}_all"
            if zid_all not in zone_id_set:
                zone_items.append({"zone_id": zid_all, "label": pretty_zone_label(zid_all)})
                zone_id_set.add(zid_all)

        zone_items.sort(key=lambda it: _sort_key(str(it.get("zone_id"))))
        return {"base_url": base_url, "zones": zone_items}

    form_outputs = [
        Output("precoolset-enable-precooling", "value"),
        Output("precoolset-enable-laeopf", "value"),
        Output("precoolset-default-mode", "value"),
        Output("precoolset-default-scenario", "value"),
        Output("precoolset-earliest", "value"),
        Output("precoolset-latest", "value"),
        Output("precoolset-min-dur", "value"),
        Output("precoolset-max-dur", "value"),
        Output("precoolset-weekday", "value"),
        Output("precoolset-weekend", "value"),
        Output("precoolset-holiday-behavior", "value"),
        Output("precoolset-min-temp", "value"),
        Output("precoolset-max-temp", "value"),
        Output("precoolset-target-temp", "value"),
        Output("precoolset-min-rh", "value"),
        Output("precoolset-max-rh", "value"),
        Output("precoolset-target-rh", "value"),
        Output("precoolset-comfort-priority", "value"),
        Output("precoolset-cap-limit", "value"),
        Output("precoolset-min-runtime", "value"),
        Output("precoolset-max-runtime", "value"),
        Output("precoolset-sp-lo", "value"),
        Output("precoolset-sp-hi", "value"),
        Output("precoolset-rh-lo", "value"),
        Output("precoolset-rh-hi", "value"),
        Output("precoolset-anti-short", "value"),
        Output("precoolset-ramp-limit", "value"),
        Output("precoolset-thermal-mass", "value"),
        Output("precoolset-floor-area", "value"),
        Output("precoolset-volume", "value"),
        Output("precoolset-u-wall", "value"),
        Output("precoolset-u-roof", "value"),
        Output("precoolset-shgc", "value"),
        Output("precoolset-ach", "value"),
        Output("precoolset-internal-gain", "value"),
        Output("precoolset-pv", "value"),
        Output("precoolset-batt-support", "value"),
        Output("precoolset-disallow-grid", "value"),
        Output("precoolset-tariff-aware", "value"),
        Output("precoolset-co2-aware", "value"),
        Output("precoolset-soc-min", "value"),
        Output("precoolset-soc-max", "value"),
        Output("precoolset-w-cost", "value"),
        Output("precoolset-w-co2", "value"),
        Output("precoolset-w-peak", "value"),
        Output("precoolset-w-comfort", "value"),
        Output("precoolset-w-battery", "value"),
        Output("precoolset-enable-fallback", "value"),
        Output("precoolset-fb-start", "value"),
        Output("precoolset-fb-dur", "value"),
        Output("precoolset-fb-temp", "value"),
        Output("precoolset-fb-rh", "value"),
        Output("precoolset-trig-missing", "value"),
        Output("precoolset-trig-optim", "value"),
        Output("precoolset-trig-batt", "value"),
        Output("precoolset-trig-comfort", "value"),
        Output("precoolset-adv-latent", "value"),
        Output("precoolset-adv-exergy", "value"),
        Output("precoolset-adv-psy", "value"),
        Output("precoolset-adv-debug", "value"),
        Output("precoolset-adv-runner", "value"),
    ]

    @app.callback(
        [
            Output("precoolset-bundle-store", "data", allow_duplicate=True),
            Output("precoolset-form-store", "data", allow_duplicate=True),
            Output("precoolset-config-badge", "children", allow_duplicate=True),
            Output("precoolset-config-badge", "style", allow_duplicate=True),
            Output("precoolset-action-msg", "children", allow_duplicate=True),
        ],
        [
            Input("precoolset-load-btn", "n_clicks"),
            Input("precoolset-floor", "value"),
            Input("precoolset-zone", "value"),
        ],
        [State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call="initial_duplicate",
    )
    def load_current(n, floor_value, zones_value, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        scope_ids = _scope_ids_from_ui(floor_value, zones_value)
        if not scope_ids:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), "Pilih Scope (Lantai + minimal 1 zone) terlebih dahulu."
        primary = scope_ids[0]
        data, err = get_settings(zone_id=primary, base_url=base_url, headers=prec_headers)
        if err:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), f"Gagal memuat konfigurasi precooling: {err}"

        bundle = data or {}
        default_data, _ = get_settings_default(zone_id=primary, base_url=base_url, headers=prec_headers)
        default_cfg = (default_data or {}).get("default", {})
        bundle = {**bundle, "default": default_cfg}

        draft = bundle.get("draft") if isinstance(bundle.get("draft"), dict) else {}
        status, suffix = _config_status(bundle)
        label = _scope_label_from_ui(floor_value, zones_value) or "-"
        scope_txt = f"scope={label}" if len(scope_ids) == 1 else f"scope={label} (targets {', '.join(scope_ids)})"
        return (
            bundle,
            draft,
            f"{status} ({suffix})",
            _badge_style(status),
            f"Loaded. {suffix} {scope_txt}",
        )

    @app.callback(
        [
            Output("precoolset-validation-store", "data", allow_duplicate=True),
            Output("precoolset-validation-badge", "children", allow_duplicate=True),
            Output("precoolset-validation-badge", "style", allow_duplicate=True),
        ],
        Input("precoolset-form-store", "data"),
        prevent_initial_call=True,
    )
    def reset_validation_on_load(form_store):
        if not isinstance(form_store, dict) or not form_store:
            return no_update, no_update, no_update
        return {}, "NOT VALIDATED", _badge_style("UNKNOWN")

    @app.callback(
        form_outputs,
        Input("precoolset-form-store", "data"),
        prevent_initial_call=True,
    )
    def render_form_from_store(cfg):
        if not isinstance(cfg, dict) or not cfg:
            return tuple([no_update] * len(form_outputs))
        return _form_from_cfg(cfg)

    @app.callback(
        [
            Output("precoolset-dirty-store", "data"),
            Output("precoolset-dirty-badge", "children"),
            Output("precoolset-dirty-badge", "style"),
            Output("precoolset-warning", "children"),
        ],
        [
            Input("precoolset-enable-precooling", "value"),
            Input("precoolset-enable-laeopf", "value"),
            Input("precoolset-default-mode", "value"),
            Input("precoolset-default-scenario", "value"),
            Input("precoolset-earliest", "value"),
            Input("precoolset-latest", "value"),
            Input("precoolset-min-dur", "value"),
            Input("precoolset-max-dur", "value"),
            Input("precoolset-weekday", "value"),
            Input("precoolset-weekend", "value"),
            Input("precoolset-holiday-behavior", "value"),
            Input("precoolset-min-temp", "value"),
            Input("precoolset-max-temp", "value"),
            Input("precoolset-target-temp", "value"),
            Input("precoolset-min-rh", "value"),
            Input("precoolset-max-rh", "value"),
            Input("precoolset-target-rh", "value"),
            Input("precoolset-comfort-priority", "value"),
            Input("precoolset-cap-limit", "value"),
            Input("precoolset-min-runtime", "value"),
            Input("precoolset-max-runtime", "value"),
            Input("precoolset-sp-lo", "value"),
            Input("precoolset-sp-hi", "value"),
            Input("precoolset-rh-lo", "value"),
            Input("precoolset-rh-hi", "value"),
            Input("precoolset-anti-short", "value"),
            Input("precoolset-ramp-limit", "value"),
            Input("precoolset-thermal-mass", "value"),
            Input("precoolset-floor-area", "value"),
            Input("precoolset-volume", "value"),
            Input("precoolset-u-wall", "value"),
            Input("precoolset-u-roof", "value"),
            Input("precoolset-shgc", "value"),
            Input("precoolset-ach", "value"),
            Input("precoolset-internal-gain", "value"),
            Input("precoolset-pv", "value"),
            Input("precoolset-batt-support", "value"),
            Input("precoolset-disallow-grid", "value"),
            Input("precoolset-tariff-aware", "value"),
            Input("precoolset-co2-aware", "value"),
            Input("precoolset-soc-min", "value"),
            Input("precoolset-soc-max", "value"),
            Input("precoolset-w-cost", "value"),
            Input("precoolset-w-co2", "value"),
            Input("precoolset-w-peak", "value"),
            Input("precoolset-w-comfort", "value"),
            Input("precoolset-w-battery", "value"),
            Input("precoolset-enable-fallback", "value"),
            Input("precoolset-fb-start", "value"),
            Input("precoolset-fb-dur", "value"),
            Input("precoolset-fb-temp", "value"),
            Input("precoolset-fb-rh", "value"),
            Input("precoolset-trig-missing", "value"),
            Input("precoolset-trig-optim", "value"),
            Input("precoolset-trig-batt", "value"),
            Input("precoolset-trig-comfort", "value"),
            Input("precoolset-adv-latent", "value"),
            Input("precoolset-adv-exergy", "value"),
            Input("precoolset-adv-psy", "value"),
            Input("precoolset-adv-debug", "value"),
            Input("precoolset-adv-runner", "value"),
        ],
        State("precoolset-form-store", "data"),
    )
    def detect_dirty(*args):
        form_store = args[-1] if len(args) else {}
        values = args[:-1]
        current = _cfg_from_form(*values)
        has_store = isinstance(form_store, dict) and bool(form_store)
        if not has_store:
            warn = html.Div(
                "Konfigurasi belum dimuat dari backend. Klik Load Current Settings untuk mengisi baseline sebelum menilai DIRTY/CLEAN.",
                style={"padding": "10px", "borderRadius": "8px", "backgroundColor": "#eef2ff", "border": "1px solid #c7d2fe", "color": "#1e3a8a", "marginTop": "10px"},
            )
            return False, "NOT LOADED", _badge_style("UNKNOWN"), warn
        dirty = not _safe_equal(current, form_store)
        if dirty:
            warn = html.Div(
                "Ada perubahan belum disimpan. Gunakan Save Settings untuk menyimpan draft dan Apply untuk mengaktifkan.",
                style={"padding": "10px", "borderRadius": "8px", "backgroundColor": "#fff3cd", "border": "1px solid #ffeeba", "color": "#856404", "marginTop": "10px"},
            )
            return True, "DIRTY", _badge_style("DIRTY"), warn
        return False, "CLEAN", _badge_style("CLEAN"), ""

    @app.callback(
        [
            Output("precoolset-validation-store", "data"),
            Output("precoolset-validation-badge", "children"),
            Output("precoolset-validation-badge", "style"),
            Output("precoolset-action-msg", "children", allow_duplicate=True),
        ],
        Input("precoolset-validate-btn", "n_clicks"),
        form_states + [State("precoolset-floor", "value"), State("precoolset-zone", "value"), State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call=True,
    )
    def validate_clicked(n, *values):
        token_data = values[-1] if len(values) else {}
        readiness = values[-2] if len(values) >= 2 else {}
        zones_value = values[-3] if len(values) >= 3 else None
        floor_value = values[-4] if len(values) >= 4 else None
        cfg = _cfg_from_form(*values[:-4])
        prec_headers = get_headers(token_data)

        base_url = effective_base_url(readiness)
        scope_ids = _scope_ids_from_ui(floor_value, zones_value)
        if not scope_ids:
            return {}, "ERROR", _badge_style("ERROR"), "Pilih Scope (Lantai + minimal 1 zone) terlebih dahulu."

        errors: list[str] = []
        warnings: list[str] = []
        ok_all = True
        for target in scope_ids:
            data, err = post_settings_validate(cfg, zone_id=target, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(f"{target}: {err}")
                ok_all = False
                continue
            ok = bool((data or {}).get("ok"))
            if not ok:
                ok_all = False
                for e in (data or {}).get("errors") or []:
                    errors.append(f"{target}: {e}")
            for w in (data or {}).get("warnings") or []:
                warnings.append(f"{target}: {w}")

        out = {"ok": ok_all, "warnings": warnings, "errors": errors, "targets": scope_ids}
        if ok_all:
            msg = "Konfigurasi valid."
            if warnings:
                msg = f"Konfigurasi valid dengan warning: {', '.join(warnings[:6])}"
            return out, "VALID", _badge_style("VALID"), msg
        msg = "Konfigurasi tidak valid."
        if errors:
            msg = f"Konfigurasi tidak valid: {', '.join(errors[:6])}"
        return out, "INVALID", _badge_style("INVALID"), msg

    @app.callback(
        [
            Output("precoolset-bundle-store", "data", allow_duplicate=True),
            Output("precoolset-form-store", "data", allow_duplicate=True),
            Output("precoolset-config-badge", "children", allow_duplicate=True),
            Output("precoolset-config-badge", "style", allow_duplicate=True),
            Output("precoolset-action-msg", "children", allow_duplicate=True),
        ],
        Input("precoolset-save-btn", "n_clicks"),
        form_states + [State("precoolset-floor", "value"), State("precoolset-zone", "value"), State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call=True,
    )
    def save_clicked(n, *values):
        token_data = values[-1] if len(values) else {}
        readiness = values[-2] if len(values) >= 2 else {}
        zones_value = values[-3] if len(values) >= 3 else None
        floor_value = values[-4] if len(values) >= 4 else None
        cfg = _cfg_from_form(*values[:-4])
        prec_headers = get_headers(token_data)

        base_url = effective_base_url(readiness)
        scope_ids = _scope_ids_from_ui(floor_value, zones_value)
        if not scope_ids:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), "Pilih Scope (Lantai + minimal 1 zone) terlebih dahulu."
        errors: list[str] = []
        warnings: list[str] = []
        first_bundle: dict[str, Any] | None = None
        for target in scope_ids:
            data, err = post_settings_save(cfg, zone_id=target, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(f"{target}: {err}")
                continue
            if (data or {}).get("warnings"):
                for w in (data or {}).get("warnings") or []:
                    warnings.append(f"{target}: {w}")
            if first_bundle is None:
                first_bundle = (data or {}).get("bundle") if isinstance((data or {}).get("bundle"), dict) else {}
        if errors:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), f"Gagal menyimpan konfigurasi: {', '.join(errors[:4])}"

        bundle = first_bundle or {}
        default_data, _ = get_settings_default(zone_id=scope_ids[0], base_url=base_url, headers=prec_headers)
        default_cfg = (default_data or {}).get("default", {})
        bundle = {**bundle, "default": default_cfg}
        draft = bundle.get("draft") if isinstance(bundle.get("draft"), dict) else {}
        status, suffix = _config_status(bundle)
        msg = "Pengaturan berhasil disimpan."
        if warnings:
            msg = f"Pengaturan disimpan dengan warning: {', '.join(warnings[:6])}"
        if len(scope_ids) > 1:
            msg = f"{msg} Targets: {', '.join(scope_ids)}"
        return bundle, draft, f"{status} ({suffix})", _badge_style(status), msg

    @app.callback(
        [
            Output("precoolset-bundle-store", "data", allow_duplicate=True),
            Output("precoolset-form-store", "data", allow_duplicate=True),
            Output("precoolset-config-badge", "children", allow_duplicate=True),
            Output("precoolset-config-badge", "style", allow_duplicate=True),
            Output("precoolset-action-msg", "children", allow_duplicate=True),
        ],
        Input("precoolset-reset-btn", "n_clicks"),
        [State("precoolset-floor", "value"), State("precoolset-zone", "value"), State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call=True,
    )
    def reset_clicked(n, floor_value, zones_value, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        scope_ids = _scope_ids_from_ui(floor_value, zones_value)
        if not scope_ids:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), "Pilih Scope (Lantai + minimal 1 zone) terlebih dahulu."
        errors: list[str] = []
        first_bundle: dict[str, Any] | None = None
        for target in scope_ids:
            data, err = post_settings_reset(zone_id=target, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(f"{target}: {err}")
                continue
            if first_bundle is None:
                first_bundle = (data or {}).get("bundle") if isinstance((data or {}).get("bundle"), dict) else {}
        if errors:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), f"Gagal reset konfigurasi: {', '.join(errors[:4])}"

        bundle = first_bundle or {}
        default_data, _ = get_settings_default(zone_id=scope_ids[0], base_url=base_url, headers=prec_headers)
        default_cfg = (default_data or {}).get("default", {})
        bundle = {**bundle, "default": default_cfg}
        draft = bundle.get("draft") if isinstance(bundle.get("draft"), dict) else {}
        status, suffix = _config_status(bundle)
        msg = "Konfigurasi default berhasil dimuat."
        if len(scope_ids) > 1:
            msg = f"{msg} Targets: {', '.join(scope_ids)}"
        return bundle, draft, f"{status} ({suffix})", _badge_style(status), msg

    @app.callback(
        [
            Output("precoolset-bundle-store", "data", allow_duplicate=True),
            Output("precoolset-form-store", "data", allow_duplicate=True),
            Output("precoolset-config-badge", "children", allow_duplicate=True),
            Output("precoolset-config-badge", "style", allow_duplicate=True),
            Output("precoolset-action-msg", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
        ],
        Input("precoolset-apply-btn", "n_clicks"),
        [State("precoolset-floor", "value"), State("precoolset-zone", "value"), State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call=True,
    )
    def apply_clicked(n, floor_value, zones_value, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        scope_ids = _scope_ids_from_ui(floor_value, zones_value)
        if not scope_ids:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), "Pilih Scope (Lantai + minimal 1 zone) terlebih dahulu.", {"ts": _now_str(), "src": "settings_apply"}

        errors: list[str] = []
        invalids: list[str] = []
        first_bundle: dict[str, Any] | None = None
        ok_all = True
        for target in scope_ids:
            data, err = post_settings_apply(zone_id=target, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(f"{target}: {err}")
                ok_all = False
                continue
            ok = bool((data or {}).get("ok"))
            if not ok:
                ok_all = False
                for e in (data or {}).get("errors") or []:
                    invalids.append(f"{target}: {e}")
            if first_bundle is None:
                first_bundle = (data or {}).get("bundle") if isinstance((data or {}).get("bundle"), dict) else {}

        if errors:
            return no_update, no_update, "ERROR", _badge_style("ERROR"), f"Gagal apply konfigurasi: {', '.join(errors[:4])}", {"ts": _now_str(), "src": "settings_apply"}

        bundle = first_bundle or {}
        default_data, _ = get_settings_default(zone_id=scope_ids[0], base_url=base_url, headers=prec_headers)
        default_cfg = (default_data or {}).get("default", {})
        bundle = {**bundle, "default": default_cfg}
        active = bundle.get("active") if isinstance(bundle.get("active"), dict) else {}
        status, suffix = _config_status(bundle)
        if not ok_all:
            msg = "Konfigurasi tidak valid."
            if invalids:
                msg = f"Konfigurasi tidak valid: {', '.join(invalids[:6])}"
            return bundle, active, "INVALID", _badge_style("INVALID"), msg, {"ts": _now_str(), "src": "settings_apply"}

        msg = "Konfigurasi berhasil di-apply ke Precooling Engine."
        if len(scope_ids) > 1:
            msg = f"{msg} Targets: {', '.join(scope_ids)}"
        return bundle, active, f"{status} ({suffix})", _badge_style(status), msg, {"ts": _now_str(), "src": "settings_apply"}
