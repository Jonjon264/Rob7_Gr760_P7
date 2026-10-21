FROM ros:foxy-ros1-bridge

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        python3-colcon-common-extensions \
        ros-noetic-ros-comm \
        ros-noetic-catkin \
        ros-noetic-message-generation \
        ros-noetic-message-runtime \
        ros-noetic-std-msgs \
        ros-foxy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Pull the .msg files from upstream (pin a tag/commit if you want reproducibility)
RUN git clone --depth 1 https://github.com/Livox-SDK/livox_ros_driver2.git /tmp/livox


# ---- ROS 1 workspace (messages only) ----
COPY docker/bridge/livox_msgs/ros1/ /ros1_ws/src/livox_ros_driver2/
RUN mkdir -p /ros1_ws/src/livox_ros_driver2/msg \
    && cp /tmp/livox/msg/CustomMsg.msg /tmp/livox/msg/CustomPoint.msg \
          /ros1_ws/src/livox_ros_driver2/msg/ \
    && source /opt/ros/noetic/setup.bash \
    && cd /ros1_ws && catkin_make

# ---- ROS 2 workspace (messages only, built WITHOUT ROS 1 sourced) ----
COPY docker/bridge/livox_msgs/ros2/ /ros2_ws/src/livox_ros_driver2/
RUN mkdir -p /ros2_ws/src/livox_ros_driver2/msg \
    && cp /tmp/livox/msg/CustomMsg.msg /tmp/livox/msg/CustomPoint.msg \
          /ros2_ws/src/livox_ros_driver2/msg/ \
    && source /opt/ros/foxy/setup.bash \
    && cd /ros2_ws && colcon build --packages-select livox_ros_driver2


# ---- Rebuild ros1_bridge from source against both ----
RUN git clone --depth 1 -b foxy https://github.com/ros2/ros1_bridge.git /ros2_ws/src/ros1_bridge
RUN source /opt/ros/noetic/setup.bash \
    && source /ros1_ws/devel/setup.bash \
    && source /opt/ros/foxy/setup.bash \
    && source /ros2_ws/install/setup.bash \
    && cd /ros2_ws \
    && colcon build --packages-select ros1_bridge \
        --cmake-force-configure 

# Set the RMW implementation
RUN echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /root/.bashrc 

CMD ["bash"]