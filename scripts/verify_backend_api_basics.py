import argparse
import gzip
import json
import os
import sys

import requests


def main() -> int:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    from ecoaims_frontend.services.contract_registry import validate_endpoint

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8010")
    ap.add_argument("--origin", default="http://127.0.0.1:8050")
    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")
    origin = str(args.origin)
    strict = str(os.getenv("ECOAIMS_DOCTOR_STRICT", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}

    ok_all = True
    reasons = []

    paths = ["/health", "/api/contracts/index", "/api/energy-data"]
    if strict:
        paths.append("/dashboard/state")
    for p in paths:
        r = requests.get(base + p, timeout=5)
        if r.status_code != 200:
            ok_all = False
            reasons.append(f"{p}:http_{r.status_code}")
        print(p, r.status_code)
        if r.headers.get("content-type", "").startswith("application/json"):
            js = r.json()
            print(" keys", list(js.keys())[:12])

        if p == "/api/energy-data" and r.status_code == 200:
            js = r.json()
            ok_contract, errs, src = validate_endpoint("GET /api/energy-data", js)
            print(" contract_ok", ok_contract, "source", src)
            if not ok_contract:
                ok_all = False
                reasons.append("energy_data_contract_mismatch")
                print(" contract_errors", errs[:20])

    if strict:
        pre = requests.options(
            base + "/api/energy-data",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
            timeout=5,
        )
        allow_origin = pre.headers.get("access-control-allow-origin")
        cors_ok = pre.status_code in {200, 204} and (allow_origin == origin or allow_origin == "*")
        print("cors_preflight", pre.status_code, allow_origin, pre.headers.get("access-control-allow-methods"))
        if not cors_ok:
            ok_all = False
            reasons.append("cors_preflight_failed")

    if strict:
        payload = {
            "renewable_energy_avail": 100.0,
            "demand_energy": 80.0,
            "battery_SOC": 0.6,
            "grid_energy_avail": 1000.0,
            "priority": "renewable",
        }
        body = gzip.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        r2 = requests.post(
            base + "/optimize",
            data=body,
            headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
            timeout=10,
        )
        out = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {"raw": r2.text}
        print("optimize_gzip", r2.status_code, out.get("status"), out.get("contract_manifest_id"), out.get("error_code"))
        if r2.status_code != 200:
            ok_all = False
            reasons.append(f"optimize_gzip_http_{r2.status_code}")

    print("summary", "OK" if ok_all else "FAIL", "reasons=" + ",".join(reasons))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
