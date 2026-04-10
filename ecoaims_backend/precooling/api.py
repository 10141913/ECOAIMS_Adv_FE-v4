import json
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

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


precooling_bp = Blueprint("precooling_bp", __name__)


def _zone() -> str:
    zone = request.args.get("zone") or (request.json.get("zone") if request.is_json and isinstance(request.json, dict) else None)
    return str(zone) if zone else "zone_a"


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _ensure_initialized(zone: str) -> None:
    st = store.get(zone)
    if st.fallback_active:
        cfg = get_active_settings()
        st.status = {**(st.status or {}), **fallback_status(zone, fallback_params(cfg)), "active_zones": zone}
        return

    if st.status and st.schedule and st.kpi and st.scenarios:
        return

    cfg = get_active_settings()
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


@precooling_bp.get("/api/precooling/status")
def api_status():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)

    if not st.status:
        st.status = {
            "status_today": "Unknown",
            "active_zones": zone,
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

    if st.fallback_active:
        cfg = get_active_settings()
        st.status = {**st.status, **fallback_status(zone, fallback_params(cfg)), "active_zones": zone}

    resp = {
        "zone": zone,
        "mode": st.mode,
        "fallback_active": st.fallback_active,
        "last_update": st.last_update,
        "data_health": "OK",
        "settings_snapshot": settings_snapshot_for_ui(get_active_settings()),
        **st.status,
    }
    return jsonify(resp)


@precooling_bp.get("/api/precooling/schedule")
def api_schedule():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)
    resp = st.schedule or {"zone": zone, "generated_at": st.last_update, "slots": []}
    return jsonify(resp)


@precooling_bp.get("/api/precooling/scenarios")
def api_scenarios():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)
    resp = st.scenarios or {"zone": zone, "generated_at": st.last_update, "scenarios": [], "comparison": []}
    return jsonify(resp)


@precooling_bp.get("/api/precooling/kpi")
def api_kpi():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)
    resp = st.kpi or {"zone": zone, "generated_at": st.last_update}
    return jsonify(resp)


@precooling_bp.get("/api/precooling/alerts")
def api_alerts():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)
    return jsonify({"zone": zone, "generated_at": st.last_update, "alerts": st.alerts})


@precooling_bp.get("/api/precooling/audit")
def api_audit():
    zone = _zone()
    st = store.get(zone)
    _ensure_initialized(zone)
    store.touch(zone)
    return jsonify({"zone": zone, "generated_at": st.last_update, "audit": st.audit})


@precooling_bp.post("/api/precooling/simulate")
def api_simulate():
    payload = _as_dict(request.get_json(silent=True))
    zone = str(payload.get("zone") or _zone())
    st = store.get(zone)

    cfg = get_active_settings()
    merged, notes = merge_simulate_payload(payload, cfg)
    result, err = run_precooling_engine(merged, zone=zone, mode=st.mode, fallback_active=st.fallback_active, settings=cfg)
    if err:
        store.append_audit(
            zone,
            {
                "timestamp": now_iso(),
                "action": "simulation_requested",
                "actor": "user",
                "scenario": payload.get("scenario_id", "-"),
                "result": "FAILED",
                "note": err,
            },
        )
        return jsonify({"error": err}), 400

    st.last_simulation = result or {}
    if isinstance(result, dict):
        st.status = result.get("status", st.status)
        st.schedule = result.get("schedule", st.schedule)
        st.kpi = result.get("kpi", st.kpi)
        st.scenarios = result.get("scenarios", st.scenarios)

    store.append_audit(
        zone,
        {
            "timestamp": now_iso(),
            "action": "simulation_requested",
            "actor": "user",
            "scenario": payload.get("scenario_id", "builder"),
            "result": "SUCCESS",
            "note": "Simulation executed",
        },
    )

    if isinstance(result, dict):
        result = {**result, "effective_payload_notes": notes, "settings_snapshot": settings_snapshot_for_ui(cfg)}
    return jsonify(result)


