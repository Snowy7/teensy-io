# teensy-io

Generic IO firmware for Teensy boards plus a Python client for host applications.

The library intentionally exposes hardware primitives only:

- Digital input and output
- PWM output
- Analog input
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
- Pulse counter configure/read/reset/frequency
- Quadrature encoder configure/read/reset
- Telemetry and edge event subscription frames
- Optional Jetson ROS2 bridge
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

The bridge is optional and expects ROS2 Python packages to be installed on the Jetson:

```bash
teensy-io-bridge --ros-args \
  -p port:=/dev/ttyACM0 \
  -p baudrate:=1000000 \
  -p config:=/path/to/io.yaml
```

It publishes JSON on:

- `teensy_io/telemetry`
- `teensy_io/events`
- `teensy_io/status`

It accepts JSON commands on:

- `teensy_io/commands`

Example command payload:

```json
{"op":"pwm_write","name":"motor_pwm","duty":0.25}
```

A systemd template for Jetson deployment is in:

```txt
deployment/systemd/teensy-io-bridge.service
```

Daemon/Unix socket IPC is intentionally deferred; see [FUTURE.md](FUTURE.md).

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
