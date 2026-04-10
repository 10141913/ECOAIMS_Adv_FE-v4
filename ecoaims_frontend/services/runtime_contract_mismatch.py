from typing import Any, Dict, List, Optional

from ecoaims_frontend.services import contract_registry


def extract_missing_fields(errors: Any) -> List[str]:
    errs = errors if isinstance(errors, list) else []
    out: List[str] = []
    for e in errs:
        s = str(e or "")
        if "$:missing:" in s:
            out.append(s.split("$:missing:", 1)[1].strip())
            continue
        if "missing:" in s:
            out.append(s.split("missing:", 1)[1].strip().split()[0])
            continue
    return sorted([x for x in out if x])


def expected_contract_label(endpoint_key: str) -> str:
    idx = contract_registry.get_registry_cache()
    endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
    meta = endpoint_map.get(endpoint_key) if isinstance(endpoint_map.get(endpoint_key), dict) else {}
    mid = str(meta.get("contract_manifest_id") or "").strip()
    mh = str(meta.get("contract_manifest_hash") or "").strip()
    if mid and mh:
        return f"{mid}@{mh}"
    if mid:
        return mid
    return "Unknown"


def actual_contract_label(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Unknown"
    mid = payload.get("contract_manifest_id") or payload.get("contract_id") or payload.get("contract_manifest")
    ver = payload.get("contract_manifest_version") or payload.get("contract_version") or payload.get("schema_version")
    mh = payload.get("contract_manifest_hash") or payload.get("contract_hash")
    mid_s = str(mid or "").strip()
    ver_s = str(ver or "").strip()
    mh_s = str(mh or "").strip()
    if mid_s and ver_s:
        return f"{mid_s}@{ver_s}"
    if ver_s:
        return ver_s
    if mid_s and mh_s:
        return f"{mid_s}@{mh_s}"
    if mid_s:
        return mid_s
    return "Unknown"


def build_runtime_endpoint_contract_mismatch(
    *,
    feature: str,
    endpoint_key: str,
    path: str,
    base_url: str,
    errors: Any,
    source: Optional[str] = None,
    payload: Any = None,
) -> Dict[str, Any]:
    errs = errors if isinstance(errors, list) else [str(errors)] if errors else []
    expected = expected_contract_label(endpoint_key)
    actual = actual_contract_label(payload)
    ops = [
        "Pastikan FE dan BE menunjuk instance backend yang sama (base_url).",
        "Cek registry backend: GET /api/contracts/index harus memuat endpoint_key ini.",
        "Restart backend lalu jalankan make doctor-stack di FE agar registry cache segar.",
    ]
    details: Dict[str, Any] = {
        "type": "runtime_endpoint_contract_mismatch",
        "feature": str(feature or ""),
        "endpoint_key": str(endpoint_key or ""),
        "path": str(path or ""),
        "base_url": str(base_url or ""),
        "errors": errs,
        "source": str(source or ""),
        "operator_actions": ops,
        "component_label": f"{feature} ({endpoint_key})",
        "expected_version": expected,
        "actual_version": actual,
        "compatibility": {"reason": "runtime_endpoint_contract_mismatch"},
        "missing_fields": extract_missing_fields(errs),
        "operator_hint": " | ".join(ops),
        "actions": {
            "retry_contract_negotiation": {"enabled": False, "hint": "Belum aktif: negotiation runtime untuk endpoint ini belum tersedia."},
            "switch_to_simulation": {"enabled": False, "hint": "Belum aktif: fallback simulasi dikontrol oleh policy/env."},
            "view_contract_details": {"enabled": False, "hint": "Buka /api/contracts/index dan /api/contracts/{manifest_id} di backend."},
        },
        "technical": {
            "feature": feature,
            "endpoint_key": endpoint_key,
            "path": path,
            "base_url": base_url,
            "source": source,
            "errors": errs,
        },
    }
    return details
