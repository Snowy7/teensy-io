from __future__ import annotations

from .base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 1_000_000, timeout: float = 0.1) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def open(self) -> None:
        import serial

        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()

    def write(self, data: bytes) -> None:
        if self._serial is None:
            raise RuntimeError("transport is not open")
        self._serial.write(data)

    def read(self, size: int = 1) -> bytes:
        if self._serial is None:
            raise RuntimeError("transport is not open")
        return self._serial.read(size)

    def read_available(self, max_bytes: int) -> bytes:
        if self._serial is None:
            raise RuntimeError("transport is not open")
        waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
        if waiting <= 0:
            return b""
        return self._serial.read(min(max_bytes, waiting))

    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)
