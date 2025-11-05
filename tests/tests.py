import unittest
import sys
import os

sys.path.append(os.path.dirname(__file__))

from main import LEDControllerApp

class TestLEDControllerEvents(unittest.TestCase):

    def setUp(self):
        """
        Create a QApplication instance before each test
        """
        if not hasattr(self, "app") or not LEDControllerApp.instance():
            self.app = LEDControllerApp(sys.argv)

    def test_toggle_unit(self):
        expected_result = [11, 0, 0]
        actual_result = self.app.toggle_all_leds(checked=True)
        self.assertEqual(expected_result, actual_result)


if __name__ == '__main__':
    unittest.main()