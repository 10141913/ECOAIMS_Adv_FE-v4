import json
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException, Query

from ecoaims_backend.precooling.config_service import (
    apply_settings,
    fallback_params,
    get_active_settings,
    get_default_settings,
    get_settings_bundle,
    merge_simulate_payload,
    reset_settings,
    save_settings,
    settings_snapshot_for_ui,
    validate_settings,
)
from ecoaims_backend.precooling.engine import run_precooling_engine
from ecoaims_backend.precooling.fallback import fallback_status
from ecoaims_backend.precooling.storage import now_iso, store


router = APIRouter(prefix="/api/precooling", tags=["precooling"])


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _zone(zone: Optional[str], payload: Optional[Dict[str, Any]] = None) -> str:
    if isinstance(zone, str) and zone:
        return zone
    if isinstance(payload, dict):
        z = payload.get("zone")
        if isinstance(z, str) and z:
            return z
    return "zone_a"


def _ensure_initialized(zone: str) -> None:
    st = store.get(zone)
    cfg = get_active_settings()
    if st.fallback_active:
        st.status = {**(st.status or {}), **fallback_status(zone, fallback_params(cfg)), "active_zones": zone}
        return
    if st.status and st.schedule and st.kpi and st.scenarios:
        return
    merged, _ = merge_simulate_payload({"zone": zone}, cfg)
    result, err = run_precooling_engine(merged, zone=zone, mode=st.mode, fallback_active=st.fallback_active, settings=cfg)
    if err or not isinstance(result, dict):
        return
    st.status = result.get("status", st.status)
    st.schedule = result.get("schedule", st.schedule)
    st.kpi = result.get("kpi", st.kpi)
    st.scenarios = result.get("scenarios", st.scenarios)
    st.last_simulation = result
    store.append_audit(
        zone,
        {
            "timestamp": now_iso(),
            "action": "engine_initialized",
            "actor": "system",
            "scenario": "default",
            "result": "SUCCESS",
            "note": "Auto-init on first load",
        },
    )
    store.touch(zone)


@router.get("/zones")
def api_zones():
    zones = [
        {"zone_id": "zone_a", "label": "Zone A"},
        {"zone_id": "zone_b", "label": "Zone B"},
        {"zone_id": "zone_c", "label": "Zone C"},
    ]
    return {"zones": zones, "default": "zone_a"}


