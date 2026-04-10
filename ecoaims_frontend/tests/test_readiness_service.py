import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import readiness_service


class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError()
            err.response = self
            raise err

    def json(self):
        return self._json_data


class TestReadinessService(unittest.TestCase):
    @patch("ecoaims_frontend.services.readiness_service.requests.get", side_effect=requests.ConnectionError("Connection refused"))
    def test_readiness_connection_refused(self, _mget):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        r = readiness_service.get_backend_readiness()
        self.assertFalse(r.get("backend_reachable"))
        self.assertEqual(r.get("error_class"), "backend_connection_refused")
        self.assertEqual(r.get("verification_lane"), "local_dev")
        self.assertFalse(r.get("verification_ok"))

    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_readiness_feature_not_ready(self, mget):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "2026-03-13"
        readiness_service._EXPECTED_CONTRACT_VERSION = "v1"

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(200, {"backend_ready": False, "capabilities": {"monitoring": {"ready": False}}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("backend_reachable"))
        self.assertFalse(r.get("backend_ready"))
        caps = r.get("capabilities")
        self.assertTrue(isinstance(caps, dict))
        self.assertFalse(caps.get("monitoring", {}).get("ready"))

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_API_BASE_URL", "http://127.0.0.1:8008")
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_readiness_rebinds_to_expected_host_port_from_startup_info(self, mget):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"

        seen = []

        def _fake(url, timeout):
            seen.append(url)
            if url == "http://127.0.0.1:8008/health":
                return _Resp(200, {"ok": True})
            if url == "http://127.0.0.1:8008/api/startup-info":
                return _Resp(
                    200,
                    {
                        "backend_ready": True,
                        "schema_version": "startup_info_v1",
                        "contract_version": "2026-03-13",
                        "capabilities": {"monitoring": {"ready": True}},
                        "reasons_not_ready": [],
                        "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"],
                        "expected_host": "127.0.0.1",
                        "expected_port": 8009,
                    },
                )
            if url == "http://127.0.0.1:8009/health":
                return _Resp(200, {"ok": True})
            if url == "http://127.0.0.1:8009/api/system/status":
                return _Resp(200, {"overall_status": "healthy", "features": {}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertEqual(r.get("bootstrap_base_url"), "http://127.0.0.1:8008")
        self.assertEqual(r.get("canonical_base_url"), "http://127.0.0.1:8009")
        self.assertEqual(r.get("base_url"), "http://127.0.0.1:8009")
        self.assertTrue(r.get("canonical_rebind_applied"))
        self.assertIn("http://127.0.0.1:8009/api/system/status", seen)

    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_readiness_contract_mismatch(self, mget):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(200, {"backend_ready": True, "schema_version": "2020-01-01", "contract_version": "v0", "capabilities": {"monitoring": {"ready": True}}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("backend_reachable"))
        self.assertFalse(r.get("contract_valid"))
        self.assertTrue(isinstance(r.get("contract_mismatch_reason"), str))

    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_invalid_startup_info_shape(self, mget):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(200, {"backend_ready": True, "schema_version": "startup_info_v1", "contract_version": "2026-03-13", "capabilities": ["bad-shape"], "required_endpoints": []})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("backend_reachable"))
        self.assertFalse(r.get("contract_valid"))
        self.assertIn("shape_errors", r.get("contract_mismatch_reason") or "")

    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_policy_endpoint_unavailable_sets_frontend_fallback(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(200, {"backend_ready": True, "schema_version": "startup_info_v1", "contract_version": "2026-03-13", "capabilities": {"reports": {"ready": True}}, "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"], "contract_manifest_id": "ecoaims-contract-v1", "contract_manifest_hash": "sha256-ecoaims-v1"})
            if url.endswith("/api/system/status"):
                return _Resp(404, {})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("backend_reachable"))
        self.assertTrue(r.get("contract_valid"))
        self.assertEqual(r.get("policy_source"), "frontend_fallback")
        self.assertEqual(r.get("verification_lane"), "local_dev")
        self.assertTrue(r.get("verification_ok"))
        self.assertIn("frontend_fallback_active", r.get("verification_reasons") or [])

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_REQUIRE_CANONICAL_POLICY", True)
    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_strict_canonical_mode_marks_not_ok_without_policy_endpoint(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(200, {"backend_ready": True, "schema_version": "startup_info_v1", "contract_version": "2026-03-13", "capabilities": {"reports": {"ready": True}}, "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"], "contract_manifest_id": "ecoaims-contract-v1", "contract_manifest_hash": "sha256-ecoaims-v1"})
            if url.endswith("/api/system/status"):
                return _Resp(404, {})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("canonical_policy_required"))
        self.assertEqual(r.get("integration_mode"), "canonical_integration")
        self.assertFalse(r.get("canonical_integration_ok"))
        self.assertEqual(r.get("verification_lane"), "canonical_integration")
        self.assertFalse(r.get("verification_ok"))
        self.assertIn("canonical_integration_required_but_unavailable", r.get("verification_reasons") or [])

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_REQUIRE_CANONICAL_POLICY", True)
    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_canonical_identity_ok_sets_verified(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"
        readiness_service._EXPECTED_BACKEND_IDENTITY_ID = "ecoaims_backend.canonical_fastapi"
        readiness_service._EXPECTED_BACKEND_REPO_ID = "ECOAIMS_Adv_BE"
        readiness_service._EXPECTED_BACKEND_SERVER_ROLE = "canonical_backend"
        readiness_service._EXPECTED_BACKEND_GIT_SHA = ""

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(
                    200,
                    {
                        "backend_ready": True,
                        "schema_version": "startup_info_v1",
                        "contract_version": "2026-03-13",
                        "capabilities": {"reports": {"ready": True}},
                        "reasons_not_ready": [],
                        "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"],
                        "contract_manifest_id": "ecoaims-contract-v1",
                        "contract_manifest_hash": "sha256-ecoaims-v1",
                        "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"},
                    },
                )
            if url.endswith("/api/system/status"):
                return _Resp(200, {"overall_status": "healthy", "features": {}, "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertEqual(r.get("policy_source"), "backend_policy")
        self.assertTrue(r.get("backend_identity_ok"))
        self.assertTrue(r.get("canonical_backend_verified"))
        self.assertEqual(r.get("verification_lane"), "canonical_integration")
        self.assertTrue(r.get("verification_ok"))

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_REQUIRE_CANONICAL_POLICY", True)
    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_backend_identity_fingerprint_mismatch_fails(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"
        readiness_service._EXPECTED_BACKEND_IDENTITY_ID = "ecoaims_backend.canonical_fastapi"
        readiness_service._EXPECTED_BACKEND_REPO_ID = "ECOAIMS_Adv_BE"
        readiness_service._EXPECTED_BACKEND_SERVER_ROLE = "canonical_backend"
        readiness_service._EXPECTED_BACKEND_GIT_SHA = ""
        readiness_service.ALLOW_LEGACY_BE_PROOF_PATH = False

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(
                    200,
                    {
                        "backend_ready": True,
                        "schema_version": "startup_info_v1",
                        "contract_version": "2026-03-13",
                        "capabilities": {"reports": {"ready": True}},
                        "reasons_not_ready": [],
                        "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"],
                        "contract_manifest_id": "ecoaims-contract-v1",
                        "contract_manifest_hash": "sha256-ecoaims-v1",
                        "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"},
                        "backend_identity_fingerprint": "bad",
                    },
                )
            if url.endswith("/api/system/status"):
                return _Resp(200, {"overall_status": "healthy", "features": {}, "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertFalse(r.get("backend_identity_ok"))
        self.assertIn("backend_identity_fingerprint_mismatch", r.get("backend_identity_reasons") or [])

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_REQUIRE_CANONICAL_POLICY", True)
    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_backend_identity_fingerprint_mismatch_allowed_in_legacy_mode(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"
        readiness_service._EXPECTED_BACKEND_IDENTITY_ID = "ecoaims_backend.canonical_fastapi"
        readiness_service._EXPECTED_BACKEND_REPO_ID = "ECOAIMS_Adv_BE"
        readiness_service._EXPECTED_BACKEND_SERVER_ROLE = "canonical_backend"
        readiness_service._EXPECTED_BACKEND_GIT_SHA = ""
        readiness_service.ALLOW_LEGACY_BE_PROOF_PATH = True

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(
                    200,
                    {
                        "backend_ready": True,
                        "schema_version": "startup_info_v1",
                        "contract_version": "2026-03-13",
                        "capabilities": {"reports": {"ready": True}},
                        "reasons_not_ready": [],
                        "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"],
                        "contract_manifest_id": "ecoaims-contract-v1",
                        "contract_manifest_hash": "sha256-ecoaims-v1",
                        "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"},
                        "backend_identity_fingerprint": "bad",
                    },
                )
            if url.endswith("/api/system/status"):
                return _Resp(200, {"overall_status": "healthy", "features": {}, "backend_identity": {"identity_id": "ecoaims_backend.canonical_fastapi", "repo_id": "ECOAIMS_Adv_BE", "server_role": "canonical_backend", "git_sha": "dev"}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertTrue(r.get("backend_identity_ok"))
        self.assertIn("backend_identity_fingerprint_mismatch", r.get("backend_identity_reasons") or [])

    @patch("ecoaims_frontend.services.readiness_service.ECOAIMS_REQUIRE_CANONICAL_POLICY", True)
    @patch("ecoaims_frontend.services.readiness_service.load_contract_registry", return_value={"registry_loaded": True, "registry_version": "v1", "active_manifest_id": "ecoaims-contract-v1", "active_manifest_hash": "sha256-ecoaims-v1", "registry_mismatch_reason": None})
    @patch("ecoaims_frontend.services.readiness_service.requests.get")
    def test_canonical_identity_mismatch_fails_verification(self, mget, _mreg):
        readiness_service._READINESS_CACHE = {}
        readiness_service._READINESS_DOWN_UNTIL_TS = 0.0
        readiness_service._EXPECTED_SCHEMA_VERSION = "startup_info_v1"
        readiness_service._EXPECTED_CONTRACT_VERSION = "2026-03-13"
        readiness_service._EXPECTED_BACKEND_IDENTITY_ID = "ecoaims_backend.canonical_fastapi"
        readiness_service._EXPECTED_BACKEND_REPO = "ECO_AIMS"
        readiness_service._EXPECTED_BACKEND_GIT_SHA = ""

        def _fake(url, timeout):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if url.endswith("/api/startup-info"):
                return _Resp(
                    200,
                    {
                        "backend_ready": True,
                        "schema_version": "startup_info_v1",
                        "contract_version": "2026-03-13",
                        "capabilities": {"reports": {"ready": True}},
                        "reasons_not_ready": [],
                        "required_endpoints": ["/health", "/api/energy-data", "/api/system/status"],
                        "contract_manifest_id": "ecoaims-contract-v1",
                        "contract_manifest_hash": "sha256-ecoaims-v1",
                        "backend_identity": {"identity_id": "not-canonical", "repo_id": "ECOAIMS_Adv_FE", "server_role": "frontend_devtools_mock", "git_sha": "dev"},
                    },
                )
            if url.endswith("/api/system/status"):
                return _Resp(200, {"overall_status": "healthy", "features": {}, "backend_identity": {"identity_id": "not-canonical", "repo_id": "ECOAIMS_Adv_FE", "server_role": "frontend_devtools_mock", "git_sha": "dev"}})
            return _Resp(404, {})

        mget.side_effect = _fake
        r = readiness_service.get_backend_readiness()
        self.assertEqual(r.get("policy_source"), "backend_policy")
        self.assertFalse(r.get("backend_identity_ok"))
        self.assertFalse(r.get("canonical_backend_verified"))
        self.assertEqual(r.get("verification_lane"), "canonical_integration")
        self.assertFalse(r.get("verification_ok"))
        self.assertIn("backend_identity_not_ok", r.get("verification_reasons") or [])
