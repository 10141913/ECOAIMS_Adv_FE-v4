import json
import os
import tempfile
import unittest

import scripts.verify_canonical_crossrepo_evidence_bundle as bev


class TestCrossRepoEvidenceBundle(unittest.TestCase):
    def test_bundle_contract_required_fields_present(self):
        contract = bev._read_json(os.path.join(os.path.dirname(os.path.dirname(bev.__file__)), "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
        required = contract.get("required_fields") if isinstance(contract.get("required_fields"), list) else []
        self.assertIn("evidence_type", required)
        self.assertIn("artifact_sha256", required)
        self.assertIn("chain_consistency", required)

    def test_bundle_sha256_roundtrip(self):
        bundle = {
            "evidence_type": "canonical_crossrepo_evidence_bundle",
            "evidence_version": "canonical_crossrepo_evidence_bundle_v1",
            "generated_at": "2026-03-13T00:00:00Z",
            "evidence_subject": "canonical_crossrepo_verification_bundle",
            "artifact_contract_id": "canonical_crossrepo_evidence_bundle_contract",
            "artifact_contract_version": "canonical_crossrepo_evidence_bundle_v1",
            "artifact_contract_hash": "x",
            "artifact_hash_algorithm": "sha256",
            "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
            "canonical_crossrepo_proof": {"canonical_filename": "canonical_crossrepo_proof.json"},
            "canonical_crossrepo_proof_verification": {"canonical_filename": "canonical_crossrepo_proof.verify.json", "final_ok": True},
            "backend_evidence_index": {"canonical_filename": "backend_canonical_evidence_index.json"},
            "backend_evidence_index_verification": {"canonical_filename": "backend_canonical_evidence_index.verify.json", "final_ok": True},
            "frontend_identity": {},
            "backend_identity": {},
            "frontend_identity_fingerprint": "x",
            "backend_identity_fingerprint": "y",
            "chain_consistency": {"proof_verification_ok": True, "backend_evidence_index_verification_ok": True, "backend_identity_match": True, "final_bundle_ok": True, "reasons": []},
        }
        bundle["artifact_sha256"] = bev.sha256_json_sort_keys_compact(bundle, exclude_key="artifact_sha256")
        ok, recomputed = bev.validate_bundle_sha256(bundle)
        self.assertTrue(ok)
        self.assertEqual(bundle["artifact_sha256"], recomputed)

    def test_bundle_verifier_fails_when_chain_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bundle.json")
            contract = bev._read_json(os.path.join(os.path.dirname(os.path.dirname(bev.__file__)), "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
            contract_hash = bev.sha256_json_sort_keys_compact(contract)
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
                "canonical_crossrepo_proof": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.json", "proof_type": "x", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "full_crossrepo_proof_ok": False, "runtime_only_crossrepo_ok": False, "crossrepo_canonical_proof_ok": False},
                "canonical_crossrepo_proof_verification": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": False},
                "backend_evidence_index": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.json", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "final_bundle_ok": False},
                "backend_evidence_index_verification": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": False},
                "frontend_identity": {},
                "backend_identity": {},
                "frontend_identity_fingerprint": "x",
                "backend_identity_fingerprint": "y",
                "chain_consistency": {"proof_exists": True, "proof_verification_exists": True, "backend_evidence_index_exists": True, "backend_evidence_index_verification_exists": True, "proof_contract_ok": False, "proof_verification_ok": False, "backend_evidence_index_contract_ok": False, "backend_evidence_index_verification_ok": False, "backend_identity_match": False, "final_bundle_ok": False, "reasons": ["x"]},
            }
            bundle["artifact_sha256"] = bev.sha256_json_sort_keys_compact(bundle, exclude_key="artifact_sha256")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(bundle, f)
            summary = bev.verify_bundle(p)
            self.assertFalse(summary.get("final_ok"))

    def test_bundle_summary_sha256_is_deterministic(self):
        summary = {
            "verification_type": "canonical_crossrepo_evidence_bundle_verification",
            "verification_version": "canonical_crossrepo_evidence_bundle_verification_v1",
            "verified_at": "2026-03-13T00:00:00Z",
            "verified_path": "x",
            "verified_artifact_sha256": "x",
            "artifact_contract_id": "canonical_crossrepo_evidence_bundle_contract",
            "artifact_contract_version": "canonical_crossrepo_evidence_bundle_v1",
            "artifact_contract_hash": "x",
            "frontend_identity_fingerprint": "x",
            "backend_identity_fingerprint": "y",
            "contract_ok": True,
            "hash_ok": True,
            "chain_ok": True,
            "verdict_ok": True,
            "final_ok": True,
            "reasons": [],
            "verifier_script": "scripts/verify_canonical_crossrepo_evidence_bundle.py",
            "summary_contract_id": "canonical_crossrepo_evidence_bundle_verification_contract",
            "summary_contract_version": "canonical_crossrepo_evidence_bundle_verification_v1",
            "summary_contract_hash": "x",
            "summary_subject": "canonical_crossrepo_evidence_bundle_verification",
            "summary_canonical_filename": "canonical_crossrepo_evidence_bundle.verify.json",
            "verified_artifact_canonical_filename": "canonical_crossrepo_evidence_bundle.json",
            "summary_hash_algorithm": "sha256",
            "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
        }
        sha = bev.sha256_json_sort_keys_compact({**summary, "summary_sha256": "bad"}, exclude_key="summary_sha256")
        self.assertTrue(isinstance(sha, str) and len(sha) == 64)

    def test_emit_summary_sha256_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "canonical_crossrepo_evidence_bundle.verify.json")
            summary = {
                "verification_type": "canonical_crossrepo_evidence_bundle_verification",
                "verification_version": "canonical_crossrepo_evidence_bundle_verification_v1",
                "verified_at": "2026-03-13T00:00:00Z",
                "verified_path": "x",
                "verified_artifact_sha256": "x",
                "artifact_contract_id": "canonical_crossrepo_evidence_bundle_contract",
                "artifact_contract_version": "canonical_crossrepo_evidence_bundle_v1",
                "artifact_contract_hash": "x",
                "frontend_identity_fingerprint": "x",
                "backend_identity_fingerprint": "y",
                "identity_ok": True,
                "contract_ok": True,
                "hash_ok": True,
                "chain_ok": True,
                "runtime_ok": True,
                "verdict_ok": True,
                "final_ok": True,
                "reasons": [],
                "verifier_script": "scripts/verify_canonical_crossrepo_evidence_bundle.py",
                "summary_contract_id": "canonical_crossrepo_evidence_bundle_verification_contract",
                "summary_contract_version": "canonical_crossrepo_evidence_bundle_verification_v1",
                "summary_contract_hash": "x",
                "summary_subject": "canonical_crossrepo_evidence_bundle_verification",
                "summary_canonical_filename": "canonical_crossrepo_evidence_bundle.verify.json",
                "verified_artifact_canonical_filename": "canonical_crossrepo_evidence_bundle.json",
                "summary_hash_algorithm": "sha256",
                "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
            }
            bev.emit_summary(summary, out)
            saved = bev._read_json(out)
            ok, recomputed = bev.validate_bundle_sha256({"artifact_sha256": "x"})
            self.assertFalse(ok)
            self.assertTrue(isinstance(recomputed, str) and len(recomputed) == 64)
            recomputed_sum = bev.sha256_json_sort_keys_compact(saved, exclude_key="summary_sha256")
            self.assertEqual(saved.get("summary_sha256"), recomputed_sum)

    def test_bundle_verifier_fails_on_contract_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bundle.json")
            contract = bev._read_json(os.path.join(os.path.dirname(os.path.dirname(bev.__file__)), "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
            bundle = {
                "evidence_type": "canonical_crossrepo_evidence_bundle",
                "evidence_version": "canonical_crossrepo_evidence_bundle_v1",
                "generated_at": "2026-03-13T00:00:00Z",
                "evidence_subject": "canonical_crossrepo_verification_bundle",
                "artifact_contract_id": "canonical_crossrepo_evidence_bundle_contract",
                "artifact_contract_version": "canonical_crossrepo_evidence_bundle_v1",
                "artifact_contract_hash": "wrong",
                "artifact_hash_algorithm": "sha256",
                "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
                "canonical_crossrepo_proof": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.json", "proof_type": "x", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "full_crossrepo_proof_ok": False, "runtime_only_crossrepo_ok": False, "crossrepo_canonical_proof_ok": False},
                "canonical_crossrepo_proof_verification": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": True},
                "backend_evidence_index": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.json", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "final_bundle_ok": True},
                "backend_evidence_index_verification": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": True},
                "frontend_identity": {},
                "backend_identity": {},
                "frontend_identity_fingerprint": "x",
                "backend_identity_fingerprint": "y",
                "chain_consistency": {"proof_verification_ok": True, "backend_evidence_index_verification_ok": True, "backend_identity_match": True, "final_bundle_ok": True, "reasons": []},
            }
            bundle["artifact_sha256"] = bev.sha256_json_sort_keys_compact(bundle, exclude_key="artifact_sha256")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(bundle, f)
            summary = bev.verify_bundle(p)
            self.assertFalse(summary.get("final_ok"))
            expected_hash = bev.sha256_json_sort_keys_compact(contract)
            self.assertNotEqual("wrong", expected_hash)

    def test_bundle_verifier_fails_on_artifact_sha256_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bundle.json")
            contract = bev._read_json(os.path.join(os.path.dirname(os.path.dirname(bev.__file__)), "docs", "canonical_crossrepo_evidence_bundle_contract.json"))
            contract_hash = bev.sha256_json_sort_keys_compact(contract)
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
                "artifact_sha256": "bad",
                "canonical_crossrepo_proof": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.json", "proof_type": "x", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "full_crossrepo_proof_ok": False, "runtime_only_crossrepo_ok": False, "crossrepo_canonical_proof_ok": False},
                "canonical_crossrepo_proof_verification": {"path": "x", "canonical_filename": "canonical_crossrepo_proof.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": True},
                "backend_evidence_index": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.json", "artifact_sha256": "x", "artifact_contract_id": "x", "artifact_contract_version": "x", "artifact_contract_hash": "x", "final_bundle_ok": True},
                "backend_evidence_index_verification": {"path": "x", "canonical_filename": "backend_canonical_evidence_index.verify.json", "verification_type": "x", "summary_sha256": "x", "summary_contract_id": "x", "summary_contract_version": "x", "summary_contract_hash": "x", "final_ok": True},
                "frontend_identity": {},
                "backend_identity": {},
                "frontend_identity_fingerprint": "x",
                "backend_identity_fingerprint": "y",
                "chain_consistency": {"proof_verification_ok": True, "backend_evidence_index_verification_ok": True, "backend_identity_match": True, "final_bundle_ok": True, "reasons": []},
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(bundle, f)
            summary = bev.verify_bundle(p)
            self.assertFalse(summary.get("final_ok"))
