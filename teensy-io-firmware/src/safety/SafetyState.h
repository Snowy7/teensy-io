#pragma once

#include <Arduino.h>

#include "../board/BoardConfig.h"

namespace teensyio {

class SafetyState {
 public:
  void heartbeat() { last_heartbeat_ms_ = millis(); watchdog_expired_ = false; }

  void update() {
    if (millis() - last_heartbeat_ms_ > watchdog_timeout_ms_) {
      watchdog_expired_ = true;
      emergency_stop_ = true;
    }
  }

  void set_watchdog_timeout(uint32_t timeout_ms) { watchdog_timeout_ms_ = timeout_ms; }
  void emergency_stop() { emergency_stop_ = true; }
  void clear_emergency_stop() {
    emergency_stop_ = false;
    watchdog_expired_ = false;
    heartbeat();
  }

  bool outputs_allowed() const { return !emergency_stop_ && !watchdog_expired_; }
  bool emergency_stop_active() const { return emergency_stop_; }
  bool watchdog_expired() const { return watchdog_expired_; }

 private:
  uint32_t watchdog_timeout_ms_ = kDefaultWatchdogTimeoutMs;
  uint32_t last_heartbeat_ms_ = 0;
  bool emergency_stop_ = false;
  bool watchdog_expired_ = false;
};

}  // namespace teensyio
