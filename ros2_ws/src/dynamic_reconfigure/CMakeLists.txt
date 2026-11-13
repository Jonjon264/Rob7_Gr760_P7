cmake_minimum_required(VERSION 3.8)
project(dynamic_reconfigure)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BoolParameter.msg"
  "msg/IntParameter.msg"
  "msg/StrParameter.msg"
  "msg/DoubleParameter.msg"
  "msg/GroupState.msg"
  "msg/Config.msg"
  "msg/ParamDescription.msg"
  "msg/Group.msg"
  "msg/ConfigDescription.msg"
  "msg/SensorLevels.msg"
  "srv/Reconfigure.srv"
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()