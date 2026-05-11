from teensy_io.protocol.commands import PacketType
from teensy_io.protocol.packet import Packet, PacketDecoder, encode_packet


def test_packet_round_trip() -> None:
    packet = Packet(PacketType.COMMAND, 42, b"\x01abc")

    decoded = PacketDecoder().feed(encode_packet(packet))

    assert decoded == [packet]


def test_decoder_handles_fragmented_input() -> None:
    packet = Packet(PacketType.DATA, 7, b"pong")
    encoded = encode_packet(packet)
    decoder = PacketDecoder()

    assert decoder.feed(encoded[:3]) == []
    assert decoder.feed(encoded[3:]) == [packet]
