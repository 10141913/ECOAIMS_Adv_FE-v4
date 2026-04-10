import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services.contract_negotiation import ContractNegotiationService
from ecoaims_frontend.ui.contract_negotiation_error import render_contract_negotiation_error


class _Resp:
    def __init__(self, status_code=200, headers=None, json_data=None):
        self.status_code = int(status_code)
        self.headers = headers or {}
        self._json_data = json_data

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class TestContractNegotiation(unittest.TestCase):
    def test_endpoint_mapping_correctness(self):
        svc = ContractNegotiationService(cache_ttl_s=300)
        e = svc.identify_contract("/api/energy-data")
        self.assertTrue(e.get("known"))
        self.assertEqual(e.get("contract_id"), "energy_data")
        self.assertEqual(e.get("expected_version"), "1.2.0")
        m = svc.identify_contract("/diag/monitoring")
        self.assertTrue(m.get("known"))
        self.assertEqual(m.get("contract_id"), "monitoring")
        self.assertEqual(m.get("expected_version"), "1.0.0")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_compatible_versions(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "1.2.1"})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="strict", negotiation_required=False)
        self.assertTrue(out.get("compatibility", {}).get("compatible"))

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_incompatible_major_version(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "2.0.0"})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="strict", negotiation_required=False)
        self.assertFalse(out.get("compatibility", {}).get("compatible"))
        self.assertEqual(out.get("decision"), "block")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_older_minor_version(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "1.1.9"})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="adaptive", negotiation_required=False)
        self.assertFalse(out.get("compatibility", {}).get("compatible"))
        self.assertEqual(out.get("decision"), "fallback")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_network_failure(self, mopt):
        mopt.side_effect = requests.Timeout("t")
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=False)
        self.assertIsNone(out.get("compatibility", {}).get("compatible"))
        self.assertIn(out.get("compatibility", {}).get("reason"), {"negotiation_unavailable", "version_unparseable"})

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_options_not_supported_405_is_unavailable(self, mopt):
        mopt.return_value = _Resp(405, headers={}, json_data=None)
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="strict", negotiation_required=False)
        self.assertIsNone(out.get("compatibility", {}).get("compatible"))
        self.assertEqual(out.get("compatibility", {}).get("reason"), "negotiation_unavailable")
        self.assertEqual(out.get("decision"), "proceed")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_required_blocks_when_unavailable(self, mopt):
        mopt.return_value = _Resp(404, headers={}, json_data=None)
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=True)
        self.assertEqual(out.get("decision"), "block")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_invalid_version_string_is_unparseable(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-Version": "2026-03-13"})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="strict", negotiation_required=False)
        self.assertIsNone(out.get("compatibility", {}).get("compatible"))
        self.assertEqual(out.get("compatibility", {}).get("reason"), "version_unparseable")
        self.assertEqual(out.get("decision"), "proceed")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_extracts_contract_from_body(self, mopt):
        mopt.return_value = _Resp(200, headers={}, json_data={"contract": {"id": "energy_data", "version": "1.2.0", "hash": "abc"}})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="strict", negotiation_required=False)
        self.assertTrue(out.get("compatibility", {}).get("compatible"))
        self.assertEqual(out.get("backend", {}).get("hash"), "abc")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_cache_behavior(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "1.2.0"})
        svc = ContractNegotiationService(cache_ttl_s=300)
        out1 = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=False)
        out2 = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=False)
        self.assertEqual(out1.get("backend", {}).get("version"), out2.get("backend", {}).get("version"))
        self.assertEqual(mopt.call_count, 1)

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    def test_negotiation_cache_expiry(self, mopt):
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "1.2.0"})
        svc = ContractNegotiationService(cache_ttl_s=-1)
        _ = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=False)
        _ = svc.negotiate_for_endpoint("http://x", method="GET", path="/api/energy-data", mode="lenient", negotiation_required=False)
        self.assertEqual(mopt.call_count, 2)

    def test_ui_error_rendering(self):
        ui = render_contract_negotiation_error({"expected": {"id": "energy_data", "version": "1.2.0"}, "backend": {"id": "energy_data", "version": "2.0.0"}, "compatibility": {"compatible": False, "reason": "major_version_mismatch"}, "decision": "block"})
        s = str(ui)
        self.assertIn("Contract Compatibility Check", s)
        self.assertIn("Version Comparison", s)
        self.assertIn("INCOMPATIBLE", s)
        self.assertIn("Use Simulation Data", s)

    def test_ui_error_rendering_handles_unexpected_input(self):
        ui = render_contract_negotiation_error(None)
        self.assertIn("Contract Compatibility Check", str(ui))
