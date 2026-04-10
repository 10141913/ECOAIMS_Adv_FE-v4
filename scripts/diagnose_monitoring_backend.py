import os
import sys
from typing import Any, Dict, Optional, Tuple

import requests


def _get(url: str, timeout_s: Tuple[float, float] = (2.5, 5.0)) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[int]]:
    try:
        r = requests.get(url, timeout=timeout_s)
        status = r.status_code
        r.raise_for_status()
        try:
            js = r.json()
        except ValueError:
            return None, "response bukan JSON", status
        if not isinstance(js, dict):
            return {"data": js}, None, status
        return js, None, status
    except requests.Timeout:
        return None, "timeout", None
    except requests.HTTPError as e:
        resp = e.response
        status = resp.status_code if resp is not None else None
        body = ""
        try:
            body = (resp.text or "")[:300] if resp is not None else ""
        except Exception:
            body = ""
        return None, f"http_error status={status} body={body}", status
    except requests.RequestException as e:
        return None, f"request_error {str(e)}", None


def main() -> int:
    base = (os.getenv("ECOAIMS_API_BASE_URL") or "").rstrip("/")
    legacy = (os.getenv("API_BASE_URL") or "").rstrip("/")
    allow_sim = (os.getenv("ALLOW_LOCAL_SIMULATION_FALLBACK") or "").lower() in {"1", "true", "yes"}
    use_real = (os.getenv("USE_REAL_DATA") or "").lower() in {"1", "true", "yes"}

    if not base:
        print("ECOAIMS_API_BASE_URL kosong; Monitoring akan gagal jika USE_REAL_DATA=true dan fallback simulasi nonaktif.")
    else:
        print(f"ECOAIMS_API_BASE_URL={base}")

    if legacy:
        print(f"API_BASE_URL={legacy}")

    print(f"USE_REAL_DATA={use_real}")
    print(f"ALLOW_LOCAL_SIMULATION_FALLBACK={allow_sim}")

    if base:
        _, err, st = _get(f"{base}/health")
        print(f"GET /health -> status={st} err={err}")
        _, err, st = _get(f"{base}/api/energy-data")
        print(f"GET /api/energy-data -> status={st} err={err}")

    if legacy:
        _, err, st = _get(f"{legacy}/api/energy-data")
        print(f"GET legacy /api/energy-data -> status={st} err={err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
