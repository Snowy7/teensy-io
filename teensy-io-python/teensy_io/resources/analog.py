from __future__ import annotations

from typing import Any

from teensy_io.protocol.commands import CommandId


class AnalogInput:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.physical_pin: int | None = None
        self.samples = 1

    def configure(self, physical_pin: int, samples: int = 1) -> "AnalogInput":
        self.physical_pin = int(physical_pin)
        self.samples = int(samples)
        if self.samples < 1 or self.samples > 255:
            raise ValueError("samples must be between 1 and 255")
        self.io._command(CommandId.CONFIG_ANALOG, bytes([self.physical_pin, self.samples]))
        return self

    def read_raw(self) -> int:
        raw, _normalized = self._read()
        return raw

    def read_normalized(self) -> float:
        _raw, normalized = self._read()
        return normalized / 10000.0

    def _read(self) -> tuple[int, int]:
        if self.physical_pin is None:
            raise RuntimeError(f"analog {self.name!r} is not configured")
        payload = self.io._command(CommandId.ANALOG_READ, bytes([self.physical_pin]))
        raw = int.from_bytes(payload[:2], "little")
        normalized = int.from_bytes(payload[2:4], "little")
        return raw, normalized
