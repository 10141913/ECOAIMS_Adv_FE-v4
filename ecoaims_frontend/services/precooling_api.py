import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, Optional, Tuple

import requests

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL, PRECOOLING_API_BASE_URL
from ecoaims_frontend.services.contract_registry import validate_endpoint
from ecoaims_frontend.services.http_trace import trace_headers
from ecoaims_frontend.services.runtime_contract_mismatch import build_runtime_endpoint_contract_mismatch

logger = logging.getLogger(__name__)
_PRECOOLING_DOWN_UNTIL_TS: float = 0.0
_PRECOOLING_LAST_LOG_TS: float = 0.0
_PRECOOLING_COOLDOWN_S: float = float(os.getenv("PRECOOLING_BACKEND_COOLDOWN_S", "5.0"))
_LAST_PRECOOLING_ENDPOINT_CONTRACT: Dict[str, Any] = {"status": "unknown", "errors": {}, "last_checked_at": None}
_FALLBACK_ZONE_ID: str = "floor1_a"


def get_last_precooling_endpoint_contract() -> Dict[str, Any]:
    return dict(_LAST_PRECOOLING_ENDPOINT_CONTRACT or {})


def _validate_contract(path: str, endpoint_key: str, payload: Optional[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _LAST_PRECOOLING_ENDPOINT_CONTRACT
    if payload is None:
        return None, None
    ok, errors, source = validate_endpoint(endpoint_key, payload)
    now = int(time.time())
    errs = _LAST_PRECOOLING_ENDPOINT_CONTRACT.get("errors")
    errs = errs if isinstance(errs, dict) else {}
    normalized = _LAST_PRECOOLING_ENDPOINT_CONTRACT.get("normalized")
    normalized = normalized if isinstance(normalized, dict) else {}
    if ok:
        errs.pop(path, None)
        normalized.pop(path, None)
        _LAST_PRECOOLING_ENDPOINT_CONTRACT = {"status": "ok" if not errs else "mismatch", "errors": errs, "normalized": normalized, "last_checked_at": now}
        return payload, None
    errs[path] = errors
    base_url = str(_LAST_PRECOOLING_ENDPOINT_CONTRACT.get("base_url") or "").rstrip("/") or str((ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/"))
    normalized[path] = build_runtime_endpoint_contract_mismatch(
        feature="precooling",
        endpoint_key=endpoint_key,
        path=path,
        base_url=base_url,
        errors=errors,
        source=source,
        payload=payload,
    )
    _LAST_PRECOOLING_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": errs, "normalized": normalized, "source": source, "base_url": base_url, "last_checked_at": now}
    return None, f"runtime_endpoint_contract_mismatch:{path} errors={errors}"


def _build_url(path: str, *, base_url: str | None = None) -> str:
    base = str(base_url).rstrip("/") if isinstance(base_url, str) and base_url.strip() else (ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _format_http_error(path: str, exc: requests.HTTPError, *, base_url: str | None = None) -> str:
    resp = exc.response
    if resp is None:
        return f"Gagal memanggil {path}: {str(exc)}"
    status = resp.status_code
    if status == 404:
        return f"Endpoint {path} belum tersedia (404)"
    hdrs = resp.headers or {}
    request_id = hdrs.get("x-request-id") or hdrs.get("x-correlation-id") or hdrs.get("x-trace-id") or hdrs.get("traceparent")
    detail = None
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            if payload.get("error_code") == "invalid_zone_id":
                zid = payload.get("zone_id") or payload.get("zone")
                return f"invalid_zone_id:{zid}" if zid else "invalid_zone_id"
            detail = payload.get("error") or payload.get("message") or payload.get("detail")
    except ValueError:
        detail = None
    if detail:
        suffix = f" request_id={request_id}" if request_id else ""
        if int(status) >= 500:
            base = str(base_url or "").strip().rstrip("/")
            hint = " cek .run/backend.log (dev) atau log backend kanonik"
            if base:
                hint = f" cek log backend ({base})"
            suffix += hint
        return f"HTTP {status} saat memanggil {path}: {detail}{suffix}"
    text = (resp.text or "").strip()
    if text:
        snippet = text[:400].replace("\n", " ")
        suffix = f" request_id={request_id}" if request_id else ""
        if int(status) >= 500:
            base = str(base_url or "").strip().rstrip("/")
            hint = " cek .run/backend.log (dev) atau log backend kanonik"
            if base:
                hint = f" cek log backend ({base})"
            suffix += hint
        return f"HTTP {status} saat memanggil {path}: {snippet}{suffix}"
    suffix = f" request_id={request_id}" if request_id else ""
    return f"HTTP {status} saat memanggil {path}{suffix}"


def _safe_get(path: str, params: Optional[Dict[str, Any]] = None, timeout_s: float = 5.0, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _PRECOOLING_DOWN_UNTIL_TS
    global _PRECOOLING_LAST_LOG_TS
    now = time.time()
    if now < _PRECOOLING_DOWN_UNTIL_TS:
        return None, f"Backend precooling tidak tersedia (cooldown {int(_PRECOOLING_DOWN_UNTIL_TS - now)}s)"
    url = _build_url(path, base_url=base_url)
    _LAST_PRECOOLING_ENDPOINT_CONTRACT["base_url"] = str(base_url or "").rstrip("/") if isinstance(base_url, str) else str((ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/"))
    try:
        th = trace_headers()
        resp = requests.get(url, params=params, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data, None
        return {"data": data}, None
    except requests.Timeout:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        return None, f"Timeout saat memuat {path}"
    except requests.HTTPError as e:
        return None, _format_http_error(path, e, base_url=base_url)
    except requests.RequestException as e:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        if now - _PRECOOLING_LAST_LOG_TS >= max(1.0, _PRECOOLING_COOLDOWN_S):
            _PRECOOLING_LAST_LOG_TS = now
            logger.warning(f"Precooling backend unavailable: {e}")
        return None, f"Gagal memuat {path}: {str(e)}"
    except ValueError:
        return None, f"Respons tidak valid (bukan JSON) dari {path}"


def _safe_post(
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_s: float = 20.0,
    *,
    params: Optional[Dict[str, Any]] = None,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _PRECOOLING_DOWN_UNTIL_TS
    global _PRECOOLING_LAST_LOG_TS
    now = time.time()
    if now < _PRECOOLING_DOWN_UNTIL_TS:
        return None, f"Backend precooling tidak tersedia (cooldown {int(_PRECOOLING_DOWN_UNTIL_TS - now)}s)"
    url = _build_url(path, base_url=base_url)
    _LAST_PRECOOLING_ENDPOINT_CONTRACT["base_url"] = str(base_url or "").rstrip("/") if isinstance(base_url, str) else str((ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/"))
    try:
        th = trace_headers()
        resp = requests.post(url, params=params, json=payload or {}, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data, None
        return {"data": data}, None
    except requests.Timeout:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        return None, f"Timeout saat memanggil {path}"
    except requests.HTTPError as e:
        return None, _format_http_error(path, e, base_url=base_url)
    except requests.RequestException as e:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        if now - _PRECOOLING_LAST_LOG_TS >= max(1.0, _PRECOOLING_COOLDOWN_S):
            _PRECOOLING_LAST_LOG_TS = now
            logger.warning(f"Precooling backend unavailable: {e}")
        return None, f"Gagal memanggil {path}: {str(e)}"
    except ValueError:
        return None, f"Respons tidak valid (bukan JSON) dari {path}"


def _as_number_list(v: Any) -> list[float]:
    if isinstance(v, list):
        out: list[float] = []
        for it in v:
            try:
                out.append(float(it))
            except Exception:
                continue
        return out
    if isinstance(v, str) and v.strip():
        out = []
        for part in v.split(","):
            try:
                out.append(float(part.strip()))
            except Exception:
                continue
        return out
    return []


def _safe_get_dashboard_state(base_url: str, *, stream_id: str = "default") -> Optional[Dict[str, Any]]:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return None
    try:
        th = trace_headers()
        r = requests.get(f"{base}/dashboard/state", params={"stream_id": stream_id}, timeout=2.5, **({"headers": th} if th else {}))
        r.raise_for_status()
        j = r.json()
        return j if isinstance(j, dict) else None
    except Exception:
        return None


def _parse_iso_ts(s: Any) -> Optional[datetime]:
    if not isinstance(s, str) or not s.strip():
        return None
    txt = s.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        return None


def _default_simulate_series(payload: Dict[str, Any], *, base_url: str) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    dash_state = _safe_get_dashboard_state(base_url, stream_id=str(payload.get("stream_id") or "default"))
    dash_ts = _parse_iso_ts(dash_state.get("timestamp") if isinstance(dash_state, dict) else None)
    start = (dash_ts or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)

    t_range = _as_number_list(payload.get("target_temp_range"))
    rh_range = _as_number_list(payload.get("target_rh_range"))
    t_center = (sum(t_range) / len(t_range)) if t_range else 24.0
    rh_center = (sum(rh_range) / len(rh_range)) if rh_range else 55.0

    indoor_mean_t = float(t_center + 1.0)
    indoor_amp_t = 1.2
    indoor_mean_rh = float(min(max(rh_center + 5.0, 35.0), 85.0))
    indoor_amp_rh = 4.0

    outdoor_mean_t = float(max(indoor_mean_t + 5.0, 29.0))
    outdoor_amp_t = 4.5
    outdoor_mean_rh = float(min(max(indoor_mean_rh + 8.0, 40.0), 92.0))
    outdoor_amp_rh = 10.0

    weather = []
    indoor = []
    for h in range(24):
        ts_dt = start + timedelta(hours=h)
        ts = ts_dt.isoformat()
        phase = 2.0 * math.pi * ((h - 8.0) / 24.0)
        outdoor_t = outdoor_mean_t + outdoor_amp_t * math.sin(phase)
        outdoor_rh = outdoor_mean_rh - outdoor_amp_rh * math.sin(phase)

        indoor_phase = 2.0 * math.pi * ((h - 10.0) / 24.0)
        zone_t = indoor_mean_t + indoor_amp_t * math.sin(indoor_phase)
        zone_rh = indoor_mean_rh - indoor_amp_rh * math.sin(indoor_phase)

        weather.append(
            {
                "timestamp": ts,
                "outdoor_temp_c": float(round(outdoor_t, 2)),
                "outdoor_rh_pct": float(round(min(max(outdoor_rh, 35.0), 95.0), 2)),
            }
        )
        indoor.append(
            {
                "timestamp": ts,
                "zone_temp_c": float(round(zone_t, 2)),
                "zone_rh_pct": float(round(min(max(zone_rh, 30.0), 90.0), 2)),
            }
        )
    return weather, indoor


def _normalize_precooling_simulate_request(raw: Dict[str, Any], *, base_url: str) -> Dict[str, Any]:
    payload = dict(raw or {})

    zone_id = payload.pop("zone_id", None) or payload.pop("zone", None) or _FALLBACK_ZONE_ID
    stream_id = payload.pop("stream_id", None) or "default"
    scenario_type = payload.pop("scenario_type", None)
    scenario = payload.pop("scenario", None) or "optimized"
    if isinstance(scenario_type, str) and scenario_type.strip():
        st = scenario_type.strip()
        if st in {"baseline", "rule_based", "optimized"}:
            scenario = st if scenario == "optimized" else scenario
        else:
            payload["scenario_type"] = st

    objective_weights = payload.pop("objective_weights", None) or payload.pop("weights", None)

    if (not isinstance(payload.get("weather"), list) or not payload.get("weather")) or (not isinstance(payload.get("indoor"), list) or not payload.get("indoor")):
        weather, indoor = _default_simulate_series(payload, base_url=base_url)
        if not isinstance(payload.get("weather"), list) or not payload.get("weather"):
            payload["weather"] = weather
        if not isinstance(payload.get("indoor"), list) or not payload.get("indoor"):
            payload["indoor"] = indoor

    req: Dict[str, Any] = {
        "zone_id": str(zone_id),
        "stream_id": str(stream_id),
        "scenario": scenario,
        "payload": payload,
    }
    if isinstance(objective_weights, dict) and objective_weights:
        req["objective_weights"] = objective_weights
    return req


def build_simulate_request(payload: Dict[str, Any], *, base_url: str | None = None) -> Dict[str, Any]:
    base = str(base_url or "").rstrip("/") if isinstance(base_url, str) and base_url.strip() else str((ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/"))
    return _normalize_precooling_simulate_request(payload if isinstance(payload, dict) else {}, base_url=base)


def get_zones(*, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    data, err = _safe_get("/api/precooling/zones", params=None, base_url=base_url)
    if err:
        return {"zones": [{"zone_id": _FALLBACK_ZONE_ID, "name": "Floor 1 / A", "type": "zone"}], "count": 1}, None
    if not data or not data.get("zones"):
        return {"zones": [{"zone_id": _FALLBACK_ZONE_ID, "name": "Floor 1 / A", "type": "zone"}], "count": 1}, None
    return _validate_contract("/api/precooling/zones", "GET /api/precooling/zones", data)


_ZONE_ID_RE = re.compile(r"^floor(?P<floor>\d+)_(?P<zone>all|a|b|c)$", re.IGNORECASE)


def pretty_zone_label(zone_id: str) -> str:
    zid = str(zone_id or "").strip()
    if not zid:
        return ""
    m = _ZONE_ID_RE.match(zid)
    if not m:
        return zid
    floor = m.group("floor")
    zone = str(m.group("zone") or "").lower()
    if zone == "all":
        return f"Lantai {floor} / All (A,B,C)"
    return f"Lantai {floor} / Zone {zone.upper()}"


def get_status(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data_v2, err_v2 = _safe_get("/api/precooling/status_v2", params=params, base_url=base_url)
    if not err_v2 and isinstance(data_v2, dict):
        return _validate_contract("/api/precooling/status_v2", "GET /api/precooling/status_v2", data_v2)
    data, err = _safe_get("/api/precooling/status", params=params, base_url=base_url)
    if err:
        return None, err_v2 or err
    return _validate_contract("/api/precooling/status", "GET /api/precooling/status", data)


def get_schedule(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data, err = _safe_get("/api/precooling/schedule", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/schedule", "GET /api/precooling/schedule", data)


def get_scenarios(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data, err = _safe_get("/api/precooling/scenarios", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/scenarios", "GET /api/precooling/scenarios", data)


def get_kpi(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data, err = _safe_get("/api/precooling/kpi", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/kpi", "GET /api/precooling/kpi", data)


def get_alerts(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data, err = _safe_get("/api/precooling/alerts", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/alerts", "GET /api/precooling/alerts", data)


def get_audit(zone: Optional[str] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone, "zone": zone} if zone else None
    data, err = _safe_get("/api/precooling/audit", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/audit", "GET /api/precooling/audit", data)


def post_simulate(payload: Dict[str, Any], *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    req = build_simulate_request(payload if isinstance(payload, dict) else {}, base_url=base_url)
    data, err = _safe_post("/api/precooling/simulate", payload=req, timeout_s=60.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/simulate", "POST /api/precooling/simulate", data)

def post_precooling_selector_preview(
    zone_id: str,
    payload: Dict[str, Any],
    *,
    return_candidates: bool = False,
    base_url: str | None = None,
) -> Dict[str, Any]:
    global _PRECOOLING_DOWN_UNTIL_TS
    global _PRECOOLING_LAST_LOG_TS
    now = time.time()
    if now < _PRECOOLING_DOWN_UNTIL_TS:
        return {"ok": False, "error": f"Backend precooling tidak tersedia (cooldown {int(_PRECOOLING_DOWN_UNTIL_TS - now)}s)", "status_code": None}

    zid = str(zone_id or "").strip()
    req: Dict[str, Any] = {"zone_id": zid, "payload": payload or {}, "return_candidates": bool(return_candidates)}
    url = _build_url("/api/precooling/selector/preview", base_url=base_url)
    _LAST_PRECOOLING_ENDPOINT_CONTRACT["base_url"] = str(base_url or "").rstrip("/") if isinstance(base_url, str) else str((ECOAIMS_API_BASE_URL or PRECOOLING_API_BASE_URL).rstrip("/"))
    try:
        th = trace_headers()
        resp = requests.post(url, json=req, timeout=20.0, **({"headers": th} if th else {}))
        status = int(getattr(resp, "status_code", 0) or 0)
        if status < 200 or status >= 300:
            body = (getattr(resp, "text", "") or "").strip()
            if len(body) > 800:
                body = body[:800] + "…"
            return {"ok": False, "error": body or f"HTTP {status}", "status_code": status}
        try:
            data = resp.json()
        except Exception:
            body = (getattr(resp, "text", "") or "").strip()
            return {"ok": False, "error": f"Respons tidak valid (bukan JSON) dari /api/precooling/selector/preview: {body[:300]}", "status_code": status}
        if isinstance(data, dict):
            return {"ok": True, "status_code": status, **data}
        return {"ok": True, "status_code": status, "data": data}
    except requests.Timeout:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        return {"ok": False, "error": "Timeout saat memanggil /api/precooling/selector/preview", "status_code": None}
    except requests.RequestException as e:
        _PRECOOLING_DOWN_UNTIL_TS = now + max(1.0, _PRECOOLING_COOLDOWN_S)
        if now - _PRECOOLING_LAST_LOG_TS >= max(1.0, _PRECOOLING_COOLDOWN_S):
            _PRECOOLING_LAST_LOG_TS = now
            logger.warning(f"Precooling backend unavailable: {e}")
        return {"ok": False, "error": f"Gagal memanggil /api/precooling/selector/preview: {str(e)}", "status_code": None}
    except Exception as e:
        return {"ok": False, "error": str(e), "status_code": None}



def post_selector_preview(
    zone_id: str,
    payload: Dict[str, Any],
    *,
    return_candidates: bool = False,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    resp = post_precooling_selector_preview(zone_id, payload, return_candidates=return_candidates, base_url=base_url)
    if not isinstance(resp, dict):
        return None, "Respons preview selector tidak valid"
    if not resp.get("ok"):
        err = resp.get("error")
        return None, str(err) if err else "Preview selector gagal"
    out = dict(resp)
    out.pop("ok", None)
    out.pop("error", None)
    out.pop("status_code", None)
    return out, None


def post_apply(payload: Dict[str, Any], *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    data, err = _safe_post("/api/precooling/apply", payload=payload, timeout_s=20.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/apply", "POST /api/precooling/apply", data)


def post_force_fallback(payload: Optional[Dict[str, Any]] = None, *, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    data, err = _safe_post("/api/precooling/force_fallback", payload=payload or {}, timeout_s=20.0, base_url=base_url)
    if err and "belum tersedia (404)" in err:
        compat_payload = {**(payload or {}), "action": "force_fallback"}
        data2, err2 = _safe_post("/api/precooling/apply", payload=compat_payload, timeout_s=20.0, base_url=base_url)
        if err2:
            return {"zones": [{"zone_id": "office_a", "name": "Office A", "type": "office"}], "count": 1}, err2
        return _validate_contract("/api/precooling/apply", "POST /api/precooling/apply", data2)
    if err:
        return None, err
    return _validate_contract("/api/precooling/force_fallback", "POST /api/precooling/force_fallback", data)


def get_settings(*, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone_id} if isinstance(zone_id, str) and zone_id.strip() else None
    data, err = _safe_get("/api/precooling/settings", params=params, timeout_s=10.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings", "GET /api/precooling/settings", data)


def get_settings_default(*, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone_id} if isinstance(zone_id, str) and zone_id.strip() else None
    data, err = _safe_get("/api/precooling/settings/default", params=params, timeout_s=10.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings/default", "GET /api/precooling/settings/default", data)


def post_settings_validate(config: Dict[str, Any], *, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload: Dict[str, Any] = {"config": config}
    if isinstance(zone_id, str) and zone_id.strip():
        payload["zone_id"] = zone_id.strip()
    data, err = _safe_post("/api/precooling/settings/validate", payload=payload, timeout_s=15.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings/validate", "POST /api/precooling/settings/validate", data)


def post_settings_save(config: Dict[str, Any], *, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload: Dict[str, Any] = {"config": config}
    if isinstance(zone_id, str) and zone_id.strip():
        payload["zone_id"] = zone_id.strip()
    data, err = _safe_post("/api/precooling/settings", payload=payload, timeout_s=15.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings", "POST /api/precooling/settings", data)


def post_settings_reset(*, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone_id} if isinstance(zone_id, str) and zone_id.strip() else None
    data, err = _safe_post("/api/precooling/settings/reset", payload={}, params=params, timeout_s=15.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings/reset", "POST /api/precooling/settings/reset", data)


def post_settings_apply(*, zone_id: str | None = None, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = {"zone_id": zone_id} if isinstance(zone_id, str) and zone_id.strip() else None
    data, err = _safe_post("/api/precooling/settings/apply", payload={}, params=params, timeout_s=20.0, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/precooling/settings/apply", "POST /api/precooling/settings/apply", data)
