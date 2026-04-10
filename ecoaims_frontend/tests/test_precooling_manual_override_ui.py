import unittest

from dash import dcc

from ecoaims_frontend.components.precooling.schedule_panel import create_schedule_and_control
from ecoaims_frontend.services.precooling_normalizer import normalize_status


def _walk(node):
    if node is None:
        return
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for c in children:
            yield from _walk(c)
    else:
        yield from _walk(children)


class TestPrecoolingManualOverrideUi(unittest.TestCase):
    def test_schedule_panel_contains_manual_override_form_ids(self):
        panel = create_schedule_and_control()
        ids = set()
        for n in _walk(panel):
            nid = getattr(n, "id", None)
            if nid:
                ids.add(nid)
        for required in [
            "precooling-override-temp",
            "precooling-override-rh",
            "precooling-override-duration",
            "precooling-override-hvac-mode",
            "precooling-override-energy-source",
            "precooling-override-reason",
            "precooling-request-override-btn",
            "precooling-approve-override-btn",
            "precooling-cancel-override-btn",
            "precooling-override-state-badge",
            "precooling-override-state-details",
        ]:
            self.assertIn(required, ids)

    def test_normalize_status_maps_manual_override(self):
        raw = {
            "manual_override": {
                "state": "active",
                "expires_at": "t1",
                "reason": "test",
                "setpoints": {"temperature_setpoint_c": 25.0, "rh_setpoint_pct": 60.0, "hvac_mode": "cooling", "energy_source": "grid"},
            }
        }
        out = normalize_status(raw)
        self.assertEqual(out.get("manual_override_state"), "active")
        self.assertEqual(out.get("manual_override_expires_at"), "t1")
        self.assertEqual(out.get("manual_override_reason"), "test")
        self.assertEqual((out.get("manual_override_setpoints") or {}).get("temperature_setpoint_c"), 25.0)

