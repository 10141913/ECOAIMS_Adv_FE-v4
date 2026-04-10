import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import policy_proposer_api


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


class TestPolicyProposerApi(unittest.TestCase):
    @patch("ecoaims_frontend.services.policy_proposer_api._SESSION.post")
    def test_propose_policy_action_builds_url_and_payload(self, mpost):
        mpost.return_value = _FakeResp(status_code=200, json_data={"proposed_action": {"a": 1}, "projected_action": {"a": 0}})
        readiness = {"base_url": "http://127.0.0.1:8008"}
        data = policy_proposer_api.propose_policy_action({"soc": 0.5, "demand_total_kwh": 10.0}, readiness=readiness)
        self.assertIsInstance(data, dict)
        url = mpost.call_args.args[0]
        self.assertIn("/api/optimizer/policy/propose", url)
        payload = mpost.call_args.kwargs.get("json")
        self.assertEqual(payload["soc"], 0.5)
        self.assertEqual(payload["demand_total_kwh"], 10.0)
        self.assertIn("renewable_potential_kwh", payload)

    @patch("ecoaims_frontend.services.policy_proposer_api._SESSION.post")
    def test_propose_policy_action_invalid_json_raises(self, mpost):
        mpost.return_value = _FakeResp(status_code=200, json_data=ValueError("bad json"), text="not json")
        with self.assertRaises(RuntimeError):
            _ = policy_proposer_api.propose_policy_action({"soc": 0.5}, base_url="http://127.0.0.1:8008")
