from __future__ import annotations

import re
from pathlib import Path

from teensy_io.protocol.commands import CommandId, ErrorCode, PacketType

ROOT = Path(__file__).resolve().parents[1]
COMMAND_IDS_H = ROOT / "teensy-io-firmware/src/protocol/CommandIds.h"
PLATFORMIO_INI = ROOT / "teensy-io-firmware/platformio.ini"


def _enum_block(source: str, enum_name: str) -> str:
    match = re.search(rf"enum class {enum_name} : uint8_t \{{(?P<body>.*?)\}};", source, re.DOTALL)
    assert match is not None, f"missing enum {enum_name}"
    return match.group("body")


def _parse_enum_values(enum_name: str) -> dict[str, int]:
    source = COMMAND_IDS_H.read_text(encoding="utf-8")
    values: dict[str, int] = {}
    for name, raw_value in re.findall(r"^\s*([A-Za-z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+),", _enum_block(source, enum_name), re.MULTILINE):
        values[name] = int(raw_value, 0)
    return values


def test_packet_type_values_match_firmware() -> None:
    firmware = _parse_enum_values("PacketType")

    assert firmware == {member.name.title().replace("_", ""): int(member) for member in PacketType}


def test_command_id_values_match_firmware() -> None:
    firmware = _parse_enum_values("CommandId")
    expected = {
        "Ping": CommandId.PING,
        "GetInfo": CommandId.GET_INFO,
        "Heartbeat": CommandId.HEARTBEAT,
        "ResetConfig": CommandId.RESET_CONFIG,
        "ConfigDigitalInput": CommandId.CONFIG_DIGITAL_INPUT,
        "ConfigDigitalOutput": CommandId.CONFIG_DIGITAL_OUTPUT,
        "DigitalRead": CommandId.DIGITAL_READ,
        "DigitalWrite": CommandId.DIGITAL_WRITE,
        "ConfigPwm": CommandId.CONFIG_PWM,
        "PwmWrite": CommandId.PWM_WRITE,
        "PwmDisable": CommandId.PWM_DISABLE,
        "ConfigAnalog": CommandId.CONFIG_ANALOG,
        "AnalogRead": CommandId.ANALOG_READ,
        "ConfigCounter": CommandId.CONFIG_COUNTER,
        "CounterRead": CommandId.COUNTER_READ,
        "CounterReset": CommandId.COUNTER_RESET,
        "CounterFrequency": CommandId.COUNTER_FREQUENCY,
        "ConfigEncoder": CommandId.CONFIG_ENCODER,
        "EncoderRead": CommandId.ENCODER_READ,
        "EncoderReset": CommandId.ENCODER_RESET,
        "Subscribe": CommandId.SUBSCRIBE,
        "Unsubscribe": CommandId.UNSUBSCRIBE,
        "TelemetryFrame": CommandId.TELEMETRY_FRAME,
        "ConfigI2cBus": CommandId.CONFIG_I2C_BUS,
        "I2cWrite": CommandId.I2C_WRITE,
        "I2cRead": CommandId.I2C_READ,
        "ConfigDac": CommandId.CONFIG_DAC,
        "DacWriteRaw": CommandId.DAC_WRITE_RAW,
        "DacWriteNormalized": CommandId.DAC_WRITE_NORMALIZED,
        "EmergencyStop": CommandId.EMERGENCY_STOP,
        "ClearEmergencyStop": CommandId.CLEAR_EMERGENCY_STOP,
    }

    assert firmware == {name: int(value) for name, value in expected.items()}


def test_error_code_values_match_firmware() -> None:
    firmware = _parse_enum_values("ErrorCode")
    expected = {
        "Ok": ErrorCode.OK,
        "UnknownCommand": ErrorCode.UNKNOWN_COMMAND,
        "InvalidPayload": ErrorCode.INVALID_PAYLOAD,
        "InvalidPin": ErrorCode.INVALID_PIN,
        "InvalidMode": ErrorCode.INVALID_MODE,
        "EmergencyStopActive": ErrorCode.EMERGENCY_STOP_ACTIVE,
        "ResourceUnavailable": ErrorCode.RESOURCE_UNAVAILABLE,
    }

    assert firmware == {name: int(value) for name, value in expected.items()}


def test_firmware_declares_build_version() -> None:
    platformio_ini = PLATFORMIO_INI.read_text(encoding="utf-8")

    assert "TEENSY_IO_FIRMWARE_VERSION" in platformio_ini
