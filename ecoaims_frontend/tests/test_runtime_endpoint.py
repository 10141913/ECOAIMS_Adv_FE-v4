import unittest
from unittest.mock import patch


class TestRuntimeEndpoint(unittest.TestCase):
    def test_runtime_endpoint_exists_and_has_required_fields(self):
        import ecoaims_frontend.app as app_mod

        client = app_mod.server.test_client()
        resp = client.get("/__runtime")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(isinstance(data, dict))
        for k in [
            "pid",
            "started_at",
            "ecoaims_api_base_url",
            "dash_host",
            "dash_port",
            "dash_debug",
            "dash_use_reloader",
        ]:
            self.assertIn(k, data)

    def test_monitoring_history_instructions_page_exists(self):
        import ecoaims_frontend.app as app_mod

        class _R:
            status_code = 200

            def json(self):
                return {"status": "ok", "history": {"required_min_for_comparison": 2}}

        with patch("ecoaims_frontend.app.requests.get", return_value=_R()):
            client = app_mod.server.test_client()
            resp = client.get("/instructions/monitoring-history")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("ECOAIMS_DEV_SEED_HISTORY_RECORDS", body)
        self.assertIn("required_min_for_comparison", body)
