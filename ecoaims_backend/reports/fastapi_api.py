import csv
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from ecoaims_backend.precooling.fastapi_api import _ensure_initialized
from ecoaims_backend.precooling.simulator import simulate_load_profile
from ecoaims_backend.precooling.storage import store


router = APIRouter(prefix="/api/reports", tags=["reports"])


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _pick_scenario(scenarios: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
    kw = keyword.lower()
    for s in scenarios:
        name = str(s.get("name") or "").lower()
        if kw in name:
            return s
    return None


def _metric(s: Dict[str, Any], key: str) -> float:
    try:
        return float(s.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _history_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base = os.getenv("ECOAIMS_OUTPUT_DIR", os.path.join(root, "output"))
    out_dir = os.path.join(base, "reports")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, "precooling_impact_history.jsonl")


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _parse_window(window: str) -> Tuple[Optional[str], Optional[int]]:
    s = str(window or "").strip()
    if not s or s == "-":
        return None, None
    if "-" not in s:
        return None, None
    a, b = [x.strip() for x in s.split("-", 1)]
    try:
        ah, am = [int(x) for x in a.split(":")]
        bh, bm = [int(x) for x in b.split(":")]
    except Exception:
        return None, None
    dur = (bh * 60 + bm) - (ah * 60 + am)
    if dur <= 0:
        return a, None
    return a, dur


def _quality_from_state(status: Dict[str, Any], kpi: Dict[str, Any], scenarios: List[Dict[str, Any]], basis: str) -> Dict[str, Any]:
    confidence = status.get("confidence_score")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = None

    unc = kpi.get("uncertainty") if isinstance(kpi.get("uncertainty"), dict) else {}
    sensor_compl = unc.get("sensor_completeness")
    try:
        sensor_compl = float(sensor_compl) * 100.0
    except (TypeError, ValueError):
        sensor_compl = None

    telemetry = sensor_compl
    coverage = sensor_compl
    gaps = False
    if telemetry is not None and telemetry < 75.0:
        gaps = True
    if confidence is not None and confidence < 0.6:
        gaps = True
    if basis in {"fallback", "insufficient_data"}:
        gaps = True

    matched_apply = 0
    try:
        for row in getattr(store.get(status.get("active_zones") or "zone_a"), "audit", []) or []:
            if isinstance(row, dict) and row.get("action") in {"recommendation_applied", "activated", "engine_initialized"}:
                matched_apply += 1
    except Exception:
        matched_apply = 0

    notes: List[str] = []
    if basis == "modeled":
        notes.append("Modeled impact; computed from Baseline vs LAEOPF comparison.")
    if basis == "applied":
        notes.append("Applied basis inferred from auto mode.")
    if basis == "fallback":
        notes.append("Fallback active; impact may not reflect optimized dispatch.")
    if basis == "insufficient_data":
        notes.append("Not enough data to reconstruct impact for selected filter.")
    if gaps:
        notes.append("Gaps detected; review telemetry completeness and confidence.")

    return {
        "reconstructable": bool(scenarios) and bool(kpi),
        "coverage_pct": coverage,
        "telemetry_completeness_pct": telemetry,
        "source_cost": "modeled_tariff",
        "source_co2": "modeled_factor",
        "source_comfort": "modeled_index",
        "matched_apply_events": matched_apply,
        "matched_dispatch_rows": None,
        "matched_windows": 1 if scenarios else 0,
        "gaps_detected": gaps,
        "confidence": confidence,
        "notes": notes,
    }


def _reason_codes_from(record: Dict[str, Any], quality: Dict[str, Any], basis_reason: str) -> Dict[str, Any]:
    basis = str(record.get("basis") or "").lower()
    basis_reason_code = None
    fallback_reason_code = None
    aggregation_reason_code = None
    if basis == "applied":
        basis_reason_code = "auto_mode_active"
    elif basis == "modeled":
        basis_reason_code = "modeled_comparison"
    elif basis == "fallback":
        basis_reason_code = "fallback_active"
        fallback_reason_code = "fallback_active"
    elif basis == "insufficient_data":
        basis_reason_code = "insufficient_data"

    agg = str((quality or {}).get("aggregation_mode") or "")
    if agg == "telemetry_native":
        aggregation_reason_code = "telemetry_native_used"
    elif agg == "session_rollup":
        aggregation_reason_code = "session_rollup_used"

    flags: List[str] = []
    flags.append("modeled_before_series")
    flags.append("modeled_after_series")
    if basis_reason and "Filtered out" in basis_reason:
        flags.append("filtered_out_by_basis")
    if (quality or {}).get("gaps_detected"):
        flags.append("gaps_detected")
    dispatch = (quality or {}).get("matched_dispatch_rows")
    if dispatch is None or dispatch == 0:
        flags.append("not_telemetry_backed")
    if aggregation_reason_code:
        flags.append(aggregation_reason_code)

    return {
        "basis_reason_code": basis_reason_code,
        "aggregation_reason_code": aggregation_reason_code,
        "fallback_reason_code": fallback_reason_code,
        "quality_flags": flags,
    }


def _history_read_all(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "rb") as f:
        for line in f:
            try:
                obj = json.loads(line.decode(errors="ignore"))
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue
    return rows


def _parse_basis(basis: Optional[str]) -> List[str]:
    if not isinstance(basis, str) or not basis.strip():
        return []
    return [x.strip() for x in basis.split(",") if x.strip()]


def _history_rows_filtered(zone_id: str, stream_id: str, allowed_basis: List[str], granularity: str) -> List[Dict[str, Any]]:
    path = _history_path()
    rows = [
        r
        for r in _history_read_all(path)
        if isinstance(r, dict)
        and r.get("zone_id") == zone_id
        and r.get("stream_id") == stream_id
        and _basis_match(str(r.get("basis")), allowed_basis)
    ]
    rows.sort(key=lambda r: str(r.get("ts") or ""), reverse=False)
    if str(granularity).lower() == "daily":
        daily: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            d = str(r.get("date") or "")[:10]
            if not d:
                continue
            daily[d] = r
        return [daily[k] for k in sorted(daily.keys())]
    return rows[-200:]


def _history_append(path: str, record: Dict[str, Any]) -> None:
    if not isinstance(record, dict) or not record:
        return
    eid = record.get("event_id")
    existing = _history_read_all(path)
    if eid and any(r.get("event_id") == eid for r in existing):
        return
    with open(path, "ab") as f:
        f.write((json.dumps(record, ensure_ascii=False) + "\n").encode())


def _make_record(
    *,
    period: str,
    zone: str,
    stream_id: str,
    basis: str,
    confidence: Optional[float],
    note: str,
    status: Dict[str, Any],
    baseline: Dict[str, Any],
    optimized: Dict[str, Any],
) -> Dict[str, Any]:
    ts = getattr(store.get(zone), "last_update", None) or _now_iso()
    date = str(ts)[:10]
    start = status.get("start_time") or "-"
    end = status.get("end_time") or "-"
    window = f"{start}-{end}" if start != "-" and end != "-" else "-"

    def _f(x: Any) -> Optional[float]:
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    be = _f(baseline.get("energy_kwh"))
    ae = _f(optimized.get("energy_kwh"))
    bp = _f(baseline.get("peak_kw"))
    ap = _f(optimized.get("peak_kw"))
    bc = _f(baseline.get("cost_idr"))
    ac = _f(optimized.get("cost_idr"))
    bco2 = _f(baseline.get("co2_kg"))
    aco2 = _f(optimized.get("co2_kg"))
    bcf = _f(baseline.get("comfort_compliance"))
    acf = _f(optimized.get("comfort_compliance"))

    return {
        "ts": ts,
        "date": date,
        "row_id": f"{zone}:{ts}",
        "session_window": window,
        "period": period,
        "basis": basis,
        "stream_id": stream_id,
        "zone_id": zone,
        "energy_before_kwh": be,
        "energy_after_kwh": ae,
        "energy_delta_kwh": (be - ae) if be is not None and ae is not None else None,
        "cost_before_idr": bc,
        "cost_after_idr": ac,
        "cost_delta_idr": (bc - ac) if bc is not None and ac is not None else None,
        "co2_before_kg": bco2,
        "co2_after_kg": aco2,
        "co2_delta_kg": (bco2 - aco2) if bco2 is not None and aco2 is not None else None,
        "comfort_before_ratio": bcf,
        "comfort_after_ratio": acf,
        "comfort_delta_ratio": (acf - bcf) if acf is not None and bcf is not None else None,
        "peak_before_kw": bp,
        "peak_after_kw": ap,
        "peak_delta_kw": (bp - ap) if bp is not None and ap is not None else None,
        "applied_scenario": optimized.get("name"),
        "fallback_used": basis == "fallback",
        "event_id": f"{zone}:{ts}",
        "confidence": confidence,
        "notes": note,
    }


@router.get("/precooling-impact")
def precooling_impact(
    period: str = Query(default="week"),
    zone: Optional[str] = Query(default=None),
    stream_id: Optional[str] = Query(default=None),
    basis: Optional[str] = Query(default=None),
    granularity: str = Query(default="daily"),
) -> Dict[str, Any]:
    z = zone or "zone_a"
    _ensure_initialized(z)
    st = store.get(z)

    status = _as_dict(st.status)
    kpi = _as_dict(st.kpi)
    scenarios_root = _as_dict(st.scenarios)
    scenarios = [s for s in _as_list(scenarios_root.get("scenarios")) if isinstance(s, dict)]

    resolved_basis = "modeled"
    basis_reason = "Default: baseline vs optimized comparison."
    if bool(getattr(st, "fallback_active", False)) or str(getattr(st, "mode", "") or "") == "fallback":
        resolved_basis = "fallback"
        basis_reason = "Fallback active."
    elif str(getattr(st, "mode", "") or "") == "auto":
        resolved_basis = "applied"
        basis_reason = "Auto mode active."

    insufficient = not kpi or not scenarios
    if insufficient:
        resolved_basis = "insufficient_data"
        basis_reason = "Missing KPI/scenarios."

    sid = stream_id or "precooling"
    allowed_basis = _parse_basis(basis)
    if allowed_basis and not _basis_match(resolved_basis, allowed_basis):
        resolved_basis = "insufficient_data"
        basis_reason = "Filtered out by basis."
        insufficient = True

    if insufficient:
        confidence = status.get("confidence_score")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
        quality = _quality_from_state(status, kpi, scenarios, resolved_basis)
        quality = {
            **quality,
            "aggregation_mode": "session_rollup",
            "aggregation_reason": "No matching rows for selected filters.",
            "basis_resolved": resolved_basis,
        }
        return {
            "period": period,
            "zone": z,
            "stream_id": sid,
            "basis": resolved_basis,
            "basis_reason": basis_reason,
            "confidence": confidence,
            "note": "Precooling impact belum tersedia untuk periode ini.",
            "generated_at": getattr(st, "last_update", None),
            "status": status,
            "quality": quality,
            "summary": {},
            "scenarios": [],
            "comparison": scenarios_root.get("comparison"),
            "filters": {"period": period, "stream_id": sid, "zone_id": z, "basis": allowed_basis, "granularity": granularity},
        }

    hist_rows = _history_rows_filtered(zone_id=z, stream_id=sid, allowed_basis=allowed_basis, granularity=granularity)
    agg_mode = None
    agg_reason = None
    if hist_rows:
        n = len(hist_rows)
        agg_mode = "session_rollup"
        agg_reason = f"Aggregated from {n} history rows for active filters."

    if hist_rows:
        def _sum(key: str) -> Optional[float]:
            vals = [r.get(key) for r in hist_rows if isinstance(r, dict)]
            nums = []
            for v in vals:
                try:
                    if v is None:
                        continue
                    nums.append(float(v))
                except (TypeError, ValueError):
                    continue
            if not nums:
                return None
            return sum(nums)

        def _avg(key: str) -> Optional[float]:
            vals = [r.get(key) for r in hist_rows if isinstance(r, dict)]
            nums = []
            for v in vals:
                try:
                    if v is None:
                        continue
                    nums.append(float(v))
                except (TypeError, ValueError):
                    continue
            if not nums:
                return None
            return sum(nums) / len(nums)

        summary = {
            "energy": {"before_kwh": _sum("energy_before_kwh"), "after_kwh": _sum("energy_after_kwh"), "delta_kwh": _sum("energy_delta_kwh"), "delta_pct": None},
            "peak": {"before_kw": _sum("peak_before_kw"), "after_kw": _sum("peak_after_kw"), "delta_kw": _sum("peak_delta_kw"), "delta_pct": None},
            "cost": {"before_idr": _sum("cost_before_idr"), "after_idr": _sum("cost_after_idr"), "delta_idr": _sum("cost_delta_idr"), "delta_pct": None},
            "co2": {"before_kg": _sum("co2_before_kg"), "after_kg": _sum("co2_after_kg"), "delta_kg": _sum("co2_delta_kg"), "delta_pct": None},
            "comfort": {"before_ratio": _avg("comfort_before_ratio"), "after_ratio": _avg("comfort_after_ratio"), "delta_ratio": _avg("comfort_delta_ratio")},
            "kpi": kpi,
        }

        confidence = status.get("confidence_score")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

        note = "Snapshot aggregated from history rows (session rollup)."
        quality = _quality_from_state(status, kpi, scenarios, resolved_basis)
        quality = {**quality, "aggregation_mode": agg_mode, "aggregation_reason": agg_reason, "basis_resolved": resolved_basis}

        return {
            "period": period,
            "zone": z,
            "stream_id": sid,
            "basis": resolved_basis,
            "basis_reason": basis_reason,
            "confidence": confidence,
            "note": note,
            "generated_at": getattr(st, "last_update", None),
            "status": status,
            "quality": quality,
            "summary": summary,
            "scenarios": scenarios,
            "comparison": scenarios_root.get("comparison"),
            "filters": {"period": period, "stream_id": sid, "zone_id": z, "basis": allowed_basis, "granularity": granularity},
        }

    baseline = _pick_scenario(scenarios, "baseline") or (scenarios[0] if scenarios else {})
    optimized = _pick_scenario(scenarios, "laeopf") or (scenarios[-1] if scenarios else {})

    before_energy = _metric(baseline, "energy_kwh")
    after_energy = _metric(optimized, "energy_kwh")
    before_peak = _metric(baseline, "peak_kw")
    after_peak = _metric(optimized, "peak_kw")
    before_cost = _metric(baseline, "cost_idr")
    after_cost = _metric(optimized, "cost_idr")
    before_co2 = _metric(baseline, "co2_kg")
    after_co2 = _metric(optimized, "co2_kg")
    before_comfort = _metric(baseline, "comfort_compliance")
    after_comfort = _metric(optimized, "comfort_compliance")

    def _pct_delta(before: float, after: float) -> Optional[float]:
        if before <= 0:
            return None
        return (after - before) / before * 100.0

    summary = {
        "energy": {"before_kwh": before_energy, "after_kwh": after_energy, "delta_kwh": before_energy - after_energy, "delta_pct": _pct_delta(before_energy, after_energy)},
        "peak": {"before_kw": before_peak, "after_kw": after_peak, "delta_kw": before_peak - after_peak, "delta_pct": _pct_delta(before_peak, after_peak)},
        "cost": {"before_idr": before_cost, "after_idr": after_cost, "delta_idr": before_cost - after_cost, "delta_pct": _pct_delta(before_cost, after_cost)},
        "co2": {"before_kg": before_co2, "after_kg": after_co2, "delta_kg": before_co2 - after_co2, "delta_pct": _pct_delta(before_co2, after_co2)},
        "comfort": {"before_ratio": before_comfort, "after_ratio": after_comfort, "delta_ratio": after_comfort - before_comfort},
        "kpi": kpi,
    }

    confidence = status.get("confidence_score")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = None

    note = None
    if resolved_basis == "modeled":
        note = "Modeled impact from baseline vs optimized comparison."
    elif resolved_basis == "applied":
        note = "Applied impact based on latest precooling state (auto mode)."
    elif resolved_basis == "fallback":
        note = "Fallback session detected; impact may not reflect optimized strategy."
    else:
        note = "Precooling impact belum tersedia untuk periode ini."

    quality = _quality_from_state(status, kpi, scenarios, resolved_basis)
    quality = {**quality, "aggregation_mode": "telemetry_native", "aggregation_reason": "Latest precooling state snapshot.", "basis_resolved": resolved_basis}
    rec = _make_record(
        period=period,
        zone=z,
        stream_id=sid,
        basis=resolved_basis,
        confidence=confidence,
        note=note,
        status=status,
        baseline=baseline,
        optimized=optimized,
    )
    try:
        _history_append(_history_path(), rec)
    except Exception:
        pass

    return {
        "period": period,
        "zone": z,
        "stream_id": sid,
        "basis": resolved_basis,
        "basis_reason": basis_reason,
        "confidence": confidence,
        "note": note,
        "generated_at": getattr(st, "last_update", None),
        "status": status,
        "quality": quality,
        "summary": summary,
        "scenarios": scenarios,
        "comparison": scenarios_root.get("comparison"),
        "filters": {"period": period, "stream_id": sid, "zone_id": z, "basis": allowed_basis, "granularity": granularity},
    }


def _basis_match(b: str, allowed: List[str]) -> bool:
    if not allowed:
        return True
    return str(b or "").lower() in {str(x).lower() for x in allowed}


@router.get("/precooling-impact/history")
def precooling_impact_history(
    period: str = Query(default="week"),
    granularity: str = Query(default="daily"),
    basis: Optional[str] = Query(default=None),
    zone: Optional[str] = Query(default=None),
    stream_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    z = zone or "zone_a"
    _ensure_initialized(z)
    sid = stream_id or "precooling"
    allowed = _parse_basis(basis)
    out = _history_rows_filtered(zone_id=z, stream_id=sid, allowed_basis=allowed, granularity=granularity)
    snap = precooling_impact(period=period, zone=z, stream_id=sid, basis=basis, granularity=granularity)

    return {
        "period": period,
        "zone": z,
        "stream_id": sid,
        "granularity": granularity,
        "basis_filter": allowed,
        "quality": snap.get("quality"),
        "aggregation_mode": (snap.get("quality") or {}).get("aggregation_mode") if isinstance(snap.get("quality"), dict) else None,
        "aggregation_reason": (snap.get("quality") or {}).get("aggregation_reason") if isinstance(snap.get("quality"), dict) else None,
        "rows": out,
    }


@router.get("/precooling-impact/export.csv")
def precooling_impact_export_csv(
    period: str = Query(default="week"),
    granularity: str = Query(default="daily"),
    basis: Optional[str] = Query(default=None),
    zone: Optional[str] = Query(default=None),
    stream_id: Optional[str] = Query(default=None),
) -> Response:
    payload = precooling_impact_history(period=period, granularity=granularity, basis=basis, zone=zone, stream_id=stream_id)
    rows = payload.get("rows") if isinstance(payload, dict) else []
    rows = rows if isinstance(rows, list) else []

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_id",
            "date",
            "ts",
            "session_window",
            "basis",
            "stream_id",
            "zone_id",
            "energy_before_kwh",
            "energy_after_kwh",
            "energy_delta_kwh",
            "cost_before_idr",
            "cost_after_idr",
            "cost_delta_idr",
            "co2_before_kg",
            "co2_after_kg",
            "co2_delta_kg",
            "comfort_before_ratio",
            "comfort_after_ratio",
            "comfort_delta_ratio",
            "peak_before_kw",
            "peak_after_kw",
            "peak_delta_kw",
            "applied_scenario",
            "fallback_used",
            "event_id",
            "confidence",
            "notes",
        ]
    )
    for r in rows:
        if not isinstance(r, dict):
            continue
        writer.writerow(
            [
                r.get("row_id"),
                r.get("date"),
                r.get("ts"),
                r.get("session_window"),
                r.get("basis"),
                r.get("stream_id"),
                r.get("zone_id"),
                r.get("energy_before_kwh"),
                r.get("energy_after_kwh"),
                r.get("energy_delta_kwh"),
                r.get("cost_before_idr"),
                r.get("cost_after_idr"),
                r.get("cost_delta_idr"),
                r.get("co2_before_kg"),
                r.get("co2_after_kg"),
                r.get("co2_delta_kg"),
                r.get("comfort_before_ratio"),
                r.get("comfort_after_ratio"),
                r.get("comfort_delta_ratio"),
                r.get("peak_before_kw"),
                r.get("peak_after_kw"),
                r.get("peak_delta_kw"),
                r.get("applied_scenario"),
                r.get("fallback_used"),
                r.get("event_id"),
                r.get("confidence"),
                r.get("notes"),
            ]
        )

    filename = f"precooling_impact_{period}_{granularity}.csv"
    data = buf.getvalue().encode("utf-8")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(data), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/precooling-impact/filter-options")
