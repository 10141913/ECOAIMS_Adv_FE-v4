import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ecoaims_backend.contracts.fastapi_api import router as contracts_router
from ecoaims_backend.energy.fastapi_api import router as energy_router
from ecoaims_backend.precooling.fastapi_api import router as precooling_router
from ecoaims_backend.reports.fastapi_api import router as reports_router


app = FastAPI(title="ECOAIMS API (Canonical FastAPI)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(energy_router)
app.include_router(precooling_router)
app.include_router(reports_router)
app.include_router(contracts_router)


@app.get("/health")
def health():
    return {"ok": True}


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
    backend_repo = os.getenv("ECOAIMS_BACKEND_REPO", "ECO_AIMS")
    backend_identity = {
        "identity_id": os.getenv("ECOAIMS_BACKEND_IDENTITY_ID", "ecoaims_backend.canonical_fastapi"),
        "repo": backend_repo,
        "repo_id": os.getenv("ECOAIMS_BACKEND_REPO_ID", backend_repo),
        "server_role": os.getenv("ECOAIMS_BACKEND_SERVER_ROLE", "canonical_backend"),
        "git_sha": os.getenv("ECOAIMS_BACKEND_GIT_SHA", "dev"),
        "build_id": os.getenv("ECOAIMS_BACKEND_BUILD_ID", ""),
        "service": "ecoaims_backend",
        "app": "canonical_fastapi_app",
    }
    return {
        "schema_version": schema_version,
        "contract_version": contract_version,
        "contract_manifest_id": contract_manifest_id,
        "contract_manifest_hash": contract_manifest_hash,
        "backend_ready": backend_ready,
        "capabilities": caps,
        "reasons_not_ready": reasons,
        "backend_identity": backend_identity,
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
    backend_repo = os.getenv("ECOAIMS_BACKEND_REPO", "ECO_AIMS")
    backend_identity = {
        "identity_id": os.getenv("ECOAIMS_BACKEND_IDENTITY_ID", "ecoaims_backend.canonical_fastapi"),
        "repo": backend_repo,
        "repo_id": os.getenv("ECOAIMS_BACKEND_REPO_ID", backend_repo),
        "server_role": os.getenv("ECOAIMS_BACKEND_SERVER_ROLE", "canonical_backend"),
        "git_sha": os.getenv("ECOAIMS_BACKEND_GIT_SHA", "dev"),
        "build_id": os.getenv("ECOAIMS_BACKEND_BUILD_ID", ""),
        "service": "ecoaims_backend",
        "app": "canonical_fastapi_app",
    }
    features = {}
    for k, enabled in caps.items():
        fail_policy = "fail_open" if k in {"monitoring", "reports"} else "fail_closed"
        if enabled:
            features[k] = {"status": "healthy", "recommended_mode": "live", "fail_policy": fail_policy, "reasons": []}
        else:
            features[k] = {"status": "blocked", "recommended_mode": "blocked", "fail_policy": fail_policy, "reasons": [f"{k}_disabled"]}
    return {"overall_status": overall_status, "features": features, "backend_identity": backend_identity, "server_time": int(time.time())}


@app.get("/dashboard/state")
def dashboard_state():
    return {"ok": True, "ts": int(time.time())}


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
            "Jika ada 404 sebelumnya, pastikan backend yang berjalan adalah ecoaims_backend.devtools.canonical_fastapi_app:app.",
        ],
    }


@app.get("/diag/monitoring")
def diag_monitoring():
    required_min = int(os.getenv("ECOAIMS_MIN_HISTORY_FOR_COMPARISON", "12") or 12)
    return {
        "status": "ok",
        "server_time": int(time.time()),
        "history": {
            "required_min_for_comparison": required_min,
            "energy_data_records_count": required_min,
        },
        "notes": [
            "Used by FE to determine Comparison readiness.",
        ],
    }
