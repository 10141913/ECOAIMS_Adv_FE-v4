import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from ecoaims_frontend.services.http_trace import trace_headers


_REGISTRY_CACHE: Dict[str, Any] = {}
_MANIFEST_CACHE: Dict[str, Any] = {}
_MANIFEST_BY_ID: Dict[str, Dict[str, Any]] = {}
_CACHE_TS: float = 0.0
_COOLDOWN_UNTIL_TS: float = 0.0
_COOLDOWN_S: float = float(os.getenv("CONTRACT_REGISTRY_COOLDOWN_S", "5.0"))
_BASE_URL_OVERRIDE: Optional[str] = None

def clear_registry_cache() -> None:
    global _REGISTRY_CACHE, _MANIFEST_CACHE, _MANIFEST_BY_ID, _CACHE_TS, _COOLDOWN_UNTIL_TS
    _REGISTRY_CACHE = {}
    _MANIFEST_CACHE = {}
    _MANIFEST_BY_ID = {}
    _CACHE_TS = 0.0
    _COOLDOWN_UNTIL_TS = 0.0

def get_registry_cache() -> Dict[str, Any]:
    return dict(_REGISTRY_CACHE) if isinstance(_REGISTRY_CACHE, dict) else {}

def set_registry_base_url(base_url: Optional[str]) -> None:
    global _BASE_URL_OVERRIDE, _REGISTRY_CACHE, _MANIFEST_CACHE, _MANIFEST_BY_ID, _CACHE_TS, _COOLDOWN_UNTIL_TS
    prev = _BASE_URL_OVERRIDE
    if isinstance(base_url, str) and base_url.strip():
        next_base = base_url.strip().rstrip("/")
    else:
        next_base = None
    if prev != next_base:
        _REGISTRY_CACHE = {}
        _MANIFEST_CACHE = {}
        _MANIFEST_BY_ID = {}
        _CACHE_TS = 0.0
        _COOLDOWN_UNTIL_TS = 0.0
    _BASE_URL_OVERRIDE = next_base


def _base_url() -> str:
    from ecoaims_frontend.config import ECOAIMS_API_BASE_URL
    if isinstance(_BASE_URL_OVERRIDE, str) and _BASE_URL_OVERRIDE.strip():
        return _BASE_URL_OVERRIDE.rstrip("/")
    return (ECOAIMS_API_BASE_URL or "").rstrip("/")


def _get_json(url: str, timeout: Tuple[float, float] = (2.5, 5.0)) -> Dict[str, Any]:
    th = trace_headers()
    r = requests.get(url, timeout=timeout, **({"headers": th} if th else {}))
    r.raise_for_status()
    js = r.json()
    return js if isinstance(js, dict) else {"data": js}


