cmake_minimum_required(VERSION 3.5)
project(move_base_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(actionlib_msgs REQUIRED)

file(GLOB MSGS RELATIVE ${PROJECT_SOURCE_DIR} "msg/*.msg")

rosidl_generate_interfaces(${PROJECT_NAME}
  ${MSGS}
  DEPENDENCIES std_msgs geometry_msgs actionlib_msgs
)

ament_package()