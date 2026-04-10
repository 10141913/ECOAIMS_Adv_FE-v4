from typing import Any, Dict, Optional

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL


def effective_base_url(readiness: Optional[Dict[str, Any]] = None, *, fallback: Optional[str] = None) -> str:
    r = readiness if isinstance(readiness, dict) else {}
    base = r.get("base_url")
    if isinstance(base, str) and base.strip():
        return base.strip().rstrip("/")
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip().rstrip("/")
    return str(ECOAIMS_API_BASE_URL or "").strip().rstrip("/")

