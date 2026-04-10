import time
from typing import Any, Dict, List, Tuple

import requests


def request_history_seed(base_url: str, *, stream_id: str, desired_records: int) -> Dict[str, Any]:
    base = str(base_url or "").rstrip("/")
    desired_records = int(desired_records)
    attempts: List[Dict[str, Any]] = []

    candidates = [
        f"{base}/api/dev/seed-history",
        f"{base}/dev/seed-history",
        f"{base}/diag/monitoring/seed-history",
        f"{base}/diag/seed-history",
    ]

    payload = {"stream_id": str(stream_id), "records": desired_records}
    for url in candidates:
        t0 = time.time()
        try:
            r = requests.post(url, json=payload, timeout=(2.5, 10.0))
            status = int(r.status_code)
            attempts.append(
                {"url": url, "method": "POST", "status": status, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": None, "error": None}
            )
            if status in {200, 201, 202}:
                try:
                    js = r.json()
                    data = js if isinstance(js, dict) else {"data": js}
                except Exception:
                    data = {"raw": (r.text or "")[:2000]}
                return {"ok": True, "attempts": attempts, "result": data, "seed_url": url}
        except requests.Timeout as e:
            attempts.append(
                {"url": url, "method": "POST", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "backend_timeout", "error": str(e)}
            )
        except requests.RequestException as e:
            attempts.append(
                {"url": url, "method": "POST", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": "backend_request_error", "error": str(e)}
            )

    return {
        "ok": False,
        "attempts": attempts,
        "error_class": "seed_endpoint_not_supported",
        "message": "backend tidak menyediakan endpoint seed history via HTTP; gunakan env ECOAIMS_DEV_SEED_HISTORY dan restart backend",
    }
