from __future__ import annotations

from typing import Any


class AnalogInput:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name
        self.physical_pin: int | None = None
        self.samples = 1

    def configure(self, physical_pin: int, samples: int = 1) -> "AnalogInput":
        self.physical_pin = int(physical_pin)
        self.samples = int(samples)
        raise NotImplementedError("analog input is reserved for the next firmware phase")

    def read_raw(self) -> int:
        raise NotImplementedError("analog input is reserved for the next firmware phase")

    def read_normalized(self) -> float:
        raise NotImplementedError("analog input is reserved for the next firmware phase")
