import json
import unittest
from unittest.mock import patch

import ecoaims_frontend.callbacks.home_callbacks as home_callbacks


class _Resp:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = int(status_code)
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class TestHomeDoctorReport(unittest.TestCase):
    def test_compute_doctor_report_ok(self):
        with patch("ecoaims_frontend.callbacks.home_callbacks.requests.get", return_value=_Resp(200, {"zones_count": 3})):
            s, msg = home_callbacks.compute_doctor_report({"base_url": "http://127.0.0.1:8008"})
        j = json.loads(s)
        self.assertTrue(j.get("ok"))
        self.assertEqual((j.get("doctor") or {}).get("zones_count"), 3)
        self.assertIn("OK (200)", msg)

    def test_compute_doctor_report_http_error(self):
        with patch("ecoaims_frontend.callbacks.home_callbacks.requests.get", return_value=_Resp(404, {}, text="not found")):
            s, msg = home_callbacks.compute_doctor_report({"base_url": "http://127.0.0.1:8008"})
        j = json.loads(s)
        self.assertFalse(j.get("ok"))
        self.assertEqual(j.get("http_status"), 404)
        self.assertIn("doctor_http_error", j.get("error") or "")
        self.assertIn("HTTP 404", msg)

    def test_doctor_report_filename_is_safe(self):
        fn = home_callbacks._doctor_report_filename(base_url="http://127.0.0.1:8008", ts=1234567890)
        self.assertTrue(fn.startswith("doctor_report_"))
        self.assertTrue(fn.endswith(".json"))

    def test_contract_change_banner_hidden_when_same(self):
        prev = {"contract_hashes": {"POST /api/precooling/simulate": "a"}}
        nxt = {"contract_hashes": {"POST /api/precooling/simulate": "a"}}
        children, style = home_callbacks._contract_change_banner(prev, nxt)
        self.assertEqual(children, "")
        self.assertEqual(style.get("display"), "none")

    def test_contract_change_banner_shown_when_changed(self):
        prev = {"contract_hashes": {"POST /api/precooling/simulate": "a"}}
        nxt = {"contract_hashes": {"POST /api/precooling/simulate": "b"}}
        children, style = home_callbacks._contract_change_banner(prev, nxt)
        self.assertNotEqual(children, "")
        self.assertNotEqual(style.get("display"), "none")
