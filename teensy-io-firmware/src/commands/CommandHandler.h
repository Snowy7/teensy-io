#pragma once

#include "../io/PulseCounter.h"
#include "../protocol/PacketWriter.h"
#include "../safety/SafetyState.h"

namespace teensyio {

class CommandHandler {
 public:
  explicit CommandHandler(PacketWriter& writer) : writer_(writer) {}
  void handle(const Packet& packet);
  void update();

 private:
  void ack(uint16_t seq);
  void nack(uint16_t seq, ErrorCode code);
  void data(uint16_t seq, const uint8_t* payload, uint16_t length);
  void apply_safe_outputs();

  void handle_system(CommandId command, const Packet& packet);
  void handle_digital(CommandId command, const Packet& packet);
  void handle_pwm(CommandId command, const Packet& packet);
  void handle_counter(CommandId command, const Packet& packet);
  bool configure_counter(uint8_t id, uint8_t pin, EdgeMode edge);

  PacketWriter& writer_;
  SafetyState safety_;
  bool pwm_configured_[NUM_DIGITAL_PINS] = {};
};

extern CounterSlot g_counters[kMaxCounters];

}  // namespace teensyio