def precooling_impact_filter_options() -> Dict[str, Any]:
    path = _history_path()
    rows = _history_read_all(path)
    zones = sorted({str(r.get("zone_id")) for r in rows if isinstance(r, dict) and r.get("zone_id")})
    streams = sorted({str(r.get("stream_id")) for r in rows if isinstance(r, dict) and r.get("stream_id")})
    if not zones:
        zones = ["zone_a"]
    if not streams:
        streams = ["precooling"]
    return {
        "zones": zones,
        "streams": streams,
        "basis": ["applied", "modeled", "fallback"],
        "granularity": ["daily", "session"],
        "defaults": {"zone_id": zones[0], "stream_id": streams[0], "basis": ["modeled", "applied", "fallback"], "granularity": "daily"},
    }


@router.get("/precooling-impact/session-detail")
def precooling_impact_session_detail(
    row_id: str = Query(...),
    period: str = Query(default="week"),
    zone: Optional[str] = Query(default=None),
    stream_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    z = zone or "zone_a"
    sid = stream_id or "precooling"
    rid = str(row_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="row_id required")

    rows = _history_read_all(_history_path())
    hit = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get("row_id") or "") == rid and str(r.get("zone_id") or "") == z and str(r.get("stream_id") or "") == sid:
            hit = r
            break
    if hit is None:
        raise HTTPException(status_code=404, detail="session not found")

    snap = precooling_impact(period=period, zone=z, stream_id=sid, basis=str(hit.get("basis") or ""), granularity="session")
    quality = snap.get("quality") if isinstance(snap, dict) else None
    telemetry_preview = []
    reasons = _reason_codes_from(hit, quality if isinstance(quality, dict) else {}, str((snap or {}).get("basis_reason") or ""))
    return {
        "row_id": rid,
        "record": hit,
        "quality": quality,
        "telemetry_preview": telemetry_preview,
        "notes": hit.get("notes"),
        "before_fidelity": "modeled",
        "after_fidelity": "modeled",
        **reasons,
    }


