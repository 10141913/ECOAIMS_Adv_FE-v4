import time
from typing import Any, Dict, List, Tuple

import requests

from ecoaims_frontend.config import CONTRACT_SYSTEM
from ecoaims_frontend.services.contract_negotiation import get_negotiation_service

def _to_int(v: Any) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            try:
                return int(float(s))
            except Exception:
                return None
    return None


def _to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y", "on"}:
            return True
        if s in {"false", "0", "no", "n", "off"}:
            return False
    return None


def extract_energy_data_limit_info(energy_data: Dict[str, Any] | None, *, records_len: int) -> Dict[str, Any]:
    energy_data = energy_data if isinstance(energy_data, dict) else {}
    applied_limit = energy_data.get("applied_limit")
    returned_records_len = energy_data.get("returned_records_len")
    available_records_len = energy_data.get("available_records_len")
    trimmed = energy_data.get("trimmed")

    applied_limit_i = _to_int(applied_limit)
    returned_i = _to_int(returned_records_len)
    available_i = _to_int(available_records_len)
    trimmed_b = _to_bool(trimmed)

    out: Dict[str, Any] = {
        "applied_limit": applied_limit_i,
        "returned_records_len": int(returned_i) if isinstance(returned_i, int) else int(records_len),
        "available_records_len": available_i,
        "trimmed": trimmed_b,
    }
    return out


