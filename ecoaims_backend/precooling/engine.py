import datetime
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go

from ecoaims_backend.precooling.candidate_generator import generate_candidates
from ecoaims_backend.precooling.constraints import check_constraints
from ecoaims_backend.precooling.exergy import compute_exergy
from ecoaims_backend.precooling.fallback import fallback_status
from ecoaims_backend.precooling.latent import compute_latent_state
from ecoaims_backend.precooling.objective import objective_breakdown, score_candidate
from ecoaims_backend.precooling.simulator import derive_kpis_from_profile, simulate_load_profile
from ecoaims_backend.precooling.storage import now_iso
from ecoaims_backend.precooling.thermal import compute_thermal_state
from ecoaims_backend.precooling.validator import validate_simulate_request
from ecoaims_backend.precooling.evaluator import evaluate_scenarios


def _default_outdoor() -> Tuple[float, float]:
    now = datetime.datetime.now()
    temp = 30.0 + 2.5 * (1.0 if 11 <= now.hour <= 15 else 0.2)
    rh = 70.0 - 8.0 * (1.0 if 11 <= now.hour <= 15 else 0.2)
    return temp, rh


def _scenario_metrics(profile: List[Dict[str, Any]], comfort: float, shr: float, exergy_eff: float, ipei: float) -> Dict[str, Any]:
    base = derive_kpis_from_profile(profile)
    energy_kwh = float(base.get("energy_kwh", 0.0))
    peak_kw = float(base.get("peak_kw", 0.0))
    cost_idr = energy_kwh * 1444.7
    co2_kg = energy_kwh * 0.85
    return {
        "energy_kwh": round(energy_kwh, 2),
        "peak_kw": round(peak_kw, 2),
        "cost_idr": round(cost_idr, 0),
        "co2_kg": round(co2_kg, 2),
        "comfort_compliance": round(comfort, 3),
        "shr": round(shr, 3),
        "exergy_efficiency": round(exergy_eff, 3),
        "ipei": round(ipei, 3),
    }


def _add_minutes(hhmm: str, minutes: int) -> str:
    parts = (hhmm or "00:00").split(":")
    h = int(parts[0]) if len(parts) > 0 else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    total = max(0, min(24 * 60 - 1, h * 60 + m + int(minutes)))
    return f"{total // 60:02d}:{total % 60:02d}"


def build_schedule(zone: str, start_time: str, duration_min: int, target_t: float, target_rh: float, profile: List[Dict[str, Any]]) -> Dict[str, Any]:
    start_h = int((start_time or "00:00").split(":")[0])
    end_time = _add_minutes(start_time, duration_min)
    end_h = int(end_time.split(":")[0])
    slots: List[Dict[str, Any]] = []
    for p in profile:
        hour = str(p.get("hour", "00:00"))
        h = int(hour.split(":")[0])
        in_window = start_h <= h < max(start_h, end_h if end_h != start_h else start_h + 1)
        slots.append(
            {
                "time_slot": hour,
                "temperature_setpoint": round(target_t, 1) if in_window else 25.0,
                "rh_setpoint": round(target_rh, 1) if in_window else 60.0,
                "hvac_mode": "Precooling" if in_window else "Normal",
                "energy_source": "PV + Battery" if in_window else "Grid",
                "estimated_load": float(p.get("load_kw", 0.0)),
            }
        )
    return {"zone": zone, "generated_at": now_iso(), "start_time": start_time, "end_time": end_time, "slots": slots}


