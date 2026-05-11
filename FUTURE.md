# Future: Daemon and IPC

The current production direction is:

```txt
ROS2 nodes / Jetson Python app
        |
        v
teensy_io ROS2 bridge node
        |
        v
TeensyIO Python client
        |
        v
/dev/ttyACM0
```

This keeps one process as the serial-port owner without adding a second custom IPC protocol yet.

## Why daemon mode still matters later

Daemon mode becomes useful when non-ROS clients need shared access at the same time as ROS2:

- dashboard
- logger
- command-line tools
- calibration tools
- non-ROS Python apps
- watchdog supervisor

The invariant should remain:

```txt
Only one process owns the Teensy serial port.
```

In daemon mode, that owner would be:

```txt
teensy-io-daemon
```

All other tools would talk to the daemon over a local Unix domain socket.

## Proposed daemon shape

```txt
Python apps / ROS2 bridge / CLI tools
        |
        v
teensy_io daemon client
        |
        v
Unix socket
        |
        v
teensy-io-daemon
        |
        v
Teensy serial protocol
```

## IPC protocol

Use newline-delimited JSON first:

```json
{"seq":1,"op":"digital_write","name":"led","value":true}
{"seq":2,"op":"counter_read","name":"wheel_ticks"}
{"seq":3,"op":"emergency_stop"}
```

Responses:

```json
{"seq":1,"ok":true,"result":null}
{"seq":2,"ok":true,"result":1234}
{"seq":3,"ok":false,"error":"EmergencyStopActiveError","message":"emergency stop is active"}
```

Telemetry and events can be pushed as server-originated frames:

```json
{"type":"telemetry","kind":"counter","name":"wheel_ticks","value":1234}
{"type":"event","kind":"digital","name":"limit_switch","value":1,"timestamp_us":12345678}
```

## Systemd service

Later service file:

```ini
[Unit]
Description=Teensy IO daemon
After=dev-ttyACM0.device

[Service]
ExecStart=/usr/bin/teensy-io-daemon --config /etc/teensy-io/io.yaml
Restart=always
RestartSec=1
User=robot
Group=dialout

[Install]
WantedBy=multi-user.target
```

## When to build it

Build daemon mode after these are stable:

- firmware analog reads
- firmware encoder reads
- telemetry/event streaming
- ROS2 bridge command and telemetry shape
- error handling contract
- reconnect behavior after USB disconnect

Until then, keep the ROS2 bridge as the singleton owner.
