from __future__ import annotations

from collections import deque
from typing import Callable, Optional

from teensy_io.protocol.commands import CommandId, ErrorCode, PacketType, ResourceKind
from teensy_io.protocol.packet import Packet, PacketDecoder, encode_packet
from teensy_io.transport.base import Transport

ResponseHandler = Callable[[Packet], Optional[Packet]]


class ScriptedTransport(Transport):
    def __init__(self, handler: ResponseHandler | None = None, *, read_chunk_size: int | None = None) -> None:
        self.opened = False
        self.writes: list[bytes] = []
        self.requests: list[Packet] = []
        self._decoder = PacketDecoder()
        self._rx = bytearray()
        self._read_chunk_size = read_chunk_size
        self._handler = handler or self._default_handler

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)
        for request in self._decoder.feed(data):
            self.requests.append(request)
            response = self._handler(request)
            if response is not None:
                self.queue(response)

    def read(self, size: int = 1) -> bytes:
        if not self._rx:
            return b""
        limit = min(size, len(self._rx))
        if self._read_chunk_size is not None:
            limit = min(limit, self._read_chunk_size)
        data = bytes(self._rx[:limit])
        del self._rx[:limit]
        return data

    def read_available(self, max_bytes: int) -> bytes:
        return self.read(max_bytes)

    @property
    def is_open(self) -> bool:
        return self.opened

    def queue(self, packet: Packet) -> None:
        self._rx.extend(encode_packet(packet))

    @staticmethod
    def _default_handler(request: Packet) -> Packet:
        command = CommandId(request.payload[0])
        if command == CommandId.PING:
            return Packet(PacketType.DATA, request.seq, b"pong")
        if command == CommandId.GET_INFO:
            return Packet(PacketType.DATA, request.seq, bytes([42, 8]) + b"0.1.0\x00")
        if command == CommandId.DIGITAL_READ:
            return Packet(PacketType.DATA, request.seq, b"\x01")
        if command == CommandId.COUNTER_READ:
            return Packet(PacketType.DATA, request.seq, (123).to_bytes(4, "little", signed=True))
        if command == CommandId.COUNTER_FREQUENCY:
            return Packet(PacketType.DATA, request.seq, (12500).to_bytes(4, "little"))
        if command == CommandId.ANALOG_READ:
            return Packet(PacketType.DATA, request.seq, (2048).to_bytes(2, "little") + (5001).to_bytes(2, "little"))
        if command == CommandId.ENCODER_READ:
            return Packet(PacketType.DATA, request.seq, (321).to_bytes(4, "little", signed=True))
        if command == CommandId.I2C_READ:
            length = request.payload[3]
            return Packet(PacketType.DATA, request.seq, bytes(range(length)))
        if command == CommandId.SUBSCRIBE:
            kind = ResourceKind(request.payload[1])
            resource_id = request.payload[2]
            return Packet(PacketType.ACK, request.seq, bytes([ErrorCode.OK]))
        return Packet(PacketType.ACK, request.seq, bytes([ErrorCode.OK]))


def command_payload(request: Packet) -> bytes:
    return request.payload[1:]
