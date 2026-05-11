# Testing Suite

This folder contains the project-level test suite for `teensy-io`.

The suite is designed to be hardware-independent and not biased toward only happy-path behavior:

- Protocol tests cover valid frames, malformed frames, noise, CRC failures, size boundaries, and fragmented input.
- Client tests assert the actual command packets sent over the transport, not just the return values.
- Resource tests cover configured and unconfigured states, invalid values, and error mapping.
- Config tests use temporary files and validate both supported and unsupported shapes.

Hardware-in-the-loop tests for a real Teensy should be added later under `testing/hardware/` and skipped by default unless a serial port is explicitly provided.

## Run from a clean checkout

```bash
./testing/run.sh
```

The script creates a disposable virtual environment in `/tmp`, installs the Python package in editable mode with dev dependencies, and runs pytest from the repository root.

## Manual setup

```bash
python3 -m venv /tmp/teensy-io-test-venv
/tmp/teensy-io-test-venv/bin/python -m pip install -r testing/requirements.txt
/tmp/teensy-io-test-venv/bin/python -m pytest
```
