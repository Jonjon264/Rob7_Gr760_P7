cmake_minimum_required(VERSION 3.8)
project(interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)          # <-- needed
find_package(geometry_msgs REQUIRED)     # if you use it as well

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Waypoint.msg"
  "msg/CustomGoal.msg"
  "msg/GoalArray.msg"
  "msg/CustomTeach.msg"
  DEPENDENCIES std_msgs geometry_msgs builtin_interfaces
)

ament_package()
