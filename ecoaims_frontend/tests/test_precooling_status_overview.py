import unittest

from ecoaims_frontend.services.precooling_normalizer import normalize_status_overview


class TestPrecoolingStatusOverview(unittest.TestCase):
    def test_status_overview_fills_fields_from_schedule_slots_and_payload(self):
        sim_result = {
            "schedule": {
                "slots": [
                    {"time_slot": "2026-03-22T02:00:00+00:00", "temperature_setpoint": 25.0, "rh_setpoint": 50.0, "energy_source": "grid"},
                    {"time_slot": "2026-03-22T03:00:00+00:00", "temperature_setpoint": 24.0, "rh_setpoint": 55.0, "energy_source": "grid"},
                ]
            },
            "comparison": {"optimized": {"timestamps": ["2026-03-22T02:00:00+00:00", "2026-03-22T03:00:00+00:00"]}},
        }
        payload = {"target_temp_range": [22, 27], "target_rh_range": [45, 65], "optimizer_backend": "mpc", "weights": {"comfort": 1, "cost": 0.35}}
        out = normalize_status_overview(sim_result, payload)
        self.assertNotEqual(out.get("start_time"), "-")
        self.assertNotEqual(out.get("end_time"), "-")
        self.assertNotEqual(out.get("duration"), "-")
        self.assertEqual(out.get("target_temperature"), "22-27")
        self.assertEqual(out.get("target_rh"), "45-65")
        self.assertEqual(out.get("recommended_energy_source"), "grid")
        self.assertIn("optimization_objective", out)

