import os
import subprocess
import sys


def main() -> int:
    env = dict(os.environ)
    env.setdefault("ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008")
    env.setdefault("ECOAIMS_DASH_HOST", "127.0.0.1")
    env.setdefault("ECOAIMS_DASH_PORT", "8050")
    env.setdefault("ECOAIMS_DASH_DEBUG", "false")
    env.setdefault("ECOAIMS_DASH_USE_RELOADER", "false")
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [sys.executable, "-m", "ecoaims_frontend.app"]
    p = subprocess.run(cmd, env=env)
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
