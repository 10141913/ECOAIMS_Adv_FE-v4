import os
import time
import datetime
from typing import Any, Dict, Optional

import requests

from ecoaims_frontend.config import ENERGY_LIMITS
from ecoaims_frontend.services.http_trace import trace_headers
from ecoaims_frontend.services.settings_service import get_setting

_SESSION = requests.Session()
_ENDPOINT_CACHE: Dict[str, object] = {"url": None, "checked_at": 0.0, "unavailable_until": 0.0}
_LAST_PUSH_AT: float = 0.0


def _env_truthy(name: str, default: str = "false") -> bool:
    v = str(os.getenv(name, default) or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _resolve_dashboard_live_state_url(base_url: str) -> str:
    now = time.time()
    cached = _ENDPOINT_CACHE.get("url")
    checked_at = float(_ENDPOINT_CACHE.get("checked_at") or 0.0)
    if isinstance(cached, str) and cached and (now - checked_at) < 60.0:
        return cached

    base = str(base_url or "").rstrip("/")
    url = f"{base}/dashboard/live/state"
    if base:
        try:
            th = trace_headers()
            js = _SESSION.get(f"{base}/api/startup-info", timeout=(1.0, 2.0), **({"headers": th} if th else {})).json()
            if isinstance(js, dict):
                eu = js.get("endpoint_urls")
                if isinstance(eu, dict):
                    u = eu.get("dashboard_live_state")
                    if isinstance(u, str) and u.strip():
                        url = u.strip()
        except Exception:
            pass
    _ENDPOINT_CACHE["url"] = url
    _ENDPOINT_CACHE["checked_at"] = now
    return url


def _build_payload(live_data: Dict[str, Any], *, stream_id: str) -> Optional[Dict[str, object]]:
    if not isinstance(live_data, dict):
        return None
    health = live_data.get("health") if isinstance(live_data.get("health"), dict) else {}
    active = int(health.get("active_sensors") or 0)
    if active <= 0:
        return None

    supply = live_data.get("supply") if isinstance(live_data.get("supply"), dict) else {}
    demand = live_data.get("demand") if isinstance(live_data.get("demand"), dict) else {}

    def fnum(v: object) -> Optional[float]:
        if isinstance(v, (int, float)):
            return float(v)
        return None

    pv = fnum(supply.get("Solar PV"))
    wt = fnum(supply.get("Wind Turbine"))
    bf = fnum(supply.get("Biofuel"))
    grid = fnum(supply.get("PLN/Grid"))
    batt_kwh = fnum(supply.get("Battery"))

    load = 0.0
    for v in demand.values():
        fv = fnum(v)
        if fv is not None:
            load += fv

    if pv is None and wt is None and bf is None and grid is None and batt_kwh is None and load <= 0:
        return None

    grid_import = 0.0
    grid_export = 0.0
    if grid is not None:
        if grid >= 0:
            grid_import = grid
        else:
            grid_export = abs(grid)

    soc = None
    batt_capacity = float(ENERGY_LIMITS.get("battery") or 0.0)
    if batt_kwh is not None and batt_capacity > 0:
        soc = max(0.0, min(1.0, batt_kwh / batt_capacity))

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload: Dict[str, object] = {
        "stream_id": str(stream_id or "default"),
        "timestamp": ts,
        "pv_power": float(pv or 0.0),
        "wind_power": float(wt or 0.0),
        "load_power": float(load),
        "grid_import": float(grid_import),
        "grid_export": float(grid_export),
        "biofuel_power": float(bf or 0.0),
        "battery_charge_power": 0.0,
        "battery_discharge_power": 0.0,
    }
    if soc is not None:
        payload["soc"] = float(soc)
    return payload


def maybe_push_live_state(*, base_url: str, live_data: Dict[str, Any], stream_id: str = "default") -> bool:
    global _LAST_PUSH_AT
    if not _env_truthy("ECOAIMS_FE_PUSH_LIVE_STATE", "false"):
        return False
    base = str(base_url or "").rstrip("/")
    if not base:
        return False

    now = time.time()
    # Settings override takes precedence, fallback to env, default 15s
    settings_interval = get_setting("live_pusher", "interval_s")
    try:
        if isinstance(settings_interval, (int, float)) and float(settings_interval) > 0:
            min_interval = float(settings_interval)
        else:
            min_interval = float(os.getenv("ECOAIMS_FE_PUSH_LIVE_STATE_MIN_INTERVAL_S", "15.0"))
    except Exception:
        min_interval = 15.0
    if (now - _LAST_PUSH_AT) < min_interval:
        return False

    unavailable_until = float(_ENDPOINT_CACHE.get("unavailable_until") or 0.0)
    if now < unavailable_until:
        return False

    payload = _build_payload(live_data, stream_id=stream_id)
    if payload is None:
        return False

    url = _resolve_dashboard_live_state_url(base)
    try:
        th = trace_headers()
        resp = _SESSION.post(url, json=payload, timeout=(1.0, 2.0), **({"headers": th} if th else {}))
        if int(resp.status_code) in {404, 405}:
            _ENDPOINT_CACHE["unavailable_until"] = now + 60.0
            return False
        if int(resp.status_code) >= 400:
            return False
        _LAST_PUSH_AT = now
        return True
    except Exception:
        return False
