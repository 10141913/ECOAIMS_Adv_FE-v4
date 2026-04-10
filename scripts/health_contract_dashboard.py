#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


_STOP = False


def _on_sig(_sig: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def _now_ts() -> int:
    return int(time.time())


def _safe_read_json(url: str, timeout_s: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw = urllib.request.urlopen(url, timeout=timeout_s).read()
        obj = json.loads(raw.decode("utf-8"))
        if isinstance(obj, dict):
            return obj, None
        return {"__raw__": obj}, None
    except urllib.error.HTTPError as e:
        return None, f"http_error:{e.code}"
    except urllib.error.URLError as e:
        msg = str(getattr(e, "reason", e))
        if "Connection refused" in msg:
            return None, "backend_connection_refused"
        if "timed out" in msg or "timeout" in msg.lower():
            return None, "backend_timeout"
        return None, f"backend_url_error:{msg}"
    except Exception as e:
        return None, f"backend_error:{type(e).__name__}"


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _endpoint_hash(endpoint_keys: list[str]) -> str:
    joined = "\n".join(sorted(endpoint_keys))
    return _sha256_text(joined)


def _normalize_backend_url(s: str) -> str:
    u = str(s or "").strip()
    if not u:
        return ""
    return u[:-1] if u.endswith("/") else u


@dataclass(frozen=True)
class Snapshot:
    ts: int
    fe_url: str
    backend_url: str
    fe_runtime_ok: bool
    backend_health_ok: bool
    schema_version: Optional[str]
    contract_version: Optional[str]
    contract_manifest_id: Optional[str]
    contract_manifest_hash: Optional[str]
    registry_manifest_hash: Optional[str]
    endpoint_map_count: int
    endpoint_map_hash: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "fe_url": self.fe_url,
            "backend_url": self.backend_url,
            "fe_runtime_ok": self.fe_runtime_ok,
            "backend_health_ok": self.backend_health_ok,
            "startup_info": {
                "schema_version": self.schema_version,
                "contract_version": self.contract_version,
                "contract_manifest_id": self.contract_manifest_id,
                "contract_manifest_hash": self.contract_manifest_hash,
            },
            "contracts_index": {
                "registry_manifest_hash": self.registry_manifest_hash,
                "endpoint_map_count": self.endpoint_map_count,
                "endpoint_map_hash": self.endpoint_map_hash,
            },
        }


def _build_snapshot(fe_url: str, backend_url_arg: str, timeout_s: float) -> Tuple[Snapshot, Dict[str, Any]]:
    meta: Dict[str, Any] = {"errors": []}
    fe_url = fe_url.rstrip("/")
    runtime, err = _safe_read_json(f"{fe_url}/__runtime", timeout_s=timeout_s)
    if err:
        meta["errors"].append({"scope": "frontend", "error": err})
    fe_runtime_ok = runtime is not None and err is None
    backend_url = _normalize_backend_url(backend_url_arg)
    if not backend_url and isinstance(runtime, dict):
        backend_url = _normalize_backend_url(str(runtime.get("ecoaims_api_base_url") or ""))
    meta["frontend_runtime"] = runtime or {}
    meta["resolved_backend_url"] = backend_url

    backend_health_ok = False
    schema_version = None
    contract_version = None
    contract_manifest_id = None
    contract_manifest_hash = None
    registry_manifest_hash = None
    endpoint_map_count = 0
    endpoint_map_hash = None

    if backend_url:
        health, herr = _safe_read_json(f"{backend_url}/health", timeout_s=timeout_s)
        if herr:
            meta["errors"].append({"scope": "backend", "endpoint": "/health", "error": herr})
        backend_health_ok = bool(health) and not herr

        startup, serr = _safe_read_json(f"{backend_url}/api/startup-info", timeout_s=timeout_s)
        if serr:
            meta["errors"].append({"scope": "backend", "endpoint": "/api/startup-info", "error": serr})
        if isinstance(startup, dict):
            schema_version = startup.get("schema_version")
            contract_version = startup.get("contract_version")
            contract_manifest_id = startup.get("contract_manifest_id")
            contract_manifest_hash = startup.get("contract_manifest_hash")
        meta["startup_info"] = startup or {}

        idx, ierr = _safe_read_json(f"{backend_url}/api/contracts/index", timeout_s=timeout_s)
        if ierr:
            meta["errors"].append({"scope": "backend", "endpoint": "/api/contracts/index", "error": ierr})
        if isinstance(idx, dict):
            manifests = idx.get("manifests") if isinstance(idx.get("manifests"), list) else []
            if manifests and isinstance(manifests[0], dict):
                registry_manifest_hash = manifests[0].get("manifest_hash")
            endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
            keys = [str(k) for k in endpoint_map.keys()]
            endpoint_map_count = len(keys)
            endpoint_map_hash = _endpoint_hash(keys) if keys else None
            meta["endpoint_keys_sample"] = sorted(keys)[:40]
        meta["contracts_index"] = idx or {}
    else:
        meta["errors"].append({"scope": "backend", "error": "backend_url_missing"})

    snap = Snapshot(
        ts=_now_ts(),
        fe_url=fe_url,
        backend_url=backend_url,
        fe_runtime_ok=fe_runtime_ok,
        backend_health_ok=backend_health_ok,
        schema_version=str(schema_version) if schema_version is not None else None,
        contract_version=str(contract_version) if contract_version is not None else None,
        contract_manifest_id=str(contract_manifest_id) if contract_manifest_id is not None else None,
        contract_manifest_hash=str(contract_manifest_hash) if contract_manifest_hash is not None else None,
        registry_manifest_hash=str(registry_manifest_hash) if registry_manifest_hash is not None else None,
        endpoint_map_count=int(endpoint_map_count),
        endpoint_map_hash=str(endpoint_map_hash) if endpoint_map_hash is not None else None,
    )
    return snap, meta


def _diff(prev: Optional[Snapshot], cur: Snapshot) -> Dict[str, Any]:
    if prev is None:
        return {"first": True}
    changed = []
    for k in (
        "backend_url",
        "fe_runtime_ok",
        "backend_health_ok",
        "schema_version",
        "contract_version",
        "contract_manifest_id",
        "contract_manifest_hash",
        "registry_manifest_hash",
        "endpoint_map_count",
        "endpoint_map_hash",
    ):
        if getattr(prev, k) != getattr(cur, k):
            changed.append(k)
    out: Dict[str, Any] = {"first": False, "changed": changed}
    if "contract_manifest_hash" in changed or "registry_manifest_hash" in changed:
        out["contract_hash_changed"] = True
    if "endpoint_map_hash" in changed or "endpoint_map_count" in changed:
        out["registry_endpoints_changed"] = True
    return out


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_last(path: str) -> Optional[Snapshot]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if not isinstance(obj, dict):
            return None
        return Snapshot(
            ts=int(obj.get("ts") or 0),
            fe_url=str(obj.get("fe_url") or ""),
            backend_url=str(obj.get("backend_url") or ""),
            fe_runtime_ok=bool(obj.get("fe_runtime_ok")),
            backend_health_ok=bool(obj.get("backend_health_ok")),
            schema_version=obj.get("startup_info", {}).get("schema_version") if isinstance(obj.get("startup_info"), dict) else None,
            contract_version=obj.get("startup_info", {}).get("contract_version") if isinstance(obj.get("startup_info"), dict) else None,
            contract_manifest_id=obj.get("startup_info", {}).get("contract_manifest_id") if isinstance(obj.get("startup_info"), dict) else None,
            contract_manifest_hash=obj.get("startup_info", {}).get("contract_manifest_hash") if isinstance(obj.get("startup_info"), dict) else None,
            registry_manifest_hash=obj.get("contracts_index", {}).get("registry_manifest_hash") if isinstance(obj.get("contracts_index"), dict) else None,
            endpoint_map_count=int(obj.get("contracts_index", {}).get("endpoint_map_count") or 0) if isinstance(obj.get("contracts_index"), dict) else 0,
            endpoint_map_hash=obj.get("contracts_index", {}).get("endpoint_map_hash") if isinstance(obj.get("contracts_index"), dict) else None,
        )
    except Exception:
        return None


def _save_last(path: str, snap: Snapshot) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap.to_dict(), f, ensure_ascii=False, sort_keys=True, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fe-url", default=os.getenv("ECOAIMS_FRONTEND_URL", "http://127.0.0.1:8050"))
    ap.add_argument("--backend-url", default=os.getenv("ECOAIMS_API_BASE_URL", ""))
    ap.add_argument("--interval-s", type=float, default=float(os.getenv("ECOAIMS_HEALTH_CONTRACT_INTERVAL_S", "5.0")))
    ap.add_argument("--timeout-s", type=float, default=float(os.getenv("ECOAIMS_HEALTH_CONTRACT_TIMEOUT_S", "3.0")))
    ap.add_argument("--out", default=os.getenv("ECOAIMS_HEALTH_CONTRACT_OUT", ".run/health_contract.jsonl"))
    ap.add_argument("--state", default=os.getenv("ECOAIMS_HEALTH_CONTRACT_STATE", ".run/health_contract_last.json"))
    args = ap.parse_args()

    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)

    prev = _load_last(args.state)
    while not _STOP:
        snap, meta = _build_snapshot(args.fe_url, args.backend_url, timeout_s=float(args.timeout_s))
        d = _diff(prev, snap)
        row = {**snap.to_dict(), "diff": d, "meta": meta}
        _append_jsonl(args.out, row)
        _save_last(args.state, snap)
        prev = snap
        t0 = time.time()
        while not _STOP and (time.time() - t0) < float(args.interval_s):
            time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
