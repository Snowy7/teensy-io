from __future__ import annotations

from typing import Any, Callable

from teensy_io.protocol.commands import CommandId, ResourceKind


class Pin:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.physical_pin: int | None = None

    def configure_output(self, physical_pin: int, initial: bool = False) -> "Pin":
        self.physical_pin = int(physical_pin)
        self.io._command(CommandId.CONFIG_DIGITAL_OUTPUT, bytes([self.physical_pin, int(initial)]))
        return self

    def configure_input(self, physical_pin: int, pull: str = "floating", debounce_us: int = 0) -> "Pin":
        del debounce_us  # Firmware debounce is reserved for the next digital input phase.
        self.physical_pin = int(physical_pin)
        pull_code = {"floating": 0, "none": 0, "up": 1, "pullup": 1, "down": 2, "pulldown": 2}[pull]
        self.io._command(CommandId.CONFIG_DIGITAL_INPUT, bytes([self.physical_pin, pull_code]))
        return self

    def read(self) -> bool:
        self._require_pin()
        return bool(self.io._command(CommandId.DIGITAL_READ, bytes([self.physical_pin]))[0])

    def write(self, value: bool) -> None:
        self._require_pin()
        self.io._command(CommandId.DIGITAL_WRITE, bytes([self.physical_pin, int(value)]), expect_response=True)

    def on_edge(self, edge: str, callback: Callable[..., None]) -> None:
        self._require_pin()
        key = (ResourceKind.DIGITAL, self.physical_pin)
        self.io._edge_callbacks.setdefault(key, []).append(callback)
        edge_flags = {"rising": 0x02, "falling": 0x04, "both": 0x06}[edge]
        self.io._command(CommandId.SUBSCRIBE, bytes([ResourceKind.DIGITAL, self.physical_pin, 0, 0, 0x01 | edge_flags]))

    def _require_pin(self) -> None:
        if self.physical_pin is None:
            raise RuntimeError(f"pin {self.name!r} is not configured")
