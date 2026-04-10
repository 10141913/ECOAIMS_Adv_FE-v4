import random
import os
import time
import requests
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode
from ecoaims_frontend.config import (
    ALLOW_LOCAL_SIMULATION_FALLBACK,
    API_BASE_URL,
    ECOAIMS_API_BASE_URL,
    ECOAIMS_CONTRACT_VALIDATION_MODE,
    CONTRACT_SYSTEM,
    ENERGY_LIMITS,
    USE_REAL_DATA,
    DEBUG_MODE,
    ECOAIMS_REQUIRE_CANONICAL_POLICY,
)
from ecoaims_frontend.services.contract_registry import validate_endpoint
from ecoaims_frontend.services.contract_negotiation import get_negotiation_service
from ecoaims_frontend.services.http_trace import trace_headers

logger = logging.getLogger(__name__)

_LAST_MONITORING_DIAGNOSTIC: Dict[str, Any] = {}
_LAST_MONITORING_ENDPOINT_CONTRACT: Dict[str, Any] = {"status": "unknown", "errors": [], "last_checked_at": None}
_LAST_DASHBOARD_KPI_DIAGNOSTIC: Dict[str, Any] = {}
_BACKEND_DOWN_UNTIL_TS: float = 0.0
_BACKEND_LAST_LOG_TS: float = 0.0
_BACKEND_COOLDOWN_S: float = float(os.getenv("MONITORING_BACKEND_COOLDOWN_S", "5.0"))

