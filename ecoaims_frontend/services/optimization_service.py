import random
import time
import os
import requests
import logging
import threading
from typing import Dict, List, Tuple
try:
    import pybreaker  # type: ignore
except Exception:
    pybreaker = None
from ecoaims_frontend.config import ALLOW_LOCAL_SIMULATION_FALLBACK, API_BASE_URL, ECOAIMS_API_BASE_URL, USE_REAL_DATA, DEBUG_MODE, ECOAIMS_REQUIRE_CANONICAL_POLICY
from ecoaims_frontend.services.contract_registry import validate_endpoint
from ecoaims_frontend.services.http_trace import trace_headers
from ecoaims_frontend.services.runtime_contract_mismatch import build_runtime_endpoint_contract_mismatch

# Configure logger
logger = logging.getLogger(__name__)
_LAST_OPTIMIZATION_ENDPOINT_CONTRACT: Dict[str, object] = {"status": "unknown", "errors": [], "last_checked_at": None}
_SESSION = requests.Session()
_OPT_CACHE: Dict[tuple, tuple[float, Tuple[Dict[str, float], str]]] = {}
_OPT_CACHE_LOCK = threading.Lock()
_INFLIGHT: Dict[tuple, Dict[str, object]] = {}
_INFLIGHT_LOCK = threading.Lock()
_OPT_CACHE_TTL_BASE_S: float = float(os.getenv("ECOAIMS_OPTIMIZATION_CACHE_TTL_S", "1.0"))
_OPT_CACHE_TTL_MIN_S: float = float(os.getenv("ECOAIMS_OPTIMIZATION_CACHE_TTL_MIN_S", "0.2"))
_OPT_CACHE_TTL_MAX_S: float = float(os.getenv("ECOAIMS_OPTIMIZATION_CACHE_TTL_MAX_S", "3.0"))
_OPT_INFLIGHT_WAIT_S: float = float(os.getenv("ECOAIMS_OPTIMIZATION_INFLIGHT_WAIT_S", "15.0"))
_CB_FAIL_MAX: int = int(os.getenv("ECOAIMS_OPTIMIZATION_CB_FAIL_MAX", "5"))
_CB_RESET_TIMEOUT_S: int = int(os.getenv("ECOAIMS_OPTIMIZATION_CB_RESET_TIMEOUT_S", "30"))
class _CircuitBreakerOpen(Exception):
    pass


class _FallbackBreaker:
    def __init__(self, fail_max: int, reset_timeout: int, name: str):
        self.fail_max = int(fail_max)
        self.reset_timeout = int(reset_timeout)
        self.name = str(name)

    def call(self, func, *args, **kwargs):
        return func(*args, **kwargs)


if pybreaker is not None:
    _BREAKER = pybreaker.CircuitBreaker(fail_max=_CB_FAIL_MAX, reset_timeout=_CB_RESET_TIMEOUT_S, name="optimization_backend")
else:
    _BREAKER = _FallbackBreaker(fail_max=_CB_FAIL_MAX, reset_timeout=_CB_RESET_TIMEOUT_S, name="optimization_backend")

_METRICS_LOCK = threading.Lock()
_METRICS: Dict[str, float] = {
    "requests_total": 0.0,
    "success_total": 0.0,
    "error_total": 0.0,
    "cache_hits_total": 0.0,
    "cache_misses_total": 0.0,
    "dedup_wait_total": 0.0,
    "cb_open_total": 0.0,
    "last_latency_ms": 0.0,
}
_LATENCY_BUCKETS_MS: List[int] = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
_LATENCY_BUCKET_COUNTS: Dict[str, int] = {str(x): 0 for x in _LATENCY_BUCKETS_MS}
_LATENCY_BUCKET_COUNTS["+Inf"] = 0
_LATENCY_SUM_MS: float = 0.0
_LATENCY_COUNT: int = 0


def _metrics_inc(name: str, n: float = 1.0) -> None:
    with _METRICS_LOCK:
        _METRICS[name] = float(_METRICS.get(name) or 0.0) + float(n)


def _metrics_set(name: str, v: float) -> None:
    with _METRICS_LOCK:
        _METRICS[name] = float(v)


