import argparse
import os
import signal
import subprocess
import time


def _pids_listening_on_port(port: int) -> list[int]:
    try:
        r = subprocess.run(
            ["lsof", "-nP", "-iTCP:%d" % int(port), "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []
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


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("ECOAIMS_DASH_PORT") or "8050"))
    ap.add_argument("--timeout-s", type=float, default=2.0)
    args = ap.parse_args()

    port = int(args.port)
    timeout_s = float(args.timeout_s)
    pids = _pids_listening_on_port(port)

    if not pids:
        print(f"stop_frontend_port port={port} pids=[]")
        return 0

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    t0 = time.time()
    while time.time() - t0 < timeout_s:
        remaining = [pid for pid in pids if _is_alive(pid)]
        if not remaining:
            break
        time.sleep(0.1)

    remaining = [pid for pid in pids if _is_alive(pid)]
    if remaining:
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    print(f"stop_frontend_port port={port} pids={pids} remaining={remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
