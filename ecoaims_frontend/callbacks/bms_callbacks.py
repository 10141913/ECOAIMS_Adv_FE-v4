import json
import time
import datetime
import requests
from typing import Any

from dash import Input, Output, State, callback_context, dcc, html, no_update
import plotly.graph_objects as go
from ecoaims_frontend.config import ENERGY_LIMITS
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.services.data_service import get_energy_data
from ecoaims_frontend.services.bms_service import bms_service
from ecoaims_frontend.services.live_data_service import get_live_sensor_data
from ecoaims_frontend.services.optimizer_tuner_api import suggest_tuner
from ecoaims_frontend.services.policy_proposer_api import propose_policy_action
from ecoaims_frontend.ui.error_ui import error_banner, error_figure, error_text


def _monitoring_battery_state(*, base_url: str | None) -> dict | None:
    try:
        live_data = get_live_sensor_data()
        live_supply = live_data.get("supply") if isinstance(live_data, dict) else {}
        if isinstance(live_supply, dict):
            live_batt = live_supply.get("Battery")
            if isinstance(live_batt, (int, float)):
                batt_max = float(ENERGY_LIMITS.get("battery") or 0.0)
                if batt_max <= 0:
                    return None
                v = max(0.0, min(float(live_batt), batt_max))
                return {"value": v, "max": batt_max, "status": "Unknown", "source": "live"}
    except Exception:
        pass

    data = get_energy_data(skip_backend=False, base_url=base_url)
    if isinstance(data, dict):
        batt = data.get("battery")
        if isinstance(batt, dict):
            v = batt.get("value")
            m = batt.get("max")
            if isinstance(v, (int, float)) and isinstance(m, (int, float)) and float(m) > 0:
                return {
                    "value": float(v),
                    "max": float(m),
                    "status": str(batt.get("status") or "Idle"),
                    "source": str(batt.get("source") or "unknown"),
                }
    return None


def _external_bms_mode(*, base_url: str | None) -> bool:
    batt = _monitoring_battery_state(base_url=base_url)
    if not isinstance(batt, dict):
        return False
    src = str(batt.get("source") or "")
    return src in {"live", "backend", "backend_state"}


def _soc_percent_from_batt(batt: dict) -> float:
    v = float(batt.get("value") or 0.0)
    m = float(batt.get("max") or 0.0)
    if m <= 0:
        return 0.0
    return max(0.0, min(100.0, (v / m) * 100.0))

def _default_rl_dispatch_payload(*, stream_id: str) -> dict:
    sid = str(stream_id or "").strip() or "proof-rl-1"
    return {
        "stream_id": sid,
        "optimizer_backend": "rl",
        "end_use_cols": ["HVAC", "Lighting", "Pump"],
        "critical_loads": ["Lighting", "Pump"],
        "flexible_loads": ["HVAC"],
        "optimizer_config": {
            "rl_enabled": True,
            "rl_train_episodes": 60,
            "rl_random_seed": 7,
            "rl_use_biofuel_action": False,
        },
        "demand_row": {"timestamp": "2026-03-10T00:00:00", "HVAC": 50.0, "Lighting": 20.0, "Pump": 10.0},
        "supply_row": {"timestamp": "2026-03-10T00:00:00", "PV_potential_kWh": 20.0, "WT_potential_kWh": 5.0},
    }

def _as_float(x: Any) -> float | None:
    try:
        return float(x)
    except Exception:
        return None

def _summarize_dispatch_result(payload: dict) -> tuple[dict, list[dict]]:
    p = payload if isinstance(payload, dict) else {}
    kpi = p.get("kpi") if isinstance(p.get("kpi"), dict) else {}
    schedule = p.get("schedule")
    if not isinstance(schedule, list):
        schedule = p.get("schedule_rows")
    if not isinstance(schedule, list):
        schedule = p.get("rows")
    rows = [r for r in schedule if isinstance(r, dict)] if isinstance(schedule, list) else []
    if not kpi and rows:
        total_grid = 0.0
        total_cost = 0.0
        total_emission = 0.0
        total_unmet = 0.0
        last_soc = None
        for r in rows:
            v = _as_float(r.get("grid_import_kwh"))
            if v is not None:
                total_grid += v
            v = _as_float(r.get("cost"))
            if v is not None:
                total_cost += v
            v = _as_float(r.get("emission"))
            if v is not None:
                total_emission += v
            v = _as_float(r.get("unmet_kwh"))
            if v is not None:
                total_unmet += v
            soc_v = _as_float(r.get("soc"))
            if soc_v is not None:
                last_soc = soc_v
        kpi = {
            "total_grid_import_kwh": total_grid,
            "total_cost": total_cost,
            "total_emission": total_emission,
            "total_unmet_kwh": total_unmet,
        }
        if last_soc is not None:
            kpi["final_soc"] = last_soc
    return kpi, rows

def _summarize_dashboard_dispatch(payload: dict) -> tuple[dict, list[dict]]:
    p = payload if isinstance(payload, dict) else {}
    records = p.get("records")
    rows = [r for r in records if isinstance(r, dict)] if isinstance(records, list) else []
    if not rows:
        return {}, []
    total_grid = 0.0
    total_cost = 0.0
    total_emission = 0.0
    total_unmet = 0.0
    last_soc = None
    for r in rows:
        v = _as_float(r.get("grid_import_kwh"))
        if v is not None:
            total_grid += v
        v = _as_float(r.get("cost"))
        if v is not None:
            total_cost += v
        v = _as_float(r.get("emission"))
        if v is not None:
            total_emission += v
        v = _as_float(r.get("unmet_load_kwh"))
        if v is not None:
            total_unmet += v
        soc_v = _as_float(r.get("soc"))
        if soc_v is not None:
            last_soc = soc_v
    kpi = {
        "total_grid_import_kwh": total_grid,
        "total_cost": total_cost,
        "total_emission": total_emission,
        "total_unmet_kwh": total_unmet,
    }
    if last_soc is not None:
        kpi["final_soc"] = last_soc
    return kpi, rows