def _adapt_energy_data_contract_to_monitoring(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    # Branch 1: Payload already in canonical energy-data shape (top-level keys with value/max)
    if all(k in payload for k in ("solar", "wind", "grid", "biofuel", "battery")):
        try:
            def _num(x, d=0.0):
                try:
                    return float(x)
                except Exception:
                    return d
            def _src(dct):
                s = dct.get("source")
                return s if isinstance(s, str) and s else "backend"
            solar = payload.get("solar") or {}
            wind = payload.get("wind") or {}
            grid = payload.get("grid") or {}
            bio = payload.get("biofuel") or {}
            batt = payload.get("battery") or {}
            batt_status = batt.get("status") if isinstance(batt.get("status"), str) else "Unknown"
            out = {
                "solar": {"value": _num(solar.get("value")), "max": _num(solar.get("max")), "value_3h": _num(solar.get("value")) * 3, "source": _src(solar)},
                "wind": {"value": _num(wind.get("value")), "max": _num(wind.get("max")), "value_3h": _num(wind.get("value")) * 3, "source": _src(wind)},
                "grid": {
                    "value": _num(grid.get("value")),
                    "max": _num(grid.get("max")),
                    "value_3h": _num(grid.get("value")) * 3,
                    "source": _src(grid),
                    "grid_export": _num(grid.get("grid_export")),
                },
                "biofuel": {"value": _num(bio.get("value")), "max": _num(bio.get("max")), "value_3h": _num(bio.get("value")) * 3, "source": _src(bio)},
                "battery": {
                    "value": _num(batt.get("value")),
                    "max": _num(batt.get("max")),
                    "value_3h": _num(batt.get("value")),
                    "status": batt_status,
                    "source": _src(batt),
                    "soc_pct": _num(batt.get("soc_pct"), None),
                    "soc": _num(batt.get("soc"), None),
                },
            }
            recs = payload.get("records") if isinstance(payload.get("records"), list) else None
            if recs is not None:
                out["records"] = recs
                if recs and isinstance(recs[-1], dict) and isinstance(recs[-1].get("timestamp"), str):
                    out["data_timestamp"] = recs[-1].get("timestamp")
            elif isinstance(payload.get("timestamp"), str):
                out["data_timestamp"] = payload.get("timestamp")
            if isinstance(payload.get("stream_id"), str):
                out["stream_id"] = payload.get("stream_id")
            return out
        except Exception:
            pass
    # Branch 2: Legacy dashboard-state style payload with "latest"/"records"
    latest = payload.get("latest")
    if not isinstance(latest, dict):
        recs = payload.get("records") if isinstance(payload.get("records"), list) else []
        if recs and isinstance(recs[-1], dict):
            latest = recs[-1]
    if not isinstance(latest, dict):
        return None
    try:
        pv = float(latest.get("pv_generation") or 0.0)
        wind = float(latest.get("wind_generation") or 0.0)
        grid_import = float(latest.get("grid_import") or 0.0)
        grid_export = float(latest.get("grid_export") or 0.0)
        soc = latest.get("battery_soc")
        battery_soc = float(soc) if soc is not None else 0.0
        battery_soc = min(max(battery_soc, 0.0), 1.0)
        batt_capacity = float(ENERGY_LIMITS.get("battery") or 0.0)
        batt_kwh = battery_soc * batt_capacity if batt_capacity > 0 else 0.0
        batt_charge = float(latest.get("battery_charge") or 0.0)
        batt_discharge = float(latest.get("battery_discharge") or 0.0)
        batt_status = "Charging" if batt_charge > batt_discharge else "Discharging"

        return {
            "solar": {"value": pv, "max": float(ENERGY_LIMITS["solar"]), "value_3h": pv * 3, "source": "backend"},
            "wind": {"value": wind, "max": float(ENERGY_LIMITS["wind"]), "value_3h": wind * 3, "source": "backend"},
            "grid": {
                "value": max(0.0, grid_import),
                "max": float(ENERGY_LIMITS["grid"]),
                "value_3h": max(0.0, grid_import) * 3,
                "source": "backend",
                "grid_export": max(0.0, grid_export),
            },
            "biofuel": {"value": 0.0, "max": float(ENERGY_LIMITS["biofuel"]), "value_3h": 0.0, "source": "backend"},
            "battery": {
                "value": batt_kwh,
                "max": batt_capacity,
                "value_3h": batt_kwh,
                "status": batt_status,
                "source": "backend",
                "soc": battery_soc,
            },
        }
    except Exception:
        return None


def _adapt_dashboard_state_to_monitoring(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("data_available") is False:
        return None
    try:
        ts_raw = payload.get("timestamp")
        ts_s = str(ts_raw) if isinstance(ts_raw, str) and ts_raw.strip() else None
        age_s = None
        if ts_s:
            try:
                ts_dt = datetime.fromisoformat(ts_s.replace("Z", "+00:00"))
                if ts_dt.tzinfo is not None:
                    ts_dt = ts_dt.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None)
                age_s = float((datetime.now() - ts_dt).total_seconds())
            except Exception:
                age_s = None
        stale_s = float(os.getenv("ECOAIMS_BACKEND_STATE_STALE_S", "900"))
        is_stale = bool(isinstance(age_s, (int, float)) and float(age_s) > stale_s)
        backend_source = str(payload.get("source") or "").strip().lower()
        card_source = "live" if backend_source == "sensor_live" and not is_stale else "backend_state"

        mix_kw = payload.get("energy_mix_kw") if isinstance(payload.get("energy_mix_kw"), dict) else {}
        mix_pct = payload.get("energy_mix_pct") if isinstance(payload.get("energy_mix_pct"), dict) else {}

        solar_kw = float(mix_kw.get("solar_pv") if "solar_pv" in mix_kw else (payload.get("pv_power") or 0.0))
        wind_kw = float(mix_kw.get("wind_turbine") if "wind_turbine" in mix_kw else (payload.get("wind_power") or 0.0))
        grid_kw = float(mix_kw.get("pln_grid") if "pln_grid" in mix_kw else (payload.get("grid_import") or 0.0))
        bio_kw = float(mix_kw.get("biofuel") if "biofuel" in mix_kw else (payload.get("biofuel_power") or 0.0))

        batt_soc = None
        energy_data = payload.get("energy_data") if isinstance(payload.get("energy_data"), dict) else {}
        batt2 = energy_data.get("battery") if isinstance(energy_data.get("battery"), dict) else {}
        if isinstance(batt2.get("soc_pct"), (int, float)):
            batt_soc = float(batt2.get("soc_pct") or 0.0) / 100.0
        elif isinstance(batt2.get("soc"), (int, float)):
            batt_soc = float(batt2.get("soc") or 0.0)
        else:
            battery_soc_pct = payload.get("battery_soc_pct")
            soc = payload.get("soc")
            if isinstance(battery_soc_pct, (int, float)):
                batt_soc = float(battery_soc_pct) / 100.0
            elif isinstance(soc, (int, float)):
                batt_soc = float(soc)
            else:
                batt_soc = 0.0
        batt_soc = min(max(batt_soc, 0.0), 1.0)

        batt_capacity = payload.get("battery_capacity_kwh")
        batt_capacity_kwh = float(batt_capacity) if isinstance(batt_capacity, (int, float)) else float(ENERGY_LIMITS.get("battery") or 0.0)
        batt_energy_kwh = payload.get("battery_energy_kwh")
        if isinstance(batt_energy_kwh, (int, float)):
            batt_kwh = float(batt_energy_kwh)
        else:
            batt_kwh = batt_soc * batt_capacity_kwh if batt_capacity_kwh > 0 else 0.0
        batt_kwh = max(0.0, min(float(batt_kwh), float(batt_capacity_kwh or 0.0) if batt_capacity_kwh > 0 else float(batt_kwh)))

        batt_status_raw = str(payload.get("battery_status") or "").strip().lower()
        if batt_status_raw == "charging":
            batt_status = "Charging"
        elif batt_status_raw == "discharging":
            batt_status = "Discharging"
        elif batt_status_raw == "idle":
            batt_status = "Idle"
        else:
            batt_status = "Unknown"

        return {
            "solar": {
                "value": max(0.0, solar_kw),
                "max": float(ENERGY_LIMITS["solar"]),
                "value_3h": max(0.0, solar_kw) * 3,
                "source": card_source,
                "pct": float(mix_pct.get("solar_pv") or 0.0),
            },
            "wind": {
                "value": max(0.0, wind_kw),
                "max": float(ENERGY_LIMITS["wind"]),
                "value_3h": max(0.0, wind_kw) * 3,
                "source": card_source,
                "pct": float(mix_pct.get("wind_turbine") or 0.0),
            },
            "grid": {
                "value": max(0.0, grid_kw),
                "max": float(ENERGY_LIMITS["grid"]),
                "value_3h": max(0.0, grid_kw) * 3,
                "source": card_source,
                "grid_export": max(0.0, float(payload.get("grid_export") or 0.0)),
                "pct": float(mix_pct.get("pln_grid") or 0.0),
            },
            "biofuel": {
                "value": max(0.0, bio_kw),
                "max": float(ENERGY_LIMITS["biofuel"]),
                "value_3h": max(0.0, bio_kw) * 3,
                "source": card_source,
                "pct": float(mix_pct.get("biofuel") or 0.0),
            },
            "battery": {
                "value": float(batt_kwh),
                "max": float(batt_capacity_kwh),
                "value_3h": float(batt_kwh),
                "status": batt_status,
                "source": card_source,
                "soc": batt_soc,
                "soc_pct": batt_soc * 100.0,
                "battery_power_kw": float(mix_kw.get("battery") or payload.get("battery_power") or 0.0),
            },
            "load_kw": float(mix_kw.get("total_load") or payload.get("load_power") or 0.0),
            "state_meta": {"source": payload.get("source"), "timestamp": ts_s, "age_s": age_s, "stale": is_stale},
        }
    except Exception:
        return None

def _allow_local_simulation() -> bool:
    if not DEBUG_MODE or ECOAIMS_REQUIRE_CANONICAL_POLICY:
        return False
    if not USE_REAL_DATA:
        return True
    return bool(ALLOW_LOCAL_SIMULATION_FALLBACK)

def allow_local_simulation() -> bool:
    return _allow_local_simulation()


def get_last_monitoring_diagnostic() -> Dict[str, Any]:
    return dict(_LAST_MONITORING_DIAGNOSTIC or {})

def get_last_monitoring_endpoint_contract() -> Dict[str, Any]:
    return dict(_LAST_MONITORING_ENDPOINT_CONTRACT or {})

def get_last_dashboard_kpi_diagnostic() -> Dict[str, Any]:
    return dict(_LAST_DASHBOARD_KPI_DIAGNOSTIC or {})


def _http_error_detail(resp: requests.Response) -> str:
    try:
        return (resp.text or "")[:500]
    except Exception:
        return ""


def _attempt_get_json(url: str, timeout_s: Tuple[float, float]) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    t0 = time.time()
    try:
        th = trace_headers()
        resp = requests.get(url, timeout=timeout_s, **({"headers": th} if th else {}))
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data, {"url": url, "ok": True, "status": resp.status_code, "elapsed_ms": int((time.time() - t0) * 1000)}
        return None, {"url": url, "ok": False, "status": resp.status_code, "elapsed_ms": int((time.time() - t0) * 1000), "error": "response_not_json_object"}
    except requests.Timeout as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "timeout", "detail": str(e)}
    except requests.ConnectionError as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "connection_error", "detail": str(e)}
    except requests.HTTPError as e:
        resp = getattr(e, "response", None)
        status = resp.status_code if resp is not None else None
        body = _http_error_detail(resp) if resp is not None else ""
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "http_error", "status": status, "body": body}
    except requests.RequestException as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "request_error", "detail": str(e)}
    except ValueError as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "invalid_json", "detail": str(e)}