@precooling_bp.post("/api/precooling/apply")
def api_apply():
    payload = _as_dict(request.get_json(silent=True))
    zone = str(payload.get("zone") or _zone())
    st = store.get(zone)

    action = str(payload.get("action") or "apply_recommendation")

    if action == "force_fallback":
        cfg = get_active_settings()
        fb = fallback_params(cfg)
        st.fallback_active = True
        st.mode = "fallback"
        st.status = {**(st.status or {}), **fallback_status(zone, fb), "active_zones": zone}
        store.append_alert(
            zone,
            {
                "timestamp": now_iso(),
                "severity": "HIGH",
                "type": "FALLBACK",
                "zone": zone,
                "description": "Fallback diaktifkan oleh user",
                "action": "System switched to fallback",
            },
        )
        store.append_audit(
            zone,
            {
                "timestamp": now_iso(),
                "action": "fallback_activated",
                "actor": "user",
                "scenario": "-",
                "result": "SUCCESS",
                "note": "Force fallback",
            },
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "mode": st.mode, "fallback_active": True, "timestamp": st.last_update})

    if action == "switch_mode":
        mode = str(payload.get("mode") or "advisory")
        st.mode = mode
        store.append_audit(
            zone,
            {
                "timestamp": now_iso(),
                "action": "mode_changed",
                "actor": "user",
                "scenario": "-",
                "result": "SUCCESS",
                "note": f"mode={mode}",
            },
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "mode": st.mode, "fallback_active": st.fallback_active, "timestamp": st.last_update})

    if action == "apply_recommendation":
        candidate = _as_dict(payload.get("candidate"))
        st.fallback_active = False
        if st.mode == "fallback":
            st.mode = "auto"
        store.append_audit(
            zone,
            {
                "timestamp": now_iso(),
                "action": "recommendation_applied",
                "actor": "user",
                "scenario": candidate.get("candidate_id", "-"),
                "result": "SUCCESS",
                "note": json.dumps(candidate)[:500],
            },
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "candidate_id": candidate.get("candidate_id"), "timestamp": st.last_update})

    if action == "activate":
        st.fallback_active = False
        st.mode = "auto"
        _ensure_initialized(zone)
        st.status = {**(st.status or {}), "status_today": "Active", "strategy_type": (st.status or {}).get("strategy_type", "LAEOPF")}
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "activated", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Activate precooling"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "mode": st.mode, "timestamp": st.last_update})

    if action == "pause":
        _ensure_initialized(zone)
        st.status = {**(st.status or {}), "status_today": "Paused", "strategy_type": (st.status or {}).get("strategy_type", "LAEOPF")}
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "paused", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Pause precooling"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    if action == "cancel_today":
        st.schedule = {"zone": zone, "generated_at": now_iso(), "slots": []}
        st.status = {**(st.status or {}), "status_today": "Cancelled", "strategy_type": "None"}
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "cancelled_today", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Cancel today"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    if action == "use_rule_based":
        _ensure_initialized(zone)
        st.mode = "advisory"
        st.status = {
            **(st.status or {}),
            "strategy_type": "Rule-Based",
            "optimization_objective": "Rule-based safety & comfort",
            "confidence_score": 0.6,
            "status_today": "Active",
        }
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "rule_based_selected", "actor": "user", "scenario": "rule_based", "result": "SUCCESS", "note": "Use rule-based strategy"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "mode": st.mode, "timestamp": st.last_update})

    if action == "recompute_schedule":
        cfg = get_active_settings()
        merged, _ = merge_simulate_payload({"zone": zone}, cfg)
        result, err = run_precooling_engine(merged, zone=zone, mode=st.mode, fallback_active=st.fallback_active, settings=cfg)
        if err or not isinstance(result, dict):
            store.append_audit(
                zone,
                {"timestamp": now_iso(), "action": "schedule_recompute", "actor": "user", "scenario": "-", "result": "FAILED", "note": err or "unknown"},
            )
            store.touch(zone)
            return jsonify({"ok": False, "error": err or "failed", "zone": zone, "action": action, "timestamp": st.last_update}), 500
        st.status = result.get("status", st.status)
        st.schedule = result.get("schedule", st.schedule)
        st.kpi = result.get("kpi", st.kpi)
        st.scenarios = result.get("scenarios", st.scenarios)
        st.last_simulation = result
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "schedule_recompute", "actor": "user", "scenario": "builder", "result": "SUCCESS", "note": "Recompute schedule"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    if action == "stop_precooling":
        st.schedule = {"zone": zone, "generated_at": now_iso(), "slots": []}
        st.status = {**(st.status or {}), "status_today": "Stopped", "strategy_type": "None"}
        store.append_alert(
            zone,
            {"timestamp": now_iso(), "severity": "MEDIUM", "type": "STOP", "zone": zone, "description": "Precooling dihentikan oleh user", "action": "Stop"},
        )
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "stopped", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Stop precooling"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    if action == "approve_manual_override":
        store.append_audit(
            zone,
            {"timestamp": now_iso(), "action": "manual_override_approved", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Approve manual override"},
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    if action == "save_scenario":
        note = json.dumps(payload.get("scenario", payload), ensure_ascii=False)[:500]
        store.append_audit(
            zone,
            {
                "timestamp": now_iso(),
                "action": "scenario_saved",
                "actor": "user",
                "scenario": (payload.get("scenario_id") or payload.get("name") or "builder"),
                "result": "SUCCESS",
                "note": note,
            },
        )
        store.touch(zone)
        return jsonify({"ok": True, "zone": zone, "action": action, "timestamp": st.last_update})

    store.append_audit(
        zone,
        {
            "timestamp": now_iso(),
            "action": action,
            "actor": "user",
            "scenario": "-",
            "result": "FAILED",
            "note": "Unknown action",
        },
    )
    store.touch(zone)
    return jsonify({"ok": False, "error": "Unknown action", "zone": zone, "action": action, "timestamp": st.last_update}), 400


@precooling_bp.post("/api/precooling/force_fallback")
def api_force_fallback():
    payload = _as_dict(request.get_json(silent=True))
    zone = str(payload.get("zone") or _zone())
    st = store.get(zone)
    cfg = get_active_settings()
    fb = fallback_params(cfg)
    st.fallback_active = True
    st.mode = "fallback"
    st.status = {**(st.status or {}), **fallback_status(zone, fb), "active_zones": zone}
    store.append_alert(
        zone,
        {
            "timestamp": now_iso(),
            "severity": "HIGH",
            "type": "FALLBACK",
            "zone": zone,
            "description": "Fallback diaktifkan oleh user",
            "action": "System switched to fallback",
        },
    )
    store.append_audit(
        zone,
        {
            "timestamp": now_iso(),
            "action": "fallback_activated",
            "actor": "user",
            "scenario": "-",
            "result": "SUCCESS",
            "note": "Force fallback",
        },
    )
    store.touch(zone)
    return jsonify({"ok": True, "zone": zone, "action": "force_fallback", "mode": st.mode, "fallback_active": True, "timestamp": st.last_update})


@precooling_bp.get("/api/precooling/settings")
def api_get_settings():
    return jsonify(get_settings_bundle())


@precooling_bp.get("/api/precooling/settings/default")
def api_get_settings_default():
    return jsonify({"default": get_default_settings()})


@precooling_bp.post("/api/precooling/settings/validate")
def api_validate_settings():
    payload = _as_dict(request.get_json(silent=True))
    cfg = _as_dict(payload.get("config", payload))
    return jsonify(validate_settings(cfg))


@precooling_bp.post("/api/precooling/settings")
def api_save_settings():
    payload = _as_dict(request.get_json(silent=True))
    cfg = _as_dict(payload.get("config", payload))
    ok, resp = save_settings(cfg)
    return jsonify(resp), (200 if ok else 400)


@precooling_bp.post("/api/precooling/settings/reset")
def api_reset_settings():
    bundle = reset_settings()
    return jsonify({"ok": True, "bundle": bundle})


@precooling_bp.post("/api/precooling/settings/apply")
def api_apply_settings():
    resp = apply_settings()
    if resp.get("ok"):
        store.append_audit(
            "zone_a",
            {"timestamp": now_iso(), "action": "settings_applied", "actor": "user", "scenario": "-", "result": "SUCCESS", "note": "Precooling settings applied"},
        )
    return jsonify(resp), (200 if resp.get("ok") else 400)
