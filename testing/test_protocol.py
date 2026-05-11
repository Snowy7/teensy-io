from __future__ import annotations

import pytest

from teensy_io.protocol.commands import PacketType
from teensy_io.protocol.errors import ProtocolError
from teensy_io.protocol.packet import (
    MAX_PAYLOAD_SIZE,
    PROTOCOL_VERSION,
    START_BYTE,
    Packet,
    PacketDecoder,
    crc16_ccitt,
    encode_packet,
)


def test_crc16_ccitt_known_vector() -> None:
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_encoded_packet_layout_and_round_trip() -> None:
    packet = Packet(PacketType.COMMAND, 0x1234, b"\x01abc")
    encoded = encode_packet(packet)

    assert encoded[0] == START_BYTE
    assert encoded[1] == PROTOCOL_VERSION
    assert encoded[2] == PacketType.COMMAND
    assert encoded[3:5] == b"\x34\x12"
    assert encoded[5:7] == b"\x04\x00"
    assert PacketDecoder().feed(encoded) == [packet]


@pytest.mark.parametrize("payload_size", [0, 1, MAX_PAYLOAD_SIZE])
def test_payload_size_boundaries(payload_size: int) -> None:
    packet = Packet(PacketType.DATA, 1, bytes([0x55]) * payload_size)

    assert PacketDecoder().feed(encode_packet(packet)) == [packet]


def test_rejects_oversized_payload_on_encode() -> None:
    with pytest.raises(ProtocolError):
        encode_packet(Packet(PacketType.DATA, 1, bytes(MAX_PAYLOAD_SIZE + 1)))


def test_decoder_accepts_byte_by_byte_fragmentation() -> None:
    packet = Packet(PacketType.DATA, 99, b"fragmented")
    decoder = PacketDecoder()
    decoded = []

    for byte in encode_packet(packet):
        decoded.extend(decoder.feed(bytes([byte])))

    assert decoded == [packet]


def test_decoder_returns_multiple_packets_from_one_buffer() -> None:
    packets = [
        Packet(PacketType.ACK, 1, b"\x00"),
        Packet(PacketType.DATA, 2, b"payload"),
        Packet(PacketType.NACK, 3, b"\x03"),
    ]
    encoded = b"".join(encode_packet(packet) for packet in packets)

    assert PacketDecoder().feed(encoded) == packets


def test_decoder_ignores_noise_before_valid_frame() -> None:
    packet = Packet(PacketType.DATA, 5, b"ok")

    assert PacketDecoder().feed(b"noise" + encode_packet(packet)) == [packet]


def test_decoder_recovers_after_bad_crc() -> None:
    bad = bytearray(encode_packet(Packet(PacketType.DATA, 1, b"bad")))
    bad[-1] ^= 0xFF
    good = Packet(PacketType.DATA, 2, b"good")

    assert PacketDecoder().feed(bytes(bad) + encode_packet(good)) == [good]


def test_decoder_recovers_after_wrong_protocol_version() -> None:
    bad = bytearray(encode_packet(Packet(PacketType.DATA, 1, b"bad")))
    bad[1] = 0xFF
    good = Packet(PacketType.DATA, 2, b"good")

    assert PacketDecoder().feed(bytes(bad) + encode_packet(good)) == [good]


def test_decoder_recovers_after_oversized_length_header() -> None:
    malformed = bytes([START_BYTE, PROTOCOL_VERSION, PacketType.DATA, 1, 0, 0xFF, 0x7F])
    good = Packet(PacketType.DATA, 2, b"good")

    assert PacketDecoder().feed(malformed + encode_packet(good)) == [good]