def _attempt_get_json_with_headers(url: str, *, headers: Dict[str, str], timeout_s: Tuple[float, float]) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    t0 = time.time()
    try:
        th = trace_headers()
        merged = dict(headers)
        if th:
            merged.update(th)
        resp = requests.get(url, timeout=timeout_s, headers=merged)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data, {
                "url": url,
                "ok": True,
                "status": resp.status_code,
                "elapsed_ms": int((time.time() - t0) * 1000),
                "headers_sent": dict(merged),
            }
        return None, {
            "url": url,
            "ok": False,
            "status": resp.status_code,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error": "response_not_json_object",
            "headers_sent": dict(merged),
        }
    except requests.Timeout as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "timeout", "detail": str(e), "headers_sent": dict(merged)}
    except requests.ConnectionError as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "connection_error", "detail": str(e), "headers_sent": dict(merged)}
    except requests.HTTPError as e:
        resp = getattr(e, "response", None)
        status = resp.status_code if resp is not None else None
        body = _http_error_detail(resp) if resp is not None else ""
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "http_error", "status": status, "body": body, "headers_sent": dict(merged)}
    except requests.RequestException as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "request_error", "detail": str(e), "headers_sent": dict(merged)}
    except ValueError as e:
        return None, {"url": url, "ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": "invalid_json", "detail": str(e), "headers_sent": dict(merged)}


