FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-lc"]

# 1. Install dependencies and ROS packages
RUN apt-get update && apt-get install -y \
    git build-essential cmake pkg-config \
    python3-colcon-common-extensions \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    libjpeg-dev libpng-dev libtiff-dev \
    liblttng-ust1 liblttng-ust-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Set ROS environment
ENV ROS_DISTRO=humble
WORKDIR /ros2_ws/src

# 3. Clone camera_ros (libcamera ROS driver)
RUN git clone --depth 1 https://github.com/christianrauch/camera_ros.git

# 4. Build workspace at runtime to ensure host libcamera is visible
WORKDIR /ros2_ws

# 5. Environment to link host libcamera
ENV PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 6. Default command
# Uses a params file that you will mount from host (camera_params.yaml)
CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    if [ ! -d /ros2_ws/install ]; then colcon build --merge-install; fi && \
    source /ros2_ws/install/setup.bash && \
    ros2 run camera_ros camera_node --ros-args --params-file /camera_params.yaml



