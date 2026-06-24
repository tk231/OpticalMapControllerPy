# Python Optical Mapping LED Controller

List of commands for the controller unit:

| Command     | Task description                          |
|-------------|-------------------------------------------|
| [255, 0, 0] | Reset unit                                |
| [3, 0, 0]   | LED 1 On/Off                              |
| [5, 0, 0]   | LED 2 On/Off                              |
| [7, 0, 0]   | LED 3 On/Off                              |
| [9, 0, 0]   | LED 4 On/Off                              |
| [10, 0, 0]  | Turn light pulsing on (not yet tested)    |
| [11, 0, 0]  | LED power source on button                |
| [12, 0, 0]  | LED power source off button               |
| [13, 0, 0]  | stop pulsing (not yet tested)             |
| [14, 0, 0]  | turn light triggering on (not yet tested) |
| [15, 0, 0]  | stop triggering (not yet tested)          |

For setting LED voltage, there is an issue of sending a 12-bit number using only 6 bits. Ergo, the 12-bit number is divided into two parts, `num1` and `num2`.

| Command         | Task description                                                  |
|-----------------|-------------------------------------------------------------------|
| [2, num1, num2] | LED 1 set voltage (x4096/10) num2 upper 8 bits, num1 lower 8 bits |
| [4, num1, num2] | LED 2 set voltage (x4096/10) num2 upper 8 bits, num1 lower 8 bits |
| [6, num1, num2] | LED 3 set voltage (x4096/10) num2 upper 8 bits, num1 lower 8 bits |
| [8, num1, num2] | LED 4 set voltage (x4096/10) num2 upper 8 bits, num1 lower 8 bits |


