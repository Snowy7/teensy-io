#pragma once

#include <Arduino.h>

namespace teensyio {

static constexpr uint32_t kDefaultBaudrate = 1000000;
static constexpr uint32_t kDefaultWatchdogTimeoutMs = 300;
static constexpr uint8_t kMaxCounters = 8;
static constexpr uint8_t kMaxEncoders = 4;
static constexpr uint8_t kMaxSubscriptions = 16;
static constexpr uint8_t kAsyncOutboundFrames = 64;
static constexpr uint8_t kMaxI2cBuses = 3;
static constexpr uint8_t kMaxDacs = 8;
static constexpr uint16_t kAdcMaxValue = 4095;

inline bool is_valid_digital_pin(uint8_t pin) {
  return pin < NUM_DIGITAL_PINS;
}

inline bool is_valid_pwm_pin(uint8_t pin) {
  return is_valid_digital_pin(pin) && digitalPinHasPWM(pin);
}

inline bool is_valid_analog_pin(uint8_t pin) {
  return pin < NUM_DIGITAL_PINS;
}

}  // namespace teensyio
