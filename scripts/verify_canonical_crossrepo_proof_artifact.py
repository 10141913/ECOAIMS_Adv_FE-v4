import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return js if isinstance(js, dict) else {"data": js}


def sha256_json_sort_keys_compact(payload: Dict[str, Any], exclude_key: str | None = None) -> str:
    d = payload if isinstance(payload, dict) else {}
    if exclude_key and exclude_key in d:
        d = {k: v for k, v in d.items() if k != exclude_key}
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def validate_required_fields(doc_contract: Dict[str, Any], proof: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons: list[str] = []
    required = doc_contract.get("required_fields") if isinstance(doc_contract.get("required_fields"), list) else []
    for k in required:
        if k not in proof:
            reasons.append(f"missing_field:{k}")
    return (len(reasons) == 0), reasons


def validate_contract_metadata(proof: Dict[str, Any], contract: Dict[str, Any]) -> Tuple[bool, list[str], str]:
    reasons: list[str] = []
    expected_id = str(contract.get("artifact_contract_id") or "")
    expected_version = str(contract.get("artifact_contract_version") or "")
    contract_hash = sha256_json_sort_keys_compact(contract if isinstance(contract, dict) else {})

    if str(proof.get("artifact_contract_id") or "") != expected_id:
        reasons.append("artifact_contract_id_mismatch")
    if str(proof.get("artifact_contract_version") or "") != expected_version:
        reasons.append("artifact_contract_version_mismatch")
    if str(proof.get("artifact_contract_hash") or "") != contract_hash:
        reasons.append("artifact_contract_hash_mismatch")

    return (len(reasons) == 0), reasons, contract_hash


def validate_artifact_sha256(proof: Dict[str, Any]) -> Tuple[bool, str]:
    expect = str(proof.get("artifact_sha256") or "")
    actual = sha256_json_sort_keys_compact(proof if isinstance(proof, dict) else {}, exclude_key="artifact_sha256")
    return (bool(expect) and expect == actual), actual


def validate_mode_rules(proof: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons: list[str] = []
    mode = str(proof.get("mode") or "")
    chain_ok = proof.get("proof_chain_ok") is True
    verifier_ok = proof.get("be_proof_verifier_ok") is True
    be_sha_ok = proof.get("be_proof_artifact_sha256_ok") is True
    be_sum_sha_ok = proof.get("be_proof_verifier_summary_sha256_ok") is True
    id_ok = proof.get("be_runtime_identity_fingerprint_match") is True
    full_ok = False
    fv = proof.get("final_verdict") if isinstance(proof.get("final_verdict"), dict) else {}
    if isinstance(fv, dict):
        full_ok = fv.get("full_crossrepo_proof_ok") is True

    if mode not in {"full_crossrepo_proof", "remote_runtime_verified"}:
        reasons.append("invalid_mode")

    if mode == "remote_runtime_verified":
        if chain_ok:
            reasons.append("runtime_only_cannot_have_proof_chain_ok")
        if full_ok:
            reasons.append("runtime_only_cannot_have_full_crossrepo_proof_ok")

    if mode == "full_crossrepo_proof":
        if not verifier_ok:
            reasons.append("full_proof_requires_be_proof_verifier_ok")
        if not be_sha_ok:
            reasons.append("full_proof_requires_be_proof_artifact_sha256_ok")
        if not be_sum_sha_ok:
            reasons.append("full_proof_requires_be_proof_verifier_summary_sha256_ok")
        if not id_ok:
            reasons.append("full_proof_requires_identity_fingerprint_match")
        if proof.get("be_evidence_index_artifact_sha256_ok") is not True:
            reasons.append("full_proof_requires_be_evidence_index_artifact_sha256_ok")
        if proof.get("be_evidence_index_verify_summary_sha256_ok") is not True:
            reasons.append("full_proof_requires_be_evidence_index_verify_summary_sha256_ok")
        if proof.get("be_evidence_index_verify_ok") is not True:
            reasons.append("full_proof_requires_be_evidence_index_verify_ok")
        if proof.get("be_evidence_index_identity_fingerprint_match") is not True:
            reasons.append("full_proof_requires_be_evidence_index_identity_fingerprint_match")
        if proof.get("be_evidence_index_chain_ok") is not True:
            reasons.append("full_proof_requires_be_evidence_index_chain_ok")
        if not chain_ok:
            reasons.append("full_proof_requires_proof_chain_ok")

    return (len(reasons) == 0), reasons


def verify_proof(path: str) -> Dict[str, Any]:
    proof = _read_json(path)
    contract_path = os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_proof_contract.json")
    contract = _read_json(contract_path)

    contract_fields_ok, field_reasons = validate_required_fields(contract, proof)
    contract_meta_ok, meta_reasons, contract_hash = validate_contract_metadata(proof, contract)
    hash_ok, recomputed = validate_artifact_sha256(proof)
    mode_ok, mode_reasons = validate_mode_rules(proof)

    verdict_ok = bool(contract_fields_ok and contract_meta_ok and hash_ok and mode_ok)
    final_ok = verdict_ok

    reasons = []
    reasons.extend(field_reasons)
    reasons.extend(meta_reasons)
    if not hash_ok:
        reasons.append("artifact_sha256_mismatch")
    reasons.extend(mode_reasons)

    mode = str(proof.get("mode") or "")
    identity_ok = bool((proof.get("backend_proof_summary") or {}).get("canonical_identity_ok") is True) if isinstance(proof.get("backend_proof_summary"), dict) else False
    if mode == "full_crossrepo_proof":
        identity_ok = bool(
            identity_ok
            and proof.get("be_runtime_identity_fingerprint_match") is True
            and proof.get("be_evidence_index_identity_fingerprint_match") is True
        )
    runtime_ok = bool((proof.get("frontend_runtime_smoke") or {}).get("pass") is True) if isinstance(proof.get("frontend_runtime_smoke"), dict) else False
    chain_ok = bool(proof.get("proof_chain_ok") is True)

    return {
        "verification_type": "canonical_crossrepo_proof_verification",
        "verification_version": "canonical_crossrepo_proof_verification_v1",
        "verified_at": _now_iso(),
        "verified_path": path,
        "verified_artifact_sha256": str(proof.get("artifact_sha256") or ""),
        "artifact_contract_id": str(proof.get("artifact_contract_id") or ""),
        "artifact_contract_version": str(proof.get("artifact_contract_version") or ""),
        "artifact_contract_hash": contract_hash,
        "proof_chain_ok": proof.get("proof_chain_ok") is True,
        "identity_ok": identity_ok,
        "contract_ok": bool(contract_fields_ok and contract_meta_ok),
        "hash_ok": bool(hash_ok),
        "chain_ok": chain_ok,
        "runtime_ok": runtime_ok,
        "verdict_ok": bool(verdict_ok),
        "final_ok": bool(final_ok),
        "reasons": reasons,
        "verifier_script": "scripts/verify_canonical_crossrepo_proof_artifact.py",
        "summary_contract_id": "canonical_crossrepo_proof_verification_contract",
        "summary_contract_version": "canonical_crossrepo_proof_verification_v1",
        "summary_contract_hash": sha256_json_sort_keys_compact(_read_json(os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_proof_verification_contract.json"))),
        "summary_subject": "canonical_crossrepo_proof_verification",
        "summary_canonical_filename": "canonical_crossrepo_proof.verify.json",
        "verified_artifact_canonical_filename": "canonical_crossrepo_proof.json",
        "summary_hash_algorithm": "sha256",
        "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
        "recomputed_artifact_sha256": recomputed,
    }


def _compute_summary_sha256(summary: Dict[str, Any]) -> str:
    return sha256_json_sort_keys_compact(summary, exclude_key="summary_sha256")


def emit_summary(path: str, summary: Dict[str, Any]) -> str:
    out_dir = os.path.join(ROOT_DIR, "output", "verification")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "canonical_crossrepo_proof.verify.json")
    s = dict(summary)
    s["summary_sha256"] = _compute_summary_sha256(s)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(_canonical_json(s))
        f.write("\n")
    os.replace(tmp, out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_proof.json"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit-summary", action="store_true")
    args = ap.parse_args()

    summary = verify_proof(args.path)
    summary_ok = summary.get("final_ok") is True

    out_path = None
    if args.emit_summary:
        out_path = emit_summary(args.path, summary)

    if args.json:
        js = dict(summary)
        if out_path:
            js["emitted_summary_path"] = out_path
        print(_canonical_json(js))
    else:
        print(f"verified_path={args.path}")
        print(f"identity_ok={summary.get('identity_ok') is True}")
        print(f"contract_ok={summary.get('contract_ok') is True}")
        print(f"hash_ok={summary.get('hash_ok') is True}")
        print(f"chain_ok={summary.get('chain_ok') is True}")
        print(f"runtime_ok={summary.get('runtime_ok') is True}")
        print(f"final_ok={summary_ok}")
        if out_path:
            print(f"summary_path={out_path}")
        if not summary_ok:
            rs = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
            print(f"reasons={','.join([str(x) for x in rs if str(x).strip()]) or '-'}")

    return 0 if summary_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
