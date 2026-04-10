import unittest

from ecoaims_frontend.services.precooling_normalizer import normalize_kpi


class TestPrecoolingNormalizerKpi(unittest.TestCase):
    def test_normalize_kpi_accepts_backend_suffix_keys(self):
        raw = {
            "peak_reduction_kw": 1.25,
            "energy_saving_kwh": 3.5,
            "cost_saving_rp": 12500,
            "co2_reduction_kg": 2.75,
            "comfort_compliance_pct": 87.5,
            "exergy_efficiency": 0.12,
            "ipei": 0.9,
            "shr_avg": 0.77,
            "uncertainty": {"forecast_confidence": 0.8},
            "model_status": {"model": "mpc"},
        }
        out = normalize_kpi(raw)
        self.assertEqual(out["peak_reduction"], 1.25)
        self.assertEqual(out["energy_saving"], 3.5)
        self.assertEqual(out["cost_saving"], 12500)
        self.assertEqual(out["co2_reduction"], 2.75)
        self.assertEqual(out["comfort_compliance"], 87.5)
        self.assertEqual(out["exergy_efficiency"], 0.12)
        self.assertEqual(out["ipei"], 0.9)
        self.assertEqual(out["shr"], 0.77)
        self.assertEqual(out["uncertainty"].get("forecast_confidence"), 0.8)
        self.assertEqual(out["model_status"].get("model"), "mpc")

    def test_normalize_kpi_defaults_to_dash_when_missing(self):
        out = normalize_kpi({})
        self.assertEqual(out["E_total"], "-")
        self.assertEqual(out["peak_reduction"], "-")
        self.assertEqual(out["energy_saving"], "-")
        self.assertEqual(out["cost_saving"], "-")
        self.assertEqual(out["co2_reduction"], "-")
        self.assertEqual(out["comfort_compliance"], "-")

