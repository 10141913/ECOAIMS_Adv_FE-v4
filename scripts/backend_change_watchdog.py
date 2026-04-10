#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _endpoint_map_hash(idx: Dict[str, Any]) -> str:
    endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
    keys = sorted([str(k) for k in endpoint_map.keys()])
    return _sha256_text("\n".join(keys))


def _get_json(url: str, timeout_s: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw = urllib.request.urlopen(url, timeout=timeout_s).read()
        obj = json.loads(raw.decode("utf-8"))
        if isinstance(obj, dict):
            return obj, None
        return None, "not_object"
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


def _normalize_url(u: str) -> str:
    s = str(u or "").strip()
    return s[:-1] if s.endswith("/") else s


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent


def _run_make(target: str, *, backend: str, cwd: Path) -> int:
    env = os.environ.copy()
    env["BACKEND"] = backend
    p = subprocess.run(["make", target], cwd=str(cwd), env=env)
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.getenv("BACKEND", "").strip() or os.getenv("ECOAIMS_API_BASE_URL", "").strip() or "http://127.0.0.1:8008")
    ap.add_argument("--interval-s", type=float, default=float(os.getenv("ECOAIMS_WATCH_INTERVAL_S", "5.0")))
    ap.add_argument("--timeout-s", type=float, default=float(os.getenv("ECOAIMS_WATCH_TIMEOUT_S", "3.0")))
    ap.add_argument("--cooldown-s", type=float, default=float(os.getenv("ECOAIMS_WATCH_COOLDOWN_S", "20.0")))
    ap.add_argument("--with-smoke", action="store_true", default=False)
    args = ap.parse_args()

    backend = _normalize_url(args.backend)
    if not backend:
        print("BACKEND/base_url kosong", file=sys.stderr)
        return 2

    cwd = _repo_root()
    last_change_ts = 0.0
    last_sig: Dict[str, str] = {}
    while True:
        startup, e1 = _get_json(f"{backend}/api/startup-info", timeout_s=float(args.timeout_s))
        idx, e2 = _get_json(f"{backend}/api/contracts/index", timeout_s=float(args.timeout_s))
        if e1 or e2 or not isinstance(startup, dict) or not isinstance(idx, dict):
            time.sleep(max(0.5, float(args.interval_s)))
            continue

        sig = {
            "contract_manifest_hash": str(startup.get("contract_manifest_hash") or ""),
            "contract_version": str(startup.get("contract_version") or ""),
            "registry_manifest_hash": str((idx.get("manifests")[0].get("manifest_hash") if isinstance(idx.get("manifests"), list) and idx.get("manifests") and isinstance(idx.get("manifests")[0], dict) else "") or ""),
            "endpoint_map_hash": _endpoint_map_hash(idx),
        }

        if last_sig and sig != last_sig:
            now = time.time()
            if (now - last_change_ts) >= float(args.cooldown_s):
                last_change_ts = now
                rc = _run_make("doctor-stack", backend=backend, cwd=cwd)
                if rc == 0 and bool(args.with_smoke):
                    _run_make("smoke", backend=backend, cwd=cwd)
        last_sig = sig
        time.sleep(max(0.5, float(args.interval_s)))


if __name__ == "__main__":
    raise SystemExit(main())
