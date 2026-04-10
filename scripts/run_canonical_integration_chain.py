import argparse
import os
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _is_backend_up(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/health", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def _parse_base_url(base_url: str) -> tuple[str, int]:
    u = urlparse(base_url)
    _assert(u.scheme in {"http", "https"}, f"unsupported scheme in ECOAIMS_API_BASE_URL: {base_url}")
    _assert(bool(u.hostname), f"missing hostname in ECOAIMS_API_BASE_URL: {base_url}")
    port = u.port
    if port is None:
        port = 443 if u.scheme == "https" else 80
    return u.hostname, int(port)


def _run(cmd: list[str], *, cwd: str, env: dict[str, str]) -> int:
    p = subprocess.run(cmd, cwd=cwd, env=env, stdout=sys.stdout, stderr=sys.stderr)
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--be-repo-path", default=os.getenv("ECOAIMS_BE_REPO_PATH", ""))
    ap.add_argument("--base-url", default=os.getenv("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008"))
    ap.add_argument("--wait-timeout-s", type=float, default=float(os.getenv("WAIT_BACKEND_TIMEOUT_S", "30")))
    args = ap.parse_args()

    be_repo = os.path.abspath(args.be_repo_path) if args.be_repo_path else ""
    base_url = str(args.base_url or "").rstrip("/")
    _assert(bool(be_repo), "missing ECOAIMS_BE_REPO_PATH (or pass --be-repo-path)")
    _assert(os.path.isdir(be_repo), f"invalid ECOAIMS_BE_REPO_PATH: {be_repo}")
    _assert(bool(base_url), "missing ECOAIMS_API_BASE_URL (or pass --base-url)")

    host, port = _parse_base_url(base_url)
    if _is_backend_up(base_url):
        raise RuntimeError(f"backend already running at {base_url}; stop it or set ECOAIMS_API_BASE_URL to a free port")

    env = dict(os.environ)
    env["ECOAIMS_API_BASE_URL"] = base_url
    env["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true"
    env["PYTHONUNBUFFERED"] = "1"

    be_cmd = ["make", "run-api", f"API_HOST={host}", f"API_PORT={port}"]
    fe_chain_cmd = ["make", "verify-and-emit-canonical-crossrepo-evidence-chain"]

    proc = None
    try:
        proc = subprocess.Popen(be_cmd, cwd=be_repo, env=env, stdout=sys.stdout, stderr=sys.stderr, start_new_session=True)

        env_wait = dict(env)
        env_wait["WAIT_BACKEND_TIMEOUT_S"] = str(args.wait_timeout_s)
        rc = _run([env.get("PYTHON", sys.executable), os.path.join(ROOT_DIR, "scripts", "wait_for_backend_ready.py")], cwd=ROOT_DIR, env=env_wait)
        _assert(rc == 0, f"backend did not become ready (rc={rc})")

        rc2 = _run(fe_chain_cmd, cwd=ROOT_DIR, env=env)
        return int(rc2)
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGINT)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            t0 = time.time()
            while time.time() - t0 < 6.0 and proc.poll() is None:
                time.sleep(0.2)
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
