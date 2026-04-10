import unittest
from unittest.mock import patch

import requests

from ecoaims_frontend.callbacks import precooling_callbacks
from ecoaims_frontend.services import precooling_api


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._json_data


class TestPrecoolingSelector(unittest.TestCase):
    @patch("ecoaims_frontend.services.precooling_api.requests.post")
    def test_post_selector_preview_uses_preview_path(self, mpost):
        mpost.return_value = _FakeResp(status_code=200, json_data={"ok": True})
        resp = precooling_api.post_precooling_selector_preview(
            "zone-a",
            {"zone_id": "zone-a", "selector_enabled": True, "selector_backend": "bandit"},
            return_candidates=True,
            base_url="http://127.0.0.1:8008",
        )
        self.assertIsInstance(resp, dict)
        self.assertTrue(resp.get("ok"))
        url = mpost.call_args.args[0]
        self.assertIn("/api/precooling/selector/preview", url)
        payload = mpost.call_args.kwargs.get("json")
        self.assertEqual(payload["zone_id"], "zone-a")
        self.assertTrue(payload["return_candidates"])
        self.assertEqual(payload["payload"]["selector_backend"], "bandit")

    def test_extract_selector_snapshot_from_audit_trail(self):
        payload = {
            "audit_trail": [
                {"status": "something_else"},
                {"status": "selector_snapshot", "selector_snapshot": {"selected_index": 2, "strategy": "bandit"}},
            ]
        }
        snap = precooling_callbacks._extract_selector_snapshot(payload)
        self.assertIsInstance(snap, dict)
        self.assertEqual(snap.get("selected_index"), 2)

    def test_render_selector_note_banner_is_graceful(self):
        self.assertIsNone(precooling_callbacks._render_selector_note_banner(None))
        banner = precooling_callbacks._render_selector_note_banner(
            {
                "message": "Candidates sedikit karena window sempit",
                "horizon_start": "2026-04-08T00:00:00Z",
                "horizon_end": "2026-04-09T00:00:00Z",
                "window_earliest": "06:00",
                "window_latest": "06:30",
                "effective_earliest": "06:10",
                "effective_latest": "06:20",
                "suggestion": "Perlebar latest_start atau tambah durations",
            }
        )
        self.assertIsNotNone(banner)

    def test_extract_selector_preview_notes_backend_notes(self):
        selector_note, backend_notes, safe_message = precooling_callbacks._extract_selector_preview_notes(
            {
                "selector_note": {"message": "x"},
                "audit_notes": [
                    {"status": "backend_note", "backend": "selector_preview", "note": "no_optimized_candidates_window_outside_horizon"},
                    {"status": "other", "note": "ignore"},
                ],
            }
        )
        self.assertIsInstance(selector_note, dict)
        self.assertEqual(backend_notes, ["no_optimized_candidates_window_outside_horizon"])
        self.assertEqual(safe_message, "Preview OK")
