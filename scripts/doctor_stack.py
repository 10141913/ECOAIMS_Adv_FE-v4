import argparse
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pids_listening_on_port(port: int) -> list[int]:
    r = subprocess.run(
        ["lsof", "-nP", "-iTCP:%d" % int(port), "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return []
    out = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(int(line))
        except Exception:
            continue
    return sorted(set(out))


def _assert_backend_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in {"http", "https"}:
        raise RuntimeError(f"invalid_backend_url_scheme:{url}")
    if not u.netloc:
        raise RuntimeError(f"invalid_backend_url_host:{url}")


def _run_py(args: list[str], env: dict[str, str], *, capture: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )


def _wait_runtime(url: str, timeout_s: float) -> dict:
    t0 = time.time()
    last_err = None
    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=1.5)
            if r.status_code == 200:
                js = r.json()
                return js if isinstance(js, dict) else {"data": js}
            last_err = f"http_{r.status_code}"
        except Exception as e:
            last_err = f"{type(e).__name__}:{e}"
        time.sleep(0.2)
    raise RuntimeError(f"runtime_endpoint_unavailable:{last_err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.getenv("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008"))
    ap.add_argument("--host", default=os.getenv("ECOAIMS_DASH_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("ECOAIMS_DASH_PORT") or "8050"))
    ap.add_argument("--timeout-s", type=float, default=12.0)
    args = ap.parse_args()

    backend = str(args.backend or "").rstrip("/")
    host = str(args.host or "127.0.0.1")
    port = int(args.port)
    _assert_backend_url(backend)

    env = dict(os.environ)
    env["ECOAIMS_API_BASE_URL"] = backend

    print("doctor_stack step=A stop_frontend_port port=%s" % port)
    _run_py(["scripts/stop_frontend_port.py", "--port", str(port)], env=env, capture=False)
    remaining = _pids_listening_on_port(port)
    if remaining:
        print("doctor_stack FAIL port_not_freed port=%s pids=%s" % (port, remaining))
        return 4

    origin = f"http://{host}:{port}"
    print("doctor_stack step=B verify_backend_api_basics backend=%s origin=%s" % (backend, origin))
    proc = _run_py(
        ["scripts/verify_backend_api_basics.py", "--base-url", backend, "--origin", origin],
        env=env,
        capture=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    ok_line = ""
    for line in out.splitlines():
        if line.strip().startswith("summary "):
            ok_line = line.strip()
            break
    print(out.rstrip())
    if "summary OK" not in ok_line:
        print("doctor_stack FAIL backend_check_failed")
        return 2

    print("doctor_stack step=C start_frontend_canonical single_process host=%s port=%s" % (host, port))
    os.makedirs(os.path.join(ROOT_DIR, ".run"), exist_ok=True)
    fe_log = os.path.join(ROOT_DIR, ".run", "frontend_canonical.log")
    fe_env = dict(env)
    fe_env["ECOAIMS_DASH_HOST"] = host
    fe_env["ECOAIMS_DASH_PORT"] = str(port)
    fe_env["ECOAIMS_DASH_DEBUG"] = "false"
    fe_env["ECOAIMS_DASH_USE_RELOADER"] = "false"
    fe_env["PYTHONUNBUFFERED"] = "1"
    with open(fe_log, "a", encoding="utf-8") as f:
        p = subprocess.Popen(
            [sys.executable, "scripts/run_frontend_canonical.py"],
            cwd=ROOT_DIR,
            env=fe_env,
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    runtime_url = f"http://{host}:{port}/__runtime"
    print("doctor_stack step=D wait_runtime url=%s" % runtime_url)
    try:
        runtime = _wait_runtime(runtime_url, timeout_s=float(args.timeout_s))
    except Exception as e:
        print("doctor_stack FAIL runtime_unavailable err=%s log=%s" % (str(e), fe_log))
        return 3

    got_base = str(runtime.get("ecoaims_api_base_url") or "").rstrip("/")
    if got_base != backend:
        print(
            "doctor_stack FAIL runtime_base_url_mismatch expected=%s got=%s runtime_url=%s log=%s"
            % (backend, got_base, runtime_url, fe_log)
        )
        return 3

    print("doctor_stack PASS")
    print("frontend pid=%s started_at=%s dash_port=%s ecoaims_api_base_url=%s" % (runtime.get("pid"), runtime.get("started_at"), runtime.get("dash_port"), got_base))
    print("open_url %s" % origin)
    print("runtime_url %s" % runtime_url)
    print("log %s" % fe_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
