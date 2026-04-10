import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.callbacks.main_callbacks import comparison_status_banner, comparison_update_button_state
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


class TestMonitoringComparisonDegraded(unittest.TestCase):
    def test_monitoring_diag_attempts_recorded(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok"})
            if "/api/energy-data" in url:
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "sim",
                        "records": [{"ts": "t"}],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": False, "dispatch_history": []})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)
        self.assertTrue(isinstance(diag.get("attempts"), list))
        self.assertEqual(len(diag["attempts"]), 3)
        self.assertTrue(all("url" in a for a in diag["attempts"]))

    def test_monitoring_comparison_degrades_on_insufficient_history(self):
        diag = {
            "backend_ok": True,
            "comparison_ready": False,
            "min_history_for_comparison": 12,
            "min_history_source": "frontend_default",
            "records_count": 1,
            "records_len": 1,
            "reasons": ["insufficient_history_for_comparison:min=12 got=1"],
            "attempts": [{"url": "http://x/diag/monitoring", "status": 200, "error_class": None, "elapsed_ms": 1}],
            "energy_contract_ok": True,
            "energy_contract_source": "registry",
        }
        banner = comparison_status_banner(diag)
        inner = banner.children[-1]
        self.assertEqual(inner.children[0].children, "Comparison degraded")
        self.assertIn("Butuh minimal=12", str(inner.children[1].children))
        self.assertIn("payload_records_len=1", str(inner.children[1].children))
        btn_disabled, btn_style, link_style, _hint = comparison_update_button_state(diag)
        self.assertFalse(btn_disabled)
        self.assertNotEqual(btn_style.get("display"), "none")
        self.assertNotEqual(link_style.get("display"), "none")

    def test_monitoring_waiting_only_when_backend_down(self):
        diag = {
            "backend_ok": False,
            "comparison_ready": False,
            "min_history_for_comparison": 12,
            "records_count": 0,
            "reasons": ["diag_monitoring_not_ok"],
            "attempts": [{"url": "http://x/diag/monitoring", "status": None, "error_class": "backend_connection_error", "elapsed_ms": 1}],
            "energy_contract_ok": None,
            "energy_contract_source": None,
        }
        banner = comparison_status_banner(diag)
        inner = banner.children[-1]
        self.assertEqual(inner.children[0].children, "Waiting for backend (Comparison)")
        self.assertIn("WAITING", str(inner.children[1].children))

    def test_backend_diag_threshold_is_used(self):
        base = "http://127.0.0.1:8008"

        def fake_get(url, timeout=None):
            if url.endswith("/diag/monitoring"):
                return _FakeResponse(200, {"status": "ok", "history": {"required_min_for_comparison": 2}})
            if "/api/energy-data" in url:
                return _FakeResponse(
                    200,
                    {
                        "contract_manifest_id": "energy_data_contract",
                        "contract_manifest_version": "2026-03-13",
                        "stream_id": "default",
                        "data_available": True,
                        "source": "sim",
                        "records": [{"ts": "t"}],
                    },
                )
            if "/dashboard/state" in url:
                return _FakeResponse(200, {"contract_manifest_id": "dashboard_state_contract", "data_available": False, "dispatch_history": []})
            raise AssertionError("unexpected_url:" + url)

        with patch("ecoaims_frontend.services.monitoring_diag.requests.get", side_effect=fake_get), patch(
            "ecoaims_frontend.services.contract_registry.validate_endpoint", return_value=(True, [], "registry")
        ):
            diag = fetch_monitoring_diag(base)

        self.assertEqual(diag.get("min_history_for_comparison"), 2)
        self.assertEqual(diag.get("min_history_source"), "backend_diag")
        banner = comparison_status_banner(diag)
        inner = banner.children[-1]
        self.assertIn("Butuh minimal=2", str(inner.children[1].children))
