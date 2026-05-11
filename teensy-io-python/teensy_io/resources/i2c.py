from __future__ import annotations

from typing import Any

from teensy_io.protocol.commands import CommandId


class I2cBus:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.bus: int | None = None
        self.frequency = 400_000

    def configure(self, bus: int = 0, frequency: int = 400_000) -> "I2cBus":
        if bus < 0 or bus > 255:
            raise ValueError("bus must fit in uint8")
        if frequency <= 0:
            raise ValueError("frequency must be positive")
        self.bus = int(bus)
        self.frequency = int(frequency)
        self.io._command(CommandId.CONFIG_I2C_BUS, bytes([self.bus]) + self.io._pack_u32(self.frequency))
        return self

    def write(self, address: int, data: bytes) -> None:
        self._require_bus()
        payload = bytes([self.bus, _u7_address(address), len(data)]) + bytes(data)
        self.io._command(CommandId.I2C_WRITE, payload)

    def read(self, address: int, length: int) -> bytes:
        self._require_bus()
        if length < 0 or length > 128:
            raise ValueError("length must be between 0 and 128")
        return self.io._command(CommandId.I2C_READ, bytes([self.bus, _u7_address(address), length]))

    def _require_bus(self) -> None:
        if self.bus is None:
            raise RuntimeError(f"i2c bus {self.name!r} is not configured")


def _u7_address(address: int) -> int:
    if address < 0 or address > 0x7F:
        raise ValueError("I2C address must be a 7-bit address")
    return int(address)
