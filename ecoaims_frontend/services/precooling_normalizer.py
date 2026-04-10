from typing import Any, Dict, List, Optional


def _pick(obj: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for k in keys:
        if k in obj and obj.get(k) is not None:
            return obj.get(k)
    return default


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list_of_dicts(x: Any) -> List[Dict[str, Any]]:
    if isinstance(x, list):
        return [i for i in x if isinstance(i, dict)]
    return []


def normalize_status(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    manual_override = _as_dict(_pick(r, ["manual_override", "override", "manualOverride"], {}))
    mo_setpoints = _as_dict(_pick(manual_override, ["setpoints", "setpoint", "targets"], {}))
    raw_status_today = _pick(r, ["status_today", "today_status", "status"], None)
    if raw_status_today is None:
        active = r.get("active")
        mode = r.get("mode")
        if active is True and isinstance(mode, str) and mode.strip():
            raw_status_today = mode.strip()
        elif active is True:
            raw_status_today = "active"
        elif active is False:
            raw_status_today = "inactive"
        else:
            raw_status_today = "Unknown"
    status = {
        "status_today": raw_status_today,
        "active_zones": _pick(r, ["active_zones", "zones_active", "zones", "zone", "zone_id"], "-"),
        "start_time": _pick(r, ["start_time", "start", "startAt"], "-"),
        "end_time": _pick(r, ["end_time", "end", "endAt"], "-"),
        "duration": _pick(r, ["duration", "duration_min", "duration_minutes"], "-"),
        "target_temperature": _pick(r, ["target_temperature", "target_temp", "t_target", "setpoint_temp"], "-"),
        "target_rh": _pick(r, ["target_rh", "target_humidity", "rh_target", "setpoint_rh"], "-"),
        "recommended_energy_source": _pick(r, ["recommended_energy_source", "energy_source", "recommended_source"], "-"),
        "optimization_objective": _pick(r, ["optimization_objective", "objective", "objective_name"], "-"),
        "confidence_score": _pick(r, ["confidence_score", "confidence", "conf"], "-"),
        "comfort_risk": _pick(r, ["comfort_risk", "risk_comfort", "comfortRisk"], "-"),
        "constraint_status": _pick(r, ["constraint_status", "constraints_status", "constraints"], "-"),
        "strategy_type": _pick(r, ["strategy_type", "strategy", "mode"], None),
        "explainability": _pick(r, ["explainability", "reasons", "why"], []),
        "thermal_state": _as_dict(_pick(r, ["thermal_state", "thermal", "zone_thermal"], {})),
        "latent_state": _as_dict(_pick(r, ["latent_state", "latent", "humidity_state"], {})),
        "exergy": _as_dict(_pick(r, ["exergy", "exergy_analysis"], {})),
        "optimization_insight": _as_dict(_pick(r, ["optimization_insight", "insight"], {})),
        "settings_snapshot": _as_dict(_pick(r, ["settings_snapshot", "settings", "config_snapshot"], {})),
        "manual_override_state": _pick(manual_override, ["state", "status"], _pick(r, ["manual_override_state"], "disabled")),
        "manual_override_expires_at": _pick(manual_override, ["expires_at", "expiresAt"], _pick(r, ["manual_override_expires_at"], "-")),
        "manual_override_reason": _pick(manual_override, ["reason", "note"], _pick(r, ["manual_override_reason"], "")),
        "manual_override_setpoints": {
            "temperature_setpoint_c": _pick(mo_setpoints, ["temperature_setpoint_c", "temp_setpoint_c", "t_c", "temperature"], None),
            "rh_setpoint_pct": _pick(mo_setpoints, ["rh_setpoint_pct", "humidity_setpoint_pct", "rh_pct", "humidity"], None),
            "hvac_mode": _pick(mo_setpoints, ["hvac_mode", "mode"], None),
            "energy_source": _pick(mo_setpoints, ["energy_source", "source"], None),
        },
    }
    exp = status.get("explainability")
    if isinstance(exp, dict):
        reasons = exp.get("reason") if isinstance(exp.get("reason"), list) else []
        warnings = exp.get("warnings") if isinstance(exp.get("warnings"), list) else []
        lines = []
        if reasons:
            lines.extend([str(x) for x in reasons if x])
        if warnings:
            lines.extend([f"warning:{x}" for x in warnings if x])
        status["explainability"] = lines
    return status


def normalize_schedule(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    slots = _pick(r, ["slots", "schedule", "timeline", "items"], [])
    slots_list = _as_list_of_dicts(slots)
    if not slots_list:
        temps = _pick(r, ["temperature_schedule", "temp_schedule", "t_schedule"], [])
        rhs = _pick(r, ["rh_schedule", "humidity_schedule"], [])

        if isinstance(temps, list) and temps and all(isinstance(x, (int, float)) for x in temps):
            start = _pick(r, ["start_time", "start"], None)
            try:
                if isinstance(start, str) and start.strip():
                    s = start.strip().replace("Z", "+00:00")
                    start_dt = __import__("datetime").datetime.fromisoformat(s)
                else:
                    start_dt = None
            except Exception:
                start_dt = None
            for i, v in enumerate(temps):
                ts = (start_dt + __import__("datetime").timedelta(hours=i)).isoformat() if start_dt is not None else ""
                slots_list.append(
                    {"time_slot": ts, "temperature_setpoint": float(v), "rh_setpoint": "", "hvac_mode": "", "energy_source": "", "estimated_load": ""}
                )
        else:
            by_ts: Dict[str, Dict[str, Any]] = {}

            def _merge(series: Any, *, t_key: str, rh_key: str) -> None:
                if not isinstance(series, list):
                    return
                for it in series:
                    if not isinstance(it, dict):
                        continue
                    ts = it.get("timestamp") or it.get("time") or it.get("time_slot")
                    if not isinstance(ts, str) or not ts.strip():
                        continue
                    row = by_ts.get(ts) or {"time_slot": ts, "hvac_mode": "", "energy_source": "", "estimated_load": ""}
                    if t_key in it:
                        row["temperature_setpoint"] = it.get(t_key)
                    if rh_key in it:
                        row["rh_setpoint"] = it.get(rh_key)
                    by_ts[ts] = row

            _merge(temps, t_key="temp_setpoint_c", rh_key="rh_setpoint_pct")
            _merge(rhs, t_key="temp_setpoint_c", rh_key="rh_setpoint_pct")
            slots_list = [by_ts[k] for k in sorted(by_ts.keys())]

    normalized_slots: List[Dict[str, Any]] = []
    for s in slots_list:
        normalized_slots.append(
            {
                "time_slot": _pick(s, ["time_slot", "timestamp", "time", "hour", "ts"], ""),
                "temperature_setpoint": _pick(s, ["temperature_setpoint", "temp_setpoint_c", "t_set", "temp_setpoint", "target_temp"], ""),
                "rh_setpoint": _pick(s, ["rh_setpoint", "rh_setpoint_pct", "rh_set", "humidity_setpoint", "target_rh"], ""),
                "hvac_mode": _pick(s, ["hvac_mode", "mode", "hvac"], ""),
                "energy_source": _pick(s, ["energy_source", "source", "power_source"], ""),
                "estimated_load": _pick(s, ["estimated_load", "load_kw", "load", "kw"], ""),
            }
        )

    return {"slots": normalized_slots, "raw_meta": _as_dict(_pick(r, ["meta", "metadata"], {}))}


def normalize_scenarios(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    scenarios_raw = _pick(r, ["scenarios", "items", "data"], [])
    scenarios = _as_list_of_dicts(scenarios_raw)

    if not scenarios and isinstance(scenarios_raw, dict):
        scenarios = [scenarios_raw]

    normalized_scenarios: List[Dict[str, Any]] = []
    for s in scenarios:
        normalized_scenarios.append(
            {
                "name": _pick(s, ["name", "scenario", "id"], "Scenario"),
                "peak": _pick(s, ["peak", "peak_kw", "peak_load"], "-"),
                "cost": _pick(s, ["cost", "cost_idr", "cost_saving"], "-"),
                "co2": _pick(s, ["co2", "co2_kg", "co2_ton"], "-"),
                "comfort": _pick(s, ["comfort", "comfort_compliance", "compliance"], "-"),
                "shr": _pick(s, ["shr", "SHR"], None),
                "exergy_efficiency": _pick(s, ["exergy_efficiency", "exergyEff"], None),
                "ipei": _pick(s, ["ipei", "IPEI"], None),
            }
        )

    comparison_rows = _as_list_of_dicts(_pick(r, ["comparison", "compare_table", "table"], []))
    candidates = _as_list_of_dicts(_pick(r, ["candidates", "candidate_pool"], []))

    return {"scenarios": normalized_scenarios, "comparison": comparison_rows, "candidates": candidates}


def normalize_kpi(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    kpi = {
        "peak_reduction": _pick(r, ["peak_reduction_kw", "peak_reduction", "peakReduction", "kpi_peak_reduction"], "-"),
        "energy_saving": _pick(r, ["energy_saving_kwh", "energy_saving", "energySaving", "kpi_energy_saving"], "-"),
        "cost_saving": _pick(r, ["cost_saving_rp", "cost_saving_idr", "cost_saving", "costSaving", "kpi_cost_saving"], "-"),
        "co2_reduction": _pick(r, ["co2_reduction_kg", "co2_reduction", "co2Reduction", "kpi_co2_reduction"], "-"),
        "comfort_compliance": _pick(r, ["comfort_compliance_pct", "comfort_compliance", "comfortCompliance", "kpi_comfort"], "-"),
        "battery_impact": _pick(r, ["battery_impact", "batteryImpact", "kpi_battery"], "-"),
        "E_total": _pick(r, ["E_total", "e_total", "energy_total", "energy_total_kwh", "latent_load_kwh"], "-"),
        "exergy_efficiency": _pick(r, ["exergy_efficiency", "exergyEfficiency"], "beta"),
        "ipei": _pick(r, ["ipei", "IPEI"], "beta"),
        "shr": _pick(r, ["shr_avg", "shr", "SHR"], None),
        "uncertainty": _as_dict(_pick(r, ["uncertainty", "confidence", "data_confidence"], {})),
        "model_status": _as_dict(_pick(r, ["model_status", "model", "ml_status"], {})),
    }
    return kpi


def normalize_scenario_kpi(kpi_block: Dict[str, Any]) -> Dict[str, float]:
    kpi = kpi_block if isinstance(kpi_block, dict) else {}

    def _num(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _first_present(*vals: Any) -> Any:
        for v in vals:
            if v is not None:
                return v
        return None

    peak_kw = _num(_first_present(kpi.get("hvac_peak_kw"), kpi.get("peak_kw"), kpi.get("peak_reduction_kw")))
    comfort_pct = _num(_first_present(kpi.get("comfort_pct"), kpi.get("comfort_compliance_pct")))
    energy_kwh = _num(_first_present(kpi.get("hvac_energy_kwh"), kpi.get("energy_kwh"), kpi.get("energy_saving_kwh")))
    cost_rp = _num(_first_present(kpi.get("estimated_cost_rp"), kpi.get("cost_rp"), kpi.get("cost_saving_rp")))
    co2_kg = _num(_first_present(kpi.get("estimated_co2_kg"), kpi.get("co2_kg"), kpi.get("co2_reduction_kg")))

    return {"peak_kw": peak_kw, "comfort_pct": comfort_pct, "energy_kwh": energy_kwh, "cost_rp": cost_rp, "co2_kg": co2_kg}


def normalize_status_overview(sim_result: Dict[str, Any], request_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sr = sim_result if isinstance(sim_result, dict) else {}
    rp = request_payload if isinstance(request_payload, dict) else {}

    schedule = sr.get("schedule") if isinstance(sr.get("schedule"), dict) else {}
    slots = schedule.get("slots")
    slots_list = slots if isinstance(slots, list) else []

    comparison = sr.get("comparison") if isinstance(sr.get("comparison"), dict) else {}
    opt = comparison.get("optimized") if isinstance(comparison.get("optimized"), dict) else {}
    ts = opt.get("timestamps") if isinstance(opt.get("timestamps"), list) else []

    def _slot_time(s: Any) -> str:
        if not isinstance(s, dict):
            return ""
        v = s.get("time_slot") or s.get("timestamp") or s.get("time") or s.get("ts")
        return v.strip() if isinstance(v, str) else str(v) if v is not None else ""

    start = schedule.get("start_time")
    start_time = start.strip() if isinstance(start, str) and start.strip() else ""
    if not start_time and slots_list:
        start_time = _slot_time(slots_list[0])
    if not start_time and ts:
        start_time = str(ts[0])

    end = schedule.get("end_time")
    end_time = end.strip() if isinstance(end, str) and end.strip() else ""
    if not end_time and slots_list:
        end_time = _slot_time(slots_list[-1])
    if not end_time and ts:
        end_time = str(ts[-1])

    dur_min = schedule.get("duration_min")
    duration_txt = ""
    if isinstance(dur_min, (int, float)) and float(dur_min) > 0:
        duration_txt = f"{int(dur_min)} min"
    elif len(slots_list) > 1:
        try:
            import datetime as _dt

            s0 = _slot_time(slots_list[0]).replace("Z", "+00:00")
            s1 = _slot_time(slots_list[-1]).replace("Z", "+00:00")
            d0 = _dt.datetime.fromisoformat(s0)
            d1 = _dt.datetime.fromisoformat(s1)
            minutes = int(max(0.0, (d1 - d0).total_seconds() / 60.0))
            duration_txt = f"{minutes} min" if minutes > 0 else ""
        except Exception:
            duration_txt = ""

    target_temp = ""
    t_range = rp.get("target_temp_range")
    if isinstance(t_range, list) and len(t_range) >= 2:
        target_temp = f"{t_range[0]}-{t_range[1]}"
    elif slots_list:
        vals: List[float] = []
        for s in slots_list:
            if isinstance(s, dict):
                v = s.get("temperature_setpoint")
                if isinstance(v, (int, float)):
                    vals.append(float(v))
        if vals:
            target_temp = f"{min(vals):g}-{max(vals):g}"

    target_rh = ""
    rh_range = rp.get("target_rh_range")
    if isinstance(rh_range, list) and len(rh_range) >= 2:
        target_rh = f"{rh_range[0]}-{rh_range[1]}"
    elif slots_list:
        vals2: List[float] = []
        for s in slots_list:
            if isinstance(s, dict):
                v = s.get("rh_setpoint")
                if isinstance(v, (int, float)):
                    vals2.append(float(v))
        if vals2:
            target_rh = f"{min(vals2):g}-{max(vals2):g}"

    source = ""
    if slots_list:
        counts: Dict[str, int] = {}
        for s in slots_list:
            if isinstance(s, dict):
                v = s.get("energy_source")
                if isinstance(v, str) and v.strip():
                    k = v.strip()
                    counts[k] = counts.get(k, 0) + 1
        if counts:
            source = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
    if not source:
        v = rp.get("optimizer_backend")
        if isinstance(v, str) and v.strip():
            source = v.strip()

    objective_txt = ""
    weights = rp.get("weights")
    if isinstance(weights, dict) and weights:
        parts = []
        for k in ["comfort", "peak", "exergy", "cost", "co2", "battery_health"]:
            if k in weights and weights.get(k) is not None:
                parts.append(f"{k}={weights.get(k)}")
        objective_txt = ", ".join(parts) if parts else ""

    out = {
        "start_time": start_time or "-",
        "end_time": end_time or "-",
        "duration": duration_txt or "N/A",
        "target_temperature": target_temp or "-",
        "target_rh": target_rh or "-",
        "recommended_energy_source": source or "-",
    }
    if objective_txt:
        out["optimization_objective"] = objective_txt
    return out


def normalize_alerts(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    alerts = _as_list_of_dicts(_pick(r, ["alerts", "data", "items"], []))
    return {"alerts": alerts}


def normalize_audit(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    audit = _as_list_of_dicts(_pick(r, ["audit", "data", "items"], []))
    return {"audit": audit}


def normalize_simulate_result(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _as_dict(raw)
    insight = _as_dict(_pick(r, ["optimization_insight", "insight", "result"], {}))
    candidates = _as_list_of_dicts(_pick(insight, ["candidates", "candidate_ranking"], []))
    constraints = _as_list_of_dicts(_pick(insight, ["constraints", "constraint_matrix"], []))
    objective = _as_dict(_pick(insight, ["objective", "objective_breakdown"], {}))
    constraint_check = _as_dict(_pick(r, ["constraint_check", "constraintCheck"], {}))
    if not constraints and constraint_check:
        tmp: List[Dict[str, Any]] = []
        for k, v in constraint_check.items():
            if k == "notes":
                continue
            if isinstance(v, (str, int, float, bool)):
                tmp.append({"constraint": str(k), "status": str(v), "note": ""})
        notes = constraint_check.get("notes")
        if isinstance(notes, list) and notes:
            tmp.append({"constraint": "notes", "status": "info", "note": "; ".join([str(x) for x in notes if x])})
        constraints = tmp
    normalized = {**r}
    status_raw = normalized.get("status")
    status_seed: Dict[str, Any] = {}
    if isinstance(status_raw, dict):
        status_seed = dict(status_raw)
    elif isinstance(status_raw, str) and status_raw.strip():
        status_seed = {"status": status_raw.strip()}
    exp = normalized.get("explainability")
    reasons: List[str] = []
    if isinstance(exp, dict):
        rr = exp.get("reason")
        if isinstance(rr, list):
            reasons = [str(x) for x in rr if x]
    status_ui = normalize_status(status_seed)
    if reasons:
        for line in reasons:
            lo = line.strip().lower()
            if lo.startswith("mode:"):
                mode_txt = line.split(":", 1)[1].strip()
                if mode_txt:
                    mode_only = mode_txt.split("(", 1)[0].strip()
                    status_ui["status_today"] = mode_only or mode_txt
            if lo.startswith("objective focus:"):
                obj_txt = line.split(":", 1)[1].strip()
                if obj_txt:
                    status_ui["optimization_objective"] = obj_txt
            if lo.startswith("confidence_score="):
                cs = line.split("=", 1)[1].strip()
                if cs:
                    status_ui["confidence_score"] = cs
    if isinstance(exp, dict):
        cs = exp.get("confidence_score")
        if cs is not None:
            status_ui["confidence_score"] = cs
        warnings = exp.get("warnings")
        if isinstance(warnings, list) and warnings:
            ex = status_ui.get("explainability")
            ex_list = ex if isinstance(ex, list) else []
            for w in warnings:
                if w:
                    ex_list.append(f"warning:{w}")
            status_ui["explainability"] = ex_list
    zid = normalized.get("zone_id") or normalized.get("zone")
    if isinstance(zid, str) and zid.strip():
        status_ui["active_zones"] = zid.strip()
    elif zid is not None:
        status_ui["active_zones"] = str(zid)
    if constraint_check and status_ui.get("constraint_status") in {None, "-", ""}:
        ok = True
        parts: List[str] = []
        for k, v in constraint_check.items():
            if k == "notes":
                continue
            parts.append(f"{k}={v}")
            if isinstance(v, str) and v.strip().lower() not in {"pass", "ok", "true"}:
                ok = False
        status_ui["constraint_status"] = "OK" if ok else ", ".join(parts)

    kpi_raw = normalized.get("kpi")
    kpi_seed: Dict[str, Any] = dict(kpi_raw) if isinstance(kpi_raw, dict) else {}
    if "uncertainty" not in kpi_seed:
        confidence = exp.get("confidence_score") if isinstance(exp, dict) else None
        if confidence is not None:
            kpi_seed["uncertainty"] = {"forecast_confidence": confidence}
    if "model_status" not in kpi_seed:
        backend = None
        for line in reasons:
            if "(backend=" in line and ")" in line:
                frag = line.split("(backend=", 1)[1]
                backend = frag.split(")", 1)[0].strip()
                break
        if isinstance(backend, str) and backend:
            kpi_seed["model_status"] = {"status": backend, "retraining": "-"}

    comparison = normalized.get("comparison")
    if isinstance(comparison, dict):
        base = comparison.get("baseline") if isinstance(comparison.get("baseline"), dict) else {}
        opt = comparison.get("optimized") if isinstance(comparison.get("optimized"), dict) else {}
        ts = opt.get("timestamps") if isinstance(opt.get("timestamps"), list) and opt.get("timestamps") else base.get("timestamps")
        ts = ts if isinstance(ts, list) else []
        base_series = base.get("series") if isinstance(base.get("series"), dict) else {}
        opt_series = opt.get("series") if isinstance(opt.get("series"), dict) else {}

        def _pick_series_key(series: Dict[str, Any], names: List[str]) -> str | None:
            for nm in names:
                if nm in series and isinstance(series.get(nm), list):
                    return nm
            return None

        def _as_num_list(x: Any) -> List[float]:
            if not isinstance(x, list):
                return []
            out: List[float] = []
            for it in x:
                if isinstance(it, (int, float)):
                    out.append(float(it))
                else:
                    try:
                        out.append(float(it))
                    except Exception:
                        out.append(float("nan"))
            return out

        def _series_pair(key: str | None) -> tuple[List[float], List[float]]:
            if not key:
                return [], []
            b = _as_num_list(base_series.get(key))
            o = _as_num_list(opt_series.get(key))
            n = min(len(ts), len(b), len(o)) if ts else min(len(b), len(o))
            return b[:n], o[:n]

        def _fig(title: str, y_label: str, b: List[float], o: List[float]) -> Dict[str, Any] | None:
            if not ts or not b or not o:
                return None
            n = min(len(ts), len(b), len(o))
            x = ts[:n]
            return {
                "data": [
                    {"type": "scatter", "mode": "lines", "name": "Baseline", "x": x, "y": b[:n]},
                    {"type": "scatter", "mode": "lines", "name": "Optimized", "x": x, "y": o[:n]},
                ],
                "layout": {
                    "template": "plotly_white",
                    "title": {"text": title},
                    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
                    "legend": {"orientation": "h"},
                    "yaxis": {"title": {"text": y_label}},
                },
            }

        load_key = _pick_series_key(opt_series, ["hvac_electrical_kw", "grid_import_kw", "battery_charge_kw", "battery_discharge_kw"])
        temp_key = _pick_series_key(opt_series, ["zone_temp_c", "indoor_temp_c"])
        rh_key = _pick_series_key(opt_series, ["zone_rh_pct", "indoor_rh_pct"])

        b_load, o_load = _series_pair(load_key)
        b_temp, o_temp = _series_pair(temp_key)
        b_rh, o_rh = _series_pair(rh_key)

        fig_load = _fig("Load: Baseline vs Optimized", "kW", b_load, o_load)
        fig_temp = _fig("Temperature: Baseline vs Optimized", "°C", b_temp, o_temp)
        fig_rh = _fig("RH: Baseline vs Optimized", "%", b_rh, o_rh)
        if fig_load is not None:
            normalized["fig_load"] = fig_load
        if fig_temp is not None:
            normalized["fig_before_after_temp"] = fig_temp
        if fig_rh is not None:
            normalized["fig_before_after_rh"] = fig_rh

        def _kpi_of(name: str) -> Dict[str, Any]:
            block = comparison.get(name)
            if isinstance(block, dict) and isinstance(block.get("kpi"), dict):
                return block.get("kpi")  # type: ignore[return-value]
            return {}

        kpi_b = _kpi_of("baseline")
        kpi_r = _kpi_of("rule_based")
        kpi_o = _kpi_of("optimized")

        kb = normalize_scenario_kpi(kpi_b)
        kr = normalize_scenario_kpi(kpi_r)
        ko = normalize_scenario_kpi(kpi_o)

        peak_vals = [kb["peak_kw"], kr["peak_kw"], ko["peak_kw"]]
        cost_vals = [kb["cost_rp"], kr["cost_rp"], ko["cost_rp"]]
        co2_vals = [kb["co2_kg"], kr["co2_kg"], ko["co2_kg"]]
        comfort_vals = [kb["comfort_pct"], kr["comfort_pct"], ko["comfort_pct"]]
        xs = ["Baseline", "Rule-Based", "LAEOPF"]
        peak_max = max(peak_vals) if peak_vals else 0.0
        comfort_max = max(comfort_vals) if comfort_vals else 0.0
        normalized["fig_peak"] = {
            "data": [
                {"type": "bar", "name": "Peak", "x": xs, "y": peak_vals, "marker": {"color": ["#2980b9", "#f39c12", "#27ae60"]}},
                {"type": "scatter", "name": "Value", "showlegend": False, "mode": "markers+text", "x": xs, "y": peak_vals, "text": [str(v) for v in peak_vals], "textposition": "top center", "marker": {"size": 10, "color": "#2c3e50"}},
            ],
            "layout": {"template": "plotly_white", "title": {"text": "Peak Comparison"}, "margin": {"l": 40, "r": 20, "t": 40, "b": 40}, "yaxis": {"title": {"text": "kW"}, "range": [0, max(1.0, peak_max * 1.2)]}},
        }
        normalized["fig_scatter"] = {
            "data": [{"type": "scatter", "mode": "markers+text", "x": cost_vals, "y": co2_vals, "text": xs, "textposition": "top center", "marker": {"size": 10, "color": ["#2980b9", "#f39c12", "#27ae60"]}}],
            "layout": {"template": "plotly_white", "title": {"text": "Cost vs CO2"}, "margin": {"l": 50, "r": 20, "t": 40, "b": 40}, "xaxis": {"title": {"text": "Cost (Rp)"}}, "yaxis": {"title": {"text": "CO2 (kg)"}}},
        }
        normalized["fig_comfort"] = {
            "data": [
                {"type": "bar", "name": "Comfort", "x": xs, "y": comfort_vals, "text": [f"{v:.1f}%" for v in comfort_vals], "textposition": "auto", "marker": {"color": ["#2980b9", "#f39c12", "#27ae60"]}},
                {"type": "scatter", "name": "Value", "showlegend": False, "mode": "markers+text", "x": xs, "y": comfort_vals, "text": [f"{v:.1f}%" for v in comfort_vals], "textposition": "top center", "marker": {"size": 10, "color": "#2c3e50"}},
            ],
            "layout": {
                "template": "plotly_white",
                "title": {"text": "Comfort Compliance"},
                "margin": {"l": 40, "r": 20, "t": 70, "b": 40},
                "yaxis": {"title": {"text": "%"}, "range": [0, max(1.0, comfort_max * 1.2)]},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0,
                        "y": 1.18,
                        "xanchor": "left",
                        "yanchor": "top",
                        "showarrow": False,
                        "text": f"Baseline: {comfort_vals[0]:.1f}% | Rule-Based: {comfort_vals[1]:.1f}% | LAEOPF: {comfort_vals[2]:.1f}%",
                        "font": {"size": 12, "color": "#566573"},
                    }
                ],
            },
        }
        if comfort_vals and all(v == 0.0 for v in comfort_vals):
            normalized["fig_comfort"]["layout"]["title"] = {"text": "Comfort Compliance (all 0% — valid result)"}
            normalized["fig_comfort"]["layout"]["annotations"].append(
                {
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0,
                    "y": 1.08,
                    "xanchor": "left",
                    "yanchor": "top",
                    "showarrow": False,
                    "text": "Comfort compliance 0% untuk semua skenario (bukan error).",
                    "font": {"size": 12, "color": "#7f8c8d"},
                }
            )

        normalized["scenarios"] = {
            "scenarios": [
                {"name": "Baseline", "peak": peak_vals[0], "peak_kw": peak_vals[0], "cost": cost_vals[0], "cost_idr": cost_vals[0], "co2": co2_vals[0], "co2_kg": co2_vals[0], "comfort": comfort_vals[0], "comfort_compliance": comfort_vals[0]},
                {"name": "Rule-Based Precooling", "peak": peak_vals[1], "peak_kw": peak_vals[1], "cost": cost_vals[1], "cost_idr": cost_vals[1], "co2": co2_vals[1], "co2_kg": co2_vals[1], "comfort": comfort_vals[1], "comfort_compliance": comfort_vals[1]},
                {"name": "LAEOPF Optimized", "peak": peak_vals[2], "peak_kw": peak_vals[2], "cost": cost_vals[2], "cost_idr": cost_vals[2], "co2": co2_vals[2], "co2_kg": co2_vals[2], "comfort": comfort_vals[2], "comfort_compliance": comfort_vals[2]},
            ],
            "comparison": [
                {"metric": "peak_kw", "baseline": peak_vals[0], "rule_based": peak_vals[1], "laeopf": peak_vals[2]},
                {"metric": "energy_kwh", "baseline": kb["energy_kwh"], "rule_based": kr["energy_kwh"], "laeopf": ko["energy_kwh"]},
                {"metric": "cost_rp", "baseline": cost_vals[0], "rule_based": cost_vals[1], "laeopf": cost_vals[2]},
                {"metric": "co2_kg", "baseline": co2_vals[0], "rule_based": co2_vals[1], "laeopf": co2_vals[2]},
                {"metric": "comfort_pct", "baseline": comfort_vals[0], "rule_based": comfort_vals[1], "laeopf": comfort_vals[2]},
            ],
            "candidates": [],
        }

    normalized["status_raw"] = status_raw
    normalized["status"] = status_ui
    if kpi_seed:
        normalized["kpi"] = kpi_seed
    normalized["optimization_insight"] = {**_as_dict(normalized.get("optimization_insight"))}
    normalized["optimization_insight"]["candidates"] = candidates
    normalized["optimization_insight"]["constraints"] = constraints
    normalized["optimization_insight"]["objective"] = objective
    return normalized
