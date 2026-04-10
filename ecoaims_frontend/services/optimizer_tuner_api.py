import time
from typing import Any, Dict, Optional, Tuple

import requests

from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.services.http_trace import trace_headers


_SESSION = requests.Session()


def suggest_tuner(
    context: Optional[Dict[str, Any]] = None,
    *,
    readiness: Optional[Dict[str, Any]] = None,
    base_url: str | None = None,
    mode: str | None = None,
    timeout: Tuple[float, float] = (2.5, 8.0),
) -> Dict[str, Any]:
    base = str(base_url).strip().rstrip("/") if isinstance(base_url, str) and base_url.strip() else effective_base_url(readiness)
    if not base:
        raise RuntimeError("base_url tidak tersedia")
    url = f"{base}/api/optimizer/tuner/suggest"
    ctx = context if isinstance(context, dict) else {}
    m = str(mode).strip() if isinstance(mode, str) and mode.strip() else None
    payload: Dict[str, Any] = {"context": dict(ctx), **dict(ctx)}
    if m is not None:
        payload["mode"] = m
        payload["context"] = {**(payload.get("context") if isinstance(payload.get("context"), dict) else {}), "mode": m}
    th = trace_headers()
    t0 = time.time()
    resp = _SESSION.post(url, json=payload, timeout=timeout, **({"headers": th} if th else {}))
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        body = (resp.text or "").strip()
        raise RuntimeError(f"Respons tuner bukan JSON (HTTP {resp.status_code}): {body[:300]}") from None
    out: Dict[str, Any] = data if isinstance(data, dict) else {"data": data}
    out.setdefault("_meta", {})
    if isinstance(out.get("_meta"), dict):
        out["_meta"].setdefault("latency_ms", float((time.time() - t0) * 1000.0))
        out["_meta"].setdefault("base_url", base)
        out["_meta"].setdefault("path", "/api/optimizer/tuner/suggest")
    return out
