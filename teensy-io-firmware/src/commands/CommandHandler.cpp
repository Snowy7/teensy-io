#include "CommandHandler.h"

#include <string.h>

#include "../board/BoardConfig.h"

namespace teensyio {

CounterSlot g_counters[kMaxCounters];

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

void counter_isr_0() { counter_tick(0); }
void counter_isr_1() { counter_tick(1); }
void counter_isr_2() { counter_tick(2); }
void counter_isr_3() { counter_tick(3); }
void counter_isr_4() { counter_tick(4); }
void counter_isr_5() { counter_tick(5); }
void counter_isr_6() { counter_tick(6); }
void counter_isr_7() { counter_tick(7); }

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
  } else if (group == 0x40) {
    handle_counter(command, packet);
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
          static_cast<uint8_t>(count & 0xFF),
          static_cast<uint8_t>((count >> 8) & 0xFF),
          static_cast<uint8_t>((count >> 16) & 0xFF),
          static_cast<uint8_t>((count >> 24) & 0xFF),
      };
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
          static_cast<uint8_t>(milli_hz & 0xFF),
          static_cast<uint8_t>((milli_hz >> 8) & 0xFF),
          static_cast<uint8_t>((milli_hz >> 16) & 0xFF),
          static_cast<uint8_t>((milli_hz >> 24) & 0xFF),
      };
      data(packet.seq, payload, sizeof(payload));
      break;
    }
    default:
      nack(packet.seq, ErrorCode::UnknownCommand);
      break;
  }
}

}  // namespace teensyio