@router.get("/status")
def api_status(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    if not st.status:
        st.status = {
            "status_today": "Unknown",
            "active_zones": z,
            "start_time": "-",
            "end_time": "-",
            "duration": "-",
            "target_temperature": "-",
            "target_rh": "-",
            "recommended_energy_source": "-",
            "optimization_objective": "-",
            "confidence_score": "-",
            "comfort_risk": "-",
            "constraint_status": "-",
            "strategy_type": "Monitoring",
            "explainability": ["Status precooling belum tersedia"],
        }
    cfg = get_active_settings()
    if st.fallback_active:
        st.status = {**st.status, **fallback_status(z, fallback_params(cfg)), "active_zones": z}
    return {
        "zone": z,
        "mode": st.mode,
        "fallback_active": st.fallback_active,
        "last_update": st.last_update,
        "data_health": "OK",
        "settings_snapshot": settings_snapshot_for_ui(cfg),
        **(st.status or {}),
    }


@router.get("/schedule")
def api_schedule(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    return st.schedule or {"zone": z, "generated_at": st.last_update, "slots": []}


@router.get("/scenarios")
def api_scenarios(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    return st.scenarios or {"zone": z, "generated_at": st.last_update, "scenarios": [], "comparison": []}


@router.get("/kpi")
def api_kpi(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    return st.kpi or {"zone": z, "generated_at": st.last_update}


@router.get("/alerts")
def api_alerts(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    return {"zone": z, "generated_at": st.last_update, "alerts": st.alerts}


@router.get("/audit")
def api_audit(zone: Optional[str] = Query(default=None)):
    z = _zone(zone)
    st = store.get(z)
    _ensure_initialized(z)
    store.touch(z)
    return {"zone": z, "generated_at": st.last_update, "audit": st.audit}


@router.post("/simulate")
def api_simulate(payload: Dict[str, Any] = Body(default_factory=dict)):
    p = _as_dict(payload)
    z = _zone(None, p)
    st = store.get(z)
    cfg = get_active_settings()
    merged, notes = merge_simulate_payload(p, cfg)
    result, err = run_precooling_engine(merged, zone=z, mode=st.mode, fallback_active=st.fallback_active, settings=cfg)
    if err:
        store.append_audit(
            z,
            {
                "timestamp": now_iso(),
                "action": "simulation_requested",
                "actor": "user",
                "scenario": p.get("scenario_id", "-"),
                "result": "FAILED",
                "note": err,
            },
        )
        raise HTTPException(status_code=400, detail=err)
    st.last_simulation = result or {}
    if isinstance(result, dict):
        st.status = result.get("status", st.status)
        st.schedule = result.get("schedule", st.schedule)
        st.kpi = result.get("kpi", st.kpi)
        st.scenarios = result.get("scenarios", st.scenarios)
    store.append_audit(
        z,
        {
            "timestamp": now_iso(),
            "action": "simulation_requested",
            "actor": "user",
            "scenario": p.get("scenario_id", "builder"),
            "result": "SUCCESS",
            "note": "Simulation executed",
        },
    )
    store.touch(z)
    return {**(result or {}), "effective_payload_notes": notes, "settings_snapshot": settings_snapshot_for_ui(cfg)}


@router.post("/apply")
def api_apply(payload: Dict[str, Any] = Body(default_factory=dict)):
    p = _as_dict(payload)
    z = _zone(None, p)
    st = store.get(z)
    action = str(p.get("action") or "apply_recommendation")

    if action == "force_fallback":
        cfg = get_active_settings()
        fb = fallback_params(cfg)
        st.fallback_active = True
        st.mode = "fallback"
        st.status = {**(st.status or {}), **fallback_status(z, fb), "active_zones": z}
        store.append_alert(
            z,
            {"timestamp": now_iso(), "severity": "HIGH", "type": "FALLBACK", "zone": z, "description": "Fallback diaktifkan oleh user", "action": "System switched to fallback"},
        )
        store.append_audit(
            z,
            {"timestamp": now_iso(), "action": "fallback_activated", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Force fallback"},
        )
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "mode": st.mode, "fallback_active": True, "timestamp": st.last_update}

    if action == "switch_mode":
        mode = str(p.get("mode") or "advisory")
        st.mode = mode
        store.append_audit(z, {"timestamp": now_iso(), "action": "mode_changed", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": f"mode={mode}"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "mode": st.mode, "fallback_active": st.fallback_active, "timestamp": st.last_update}

    if action == "apply_recommendation":
        candidate = _as_dict(p.get("candidate"))
        st.fallback_active = False
        if st.mode == "fallback":
            st.mode = "auto"
        store.append_audit(
            z,
            {"timestamp": now_iso(), "action": "recommendation_applied", "actor": "user", "scenario": candidate.get("candidate_id", "-"), "result": "SUCCESS", "note": json.dumps(candidate)[:500]},
        )
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "candidate_id": candidate.get("candidate_id"), "timestamp": st.last_update}

    if action == "activate":
        st.fallback_active = False
        st.mode = "auto"
        _ensure_initialized(z)
        st.status = {**(st.status or {}), "status_today": "Active", "strategy_type": (st.status or {}).get("strategy_type", "LAEOPF")}
        store.append_audit(z, {"timestamp": now_iso(), "action": "activated", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Activate precooling"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "mode": st.mode, "timestamp": st.last_update}

    if action == "pause":
        _ensure_initialized(z)
        st.status = {**(st.status or {}), "status_today": "Paused", "strategy_type": (st.status or {}).get("strategy_type", "LAEOPF")}
        store.append_audit(z, {"timestamp": now_iso(), "action": "paused", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Pause precooling"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    if action == "cancel_today":
        st.schedule = {"zone": z, "generated_at": now_iso(), "slots": []}
        st.status = {**(st.status or {}), "status_today": "Cancelled", "strategy_type": "None"}
        store.append_audit(z, {"timestamp": now_iso(), "action": "cancelled_today", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Cancel today"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    if action == "use_rule_based":
        _ensure_initialized(z)
        st.mode = "advisory"
        st.status = {**(st.status or {}), "strategy_type": "Rule-Based", "optimization_objective": "Rule-based safety & comfort", "confidence_score": 0.6, "status_today": "Active"}
        store.append_audit(z, {"timestamp": now_iso(), "action": "rule_based_selected", "actor": "user", "scenario": "rule_based", "result": "SUCCESS", "note": "Use rule-based strategy"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "mode": st.mode, "timestamp": st.last_update}

    if action == "recompute_schedule":
        cfg = get_active_settings()
        merged, _ = merge_simulate_payload({"zone": z}, cfg)
        result, err = run_precooling_engine(merged, zone=z, mode=st.mode, fallback_active=st.fallback_active, settings=cfg)
        if err or not isinstance(result, dict):
            store.append_audit(z, {"timestamp": now_iso(), "action": "schedule_recompute", "actor": "user", "scenario": "-", "result": "FAILED", "note": err or "unknown"})
            store.touch(z)
            raise HTTPException(status_code=500, detail=err or "failed")
        st.status = result.get("status", st.status)
        st.schedule = result.get("schedule", st.schedule)
        st.kpi = result.get("kpi", st.kpi)
        st.scenarios = result.get("scenarios", st.scenarios)
        st.last_simulation = result
        store.append_audit(z, {"timestamp": now_iso(), "action": "schedule_recompute", "actor": "user", "scenario": "builder", "result": "SUCCESS", "note": "Recompute schedule"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    if action == "stop_precooling":
        st.schedule = {"zone": z, "generated_at": now_iso(), "slots": []}
        st.status = {**(st.status or {}), "status_today": "Stopped", "strategy_type": "None"}
        store.append_alert(z, {"timestamp": now_iso(), "severity": "MEDIUM", "type": "STOP", "zone": z, "description": "Precooling dihentikan oleh user", "action": "Stop"})
        store.append_audit(z, {"timestamp": now_iso(), "action": "stopped", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Stop precooling"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    if action == "approve_manual_override":
        store.append_audit(z, {"timestamp": now_iso(), "action": "manual_override_approved", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Approve manual override"})
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    if action == "save_scenario":
        note = json.dumps(p.get("scenario", p), ensure_ascii=False)[:500]
        store.append_audit(
            z,
            {"timestamp": now_iso(), "action": "scenario_saved", "actor": "user", "scenario": (p.get("scenario_id") or p.get("name") or "builder"), "result": "SUCCESS", "note": note},
        )
        store.touch(z)
        return {"ok": True, "zone": z, "action": action, "timestamp": st.last_update}

    store.append_audit(z, {"timestamp": now_iso(), "action": action, "actor": "user", "scenario": "-", "result": "FAILED", "note": "Unknown action"})
    store.touch(z)
    raise HTTPException(status_code=400, detail="Unknown action")


@router.post("/force_fallback")
def api_force_fallback(payload: Dict[str, Any] = Body(default_factory=dict)):
    p = _as_dict(payload)
    z = _zone(None, p)
    st = store.get(z)
    cfg = get_active_settings()
    fb = fallback_params(cfg)
    st.fallback_active = True
    st.mode = "fallback"
    st.status = {**(st.status or {}), **fallback_status(z, fb), "active_zones": z}
    store.append_alert(z, {"timestamp": now_iso(), "severity": "HIGH", "type": "FALLBACK", "zone": z, "description": "Fallback diaktifkan oleh user", "action": "System switched to fallback"})
    store.append_audit(z, {"timestamp": now_iso(), "action": "fallback_activated", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Force fallback"})
    store.touch(z)
    return {"ok": True, "zone": z, "action": "force_fallback", "mode": st.mode, "fallback_active": True, "timestamp": st.last_update}


@router.get("/settings")
def api_get_settings():
    return get_settings_bundle()


@router.get("/settings/default")
def api_get_settings_default():
    return {"default": get_default_settings()}


@router.post("/settings/validate")
def api_validate_settings(payload: Dict[str, Any] = Body(default_factory=dict)):
    p = _as_dict(payload)
    cfg = _as_dict(p.get("config", p))
    return validate_settings(cfg)


@router.post("/settings")
def api_save_settings(payload: Dict[str, Any] = Body(default_factory=dict)):
    p = _as_dict(payload)
    cfg = _as_dict(p.get("config", p))
    ok, resp = save_settings(cfg)
    if not ok:
        raise HTTPException(status_code=400, detail={"errors": resp.get("errors"), "warnings": resp.get("warnings")})
    return resp


@router.post("/settings/reset")
def api_reset_settings():
    bundle = reset_settings()
    return {"ok": True, "bundle": bundle}


@router.post("/settings/apply")
def api_apply_settings():
    resp = apply_settings()
    if resp.get("ok"):
        store.append_audit("zone_a", {"timestamp": now_iso(), "action": "settings_applied", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Precooling settings applied"})
    if not resp.get("ok"):
        raise HTTPException(status_code=400, detail={"errors": resp.get("errors"), "warnings": resp.get("warnings")})
    return resp
