import os
import time
from uuid import uuid4

_FE_SESSION_ID: str = os.getenv("ECOAIMS_FE_SESSION_ID", "").strip() or uuid4().hex
_FE_BOOT_TS: int = int(os.getenv("ECOAIMS_FE_BOOT_TS", "") or 0) or int(time.time())
_TRACE_HEADERS_ENABLED: bool = str(os.getenv("ECOAIMS_HTTP_TRACE_HEADERS", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}


def trace_headers() -> dict[str, str]:
    if not _TRACE_HEADERS_ENABLED:
        return {}
    build = os.getenv("ECOAIMS_FE_BUILD_ID", "").strip() or f"dev-{_FE_BOOT_TS}"
    out = {
        "X-ECOAIMS-FE-BUILD": build,
        "X-ECOAIMS-FE-SESSION": _FE_SESSION_ID,
    }
    ver = os.getenv("ECOAIMS_FE_VERSION", "").strip()
    if ver:
        out["X-ECOAIMS-FE-VERSION"] = ver
    return out
