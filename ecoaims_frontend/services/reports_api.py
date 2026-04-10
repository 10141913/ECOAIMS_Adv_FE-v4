import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL
from ecoaims_frontend.services.contract_registry import validate_endpoint
from ecoaims_frontend.services.http_trace import trace_headers
from ecoaims_frontend.services.runtime_contract_mismatch import build_runtime_endpoint_contract_mismatch


logger = logging.getLogger(__name__)
_REPORTS_DOWN_UNTIL_TS: float = 0.0
_REPORTS_LAST_LOG_TS: float = 0.0
_REPORTS_COOLDOWN_S: float = float(os.getenv("REPORTS_BACKEND_COOLDOWN_S", "5.0"))
_LAST_REPORTS_ENDPOINT_CONTRACT: Dict[str, Any] = {"status": "unknown", "errors": {}, "last_checked_at": None}


def get_last_reports_endpoint_contract() -> Dict[str, Any]:
    return dict(_LAST_REPORTS_ENDPOINT_CONTRACT or {})


def _validate_contract(path: str, endpoint_key: str, payload: Optional[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _LAST_REPORTS_ENDPOINT_CONTRACT
    if payload is None:
        return None, None
    ok, errors, source = validate_endpoint(endpoint_key, payload)
    now = int(time.time())
    errs = _LAST_REPORTS_ENDPOINT_CONTRACT.get("errors")
    errs = errs if isinstance(errs, dict) else {}
    normalized = _LAST_REPORTS_ENDPOINT_CONTRACT.get("normalized")
    normalized = normalized if isinstance(normalized, dict) else {}
    if ok:
        errs.pop(path, None)
        normalized.pop(path, None)
        _LAST_REPORTS_ENDPOINT_CONTRACT = {"status": "ok" if not errs else "mismatch", "errors": errs, "normalized": normalized, "last_checked_at": now}
        return payload, None
    errs[path] = errors
    base_url = str(_LAST_REPORTS_ENDPOINT_CONTRACT.get("base_url") or "").rstrip("/") or str((ECOAIMS_API_BASE_URL or "").rstrip("/"))
    normalized[path] = build_runtime_endpoint_contract_mismatch(
        feature="reports",
        endpoint_key=endpoint_key,
        path=path,
        base_url=base_url,
        errors=errors,
        source=source,
        payload=payload,
    )
    _LAST_REPORTS_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": errs, "normalized": normalized, "source": source, "base_url": base_url, "last_checked_at": now}
    return None, f"runtime_endpoint_contract_mismatch:{path} errors={errors}"


def _build_url(path: str, *, base_url: str | None = None) -> str:
    base = str(base_url).rstrip("/") if isinstance(base_url, str) and base_url.strip() else (ECOAIMS_API_BASE_URL or "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _format_http_error(path: str, exc: requests.HTTPError) -> str:
    resp = exc.response
    if resp is None:
        return f"Gagal memanggil {path}: {str(exc)}"
    status = resp.status_code
    if status == 404:
        return f"endpoint_not_supported:{path}"
    detail = None
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("message") or payload.get("detail")
    except ValueError:
        detail = None
    if detail:
        return f"HTTP {status} saat memanggil {path}: {detail}"
    return f"HTTP {status} saat memanggil {path}"


def _safe_get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout_s: float = 8.0,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _REPORTS_DOWN_UNTIL_TS
    global _REPORTS_LAST_LOG_TS
    now = time.time()
    if now < _REPORTS_DOWN_UNTIL_TS:
        return None, f"Backend reports tidak tersedia (cooldown {int(_REPORTS_DOWN_UNTIL_TS - now)}s)"
    url = _build_url(path, base_url=base_url)
    _LAST_REPORTS_ENDPOINT_CONTRACT["base_url"] = str(base_url or "").rstrip("/") if isinstance(base_url, str) else str((ECOAIMS_API_BASE_URL or "").rstrip("/"))
    try:
        th = trace_headers()
        resp = requests.get(url, params=params, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data, None
        return {"data": data}, None
    except requests.Timeout:
        _REPORTS_DOWN_UNTIL_TS = now + max(1.0, _REPORTS_COOLDOWN_S)
        return None, f"Timeout saat memuat {path}"
    except requests.HTTPError as e:
        return None, _format_http_error(path, e)
    except requests.RequestException as e:
        _REPORTS_DOWN_UNTIL_TS = now + max(1.0, _REPORTS_COOLDOWN_S)
        if now - _REPORTS_LAST_LOG_TS >= max(1.0, _REPORTS_COOLDOWN_S):
            _REPORTS_LAST_LOG_TS = now
            logger.warning(f"Reports backend unavailable: {e}")
        return None, f"Gagal memuat {path}: {str(e)}"
    except ValueError:
        return None, f"Respons tidak valid (bukan JSON) dari {path}"


def get_precooling_impact(
    period: str,
    zone: Optional[str] = None,
    stream_id: Optional[str] = None,
    basis_filter: Optional[str] = None,
    granularity: Optional[str] = None,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params: Dict[str, Any] = {"period": period}
    if zone:
        params["zone"] = zone
    if stream_id:
        params["stream_id"] = stream_id
    if basis_filter:
        params["basis"] = basis_filter
    if granularity:
        params["granularity"] = granularity
    data, err = _safe_get("/api/reports/precooling-impact", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/reports/precooling-impact", "GET /api/reports/precooling-impact", data)


def get_precooling_impact_filter_options(*, base_url: str | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    data, err = _safe_get("/api/reports/precooling-impact/filter-options", params=None, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/reports/precooling-impact/filter-options", "GET /api/reports/precooling-impact/filter-options", data)


def get_precooling_impact_history(
    period: str,
    granularity: str,
    basis_filter: Optional[str] = None,
    zone: Optional[str] = None,
    stream_id: Optional[str] = None,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params: Dict[str, Any] = {"period": period, "granularity": granularity}
    if basis_filter:
        params["basis"] = basis_filter
    if zone:
        params["zone"] = zone
    if stream_id:
        params["stream_id"] = stream_id
    data, err = _safe_get("/api/reports/precooling-impact/history", params=params, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/reports/precooling-impact/history", "GET /api/reports/precooling-impact/history", data)


def get_precooling_impact_export_csv(
    period: str,
    granularity: str,
    basis_filter: Optional[str] = None,
    zone: Optional[str] = None,
    stream_id: Optional[str] = None,
    timeout_s: float = 20.0,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[bytes], Optional[str]]:
    global _REPORTS_DOWN_UNTIL_TS
    global _REPORTS_LAST_LOG_TS
    now = time.time()
    if now < _REPORTS_DOWN_UNTIL_TS:
        return None, f"Backend reports tidak tersedia (cooldown {int(_REPORTS_DOWN_UNTIL_TS - now)}s)"
    params: Dict[str, Any] = {"period": period, "granularity": granularity}
    if basis_filter:
        params["basis"] = basis_filter
    if zone:
        params["zone"] = zone
    if stream_id:
        params["stream_id"] = stream_id
    url = _build_url("/api/reports/precooling-impact/export.csv", base_url=base_url)
    try:
        th = trace_headers()
        resp = requests.get(url, params=params, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        return resp.content, None
    except requests.Timeout:
        _REPORTS_DOWN_UNTIL_TS = now + max(1.0, _REPORTS_COOLDOWN_S)
        return None, "Timeout saat mengunduh export CSV"
    except requests.HTTPError as e:
        return None, _format_http_error("/api/reports/precooling-impact/export.csv", e)
    except requests.RequestException as e:
        _REPORTS_DOWN_UNTIL_TS = now + max(1.0, _REPORTS_COOLDOWN_S)
        if now - _REPORTS_LAST_LOG_TS >= max(1.0, _REPORTS_COOLDOWN_S):
            _REPORTS_LAST_LOG_TS = now
            logger.warning(f"Reports export unavailable: {e}")
        return None, f"Gagal mengunduh export CSV: {str(e)}"


def get_precooling_impact_session_detail(
    row_id: str,
    period: str,
    zone: Optional[str] = None,
    stream_id: Optional[str] = None,
    timeout_s: float = 10.0,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params: Dict[str, Any] = {"row_id": row_id, "period": period}
    if zone:
        params["zone"] = zone
    if stream_id:
        params["stream_id"] = stream_id
    data, err = _safe_get("/api/reports/precooling-impact/session-detail", params=params, timeout_s=timeout_s, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/reports/precooling-impact/session-detail", "GET /api/reports/precooling-impact/session-detail", data)


def get_precooling_impact_session_timeseries(
    row_id: str,
    period: str,
    zone: Optional[str] = None,
    stream_id: Optional[str] = None,
    timeout_s: float = 10.0,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params: Dict[str, Any] = {"row_id": row_id, "period": period}
    if zone:
        params["zone"] = zone
    if stream_id:
        params["stream_id"] = stream_id
    data, err = _safe_get("/api/reports/precooling-impact/session-timeseries", params=params, timeout_s=timeout_s, base_url=base_url)
    if err:
        return None, err
    return _validate_contract("/api/reports/precooling-impact/session-timeseries", "GET /api/reports/precooling-impact/session-timeseries", data)


def _safe_get_text(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout_s: float = 3.5,
    *,
    base_url: str | None = None,
) -> Tuple[Optional[str], Optional[str]]:
    url = _build_url(path, base_url=base_url)
    try:
        th = trace_headers()
        resp = requests.get(url, params=params, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        return (resp.text or "").rstrip(), None
    except requests.Timeout:
        return None, f"Timeout saat memuat {path}"
    except requests.HTTPError as e:
        return None, _format_http_error(path, e)
    except requests.RequestException as e:
        return None, f"Gagal memuat {path}: {str(e)}"


def get_ops_watch_summary(
    *,
    base_url: str | None = None,
    tail_lines: int = 200,
) -> Tuple[Optional[str], Optional[str]]:
    params = {"tail": int(tail_lines)} if int(tail_lines) > 0 else None
    candidates = [
        "/ops/watch",
        "/ops-watch",
        "/diag/ops-watch",
        "/diag/ops_watch",
        "/ops/ops-watch",
        "/ops/ops_watch",
    ]
    last_err: Optional[str] = None
    for path in candidates:
        txt, err = _safe_get_text(path, params=params, base_url=base_url)
        if err and isinstance(err, str) and err.startswith("endpoint_not_supported:"):
            last_err = err
            continue
        if err:
            return None, err
        if isinstance(txt, str) and txt.strip():
            return txt, None
        last_err = f"Respons kosong dari {path}"
    return None, last_err or "ops-watch belum tersedia di backend"