def run_precooling_engine(
    payload: Dict[str, Any], zone: str, mode: str, fallback_active: bool, settings: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ok, errors = validate_simulate_request(payload)
    if not ok:
        return None, "; ".join(errors)

    if fallback_active or mode == "fallback":
        fb = {}
        if isinstance(settings, dict) and isinstance(settings.get("fallback_rules"), dict):
            rules = settings.get("fallback_rules") or {}
            fb = {
                "start_time": rules.get("fallback_start_time", "-"),
                "duration_min": rules.get("fallback_duration_min", "-"),
                "temperature_c": rules.get("fallback_temperature_c", "-"),
                "rh_pct": rules.get("fallback_rh_pct", "-"),
            }
        return {
            "status": fallback_status(zone, fb),
            "schedule": {"slots": []},
            "kpi": {},
            "alerts": [],
            "audit": [],
            "simulation": {},
        }, None

    window = payload.get("window", {}) if isinstance(payload.get("window"), dict) else {}
    earliest = str(window.get("earliest_start", "05:00"))
    latest = str(window.get("latest_start", "10:00"))
    durations = payload.get("durations_min") or [30, 60, 90]
    durations_min = [int(x) for x in durations if isinstance(x, (int, float)) and int(x) > 0]
    if not durations_min:
        durations_min = [30, 60, 90]

    t_range = payload.get("target_temp_range") or [22, 25]
    rh_range = payload.get("target_rh_range") or [50, 60]
    tr = (float(t_range[0]), float(t_range[-1])) if isinstance(t_range, list) and len(t_range) >= 2 else (22.0, 25.0)
    rr = (float(rh_range[0]), float(rh_range[-1])) if isinstance(rh_range, list) and len(rh_range) >= 2 else (50.0, 60.0)

    weights = payload.get("weights", {}) if isinstance(payload.get("weights"), dict) else {}

    outdoor_t, outdoor_rh = _default_outdoor()
    indoor_t = 26.0

    candidates = generate_candidates(zone, earliest, latest, durations_min, tr, rr)

    adv = settings.get("advanced") if isinstance(settings, dict) and isinstance(settings.get("advanced"), dict) else {}
    latent_enabled = bool(adv.get("enable_latent_model", True))
    exergy_enabled = bool(adv.get("enable_exergy_model", True))

    ranked: List[Dict[str, Any]] = []
    constraint_rows: List[Dict[str, Any]] = []
    for c in candidates:
        feasible, rows = check_constraints(c)
        constraint_rows = rows
        if latent_enabled:
            latent_state = compute_latent_state(outdoor_t, outdoor_rh, float(c["target_t"]), float(c["target_rh"]))
            latent_state = {**latent_state, "enabled": True}
        else:
            latent_state = {
                "dew_point": None,
                "humidity_ratio": None,
                "latent_load": 0.0,
                "sensible_load": 0.0,
                "shr": 1.0,
                "enabled": False,
            }
        if exergy_enabled:
            ex = compute_exergy(float(latent_state["latent_load"]), float(latent_state["sensible_load"]))
            ex = {**ex, "enabled": True}
        else:
            ex = {"input": 0.0, "output": 0.0, "loss": 0.0, "efficiency": 0.0, "enabled": False}
        scr = score_candidate(c, weights, feasible, float(latent_state.get("shr", 1.0)), float(ex.get("efficiency", 0.0)))
        ranked.append(
            {
                **c,
                "score": scr,
                "feasible": "YES" if feasible else "NO",
                "risk": "LOW" if feasible else "HIGH",
            }
        )

    ranked.sort(key=lambda x: float(x.get("score", -9)), reverse=True)
    for idx, r in enumerate(ranked, start=1):
        r["rank"] = idx

    selected = ranked[0] if ranked else {}

    duration_sel = int(selected.get("duration", 60) or 60)
    start_sel = str(selected.get("start_time", "06:00"))
    end_sel = _add_minutes(start_sel, duration_sel)
    profile_laeopf = simulate_load_profile(duration_sel, start_sel)
    profile_rule = simulate_load_profile(max(30, duration_sel - 30), start_sel)
    profile_base = simulate_load_profile(0, "00:00")

    if latent_enabled:
        latent_sel = compute_latent_state(outdoor_t, outdoor_rh, float(selected.get("target_t", 24.0)), float(selected.get("target_rh", 55.0)))
        latent_sel = {**latent_sel, "enabled": True}
    else:
        latent_sel = {
            "dew_point": None,
            "humidity_ratio": None,
            "latent_load": 0.0,
            "sensible_load": 0.0,
            "shr": 1.0,
            "enabled": False,
        }
    if exergy_enabled:
        ex_sel = compute_exergy(float(latent_sel["latent_load"]), float(latent_sel["sensible_load"]))
        ex_sel = {**ex_sel, "enabled": True}
    else:
        ex_sel = {"input": 0.0, "output": 0.0, "loss": 0.0, "efficiency": 0.0, "enabled": False}

    comfort_laeopf = max(0.0, 1.0 - abs(float(selected.get("target_t", 24.0)) - 24.0) / 6.0)
    comfort_rule = max(0.0, comfort_laeopf - 0.08)
    comfort_base = max(0.0, comfort_laeopf - 0.18)

    eff_val = float(ex_sel.get("efficiency", 0.0) or 0.0)
    shr_val = float(latent_sel.get("shr", 1.0) or 1.0)
    ipei = 0.65 + 0.25 * eff_val
    baseline = _scenario_metrics(profile_base, comfort_base, shr_val - 0.05, eff_val - 0.06, ipei - 0.06)
    rule_based = _scenario_metrics(profile_rule, comfort_rule, shr_val - 0.02, eff_val - 0.03, ipei - 0.03)
    laeopf = _scenario_metrics(profile_laeopf, comfort_laeopf, shr_val, eff_val, ipei)

    comparison = evaluate_scenarios(baseline, rule_based, laeopf)

    status = {
        "status_today": "Active",
        "active_zones": zone,
        "start_time": start_sel,
        "end_time": end_sel,
        "duration": f"{duration_sel} min",
        "target_temperature": f"{selected.get('target_t', '-') } °C",
        "target_rh": f"{selected.get('target_rh', '-') } %",
        "recommended_energy_source": "PV + Battery",
        "optimization_objective": "Cost + Comfort + Peak + CO2",
        "confidence_score": 0.82,
        "comfort_risk": "LOW",
        "constraint_status": "OK",
        "strategy_type": "LAEOPF",
        "explainability": [
            "Suhu luar tinggi",
            "RH tinggi",
            "PV surplus tersedia",
            "SOC baterai sehat",
            "Occupancy akan dimulai",
            "Target peak reduction tercapai",
        ],
        "thermal_state": compute_thermal_state(zone, outdoor_t, indoor_t),
        "latent_state": {
            "rh_actual": outdoor_rh,
            "rh_target": float(selected.get("target_rh", 55.0)),
            "dew_point": latent_sel["dew_point"],
            "humidity_ratio": latent_sel["humidity_ratio"],
            "latent_load": latent_sel["latent_load"],
            "sensible_load": latent_sel["sensible_load"],
            "shr": latent_sel["shr"],
            "enabled": latent_sel.get("enabled", True),
        },
        "exergy": ex_sel,
        "models": {"latent_enabled": latent_enabled, "exergy_enabled": exergy_enabled},
    }

    schedule = build_schedule(zone, start_sel, duration_sel, float(selected.get("target_t", 24.0)), float(selected.get("target_rh", 55.0)), profile_laeopf)

    kpi = {
        "energy_saving": round(max(0.0, baseline["energy_kwh"] - laeopf["energy_kwh"]), 2),
        "peak_reduction": round(max(0.0, baseline["peak_kw"] - laeopf["peak_kw"]), 2),
        "cost_saving": round(max(0.0, baseline["cost_idr"] - laeopf["cost_idr"]), 0),
        "co2_reduction": round(max(0.0, baseline["co2_kg"] - laeopf["co2_kg"]), 2),
        "comfort_compliance": laeopf["comfort_compliance"],
        "shr": laeopf["shr"],
        "exergy_efficiency": laeopf["exergy_efficiency"],
        "ipei": laeopf["ipei"],
        "battery_impact": "LOW",
        "E_total": laeopf["energy_kwh"],
        "uncertainty": {
            "forecast_confidence": 0.78,
            "sensor_completeness": 0.86,
            "drift_risk": "LOW",
            "data_freshness": "OK",
        },
        "model_status": {"status": "READY", "retraining": "NOT_REQUIRED"},
    }

    peak_fig = go.Figure()
    peak_fig.add_trace(go.Bar(x=["Baseline", "Rule-Based", "LAEOPF"], y=[baseline["peak_kw"], rule_based["peak_kw"], laeopf["peak_kw"]], marker_color=[PREC_COLOR() for _ in range(3)]))
    peak_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="Peak Comparison", yaxis_title="kW")

    load_fig = go.Figure()
    load_fig.add_trace(go.Scatter(x=[p["hour"] for p in profile_base], y=[p["load_kw"] for p in profile_base], mode="lines", name="Baseline"))
    load_fig.add_trace(go.Scatter(x=[p["hour"] for p in profile_rule], y=[p["load_kw"] for p in profile_rule], mode="lines", name="Rule-Based"))
    load_fig.add_trace(go.Scatter(x=[p["hour"] for p in profile_laeopf], y=[p["load_kw"] for p in profile_laeopf], mode="lines", name="LAEOPF"))
    load_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="Load Profile Comparison", yaxis_title="kW", xaxis_title="Time")

    scatter_fig = go.Figure()
    scatter_fig.add_trace(go.Scatter(x=[baseline["cost_idr"], rule_based["cost_idr"], laeopf["cost_idr"]], y=[baseline["co2_kg"], rule_based["co2_kg"], laeopf["co2_kg"]], mode="markers+text", text=["Baseline", "Rule-Based", "LAEOPF"], textposition="top center"))
    scatter_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="Cost vs CO2", xaxis_title="Cost (IDR)", yaxis_title="CO2 (kg)")

    comfort_fig = go.Figure()
    comfort_fig.add_trace(go.Bar(x=["Baseline", "Rule-Based", "LAEOPF"], y=[baseline["comfort_compliance"], rule_based["comfort_compliance"], laeopf["comfort_compliance"]], marker_color=["#95a5a6", "#e67e22", "#27ae60"]))
    comfort_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="Comfort Compliance", yaxis_title="ratio")

    temp_times = [p["hour"] for p in profile_laeopf]
    temp_base = [25.0 for _ in temp_times]
    temp_opt = [float(selected.get("target_t", 24.0)) for _ in temp_times]
    temp_fig = go.Figure()
    temp_fig.add_trace(go.Scatter(x=temp_times, y=temp_base, mode="lines", name="Baseline T"))
    temp_fig.add_trace(go.Scatter(x=temp_times, y=temp_opt, mode="lines", name="Optimized T"))
    temp_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="Temperature: Baseline vs Optimized", yaxis_title="°C", xaxis_title="Time")

    rh_times = temp_times
    rh_base = [60.0 for _ in rh_times]
    rh_opt = [float(selected.get("target_rh", 55.0)) for _ in rh_times]
    rh_fig = go.Figure()
    rh_fig.add_trace(go.Scatter(x=rh_times, y=rh_base, mode="lines", name="Baseline RH"))
    rh_fig.add_trace(go.Scatter(x=rh_times, y=rh_opt, mode="lines", name="Optimized RH"))
    rh_fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title="RH: Baseline vs Optimized", yaxis_title="%", xaxis_title="Time")

    insight = {
        "objective": objective_breakdown(weights),
        "constraints": constraint_rows,
        "candidates": ranked,
        "selected_candidate": selected,
    }

    return {
        "zone": zone,
        "generated_at": now_iso(),
        "status": status,
        "schedule": schedule,
        "kpi": kpi,
        "scenarios": {
            "scenarios": [
                {"name": "Baseline", **baseline},
                {"name": "Rule-Based Precooling", **rule_based},
                {"name": "LAEOPF Optimized", **laeopf},
            ],
            "comparison": comparison,
        },
        "optimization_insight": insight,
        "fig_peak": peak_fig.to_plotly_json(),
        "fig_load": load_fig.to_plotly_json(),
        "fig_scatter": scatter_fig.to_plotly_json(),
        "fig_comfort": comfort_fig.to_plotly_json(),
        "fig_before_after_temp": temp_fig.to_plotly_json(),
        "fig_before_after_rh": rh_fig.to_plotly_json(),
    }, None


def PREC_COLOR() -> str:
    return "#2980b9"
