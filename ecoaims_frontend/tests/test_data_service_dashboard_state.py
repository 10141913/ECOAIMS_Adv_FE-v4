import unittest

from ecoaims_frontend.services import data_service


class TestDataServiceDashboardState(unittest.TestCase):
    def test_adapt_dashboard_state_to_monitoring_maps_energy_mix(self):
        payload = {
            "data_available": True,
            "pv_power": 10.0,
            "wind_power": 5.0,
            "grid_import": 2.0,
            "biofuel_power": 1.0,
            "battery_soc_pct": 62.5,
            "battery_capacity_kwh": 80.0,
            "battery_energy_kwh": 50.0,
            "battery_status": "discharging",
            "energy_mix_kw": {
                "solar_pv": 9.0,
                "wind_turbine": 4.0,
                "pln_grid": 3.0,
                "biofuel": 2.0,
                "battery": 1.0,
                "total_load": 19.0,
            },
            "energy_mix_pct": {
                "solar_pv": 47.0,
                "wind_turbine": 21.0,
                "pln_grid": 16.0,
                "biofuel": 11.0,
                "battery": 5.0,
            },
        }

        out = data_service._adapt_dashboard_state_to_monitoring(payload)
        self.assertIsInstance(out, dict)
        self.assertEqual(out["solar"]["value"], 9.0)
        self.assertEqual(out["wind"]["value"], 4.0)
        self.assertEqual(out["grid"]["value"], 3.0)
        self.assertEqual(out["biofuel"]["value"], 2.0)
        self.assertEqual(out["solar"]["pct"], 47.0)
        self.assertEqual(out["grid"]["pct"], 16.0)
        self.assertEqual(out["battery"]["value"], 50.0)
        self.assertEqual(out["battery"]["max"], 80.0)
        self.assertEqual(out["battery"]["status"], "Discharging")
        self.assertAlmostEqual(out["battery"]["soc_pct"], 62.5, places=3)
        self.assertEqual(out["battery"]["battery_power_kw"], 1.0)
        self.assertEqual(out["load_kw"], 19.0)

