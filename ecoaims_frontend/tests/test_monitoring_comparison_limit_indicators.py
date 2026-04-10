import unittest

from ecoaims_frontend.callbacks.main_callbacks import comparison_status_banner


class TestMonitoringComparisonLimitIndicators(unittest.TestCase):
    def test_limit_and_trimmed_indicators_render(self):
        diag = {
            "backend_ok": True,
            "comparison_ready": False,
            "min_history_for_comparison": 12,
            "min_history_source": "backend_diag",
            "records_len": 1,
            "records_count": 1,
            "diag_energy_data_records_count": 24,
            "data_maybe_trimmed": True,
            "data_trim_gap": 23,
            "applied_limit": 1,
            "returned_records_len": 1,
            "available_records_len": 24,
            "trimmed": True,
            "reasons": ["insufficient_history_for_comparison:min=12 got=1"],
            "attempts": [],
            "energy_contract_ok": True,
            "energy_contract_source": "registry",
        }
        banner = comparison_status_banner(diag)
        s = str(banner)
        self.assertIn("LIMIT=1", s)
        self.assertIn("RETURNED=1", s)
        self.assertIn("AVAILABLE=24", s)
        self.assertIn("TRIMMED=true", s)

    def test_maybe_trimmed_indicator_render(self):
        diag = {
            "backend_ok": True,
            "comparison_ready": True,
            "min_history_for_comparison": 2,
            "min_history_source": "backend_diag",
            "records_len": 2,
            "records_count": 2,
            "diag_energy_data_records_count": 24,
            "data_maybe_trimmed": True,
            "data_trim_gap": 22,
            "applied_limit": 2,
            "returned_records_len": 2,
            "available_records_len": 24,
            "trimmed": False,
            "reasons": [],
            "attempts": [],
            "energy_contract_ok": True,
            "energy_contract_source": "registry",
        }
        banner = comparison_status_banner(diag)
        self.assertIn("MAYBE_TRIMMED", str(banner))