def _classify_attempt(attempt: Dict[str, Any]) -> str:
    err = str(attempt.get("error") or "")
    status = attempt.get("status")
    detail = str(attempt.get("detail") or attempt.get("body") or "")
    if err == "timeout":
        return "backend_timeout"
    if err == "connection_error" and ("Connection refused" in detail or "Errno 61" in detail or "ECONNREFUSED" in detail):
        return "backend_connection_refused"
    if err in {"connection_error", "request_error"}:
        return "backend_request_error"
    if err == "http_error" and status == 404:
        return "backend_endpoint_unavailable"
    if err == "http_error":
        return "backend_http_error"
    if err == "cooldown":
        return "backend_cooldown"
    if err == "missing_base_url":
        return "backend_base_url_missing"
    return "backend_unknown_error"


def _classify_monitoring_diagnostic(diag: Dict[str, Any]) -> str:
    if isinstance(diag.get("class"), str) and diag.get("class"):
        return str(diag.get("class"))
    attempts = diag.get("attempts") if isinstance(diag.get("attempts"), list) else []
    primary = None
    for a in attempts:
        if not isinstance(a, dict):
            continue
        if a.get("source") == "canonical_health":
            primary = a
            break
    if primary is None:
        for a in attempts:
            if isinstance(a, dict) and a.get("source") == "canonical":
                primary = a
                break
    if primary is None:
        return "backend_unknown_error"
    return _classify_attempt(primary)


def _action_hint(error_class: str, base_url: str | None) -> str:
    base = (base_url or "").rstrip("/")
    if error_class == "backend_connection_refused":
        return f"Jalankan backend kanonik dan pastikan listen di {base or 'ECOAIMS_API_BASE_URL'}."
    if error_class == "backend_timeout":
        return "Backend lambat/timeout. Periksa beban server atau jaringan, lalu coba lagi."
    if error_class == "backend_endpoint_unavailable":
        return "Backend sehat tetapi endpoint Monitoring tidak tersedia. Pastikan versi backend sesuai (GET /api/energy-data)."
    if error_class == "backend_health_failed":
        return "Backend merespons tetapi health check gagal. Periksa log backend dan endpoint /health."
    if error_class == "backend_base_url_missing":
        return "Set ECOAIMS_API_BASE_URL ke URL backend kanonik (contoh: http://127.0.0.1:8008)."
    return "Periksa koneksi backend dan konfigurasi base URL."


