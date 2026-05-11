#pragma once

#include <stdint.h>

namespace teensyio {

enum class PacketType : uint8_t {
  Command = 0x01,
  Ack = 0x02,
  Nack = 0x03,
  Data = 0x04,
  Event = 0x05,
  Telemetry = 0x06,
  Error = 0x07,
};

enum class CommandId : uint8_t {
  Ping = 0x01,
  GetInfo = 0x02,
  Heartbeat = 0x03,
  ResetConfig = 0x04,

  ConfigDigitalInput = 0x10,
  ConfigDigitalOutput = 0x11,
  DigitalRead = 0x12,
  DigitalWrite = 0x13,

  ConfigPwm = 0x20,
  PwmWrite = 0x21,
  PwmDisable = 0x22,

  ConfigAnalog = 0x30,
  AnalogRead = 0x31,

  ConfigCounter = 0x40,
  CounterRead = 0x41,
  CounterReset = 0x42,
  CounterFrequency = 0x43,

  ConfigEncoder = 0x50,
  EncoderRead = 0x51,
  EncoderReset = 0x52,

  Subscribe = 0x60,
  Unsubscribe = 0x61,
  TelemetryFrame = 0x62,

  ConfigI2cBus = 0x70,
  I2cWrite = 0x71,
  I2cRead = 0x72,
  ConfigDac = 0x73,
  DacWriteRaw = 0x74,
  DacWriteNormalized = 0x75,

  EmergencyStop = 0xF0,
  ClearEmergencyStop = 0xF1,
};

enum class ErrorCode : uint8_t {
  Ok = 0x00,
  UnknownCommand = 0x01,
  InvalidPayload = 0x02,
  InvalidPin = 0x03,
  InvalidMode = 0x04,
  EmergencyStopActive = 0x05,
  ResourceUnavailable = 0x06,
};

}  // namespace teensyio
