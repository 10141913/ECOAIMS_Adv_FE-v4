import os
import sys
import argparse

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ecoaims_frontend.services.contract_registry import validate_endpoint
from ecoaims_frontend.services.readiness_service import get_backend_readiness


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008"))
    args = ap.parse_args()

    base = str(args.base_url or "").rstrip("/")
    os.environ["ECOAIMS_API_BASE_URL"] = base

    r = get_backend_readiness()
    print("base_url", r.get("base_url"))
    print("expected_schema_version", os.getenv("ECOAIMS_EXPECTED_SCHEMA_VERSION", "startup_info_v1"))
    print("expected_contract_version", os.getenv("ECOAIMS_EXPECTED_CONTRACT_VERSION", "2026-03-13"))
    print("startup_info schema_version", r.get("schema_version"))
    print("startup_info contract_version", r.get("contract_version"))
    print("contract_valid", r.get("contract_valid"))
    if r.get("contract_mismatch_reason"):
        print("contract_mismatch_reason", r.get("contract_mismatch_reason"))
    print("registry_loaded", r.get("registry_loaded"))
    print("registry_version", r.get("registry_version"))
    print("registry_mismatch_reason", r.get("registry_mismatch_reason"))

    try:
        js = requests.get(base + "/api/energy-data", timeout=5).json()
        ok, errs, src = validate_endpoint("GET /api/energy-data", js if isinstance(js, dict) else {"data": js})
        print("energy_data_contract_ok", ok)
        print("energy_data_contract_source", src)
        if not ok:
            print("energy_data_contract_errors", errs[:25])
    except Exception as e:
        print("energy_data_fetch_error", type(e).__name__, str(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
