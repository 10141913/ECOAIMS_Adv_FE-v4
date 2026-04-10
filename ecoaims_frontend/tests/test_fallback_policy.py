import unittest
from unittest.mock import patch

import requests

import ecoaims_frontend.services.data_service as data_service
import ecoaims_frontend.services.optimization_service as optimization_service


class TestFallbackPolicy(unittest.TestCase):
    def test_monitoring_backend_down_no_local_sim(self):
        data_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        data_service.API_BASE_URL = None
        data_service.ALLOW_LOCAL_SIMULATION_FALLBACK = False
        data_service.DEBUG_MODE = True
        data_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = False
        data_service.USE_REAL_DATA = True
        with patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.RequestException("down")):
            self.assertIsNone(data_service.get_energy_data())

    def test_monitoring_backend_down_local_sim_enabled(self):
        data_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        data_service.API_BASE_URL = None
        data_service.ALLOW_LOCAL_SIMULATION_FALLBACK = True
        data_service.DEBUG_MODE = True
        data_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = False
        with patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.RequestException("down")):
            data = data_service.get_energy_data()
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("solar", {}).get("source"), "local_sim")

    def test_optimization_backend_down_no_local_sim(self):
        optimization_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        optimization_service.API_BASE_URL = None
        optimization_service.ALLOW_LOCAL_SIMULATION_FALLBACK = False
        optimization_service.DEBUG_MODE = True
        optimization_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = False
        optimization_service.USE_REAL_DATA = True
        optimization_service._OPT_CACHE.clear()
        optimization_service._INFLIGHT.clear()
        optimization_service._OPT_CACHE_TTL_BASE_S = 0.0
        with patch("ecoaims_frontend.services.optimization_service._SESSION.post", side_effect=requests.RequestException("down")):
            with self.assertRaises(RuntimeError):
                optimization_service.run_energy_optimization(
                    priority="renewable",
                    battery_capacity_usage=50,
                    grid_limit=100,
                    solar_available=60,
                    wind_available=30,
                    total_demand=120,
                )

    def test_optimization_backend_down_local_sim_enabled(self):
        optimization_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        optimization_service.API_BASE_URL = None
        optimization_service.ALLOW_LOCAL_SIMULATION_FALLBACK = True
        optimization_service.DEBUG_MODE = True
        optimization_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = False
        optimization_service.USE_REAL_DATA = True
        optimization_service._OPT_CACHE.clear()
        optimization_service._INFLIGHT.clear()
        optimization_service._OPT_CACHE_TTL_BASE_S = 0.0
        with patch("ecoaims_frontend.services.optimization_service._SESSION.post", side_effect=requests.RequestException("down")):
            usage, recommendation = optimization_service.run_energy_optimization(
                priority="renewable",
                battery_capacity_usage=50,
                grid_limit=100,
                solar_available=60,
                wind_available=30,
                total_demand=120,
            )
        self.assertIn("Solar PV", usage)
        self.assertIn("Simulasi lokal", recommendation)

    def test_monitoring_canonical_mode_disables_local_sim(self):
        data_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        data_service.API_BASE_URL = None
        data_service.ALLOW_LOCAL_SIMULATION_FALLBACK = True
        data_service.DEBUG_MODE = True
        data_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = True
        with patch("ecoaims_frontend.services.data_service.requests.get", side_effect=requests.RequestException("down")):
            self.assertIsNone(data_service.get_energy_data())

    def test_optimization_canonical_mode_disables_local_sim(self):
        optimization_service.ECOAIMS_API_BASE_URL = "http://127.0.0.1:9999"
        optimization_service.API_BASE_URL = None
        optimization_service.ALLOW_LOCAL_SIMULATION_FALLBACK = True
        optimization_service.DEBUG_MODE = True
        optimization_service.ECOAIMS_REQUIRE_CANONICAL_POLICY = True
        optimization_service._OPT_CACHE.clear()
        optimization_service._INFLIGHT.clear()
        optimization_service._OPT_CACHE_TTL_BASE_S = 0.0
        with patch("ecoaims_frontend.services.optimization_service._SESSION.post", side_effect=requests.RequestException("down")):
            with self.assertRaises(RuntimeError):
                optimization_service.run_energy_optimization(
                    priority="renewable",
                    battery_capacity_usage=50,
                    grid_limit=100,
                    solar_available=60,
                    wind_available=30,
                    total_demand=120,
                )
