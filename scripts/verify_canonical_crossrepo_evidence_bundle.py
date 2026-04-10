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


def sha256_json_sort_keys_compact(payload: Dict[str, Any], exclude_key: str | None = None) -> str:
    d = payload if isinstance(payload, dict) else {}
    if exclude_key and exclude_key in d:
        d = {k: v for k, v in d.items() if k != exclude_key}
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return js if isinstance(js, dict) else {"data": js}


def validate_required_fields(contract: Dict[str, Any], bundle: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons: list[str] = []
    required = contract.get("required_fields") if isinstance(contract.get("required_fields"), list) else []
    for k in required:
        if k not in bundle:
            reasons.append(f"missing_field:{k}")
    return (len(reasons) == 0), reasons


def validate_bundle_contract_metadata(bundle: Dict[str, Any], contract: Dict[str, Any]) -> Tuple[bool, list[str], str]:
    reasons: list[str] = []
    expected_id = str(contract.get("artifact_contract_id") or "")
    expected_version = str(contract.get("artifact_contract_version") or "")
    contract_hash = sha256_json_sort_keys_compact(contract)
    if str(bundle.get("artifact_contract_id") or "") != expected_id:
        reasons.append("artifact_contract_id_mismatch")
    if str(bundle.get("artifact_contract_version") or "") != expected_version:
        reasons.append("artifact_contract_version_mismatch")
    if str(bundle.get("artifact_contract_hash") or "") != contract_hash:
        reasons.append("artifact_contract_hash_mismatch")
    if str(bundle.get("artifact_hash_algorithm") or "") != "sha256":
        reasons.append("artifact_hash_algorithm_mismatch")
    if str(bundle.get("artifact_serialization") or "") != "json_sort_keys_compact_without_artifact_sha256":
        reasons.append("artifact_serialization_mismatch")
    return (len(reasons) == 0), reasons, contract_hash


def validate_bundle_sha256(bundle: Dict[str, Any]) -> Tuple[bool, str]:
    expect = str(bundle.get("artifact_sha256") or "")
    actual = sha256_json_sort_keys_compact(bundle, exclude_key="artifact_sha256")
    return (bool(expect) and expect == actual), actual


def validate_canonical_filenames(bundle: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons: list[str] = []
    expected = {
        ("canonical_crossrepo_proof", "canonical_filename"): "canonical_crossrepo_proof.json",
        ("canonical_crossrepo_proof_verification", "canonical_filename"): "canonical_crossrepo_proof.verify.json",
        ("backend_evidence_index", "canonical_filename"): "backend_canonical_evidence_index.json",
        ("backend_evidence_index_verification", "canonical_filename"): "backend_canonical_evidence_index.verify.json",
    }
    for (k1, k2), v in expected.items():
        sub = bundle.get(k1) if isinstance(bundle.get(k1), dict) else {}
        if str(sub.get(k2) or "") != v:
            reasons.append(f"canonical_filename_mismatch:{k1}")
    return (len(reasons) == 0), reasons


def validate_chain_consistency(bundle: Dict[str, Any]) -> Tuple[bool, list[str]]:
    reasons: list[str] = []
    cc = bundle.get("chain_consistency") if isinstance(bundle.get("chain_consistency"), dict) else {}
    if cc.get("proof_verification_ok") is not True:
        reasons.append("proof_verification_not_ok")
    if cc.get("backend_evidence_index_verification_ok") is not True:
        reasons.append("backend_evidence_index_verification_not_ok")
    if cc.get("backend_identity_match") is not True:
        reasons.append("backend_identity_not_match")
    if cc.get("final_bundle_ok") is not True:
        reasons.append("final_bundle_ok_not_true")
    return (len(reasons) == 0), reasons


def verify_bundle(path: str) -> Dict[str, Any]:
    bundle = _read_json(path)
    contract = _read_json(os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
    contract_ok1, req_reasons = validate_required_fields(contract, bundle)
    contract_ok2, meta_reasons, contract_hash = validate_bundle_contract_metadata(bundle, contract)
    hash_ok, _recomputed = validate_bundle_sha256(bundle)
    fn_ok, fn_reasons = validate_canonical_filenames(bundle)
    chain_ok, chain_reasons = validate_chain_consistency(bundle)

    contract_ok = bool(contract_ok1 and contract_ok2)
    verdict_ok = bool(contract_ok and hash_ok and fn_ok and chain_ok)
    final_ok = verdict_ok

    reasons: list[str] = []
    reasons.extend(req_reasons)
    reasons.extend(meta_reasons)
    if not hash_ok:
        reasons.append("artifact_sha256_mismatch")
    reasons.extend(fn_reasons)
    reasons.extend(chain_reasons)

    fe_fp = str(bundle.get("frontend_identity_fingerprint") or "")
    be_fp = str(bundle.get("backend_identity_fingerprint") or "")
    cc = bundle.get("chain_consistency") if isinstance(bundle.get("chain_consistency"), dict) else {}
    identity_ok = cc.get("backend_identity_match") is True
    runtime_ok = False
    proof_sub = bundle.get("canonical_crossrepo_proof") if isinstance(bundle.get("canonical_crossrepo_proof"), dict) else {}
    if isinstance(proof_sub, dict):
        runtime_ok = proof_sub.get("crossrepo_canonical_proof_ok") is True

    return {
        "verification_type": "canonical_crossrepo_evidence_bundle_verification",
        "verification_version": "canonical_crossrepo_evidence_bundle_verification_v1",
        "verified_at": _now_iso(),
        "verified_path": path,
        "verified_artifact_sha256": str(bundle.get("artifact_sha256") or ""),
        "artifact_contract_id": str(bundle.get("artifact_contract_id") or ""),
        "artifact_contract_version": str(bundle.get("artifact_contract_version") or ""),
        "artifact_contract_hash": contract_hash,
        "frontend_identity_fingerprint": fe_fp,
        "backend_identity_fingerprint": be_fp,
        "identity_ok": identity_ok,
        "contract_ok": contract_ok,
        "hash_ok": hash_ok,
        "chain_ok": chain_ok,
        "runtime_ok": runtime_ok,
        "verdict_ok": verdict_ok,
        "final_ok": final_ok,
        "reasons": reasons,
        "verifier_script": "scripts/verify_canonical_crossrepo_evidence_bundle.py",
        "summary_contract_id": "canonical_crossrepo_evidence_bundle_verification_contract",
        "summary_contract_version": "canonical_crossrepo_evidence_bundle_verification_v1",
        "summary_contract_hash": sha256_json_sort_keys_compact(_read_json(os.path.join(ROOT_DIR, "docs", "canonical_crossrepo_evidence_bundle_verification_contract.json"))),
        "summary_subject": "canonical_crossrepo_evidence_bundle_verification",
        "summary_canonical_filename": "canonical_crossrepo_evidence_bundle.verify.json",
        "verified_artifact_canonical_filename": "canonical_crossrepo_evidence_bundle.json",
        "summary_hash_algorithm": "sha256",
        "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
    }


def emit_summary(summary: Dict[str, Any], out_path: str) -> str:
    s = dict(summary)
    s["summary_sha256"] = sha256_json_sort_keys_compact(s, exclude_key="summary_sha256")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_evidence_bundle.json"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit-summary", action="store_true")
    ap.add_argument("--summary-out-file", default=os.path.join(ROOT_DIR, "output", "verification", "canonical_crossrepo_evidence_bundle.verify.json"))
    args = ap.parse_args()

    summary = verify_bundle(args.path)
    ok = summary.get("final_ok") is True

    out_path = None
    if args.emit_summary:
        out_path = emit_summary(summary, args.summary_out_file)

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
        print(f"final_ok={ok}")
        if out_path:
            print(f"summary_path={out_path}")
        if not ok:
            rs = summary.get("reasons") if isinstance(summary.get("reasons"), list) else []
            print(f"reasons={','.join([str(x) for x in rs if str(x).strip()]) or '-'}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
