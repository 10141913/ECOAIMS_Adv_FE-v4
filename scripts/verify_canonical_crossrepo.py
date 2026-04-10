import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_backend_identity(backend_identity: Dict[str, Any]) -> str:
    s = _canonical_json(backend_identity if isinstance(backend_identity, dict) else {})
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_json_sort_keys_compact(payload: Dict[str, Any], exclude_key: str | None = None) -> str:
    d = payload if isinstance(payload, dict) else {}
    if exclude_key and exclude_key in d:
        d = {k: v for k, v in d.items() if k != exclude_key}
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _identity_subset_match(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    if not (isinstance(expected, dict) and isinstance(actual, dict)):
        return False
    for k, v in expected.items():
        if actual.get(k) != v:
            return False
    return True


def _wait_http_ok(url: str, timeout_s: float = 25.0) -> None:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=3)
            last = r.status_code
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"timeout waiting for {url} (last_status={last})")


def _read_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return js if isinstance(js, dict) else {"data": js}


def _write_json_file(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(_canonical_json(payload))
        f.write("\n")
    os.replace(tmp, path)


def _run_make(cwd: str, target: str) -> Tuple[int, str]:
    p = subprocess.run(["make", target], cwd=cwd, capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode, out.strip()


def _truthy_env(name: str, default: str = "false") -> bool:
    v = str(os.getenv(name, default)).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _official_be_proof_paths(be_repo_path: str) -> tuple[str, str]:
    proof = os.path.join(be_repo_path, "output", "verification", "backend_canonical_proof.json")
    verify = os.path.join(be_repo_path, "output", "verification", "backend_canonical_proof.verify.json")
    return proof, verify

def _official_be_evidence_index_path(be_repo_path: str) -> str:
    return os.path.join(be_repo_path, "output", "verification", "backend_canonical_evidence_index.json")

def _official_be_evidence_index_verify_path(be_repo_path: str) -> str:
    return os.path.join(be_repo_path, "output", "verification", "backend_canonical_evidence_index.verify.json")


def _load_be_proof(be_repo_path: str) -> Dict[str, Any]:
    proof_path = os.getenv("ECOAIMS_BE_PROOF_PATH", "").strip()
    if not proof_path:
        proof_path, _ = _official_be_proof_paths(be_repo_path)
    if not os.path.isabs(proof_path):
        proof_path = os.path.join(be_repo_path, proof_path)
    allow_legacy = _truthy_env("ECOAIMS_ALLOW_LEGACY_BE_PROOF_PATH", "false")
    if not allow_legacy:
        official, _ = _official_be_proof_paths(be_repo_path)
        _assert(os.path.abspath(proof_path) == os.path.abspath(official), f"legacy BE proof path not allowed: {proof_path}")
    _assert(os.path.exists(proof_path), f"BE proof artifact missing: {proof_path}")
    return _read_json_file(proof_path)


def _validate_be_proof(be_proof: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons = []
    pt = str(be_proof.get("proof_type") or "")
    if pt != "backend_canonical_proof":
        reasons.append(f"be_proof_invalid:proof_type expected=backend_canonical_proof got={pt or '-'}")

    if not str(be_proof.get("proof_version") or "").strip():
        reasons.append("be_proof_missing:proof_version")

    if str(be_proof.get("artifact_contract_id") or "") != "backend_canonical_proof_contract":
        reasons.append(f"be_proof_invalid:artifact_contract_id expected=backend_canonical_proof_contract got={be_proof.get('artifact_contract_id')}")
    if not str(be_proof.get("artifact_contract_version") or "").strip():
        reasons.append("be_proof_missing:artifact_contract_version")
    if not str(be_proof.get("artifact_contract_hash") or "").strip():
        reasons.append("be_proof_missing:artifact_contract_hash")

    if str(be_proof.get("artifact_hash_algorithm") or "") != "sha256":
        reasons.append(f"be_proof_invalid:artifact_hash_algorithm expected=sha256 got={be_proof.get('artifact_hash_algorithm')}")
    if str(be_proof.get("artifact_serialization") or "") != "json_sort_keys_compact_without_artifact_sha256":
        reasons.append(f"be_proof_invalid:artifact_serialization expected=json_sort_keys_compact_without_artifact_sha256 got={be_proof.get('artifact_serialization')}")

    if str(be_proof.get("proof_subject") or "") != "backend_canonical_verification":
        reasons.append(f"be_proof_invalid:proof_subject expected=backend_canonical_verification got={be_proof.get('proof_subject')}")
    if not str(be_proof.get("proof_verdict") or "").strip():
        reasons.append("be_proof_missing:proof_verdict")
    pvr = be_proof.get("proof_verdict_reasons")
    if not isinstance(pvr, list):
        reasons.append("be_proof_invalid:proof_verdict_reasons_not_list")

    if not str(be_proof.get("artifact_sha256") or "").strip():
        reasons.append("be_proof_missing:artifact_sha256")

    bi = be_proof.get("backend_identity")
    if not isinstance(bi, dict) or not bi:
        reasons.append("be_proof_missing:backend_identity")
    if not str(be_proof.get("backend_identity_fingerprint") or "").strip():
        reasons.append("be_proof_missing:backend_identity_fingerprint")

    if not isinstance(be_proof.get("manifest_summary"), dict):
        reasons.append("be_proof_missing:manifest_summary")

    if be_proof.get("canonical_identity_ok") is not True:
        reasons.append(f"be_proof_canonical_identity_ok_not_true got={be_proof.get('canonical_identity_ok')}")
    if be_proof.get("canonical_verification_ok") is not True:
        reasons.append(f"be_proof_canonical_verification_ok_not_true got={be_proof.get('canonical_verification_ok')}")
    if be_proof.get("integration_ready") is not True:
        reasons.append(f"be_proof_integration_ready_not_true got={be_proof.get('integration_ready')}")
    return (len(reasons) == 0), reasons


def _recompute_be_artifact_sha256(be_proof: Dict[str, Any]) -> str:
    return sha256_json_sort_keys_compact(be_proof if isinstance(be_proof, dict) else {}, exclude_key="artifact_sha256")


def _load_be_verifier_summary(be_repo_path: str) -> Dict[str, Any]:
    p = os.getenv("ECOAIMS_BE_VERIFIER_SUMMARY_PATH", "").strip()
    if not p:
        _, p = _official_be_proof_paths(be_repo_path)
    if not os.path.isabs(p):
        p = os.path.join(be_repo_path, p)
    allow_legacy = _truthy_env("ECOAIMS_ALLOW_LEGACY_BE_PROOF_PATH", "false")
    if not allow_legacy:
        _, official = _official_be_proof_paths(be_repo_path)
        _assert(os.path.abspath(p) == os.path.abspath(official), f"legacy BE verifier summary path not allowed: {p}")
    _assert(os.path.exists(p), f"BE verifier summary missing: {p}")
    return _read_json_file(p)


def _validate_be_verifier_summary(js: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if str(js.get("verification_type") or "") != "backend_canonical_proof_verification":
        reasons.append(f"be_verifier_invalid:verification_type expected=backend_canonical_proof_verification got={js.get('verification_type')}")
    if not str(js.get("verification_version") or "").strip():
        reasons.append("be_verifier_missing:verification_version")

    if str(js.get("summary_contract_id") or "") != "backend_canonical_proof_verification_contract":
        reasons.append(f"be_verifier_invalid:summary_contract_id expected=backend_canonical_proof_verification_contract got={js.get('summary_contract_id')}")
    if not str(js.get("summary_contract_version") or "").strip():
        reasons.append("be_verifier_missing:summary_contract_version")
    if not str(js.get("summary_contract_hash") or "").strip():
        reasons.append("be_verifier_missing:summary_contract_hash")

    if str(js.get("summary_subject") or "") != "backend_canonical_proof_verification":
        reasons.append(f"be_verifier_invalid:summary_subject expected=backend_canonical_proof_verification got={js.get('summary_subject')}")

    if str(js.get("summary_canonical_filename") or "") != "backend_canonical_proof.verify.json":
        reasons.append(f"be_verifier_invalid:summary_canonical_filename expected=backend_canonical_proof.verify.json got={js.get('summary_canonical_filename')}")
    if str(js.get("verified_artifact_canonical_filename") or "") != "backend_canonical_proof.json":
        reasons.append(f"be_verifier_invalid:verified_artifact_canonical_filename expected=backend_canonical_proof.json got={js.get('verified_artifact_canonical_filename')}")

    if str(js.get("summary_hash_algorithm") or "") != "sha256":
        reasons.append(f"be_verifier_invalid:summary_hash_algorithm expected=sha256 got={js.get('summary_hash_algorithm')}")
    if str(js.get("summary_serialization") or "") != "json_sort_keys_compact_without_summary_sha256":
        reasons.append(f"be_verifier_invalid:summary_serialization expected=json_sort_keys_compact_without_summary_sha256 got={js.get('summary_serialization')}")
    if not str(js.get("summary_sha256") or "").strip():
        reasons.append("be_verifier_missing:summary_sha256")

    if not str(js.get("verified_artifact_sha256") or "").strip():
        reasons.append("be_verifier_missing:verified_artifact_sha256")

    for k in ("contract_ok", "hash_ok", "verdict_ok", "final_ok"):
        if js.get(k) is not True:
            reasons.append(f"be_verifier_{k}_not_true got={js.get(k)}")

    if not isinstance(js.get("reasons"), list):
        reasons.append("be_verifier_invalid:reasons_not_list")

    if not str(js.get("backend_identity_fingerprint") or "").strip():
        reasons.append("be_verifier_missing:backend_identity_fingerprint")

    if str(js.get("artifact_contract_id") or "") != "backend_canonical_proof_contract":
        reasons.append(f"be_verifier_invalid:artifact_contract_id expected=backend_canonical_proof_contract got={js.get('artifact_contract_id')}")
    if not str(js.get("artifact_contract_version") or "").strip():
        reasons.append("be_verifier_missing:artifact_contract_version")
    if not str(js.get("artifact_contract_hash") or "").strip():
        reasons.append("be_verifier_missing:artifact_contract_hash")

    return (len(reasons) == 0), reasons


def _recompute_be_verifier_summary_sha256(js: Dict[str, Any]) -> str:
    return sha256_json_sort_keys_compact(js if isinstance(js, dict) else {}, exclude_key="summary_sha256")


def _validate_be_verifier_summary_with_hash(js: Dict[str, Any]) -> tuple[bool, list[str]]:
    ok, reasons = _validate_be_verifier_summary(js)
    if not isinstance(js, dict):
        return False, reasons
    expect = str(js.get("summary_sha256") or "")
    actual = _recompute_be_verifier_summary_sha256(js)
    if not expect or expect != actual:
        reasons.append("be_verifier_summary_sha256_mismatch")
        ok = False
    return ok, reasons


def _load_be_evidence_index(be_repo_path: str) -> Dict[str, Any]:
    p = os.getenv("ECOAIMS_BE_EVIDENCE_INDEX_PATH", "").strip()
    if not p:
        p = _official_be_evidence_index_path(be_repo_path)
    if not os.path.isabs(p):
        p = os.path.join(be_repo_path, p)
    _assert(os.path.exists(p), f"BE evidence index missing: {p}")
    return _read_json_file(p)


def _recompute_be_evidence_index_sha256(idx: Dict[str, Any]) -> str:
    return sha256_json_sort_keys_compact(idx if isinstance(idx, dict) else {}, exclude_key="artifact_sha256")


def _validate_be_evidence_index(idx: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if str(idx.get("evidence_type") or "") != "backend_canonical_evidence_index":
        reasons.append(f"be_index_invalid:evidence_type expected=backend_canonical_evidence_index got={idx.get('evidence_type')}")
    if str(idx.get("artifact_contract_id") or "") != "backend_canonical_evidence_index_contract":
        reasons.append(f"be_index_invalid:artifact_contract_id expected=backend_canonical_evidence_index_contract got={idx.get('artifact_contract_id')}")
    if not str(idx.get("artifact_contract_version") or "").strip():
        reasons.append("be_index_missing:artifact_contract_version")
    if not str(idx.get("artifact_contract_hash") or "").strip():
        reasons.append("be_index_missing:artifact_contract_hash")
    if str(idx.get("artifact_hash_algorithm") or "") != "sha256":
        reasons.append(f"be_index_invalid:artifact_hash_algorithm expected=sha256 got={idx.get('artifact_hash_algorithm')}")
    if str(idx.get("artifact_serialization") or "") != "json_sort_keys_compact_without_artifact_sha256":
        reasons.append(f"be_index_invalid:artifact_serialization expected=json_sort_keys_compact_without_artifact_sha256 got={idx.get('artifact_serialization')}")
    if not str(idx.get("artifact_sha256") or "").strip():
        reasons.append("be_index_missing:artifact_sha256")
    else:
        recomputed = _recompute_be_evidence_index_sha256(idx)
        if str(idx.get("artifact_sha256") or "") != recomputed:
            reasons.append("be_index_artifact_sha256_mismatch")
    cp = idx.get("canonical_proof") if isinstance(idx.get("canonical_proof"), dict) else {}
    cv = idx.get("canonical_proof_verification") if isinstance(idx.get("canonical_proof_verification"), dict) else {}
    if not str(cp.get("path") or "").strip():
        reasons.append("be_index_missing:canonical_proof.path")
    if not str(cp.get("artifact_sha256") or "").strip():
        reasons.append("be_index_missing:canonical_proof.artifact_sha256")
    if not str(cv.get("path") or "").strip():
        reasons.append("be_index_missing:canonical_proof_verification.path")
    if not str(cv.get("summary_sha256") or "").strip():
        reasons.append("be_index_missing:canonical_proof_verification.summary_sha256")
    if not str(idx.get("backend_identity_fingerprint") or "").strip():
        reasons.append("be_index_missing:backend_identity_fingerprint")
    cc = idx.get("chain_consistency") if isinstance(idx.get("chain_consistency"), dict) else {}
    if cc.get("final_bundle_ok") is not True:
        reasons.append(f"be_index_chain_consistency_final_bundle_ok_not_true got={cc.get('final_bundle_ok')}")
    return (len(reasons) == 0), reasons


def _load_be_evidence_index_verify_summary(be_repo_path: str) -> Dict[str, Any]:
    p = os.getenv("ECOAIMS_BE_EVIDENCE_INDEX_VERIFY_PATH", "").strip()
    if not p:
        p = _official_be_evidence_index_verify_path(be_repo_path)
    if not os.path.isabs(p):
        p = os.path.join(be_repo_path, p)
    _assert(os.path.exists(p), f"BE evidence index verifier summary missing: {p}")
    return _read_json_file(p)


def _recompute_be_evidence_index_verify_sha256(js: Dict[str, Any]) -> str:
    return sha256_json_sort_keys_compact(js if isinstance(js, dict) else {}, exclude_key="summary_sha256")


def _validate_be_evidence_index_verify_summary(js: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if str(js.get("verification_type") or "") != "backend_canonical_evidence_index_verification":
        reasons.append(f"be_index_verify_invalid:verification_type expected=backend_canonical_evidence_index_verification got={js.get('verification_type')}")
    if str(js.get("summary_contract_id") or "") != "backend_canonical_evidence_index_verification_contract":
        reasons.append(f"be_index_verify_invalid:summary_contract_id expected=backend_canonical_evidence_index_verification_contract got={js.get('summary_contract_id')}")
    if not str(js.get("verification_version") or "").strip():
        reasons.append("be_index_verify_missing:verification_version")
    if not str(js.get("summary_contract_version") or "").strip():
        reasons.append("be_index_verify_missing:summary_contract_version")
    if not str(js.get("summary_contract_hash") or "").strip():
        reasons.append("be_index_verify_missing:summary_contract_hash")
    if str(js.get("summary_subject") or "") != "backend_canonical_evidence_index_verification":
        reasons.append(f"be_index_verify_invalid:summary_subject expected=backend_canonical_evidence_index_verification got={js.get('summary_subject')}")
    if str(js.get("summary_canonical_filename") or "") != "backend_canonical_evidence_index.verify.json":
        reasons.append(f"be_index_verify_invalid:summary_canonical_filename expected=backend_canonical_evidence_index.verify.json got={js.get('summary_canonical_filename')}")
    if str(js.get("verified_artifact_canonical_filename") or "") != "backend_canonical_evidence_index.json":
        reasons.append(f"be_index_verify_invalid:verified_artifact_canonical_filename expected=backend_canonical_evidence_index.json got={js.get('verified_artifact_canonical_filename')}")
    if str(js.get("summary_hash_algorithm") or "") != "sha256":
        reasons.append(f"be_index_verify_invalid:summary_hash_algorithm expected=sha256 got={js.get('summary_hash_algorithm')}")
    if str(js.get("summary_serialization") or "") != "json_sort_keys_compact_without_summary_sha256":
        reasons.append(f"be_index_verify_invalid:summary_serialization expected=json_sort_keys_compact_without_summary_sha256 got={js.get('summary_serialization')}")
    if not str(js.get("summary_sha256") or "").strip():
        reasons.append("be_index_verify_missing:summary_sha256")
    if not str(js.get("verified_artifact_sha256") or "").strip():
        reasons.append("be_index_verify_missing:verified_artifact_sha256")
    if not str(js.get("backend_identity_fingerprint") or "").strip():
        reasons.append("be_index_verify_missing:backend_identity_fingerprint")
    if not isinstance(js.get("reasons"), list):
        reasons.append("be_index_verify_invalid:reasons_not_list")
    for k in ("contract_ok", "hash_ok", "chain_ok", "verdict_ok", "final_ok"):
        if js.get(k) is not True:
            reasons.append(f"be_index_verify_{k}_not_true got={js.get(k)}")
    if not str(js.get("summary_sha256") or "").strip() or str(js.get("summary_sha256") or "") != _recompute_be_evidence_index_verify_sha256(js):
        reasons.append("be_index_verify_summary_sha256_mismatch")
    return (len(reasons) == 0), reasons


def _pick_backend_summary(js: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(js, dict):
        return {}
    keep = {}
    for k in ("schema_version", "contract_version", "contract_manifest_id", "contract_manifest_hash", "backend_ready", "required_endpoints", "overall_status", "backend_identity", "server_time", "version"):
        if k in js:
            keep[k] = js.get(k)
    if "features" in js and isinstance(js.get("features"), dict):
        keep["features"] = {k: {"status": (v.get("status") if isinstance(v, dict) else None), "recommended_mode": (v.get("recommended_mode") if isinstance(v, dict) else None)} for k, v in js["features"].items()}
    return keep


def main() -> int:
    lane = "canonical_crossrepo"
    proof_path = os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_proof.json")
    contract_path = os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_proof_contract.json")

    backend_url = os.getenv("ECOAIMS_API_BASE_URL", "").strip().rstrip("/")
    be_repo_path = os.getenv("ECOAIMS_BE_REPO_PATH", "").strip()
    use_be_repo_proof = bool(be_repo_path)
    runtime_only = bool(backend_url) and not use_be_repo_proof

    if not backend_url and not be_repo_path:
        print("ERROR: verify-canonical-crossrepo requires ECOAIMS_API_BASE_URL or ECOAIMS_BE_REPO_PATH")
        return 2

    be_proof = None
    be_proof_ok = None
    be_proof_reasons = []
    be_proof_artifact_sha256 = None
    be_proof_artifact_sha256_ok = None
    be_proof_verifier = None
    be_proof_verifier_ok = None
    be_proof_verifier_reasons: list[str] = []
    be_proof_verifier_summary_sha256 = None
    be_proof_verifier_summary_sha256_ok = None
    be_proof_verifier_summary_contract_id = None
    be_proof_verifier_summary_contract_version = None
    be_proof_verifier_summary_contract_hash = None
    be_proof_contract_ok = None
    be_make = {"verify-canonical": None, "emit-canonical-proof": None, "verify-and-emit-canonical-evidence-bundle": None}
    be_proof_path = os.getenv("ECOAIMS_BE_PROOF_PATH", "").strip() or (os.path.join(be_repo_path, "output", "verification", "backend_canonical_proof.json") if be_repo_path else None)
    be_verifier_path = os.getenv("ECOAIMS_BE_VERIFIER_SUMMARY_PATH", "").strip() or (os.path.join(be_repo_path, "output", "verification", "backend_canonical_proof.verify.json") if be_repo_path else None)
    be_index_path = os.getenv("ECOAIMS_BE_EVIDENCE_INDEX_PATH", "").strip() or (os.path.join(be_repo_path, "output", "verification", "backend_canonical_evidence_index.json") if be_repo_path else None)
    be_index_verify_path = os.getenv("ECOAIMS_BE_EVIDENCE_INDEX_VERIFY_PATH", "").strip() or (os.path.join(be_repo_path, "output", "verification", "backend_canonical_evidence_index.verify.json") if be_repo_path else None)
    be_index = None
    be_index_ok = None
    be_index_reasons: list[str] = []
    be_index_artifact_sha256 = None
    be_index_artifact_sha256_ok = None
    be_index_contract_id = None
    be_index_contract_version = None
    be_index_contract_hash = None
    be_index_verify = None
    be_index_verify_ok = None
    be_index_verify_reasons: list[str] = []
    be_index_verify_summary_sha256 = None
    be_index_verify_summary_sha256_ok = None
    be_index_verify_contract_id = None
    be_index_verify_contract_version = None
    be_index_verify_contract_hash = None
    be_index_backend_identity_fingerprint = None
    be_index_identity_fingerprint_match = None
    be_index_chain_ok = None

    if use_be_repo_proof:
        allow_legacy = _truthy_env("ECOAIMS_ALLOW_LEGACY_BE_PROOF_PATH", "false")
        rc, out = _run_make(be_repo_path, "verify-and-emit-canonical-evidence-bundle")
        be_make["verify-and-emit-canonical-evidence-bundle"] = {"exit_code": rc, "output": out[:4000]}
        if rc != 0:
            _assert(allow_legacy, "BE make verify-and-emit-canonical-evidence-bundle failed and legacy not allowed")
            rc2, out2 = _run_make(be_repo_path, "verify-and-emit-canonical-proof")
            be_make["verify-canonical"] = {"exit_code": rc2, "output": out2[:4000]}
            _assert(rc2 == 0, "BE make verify-and-emit-canonical-proof failed (legacy)")
            rc3, out3 = _run_make(be_repo_path, "emit-canonical-proof-verification-summary")
            be_make["emit-canonical-proof"] = {"exit_code": rc3, "output": out3[:4000]}
            _assert(rc3 == 0, "BE make emit-canonical-proof-verification-summary failed (legacy)")

        # Prefer official evidence index
        try:
            be_index = _load_be_evidence_index(be_repo_path)
            be_index_ok, be_index_reasons = _validate_be_evidence_index(be_index)
            _assert(be_index_ok is True, f"BE evidence index invalid: {','.join(be_index_reasons) or '-'}")
            be_index_artifact_sha256 = str(be_index.get("artifact_sha256") or "")
            be_index_artifact_sha256_ok = bool(be_index_artifact_sha256 and be_index_artifact_sha256 == _recompute_be_evidence_index_sha256(be_index))
            _assert(be_index_artifact_sha256_ok is True, "BE evidence index artifact_sha256 mismatch")
            be_index_contract_id = str(be_index.get("artifact_contract_id") or "")
            be_index_contract_version = str(be_index.get("artifact_contract_version") or "")
            be_index_contract_hash = str(be_index.get("artifact_contract_hash") or "")
            be_index_backend_identity_fingerprint = str(be_index.get("backend_identity_fingerprint") or "")
            be_index_chain_ok = bool((be_index.get("chain_consistency") or {}).get("final_bundle_ok") is True)

            be_index_verify = _load_be_evidence_index_verify_summary(be_repo_path)
            be_index_verify_ok, be_index_verify_reasons = _validate_be_evidence_index_verify_summary(be_index_verify)
            _assert(be_index_verify_ok is True, f"BE evidence index verifier invalid: {','.join(be_index_verify_reasons) or '-'}")
            be_index_verify_summary_sha256 = str(be_index_verify.get("summary_sha256") or "")
            be_index_verify_summary_sha256_ok = bool(be_index_verify_summary_sha256 and be_index_verify_summary_sha256 == _recompute_be_evidence_index_verify_sha256(be_index_verify))
            _assert(be_index_verify_summary_sha256_ok is True, "BE evidence index verifier summary_sha256 mismatch")
            _assert(str(be_index_verify.get("verified_artifact_sha256") or "") == be_index_artifact_sha256, "BE evidence index verifier verified_artifact_sha256 mismatch")
            _assert(str(be_index_verify.get("backend_identity_fingerprint") or "") == be_index_backend_identity_fingerprint, "BE evidence index verifier backend_identity_fingerprint mismatch")

            be_index_verify_contract_id = str(be_index_verify.get("summary_contract_id") or "")
            be_index_verify_contract_version = str(be_index_verify.get("summary_contract_version") or "")
            be_index_verify_contract_hash = str(be_index_verify.get("summary_contract_hash") or "")
            # Resolve proof & verifier paths from index (relative to BE repo)
            cp = be_index.get("canonical_proof") if isinstance(be_index.get("canonical_proof"), dict) else {}
            cv = be_index.get("canonical_proof_verification") if isinstance(be_index.get("canonical_proof_verification"), dict) else {}
            be_proof_path = os.path.join(be_repo_path, str(cp.get("path")))
            be_verifier_path = os.path.join(be_repo_path, str(cv.get("path")))
        except Exception as ex:
            _assert(allow_legacy, f"BE evidence index unavailable or invalid and legacy not allowed: {type(ex).__name__}: {ex}")

        be_proof = _read_json_file(be_proof_path) if be_proof_path else _load_be_proof(be_repo_path)
        be_proof_ok, be_proof_reasons = _validate_be_proof(be_proof)
        _assert(be_proof_ok is True, f"BE proof invalid: {','.join(be_proof_reasons) or '-'}")
        be_proof_artifact_sha256 = str((be_proof or {}).get("artifact_sha256") or "")
        recomputed = _recompute_be_artifact_sha256(be_proof if isinstance(be_proof, dict) else {})
        be_proof_artifact_sha256_ok = bool(be_proof_artifact_sha256 and be_proof_artifact_sha256 == recomputed)
        _assert(be_proof_artifact_sha256_ok is True, "BE proof artifact_sha256 mismatch")

        be_proof_verifier = _read_json_file(be_verifier_path) if be_verifier_path else _load_be_verifier_summary(be_repo_path)
        be_proof_verifier_ok, be_proof_verifier_reasons = _validate_be_verifier_summary_with_hash(be_proof_verifier)
        _assert(be_proof_verifier_ok is True, f"BE verifier summary invalid: {','.join(be_proof_verifier_reasons) or '-'}")
        be_proof_contract_ok = be_proof_verifier.get("contract_ok") is True if isinstance(be_proof_verifier, dict) else False

        be_proof_verifier_summary_sha256 = str(be_proof_verifier.get("summary_sha256") or "")
        recomputed_vs = _recompute_be_verifier_summary_sha256(be_proof_verifier)
        be_proof_verifier_summary_sha256_ok = bool(be_proof_verifier_summary_sha256 and be_proof_verifier_summary_sha256 == recomputed_vs)

        be_proof_verifier_summary_contract_id = str(be_proof_verifier.get("summary_contract_id") or "")
        be_proof_verifier_summary_contract_version = str(be_proof_verifier.get("summary_contract_version") or "")
        be_proof_verifier_summary_contract_hash = str(be_proof_verifier.get("summary_contract_hash") or "")

        _assert(str(be_proof_verifier.get("verified_artifact_sha256") or "") == be_proof_artifact_sha256, "BE verifier verified_artifact_sha256 mismatch")
        _assert(str(be_proof_verifier.get("backend_identity_fingerprint") or "") == str((be_proof or {}).get("backend_identity_fingerprint") or ""), "BE verifier backend_identity_fingerprint mismatch")
        _assert(str(be_proof_verifier.get("artifact_contract_id") or "") == str((be_proof or {}).get("artifact_contract_id") or ""), "BE verifier artifact_contract_id mismatch vs BE proof")
        _assert(str(be_proof_verifier.get("artifact_contract_version") or "") == str((be_proof or {}).get("artifact_contract_version") or ""), "BE verifier artifact_contract_version mismatch vs BE proof")
        _assert(str(be_proof_verifier.get("artifact_contract_hash") or "") == str((be_proof or {}).get("artifact_contract_hash") or ""), "BE verifier artifact_contract_hash mismatch vs BE proof")
        _assert(be_proof_verifier.get("final_ok") is True, "BE verifier final_ok not true")
        if not backend_url:
            backend_url = str(be_proof.get("api_base_url") or be_proof.get("base_url") or "").strip().rstrip("/")
            _assert(bool(backend_url), "BE proof missing base_url and ECOAIMS_API_BASE_URL not set")

    backend_url = backend_url.rstrip("/")
    _wait_http_ok(f"{backend_url}/health", timeout_s=30.0)

    si = requests.get(f"{backend_url}/api/startup-info", timeout=8)
    _assert(si.status_code == 200, f"backend /api/startup-info status {si.status_code}")
    startup_info = si.json() if si.headers.get("content-type", "").startswith("application/json") else {}

    ss = requests.get(f"{backend_url}/api/system/status", timeout=8)
    _assert(ss.status_code == 200, f"backend /api/system/status status {ss.status_code}")
    system_status = ss.json() if ss.headers.get("content-type", "").startswith("application/json") else {}

    from ecoaims_frontend.services.readiness_service import get_backend_readiness

    rr = get_backend_readiness()
    runtime_backend_identity = rr.get("backend_identity") if isinstance(rr.get("backend_identity"), dict) else {}
    runtime_backend_identity_fp_recomputed = str(rr.get("backend_identity_fingerprint_recomputed") or "").strip() or fingerprint_backend_identity(runtime_backend_identity)
    runtime_backend_identity_fp_reported = str(rr.get("backend_identity_fingerprint") or "").strip()
    runtime_backend_identity_fp = runtime_backend_identity_fp_reported or runtime_backend_identity_fp_recomputed
    allow_legacy_identity_match = _truthy_env("ECOAIMS_ALLOW_LEGACY_BE_PROOF_PATH", "false")

    identity_crosscheck_ok = None
    identity_crosscheck_reasons = []
    if isinstance(be_proof, dict):
        be_identity = be_proof.get("backend_identity") if isinstance(be_proof.get("backend_identity"), dict) else {}
        be_fp = str(be_proof.get("backend_identity_fingerprint") or "")
        recomputed = runtime_backend_identity_fp_recomputed
        if be_fp and be_fp == recomputed:
            identity_crosscheck_ok = True
        elif allow_legacy_identity_match and _identity_subset_match(be_identity, runtime_backend_identity):
            identity_crosscheck_ok = True
            identity_crosscheck_reasons.append("legacy_identity_subset_match_used:be_proof")
        else:
            identity_crosscheck_ok = False
            identity_crosscheck_reasons.append("be_proof_identity_fingerprint_mismatch")
    if isinstance(be_index, dict):
        expected_fp = str(be_index.get("backend_identity_fingerprint") or "")
        expected_bi = be_index.get("backend_identity") if isinstance(be_index.get("backend_identity"), dict) else {}
        recomputed = runtime_backend_identity_fp_recomputed
        if expected_fp and expected_fp == recomputed:
            be_index_identity_fingerprint_match = True
        elif allow_legacy_identity_match and _identity_subset_match(expected_bi, runtime_backend_identity):
            be_index_identity_fingerprint_match = True
            identity_crosscheck_reasons.append("legacy_identity_subset_match_used:evidence_index")
        else:
            be_index_identity_fingerprint_match = False

    env_fe = os.environ.copy()
    env_fe["ECOAIMS_API_BASE_URL"] = backend_url
    env_fe["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true"
    env_fe["ECOAIMS_FRONTEND_PORT"] = os.getenv("ECOAIMS_FRONTEND_PORT", "8072")
    env_fe["ECOAIMS_FRONTEND_HOST"] = os.getenv("ECOAIMS_FRONTEND_HOST", "127.0.0.1")

    proc_fe = subprocess.Popen([sys.executable, "-m", "ecoaims_frontend.app"], env=env_fe, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fe_url = f"http://{env_fe['ECOAIMS_FRONTEND_HOST']}:{env_fe['ECOAIMS_FRONTEND_PORT']}"

    runtime_smoke_ok = False
    runtime_smoke_output = ""
    browser_smoke_ok: Optional[bool] = None
    browser_smoke_output = ""

    try:
        _wait_http_ok(f"{fe_url}/_dash-layout", timeout_s=25.0)

        e = os.environ.copy()
        e["ECOAIMS_API_BASE_URL"] = backend_url
        e["ECOAIMS_FRONTEND_URL"] = fe_url
        e["ECOAIMS_REQUIRE_CANONICAL_POLICY"] = "true"
        p = subprocess.run([sys.executable, "scripts/smoke_runtime.py"], env=e, capture_output=True, text=True)
        runtime_smoke_ok = p.returncode == 0
        runtime_smoke_output = ((p.stdout or "") + ("\n" + p.stderr if p.stderr else "")).strip()[:4000]

        try:
            p = subprocess.run([sys.executable, "scripts/smoke_browser_tabs_playwright.py"], env={**os.environ.copy(), "ECOAIMS_FRONTEND_URL": fe_url}, capture_output=True, text=True)
            browser_smoke_ok = p.returncode == 0
            browser_smoke_output = ((p.stdout or "") + ("\n" + p.stderr if p.stderr else "")).strip()[:4000]
        except Exception as ex:
            browser_smoke_ok = None
            browser_smoke_output = f"skipped: {type(ex).__name__}: {ex}"
    finally:
        proc_fe.terminate()
        try:
            proc_fe.wait(timeout=5)
        except Exception:
            proc_fe.kill()

    verification_ok = rr.get("verification_ok") is True
    verification_reasons = rr.get("verification_reasons") if isinstance(rr.get("verification_reasons"), list) else []

    runtime_only_crossrepo_ok = bool(runtime_only and runtime_smoke_ok and verification_ok)
    full_crossrepo_proof_ok = bool(
        use_be_repo_proof
        and be_index_ok is True
        and be_index_artifact_sha256_ok is True
        and be_index_verify_ok is True
        and be_index_verify_summary_sha256_ok is True
        and be_index_identity_fingerprint_match is True
        and be_index_chain_ok is True
        and be_proof_ok is True
        and be_proof_artifact_sha256_ok is True
        and be_proof_verifier_ok is True
        and be_proof_verifier_summary_sha256_ok is True
        and identity_crosscheck_ok is True
        and runtime_smoke_ok
        and (browser_smoke_ok is True)
    )
    crossrepo_canonical_proof_ok = bool(full_crossrepo_proof_ok or runtime_only_crossrepo_ok)
    proof_chain_ok = bool(full_crossrepo_proof_ok)

    fe_identity = {
        "repo_id": "ECOAIMS_Adv_FE",
        "frontend_app": "ecoaims_frontend.app",
        "integration_mode": str(rr.get("integration_mode") or ""),
        "verification_lane": str(rr.get("verification_lane") or ""),
    }

    contract = _read_json_file(contract_path) if os.path.exists(contract_path) else {}
    contract_id = str(contract.get("artifact_contract_id") or "canonical_crossrepo_proof_contract")
    contract_version = str(contract.get("artifact_contract_version") or "canonical_crossrepo_proof_v1")
    contract_hash = sha256_json_sort_keys_compact(contract if isinstance(contract, dict) else {})
    fe_artifact_contract_ok = bool(contract_id == "canonical_crossrepo_proof_contract" and contract_version and contract_hash)

    payload: Dict[str, Any] = {
        "proof_type": "ecoaims_frontend.canonical_crossrepo_proof",
        "proof_version": "2026-03-13",
        "generated_at": _now_iso(),
        "lane": lane,
        "mode": "full_crossrepo_proof" if use_be_repo_proof else "remote_runtime_verified",
        "artifact_contract_id": contract_id,
        "artifact_contract_version": contract_version,
        "artifact_contract_hash": contract_hash,
        "artifact_hash_algorithm": "sha256",
        "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
        "frontend_identity": fe_identity,
        "backend_proof_summary": {
            "backend_identity": runtime_backend_identity,
            "backend_identity_fingerprint": runtime_backend_identity_fp,
            "canonical_identity_ok": rr.get("backend_identity_ok") is True,
            "canonical_verification_ok": verification_ok,
            "integration_ready": rr.get("canonical_backend_verified") is True,
            "policy_source": rr.get("policy_source"),
            "registry_loaded": rr.get("registry_loaded") is True,
        },
        "backend_inputs": {
            "api_base_url": backend_url,
            "startup_info": _pick_backend_summary(startup_info if isinstance(startup_info, dict) else {}),
            "system_status": _pick_backend_summary(system_status if isinstance(system_status, dict) else {}),
        },
        "be_proof_path": be_proof_path,
        "be_proof_contract_id": (str(be_proof.get("artifact_contract_id")) if isinstance(be_proof, dict) else None),
        "be_proof_contract_version": (str(be_proof.get("artifact_contract_version")) if isinstance(be_proof, dict) else None),
        "be_proof_contract_hash": (str(be_proof.get("artifact_contract_hash")) if isinstance(be_proof, dict) else None),
        "be_proof_artifact_sha256": be_proof_artifact_sha256,
        "be_proof_artifact_sha256_ok": be_proof_artifact_sha256_ok,
        "be_proof_verifier_summary_path": be_verifier_path,
        "be_proof_verifier_ok": be_proof_verifier_ok,
        "be_proof_verifier_reasons": be_proof_verifier_reasons,
        "be_proof_verifier_summary_sha256": be_proof_verifier_summary_sha256,
        "be_proof_verifier_summary_sha256_ok": be_proof_verifier_summary_sha256_ok,
        "be_proof_verifier_summary_contract_id": be_proof_verifier_summary_contract_id,
        "be_proof_verifier_summary_contract_version": be_proof_verifier_summary_contract_version,
        "be_proof_verifier_summary_contract_hash": be_proof_verifier_summary_contract_hash,
        "be_proof_contract_ok": be_proof_contract_ok,
        "be_runtime_identity_fingerprint_match": identity_crosscheck_ok,
        "be_evidence_index_path": be_index_path,
        "be_evidence_index_contract_id": be_index_contract_id,
        "be_evidence_index_contract_version": be_index_contract_version,
        "be_evidence_index_contract_hash": be_index_contract_hash,
        "be_evidence_index_artifact_sha256": be_index_artifact_sha256,
        "be_evidence_index_artifact_sha256_ok": be_index_artifact_sha256_ok,
        "be_evidence_index_verify_path": be_index_verify_path,
        "be_evidence_index_verify_contract_id": be_index_verify_contract_id,
        "be_evidence_index_verify_contract_version": be_index_verify_contract_version,
        "be_evidence_index_verify_contract_hash": be_index_verify_contract_hash,
        "be_evidence_index_verify_summary_sha256": be_index_verify_summary_sha256,
        "be_evidence_index_verify_summary_sha256_ok": be_index_verify_summary_sha256_ok,
        "be_evidence_index_verify_ok": be_index_verify_ok,
        "be_evidence_index_identity_fingerprint_match": be_index_identity_fingerprint_match,
        "be_evidence_index_chain_ok": be_index_chain_ok,
        "proof_chain_ok": proof_chain_ok,
        "fe_artifact_contract_ok": fe_artifact_contract_ok,
        "frontend_runtime_smoke": {"pass": runtime_smoke_ok, "verification_ok": verification_ok, "verification_reasons": verification_reasons, "output": runtime_smoke_output},
        "frontend_browser_smoke": {"pass": browser_smoke_ok, "output": browser_smoke_output},
        "be_repo_proof": {
            "used": use_be_repo_proof,
            "make": be_make,
            "proof_ok": be_proof_ok,
            "proof_reasons": be_proof_reasons,
            "verifier_ok": be_proof_verifier_ok,
            "verifier_reasons": be_proof_verifier_reasons,
        },
        "final_verdict": {
            "full_crossrepo_proof_ok": full_crossrepo_proof_ok,
            "runtime_only_crossrepo_ok": runtime_only_crossrepo_ok,
            "crossrepo_canonical_proof_ok": crossrepo_canonical_proof_ok,
        },
    }

    payload["artifact_sha256"] = sha256_json_sort_keys_compact(payload, exclude_key="artifact_sha256")
    _write_json_file(proof_path, payload)

    if not crossrepo_canonical_proof_ok:
        if not runtime_smoke_ok and "endpoint_not_in_manifest" in (runtime_smoke_output or ""):
            print("HINT: backend contract registry manifest belum memuat endpoint specs yang dibutuhkan (endpoint_not_in_manifest).")
        if use_be_repo_proof and be_index_identity_fingerprint_match is False:
            print("ERROR: backend_identity_fingerprint mismatch (runtime vs BE evidence index).")
        if use_be_repo_proof and identity_crosscheck_ok is False:
            print("ERROR: backend_identity_fingerprint mismatch (runtime vs BE canonical proof).")
        print(f"FAIL: wrote proof artifact but verification not OK: {proof_path}")
        return 1
    print(f"OK: wrote proof artifact: {proof_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
