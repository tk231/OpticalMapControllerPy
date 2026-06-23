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


# ===========================================================================
# Pulse protocol
# ===========================================================================
class TestPulseProtocol(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    # --- start ---

    def test_start_pulse_sends_correct_bytes(self):
        self.window.start_pulse()
        self.assertIn([10, 0, 0], written_bytes(self.window))

    def test_start_pulse_sends_exactly_one_command(self):
        self.window.start_pulse()
        self.assertEqual(len(written_bytes(self.window)), 1)

    def test_start_pulse_command_byte_is_10(self):
        self.window.start_pulse()
        sent = written_bytes(self.window)
        self.assertTrue(any(cmd[0] == 10 for cmd in sent))

    def test_start_pulse_data_bytes_are_zero(self):
        self.window.start_pulse()
        cmd = written_bytes(self.window)[0]
        self.assertEqual(cmd[1], 0)
        self.assertEqual(cmd[2], 0)

    def test_start_pulse_does_nothing_when_disconnected(self):
        self.window.serial = None
        # Must return without raising
        self.window.start_pulse()

    def test_start_pulse_does_not_send_stop_command(self):
        self.window.start_pulse()
        self.assertNotIn([13, 0, 0], written_bytes(self.window))

    # --- stop ---

    def test_stop_pulse_sends_correct_bytes(self):
        self.window.stop_pulse()
        self.assertIn([13, 0, 0], written_bytes(self.window))

    def test_stop_pulse_sends_exactly_one_command(self):
        self.window.stop_pulse()
        self.assertEqual(len(written_bytes(self.window)), 1)

    def test_stop_pulse_command_byte_is_13(self):
        self.window.stop_pulse()
        sent = written_bytes(self.window)
        self.assertTrue(any(cmd[0] == 13 for cmd in sent))

    def test_stop_pulse_data_bytes_are_zero(self):
        self.window.stop_pulse()
        cmd = written_bytes(self.window)[0]
        self.assertEqual(cmd[1], 0)
        self.assertEqual(cmd[2], 0)

    def test_stop_pulse_does_nothing_when_disconnected(self):
        self.window.serial = None
        self.window.stop_pulse()

    def test_stop_pulse_does_not_send_start_command(self):
        self.window.stop_pulse()
        self.assertNotIn([10, 0, 0], written_bytes(self.window))

    # --- start/stop interaction ---

    def test_start_and_stop_pulse_send_distinct_commands(self):
        self.window.start_pulse()
        self.window.stop_pulse()
        sent = written_bytes(self.window)
        self.assertIn([10, 0, 0], sent)
        self.assertIn([13, 0, 0], sent)
        self.assertNotEqual(sent[0], sent[1])

    def test_start_pulse_command_differs_from_stop_pulse_command(self):
        start_cmd = [10, 0, 0]
        stop_cmd  = [13, 0, 0]
        self.assertNotEqual(start_cmd[0], stop_cmd[0])

    def test_start_then_stop_pulse_sends_two_commands_total(self):
        self.window.start_pulse()
        self.window.stop_pulse()
        self.assertEqual(len(written_bytes(self.window)), 2)

    def test_start_then_stop_pulse_order_is_preserved(self):
        self.window.start_pulse()
        self.window.stop_pulse()
        sent = written_bytes(self.window)
        self.assertEqual(sent[0], [10, 0, 0])
        self.assertEqual(sent[1], [13, 0, 0])


# ===========================================================================
# Triggered protocol
# ===========================================================================
class TestTriggeredProtocol(unittest.TestCase):

    def setUp(self):
        self.window = make_window()

    # --- start ---

    def test_start_triggered_sends_correct_bytes(self):
        self.window.start_triggered()
        self.assertIn([14, 0, 0], written_bytes(self.window))

    def test_start_triggered_sends_exactly_one_command(self):
        self.window.start_triggered()
        self.assertEqual(len(written_bytes(self.window)), 1)

    def test_start_triggered_command_byte_is_14(self):
        self.window.start_triggered()
        sent = written_bytes(self.window)
        self.assertTrue(any(cmd[0] == 14 for cmd in sent))

    def test_start_triggered_data_bytes_are_zero(self):
        self.window.start_triggered()
        cmd = written_bytes(self.window)[0]
        self.assertEqual(cmd[1], 0)
        self.assertEqual(cmd[2], 0)

    def test_start_triggered_does_nothing_when_disconnected(self):
        self.window.serial = None
        self.window.start_triggered()

    def test_start_triggered_does_not_send_stop_command(self):
        self.window.start_triggered()
        self.assertNotIn([15, 0, 0], written_bytes(self.window))

    # --- stop ---

    def test_stop_triggered_sends_correct_bytes(self):
        self.window.stop_triggered()
        self.assertIn([15, 0, 0], written_bytes(self.window))

    def test_stop_triggered_sends_exactly_one_command(self):
        self.window.stop_triggered()
        self.assertEqual(len(written_bytes(self.window)), 1)

    def test_stop_triggered_command_byte_is_15(self):
        self.window.stop_triggered()
        sent = written_bytes(self.window)
        self.assertTrue(any(cmd[0] == 15 for cmd in sent))

    def test_stop_triggered_data_bytes_are_zero(self):
        self.window.stop_triggered()
        cmd = written_bytes(self.window)[0]
        self.assertEqual(cmd[1], 0)
        self.assertEqual(cmd[2], 0)

    def test_stop_triggered_does_nothing_when_disconnected(self):
        self.window.serial = None
        self.window.stop_triggered()

    def test_stop_triggered_does_not_send_start_command(self):
        self.window.stop_triggered()
        self.assertNotIn([14, 0, 0], written_bytes(self.window))

    # --- start/stop interaction ---

    def test_start_and_stop_triggered_send_distinct_commands(self):
        self.window.start_triggered()
        self.window.stop_triggered()
        sent = written_bytes(self.window)
        self.assertIn([14, 0, 0], sent)
        self.assertIn([15, 0, 0], sent)
        self.assertNotEqual(sent[0], sent[1])

    def test_start_triggered_command_differs_from_stop_triggered_command(self):
        start_cmd = [14, 0, 0]
        stop_cmd  = [15, 0, 0]
        self.assertNotEqual(start_cmd[0], stop_cmd[0])

    def test_start_then_stop_triggered_sends_two_commands_total(self):
        self.window.start_triggered()
        self.window.stop_triggered()
        self.assertEqual(len(written_bytes(self.window)), 2)

    def test_start_then_stop_triggered_order_is_preserved(self):
        self.window.start_triggered()
        self.window.stop_triggered()
        sent = written_bytes(self.window)
        self.assertEqual(sent[0], [14, 0, 0])
        self.assertEqual(sent[1], [15, 0, 0])


# ===========================================================================
# Cross-protocol command uniqueness
# ===========================================================================
class TestProtocolCommandUniqueness(unittest.TestCase):
    """
    Sanity-check that the four protocol command bytes are all distinct,
    so a firmware mix-up would be caught by the individual tests above.
    """

    def test_all_four_protocol_command_bytes_are_unique(self):
        command_bytes = {
            "start_pulse":     10,
            "stop_pulse":      13,
            "start_triggered": 14,
            "stop_triggered":  15,
        }
        values = list(command_bytes.values())
        self.assertEqual(len(values), len(set(values)),
                         "Protocol command bytes must all be unique")

    def test_pulse_commands_differ_from_triggered_commands(self):
        pulse_cmds     = {10, 13}
        triggered_cmds = {14, 15}
        self.assertTrue(pulse_cmds.isdisjoint(triggered_cmds))

    def test_protocol_commands_do_not_overlap_with_led_toggle_commands(self):
        # LED toggle command bytes: 3, 5, 7, 9
        led_toggle_bytes = {(2 * i) + 1 for i in range(1, 5)}
        protocol_bytes   = {10, 13, 14, 15}
        self.assertTrue(led_toggle_bytes.isdisjoint(protocol_bytes))

    def test_protocol_commands_do_not_overlap_with_unit_power_commands(self):
        unit_power_bytes = {11, 12}
        protocol_bytes   = {10, 13, 14, 15}
        self.assertTrue(unit_power_bytes.isdisjoint(protocol_bytes))


if __name__ == '__main__':
    unittest.main(verbosity=2)