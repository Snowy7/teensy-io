from __future__ import annotations

from collections import deque

import pytest

from teensy_io import EmergencyStopActiveError, TeensyIO
from teensy_io.protocol.commands import CommandId, ErrorCode, PacketType
from teensy_io.protocol.packet import Packet, PacketDecoder, encode_packet
from teensy_io.transport.base import Transport


class FakeTransport(Transport):
    def __init__(self) -> None:
        self.opened = False
        self.writes: list[bytes] = []
        self.responses: deque[bytes] = deque()
        self.decoder = PacketDecoder()

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)
        request = self.decoder.feed(data)[0]
        command = CommandId(request.payload[0])
        if command == CommandId.PING:
            response = Packet(PacketType.DATA, request.seq, b"pong")
        elif command == CommandId.COUNTER_READ:
            response = Packet(PacketType.DATA, request.seq, (123).to_bytes(4, "little", signed=True))
        elif command == CommandId.PWM_WRITE:
            response = Packet(PacketType.NACK, request.seq, bytes([ErrorCode.EMERGENCY_STOP_ACTIVE]))
        else:
            response = Packet(PacketType.ACK, request.seq, bytes([ErrorCode.OK]))
        self.responses.append(encode_packet(response))

    def read(self, size: int = 1) -> bytes:
        if not self.responses:
            return b""
        data = self.responses.popleft()
        return data[:size] if size < len(data) else data

    @property
    def is_open(self) -> bool:
        return self.opened


def test_ping() -> None:
    io = TeensyIO(transport=FakeTransport()).connect()

    assert io.ping() is True


def test_pin_output_commands() -> None:
    transport = FakeTransport()
    io = TeensyIO(transport=transport).connect()

    io.pin("led").configure_output(13, initial=False)
    io.pin("led").write(True)

    assert len(transport.writes) == 2


def test_counter_read() -> None:
    io = TeensyIO(transport=FakeTransport()).connect()
    io.pin("pulse").configure_input(7, pull="up")
    counter = io.counter("ticks").attach("pulse")

    assert counter.read() == 123


def test_emergency_stop_error_mapping() -> None:
    io = TeensyIO(transport=FakeTransport()).connect()
    io.pwm("out").physical_pin = 3

    with pytest.raises(EmergencyStopActiveError):
        io.pwm("out").write(0.5)
