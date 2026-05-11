#pragma once

#include <Arduino.h>

#include "Packet.h"

namespace teensyio {

class PacketWriter {
 public:
  explicit PacketWriter(Stream& stream) : stream_(stream) {}
  void write(const Packet& packet);
  void write(PacketType type, uint16_t seq, const uint8_t* payload, uint16_t length);
  int available_for_write() const;
  static uint16_t encoded_size(uint16_t payload_length);

 private:
  Stream& stream_;
};

}  // namespace teensyio