def _attempt_get_json(url: str, timeout_s: Tuple[float, float]) -> Tuple[Dict[str, Any] | None, Dict[str, Any]]:
    t0 = time.time()
    try:
        r = requests.get(url, timeout=timeout_s)
        status = int(r.status_code)
        r.raise_for_status()
        js = r.json()
        data = js if isinstance(js, dict) else {"data": js}
        return data, {"url": url, "method": "GET", "status": status, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": None, "error": None}
    except requests.Timeout as e:
        return None, {"url": url, "method": "GET", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "backend_timeout", "error": str(e)}
    except requests.ConnectionError as e:
        return None, {"url": url, "method": "GET", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "backend_connection_error", "error": str(e)}
    except requests.HTTPError as e:
        resp = getattr(e, "response", None)
        status = int(resp.status_code) if resp is not None else None
        cls = "backend_endpoint_unavailable" if status == 404 else "backend_http_error"
        return None, {"url": url, "method": "GET", "status": status, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": cls, "error": str(e)}
    except requests.RequestException as e:
        return None, {"url": url, "method": "GET", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "backend_request_error", "error": str(e)}
    except ValueError as e:
        return None, {"url": url, "method": "GET", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "invalid_json", "error": str(e)}


def fetch_monitoring_diag(base_url: str, *, stream_id: str = "default") -> Dict[str, Any]:
    from ecoaims_frontend.config import MIN_HISTORY_FOR_COMPARISON
    from ecoaims_frontend.services.contract_registry import validate_endpoint

    base = str(base_url or "").rstrip("/")
    attempts: List[Dict[str, Any]] = []
    reasons: List[str] = []

    diag_url = f"{base}/diag/monitoring"
    if CONTRACT_SYSTEM.get("enabled") is True:
        svc = get_negotiation_service(cache_ttl_s=int(CONTRACT_SYSTEM.get("cache_ttl") or 300))
        nego = svc.negotiate_for_endpoint(
            base,
            method="GET",
            path="/diag/monitoring",
            mode=str(CONTRACT_SYSTEM.get("mode") or "lenient"),
            negotiation_required=bool(CONTRACT_SYSTEM.get("negotiation_required")),
        )
        attempts.append({**(nego.get("attempt") if isinstance(nego.get("attempt"), dict) else {}), "source": "contract_negotiation"})
        if str(nego.get("decision") or "") in {"block", "fallback"}:
            return {
                "backend_ok": True,
                "comparison_ready": False,
                "min_history_for_comparison": int(MIN_HISTORY_FOR_COMPARISON),
                "min_history_source": "frontend_default",
                "reasons": ["contract_negotiation_incompatible"],
                "attempts": attempts,
                "negotiation": nego,
            }
    diag, att = _attempt_get_json(diag_url, timeout_s=(1.5, 2.5))
    attempts.append(att)
    diag_status = str(diag.get("status") or "").strip().lower() if isinstance(diag, dict) else ""
    backend_ok = diag_status in {"ok", "degraded"}
    if not backend_ok:
        reasons.append("diag_monitoring_not_ok")

    effective_min = int(MIN_HISTORY_FOR_COMPARISON)
    min_source = "frontend_default"
    if isinstance(diag, dict):
        hist = diag.get("history")
        if isinstance(hist, dict) and hist.get("required_min_for_comparison") is not None:
            try:
                v = int(hist.get("required_min_for_comparison"))
                if v > 0:
                    effective_min = v
                    min_source = "backend_diag"
            except Exception:
                pass

    requested_limit = max(int(MIN_HISTORY_FOR_COMPARISON), int(effective_min))
    energy_url = f"{base}/api/energy-data?stream_id={stream_id}&limit={int(requested_limit)}"
    if CONTRACT_SYSTEM.get("enabled") is True:
        svc = get_negotiation_service(cache_ttl_s=int(CONTRACT_SYSTEM.get("cache_ttl") or 300))
        nego2 = svc.negotiate_for_endpoint(
            base,
            method="GET",
            path="/api/energy-data",
            mode=str(CONTRACT_SYSTEM.get("mode") or "lenient"),
            negotiation_required=bool(CONTRACT_SYSTEM.get("negotiation_required")),
        )
        attempts.append({**(nego2.get("attempt") if isinstance(nego2.get("attempt"), dict) else {}), "source": "contract_negotiation"})
        if str(nego2.get("decision") or "") in {"block", "fallback"}:
            return {
                "backend_ok": backend_ok,
                "comparison_ready": False,
                "min_history_for_comparison": int(effective_min),
                "min_history_source": min_source,
                "reasons": reasons + ["contract_negotiation_incompatible"],
                "attempts": attempts,
                "negotiation": nego2,
            }
    energy, att2 = _attempt_get_json(energy_url, timeout_s=(2.5, 5.0))
    attempts.append(att2)

    state_url = f"{base}/dashboard/state?stream_id={stream_id}"
    state, att3 = _attempt_get_json(state_url, timeout_s=(2.5, 5.0))
    attempts.append(att3)

    records_len = 0
    data_available = False
    energy_contract_ok = None
    energy_contract_errors = []
    energy_contract_source = None
    energy_limit_info: Dict[str, Any] = {}
    if isinstance(energy, dict):
        data_available = bool(energy.get("data_available"))
        recs = energy.get("records")
        if isinstance(recs, list):
            records_len = len(recs)
        energy_limit_info = extract_energy_data_limit_info(energy, records_len=records_len)
        ok, errs, src = validate_endpoint("GET /api/energy-data", energy)
        energy_contract_ok = bool(ok)
        energy_contract_errors = errs
        energy_contract_source = src
        if not ok:
            reasons.append("runtime_endpoint_contract_mismatch:/api/energy-data")

    returned_len = int(energy_limit_info.get("returned_records_len") or records_len)

    diag_energy_data_records_count = None
    if isinstance(diag, dict):
        hist = diag.get("history")
        if isinstance(hist, dict) and isinstance(hist.get("energy_data_records_count"), int):
            diag_energy_data_records_count = int(hist.get("energy_data_records_count"))

    data_trim_gap = None
    data_maybe_trimmed = False
    if isinstance(diag_energy_data_records_count, int) and diag_energy_data_records_count > int(returned_len):
        data_maybe_trimmed = True
        data_trim_gap = int(diag_energy_data_records_count) - int(returned_len)

    comparison_ready = bool(data_available and returned_len >= int(effective_min) and energy_contract_ok is True)
    if backend_ok and (data_available and returned_len < int(effective_min)):
        reasons.append(f"insufficient_history_for_comparison:min={int(effective_min)} got={returned_len}")
    if backend_ok and not data_available:
        reasons.append("energy_data_not_available")

    out: Dict[str, Any] = {
        "backend_ok": backend_ok,
        "comparison_ready": comparison_ready,
        "min_history_for_comparison": int(effective_min),
        "min_history_source": min_source,
        "requested_limit": int(requested_limit),
        "reasons": reasons,
        "attempts": attempts,
        "energy_data_available": data_available,
        "payload_records_len": int(records_len),
        "records_len": int(records_len),
        "records_count": int(records_len),
        "comparison_returned_records_len": int(returned_len),
        **energy_limit_info,
        "diag_energy_data_records_count": diag_energy_data_records_count,
        "data_maybe_trimmed": bool(data_maybe_trimmed),
        "data_trim_gap": data_trim_gap,
        "energy_contract_ok": energy_contract_ok,
        "energy_contract_source": energy_contract_source,
        "energy_contract_errors": energy_contract_errors[:100] if isinstance(energy_contract_errors, list) else [],
        "diag_status": (diag.get("status") if isinstance(diag, dict) else None),
        "diag": diag if isinstance(diag, dict) else None,
        "energy_data": energy if isinstance(energy, dict) else None,
        "dashboard_state": state if isinstance(state, dict) else None,
    }
    return out
