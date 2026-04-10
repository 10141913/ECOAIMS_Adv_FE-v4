import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import reports_api


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class TestReportsApi(unittest.TestCase):
    @patch("ecoaims_frontend.services.reports_api.requests.get")
    def test_get_precooling_impact_params(self, mget):
        reports_api._REPORTS_DOWN_UNTIL_TS = 0.0
        mget.return_value = _FakeResp(status_code=200, json_data={"basis": "modeled", "summary": {}, "scenarios": [], "quality": {}})
        _data, _err = reports_api.get_precooling_impact(
            period="week",
            zone="zone_a",
            stream_id="precooling",
            basis_filter="modeled,applied",
            granularity="daily",
        )
        self.assertIsNone(_err)
        self.assertEqual(mget.call_count, 1)
        _url = mget.call_args.kwargs.get("url") or mget.call_args.args[0]
        _params = mget.call_args.kwargs.get("params")
        self.assertIn("/api/reports/precooling-impact", _url)
        self.assertEqual(_params["period"], "week")
        self.assertEqual(_params["zone"], "zone_a")
        self.assertEqual(_params["stream_id"], "precooling")
        self.assertEqual(_params["basis"], "modeled,applied")
        self.assertEqual(_params["granularity"], "daily")

    @patch("ecoaims_frontend.services.reports_api.requests.get")
    def test_export_csv_success(self, mget):
        reports_api._REPORTS_DOWN_UNTIL_TS = 0.0
        mget.return_value = _FakeResp(status_code=200, json_data={"ignored": True}, content=b"a,b\n1,2\n")
        content, err = reports_api.get_precooling_impact_export_csv(
            period="week",
            granularity="daily",
            basis_filter="modeled",
            zone="zone_a",
            stream_id="precooling",
        )
        self.assertIsNone(err)
        self.assertEqual(content, b"a,b\n1,2\n")

    @patch("ecoaims_frontend.services.reports_api.requests.get", side_effect=requests.Timeout())
    def test_export_csv_timeout(self, _mget):
        reports_api._REPORTS_DOWN_UNTIL_TS = 0.0
        content, err = reports_api.get_precooling_impact_export_csv(period="week", granularity="daily")
        self.assertIsNone(content)
        self.assertIn("Timeout", err)

    @patch("ecoaims_frontend.services.reports_api.requests.get")
    def test_safe_get_invalid_json(self, mget):
        reports_api._REPORTS_DOWN_UNTIL_TS = 0.0
        mget.return_value = _FakeResp(status_code=200, json_data=ValueError("bad json"))
        data, err = reports_api.get_precooling_impact_filter_options()
        self.assertIsNone(data)
        self.assertIn("bukan JSON", err)
