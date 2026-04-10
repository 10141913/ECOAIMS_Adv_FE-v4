import unittest
from ecoaims_frontend.components.gauges import create_gauge_figure
from ecoaims_frontend.services.data_service import update_trend_data

class TestComponents(unittest.TestCase):
    def test_gauge_figure_creation(self):
        """Test if gauge figure is created correctly"""
        fig = create_gauge_figure(50, 100)
        self.assertIsNotNone(fig)
        self.assertEqual(fig.data[0].value, 50)
        
    def test_gauge_figure_invalid_input(self):
        """Test gauge figure handles invalid input gracefully (clamping)"""
        fig = create_gauge_figure(-10, 100)
        self.assertEqual(fig.data[0].value, 0)

    def test_trend_data_update(self):
        """Test trend data list update logic"""
        data = [{'time': '08:00', 'consumption': 10, 'renewable_supply': 5}]
        updated = update_trend_data(data, 20, 8, '09:00', max_points=2)
        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[-1]['consumption'], 20)
        
        # Test max points limit
        updated = update_trend_data(updated, 30, 9, '10:00', max_points=2)
        self.assertEqual(len(updated), 2)
        self.assertEqual(updated[0]['time'], '09:00')

if __name__ == '__main__':
    unittest.main()
