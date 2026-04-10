import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ecoaims_frontend.services import contract_registry
from ecoaims_frontend.services.contract_negotiation import get_negotiation_service

logger = logging.getLogger(__name__)


class ContractSynchronizationService:
    def __init__(self):
        self.sync_interval_s = 300.0
        self.last_sync_ts: float | None = None
        self.last_diff: Dict[str, Any] | None = None

    def _snapshot(self) -> Dict[str, Any]:
        idx = contract_registry.get_registry_cache()
        out = {
            "registry_version": idx.get("registry_version"),
        }
        manifests = idx.get("manifests") if isinstance(idx.get("manifests"), list) else []
        out["manifests"] = [
            {"manifest_id": it.get("manifest_id"), "manifest_hash": it.get("manifest_hash")}
            for it in manifests
            if isinstance(it, dict)
        ]
        endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
        out["endpoint_map_keys"] = sorted([str(k) for k in endpoint_map.keys()])
        return out

    def _compare(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        has_changes = before != after
        return {
            "has_changes": bool(has_changes),
            "before": before,
            "after": after,
            "summary": "changed" if has_changes else "no_change",
            "breaking": False,
            "recommendation": "reload_frontend" if has_changes else None,
        }

    def sync_with_backend(self, manifest_id: str, expected_hash: Optional[str]) -> Dict[str, Any]:
        now = time.time()
        if self.last_sync_ts is not None and (now - float(self.last_sync_ts)) < float(self.sync_interval_s):
            return {"success": True, "skipped": True, "last_sync": self.last_sync_ts, "changes": self.last_diff or {}}

        before = self._snapshot()
        reg = contract_registry.load_contract_registry(manifest_id, expected_hash)
        after = self._snapshot()
        diff = self._compare(before, after)
        self.last_sync_ts = now
        self.last_diff = diff
        _ = reg
        if diff.get("has_changes"):
            logger.info(f"Contracts updated: {diff.get('summary')}")
        return {"success": True, "skipped": False, "last_sync": datetime.now(timezone.utc).isoformat(), "changes": diff}


class ContractVersionSynchronizer:
    def __init__(self, *, sync_interval_s: float = 3600.0, cache_ttl_s: int = 300):
        self.sync_interval_s = float(sync_interval_s)
        self.cache_ttl_s = int(cache_ttl_s)
        self.last_check_ts: float | None = None
        self.last_report: Dict[str, Any] | None = None

    def check_and_sync(self, base_url: str, *, mode: str = "lenient") -> Dict[str, Any]:
        now = time.time()
        if self.last_check_ts is not None and (now - float(self.last_check_ts)) < float(self.sync_interval_s):
            return {"has_drift": bool((self.last_report or {}).get("has_drift")), "skipped": True, "details": (self.last_report or {}).get("details") or {}, "recommended_action": (self.last_report or {}).get("recommended_action")}

        svc = get_negotiation_service(cache_ttl_s=self.cache_ttl_s)
        endpoints = ["/api/energy-data", "/diag/monitoring"]
        details: Dict[str, Any] = {}
        has_drift = False
        highest = "low"

        for p in endpoints:
            nego = svc.negotiate_for_endpoint(base_url, method="GET", path=p, mode=str(mode or "lenient"), negotiation_required=False)
            compat = nego.get("compatibility") if isinstance(nego.get("compatibility"), dict) else {}
            comp = compat.get("compatible")
            if comp is False:
                has_drift = True
            sev = str(compat.get("severity") or "low")
            if sev == "high":
                highest = "high"
            elif sev == "medium" and highest != "high":
                highest = "medium"
            details[p] = {
                "expected": nego.get("expected"),
                "backend": nego.get("backend"),
                "compatibility": compat,
                "decision": nego.get("decision"),
            }

        recommended_action = "ignore"
        if has_drift:
            recommended_action = "update_frontend" if highest in {"high", "medium"} else "reload_frontend"

        report = {"has_drift": bool(has_drift), "skipped": False, "details": details, "recommended_action": recommended_action}
        self.last_check_ts = now
        self.last_report = dict(report)
        return report
