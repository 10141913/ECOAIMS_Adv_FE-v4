import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import data_service


class TestMonitoringDiagnostics(unittest.TestCase):
    @patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.Timeout("t"))
    def test_fetch_real_energy_data_sets_diagnostic_on_timeout(self, _mget):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data = data_service.fetch_real_energy_data()
        self.assertIsNone(data)
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertIn("attempts", diag)
        self.assertTrue(isinstance(diag["attempts"], list))
        self.assertTrue(diag["attempts"])
        self.assertEqual(diag.get("class"), "backend_timeout")

    @patch("ecoaims_frontend.services.data_service.time.time", return_value=1000.0)
    @patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.Timeout("t"))
    def test_circuit_breaker_skips_requests_during_cooldown(self, _mget, _mtime):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service._BACKEND_LAST_LOG_TS = 0.0
        data_service.fetch_real_energy_data()
        calls_after_first = _mget.call_count
        self.assertGreaterEqual(calls_after_first, 1)
        data_service.fetch_real_energy_data()
        self.assertEqual(_mget.call_count, calls_after_first)

    def test_format_monitoring_failure_detail_has_reason(self):
        msg = data_service.format_monitoring_failure_detail("x")
        self.assertIn("reason=x", msg)

    @patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.ConnectionError("Connection refused"))
    def test_classify_connection_refused(self, _mget):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service.fetch_real_energy_data()
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertEqual(diag.get("class"), "backend_connection_refused")

    @patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.Timeout("t"))
    def test_classify_timeout(self, _mget):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service.fetch_real_energy_data()
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertEqual(diag.get("class"), "backend_timeout")
