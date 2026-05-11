from __future__ import annotations

from typing import Any

from teensy_io.protocol.commands import CommandId


class PwmOutput:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.physical_pin: int | None = None

    def configure(self, physical_pin: int, frequency: int = 1000, initial_duty: float = 0.0) -> "PwmOutput":
        self.physical_pin = int(physical_pin)
        payload = bytes([self.physical_pin]) + self.io._pack_u32(int(frequency)) + bytes([self.io._u8_duty(initial_duty)])
        self.io._command(CommandId.CONFIG_PWM, payload)
        return self

    def write(self, duty: float) -> None:
        self._require_pin()
        self.io._command(CommandId.PWM_WRITE, bytes([self.physical_pin, self.io._u8_duty(duty)]))

    def disable(self) -> None:
        self._require_pin()
        self.io._command(CommandId.PWM_DISABLE, bytes([self.physical_pin]))

    def _require_pin(self) -> None:
        if self.physical_pin is None:
            raise RuntimeError(f"pwm {self.name!r} is not configured")
