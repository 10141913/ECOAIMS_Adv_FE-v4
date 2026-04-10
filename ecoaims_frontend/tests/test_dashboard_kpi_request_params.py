import unittest

from ecoaims_frontend.services import data_service


class TestDashboardKpiRequestParams(unittest.TestCase):
    def test_fetch_dashboard_kpi_does_not_send_building_area_by_default(self):
        captured = {}
        original = data_service._attempt_get_json
        try:
            def fake_attempt(url, timeout_s=(2.5, 5.0)):
                captured["url"] = url
                return {"ok": True}, {"url": url}

            data_service._attempt_get_json = fake_attempt
            out = data_service.fetch_dashboard_kpi(base_url="http://example", stream_id="default")
            self.assertEqual(out, {"ok": True})
            self.assertIn("/dashboard/kpi?", captured["url"])
            self.assertIn("stream_id=default", captured["url"])
            self.assertNotIn("building_area_m2=", captured["url"])
        finally:
            data_service._attempt_get_json = original

    def test_fetch_dashboard_kpi_sends_building_area_when_overridden(self):
        captured = {}
        original = data_service._attempt_get_json
        try:
            def fake_attempt(url, timeout_s=(2.5, 5.0)):
                captured["url"] = url
                return {"ok": True}, {"url": url}

            data_service._attempt_get_json = fake_attempt
            out = data_service.fetch_dashboard_kpi(base_url="http://example", stream_id="default", building_area_m2=123.4)
            self.assertEqual(out, {"ok": True})
            self.assertIn("stream_id=default", captured["url"])
            self.assertIn("building_area_m2=123.4", captured["url"])
        finally:
            data_service._attempt_get_json = original
