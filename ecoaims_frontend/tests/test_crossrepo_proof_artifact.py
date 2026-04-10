import json
import os
import tempfile
import unittest

import scripts.verify_canonical_crossrepo as proof
import scripts.verify_canonical_crossrepo_proof_artifact as fev


class TestCrossRepoProofArtifact(unittest.TestCase):
    def test_fingerprint_is_stable(self):
        bi = {"repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "identity_id": "x", "git_sha": "abc"}
        a = proof.fingerprint_backend_identity(bi)
        b = proof.fingerprint_backend_identity({"git_sha": "abc", "identity_id": "x", "server_role": "canonical_backend", "repo_id": "ECOAIMS_Adv_BE"})
        self.assertEqual(a, b)

    def test_validate_be_proof_missing_fields_fails(self):
        ok, reasons = proof._validate_be_proof({})
        self.assertFalse(ok)
        self.assertTrue(len(reasons) >= 1)

    def test_validate_be_proof_ok(self):
        ok, reasons = proof._validate_be_proof({"proof_type": "backend_canonical_proof", "canonical_verification_ok": True, "backend_identity": {"repo_id": "ECOAIMS_Adv_BE"}})
        self.assertFalse(ok)
        self.assertTrue(len(reasons) >= 1)

    def test_validate_be_proof_full_ok(self):
        be = {
            "proof_type": "backend_canonical_proof",
            "proof_version": "backend_canonical_proof_v1",
            "artifact_contract_id": "backend_canonical_proof_contract",
            "artifact_contract_version": "backend_canonical_proof_v1",
            "artifact_contract_hash": "x",
            "artifact_hash_algorithm": "sha256",
            "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
            "proof_subject": "backend_canonical_verification",
            "proof_verdict": "authoritative_ok",
            "proof_verdict_reasons": [],
            "artifact_sha256": "x",
            "backend_identity": {"repo_id": "ECOAIMS_Adv_BE"},
            "backend_identity_fingerprint": "x",
            "manifest_summary": {},
            "canonical_identity_ok": True,
            "canonical_verification_ok": True,
            "integration_ready": True,
        }
        ok, reasons = proof._validate_be_proof(be)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_be_proof_hash_mismatch_detectable(self):
        be = {
            "proof_type": "backend_canonical_proof",
            "proof_version": "backend_canonical_proof_v1",
            "artifact_contract_id": "backend_canonical_proof_contract",
            "artifact_contract_version": "backend_canonical_proof_v1",
            "artifact_contract_hash": "x",
            "artifact_hash_algorithm": "sha256",
            "artifact_serialization": "json_sort_keys_compact_without_artifact_sha256",
            "proof_subject": "backend_canonical_verification",
            "proof_verdict": "authoritative_ok",
            "proof_verdict_reasons": [],
            "backend_identity": {"repo_id": "ECOAIMS_Adv_BE"},
            "backend_identity_fingerprint": "x",
            "manifest_summary": {},
            "canonical_identity_ok": True,
            "canonical_verification_ok": True,
            "integration_ready": True,
            "artifact_sha256": "not-a-real-hash",
        }
        recomputed = proof._recompute_be_artifact_sha256(be)
        self.assertNotEqual(recomputed, be["artifact_sha256"])

    def test_write_json_is_canonical_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "out.json")
            proof._write_json_file(p, {"b": 1, "a": 2})
            with open(p, "r", encoding="utf-8") as f:
                s = f.read()
            self.assertTrue(s.strip().startswith("{\"a\":2,\"b\":1}"))
            js = json.loads(s)
            self.assertEqual(js, {"a": 2, "b": 1})

    def test_sha256_json_sort_keys_compact_exclude_key(self):
        h1 = proof.sha256_json_sort_keys_compact({"a": 1, "artifact_sha256": "x"}, exclude_key="artifact_sha256")
        h2 = proof.sha256_json_sort_keys_compact({"a": 1}, exclude_key=None)
        self.assertEqual(h1, h2)

    def test_validate_be_verifier_summary_requires_fields(self):
        ok, reasons = proof._validate_be_verifier_summary({})
        self.assertFalse(ok)
        self.assertTrue(len(reasons) >= 1)

    def test_recompute_be_verifier_summary_sha256_excludes_field(self):
        js = {
            "verification_type": "backend_canonical_proof_verification",
            "verification_version": "v1",
            "summary_contract_id": "backend_canonical_proof_verification_contract",
            "summary_contract_version": "v1",
            "summary_contract_hash": "x",
            "summary_subject": "backend_canonical_proof_verification",
            "summary_canonical_filename": "backend_canonical_proof.verify.json",
            "verified_artifact_canonical_filename": "backend_canonical_proof.json",
            "summary_hash_algorithm": "sha256",
            "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
            "verified_artifact_sha256": "x",
            "artifact_contract_id": "backend_canonical_proof_contract",
            "artifact_contract_version": "v1",
            "artifact_contract_hash": "x",
            "backend_identity_fingerprint": "x",
            "contract_ok": True,
            "hash_ok": True,
            "verdict_ok": True,
            "final_ok": True,
            "reasons": [],
        }
        h = proof._recompute_be_verifier_summary_sha256(js)
        self.assertTrue(isinstance(h, str) and len(h) == 64)

    def test_validate_be_verifier_summary_with_hash_fails_on_mismatch(self):
        js = {
            "verification_type": "backend_canonical_proof_verification",
            "verification_version": "v1",
            "summary_contract_id": "backend_canonical_proof_verification_contract",
            "summary_contract_version": "v1",
            "summary_contract_hash": "x",
            "summary_subject": "backend_canonical_proof_verification",
            "summary_canonical_filename": "backend_canonical_proof.verify.json",
            "verified_artifact_canonical_filename": "backend_canonical_proof.json",
            "summary_hash_algorithm": "sha256",
            "summary_serialization": "json_sort_keys_compact_without_summary_sha256",
            "summary_contract_id": "backend_canonical_proof_verification_contract",
            "summary_contract_version": "v1",
            "summary_contract_hash": "x",
            "summary_sha256": "bad",
            "verified_artifact_sha256": "x",
            "artifact_contract_id": "backend_canonical_proof_contract",
            "artifact_contract_version": "v1",
            "artifact_contract_hash": "x",
            "backend_identity_fingerprint": "x",
            "contract_ok": True,
            "hash_ok": True,
            "verdict_ok": True,
            "final_ok": True,
            "reasons": [],
        }
        ok, reasons = proof._validate_be_verifier_summary_with_hash(js)
        self.assertFalse(ok)
        self.assertIn("be_verifier_summary_sha256_mismatch", reasons)

    def test_fe_validate_artifact_sha256_fails_on_bad_sha(self):
        payload = {"a": 1, "artifact_sha256": "bad"}
        ok, _recomputed = fev.validate_artifact_sha256(payload)
        self.assertFalse(ok)

    def test_fe_mode_rules_runtime_only_cannot_claim_full_chain(self):
        ok, reasons = fev.validate_mode_rules({"mode": "remote_runtime_verified", "proof_chain_ok": True, "final_verdict": {"full_crossrepo_proof_ok": True}})
        self.assertFalse(ok)
        self.assertIn("runtime_only_cannot_have_proof_chain_ok", reasons)

    def test_validate_be_evidence_index_missing_fields_fails(self):
        ok, reasons = proof._validate_be_evidence_index({})
        self.assertFalse(ok)
        self.assertTrue(len(reasons) >= 1)

    def test_validate_be_evidence_index_verify_summary_missing_fields_fails(self):
        ok, reasons = proof._validate_be_evidence_index_verify_summary({})
        self.assertFalse(ok)
        self.assertTrue(len(reasons) >= 1)

    def test_contract_contains_evidence_index_fields(self):
        contract_path = os.path.join(os.path.dirname(os.path.dirname(proof.__file__)), "docs", "canonical_crossrepo_proof_contract.json")
        with open(contract_path, "r", encoding="utf-8") as f:
            js = json.load(f)
        req = set(js.get("required_fields") or [])
        self.assertIn("be_evidence_index_path", req)
        self.assertIn("be_evidence_index_artifact_sha256_ok", req)
        self.assertIn("be_evidence_index_verify_ok", req)
