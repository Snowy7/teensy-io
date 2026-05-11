#include "CommandHandler.h"

#include <Wire.h>
#include <string.h>

#include "../board/BoardConfig.h"

namespace teensyio {

CounterSlot g_counters[kMaxCounters];
EncoderSlot g_encoders[kMaxEncoders];

using IsrPtr = void (*)();

static IsrPtr counter_isr_for(uint8_t id) {
  static IsrPtr isrs[kMaxCounters] = {
      counter_isr_0, counter_isr_1, counter_isr_2, counter_isr_3,
      counter_isr_4, counter_isr_5, counter_isr_6, counter_isr_7,
  };
  return id < kMaxCounters ? isrs[id] : nullptr;
}

static int edge_to_interrupt_mode(EdgeMode edge) {
  switch (edge) {
    case EdgeMode::Rising:
      return RISING;
    case EdgeMode::Falling:
      return FALLING;
    case EdgeMode::Both:
      return CHANGE;
  }
  return RISING;
}

static TwoWire* wire_for_bus(uint8_t bus) {
  switch (bus) {
    case 0:
      return &Wire;
#if defined(WIRE_IMPLEMENT_WIRE1) || defined(__IMXRT1062__)
    case 1:
      return &Wire1;
#endif
#if defined(WIRE_IMPLEMENT_WIRE2) || defined(__IMXRT1062__)
    case 2:
      return &Wire2;
#endif
    default:
      return nullptr;
  }
}

static uint8_t encoder_state(uint8_t pin_a, uint8_t pin_b) {
  return static_cast<uint8_t>((digitalRead(pin_a) == HIGH ? 2 : 0) | (digitalRead(pin_b) == HIGH ? 1 : 0));
}

static int8_t encoder_delta(uint8_t previous, uint8_t current) {
  static const int8_t table[16] = {
      0, -1, 1, 0,
      1, 0, 0, -1,
      -1, 0, 0, 1,
      0, 1, -1, 0,
  };
  return table[((previous & 0x03) << 2) | (current & 0x03)];
}

static void counter_tick(uint8_t id) {
  if (id >= kMaxCounters || !g_counters[id].active) {
    return;
  }
  const uint32_t now = micros();
  const uint32_t previous = g_counters[id].last_edge_us;
  g_counters[id].count++;
  if (previous != 0) {
    g_counters[id].period_us = now - previous;
  }
  g_counters[id].last_edge_us = now;
}

static void encoder_tick(uint8_t id) {
  if (id >= kMaxEncoders || !g_encoders[id].active) {
    return;
  }
  const uint8_t current = encoder_state(g_encoders[id].pin_a, g_encoders[id].pin_b);
  const int8_t delta = encoder_delta(g_encoders[id].last_state, current);
  g_encoders[id].position += delta;
  g_encoders[id].last_state = current;
}

void counter_isr_0() { counter_tick(0); }
void counter_isr_1() { counter_tick(1); }
void counter_isr_2() { counter_tick(2); }
void counter_isr_3() { counter_tick(3); }
void counter_isr_4() { counter_tick(4); }
void counter_isr_5() { counter_tick(5); }
void counter_isr_6() { counter_tick(6); }
void counter_isr_7() { counter_tick(7); }

void encoder_isr_0() { encoder_tick(0); }
void encoder_isr_1() { encoder_tick(1); }
void encoder_isr_2() { encoder_tick(2); }
void encoder_isr_3() { encoder_tick(3); }

static IsrPtr encoder_isr_for(uint8_t id) {
  static IsrPtr isrs[kMaxEncoders] = {
      encoder_isr_0,
      encoder_isr_1,
      encoder_isr_2,
      encoder_isr_3,
  };
  return id < kMaxEncoders ? isrs[id] : nullptr;
}

void CommandHandler::handle(const Packet& packet) {
  if (packet.type != PacketType::Command || packet.length == 0) {
    nack(packet.seq, ErrorCode::InvalidPayload);
    return;
  }

  const CommandId command = static_cast<CommandId>(packet.payload[0]);
  const uint8_t group = static_cast<uint8_t>(command) & 0xF0;

  if (command == CommandId::Ping || command == CommandId::GetInfo || command == CommandId::Heartbeat ||
      command == CommandId::ResetConfig || command == CommandId::EmergencyStop ||
      command == CommandId::ClearEmergencyStop) {
    handle_system(command, packet);
  } else if (group == 0x10) {
    handle_digital(command, packet);
  } else if (group == 0x20) {
    handle_pwm(command, packet);
  } else if (group == 0x30) {
    handle_analog(command, packet);
  } else if (group == 0x40) {
    handle_counter(command, packet);
  } else if (group == 0x50) {
    handle_encoder(command, packet);
  } else if (group == 0x60) {
    handle_subscription(command, packet);
  } else if (group == 0x70) {
    handle_i2c(command, packet);
  } else {
    nack(packet.seq, ErrorCode::UnknownCommand);
  }
}

void CommandHandler::update() {
  const bool allowed_before = safety_.outputs_allowed();
  safety_.update();
  if (allowed_before && !safety_.outputs_allowed()) {
    apply_safe_outputs();
  }
  update_subscriptions();
}

void CommandHandler::ack(uint16_t seq) {
  uint8_t payload[1] = {static_cast<uint8_t>(ErrorCode::Ok)};
  writer_.write(PacketType::Ack, seq, payload, sizeof(payload));
}

void CommandHandler::nack(uint16_t seq, ErrorCode code) {
  uint8_t payload[1] = {static_cast<uint8_t>(code)};
  writer_.write(PacketType::Nack, seq, payload, sizeof(payload));
}

void CommandHandler::data(uint16_t seq, const uint8_t* payload, uint16_t length) {
  writer_.write(PacketType::Data, seq, payload, length);
}

void CommandHandler::write_i32(uint8_t* payload, int32_t value) {
  payload[0] = static_cast<uint8_t>(value & 0xFF);
  payload[1] = static_cast<uint8_t>((value >> 8) & 0xFF);
  payload[2] = static_cast<uint8_t>((value >> 16) & 0xFF);
  payload[3] = static_cast<uint8_t>((value >> 24) & 0xFF);
}

void CommandHandler::write_u32(uint8_t* payload, uint32_t value) {
  payload[0] = static_cast<uint8_t>(value & 0xFF);
  payload[1] = static_cast<uint8_t>((value >> 8) & 0xFF);
  payload[2] = static_cast<uint8_t>((value >> 16) & 0xFF);
  payload[3] = static_cast<uint8_t>((value >> 24) & 0xFF);
}

void CommandHandler::apply_safe_outputs() {
  for (uint8_t pin = 0; pin < NUM_DIGITAL_PINS; ++pin) {
    if (pwm_configured_[pin]) {
      analogWrite(pin, 0);
    }
  }
}

void CommandHandler::handle_system(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::Ping:
      data(packet.seq, reinterpret_cast<const uint8_t*>("pong"), 4);
      break;
    case CommandId::GetInfo: {
      const char* version = TEENSY_IO_FIRMWARE_VERSION;
      uint8_t payload[48] = {};
      payload[0] = NUM_DIGITAL_PINS;
      payload[1] = kMaxCounters;
      strncpy(reinterpret_cast<char*>(&payload[2]), version, sizeof(payload) - 2);
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    case CommandId::Heartbeat:
      safety_.heartbeat();
      ack(packet.seq);
      break;
    case CommandId::EmergencyStop:
      safety_.emergency_stop();
      apply_safe_outputs();
      ack(packet.seq);
      break;
    case CommandId::ClearEmergencyStop:
      safety_.clear_emergency_stop();
      ack(packet.seq);
      break;
    case CommandId::ResetConfig:
      apply_safe_outputs();
      for (uint8_t i = 0; i < kMaxCounters; ++i) {
        if (g_counters[i].active) {
          detachInterrupt(digitalPinToInterrupt(g_counters[i].pin));
        }
        g_counters[i] = CounterSlot{};
      }
      memset(pwm_configured_, 0, sizeof(pwm_configured_));
      memset(analog_configured_, 0, sizeof(analog_configured_));
      memset(analog_samples_, 0, sizeof(analog_samples_));
      for (uint8_t i = 0; i < kMaxEncoders; ++i) {
        if (g_encoders[i].active) {
          detachInterrupt(digitalPinToInterrupt(g_encoders[i].pin_a));
          detachInterrupt(digitalPinToInterrupt(g_encoders[i].pin_b));
        }
        g_encoders[i] = EncoderSlot{};
      }
      for (uint8_t i = 0; i < kMaxSubscriptions; ++i) {
        subscriptions_[i] = SubscriptionSlot{};
      }
      memset(i2c_configured_, 0, sizeof(i2c_configured_));
      for (uint8_t i = 0; i < kMaxDacs; ++i) {
        dacs_[i] = DacSlot{};
      }
      ack(packet.seq);
      break;
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::handle_digital(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigDigitalOutput: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const bool initial = packet.payload[2] != 0;
      if (initial && !safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      if (!is_valid_digital_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      pinMode(pin, OUTPUT);
      digitalWrite(pin, initial ? HIGH : LOW);
      ack(packet.seq);
      break;
    }
    case CommandId::ConfigDigitalInput: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const uint8_t pull = packet.payload[2];
      if (!is_valid_digital_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      if (pull == 1) {
        pinMode(pin, INPUT_PULLUP);
      } else if (pull == 2) {
        pinMode(pin, INPUT_PULLDOWN);
      } else {
        pinMode(pin, INPUT);
      }
      ack(packet.seq);
      break;
    }
    case CommandId::DigitalRead: {
      if (packet.length < 2) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      if (!is_valid_digital_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      uint8_t payload[1] = {static_cast<uint8_t>(digitalRead(pin) == HIGH)};
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    case CommandId::DigitalWrite: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      if (!safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const bool value = packet.payload[2] != 0;
      if (!is_valid_digital_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      digitalWrite(pin, value ? HIGH : LOW);
      ack(packet.seq);
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::handle_pwm(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigPwm: {
      if (packet.length < 7) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const uint32_t frequency = static_cast<uint32_t>(packet.payload[2]) |
                                 (static_cast<uint32_t>(packet.payload[3]) << 8) |
                                 (static_cast<uint32_t>(packet.payload[4]) << 16) |
                                 (static_cast<uint32_t>(packet.payload[5]) << 24);
      const uint8_t duty = packet.payload[6];
      if (duty > 0 && !safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      if (!is_valid_pwm_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      pinMode(pin, OUTPUT);
      analogWriteResolution(8);
      analogWriteFrequency(pin, frequency);
      analogWrite(pin, duty);
      pwm_configured_[pin] = true;
      ack(packet.seq);
      break;
    }
    case CommandId::PwmWrite: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      if (!safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const uint8_t duty = packet.payload[2];
      if (!is_valid_pwm_pin(pin) || !pwm_configured_[pin]) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      analogWrite(pin, duty);
      ack(packet.seq);
      break;
    }
    case CommandId::PwmDisable: {
      if (packet.length < 2) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      if (!is_valid_pwm_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      analogWrite(pin, 0);
      pwm_configured_[pin] = false;
      ack(packet.seq);
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::handle_analog(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigAnalog: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      const uint8_t samples = packet.payload[2] == 0 ? 1 : packet.payload[2];
      if (!is_valid_analog_pin(pin)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      analogReadResolution(12);
      analog_configured_[pin] = true;
      analog_samples_[pin] = samples;
      ack(packet.seq);
      break;
    }
    case CommandId::AnalogRead: {
      if (packet.length < 2) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t pin = packet.payload[1];
      if (!is_valid_analog_pin(pin) || !analog_configured_[pin]) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      const uint8_t samples = analog_samples_[pin] == 0 ? 1 : analog_samples_[pin];
      uint32_t total = 0;
      for (uint8_t i = 0; i < samples; ++i) {
        total += analogRead(pin);
      }
      const uint16_t raw = static_cast<uint16_t>(total / samples);
      const uint16_t normalized = static_cast<uint16_t>((static_cast<uint32_t>(raw) * 10000UL) / kAdcMaxValue);
      uint8_t payload[4] = {
          static_cast<uint8_t>(raw & 0xFF),
          static_cast<uint8_t>((raw >> 8) & 0xFF),
          static_cast<uint8_t>(normalized & 0xFF),
          static_cast<uint8_t>((normalized >> 8) & 0xFF),
      };
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

bool CommandHandler::configure_counter(uint8_t id, uint8_t pin, EdgeMode edge) {
  if (id >= kMaxCounters || !is_valid_digital_pin(pin)) {
    return false;
  }
  if (g_counters[id].active) {
    detachInterrupt(digitalPinToInterrupt(g_counters[id].pin));
  }
  g_counters[id] = CounterSlot{};
  g_counters[id].active = true;
  g_counters[id].pin = pin;
  g_counters[id].edge = edge;
  attachInterrupt(digitalPinToInterrupt(pin), counter_isr_for(id), edge_to_interrupt_mode(edge));
  return true;
}

bool CommandHandler::configure_encoder(uint8_t id, uint8_t pin_a, uint8_t pin_b, uint8_t mode) {
  if (id >= kMaxEncoders || !is_valid_digital_pin(pin_a) || !is_valid_digital_pin(pin_b)) {
    return false;
  }
  pinMode(pin_a, INPUT);
  pinMode(pin_b, INPUT);
  if (g_encoders[id].active) {
    detachInterrupt(digitalPinToInterrupt(g_encoders[id].pin_a));
    detachInterrupt(digitalPinToInterrupt(g_encoders[id].pin_b));
  }
  g_encoders[id] = EncoderSlot{};
  g_encoders[id].active = true;
  g_encoders[id].pin_a = pin_a;
  g_encoders[id].pin_b = pin_b;
  g_encoders[id].mode = mode;
  g_encoders[id].last_state = encoder_state(pin_a, pin_b);
  attachInterrupt(digitalPinToInterrupt(pin_a), encoder_isr_for(id), CHANGE);
  attachInterrupt(digitalPinToInterrupt(pin_b), encoder_isr_for(id), CHANGE);
  return true;
}

void CommandHandler::handle_counter(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigCounter: {
      if (packet.length < 4) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      const uint8_t pin = packet.payload[2];
      const EdgeMode edge = static_cast<EdgeMode>(packet.payload[3]);
      if (!configure_counter(id, pin, edge)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      ack(packet.seq);
      break;
    }
    case CommandId::CounterRead: {
      if (packet.length < 2 || packet.payload[1] >= kMaxCounters || !g_counters[packet.payload[1]].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      noInterrupts();
      const int32_t count = g_counters[id].count;
      interrupts();
      uint8_t payload[4] = {
          0,
      };
      write_i32(payload, count);
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    case CommandId::CounterReset: {
      if (packet.length < 2 || packet.payload[1] >= kMaxCounters || !g_counters[packet.payload[1]].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      noInterrupts();
      g_counters[id].count = 0;
      g_counters[id].last_edge_us = 0;
      g_counters[id].period_us = 0;
      interrupts();
      ack(packet.seq);
      break;
    }
    case CommandId::CounterFrequency: {
      if (packet.length < 2 || packet.payload[1] >= kMaxCounters || !g_counters[packet.payload[1]].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      noInterrupts();
      const uint32_t period_us = g_counters[id].period_us;
      interrupts();
      const uint32_t milli_hz = period_us == 0 ? 0 : 1000000000UL / period_us;
      uint8_t payload[4] = {
          0,
      };
      write_u32(payload, milli_hz);
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::handle_encoder(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigEncoder: {
      if (packet.length < 5) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      const uint8_t pin_a = packet.payload[2];
      const uint8_t pin_b = packet.payload[3];
      const uint8_t mode = packet.payload[4];
      if (!configure_encoder(id, pin_a, pin_b, mode)) {
        nack(packet.seq, ErrorCode::InvalidPin);
        return;
      }
      ack(packet.seq);
      break;
    }
    case CommandId::EncoderRead: {
      if (packet.length < 2 || packet.payload[1] >= kMaxEncoders || !g_encoders[packet.payload[1]].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      noInterrupts();
      const int32_t position = g_encoders[id].position;
      interrupts();
      uint8_t payload[4] = {0};
      write_i32(payload, position);
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    case CommandId::EncoderReset: {
      if (packet.length < 2 || packet.payload[1] >= kMaxEncoders || !g_encoders[packet.payload[1]].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      noInterrupts();
      g_encoders[packet.payload[1]].position = 0;
      interrupts();
      ack(packet.seq);
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::handle_subscription(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::Subscribe: {
      if (packet.length < 6) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const ResourceKind kind = static_cast<ResourceKind>(packet.payload[1]);
      const uint8_t id = packet.payload[2];
      const uint16_t rate_hz = static_cast<uint16_t>(packet.payload[3]) | (static_cast<uint16_t>(packet.payload[4]) << 8);
      const uint8_t flags = packet.payload[5];
      bool ok = false;
      (void)read_resource_value(kind, id, ok);
      if (!ok) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      for (uint8_t i = 0; i < kMaxSubscriptions; ++i) {
        if (!subscriptions_[i].active) {
          subscriptions_[i].active = true;
          subscriptions_[i].kind = kind;
          subscriptions_[i].id = id;
          subscriptions_[i].rate_hz = rate_hz;
          subscriptions_[i].flags = flags;
          subscriptions_[i].next_due_ms = millis();
          subscriptions_[i].has_last_value = false;
          ack(packet.seq);
          return;
        }
      }
      nack(packet.seq, ErrorCode::ResourceUnavailable);
      break;
    }
    case CommandId::Unsubscribe: {
      if (packet.length < 3) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const ResourceKind kind = static_cast<ResourceKind>(packet.payload[1]);
      const uint8_t id = packet.payload[2];
      for (uint8_t i = 0; i < kMaxSubscriptions; ++i) {
        if (subscriptions_[i].active && subscriptions_[i].kind == kind && subscriptions_[i].id == id) {
          subscriptions_[i] = SubscriptionSlot{};
        }
      }
      ack(packet.seq);
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

int32_t CommandHandler::read_resource_value(ResourceKind kind, uint8_t id, bool& ok) {
  ok = true;
  switch (kind) {
    case ResourceKind::Digital:
      if (!is_valid_digital_pin(id)) {
        ok = false;
        return 0;
      }
      return digitalRead(id) == HIGH ? 1 : 0;
    case ResourceKind::Analog: {
      if (!is_valid_analog_pin(id) || !analog_configured_[id]) {
        ok = false;
        return 0;
      }
      const uint8_t samples = analog_samples_[id] == 0 ? 1 : analog_samples_[id];
      uint32_t total = 0;
      for (uint8_t i = 0; i < samples; ++i) {
        total += analogRead(id);
      }
      return static_cast<int32_t>(total / samples);
    }
    case ResourceKind::Counter:
      if (id >= kMaxCounters || !g_counters[id].active) {
        ok = false;
        return 0;
      }
      noInterrupts();
      {
        const int32_t count = g_counters[id].count;
        interrupts();
        return count;
      }
    case ResourceKind::Encoder:
      if (id >= kMaxEncoders || !g_encoders[id].active) {
        ok = false;
        return 0;
      }
      noInterrupts();
      {
        const int32_t position = g_encoders[id].position;
        interrupts();
        return position;
      }
    case ResourceKind::Dac:
      if (id >= kMaxDacs || !dacs_[id].active) {
        ok = false;
        return 0;
      }
      return dacs_[id].last_value;
  }
  ok = false;
  return 0;
}

bool CommandHandler::write_dac_raw(uint8_t id, uint8_t channel, uint16_t value) {
  if (id >= kMaxDacs || !dacs_[id].active || channel >= dacs_[id].channels) {
    return false;
  }
  TwoWire* wire = wire_for_bus(dacs_[id].bus);
  if (wire == nullptr || !i2c_configured_[dacs_[id].bus]) {
    return false;
  }
  const uint8_t resolution = dacs_[id].resolution_bits == 0 ? 12 : dacs_[id].resolution_bits;
  const uint16_t max_value = resolution >= 16 ? 0xFFFF : static_cast<uint16_t>((1UL << resolution) - 1UL);
  if (value > max_value) {
    value = max_value;
  }
  wire->beginTransmission(dacs_[id].address);
  if (dacs_[id].channels > 1) {
    wire->write(channel);
  }
  wire->write(static_cast<uint8_t>((value >> 8) & 0xFF));
  wire->write(static_cast<uint8_t>(value & 0xFF));
  const uint8_t result = wire->endTransmission();
  if (result != 0) {
    return false;
  }
  dacs_[id].last_value = value;
  return true;
}

void CommandHandler::handle_i2c(CommandId command, const Packet& packet) {
  switch (command) {
    case CommandId::ConfigI2cBus: {
      if (packet.length < 6) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t bus = packet.payload[1];
      const uint32_t frequency = static_cast<uint32_t>(packet.payload[2]) |
                                 (static_cast<uint32_t>(packet.payload[3]) << 8) |
                                 (static_cast<uint32_t>(packet.payload[4]) << 16) |
                                 (static_cast<uint32_t>(packet.payload[5]) << 24);
      TwoWire* wire = wire_for_bus(bus);
      if (bus >= kMaxI2cBuses || wire == nullptr) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      wire->begin();
      wire->setClock(frequency == 0 ? 400000 : frequency);
      i2c_configured_[bus] = true;
      ack(packet.seq);
      break;
    }
    case CommandId::I2cWrite: {
      if (packet.length < 4) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t bus = packet.payload[1];
      const uint8_t address = packet.payload[2];
      const uint8_t length = packet.payload[3];
      if (bus >= kMaxI2cBuses || !i2c_configured_[bus] || packet.length < 4 + length) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      TwoWire* wire = wire_for_bus(bus);
      if (wire == nullptr) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      wire->beginTransmission(address);
      for (uint8_t i = 0; i < length; ++i) {
        wire->write(packet.payload[4 + i]);
      }
      const uint8_t result = wire->endTransmission();
      if (result != 0) {
        nack(packet.seq, ErrorCode::ResourceUnavailable);
        return;
      }
      ack(packet.seq);
      break;
    }
    case CommandId::I2cRead: {
      if (packet.length < 4) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t bus = packet.payload[1];
      const uint8_t address = packet.payload[2];
      const uint8_t length = packet.payload[3];
      if (bus >= kMaxI2cBuses || !i2c_configured_[bus] || length > kMaxPayloadSize) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      TwoWire* wire = wire_for_bus(bus);
      if (wire == nullptr) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t received = wire->requestFrom(static_cast<int>(address), static_cast<int>(length));
      uint8_t payload[kMaxPayloadSize] = {};
      for (uint8_t i = 0; i < received && wire->available(); ++i) {
        payload[i] = static_cast<uint8_t>(wire->read());
      }
      data(packet.seq, payload, received);
      break;
    }
    case CommandId::ConfigDac: {
      if (packet.length < 6) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint8_t id = packet.payload[1];
      const uint8_t bus = packet.payload[2];
      const uint8_t address = packet.payload[3];
      const uint8_t channels = packet.payload[4];
      const uint8_t resolution = packet.payload[5];
      if (id >= kMaxDacs || bus >= kMaxI2cBuses || !i2c_configured_[bus] || channels == 0 || resolution == 0 || resolution > 16) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      dacs_[id] = DacSlot{};
      dacs_[id].active = true;
      dacs_[id].bus = bus;
      dacs_[id].address = address;
      dacs_[id].channels = channels;
      dacs_[id].resolution_bits = resolution;
      ack(packet.seq);
      break;
    }
    case CommandId::DacWriteRaw: {
      if (packet.length < 5) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      if (!safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      const uint8_t id = packet.payload[1];
      const uint8_t channel = packet.payload[2];
      const uint16_t value = static_cast<uint16_t>(packet.payload[3]) | (static_cast<uint16_t>(packet.payload[4]) << 8);
      if (!write_dac_raw(id, channel, value)) {
        nack(packet.seq, ErrorCode::ResourceUnavailable);
        return;
      }
      ack(packet.seq);
      break;
    }
    case CommandId::DacWriteNormalized: {
      if (packet.length < 5) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      if (!safety_.outputs_allowed()) {
        nack(packet.seq, ErrorCode::EmergencyStopActive);
        return;
      }
      const uint8_t id = packet.payload[1];
      const uint8_t channel = packet.payload[2];
      if (id >= kMaxDacs || !dacs_[id].active) {
        nack(packet.seq, ErrorCode::InvalidPayload);
        return;
      }
      const uint16_t normalized = static_cast<uint16_t>(packet.payload[3]) | (static_cast<uint16_t>(packet.payload[4]) << 8);
      const uint8_t resolution = dacs_[id].resolution_bits == 0 ? 12 : dacs_[id].resolution_bits;
      const uint16_t max_value = resolution >= 16 ? 0xFFFF : static_cast<uint16_t>((1UL << resolution) - 1UL);
      const uint16_t value = static_cast<uint16_t>((static_cast<uint32_t>(normalized) * max_value) / 10000UL);
      if (!write_dac_raw(id, channel, value)) {
        nack(packet.seq, ErrorCode::ResourceUnavailable);
        return;
      }
      ack(packet.seq);
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

void CommandHandler::update_subscriptions() {
  const uint32_t now = millis();
  for (uint8_t i = 0; i < kMaxSubscriptions; ++i) {
    if (!subscriptions_[i].active) {
      continue;
    }
    bool ok = false;
    const int32_t value = read_resource_value(subscriptions_[i].kind, subscriptions_[i].id, ok);
    if (!ok) {
      subscriptions_[i] = SubscriptionSlot{};
      continue;
    }
    const bool on_change = (subscriptions_[i].flags & 0x01) != 0;
    if (on_change && subscriptions_[i].has_last_value && value != subscriptions_[i].last_value) {
      bool should_emit = true;
      if (subscriptions_[i].kind == ResourceKind::Digital) {
        const bool rising = subscriptions_[i].last_value == 0 && value != 0;
        const bool falling = subscriptions_[i].last_value != 0 && value == 0;
        const bool wants_rising = (subscriptions_[i].flags & 0x02) != 0;
        const bool wants_falling = (subscriptions_[i].flags & 0x04) != 0;
        should_emit = (rising && wants_rising) || (falling && wants_falling) || (!wants_rising && !wants_falling);
      }
      if (should_emit) {
        uint8_t payload[10] = {
            static_cast<uint8_t>(subscriptions_[i].kind),
            subscriptions_[i].id,
        };
        write_i32(&payload[2], value);
        write_u32(&payload[6], micros());
        writer_.write(PacketType::Event, 0, payload, sizeof(payload));
      }
    }
    subscriptions_[i].last_value = value;
    subscriptions_[i].has_last_value = true;

    if (subscriptions_[i].rate_hz == 0 || now < subscriptions_[i].next_due_ms) {
      continue;
    }
    uint8_t payload[6] = {
        static_cast<uint8_t>(subscriptions_[i].kind),
        subscriptions_[i].id,
    };
    write_i32(&payload[2], value);
    writer_.write(PacketType::Telemetry, 0, payload, sizeof(payload));
    const uint32_t interval_ms = 1000UL / subscriptions_[i].rate_hz;
    subscriptions_[i].next_due_ms = now + (interval_ms == 0 ? 1 : interval_ms);
  }
}

}  // namespace teensyio
