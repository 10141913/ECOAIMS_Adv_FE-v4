import time
from typing import Any, Dict, Optional, Tuple

import requests

from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.services.http_trace import trace_headers


_SESSION = requests.Session()


def propose_policy_action(
    context: Optional[Dict[str, Any]] = None,
    *,
    readiness: Optional[Dict[str, Any]] = None,
    base_url: str | None = None,
    timeout: Tuple[float, float] = (2.5, 8.0),
) -> Dict[str, Any]:
    base = str(base_url).strip().rstrip("/") if isinstance(base_url, str) and base_url.strip() else effective_base_url(readiness)
    if not base:
        raise RuntimeError("base_url tidak tersedia")
    url = f"{base}/api/optimizer/policy/propose"
    ctx = context if isinstance(context, dict) else {}

    def _num(v: Any) -> float | None:
        try:
            return float(v)
        except Exception:
            return None

    soc = _num(ctx.get("soc"))
    if soc is None:
        soc = 0.5
    soc = max(0.0, min(1.0, float(soc)))

    demand_total_kwh = _num(ctx.get("demand_total_kwh"))
    if demand_total_kwh is None:
        demand_total_kwh = 0.0
    demand_total_kwh = max(0.0, float(demand_total_kwh))

    renewable_potential_kwh = _num(ctx.get("renewable_potential_kwh"))
    if renewable_potential_kwh is None:
        renewable_potential_kwh = 0.0
    renewable_potential_kwh = max(0.0, float(renewable_potential_kwh))

    grid_cost_per_kwh = _num(ctx.get("grid_cost_per_kwh"))
    if grid_cost_per_kwh is None:
        grid_cost_per_kwh = _num(ctx.get("tariff"))

    grid_emission_kg_per_kwh = _num(ctx.get("grid_emission_kg_per_kwh"))
    if grid_emission_kg_per_kwh is None:
        grid_emission_kg_per_kwh = _num(ctx.get("emission_factor"))

    payload: Dict[str, Any] = {
        "soc": soc,
        "demand_total_kwh": demand_total_kwh,
        "renewable_potential_kwh": renewable_potential_kwh,
    }
    if grid_cost_per_kwh is not None:
        payload["grid_cost_per_kwh"] = float(grid_cost_per_kwh)
    if grid_emission_kg_per_kwh is not None:
        payload["grid_emission_kg_per_kwh"] = float(grid_emission_kg_per_kwh)
    if isinstance(ctx.get("timestamp"), str) and str(ctx.get("timestamp")).strip():
        payload["timestamp"] = str(ctx.get("timestamp")).strip()
    if isinstance(ctx.get("hour"), (int, float)):
        try:
            payload["hour"] = int(ctx.get("hour"))
        except Exception:
            pass
    th = trace_headers()
    t0 = time.time()
    resp = _SESSION.post(url, json=payload, timeout=timeout, **({"headers": th} if th else {}))
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        body = (resp.text or "").strip()
        raise RuntimeError(f"Respons policy proposer bukan JSON (HTTP {resp.status_code}): {body[:300]}") from None
    out: Dict[str, Any] = data if isinstance(data, dict) else {"data": data}
    out.setdefault("_meta", {})
    if isinstance(out.get("_meta"), dict):
        out["_meta"].setdefault("latency_ms", float((time.time() - t0) * 1000.0))
        out["_meta"].setdefault("base_url", base)
        out["_meta"].setdefault("path", "/api/optimizer/policy/propose")
    return out
