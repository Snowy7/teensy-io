from __future__ import annotations

import textwrap

import pytest

from teensy_io import InvalidModeError, TeensyIO
from teensy_io.config.loader import load_config
from teensy_io.protocol.commands import CommandId
from testing.fakes import ScriptedTransport, command_payload


def test_load_config_rejects_non_mapping_root(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(path)


def test_from_config_and_configure_all(tmp_path) -> None:
    path = tmp_path / "io.yaml"
    path.write_text(
        textwrap.dedent(
            """
            port: /dev/ttyACM0
            baudrate: 1000000
            pins:
              status_led:
                type: digital_output
                physical_pin: 13
                initial: false
              motor_pwm:
                type: pwm
                physical_pin: 3
                frequency: 20000
                initial_duty: 0.25
            inputs:
              wheel_pulse:
                physical_pin: 7
                pull: up
                debounce_us: 50
            counters:
              wheel_ticks:
                input: wheel_pulse
                edge: rising
            encoders:
              steering:
                pin_a: 5
                pin_b: 6
                mode: x4
            """
        ),
        encoding="utf-8",
    )
    transport = ScriptedTransport()
    io = TeensyIO.from_config(path)
    io.transport = transport
    io.connect()

    io.configure_all()

    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_DIGITAL_OUTPUT, b"\x0d\x00"),
        (CommandId.CONFIG_PWM, b"\x03\x20\x4e\x00\x00\x40"),
        (CommandId.CONFIG_DIGITAL_INPUT, b"\x07\x01"),
        (CommandId.CONFIG_COUNTER, b"\x00\x07\x00"),
        (CommandId.CONFIG_ENCODER, b"\x00\x05\x06\x04"),
    ]


def test_load_config_method_replaces_current_config(tmp_path) -> None:
    path = tmp_path / "io.yaml"
    path.write_text(
        textwrap.dedent(
            """
            pins:
              led:
                type: digital_output
                physical_pin: 13
            """
        ),
        encoding="utf-8",
    )
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.load_config(path)
    io.configure_all()

    assert transport.requests[-1].payload[0] == CommandId.CONFIG_DIGITAL_OUTPUT


def test_configure_all_rejects_unknown_pin_type() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()
    io._config = {"pins": {"bad": {"type": "motor", "physical_pin": 1}}}

    with pytest.raises(InvalidModeError):
        io.configure_all()
