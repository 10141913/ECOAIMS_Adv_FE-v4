import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import data_service, optimization_service, reports_api


class _Resp:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError()
            err.response = self
            raise err

    def json(self):
        return self._json_data


class TestRuntimeEndpointContracts(unittest.TestCase):
    @patch("ecoaims_frontend.services.data_service.requests.get")
    def test_energy_data_invalid_shape_marked_mismatch(self, mget):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service._LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "unknown", "errors": [], "last_checked_at": None}

        def _fake(url, timeout=None, **kwargs):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if "/dashboard/state" in url:
                return _Resp(404, {})
            return _Resp(200, {"solar": 1})

        mget.side_effect = _fake
        with patch.object(data_service, "CONTRACT_SYSTEM", {"enabled": False}):
            out = data_service.fetch_real_energy_data()
        self.assertIsNone(out)
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertEqual(diag.get("class"), "runtime_endpoint_contract_mismatch")
        c = data_service.get_last_monitoring_endpoint_contract()
        self.assertEqual(c.get("status"), "mismatch")

    @patch("ecoaims_frontend.services.data_service.requests.get")
    def test_energy_data_invalid_shape_lenient_mode_returns_adapted_with_warning(self, mget):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service._LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "unknown", "errors": [], "last_checked_at": None}
        data_service.ECOAIMS_CONTRACT_VALIDATION_MODE = "lenient"

        def _fake(url, timeout=None, **kwargs):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if "/dashboard/state" in url:
                return _Resp(404, {})
            return _Resp(
                200,
                {
                    "latest": {
                        "pv_generation": 1.0,
                        "wind_generation": 2.0,
                        "grid_import": 3.0,
                        "grid_export": 0.0,
                        "battery_soc": 0.5,
                        "battery_charge": 0.0,
                        "battery_discharge": 1.0,
                    }
                },
            )

        mget.side_effect = _fake
        with patch.object(data_service, "CONTRACT_SYSTEM", {"enabled": False}), patch(
            "ecoaims_frontend.services.data_service.validate_endpoint", return_value=(False, ["$:missing:records"], "registry")
        ):
            out = data_service.fetch_real_energy_data()
        self.assertTrue(isinstance(out, dict))
        c = data_service.get_last_monitoring_endpoint_contract()
        self.assertEqual(c.get("status"), "warn")
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertTrue(diag.get("ok"))
        self.assertEqual(diag.get("warning_class"), "runtime_endpoint_contract_mismatch")

    @patch("ecoaims_frontend.services.contract_negotiation.requests.options")
    @patch("ecoaims_frontend.services.data_service.requests.get")
    def test_contract_negotiation_blocks_before_get_when_required(self, mget, mopt):
        data_service._BACKEND_DOWN_UNTIL_TS = 0.0
        data_service._LAST_MONITORING_ENDPOINT_CONTRACT = {"status": "unknown", "errors": [], "last_checked_at": None}
        cfg = {"enabled": True, "mode": "strict", "negotiation_required": True, "cache_ttl": 300, "fallback_to_simulation": False}

        def _fake_get(url, timeout=None, headers=None):
            if url.endswith("/health"):
                return _Resp(200, {"ok": True})
            if "/dashboard/state" in url:
                return _Resp(404, {})
            raise AssertionError("unexpected_get:" + url)

        mget.side_effect = _fake_get
        mopt.return_value = _Resp(200, headers={"X-Contract-ID": "energy_data", "X-Contract-Version": "2.0.0"})
        with patch.object(data_service, "CONTRACT_SYSTEM", cfg):
            out = data_service.fetch_real_energy_data()
        self.assertIsNone(out)
        diag = data_service.get_last_monitoring_diagnostic()
        self.assertEqual(diag.get("class"), "contract_negotiation_incompatible")
        c = data_service.get_last_monitoring_endpoint_contract()
        self.assertEqual(c.get("status"), "blocked")

    @patch("ecoaims_frontend.services.optimization_service._SESSION.post")
    def test_optimize_invalid_shape_raises_runtime_mismatch(self, mpost):
        optimization_service._LAST_OPTIMIZATION_ENDPOINT_CONTRACT = {"status": "unknown", "errors": [], "last_checked_at": None}
        mpost.return_value = _Resp(200, {"energy_distribution": "bad", "recommendation": ""})
        with self.assertRaises(RuntimeError) as ctx:
            optimization_service.run_energy_optimization(priority="renewable", battery_capacity_usage=50, skip_backend=False)
        self.assertIn("runtime_endpoint_contract_mismatch", str(ctx.exception))
        d = optimization_service.get_last_optimization_endpoint_contract()
        self.assertEqual(d.get("status"), "mismatch")

    @patch("ecoaims_frontend.services.reports_api.requests.get")
    def test_reports_precooling_impact_invalid_shape_returns_mismatch(self, mget):
        reports_api._REPORTS_DOWN_UNTIL_TS = 0.0
        mget.return_value = _Resp(200, {"summary": {}})
        data, err = reports_api.get_precooling_impact(period="week")
        self.assertIsNone(data)
        self.assertTrue(isinstance(err, str))
        self.assertIn("runtime_endpoint_contract_mismatch", err)
