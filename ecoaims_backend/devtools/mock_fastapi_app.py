import os
import time

from fastapi import FastAPI
from fastapi import Request

from ecoaims_backend.contracts.fastapi_api import router as contracts_router
from ecoaims_backend.energy.fastapi_api import router as energy_router
from ecoaims_backend.precooling.fastapi_api import router as precooling_router
from ecoaims_backend.reports.fastapi_api import router as reports_router


app = FastAPI(title="ECOAIMS Frontend Devtools Mock API", version="0.0.1")
app.include_router(energy_router)
app.include_router(precooling_router)
app.include_router(reports_router)
app.include_router(contracts_router)


@app.get("/health")
def health():
    return {"ok": True}


def _mock_identity():
    # Explicit NON-CANONICAL identity (cannot pass strict canonical lane)
    return {
        "identity_id": "ecoaims_frontend.devtools_mock",
        "repo_id": "ECOAIMS_Adv_FE",
        "repo": "ECOAIMS_Adv_FE",
        "server_role": "frontend_devtools_mock",
        "policy_owner": "frontend_devtools",
        "contracts_owner": "frontend_devtools",
        "git_sha": os.getenv("ECOAIMS_DEVTOOLS_GIT_SHA", "dev"),
        "build_id": os.getenv("ECOAIMS_DEVTOOLS_BUILD_ID", ""),
        "canonical_backend_identity_ok": False,
        "service": "ecoaims_frontend_devtools",
        "app": "mock_fastapi_app",
    }


@app.get("/api/startup-info")
def startup_info():
    schema_version = os.getenv("ECOAIMS_SCHEMA_VERSION", "startup_info_v1")
    contract_version = os.getenv("ECOAIMS_CONTRACT_VERSION", "2026-03-13")
    contract_manifest_id = os.getenv("ECOAIMS_CONTRACT_MANIFEST_ID", "ecoaims-contract-v1")
    contract_manifest_hash = os.getenv("ECOAIMS_CONTRACT_MANIFEST_HASH", "sha256-ecoaims-v1")
    caps_env = {
        "monitoring": os.getenv("ECOAIMS_CAP_MONITORING", "true"),
        "comparison": os.getenv("ECOAIMS_CAP_COMPARISON", "true"),
        "optimization": os.getenv("ECOAIMS_CAP_OPTIMIZATION", "true"),
        "reports": os.getenv("ECOAIMS_CAP_REPORTS", "true"),
        "precooling": os.getenv("ECOAIMS_CAP_PRECOOLING", "true"),
    }
    caps = {}
    reasons = []
    for k, v in caps_env.items():
        ok = str(v).lower() in {"1", "true", "yes"}
        caps[k] = {"ready": ok}
        if not ok:
            reasons.append(f"{k}_disabled")
    backend_ready = len(reasons) == 0
    return {
        "schema_version": schema_version,
        "contract_version": contract_version,
        "contract_manifest_id": contract_manifest_id,
        "contract_manifest_hash": contract_manifest_hash,
        "backend_ready": backend_ready,
        "capabilities": caps,
        "reasons_not_ready": reasons,
        "backend_identity": _mock_identity(),
        "required_endpoints": [
            "/health",
            "/api/startup-info",
            "/api/system/status",
            "/api/contracts/index",
            f"/api/contracts/{contract_manifest_id}",
            "/api/energy-data",
            "/optimize",
            "/api/reports/precooling-impact",
            "/api/reports/precooling-impact/history",
            "/api/reports/precooling-impact/filter-options",
            "/api/reports/precooling-impact/session-detail",
            "/api/reports/precooling-impact/session-timeseries",
        ],
        "server_time": int(time.time()),
        "version": app.version,
    }


