#pragma once

#include <Arduino.h>

namespace teensyio {

enum class EdgeMode : uint8_t {
  Rising = 0,
  Falling = 1,
  Both = 2,
};

struct CounterSlot {
  bool active = false;
  uint8_t pin = 0;
  EdgeMode edge = EdgeMode::Rising;
  volatile int32_t count = 0;
  volatile uint32_t last_edge_us = 0;
  volatile uint32_t period_us = 0;
};

void counter_isr_0();
void counter_isr_1();
void counter_isr_2();
void counter_isr_3();
void counter_isr_4();
void counter_isr_5();
void counter_isr_6();
void counter_isr_7();

}  // namespace teensyio
