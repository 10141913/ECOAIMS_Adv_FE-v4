import unittest
from unittest.mock import patch

import ecoaims_frontend.callbacks.home_callbacks as home_callbacks


class TestHomeRunbook(unittest.TestCase):
    def test_extract_runbook_prefers_home_on_home_tab(self):
        md, src = home_callbacks._extract_runbook_md({"home_runbook_md": "a", "runbook_md": "b"}, prefer_home=True)
        self.assertEqual(md, "a")
        self.assertEqual(src, "backend:home_runbook_md")

    def test_extract_runbook_prefers_runbook_md_when_not_home(self):
        md, src = home_callbacks._extract_runbook_md({"home_runbook_md": "a", "runbook_md": "b"}, prefer_home=False)
        self.assertEqual(md, "b")
        self.assertEqual(src, "backend:runbook_md")

    def test_auto_runbook_generation_when_runbook_md_missing(self):
        info = {
            "expected_host": "127.0.0.1",
            "expected_port": 8008,
            "ready": True,
            "canonical_backend_identity_ok": True,
            "required_endpoints": ["/health", "/api/energy-data", "/api/contracts/index"],
            "capabilities": {"monitoring": {"ready": True}, "reports": {"ready": False}},
        }
        md = home_callbacks._build_runbook_from_startup_info(info, bootstrap_base_url="http://127.0.0.1:8008")
        self.assertIn("Cara menjalankan ECOAIMS", md)
        self.assertIn("http://127.0.0.1:8008", md)
        self.assertIn("`/api/contracts/index`", md)
        self.assertIn("`monitoring`: ready=True", md)

    def test_compute_home_runbook_uses_env_override(self):
        class _Resp:
            status_code = 200

            headers = {"content-type": "text/plain"}

            text = "### Runbook dari endpoint khusus"

        with patch.dict("os.environ", {"ECOAIMS_HOME_RUNBOOK_URL": "http://127.0.0.1:8008/api/runbook"}), patch(
            "ecoaims_frontend.callbacks.home_callbacks.requests.get", return_value=_Resp()
        ):
            md, src = home_callbacks.compute_home_runbook({"base_url": "http://127.0.0.1:8008"})
        self.assertIn("Runbook dari endpoint khusus", md)
        self.assertIn("Sumber panduan: http://127.0.0.1:8008/api/runbook", src)

    def test_compute_home_runbook_builds_auto_when_startup_info_missing_runbook(self):
        class _Resp:
            status_code = 200

            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        payload = {
            "expected_host": "127.0.0.1",
            "expected_port": 8008,
            "ready": True,
            "required_endpoints": ["/health", "/api/contracts/index"],
            "capabilities": {"monitoring": {"ready": True}},
        }

        def fake_get(url, timeout=None):
            self.assertTrue(url.endswith("/api/startup-info"))
            return _Resp(payload)

        with patch("ecoaims_frontend.callbacks.home_callbacks.requests.get", side_effect=fake_get):
            md, src = home_callbacks.compute_home_runbook({"base_url": "http://127.0.0.1:8008"})
        self.assertIn("Cara menjalankan ECOAIMS", md)
        self.assertIn("Sumber panduan: backend:/api/startup-info (auto)", src)
