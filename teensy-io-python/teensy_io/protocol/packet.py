from __future__ import annotations

from dataclasses import dataclass

from .commands import PacketType
from .errors import ProtocolError

START_BYTE = 0xA5
PROTOCOL_VERSION = 0x01
MAX_PAYLOAD_SIZE = 128


@dataclass(frozen=True)
class Packet:
    type: PacketType
    seq: int
    payload: bytes = b""


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_packet(packet: Packet) -> bytes:
    if len(packet.payload) > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"payload too large: {len(packet.payload)}")
    header = bytes(
        [
            PROTOCOL_VERSION,
            int(packet.type),
            packet.seq & 0xFF,
            (packet.seq >> 8) & 0xFF,
            len(packet.payload) & 0xFF,
            (len(packet.payload) >> 8) & 0xFF,
        ]
    )
    crc = crc16_ccitt(header + packet.payload)
    return bytes([START_BYTE]) + header + packet.payload + crc.to_bytes(2, "little")


class PacketDecoder:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        self._buffer.extend(data)
        packets: list[Packet] = []

        while True:
            try:
                start_index = self._buffer.index(START_BYTE)
            except ValueError:
                self._buffer.clear()
                break

            if start_index:
                del self._buffer[:start_index]
            if len(self._buffer) < 9:
                break

            version = self._buffer[1]
            if version != PROTOCOL_VERSION:
                del self._buffer[0]
                continue

            length = self._buffer[5] | (self._buffer[6] << 8)
            if length > MAX_PAYLOAD_SIZE:
                del self._buffer[0]
                continue

            frame_len = 1 + 6 + length + 2
            if len(self._buffer) < frame_len:
                break

            frame = bytes(self._buffer[:frame_len])
            crc_expected = int.from_bytes(frame[-2:], "little")
            crc_actual = crc16_ccitt(frame[1:-2])
            if crc_actual != crc_expected:
                del self._buffer[0]
                continue

            payload = frame[7:-2]
            packets.append(
                Packet(
                    type=PacketType(frame[2]),
                    seq=frame[3] | (frame[4] << 8),
                    payload=payload,
                )
            )
            del self._buffer[:frame_len]

        return packets
