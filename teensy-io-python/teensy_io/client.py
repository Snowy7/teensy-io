from __future__ import annotations

import itertools
import queue
import struct
import threading
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .config.loader import load_config
from .protocol.commands import CommandId, ErrorCode, PacketType, ResourceKind
from .protocol.errors import (
    CommandRejectedError,
    EmergencyStopActiveError,
    InvalidModeError,
    InvalidPinError,
    ProtocolError,
    QueueFullError,
    TeensyIOTimeoutError,
)
from .protocol.frames import EdgeEvent, TelemetryFrame
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
        queue_max_bytes: int | None = None,
        flush_chunk_size: int = 65536,
        telemetry_max_frames: int = 4096,
        event_max_frames: int = 4096,
    ) -> None:
        if transport is None and port is None:
            raise ValueError("port or transport is required")
        self.transport = transport or SerialTransport(port or "", baudrate=baudrate)
        self.timeout = timeout
        self.auto_flush = auto_flush
        self.flush_rate_hz = flush_rate_hz
        self.queue_max_bytes = queue_max_bytes
        self.flush_chunk_size = flush_chunk_size
        self._decoder = PacketDecoder()
        self._seq = itertools.count(1)
        self._lock = threading.RLock()
        self._batch_depth = 0
        self._queued: deque[bytes] = deque()
        self._queued_bytes = 0
        self._pins: dict[str, Pin] = {}
        self._pwms: dict[str, PwmOutput] = {}
        self._analogs: dict[str, AnalogInput] = {}
        self._counters: dict[str, PulseCounter] = {}
        self._encoders: dict[str, QuadratureEncoder] = {}
        self._counter_ids: dict[str, int] = {}
        self._encoder_ids: dict[str, int] = {}
        self._config: dict[str, Any] = {}
        self._telemetry_queue: "queue.Queue[TelemetryFrame]" = queue.Queue(maxsize=telemetry_max_frames)
        self._event_queue: "queue.Queue[EdgeEvent]" = queue.Queue(maxsize=event_max_frames)
        self.telemetry_dropped = 0
        self.events_dropped = 0
        self._telemetry_callbacks: list[Callable[[TelemetryFrame], None]] = []
        self._edge_callbacks: dict[tuple[ResourceKind, int], list[Callable[[EdgeEvent], None]]] = {}
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._flush_thread: threading.Thread | None = None
        self._flush_stop = threading.Event()

    @property
    def queued_packet_count(self) -> int:
        with self._lock:
            return len(self._queued)

    @property
    def queued_byte_count(self) -> int:
        with self._lock:
            return self._queued_bytes

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
        if self.queued_packet_count:
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

        for name, spec in self._config.get("encoders", {}).items():
            self.encoder(name).attach(spec["pin_a"], spec["pin_b"], mode=spec.get("mode", "x4"))

    def begin_batch(self) -> None:
        with self._lock:
            self._batch_depth += 1

    def flush(self) -> None:
        while True:
            with self._lock:
                if not self._queued:
                    return
                chunk = bytearray()
                while self._queued and len(chunk) + len(self._queued[0]) <= self.flush_chunk_size:
                    item = self._queued.popleft()
                    chunk.extend(item)
                    self._queued_bytes -= len(item)
                if not chunk and self._queued:
                    item = self._queued.popleft()
                    chunk.extend(item)
                    self._queued_bytes -= len(item)
            self.transport.write(bytes(chunk))

    @contextmanager
    def batch(self) -> Iterator[None]:
        self.begin_batch()
        try:
            yield
        finally:
            with self._lock:
                self._batch_depth -= 1
                should_flush = self._batch_depth == 0
            if should_flush:
                self.flush()

    def subscribe(self, name: str, rate_hz: float | None = None, on_change: bool = False) -> None:
        kind, resource_id = self._resource_ref(name)
        hz = 0 if rate_hz is None else int(rate_hz)
        flags = 1 if on_change else 0
        self._command(CommandId.SUBSCRIBE, bytes([int(kind), resource_id]) + struct.pack("<H", hz) + bytes([flags]))

    def unsubscribe(self, name: str) -> None:
        kind, resource_id = self._resource_ref(name)
        self._command(CommandId.UNSUBSCRIBE, bytes([int(kind), resource_id]))

    def read_telemetry(self, timeout: float | None = None) -> TelemetryFrame:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                return self._telemetry_queue.get_nowait()
            except queue.Empty:
                self._poll_async_packets(timeout=0.01)
            if deadline is not None and time.monotonic() >= deadline:
                raise TeensyIOTimeoutError("timeout waiting for telemetry")

    def read_event(self, timeout: float | None = None) -> EdgeEvent:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                return self._event_queue.get_nowait()
            except queue.Empty:
                self._poll_async_packets(timeout=0.01)
            if deadline is not None and time.monotonic() >= deadline:
                raise TeensyIOTimeoutError("timeout waiting for event")

    def on_telemetry(self, callback: Callable[[TelemetryFrame], None]) -> None:
        self._telemetry_callbacks.append(callback)

    def _command(self, command: CommandId, payload: bytes = b"", *, expect_response: bool = True) -> bytes:
        seq = next(self._seq) & 0xFFFF
        packet = Packet(PacketType.COMMAND, seq, bytes([int(command)]) + payload)
        encoded = encode_packet(packet)

        with self._lock:
            should_queue = self._batch_depth > 0 or (self.flush_rate_hz is not None and not expect_response)

        if should_queue:
            self._queue_packet(encoded)
            with self._lock:
                should_flush = self.auto_flush and not self.flush_rate_hz and self._batch_depth == 0
            if should_flush:
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
                self._handle_async_packet(packet)
        raise TeensyIOTimeoutError(f"timeout waiting for response seq={seq}")

    def _poll_async_packets(self, timeout: float = 0.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            data = self.transport.read(64)
            if data:
                for packet in self._decoder.feed(data):
                    self._handle_async_packet(packet)
                return
            if timeout <= 0 or time.monotonic() >= deadline:
                return

    def _queue_packet(self, encoded: bytes) -> None:
        with self._lock:
            next_size = self._queued_bytes + len(encoded)
            if self.queue_max_bytes is not None and next_size > self.queue_max_bytes:
                raise QueueFullError(
                    f"queued command bytes would exceed limit: {next_size} > {self.queue_max_bytes}"
                )
            self._queued.append(encoded)
            self._queued_bytes = next_size

    def _handle_async_packet(self, packet: Packet) -> None:
        if packet.type == PacketType.TELEMETRY and len(packet.payload) >= 6:
            try:
                kind = ResourceKind(packet.payload[0])
            except ValueError:
                return
            frame = TelemetryFrame(
                kind,
                packet.payload[1],
                self._unpack_i32(packet.payload[2:6]),
            )
            self._put_bounded(self._telemetry_queue, frame, "telemetry")
            for callback in list(self._telemetry_callbacks):
                callback(frame)
        elif packet.type == PacketType.EVENT and len(packet.payload) >= 10:
            try:
                kind = ResourceKind(packet.payload[0])
            except ValueError:
                return
            event = EdgeEvent(
                kind,
                packet.payload[1],
                self._unpack_i32(packet.payload[2:6]),
                self._unpack_u32(packet.payload[6:10]),
            )
            self._put_bounded(self._event_queue, event, "event")
            for callback in list(self._edge_callbacks.get((event.kind, event.resource_id), [])):
                callback(event)

    def _put_bounded(self, target: queue.Queue[Any], item: Any, kind: str) -> None:
        try:
            target.put_nowait(item)
            return
        except queue.Full:
            try:
                target.get_nowait()
            except queue.Empty:
                pass
            if kind == "telemetry":
                self.telemetry_dropped += 1
            else:
                self.events_dropped += 1
            target.put_nowait(item)

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

    def _encoder_id(self, name: str) -> int:
        if name not in self._encoder_ids:
            self._encoder_ids[name] = len(self._encoder_ids)
        return self._encoder_ids[name]

    def _resource_ref(self, name: str) -> tuple[ResourceKind, int]:
        if name in self._pins and self._pins[name].physical_pin is not None:
            return ResourceKind.DIGITAL, self._pins[name].physical_pin
        if name in self._analogs and self._analogs[name].physical_pin is not None:
            return ResourceKind.ANALOG, self._analogs[name].physical_pin
        if name in self._counters and self._counters[name].id is not None:
            return ResourceKind.COUNTER, self._counters[name].id
        if name in self._encoders and self._encoders[name].id is not None:
            return ResourceKind.ENCODER, self._encoders[name].id
        raise KeyError(f"unknown or unconfigured resource: {name}")

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
