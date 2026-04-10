#!/usr/bin/env python3
import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServiceConfig:
    mode: str
    api_host: str
    api_port: int
    fe_host: str
    fe_port: int


def _detect_python(venv_dir: Path) -> Path | None:
    p = venv_dir / "bin" / "python"
    if p.exists():
        return p
    return None


def _detect_be_python(be_repo: Path) -> Path:
    for name in ("venv", ".venv"):
        p = _detect_python(be_repo / name)
        if p:
            return p
    raise SystemExit(f"Tidak menemukan python venv di BE repo: {be_repo} (coba buat venv/ atau .venv/)")


def _detect_fe_python(fe_repo: Path) -> Path:
    for name in ("ecoaims_frontend_env", "venv", ".venv"):
        p = _detect_python(fe_repo / name)
        if p:
            return p
    raise SystemExit(f"Tidak menemukan python env di FE repo: {fe_repo} (cari ecoaims_frontend_env/)")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _launchd_plist(label: str, program_args: list[str], workdir: str, stdout_path: str, stderr_path: str, env: dict[str, str]) -> str:
    def k(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    env_items = []
    for ek, ev in env.items():
        env_items.append(f"      <key>{k(ek)}</key>\n      <string>{k(ev)}</string>")
    env_xml = "\n".join(env_items)

    args_xml = "\n".join([f"    <string>{k(a)}</string>" for a in program_args])
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n"
        "<dict>\n"
        f"  <key>Label</key>\n  <string>{k(label)}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        f"{args_xml}\n"
        "  </array>\n"
        f"  <key>WorkingDirectory</key>\n  <string>{k(workdir)}</string>\n"
        "  <key>RunAtLoad</key>\n  <true/>\n"
        "  <key>KeepAlive</key>\n  <true/>\n"
        "  <key>EnvironmentVariables</key>\n"
        "  <dict>\n"
        f"{env_xml}\n"
        "  </dict>\n"
        f"  <key>StandardOutPath</key>\n  <string>{k(stdout_path)}</string>\n"
        f"  <key>StandardErrorPath</key>\n  <string>{k(stderr_path)}</string>\n"
        "</dict>\n"
        "</plist>\n"
    )


