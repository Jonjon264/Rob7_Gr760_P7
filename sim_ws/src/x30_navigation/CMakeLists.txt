cmake_minimum_required(VERSION 3.8)
project(x30_navigation)

find_package(ament_cmake REQUIRED)

# config/*.yaml, launch/navigation.launch.py, rviz/nav2.rviz, tools/save_map
install(DIRECTORY config launch rviz DESTINATION share/${PROJECT_NAME})
install(PROGRAMS tools/save_map DESTINATION lib/${PROJECT_NAME})

ament_package()
