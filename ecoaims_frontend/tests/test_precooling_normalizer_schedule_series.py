import unittest

from ecoaims_frontend.services.precooling_normalizer import normalize_schedule


class TestPrecoolingNormalizerScheduleSeries(unittest.TestCase):
    def test_normalize_schedule_builds_slots_from_temperature_schedule_dicts(self):
        raw = {
            "temperature_schedule": [
                {"timestamp": "t1", "temp_setpoint_c": 25.0, "rh_setpoint_pct": 60.0},
                {"timestamp": "t2", "temp_setpoint_c": 24.0, "rh_setpoint_pct": 58.0},
            ],
            "rh_schedule": [
                {"timestamp": "t1", "temp_setpoint_c": 25.0, "rh_setpoint_pct": 60.0},
                {"timestamp": "t2", "temp_setpoint_c": 24.0, "rh_setpoint_pct": 58.0},
            ],
        }
        out = normalize_schedule(raw)
        slots = out.get("slots") or []
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0].get("time_slot"), "t1")
        self.assertEqual(slots[0].get("temperature_setpoint"), 25.0)
        self.assertEqual(slots[0].get("rh_setpoint"), 60.0)