def _observe_latency_ms(ms: float) -> None:
    global _LATENCY_SUM_MS, _LATENCY_COUNT
    msv = float(ms)
    with _METRICS_LOCK:
        _LATENCY_SUM_MS += msv
        _LATENCY_COUNT += 1
        placed = False
        for b in _LATENCY_BUCKETS_MS:
            if msv <= float(b):
                _LATENCY_BUCKET_COUNTS[str(b)] = int(_LATENCY_BUCKET_COUNTS.get(str(b)) or 0) + 1
                placed = True
                break
        if not placed:
            _LATENCY_BUCKET_COUNTS["+Inf"] = int(_LATENCY_BUCKET_COUNTS.get("+Inf") or 0) + 1


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(v)))


def _adaptive_ttl_s(priority: str, battery_capacity_usage: float, grid_limit: float, solar_available: float, wind_available: float, total_demand: float) -> float:
    base = float(_OPT_CACHE_TTL_BASE_S)
    if base <= 0:
        return 0.0
    score = 0.0
    score += abs(float(battery_capacity_usage) - 50.0) / 50.0
    score += abs(float(grid_limit) - 100.0) / 100.0
    score += abs(float(solar_available) - 50.0) / 50.0
    score += abs(float(wind_available) - 30.0) / 30.0
    score += abs(float(total_demand) - 100.0) / 100.0
    if str(priority or "") not in {"renewable", "battery", "grid"}:
        score += 0.5
    mult = _clamp(1.5 - (score / 3.0), 0.5, 1.5)
    return _clamp(base * mult, _OPT_CACHE_TTL_MIN_S, _OPT_CACHE_TTL_MAX_S)


def prometheus_metrics_text() -> str:
    with _METRICS_LOCK, _OPT_CACHE_LOCK:
        snap = dict(_METRICS)
        cache_size = len(_OPT_CACHE)
        bucket_counts = dict(_LATENCY_BUCKET_COUNTS)
        latency_sum = float(_LATENCY_SUM_MS)
        latency_count = int(_LATENCY_COUNT)

    lines = [
        "# HELP ecoaims_fe_optimization_requests_total Total optimization requests (frontend).",
        "# TYPE ecoaims_fe_optimization_requests_total counter",
        f"ecoaims_fe_optimization_requests_total {int(snap.get('requests_total') or 0)}",
        "# HELP ecoaims_fe_optimization_success_total Total optimization successes.",
        "# TYPE ecoaims_fe_optimization_success_total counter",
        f"ecoaims_fe_optimization_success_total {int(snap.get('success_total') or 0)}",
        "# HELP ecoaims_fe_optimization_error_total Total optimization errors.",
        "# TYPE ecoaims_fe_optimization_error_total counter",
        f"ecoaims_fe_optimization_error_total {int(snap.get('error_total') or 0)}",
        "# HELP ecoaims_fe_optimization_cache_hits_total Total optimization cache hits.",
        "# TYPE ecoaims_fe_optimization_cache_hits_total counter",
        f"ecoaims_fe_optimization_cache_hits_total {int(snap.get('cache_hits_total') or 0)}",
        "# HELP ecoaims_fe_optimization_cache_misses_total Total optimization cache misses.",
        "# TYPE ecoaims_fe_optimization_cache_misses_total counter",
        f"ecoaims_fe_optimization_cache_misses_total {int(snap.get('cache_misses_total') or 0)}",
        "# HELP ecoaims_fe_optimization_dedup_wait_total Total waits due to in-flight request deduplication.",
        "# TYPE ecoaims_fe_optimization_dedup_wait_total counter",
        f"ecoaims_fe_optimization_dedup_wait_total {int(snap.get('dedup_wait_total') or 0)}",
        "# HELP ecoaims_fe_optimization_cb_open_total Total circuit breaker open rejections.",
        "# TYPE ecoaims_fe_optimization_cb_open_total counter",
        f"ecoaims_fe_optimization_cb_open_total {int(snap.get('cb_open_total') or 0)}",
        "# HELP ecoaims_fe_optimization_last_latency_ms Last optimization end-to-end latency in milliseconds.",
        "# TYPE ecoaims_fe_optimization_last_latency_ms gauge",
        f"ecoaims_fe_optimization_last_latency_ms {float(snap.get('last_latency_ms') or 0.0):.3f}",
        "# HELP ecoaims_fe_optimization_latency_ms Optimization end-to-end latency histogram (milliseconds).",
        "# TYPE ecoaims_fe_optimization_latency_ms histogram",
    ]

    cum = 0
    for b in _LATENCY_BUCKETS_MS:
        cum += int(bucket_counts.get(str(b)) or 0)
        lines.append(f'ecoaims_fe_optimization_latency_ms_bucket{{le="{b}"}} {cum}')
    cum += int(bucket_counts.get("+Inf") or 0)
    lines.append(f'ecoaims_fe_optimization_latency_ms_bucket{{le="+Inf"}} {cum}')
    lines.append(f"ecoaims_fe_optimization_latency_ms_sum {latency_sum:.6f}")
    lines.append(f"ecoaims_fe_optimization_latency_ms_count {latency_count}")

    lines.extend(
        [
            "# HELP ecoaims_fe_optimization_cache_size Current cache size.",
            "# TYPE ecoaims_fe_optimization_cache_size gauge",
            f"ecoaims_fe_optimization_cache_size {cache_size}",
            "# HELP ecoaims_fe_optimization_cache_ttl_base_s Base TTL for optimization cache.",
            "# TYPE ecoaims_fe_optimization_cache_ttl_base_s gauge",
            f"ecoaims_fe_optimization_cache_ttl_base_s {float(_OPT_CACHE_TTL_BASE_S):.6f}",
        ]
    )
    return "\n".join(lines) + "\n"


