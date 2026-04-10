#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple


def _is_fe_repo(p: Path) -> bool:
    return (p / "ecoaims_frontend").is_dir() and (p / "Makefile").is_file()


def _is_be_repo(p: Path) -> bool:
    return (p / "api").is_dir() and (p / "api" / "qa_scorecard_fastapi.py").is_file() and (p / "Makefile").is_file()


def _find_repo_root(start: Path) -> Optional[Path]:
    cur = start.resolve()
    for _ in range(30):
        if (cur / "Makefile").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _guess_peer_repo(current: Path, want: str) -> Optional[Path]:
    parent = current.parent
    candidates = []
    if parent.is_dir():
        for c in parent.iterdir():
            if not c.is_dir():
                continue
            name = c.name.lower()
            if want == "fe" and ("adv_fe" in name or "frontend" in name):
                candidates.append(c)
            if want == "be" and ("adv_be" in name or "backend" in name):
                candidates.append(c)
    for c in sorted(candidates):
        if want == "fe" and _is_fe_repo(c):
            return c
        if want == "be" and _is_be_repo(c):
            return c
    return None


def _resolve_repos(cwd: Path, fe_repo_env: Optional[str], be_repo_env: Optional[str]) -> Tuple[Path, Optional[Path]]:
    root = _find_repo_root(cwd) or cwd.resolve()
    fe_repo = None
    be_repo = None

    if fe_repo_env:
        fe_repo = Path(fe_repo_env).expanduser().resolve()
    if be_repo_env:
        be_repo = Path(be_repo_env).expanduser().resolve()

    if fe_repo is None and _is_fe_repo(root):
        fe_repo = root
    if be_repo is None and _is_be_repo(root):
        be_repo = root

    if fe_repo is None:
        if be_repo is not None:
            fe_repo = _guess_peer_repo(be_repo, "fe")
        else:
            fe_repo = _guess_peer_repo(root, "fe")

    if be_repo is None:
        if fe_repo is not None:
            be_repo = _guess_peer_repo(fe_repo, "be")
        else:
            be_repo = _guess_peer_repo(root, "be")

    if fe_repo is None:
        raise SystemExit("Tidak menemukan FE repo. Set ECOAIMS_FE_REPO=/path/ke/ECOAIMS_Adv_FE v-4")

    return fe_repo, be_repo


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=check)


def _url_ok(url: str, timeout_s: float = 2.5) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout_s).read()
        return True
    except Exception:
        return False


def _json_get(url: str, timeout_s: float = 4.0) -> Optional[dict]:
    try:
        raw = urllib.request.urlopen(url, timeout=timeout_s).read()
        j = json.loads(raw.decode("utf-8"))
        return j if isinstance(j, dict) else None
    except Exception:
        return None


def cmd_up(args: argparse.Namespace, fe_repo: Path, be_repo: Optional[Path]) -> int:
    if args.mode == "canonical":
        env = os.environ.copy()
        env["NO_OPEN"] = "1" if args.no_open else env.get("NO_OPEN", "0")
        subprocess.run(["make", "stack-canonical"], cwd=str(fe_repo), env=env, check=True)
        return 0

    if args.mode == "devtools":
        env = os.environ.copy()
        env["NO_OPEN"] = "1" if args.no_open else env.get("NO_OPEN", "0")
        subprocess.run(["make", "stack-devtools"], cwd=str(fe_repo), env=env, check=True)
        return 0

    if args.mode == "external":
        if not args.backend_url:
            raise SystemExit("--backend-url wajib untuk mode external")
        env = os.environ.copy()
        env["ECOAIMS_API_BASE_URL_CANONICAL"] = args.backend_url
        env["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "false"
        env["ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO"] = "true"
        env["FE_HOST"] = args.fe_host
        env["FE_PORT"] = str(args.fe_port)
        subprocess.run(["make", "run-frontend-canonical"], cwd=str(fe_repo), env=env, check=True)
        return 0

    raise SystemExit(f"mode tidak dikenal: {args.mode}")


def cmd_down(args: argparse.Namespace, fe_repo: Path, be_repo: Optional[Path]) -> int:
    env = os.environ.copy()
    env["FE_PORT"] = str(args.fe_port)
    subprocess.run(["make", "stop-frontend"], cwd=str(fe_repo), env=env, check=False)

    if args.mode in {"canonical", "all"}:
        subprocess.run(["bash", "-lc", "lsof -nP -iTCP:8008 -sTCP:LISTEN -t | xargs kill -9 >/dev/null 2>&1 || true"], cwd=str(fe_repo), check=False)
    if args.mode in {"devtools", "all"}:
        subprocess.run(["bash", "-lc", "lsof -nP -iTCP:8009 -sTCP:LISTEN -t | xargs kill -9 >/dev/null 2>&1 || true"], cwd=str(fe_repo), check=False)
    if args.mode == "external":
        if args.kill_backend and args.backend_url:
            try:
                port = int(args.backend_url.rstrip("/").split(":")[-1])
                subprocess.run(["bash", "-lc", f"lsof -nP -iTCP:{port} -sTCP:LISTEN -t | xargs kill -9 >/dev/null 2>&1 || true"], cwd=str(fe_repo), check=False)
            except Exception:
                pass
    return 0


def cmd_restart(args: argparse.Namespace, fe_repo: Path, be_repo: Optional[Path]) -> int:
    cmd_down(args, fe_repo, be_repo)
    time.sleep(0.6)
    return cmd_up(args, fe_repo, be_repo)


def cmd_status(args: argparse.Namespace, fe_repo: Path, be_repo: Optional[Path]) -> int:
    fe = f"http://{args.fe_host}:{args.fe_port}"
    runtime = _json_get(fe + "/__runtime")
    ok_fe = runtime is not None

    be_url = args.backend_url
    if not be_url and isinstance(runtime, dict):
        be_url = runtime.get("ecoaims_api_base_url")

    ok_be_health = bool(be_url) and _url_ok(str(be_url).rstrip("/") + "/health")
    out = {
        "fe": {"url": fe, "runtime_ok": ok_fe, "runtime": runtime},
        "be": {"base_url": be_url, "health_ok": ok_be_health},
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if ok_fe else 1


def main() -> int:
    p = argparse.ArgumentParser(prog="ecoaims", add_help=True)
    p.add_argument("command", choices=["up", "down", "restart", "status"])
    p.add_argument("--mode", choices=["canonical", "devtools", "external", "all"], default="canonical")
    p.add_argument("--backend-url", default=os.getenv("ECOAIMS_API_BASE_URL", "").strip() or None)
    p.add_argument("--fe-host", default=os.getenv("FE_HOST", "127.0.0.1"))
    p.add_argument("--fe-port", type=int, default=int(os.getenv("FE_PORT", "8050")))
    p.add_argument("--kill-backend", action="store_true", default=False)
    p.add_argument("--no-open", action="store_true", default=True)
    args = p.parse_args()

    fe_repo, be_repo = _resolve_repos(Path.cwd(), os.getenv("ECOAIMS_FE_REPO"), os.getenv("ECOAIMS_BE_REPO"))
    if args.command == "up":
        return cmd_up(args, fe_repo, be_repo)
    if args.command == "down":
        return cmd_down(args, fe_repo, be_repo)
    if args.command == "restart":
        return cmd_restart(args, fe_repo, be_repo)
    if args.command == "status":
        return cmd_status(args, fe_repo, be_repo)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
