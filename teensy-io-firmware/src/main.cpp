#include <Arduino.h>

#include "board/BoardConfig.h"
#include "commands/CommandHandler.h"
#include "protocol/PacketParser.h"
#include "protocol/PacketWriter.h"

using namespace teensyio;

PacketParser parser;
PacketWriter writer(Serial);
CommandHandler handler(writer);

void setup() {
  Serial.begin(kDefaultBaudrate);
}

void loop() {
  Packet packet;
  while (Serial.available() > 0) {
    if (parser.push(static_cast<uint8_t>(Serial.read()), packet)) {
      handler.handle(packet);
    }
  }
  handler.update();
}
