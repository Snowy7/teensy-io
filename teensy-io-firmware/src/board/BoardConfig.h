#pragma once

#include <Arduino.h>

namespace teensyio {

static constexpr uint32_t kDefaultBaudrate = 1000000;
static constexpr uint32_t kDefaultWatchdogTimeoutMs = 300;
static constexpr uint8_t kMaxCounters = 8;

inline bool is_valid_digital_pin(uint8_t pin) {
  return pin < NUM_DIGITAL_PINS;
}

inline bool is_valid_pwm_pin(uint8_t pin) {
  return is_valid_digital_pin(pin) && digitalPinHasPWM(pin);
}

}  // namespace teensyio
