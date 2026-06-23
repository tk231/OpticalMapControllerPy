import math
import sys
import unittest
from unittest.mock import MagicMock, patch, call

import PyQt6.QtWidgets

# A single QApplication must exist for the lifetime of the test suite
_qapp = PyQt6.QtWidgets.QApplication.instance() or PyQt6.QtWidgets.QApplication(sys.argv)

from main import LEDControllerApp


def make_window() -> LEDControllerApp:
    """
    Return a fresh LEDControllerApp with a mock serial port already
    injected, so every test starts in a 'connected' state without
    real hardware.
    """
    window = LEDControllerApp()
    mock_serial = MagicMock()
    mock_serial.is_open = True
    window.serial = mock_serial
    return window


def written_bytes(window: LEDControllerApp) -> list[list[int]]:
    """
    Return all byte sequences that were passed to serial.write(), each converted to a plain list for easy assertEqual
    comparisons.
    """
    return [list(c.args[0]) for c in window.serial.write.call_args_list]


# ---------------------------------------------------------------------------
# Helper: expected voltage bytes for a given LED id and voltage
# ---------------------------------------------------------------------------
def expected_voltage_bytes(led_id: int, voltage: float) -> list[int]:
    num  = round(4096 * voltage / 10)
    num2 = math.floor(num / 256)
    num1 = num - (num2 * 256)
    return [led_id * 2, num1, num2]


