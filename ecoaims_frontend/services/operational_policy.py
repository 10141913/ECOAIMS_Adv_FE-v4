from typing import Any, Dict, List


def effective_feature_decision(feature_name: str, readiness_store: Dict[str, Any]) -> Dict[str, Any]:
    r = readiness_store if isinstance(readiness_store, dict) else {}
    canonical_policy_required = bool(r.get("canonical_policy_required"))
    integration_mode = "canonical_integration" if canonical_policy_required else "local_dev"
    policy_source = str(r.get("policy_source") or "frontend_fallback")
    backend_identity_ok = r.get("backend_identity_ok") is True
    backend_reachable = r.get("backend_reachable") is True
    backend_ready = r.get("backend_ready") is True
    contract_valid = r.get("contract_valid") is True
    registry_loaded = r.get("registry_loaded") is True

    endpoint_errors = r.get("endpoint_contract_errors") if isinstance(r.get("endpoint_contract_errors"), dict) else {}
    endpoint_mismatch = bool(endpoint_errors) if feature_name == "__verification__" else (feature_name in endpoint_errors and bool(endpoint_errors.get(feature_name)))

    default_fail_policy = "fail_open" if feature_name in {"monitoring", "reports"} else "fail_closed"

    system_status = r.get("system_status") if isinstance(r.get("system_status"), dict) else None
    features = system_status.get("features") if isinstance(system_status, dict) and isinstance(system_status.get("features"), dict) else {}
    fs = features.get(feature_name) if isinstance(features.get(feature_name), dict) else None

    if fs:
        baseline_mode = str(fs.get("recommended_mode") or "blocked")
        if baseline_mode == "normal":
            baseline_mode = "live"
        baseline_fail_policy = str(fs.get("fail_policy") or default_fail_policy)
        baseline_status = str(fs.get("status") or "")
        if baseline_status not in {"healthy", "degraded", "blocked"}:
            baseline_status = "blocked" if baseline_mode == "blocked" else ("degraded" if baseline_mode == "placeholder" else "healthy")
        baseline_reasons = fs.get("reasons") if isinstance(fs.get("reasons"), list) else []
        provenance = "backend_policy" if policy_source == "backend_policy" else "frontend_fallback"
    else:
        baseline_mode = "live"
        baseline_fail_policy = default_fail_policy
        baseline_status = "healthy"
        baseline_reasons = []
        provenance = "frontend_fallback"

    reason_chain = []
    if canonical_policy_required and (r.get("canonical_integration_ok") is not True or backend_identity_ok is not True):
        reasons = ["canonical_integration_required_but_unavailable"]
        if backend_identity_ok is not True:
            reasons.append("canonical_backend_identity_not_ok")
        return {
            "final_mode": "blocked",
            "fail_policy": baseline_fail_policy,
            "provenance": "frontend_fallback",
            "policy_source": policy_source,
            "integration_mode": integration_mode,
            "canonical_policy_required": canonical_policy_required,
            "reason_chain": reasons,
        }
    if not backend_reachable:
        return {"final_mode": "placeholder", "fail_policy": baseline_fail_policy, "provenance": "frontend_fallback", "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["backend_unreachable"]}
    if not backend_ready:
        return {"final_mode": "placeholder", "fail_policy": baseline_fail_policy, "provenance": "frontend_fallback", "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["backend_not_ready"]}
    if not contract_valid:
        return {"final_mode": "blocked", "fail_policy": baseline_fail_policy, "provenance": "frontend_fallback", "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["startup_contract_invalid"]}

    if not registry_loaded:
        if baseline_fail_policy == "fail_open":
            return {"final_mode": "placeholder", "fail_policy": baseline_fail_policy, "provenance": "frontend_fallback", "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["contract_registry_unavailable"]}
        return {"final_mode": "blocked", "fail_policy": baseline_fail_policy, "provenance": "frontend_fallback", "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["contract_registry_unavailable"]}

    if feature_name == "__verification__":
        if endpoint_mismatch:
            keys = ",".join(sorted([str(k) for k in endpoint_errors.keys()]))
            return {
                "final_mode": "blocked",
                "fail_policy": baseline_fail_policy,
                "provenance": "runtime_overlay" if provenance == "backend_policy" else provenance,
                "policy_source": policy_source,
                "integration_mode": integration_mode,
                "canonical_policy_required": canonical_policy_required,
                "reason_chain": ["runtime_endpoint_contract_mismatch", f"runtime_endpoint_contract_mismatch:{keys}"],
            }
        return {
            "final_mode": "live",
            "fail_policy": baseline_fail_policy,
            "provenance": provenance,
            "policy_source": policy_source,
            "integration_mode": integration_mode,
            "canonical_policy_required": canonical_policy_required,
            "reason_chain": [],
        }

    caps = r.get("capabilities") if isinstance(r.get("capabilities"), dict) else {}
    cap = caps.get(feature_name) if isinstance(caps.get(feature_name), dict) else None
    if not (isinstance(cap, dict) and cap.get("ready") is True):
        return {"final_mode": "blocked", "fail_policy": baseline_fail_policy, "provenance": provenance, "policy_source": policy_source, "integration_mode": integration_mode, "canonical_policy_required": canonical_policy_required, "reason_chain": ["capability_not_ready"]}

    if fs:
        if baseline_mode not in {"live", "placeholder", "blocked"}:
            baseline_mode = "blocked"
        reason_chain.extend([str(x) for x in baseline_reasons if str(x).strip()])
        final_mode = baseline_mode
    else:
        final_mode = "live"

    if endpoint_mismatch:
        if feature_name in {"monitoring", "reports"}:
            final_mode = "placeholder"
        else:
            final_mode = "blocked"
        reason_chain.append("runtime_endpoint_contract_mismatch")
        provenance = "runtime_overlay" if provenance == "backend_policy" else provenance

    if not reason_chain and baseline_status in {"degraded", "blocked"} and final_mode != "live":
        reason_chain.append(f"backend_policy:{baseline_status}")

    return {
        "final_mode": final_mode,
        "fail_policy": baseline_fail_policy,
        "provenance": provenance,
        "policy_source": policy_source,
        "integration_mode": integration_mode,
        "canonical_policy_required": canonical_policy_required,
        "reason_chain": reason_chain,
    }


def effective_verification_summary(readiness_store: Dict[str, Any]) -> Dict[str, Any]:
    r = readiness_store if isinstance(readiness_store, dict) else {}
    canonical_policy_required = bool(r.get("canonical_policy_required"))
    verification_lane = "canonical_integration" if canonical_policy_required else "local_dev"
    policy_source = str(r.get("policy_source") or "frontend_fallback")
    integration_mode = str(r.get("integration_mode") or verification_lane)
    canonical_integration_ok = r.get("canonical_integration_ok") is True
    registry_loaded = r.get("registry_loaded") is True
    backend_identity_ok = r.get("backend_identity_ok") is True
    backend_identity_reasons = r.get("backend_identity_reasons") if isinstance(r.get("backend_identity_reasons"), list) else []
    canonical_backend_verified = r.get("canonical_backend_verified") is True

    eff = effective_feature_decision("__verification__", r)
    reasons: List[str] = [str(x) for x in (eff.get("reason_chain") or []) if str(x).strip()]

    if verification_lane == "local_dev":
        if policy_source == "frontend_fallback":
            reasons.append("frontend_fallback_active")
    else:
        if policy_source != "backend_policy":
            reasons.append("policy_source_not_backend_policy")
        if not registry_loaded:
            reasons.append("registry_not_loaded")
        if not canonical_integration_ok:
            reasons.append("canonical_integration_not_ok")
        if not backend_identity_ok:
            reasons.append("backend_identity_not_ok")
            reasons.extend([str(x) for x in backend_identity_reasons if str(x).strip()])

    seen = set()
    deduped = []
    for x in reasons:
        if x not in seen:
            seen.add(x)
            deduped.append(x)

    return {
        "verification_lane": verification_lane,
        "verification_ok": eff.get("final_mode") == "live",
        "verification_reasons": deduped,
        "policy_source": policy_source,
        "integration_mode": integration_mode,
        "canonical_integration_ok": canonical_integration_ok,
        "backend_identity_ok": backend_identity_ok,
        "backend_identity_reasons": backend_identity_reasons,
        "canonical_backend_verified": canonical_backend_verified,
    }
