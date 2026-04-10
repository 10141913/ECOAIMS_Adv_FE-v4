import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.services import contract_registry


class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError()
            err.response = self
            raise err

    def json(self):
        return self._json_data


class TestContractRegistry(unittest.TestCase):
    @patch("ecoaims_frontend.services.contract_registry._base_url", return_value="http://127.0.0.1:8008")
    @patch("ecoaims_frontend.services.contract_registry.requests.get")
    def test_registry_load_and_registry_validation_used(self, mget, _mbase):
        contract_registry._MANIFEST_CACHE = {}
        contract_registry._REGISTRY_CACHE = {}

        manifest = {
            "manifest_id": "ecoaims-contract-v1",
            "manifest_hash": "sha256-ecoaims-v1",
            "endpoints": {"GET /api/energy-data": {"type": "object", "required": {"solar": {"type": "object", "required": {"value": {"type": "number"}, "max": {"type": "number"}}}}}},
        }

        def _fake(url, timeout):
            if url.endswith("/api/contracts/index"):
                return _Resp(200, {"registry_version": "v1", "manifests": [{"manifest_id": "ecoaims-contract-v1"}]})
            if url.endswith("/api/contracts/ecoaims-contract-v1"):
                return _Resp(200, manifest)
            return _Resp(404, {})

        mget.side_effect = _fake
        reg = contract_registry.load_contract_registry("ecoaims-contract-v1", "sha256-ecoaims-v1")
        self.assertTrue(reg.get("registry_loaded"))
        ok, errs, src = contract_registry.validate_endpoint("GET /api/energy-data", {"solar": {"value": 1, "max": 2}})
        self.assertTrue(ok)
        self.assertEqual(src, "registry")
        self.assertEqual(errs, [])

    @patch("ecoaims_frontend.services.contract_registry._base_url", return_value="http://127.0.0.1:8008")
    @patch("ecoaims_frontend.services.contract_registry.requests.get", side_effect=requests.ConnectionError("down"))
    def test_registry_unavailable_falls_back(self, _mget, _mbase):
        contract_registry._MANIFEST_CACHE = {}
        reg = contract_registry.load_contract_registry("ecoaims-contract-v1", "sha256-ecoaims-v1")
        self.assertFalse(reg.get("registry_loaded"))
        ok, errs, src = contract_registry.validate_endpoint("GET /api/energy-data", {"solar": 1})
        self.assertEqual(src, "fallback")
        self.assertFalse(ok)
        self.assertTrue(errs)

    @patch("ecoaims_frontend.services.contract_registry._base_url", return_value="http://127.0.0.1:8008")
    @patch("ecoaims_frontend.services.contract_registry.requests.get")
    def test_backend_endpoint_map_contract_is_supported(self, mget, _mbase):
        contract_registry._MANIFEST_CACHE = {}
        contract_registry._REGISTRY_CACHE = {"registry_version": "contracts_registry_v1", "manifests": [{"manifest_id": "energy_data_contract", "manifest_hash": "h"}]}

        manifest = {
            "manifest_id": "energy_data_contract",
            "manifest_hash": "h",
            "endpoint_map": {
                "GET /api/energy-data": {
                    "method": "GET",
                    "path": "/api/energy-data",
                    "response": {
                        "required_fields": ["contract_manifest_id", "contract_manifest_version", "stream_id", "data_available", "source", "records"],
                        "optional_fields": ["notes"],
                    },
                }
            },
            "manifest": {"required_fields": [], "nested_shape": {"records[]": {"timestamp": "string", "pv_generation": "number"}}},
        }

        def _fake(url, timeout):
            if url.endswith("/api/contracts/index"):
                return _Resp(200, contract_registry._REGISTRY_CACHE)
            if url.endswith("/api/contracts/energy_data_contract"):
                return _Resp(200, manifest)
            return _Resp(404, {})

        mget.side_effect = _fake
        reg = contract_registry.load_contract_registry("energy_data_contract", "h")
        self.assertTrue(reg.get("registry_loaded"))
        ok, errs, src = contract_registry.validate_endpoint(
            "GET /api/energy-data",
            {
                "contract_manifest_id": "energy_data_contract",
                "contract_manifest_version": "2026-03-13",
                "stream_id": "default",
                "data_available": False,
                "source": "x",
                "records": [],
            },
        )
        self.assertTrue(ok)
        self.assertEqual(errs, [])
        self.assertEqual(src, "registry")

        ok2, errs2, _ = contract_registry.validate_endpoint(
            "GET /api/energy-data",
            {
                "contract_manifest_id": "energy_data_contract",
                "contract_manifest_version": "2026-03-13",
                "stream_id": "default",
                "data_available": "no",
                "source": "x",
                "records": [],
            },
        )
        self.assertFalse(ok2)
        self.assertTrue(any("not_bool" in e for e in errs2))
