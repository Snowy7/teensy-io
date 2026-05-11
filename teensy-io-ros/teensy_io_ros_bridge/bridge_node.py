from __future__ import annotations

from typing import Any, Callable

from teensy_io import TeensyIO
from teensy_io.protocol.commands import ResourceKind


class TeensyIORosBridge:
    def __init__(self, node: Any, io: TeensyIO) -> None:
        self.node = node
        self.io = io
        self.info: dict[str, Any] = {}
        self.name_by_ref: dict[tuple[ResourceKind, int], str] = {}

        from teensy_io_ros.msg import BridgeStatus, EdgeEvent, TelemetryFrame
        from teensy_io_ros.srv import (
            AnalogRead,
            CounterRead,
            CounterReset,
            DigitalRead,
            DigitalWrite,
            EmergencyStop,
            EncoderRead,
            EncoderReset,
            I2cRead,
            I2cWrite,
            PwmWrite,
            DacWrite,
            Subscribe,
        )

        self.BridgeStatus = BridgeStatus
        self.EdgeEvent = EdgeEvent
        self.TelemetryFrame = TelemetryFrame

        self.telemetry_pub = node.create_publisher(TelemetryFrame, "teensy_io/telemetry", 50)
        self.events_pub = node.create_publisher(EdgeEvent, "teensy_io/events", 50)
        self.status_pub = node.create_publisher(BridgeStatus, "teensy_io/status", 5)

        self._service(DigitalRead, "teensy_io/digital_read", self._digital_read)
        self._service(DigitalWrite, "teensy_io/digital_write", self._digital_write)
        self._service(PwmWrite, "teensy_io/pwm_write", self._pwm_write)
        self._service(CounterRead, "teensy_io/counter_read", self._counter_read)
        self._service(CounterReset, "teensy_io/counter_reset", self._counter_reset)
        self._service(AnalogRead, "teensy_io/analog_read", self._analog_read)
        self._service(EncoderRead, "teensy_io/encoder_read", self._encoder_read)
        self._service(EncoderReset, "teensy_io/encoder_reset", self._encoder_reset)
        self._service(I2cWrite, "teensy_io/i2c_write", self._i2c_write)
        self._service(I2cRead, "teensy_io/i2c_read", self._i2c_read)
        self._service(DacWrite, "teensy_io/dac_write", self._dac_write)
        self._service(Subscribe, "teensy_io/subscribe", self._subscribe)
        self._service(EmergencyStop, "teensy_io/emergency_stop", self._emergency_stop)

        self.max_publish_per_poll = 1000
        self.poll_timer = node.create_timer(0.001, self._poll)
        self.status_timer = node.create_timer(1.0, self.publish_status)

    def configure_names(self) -> None:
        for name in list(self.io._pins) + list(self.io._analogs) + list(self.io._counters) + list(self.io._encoders):
            try:
                self.name_by_ref[self.io._resource_ref(name)] = name
            except KeyError:
                pass

    def publish_status(self) -> None:
        msg = self.BridgeStatus()
        msg.stamp = self.node.get_clock().now().to_msg()
        msg.connected = self.io.transport.is_open
        msg.emergency_stop_active = False
        msg.telemetry_dropped = int(self.io.telemetry_dropped)
        msg.events_dropped = int(self.io.events_dropped)
        msg.firmware_version = str(self.info.get("version", ""))
        msg.message = "ok"
        self.status_pub.publish(msg)

    def _service(self, service_type: Any, name: str, callback: Callable[[Any, Any], Any]) -> None:
        self.node.create_service(service_type, name, callback)

    def _ok(self, response: Any) -> Any:
        response.ok = True
        response.error = ""
        return response

    def _fail(self, response: Any, exc: Exception) -> Any:
        response.ok = False
        response.error = f"{type(exc).__name__}: {exc}"
        return response

    def _digital_read(self, request: Any, response: Any) -> Any:
        try:
            response.value = self.io.pin(request.name).read()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _digital_write(self, request: Any, response: Any) -> Any:
        try:
            self.io.pin(request.name).write(request.value)
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _pwm_write(self, request: Any, response: Any) -> Any:
        try:
            self.io.pwm(request.name).write(request.duty)
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _counter_read(self, request: Any, response: Any) -> Any:
        try:
            counter = self.io.counter(request.name)
            response.count = counter.read()
            response.frequency_hz = counter.frequency()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _counter_reset(self, request: Any, response: Any) -> Any:
        try:
            self.io.counter(request.name).reset()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _analog_read(self, request: Any, response: Any) -> Any:
        try:
            analog = self.io.analog(request.name)
            response.raw = analog.read_raw()
            response.normalized = analog.read_normalized()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _encoder_read(self, request: Any, response: Any) -> Any:
        try:
            response.position = self.io.encoder(request.name).read()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _encoder_reset(self, request: Any, response: Any) -> Any:
        try:
            self.io.encoder(request.name).reset()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _i2c_write(self, request: Any, response: Any) -> Any:
        try:
            self.io.i2c_bus(request.bus).write(request.address, bytes(request.data))
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _i2c_read(self, request: Any, response: Any) -> Any:
        try:
            response.data = list(self.io.i2c_bus(request.bus).read(request.address, request.length))
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _dac_write(self, request: Any, response: Any) -> Any:
        try:
            dac = self.io.dac(request.name)
            if request.use_normalized:
                dac.write_normalized(request.normalized, channel=request.channel)
            else:
                dac.write_raw(request.raw, channel=request.channel)
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _subscribe(self, request: Any, response: Any) -> Any:
        try:
            self.io.subscribe(request.name, rate_hz=request.rate_hz, on_change=request.on_change)
            self.configure_names()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _emergency_stop(self, request: Any, response: Any) -> Any:
        try:
            if request.active:
                self.io.emergency_stop()
            else:
                self.io.clear_emergency_stop()
            return self._ok(response)
        except Exception as exc:
            return self._fail(response, exc)

    def _poll(self) -> None:
        self.io._poll_async_packets(timeout=0.0)
        published = 0
        while True:
            if published >= self.max_publish_per_poll:
                break
            try:
                frame = self.io._telemetry_queue.get_nowait()
            except Exception:
                break
            msg = self.TelemetryFrame()
            msg.stamp = self.node.get_clock().now().to_msg()
            msg.name = self.name_by_ref.get((frame.kind, frame.resource_id), "")
            msg.kind = int(frame.kind)
            msg.resource_id = frame.resource_id
            msg.value = frame.value
            msg.value_float = float(frame.value)
            self.telemetry_pub.publish(msg)
            published += 1
        published = 0
        while True:
            if published >= self.max_publish_per_poll:
                break
            try:
                event = self.io._event_queue.get_nowait()
            except Exception:
                break
            msg = self.EdgeEvent()
            msg.stamp = self.node.get_clock().now().to_msg()
            msg.name = self.name_by_ref.get((event.kind, event.resource_id), "")
            msg.kind = int(event.kind)
            msg.resource_id = event.resource_id
            msg.value = event.value
            msg.firmware_timestamp_us = event.timestamp_us
            self.events_pub.publish(msg)
            published += 1


def main() -> None:
    import rclpy

    rclpy.init()
    node = rclpy.create_node("teensy_io_bridge")
    port = node.declare_parameter("port", "/dev/ttyACM0").value
    baudrate = int(node.declare_parameter("baudrate", 1_000_000).value)
    config = node.declare_parameter("config", "").value
    heartbeat_hz = float(node.declare_parameter("heartbeat_hz", 20.0).value)

    client_options = {"telemetry_max_frames": 32768, "event_max_frames": 32768}
    io = TeensyIO.from_config(config, **client_options) if config else TeensyIO(port, baudrate=baudrate, **client_options)
    io.connect()
    if config:
        io.configure_all()
    if heartbeat_hz > 0:
        io.start_heartbeat(heartbeat_hz)

    bridge = TeensyIORosBridge(node, io)
    bridge.info = io.get_info()
    bridge.configure_names()
    bridge.publish_status()

    try:
        rclpy.spin(node)
    finally:
        io.close()
        node.destroy_node()
        rclpy.shutdown()
