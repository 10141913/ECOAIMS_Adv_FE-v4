import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
import hashlib
import json
from urllib.parse import urlparse

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL, ECOAIMS_REQUIRE_CANONICAL_POLICY
from ecoaims_frontend.services.contract_registry import get_registry_cache, load_contract_registry
from ecoaims_frontend.services.operational_policy import effective_verification_summary
from ecoaims_frontend.services.http_trace import trace_headers

_READINESS_CACHE: Dict[str, Any] = {}
_READINESS_DOWN_UNTIL_TS: float = 0.0
_READINESS_LAST_LOG_TS: float = 0.0
_READINESS_COOLDOWN_S: float = float(os.getenv("READINESS_BACKEND_COOLDOWN_S", "2.0"))
_EXPECTED_SCHEMA_VERSION: str = os.getenv("ECOAIMS_EXPECTED_SCHEMA_VERSION", "startup_info_v1")
_EXPECTED_CONTRACT_VERSION: str = os.getenv("ECOAIMS_EXPECTED_CONTRACT_VERSION", "2026-03-13")
_EXPECTED_BACKEND_IDENTITY_ID: str = os.getenv("ECOAIMS_EXPECTED_BACKEND_IDENTITY_ID", "").strip()
_EXPECTED_BACKEND_REPO_ID: str = os.getenv("ECOAIMS_EXPECTED_BACKEND_REPO_ID", "ECO_AIMS")
_EXPECTED_BACKEND_REPO: str = os.getenv("ECOAIMS_EXPECTED_BACKEND_REPO", "ECO_AIMS")
_EXPECTED_BACKEND_SERVER_ROLE: str = os.getenv("ECOAIMS_EXPECTED_BACKEND_SERVER_ROLE", "canonical_backend")
_EXPECTED_BACKEND_GIT_SHA: str = os.getenv("ECOAIMS_EXPECTED_BACKEND_GIT_SHA", "").strip()
ALLOW_LEGACY_BE_PROOF_PATH: bool = str(os.getenv("ECOAIMS_ALLOW_LEGACY_BE_PROOF_PATH", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
ALLOW_MINIMAL_STARTUP_INFO: bool = str(os.getenv("ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
STRICT_CONTRACT_VERSION: bool = str(os.getenv("ECOAIMS_STRICT_CONTRACT_VERSION", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}


def _extract_backend_identity(startup_info: Dict[str, Any], system_status: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    for src in (system_status, startup_info):
        if isinstance(src, dict):
            bi = src.get("backend_identity")
            if isinstance(bi, dict) and bi:
                return dict(bi)
            ident = src.get("identity")
            if isinstance(ident, dict) and ident:
                return dict(ident)
    return {}


def _extract_backend_identity_fingerprint(startup_info: Dict[str, Any], system_status: Optional[Dict[str, Any]]) -> str:
    for src in (system_status, startup_info):
        if isinstance(src, dict):
            v = src.get("backend_identity_fingerprint")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _manifest_hashes_from_registry_items(items: Any) -> Dict[str, str]:
    if not isinstance(items, list):
        return {}
    out: Dict[str, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        mid = it.get("manifest_id")
        mh = it.get("manifest_hash")
        if mid is None or mh is None:
            continue
        out[str(mid)] = str(mh)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def _fingerprint_backend_identity(
    backend_identity: Dict[str, Any],
    canonical_backend_identity_version: str | None = None,
    contracts_registry_version: str | None = None,
    manifest_hashes: Dict[str, str] | None = None,
) -> str:
    if canonical_backend_identity_version and contracts_registry_version and isinstance(manifest_hashes, dict) and manifest_hashes:
        material = {
            "backend_identity": backend_identity if isinstance(backend_identity, dict) else {},
            "canonical_backend_identity_version": str(canonical_backend_identity_version),
            "contracts_registry_version": str(contracts_registry_version),
            "manifest_hashes": dict(sorted((manifest_hashes or {}).items(), key=lambda kv: kv[0])),
        }
        raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    raw = json.dumps(backend_identity if isinstance(backend_identity, dict) else {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_backend_identity(backend_identity: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    identity_id = str(backend_identity.get("identity_id") or "")
    repo = str(backend_identity.get("repo") or "")
    repo_id = str(backend_identity.get("repo_id") or repo)
    server_role = str(backend_identity.get("server_role") or "")
    git_sha = str(backend_identity.get("git_sha") or "")

    if _EXPECTED_BACKEND_IDENTITY_ID:
        if not identity_id:
            reasons.append("backend_identity_missing:identity_id")
        elif identity_id != _EXPECTED_BACKEND_IDENTITY_ID:
            reasons.append(f"backend_identity_mismatch:identity_id expected={_EXPECTED_BACKEND_IDENTITY_ID} got={identity_id}")

    if not repo_id:
        reasons.append("backend_identity_missing:repo_id")
    elif repo_id != _EXPECTED_BACKEND_REPO_ID:
        reasons.append(f"backend_identity_mismatch:repo_id expected={_EXPECTED_BACKEND_REPO_ID} got={repo_id}")

    if not server_role:
        reasons.append("backend_identity_missing:server_role")
    elif server_role != _EXPECTED_BACKEND_SERVER_ROLE:
        reasons.append(f"backend_identity_mismatch:server_role expected={_EXPECTED_BACKEND_SERVER_ROLE} got={server_role}")

    if _EXPECTED_BACKEND_GIT_SHA:
        if not git_sha:
            reasons.append("backend_identity_missing:git_sha")
        elif git_sha != _EXPECTED_BACKEND_GIT_SHA:
            reasons.append(f"backend_identity_mismatch:git_sha expected={_EXPECTED_BACKEND_GIT_SHA} got={git_sha}")

    return (len(reasons) == 0), reasons


def _classify_error(exc: Exception) -> str:
    s = str(exc)
    if isinstance(exc, requests.Timeout):
        return "backend_timeout"
    if isinstance(exc, requests.ConnectionError) and ("Connection refused" in s or "Errno 61" in s or "ECONNREFUSED" in s):
        return "backend_connection_refused"
    if isinstance(exc, requests.ConnectionError):
        return "backend_connection_error"
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None and resp.status_code == 404:
            return "backend_endpoint_unavailable"
        return "backend_http_error"
    if isinstance(exc, requests.RequestException):
        return "backend_request_error"
    return "backend_unknown_error"


def _get_json(url: str, timeout: Tuple[float, float]) -> Dict[str, Any]:
    th = trace_headers()
    r = requests.get(url, timeout=timeout, **({"headers": th} if th else {}))
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict):
        return js
    return {"data": js}


def get_backend_readiness() -> Dict[str, Any]:
    global _READINESS_CACHE
    global _READINESS_DOWN_UNTIL_TS
    global _READINESS_LAST_LOG_TS

    base = (ECOAIMS_API_BASE_URL or "").rstrip("/")
    now = time.time()

    if now < _READINESS_DOWN_UNTIL_TS and _READINESS_CACHE:
        return dict(_READINESS_CACHE)

    readiness: Dict[str, Any] = {
        "base_url": base,
        "bootstrap_base_url": base,
        "canonical_base_url": base,
        "canonical_rebind_applied": False,
        "backend_reachable": False,
        "backend_ready": False,
        "capabilities": {},
        "reasons_not_ready": [],
        "last_checked_at": int(now),
        "error_class": None,
        "contract_valid": False,
        "contract_version": None,
        "schema_version": None,
        "contract_mismatch_reason": None,
        "contract_manifest_id": None,
        "contract_manifest_hash": None,
        "registry_loaded": False,
        "registry_version": None,
        "registry_manifest_id": None,
        "registry_manifest_hash": None,
        "registry_mismatch_reason": None,
        "overall_status": None,
        "feature_status": {},
        "recommended_mode": {},
        "policy_source": None,
        "canonical_policy_required": bool(ECOAIMS_REQUIRE_CANONICAL_POLICY),
        "integration_mode": "canonical_integration" if ECOAIMS_REQUIRE_CANONICAL_POLICY else "local_dev",
        "canonical_integration_ok": False,
        "backend_identity": {},
        "backend_identity_ok": False,
        "backend_identity_reasons": [],
        "canonical_backend_verified": False,
        "system_status": None,
    }

    mode = str(os.getenv("ECOAIMS_STACK_MODE", "") or "").strip().lower()
    expected_base = None
    if mode == "devtools":
        expected_base = str(os.getenv("ECOAIMS_DEVTOOLS_BASE_URL", "http://127.0.0.1:8009") or "").strip().rstrip("/")
    elif mode == "canonical":
        expected_base = str(os.getenv("ECOAIMS_CANONICAL_BASE_URL", "http://127.0.0.1:8008") or "").strip().rstrip("/")
    if expected_base and base and base.rstrip("/") != expected_base.rstrip("/"):
        readiness["error_class"] = "backend_mode_mismatch"
        readiness["backend_reachable"] = False
        readiness["backend_ready"] = False
        readiness["contract_valid"] = False
        readiness["contract_mismatch_reason"] = f"mode_mismatch mode={mode} expected_base_url={expected_base} got_base_url={base}"
        readiness["reasons_not_ready"] = [f"mode_mismatch:{mode}", f"expected_base_url={expected_base}", f"got_base_url={base}"]
        readiness["policy_source"] = "frontend_fallback"
        readiness["canonical_integration_ok"] = False
        readiness["backend_identity_ok"] = False
        readiness["backend_identity_reasons"] = ["backend_identity_unavailable"]
        readiness["canonical_backend_verified"] = False
        readiness.update(effective_verification_summary(readiness))
        _READINESS_CACHE = readiness
        return dict(_READINESS_CACHE)

    if not base:
        readiness["error_class"] = "backend_base_url_missing"
        readiness["reasons_not_ready"] = ["ECOAIMS_API_BASE_URL kosong"]
        readiness["backend_identity_ok"] = False
        readiness["backend_identity_reasons"] = ["backend_identity_unavailable"]
        readiness["canonical_backend_verified"] = False
        readiness.update(effective_verification_summary(readiness))
        _READINESS_CACHE = readiness
        return dict(_READINESS_CACHE)

    try:
        _ = _get_json(f"{base}/health", timeout=(1.5, 2.5))
        readiness["backend_reachable"] = True
    except Exception as e:
        readiness["error_class"] = _classify_error(e)
        readiness["reasons_not_ready"] = ["health_check_failed"]
        readiness["backend_identity_ok"] = False
        readiness["backend_identity_reasons"] = ["backend_identity_unavailable"]
        readiness["canonical_backend_verified"] = False
        readiness.update(effective_verification_summary(readiness))
        _READINESS_CACHE = readiness
        _READINESS_DOWN_UNTIL_TS = now + max(1.0, _READINESS_COOLDOWN_S)
        return dict(_READINESS_CACHE)

    try:
        info = _get_json(f"{base}/api/startup-info", timeout=(1.5, 2.5))
        readiness["capabilities"] = info.get("capabilities") if isinstance(info.get("capabilities"), dict) else {}
        readiness["backend_ready"] = bool(info.get("backend_ready", True))
        readiness["reasons_not_ready"] = info.get("reasons_not_ready") if isinstance(info.get("reasons_not_ready"), list) else []
        readiness["schema_version"] = info.get("schema_version")
        readiness["contract_version"] = info.get("contract_version")
        readiness["contract_manifest_id"] = info.get("contract_manifest_id")
        readiness["contract_manifest_hash"] = info.get("contract_manifest_hash")
        if not readiness["contract_manifest_id"] or not readiness["contract_manifest_hash"]:
            c = info.get("contracts") if isinstance(info.get("contracts"), dict) else {}
            readiness["contract_manifest_id"] = readiness["contract_manifest_id"] or c.get("contract_manifest_id")
            readiness["contract_manifest_hash"] = readiness["contract_manifest_hash"] or c.get("contract_manifest_hash")
        # Shape validation
        shape_errors = []
        if not isinstance(readiness["capabilities"], dict):
            shape_errors.append("capabilities_not_object")
        else:
            for k, v in readiness["capabilities"].items():
                if not isinstance(v, dict) or ("ready" not in v):
                    shape_errors.append(f"capability_{k}_invalid")
        if not isinstance(readiness["reasons_not_ready"], list):
            shape_errors.append("reasons_not_ready_not_list")
        req_eps = info.get("required_endpoints")
        if not isinstance(req_eps, list) or not req_eps:
            if not ALLOW_MINIMAL_STARTUP_INFO:
                shape_errors.append("required_endpoints_missing")
        else:
            required = {"/health", "/api/energy-data", "/api/system/status"}
            missing = [x for x in required if x not in req_eps]
            if missing and not ALLOW_MINIMAL_STARTUP_INFO:
                shape_errors.append(f"required_endpoints_missing:{','.join(missing)}")
        schema_ok = str(readiness["schema_version"] or "") == str(_EXPECTED_SCHEMA_VERSION)
        expected_contract_env = os.getenv("ECOAIMS_EXPECTED_CONTRACT_VERSION")
        expected_contract = str(expected_contract_env).strip() if isinstance(expected_contract_env, str) and expected_contract_env.strip() else str(_EXPECTED_CONTRACT_VERSION)
        strict_contract = bool(STRICT_CONTRACT_VERSION or ECOAIMS_REQUIRE_CANONICAL_POLICY or (isinstance(expected_contract_env, str) and expected_contract_env.strip()))
        if strict_contract:
            contract_ok = str(readiness["contract_version"] or "") == expected_contract
        else:
            contract_ok = True
        readiness["contract_valid"] = bool(schema_ok and contract_ok and not shape_errors)
        if not readiness["contract_valid"]:
            reason = f"expected schema={_EXPECTED_SCHEMA_VERSION} contract={expected_contract}, got schema={readiness['schema_version']} contract={readiness['contract_version']}"
            if shape_errors:
                reason += f" | shape_errors={','.join(shape_errors)}"
            readiness["contract_mismatch_reason"] = reason
        readiness["error_class"] = None

        # Compatibility with BE diag monitoring contract to reduce false negatives
        try:
            diag = _get_json(f"{base}/diag/monitoring", timeout=(1.0, 2.0))
            if isinstance(diag, dict) and (str(diag.get("contract_manifest_id") or "").strip() == "diag_monitoring_contract" or "history" in diag or "status" in diag):
                hist = diag.get("history") if isinstance(diag.get("history"), dict) else {}
                rec_count = int(hist.get("energy_data_records_count") or 0) if isinstance(hist.get("energy_data_records_count"), (int, float)) else 0
                required_min = int(hist.get("required_min_for_comparison") or 1) if isinstance(hist.get("required_min_for_comparison"), (int, float)) else 1
                sensor_bridge = diag.get("sensor_bridge") if isinstance(diag.get("sensor_bridge"), dict) else {}
                is_stale = bool(sensor_bridge.get("is_stale") is True)
                # Treat backend ready if diag contract present; adjust flags by history/sensor state
                readiness["backend_reachable"] = True
                readiness["backend_ready"] = True
                if rec_count < max(1, required_min) or is_stale:
                    readiness["reasons_not_ready"] = ["insufficient_history" if rec_count < required_min else "sensor_bridge_stale"]
                # Aliases for gating compatibility
                readiness["diag_status"] = str(diag.get("status") or "").strip().lower()
                energy_ready = bool(rec_count >= max(1, required_min))
                readiness["energy_ready"] = energy_ready
                readiness["comparison_ready"] = energy_ready
                if not energy_ready:
                    readiness["reasons_not_ready"] = ["insufficient_history"]
                elif is_stale:
                    readiness["reasons_not_ready"] = ["sensor_bridge_stale"]
                readiness["backend_ok"] = True
                readiness["records_len"] = rec_count
                readiness["records_count"] = rec_count
                readiness["diag_energy_data_records_count"] = rec_count
                readiness["returned_records_len"] = rec_count
                readiness["available_records_len"] = hist.get("available_records_len") if isinstance(hist.get("available_records_len"), int) else None
                readiness["required_min_for_comparison"] = required_min
                readiness["min_history_for_comparison"] = required_min
        except Exception:
            diag = None

        if not isinstance(diag, dict) or not isinstance(diag.get("history"), dict):
            try:
                ed = _get_json(f"{base}/api/energy-data", timeout=(1.0, 2.5))
                recs = ed.get("records") if isinstance(ed, dict) and isinstance(ed.get("records"), list) else []
                rec_count = len(recs)
                readiness["backend_reachable"] = True
                readiness["backend_ready"] = True
                readiness["backend_ok"] = True
                readiness["records_len"] = rec_count
                readiness["records_count"] = rec_count
                readiness["returned_records_len"] = rec_count
                readiness["required_min_for_comparison"] = 1
                readiness["min_history_for_comparison"] = 1
                readiness["energy_ready"] = bool(rec_count >= 1)
                readiness["comparison_ready"] = bool(rec_count >= 1)
            except Exception:
                pass

        expected_host = info.get("expected_host") if isinstance(info, dict) else None
        expected_port = info.get("expected_port") if isinstance(info, dict) else None
        canonical = None
        if isinstance(expected_host, str) and expected_host.strip() and isinstance(expected_port, int) and int(expected_port) > 0:
            scheme = urlparse(base).scheme or "http"
            canonical = f"{scheme}://{expected_host.strip()}:{int(expected_port)}"
        readiness["canonical_base_url"] = canonical or base
        if canonical and canonical.rstrip("/") != base.rstrip("/"):
            try:
                _ = _get_json(f"{canonical.rstrip('/')}/health", timeout=(1.0, 2.0))
                base = canonical.rstrip("/")
                readiness["base_url"] = base
                readiness["canonical_rebind_applied"] = True
            except Exception:
                pass

        if readiness["contract_manifest_id"]:
            reg = load_contract_registry(str(readiness["contract_manifest_id"]), str(readiness["contract_manifest_hash"] or ""))
            readiness["registry_loaded"] = bool(reg.get("registry_loaded"))
            readiness["registry_version"] = reg.get("registry_version")
            readiness["registry_manifest_id"] = reg.get("active_manifest_id")
            readiness["registry_manifest_hash"] = reg.get("active_manifest_hash")
            readiness["registry_mismatch_reason"] = reg.get("registry_mismatch_reason")

        try:
            sys_status = _get_json(f"{base}/api/system/status", timeout=(1.5, 2.5))
            if isinstance(sys_status, dict) and "overall_status" in sys_status and isinstance(sys_status.get("features"), dict):
                readiness["system_status"] = sys_status
                readiness["overall_status"] = sys_status.get("overall_status")
                readiness["policy_source"] = "backend_policy"
                feats = sys_status.get("features") if isinstance(sys_status.get("features"), dict) else {}
                readiness["feature_status"] = {k: (v.get("status") if isinstance(v, dict) else None) for k, v in feats.items()}
                readiness["recommended_mode"] = {k: (v.get("recommended_mode") if isinstance(v, dict) else None) for k, v in feats.items()}
        except Exception:
            readiness["policy_source"] = "frontend_fallback"

        readiness["backend_identity"] = _extract_backend_identity(info if isinstance(info, dict) else {}, readiness.get("system_status") if isinstance(readiness.get("system_status"), dict) else None)
        readiness["backend_identity_fingerprint"] = _extract_backend_identity_fingerprint(info if isinstance(info, dict) else {}, readiness.get("system_status") if isinstance(readiness.get("system_status"), dict) else None)
        ok_ident, ident_reasons = _validate_backend_identity(readiness["backend_identity"] if isinstance(readiness.get("backend_identity"), dict) else {})
        if readiness.get("backend_identity_fingerprint"):
            reg = get_registry_cache()
            reg_ver = str(reg.get("registry_version") or "") if isinstance(reg, dict) else ""
            reg_items = (reg.get("manifests") if isinstance(reg, dict) else None) or []
            manifest_hashes = _manifest_hashes_from_registry_items(reg_items)
            sys_status = readiness.get("system_status") if isinstance(readiness.get("system_status"), dict) else {}
            ident_ver = str(sys_status.get("canonical_backend_identity_version") or "")
            recomputed = _fingerprint_backend_identity(
                readiness["backend_identity"] if isinstance(readiness.get("backend_identity"), dict) else {},
                ident_ver or None,
                reg_ver or None,
                manifest_hashes or None,
            )
            readiness["backend_identity_fingerprint_recomputed"] = recomputed
            if str(readiness.get("backend_identity_fingerprint") or "") != recomputed:
                if not ALLOW_LEGACY_BE_PROOF_PATH:
                    ok_ident = False
                ident_reasons = list(ident_reasons) + ["backend_identity_fingerprint_mismatch"]
        readiness["backend_identity_ok"] = bool(ok_ident)
        readiness["backend_identity_reasons"] = ident_reasons

        readiness["canonical_integration_ok"] = bool(
            readiness.get("backend_reachable") is True
            and readiness.get("backend_ready") is True
            and readiness.get("contract_valid") is True
            and readiness.get("registry_loaded") is True
            and readiness.get("policy_source") == "backend_policy"
        )
        readiness["canonical_backend_verified"] = bool(readiness.get("canonical_integration_ok") is True and readiness.get("backend_identity_ok") is True)
        readiness.update(effective_verification_summary(readiness))
        _READINESS_CACHE = readiness
        return dict(_READINESS_CACHE)
    except Exception as e:
        cls = _classify_error(e)
        readiness["error_class"] = cls
        readiness["backend_ready"] = False
        readiness["capabilities"] = {}
        readiness["reasons_not_ready"] = ["startup_info_unavailable"]
        readiness["contract_valid"] = False
        readiness["contract_mismatch_reason"] = f"startup_info_unavailable (expected schema={_EXPECTED_SCHEMA_VERSION} contract={_EXPECTED_CONTRACT_VERSION})"
        readiness["policy_source"] = "frontend_fallback"
        readiness["canonical_integration_ok"] = False
        readiness["backend_identity_ok"] = False
        readiness["backend_identity_reasons"] = ["backend_identity_unavailable"]
        readiness["canonical_backend_verified"] = False
        readiness.update(effective_verification_summary(readiness))
        if now - _READINESS_LAST_LOG_TS >= max(1.0, _READINESS_COOLDOWN_S):
            _READINESS_LAST_LOG_TS = now
            _READINESS_DOWN_UNTIL_TS = now + max(1.0, _READINESS_COOLDOWN_S)
        _READINESS_CACHE = readiness
        return dict(_READINESS_CACHE)
