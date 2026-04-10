import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.callbacks.main_callbacks import comparison_status_banner
from ecoaims_frontend.services.monitoring_diag import fetch_monitoring_diag


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = int(status_code)
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("http_error", response=self)

    def json(self):
        return self._payload


class TestMonitoringComparisonRequestsLimit(unittest.TestCase):
    def test_comparison_requests_limit_minimum_and_becomes_ready(self):
        base = "http://127.0.0.1:8008"
        seen_energy_urls = []

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(
                    200,
                    {
                        "status": "ok",
                        "history": {"required_min_for_comparison": 2, "energy_data_records_count": 24, "sufficient_for_comparison": True},
                    },
                )
            if "/api/energy-data" in url:
                seen_energy_urls.append(url)
                self.assertIn("limit=12", url)
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": f"t{i}"} for i in range(12)],
                        "returned_records_len": 12,
                        "applied_limit": 12,
                        "available_records_len": 24,
                        "trimmed": False,
                        "notes": [],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertTrue(seen_energy_urls)
        self.assertTrue(diag.get("comparison_ready"))
        self.assertEqual(diag.get("returned_records_len"), 12)
        self.assertEqual(diag.get("min_history_for_comparison"), 2)
        self.assertEqual(diag.get("requested_limit"), 12)

    def test_degraded_when_returned_records_len_below_minimum(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok", "history": {"required_min_for_comparison": 2, "energy_data_records_count": 24}})
            if "/api/energy-data" in url:
                self.assertIn("limit=12", url)
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": "t0"}],
                        "returned_records_len": 1,
                        "applied_limit": 1,
                        "available_records_len": 24,
                        "trimmed": True,
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertFalse(diag.get("comparison_ready"))
        self.assertIn("insufficient_history_for_comparison", " ".join(diag.get("reasons") or []))

    def test_audit_fallback_when_energy_payload_has_no_audit_fields(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok", "history": {"required_min_for_comparison": 2}})
            if "/api/energy-data" in url:
                self.assertIn("limit=12", url)
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": f"t{i}"} for i in range(12)],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertTrue(diag.get("comparison_ready"))
        self.assertEqual(diag.get("returned_records_len"), 12)
        self.assertEqual(diag.get("payload_records_len"), 12)
        banner = comparison_status_banner(diag)
        s = str(banner)
        self.assertIn("applied_limit=n/a", s)
        self.assertIn("available_records_len=n/a", s)
        self.assertIn("trimmed=n/a", s)

    def test_audit_fields_parsed_when_backend_returns_strings(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok", "history": {"required_min_for_comparison": 2, "energy_data_records_count": 24}})
            if "/api/energy-data" in url:
                self.assertIn("limit=12", url)
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": f"t{i}"} for i in range(12)],
                        "returned_records_len": "12",
                        "applied_limit": "12",
                        "available_records_len": "24",
                        "trimmed": "true",
                        "notes": ["records_trimmed_to_limit total=24 limit=12"],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertTrue(diag.get("comparison_ready"))
        self.assertEqual(diag.get("returned_records_len"), 12)
        self.assertEqual(diag.get("applied_limit"), 12)
        self.assertEqual(diag.get("available_records_len"), 24)
        self.assertEqual(diag.get("trimmed"), True)
