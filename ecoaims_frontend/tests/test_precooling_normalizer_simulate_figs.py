import unittest

from ecoaims_frontend.services.precooling_normalizer import normalize_simulate_result


class TestPrecoolingNormalizerSimulateFigs(unittest.TestCase):
    def test_normalize_simulate_result_builds_before_after_figs_from_comparison(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "kpi": {"latent_load_kwh": 6.3},
            "explainability": {"confidence_score": 0.65, "fallback_used": False, "reason": ["Mode: optimized (backend=mpc)"], "warnings": []},
            "comparison": {
                "baseline": {"timestamps": ["t1", "t2"], "series": {"hvac_electrical_kw": [1, 2], "zone_temp_c": [25, 24], "zone_rh_pct": [60, 61]}},
                "optimized": {"timestamps": ["t1", "t2"], "series": {"hvac_electrical_kw": [1.5, 1.8], "zone_temp_c": [24.5, 24.0], "zone_rh_pct": [58, 59]}},
            },
        }
        out = normalize_simulate_result(raw)
        self.assertIn("fig_load", out)
        self.assertIn("fig_before_after_temp", out)
        self.assertIn("fig_before_after_rh", out)
        self.assertIn("kpi", out)
        kpi = out.get("kpi") or {}
        self.assertEqual((kpi.get("model_status") or {}).get("status"), "mpc")
        self.assertEqual((kpi.get("uncertainty") or {}).get("forecast_confidence"), 0.65)

    def test_peak_comparison_prefers_hvac_peak_kw(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"hvac_peak_kw": 2.59, "peak_reduction_kw": 0}},
                "rule_based": {"kpi": {"hvac_peak_kw": 7.88, "peak_reduction_kw": 0}},
                "optimized": {"kpi": {"hvac_peak_kw": 2.59, "peak_reduction_kw": 0}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_peak") or {}
        y = (((fig.get("data") or [{}])[0]).get("y")) if isinstance(fig, dict) else None
        self.assertEqual(y, [2.59, 7.88, 2.59])

    def test_peak_comparison_falls_back_to_peak_kw_then_peak_reduction_kw(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"peak_kw": 1.1}},
                "rule_based": {"kpi": {"peak_reduction_kw": 0.5}},
                "optimized": {"kpi": {}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_peak") or {}
        y = (((fig.get("data") or [{}])[0]).get("y")) if isinstance(fig, dict) else None
        self.assertEqual(y, [1.1, 0.5, 0.0])

    def test_cost_co2_scatter_prefers_estimated_absolute(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"estimated_cost_rp": 1000, "estimated_co2_kg": 10}},
                "rule_based": {"kpi": {"estimated_cost_rp": 2000, "estimated_co2_kg": 20}},
                "optimized": {"kpi": {"estimated_cost_rp": 1500, "estimated_co2_kg": 15}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_scatter") or {}
        trace = (fig.get("data") or [{}])[0] if isinstance(fig, dict) else {}
        self.assertEqual(trace.get("x"), [1000.0, 2000.0, 1500.0])
        self.assertEqual(trace.get("y"), [10.0, 20.0, 15.0])

    def test_cost_co2_scatter_falls_back_to_saving_when_no_estimated(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"cost_saving_rp": 0, "co2_reduction_kg": 0}},
                "rule_based": {"kpi": {"cost_saving_rp": 500, "co2_reduction_kg": 5}},
                "optimized": {"kpi": {"cost_saving_rp": 250, "co2_reduction_kg": 2.5}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_scatter") or {}
        trace = (fig.get("data") or [{}])[0] if isinstance(fig, dict) else {}
        self.assertEqual(trace.get("x"), [0.0, 500.0, 250.0])
        self.assertEqual(trace.get("y"), [0.0, 5.0, 2.5])

    def test_comfort_compliance_prefers_comfort_pct(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"comfort_pct": 10.0, "comfort_compliance_pct": 99.0}},
                "rule_based": {"kpi": {"comfort_pct": 20.0}},
                "optimized": {"kpi": {"comfort_pct": 30.0}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_comfort") or {}
        y = (((fig.get("data") or [{}])[0]).get("y")) if isinstance(fig, dict) else None
        self.assertEqual(y, [10.0, 20.0, 30.0])

    def test_comfort_compliance_falls_back_to_comfort_compliance_pct(self):
        raw = {
            "zone_id": "zone_a",
            "status": "optimized",
            "comparison": {
                "baseline": {"kpi": {"comfort_compliance_pct": 11.0}},
                "rule_based": {"kpi": {"comfort_compliance_pct": 22.0}},
                "optimized": {"kpi": {}},
            },
        }
        out = normalize_simulate_result(raw)
        fig = out.get("fig_comfort") or {}
        y = (((fig.get("data") or [{}])[0]).get("y")) if isinstance(fig, dict) else None
        self.assertEqual(y, [11.0, 22.0, 0.0])
