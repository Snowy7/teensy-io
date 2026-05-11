from __future__ import annotations

import pytest

from teensy_io import TeensyIO
from teensy_io.protocol.commands import CommandId, PacketType, ResourceKind
from teensy_io.protocol.frames import EdgeEvent
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


def test_analog_configure_and_read_payloads() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    analog = io.analog("battery").configure(physical_pin=14, samples=8)

    assert analog.read_raw() == 2048
    assert analog.read_normalized() == 0.5001
    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_ANALOG, b"\x0e\x08"),
        (CommandId.ANALOG_READ, b"\x0e"),
        (CommandId.ANALOG_READ, b"\x0e"),
    ]


def test_analog_requires_configuration_and_valid_sample_count() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(ValueError):
        io.analog("bad").configure(physical_pin=14, samples=0)
    with pytest.raises(RuntimeError):
        io.analog("battery").read_raw()


def test_encoder_attach_read_delta_and_reset() -> None:
    positions = iter([100, 130])

    def handler(request):
        command = CommandId(request.payload[0])
        if command == CommandId.ENCODER_READ:
            return Packet(PacketType.DATA, request.seq, next(positions).to_bytes(4, "little", signed=True))
        return Packet(PacketType.ACK, request.seq, b"\x00")

    transport = ScriptedTransport(handler)
    io = TeensyIO(transport=transport).connect()
    encoder = io.encoder("steering").attach(5, 6, mode="x4")

    assert encoder.read() == 100
    assert encoder.delta() == 130
    encoder.reset()
    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_ENCODER, b"\x00\x05\x06\x04"),
        (CommandId.ENCODER_READ, b"\x00"),
        (CommandId.ENCODER_READ, b"\x00"),
        (CommandId.ENCODER_RESET, b"\x00"),
    ]


def test_encoder_requires_attach_and_valid_mode() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(KeyError):
        io.encoder("bad").attach(1, 2, mode="x8")
    with pytest.raises(RuntimeError):
        io.encoder("steering").read()


def test_subscribe_unsubscribe_and_edge_callback() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()
    seen: list[EdgeEvent] = []

    io.pin("switch").configure_input(physical_pin=7, pull="up")
    io.subscribe("switch", rate_hz=10, on_change=True)
    io.unsubscribe("switch")
    io.pin("switch").on_edge("rising", seen.append)

    assert [(request.payload[0], command_payload(request)) for request in transport.requests] == [
        (CommandId.CONFIG_DIGITAL_INPUT, b"\x07\x01"),
        (CommandId.SUBSCRIBE, bytes([ResourceKind.DIGITAL, 7, 10, 0, 1])),
        (CommandId.UNSUBSCRIBE, bytes([ResourceKind.DIGITAL, 7])),
        (CommandId.SUBSCRIBE, bytes([ResourceKind.DIGITAL, 7, 0, 0, 3])),
    ]

    transport.queue(Packet(PacketType.EVENT, 0, bytes([ResourceKind.DIGITAL, 7]) + (1).to_bytes(4, "little", signed=True) + (55).to_bytes(4, "little")))
    event = io.read_event(timeout=0.1)

    assert event.value == 1
    assert seen == [event]


def test_read_telemetry_frame() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()
    seen = []
    io.on_telemetry(seen.append)
    transport.queue(Packet(PacketType.TELEMETRY, 0, bytes([ResourceKind.COUNTER, 2]) + (456).to_bytes(4, "little", signed=True)))

    frame = io.read_telemetry(timeout=0.1)

    assert frame.kind == ResourceKind.COUNTER
    assert frame.resource_id == 2
    assert frame.value == 456
    assert seen == [frame]


def test_unconfigured_resource_subscribe_raises_key_error() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    with pytest.raises(KeyError):
        io.subscribe("x")
