from __future__ import annotations

from typing import Any

from teensy_io.protocol.commands import CommandId


class DacOutput:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.id: int | None = None
        self.bus_name: str | None = None
        self.address: int | None = None
        self.channels = 1
        self.resolution_bits = 12

    def attach_i2c(
        self,
        bus: str,
        address: int,
        channels: int = 1,
        resolution_bits: int = 12,
    ) -> "DacOutput":
        bus_resource = self.io.i2c_bus(bus)
        if bus_resource.bus is None:
            raise RuntimeError(f"i2c bus {bus!r} is not configured")
        if channels < 1 or channels > 255:
            raise ValueError("channels must be between 1 and 255")
        if resolution_bits < 1 or resolution_bits > 16:
            raise ValueError("resolution_bits must be between 1 and 16")
        self.id = self.io._dac_id(self.name)
        self.bus_name = bus
        self.address = _u7_address(address)
        self.channels = int(channels)
        self.resolution_bits = int(resolution_bits)
        self.io._command(
            CommandId.CONFIG_DAC,
            bytes([self.id, bus_resource.bus, self.address, self.channels, self.resolution_bits]),
        )
        return self

    def write_raw(self, value: int, channel: int = 0) -> None:
        self._require_dac()
        self._check_channel(channel)
        max_value = (1 << self.resolution_bits) - 1 if self.resolution_bits < 16 else 0xFFFF
        if value < 0 or value > max_value:
            raise ValueError(f"value must be between 0 and {max_value}")
        self.io._command(CommandId.DAC_WRITE_RAW, bytes([self.id, channel]) + int(value).to_bytes(2, "little"))

    def write_normalized(self, value: float, channel: int = 0) -> None:
        self._require_dac()
        self._check_channel(channel)
        if value < 0.0 or value > 1.0:
            raise ValueError("value must be between 0.0 and 1.0")
        scaled = int(round(value * 10000))
        self.io._command(CommandId.DAC_WRITE_NORMALIZED, bytes([self.id, channel]) + scaled.to_bytes(2, "little"))

    def _require_dac(self) -> None:
        if self.id is None:
            raise RuntimeError(f"dac {self.name!r} is not attached")

    def _check_channel(self, channel: int) -> None:
        if channel < 0 or channel >= self.channels:
            raise ValueError(f"channel must be between 0 and {self.channels - 1}")


def _u7_address(address: int) -> int:
    if address < 0 or address > 0x7F:
        raise ValueError("I2C address must be a 7-bit address")
    return int(address)
