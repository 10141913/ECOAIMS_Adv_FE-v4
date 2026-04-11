import os
import re
import subprocess
import sys
import time

import requests

def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _read_urls_from_logs(timeout_s: float = 45.0) -> tuple[str, str]:
    root = os.getcwd()
    backend_log = os.path.join(root, ".run", "backend.log")
    frontend_log = os.path.join(root, ".run", "frontend.log")

    backend_url = None
    frontend_url = None

    pat_backend = re.compile(r"Uvicorn running on (https?://\S+)")
    pat_frontend = re.compile(r"Dash is running on (https?://\S+)")

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


def _wait_http_ok(url: str, timeout_s: float = 20.0) -> None:
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
    require_canonical = str(os.getenv("ECOAIMS_REQUIRE_CANONICAL_POLICY", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    lane = "canonical_integration" if require_canonical else "local_dev"
    print(f"MODE={lane}")
    expected_identity_id = str(os.getenv("ECOAIMS_EXPECTED_BACKEND_IDENTITY_ID", "ecoaims_backend.canonical_fastapi"))
    expected_repo = str(os.getenv("ECOAIMS_EXPECTED_BACKEND_REPO", "ECO_AIMS"))
    expected_git_sha = str(os.getenv("ECOAIMS_EXPECTED_BACKEND_GIT_SHA", "")).strip()
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("BACKEND_PORT_BASE", "8008")
    env.setdefault("FRONTEND_PORT_BASE", "8050")
    env.setdefault("ECOAIMS_AUTH_ENABLED", "false")
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

    proc = subprocess.Popen(
        ["bash", "./run_dev.sh"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    backend_url = None
    frontend_url = None
    try:
        backend_url, frontend_url = _read_urls_from_logs()
        _wait_http_ok(f"{backend_url.rstrip('/')}/health", timeout_s=25.0)
        r = requests.get(f"{backend_url.rstrip('/')}/api/startup-info", timeout=5)
        _assert(r.status_code == 200, f"startup-info status {r.status_code}")
        js = r.json()
        _assert("schema_version" in js and "contract_version" in js, "startup-info missing schema/contract version")
        _assert("capabilities" in js and isinstance(js["capabilities"], dict), "startup-info missing capabilities object")
        _assert("required_endpoints" in js and "/api/energy-data" in js["required_endpoints"], "startup-info missing required_endpoints /api/energy-data")
        _assert("contract_manifest_id" in js and "contract_manifest_hash" in js, "startup-info missing manifest id/hash")
        bi = js.get("backend_identity") if isinstance(js.get("backend_identity"), dict) else {}
        identity_id = str((bi or {}).get("identity_id") or "")
        repo = str((bi or {}).get("repo") or "")
        git_sha = str((bi or {}).get("git_sha") or "")
        if require_canonical:
            _assert(bool(identity_id), "canonical mode requires startup-info backend_identity.identity_id")
            _assert(identity_id == expected_identity_id, f"canonical backend identity mismatch: expected identity_id={expected_identity_id} got={identity_id}")
            _assert(bool(repo), "canonical mode requires startup-info backend_identity.repo")
            _assert(repo == expected_repo, f"canonical backend identity mismatch: expected repo={expected_repo} got={repo}")
            if expected_git_sha:
                _assert(bool(git_sha), "canonical mode requires startup-info backend_identity.git_sha")
                _assert(git_sha == expected_git_sha, f"canonical backend identity mismatch: expected git_sha={expected_git_sha} got={git_sha}")
        print(f"BACKEND_IDENTITY_OK={'true' if (not require_canonical or (identity_id == expected_identity_id and repo == expected_repo and (not expected_git_sha or git_sha == expected_git_sha))) else 'false'}")
        mid = js.get("contract_manifest_id")
        mh = js.get("contract_manifest_hash")
        r = requests.get(f"{backend_url.rstrip('/')}/api/contracts/index", timeout=5)
        _assert(r.status_code == 200, f"contracts index status {r.status_code}")
        idx = r.json()
        _assert("manifests" in idx and isinstance(idx.get("manifests"), list), "contracts index missing manifests")
        r = requests.get(f"{backend_url.rstrip('/')}/api/contracts/{mid}", timeout=5)
        _assert(r.status_code == 200, f"contracts manifest status {r.status_code}")
        man = r.json()
        _assert(man.get("manifest_hash") == mh, "contracts manifest hash mismatch")
        if require_canonical:
            r = requests.get(f"{backend_url.rstrip('/')}/api/system/status", timeout=5)
            _assert(r.status_code == 200, f"system status required but status {r.status_code}")
        _wait_http_ok(f"{frontend_url.rstrip('/')}/_dash-layout", timeout_s=25.0)
        env2 = os.environ.copy()
        env2["ECOAIMS_API_BASE_URL"] = backend_url
        env2["ECOAIMS_FRONTEND_URL"] = frontend_url
        env2["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true" if require_canonical else "false"
        p = subprocess.run([sys.executable, "scripts/smoke_runtime.py"], env=env2)
        _assert(p.returncode == 0, "runtime smoke gagal")
        log_path = os.path.join(os.getcwd(), ".run", "frontend.log")
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                s = f.read()
            _assert("Duplicate callback outputs" not in s, "Duplicate callback outputs terdeteksi pada frontend.log")
        print(f"PASS {lane}: stack smoke")
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
