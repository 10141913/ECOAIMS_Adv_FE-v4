import unittest
from unittest.mock import patch

from ecoaims_frontend.callbacks.main_callbacks import comparison_status_banner
from ecoaims_frontend.ui.contract_error_ui import render_contract_mismatch_error


class TestContractErrorUI(unittest.TestCase):
    def test_render_contract_mismatch_error_renders_expected_sections(self):
        details = {
            "expected_version": "energy_data_contract@h1",
            "actual_version": "2026-03-13",
            "compatibility": {"reason": "shape_validation_failed"},
            "missing_fields": ["records", "stream_id"],
            "technical": {"endpoint": "GET /api/energy-data", "errors": ["$:missing:records"]},
        }
        ui = render_contract_mismatch_error(details)
        s = str(ui)
        self.assertIn("Contract Compatibility Issue", s)
        self.assertIn("Contract Version Analysis", s)
        self.assertIn("Energy Data Contract", s)
        self.assertIn("energy_data_contract@h1", s)
        self.assertIn("2026-03-13", s)
        self.assertIn("Missing Required Fields", s)
        self.assertIn("records", s)
        self.assertIn("stream_id", s)
        self.assertIn("Operator Actions", s)
        self.assertIn("Fitur ini belum diaktifkan", s)

    def test_render_contract_mismatch_error_without_missing_fields_is_ok(self):
        details = {"expected_version": "x", "actual_version": "y", "compatibility": {}, "technical": "raw"}
        ui = render_contract_mismatch_error(details)
        s = str(ui)
        self.assertIn("Contract Compatibility Issue", s)
        self.assertIn("Operator Actions", s)
        self.assertNotIn("Missing Required Fields", s)
        self.assertIn("Technical Details", s)

    def test_render_contract_mismatch_error_handles_unexpected_types(self):
        ui = render_contract_mismatch_error(None)
        self.assertIn("Contract Compatibility Issue", str(ui))

        ui2 = render_contract_mismatch_error(
            {
                "expected_version": 123,
                "actual_version": True,
                "compatibility": "bad",
                "missing_fields": "records,stream_id",
                "technical": {"x": object()},
            }
        )
        s2 = str(ui2)
        self.assertIn("Missing Required Fields", s2)
        self.assertIn("records", s2)
        self.assertIn("stream_id", s2)
        self.assertIn("Technical Details", s2)

    def test_comparison_status_banner_renders_contract_mismatch_when_runtime_mismatch(self):
        diag = {
            "backend_ok": True,
            "comparison_ready": False,
            "min_history_for_comparison": 12,
            "reasons": ["runtime_endpoint_contract_mismatch:/api/energy-data"],
            "energy_contract_ok": False,
            "energy_contract_source": "registry",
            "energy_contract_errors": ["$:missing:records", "missing:stream_id", "$.data_available:not_bool"],
            "energy_data": {"contract_manifest_version": "2026-03-13", "contract_manifest_id": "energy_data_contract"},
        }
        with patch(
            "ecoaims_frontend.callbacks.main_callbacks.contract_registry.get_registry_cache",
            return_value={"endpoint_map": {"GET /api/energy-data": {"contract_manifest_id": "energy_data_contract", "contract_manifest_hash": "h1"}}},
        ):
            banner = comparison_status_banner(diag)
        s = str(banner)
        self.assertIn("Contract Compatibility Issue", s)
        self.assertIn("Missing Required Fields", s)
        self.assertIn("records", s)
        self.assertIn("stream_id", s)
