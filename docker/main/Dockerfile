FROM ros:humble-ros-base-jammy

# Install useful dev tools
RUN apt update && \
    apt install -y software-properties-common && \
    add-apt-repository universe && \
    apt update && \
    apt install -y \
    	python3-colcon-common-extensions \
    	python3-rosdep \
	    iputils-ping \
	    net-tools \
    	nano \
    	cmake \
        python3-pip \
        python3-dev \
        build-essential \
        portaudio19-dev \
        libportaudio2 \
        libsndfile1 \
        libasound2-plugins \
        pulseaudio-utils \
        libgomp1 \
        alsa-utils \
    	libpcl-dev \
        libeigen3-dev \
    	ros-humble-pcl-conversions \
        ros-humble-pcl-msgs \
        ros-humble-pcl-ros \
	    ros-humble-tf2-ros \
	    ros-humble-tf2-eigen \
	    ros-humble-rviz2 \
        ros-humble-teleop-twist-keyboard \
        ros-humble-bondcpp \
        ros-humble-test-msgs \
        ros-humble-rmw-cyclonedds-cpp \
    	wget \
    && rm -rf /var/lib/apt/lists/*


# Voice dependencies (Raspberry Pi stack, see requirements-voice.txt).
COPY ros2_ws/src/qwen_voice_manager/requirements-voice.txt /tmp/requirements-voice.txt

RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-voice.txt \
    # openWakeWord goes in without deps: it declares tflite-runtime, which we do not use.
    && python3 -m pip install --no-cache-dir --no-deps openwakeword==0.6.0 \
    # Fetch the wake-word and VAD models now, so the robot needs no internet at first start.
    && python3 -c "import openwakeword; openwakeword.utils.download_models()"

# Route ALSA applications through the host audio server.
RUN printf '%s\n' \
    'pcm.!default { type pulse }' \
    'ctl.!default { type pulse }' \
    > /etc/asound.conf
# Initialize rosdep
RUN rosdep init || true
RUN rosdep update

# Copy only package manifests so rosdep can resolve dependencies
# COPY ros2_ws/src /tmp/ws/src
# WORKDIR /tmp/ws

# # # Install all ROS dependencies from package.xml files
# RUN apt-get update && \
#     rosdep install --from-paths src --ignore-src -r -y\
#     --from-paths ./src \
#     --ignore-src \
#     --skip-keys="gazebo_ros gazebo_ros_pkgs"

# # Clean up (since you'll mount the real workspace at runtime)
# RUN rm -rf /tmp/ws

# Auto-source ROS
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
RUN echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc
# Set the RMW implementation
RUN echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /root/.bashrc 
#RUN echo "export CYCLONEDDS_URI="file:///root/cyclone_iface.xml,file:///root/ros2_ws/install/main_bringup/share/main_bringup/config/cyclonedds.xml"" >> /root/.bashrc 

WORKDIR /root/ros2_ws

CMD ["bash"]
