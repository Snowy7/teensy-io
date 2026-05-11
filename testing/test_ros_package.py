from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROS = ROOT / "teensy-io-ros"


def test_ros_package_has_typed_interfaces() -> None:
    assert (ROS / "package.xml").exists()
    assert (ROS / "CMakeLists.txt").exists()
    assert (ROS / "msg/TelemetryFrame.msg").exists()
    assert (ROS / "msg/EdgeEvent.msg").exists()
    assert (ROS / "msg/BridgeStatus.msg").exists()
    assert (ROS / "srv/PwmWrite.srv").exists()
    assert (ROS / "srv/EmergencyStop.srv").exists()


def test_ros_bridge_script_is_executable() -> None:
    script = ROS / "scripts/teensy_io_bridge_node"

    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_ros_package_uses_dedicated_interfaces_not_json_string_command_topic() -> None:
    bridge = (ROS / "teensy_io_ros/bridge_node.py").read_text(encoding="utf-8")

    assert "create_service" in bridge
    assert "std_msgs.msg import String" not in bridge
    assert "json.loads" not in bridge
