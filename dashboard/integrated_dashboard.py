import os
import subprocess
import sys


def main() -> int:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env.setdefault("ECOAIMS_DASH_HOST", "127.0.0.1")
    env.setdefault("ECOAIMS_DASH_PORT", "8050")
    env.setdefault("ECOAIMS_DASH_DEBUG", "true")
    env.setdefault("ECOAIMS_DASH_USE_RELOADER", "true")
    p = subprocess.run([sys.executable, "-m", "ecoaims_frontend.app"], cwd=root_dir, env=env)
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
