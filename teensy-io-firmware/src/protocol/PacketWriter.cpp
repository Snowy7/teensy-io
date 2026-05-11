#include "PacketWriter.h"

namespace teensyio {

void PacketWriter::write(const Packet& packet) {
  write(packet.type, packet.seq, packet.payload, packet.length);
}

void PacketWriter::write(PacketType type, uint16_t seq, const uint8_t* payload, uint16_t length) {
  uint8_t header[6] = {
      kProtocolVersion,
      static_cast<uint8_t>(type),
      static_cast<uint8_t>(seq & 0xFF),
      static_cast<uint8_t>((seq >> 8) & 0xFF),
      static_cast<uint8_t>(length & 0xFF),
      static_cast<uint8_t>((length >> 8) & 0xFF),
  };

  uint8_t crc_buffer[6 + kMaxPayloadSize] = {};
  for (uint8_t i = 0; i < 6; ++i) {
    crc_buffer[i] = header[i];
  }
  for (uint16_t i = 0; i < length; ++i) {
    crc_buffer[6 + i] = payload[i];
  }
  const uint16_t crc = crc16_ccitt(crc_buffer, 6 + length);

  stream_.write(kStartByte);
  stream_.write(header, sizeof(header));
  if (length > 0 && payload != nullptr) {
    stream_.write(payload, length);
  }
  stream_.write(static_cast<uint8_t>(crc & 0xFF));
  stream_.write(static_cast<uint8_t>((crc >> 8) & 0xFF));
}

}  // namespace teensyio
