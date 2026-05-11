from __future__ import annotations

import itertools
import struct
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config.loader import load_config
from .protocol.commands import CommandId, ErrorCode, PacketType
from .protocol.errors import (
    CommandRejectedError,
    EmergencyStopActiveError,
    InvalidModeError,
    InvalidPinError,
    ProtocolError,
    TeensyIOTimeoutError,
)
from .protocol.packet import Packet, PacketDecoder, encode_packet
from .resources.analog import AnalogInput
from .resources.counter import PulseCounter
from .resources.encoder import QuadratureEncoder
from .resources.pin import Pin
from .resources.pwm import PwmOutput
from .transport.base import Transport
from .transport.serial_transport import SerialTransport


class TeensyIO:
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 1_000_000,
        *,
        transport: Transport | None = None,
        timeout: float = 1.0,
        auto_flush: bool = True,
        flush_rate_hz: float | None = None,
    ) -> None:
        if transport is None and port is None:
            raise ValueError("port or transport is required")
        self.transport = transport or SerialTransport(port or "", baudrate=baudrate)
        self.timeout = timeout
        self.auto_flush = auto_flush
        self.flush_rate_hz = flush_rate_hz
        self._decoder = PacketDecoder()
        self._seq = itertools.count(1)
        self._batch_depth = 0
        self._queued: list[bytes] = []
        self._pins: dict[str, Pin] = {}
        self._pwms: dict[str, PwmOutput] = {}
        self._analogs: dict[str, AnalogInput] = {}
        self._counters: dict[str, PulseCounter] = {}
        self._encoders: dict[str, QuadratureEncoder] = {}
        self._counter_ids: dict[str, int] = {}
        self._config: dict[str, Any] = {}
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._flush_thread: threading.Thread | None = None
        self._flush_stop = threading.Event()

    @classmethod
    def from_config(cls, path: str | Path) -> "TeensyIO":
        config = load_config(path)
        io = cls(
            config.get("port"),
            baudrate=int(config.get("baudrate", 1_000_000)),
            timeout=float(config.get("timeout", 1.0)),
        )
        io._config = config
        return io

    def connect(self) -> "TeensyIO":
        self.transport.open()
        if self.flush_rate_hz:
            self._start_auto_flush()
        return self

    def close(self) -> None:
        self.stop_heartbeat()
        self._stop_auto_flush()
        if self._queued:
            self.flush()
        self.transport.close()

    def ping(self) -> bool:
        return self._command(CommandId.PING) == b"pong"

    def get_info(self) -> dict[str, Any]:
        payload = self._command(CommandId.GET_INFO)
        version = payload[2:].split(b"\x00", 1)[0].decode("ascii", errors="replace")
        return {"digital_pins": payload[0], "counters": payload[1], "version": version}

    def reset_config(self) -> None:
        self._command(CommandId.RESET_CONFIG)

    def heartbeat(self) -> None:
        self._command(CommandId.HEARTBEAT)

    def start_heartbeat(self, rate_hz: float = 20) -> None:
        self.stop_heartbeat()
        self._heartbeat_stop.clear()

        def run() -> None:
            interval = 1.0 / rate_hz
            while not self._heartbeat_stop.wait(interval):
                self.heartbeat()

        self._heartbeat_thread = threading.Thread(target=run, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        self._heartbeat_thread = None

    def emergency_stop(self) -> None:
        self._command(CommandId.EMERGENCY_STOP)

    def clear_emergency_stop(self) -> None:
        self._command(CommandId.CLEAR_EMERGENCY_STOP)

    def pin(self, name: str) -> Pin:
        return self._pins.setdefault(name, Pin(self, name))

    def pwm(self, name: str) -> PwmOutput:
        return self._pwms.setdefault(name, PwmOutput(self, name))

    def analog(self, name: str) -> AnalogInput:
        return self._analogs.setdefault(name, AnalogInput(self, name))

    def counter(self, name: str) -> PulseCounter:
        return self._counters.setdefault(name, PulseCounter(self, name))

    def encoder(self, name: str) -> QuadratureEncoder:
        return self._encoders.setdefault(name, QuadratureEncoder(self, name))

    def load_config(self, path: str | Path) -> None:
        self._config = load_config(path)

    def configure_all(self) -> None:
        for name, spec in self._config.get("pins", {}).items():
            pin_type = spec.get("type")
            if pin_type == "digital_output":
                self.pin(name).configure_output(spec["physical_pin"], initial=spec.get("initial", False))
            elif pin_type == "digital_input":
                self.pin(name).configure_input(
                    spec["physical_pin"],
                    pull=spec.get("pull", "floating"),
                    debounce_us=int(spec.get("debounce_us", 0)),
                )
            elif pin_type == "pwm":
                self.pwm(name).configure(
                    spec["physical_pin"],
                    frequency=int(spec.get("frequency", 1000)),
                    initial_duty=float(spec.get("initial_duty", 0.0)),
                )
            elif pin_type == "analog":
                self.analog(name).configure(spec["physical_pin"], samples=int(spec.get("samples", 1)))
            else:
                raise InvalidModeError(f"unknown pin type for {name}: {pin_type}")

        for name, spec in self._config.get("inputs", {}).items():
            self.pin(name).configure_input(
                spec["physical_pin"],
                pull=spec.get("pull", "floating"),
                debounce_us=int(spec.get("debounce_us", 0)),
            )

        for name, spec in self._config.get("counters", {}).items():
            pin_name = spec.get("pin") or spec.get("input")
            self.counter(name).attach(pin=pin_name, edge=spec.get("edge", "rising"))

    def begin_batch(self) -> None:
        self._batch_depth += 1

    def flush(self) -> None:
        queued = self._queued
        self._queued = []
        for data in queued:
            self.transport.write(data)

    @contextmanager
    def batch(self) -> Iterator[None]:
        self.begin_batch()
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0:
                self.flush()

    def subscribe(self, name: str, rate_hz: float | None = None, on_change: bool = False) -> None:
        raise NotImplementedError("telemetry subscriptions are reserved for the next protocol phase")

    def read_telemetry(self) -> dict[str, Any]:
        raise NotImplementedError("telemetry subscriptions are reserved for the next protocol phase")

    def on_telemetry(self, callback: Any) -> None:
        raise NotImplementedError("telemetry subscriptions are reserved for the next protocol phase")

    def _command(self, command: CommandId, payload: bytes = b"", *, expect_response: bool = True) -> bytes:
        seq = next(self._seq) & 0xFFFF
        packet = Packet(PacketType.COMMAND, seq, bytes([int(command)]) + payload)
        encoded = encode_packet(packet)

        if self._batch_depth or (self.flush_rate_hz and not expect_response):
            self._queued.append(encoded)
            if self.auto_flush and not self.flush_rate_hz and self._batch_depth == 0:
                self.flush()
            return b""

        self.transport.write(encoded)
        if not expect_response:
            return b""
        response = self._read_response(seq)
        if response.type == PacketType.ACK:
            return b""
        if response.type == PacketType.DATA:
            return response.payload
        if response.type == PacketType.NACK:
            code = ErrorCode(response.payload[0]) if response.payload else ErrorCode.INVALID_PAYLOAD
            self._raise_for_error(code)
        raise ProtocolError(f"unexpected response type: {response.type!r}")

    def _read_response(self, seq: int) -> Packet:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            data = self.transport.read(64)
            if not data:
                continue
            for packet in self._decoder.feed(data):
                if packet.seq == seq:
                    return packet
        raise TeensyIOTimeoutError(f"timeout waiting for response seq={seq}")

    def _raise_for_error(self, code: ErrorCode) -> None:
        if code == ErrorCode.INVALID_PIN:
            raise InvalidPinError("invalid pin")
        if code == ErrorCode.INVALID_MODE:
            raise InvalidModeError("invalid mode")
        if code == ErrorCode.EMERGENCY_STOP_ACTIVE:
            raise EmergencyStopActiveError("emergency stop is active")
        raise CommandRejectedError(f"command rejected: {code.name}")

    def _start_auto_flush(self) -> None:
        self._flush_stop.clear()

        def run() -> None:
            interval = 1.0 / float(self.flush_rate_hz)
            while not self._flush_stop.wait(interval):
                if self._queued:
                    self.flush()

        self._flush_thread = threading.Thread(target=run, daemon=True)
        self._flush_thread.start()

    def _stop_auto_flush(self) -> None:
        self._flush_stop.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=1.0)
        self._flush_thread = None

    def _counter_id(self, name: str) -> int:
        if name not in self._counter_ids:
            self._counter_ids[name] = len(self._counter_ids)
        return self._counter_ids[name]

    @staticmethod
    def _u8_duty(duty: float) -> int:
        if duty < 0.0 or duty > 1.0:
            raise ValueError("duty must be between 0.0 and 1.0")
        return int(round(duty * 255))

    @staticmethod
    def _pack_u32(value: int) -> bytes:
        return struct.pack("<I", value)

    @staticmethod
    def _unpack_i32(payload: bytes) -> int:
        return struct.unpack("<i", payload[:4])[0]

    @staticmethod
    def _unpack_u32(payload: bytes) -> int:
        return struct.unpack("<I", payload[:4])[0]
