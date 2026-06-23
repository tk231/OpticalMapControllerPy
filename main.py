import math
import serial
import serial.tools.list_ports
import PyQt6.QtCore
import PyQt6.QtWidgets

class LEDControllerApp(PyQt6.QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IEKM LED Controller")
        self.serial = None

        # === MAIN LAYOUT ===
        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)

        # --- COM PORT SELECTION ---
        port_layout = PyQt6.QtWidgets.QHBoxLayout()
        port_layout.addWidget(PyQt6.QtWidgets.QLabel("COM Port: "))
        self.port_combo = PyQt6.QtWidgets.QComboBox()

        self.refresh_button = PyQt6.QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.connect_toggle = PyQt6.QtWidgets.QPushButton("Connect")
        self.connect_toggle.setCheckable(True)
        self.connect_toggle.setStyleSheet("background-color: red; color: white;")
        self.connect_toggle.toggled.connect(self.toggle_connection)

        self.reset_button = PyQt6.QtWidgets.QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_serial)

        for w in [self.port_combo, self.refresh_button, self.connect_toggle, self.reset_button]:
            port_layout.addWidget(w)

        main_layout.addLayout(port_layout)

        # --- MASTER UNIT ON/OFF BUTTON ---
        self.master_button = PyQt6.QtWidgets.QPushButton("Unit OFF")
        self.master_button.setCheckable(True)
        self.master_button.setStyleSheet("background-color: red; color: white;")
        self.master_button.toggled.connect(self.toggle_unit)

        main_layout.addWidget(self.master_button)

        # --- LED CONTROLS ---
        self.led_groups = []
        for i in range(1, 5):
            group = self.create_led_group(i)
            self.led_groups.append(group)
            main_layout.addWidget(group)

        # Disable all LED controls initially
        self.set_led_controls_enabled(False)

        # --- All LEDs On/Off Button ---
        self.all_led_button = PyQt6.QtWidgets.QPushButton("All LEDs OFF")
        self.all_led_button.setCheckable(True)
        self.all_led_button.setStyleSheet("background-color: red; color: white;")
        self.all_led_button.toggled.connect(self.toggle_all_leds)

        main_layout.addWidget(self.all_led_button)

        # --- STATUS BAR ---
        self.status_label = PyQt6.QtWidgets.QLabel("Disconnected")
        main_layout.addWidget(self.status_label)

        # populate COM ports at startup
        self.refresh_ports()

    # ==================== Enable LED Controls ====================
    def set_led_controls_enabled(self, enabled: bool):
        """
        Enable or disable all LED control buttons and spinboxes.
        """
        for group in self.led_groups:
            group.voltage_spin.setEnabled(enabled)
            group.toggle_button.setEnabled(enabled)

    # ==================== GUI ELEMENT CREATION ====================
    def create_led_group(self, led_id: int):
        """
        Create a group box with voltage and ON/OFF control for one LED.
        """
        group = PyQt6.QtWidgets.QGroupBox(f"LED {led_id}")
        layout = PyQt6.QtWidgets.QHBoxLayout()

        voltage_spin = PyQt6.QtWidgets.QDoubleSpinBox()
        voltage_spin.setRange(0, 4.5)
        voltage_spin.setSuffix(" V")

        # --- New Set PushButton ---
        set_voltage_button = PyQt6.QtWidgets.QPushButton("Set Voltage")

        # --- Connect Set Voltage PushButton ---
        set_voltage_button.clicked.connect(lambda _, g=group: self.set_led_voltage(g))

        # --- Toggle PushButton instead of Checkbox ---
        toggle_button = PyQt6.QtWidgets.QPushButton("OFF")
        toggle_button.setCheckable(True)
        toggle_button.setStyleSheet("background-color: red; color: white;")

        # Connect button style updates
        toggle_button.toggled.connect(lambda checked, b=toggle_button: self.update_button_style(b, checked))

        # ✅ Connect toggle to toggle_led_state
        toggle_button.toggled.connect(lambda _, g=group: self.toggle_led_state(g))

        # --- Layout arrangement ---
        layout.addWidget(PyQt6.QtWidgets.QLabel("Voltage:"))
        layout.addWidget(voltage_spin)
        layout.addWidget(set_voltage_button)
        layout.addWidget(toggle_button)

        group.setLayout(layout)

        # store widgets for reference
        group.led_id = led_id
        group.voltage_spin = voltage_spin
        group.set_voltage_button = set_voltage_button
        group.toggle_button = toggle_button
        return group

    # ==================== GUI BEHAVIOR ====================
    def update_button_style(self, button, checked):
        if checked:
            button.setText("ON")
            button.setStyleSheet("background-color: green; color: white;")
        else:
            button.setText("OFF")
            button.setStyleSheet("background-color: red; color: white;")

    # ==================== SERIAL WRITE HELPER ====================
    def serial_write(self, data: bytes) -> bool:
        """
        Write bytes to the serial port with full error handling.
        Shows a popup with the error type and message on failure, then disconnects so the UI stays in sync with reality.
        Returns True on success, False on failure.
        """
        try:
            self.serial.write(data)
            return True

        except serial.SerialException as e:
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                f"Serial Error [{type(e).__name__}]",
                f"Failed to write to serial port.\nError: {e}\nThe port will be disconnected."
            )

        except OSError as e:
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                f"OS Error [{type(e).__name__}]",
                f"OS-level failure while writing to serial port.\n\nError: {e}\n\nThe port will be disconnected."
            )

        except Exception as e:
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                f"Unexpected Error [{type(e).__name__}]",
                f"An unexpected error occurred while writing to the serial port.\n\nError: {e}\n\nThe port will be disconnected."
            )

        # Any exception reaches here — force a clean disconnect
        self.connect_toggle.setChecked(False)
        return False

    # ==================== SERIAL PORT HANDLING ====================
    def refresh_ports(self):
        """
        Scan available COM ports and update dropdown.
        """
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} ({port.description})")

    def toggle_connection(self, checked: bool):
        """
        Toggle serial connection ON/OFF with a single button.
        """
        if checked:
            # === Try to connect ===
            if self.port_combo.count() == 0:
                PyQt6.QtWidgets.QMessageBox.warning(None, "Warning", "No COM ports available")
                self.connect_toggle.setChecked(False)
                return

            port = self.port_combo.currentText().split()[0]

            try:
                self.serial = serial.Serial(port, baudrate=115200, timeout=1)
                self.status_label.setText(f"Connected to {port}")
                self.connect_toggle.setText("Disconnect")
                self.connect_toggle.setStyleSheet("background-color: green; color: white;")
                self.set_led_controls_enabled(True)

            except Exception as e:
                PyQt6.QtWidgets.QMessageBox.critical(None, "Error", f"Could not connect: {e}")
                self.status_label.setText("Disconnected")
                self.connect_toggle.setChecked(False)
                self.connect_toggle.setStyleSheet("background-color: red; color: white;")
                self.set_led_controls_enabled(False)

        else:
            # === Disconnect ===
            if self.serial and self.serial.is_open:
                try:
                    self.serial.close()
                except Exception as e:
                    PyQt6.QtWidgets.QMessageBox.warning(None, "Warning", f"Error closing port: {e}")

            self.serial = None
            self.status_label.setText("Disconnected")
            self.connect_toggle.setText("Connect")
            self.connect_toggle.setStyleSheet("background-color: red; color: white;")
            self.set_led_controls_enabled(False)
            self.master_button.setChecked(False)
            self.master_button.setText("Unit OFF")
            self.master_button.setStyleSheet("background-color: red; color: white;")

    def reset_serial(self):
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(bytes([255, 0, 0]))
                self.status_label.setText(f"Serial reset")
            except Exception as e:
                PyQt6.QtWidgets.QMessageBox.warning(None, "Warning", f"Error resetting: {e}")

    # ==================== COMMAND HANDLING ====================
    def toggle_unit(self, checked: bool):
        if not self.serial or not self.serial.is_open:
            PyQt6.QtWidgets.QMessageBox.warning(None, "Warning", "Not connected")
            self.master_button.setChecked(False)
            return

        if checked:
            self.master_button.setText("Unit ON")
            self.master_button.setStyleSheet("background-color: green; color: white;")
            if not self.serial.write(bytes([11, 0, 0])):  # Command to turn unit on
                self.master_button.setChecked(False)

        else:
            self.master_button.setText("Unit OFF")
            self.master_button.setStyleSheet("background-color: red; color: white;")
            self.serial.write(bytes([12, 0, 0]))  # Command to turn unit off

    def set_led_voltage(self, led_group):
        """
        Send LED updates only for LEDs that are ON.
        """
        if not self.serial or not self.serial.is_open:
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "Serial port not open. Cannot send voltage command."
            )
            return

        # Get LED params
        led_id = led_group.led_id
        voltage = led_group.voltage_spin.value()

        # Convert voltage to useable serial commands
        num = round(4096 * voltage / 10)
        num2 = math.floor(num / 256)
        num1 = num - (num2 * 256)

        self.serial.write(bytes([led_id * 2, num1, num2]))

    def toggle_led_state(self, led_group):
        """
        Send serial command to turn LED on or off
        """
        if not self.serial or not self.serial.is_open:
            return

        # Get LED params
        led_id = led_group.led_id

        self.serial.write(bytes([(2 * led_id) + 1, 0, 0]))

    def toggle_all_leds(self, checked):
        """
        Toggle all LEDs ON or OFF.
        """
        if not self.serial or not self.serial.is_open:
            PyQt6.QtWidgets.QMessageBox.warning(None, "Warning", "Not connected")
            self.all_led_button.setChecked(False)
            return

        # Update button text and color
        if checked:
            self.all_led_button.setText("All LEDs ON")
            self.all_led_button.setStyleSheet("background-color: green; color: white;")

            # Turn all individual LEDs ON
            for group in self.led_groups:
                if not group.toggle_button.isChecked():
                    group.toggle_button.setChecked(True)  # triggers toggle_led_state automatically

        else:
            self.all_led_button.setText("All LEDs OFF")
            self.all_led_button.setStyleSheet("background-color: red; color: white;")

            # Turn all individual LEDs OFF
            for group in self.led_groups:
                if group.toggle_button.isChecked():
                    group.toggle_button.setChecked(False)  # triggers toggle_led_state automatically

def main():
    import sys

    app = PyQt6.QtWidgets.QApplication(sys.argv)
    window = LEDControllerApp()
    window.resize(400, 300)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()