def _build_rl_dispatch_payload(*, base_url: str, stream_id: str, existing: dict, mode: str) -> dict:
    payload = dict(existing or {})
    payload["stream_id"] = stream_id
    payload["optimizer_backend"] = "rl"

    energy = get_energy_data(skip_backend=False, base_url=base_url) if base_url else None
    energy = energy if isinstance(energy, dict) else {}

    def _num(v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    solar_kw = _num(((energy.get("solar") or {}) if isinstance(energy.get("solar"), dict) else {}).get("value"))
    wind_kw = _num(((energy.get("wind") or {}) if isinstance(energy.get("wind"), dict) else {}).get("value"))
    grid_kw = _num(((energy.get("grid") or {}) if isinstance(energy.get("grid"), dict) else {}).get("value"))
    bio_kw = _num(((energy.get("biofuel") or {}) if isinstance(energy.get("biofuel"), dict) else {}).get("value"))
    batt = (energy.get("battery") if isinstance(energy.get("battery"), dict) else {}) or {}
    batt_soc_pct = batt.get("soc_pct")
    batt_soc = batt.get("soc")

    if isinstance(payload.get("end_use_cols"), list) and payload.get("end_use_cols"):
        end_use_cols = [str(x) for x in payload.get("end_use_cols") if isinstance(x, (str, int, float)) and str(x).strip()]
    else:
        end_use_cols = ["HVAC", "Lighting", "Pump"]
    payload["end_use_cols"] = end_use_cols

    if not isinstance(payload.get("supply_row"), dict) or not payload.get("supply_row"):
        supply_row: dict[str, Any] = {}
        supply_row["PV_potential_kWh"] = max(0.0, solar_kw)
        supply_row["WT_potential_kWh"] = max(0.0, wind_kw)
        supply_row["timestamp"] = datetime.datetime.now().isoformat()
        payload["supply_row"] = supply_row

    total_load_kw = None
    if isinstance(energy.get("load_kw"), (int, float)):
        total_load_kw = float(energy.get("load_kw") or 0.0)
    if total_load_kw is None and isinstance(energy.get("records"), list) and energy.get("records"):
        last = energy.get("records")[-1]
        if isinstance(last, dict):
            for k in ["load_kw", "total_load_kw", "total_load", "load_power", "total_demand_kw"]:
                if isinstance(last.get(k), (int, float)):
                    total_load_kw = float(last.get(k) or 0.0)
                    break
    if total_load_kw is None:
        total_load_kw = max(0.0, solar_kw + wind_kw + grid_kw + bio_kw)
    if total_load_kw <= 0:
        total_load_kw = 80.0

    if not isinstance(payload.get("demand_row"), dict) or not payload.get("demand_row"):
        demand_row: dict[str, Any] = {"timestamp": datetime.datetime.now().isoformat()}
        ratios = {"HVAC": 0.6, "Lighting": 0.25, "Pump": 0.15}
        for c in end_use_cols:
            r = float(ratios.get(c, 0.0))
            demand_row[str(c)] = float(total_load_kw) * r if r > 0 else 0.0
        payload["demand_row"] = demand_row

    if not isinstance(payload.get("optimizer_config"), dict):
        payload["optimizer_config"] = {}
    cfg = payload.get("optimizer_config") if isinstance(payload.get("optimizer_config"), dict) else {}
    if "battery_soc_min" not in cfg:
        cfg["battery_soc_min"] = 0.2
    if "battery_soc_max" not in cfg:
        cfg["battery_soc_max"] = 0.8
    if "battery_soc_initial" not in cfg:
        init = None
        if isinstance(batt_soc_pct, (int, float)):
            init = float(batt_soc_pct) / 100.0
        elif isinstance(batt_soc, (int, float)):
            init = float(batt_soc)
        init = init if isinstance(init, (int, float)) else 0.5
        cfg["battery_soc_initial"] = max(0.0, min(1.0, float(init)))
    if "battery_capacity_kwh" not in cfg:
        cfg["battery_capacity_kwh"] = 60.0
    if "battery_max_charge_kw" not in cfg:
        cfg["battery_max_charge_kw"] = 30.0
    if "battery_max_discharge_kw" not in cfg:
        cfg["battery_max_discharge_kw"] = 30.0
    if "battery_charge_efficiency" not in cfg:
        cfg["battery_charge_efficiency"] = 0.95
    if "battery_discharge_efficiency" not in cfg:
        cfg["battery_discharge_efficiency"] = 0.95
    if "charge_before_export" not in cfg:
        cfg["charge_before_export"] = True
    if "allow_grid_export" not in cfg:
        cfg["allow_grid_export"] = False
    cfg.pop("prefer_charge_with_surplus", None)
    payload["optimizer_config"] = cfg

    if "critical_loads" not in payload:
        payload["critical_loads"] = ["Lighting", "Pump"]
    if "flexible_loads" not in payload:
        payload["flexible_loads"] = ["HVAC"]

    if mode == "batch":
        horizon = 24
        demand_rows = payload.get("demand_rows") if isinstance(payload.get("demand_rows"), list) else []
        supply_rows = payload.get("supply_rows") if isinstance(payload.get("supply_rows"), list) else []
        if not demand_rows or not supply_rows or len(demand_rows) != len(supply_rows):
            base_demand = payload.get("demand_row") if isinstance(payload.get("demand_row"), dict) else {}
            base_supply = payload.get("supply_row") if isinstance(payload.get("supply_row"), dict) else {}
            now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
            demand_rows = []
            supply_rows = []
            for i in range(horizon):
                ts = (now + datetime.timedelta(hours=i)).isoformat()
                dr = dict(base_demand)
                dr["timestamp"] = ts
                sr = dict(base_supply)
                sr["timestamp"] = ts
                demand_rows.append(dr)
                supply_rows.append(sr)
        payload2 = {
            "stream_id": payload.get("stream_id"),
            "optimizer_backend": payload.get("optimizer_backend"),
            "end_use_cols": payload.get("end_use_cols"),
            "critical_loads": payload.get("critical_loads"),
            "flexible_loads": payload.get("flexible_loads"),
            "optimizer_config": payload.get("optimizer_config"),
            "demand_rows": demand_rows,
            "supply_rows": supply_rows,
        }
        return payload2

    if payload.get("bootstrap_demand_rows") is None:
        base_row = payload.get("demand_row") if isinstance(payload.get("demand_row"), dict) else {}
        seq: list[dict[str, Any]] = []
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        for i in range(8):
            row = dict(base_row)
            row["timestamp"] = (now + datetime.timedelta(hours=i)).isoformat()
            seq.append(row)
        payload["bootstrap_demand_rows"] = seq

    if payload.get("bootstrap_supply_rows") is None:
        base_row = payload.get("supply_row") if isinstance(payload.get("supply_row"), dict) else {}
        seq: list[dict[str, Any]] = []
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        for i in range(8):
            row = dict(base_row)
            row["timestamp"] = (now + datetime.timedelta(hours=i)).isoformat()
            seq.append(row)
        payload["bootstrap_supply_rows"] = seq

    return payload


def _tuner_context_from_dispatch_payload(payload: dict) -> dict:
    p = payload if isinstance(payload, dict) else {}
    cfg = p.get("optimizer_config") if isinstance(p.get("optimizer_config"), dict) else {}
    soc = cfg.get("battery_soc_initial")
    soc_v = float(soc) if isinstance(soc, (int, float)) else None

    def _first_row(key_rows: str, key_row: str) -> dict | None:
        rows = p.get(key_rows)
        if isinstance(rows, list) and rows:
            r0 = rows[0]
            return r0 if isinstance(r0, dict) else None
        r1 = p.get(key_row)
        return r1 if isinstance(r1, dict) else None

    dr = _first_row("demand_rows", "demand_row") or {}
    sr = _first_row("supply_rows", "supply_row") or {}

    demand_total = 0.0
    for k, v in dr.items():
        if str(k) == "timestamp":
            continue
        if isinstance(v, (int, float)):
            demand_total += float(v)

    renewable_potential = 0.0
    for k in ["PV_potential_kWh", "WT_potential_kWh", "pv_potential_kwh", "wt_potential_kwh", "renewable_potential_kwh"]:
        v = sr.get(k)
        if isinstance(v, (int, float)):
            renewable_potential += float(v)

    ts = None
    for cand in [dr.get("timestamp"), sr.get("timestamp")]:
        if isinstance(cand, str) and cand.strip():
            ts = cand.strip()
            break

    hour = None
    if isinstance(ts, str) and ts:
        try:
            t = ts.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(t)
            hour = int(dt.hour)
        except Exception:
            hour = None

    ctx: dict[str, Any] = {}
    if soc_v is not None:
        ctx["soc"] = soc_v
    if demand_total > 0:
        ctx["demand_total_kwh"] = demand_total
    if renewable_potential > 0:
        ctx["renewable_potential_kwh"] = renewable_potential
    if ts is not None:
        ctx["timestamp"] = ts
    if hour is not None:
        ctx["hour"] = hour
    return ctx


def _extract_tuner_parts(resp: dict) -> tuple[dict | None, dict | None, dict]:
    r = resp if isinstance(resp, dict) else {}
    meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}

    suggested = None
    for k in ["suggested_weights", "suggested_params", "suggested"]:
        v = r.get(k)
        if isinstance(v, dict):
            suggested = v
            break

    effective = None
    for k in ["effective_weights", "effective_params", "effective"]:
        v = r.get(k)
        if isinstance(v, dict):
            effective = v
            break

    if not meta:
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
    if not meta:
        meta = {}
        for k in ["profile", "epsilon", "fallback_used", "fallback_reason", "reason"]:
            if k in r:
                meta[k] = r.get(k)
    return suggested, effective, meta