def load_contract_registry(manifest_id: str, expected_hash: Optional[str]) -> Dict[str, Any]:
    global _REGISTRY_CACHE, _MANIFEST_CACHE, _MANIFEST_BY_ID, _CACHE_TS, _COOLDOWN_UNTIL_TS
    now = time.time()
    base = _base_url()
    if not base:
        return {"registry_loaded": False, "registry_mismatch_reason": "missing_base_url"}
    if now < _COOLDOWN_UNTIL_TS and _MANIFEST_CACHE.get("manifest_id") == manifest_id:
        return {
            "registry_loaded": bool(_MANIFEST_CACHE),
            "registry_version": _REGISTRY_CACHE.get("registry_version"),
            "active_manifest_id": _MANIFEST_CACHE.get("manifest_id"),
            "active_manifest_hash": _MANIFEST_CACHE.get("manifest_hash"),
            "registry_mismatch_reason": _MANIFEST_CACHE.get("_registry_mismatch_reason"),
        }
    try:
        idx = _get_json(f"{base}/api/contracts/index", timeout=(1.5, 2.5))
        _REGISTRY_CACHE = idx
        manifest = _get_json(f"{base}/api/contracts/{manifest_id}", timeout=(1.5, 2.5))
        mh = str(manifest.get("manifest_hash") or manifest.get("contract_manifest_hash") or "")
        if expected_hash is not None and mh != str(expected_hash):
            _MANIFEST_CACHE = {**manifest, "_registry_mismatch_reason": f"manifest_hash_mismatch expected={expected_hash} got={mh}"}
            _COOLDOWN_UNTIL_TS = now + max(1.0, _COOLDOWN_S)
            return {
                "registry_loaded": False,
                "registry_version": idx.get("registry_version"),
                "active_manifest_id": manifest_id,
                "active_manifest_hash": mh,
                "registry_mismatch_reason": _MANIFEST_CACHE.get("_registry_mismatch_reason"),
            }
        _MANIFEST_CACHE = manifest
        mid = manifest.get("manifest_id") or manifest.get("contract_manifest_id")
        if isinstance(mid, str) and mid:
            _MANIFEST_BY_ID[str(mid)] = dict(manifest)
        _CACHE_TS = now
        return {
            "registry_loaded": True,
            "registry_version": idx.get("registry_version"),
            "active_manifest_id": mid,
            "active_manifest_hash": mh,
            "registry_mismatch_reason": None,
        }
    except Exception as e:
        _COOLDOWN_UNTIL_TS = now + max(1.0, _COOLDOWN_S)
        return {"registry_loaded": False, "registry_mismatch_reason": f"registry_unavailable:{str(e)}"}


def _expected_manifest_hash_from_registry(manifest_id: str) -> str:
    idx = _REGISTRY_CACHE if isinstance(_REGISTRY_CACHE, dict) else {}
    items = idx.get("manifests") if isinstance(idx.get("manifests"), list) else []
    for it in items:
        if not isinstance(it, dict):
            continue
        if str(it.get("manifest_id") or "") == str(manifest_id):
            return str(it.get("manifest_hash") or "")
    endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
    for ek, ev in endpoint_map.items():
        if not isinstance(ev, dict):
            continue
        if str(ev.get("contract_manifest_id") or "") == str(manifest_id):
            return str(ev.get("contract_manifest_hash") or "")
    return ""


