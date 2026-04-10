import unittest
from unittest.mock import patch

from ecoaims_frontend.layouts import reports_layout


class TestReportsGating(unittest.TestCase):
    def test_reports_backend_unreachable_returns_placeholders(self):
        readiness = {"backend_reachable": False, "base_url": "http://127.0.0.1:8008", "error_class": "backend_connection_refused"}
        with patch.object(reports_layout, "get_precooling_impact_filter_options") as p1, patch.object(reports_layout, "get_precooling_impact") as p2, patch.object(reports_layout, "get_precooling_impact_history") as p3:
            out = reports_layout.compute_reports_outputs("week", None, None, "daily", [], readiness)
            self.assertEqual(len(out), 21)
            p1.assert_not_called()
            p2.assert_not_called()
            p3.assert_not_called()

    def test_reports_contract_mismatch_returns_placeholders(self):
        readiness = {"backend_reachable": True, "backend_ready": True, "contract_valid": False, "contract_mismatch_reason": "mismatch"}
        with patch.object(reports_layout, "get_precooling_impact_filter_options") as p1, patch.object(reports_layout, "get_precooling_impact") as p2, patch.object(reports_layout, "get_precooling_impact_history") as p3:
            out = reports_layout.compute_reports_outputs("week", None, None, "daily", [], readiness)
            self.assertEqual(len(out), 21)
            p1.assert_not_called()
            p2.assert_not_called()
            p3.assert_not_called()

    def test_reports_capability_false_returns_placeholders(self):
        readiness = {"backend_reachable": True, "backend_ready": True, "contract_valid": True, "capabilities": {"reports": {"ready": False}}}
        with patch.object(reports_layout, "get_precooling_impact_filter_options") as p1, patch.object(reports_layout, "get_precooling_impact") as p2, patch.object(reports_layout, "get_precooling_impact_history") as p3:
            out = reports_layout.compute_reports_outputs("week", None, None, "daily", [], readiness)
            self.assertEqual(len(out), 21)
            p1.assert_not_called()
            p2.assert_not_called()
            p3.assert_not_called()

