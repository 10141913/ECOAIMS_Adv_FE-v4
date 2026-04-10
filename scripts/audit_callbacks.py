import os
import sys


def main() -> int:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ecoaims_frontend.app import create_app

    app = create_app()
    _ = app.layout

    callback_map = getattr(app, "callback_map", {}) or {}
    if not isinstance(callback_map, dict) or not callback_map:
        raise RuntimeError("callback_map kosong atau tidak valid")

    print(f"OK: callbacks={len(callback_map)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
