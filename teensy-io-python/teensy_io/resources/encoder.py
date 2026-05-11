from __future__ import annotations

from typing import Any

from teensy_io.protocol.commands import CommandId


class QuadratureEncoder:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.id: int | None = None
        self._last_position = 0

    def attach(self, pin_a: int, pin_b: int, mode: str = "x4") -> "QuadratureEncoder":
        mode_code = {"x1": 1, "x2": 2, "x4": 4}[mode]
        self.id = self.io._encoder_id(self.name)
        self.io._command(CommandId.CONFIG_ENCODER, bytes([self.id, int(pin_a), int(pin_b), mode_code]))
        return self

    def read(self) -> int:
        self._require_encoder()
        return self.io._unpack_i32(self.io._command(CommandId.ENCODER_READ, bytes([self.id])))

    def delta(self) -> int:
        position = self.read()
        delta = position - self._last_position
        self._last_position = position
        return delta

    def reset(self) -> None:
        self._require_encoder()
        self.io._command(CommandId.ENCODER_RESET, bytes([self.id]))
        self._last_position = 0

    def _require_encoder(self) -> None:
        if self.id is None:
            raise RuntimeError(f"encoder {self.name!r} is not attached")
