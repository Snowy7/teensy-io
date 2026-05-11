#pragma once

#include "../io/PulseCounter.h"
#include "../protocol/PacketWriter.h"
#include "../safety/SafetyState.h"

namespace teensyio {

enum class ResourceKind : uint8_t {
  Digital = 1,
  Analog = 2,
  Counter = 3,
  Encoder = 4,
};

struct EncoderSlot {
  bool active = false;
  uint8_t pin_a = 0;
  uint8_t pin_b = 0;
  uint8_t mode = 4;
  int32_t position = 0;
  uint8_t last_state = 0;
};

struct SubscriptionSlot {
  bool active = false;
  ResourceKind kind = ResourceKind::Digital;
  uint8_t id = 0;
  uint16_t rate_hz = 0;
  uint8_t flags = 0;
  uint32_t next_due_ms = 0;
  int32_t last_value = 0;
  bool has_last_value = false;
};

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
  void handle_analog(CommandId command, const Packet& packet);
  void handle_counter(CommandId command, const Packet& packet);
  void handle_encoder(CommandId command, const Packet& packet);
  void handle_subscription(CommandId command, const Packet& packet);
  bool configure_counter(uint8_t id, uint8_t pin, EdgeMode edge);
  bool configure_encoder(uint8_t id, uint8_t pin_a, uint8_t pin_b, uint8_t mode);
  int32_t read_resource_value(ResourceKind kind, uint8_t id, bool& ok);
  void update_subscriptions();
  void write_i32(uint8_t* payload, int32_t value);
  void write_u32(uint8_t* payload, uint32_t value);

  PacketWriter& writer_;
  SafetyState safety_;
  bool pwm_configured_[NUM_DIGITAL_PINS] = {};
  bool analog_configured_[NUM_DIGITAL_PINS] = {};
  uint8_t analog_samples_[NUM_DIGITAL_PINS] = {};
  SubscriptionSlot subscriptions_[kMaxSubscriptions] = {};
};

extern CounterSlot g_counters[kMaxCounters];
extern EncoderSlot g_encoders[kMaxEncoders];

}  // namespace teensyio
