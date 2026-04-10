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

    def test_auth_flow_uses_captcha_cookie_and_csrf(self):
        import os
        import ecoaims_frontend.app as app_mod
        from werkzeug.security import generate_password_hash

        with patch.dict(
            os.environ,
            {
                "ECOAIMS_AUTH_ENABLED": "true",
                "ECOAIMS_ADMIN_USERNAME": "AdminECOAIMS",
                "ECOAIMS_ADMIN_PASSWORD_HASH": generate_password_hash("Admin3C041M5"),
            },
            clear=False,
        ):
            client = app_mod.server.test_client()
            cap = client.get("/api/auth/captcha")
            self.assertEqual(cap.status_code, 200)
            cap_js = cap.get_json()
            self.assertTrue(isinstance(cap_js, dict))
            csrf = cap_js.get("csrf_token")
            self.assertTrue(isinstance(csrf, str) and len(csrf) > 10)

            with client.session_transaction() as sess:
                captcha_txt = sess.get("ecoaims_captcha")
            self.assertTrue(isinstance(captcha_txt, str) and len(captcha_txt) == 6)

            resp = client.post(
                "/api/auth/login",
                json={"username": "AdminECOAIMS", "password": "Admin3C041M5", "captcha": captcha_txt, "next": "/"},
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(resp.status_code, 200)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("ok"), True)

    def test_auth_login_rejects_missing_csrf(self):
        import os
        import ecoaims_frontend.app as app_mod

        with patch.dict(os.environ, {"ECOAIMS_AUTH_ENABLED": "true"}, clear=False):
            client = app_mod.server.test_client()
            _ = client.get("/api/auth/captcha")
            resp = client.post("/api/auth/login", json={"username": "x", "password": "y", "captcha": "z"})
            self.assertEqual(resp.status_code, 403)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("error"), "csrf_invalid")

    def test_auth_login_rejects_wrong_captcha_case_sensitive(self):
        import os
        import ecoaims_frontend.app as app_mod
        from werkzeug.security import generate_password_hash

        with patch.dict(
            os.environ,
            {
                "ECOAIMS_AUTH_ENABLED": "true",
                "ECOAIMS_ADMIN_USERNAME": "AdminECOAIMS",
                "ECOAIMS_ADMIN_PASSWORD_HASH": generate_password_hash("Admin3C041M5"),
            },
            clear=False,
        ):
            client = app_mod.server.test_client()
            cap = client.get("/api/auth/captcha")
            csrf = (cap.get_json() or {}).get("csrf_token")
            with client.session_transaction() as sess:
                captcha_txt = str(sess.get("ecoaims_captcha") or "")
            bad = (captcha_txt[:-1] + ("A" if captcha_txt[-1:] != "A" else "B")) if captcha_txt else "AAAAAA"
            resp = client.post(
                "/api/auth/login",
                json={"username": "AdminECOAIMS", "password": "Admin3C041M5", "captcha": bad, "next": "/"},
                headers={"X-CSRF-Token": csrf or ""},
            )
            self.assertEqual(resp.status_code, 401)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("error"), "login_failed")
