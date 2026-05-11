#pragma once

#include <stdint.h>

#include "Packet.h"

namespace teensyio {

class PacketParser {
 public:
  bool push(uint8_t byte, Packet& packet);
  void reset();

 private:
  enum class State : uint8_t {
    Start,
    Version,
    Type,
    SeqLo,
    SeqHi,
    LengthLo,
    LengthHi,
    Payload,
    CrcLo,
    CrcHi,
  };

  State state_ = State::Start;
  Packet current_;
  uint16_t payload_index_ = 0;
  uint8_t crc_lo_ = 0;
};

}  // namespace teensyio
