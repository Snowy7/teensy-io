from __future__ import annotations

import json
from typing import Any

from teensy_io import TeensyIO


class TeensyIOBridge:
    def __init__(self, node: Any, io: TeensyIO) -> None:
        self.node = node
        self.io = io

        from std_msgs.msg import String

        self._string_type = String
        self.telemetry_pub = node.create_publisher(String, "teensy_io/telemetry", 10)
        self.events_pub = node.create_publisher(String, "teensy_io/events", 10)
        self.status_pub = node.create_publisher(String, "teensy_io/status", 10)
        self.command_sub = node.create_subscription(String, "teensy_io/commands", self._on_command, 10)
        self.poll_timer = node.create_timer(0.01, self._poll)

    def publish_status(self) -> None:
        self.status_pub.publish(self._message({"connected": self.io.transport.is_open, "info": self.io.get_info()}))

    def _on_command(self, msg: Any) -> None:
        try:
            command = json.loads(msg.data)
            result = self._dispatch(command)
            self.status_pub.publish(self._message({"ok": True, "result": result}))
        except Exception as exc:
            self.status_pub.publish(self._message({"ok": False, "error": type(exc).__name__, "message": str(exc)}))

    def _dispatch(self, command: dict[str, Any]) -> Any:
        op = command.get("op")
        if op == "digital_write":
            self.io.pin(command["name"]).write(bool(command["value"]))
            return None
        if op == "digital_read":
            return self.io.pin(command["name"]).read()
        if op == "pwm_write":
            self.io.pwm(command["name"]).write(float(command["duty"]))
            return None
        if op == "counter_read":
            return self.io.counter(command["name"]).read()
        if op == "counter_reset":
            self.io.counter(command["name"]).reset()
            return None
        if op == "analog_read_raw":
            return self.io.analog(command["name"]).read_raw()
        if op == "analog_read_normalized":
            return self.io.analog(command["name"]).read_normalized()
        if op == "encoder_read":
            return self.io.encoder(command["name"]).read()
        if op == "encoder_reset":
            self.io.encoder(command["name"]).reset()
            return None
        if op == "subscribe":
            self.io.subscribe(command["name"], rate_hz=command.get("rate_hz"), on_change=bool(command.get("on_change", False)))
            return None
        if op == "emergency_stop":
            self.io.emergency_stop()
            return None
        if op == "clear_emergency_stop":
            self.io.clear_emergency_stop()
            return None
        if op == "heartbeat":
            self.io.heartbeat()
            return None
        raise ValueError(f"unknown bridge command: {op}")

    def _poll(self) -> None:
        self.io._poll_async_packets(timeout=0.0)
        while True:
            try:
                frame = self.io._telemetry_queue.get_nowait()
            except Exception:
                break
            self.telemetry_pub.publish(
                self._message({"kind": frame.kind.name.lower(), "id": frame.resource_id, "value": frame.value})
            )
        while True:
            try:
                event = self.io._event_queue.get_nowait()
            except Exception:
                break
            self.events_pub.publish(
                self._message(
                    {
                        "kind": event.kind.name.lower(),
                        "id": event.resource_id,
                        "value": event.value,
                        "timestamp_us": event.timestamp_us,
                    }
                )
            )

    def _message(self, payload: dict[str, Any]) -> Any:
        msg = self._string_type()
        msg.data = json.dumps(payload, separators=(",", ":"))
        return msg


def main() -> None:
    try:
        import rclpy
    except ModuleNotFoundError as exc:
        raise SystemExit("rclpy is required to run the Teensy IO ROS2 bridge on Jetson") from exc

    rclpy.init()
    node = rclpy.create_node("teensy_io_bridge")
    port = node.declare_parameter("port", "/dev/ttyACM0").value
    baudrate = int(node.declare_parameter("baudrate", 1_000_000).value)
    config = node.declare_parameter("config", "").value
    heartbeat_hz = float(node.declare_parameter("heartbeat_hz", 20.0).value)

    io = TeensyIO.from_config(config) if config else TeensyIO(port, baudrate=baudrate)
    io.connect()
    if config:
        io.configure_all()
    if heartbeat_hz > 0:
        io.start_heartbeat(heartbeat_hz)

    bridge = TeensyIOBridge(node, io)
    bridge.publish_status()
    try:
        rclpy.spin(node)
    finally:
        io.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
