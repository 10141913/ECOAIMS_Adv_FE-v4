from dash import Input, Output, html

from ecoaims_frontend.services.readiness_service import get_backend_readiness
from ecoaims_frontend.services.data_service import get_last_monitoring_endpoint_contract
from ecoaims_frontend.services.optimization_service import get_last_optimization_endpoint_contract
from ecoaims_frontend.services.reports_api import get_last_reports_endpoint_contract
from ecoaims_frontend.services import contract_registry
from ecoaims_frontend.services.operational_policy import effective_verification_summary
from ecoaims_frontend.ui.error_ui import error_banner, status_banner


def register_readiness_callbacks(app):
    @app.callback(
        Output("backend-readiness-store", "data"),
        [Input("backend-readiness-interval", "n_intervals")],
    )
    def update_backend_readiness(n):
        r = get_backend_readiness()
        contract_registry.set_registry_base_url((r or {}).get("base_url") if isinstance(r, dict) else None)
        monitoring = get_last_monitoring_endpoint_contract()
        optimization = get_last_optimization_endpoint_contract()
        reports = get_last_reports_endpoint_contract()
        status = {
            "monitoring": {"status": monitoring.get("status"), "source": monitoring.get("source")},
            "optimization": {"status": optimization.get("status"), "source": optimization.get("source")},
            "reports": {"status": reports.get("status"), "source": reports.get("source")},
        }
        errors = {}
        warnings = {}
        if monitoring.get("status") in {"mismatch", "blocked"}:
            errors["monitoring"] = monitoring.get("errors")
        if monitoring.get("status") == "warn":
            warnings["monitoring"] = monitoring.get("errors")
        if optimization.get("status") in {"mismatch", "blocked"}:
            errors["optimization"] = optimization.get("errors")
        if optimization.get("status") == "warn":
            warnings["optimization"] = optimization.get("errors")
        if reports.get("status") in {"mismatch", "blocked"}:
            errors["reports"] = reports.get("errors")
        if reports.get("status") == "warn":
            warnings["reports"] = reports.get("errors")
        merged = {
            **(r if isinstance(r, dict) else {}),
            "endpoint_contract_status": status,
            "endpoint_contract_errors": errors,
            "endpoint_contract_warnings": warnings,
        }
        merged.update(effective_verification_summary(merged))
        return merged

    @app.callback(
        Output("backend-status-banner", "children"),
        [Input("backend-readiness-store", "data")],
    )
    def render_backend_status_banner(data):
        d = data if isinstance(data, dict) else {}
        base = d.get("base_url") or "-"
        reachable = bool(d.get("backend_reachable"))
        ready = bool(d.get("backend_ready"))
        err = d.get("error_class")
        contract_valid = bool(d.get("contract_valid")) if "contract_valid" in d else True
        endpoint_errors = d.get("endpoint_contract_errors") if isinstance(d.get("endpoint_contract_errors"), dict) else {}
        endpoint_warnings = d.get("endpoint_contract_warnings") if isinstance(d.get("endpoint_contract_warnings"), dict) else {}
        overall = d.get("overall_status")
        registry_loaded = d.get("registry_loaded")
        registry_reason = d.get("registry_mismatch_reason")
        policy_source = d.get("policy_source")
        canonical_required = bool(d.get("canonical_policy_required"))
        canonical_ok = bool(d.get("canonical_integration_ok"))
        lane = str(d.get("verification_lane") or ("canonical_integration" if canonical_required else "local_dev"))
        verification_ok = d.get("verification_ok") is True
        backend_identity_ok = d.get("backend_identity_ok") is True
        backend_identity_reasons = d.get("backend_identity_reasons") if isinstance(d.get("backend_identity_reasons"), list) else []
        canonical_backend_verified = d.get("canonical_backend_verified") is True
        reasons = d.get("verification_reasons") if isinstance(d.get("verification_reasons"), list) else []
        reasons_s = ",".join([str(x) for x in reasons if str(x).strip()])
        ident_s = ",".join([str(x) for x in backend_identity_reasons if str(x).strip()])

        if not reachable:
            msg = f"base_url={base}\nerror_class={err}"
            return status_banner("Backend", "Waiting for backend", msg)

        if not contract_valid:
            msg = f"base_url={base}\ncontract_mismatch={d.get('contract_mismatch_reason')}"
            return status_banner("Backend", "Backend connected but contract mismatch", msg)

        if registry_loaded is False:
            msg = f"base_url={base}\nregistry_mismatch={registry_reason}"
            return status_banner("Backend", "Backend degraded (contract registry unavailable)", msg)

        if endpoint_errors:
            keys = ",".join(sorted([str(k) for k in endpoint_errors.keys()]))
            msg = f"base_url={base}\nruntime_endpoint_contract_mismatch={keys}"
            return status_banner("Backend", "Backend ready but runtime endpoint mismatch", msg)

        if endpoint_warnings:
            keys = ",".join(sorted([str(k) for k in endpoint_warnings.keys()]))
            msg = f"base_url={base}\nruntime_endpoint_contract_warning={keys}"
            return status_banner("Backend", "Backend ready with runtime endpoint warnings", msg)

        if lane == "canonical_integration":
            if not backend_identity_ok:
                msg = f"base_url={base}\nMODE=canonical_integration\nPOLICY_SOURCE={policy_source}\nBACKEND_IDENTITY_OK={backend_identity_ok}\nCANONICAL_BACKEND_VERIFIED={canonical_backend_verified}\nVERIFICATION_OK={verification_ok}\nIDENTITY_REASONS={ident_s or '-'}\nREASONS={reasons_s or '-'}"
                return status_banner(
                    "Backend",
                    "Canonical backend identity mismatch",
                    msg,
                    "Backend yang terhubung bukan canonical backend yang diharapkan. Lane canonical harus FAIL closed.",
                )
            if not verification_ok:
                msg = f"base_url={base}\nMODE=canonical_integration\nPOLICY_SOURCE={policy_source}\nREGISTRY_LOADED={registry_loaded}\nCANONICAL_INTEGRATION_OK={canonical_ok}\nBACKEND_IDENTITY_OK={backend_identity_ok}\nCANONICAL_BACKEND_VERIFIED={canonical_backend_verified}\nVERIFICATION_OK={verification_ok}\nREASONS={reasons_s or '-'}"
                return status_banner(
                    "Backend",
                    "Cross-repo canonical proof required but unavailable",
                    msg,
                    "Frontend diblokir oleh canonical gate. Tidak boleh fallback dalam lane ini.",
                )
            msg = f"base_url={base}\nMODE=canonical_integration\nPOLICY_SOURCE={policy_source}\nREGISTRY_LOADED={registry_loaded}\nCANONICAL_INTEGRATION_OK={canonical_ok}\nBACKEND_IDENTITY_OK={backend_identity_ok}\nCANONICAL_BACKEND_VERIFIED={canonical_backend_verified}\nVERIFICATION_OK={verification_ok}"
            return status_banner("Backend", "Canonical integration verified", msg, "Koneksi backend, kontrak, registry, dan policy backend terverifikasi.")

        if lane == "local_dev" and policy_source == "frontend_fallback":
            msg = f"base_url={base}\nMODE=local_dev\nPOLICY_SOURCE=frontend_fallback\nVERIFICATION_OK={verification_ok}\nREASONS={reasons_s or '-'}"
            return status_banner("Backend", "Local fallback mode active", msg, "Ini bukan bukti integrasi canonical. Gunakan lane canonical_integration untuk verifikasi strict.")

        if overall in {"healthy", "degraded", "blocked"} and overall != "healthy":
            msg = f"base_url={base}\noverall_status={overall}"
            return status_banner("Backend", f"Backend {overall}", msg)

        caps = d.get("capabilities") if isinstance(d.get("capabilities"), dict) else {}
        not_ready = []
        for k, v in caps.items():
            if isinstance(v, dict) and v.get("ready") is False:
                not_ready.append(str(k))
        if not_ready:
            msg = f"base_url={base}\nfeature_not_ready={','.join(not_ready)}"
            return status_banner("Backend", "Backend connected (some features not ready)", msg)

        if err and err == "backend_endpoint_unavailable":
            msg = f"base_url={base}\nstartup_info_unavailable"
            return status_banner("Backend", "Backend connected (startup-info not available)", msg)

        if not ready:
            msg = f"base_url={base}\nreasons_not_ready={d.get('reasons_not_ready')}"
            return status_banner("Backend", "Backend connected (warming up)", msg)

        return html.Div()

    @app.callback(
        [
            Output("tab-monitoring", "disabled"),
            Output("tab-forecasting", "disabled"),
            Output("tab-optimization", "disabled"),
            Output("tab-precooling", "disabled"),
            Output("tab-bms", "disabled"),
            Output("tab-reports", "disabled"),
            Output("tab-settings", "disabled"),
            Output("tab-about", "disabled"),
        ],
        Input("contract-mismatch-store", "data"),
    )
    def gate_tabs_on_contract_mismatch(mismatch_store):
        count = 0
        if isinstance(mismatch_store, dict):
            try:
                count = int(mismatch_store.get("count") or 0)
            except Exception:
                count = 0
        locked = count > 0
        return (locked, locked, locked, locked, locked, locked, locked, locked)
