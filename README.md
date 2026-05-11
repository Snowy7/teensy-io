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
- Pulse counter configure/read/reset/frequency
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

## Firmware build

The firmware package is set up for PlatformIO:

```bash
cd teensy-io-firmware
pio run
```

The default board is `teensy41`. Adjust `platformio.ini` for a different Teensy model.

## Python development

```bash
cd teensy-io-python
python -m pip install -e ".[dev]"
pytest
```