def _ensure_manifest_for_endpoint(endpoint_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    global _REGISTRY_CACHE, _COOLDOWN_UNTIL_TS
    idx = _REGISTRY_CACHE if isinstance(_REGISTRY_CACHE, dict) else {}
    endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
    if not endpoint_map:
        base = _base_url()
        now = time.time()
        if not base:
            return None, "missing_base_url"
        if now < _COOLDOWN_UNTIL_TS:
            return None, "registry_cooldown"
        try:
            idx = _get_json(f"{base}/api/contracts/index", timeout=(1.5, 2.5))
            _REGISTRY_CACHE = idx
            endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
        except Exception as e:
            _COOLDOWN_UNTIL_TS = now + max(1.0, _COOLDOWN_S)
            return None, f"registry_unavailable:{str(e)}"
    meta = endpoint_map.get(endpoint_key) if isinstance(endpoint_map.get(endpoint_key), dict) else None
    if meta is None:
        self_heal = str(os.getenv("ECOAIMS_CONTRACT_SELF_HEAL", "1") or "").strip().lower() not in {"0", "false", "no"}
        if self_heal:
            base = _base_url()
            now = time.time()
            if base and now >= _COOLDOWN_UNTIL_TS:
                try:
                    fresh = _get_json(f"{base}/api/contracts/index", timeout=(1.5, 2.5))
                    _REGISTRY_CACHE = fresh
                    fresh_map = fresh.get("endpoint_map") if isinstance(fresh.get("endpoint_map"), dict) else {}
                    meta = fresh_map.get(endpoint_key) if isinstance(fresh_map.get(endpoint_key), dict) else None
                except Exception:
                    meta = None
        if meta is None:
            return None, f"endpoint_not_in_registry_index:{endpoint_key}"
    primary_id = str(meta.get("contract_manifest_id") or "").strip()
    secondary_id = str(meta.get("manifest_id") or "").strip()
    if not primary_id and not secondary_id:
        return None, f"missing_contract_manifest_id_for_endpoint:{endpoint_key}"

    candidates: list[str] = []
    if primary_id:
        candidates.append(primary_id)
    if secondary_id and secondary_id != primary_id:
        candidates.append(secondary_id)

    def _is_usable_for_endpoint(mf: Dict[str, Any]) -> bool:
        if not isinstance(mf, dict) or not mf:
            return False
        endpoints = mf.get("endpoints") if isinstance(mf.get("endpoints"), dict) else {}
        if endpoint_key in endpoints:
            return True
        endpoint_map2 = mf.get("endpoint_map") if isinstance(mf.get("endpoint_map"), dict) else {}
        if endpoint_key in endpoint_map2:
            return True
        required_fields = mf.get("required_fields") if isinstance(mf.get("required_fields"), list) else []
        return bool(required_fields)

    def _fetch_manifest(mid: str, expected_hash: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        cached = _MANIFEST_BY_ID.get(mid)
        if isinstance(cached, dict) and str(cached.get("manifest_id") or "") == mid:
            if expected_hash and str(cached.get("manifest_hash") or "") != expected_hash:
                cached = None
            else:
                return cached, None

        base = _base_url()
        if not base:
            return None, "missing_base_url"
        try:
            mf = _get_json(f"{base}/api/contracts/{mid}", timeout=(1.5, 2.5))
            mh = str(mf.get("manifest_hash") or mf.get("contract_manifest_hash") or "")
            if expected_hash and mh and mh != expected_hash:
                return None, f"manifest_hash_mismatch expected={expected_hash} got={mh}"
            _MANIFEST_BY_ID[mid] = mf
            return mf, None
        except Exception as e:
            return None, f"registry_unavailable:{str(e)}"

    for mid in candidates:
        expected_hash = _expected_manifest_hash_from_registry(mid)
        mf, err = _fetch_manifest(mid, expected_hash)
        if err:
            return None, err
        if isinstance(mf, dict) and _is_usable_for_endpoint(mf):
            return mf, None

    return None, f"endpoint_not_in_manifest:{endpoint_key}"


def _is_number(x: Any) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def _validate_node(node: Dict[str, Any], value: Any, path: str) -> List[str]:
    t = str(node.get("type") or "")
    errs: List[str] = []
    if node.get("nullable") is True and value is None:
        return []
    if t == "object":
        if not isinstance(value, dict):
            return [f"{path}:not_object"]
        req = node.get("required") if isinstance(node.get("required"), dict) else {}
        for k, sub in req.items():
            if k not in value:
                errs.append(f"{path}:missing:{k}")
                continue
            if isinstance(sub, dict):
                errs.extend(_validate_node(sub, value.get(k), f"{path}.{k}"))
    elif t == "list":
        if not isinstance(value, list):
            errs.append(f"{path}:not_list")
        else:
            items = node.get("items") if isinstance(node.get("items"), dict) else None
            if items is not None:
                for i, it in enumerate(value):
                    errs.extend(_validate_node(items, it, f"{path}[{i}]"))
    elif t == "string":
        if not isinstance(value, str):
            errs.append(f"{path}:not_string")
    elif t == "number":
        if not _is_number(value):
            errs.append(f"{path}:not_number")
    elif t in {"bool", "boolean"}:
        if isinstance(value, bool):
            return errs
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "false", "1", "0"}:
                return errs
        errs.append(f"{path}:not_bool")
    else:
        errs.append(f"{path}:unknown_type:{t}")
    return errs


def _type_node_from_keyword(keyword: str) -> Dict[str, Any]:
    k = str(keyword or "").strip().lower()
    if k.endswith("|null"):
        base = k[:-5]
        node = _type_node_from_keyword(base)
        node["nullable"] = True
        return node
    if k.startswith("array[") and k.endswith("]"):
        inner = k[6:-1].strip()
        return {"type": "list", "items": _type_node_from_keyword(inner)}
    if k in {"string", "str"}:
        return {"type": "string"}
    if k in {"number", "float", "int"}:
        return {"type": "number"}
    if k in {"bool", "boolean"}:
        return {"type": "bool"}
    if k in {"list", "array"}:
        return {"type": "list"}
    if k in {"object", "dict"}:
        return {"type": "object", "required": {}}
    return {"type": "string"}


def _spec_from_backend_contract_manifest(backend_contract: Dict[str, Any], endpoint_key: str) -> Optional[Dict[str, Any]]:
    endpoint_map = backend_contract.get("endpoint_map") if isinstance(backend_contract.get("endpoint_map"), dict) else {}
    spec = endpoint_map.get(endpoint_key)
    if not isinstance(spec, dict):
        required_fields = backend_contract.get("required_fields") if isinstance(backend_contract.get("required_fields"), list) else []
        if not required_fields:
            return None
        root_required: Dict[str, Any] = {}
        fields_set = set([str(x) for x in required_fields])
        for f in required_fields:
            field = str(f)
            if field in {"dirty", "ok", "valid", "applied", "saved", "active", "enabled", "fallback_active", "forced_fallback", "forced"}:
                root_required[field] = {"type": "bool"}
                continue
            if field.endswith("_at") or field.endswith("_time") or field.endswith("_ts") or field in {"timestamp", "last_update", "mode"}:
                root_required[field] = {"type": "string", "nullable": True}
                continue
            if field in {"draft", "default", "bundle", "config", "settings"} or (field == "active" and ("draft" in fields_set or "bundle" in fields_set)):
                root_required[field] = {"type": "object", "required": {}}
                continue
            if field in {"warnings", "errors", "reasons"}:
                root_required[field] = {"type": "list", "items": {"type": "string"}}
                continue
            root_required[field] = {"type": "string"}
        return {"type": "object", "required": root_required}
    resp = spec.get("response") if isinstance(spec.get("response"), dict) else {}
    required_fields = resp.get("required_fields") if isinstance(resp.get("required_fields"), list) else []
    nested_shape = {}
    manifest = backend_contract.get("manifest") if isinstance(backend_contract.get("manifest"), dict) else {}
    if isinstance(manifest.get("nested_shape"), dict):
        nested_shape = manifest.get("nested_shape") or {}

    root_required: Dict[str, Any] = {}
    for f in required_fields:
        field = str(f)
        list_key = f"{field}[]"
        if list_key in nested_shape and isinstance(nested_shape.get(list_key), dict):
            item_shape = nested_shape.get(list_key) or {}
            item_req = {str(k): _type_node_from_keyword(v) for k, v in item_shape.items()}
            root_required[field] = {"type": "list", "items": {"type": "object", "required": item_req}}
            continue
        if field in nested_shape:
            ns = nested_shape.get(field)
            if isinstance(ns, dict):
                root_required[field] = {"type": "object", "required": {str(k): _type_node_from_keyword(v) for k, v in ns.items()}}
            else:
                root_required[field] = _type_node_from_keyword(str(ns))
            continue
        if field in {"data_available", "available", "startup_ready", "registry_available", "integration_ready", "final_ok", "verdict_ok", "contract_ok", "hash_ok", "chain_ok", "runtime_ok", "identity_ok"}:
            root_required[field] = {"type": "bool"}
            continue
        if field in {"returned_records_len", "applied_limit", "available_records_len", "records_len"}:
            root_required[field] = {"type": "number"}
            continue
        if field in {"trimmed"}:
            root_required[field] = {"type": "bool"}
            continue
        if field in {"notes", "reasons", "integration_reasons", "canonical_verification_reasons", "canonical_identity_reasons"}:
            root_required[field] = {"type": "list", "items": {"type": "string"}}
            continue
        if field == "summary" or field.endswith("_summary"):
            root_required[field] = {"type": "object", "required": {}}
            continue
        if field in {"input", "backend_identity", "features"}:
            root_required[field] = {"type": "object", "required": {}}
            continue
        root_required[field] = {"type": "string"}

    return {"type": "object", "required": root_required}


def validate_with_registry(endpoint_key: str, payload: Any) -> Tuple[bool, List[str], str]:
    manifest = _MANIFEST_CACHE if isinstance(_MANIFEST_CACHE, dict) else {}
    endpoints = manifest.get("endpoints") if isinstance(manifest.get("endpoints"), dict) else {}
    spec = endpoints.get(endpoint_key)
    if not isinstance(spec, dict):
        backend_spec = _spec_from_backend_contract_manifest(manifest, endpoint_key)
        if not isinstance(backend_spec, dict):
            mf, err = _ensure_manifest_for_endpoint(endpoint_key)
            if err:
                return False, [err], "registry"
            backend_spec = _spec_from_backend_contract_manifest(mf if isinstance(mf, dict) else {}, endpoint_key)
        if not isinstance(backend_spec, dict):
            return False, [f"endpoint_not_in_manifest:{endpoint_key}"], "registry"
        spec = backend_spec
    errs = _validate_node(spec, payload, "$")
    return len(errs) == 0, errs, "registry"


def validate_fallback(endpoint_key: str, payload: Any) -> Tuple[bool, List[str], str]:
    from ecoaims_frontend.services import runtime_contracts

    mapping = {
        "GET /api/energy-data": runtime_contracts.validate_energy_data,
        "POST /optimize": runtime_contracts.validate_optimize_response,
        "GET /api/precooling/zones": runtime_contracts.validate_precooling_zones,
        "GET /api/reports/precooling-impact": runtime_contracts.validate_reports_precooling_impact,
        "GET /api/reports/precooling-impact/history": runtime_contracts.validate_reports_precooling_impact_history,
        "GET /api/reports/precooling-impact/filter-options": runtime_contracts.validate_reports_precooling_impact_filter_options,
        "GET /api/reports/precooling-impact/session-detail": runtime_contracts.validate_reports_precooling_impact_session_detail,
        "GET /api/reports/precooling-impact/session-timeseries": runtime_contracts.validate_reports_precooling_impact_session_timeseries,
    }
    fn = mapping.get(endpoint_key)
    if fn is None:
        return False, [f"no_fallback_validator:{endpoint_key}"], "fallback"
    ok, errs = fn(payload)
    return ok, errs, "fallback"


def validate_endpoint(endpoint_key: str, payload: Any) -> Tuple[bool, List[str], str]:
    from ecoaims_frontend.config import ECOAIMS_REQUIRE_CANONICAL_POLICY

    looks_contracty = isinstance(payload, dict) and any(
        k in payload
        for k in (
            "contract_manifest_id",
            "contract_manifest_version",
            "schema_version",
            "contract_version",
            "manifest_id",
            "manifest_hash",
        )
    )
    manifest = _MANIFEST_CACHE if isinstance(_MANIFEST_CACHE, dict) else {}
    if manifest.get("manifest_id"):
        ok, errs, src = validate_with_registry(endpoint_key, payload)
        if ok:
            return ok, errs, src
        if not ECOAIMS_REQUIRE_CANONICAL_POLICY:
            fallbackable_prefixes = (
                "endpoint_not_in_manifest:",
                "missing_contract_manifest_id_for_endpoint:",
                "endpoint_not_in_registry_index:",
                "registry_unavailable:",
            )
            if any(isinstance(e, str) and e.startswith(fallbackable_prefixes) for e in (errs or [])):
                return validate_fallback(endpoint_key, payload)
        return ok, errs, src
    if looks_contracty:
        ok, errs, src = validate_with_registry(endpoint_key, payload)
        if ok:
            return ok, errs, src
        fallbackable_prefixes = (
            "endpoint_not_in_manifest:",
            "missing_contract_manifest_id_for_endpoint:",
            "endpoint_not_in_registry_index:",
            "registry_unavailable:",
        )
        if any(isinstance(e, str) and e.startswith(fallbackable_prefixes) for e in (errs or [])):
            return validate_fallback(endpoint_key, payload)
        return ok, errs, src
    return validate_fallback(endpoint_key, payload)
