import math
import time

from teensy_io import TeensyIO


PULSES_PER_REV = 20
WHEEL_DIAMETER_M = 0.5
WHEEL_CIRCUMFERENCE_M = math.pi * WHEEL_DIAMETER_M

io = TeensyIO("/dev/ttyACM0").connect()
try:
    io.pin("wheel_pulse").configure_input(physical_pin=7, pull="up", debounce_us=50)
    ticks = io.counter("wheel_ticks").attach(pin="wheel_pulse", edge="rising")

    while True:
        pulse_hz = ticks.frequency(window_ms=100)
        speed_mps = pulse_hz / PULSES_PER_REV * WHEEL_CIRCUMFERENCE_M
        print(f"{speed_mps * 3.6:.2f} km/h")
        time.sleep(0.1)
finally:
    io.close()
