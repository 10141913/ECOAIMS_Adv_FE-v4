import argparse
import json
import os
import sys
import tempfile
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import verify_canonical_crossrepo_evidence_bundle as bev


def _mk_big_identity(num_fields: int, value_len: int) -> dict:
    v = "x" * max(0, int(value_len))
    return {f"k{i:06d}": v for i in range(max(0, int(num_fields)))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-fields", type=int, default=5000)
    ap.add_argument("--value-len", type=int, default=64)
    ap.add_argument("--emit-summary", action="store_true")
    args = ap.parse_args()

    t0 = time.perf_counter()
    contract = bev._read_json(os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
    contract_hash = bev.sha256_json_sort_keys_compact(contract)

    fe_id = _mk_big_identity(args.num_fields, args.value_len)
    be_id = _mk_big_identity(args.num_fields, args.value_len)

    bundle = {
        "evidence_type": "canonical_crossrepo_evidence_bundle",
        "evidence_version": "canonical_crossrepo_evidence_bundle_v1",
        "generated_at": "2026-03-13T00:00:00Z",
        "evidence_subject": "canonical_crossrepo_verification_bundle",
        "artifact_contract_id": "canonical_crossrepo_evidence_bundle_contract",
        "artifact_contract_version": "canonical_crossrepo_evidence_bundle_v1",
        "artifact_contract_hash": contract_hash,
        "artifact_hash_algorithm": "sha256",
        "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
        "canonical_crossrepo_proof": {
            "path": "output/verification/canonical_crossrepo_proof.json",
            "canonical_filename": "canonical_crossrepo_proof.json",
            "proof_type": "canonical_crossrepo_proof",
            "artifact_sha256": "x",
            "artifact_contract_id": "canonical_crossrepo_proof_contract",
            "artifact_contract_version": "canonical_crossrepo_proof_v1",
            "artifact_contract_hash": "x",
            "full_crossrepo_proof_ok": True,
            "runtime_only_crossrepo_ok": False,
            "crossrepo_canonical_proof_ok": True,
        },
        "canonical_crossrepo_proof_verification": {
            "path": "output/verification/canonical_crossrepo_proof.verify.json",
            "canonical_filename": "canonical_crossrepo_proof.verify.json",
            "verification_type": "canonical_crossrepo_proof_verification",
            "summary_sha256": "x",
            "summary_contract_id": "canonical_crossrepo_proof_verification_contract",
            "summary_contract_version": "canonical_crossrepo_proof_verification_v1",
            "summary_contract_hash": "x",
            "final_ok": True,
        },
        "backend_evidence_index": {
            "path": "output/verification/backend_canonical_evidence_index.json",
            "canonical_filename": "backend_canonical_evidence_index.json",
            "artifact_sha256": "x",
            "artifact_contract_id": "backend_canonical_evidence_index_contract",
            "artifact_contract_version": "backend_canonical_evidence_index_v1",
            "artifact_contract_hash": "x",
            "final_bundle_ok": True,
        },
        "backend_evidence_index_verification": {
            "path": "output/verification/backend_canonical_evidence_index.verify.json",
            "canonical_filename": "backend_canonical_evidence_index.verify.json",
            "verification_type": "backend_canonical_evidence_index_verification",
            "summary_sha256": "x",
            "summary_contract_id": "backend_canonical_evidence_index_verification_contract",
            "summary_contract_version": "backend_canonical_evidence_index_verification_v1",
            "summary_contract_hash": "x",
            "final_ok": True,
        },
        "frontend_identity": fe_id,
        "backend_identity": be_id,
        "frontend_identity_fingerprint": "x",
        "backend_identity_fingerprint": "y",
        "chain_consistency": {
            "proof_exists": True,
            "proof_verification_exists": True,
            "backend_evidence_index_exists": True,
            "backend_evidence_index_verification_exists": True,
            "proof_contract_ok": True,
            "proof_verification_ok": True,
            "backend_evidence_index_contract_ok": True,
            "backend_evidence_index_verification_ok": True,
            "backend_identity_match": True,
            "final_bundle_ok": True,
            "reasons": [],
        },
    }
    bundle["artifact_sha256"] = bev.sha256_json_sort_keys_compact(bundle, exclude_key="artifact_sha256")
    t1 = time.perf_counter()

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "canonical_crossrepo_evidence_bundle.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(bundle, f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write("\n")
        t2 = time.perf_counter()
        summary = bev.verify_bundle(p)
        t3 = time.perf_counter()
        summary_path = None
        if args.emit_summary:
            summary_path = os.path.join(d, "canonical_crossrepo_evidence_bundle.verify.json")
            bev.emit_summary(summary, summary_path)
        t4 = time.perf_counter()

    out = {
        "num_fields": args.num_fields,
        "value_len": args.value_len,
        "bundle_bytes_estimate": len(json.dumps(bundle, ensure_ascii=False).encode("utf-8")),
        "timing_ms": {
            "build_hash": int((t1 - t0) * 1000),
            "write_bundle": int((t2 - t1) * 1000),
            "verify_bundle": int((t3 - t2) * 1000),
            "emit_summary": int((t4 - t3) * 1000),
            "total": int((t4 - t0) * 1000),
        },
        "final_ok": summary.get("final_ok") is True,
        "summary_path_emitted": bool(summary_path),
    }
    print(json.dumps(out, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
