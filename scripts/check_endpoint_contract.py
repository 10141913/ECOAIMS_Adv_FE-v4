import argparse
import json
import os
import sys
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


_SESSION = requests.Session()


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _parse_endpoint_key(endpoint_key: str) -> Tuple[str, str]:
    ek = str(endpoint_key or "").strip()
    parts = ek.split(" ", 1)
    _assert(len(parts) == 2, f"invalid endpoint_key: {endpoint_key!r} (expected 'METHOD /path')")
    method = parts[0].strip().upper()
    path = parts[1].strip()
    _assert(path.startswith("/"), f"invalid endpoint_key path: {path!r} (must start with /)")
    return method, path


def _norm_base_url(base_url: str) -> str:
    b = str(base_url or "").strip().rstrip("/")
    _assert(bool(b), "missing base_url (use --base-url or set ECOAIMS_API_BASE_URL)")
    u = urlparse(b)
    _assert(u.scheme in {"http", "https"}, f"invalid base_url scheme: {b}")
    _assert(bool(u.hostname), f"invalid base_url host: {b}")
    return b


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        js = resp.json()
        if isinstance(js, dict):
            return js
        return {"data": js}
    except Exception:
        return {"raw": (resp.text or "")[:2000]}


def _call_endpoint(base: str, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base}{path}"
    out: Dict[str, Any] = {"url": url, "method": method, "ok": False, "status": None}
    try:
        if method == "GET":
            r = _SESSION.get(url, timeout=8)
        elif method == "POST":
            r = _SESSION.post(url, json=payload, timeout=12)
        else:
            r = _SESSION.request(method, url, timeout=12)
        out["status"] = int(r.status_code)
        out["json"] = _safe_json(r)
        out["ok"] = r.status_code == 200
        out["exists"] = r.status_code != 404
        return out
    except Exception as e:
        out["error"] = str(e)
        out["exists"] = False
        return out


def _get_registry_index(base: str) -> Dict[str, Any]:
    url = f"{base}/api/contracts/index"
    r = _SESSION.get(url, timeout=10)
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict):
        return js
    return {"data": js}


def _get_manifest(base: str, manifest_id: str) -> Dict[str, Any]:
    url = f"{base}/api/contracts/{manifest_id}"
    r = _SESSION.get(url, timeout=10)
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict):
        return js
    return {"data": js}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8009"))
    ap.add_argument("--endpoint-key", required=True)
    ap.add_argument("--payload-json", default=os.getenv("ECOAIMS_ENDPOINT_PAYLOAD_JSON", "{}"))
    args = ap.parse_args()

    base = _norm_base_url(args.base_url)
    method, path = _parse_endpoint_key(args.endpoint_key)
    try:
        payload = json.loads(args.payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    report: Dict[str, Any] = {
        "base_url": base,
        "endpoint_key": f"{method} {path}",
        "steps": {},
    }

    step1 = _call_endpoint(base, method, path, payload)
    report["steps"]["route"] = step1

    idx_ok = False
    idx: Dict[str, Any] = {}
    try:
        idx = _get_registry_index(base)
        idx_ok = True
    except Exception as e:
        report["steps"]["registry_index"] = {"ok": False, "error": str(e)}
    if idx_ok:
        endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
        meta = endpoint_map.get(f"{method} {path}") if isinstance(endpoint_map.get(f"{method} {path}"), dict) else None
        report["steps"]["registry_index"] = {
            "ok": meta is not None,
            "has_endpoint_key": meta is not None,
            "meta": meta or {},
            "endpoint_map_count": int(len(endpoint_map)),
        }

        manifest_id = ""
        if isinstance(meta, dict):
            manifest_id = str(meta.get("contract_manifest_id") or meta.get("manifest_id") or "").strip()
        report["steps"]["manifest"] = {"ok": False, "manifest_id": manifest_id, "has_endpoint_key": False}
        if manifest_id:
            try:
                mf = _get_manifest(base, manifest_id)
                endpoints = mf.get("endpoints") if isinstance(mf.get("endpoints"), dict) else {}
                report["steps"]["manifest"] = {
                    "ok": True,
                    "manifest_id": manifest_id,
                    "manifest_hash": str(mf.get("manifest_hash") or ""),
                    "has_endpoint_key": f"{method} {path}" in endpoints,
                    "endpoints_count": int(len(endpoints)),
                }
            except Exception as e:
                report["steps"]["manifest"] = {"ok": False, "manifest_id": manifest_id, "error": str(e)}

    rt = step1.get("json") if isinstance(step1, dict) else {}
    rt = rt if isinstance(rt, dict) else {}
    runtime_meta = {
        "contract_manifest_id": rt.get("contract_manifest_id"),
        "contract_manifest_hash": rt.get("contract_manifest_hash"),
        "contract_version": rt.get("contract_version"),
        "schema_version": rt.get("schema_version"),
        "manifest_id": rt.get("manifest_id"),
        "manifest_hash": rt.get("manifest_hash"),
        "manifest_version": rt.get("manifest_version"),
    }
    report["steps"]["runtime_metadata"] = {
        "ok": any(v is not None and str(v).strip() for v in runtime_meta.values()),
        "fields": runtime_meta,
    }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

