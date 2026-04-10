import unittest

from ecoaims_frontend.services.precooling_normalizer import normalize_scenario_kpi, normalize_simulate_result


class TestPrecoolingNormalizerKpiCanonical(unittest.TestCase):
    def test_peak_kw_prefers_hvac_peak_kw(self):
        out = normalize_scenario_kpi({"hvac_peak_kw": 2.5, "peak_kw": 9.9, "peak_reduction_kw": 1.1})
        self.assertEqual(out["peak_kw"], 2.5)

    def test_peak_kw_falls_back_to_peak_kw_then_peak_reduction_kw(self):
        out1 = normalize_scenario_kpi({"peak_kw": 3.3, "peak_reduction_kw": 1.1})
        self.assertEqual(out1["peak_kw"], 3.3)
        out2 = normalize_scenario_kpi({"peak_reduction_kw": 1.1})
        self.assertEqual(out2["peak_kw"], 1.1)

    def test_comfort_pct_priority_and_default(self):
        out1 = normalize_scenario_kpi({"comfort_pct": 12.0, "comfort_compliance_pct": 99.0})
        self.assertEqual(out1["comfort_pct"], 12.0)
        out2 = normalize_scenario_kpi({"comfort_compliance_pct": 22.0})
        self.assertEqual(out2["comfort_pct"], 22.0)
        out3 = normalize_scenario_kpi({})
        self.assertEqual(out3["comfort_pct"], 0.0)

    def test_energy_cost_co2_absolute_priority_and_delta_fallback(self):
        out = normalize_scenario_kpi(
            {
                "hvac_energy_kwh": 10,
                "estimated_cost_rp": 1000,
                "estimated_co2_kg": 12,
                "energy_saving_kwh": 1,
                "cost_saving_rp": 2,
                "co2_reduction_kg": 3,
            }
        )
        self.assertEqual(out["energy_kwh"], 10.0)
        self.assertEqual(out["cost_rp"], 1000.0)
        self.assertEqual(out["co2_kg"], 12.0)

    def test_fig_peak_uses_canonical_peak_kw(self):
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

