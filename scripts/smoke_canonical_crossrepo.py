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


def main() -> int:
    env = os.environ.copy()
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("FRONTEND_PORT_BASE", "8050")
    env["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true"

    backend_url = os.getenv("ECOAIMS_API_BASE_URL", "").strip()
    be_repo = os.getenv("ECOAIMS_BE_REPO_PATH", "").strip()
    if not backend_url and not be_repo:
        print("ERROR: canonical cross-repo lane requires ECOAIMS_API_BASE_URL or ECOAIMS_BE_REPO_PATH")
        return 2

    proc_be = None
    try:
        if not backend_url and be_repo:
            # Start backend from external repo (must provide canonical app)
            cmd = [sys.executable, "-m", "uvicorn", "ecoaims_backend.devtools.canonical_fastapi_app:app", "--host", env["HOST"], "--port", "8008"]
            proc_be = subprocess.Popen(cmd, cwd=be_repo, env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            backend_url = "http://127.0.0.1:8008"
            _wait_http_ok(f"{backend_url.rstrip('/')}/health", timeout_s=30.0)

        env2 = os.environ.copy()
        env2["ECOAIMS_API_BASE_URL"] = backend_url
        env2["ECOAIMS_FRONTEND_PORT"] = os.getenv("ECOAIMS_FRONTEND_PORT", "8070")
        env2["ECOAIMS_FRONTEND_HOST"] = env["HOST"]
        proc_fe = subprocess.Popen([sys.executable, "-m", "ecoaims_frontend.app"], env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        fe_url = f"http://{env['HOST']}:{env2['ECOAIMS_FRONTEND_PORT']}"
        try:
            _wait_http_ok(f"{fe_url.rstrip('/')}/_dash-layout", timeout_s=25.0)
            e = os.environ.copy()
            e["ECOAIMS_API_BASE_URL"] = backend_url
            e["ECOAIMS_FRONTEND_URL"] = fe_url
            e["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true"
            p = subprocess.run([sys.executable, "scripts/smoke_runtime.py"], env=e)
            _assert(p.returncode == 0, "canonical cross-repo runtime smoke gagal")
            print("PASS canonical_crossrepo: runtime smoke")
            return 0
        finally:
            proc_fe.terminate()
            try:
                proc_fe.wait(timeout=5)
            except Exception:
                proc_fe.kill()
    finally:
        if proc_be is not None:
            try:
                proc_be.terminate()
                proc_be.wait(timeout=5)
            except Exception:
                proc_be.kill()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
