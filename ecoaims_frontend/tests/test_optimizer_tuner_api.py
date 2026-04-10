import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import optimizer_tuner_api


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class TestOptimizerTunerApi(unittest.TestCase):
    @patch("ecoaims_frontend.services.optimizer_tuner_api._SESSION.post")
    def test_suggest_tuner_builds_url_and_payload(self, mpost):
        mpost.return_value = _FakeResp(status_code=200, json_data={"effective_params": {"weights": {"a": 1}}})
        readiness = {"base_url": "http://127.0.0.1:8008"}
        data = optimizer_tuner_api.suggest_tuner({"soc": 0.5, "hour": 10}, readiness=readiness, mode="drl_meta")
        self.assertIsInstance(data, dict)
        url = mpost.call_args.args[0]
        self.assertIn("/api/optimizer/tuner/suggest", url)
        payload = mpost.call_args.kwargs.get("json")
        self.assertEqual(payload["mode"], "drl_meta")
        self.assertEqual(payload["context"]["soc"], 0.5)
        self.assertEqual(payload["soc"], 0.5)

    @patch("ecoaims_frontend.services.optimizer_tuner_api._SESSION.post")
    def test_suggest_tuner_invalid_json_raises(self, mpost):
        mpost.return_value = _FakeResp(status_code=200, json_data=ValueError("bad json"), text="not json")
        with self.assertRaises(RuntimeError):
            _ = optimizer_tuner_api.suggest_tuner({"soc": 0.5}, base_url="http://127.0.0.1:8008")