def fetch_real_energy_data(*, base_url: str | None = None) -> Dict | None:
    """
    Fetches real energy data from the backend API.

    Returns:
        Dict: Energy data from API or None if fetch fails.
    """
    global _LAST_MONITORING_DIAGNOSTIC
    global _LAST_MONITORING_ENDPOINT_CONTRACT
    global _BACKEND_DOWN_UNTIL_TS
    global _BACKEND_LAST_LOG_TS
    diag: Dict[str, Any] = {
        "canonical_base_url": (base_url or ECOAIMS_API_BASE_URL),
        "legacy_base_url": API_BASE_URL,
        "attempts": [],
    }

    now = time.time()
    if now < _BACKEND_DOWN_UNTIL_TS:
        diag["attempts"].append({"source": "circuit_breaker", "ok": False, "error": "cooldown", "until_ts": _BACKEND_DOWN_UNTIL_TS})
        _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "cooldown": True}
        return None

    canonical = (str(base_url).rstrip("/") if isinstance(base_url, str) and base_url.strip() else (ECOAIMS_API_BASE_URL or "").rstrip("/"))
    if canonical:
        health_data, attempt_h = _attempt_get_json(f"{canonical}/health", timeout_s=(2.0, 3.0))
        if attempt_h:
            diag["attempts"].append({**attempt_h, "source": "canonical_health", "class": _classify_attempt(attempt_h)})
        state_data, attempt_s = _attempt_get_json(f"{canonical}/dashboard/state?stream_id=default", timeout_s=(2.5, 5.0))
        if attempt_s:
            diag["attempts"].append({**attempt_s, "source": "canonical_state", "class": _classify_attempt(attempt_s)})
        if isinstance(state_data, dict) and state_data:
            adapted_state = _adapt_dashboard_state_to_monitoring(state_data)
            if adapted_state is not None:
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "ok", "errors": [], "source": "dashboard_state", "last_checked_at": int(now)}
                _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": True, "selected": "canonical_state"}
                return adapted_state
        if CONTRACT_SYSTEM.get("enabled") is True:
            svc = get_negotiation_service(cache_ttl_s=int(CONTRACT_SYSTEM.get("cache_ttl") or 300))
            nego = svc.negotiate_for_endpoint(
                canonical,
                method="GET",
                path="/api/energy-data",
                mode=str(CONTRACT_SYSTEM.get("mode") or "lenient"),
                negotiation_required=bool(CONTRACT_SYSTEM.get("negotiation_required")),
            )
            diag["attempts"].append({**(nego.get("attempt") if isinstance(nego.get("attempt"), dict) else {}), "source": "contract_negotiation"})
            if str(nego.get("decision") or "") in {"block", "fallback"}:
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "blocked", "errors": ["contract_negotiation_failed"], "source": "negotiation", "last_checked_at": int(now)}
                _LAST_MONITORING_DIAGNOSTIC = {
                    **diag,
                    "ok": False,
                    "class": "contract_negotiation_incompatible",
                    "action": "Pre-flight contract negotiation menolak request /api/energy-data.",
                    "negotiation": nego,
                }
                if bool(CONTRACT_SYSTEM.get("fallback_to_simulation")) and _allow_local_simulation():
                    _LAST_MONITORING_DIAGNOSTIC = {
                        **diag,
                        "ok": True,
                        "selected": "simulation_fallback",
                        "warning_class": "contract_negotiation_incompatible",
                        "warning_action": "Pre-flight contract negotiation gagal; fallback ke simulasi lokal.",
                        "negotiation": nego,
                    }
                    return _generate_local_simulated_energy_data()
                _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
                return None
        url = f"{canonical}/api/energy-data"
        headers = {}
        if CONTRACT_SYSTEM.get("enabled") is True:
            try:
                svc = get_negotiation_service(cache_ttl_s=int(CONTRACT_SYSTEM.get("cache_ttl") or 300))
                headers = svc.headers_for_expected_contract("/api/energy-data")
            except Exception:
                headers = {}
        data, attempt = _attempt_get_json(url, timeout_s=(2.5, 5.0)) if not headers else _attempt_get_json_with_headers(url, headers=headers, timeout_s=(2.5, 5.0))
        if attempt:
            diag["attempts"].append({**attempt, "source": "canonical", "class": _classify_attempt(attempt)})
        if isinstance(data, dict) and data:
            ok_shape, shape_errors, source = validate_endpoint("GET /api/energy-data", data)
            if not ok_shape:
                if str(ECOAIMS_CONTRACT_VALIDATION_MODE or "").strip().lower() == "lenient":
                    adapted = _adapt_energy_data_contract_to_monitoring(data)
                    if adapted is not None:
                        _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "warn", "errors": shape_errors, "source": source, "last_checked_at": int(now)}
                        hint = "Payload /api/energy-data tidak sesuai kontrak minimum, tetapi diproses dalam mode lenient."
                        _LAST_MONITORING_DIAGNOSTIC = {
                            **diag,
                            "ok": True,
                            "selected": "canonical",
                            "warning_class": "runtime_endpoint_contract_mismatch",
                            "warning_action": hint,
                            "contract_errors": shape_errors,
                        }
                        return adapted
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": shape_errors, "source": source, "last_checked_at": int(now)}
                error_class = "runtime_endpoint_contract_mismatch"
                hint = "Payload /api/energy-data tidak sesuai kontrak minimum. Pastikan backend kanonik versi sesuai."
                _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "class": error_class, "action": hint, "contract_errors": shape_errors}
                _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
                return None
            adapted = _adapt_energy_data_contract_to_monitoring(data)
            if adapted is None:
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": ["energy_data_adapter_failed"], "source": source, "last_checked_at": int(now)}
                _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "class": "energy_data_adapter_failed", "action": "Payload valid, tetapi mapping ke format Monitoring gagal."}
                _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
                return None
            _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "ok", "errors": [], "source": source, "last_checked_at": int(now)}
            _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": True, "selected": "canonical"}
            return adapted
        if attempt_h and attempt_h.get("ok") and attempt and attempt.get("error") == "http_error" and attempt.get("status") == 404:
            diag["class"] = "backend_endpoint_unavailable"
    else:
        diag["attempts"].append({"url": None, "ok": False, "error": "missing_base_url", "source": "canonical"})

    if API_BASE_URL:
        base = API_BASE_URL.rstrip("/")
        if base.endswith("/api/energy-data") or base.endswith("/energy-data"):
            legacy_url = base
        elif base.endswith("/api"):
            legacy_url = f"{base}/energy-data"
        else:
            legacy_url = f"{base}/api/energy-data"
        legacy_data, attempt2 = _attempt_get_json(legacy_url, timeout_s=(2.5, 5.0))
        if attempt2:
            diag["attempts"].append({**attempt2, "source": "legacy"})
        if isinstance(legacy_data, dict) and legacy_data:
            ok_shape, shape_errors, source = validate_endpoint("GET /api/energy-data", legacy_data)
            if not ok_shape:
                if str(ECOAIMS_CONTRACT_VALIDATION_MODE or "").strip().lower() == "lenient":
                    adapted = _adapt_energy_data_contract_to_monitoring(legacy_data)
                    if adapted is not None:
                        _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "warn", "errors": shape_errors, "source": source, "last_checked_at": int(now)}
                        hint = "Payload legacy /api/energy-data tidak sesuai kontrak minimum, tetapi diproses dalam mode lenient."
                        _LAST_MONITORING_DIAGNOSTIC = {
                            **diag,
                            "ok": True,
                            "selected": "legacy",
                            "warning_class": "runtime_endpoint_contract_mismatch",
                            "warning_action": hint,
                            "contract_errors": shape_errors,
                        }
                        return adapted
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": shape_errors, "source": source, "last_checked_at": int(now)}
                error_class = "runtime_endpoint_contract_mismatch"
                hint = "Payload legacy /api/energy-data tidak sesuai kontrak minimum."
                _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "class": error_class, "action": hint, "contract_errors": shape_errors}
                _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
                return None
            adapted = _adapt_energy_data_contract_to_monitoring(legacy_data)
            if adapted is None:
                _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "mismatch", "errors": ["energy_data_adapter_failed"], "source": source, "last_checked_at": int(now)}
                _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "class": "energy_data_adapter_failed", "action": "Payload valid, tetapi mapping ke format Monitoring gagal."}
                _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
                return None
            _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "ok", "errors": [], "source": source, "last_checked_at": int(now)}
            logger.warning(f"Monitoring fallback ke legacy API_BASE_URL: {legacy_url}")
            _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": True, "selected": "legacy"}
            return adapted

    error_class = _classify_monitoring_diagnostic(diag)
    hint = _action_hint(error_class, diag.get("canonical_base_url"))
    _LAST_MONITORING_DIAGNOSTIC = {**diag, "ok": False, "class": error_class, "action": hint}
    if _LAST_MONITORING_ENDPOINT_CONTRACT.get("last_checked_at") is None:
        _LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "unknown", "errors": [], "last_checked_at": int(now)}
    _BACKEND_DOWN_UNTIL_TS = now + max(1.0, _BACKEND_COOLDOWN_S)
    if now - _BACKEND_LAST_LOG_TS >= max(1.0, _BACKEND_COOLDOWN_S):
        _BACKEND_LAST_LOG_TS = now
        logger.warning(f"Monitoring backend unavailable ({error_class}); base={diag.get('canonical_base_url')} cooldown={_BACKEND_COOLDOWN_S}s")
    return None