@router.get("/precooling-impact/session-timeseries")
def precooling_impact_session_timeseries(
    row_id: str = Query(...),
    period: str = Query(default="week"),
    zone: Optional[str] = Query(default=None),
    stream_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    z = zone or "zone_a"
    sid = stream_id or "precooling"
    rid = str(row_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="row_id required")

    rows = _history_read_all(_history_path())
    hit = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get("row_id") or "") == rid and str(r.get("zone_id") or "") == z and str(r.get("stream_id") or "") == sid:
            hit = r
            break
    if hit is None:
        raise HTTPException(status_code=404, detail="session not found")

    start, dur_min = _parse_window(str(hit.get("session_window") or ""))
    if start is None:
        start = "06:00"
    if dur_min is None:
        dur_min = 60

    before_profile = simulate_load_profile(0, "00:00")
    after_profile = simulate_load_profile(int(dur_min), str(start))

    tariff = 1444.70
    co2_factor = 0.85

    ts = [p.get("hour") for p in after_profile]
    before_kw = [p.get("load_kw") for p in before_profile]
    after_kw = [p.get("load_kw") for p in after_profile]

    def _safe_mul(xs: List[Any], factor: float) -> List[Optional[float]]:
        out: List[Optional[float]] = []
        for v in xs:
            try:
                out.append(float(v) * factor)
            except (TypeError, ValueError):
                out.append(None)
        return out

    before_cost = _safe_mul(before_kw, tariff)
    after_cost = _safe_mul(after_kw, tariff)
    before_co2 = _safe_mul(before_kw, co2_factor)
    after_co2 = _safe_mul(after_kw, co2_factor)

    comfort_before = [hit.get("comfort_before_ratio") for _ in ts]
    comfort_after = [hit.get("comfort_after_ratio") for _ in ts]

    snap = precooling_impact(period=period, zone=z, stream_id=sid, basis=str(hit.get("basis") or ""), granularity="session")
    quality = snap.get("quality") if isinstance(snap, dict) else {}
    reasons = _reason_codes_from(hit, quality if isinstance(quality, dict) else {}, str((snap or {}).get("basis_reason") or ""))

    return {
        "row_id": rid,
        "period": period,
        "zone_id": z,
        "stream_id": sid,
        "timestep": "hour",
        "timestamps": ts,
        "series": {
            "energy_kw_before": before_kw,
            "energy_kw_after": after_kw,
            "cost_idr_before": before_cost,
            "cost_idr_after": after_cost,
            "co2_kg_before": before_co2,
            "co2_kg_after": after_co2,
            "comfort_before": comfort_before,
            "comfort_after": comfort_after,
        },
        "before_fidelity": "modeled",
        "after_fidelity": "modeled",
        **reasons,
    }
