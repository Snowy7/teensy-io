from __future__ import annotations

import time
from collections import deque
from typing import Any

from teensy_io.protocol.commands import CommandId


class PulseCounter:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.id: int | None = None
        self._last_count = 0
        self._samples: deque[tuple[float, int]] = deque()

    def attach(self, pin: str | int, edge: str = "rising") -> "PulseCounter":
        physical_pin = self._resolve_pin(pin)
        self.id = self.io._counter_id(self.name)
        edge_code = {"rising": 0, "falling": 1, "both": 2}[edge]
        self.io._command(CommandId.CONFIG_COUNTER, bytes([self.id, physical_pin, edge_code]))
        return self

    def read(self) -> int:
        self._require_counter()
        return self.io._unpack_i32(self.io._command(CommandId.COUNTER_READ, bytes([self.id])))

    def delta(self) -> int:
        count = self.read()
        delta = count - self._last_count
        self._last_count = count
        return delta

    def frequency(self, window_ms: int = 100) -> float:
        self._require_counter()
        if window_ms <= 0:
            milli_hz = self.io._unpack_u32(self.io._command(CommandId.COUNTER_FREQUENCY, bytes([self.id])))
            return milli_hz / 1000.0

        now = time.monotonic()
        count = self.read()
        self._samples.append((now, count))
        cutoff = now - (window_ms / 1000.0)
        while len(self._samples) > 2 and self._samples[0][0] < cutoff:
            self._samples.popleft()
        if len(self._samples) < 2:
            return 0.0
        start_time, start_count = self._samples[0]
        elapsed = now - start_time
        if elapsed <= 0:
            return 0.0
        return (count - start_count) / elapsed

    def reset(self) -> None:
        self._require_counter()
        self.io._command(CommandId.COUNTER_RESET, bytes([self.id]))
        self._last_count = 0
        self._samples.clear()

    def _resolve_pin(self, pin: str | int) -> int:
        if isinstance(pin, int):
            return pin
        resource = self.io.pin(pin)
        if resource.physical_pin is None:
            raise RuntimeError(f"pin {pin!r} is not configured")
        return resource.physical_pin

    def _require_counter(self) -> None:
        if self.id is None:
            raise RuntimeError(f"counter {self.name!r} is not attached")