def fetch_dashboard_kpi(*, base_url: str | None = None, stream_id: str = "default", building_area_m2: float | None = None) -> Dict[str, Any] | None:
    global _LAST_DASHBOARD_KPI_DIAGNOSTIC
    canonical = (str(base_url).rstrip("/") if isinstance(base_url, str) and base_url.strip() else (ECOAIMS_API_BASE_URL or "").rstrip("/"))
    if not canonical:
        _LAST_DASHBOARD_KPI_DIAGNOSTIC = {"ok": False, "error": "missing_base_url"}
        return None
    params: Dict[str, Any] = {"stream_id": stream_id}
    if building_area_m2 is not None:
        params["building_area_m2"] = float(building_area_m2)
    url = f"{canonical}/dashboard/kpi?{urlencode(params)}"
    data, attempt = _attempt_get_json(url, timeout_s=(2.5, 5.0))
    _LAST_DASHBOARD_KPI_DIAGNOSTIC = {"ok": bool(isinstance(data, dict) and data), "url": url, "attempt": attempt}
    return data if isinstance(data, dict) and data else None


def format_monitoring_failure_detail(reason: str) -> str:
    diag = get_last_monitoring_diagnostic()
    lines = []
    lines.append(f"reason={reason}")
    if diag.get("class"):
        lines.append(f"class={diag.get('class')}")
    lines.append(f"ECOAIMS_API_BASE_URL={diag.get('canonical_base_url')}")
    if diag.get("legacy_base_url"):
        lines.append(f"API_BASE_URL={diag.get('legacy_base_url')}")
    lines.append(f"USE_REAL_DATA={USE_REAL_DATA}")
    lines.append(f"ALLOW_LOCAL_SIMULATION_FALLBACK={ALLOW_LOCAL_SIMULATION_FALLBACK}")
    lines.append(f"ALLOW_LOCAL_SIMULATION_FALLBACK_EFFECTIVE={_allow_local_simulation()}")
    if diag.get("action"):
        lines.append(f"action={diag.get('action')}")
    attempts = diag.get("attempts") if isinstance(diag.get("attempts"), list) else []
    for i, a in enumerate(attempts, start=1):
        if not isinstance(a, dict):
            continue
        src = a.get("source")
        url = a.get("url")
        err = a.get("error")
        cls = a.get("class")
        status = a.get("status")
        elapsed = a.get("elapsed_ms")
        detail = a.get("detail") or a.get("body")
        line = f"attempt[{i}] source={src} class={cls} url={url} status={status} error={err} elapsed_ms={elapsed}"
        if detail:
            line += f" detail={str(detail)[:220]}"
        lines.append(line)
    return "\n".join(lines)

