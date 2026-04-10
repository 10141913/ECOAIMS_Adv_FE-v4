import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass(frozen=True)
class Target:
    method: str
    path: str
    name: str


def _pct(xs: List[int], p: float) -> int:
    if not xs:
        return 0
    ys = sorted(xs)
    idx = int((len(ys) - 1) * p)
    return int(ys[max(0, min(len(ys) - 1, idx))])


def _sample_append(samples: List[int], total: int, v: int, *, sample_max: int) -> None:
    if len(samples) < sample_max:
        samples.append(v)
        return
    j = random.randint(0, max(0, total - 1))
    if j < sample_max:
        samples[j] = v


def _request(session: requests.Session, base_url: str, target: Target, timeout_s: float) -> Tuple[int, int]:
    url = base_url.rstrip("/") + target.path
    t0 = time.time()
    if target.method == "GET":
        r = session.get(url, timeout=timeout_s)
    elif target.method == "POST":
        payload = {
            "priority": "grid",
            "battery_SOC": 50.0,
            "grid_limit": 100.0,
            "renewable_energy_avail": 100.0,
            "solar_available": 60.0,
            "wind_available": 40.0,
            "demand_energy": 120.0,
        }
        r = session.post(url, json=payload, timeout=timeout_s)
    else:
        raise RuntimeError("unsupported method")
    ms = int((time.time() - t0) * 1000)
    return int(r.status_code), ms


def main() -> int:
    base_url = str(os.getenv("ECOAIMS_LOAD_BASE_URL", "http://127.0.0.1:8008")).strip()
    concurrency = int(os.getenv("ECOAIMS_LOAD_CONCURRENCY", "20"))
    total_requests = int(os.getenv("ECOAIMS_LOAD_TOTAL_REQUESTS", "1000"))
    ramp_up_s = float(os.getenv("ECOAIMS_LOAD_RAMP_UP_S", "10"))
    timeout_s = float(os.getenv("ECOAIMS_LOAD_TIMEOUT_S", "5"))
    sample_max = int(os.getenv("ECOAIMS_LOAD_SAMPLE_MAX", "50000"))

    p95_threshold_ms = int(os.getenv("ECOAIMS_LOAD_P95_THRESHOLD_MS", "0"))
    ratio_429_max = float(os.getenv("ECOAIMS_LOAD_429_RATIO_MAX", "1.0"))
    ratio_err_max = float(os.getenv("ECOAIMS_LOAD_ERROR_RATIO_MAX", "1.0"))
    emit_json = str(os.getenv("ECOAIMS_LOAD_EMIT_JSON", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}

    targets = [
        Target("GET", "/api/contracts/index", "contracts_index"),
        Target("POST", "/optimize", "optimize"),
    ]

    conc = max(1, int(concurrency))
    total = max(1, int(total_requests))
    sample_max = max(100, int(sample_max))

    status_counts: Dict[int, int] = {}
    latency_samples: List[int] = []
    total_done = 0
    errors = 0
    r429 = 0

    session = requests.Session()
    t0 = time.time()

    def _sleep_for_ramp(i: int) -> None:
        if ramp_up_s <= 0:
            return
        slot = float(ramp_up_s) / float(max(1, conc))
        step = int(i % conc)
        time.sleep(slot * float(step))

    def _job(i: int) -> Tuple[int, int]:
        _sleep_for_ramp(i)
        target = targets[i % len(targets)]
        return _request(session, base_url, target, timeout_s)

    with ThreadPoolExecutor(max_workers=conc) as ex:
        futs = [ex.submit(_job, i) for i in range(total)]
        for fut in as_completed(futs):
            try:
                status, ms = fut.result()
            except Exception:
                status, ms = 0, 0
            total_done += 1
            status_counts[status] = int(status_counts.get(status, 0)) + 1
            if status == 429:
                r429 += 1
            if status == 0 or status >= 400:
                if status != 429:
                    errors += 1
            _sample_append(latency_samples, total_done, int(ms), sample_max=sample_max)

    wall_ms = int((time.time() - t0) * 1000)
    p50 = _pct(latency_samples, 0.50)
    p95 = _pct(latency_samples, 0.95)
    p99 = _pct(latency_samples, 0.99)
    mx = max(latency_samples) if latency_samples else 0

    ratio_429 = float(r429) / float(max(1, total_done))
    ratio_err = float(errors) / float(max(1, total_done))

    print(f"LOAD total={total_done} concurrency={conc} wall_ms={wall_ms} p50_ms={p50} p95_ms={p95} p99_ms={p99} max_ms={mx} 429_ratio={ratio_429:.4f} err_ratio={ratio_err:.4f}")
    print("STATUS_COUNTS " + json.dumps({str(k): v for k, v in sorted(status_counts.items(), key=lambda x: x[0])}, sort_keys=True))

    if emit_json:
        out = {
            "base_url": base_url,
            "total": total_done,
            "concurrency": conc,
            "wall_ms": wall_ms,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "max_ms": mx,
            "ratio_429": ratio_429,
            "ratio_err": ratio_err,
            "status_counts": status_counts,
        }
        print("LOAD_JSON " + json.dumps(out, sort_keys=True))

    ok = True
    if p95_threshold_ms > 0 and p95 > p95_threshold_ms:
        ok = False
        print(f"FAIL p95_ms={p95} threshold_ms={p95_threshold_ms}")
    if ratio_429 > ratio_429_max:
        ok = False
        print(f"FAIL 429_ratio={ratio_429:.4f} max={ratio_429_max:.4f}")
    if ratio_err > ratio_err_max:
        ok = False
        print(f"FAIL err_ratio={ratio_err:.4f} max={ratio_err_max:.4f}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

