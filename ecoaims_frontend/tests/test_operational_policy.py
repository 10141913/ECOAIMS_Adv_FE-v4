import unittest

from ecoaims_frontend.services.operational_policy import effective_feature_decision, effective_verification_summary


class TestOperationalPolicy(unittest.TestCase):
    def test_healthy_allows_fetch(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "policy_source": "backend_policy",
            "system_status": {"features": {"reports": {"status": "healthy", "recommended_mode": "live", "fail_policy": "fail_open", "reasons": []}}},
            "capabilities": {"reports": {"ready": True}},
        }
        d = effective_feature_decision("reports", readiness)
        self.assertEqual(d.get("final_mode"), "live")
        self.assertEqual(d.get("provenance"), "backend_policy")

    def test_degraded_placeholder_blocks_fetch(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "policy_source": "backend_policy",
            "system_status": {"features": {"monitoring": {"status": "degraded", "recommended_mode": "placeholder", "fail_policy": "fail_open", "reasons": ["contract_registry_unavailable"]}}},
            "capabilities": {"monitoring": {"ready": True}},
        }
        d = effective_feature_decision("monitoring", readiness)
        self.assertEqual(d.get("final_mode"), "placeholder")
        self.assertEqual(d.get("provenance"), "backend_policy")

    def test_runtime_endpoint_mismatch_blocks_optimization(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {"optimization": ["x"]},
            "policy_source": "backend_policy",
            "system_status": {"features": {"optimization": {"status": "healthy", "recommended_mode": "live", "fail_policy": "fail_closed", "reasons": []}}},
            "capabilities": {"optimization": {"ready": True}},
        }
        d = effective_feature_decision("optimization", readiness)
        self.assertEqual(d.get("final_mode"), "blocked")
        self.assertEqual(d.get("provenance"), "runtime_overlay")

    def test_backend_policy_unavailable_is_explicit_fallback(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "capabilities": {"reports": {"ready": True}},
            "policy_source": "frontend_fallback",
        }
        d = effective_feature_decision("reports", readiness)
        self.assertEqual(d.get("provenance"), "frontend_fallback")

    def test_strict_canonical_mode_blocks_when_not_ok(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "capabilities": {"optimization": {"ready": True}},
            "canonical_policy_required": True,
            "canonical_integration_ok": False,
            "policy_source": "frontend_fallback",
        }
        d = effective_feature_decision("optimization", readiness)
        self.assertEqual(d.get("final_mode"), "blocked")
        self.assertIn("canonical_integration_required_but_unavailable", d.get("reason_chain") or [])

    def test_local_dev_lane_allows_frontend_fallback(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "canonical_policy_required": False,
            "policy_source": "frontend_fallback",
        }
        s = effective_verification_summary(readiness)
        self.assertEqual(s.get("verification_lane"), "local_dev")
        self.assertTrue(s.get("verification_ok"))
        self.assertIn("frontend_fallback_active", s.get("verification_reasons") or [])

    def test_canonical_lane_rejects_frontend_fallback(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "canonical_policy_required": True,
            "canonical_integration_ok": False,
            "policy_source": "frontend_fallback",
        }
        s = effective_verification_summary(readiness)
        self.assertEqual(s.get("verification_lane"), "canonical_integration")
        self.assertFalse(s.get("verification_ok"))
        self.assertIn("canonical_integration_required_but_unavailable", s.get("verification_reasons") or [])
        self.assertIn("policy_source_not_backend_policy", s.get("verification_reasons") or [])

    def test_verification_fails_on_runtime_endpoint_contract_mismatch(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {"reports": ["x"]},
            "canonical_policy_required": False,
            "policy_source": "backend_policy",
        }
        s = effective_verification_summary(readiness)
        self.assertFalse(s.get("verification_ok"))
        self.assertIn("runtime_endpoint_contract_mismatch", s.get("verification_reasons") or [])

    def test_canonical_feature_blocked_when_identity_not_ok(self):
        readiness = {
            "backend_reachable": True,
            "backend_ready": True,
            "contract_valid": True,
            "registry_loaded": True,
            "endpoint_contract_errors": {},
            "canonical_policy_required": True,
            "canonical_integration_ok": True,
            "backend_identity_ok": False,
            "policy_source": "backend_policy",
            "capabilities": {"optimization": {"ready": True}},
            "system_status": {"features": {"optimization": {"status": "healthy", "recommended_mode": "live", "fail_policy": "fail_closed", "reasons": []}}},
        }
        d = effective_feature_decision("optimization", readiness)
        self.assertEqual(d.get("final_mode"), "blocked")
        self.assertIn("canonical_backend_identity_not_ok", d.get("reason_chain") or [])
