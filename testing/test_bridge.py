from __future__ import annotations

import json

from teensy_io import TeensyIO
from teensy_io.ros.bridge_node import TeensyIOBridge
from testing.fakes import ScriptedTransport


class FakeMsg:
    def __init__(self) -> None:
        self.data = ""


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[FakeMsg] = []

    def publish(self, msg: FakeMsg) -> None:
        self.messages.append(msg)


class FakeNode:
    def __init__(self) -> None:
        self.publishers: dict[str, FakePublisher] = {}
        self.subscription = None

    def create_publisher(self, msg_type, topic: str, qos: int) -> FakePublisher:
        del msg_type, qos
        publisher = FakePublisher()
        self.publishers[topic] = publisher
        return publisher

    def create_subscription(self, msg_type, topic: str, callback, qos: int):
        del msg_type, topic, qos
        self.subscription = callback
        return callback

    def create_timer(self, interval: float, callback):
        del interval
        return callback


def test_bridge_dispatches_json_commands(monkeypatch) -> None:
    import sys
    import types

    std_msgs = types.ModuleType("std_msgs")
    msg_module = types.ModuleType("std_msgs.msg")
    msg_module.String = FakeMsg
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", msg_module)

    node = FakeNode()
    io = TeensyIO(transport=ScriptedTransport()).connect()
    io.pin("led").configure_output(13)
    bridge = TeensyIOBridge(node, io)

    msg = FakeMsg()
    msg.data = json.dumps({"op": "digital_write", "name": "led", "value": True})
    bridge._on_command(msg)

    status = json.loads(node.publishers["teensy_io/status"].messages[-1].data)
    assert status == {"ok": True, "result": None}
