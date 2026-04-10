import os
import time
from typing import Any, Dict, Tuple

import requests


def _get_json(url: str, timeout: Tuple[float, float]) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    js = r.json()
    return js if isinstance(js, dict) else {"data": js}


def main() -> int:
    base = (os.getenv("ECOAIMS_API_BASE_URL") or "").rstrip("/")
    expected_schema = os.getenv("ECOAIMS_EXPECTED_SCHEMA_VERSION", "startup_info_v1")
    expected_contract = os.getenv("ECOAIMS_EXPECTED_CONTRACT_VERSION", "2026-03-13")
    expect_manifest_id = os.getenv("ECOAIMS_EXPECTED_CONTRACT_MANIFEST_ID")
    expect_manifest_hash = os.getenv("ECOAIMS_EXPECTED_CONTRACT_MANIFEST_HASH")
    require_canonical = str(os.getenv("ECOAIMS_REQUIRE_CANONICAL_POLICY", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    timeout_s = float(os.getenv("WAIT_BACKEND_TIMEOUT_S", "30"))
    poll_s = float(os.getenv("WAIT_BACKEND_POLL_S", "1.0"))

    if not base:
        print("ECOAIMS_API_BASE_URL kosong")
        return 2

    t0 = time.time()
    last_err = None
    while time.time() - t0 < timeout_s:
        try:
            _ = _get_json(f"{base}/health", timeout=(1.5, 2.5))
            info = _get_json(f"{base}/api/startup-info", timeout=(1.5, 2.5))
            schema = str(info.get("schema_version") or "")
            contract = str(info.get("contract_version") or "")
            manifest_id = info.get("contract_manifest_id")
            manifest_hash = info.get("contract_manifest_hash")
            backend_ready = bool(info.get("backend_ready", True))
            schema_ok = schema == expected_schema
            contract_ok = contract == expected_contract
            manifest_ok = True
            if expect_manifest_id is not None:
                manifest_ok = manifest_ok and (manifest_id == expect_manifest_id)
            if expect_manifest_hash is not None:
                manifest_ok = manifest_ok and (manifest_hash == expect_manifest_hash)
            registry_ok = True
            try:
                _ = _get_json(f"{base}/api/contracts/index", timeout=(1.5, 2.5))
                m = _get_json(f"{base}/api/contracts/{manifest_id}", timeout=(1.5, 2.5)) if manifest_id else {}
                if manifest_hash and m.get("manifest_hash") != manifest_hash:
                    registry_ok = False
            except Exception:
                registry_ok = False

            policy_ok = True
            if require_canonical:
                try:
                    ss = _get_json(f"{base}/api/system/status", timeout=(1.5, 2.5))
                    policy_ok = isinstance(ss, dict) and ss.get("overall_status") in {"healthy", "degraded", "blocked"}
                except Exception:
                    policy_ok = False

            if backend_ready and schema_ok and contract_ok and manifest_ok and registry_ok and policy_ok:
                print(f"OK backend_ready schema_version={schema} contract_version={contract} manifest_id={manifest_id} manifest_hash={manifest_hash}")
                return 0
            print(
                "WAIT backend_not_ready "
                f"backend_ready={backend_ready} "
                f"schema={schema} expected_schema={expected_schema} "
                f"contract={contract} expected_contract={expected_contract} "
                f"manifest_id={manifest_id} expected_manifest_id={expect_manifest_id} "
                f"manifest_hash={manifest_hash} expected_manifest_hash={expect_manifest_hash} "
                f"registry_ok={registry_ok} policy_ok={policy_ok} require_canonical={require_canonical}"
            )
        except Exception as e:
            last_err = str(e)
            print(f"WAIT backend_unavailable {last_err}")
        time.sleep(max(0.2, poll_s))

    print(f"TIMEOUT waiting backend ready; last_err={last_err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