def _render_tuner_output(resp: dict) -> html.Div:
    suggested, effective, meta = _extract_tuner_parts(resp)
    fallback_used = bool(meta.get("fallback_used")) if isinstance(meta, dict) else False
    fallback_reason = ""
    if isinstance(meta, dict):
        for k in ["fallback_reason", "reason"]:
            if isinstance(meta.get(k), str) and meta.get(k):
                fallback_reason = str(meta.get(k))
                break

    badge = None
    if fallback_used:
        badge = html.Span(
            "FALLBACK",
            style={
                "backgroundColor": "#f39c12",
                "color": "white",
                "padding": "2px 8px",
                "borderRadius": "999px",
                "fontSize": "11px",
                "fontWeight": "bold",
                "marginLeft": "8px",
            },
        )

    def _box(title: str, payload: dict | None) -> html.Div:
        txt = json.dumps(payload or {}, indent=2, sort_keys=True, ensure_ascii=False)
        return html.Div(
            [
                html.Div(title, style={"fontWeight": "bold", "color": "#2c3e50", "marginBottom": "6px"}),
                html.Pre(txt, style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
            ],
            style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
        )

    meta_txt = json.dumps(meta or {}, indent=2, sort_keys=True, ensure_ascii=False)
    meta_box = html.Div(
        [
            html.Div(["Meta", badge] if badge else ["Meta"], style={"fontWeight": "bold", "color": "#2c3e50", "marginBottom": "6px"}),
            html.Pre(meta_txt, style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
            html.Div(f"Reason: {fallback_reason}", style={"marginTop": "6px", "color": "#7f8c8d", "fontSize": "12px"}) if fallback_reason else None,
        ],
        style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
    )

    return html.Div(
        [
            html.Div(
                [
                    _box("Suggested weights (raw)", suggested),
                    _box("Effective weights (setelah shield)", effective),
                    meta_box,
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "10px"},
            )
        ]
    )


def _build_policy_context_from_ui(
    soc_pct: Any,
    demand_total_kwh: Any,
    renewable_potential_kwh: Any,
    tariff: Any,
    emission_factor: Any,
) -> dict:
    ctx: dict[str, Any] = {}
    if isinstance(soc_pct, (int, float)):
        ctx["soc"] = max(0.0, min(1.0, float(soc_pct) / 100.0))
    if isinstance(demand_total_kwh, (int, float)):
        v = float(demand_total_kwh)
        if v >= 0:
            ctx["demand_total_kwh"] = v
    if isinstance(renewable_potential_kwh, (int, float)):
        v = float(renewable_potential_kwh)
        if v >= 0:
            ctx["renewable_potential_kwh"] = v
    if isinstance(tariff, (int, float)):
        ctx["tariff"] = float(tariff)
    if isinstance(emission_factor, (int, float)):
        ctx["emission_factor"] = float(emission_factor)
    return ctx


def _extract_policy_preview_parts(resp: dict) -> tuple[dict | None, dict | None, dict]:
    r = resp if isinstance(resp, dict) else {}
    proposed = None
    projected = None
    if isinstance(r.get("proposed_action"), dict):
        proposed = r.get("proposed_action")
    if isinstance(r.get("projected_action"), dict):
        projected = r.get("projected_action")
    if projected is None and isinstance(r.get("safe_action"), dict):
        projected = r.get("safe_action")

    meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
    if not meta:
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
    if not meta:
        meta = {}
        for k in ["projection_applied", "fallback_used", "reason", "fallback_reason"]:
            if k in r:
                meta[k] = r.get(k)
    return proposed, projected, meta


def _render_policy_preview_output(resp: dict) -> html.Div:
    proposed, projected, meta = _extract_policy_preview_parts(resp)
    projection_applied = bool(meta.get("projection_applied")) if isinstance(meta, dict) else False
    fallback_used = bool(meta.get("fallback_used")) if isinstance(meta, dict) else False
    reason = ""
    if isinstance(meta, dict):
        for k in ["fallback_reason", "reason"]:
            if isinstance(meta.get(k), str) and meta.get(k):
                reason = str(meta.get(k))
                break

    badges = []
    if projection_applied:
        badges.append(
            html.Span(
                "PROJECTION",
                style={"backgroundColor": "#2e86c1", "color": "white", "padding": "2px 8px", "borderRadius": "999px", "fontSize": "11px", "fontWeight": "bold"},
            )
        )
    if fallback_used:
        badges.append(
            html.Span(
                "FALLBACK",
                style={"backgroundColor": "#f39c12", "color": "white", "padding": "2px 8px", "borderRadius": "999px", "fontSize": "11px", "fontWeight": "bold"},
            )
        )

    def _box(title: str, payload: dict | None) -> html.Div:
        txt = json.dumps(payload or {}, indent=2, sort_keys=True, ensure_ascii=False)
        return html.Div(
            [
                html.Div(title, style={"fontWeight": "bold", "color": "#2c3e50", "marginBottom": "6px"}),
                html.Pre(txt, style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
            ],
            style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
        )

    header = html.Div(
        [
            html.Div("Preview", style={"fontWeight": "bold", "color": "#2c3e50"}),
            html.Div(badges, style={"display": "flex", "gap": "8px"}) if badges else None,
        ],
        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "8px"},
    )
    reason_el = html.Div(f"Reason: {reason}", style={"marginTop": "8px", "color": "#7f8c8d", "fontSize": "12px"}) if reason else None
    return html.Div(
        [
            header,
            html.Div([_box("proposed_action", proposed), _box("projected_action (safe)", projected)], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "10px"}),
            reason_el,
        ]
    )


def _extract_policy_snapshot(payload: dict) -> dict | None:
    d = payload if isinstance(payload, dict) else {}
    job = d.get("job") if isinstance(d.get("job"), dict) else None
    if isinstance(job, dict) and isinstance(job.get("policy_snapshot"), dict):
        return job.get("policy_snapshot")
    snap = d.get("policy_snapshot")
    if isinstance(snap, dict):
        return snap
    audit = d.get("audit") if isinstance(d.get("audit"), dict) else {}
    snap = audit.get("policy_snapshot")
    if isinstance(snap, dict):
        return snap
    meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
    snap = meta.get("policy_snapshot")
    if isinstance(snap, dict):
        return snap
    recs = d.get("records") if isinstance(d.get("records"), list) else []
    if recs and isinstance(recs[0], dict) and isinstance(recs[0].get("policy_snapshot"), dict):
        return recs[0].get("policy_snapshot")
    return None


def _extract_tuner_snapshot(payload: dict) -> dict | None:
    d = payload if isinstance(payload, dict) else {}
    job = d.get("job") if isinstance(d.get("job"), dict) else None
    if isinstance(job, dict) and isinstance(job.get("tuner_snapshot"), dict):
        return job.get("tuner_snapshot")
    snap = d.get("tuner_snapshot")
    if isinstance(snap, dict):
        return snap
    audit = d.get("audit") if isinstance(d.get("audit"), dict) else {}
    snap = audit.get("tuner_snapshot")
    if isinstance(snap, dict):
        return snap
    meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
    snap = meta.get("tuner_snapshot")
    if isinstance(snap, dict):
        return snap
    recs = d.get("records") if isinstance(d.get("records"), list) else []
    if recs and isinstance(recs[0], dict) and isinstance(recs[0].get("tuner_snapshot"), dict):
        return recs[0].get("tuner_snapshot")
    return None


def _render_policy_snapshot_audit(payload: dict) -> html.Div:
    snap = _extract_policy_snapshot(payload)
    tuner_snap = _extract_tuner_snapshot(payload)
    if (not isinstance(snap, dict) or not snap) and (not isinstance(tuner_snap, dict) or not tuner_snap):
        return html.Div("policy_snapshot/tuner_snapshot: (tidak tersedia)", style={"color": "#7f8c8d"})

    blocks: list[html.Div] = []
    if isinstance(snap, dict) and snap:
        proposed, projected, meta = _extract_policy_preview_parts(snap)
        projection_applied = bool(meta.get("projection_applied")) if isinstance(meta, dict) else False
        fallback_used = bool(meta.get("fallback_used")) if isinstance(meta, dict) else False
        badges = []
        if projection_applied:
            badges.append(html.Span("PROJECTION", style={"backgroundColor": "#2e86c1", "color": "white", "padding": "2px 8px", "borderRadius": "999px", "fontSize": "11px", "fontWeight": "bold"}))
        if fallback_used:
            badges.append(html.Span("FALLBACK", style={"backgroundColor": "#f39c12", "color": "white", "padding": "2px 8px", "borderRadius": "999px", "fontSize": "11px", "fontWeight": "bold"}))
        txt = json.dumps(snap, indent=2, sort_keys=True, ensure_ascii=False)
        blocks.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Audit: policy_snapshot", style={"fontWeight": "bold", "color": "#2c3e50"}),
                            html.Div(badges, style={"display": "flex", "gap": "8px"}) if badges else None,
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("proposed_action", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                    html.Pre(json.dumps(proposed or {}, indent=2, sort_keys=True, ensure_ascii=False), style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
                                ],
                                style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
                            ),
                            html.Div(
                                [
                                    html.Div("projected_action", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                    html.Pre(json.dumps(projected or {}, indent=2, sort_keys=True, ensure_ascii=False), style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
                                ],
                                style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
                            ),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "10px", "marginTop": "8px"},
                    ),
                    html.Details(
                        [
                            html.Summary("Raw policy_snapshot (copy)", style={"cursor": "pointer", "marginTop": "8px"}),
                            dcc.Textarea(value=txt, style={"width": "100%", "height": "140px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"}),
                        ],
                        open=False,
                        style={"marginTop": "6px"},
                    ),
                ],
                style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
            )
        )

    if isinstance(tuner_snap, dict) and tuner_snap:
        txt = json.dumps(tuner_snap, indent=2, sort_keys=True, ensure_ascii=False)
        blocks.append(
            html.Div(
                [
                    html.Div("Audit: tuner_snapshot", style={"fontWeight": "bold", "color": "#2c3e50", "marginBottom": "6px"}),
                    html.Pre(txt, style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
                ],
                style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
            )
        )

    return html.Div(blocks, style={"display": "grid", "gap": "10px"})


def register_bms_callbacks(app):
    """
    Registers callbacks for the BMS Tab.
    """
    
    # 1. Handle Control Buttons
    @app.callback(
        Output('bms-control-feedback', 'children'),
        [Input('btn-start-charge', 'n_clicks'),
         Input('btn-start-discharge', 'n_clicks'),
         Input('btn-stop-system', 'n_clicks')],
        [State("backend-readiness-store", "data")],
    )
    def control_bms(btn_charge, btn_discharge, btn_stop, readiness):
        """
        Handles BMS control actions: Charge, Discharge, Stop.
        """
        try:
            base_url = effective_base_url(readiness if isinstance(readiness, dict) else {})
            if _external_bms_mode(base_url=base_url):
                return "Kontrol BMS nonaktif (SOC mengikuti data Monitoring/Backend)."
            ctx = callback_context
            if not ctx.triggered:
                return ""
                
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'btn-start-charge':
                bms_service.update(action='charge')
                return "✅ Sistem Pengisian Dimulai."
            elif button_id == 'btn-start-discharge':
                bms_service.update(action='discharge')
                return "✅ Sistem Pengosongan Dimulai."
            elif button_id == 'btn-stop-system':
                bms_service.update(action='stop')
                return "🛑 Sistem Dihentikan."
                
            return ""
        except Exception as e:
            return error_banner("BMS", "Gagal menjalankan aksi kontrol BMS", str(e))

    @app.callback(
        [Output("btn-start-charge", "disabled"), Output("btn-start-discharge", "disabled"), Output("btn-stop-system", "disabled")],
        [Input("backend-readiness-store", "data"), Input("bms-interval", "n_intervals")],
    )
    def update_bms_controls_disabled(_readiness, _n):
        base_url = str((_readiness or {}).get("base_url") or "").rstrip("/") if isinstance(_readiness, dict) else None
        disabled = bool(_external_bms_mode(base_url=base_url))
        return disabled, disabled, disabled

    # 2. Update Live Data (Gauge, Text, Graphs)
    @app.callback(
        [Output('bms-soc-gauge', 'figure'),
         Output('bms-voltage-text', 'children'),
         Output('bms-current-text', 'children'),
         Output('bms-temp-text', 'children'),
         Output('bms-health-text', 'children'),
         Output('bms-live-graph', 'figure')],
        [Input('backend-readiness-store', 'data'),
         Input('bms-interval', 'n_intervals')]
    )
    def update_bms_live(readiness, n):
        """
        Updates BMS dashboard components with live simulation data.
        """
        try:
            base_url = str((readiness or {}).get("base_url") or "").rstrip("/") if isinstance(readiness, dict) else None
            data = bms_service.update()
            batt = _monitoring_battery_state(base_url=base_url)
            if isinstance(batt, dict) and str(batt.get("source") or "") in {"live", "backend", "backend_state"}:
                soc_val = _soc_percent_from_batt(batt)
                status = str(batt.get("status") or "Idle")
                soc_color = "#2ecc71" if 20 <= soc_val <= 80 else "#e74c3c"

                soc_fig = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=soc_val,
                        number={"suffix": "%"},
                        gauge={
                            "axis": {"range": [None, 100]},
                            "bar": {"color": soc_color},
                            "steps": [
                                {"range": [0, 20], "color": "#e74c3c"},
                                {"range": [20, 80], "color": "#2ecc71"},
                                {"range": [80, 100], "color": "#e74c3c"},
                            ],
                        },
                    )
                )
                soc_fig.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=20))

                max_v = float(getattr(bms_service, "max_voltage", 54.6))
                min_v = float(getattr(bms_service, "min_voltage", 42.0))
                open_circuit_voltage = min_v + (max_v - min_v) * (soc_val / 100.0)
                current = 0.0
                if status == "Charging":
                    current = float(getattr(bms_service, "charging_current", 20.0))
                elif status == "Discharging":
                    current = float(getattr(bms_service, "discharging_current", -15.0))
                volt_text = f"{open_circuit_voltage:.2f} V"
                curr_text = f"{current:.2f} A"
                temp_text = f"{float(getattr(bms_service, 'ambient_temp', 25.0)):.1f} °C"
                health_text = "Normal" if 20 <= soc_val <= 80 else "Warning"

                t_now = f"{int(n or 0):02d}"
                xs = [t_now]
                socs = [soc_val]
                volts = [open_circuit_voltage]
                temps = [float(getattr(bms_service, 'ambient_temp', 25.0))]

                graph_fig = go.Figure()
                graph_fig.add_trace(go.Scatter(x=xs, y=socs, name="SOC (%)", mode="lines+markers", line=dict(color="#2ecc71", width=3)))
                graph_fig.add_trace(go.Scatter(x=xs, y=volts, name="Voltage (V)", mode="lines+markers", line=dict(color="#3498db"), yaxis="y2"))
                graph_fig.add_trace(go.Scatter(x=xs, y=temps, name="Temp (°C)", mode="lines+markers", line=dict(color="#e74c3c", dash="dot"), yaxis="y2"))
                graph_fig.update_layout(
                    title=f"Monitoring Real-time (SOC, Voltage, Temp) — source={batt.get('source')}",
                    xaxis_title="Waktu",
                    yaxis=dict(title="SOC (%)", range=[0, 100]),
                    yaxis2=dict(title="Voltage / Temp", overlaying="y", side="right"),
                    legend=dict(x=0, y=1.1, orientation="h"),
                    margin=dict(l=50, r=50, t=50, b=50),
                    height=350,
                )
                return soc_fig, volt_text, curr_text, temp_text, health_text, graph_fig

            data = bms_service.update()
            soc_val = data['soc']
            soc_color = "#2ecc71" if 20 <= soc_val <= 80 else "#e74c3c"
            
            soc_fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = soc_val,
                number = {'suffix': "%"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': soc_color},
                    'steps': [
                        {'range': [0, 20], 'color': "#e74c3c"},
                        {'range': [20, 80], 'color': "#2ecc71"},
                        {'range': [80, 100], 'color': "#e74c3c"}
                    ]
                }
            ))
            soc_fig.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=20))
            
            volt_text = f"{data['voltage']:.2f} V"
            curr_text = f"{data['current']:.2f} A"
            temp_text = f"{data['temperature']:.1f} °C"
            health_text = data['health']
            
            history = bms_service.get_history()
            
            graph_fig = go.Figure()
            
            graph_fig.add_trace(go.Scatter(
                x=history['timestamp'], y=history['soc'],
                name='SOC (%)', mode='lines', line=dict(color='#2ecc71', width=3)
            ))
            
            graph_fig.add_trace(go.Scatter(
                x=history['timestamp'], y=history['voltage'],
                name='Voltage (V)', mode='lines', line=dict(color='#3498db'),
                yaxis='y2'
            ))
            
            graph_fig.add_trace(go.Scatter(
                x=history['timestamp'], y=history['temperature'],
                name='Temp (°C)', mode='lines', line=dict(color='#e74c3c', dash='dot'),
                yaxis='y2'
            ))

            graph_fig.update_layout(
                title="Monitoring Real-time (SOC, Voltage, Temp)",
                xaxis_title="Waktu",
                yaxis=dict(title="SOC (%)", range=[0, 100]),
                yaxis2=dict(
                    title="Voltage / Temp",
                    overlaying='y',
                    side='right'
                ),
                legend=dict(x=0, y=1.1, orientation='h'),
                margin=dict(l=50, r=50, t=50, b=50),
                height=350
            )
            
            return soc_fig, volt_text, curr_text, temp_text, health_text, graph_fig
        except Exception as e:
            fig = error_figure("BMS", str(e))
            return fig, "N/A", "N/A", "N/A", error_text("BMS", str(e)), fig

    @app.callback(
        [
            Output("bms-rl-status", "children"),
            Output("bms-rl-kpi", "children"),
            Output("bms-policy-audit", "children"),
            Output("bms-rl-table", "columns"),
            Output("bms-rl-table", "data"),
            Output("bms-rl-raw", "value"),
            Output("bms-rl-payload", "value"),
            Output("bms-rl-stream-id", "value"),
        ],
        [
            Input("bms-rl-run-btn", "n_clicks"),
            Input("bms-rl-load-btn", "n_clicks"),
            Input("bms-rl-export-mode", "value"),
        ],
        [
            State("backend-readiness-store", "data"),
            State("bms-rl-stream-id", "value"),
            State("bms-rl-endpoint-path", "value"),
            State("bms-rl-dispatch-mode", "value"),
            State("bms-rl-payload", "value"),
            State("bms-tuner-enable", "value"),
            State("bms-tuner-mode", "value"),
            State("bms-policy-enable", "value"),
        ],
        prevent_initial_call=True,
    )
    def run_bms_rl_dispatch(_n_run, _n_load, export_mode, readiness, stream_id, endpoint_path, dispatch_mode, payload_text, tuner_enable, tuner_mode, policy_enable):
        base_url = effective_base_url(readiness if isinstance(readiness, dict) else {})
        sid_in = str(stream_id or "").strip() or "proof-rl-1"
        mode = str(dispatch_mode or "").strip().lower() or "batch"
        default_path = "/ai/optimizer/dispatch/batch" if mode == "batch" else "/ai/optimizer/dispatch"
        path = str(endpoint_path or "").strip() or default_path
        if not path.startswith("/"):
            path = "/" + path
        url = f"{base_url}{path}" if base_url else ""

        trig = ""
        try:
            if callback_context and callback_context.triggered:
                trig = str(callback_context.triggered[0].get("prop_id") or "")
        except Exception:
            trig = ""

        sid = sid_in
        if trig.startswith("bms-rl-run-btn"):
            now = datetime.datetime.now(datetime.timezone.utc)
            stamp = now.strftime("%Y%m%d-%H%M%S")
            ms = int(now.microsecond / 1000)
            sid = f"proof-rl-{stamp}-{ms:03d}"

        parsed_payload = None
        if isinstance(payload_text, str) and payload_text.strip():
            try:
                parsed_payload = json.loads(payload_text)
            except Exception:
                parsed_payload = None

        if not isinstance(parsed_payload, dict):
            parsed_payload = {}

        if trig.startswith("bms-rl-export-mode"):
            allow_export = str(export_mode or "").strip().lower() == "export"
            cfg = parsed_payload.get("optimizer_config") if isinstance(parsed_payload.get("optimizer_config"), dict) else {}
            cfg2 = dict(cfg)
            cfg2["allow_grid_export"] = bool(allow_export)
            parsed_payload["optimizer_config"] = cfg2
            payload_text2 = json.dumps(parsed_payload, indent=2, sort_keys=True, ensure_ascii=False)
            return no_update, no_update, no_update, no_update, no_update, no_update, payload_text2, no_update

        def _openapi_paths(base: str) -> tuple[dict[str, Any] | None, str | None]:
            try:
                resp = requests.get(f"{base}/openapi.json", timeout=(2.5, 5.0))
                if int(resp.status_code) != 200:
                    return None, f"http_{resp.status_code}"
                js = resp.json()
                paths = js.get("paths") if isinstance(js, dict) else None
                return (paths if isinstance(paths, dict) else {}), None
            except Exception as e:
                return None, str(e)[:200]

        def _has_dispatch_endpoint(base: str, p: str) -> tuple[bool, str | None]:
            paths, err = _openapi_paths(base)
            if err:
                return True, None
            if paths is None:
                return True, None
            return (p in paths), None

        parsed_payload = _build_rl_dispatch_payload(base_url=base_url, stream_id=sid, existing=parsed_payload, mode=mode)

        tuner_enabled = isinstance(tuner_enable, list) and ("on" in tuner_enable)
        tuner_note = ""
        if tuner_enabled and trig.startswith("bms-rl-run-btn"):
            try:
                ctx = _tuner_context_from_dispatch_payload(parsed_payload)
                resp_tuner = suggest_tuner(ctx, readiness=readiness if isinstance(readiness, dict) else {}, mode=tuner_mode)
                _suggested, effective_params, _meta = _extract_tuner_parts(resp_tuner)
                if isinstance(effective_params, dict) and effective_params:
                    parsed_payload["effective_params"] = effective_params
                    cfg = parsed_payload.get("optimizer_config") if isinstance(parsed_payload.get("optimizer_config"), dict) else {}
                    if isinstance(cfg, dict) and isinstance(effective_params.get("weights"), dict):
                        cfg2 = dict(cfg)
                        w0 = cfg2.get("weights") if isinstance(cfg2.get("weights"), dict) else {}
                        cfg2["weights"] = {**dict(w0), **dict(effective_params.get("weights") or {})}
                        parsed_payload["optimizer_config"] = cfg2
            except Exception as e:
                tuner_note = f"DRL Tuner gagal: {str(e)[:200]} (fallback tanpa tuner)"

        policy_enabled = isinstance(policy_enable, list) and ("on" in policy_enable)
        if policy_enabled and trig.startswith("bms-rl-run-btn"):
            cfg = parsed_payload.get("optimizer_config") if isinstance(parsed_payload.get("optimizer_config"), dict) else {}
            cfg2 = dict(cfg) if isinstance(cfg, dict) else {}
            cfg2["policy_enabled"] = True
            parsed_payload["optimizer_config"] = cfg2

        payload_text = json.dumps(parsed_payload, indent=2, sort_keys=True, ensure_ascii=False)

        if not url:
            return "base_url tidak tersedia (backend belum ready).", "", "", [], [], "{}", payload_text, sid

        def _poll_dashboard_dispatch(base: str, stream: str) -> tuple[dict | None, str]:
            dash_url = f"{base}/dashboard/dispatch?stream_id={stream}"
            last = ""
            last_json: dict[str, Any] | None = None
            for _ in range(20):
                try:
                    r = requests.get(dash_url, timeout=(2.0, 6.0))
                    last = f"HTTP {r.status_code}"
                    if int(r.status_code) == 200:
                        js = r.json()
                        if isinstance(js, dict):
                            last_json = js
                            recs = js.get("records") if isinstance(js.get("records"), list) else []
                            if recs:
                                return js, f"GET /dashboard/dispatch?stream_id={stream} -> HTTP 200"
                except Exception as e:
                    last = str(e)[:200]
                time.sleep(0.5)
            if isinstance(last_json, dict):
                return last_json, f"GET /dashboard/dispatch?stream_id={stream} -> HTTP 200 (empty)"
            return None, f"GET /dashboard/dispatch?stream_id={stream} -> {last or 'no_response'}"

        def _poll_job_status(base: str, job_id: str) -> tuple[dict | None, str]:
            jid = str(job_id or "").strip()
            if not jid:
                return None, "job_id kosong"
            job_url = f"{base}/ai/optimizer/jobs/{jid}"
            last = ""
            last_json: dict[str, Any] | None = None
            for _ in range(20):
                try:
                    r = requests.get(job_url, timeout=(2.0, 6.0))
                    last = f"HTTP {r.status_code}"
                    if int(r.status_code) == 200:
                        js = r.json()
                        if isinstance(js, dict):
                            last_json = js
                            st = str(js.get("status") or js.get("state") or "").strip().lower()
                            if st in {"done", "completed", "succeeded", "success", "failed", "error", "cancelled", "canceled"}:
                                return js, f"GET /ai/optimizer/jobs/{jid} -> HTTP 200 ({st})"
                            return js, f"GET /ai/optimizer/jobs/{jid} -> HTTP 200"
                    if int(r.status_code) in {404, 410}:
                        break
                except Exception as e:
                    last = str(e)[:200]
                time.sleep(0.5)
            if isinstance(last_json, dict):
                return last_json, f"GET /ai/optimizer/jobs/{jid} -> HTTP 200 (last)"
            return None, f"GET /ai/optimizer/jobs/{jid} -> {last or 'no_response'}"

        try:
            if trig.startswith("bms-rl-load-btn"):
                polled, status2 = _poll_dashboard_dispatch(base_url, sid)
                status = f"{status2} (base_url={base_url})"
                data = polled if isinstance(polled, dict) else {}
                recs = data.get("records") if isinstance(data.get("records"), list) else []
                if not recs:
                    raw = json.dumps({"ok": False, "url": f"{base_url}/dashboard/dispatch?stream_id={sid}", "error": "empty_or_not_ready"}, indent=2, sort_keys=True, ensure_ascii=False)
                    raw2 = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) if data else raw
                    return status, html.Div("Data dispatch belum siap / kosong. Coba klik Load Dashboard Dispatch lagi setelah beberapa detik.", style={"color": "#c0392b", "fontWeight": "bold"}), "", [], [], raw2, payload_text, sid
                kpi, rows = _summarize_dashboard_dispatch(data)
            else:
                ok_ep, _ = _has_dispatch_endpoint(base_url, path)
                if not ok_ep:
                    msg = "Backend yang sedang berjalan tidak menyediakan endpoint /ai/optimizer/dispatch. Pastikan backend port 8008 dijalankan dari build terbaru dan restart backend."
                    raw = json.dumps({"ok": False, "error": "endpoint_missing", "required_path": "/ai/optimizer/dispatch", "base_url": base_url}, indent=2, sort_keys=True, ensure_ascii=False)
                    return msg, html.Div(msg, style={"color": "#c0392b", "fontWeight": "bold"}), "", [], [], raw, payload_text, sid

                job = None
                job_id = None
                resp = requests.post(url, json=parsed_payload, timeout=(2.5, 15.0))
                status = f"POST {path} -> HTTP {resp.status_code} (base_url={base_url})"
                if tuner_note:
                    status = f"{tuner_note} | {status}"
                if int(resp.status_code) not in {200, 202}:
                    body = (resp.text or "").strip()
                    if int(resp.status_code) == 400 and "unexpected keyword argument" in body and "OptimizerConfig" in body:
                        msg = "Backend menolak optimizer_config (400): ada field yang belum didukung. Pastikan backend port 8008 sudah di-update dan di-restart."
                        raw = json.dumps({"ok": False, "http_status": int(resp.status_code), "url": url, "error": msg, "error_body": body[:2000]}, indent=2, sort_keys=True, ensure_ascii=False)
                        return msg, html.Div(msg, style={"color": "#c0392b", "fontWeight": "bold"}), "", [], [], raw, payload_text, sid
                    if int(resp.status_code) == 404:
                        msg = "Backend yang sedang berjalan tidak menyediakan endpoint /ai/optimizer/dispatch. Pastikan backend port 8008 dijalankan dari build terbaru dan restart backend."
                        raw = json.dumps({"ok": False, "http_status": int(resp.status_code), "url": url, "error": msg, "error_body": body[:2000]}, indent=2, sort_keys=True, ensure_ascii=False)
                        return msg, html.Div(msg, style={"color": "#c0392b", "fontWeight": "bold"}), "", [], [], raw, payload_text, sid
                    raw = json.dumps(
                        {"ok": False, "http_status": int(resp.status_code), "url": url, "error_body": body[:2000]},
                        indent=2,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    return status, html.Div("Backend mengembalikan error.", style={"color": "#c0392b", "fontWeight": "bold"}), "", [], [], raw, payload_text, sid
                ack = None
                if int(resp.status_code) == 202:
                    try:
                        ack = resp.json()
                    except Exception:
                        ack = None
                    if isinstance(ack, dict):
                        job_id = ack.get("job_id") or ack.get("jobId") or ack.get("id")
                    if job_id is not None:
                        job, job_status = _poll_job_status(base_url, str(job_id))
                        status = f"{status} | {job_status}"
                    if isinstance(ack, dict):
                        data = dict(ack)
                    elif ack is not None:
                        data = {"data": ack}
                    else:
                        data = {}
                    if isinstance(data, dict) and job is not None:
                        data["job_id"] = str(job_id)
                        data["job"] = job
                else:
                    data = resp.json() if int(resp.status_code) == 200 else {}
                polled, status2 = _poll_dashboard_dispatch(base_url, sid)
                if isinstance(polled, dict) and isinstance(polled.get("records"), list) and polled.get("records"):
                    status = f"{status} | {status2}"
                    data = polled
                    if job is not None and isinstance(data, dict):
                        data["job_id"] = str(job_id)
                        data["job"] = job
                    kpi, rows = _summarize_dashboard_dispatch(data)
                else:
                    if isinstance(polled, dict):
                        status = f"{status} | {status2}"
                        data = polled
                        if job is not None and isinstance(data, dict):
                            data["job_id"] = str(job_id)
                            data["job"] = job
                        kpi, rows = {"info": "Data dispatch belum siap / kosong. Coba klik Load Dashboard Dispatch lagi setelah beberapa detik; jika tetap kosong, cek log backend untuk stream_id ini."}, []
                    else:
                        kpi, rows = _summarize_dispatch_result(data if isinstance(data, dict) else {})
        except Exception as e:
            raw = json.dumps({"ok": False, "url": url, "error": str(e)[:400]}, indent=2, sort_keys=True, ensure_ascii=False)
            return f"Gagal memanggil backend (base_url={base_url})", html.Div(str(e), style={"color": "#c0392b"}), "", [], [], raw, payload_text, sid

        keys_priority = ["timestamp", "grid_import_kwh", "soc", "cost", "emission", "unmet_kwh", "battery_charge_kwh", "battery_discharge_kwh", "reward", "rl_action_level", "rl_biofuel_on"]
        seen = set()
        cols = []
        for k in keys_priority:
            if any(isinstance(r, dict) and k in r for r in rows):
                seen.add(k)
                cols.append({"name": k, "id": k})
        for r in rows[:50]:
            for k in sorted(r.keys()):
                if k in seen:
                    continue
                if len(cols) >= 18:
                    break
                seen.add(k)
                cols.append({"name": k, "id": k})

        preview_rows = rows[:50]
        kpi_items = []
        if isinstance(kpi, dict) and kpi:
            for k in sorted(kpi.keys()):
                kpi_items.append(html.Div(f"{k} = {kpi.get(k)}", style={"fontFamily": "monospace", "fontSize": "12px"}))
        kpi_box = html.Div(
            [
                html.Div("KPI (ringkas)", style={"fontWeight": "bold", "color": "#2c3e50", "marginBottom": "6px"}),
                html.Div(kpi_items or [html.Div("KPI tidak tersedia.", style={"color": "#7f8c8d"})]),
            ],
            style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white"},
        )

        raw_text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) if isinstance(data, (dict, list)) else json.dumps({"response": str(data)}, indent=2, ensure_ascii=False)
        policy_audit = _render_policy_snapshot_audit(data if isinstance(data, dict) else {})
        return status, kpi_box, policy_audit, cols, preview_rows, raw_text, payload_text, sid

    @app.callback(
        [Output("bms-tuner-output", "children"), Output("bms-tuner-raw", "value")],
        [Input("bms-tuner-preview-btn", "n_clicks")],
        [
            State("backend-readiness-store", "data"),
            State("bms-rl-stream-id", "value"),
            State("bms-rl-dispatch-mode", "value"),
            State("bms-rl-payload", "value"),
            State("bms-tuner-enable", "value"),
            State("bms-tuner-mode", "value"),
        ],
        prevent_initial_call=True,
    )
    def preview_bms_drl_tuner(_n, readiness, stream_id, dispatch_mode, payload_text, tuner_enable, tuner_mode):
        enabled = isinstance(tuner_enable, list) and ("on" in tuner_enable)
        if not enabled:
            msg = "DRL Tuner masih OFF. Aktifkan toggle lalu klik Preview Suggestion."
            return html.Div(msg, style={"color": "#7f8c8d", "fontWeight": "bold"}), "{}"

        base_url = effective_base_url(readiness if isinstance(readiness, dict) else {})
        sid = str(stream_id or "").strip() or "proof-rl-1"
        mode = str(dispatch_mode or "").strip().lower() or "batch"

        parsed_payload = None
        if isinstance(payload_text, str) and payload_text.strip():
            try:
                parsed_payload = json.loads(payload_text)
            except Exception:
                parsed_payload = None
        if not isinstance(parsed_payload, dict):
            parsed_payload = {}

        built = _build_rl_dispatch_payload(base_url=base_url, stream_id=sid, existing=parsed_payload, mode=mode)
        ctx = _tuner_context_from_dispatch_payload(built)
        try:
            resp_tuner = suggest_tuner(ctx, readiness=readiness if isinstance(readiness, dict) else {}, mode=tuner_mode)
            raw = json.dumps(resp_tuner, indent=2, sort_keys=True, ensure_ascii=False)
            return _render_tuner_output(resp_tuner), raw
        except Exception as e:
            raw = json.dumps({"ok": False, "error": str(e)[:400], "base_url": base_url, "context": ctx}, indent=2, sort_keys=True, ensure_ascii=False)
            return html.Div(str(e), style={"color": "#c0392b", "fontWeight": "bold"}), raw

    @app.callback(
        [Output("bms-policy-output", "children"), Output("bms-policy-raw", "value")],
        [Input("bms-policy-preview-btn", "n_clicks")],
        [
            State("backend-readiness-store", "data"),
            State("bms-policy-enable", "value"),
            State("bms-policy-soc", "value"),
            State("bms-policy-demand", "value"),
            State("bms-policy-renewable", "value"),
            State("bms-policy-tariff", "value"),
            State("bms-policy-emission", "value"),
        ],
        prevent_initial_call=True,
    )
    def preview_bms_policy_proposer(_n, readiness, policy_enable, soc_pct, demand_total_kwh, renewable_potential_kwh, tariff, emission_factor):
        enabled = isinstance(policy_enable, list) and ("on" in policy_enable)
        if not enabled:
            msg = "Policy Proposer masih OFF. Aktifkan toggle lalu klik Preview Action."
            return html.Div(msg, style={"color": "#7f8c8d", "fontWeight": "bold"}), "{}"

        ctx = _build_policy_context_from_ui(soc_pct, demand_total_kwh, renewable_potential_kwh, tariff, emission_factor)
        try:
            resp_pol = propose_policy_action(ctx, readiness=readiness if isinstance(readiness, dict) else {})
            raw = json.dumps(resp_pol, indent=2, sort_keys=True, ensure_ascii=False)
            return _render_policy_preview_output(resp_pol), raw
        except Exception as e:
            base_url = effective_base_url(readiness if isinstance(readiness, dict) else {})
            raw = json.dumps({"ok": False, "error": str(e)[:400], "base_url": base_url, "context": ctx}, indent=2, sort_keys=True, ensure_ascii=False)
            return html.Div(str(e), style={"color": "#c0392b", "fontWeight": "bold"}), raw

    @app.callback(
        Output("bms-rl-endpoint-path", "value"),
        Input("bms-rl-dispatch-mode", "value"),
    )
    def set_bms_rl_dispatch_mode(dispatch_mode):
        mode = str(dispatch_mode or "").strip().lower() or "batch"
        return "/ai/optimizer/dispatch/batch" if mode == "batch" else "/ai/optimizer/dispatch"
