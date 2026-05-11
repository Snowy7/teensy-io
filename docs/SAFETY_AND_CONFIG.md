# Safety and Configuration

## Emergency Stop

`emergency_stop()` is a software safety command sent from the host to the Teensy.

When active, firmware immediately drives configured PWM outputs to zero and rejects output commands that could energize hardware. The stop remains latched until `clear_emergency_stop()` is called.

Typical use:

```python
io.emergency_stop()

# Later, after the physical system is safe:
io.clear_emergency_stop()
```

The heartbeat/watchdog path uses the same safe-output behavior. If heartbeats stop for the watchdog interval, firmware enters the safe state.

This is not a replacement for a physical emergency stop circuit. Use it as a software layer in addition to hardwired power removal where people or expensive equipment are at risk.

## Full Configuration

Configuration is YAML and maps names to generic IO resources. Application meaning stays outside this library.

```yaml
port: /dev/ttyACM0
baudrate: 1000000
timeout: 1.0
heartbeat_hz: 20
watchdog_timeout_ms: 300

pins:
  status_led:
    type: digital_output
    physical_pin: 13
    initial: false

  enable_line:
    type: digital_output
    physical_pin: 8
    initial: false

  limit_switch:
    type: digital_input
    physical_pin: 7
    pull: up
    debounce_us: 500

  motor_pwm:
    type: pwm
    physical_pin: 3
    frequency: 20000
    initial_duty: 0.0

  battery_adc:
    type: analog
    physical_pin: 14
    samples: 16

inputs:
  wheel_pulse:
    physical_pin: 6
    pull: up
    debounce_us: 50

counters:
  wheel_ticks:
    input: wheel_pulse
    edge: rising

encoders:
  steering_encoder:
    pin_a: 5
    pin_b: 6
    mode: x4
```

Supported digital pulls:

- `floating`
- `none`
- `up`
- `pullup`
- `down`
- `pulldown`

Supported counter edges:

- `rising`
- `falling`
- `both`

Supported encoder modes:

- `x1`
- `x2`
- `x4`

Analog values are returned as raw ADC values and normalized values from `0.0` to `1.0`. Scaling into volts, speed, angle, or any application meaning belongs in the application layer.
