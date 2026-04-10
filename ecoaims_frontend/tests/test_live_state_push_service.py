import unittest
from unittest.mock import patch

from ecoaims_frontend.services.live_state_push_service import maybe_push_live_state


class TestLiveStatePushService(unittest.TestCase):
    def test_disabled_by_default(self):
        live_data = {"health": {"active_sensors": 1}, "supply": {"Solar PV": 10.0}, "demand": {"Load": 5.0}}
        with patch("ecoaims_frontend.services.live_state_push_service._SESSION.post") as mpost:
            ok = maybe_push_live_state(base_url="http://127.0.0.1:8008", live_data=live_data, stream_id="default")
        self.assertFalse(ok)
        self.assertEqual(mpost.call_count, 0)

    def test_posts_when_enabled_and_has_active_sensors(self):
        live_data = {
            "health": {"active_sensors": 2},
            "supply": {"Solar PV": 12.0, "Wind Turbine": 1.0, "PLN/Grid": 0.5, "Biofuel": 0.0, "Battery": 40.0},
            "demand": {"Load": 9.0},
        }

        class _Resp:
            status_code = 200

        with patch.dict("os.environ", {"ECOAIMS_FE_PUSH_LIVE_STATE": "true", "ECOAIMS_FE_PUSH_LIVE_STATE_MIN_INTERVAL_S": "0"}), patch(
            "ecoaims_frontend.services.live_state_push_service._SESSION.get", side_effect=Exception("skip_startup_info")
        ), patch("ecoaims_frontend.services.live_state_push_service._SESSION.post", return_value=_Resp()) as mpost:
            ok = maybe_push_live_state(base_url="http://127.0.0.1:8008", live_data=live_data, stream_id="default")

        self.assertTrue(ok)
        self.assertEqual(mpost.call_count, 1)
        url = mpost.call_args[0][0]
        payload = mpost.call_args[1]["json"]
        self.assertIn("/dashboard/live/state", url)
        self.assertEqual(payload["stream_id"], "default")
        self.assertEqual(payload["pv_power"], 12.0)
        self.assertEqual(payload["wind_power"], 1.0)
        self.assertEqual(payload["load_power"], 9.0)