@app.get("/api/system/status")
def system_status():
    caps_env = {
        "monitoring": os.getenv("ECOAIMS_CAP_MONITORING", "true"),
        "comparison": os.getenv("ECOAIMS_CAP_COMPARISON", "true"),
        "optimization": os.getenv("ECOAIMS_CAP_OPTIMIZATION", "true"),
        "reports": os.getenv("ECOAIMS_CAP_REPORTS", "true"),
        "precooling": os.getenv("ECOAIMS_CAP_PRECOOLING", "true"),
    }
    caps = {k: (str(v).lower() in {"1", "true", "yes"}) for k, v in caps_env.items()}
    any_disabled = any((not v) for v in caps.values())
    overall_status = "degraded" if any_disabled else "healthy"
    features = {}
    for k, enabled in caps.items():
        fail_policy = "fail_open" if k in {"monitoring", "reports"} else "fail_closed"
        if enabled:
            features[k] = {"status": "healthy", "recommended_mode": "live", "fail_policy": fail_policy, "reasons": []}
        else:
            features[k] = {"status": "blocked", "recommended_mode": "blocked", "fail_policy": fail_policy, "reasons": [f"{k}_disabled"]}
    return {"overall_status": overall_status, "features": features, "backend_identity": _mock_identity(), "server_time": int(time.time())}


@app.get("/diag/doctor")
def diag_doctor():
    si = startup_info()
    ss = system_status()
    required = si.get("required_endpoints") if isinstance(si, dict) else []
    required = required if isinstance(required, list) else []
    return {
        "ok": True,
        "server_time": int(time.time()),
        "backend_identity": (si.get("backend_identity") if isinstance(si, dict) else None),
        "startup_info": si,
        "system_status": ss,
        "required_endpoints": required + ["/diag/doctor"],
        "notes": [
            "Endpoint ini digunakan FE (tab Home) untuk menampilkan Doctor Report ringkas.",
            "Jika ada 404 sebelumnya, pastikan backend yang berjalan adalah ecoaims_backend.devtools.mock_fastapi_app:app.",
        ],
    }


@app.post("/ai/optimizer/dispatch")
async def ai_optimizer_dispatch(req: Request):
    js = {}
    try:
        js = await req.json()
    except Exception:
        js = {}

    stream_id = str((js or {}).get("stream_id") or "proof-rl-1").strip() or "proof-rl-1"
    optimizer_backend = str((js or {}).get("optimizer_backend") or "rl").strip() or "rl"
    demand_row = (js or {}).get("demand_row") if isinstance((js or {}).get("demand_row"), dict) else {}
    ts0 = str(demand_row.get("timestamp") or "2026-03-10T00:00:00")

    rows = []
    soc = 50.0
    total_grid = 0.0
    total_cost = 0.0
    total_emission = 0.0
    total_unmet = 0.0

    for h in range(24):
        if 6 <= h <= 12:
            battery_charge = 4.0
            battery_discharge = 0.0
            grid_import = 1.2
        elif 18 <= h <= 22:
            battery_charge = 0.0
            battery_discharge = 3.5
            grid_import = 2.6
        else:
            battery_charge = 0.0
            battery_discharge = 0.8
            grid_import = 1.8

        soc = max(0.0, min(100.0, soc + battery_charge - battery_discharge))
        cost = grid_import * 1500.0
        emission = grid_import * 0.85
        unmet = 0.0

        total_grid += grid_import
        total_cost += cost
        total_emission += emission
        total_unmet += unmet

        rows.append(
            {
                "timestamp": f"{ts0}+{h:02d}:00",
                "grid_import_kwh": round(grid_import, 4),
                "soc": round(soc, 2),
                "cost": round(cost, 4),
                "emission": round(emission, 6),
                "unmet_kwh": round(unmet, 4),
                "battery_charge_kwh": round(battery_charge, 4),
                "battery_discharge_kwh": round(battery_discharge, 4),
                "reward": round(-(0.6 * cost + 0.3 * emission + 1.0 * unmet), 6),
                "rl_action_level": int(2 if battery_charge > 0 else (1 if battery_discharge > 0 else 0)),
                "rl_biofuel_on": False,
                "optimizer_backend": optimizer_backend,
                "stream_id": stream_id,
            }
        )

    return {
        "ok": True,
        "stream_id": stream_id,
        "optimizer_backend": optimizer_backend,
        "kpi": {
            "total_grid_import_kwh": round(total_grid, 6),
            "total_cost": round(total_cost, 6),
            "total_emission": round(total_emission, 6),
            "total_unmet_kwh": round(total_unmet, 6),
            "final_soc": round(soc, 2),
        },
        "schedule": rows,
    }
