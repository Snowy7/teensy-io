# teensy-io

Generic IO firmware for Teensy boards plus a Python client for host applications.

The library intentionally exposes hardware primitives only:

- Digital input and output
- PWM output
- Analog input
- I2C bus access
- External DAC output
- Pulse counters
- Quadrature encoders
- Batch writes
- Telemetry hooks
- Heartbeat/watchdog
- Emergency stop

Application-specific meaning, such as wheel speed, motor throttle, brakes, or steering, belongs in the user application above this library.

## Packages

```txt
teensy-io-firmware/  # Teensy firmware
teensy-io-python/    # Python client library
teensy-io-ros/       # ROS2 bridge and typed interfaces
```

## Current v1 scope

This scaffold implements the first reliable slice:

- Binary packet framing with CRC-16
- Sequence IDs
- ACK/NACK/DATA/ERROR response types
- Ping
- Board info
- Heartbeat
- Emergency stop and clear emergency stop
- Digital output configure/write
- Digital input configure/read
- PWM configure/write/disable
- Analog configure/read
- I2C bus configure/read/write
- External I2C DAC configure/write
- Pulse counter configure/read/reset/frequency
- Quadrature encoder configure/read/reset
- Telemetry and edge event subscription frames
- Jetson ROS2 bridge with typed messages/services
- Python batching API
- YAML config loader

## Python quick start

```python
from teensy_io import TeensyIO

io = TeensyIO("/dev/ttyACM0", baudrate=1_000_000).connect()
print(io.ping())

io.pin("led").configure_output(physical_pin=13, initial=False)
io.pin("led").write(True)

io.close()
```

## High-rate batching

For frame-by-frame control loops, queue command writes and flush once per frame:

```python
io = TeensyIO(
    "/dev/ttyACM0",
    baudrate=1_000_000,
    flush_chunk_size=65_536,
    queue_max_bytes=None,
).connect()

with io.batch():
    io.pwm("motor").write(0.25)
    io.pin("enable").write(True)
```

The Python client stores queued packets in a thread-safe byte-counted queue and coalesces them into large serial writes on `flush()`. Set `queue_max_bytes` to a real number if you want explicit backpressure instead of an unbounded queue.

## Jetson ROS2 bridge

The production ROS2 bridge lives in the separate `teensy-io-ros/` package and uses dedicated `.msg` and `.srv` interfaces instead of JSON strings.

```bash
colcon build --packages-select teensy_io_ros
source install/setup.bash
ros2 launch teensy_io_ros bridge.launch.py
```

It publishes typed messages on:

- `teensy_io/telemetry`
- `teensy_io/events`
- `teensy_io/status`

It exposes typed services including:

- `teensy_io/digital_read`
- `teensy_io/digital_write`
- `teensy_io/pwm_write`
- `teensy_io/counter_read`
- `teensy_io/analog_read`
- `teensy_io/encoder_read`
- `teensy_io/i2c_write`
- `teensy_io/i2c_read`
- `teensy_io/dac_write`
- `teensy_io/subscribe`
- `teensy_io/emergency_stop`

A systemd template for Jetson deployment is in:

```txt
deployment/systemd/teensy-io-bridge.service
```

Daemon/Unix socket IPC is intentionally deferred; see [FUTURE.md](FUTURE.md).
Safety and full YAML configuration are documented in [docs/SAFETY_AND_CONFIG.md](docs/SAFETY_AND_CONFIG.md).

Production hardening currently includes interrupt-based pulse counters, interrupt-based quadrature encoder counting, host-side rolling-window counter frequency, bounded host telemetry/event queues with drop counters, config validation, and coalesced high-rate batch writes.

## Firmware build

The firmware package is set up for PlatformIO:

```bash
cd teensy-io-firmware
pio run
```

If PlatformIO was installed with `python3 -m pip install --user platformio` and `pio` is not on `PATH`, use:

```bash
/Users/islam/Library/Python/3.9/bin/pio run
```

The default board is `teensy41`. Adjust `platformio.ini` for a different Teensy model.

## Python development

```bash
cd teensy-io-python
python -m pip install -e ".[dev]"
pytest
```
