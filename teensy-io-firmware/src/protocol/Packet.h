#pragma once

#include <stdint.h>
#include <stddef.h>

#include "CommandIds.h"

namespace teensyio {

static constexpr uint8_t kStartByte = 0xA5;
static constexpr uint8_t kProtocolVersion = 0x01;
static constexpr size_t kMaxPayloadSize = 128;

struct Packet {
  PacketType type = PacketType::Command;
  uint16_t seq = 0;
  uint8_t payload[kMaxPayloadSize] = {};
  uint16_t length = 0;
};

uint16_t crc16_ccitt(const uint8_t* data, size_t length);

}  // namespace teensyio
