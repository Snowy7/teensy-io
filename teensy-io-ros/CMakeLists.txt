cmake_minimum_required(VERSION 3.8)
project(teensy_io_ros)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TelemetryFrame.msg"
  "msg/EdgeEvent.msg"
  "msg/BridgeStatus.msg"
  "srv/DigitalRead.srv"
  "srv/DigitalWrite.srv"
  "srv/PwmWrite.srv"
  "srv/CounterRead.srv"
  "srv/CounterReset.srv"
  "srv/AnalogRead.srv"
  "srv/EncoderRead.srv"
  "srv/EncoderReset.srv"
  "srv/Subscribe.srv"
  "srv/EmergencyStop.srv"
  DEPENDENCIES builtin_interfaces
)

ament_python_install_package(teensy_io_ros)

install(PROGRAMS
  scripts/teensy_io_bridge_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
