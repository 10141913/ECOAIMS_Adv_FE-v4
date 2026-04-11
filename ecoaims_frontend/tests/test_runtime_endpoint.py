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
                "ECOAIMS_AUTH_MODE": "local",
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
            captcha_token = cap_js.get("captcha_token")
            csrf_session = cap_js.get("csrf_session")
            self.assertTrue(isinstance(captcha_token, str) and len(captcha_token) > 10)
            self.assertTrue(isinstance(csrf_session, str) and len(csrf_session) > 10)

            with client.session_transaction() as sess:
                captcha_txt = sess.get("ecoaims_captcha")
            self.assertTrue(isinstance(captcha_txt, str) and len(captcha_txt) == 6)

            resp = client.post(
                "/api/auth/login",
                json={
                    "username": "AdminECOAIMS",
                    "password": "Admin3C041M5",
                    "captcha": captcha_txt,
                    "csrf_token": csrf,
                    "csrf_session": csrf_session,
                    "captcha_token": captcha_token,
                    "next": "/",
                },
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(resp.status_code, 200)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("ok"), True)

    def test_login_page_uses_relative_auth_endpoints(self):
        import os
        import ecoaims_frontend.app as app_mod

        with patch.dict(os.environ, {"ECOAIMS_AUTH_ENABLED": "true"}, clear=False):
            client = app_mod.server.test_client()
            resp = client.get("/login")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_data(as_text=True)
            self.assertIn("fetch('api/auth/captcha'", body)
            self.assertIn("fetch('api/auth/login'", body)

    def test_auth_login_rejects_missing_csrf(self):
        import os
        import ecoaims_frontend.app as app_mod

        with patch.dict(os.environ, {"ECOAIMS_AUTH_ENABLED": "true", "ECOAIMS_AUTH_MODE": "local"}, clear=False):
            client = app_mod.server.test_client()
            _ = client.get("/api/auth/captcha")
            resp = client.post("/api/auth/login", json={"username": "x", "password": "y", "captcha": "z"})
            self.assertEqual(resp.status_code, 403)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("detail"), "csrf_invalid")

    def test_auth_login_rejects_wrong_captcha_case_sensitive(self):
        import os
        import ecoaims_frontend.app as app_mod
        from werkzeug.security import generate_password_hash

        with patch.dict(
            os.environ,
            {
                "ECOAIMS_AUTH_ENABLED": "true",
                "ECOAIMS_AUTH_MODE": "local",
                "ECOAIMS_ADMIN_USERNAME": "AdminECOAIMS",
                "ECOAIMS_ADMIN_PASSWORD_HASH": generate_password_hash("Admin3C041M5"),
            },
            clear=False,
        ):
            client = app_mod.server.test_client()
            cap = client.get("/api/auth/captcha")
            cap_js = cap.get_json() or {}
            csrf = cap_js.get("csrf_token")
            captcha_token = cap_js.get("captcha_token")
            csrf_session = cap_js.get("csrf_session")
            with client.session_transaction() as sess:
                captcha_txt = str(sess.get("ecoaims_captcha") or "")
            bad = (captcha_txt[:-1] + ("A" if captcha_txt[-1:] != "A" else "B")) if captcha_txt else "AAAAAA"
            resp = client.post(
                "/api/auth/login",
                json={
                    "username": "AdminECOAIMS",
                    "password": "Admin3C041M5",
                    "captcha": bad,
                    "csrf_token": csrf or "",
                    "csrf_session": csrf_session or "",
                    "captcha_token": captcha_token or "",
                    "next": "/",
                },
                headers={"X-CSRF-Token": csrf or ""},
            )
            self.assertEqual(resp.status_code, 401)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertEqual(js.get("error"), "login_failed")

    def test_auth_proxy_mode_forwards_to_backend(self):
        import os
        import ecoaims_frontend.app as app_mod

        class _RawHeaders:
            def __init__(self, values):
                self._values = values

            def get_all(self, _k):
                return list(self._values)

        class _Raw:
            def __init__(self, values):
                self.headers = _RawHeaders(values)

        class _Resp:
            def __init__(self, status_code, payload, set_cookies):
                self.status_code = status_code
                self._payload = payload
                self.headers = {"content-type": "application/json", "x-request-id": "rid"}
                self.raw = _Raw(set_cookies)
                self.content = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

            def json(self):
                return self._payload

        import json

        def _fake_request(method, url, json=None, headers=None, timeout=None, stream=None):
            if method.upper() == "GET" and url.endswith("/api/auth/captcha"):
                return _Resp(
                    200,
                    {
                        "csrf_token": "csrf123",
                        "csrf_session": "csrf_sess",
                        "captcha_token": "cap_tok",
                        "captcha_svg_base64": "PHN2Zz48L3N2Zz4=",
                        "expires_in_s": 300,
                    },
                    ["ecoaims_captcha=cap_tok; Path=/; HttpOnly", "ecoaims_csrf=csrf_sess; Path=/; HttpOnly"],
                )
            if method.upper() == "POST" and url.endswith("/api/auth/login"):
                return _Resp(
                    200,
                    {"access_token": "tok", "token_type": "bearer", "expires_in_s": 86400},
                    ["ecoaims_session=sess; Path=/; HttpOnly"],
                )
            return _Resp(404, {"detail": "not_found"}, [])

        with patch.dict(
            os.environ,
            {
                "ECOAIMS_AUTH_ENABLED": "true",
                "ECOAIMS_AUTH_MODE": "proxy",
                "ECOAIMS_AUTH_BACKEND_BASE_URL": "http://127.0.0.1:8008",
            },
            clear=False,
        ), patch("ecoaims_frontend.app.requests.request", side_effect=_fake_request):
            client = app_mod.server.test_client()
            cap = client.get("/api/auth/captcha")
            self.assertEqual(cap.status_code, 200)
            cap_js = cap.get_json()
            self.assertTrue(isinstance(cap_js, dict))
            self.assertIn("captcha_image", cap_js)
            csrf = cap_js.get("csrf_token")
            self.assertEqual(csrf, "csrf123")

            resp = client.post(
                "/api/auth/login",
                json={"username": "AdminECOAIMS", "password": "Admin3C041M5", "captcha": "ABCDEF", "csrf_token": "csrf123"},
                headers={"X-CSRF-Token": "csrf123"},
            )
            self.assertEqual(resp.status_code, 200)
            js = resp.get_json()
            self.assertTrue(isinstance(js, dict))
            self.assertIn("access_token", js)
