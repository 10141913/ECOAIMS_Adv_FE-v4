import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


def _parse_semver(v: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    if s.startswith("v") or s.startswith("V"):
        s = s[1:].strip()
    parts = s.split(".")
    if len(parts) < 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
        return major, minor, patch
    except Exception:
        return None


def _compare_versions(expected: Any, actual: Any) -> Dict[str, Any]:
    ev = _parse_semver(expected)
    av = _parse_semver(actual)
    if ev is None or av is None:
        return {"compatible": None, "reason": "version_unparseable", "severity": "medium"}
    emj, emn, _ = ev
    amj, amn, _ = av
    if emj != amj:
        return {"compatible": False, "reason": "major_version_mismatch", "severity": "high"}
    if amn < emn:
        return {"compatible": False, "reason": "backend_minor_older_than_frontend", "severity": "medium"}
    if amn > emn:
        return {"compatible": True, "reason": "backend_minor_newer_or_equal", "severity": "low"}
    return {"compatible": True, "reason": "same_major_minor", "severity": "low"}


@dataclass(frozen=True)
class NegotiationKey:
    base_url: str
    method: str
    path: str


class ContractMismatchError(RuntimeError):
    def __init__(self, message: str, *, negotiation_result: Dict[str, Any]):
        super().__init__(message)
        self.negotiation_result = negotiation_result


class ContractNegotiationService:
    def __init__(self, *, cache_ttl_s: int = 300):
        self.cache_ttl_s = int(cache_ttl_s)
        self._cache: Dict[NegotiationKey, Tuple[float, Dict[str, Any]]] = {}

        self.endpoint_map = {
            "/api/energy-data": {"contract_id": "energy_data", "version": "1.2.0"},
            "/diag/monitoring": {"contract_id": "monitoring", "version": "1.0.0"},
        }

    def _cache_get(self, key: NegotiationKey) -> Optional[Dict[str, Any]]:
        row = self._cache.get(key)
        if not row:
            return None
        ts, data = row
        if (time.time() - float(ts)) > float(self.cache_ttl_s):
            self._cache.pop(key, None)
            return None
        return dict(data)

    def _cache_put(self, key: NegotiationKey, data: Dict[str, Any]) -> None:
        self._cache[key] = (time.time(), dict(data))

    def identify_contract(self, path: str) -> Dict[str, Any]:
        p = str(path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        spec = self.endpoint_map.get(p)
        if not isinstance(spec, dict):
            return {"known": False, "path": p, "contract_id": None, "expected_version": None}
        return {"known": True, "path": p, "contract_id": spec.get("contract_id"), "expected_version": spec.get("version")}

    def _options(self, url: str, *, timeout_s: Tuple[float, float]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        t0 = time.time()
        try:
            r = requests.options(url, timeout=timeout_s)
            status = int(r.status_code)
            headers = {str(k): str(v) for k, v in (r.headers or {}).items()}
            body = None
            try:
                js = r.json()
                body = js if isinstance(js, dict) else {"data": js}
            except Exception:
                body = None
            return body, {"url": url, "method": "OPTIONS", "status": status, "elapsed_ms": int((time.time() - t0) * 1000), "headers": headers}
        except Exception as e:
            return None, {"url": url, "method": "OPTIONS", "status": None, "elapsed_ms": int((time.time() - t0) * 1000), "error_class": type(e).__name__, "error": str(e)}

    def negotiate_for_endpoint(self, base_url: str, *, method: str, path: str, mode: str, negotiation_required: bool) -> Dict[str, Any]:
        base = str(base_url or "").rstrip("/")
        p = self.identify_contract(path)
        key = NegotiationKey(base, str(method or "GET").upper(), p.get("path") or str(path))
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        url = f"{base}{p.get('path')}"
        body, attempt = self._options(url, timeout_s=(1.0, 2.0))
        hdrs = attempt.get("headers") if isinstance(attempt.get("headers"), dict) else {}
        be_contract_id = hdrs.get("X-Contract-ID") or hdrs.get("x-contract-id")
        be_contract_version = hdrs.get("X-Contract-Version") or hdrs.get("x-contract-version")
        be_contract_hash = hdrs.get("X-Contract-Hash") or hdrs.get("x-contract-hash")
        if isinstance(body, dict):
            contract = body.get("contract") if isinstance(body.get("contract"), dict) else None
            if isinstance(contract, dict):
                be_contract_id = be_contract_id or contract.get("id")
                be_contract_version = be_contract_version or contract.get("version")
                be_contract_hash = be_contract_hash or contract.get("hash")

        status = attempt.get("status")
        if status is None:
            compatible = None
            compat = {"compatible": None, "reason": "negotiation_unavailable", "severity": "medium"}
        elif int(status) in {404, 405, 501}:
            compatible = None
            compat = {"compatible": None, "reason": "negotiation_unavailable", "severity": "medium"}
        else:
            compat = _compare_versions(p.get("expected_version"), be_contract_version)
            compatible = compat.get("compatible")

        decision = "proceed"
        if negotiation_required and (compatible is not True):
            decision = "block"
        elif str(mode or "").lower() == "strict" and compatible is False:
            decision = "block"
        elif str(mode or "").lower() == "adaptive" and compatible is False:
            decision = "fallback"
        elif str(mode or "").lower() == "lenient" and compatible is False:
            decision = "warn"

        out = {
            "endpoint": p.get("path"),
            "method": key.method,
            "known_contract": bool(p.get("known")),
            "expected": {"id": p.get("contract_id"), "version": p.get("expected_version")},
            "backend": {"id": be_contract_id, "version": be_contract_version, "hash": be_contract_hash},
            "compatibility": compat,
            "decision": decision,
            "attempt": attempt,
        }
        self._cache_put(key, out)
        return out

    def headers_for_expected_contract(self, path: str) -> Dict[str, str]:
        p = self.identify_contract(path)
        cid = p.get("contract_id")
        ver = p.get("expected_version")
        out: Dict[str, str] = {}
        if isinstance(cid, str) and cid.strip():
            out["X-Expected-Contract-ID"] = cid.strip()
        if isinstance(ver, str) and ver.strip():
            out["X-Expected-Contract-Version"] = ver.strip()
        return out


_GLOBAL_NEGOTIATION_SERVICE: ContractNegotiationService | None = None
_GLOBAL_NEGOTIATION_TTL_S: int | None = None


def get_negotiation_service(*, cache_ttl_s: int = 300) -> ContractNegotiationService:
    global _GLOBAL_NEGOTIATION_SERVICE, _GLOBAL_NEGOTIATION_TTL_S
    ttl = int(cache_ttl_s)
    if _GLOBAL_NEGOTIATION_SERVICE is None or _GLOBAL_NEGOTIATION_TTL_S != ttl:
        _GLOBAL_NEGOTIATION_SERVICE = ContractNegotiationService(cache_ttl_s=ttl)
        _GLOBAL_NEGOTIATION_TTL_S = ttl
    return _GLOBAL_NEGOTIATION_SERVICE