def _systemd_unit(name: str, description: str, workdir: str, exec_start: str, env: dict[str, str]) -> str:
    env_lines = "\n".join([f"Environment={k}={v}" for k, v in env.items()])
    return (
        "[Unit]\n"
        f"Description={description}\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={workdir}\n"
        f"ExecStart={exec_start}\n"
        f"{env_lines}\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _cfg_for_mode(mode: str, api_host: str, api_port: int, fe_host: str, fe_port: int) -> ServiceConfig:
    if mode == "canonical":
        return ServiceConfig(mode=mode, api_host=api_host, api_port=api_port or 8008, fe_host=fe_host, fe_port=fe_port or 8050)
    if mode == "external":
        return ServiceConfig(mode=mode, api_host=api_host, api_port=api_port or 8009, fe_host=fe_host, fe_port=fe_port or 8050)
    if mode == "devtools":
        return ServiceConfig(mode=mode, api_host=api_host, api_port=api_port or 8009, fe_host=fe_host, fe_port=fe_port or 8060)
    raise SystemExit(f"mode tidak dikenal: {mode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["canonical", "external", "devtools"], default="external")
    ap.add_argument("--fe-repo", default=os.getenv("ECOAIMS_FE_REPO", "").strip() or None)
    ap.add_argument("--be-repo", default=os.getenv("ECOAIMS_BE_REPO", "").strip() or None)
    ap.add_argument("--api-host", default="127.0.0.1")
    ap.add_argument("--api-port", type=int, default=0)
    ap.add_argument("--fe-host", default="127.0.0.1")
    ap.add_argument("--fe-port", type=int, default=0)
    ap.add_argument("--out-dir", default="ops/generated")
    args = ap.parse_args()

    fe_repo = Path(args.fe_repo).expanduser().resolve() if args.fe_repo else Path.cwd().resolve()
    if not (fe_repo / "ecoaims_frontend").is_dir():
        raise SystemExit(f"fe-repo tidak valid: {fe_repo}")
    if not args.be_repo:
        raise SystemExit("be-repo wajib (set ECOAIMS_BE_REPO atau pakai --be-repo)")
    be_repo = Path(args.be_repo).expanduser().resolve()
    if not (be_repo / "api" / "qa_scorecard_fastapi.py").exists():
        raise SystemExit(f"be-repo tidak valid: {be_repo}")

    cfg = _cfg_for_mode(args.mode, args.api_host, args.api_port, args.fe_host, args.fe_port)
    api_base_url = f"http://{cfg.api_host}:{cfg.api_port}"

    be_py = _detect_be_python(be_repo)
    fe_py = _detect_fe_python(fe_repo)

    out_root = Path(args.out_dir).expanduser().resolve()
    launchd_dir = out_root / "launchd"
    systemd_dir = out_root / "systemd"
    _ensure_dir(launchd_dir)
    _ensure_dir(systemd_dir)

    logs_dir = out_root / "logs"
    _ensure_dir(logs_dir)

    backend_label = f"com.ecoaims.backend.{cfg.api_port}"
    frontend_label = f"com.ecoaims.frontend.{cfg.fe_port}"

    backend_args = [str(be_py), "-m", "uvicorn", "api.qa_scorecard_fastapi:app", "--host", cfg.api_host, "--port", str(cfg.api_port)]
    backend_env: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
    backend_plist = _launchd_plist(
        backend_label,
        backend_args,
        str(be_repo),
        str(logs_dir / f"{backend_label}.out.log"),
        str(logs_dir / f"{backend_label}.err.log"),
        backend_env,
    )
    (launchd_dir / f"{backend_label}.plist").write_text(backend_plist, encoding="utf-8")

    fe_env: dict[str, str] = {
        "ECOAIMS_API_BASE_URL": api_base_url,
        "ECOAIMS_DASH_HOST": cfg.fe_host,
        "ECOAIMS_DASH_PORT": str(cfg.fe_port),
        "ECOAIMS_DASH_DEBUG": "false",
        "ECOAIMS_DASH_USE_RELOADER": "false",
        "PYTHONUNBUFFERED": "1",
    }
    if cfg.mode != "canonical":
        fe_env["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "false"
        fe_env["ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO"] = "true"
    frontend_args = [str(fe_py), str(fe_repo / "scripts" / "run_frontend_canonical.py")]
    frontend_plist = _launchd_plist(
        frontend_label,
        frontend_args,
        str(fe_repo),
        str(logs_dir / f"{frontend_label}.out.log"),
        str(logs_dir / f"{frontend_label}.err.log"),
        fe_env,
    )
    (launchd_dir / f"{frontend_label}.plist").write_text(frontend_plist, encoding="utf-8")

    backend_exec = " ".join([str(x) for x in backend_args])
    frontend_exec = " ".join([str(x) for x in frontend_args])
    (systemd_dir / f"{backend_label}.service").write_text(
        _systemd_unit(backend_label, f"ECO-AIMS Backend ({cfg.api_port})", str(be_repo), backend_exec, backend_env),
        encoding="utf-8",
    )
    (systemd_dir / f"{frontend_label}.service").write_text(
        _systemd_unit(frontend_label, f"ECO-AIMS Frontend ({cfg.fe_port})", str(fe_repo), frontend_exec, fe_env),
        encoding="utf-8",
    )

    print("OK")
    print(str((launchd_dir / f"{backend_label}.plist").resolve()))
    print(str((launchd_dir / f"{frontend_label}.plist").resolve()))
    print(str((systemd_dir / f"{backend_label}.service").resolve()))
    print(str((systemd_dir / f"{frontend_label}.service").resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
