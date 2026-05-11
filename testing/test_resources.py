from __future__ import annotations

import pytest

from teensy_io import TeensyIO
from teensy_io.protocol.commands import CommandId, PacketType
from teensy_io.protocol.packet import Packet
from testing.fakes import ScriptedTransport, command_payload


def test_digital_output_configure_write_and_input_read_payloads() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.pin("led").configure_output(physical_pin=13, initial=True)
    io.pin("led").write(False)
    io.pin("switch").configure_input(physical_pin=7, pull="up", debounce_us=50)
    assert io.pin("switch").read() is True

    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_DIGITAL_OUTPUT, b"\x0d\x01"),
        (CommandId.DIGITAL_WRITE, b"\x0d\x00"),
        (CommandId.CONFIG_DIGITAL_INPUT, b"\x07\x01"),
        (CommandId.DIGITAL_READ, b"\x07"),
    ]


@pytest.mark.parametrize(
    ("pull", "code"),
    [
        ("floating", 0),
        ("none", 0),
        ("up", 1),
        ("pullup", 1),
        ("down", 2),
        ("pulldown", 2),
    ],
)
def test_input_pull_modes(pull: str, code: int) -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.pin("input").configure_input(physical_pin=2, pull=pull)

    assert command_payload(transport.requests[-1]) == bytes([2, code])


def test_invalid_pull_mode_raises_key_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(KeyError):
        io.pin("input").configure_input(physical_pin=2, pull="sideways")


def test_unconfigured_pin_read_write_raise_runtime_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(RuntimeError):
        io.pin("x").read()
    with pytest.raises(RuntimeError):
        io.pin("x").write(True)


def test_pwm_configure_write_disable_payloads() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.pwm("out").configure(physical_pin=3, frequency=20_000, initial_duty=0.5)
    io.pwm("out").write(1.0)
    io.pwm("out").disable()

    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_PWM, b"\x03\x20\x4e\x00\x00\x80"),
        (CommandId.PWM_WRITE, b"\x03\xff"),
        (CommandId.PWM_DISABLE, b"\x03"),
    ]


@pytest.mark.parametrize("duty", [-0.01, 1.01])
def test_pwm_duty_must_be_normalized(duty: float) -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(ValueError):
        io.pwm("out").configure(physical_pin=3, initial_duty=duty)


def test_unconfigured_pwm_write_disable_raise_runtime_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(RuntimeError):
        io.pwm("out").write(0.1)
    with pytest.raises(RuntimeError):
        io.pwm("out").disable()


def test_counter_attach_read_delta_frequency_and_reset() -> None:
    counts = iter([10, 17, 25])

    def handler(request):
        command = CommandId(request.payload[0])
        if command == CommandId.COUNTER_READ:
            return Packet(PacketType.DATA, request.seq, next(counts).to_bytes(4, "little", signed=True))
        if command == CommandId.COUNTER_FREQUENCY:
            return Packet(PacketType.DATA, request.seq, (12500).to_bytes(4, "little"))
        return Packet(PacketType.ACK, request.seq, b"\x00")

    transport = ScriptedTransport(handler)
    io = TeensyIO(transport=transport).connect()
    io.pin("pulse").configure_input(physical_pin=7, pull="up")
    counter = io.counter("ticks").attach(pin="pulse", edge="both")

    assert counter.read() == 10
    assert counter.delta() == 17
    assert counter.delta() == 8
    assert counter.frequency(window_ms=100) == 12.5
    counter.reset()

    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_DIGITAL_INPUT, b"\x07\x01"),
        (CommandId.CONFIG_COUNTER, b"\x00\x07\x02"),
        (CommandId.COUNTER_READ, b"\x00"),
        (CommandId.COUNTER_READ, b"\x00"),
        (CommandId.COUNTER_READ, b"\x00"),
        (CommandId.COUNTER_FREQUENCY, b"\x00"),
        (CommandId.COUNTER_RESET, b"\x00"),
    ]


def test_counter_attach_accepts_physical_pin_directly() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.counter("ticks").attach(pin=12, edge="falling")

    assert command_payload(transport.requests[-1]) == b"\x00\x0c\x01"


def test_counter_requires_configured_named_pin() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(RuntimeError):
        io.counter("ticks").attach(pin="missing")


def test_counter_invalid_edge_raises_key_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(KeyError):
        io.counter("ticks").attach(pin=7, edge="middle")


def test_counter_read_before_attach_raises_runtime_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(RuntimeError):
        io.counter("ticks").read()


def test_reserved_feature_methods_raise_not_implemented() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(NotImplementedError):
        io.subscribe("x")
    with pytest.raises(NotImplementedError):
        io.read_telemetry()
    with pytest.raises(NotImplementedError):
        io.on_telemetry(lambda frame: None)
    with pytest.raises(NotImplementedError):
        io.pin("x").on_edge("rising", lambda event: None)
    with pytest.raises(NotImplementedError):
        io.analog("a").configure(14)
    with pytest.raises(NotImplementedError):
        io.encoder("e").attach(1, 2)
