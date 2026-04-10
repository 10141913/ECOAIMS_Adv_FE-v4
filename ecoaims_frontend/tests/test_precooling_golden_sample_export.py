import unittest

from ecoaims_frontend.callbacks.precooling_callbacks import _build_precooling_golden_sample_bundle, _golden_sample_filename


class TestPrecoolingGoldenSampleExport(unittest.TestCase):
    def test_filename_is_safe(self):
        import datetime

        fn = _golden_sample_filename(zone="zone/a", ts=datetime.datetime(2026, 3, 23, 10, 0, 0))
        self.assertTrue(fn.startswith("precooling_golden_sample_"))
        self.assertIn("zone_a", fn)
        self.assertTrue(fn.endswith(".json"))

    def test_bundle_contains_required_fields(self):
        out = _build_precooling_golden_sample_bundle(
            base_url="http://127.0.0.1:8008",
            zone="zone_a",
            mode="advisory",
            simulate_request_diag={"endpoint": "POST /api/precooling/simulate"},
            simulate_result={"status": {"status_today": "optimized"}},
            doctor={"ok": True},
            doctor_error=None,
        )
        self.assertEqual(out.get("feature"), "precooling")
        self.assertEqual(out.get("selected_zone"), "zone_a")
        self.assertIn("simulate_request_diag", out)
        self.assertIn("simulate_response", out)
        self.assertIn("doctor", out)

