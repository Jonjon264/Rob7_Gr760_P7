cmake_minimum_required(VERSION 3.8)
project(move_base_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GoalID.msg"
  "msg/MoveBaseGoal.msg"
  "msg/MoveBaseActionGoal.msg"
  "msg/GoalStatus.msg"
  "msg/MoveBaseResult.msg"
  "msg/MoveBaseActionResult.msg"
  DEPENDENCIES std_msgs geometry_msgs builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()