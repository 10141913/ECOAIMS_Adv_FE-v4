import os
import subprocess
import sys
import time

import requests


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _wait_http_ok(url: str, timeout_s: float = 25.0) -> None:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=3)
            last = r.status_code
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"timeout waiting for {url} (last_status={last})")


def _read_urls_from_logs(timeout_s: float = 45.0) -> tuple[str, str]:
    import re

    root = os.getcwd()
    backend_log = os.path.join(root, ".run", "backend.log")
    frontend_log = os.path.join(root, ".run", "frontend.log")

    pat_backend = re.compile(r"Uvicorn running on (https?://\S+)")
    pat_frontend = re.compile(r"Dash is running on (https?://\S+)")

    backend_url = None
    frontend_url = None

    t0 = time.time()
    while time.time() - t0 < timeout_s and not (backend_url and frontend_url):
        if backend_url is None and os.path.exists(backend_log):
            try:
                with open(backend_log, "rb") as f:
                    head = f.read(16384)
                    try:
                        f.seek(-16384, os.SEEK_END)
                        tail = f.read(16384)
                    except Exception:
                        tail = b""
                s = (head + b"\n" + tail).decode(errors="ignore")
                m = pat_backend.search(s)
                if m:
                    backend_url = m.group(1).strip()
            except Exception:
                pass
        if frontend_url is None and os.path.exists(frontend_log):
            try:
                with open(frontend_log, "rb") as f:
                    head = f.read(16384)
                    try:
                        f.seek(-16384, os.SEEK_END)
                        tail = f.read(16384)
                    except Exception:
                        tail = b""
                s = (head + b"\n" + tail).decode(errors="ignore")
                m = pat_frontend.search(s)
                if m:
                    frontend_url = m.group(1).strip()
            except Exception:
                pass
        time.sleep(0.25)

    if not backend_url or not frontend_url:
        raise RuntimeError("timeout membaca URL backend/frontend dari log .run/")
    return backend_url, frontend_url


def main() -> int:
    env = os.environ.copy()
    require_canonical = str(os.getenv("ECOAIMS_REQUIRE_CANONICAL_POLICY", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    lane = "canonical_integration" if require_canonical else "local_dev"
    print(f"MODE={lane}")
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("BACKEND_PORT_BASE", "8008")
    env.setdefault("FRONTEND_PORT_BASE", "8050")
    env["ALLOW_LOCAL_SIMULATION_FALLBACK"] = "false"
    env["ECOAIMS_DEBUG_MODE"] = "false"
    env["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true" if require_canonical else "false"

    subprocess.run(["bash", "./stop_dev.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.makedirs(os.path.join(os.getcwd(), ".run"), exist_ok=True)
    for p in (os.path.join(os.getcwd(), ".run", "backend.log"), os.path.join(os.getcwd(), ".run", "frontend.log")):
        try:
            with open(p, "wb"):
                pass
        except Exception:
            pass

    proc = subprocess.Popen(["bash", "./run_dev.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        backend_url, frontend_url = _read_urls_from_logs()
        _wait_http_ok(f"{backend_url.rstrip('/')}/health", timeout_s=25.0)
        _wait_http_ok(f"{frontend_url.rstrip('/')}/_dash-layout", timeout_s=25.0)

        env2 = os.environ.copy()
        env2["ECOAIMS_API_BASE_URL"] = backend_url
        env2["ECOAIMS_FRONTEND_URL"] = frontend_url
        env2["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true" if require_canonical else "false"
        if require_canonical:
            p = subprocess.run([sys.executable, "scripts/smoke_runtime.py"], env=env2)
            _assert(p.returncode == 0, "runtime smoke (canonical) gagal")
        p = subprocess.run([sys.executable, "scripts/smoke_browser.py"], env=env2)
        _assert(p.returncode == 0, "browser smoke gagal")
        print(f"PASS {lane}: browser smoke")
        return 0
    finally:
        subprocess.run(["bash", "./stop_dev.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
