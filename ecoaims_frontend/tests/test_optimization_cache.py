import unittest
from unittest.mock import patch

from ecoaims_frontend.services import optimization_service


class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if int(self.status_code) >= 400:
            raise RuntimeError("http_error")

    def json(self):
        return self._json_data


class TestOptimizationCache(unittest.TestCase):
    def setUp(self):
        optimization_service._OPT_CACHE.clear()
        optimization_service._INFLIGHT.clear()

    @patch("ecoaims_frontend.services.optimization_service.validate_endpoint", return_value=(True, [], "test"))
    @patch("ecoaims_frontend.services.optimization_service._SESSION.post")
    def test_cache_hits_within_ttl(self, mpost, _mval):
        optimization_service._OPT_CACHE_TTL_BASE_S = 10.0
        mpost.return_value = _Resp(
            200,
            {
                "energy_distribution": {"Solar PV": 1, "Wind Turbine": 2, "Battery": 3, "PLN/Grid": 4},
                "recommendation": "ok",
            },
        )
        a = optimization_service.run_energy_optimization(priority="grid", battery_capacity_usage=50, grid_limit=100, skip_backend=False)
        b = optimization_service.run_energy_optimization(priority="grid", battery_capacity_usage=50, grid_limit=100, skip_backend=False)
        self.assertEqual(mpost.call_count, 1)
        self.assertEqual(a, b)

    @patch("ecoaims_frontend.services.optimization_service.validate_endpoint", return_value=(True, [], "test"))
    @patch("ecoaims_frontend.services.optimization_service._SESSION.post")
    def test_cache_disabled_calls_backend_each_time(self, mpost, _mval):
        optimization_service._OPT_CACHE_TTL_BASE_S = 0.0
        mpost.return_value = _Resp(
            200,
            {
                "energy_distribution": {"Solar PV": 1, "Wind Turbine": 2, "Battery": 3, "PLN/Grid": 4},
                "recommendation": "ok",
            },
        )
        _ = optimization_service.run_energy_optimization(priority="grid", battery_capacity_usage=50, grid_limit=100, skip_backend=False)
        _ = optimization_service.run_energy_optimization(priority="grid", battery_capacity_usage=50, grid_limit=100, skip_backend=False)
        self.assertEqual(mpost.call_count, 1)
