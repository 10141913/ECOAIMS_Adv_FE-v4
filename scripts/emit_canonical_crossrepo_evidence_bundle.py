import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json_sort_keys_compact(payload: Dict[str, Any], exclude_key: str | None = None) -> str:
    d = payload if isinstance(payload, dict) else {}
    if exclude_key and exclude_key in d:
        d = {k: v for k, v in d.items() if k != exclude_key}
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fingerprint_identity(identity: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(identity if isinstance(identity, dict) else {}).encode("utf-8")).hexdigest()


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return js if isinstance(js, dict) else {"data": js}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_evidence_bundle.json"))
    ap.add_argument("--proof", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_proof.json"))
    ap.add_argument("--proof-verify", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_proof.verify.json"))
    ap.add_argument("--be-index-path", default="")
    ap.add_argument("--be-index-verify-path", default="")
    args = ap.parse_args()

    _assert(os.path.exists(args.proof), f"missing proof: {args.proof}")
    _assert(os.path.exists(args.proof_verify), f"missing proof verification summary: {args.proof_verify}")

    proof = _read_json(args.proof)
    proof_verify = _read_json(args.proof_verify)

    be_idx_path = args.be_index_path.strip() or str(proof.get("be_evidence_index_path") or "")
    be_idx_verify_path = args.be_index_verify_path.strip() or str(proof.get("be_evidence_index_verify_path") or "")
    _assert(bool(be_idx_path), "missing be_evidence_index_path (provide --be-index-path or run full-proof)")
    _assert(bool(be_idx_verify_path), "missing be_evidence_index_verify_path (provide --be-index-verify-path or run full-proof)")
    _assert(os.path.exists(be_idx_path), f"missing backend evidence index: {be_idx_path}")
    _assert(os.path.exists(be_idx_verify_path), f"missing backend evidence index verification: {be_idx_verify_path}")

    be_idx = _read_json(be_idx_path)
    be_idx_verify = _read_json(be_idx_verify_path)

    contract_path = os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_evidence_bundle_contract.json")
    contract = _read_json(contract_path)
    contract_id = str(contract.get("artifact_contract_id") or "canonical_crossrepo_evidence_bundle_contract")
    contract_version = str(contract.get("artifact_contract_version") or "canonical_crossrepo_evidence_bundle_v1")
    contract_hash = sha256_json_sort_keys_compact(contract)

    frontend_identity = proof.get("frontend_identity") if isinstance(proof.get("frontend_identity"), dict) else {}
    backend_identity = (proof.get("backend_proof_summary") or {}).get("backend_identity") if isinstance(proof.get("backend_proof_summary"), dict) else {}
    backend_identity = backend_identity if isinstance(backend_identity, dict) else {}

    fe_fp = fingerprint_identity(frontend_identity)
    be_fp = str(proof.get("backend_proof_summary", {}).get("backend_identity_fingerprint") or "") if isinstance(proof.get("backend_proof_summary"), dict) else ""
    if not be_fp:
        be_fp = fingerprint_identity(backend_identity)

    proof_sub = {
        "path": os.path.relpath(args.proof, ROOT_DIR),
        "canonical_filename": "canonical_crossrepo_proof.json",
        "proof_type": str(proof.get("proof_type") or ""),
        "artifact_sha256": str(proof.get("artifact_sha256") or ""),
        "artifact_contract_id": str(proof.get("artifact_contract_id") or ""),
        "artifact_contract_version": str(proof.get("artifact_contract_version") or ""),
        "artifact_contract_hash": str(proof.get("artifact_contract_hash") or ""),
        "full_crossrepo_proof_ok": bool((proof.get("final_verdict") or {}).get("full_crossrepo_proof_ok") is True) if isinstance(proof.get("final_verdict"), dict) else False,
        "runtime_only_crossrepo_ok": bool((proof.get("final_verdict") or {}).get("runtime_only_crossrepo_ok") is True) if isinstance(proof.get("final_verdict"), dict) else False,
        "crossrepo_canonical_proof_ok": bool((proof.get("final_verdict") or {}).get("crossrepo_canonical_proof_ok") is True) if isinstance(proof.get("final_verdict"), dict) else False,
    }
    proof_verify_sub = {
        "path": os.path.relpath(args.proof_verify, ROOT_DIR),
        "canonical_filename": "canonical_crossrepo_proof.verify.json",
        "verification_type": str(proof_verify.get("verification_type") or ""),
        "summary_sha256": str(proof_verify.get("summary_sha256") or ""),
        "summary_contract_id": str(proof_verify.get("summary_contract_id") or ""),
        "summary_contract_version": str(proof_verify.get("summary_contract_version") or ""),
        "summary_contract_hash": str(proof_verify.get("summary_contract_hash") or ""),
        "final_ok": proof_verify.get("final_ok") is True,
    }

    be_final_bundle_ok = bool(
        (be_idx.get("final_bundle_ok") is True)
        or (
            isinstance(be_idx.get("chain_consistency"), dict)
            and (be_idx.get("chain_consistency") or {}).get("final_bundle_ok") is True
        )
    )
    be_idx_sub = {
        "path": os.path.relpath(be_idx_path, ROOT_DIR),
        "canonical_filename": "backend_canonical_evidence_index.json",
        "artifact_sha256": str(be_idx.get("artifact_sha256") or ""),
        "artifact_contract_id": str(be_idx.get("artifact_contract_id") or ""),
        "artifact_contract_version": str(be_idx.get("artifact_contract_version") or ""),
        "artifact_contract_hash": str(be_idx.get("artifact_contract_hash") or ""),
        "final_bundle_ok": be_final_bundle_ok,
    }
    be_idx_verify_sub = {
        "path": os.path.relpath(be_idx_verify_path, ROOT_DIR),
        "canonical_filename": "backend_canonical_evidence_index.verify.json",
        "verification_type": str(be_idx_verify.get("verification_type") or ""),
        "summary_sha256": str(be_idx_verify.get("summary_sha256") or ""),
        "summary_contract_id": str(be_idx_verify.get("summary_contract_id") or ""),
        "summary_contract_version": str(be_idx_verify.get("summary_contract_version") or ""),
        "summary_contract_hash": str(be_idx_verify.get("summary_contract_hash") or ""),
        "final_ok": be_idx_verify.get("final_ok") is True,
    }

    reasons = []
    proof_exists = os.path.exists(args.proof)
    proof_verify_exists = os.path.exists(args.proof_verify)
    be_idx_exists = os.path.exists(be_idx_path)
    be_idx_verify_exists = os.path.exists(be_idx_verify_path)
    if not proof_exists:
        reasons.append("missing:proof")
    if not proof_verify_exists:
        reasons.append("missing:proof_verification")
    if not be_idx_exists:
        reasons.append("missing:backend_evidence_index")
    if not be_idx_verify_exists:
        reasons.append("missing:backend_evidence_index_verification")

    backend_identity_match = str(be_idx.get("backend_identity_fingerprint") or "") == be_fp if isinstance(be_idx, dict) else False
    if not backend_identity_match:
        reasons.append("backend_identity_fingerprint_mismatch")
    if proof_verify_sub["final_ok"] is not True:
        reasons.append("proof_verification_final_ok_false")
    if be_idx_verify_sub["final_ok"] is not True:
        reasons.append("backend_evidence_index_verification_final_ok_false")

    final_bundle_ok = bool(
        proof_exists
        and proof_verify_exists
        and be_idx_exists
        and be_idx_verify_exists
        and backend_identity_match
        and proof_verify_sub["final_ok"] is True
        and be_idx_verify_sub["final_ok"] is True
        and be_final_bundle_ok is True
    )

    payload: Dict[str, Any] = {
        "evidence_type": "canonical_crossrepo_evidence_bundle",
        "evidence_version": "canonical_crossrepo_evidence_bundle_v1",
        "generated_at": _now_iso(),
        "evidence_subject": "canonical_crossrepo_verification_bundle",
        "artifact_contract_id": contract_id,
        "artifact_contract_version": contract_version,
        "artifact_contract_hash": contract_hash,
        "artifact_hash_algorithm": "sha256",
        "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
        "canonical_crossrepo_proof": proof_sub,
        "canonical_crossrepo_proof_verification": proof_verify_sub,
        "backend_evidence_index": be_idx_sub,
        "backend_evidence_index_verification": be_idx_verify_sub,
        "frontend_identity": frontend_identity,
        "backend_identity": backend_identity,
        "frontend_identity_fingerprint": fe_fp,
        "backend_identity_fingerprint": be_fp,
        "chain_consistency": {
            "proof_exists": proof_exists,
            "proof_verification_exists": proof_verify_exists,
            "backend_evidence_index_exists": be_idx_exists,
            "backend_evidence_index_verification_exists": be_idx_verify_exists,
            "proof_contract_ok": proof_verify.get("contract_ok") is True if isinstance(proof_verify, dict) else False,
            "proof_verification_ok": proof_verify_sub["final_ok"] is True,
            "backend_evidence_index_contract_ok": be_idx_verify.get("contract_ok") is True if isinstance(be_idx_verify, dict) else False,
            "backend_evidence_index_verification_ok": be_idx_verify_sub["final_ok"] is True,
            "backend_identity_match": backend_identity_match,
            "final_bundle_ok": final_bundle_ok,
            "reasons": reasons,
        },
    }
    payload["artifact_sha256"] = sha256_json_sort_keys_compact(payload, exclude_key="artifact_sha256")

    _write_json(args.out, payload)
    return 0 if final_bundle_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
