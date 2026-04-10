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


class TestMonitoringComparisonRecordsLen(unittest.TestCase):
    def test_trim_indication_when_diag_count_exceeds_payload_records_len(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "degraded", "history": {"required_min_for_comparison": 12, "energy_data_records_count": 24}})
            if "/api/energy-data" in url:
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": "t"}],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertEqual(diag.get("records_len"), 1)
        self.assertEqual(diag.get("diag_energy_data_records_count"), 24)
        self.assertTrue(diag.get("data_maybe_trimmed"))
        self.assertEqual(diag.get("data_trim_gap"), 23)

        banner = comparison_status_banner(diag)
        self.assertIn("records_len=1", str(banner))
        self.assertIn("diag_count=24", str(banner))

    def test_no_trim_indication_when_counts_match(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok", "history": {"required_min_for_comparison": 2, "energy_data_records_count": 24}})
            if "/api/energy-data" in url:
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "dashboard_history",
                        "records": [{"timestamp": str(i)} for i in range(24)],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": True})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertEqual(diag.get("records_len"), 24)
        self.assertEqual(diag.get("diag_energy_data_records_count"), 24)
        self.assertFalse(diag.get("data_maybe_trimmed"))
        self.assertIsNone(diag.get("data_trim_gap"))