def _allow_local_simulation() -> bool:
    if not DEBUG_MODE or ECOAIMS_REQUIRE_CANONICAL_POLICY:
        return False
    if not USE_REAL_DATA:
        return True
    return bool(ALLOW_LOCAL_SIMULATION_FALLBACK)


def get_last_optimization_endpoint_contract() -> Dict[str, object]:
    return dict(_LAST_OPTIMIZATION_ENDPOINT_CONTRACT or {})

def run_energy_optimization(
    priority: str,
    battery_capacity_usage: float,
    grid_limit: float = 100.0,
    solar_available: float = 50.0,
    wind_available: float = 30.0,
    biofuel_available: float = 0.0,
    total_demand: float = 100.0,
    skip_backend: bool = False,
    base_url: str | None = None,
) -> Tuple[Dict[str, float], str]:
    """
    Simulates energy distribution optimization based on user priorities.
    Can switch between local simulation and backend API based on config.

    Args:
        priority (str): 'renewable', 'battery', or 'grid'.
        battery_capacity_usage (float): Percentage of battery capacity to use (0-100).
        grid_limit (float): Max grid power available (kW).
        solar_available (float): Available solar power (kW).
        wind_available (float): Available wind power (kW).
        total_demand (float): Total energy demand (kW).

    Returns:
        Tuple[Dict[str, float], str]: 
            - Dictionary of energy source distribution (values in kW).
            - Recommendation string.
    """

    backend_warning = ""
    last_backend_error: Exception | None = None
    global _LAST_OPTIMIZATION_ENDPOINT_CONTRACT
    _metrics_inc("requests_total", 1.0)
    t0_all = time.time()
    now = float(t0_all)
    canonical_base = str(base_url).rstrip("/") if isinstance(base_url, str) and base_url.strip() else str((ECOAIMS_API_BASE_URL or "").rstrip("/"))
    cache_key = (
        str(priority or ""),
        round(float(battery_capacity_usage or 0.0), 4),
        round(float(grid_limit or 0.0), 4),
        round(float(solar_available or 0.0), 4),
        round(float(wind_available or 0.0), 4),
        round(float(biofuel_available or 0.0), 4),
        round(float(total_demand or 0.0), 4),
        bool(skip_backend),
        canonical_base,
        str((API_BASE_URL or "").rstrip("/")),
        bool(ECOAIMS_REQUIRE_CANONICAL_POLICY),
    )
    ttl_s = _adaptive_ttl_s(str(priority or ""), float(battery_capacity_usage or 0.0), float(grid_limit or 0.0), float(solar_available or 0.0), float(wind_available or 0.0), float(total_demand or 0.0))
    if ttl_s > 0:
        with _OPT_CACHE_LOCK:
            cached = _OPT_CACHE.get(cache_key)
            if cached is not None:
                expires_at, val = cached
                if now <= float(expires_at):
                    _metrics_inc("cache_hits_total", 1.0)
                    latency_ms = float((time.time() - t0_all) * 1000.0)
                    _metrics_set("last_latency_ms", latency_ms)
                    _observe_latency_ms(latency_ms)
                    return val
                _OPT_CACHE.pop(cache_key, None)
        _metrics_inc("cache_misses_total", 1.0)
    base_payload = {
        "priority": priority,
        "grid_limit": grid_limit,
        "grid_energy_avail": grid_limit,
        "renewable_energy_avail": solar_available + wind_available,
        "solar_available": solar_available,
        "wind_available": wind_available,
        "solar_component": solar_available,
        "wind_component": wind_available,
        "grid_component": grid_limit,
        "battery_component": float(battery_capacity_usage),
        "demand_energy": total_demand,
    }
    payload_variants: List[Dict[str, object]] = []
    payload_soc_fraction = float(battery_capacity_usage) / 100.0 if float(battery_capacity_usage) > 1.0 else float(battery_capacity_usage)
    payload_soc_fraction = max(0.0, min(1.0, payload_soc_fraction))
    payload_variants.append({**base_payload, "battery_SOC": payload_soc_fraction, "biofuel_energy_avail": float(biofuel_available or 0.0)})
    payload_variants.append({**base_payload, "battery_SOC": payload_soc_fraction})
    payload_variants.append({**base_payload, "battery_SOC": float(battery_capacity_usage)})
    canonical_url = f"{canonical_base}/optimize" if canonical_base else ""
    tried_legacy = False
    if skip_backend and not _allow_local_simulation():
        raise RuntimeError("Optimization backend tidak tersedia dan fallback simulasi lokal nonaktif.")

    owner = False
    ev: threading.Event | None = None
    with _INFLIGHT_LOCK:
        entry = _INFLIGHT.get(cache_key)
        if isinstance(entry, dict) and isinstance(entry.get("event"), threading.Event):
            done_at = float(entry.get("done_at") or 0.0)
            if done_at and (now - done_at) > 10.0:
                _INFLIGHT.pop(cache_key, None)
                entry = None
        if isinstance(entry, dict) and isinstance(entry.get("event"), threading.Event):
            ev = entry.get("event")  # type: ignore[assignment]
        else:
            ev = threading.Event()
            _INFLIGHT[cache_key] = {"event": ev, "result": None, "exc": None, "done_at": 0.0}
            owner = True

    if not owner and ev is not None:
        _metrics_inc("dedup_wait_total", 1.0)
        ok = ev.wait(timeout=float(_OPT_INFLIGHT_WAIT_S))
        with _INFLIGHT_LOCK:
            done = _INFLIGHT.get(cache_key)
        if ok and isinstance(done, dict):
            if done.get("exc") is not None:
                raise done.get("exc")  # type: ignore[misc]
            if done.get("result") is not None:
                latency_ms = float((time.time() - t0_all) * 1000.0)
                _metrics_set("last_latency_ms", latency_ms)
                _observe_latency_ms(latency_ms)
                return done.get("result")  # type: ignore[return-value]
    try:
        if skip_backend:
            raise requests.RequestException("skip_backend")
        def _call_backend(url: str, js: dict) -> requests.Response:
            th = trace_headers()
            return _SESSION.post(url, json=js, timeout=5, **({"headers": th} if th else {}))
        try:
            last_err: Exception | None = None
            resp = None
            for js in payload_variants:
                try:
                    resp = _BREAKER.call(_call_backend, canonical_url, js)  # type: ignore[arg-type]
                    break
                except Exception as e_call:
                    last_err = e_call
            if resp is None:
                raise last_err or requests.RequestException("backend_call_failed")
        except Exception as ecb:
            if pybreaker is not None and isinstance(ecb, pybreaker.CircuitBreakerError):
                _metrics_inc("cb_open_total", 1.0)
                raise requests.RequestException(f"circuit_breaker_open:{ecb}") from ecb
            raise
        resp.raise_for_status()
        data = resp.json()
        ok_shape, shape_errors, source = validate_endpoint("POST /optimize", data)
        if not ok_shape:
            _LAST_OPTIMIZATION_ENDPOINT_CONTRACT = {
                "status": "mismatch",
                "errors": shape_errors,
                "base_url": canonical_base,
                "normalized": build_runtime_endpoint_contract_mismatch(
                    feature="optimization",
                    endpoint_key="POST /optimize",
                    path="/optimize",
                    base_url=canonical_base,
                    errors=shape_errors,
                    source=source,
                    payload=data if isinstance(data, dict) else None,
                ),
                "last_checked_at": int(time.time()),
            }
            raise RuntimeError(f"runtime_endpoint_contract_mismatch:/optimize errors={shape_errors}")
        _LAST_OPTIMIZATION_ENDPOINT_CONTRACT = {"status": "ok", "errors": [], "source": source, "last_checked_at": int(time.time())}
        distribution = data.get("energy_distribution", {}) if isinstance(data, dict) else {}
        recommendation = data.get("recommendation", "") if isinstance(data, dict) else ""
        if not isinstance(recommendation, str) or not recommendation.strip():
            recommendation = "Optimasi berhasil dijalankan via Backend."
        usage: Dict[str, float] = {"Solar PV": 0.0, "Wind Turbine": 0.0, "Biofuel": 0.0, "Battery": 0.0, "PLN/Grid": 0.0}
        if isinstance(distribution, dict):
            if any(k in distribution for k in ("solar", "wind", "battery", "grid", "unmet")):
                usage["Solar PV"] = float(distribution.get("solar") or 0.0)
                usage["Wind Turbine"] = float(distribution.get("wind") or 0.0)
                usage["Battery"] = float(distribution.get("battery") or 0.0)
                usage["PLN/Grid"] = float(distribution.get("grid") or 0.0)
                usage["Biofuel"] = float(distribution.get("biofuel") or distribution.get("Biofuel") or 0.0)
            else:
                bio_v = distribution.get("Biofuel")
                if bio_v is None:
                    bio_v = distribution.get("biofuel")
                usage["Solar PV"] = float(distribution.get("Solar PV") or 0.0)
                usage["Wind Turbine"] = float(distribution.get("Wind Turbine") or 0.0)
                usage["Battery"] = float(distribution.get("Battery") or 0.0)
                usage["PLN/Grid"] = float(distribution.get("PLN/Grid") or 0.0)
                usage["Biofuel"] = float(bio_v or 0.0)
        res = (usage, recommendation)
        if ttl_s > 0:
            with _OPT_CACHE_LOCK:
                _OPT_CACHE[cache_key] = (now + float(ttl_s), res)
        _metrics_inc("success_total", 1.0)
        if owner and ev is not None:
            with _INFLIGHT_LOCK:
                entry = _INFLIGHT.get(cache_key)
                if isinstance(entry, dict):
                    entry["result"] = res
                    entry["done_at"] = time.time()
            ev.set()
        latency_ms = float((time.time() - t0_all) * 1000.0)
        _metrics_set("last_latency_ms", latency_ms)
        _observe_latency_ms(latency_ms)
        return res
    except requests.RequestException as e:
        last_backend_error = e
        if API_BASE_URL:
            try:
                if skip_backend:
                    raise requests.RequestException("skip_backend")
                base = API_BASE_URL.rstrip("/")
                if base.endswith("/api/energy-data"):
                    base = base[: -len("/api/energy-data")]
                elif base.endswith("/energy-data"):
                    base = base[: -len("/energy-data")]
                legacy_url = f"{base}/optimize"
                tried_legacy = True
                logger.warning(f"Optimization fallback ke legacy API_BASE_URL: {legacy_url}")
                def _call_backend2(url: str, js: dict) -> requests.Response:
                    th = trace_headers()
                    return _SESSION.post(url, json=js, timeout=5, **({"headers": th} if th else {}))
                try:
                    last_err2: Exception | None = None
                    resp2 = None
                    for js in payload_variants:
                        try:
                            resp2 = _BREAKER.call(_call_backend2, legacy_url, js)  # type: ignore[arg-type]
                            break
                        except Exception as e_call2:
                            last_err2 = e_call2
                    if resp2 is None:
                        raise last_err2 or requests.RequestException("legacy_backend_call_failed")
                except Exception as ecb2:
                    if pybreaker is not None and isinstance(ecb2, pybreaker.CircuitBreakerError):
                        _metrics_inc("cb_open_total", 1.0)
                        raise requests.RequestException(f"circuit_breaker_open:{ecb2}") from ecb2
                    raise
                resp2.raise_for_status()
                data2 = resp2.json()
                ok_shape2, shape_errors2, source2 = validate_endpoint("POST /optimize", data2)
                if not ok_shape2:
                    legacy_base = str((API_BASE_URL or "").rstrip("/"))
                    _LAST_OPTIMIZATION_ENDPOINT_CONTRACT = {
                        "status": "mismatch",
                        "errors": shape_errors2,
                        "base_url": legacy_base,
                        "normalized": build_runtime_endpoint_contract_mismatch(
                            feature="optimization",
                            endpoint_key="POST /optimize",
                            path="/optimize(legacy)",
                            base_url=legacy_base,
                            errors=shape_errors2,
                            source=source2,
                            payload=data2 if isinstance(data2, dict) else None,
                        ),
                        "last_checked_at": int(time.time()),
                    }
                    raise RuntimeError(f"runtime_endpoint_contract_mismatch:/optimize(legacy) errors={shape_errors2}")
                _LAST_OPTIMIZATION_ENDPOINT_CONTRACT = {"status": "ok", "errors": [], "source": source2, "last_checked_at": int(time.time())}
                distribution2 = data2.get('energy_distribution', {}) if isinstance(data2, dict) else {}
                recommendation2 = data2.get('recommendation', "Optimasi berhasil dijalankan via Backend.") if isinstance(data2, dict) else "Optimasi berhasil dijalankan via Backend."
                bio_v2 = distribution2.get("Biofuel")
                if bio_v2 is None:
                    bio_v2 = distribution2.get("biofuel")
                usage2 = {
                    'Solar PV': float(distribution2.get('Solar PV', 0.0) or 0.0),
                    'Wind Turbine': float(distribution2.get('Wind Turbine', 0.0) or 0.0),
                    'Biofuel': float(bio_v2 or 0.0),
                    'Battery': float(distribution2.get('Battery', 0.0) or 0.0),
                    'PLN/Grid': float(distribution2.get('PLN/Grid', 0.0) or 0.0)
                }
                res2 = (usage2, recommendation2)
                if ttl_s > 0:
                    with _OPT_CACHE_LOCK:
                        _OPT_CACHE[cache_key] = (now + float(ttl_s), res2)
                _metrics_inc("success_total", 1.0)
                if owner and ev is not None:
                    with _INFLIGHT_LOCK:
                        entry = _INFLIGHT.get(cache_key)
                        if isinstance(entry, dict):
                            entry["result"] = res2
                            entry["done_at"] = time.time()
                    ev.set()
                latency_ms = float((time.time() - t0_all) * 1000.0)
                _metrics_set("last_latency_ms", latency_ms)
                _observe_latency_ms(latency_ms)
                return res2
            except requests.RequestException as e2:
                last_backend_error = e2
                logger.warning(f"Optimization gagal memanggil legacy API_BASE_URL: {e2}")
        if not tried_legacy:
            logger.warning(f"Optimization gagal memanggil backend kanonik: {e}")
        _metrics_inc("error_total", 1.0)
        if owner and ev is not None:
            with _INFLIGHT_LOCK:
                entry = _INFLIGHT.get(cache_key)
                if isinstance(entry, dict):
                    entry["exc"] = e
                    entry["done_at"] = time.time()
            ev.set()

    if not _allow_local_simulation():
        if owner and ev is not None:
            with _INFLIGHT_LOCK:
                entry = _INFLIGHT.get(cache_key)
                if isinstance(entry, dict):
                    entry["exc"] = RuntimeError("Gagal menjalankan Optimization melalui backend kanonik dan fallback legacy tidak tersedia.")
                    entry["done_at"] = time.time()
            ev.set()
        raise RuntimeError("Gagal menjalankan Optimization melalui backend kanonik dan fallback legacy tidak tersedia.") from last_backend_error

    backend_warning = " (Simulasi lokal; backend tidak tersedia)"
    
    # --- 2. Local Simulation Logic (Fallback or Default) ---
    
    # Base capacities (simulated for now, could be passed in)
    MAX_BATTERY_CAPACITY_KW = 200.0
    
    # Calculate available battery power based on user slider %
    # Assuming current SOC allows for this discharge
    battery_available = MAX_BATTERY_CAPACITY_KW * (battery_capacity_usage / 100.0)
    
    # Initialize usage
    usage = {
        'Solar PV': 0.0,
        'Wind Turbine': 0.0,
        'Biofuel': 0.0,
        'Battery': 0.0,
        'PLN/Grid': 0.0
    }
    
    remaining_demand = total_demand
    
    # --- Optimization Logic ---
    
    if priority == 'renewable':
        # 1. Use Renewables first
        solar_use = min(remaining_demand, solar_available)
        usage['Solar PV'] = solar_use
        remaining_demand -= solar_use
        
        wind_use = min(remaining_demand, wind_available)
        usage['Wind Turbine'] = wind_use
        remaining_demand -= wind_use

        bio_use = min(remaining_demand, float(biofuel_available or 0.0))
        usage['Biofuel'] = bio_use
        remaining_demand -= bio_use

        # 2. Use Battery second
        batt_use = min(remaining_demand, battery_available)
        usage['Battery'] = batt_use
        remaining_demand -= batt_use
        
        # 3. Use Grid last
        grid_use = min(remaining_demand, grid_limit)
        usage['PLN/Grid'] = grid_use
        remaining_demand -= grid_use
        
        recommendation = (
            "Strategi ini memaksimalkan penggunaan energi hijau. "
            "Sangat baik untuk mengurangi jejak karbon, namun pastikan kapasitas baterai mencukupi saat malam hari."
        )

    elif priority == 'battery':
        # 1. Use Battery first (aggressive discharge)
        batt_use = min(remaining_demand, battery_available)
        usage['Battery'] = batt_use
        remaining_demand -= batt_use
        
        # 2. Use Renewables second
        solar_use = min(remaining_demand, solar_available)
        usage['Solar PV'] = solar_use
        remaining_demand -= solar_use
        
        wind_use = min(remaining_demand, wind_available)
        usage['Wind Turbine'] = wind_use
        remaining_demand -= wind_use

        bio_use = min(remaining_demand, float(biofuel_available or 0.0))
        usage['Biofuel'] = bio_use
        remaining_demand -= bio_use
        
        # 3. Use Grid last
        grid_use = min(remaining_demand, grid_limit)
        usage['PLN/Grid'] = grid_use
        remaining_demand -= grid_use
        
        recommendation = (
            f"Anda memprioritaskan penggunaan baterai (Target: {battery_capacity_usage}% kapasitas). "
            "Ini efektif untuk 'Peak Shaving' saat tarif listrik grid mahal, tetapi dapat memperpendek umur siklus baterai jika sering dilakukan."
        )

    elif priority == 'grid':
        # 1. Use Grid first
        grid_use = min(remaining_demand, grid_limit)
        usage['PLN/Grid'] = grid_use
        remaining_demand -= grid_use
        
        # 2. Use Renewables second (to top up)
        solar_use = min(remaining_demand, solar_available)
        usage['Solar PV'] = solar_use
        remaining_demand -= solar_use
        
        wind_use = min(remaining_demand, wind_available)
        usage['Wind Turbine'] = wind_use
        remaining_demand -= wind_use

        bio_use = min(remaining_demand, float(biofuel_available or 0.0))
        usage['Biofuel'] = bio_use
        remaining_demand -= bio_use
        
        # 3. Use Battery last
        batt_use = min(remaining_demand, battery_available)
        usage['Battery'] = batt_use
        remaining_demand -= batt_use
        
        recommendation = (
            "Prioritas Grid dipilih. Ini menjamin kestabilan pasokan tertinggi, "
            "namun mungkin meningkatkan biaya operasional dan emisi CO2. Energi terbarukan hanya digunakan sebagai pelengkap."
        )
    
    # Handle deficit (if any) - in real world this means blackout or shedding
    # For sim, we just log it or leave it as unserved demand (implicitly 0 in usage dict)
    
    if backend_warning:
        recommendation = f"{recommendation}{backend_warning}"
    res3 = (usage, recommendation)
    if ttl_s > 0:
        with _OPT_CACHE_LOCK:
            _OPT_CACHE[cache_key] = (now + float(ttl_s), res3)
    _metrics_inc("success_total", 1.0)
    if owner and ev is not None:
        with _INFLIGHT_LOCK:
            entry = _INFLIGHT.get(cache_key)
            if isinstance(entry, dict):
                entry["result"] = res3
                entry["done_at"] = time.time()
        ev.set()
    latency_ms = float((time.time() - t0_all) * 1000.0)
    _metrics_set("last_latency_ms", latency_ms)
    _observe_latency_ms(latency_ms)
    return res3