# ===========================================================================
# Unit ON / OFF
# ===========================================================================
class TestToggleUnit(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def test_unit_on_sends_correct_bytes(self):
        self.window.toggle_unit(checked=True)
        self.assertIn([11, 0, 0], written_bytes(self.window))

    def test_unit_off_sends_correct_bytes(self):
        self.window.toggle_unit(checked=False)
        self.assertIn([12, 0, 0], written_bytes(self.window))

    def test_unit_on_does_nothing_when_disconnected(self):
        self.window.serial = None
        self.window.toggle_unit(checked=True)
        # No serial object — nothing should have been written
        # (MagicMock was replaced with None, so we just check no exception)

    def test_unit_on_sets_button_text(self):
        self.window.toggle_unit(checked=True)
        self.assertEqual(self.window.master_button.text(), "Unit ON")

    def test_unit_off_sets_button_text(self):
        self.window.toggle_unit(checked=False)
        self.assertEqual(self.window.master_button.text(), "Unit OFF")


# ===========================================================================
# LED toggle (ON / OFF state)
# ===========================================================================
class TestToggleLEDState(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def _toggle_command(self, led_id: int) -> list[int]:
        return [(2 * led_id) + 1, 0, 0]

    def test_led1_toggle_sends_correct_bytes(self):
        self.window.toggle_led_state(self.window.led_groups[0])
        self.assertIn(self._toggle_command(1), written_bytes(self.window))

    def test_led2_toggle_sends_correct_bytes(self):
        self.window.toggle_led_state(self.window.led_groups[1])
        self.assertIn(self._toggle_command(2), written_bytes(self.window))

    def test_led3_toggle_sends_correct_bytes(self):
        self.window.toggle_led_state(self.window.led_groups[2])
        self.assertIn(self._toggle_command(3), written_bytes(self.window))

    def test_led4_toggle_sends_correct_bytes(self):
        self.window.toggle_led_state(self.window.led_groups[3])
        self.assertIn(self._toggle_command(4), written_bytes(self.window))

    def test_toggle_does_nothing_when_disconnected(self):
        self.window.serial = None
        # Should return silently without raising
        self.window.toggle_led_state(self.window.led_groups[0])

    def test_all_four_led_toggle_commands_are_distinct(self):
        """Each LED must produce a unique first byte."""
        commands = [self._toggle_command(i) for i in range(1, 5)]
        first_bytes = [c[0] for c in commands]
        self.assertEqual(len(set(first_bytes)), 4)


# ===========================================================================
# LED voltage
# ===========================================================================
class TestSetLEDVoltage(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def _set_voltage(self, led_index: int, voltage: float):
        group = self.window.led_groups[led_index]
        group.voltage_spin.setValue(voltage)
        self.window.set_led_voltage(group)

    def test_led1_zero_volts(self):
        self._set_voltage(0, 0.0)
        self.assertIn(expected_voltage_bytes(1, 0.0), written_bytes(self.window))

    def test_led1_max_volts(self):
        self._set_voltage(0, 4.5)
        self.assertIn(expected_voltage_bytes(1, 4.5), written_bytes(self.window))

    def test_led2_midpoint_volts(self):
        self._set_voltage(1, 2.5)
        self.assertIn(expected_voltage_bytes(2, 2.5), written_bytes(self.window))

    def test_led3_one_volt(self):
        self._set_voltage(2, 1.0)
        self.assertIn(expected_voltage_bytes(3, 1.0), written_bytes(self.window))

    def test_led4_voltage_uses_correct_command_byte(self):
        """First byte of a voltage command must be led_id * 2."""
        self._set_voltage(3, 1.0)
        sent = written_bytes(self.window)
        self.assertTrue(any(cmd[0] == 4 * 2 for cmd in sent))

    def test_voltage_does_nothing_when_disconnected(self):
        self.window.serial = None
        # Should show a warning dialog, not crash — patch it out
        with patch.object(PyQt6.QtWidgets.QMessageBox, 'warning'):
            self.window.set_led_voltage(self.window.led_groups[0])

    def test_voltage_encoding_byte_values_in_range(self):
        """Both data bytes must stay within 0–255."""
        for voltage in [0.0, 1.0, 2.25, 3.3, 4.5]:
            self._set_voltage(0, voltage)
        for cmd in written_bytes(self.window):
            self.assertGreaterEqual(cmd[1], 0)
            self.assertLessEqual(cmd[1], 255)
            self.assertGreaterEqual(cmd[2], 0)
            self.assertLessEqual(cmd[2], 255)


# ===========================================================================
# Toggle ALL LEDs
# ===========================================================================
class TestToggleAllLEDs(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def _expected_toggle(self, led_id: int) -> list[int]:
        return [(2 * led_id) + 1, 0, 0]

    def test_all_leds_on_sends_toggle_for_each_led(self):
        self.window.toggle_all_leds(checked=True)
        sent = written_bytes(self.window)
        for led_id in range(1, 5):
            self.assertIn(self._expected_toggle(led_id), sent,
                          msg=f"Toggle command for LED {led_id} not found")

    def test_all_leds_off_sends_toggle_for_each_led(self):
        # First turn them all on so they are in the checked state
        for group in self.window.led_groups:
            group.toggle_button.setChecked(True)
        self.window.serial.write.reset_mock()

        self.window.toggle_all_leds(checked=False)
        sent = written_bytes(self.window)
        for led_id in range(1, 5):
            self.assertIn(self._expected_toggle(led_id), sent,
                          msg=f"Toggle command for LED {led_id} not found")

    def test_all_leds_on_does_nothing_when_disconnected(self):
        self.window.serial = None
        with patch.object(PyQt6.QtWidgets.QMessageBox, 'warning'):
            self.window.toggle_all_leds(checked=True)


# ===========================================================================
# Serial reset
# ===========================================================================
class TestResetSerial(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def test_reset_sends_correct_bytes(self):
        self.window.reset_serial()
        self.assertIn([255, 0, 0], written_bytes(self.window))

    def test_reset_does_nothing_when_disconnected(self):
        self.window.serial = None
        self.window.reset_serial()  # Must not raise


# ===========================================================================
# serial_write error handling
# ===========================================================================
class TestSerialWriteErrorHandling(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    def _raise(self, exc):
        """Configure mock serial.write to raise exc."""
        self.window.serial.write.side_effect = exc

    def test_serial_exception_shows_popup_and_returns_false(self):
        self._raise(Exception("port error"))
        with patch.object(PyQt6.QtWidgets.QMessageBox, 'critical') as mock_crit:
            result = self.window.serial_write(bytes([1, 0, 0]))
        self.assertFalse(result)
        mock_crit.assert_called_once()

    def test_os_error_shows_popup_and_returns_false(self):
        self._raise(OSError(5, "I/O error"))
        with patch.object(PyQt6.QtWidgets.QMessageBox, 'critical') as mock_crit:
            result = self.window.serial_write(bytes([1, 0, 0]))
        self.assertFalse(result)
        mock_crit.assert_called_once()

    def test_successful_write_returns_true(self):
        self.window.serial.write.side_effect = None
        result = self.window.serial_write(bytes([11, 0, 0]))
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)