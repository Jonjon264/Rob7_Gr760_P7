# syntax=docker/dockerfile:1
# ROS 2 Jazzy / Gazebo Harmonic simulator, separate from the Humble workspace.
FROM ros:jazzy-ros-base-noble

ARG DEBIAN_FRONTEND=noninteractive
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG QUADRUPED_REF=5434c5810d1a7fe223bcfd04550e9d3bfdd4b458
ARG BUILD_JOBS=4

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates sudo \
        procps iputils-ping iproute2 \
        python3-colcon-common-extensions python3-rosdep python3-vcstool \
        python3-numpy python3-scipy python3-yaml python3-opencv \
        python3-pil python3-matplotlib python3-pytest \
        libeigen3-dev \
        libgl1 libegl1 libglx-mesa0 libgl1-mesa-dri libegl-mesa0 libgbm1 \
        mesa-utils \
        ros-jazzy-rmw-cyclonedds-cpp \
        ros-jazzy-ros-gz ros-jazzy-gz-ros2-control \
        ros-jazzy-ros2-control ros-jazzy-ros2-controllers \
        ros-jazzy-imu-sensor-broadcaster ros-jazzy-joint-state-publisher \
        ros-jazzy-backward-ros ros-jazzy-kdl-parser \
        ros-jazzy-pluginlib ros-jazzy-realtime-tools \
        ros-jazzy-xacro ros-jazzy-robot-state-publisher \
        ros-jazzy-tf2-ros ros-jazzy-tf2-ros-py ros-jazzy-tf2-tools \
        ros-jazzy-tf2-geometry-msgs ros-jazzy-diagnostic-msgs \
        ros-jazzy-cv-bridge ros-jazzy-sensor-msgs-py \
        ros-jazzy-image-transport ros-jazzy-ros2bag \
        ros-jazzy-rosbag2-storage-default-plugins \
        ros-jazzy-teleop-twist-keyboard \
        ros-jazzy-rviz2 \
        ros-jazzy-rqt ros-jazzy-rqt-common-plugins ros-jazzy-rqt-tf-tree \
    && rm -rf /var/lib/apt/lists/*

# Noble images may already contain the default ubuntu user with UID 1000.
RUN if id ubuntu >/dev/null 2>&1; then userdel -r ubuntu; fi \
    && groupadd --gid "${HOST_GID}" x30 \
    && useradd --uid "${HOST_UID}" --gid "${HOST_GID}" --create-home --shell /bin/bash x30 \
    && usermod -aG video,dialout x30 \
    && echo 'x30 ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/x30 \
    && chmod 0440 /etc/sudoers.d/x30 \
    && mkdir -p /ws/src /ws/build /ws/install /ws/log /x30 /opt/x30_ext/src \
    && chown -R x30:x30 /ws /opt/x30_ext

# The X30 model and locomotion controllers come from the same pinned upstream
# revision as the original simulator. The unused navigation repository is omitted.
COPY --chown=x30:x30 docker/sim/patches/ /opt/x30_ext/patches/
USER x30
WORKDIR /opt/x30_ext
RUN git init src/quadruped_ros2_control \
    && git -C src/quadruped_ros2_control remote add origin https://github.com/legubiao/quadruped_ros2_control.git \
    && git -C src/quadruped_ros2_control fetch --depth 1 origin "${QUADRUPED_REF}" \
    && git -C src/quadruped_ros2_control checkout --detach FETCH_HEAD \
    && git -C src/quadruped_ros2_control apply /opt/x30_ext/patches/unitree_guide_x30.patch \
    && sed -i '/<joint name="imu_joint"/,/<\/joint>/ s#xyz="0 0 0"#xyz="0.13045 -0.001 0.0149"#' \
        src/quadruped_ros2_control/descriptions/deep_robotics/x30_description/xacro/imu_link.xacro \
    && test "$(grep -c '0.13045' src/quadruped_ros2_control/descriptions/deep_robotics/x30_description/xacro/imu_link.xacro)" = 1

SHELL ["/bin/bash", "-c"]
RUN source /opt/ros/jazzy/setup.bash \
    && CMAKE_BUILD_PARALLEL_LEVEL="${BUILD_JOBS}" colcon --log-base /tmp/x30_ext_log build \
        --merge-install --install-base /opt/x30_ext/install --build-base /tmp/x30_ext_build \
        --parallel-workers "${BUILD_JOBS}" \
        --base-paths src/quadruped_ros2_control \
        --packages-up-to control_input_msgs controller_common leg_pd_controller unitree_guide_controller x30_description \
        --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    && rm -rf /tmp/x30_ext_build /tmp/x30_ext_log

USER root

# Desktop dependency for the original on-screen joystick.
RUN python3 -c 'import tkinter' || \
    (apt-get update && apt-get install -y --no-install-recommends python3-tk \
     && rm -rf /var/lib/apt/lists/*)

# Navigation stack (and the PCL libraries FAST-LIO builds against): Nav2 (planner, MPPI controller, costmaps, BT navigator, lifecycle manager),
# its launch files/params (nav2_bringup) and SLAM Toolbox for building the map and the map->odom TF.
# Kept as its own layer after the controller build so adding packages here does not rebuild that.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-navigation2 \
        ros-jazzy-nav2-bringup \
        ros-jazzy-slam-toolbox \
        ros-jazzy-pointcloud-to-laserscan \
        ros-jazzy-pcl-ros ros-jazzy-pcl-conversions libpcl-dev \
    && rm -rf /var/lib/apt/lists/*

# Speech input for the AI task pipeline (qwen_voice_manager). Same approach as docker/main, adapted to Noble:
# Python 3.12 with PEP 668, so the pip packages go into a virtualenv that sees the system packages. A venv installs the
# versions RealtimeSTT pins (scipy, websockets, ...) beside apt's copies instead of trying to uninstall them.
# Its site-packages is put on PYTHONPATH below, so the ROS nodes (system python3) can import it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-venv python3-pip portaudio19-dev libsndfile1 libasound2-plugins pulseaudio-utils libgomp1 alsa-utils \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/voice-venv \
    && /opt/voice-venv/bin/pip install --no-cache-dir \
        torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY sim_ws/src/qwen_voice_manager/requirements-voice.txt sim_ws/src/qwen_voice_manager/constraints-voice.txt /tmp/
RUN /opt/voice-venv/bin/pip install --no-cache-dir -c /tmp/constraints-voice.txt -r /tmp/requirements-voice.txt
# pvporcupine 1.9.5 depends on enum34, a Python 2 backport that shadows the standard library's enum and breaks every
# Python program once this path is active. Remove it, then fail the build early if anything still shadows the
# standard library or if the speech libraries do not import.
RUN /opt/voice-venv/bin/pip uninstall -y enum34
ENV PYTHONPATH=/opt/voice-venv/lib/python3.12/site-packages
RUN python3 -c "import os, sys; names = {n.split('.')[0].split('-')[0] for n in os.listdir('/opt/voice-venv/lib/python3.12/site-packages')}; bad = sorted(names & set(sys.stdlib_module_names)); assert not bad, f'venv shadows the standard library: {bad}'" \
    && python3 -c "import re, enum, openai, pvporcupine, torch, torchaudio, RealtimeSTT; assert torch.__version__.startswith('2.5.1'), torch.__version__; print('voice dependencies OK, torch', torch.__version__)"
RUN printf '%s\n' \
    'pcm.!default { type pulse }' \
    'ctl.!default { type pulse }' \
    > /etc/asound.conf

# Source Jazzy and any simulator overlay for commands and interactive shells.
COPY <<'EOF' /etc/profile.d/x30-sim.sh
source /opt/ros/jazzy/setup.bash
source /opt/x30_ext/install/setup.bash
if [ -f /ws/install/setup.bash ]; then
    source /ws/install/setup.bash
fi
EOF

COPY --chmod=755 <<'EOF' /usr/local/bin/sim-entrypoint
#!/bin/bash
set -e
source /etc/profile.d/x30-sim.sh
exec "$@"
EOF

RUN echo 'source /etc/profile.d/x30-sim.sh' >> /home/x30/.bashrc

COPY --chmod=755 <<'EOF' /usr/local/bin/sim-build
#!/bin/bash
set -eo pipefail
source /etc/profile.d/x30-sim.sh
cd /ws
CMAKE_BUILD_PARALLEL_LEVEL="${X30_BUILD_JOBS:-4}" colcon build --symlink-install --parallel-workers "${X30_BUILD_JOBS:-4}" \
    --packages-up-to x30_msgs x30_worlds x30_sim livox_ros_driver2 fast_lio x30_fastlio x30_navigation \
    interfaces robot_task_handler qwen_voice_manager x30_task_executor \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
EOF

# Headless software rendering supports both cameras and Gazebo gpu_lidar.
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    LIBGL_ALWAYS_SOFTWARE=1 \
    GALLIUM_DRIVER=llvmpipe \
    MESA_LOADER_DRIVER_OVERRIDE=swrast \
    LP_NUM_THREADS=4 \
    PYTHONUNBUFFERED=1 \
    X30_ROOT=/x30 \
    X30_CONFIGS=/x30/configs/sim

USER x30
WORKDIR /ws
COPY --chown=x30:x30 sim_ws/src/ /ws/src/
# Resolve every package.xml dependency with rosdep. Packages built into /opt/x30_ext are skipped.
RUN sudo rosdep init 2>/dev/null || true
RUN rosdep update --rosdistro jazzy \
    && sudo apt-get update \
    && rosdep install --from-paths src --ignore-src -y --rosdistro jazzy \
        --skip-keys "ament_python x30_description unitree_guide_controller leg_pd_controller controller_common control_input_msgs" \
    && sudo rm -rf /var/lib/apt/lists/*
COPY --chown=x30:x30 configs/sim/ /x30/configs/sim/
RUN X30_BUILD_JOBS="${BUILD_JOBS}" sim-build
ENTRYPOINT ["/usr/local/bin/sim-entrypoint"]
CMD ["bash"]
