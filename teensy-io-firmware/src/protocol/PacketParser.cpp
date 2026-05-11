#include "PacketParser.h"

namespace teensyio {

bool PacketParser::push(uint8_t byte, Packet& packet) {
  switch (state_) {
    case State::Start:
      if (byte == kStartByte) {
        current_ = Packet{};
        payload_index_ = 0;
        state_ = State::Version;
      }
      break;
    case State::Version:
      state_ = byte == kProtocolVersion ? State::Type : State::Start;
      break;
    case State::Type:
      current_.type = static_cast<PacketType>(byte);
      state_ = State::SeqLo;
      break;
    case State::SeqLo:
      current_.seq = byte;
      state_ = State::SeqHi;
      break;
    case State::SeqHi:
      current_.seq |= static_cast<uint16_t>(byte) << 8;
      state_ = State::LengthLo;
      break;
    case State::LengthLo:
      current_.length = byte;
      state_ = State::LengthHi;
      break;
    case State::LengthHi:
      current_.length |= static_cast<uint16_t>(byte) << 8;
      if (current_.length > kMaxPayloadSize) {
        reset();
      } else {
        state_ = current_.length == 0 ? State::CrcLo : State::Payload;
      }
      break;
    case State::Payload:
      current_.payload[payload_index_++] = byte;
      if (payload_index_ >= current_.length) {
        state_ = State::CrcLo;
      }
      break;
    case State::CrcLo:
      crc_lo_ = byte;
      state_ = State::CrcHi;
      break;
    case State::CrcHi: {
      const uint16_t expected = static_cast<uint16_t>(crc_lo_) | (static_cast<uint16_t>(byte) << 8);
      uint8_t buffer[6 + kMaxPayloadSize] = {};
      buffer[0] = kProtocolVersion;
      buffer[1] = static_cast<uint8_t>(current_.type);
      buffer[2] = static_cast<uint8_t>(current_.seq & 0xFF);
      buffer[3] = static_cast<uint8_t>((current_.seq >> 8) & 0xFF);
      buffer[4] = static_cast<uint8_t>(current_.length & 0xFF);
      buffer[5] = static_cast<uint8_t>((current_.length >> 8) & 0xFF);
      for (uint16_t i = 0; i < current_.length; ++i) {
        buffer[6 + i] = current_.payload[i];
      }
      const uint16_t actual = crc16_ccitt(buffer, 6 + current_.length);
      if (actual == expected) {
        packet = current_;
        reset();
        return true;
      }
      reset();
      break;
    }
  }
  return false;
}

void PacketParser::reset() {
  state_ = State::Start;
  current_ = Packet{};
  payload_index_ = 0;
  crc_lo_ = 0;
}

}  // namespace teensyio
