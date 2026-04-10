import os
import tempfile
import unittest


class TestReportsBackendContract(unittest.TestCase):
    def test_precooling_impact_endpoints_contract(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["ECOAIMS_OUTPUT_DIR"] = d
            from ecoaims_backend.reports import fastapi_api as reports

            opts = reports.precooling_impact_filter_options()
            self.assertIn("zones", opts)
            self.assertIn("streams", opts)

            snap = reports.precooling_impact(
                period="week",
                zone="zone_a",
                stream_id="precooling",
                basis="modeled,applied,fallback",
                granularity="daily",
            )
            self.assertIn("quality", snap)
            self.assertIn("filters", snap)
            self.assertEqual(snap["filters"]["zone_id"], "zone_a")

            hist = reports.precooling_impact_history(
                period="week",
                granularity="daily",
                basis="modeled,applied,fallback",
                zone="zone_a",
                stream_id="precooling",
            )
            self.assertIn("rows", hist)
            rows = hist["rows"]
            self.assertIsInstance(rows, list)

            if rows:
                rid = rows[-1].get("row_id")
                self.assertTrue(rid)

                detail = reports.precooling_impact_session_detail(row_id=rid, period="week", zone="zone_a", stream_id="precooling")
                self.assertIn("before_fidelity", detail)
                self.assertIn("after_fidelity", detail)
                self.assertIn("quality_flags", detail)

                ts = reports.precooling_impact_session_timeseries(row_id=rid, period="week", zone="zone_a", stream_id="precooling")
                self.assertIn("timestamps", ts)
                self.assertIn("series", ts)
                self.assertIsInstance(ts["timestamps"], list)
                self.assertIsInstance(ts["series"], dict)

