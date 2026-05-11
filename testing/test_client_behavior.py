from __future__ import annotations

import threading
import time

import pytest

from teensy_io import (
    CommandRejectedError,
    EmergencyStopActiveError,
    InvalidModeError,
    InvalidPinError,
    QueueFullError,
    TeensyIO,
    TeensyIOTimeoutError,
)
from teensy_io.protocol.commands import CommandId, ErrorCode, PacketType
from teensy_io.protocol.errors import ProtocolError
from teensy_io.protocol.packet import Packet
from testing.fakes import ScriptedTransport, command_payload


def test_connect_and_close_open_transport() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport)

    assert io.connect() is io
    assert transport.is_open is True
    io.close()
    assert transport.is_open is False


def test_ping_and_get_info() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    assert io.ping() is True
    assert io.get_info() == {"digital_pins": 42, "counters": 8, "version": "0.1.0"}


def test_system_commands_send_expected_command_ids() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()

    io.heartbeat()
    io.emergency_stop()
    io.clear_emergency_stop()
    io.reset_config()

    assert [request.payload[0] for request in transport.requests] == [
        CommandId.HEARTBEAT,
        CommandId.EMERGENCY_STOP,
        CommandId.CLEAR_EMERGENCY_STOP,
        CommandId.RESET_CONFIG,
    ]


def test_timeout_when_transport_never_responds() -> None:
    io = TeensyIO(transport=ScriptedTransport(lambda request: None), timeout=0.01).connect()

    with pytest.raises(TeensyIOTimeoutError):
        io.ping()


@pytest.mark.parametrize(
    ("error_code", "expected_exception"),
    [
        (ErrorCode.INVALID_PIN, InvalidPinError),
        (ErrorCode.INVALID_MODE, InvalidModeError),
        (ErrorCode.EMERGENCY_STOP_ACTIVE, EmergencyStopActiveError),
        (ErrorCode.RESOURCE_UNAVAILABLE, CommandRejectedError),
    ],
)
def test_nack_error_mapping(error_code: ErrorCode, expected_exception: type[Exception]) -> None:
    def reject(request: Packet) -> Packet:
        return Packet(PacketType.NACK, request.seq, bytes([error_code]))

    io = TeensyIO(transport=ScriptedTransport(reject)).connect()

    with pytest.raises(expected_exception):
        io.ping()


def test_unexpected_response_type_raises_protocol_error() -> None:
    def respond_with_event(request: Packet) -> Packet:
        return Packet(PacketType.EVENT, request.seq, b"unexpected")

    io = TeensyIO(transport=ScriptedTransport(respond_with_event)).connect()

    with pytest.raises(ProtocolError):
        io.ping()


def test_reads_fragmented_responses() -> None:
    io = TeensyIO(transport=ScriptedTransport(read_chunk_size=1), timeout=0.5).connect()

    assert io.ping() is True


def test_ignores_unrelated_response_sequence_until_expected_sequence_arrives() -> None:
    def handler(request: Packet) -> Packet:
        transport.queue(Packet(PacketType.DATA, 999, b"stale"))
        return Packet(PacketType.DATA, request.seq, b"pong")

    transport = ScriptedTransport(handler)
    io = TeensyIO(transport=transport, timeout=0.5).connect()

    assert io.ping() is True


def test_batch_queues_commands_and_flushes_on_exit() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()
    io.pin("relay").configure_output(8, initial=False)
    io.pwm("output").configure(3, frequency=20_000, initial_duty=0.0)
    transport.requests.clear()
    transport.writes.clear()

    with io.batch():
        io.pin("relay").write(True)
        io.pwm("output").write(0.25)

    assert len(transport.writes) == 1
    assert [request.payload[0] for request in transport.requests] == [CommandId.DIGITAL_WRITE, CommandId.PWM_WRITE]


def test_close_flushes_queued_commands() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport).connect()
    io.pin("led").physical_pin = 13
    io.begin_batch()
    io.pin("led").write(True)

    assert transport.writes == []
    io.close()
    assert len(transport.writes) == 1


def test_large_batch_flushes_as_coalesced_chunks_without_dropping_packets() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport, flush_chunk_size=4096).connect()
    io.pin("led").physical_pin = 13
    count = 2000

    with io.batch():
        for index in range(count):
            io.pin("led").write(index % 2 == 0)
            assert io.queued_packet_count >= 0
            assert io.queued_byte_count >= 0

    assert len(transport.requests) == count
    assert io.queued_packet_count == 0
    assert io.queued_byte_count == 0
    assert 1 < len(transport.writes) < count


def test_large_batch_can_flush_in_one_write_when_chunk_is_large_enough() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport, flush_chunk_size=1_000_000).connect()
    io.pin("led").physical_pin = 13

    with io.batch():
        for _ in range(1000):
            io.pin("led").write(True)

    assert len(transport.requests) == 1000
    assert len(transport.writes) == 1


def test_queue_max_bytes_applies_backpressure_before_memory_growth() -> None:
    io = TeensyIO(transport=ScriptedTransport(), queue_max_bytes=20).connect()
    io.pin("led").physical_pin = 13
    io.begin_batch()

    io.pin("led").write(True)
    with pytest.raises(QueueFullError):
        for _ in range(10):
            io.pin("led").write(True)

    assert io.queued_byte_count <= 20


def test_auto_flush_thread_flushes_queued_fire_and_forget_command() -> None:
    transport = ScriptedTransport()
    io = TeensyIO(transport=transport, flush_rate_hz=100).connect()

    io._command(CommandId.HEARTBEAT, expect_response=False)
    deadline = time.monotonic() + 0.5
    while not transport.writes and time.monotonic() < deadline:
        time.sleep(0.01)
    io.close()

    assert len(transport.writes) == 1


def test_foreground_commands_and_heartbeat_are_serialized() -> None:
    entered = threading.Event()
    release = threading.Event()

    def handler(request: Packet) -> Packet:
        if request.payload[0] == CommandId.HEARTBEAT:
            entered.set()
            assert release.wait(timeout=1.0)
        return Packet(PacketType.ACK, request.seq, b"\x00")

    transport = ScriptedTransport(handler)
    io = TeensyIO(transport=transport).connect()

    heartbeat_thread = threading.Thread(target=io.heartbeat)
    heartbeat_thread.start()
    assert entered.wait(timeout=1.0)

    foreground_done = threading.Event()
    foreground_thread = threading.Thread(target=lambda: (io.clear_emergency_stop(), foreground_done.set()))
    foreground_thread.start()
    time.sleep(0.05)
    assert not foreground_done.is_set()

    release.set()
    heartbeat_thread.join(timeout=1.0)
    foreground_thread.join(timeout=1.0)

    assert foreground_done.is_set()
    assert [request.payload[0] for request in transport.requests] == [
        CommandId.HEARTBEAT,
        CommandId.CLEAR_EMERGENCY_STOP,
    ]


def test_counter_ids_are_stable_and_incremental() -> None:
    io = TeensyIO(transport=ScriptedTransport()).connect()

    assert io._counter_id("left") == 0
    assert io._counter_id("right") == 1
    assert io._counter_id("left") == 0


def test_pack_and_unpack_helpers_are_little_endian() -> None:
    assert TeensyIO._pack_u32(0x12345678) == b"\x78\x56\x34\x12"
    assert TeensyIO._unpack_u32(b"\x78\x56\x34\x12") == 0x12345678
    assert TeensyIO._unpack_i32((-2).to_bytes(4, "little", signed=True)) == -2
