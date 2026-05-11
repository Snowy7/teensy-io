from __future__ import annotations

from typing import Any


class QuadratureEncoder:
    def __init__(self, io: Any, name: str) -> None:
        self.io = io
        self.name = name

    def attach(self, pin_a: int, pin_b: int, mode: str = "x4") -> "QuadratureEncoder":
        raise NotImplementedError("quadrature encoder support is reserved for the next firmware phase")

    def read(self) -> int:
        raise NotImplementedError("quadrature encoder support is reserved for the next firmware phase")

    def delta(self) -> int:
        raise NotImplementedError("quadrature encoder support is reserved for the next firmware phase")

    def reset(self) -> None:
        raise NotImplementedError("quadrature encoder support is reserved for the next firmware phase")
