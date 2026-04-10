import unittest

from dash import dcc

from ecoaims_frontend.components.precooling.header import create_precooling_header
from ecoaims_frontend.components.precooling.scenario_lab import create_scenario_lab
from ecoaims_frontend.services.precooling_api import build_simulate_request


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


class TestPrecoolingDebugPayloadViewer(unittest.TestCase):
    def test_header_has_simulate_request_textarea_and_clipboard(self):
        header = create_precooling_header()
        ids = set()
        clipboard_targets = set()
        for n in _walk(header):
            nid = getattr(n, "id", None)
            if nid:
                ids.add(nid)
            if isinstance(n, dcc.Clipboard):
                tid = getattr(n, "target_id", None)
                if tid:
                    clipboard_targets.add(tid)
        self.assertIn("precooling-simulate-request-text", ids)
        self.assertIn("precooling-simulate-request-text", clipboard_targets)

    def test_scenario_lab_has_optimizer_backend_dropdown(self):
        lab = create_scenario_lab()
        ids = set()
        for n in _walk(lab):
            nid = getattr(n, "id", None)
            if nid:
                ids.add(nid)
        self.assertIn("precooling-optimizer-backend", ids)

    def test_build_simulate_request_includes_optimizer_backend(self):
        req = build_simulate_request({"zone": "floor1_a", "optimizer_backend": "mpc"}, base_url="http://127.0.0.1:8008")
        self.assertEqual(req.get("zone_id"), "floor1_a")
        self.assertIn("payload", req)
        self.assertEqual((req.get("payload") or {}).get("optimizer_backend"), "mpc")
