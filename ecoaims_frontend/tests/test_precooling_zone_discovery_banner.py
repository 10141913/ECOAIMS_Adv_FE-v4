import unittest

from ecoaims_frontend.callbacks.precooling_callbacks import _zone_discovery_banner


class TestPrecoolingZoneDiscoveryBanner(unittest.TestCase):
    def test_banner_hidden_when_no_error(self):
        children, style = _zone_discovery_banner(None, False)
        self.assertEqual(children, "")
        self.assertEqual(style.get("display"), "none")

    def test_banner_shown_when_error(self):
        children, style = _zone_discovery_banner("backend_timeout", True)
        self.assertNotEqual(children, "")
        self.assertNotEqual(style.get("display"), "none")

