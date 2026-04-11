import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ecoaims_frontend.services.contract_registry import load_contract_registry, validate_with_registry

def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


_SESSION = requests.Session()

def _ps_sample(pid: int) -> dict:
    try:
        p = subprocess.run(
            ["ps", "-o", "pid=,%cpu=,rss=,vsz=", "-p", str(int(pid))],
            capture_output=True,
            text=True,
            check=False,
        )
        s = (p.stdout or "").strip()
        if not s:
            return {}
        parts = [x for x in s.split() if x.strip()]
        if len(parts) < 4:
            return {}
        return {"pid": int(parts[0]), "cpu": float(parts[1]), "rss_kb": int(parts[2]), "vsz_kb": int(parts[3])}
    except Exception:
        return {}


def _get(url: str) -> requests.Response:
    return _SESSION.get(url, timeout=10)


def _post(url: str, payload: dict) -> requests.Response:
    return _SESSION.post(url, json=payload, timeout=10)

def _wait_http_ok(url: str, timeout_s: float = 15.0) -> None:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        try:
            r = _SESSION.get(url, timeout=2)
            last = r.status_code
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"timeout waiting for {url} (last_status={last})")

def main() -> int:
    backend = (os.getenv("ECOAIMS_API_BASE_URL") or "http://127.0.0.1:8008").rstrip("/")
    frontend = (os.getenv("ECOAIMS_FRONTEND_URL") or "http://127.0.0.1:8050").rstrip("/")
    require_canonical = str(os.getenv("ECOAIMS_REQUIRE_CANONICAL_POLICY", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    expected_lane = "canonical_integration" if require_canonical else "local_dev"
    loop_iters = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_ITERS", "0"))
    loop_sleep_ms = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_SLEEP_MS", "0"))
    loop_targets = str(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_TARGETS", "monitoring,comparison")).strip().lower()
    loop_concurrency = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY", "1"))
    loop_progress_every = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_PROGRESS_EVERY", "500"))
    loop_max_errors = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_MAX_ERRORS", "10"))
    loop_sample_max = int(os.getenv("ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX", "50000"))
    verify_metrics = str(os.getenv("ECOAIMS_SMOKE_VERIFY_METRICS", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}

    r = _get(f"{backend}/health")
    _assert(r.status_code == 200, f"backend /health status {r.status_code}")

    si = _get(f"{backend}/api/startup-info")
    _assert(si.status_code == 200, f"backend /api/startup-info status {si.status_code}")
    info = si.json()
    manifest_id = str((info or {}).get("contract_manifest_id") or "")
    manifest_hash = str((info or {}).get("contract_manifest_hash") or "")
    _assert(manifest_id and manifest_hash, "startup-info missing contract manifest id/hash")
    reg = load_contract_registry(manifest_id, manifest_hash)
    _assert(reg.get("registry_loaded") is True, f"contract registry not loaded: {reg.get('registry_mismatch_reason')}")
    st = _get(f"{backend}/api/system/status")
    if require_canonical:
        _assert(st.status_code == 200, f"canonical integration required but /api/system/status status {st.status_code}")
    if st.status_code == 200:
        sj = st.json()
        _assert(sj.get("overall_status") in {"healthy", "degraded", "blocked"}, "system status missing overall_status")
    elif not require_canonical:
        print("INFO local_dev: /api/system/status unavailable; frontend_fallback policy expected")
    from ecoaims_frontend.services.readiness_service import get_backend_readiness
    rr = get_backend_readiness()
    lane = str(rr.get("verification_lane") or rr.get("integration_mode") or expected_lane)
    verification_ok = rr.get("verification_ok") is True
    backend_identity_ok = rr.get("backend_identity_ok") is True
    reasons = rr.get("verification_reasons") if isinstance(rr.get("verification_reasons"), list) else []
    reasons_s = ",".join([str(x) for x in reasons if str(x).strip()])

    print(f"MODE={lane}")
    print(f"POLICY_SOURCE={rr.get('policy_source')}")
    print(f"INTEGRATION_MODE={rr.get('integration_mode')}")
    print(f"REGISTRY_LOADED={rr.get('registry_loaded')}")
    print(f"CANONICAL_INTEGRATION_OK={rr.get('canonical_integration_ok')}")
    print(f"BACKEND_IDENTITY_OK={backend_identity_ok}")
    print(f"VERIFICATION_OK={verification_ok}")
    print(f"REASONS={reasons_s or '-'}")
    _assert(lane == expected_lane, f"expected MODE={expected_lane}, got MODE={lane}")
    if require_canonical:
        _assert(rr.get("policy_source") == "backend_policy", f"expected backend_policy in canonical mode, got {rr.get('policy_source')}")
        _assert(rr.get("registry_loaded") is True, "expected registry_loaded true in canonical mode")
        _assert(rr.get("canonical_integration_ok") is True, "expected canonical_integration_ok true in canonical mode")
        _assert(backend_identity_ok is True, f"expected backend_identity_ok true in canonical mode, reasons={reasons_s or '-'}")
        _assert(verification_ok is True, f"expected verification_ok true in canonical mode, reasons={reasons_s or '-'}")
    else:
        if st.status_code == 200:
            _assert(rr.get("policy_source") != "frontend_fallback", "expected backend_policy when /api/system/status available")
        else:
            _assert(rr.get("policy_source") == "frontend_fallback", "expected frontend_fallback when /api/system/status unavailable")

    r = _get(f"{backend}/api/energy-data")
    _assert(r.status_code == 200, f"backend /api/energy-data status {r.status_code}")
    js = r.json()
    ok, errs, _src = validate_with_registry("GET /api/energy-data", js)
    _assert(ok, f"backend /api/energy-data shape mismatch: {errs}")

    payload = {
        "priority": "renewable",
        "battery_SOC": 50,
        "grid_energy_avail": 100,
        "renewable_energy_avail": 90,
        "solar_avail": 60,
        "wind_avail": 30,
        "demand_energy": 120,
    }
    r = _post(f"{backend}/optimize", payload)
    _assert(r.status_code == 200, f"backend /optimize status {r.status_code}")
    js = r.json()
    ok, errs, _src = validate_with_registry("POST /optimize", js)
    _assert(ok, f"backend /optimize shape mismatch: {errs}")

    r = requests.get(
        f"{backend}/api/reports/precooling-impact",
        params={"start_date": "2026-03-01", "end_date": "2026-03-07", "granularity": "daily"},
        timeout=10,
    )
    _assert(r.status_code == 200, f"backend /api/reports/precooling-impact status {r.status_code}")
    js = r.json()
    ok, errs, _src = validate_with_registry("GET /api/reports/precooling-impact", js)
    _assert(ok, f"backend /api/reports/precooling-impact shape mismatch: {errs}")

    r = requests.get(
        f"{backend}/api/reports/precooling-impact/history",
        params={"start_date": "2026-03-01", "end_date": "2026-03-07", "granularity": "daily", "period": "week"},
        timeout=10,
    )
    _assert(r.status_code == 200, f"backend /api/reports/precooling-impact/history status {r.status_code}")
    js = r.json()
    ok, errs, _src = validate_with_registry("GET /api/reports/precooling-impact/history", js)
    _assert(ok, f"backend /api/reports/precooling-impact/history shape mismatch: {errs}")
    rows = js.get("rows") if isinstance(js, dict) else None
    if isinstance(rows, list) and rows:
        rid = rows[0].get("row_id")
        if rid:
            r = requests.get(f"{backend}/api/reports/precooling-impact/session-detail", params={"row_id": rid, "period": "week"}, timeout=10)
            _assert(r.status_code == 200, f"backend /api/reports/precooling-impact/session-detail status {r.status_code}")
            dj = r.json()
            ok, errs, _src = validate_with_registry("GET /api/reports/precooling-impact/session-detail", dj)
            _assert(ok, f"backend /api/reports/precooling-impact/session-detail shape mismatch: {errs}")
            r = requests.get(f"{backend}/api/reports/precooling-impact/session-timeseries", params={"row_id": rid, "period": "week"}, timeout=10)
            _assert(r.status_code == 200, f"backend /api/reports/precooling-impact/session-timeseries status {r.status_code}")
            tj = r.json()
            ok, errs, _src = validate_with_registry("GET /api/reports/precooling-impact/session-timeseries", tj)
            _assert(ok, f"backend /api/reports/precooling-impact/session-timeseries shape mismatch: {errs}")

    r = requests.get(
        f"{backend}/api/reports/precooling-impact/export.csv",
        params={"start_date": "2026-03-01", "end_date": "2026-03-07", "granularity": "daily", "period": "week"},
        timeout=10,
    )
    _assert(r.status_code == 200, f"backend /api/reports/precooling-impact/export.csv status {r.status_code}")
    ct = r.headers.get("content-type", "")
    _assert("text/csv" in ct, f"unexpected export content-type: {ct}")

    r = _get(f"{backend}/api/reports/precooling-impact/filter-options")
    _assert(r.status_code == 200, f"backend /api/reports/precooling-impact/filter-options status {r.status_code}")
    js = r.json()
    ok, errs, _src = validate_with_registry("GET /api/reports/precooling-impact/filter-options", js)
    _assert(ok, f"backend /api/reports/precooling-impact/filter-options shape mismatch: {errs}")

    r = _get(f"{frontend}/")
    _assert(r.status_code == 200, f"frontend / status {r.status_code}")
    r = _get(f"{frontend}/_dash-layout")
    _assert(r.status_code == 200, f"frontend /_dash-layout status {r.status_code}")
    r = _get(f"{frontend}/_dash-dependencies")
    _assert(r.status_code == 200, f"frontend /_dash-dependencies status {r.status_code}")

    deps = r.json()

    def _find_cb(output_id: str, output_prop: str) -> dict:
        for cb in deps:
            out = cb.get("output")
            if isinstance(out, str) and f"{output_id}.{output_prop}" in out:
                return cb
        raise RuntimeError(f"callback not found for {output_id}.{output_prop}")

    def _parse_outputs(output_sig: str):
        if output_sig.startswith("..") and output_sig.endswith(".."):
            inner = output_sig[2:-2]
            parts = inner.split("...")
            outs = []
            for p in parts:
                if "." not in p:
                    continue
                cid, prop = p.rsplit(".", 1)
                outs.append({"id": cid, "property": prop})
            return outs
        else:
            cid, prop = output_sig.rsplit(".", 1)
            return {"id": cid, "property": prop}

    def _run_cb(cb: dict, input_values: dict, state_values: dict) -> str:
        inputs = []
        for i in cb.get("inputs", []):
            key = f"{i.get('id')}.{i.get('property')}"
            inputs.append({"id": i.get("id"), "property": i.get("property"), "value": input_values.get(key)})
        state = []
        for s in cb.get("state", []):
            key = f"{s.get('id')}.{s.get('property')}"
            state.append({"id": s.get("id"), "property": s.get("property"), "value": state_values.get(key)})
        changed = []
        for i in cb.get("inputs", []):
            changed.append(f"{i.get('id')}.{i.get('property')}")
        output_sig = cb.get("output")
        _assert(isinstance(output_sig, str) and output_sig, "dash callback output signature missing")
        payload = {
            "output": output_sig,
            "outputs": _parse_outputs(output_sig),
            "inputs": inputs,
            "state": state,
            "changedPropIds": changed,
        }
        r2 = _SESSION.post(f"{frontend}/_dash-update-component", json=payload, timeout=15)
        _assert(r2.status_code == 200, f"dash update status {r2.status_code}")
        return r2.text

    cb_monitor = _find_cb("alert-container", "children")
    txt = _run_cb(
        cb_monitor,
        {"interval-component.n_intervals": 1},
        {
            "trend-data-store.data": [],
            "backend-readiness-store.data": {"backend_reachable": True, "backend_ready": True, "capabilities": {"monitoring": {"ready": True}}, "base_url": backend, "contract_valid": True, "schema_version": "2026-03-13", "contract_version": "v1"},
        },
    )
    _assert("Gagal memuat data Monitoring" not in txt, "unexpected Monitoring error banner when backend up")

    def _metric_value(text: str, key: str) -> float | None:
        for line in (text or "").splitlines():
            if not line or line.startswith("#"):
                continue
            if line.startswith(key + " "):
                parts = [p for p in line.split(" ") if p]
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except Exception:
                        return None
        return None

    if verify_metrics:
        r = _SESSION.get(f"{frontend}/metrics", timeout=5)
        _assert(r.status_code == 200, f"/metrics status {r.status_code}")
        before_txt = r.text or ""
        before_req = _metric_value(before_txt, "ecoaims_fe_optimization_requests_total")
        before_hits = _metric_value(before_txt, "ecoaims_fe_optimization_cache_hits_total")
        before_miss = _metric_value(before_txt, "ecoaims_fe_optimization_cache_misses_total")
        _assert(before_req is not None, "missing metric ecoaims_fe_optimization_requests_total")
        _assert(before_hits is not None, "missing metric ecoaims_fe_optimization_cache_hits_total")
        _assert(before_miss is not None, "missing metric ecoaims_fe_optimization_cache_misses_total")

        cb_opt = _find_cb("opt-recommendation-text", "children")
        readiness_opt = {
            "canonical_policy_required": bool(require_canonical),
            "policy_source": "backend_policy",
            "backend_identity_ok": True,
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "capabilities": {"optimization": {"ready": True}},
        }
        for _i in range(3):
            _ = _run_cb(
                cb_opt,
                {
                    "opt-run-btn.n_clicks": 1,
                    "opt-priority-dropdown.value": "grid",
                    "opt-battery-slider.value": 50,
                    "opt-grid-slider.value": 100,
                },
                {"backend-readiness-store.data": readiness_opt},
            )
        r = _SESSION.get(f"{frontend}/metrics", timeout=5)
        _assert(r.status_code == 200, f"/metrics status {r.status_code}")
        after_txt = r.text or ""
        after_req = _metric_value(after_txt, "ecoaims_fe_optimization_requests_total")
        after_hits = _metric_value(after_txt, "ecoaims_fe_optimization_cache_hits_total")
        after_miss = _metric_value(after_txt, "ecoaims_fe_optimization_cache_misses_total")
        _assert(after_req is not None, "missing metric ecoaims_fe_optimization_requests_total (after)")
        _assert(after_hits is not None, "missing metric ecoaims_fe_optimization_cache_hits_total (after)")
        _assert(after_miss is not None, "missing metric ecoaims_fe_optimization_cache_misses_total (after)")
        _assert(after_req >= (before_req + 1.0), f"expected requests_total to increase: before={before_req} after={after_req}")
        _assert(after_hits >= (before_hits + 1.0), f"expected cache_hits_total to increase: before={before_hits} after={after_hits}")
        _assert(after_miss >= (before_miss + 1.0), f"expected cache_misses_total to increase: before={before_miss} after={after_miss}")
        print(f"METRICS_OK optimization_requests_total_delta={int(after_req - before_req)} cache_hits_delta={int(after_hits - before_hits)} cache_misses_delta={int(after_miss - before_miss)}")

    if loop_iters > 0:
        run_monitoring = "monitoring" in loop_targets
        run_comparison = "comparison" in loop_targets
        cb_comp = _find_cb("renewable-comparison-status", "children") if run_comparison else None

        readiness_ok = {
            "backend_reachable": True,
            "backend_ready": True,
            "capabilities": {"monitoring": {"ready": True}, "comparison": {"ready": True}},
            "base_url": backend,
            "contract_valid": True,
            "schema_version": "2026-03-13",
            "contract_version": "v1",
        }

        mon_lat = []
        comp_lat = []
        err_count = 0
        mon_total = 0
        comp_total = 0
        peak_cpu = 0.0
        peak_rss_kb = 0
        peak_vsz_kb = 0
        t0 = time.time()
        iters = int(loop_iters)
        conc = max(1, int(loop_concurrency))
        progress_every = max(1, int(loop_progress_every))
        max_errors = max(0, int(loop_max_errors))
        sample_max = max(1, int(loop_sample_max))

        def _call_monitor(n: int) -> int:
            ts = time.time()
            _ = _run_cb(
                cb_monitor,
                {"interval-component.n_intervals": n},
                {"trend-data-store.data": [], "backend-readiness-store.data": readiness_ok},
            )
            return int((time.time() - ts) * 1000)

        def _call_comp(n: int) -> int:
            ts = time.time()
            _ = _run_cb(
                cb_comp,
                {"interval-1h.n_intervals": n, "comparison-update-history-btn.n_clicks": 0},
                {"backend-readiness-store.data": readiness_ok, "comparison-update-click-store.data": 0},
            )
            return int((time.time() - ts) * 1000)

        def _sample_append(samples: list[int], total: int, v: int) -> None:
            if len(samples) < sample_max:
                samples.append(v)
                return
            j = random.randint(0, max(0, total - 1))
            if j < sample_max:
                samples[j] = v

        def _tick(ex: ThreadPoolExecutor, base_n: int) -> None:
            nonlocal err_count
            nonlocal mon_total, comp_total
            jobs = []
            fut_kind = {}
            if run_monitoring:
                for j in range(conc):
                    f = ex.submit(_call_monitor, base_n + j)
                    fut_kind[f] = "monitoring"
                    jobs.append(f)
            if run_comparison and cb_comp is not None:
                for j in range(conc):
                    f = ex.submit(_call_comp, base_n + j)
                    fut_kind[f] = "comparison"
                    jobs.append(f)
            for fut in as_completed(jobs):
                try:
                    ms = int(fut.result())
                    if fut_kind.get(fut) == "monitoring":
                        mon_total += 1
                        _sample_append(mon_lat, mon_total, ms)
                    elif fut_kind.get(fut) == "comparison":
                        comp_total += 1
                        _sample_append(comp_lat, comp_total, ms)
                except Exception:
                    err_count += 1
                    if max_errors and err_count >= max_errors:
                        raise

        workers = conc
        if run_monitoring and run_comparison and cb_comp is not None:
            workers = conc * 2
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            for i in range(iters):
                _tick(ex, (i * conc) + 2)
                if (i + 1) % progress_every == 0:
                    wall_ms = int((time.time() - t0) * 1000)
                    samp = _ps_sample(os.getpid())
                    if samp:
                        peak_cpu = max(peak_cpu, float(samp.get("cpu") or 0.0))
                        peak_rss_kb = max(peak_rss_kb, int(samp.get("rss_kb") or 0))
                        peak_vsz_kb = max(peak_vsz_kb, int(samp.get("vsz_kb") or 0))
                    extra = ""
                    if samp:
                        extra = f" cpu={samp.get('cpu')} rss_kb={samp.get('rss_kb')} vsz_kb={samp.get('vsz_kb')}"
                    print(f"DASH_LOOP progress iters={i+1}/{iters} concurrency={conc} errors={err_count} wall_ms={wall_ms}{extra}")
                if loop_sleep_ms > 0:
                    time.sleep(float(loop_sleep_ms) / 1000.0)
        finally:
            ex.shutdown(wait=True)
        wall_ms = int((time.time() - t0) * 1000)

        def _pct(xs: list[int], p: float) -> int:
            if not xs:
                return 0
            ys = sorted(xs)
            idx = int((len(ys) - 1) * p)
            return int(ys[max(0, min(len(ys) - 1, idx))])

        samp = _ps_sample(os.getpid())
        if samp:
            peak_cpu = max(peak_cpu, float(samp.get("cpu") or 0.0))
            peak_rss_kb = max(peak_rss_kb, int(samp.get("rss_kb") or 0))
            peak_vsz_kb = max(peak_vsz_kb, int(samp.get("vsz_kb") or 0))
        print(f"DASH_LOOP done iters={iters} concurrency={conc} errors={err_count} wall_ms={wall_ms} peak_cpu={peak_cpu} peak_rss_kb={peak_rss_kb} peak_vsz_kb={peak_vsz_kb}")
        if mon_lat:
            print(
                f"DASH_LOOP Monitoring total={mon_total} samples={len(mon_lat)} wall_ms={wall_ms} p50_ms={_pct(mon_lat,0.50)} p95_ms={_pct(mon_lat,0.95)} p99_ms={_pct(mon_lat,0.99)} max_ms={max(mon_lat)}"
            )
        if comp_lat:
            print(
                f"DASH_LOOP Comparison total={comp_total} samples={len(comp_lat)} wall_ms={wall_ms} p50_ms={_pct(comp_lat,0.50)} p95_ms={_pct(comp_lat,0.95)} p99_ms={_pct(comp_lat,0.99)} max_ms={max(comp_lat)}"
            )

    env = os.environ.copy()
    env["ECOAIMS_API_BASE_URL"] = "http://127.0.0.1:9999"
    env.pop("API_BASE_URL", None)
    env["USE_REAL_DATA"] = "true"
    env["ALLOW_LOCAL_SIMULATION_FALLBACK"] = "false"
    snippet = r"""
from ecoaims_frontend.services.data_service import get_energy_data
from ecoaims_frontend.services.optimization_service import run_energy_optimization

data = get_energy_data()
if data is not None:
    raise SystemExit("expected None when backend down and local sim disabled")

try:
    run_energy_optimization(priority="renewable", battery_capacity_usage=50, grid_limit=100, solar_available=60, wind_available=30, total_demand=120)
    raise SystemExit("expected optimization to fail when backend down and local sim disabled")
except RuntimeError:
    pass
"""
    p = subprocess.run([sys.executable, "-c", snippet], env=env, capture_output=True, text=True)
    _assert(p.returncode == 0, f"negative fallback test failed: {p.stdout}\n{p.stderr}")

    env2 = os.environ.copy()
    env2["ECOAIMS_API_BASE_URL"] = "http://127.0.0.1:9999"
    env2.pop("API_BASE_URL", None)
    env2["USE_REAL_DATA"] = "true"
    env2["ALLOW_LOCAL_SIMULATION_FALLBACK"] = "false"
    env2["ECOAIMS_AUTH_ENABLED"] = "false"
    env2["ECOAIMS_FRONTEND_PORT"] = "8060"
    env2["ECOAIMS_FRONTEND_HOST"] = "127.0.0.1"

    proc = subprocess.Popen([sys.executable, "-m", "ecoaims_frontend.app"], env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        fe2 = "http://127.0.0.1:8060"
        _wait_http_ok(f"{fe2}/_dash-layout", timeout_s=20.0)
        deps = requests.get(f"{fe2}/_dash-dependencies", timeout=10).json()

        def find_cb(output_id: str, output_prop: str) -> dict:
            for cb in deps:
                out = cb.get("output")
                if isinstance(out, str) and f"{output_id}.{output_prop}" in out:
                    return cb
            raise RuntimeError(f"callback not found for {output_id}.{output_prop}")

        def parse_outputs(output_sig: str):
            if output_sig.startswith("..") and output_sig.endswith(".."):
                inner = output_sig[2:-2]
                parts = inner.split("...")
                outs = []
                for p in parts:
                    if "." not in p:
                        continue
                    cid, prop = p.rsplit(".", 1)
                    outs.append({"id": cid, "property": prop})
                return outs
            else:
                cid, prop = output_sig.rsplit(".", 1)
                return {"id": cid, "property": prop}

        def run_cb(cb: dict, input_values: dict, state_values: dict) -> str:
            inputs = []
            for i in cb.get("inputs", []):
                key = f"{i.get('id')}.{i.get('property')}"
                inputs.append({"id": i.get("id"), "property": i.get("property"), "value": input_values.get(key)})
            state = []
            for s in cb.get("state", []):
                key = f"{s.get('id')}.{s.get('property')}"
                state.append({"id": s.get("id"), "property": s.get("property"), "value": state_values.get(key)})
            changed = []
            for i in cb.get("inputs", []):
                changed.append(f"{i.get('id')}.{i.get('property')}")
            output_sig = cb.get("output")
            if not isinstance(output_sig, str) or not output_sig:
                raise RuntimeError("dash callback output signature missing")
            payload = {
                "output": output_sig,
                "outputs": parse_outputs(output_sig),
                "inputs": inputs,
                "state": state,
                "changedPropIds": changed,
            }
            r = requests.post(f"{fe2}/_dash-update-component", json=payload, timeout=15)
            _assert(r.status_code == 200, f"dash update status {r.status_code}")
            try:
                return r.json()
            except Exception:
                return {"__raw_text__": r.text}

        cb_monitor = find_cb("alert-container", "children")
        resp = run_cb(
            cb_monitor,
            {"interval-component.n_intervals": 1},
            {
                "trend-data-store.data": [],
                "backend-readiness-store.data": {"backend_reachable": True, "backend_ready": True, "capabilities": {}, "base_url": "http://127.0.0.1:9999", "error_class": "backend_connection_refused", "contract_valid": False},
            },
        )
        def _collect_strings(node) -> list[str]:
            out: list[str] = []
            if isinstance(node, str):
                return [node]
            if isinstance(node, list):
                for x in node:
                    out.extend(_collect_strings(x))
                return out
            if isinstance(node, dict):
                for v in node.values():
                    out.extend(_collect_strings(v))
                return out
            return out

        _assert(isinstance(resp, dict) and ("response" in resp or "__raw_text__" in resp), "expected dash callback response for Monitoring")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"PASS {expected_lane}: backend endpoints, frontend endpoints, and policy gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
