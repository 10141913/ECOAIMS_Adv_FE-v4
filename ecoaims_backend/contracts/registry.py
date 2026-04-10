import time
from typing import Any, Dict


def canonical_contract_index() -> Dict[str, Any]:
    mid = "ecoaims-contract-v1"
    mh = "sha256-ecoaims-v1"
    m = canonical_contract_manifest(mid) or {}
    endpoints = m.get("endpoints") if isinstance(m.get("endpoints"), dict) else {}
    endpoint_map: Dict[str, Any] = {}
    for endpoint_key in sorted([str(k) for k in endpoints.keys()]):
        parts = endpoint_key.split(" ", 1)
        method = parts[0] if parts else ""
        path = parts[1] if len(parts) > 1 else ""
        endpoint_map[endpoint_key] = {
            "method": method,
            "path": path,
            "contract_manifest_id": mid,
            "contract_manifest_hash": mh,
            "manifest_id": mid,
            "manifest_version": "2026-03-13",
        }
    return {
        "registry_version": "v1",
        "generated_at": int(time.time()),
        "manifests": [
            {
                "manifest_id": mid,
                "manifest_hash": mh,
                "schema_version": "2026-03-13",
                "contract_version": "v1",
            }
        ],
        "endpoint_map": endpoint_map,
    }


def canonical_contract_manifest(manifest_id: str) -> Dict[str, Any] | None:
    if manifest_id != "ecoaims-contract-v1":
        return None
    return {
        "manifest_id": "ecoaims-contract-v1",
        "manifest_hash": "sha256-ecoaims-v1",
        "schema_version": "2026-03-13",
        "contract_version": "v1",
        "endpoints": {
            "GET /api/energy-data": {
                "type": "object",
                "required": {
                    "solar": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}},
                    "wind": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}},
                    "battery": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}},
                    "grid": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}},
                    "biofuel": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}},
                },
            },
            "GET /api/precooling/zones": {"type": "object", "required": {}},
            "GET /api/precooling/status": {"type": "object", "required": {}},
            "GET /api/precooling/status_v2": {"type": "object", "required": {}},
            "GET /api/precooling/schedule": {"type": "object", "required": {}},
            "GET /api/precooling/scenarios": {"type": "object", "required": {}},
            "GET /api/precooling/kpi": {"type": "object", "required": {}},
            "GET /api/precooling/alerts": {"type": "object", "required": {}},
            "GET /api/precooling/audit": {"type": "object", "required": {}},
            "POST /api/precooling/simulate": {"type": "object", "required": {}},
            "POST /api/precooling/apply": {"type": "object", "required": {}},
            "POST /api/precooling/settings": {"type": "object", "required": {}},
            "GET /api/precooling/settings": {"type": "object", "required": {}},
            "GET /api/precooling/settings/default": {"type": "object", "required": {}},
            "POST /api/precooling/settings/validate": {"type": "object", "required": {}},
            "POST /api/precooling/settings/reset": {"type": "object", "required": {}},
            "POST /api/precooling/settings/apply": {"type": "object", "required": {}},
            "POST /optimize": {
                "type": "object",
                "required": {
                    "energy_distribution": {
                        "type": "object",
                        "required": {
                            "Solar PV": {"type": "number"},
                            "Wind Turbine": {"type": "number"},
                            "Battery": {"type": "number"},
                            "PLN/Grid": {"type": "number"},
                        },
                    },
                    "recommendation": {"type": "string"},
                },
            },
            "GET /api/reports/precooling-impact": {
                "type": "object",
                "required": {
                    "basis": {"type": "string"},
                    "summary": {"type": "object"},
                    "scenarios": {"type": "list"},
                    "quality": {"type": "object"},
                },
            },
            "GET /api/reports/precooling-impact/history": {"type": "object", "required": {"rows": {"type": "list"}}},
            "GET /api/reports/precooling-impact/filter-options": {
                "type": "object",
                "required": {"zones": {"type": "list"}, "streams": {"type": "list"}},
            },
            "GET /api/reports/precooling-impact/session-detail": {
                "type": "object",
                "required": {"record": {"type": "object"}, "quality": {"type": "object"}, "before_fidelity": {"type": "string"}, "after_fidelity": {"type": "string"}},
            },
            "GET /api/reports/precooling-impact/session-timeseries": {"type": "object", "required": {"timestamps": {"type": "list"}, "series": {"type": "object"}}},
        },
    }