def _generate_local_simulated_energy_data() -> Dict:
    solar_max = ENERGY_LIMITS['solar']
    wind_max = ENERGY_LIMITS['wind']
    battery_max = ENERGY_LIMITS['battery']
    grid_max = ENERGY_LIMITS['grid']
    bio_max = ENERGY_LIMITS['biofuel']
    
    # Generate current values
    solar_val = random.uniform(0, solar_max)
    wind_val = random.uniform(0, wind_max)
    batt_val = random.uniform(20, battery_max * 0.9) # Battery rarely 100% full in sim
    grid_val = random.uniform(10, grid_max * 0.9)
    bio_val = random.uniform(0, bio_max)

    # Determine Battery Status (Charge/Discharge)
    # Simple logic: If Solar+Wind is high, we charge. Else, discharge.
    # Threshold is arbitrary for simulation purposes.
    renewable_total = solar_val + wind_val
    is_charging = renewable_total > 80 # Example threshold
    battery_status = "Charging" if is_charging else "Discharging"

    # Simulate 1-hour aggregated data (roughly 1x current rate with variation)
    # Using variation 0.9 to 1.1 to simulate fluctuation over the period
    def simulate_1h(val):
        return val * 1 * random.uniform(0.9, 1.1)

    return {
        'solar': {'value': solar_val, 'max': solar_max, 'value_3h': simulate_1h(solar_val), 'source': 'local_sim'},
        'wind': {'value': wind_val, 'max': wind_max, 'value_3h': simulate_1h(wind_val), 'source': 'local_sim'},
        'battery': {
            'value': batt_val, 
            'max': battery_max, 
            'value_3h': simulate_1h(batt_val),
            'status': battery_status,
            'source': 'local_sim',
        },
        'grid': {'value': grid_val, 'max': grid_max, 'value_3h': simulate_1h(grid_val), 'source': 'local_sim'},
        'biofuel': {'value': bio_val, 'max': bio_max, 'value_3h': simulate_1h(bio_val), 'source': 'local_sim'}
    }


def get_energy_data(skip_backend: bool = False, *, base_url: str | None = None) -> Dict | None:
    data = None if skip_backend else fetch_real_energy_data(base_url=base_url)
    if isinstance(data, dict) and data:
        return data
    if USE_REAL_DATA:
        logger.warning("USE_REAL_DATA=True tetapi backend kanonik tidak mengembalikan data.")
    if _allow_local_simulation():
        logger.warning("Monitoring menggunakan simulasi lokal karena backend tidak tersedia.")
        return _generate_local_simulated_energy_data()
    return None


def get_simulated_energy_data() -> Dict:
    data = get_energy_data()
    if isinstance(data, dict) and data:
        return data
    raise RuntimeError("Backend kanonik tidak tersedia dan fallback simulasi lokal nonaktif.")

def get_forecast_data(period: str = 'hourly') -> Dict[str, List]:
    """
    Generates forecast data for consumption and renewable energy.
    
    Args:
        period (str): 'hourly' for next 24 hours, 'daily' for next 7 days.
        
    Returns:
        Dict: Contains lists for 'time', 'consumption', 'solar', 'wind'.
    """
    if period == 'hourly':
        periods = 24
        freq = 'h'
        start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    else:
        periods = 7
        freq = 'D'
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
    time_index = pd.date_range(start=start_time, periods=periods, freq=freq)
    
    # Base values
    base_consumption = 100
    base_solar = 50
    base_wind = 30
    
    consumption = []
    solar = []
    wind = []
    
    for i in range(periods):
        # Add some randomness and trends
        if period == 'hourly':
            # Solar peaks at noon (approx index 12 if starting at midnight, but here relative to now)
            hour = (start_time.hour + i) % 24
            is_day = 6 <= hour <= 18
            solar_factor = 1.0 if is_day else 0.0
            if is_day:
                # Simple bell curve approximation for solar
                solar_factor = 1 - abs(12 - hour) / 6
                solar_factor = max(0, solar_factor)
                
            cons_val = base_consumption + random.uniform(-10, 20) + (10 if 18 <= hour <= 22 else 0) # Peak evening
            solar_val = base_solar * solar_factor * random.uniform(0.8, 1.2)
            wind_val = base_wind * random.uniform(0.5, 1.5)
        else:
            # Daily
            cons_val = base_consumption * 24 + random.uniform(-100, 200)
            solar_val = base_solar * 12 * random.uniform(0.7, 1.3) # Average 12 hours sun
            wind_val = base_wind * 24 * random.uniform(0.6, 1.4)
            
        consumption.append(round(cons_val, 2))
        solar.append(round(solar_val, 2))
        wind.append(round(wind_val, 2))
        
    return {
        'time': time_index.strftime('%Y-%m-%d %H:%M').tolist() if period == 'hourly' else time_index.strftime('%Y-%m-%d').tolist(),
        'consumption': consumption,
        'solar': solar,
        'wind': wind
    }

def get_accuracy_data() -> Dict[str, List]:
    """
    Generates comparison data between Historical (Actual) and Forecast values
    for the past 24 hours to show model accuracy.
    """
    periods = 24
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=23)
    
    time_index = pd.date_range(start=start_time, end=end_time, freq='h')
    
    actual = []
    forecast = []
    
    base_val = 100
    
    for i in range(periods):
        # Create a "true" value
        true_val = base_val + random.uniform(-20, 20)
        
        # Forecast usually has some error
        error = random.uniform(-10, 10)
        pred_val = true_val + error
        
        actual.append(round(true_val, 2))
        forecast.append(round(pred_val, 2))
        
    return {
        'time': time_index.strftime('%H:%M').tolist(),
        'actual': actual,
        'forecast': forecast
    }

def update_trend_data(current_data: List[Dict], consumption: float, renewable_supply: float, timestamp: str, max_points: int = 10) -> List[Dict]:
    """
    Updates the historical trend data list.

    Args:
        current_data (List[Dict]): The existing list of data points.
        consumption (float): The new consumption value to add.
        renewable_supply (float): The new renewable supply value to add.
        timestamp (str): The timestamp string for the new value.
        max_points (int, optional): Maximum number of points to keep. Defaults to 10.

    Returns:
        List[Dict]: The updated list of data points.
    """
    current_data.append({
        'time': timestamp, 
        'consumption': consumption,
        'renewable_supply': renewable_supply
    })
    if len(current_data) > max_points:
        current_data.pop(0)
    return current_data
